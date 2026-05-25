"""Semantic edge generation and query verification for ASIP."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol, Tuple

from .config_values import expand_extra_headers
from .graph_schema import ALLOWED_PRODUCT_RELATIONS
from .limits import load_workbench_limits

PRODUCT_RELATION_PROMPT = ", ".join(sorted(ALLOWED_PRODUCT_RELATIONS))


@dataclass(frozen=True)
class EdgeModelConfig:
    preferred: str
    fallback: str
    provider: str = "ollama"
    api_base_url: str = "http://localhost:11434"
    api_path: str = ""
    extra_headers: Dict[str, str] = field(default_factory=dict)
    format: str = "json"
    num_ctx: int = 8192
    num_predict: int = 512
    temperature: float = 0
    keep_alive: str = "0s"
    think: bool = False
    timeout_seconds: int = 600


@dataclass(frozen=True)
class EdgeRepoConfig:
    url: str
    default_source_root: str


@dataclass(frozen=True)
class EdgeCase:
    id: str
    question: str
    path: str
    start: int
    end: int
    expected_terms: List[str]


@dataclass(frozen=True)
class EdgeCaseConfig:
    name: str
    repo: EdgeRepoConfig
    model: EdgeModelConfig
    cases: List[EdgeCase]


@dataclass(frozen=True)
class FullCorpusSubfolder:
    relative_root: str = ""
    include: List[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.include is None:
            object.__setattr__(self, "include", ["**/*.c", "**/*.h"])


@dataclass(frozen=True)
class FullCorpus:
    id: str
    repo: str
    default_source_root: str
    relative_root: str = ""
    include: List[str] = None  # type: ignore[assignment]
    subfolders: List[FullCorpusSubfolder] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.include is None:
            object.__setattr__(self, "include", ["**/*.c", "**/*.h"])
        if self.subfolders is None:
            object.__setattr__(self, "subfolders", [])


def normalize_corpus_relative_root(relative_root: Any, *, allow_empty: bool = True) -> str:
    text = str(relative_root or "").strip().replace("\\", "/")
    if text in {"", "."}:
        if allow_empty:
            return ""
        raise ValueError("corpus subfolder must be a repo-relative path")
    if text.startswith("~"):
        raise ValueError(f"corpus subfolder must be repo-relative: {text}")
    path = PurePosixPath(text)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts) or ":" in text:
        raise ValueError(f"corpus subfolder must be repo-relative: {text}")
    return str(path)


@dataclass(frozen=True)
class FullCorpusQuery:
    id: str
    corpus: str
    question: str
    terms: List[str]
    expected_terms: List[str]
    max_snippets: int = 2
    context_before: int = 3
    context_after: int = 5


@dataclass(frozen=True)
class FullCorpusEdgeConfig:
    name: str
    model: EdgeModelConfig
    corpora: List[FullCorpus]
    queries: List[FullCorpusQuery]


class EdgeProvider(Protocol):
    def generate(self, prompt: str, model: EdgeModelConfig) -> Dict[str, Any]:
        """Generate semantic edges from a prompt."""


class FakeEdgeProvider:
    """Deterministic provider for tests."""

    def generate(self, prompt: str, model: EdgeModelConfig) -> Dict[str, Any]:
        cases: List[Dict[str, Any]] = []
        current_id: Optional[str] = None
        terms: List[str] = []
        for line in prompt.splitlines():
            if line.startswith("CASE "):
                if current_id:
                    cases.append(_fake_case(current_id, terms))
                current_id = line.split(" ", 1)[1].strip()
                terms = []
            elif line.startswith("TERMS:"):
                terms.extend(_extract_identifiers(line.split(":", 1)[1]))
            elif _looks_like_source_line(line):
                terms.extend(_extract_identifiers(line.split(":", 1)[1]))
        if current_id:
            cases.append(_fake_case(current_id, terms))
        return {"cases": cases}


class OllamaEdgeProvider:
    """Ollama HTTP provider for semantic edge generation."""

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url.rstrip("/")
        self.attempted_models: List[str] = []

    def generate(self, prompt: str, model: EdgeModelConfig) -> Dict[str, Any]:
        model_names = [model.preferred]
        if model.fallback and model.fallback not in model_names:
            model_names.append(model.fallback)
        errors: List[str] = []
        for model_name in model_names:
            try:
                if model_name not in self.attempted_models:
                    self.attempted_models.append(model_name)
                return self._generate_with_model(prompt, model, model_name)
            except Exception as exc:  # pragma: no cover - exercised by tests through fallback
                errors.append(f"{model_name}: {exc}")
                if model_name == model_names[-1]:
                    raise RuntimeError("Ollama edge generation failed: " + "; ".join(errors)) from exc
        return {"cases": []}

    def cleanup_model_names(self, model: EdgeModelConfig) -> List[str]:
        return self.attempted_models or [model.preferred]

    def _generate_with_model(self, prompt: str, model: EdgeModelConfig, model_name: str) -> Dict[str, Any]:
        body = {
            "model": model_name,
            "stream": False,
            "format": model.format,
            "think": model.think,
            "keep_alive": model.keep_alive,
            "options": {
                "num_ctx": model.num_ctx,
                "num_predict": model.num_predict,
                "temperature": model.temperature,
            },
            "messages": _edge_messages(prompt),
        }
        request = urllib.request.Request(
            _request_url(model, self.base_url, "/api/chat"),
            data=json.dumps(body).encode("utf-8"),
            headers=_request_headers(model),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=model.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        return parse_ollama_json_message(data)


class OllamaDocNodeProvider(OllamaEdgeProvider):
    """Ollama HTTP provider for BoxMatrix-style document node extraction."""

    def _generate_with_model(self, prompt: str, model: EdgeModelConfig, model_name: str) -> Dict[str, Any]:
        body = {
            "model": model_name,
            "stream": False,
            "format": model.format,
            "think": model.think,
            "keep_alive": model.keep_alive,
            "options": {
                "num_ctx": model.num_ctx,
                "num_predict": model.num_predict,
                "temperature": model.temperature,
            },
            "messages": _doc_node_messages(prompt),
        }
        request = urllib.request.Request(
            _request_url(model, self.base_url, "/api/chat"),
            data=json.dumps(body).encode("utf-8"),
            headers=_request_headers(model),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=model.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        return parse_ollama_json_message(data)


class OllamaBlackboxProfileProvider(OllamaEdgeProvider):
    """Ollama HTTP provider for blackbox input-output node profiles."""

    def _generate_with_model(self, prompt: str, model: EdgeModelConfig, model_name: str) -> Dict[str, Any]:
        body = {
            "model": model_name,
            "stream": False,
            "format": model.format,
            "think": model.think,
            "keep_alive": model.keep_alive,
            "options": {
                "num_ctx": model.num_ctx,
                "num_predict": model.num_predict,
                "temperature": model.temperature,
            },
            "messages": _blackbox_profile_messages(prompt),
        }
        request = urllib.request.Request(
            _request_url(model, self.base_url, "/api/chat"),
            data=json.dumps(body).encode("utf-8"),
            headers=_request_headers(model),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=model.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        return parse_ollama_json_message(data)


class OpenAICompatibleEdgeProvider:
    """OpenAI-compatible chat completions provider for semantic edge generation."""

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url.rstrip("/")

    def generate(self, prompt: str, model: EdgeModelConfig) -> Dict[str, Any]:
        model_names = [model.preferred]
        if model.fallback and model.fallback not in model_names:
            model_names.append(model.fallback)
        errors: List[str] = []
        for model_name in model_names:
            try:
                return self._generate_with_model(prompt, model, model_name)
            except Exception as exc:  # pragma: no cover - exercised by tests through fallback
                errors.append(f"{model_name}: {exc}")
                if model_name == model_names[-1]:
                    raise RuntimeError("OpenAI-compatible edge generation failed: " + "; ".join(errors)) from exc
        return {"cases": []}

    def _generate_with_model(self, prompt: str, model: EdgeModelConfig, model_name: str) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "model": model_name,
            "stream": False,
            "temperature": model.temperature,
            "max_tokens": model.num_predict,
            "messages": _edge_messages(prompt),
        }
        if model.format == "json":
            body["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(
            _request_url(model, self.base_url, "/v1/chat/completions"),
            data=json.dumps(body).encode("utf-8"),
            headers=_request_headers(model),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=model.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        return parse_openai_compatible_json_message(data)


class OpenAICompatibleDocNodeProvider(OpenAICompatibleEdgeProvider):
    """OpenAI-compatible provider for BoxMatrix-style document node extraction."""

    def _generate_with_model(self, prompt: str, model: EdgeModelConfig, model_name: str) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "model": model_name,
            "stream": False,
            "temperature": model.temperature,
            "max_tokens": model.num_predict,
            "messages": _doc_node_messages(prompt),
        }
        if model.format == "json":
            body["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(
            _request_url(model, self.base_url, "/v1/chat/completions"),
            data=json.dumps(body).encode("utf-8"),
            headers=_request_headers(model),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=model.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        return parse_openai_compatible_json_message(data)


class OpenAICompatibleBlackboxProfileProvider(OpenAICompatibleEdgeProvider):
    """OpenAI-compatible provider for blackbox input-output node profiles."""

    def _generate_with_model(self, prompt: str, model: EdgeModelConfig, model_name: str) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "model": model_name,
            "stream": False,
            "temperature": model.temperature,
            "max_tokens": model.num_predict,
            "messages": _blackbox_profile_messages(prompt),
        }
        if model.format == "json":
            body["response_format"] = {"type": "json_object"}
        request = urllib.request.Request(
            _request_url(model, self.base_url, "/v1/chat/completions"),
            data=json.dumps(body).encode("utf-8"),
            headers=_request_headers(model),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=model.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        return parse_openai_compatible_json_message(data)


def create_edge_provider(model: EdgeModelConfig) -> EdgeProvider:
    provider = _normalize_provider_id(model.provider)
    if provider == "ollama":
        return OllamaEdgeProvider()
    if provider in {"openai", "openai-compatible"}:
        return OpenAICompatibleEdgeProvider()
    raise ValueError(f"Unsupported edge provider: {model.provider}")


def create_doc_node_provider(model: EdgeModelConfig) -> EdgeProvider:
    provider = _normalize_provider_id(model.provider)
    if provider == "ollama":
        return OllamaDocNodeProvider()
    if provider in {"openai", "openai-compatible"}:
        return OpenAICompatibleDocNodeProvider()
    raise ValueError(f"Unsupported edge provider: {model.provider}")


def create_blackbox_profile_provider(model: EdgeModelConfig) -> EdgeProvider:
    provider = _normalize_provider_id(model.provider)
    if provider == "ollama":
        return OllamaBlackboxProfileProvider()
    if provider in {"openai", "openai-compatible"}:
        return OpenAICompatibleBlackboxProfileProvider()
    raise ValueError(f"Unsupported edge provider: {model.provider}")


def _normalize_provider_id(provider: Any) -> str:
    return str(provider or "ollama").strip().lower().replace("_", "-")


def _edge_messages(prompt: str) -> List[Dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "/no_think "
                "Return only valid JSON. Preserve exact C identifiers. "
                "For every case, include edges that mention every supplied TERMS identifier when the snippets support it. "
                "Use only code, register, field, or function identifiers as src and dst. Do not use file paths as src or dst. "
                "Each supplied TERMS identifier must appear in src or dst of at least one edge when the snippet supports it. "
                "Emit at most six edges per case. Keep evidence under 12 words and include line numbers when available. "
                "Do not use markdown fences. "
                f"Use relation names from: {PRODUCT_RELATION_PROMPT}. "
                "Schema: {\"cases\":[{\"id\":string,\"edges\":[{\"src\":string,"
                "\"relation\":string,\"dst\":string,\"confidence\":number,"
                "\"evidence\":string}]}]}"
            ),
        },
        {"role": "user", "content": f"/no_think\n{prompt}"},
    ]


def _doc_node_messages(prompt: str) -> List[Dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "/no_think "
                "Return only valid JSON for ASIP document graph extraction. "
                "Use the exact DOCUMENT ids provided by the user as documents[].id. "
                "Extract BoxMatrix boxes only when the text contains a concrete hardware concept, workflow, "
                "constraint, register behavior, telemetry metric, RAS event, or API surface. "
                "Use linked register or function symbols as relationship endpoints when provided; "
                "put fields and enum values inside box inputs, outputs, or constraints instead of endpoints. "
                "Do not emit markdown fences or prose. "
                "Schema: {\"documents\":[{\"id\":string,\"boxes\":[{\"id\":string,"
                "\"name\":string,\"summary\":string,\"inputs\":[string],\"outputs\":[string],"
                "\"constraints\":[string],\"confidence\":number,\"evidence\":string}],"
                "\"relationships\":[{\"src\":string,\"relation\":string,\"dst\":string,"
                "\"confidence\":number,\"evidence\":string}]}]}"
            ),
        },
        {"role": "user", "content": f"/no_think\n{prompt}"},
    ]


def _blackbox_profile_messages(prompt: str) -> List[Dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "/no_think "
                "Return only valid JSON for ASIP blackbox graph profiles. "
                "Treat each endpoint as a black box: infer behavior only from observable inputs, "
                "outputs, source snippets, and graph facts supplied by the user. "
                "Use exact endpoint ids from the prompt for profiles[].id and relationship src/dst. "
                "Do not invent endpoints, local variables, wrapper names, field names, providers, or file paths as nodes. "
                "Keep evidence under 12 words. Do not emit markdown fences or prose. "
                "Schema: {\"profiles\":[{\"id\":string,\"method\":string,\"inputs\":[string],"
                "\"outputs\":[string],\"observed_behavior\":string,\"explanation_layer\":string,"
                "\"confidence\":number,\"evidence\":string}],\"relationships\":[{\"src\":string,"
                "\"relation\":string,\"dst\":string,\"confidence\":number,\"evidence\":string}]}"
            ),
        },
        {"role": "user", "content": f"/no_think\n{prompt}"},
    ]


def _request_headers(model: EdgeModelConfig) -> Dict[str, str]:
    return {"Content-Type": "application/json", **expand_extra_headers(model.extra_headers)}


def _request_url(model: EdgeModelConfig, default_base_url: str, default_path: str) -> str:
    base_url = (model.api_base_url or default_base_url).rstrip("/")
    api_path = model.api_path or default_path
    if not api_path.startswith("/"):
        api_path = f"/{api_path}"
    return f"{base_url}{api_path}"


def load_edge_case_config(path: Path) -> EdgeCaseConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    repo_data = data.get("repo", {})
    return EdgeCaseConfig(
        name=data["name"],
        repo=EdgeRepoConfig(
            url=repo_data["url"],
            default_source_root=repo_data["default_source_root"],
        ),
        model=_load_model_config(data.get("model", {})),
        cases=[
            EdgeCase(
                id=item["id"],
                question=item["question"],
                path=item["path"],
                start=int(item["start"]),
                end=int(item["end"]),
                expected_terms=list(item["expected_terms"]),
            )
            for item in data["cases"]
        ],
    )


def _load_model_config(model_data: Mapping[str, Any]) -> EdgeModelConfig:
    extra_headers = model_data.get("extra_headers", {})
    if not isinstance(extra_headers, dict):
        raise ValueError("model.extra_headers must be an object")
    provider = _normalize_provider_id(model_data.get("provider", "ollama"))
    default_api_path = "/v1/chat/completions" if provider in {"openai", "openai-compatible"} else "/api/chat"
    return EdgeModelConfig(
        preferred=model_data["preferred"],
        fallback=model_data.get("fallback", ""),
        provider=provider,
        api_base_url=model_data.get("api_base_url", model_data.get("base_url", "http://localhost:11434")),
        api_path=model_data.get("api_path", default_api_path),
        extra_headers={str(key): str(value) for key, value in extra_headers.items()},
        format=model_data.get("format", "json"),
        num_ctx=int(model_data.get("num_ctx", 8192)),
        num_predict=int(model_data.get("num_predict", 512)),
        temperature=float(model_data.get("temperature", 0)),
        keep_alive=model_data.get("keep_alive", "0s"),
        think=bool(model_data.get("think", False)),
        timeout_seconds=int(model_data.get("timeout_seconds", 600)),
    )


def load_full_corpus_edge_config(path: Path) -> FullCorpusEdgeConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    return FullCorpusEdgeConfig(
        name=data["name"],
        model=_load_model_config(data.get("model", {})),
        corpora=[
            FullCorpus(
                id=item["id"],
                repo=item["repo"],
                default_source_root=item["default_source_root"],
                relative_root=item.get("relative_root", ""),
                include=list(item.get("include", ["**/*.c", "**/*.h"])),
                subfolders=_load_corpus_subfolders(item),
            )
            for item in data["corpora"]
        ],
        queries=[
            FullCorpusQuery(
                id=item["id"],
                corpus=item["corpus"],
                question=item["question"],
                terms=list(item["terms"]),
                expected_terms=list(item.get("expected_terms", item["terms"])),
                max_snippets=int(item.get("max_snippets", 2)),
                context_before=int(item.get("context_before", 3)),
                context_after=int(item.get("context_after", 5)),
            )
            for item in data["queries"]
        ],
    )


def _load_corpus_subfolders(item: Mapping[str, Any]) -> List[FullCorpusSubfolder]:
    include = list(item.get("include", ["**/*.c", "**/*.h"]))
    raw_subfolders = item.get("subfolders", item.get("filters", []))
    if not raw_subfolders and item.get("relative_roots"):
        raw_subfolders = [{"relative_root": value, "include": include} for value in item.get("relative_roots", [])]
    if not isinstance(raw_subfolders, list):
        return []
    subfolders: List[FullCorpusSubfolder] = []
    for raw in raw_subfolders:
        if isinstance(raw, str):
            subfolders.append(
                FullCorpusSubfolder(
                    relative_root=normalize_corpus_relative_root(raw, allow_empty=False),
                    include=include,
                )
            )
            continue
        if not isinstance(raw, Mapping):
            continue
        relative_root = normalize_corpus_relative_root(
            raw.get("relative_root", raw.get("relativeRoot", raw.get("root", raw.get("path", "")))),
            allow_empty=False,
        )
        subfolder_include = raw.get("include", include)
        if isinstance(subfolder_include, str):
            subfolder_include = [item.strip() for item in subfolder_include.split(",") if item.strip()]
        subfolders.append(
            FullCorpusSubfolder(
                relative_root=relative_root,
                include=list(subfolder_include or include),
            )
        )
    return subfolders


def full_corpus_scan_folders(corpus: FullCorpus) -> List[FullCorpusSubfolder]:
    if corpus.subfolders:
        return [
            FullCorpusSubfolder(
                relative_root=normalize_corpus_relative_root(folder.relative_root),
                include=list(folder.include),
            )
            for folder in corpus.subfolders
        ]
    return [
        FullCorpusSubfolder(
            relative_root=normalize_corpus_relative_root(corpus.relative_root),
            include=corpus.include,
        )
    ]


def read_snippet(case: EdgeCase, source_root: Path) -> str:
    file_path = source_root / case.path
    lines = file_path.read_text(errors="replace", encoding="utf-8").splitlines()
    selected = lines[case.start - 1 : case.end]
    return "\n".join(f"{case.start + offset}: {line}" for offset, line in enumerate(selected))


def build_prompt(config: EdgeCaseConfig, source_root: Path) -> str:
    parts = [
        "Extract semantic graph edges from these real AMD MxGPU source snippets.",
        "For each case, answer the question by emitting only edges grounded in that snippet.",
    ]
    for case in config.cases:
        parts.append(
            "\n".join(
                [
                    f"CASE {case.id}",
                    f"QUESTION: {case.question}",
                    f"SOURCE: {case.path}:{case.start}-{case.end}",
                    "SNIPPET:",
                    read_snippet(case, source_root),
                ]
            )
        )
    return "\n\n".join(parts)


def verify_queries(config: EdgeCaseConfig, generated: Dict[str, Any]) -> List[Dict[str, Any]]:
    by_case = {case.get("id"): case for case in generated.get("cases", [])}
    results: List[Dict[str, Any]] = []
    for case in config.cases:
        generated_case = by_case.get(case.id, {"edges": []})
        haystack = json.dumps(generated_case.get("edges", []), sort_keys=True)
        missing = [term for term in case.expected_terms if term not in haystack]
        results.append(
            {
                "id": f"query_{case.id}",
                "case": case.id,
                "passed": not missing,
                "missing": missing,
                "edge_count": len(generated_case.get("edges", [])),
            }
        )
    return results


def scan_full_corpus_queries(
    config: FullCorpusEdgeConfig,
    source_roots: Mapping[str, Path],
) -> Dict[str, Any]:
    corpus_by_id = {corpus.id: corpus for corpus in config.corpora}
    scanned_files: Dict[str, List[Path]] = {}
    corpus_summary: Dict[str, Dict[str, Any]] = {}

    for corpus in config.corpora:
        source_root = Path(source_roots.get(corpus.id, Path(corpus.default_source_root))).expanduser()
        files: List[Path] = []
        seen_files: set[Path] = set()
        scan_roots: List[Dict[str, Any]] = []
        for folder in full_corpus_scan_folders(corpus):
            scan_root = source_root / folder.relative_root if folder.relative_root else source_root
            resolved_source_root = source_root.resolve(strict=False)
            resolved_scan_root = scan_root.resolve(strict=False)
            if resolved_scan_root != resolved_source_root and resolved_source_root not in resolved_scan_root.parents:
                raise ValueError(f"corpus subfolder must be repo-relative: {folder.relative_root}")
            folder_files = list(_iter_source_files(scan_root, folder.include))
            for file_path in folder_files:
                file_key = file_path.resolve(strict=False)
                if file_key in seen_files:
                    continue
                seen_files.add(file_key)
                files.append(file_path)
            scan_roots.append(
                {
                    "relative_root": folder.relative_root,
                    "scan_root": str(scan_root),
                    "include": list(folder.include),
                    "file_count": len(folder_files),
                }
            )
        scanned_files[corpus.id] = files
        first_scan_root = scan_roots[0]["scan_root"] if scan_roots else str(source_root)
        corpus_summary[corpus.id] = {
            "repo": corpus.repo,
            "source_root": str(source_root),
            "scan_root": first_scan_root,
            "scan_roots": scan_roots,
            "relative_root": corpus.relative_root,
            "file_count": len(files),
            "commit": git_short_commit(source_root),
        }

    resolved_queries: List[Dict[str, Any]] = []
    for query in config.queries:
        corpus = corpus_by_id[query.corpus]
        source_root = Path(source_roots.get(corpus.id, Path(corpus.default_source_root))).expanduser()
        snippets = _resolve_query_snippets(
            query=query,
            files=scanned_files[corpus.id],
            source_root=source_root,
            scan_root=source_root,
        )
        resolved_queries.append(
            {
                "id": query.id,
                "corpus": query.corpus,
                "repo": corpus.repo,
                "question": query.question,
                "terms": query.terms,
                "expected_terms": query.expected_terms,
                "snippets": snippets,
                "resolved": bool(snippets),
            }
        )

    total_files = sum(item["file_count"] for item in corpus_summary.values())
    return {
        "config": config.name,
        "model": config.model.preferred,
        "corpora": corpus_summary,
        "queries": resolved_queries,
        "summary": {
            "query_count": len(resolved_queries),
            "resolved_query_count": sum(1 for item in resolved_queries if item["resolved"]),
            "total_files_scanned": total_files,
            "corpora": corpus_summary,
        },
    }


def build_full_corpus_prompt(scan: Dict[str, Any]) -> str:
    parts = [
        "Extract semantic graph edges from real source snippets discovered by scanning full repositories.",
        "Every edge must be grounded in the provided SOURCE and preserve exact C identifiers.",
        "If a case has multiple snippets, emit only edges supported by at least one snippet.",
        "Use code/register/field/function identifiers as src and dst. Do not use file paths as src or dst.",
        f"Use relation names from: {PRODUCT_RELATION_PROMPT}.",
        "Every supplied TERMS identifier that appears in the snippet must appear in src or dst of at least one edge.",
        "",
        "SCAN SUMMARY:",
    ]
    for corpus_id, summary in scan["corpora"].items():
        parts.append(
            f"- {corpus_id}: repo={summary['repo']} files={summary['file_count']} "
            f"root={summary['source_root']} scan_root={summary['scan_root']}"
        )
    for query in scan["queries"]:
        block = [
            f"CASE {query['id']}",
            f"CORPUS: {query['corpus']}",
            f"QUESTION: {query['question']}",
            f"TERMS: {', '.join(query['terms'])}",
        ]
        for index, snippet in enumerate(query["snippets"], start=1):
            block.extend(
                [
                    f"SOURCE {index}: {snippet['path']}:{snippet['line_start']}-{snippet['line_end']}",
                    "SNIPPET:",
                    snippet["text"],
                ]
            )
        if not query["snippets"]:
            block.append("SNIPPET: <no matching source snippet found>")
        parts.append("\n".join(block))
    return "\n\n".join(parts)


def verify_full_corpus_queries(
    config: FullCorpusEdgeConfig,
    scan: Dict[str, Any],
    generated: Dict[str, Any],
) -> List[Dict[str, Any]]:
    by_case = {case.get("id"): case for case in generated.get("cases", [])}
    scan_by_query = {item["id"]: item for item in scan["queries"]}
    results: List[Dict[str, Any]] = []
    for query in config.queries:
        generated_case = by_case.get(query.id, {"edges": []})
        edges = list(generated_case.get("edges", []))
        haystack = json.dumps(edges, sort_keys=True)
        missing = [term for term in query.expected_terms if term not in haystack]
        source_hits = scan_by_query[query.id]["snippets"]
        source_haystack = "\n".join(str(snippet.get("text", "")) for snippet in source_hits)
        missing_in_sources = [term for term in query.expected_terms if term not in source_haystack]
        ungrounded_edges = _ungrounded_edge_labels(edges, source_haystack)
        results.append(
            {
                "id": f"query_{query.id}",
                "case": query.id,
                "corpus": query.corpus,
                "passed": bool(source_hits) and bool(edges) and not missing and not missing_in_sources and not ungrounded_edges,
                "missing": missing,
                "missing_in_sources": missing_in_sources,
                "ungrounded_edges": ungrounded_edges,
                "edge_count": len(edges),
                "source_hit_count": len(source_hits),
                "sources": [
                    f"{snippet['path']}:{snippet['line_start']}-{snippet['line_end']}"
                    for snippet in source_hits
                ],
            }
        )
    return results


def run_generation(
    config_path: Path,
    source_root: Optional[Path] = None,
    output_json: Optional[Path] = None,
    output_md: Optional[Path] = None,
    provider: Optional[EdgeProvider] = None,
    min_pass: int = 6,
) -> Dict[str, Any]:
    config = load_edge_case_config(config_path)
    actual_source_root = source_root or Path(config.repo.default_source_root)
    edge_provider = provider or create_edge_provider(config.model)
    started = time.time()
    prompt = build_prompt(config, actual_source_root)
    generated = edge_provider.generate(prompt, config.model)
    ollama_ps = provider_status_after_run(edge_provider, config.model)
    query_results = verify_queries(config, generated)
    passed = sum(1 for item in query_results if item["passed"])
    payload: Dict[str, Any] = {
        "config": config.name,
        "model": config.model.preferred,
        "repo": {
            "url": config.repo.url,
            "source_root": str(actual_source_root),
            "commit": git_short_commit(actual_source_root),
        },
        "duration_seconds": round(time.time() - started, 2),
        "generated": generated,
        "query_results": query_results,
        "summary": {
            "query_count": len(query_results),
            "passed": passed,
            "failed": len(query_results) - passed,
            "min_pass": min_pass,
            "ollama_ps_after": ollama_ps.strip(),
        },
    }
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if output_md:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_markdown(payload), encoding="utf-8")
    if passed < min_pass:
        raise RuntimeError(f"Only {passed}/{len(query_results)} edge queries passed; required {min_pass}")
    return payload


def run_full_corpus_generation(
    config_path: Path,
    source_roots: Optional[Mapping[str, Path]] = None,
    output_json: Optional[Path] = None,
    output_md: Optional[Path] = None,
    provider: Optional[EdgeProvider] = None,
    min_pass: int = 6,
    batch_size: Optional[int] = None,
) -> Dict[str, Any]:
    limits = load_workbench_limits()
    effective_batch_size = batch_size if batch_size is not None else limits.int_value("semantic", "full_corpus_batch_size", minimum=1)
    if effective_batch_size is None:
        raise ValueError(f"semantic.fullCorpusBatchSize is missing from {limits.path}")
    config = load_full_corpus_edge_config(config_path)
    actual_source_roots = source_roots or {}
    edge_provider = provider or create_edge_provider(config.model)
    started = time.time()
    scan = scan_full_corpus_queries(config, actual_source_roots)
    generated = generate_full_corpus_batches(scan, edge_provider, config.model, batch_size=effective_batch_size)
    ollama_ps = provider_status_after_run(edge_provider, config.model)
    query_results = verify_full_corpus_queries(config, scan, generated)
    passed = sum(1 for item in query_results if item["passed"])
    payload: Dict[str, Any] = {
        "config": config.name,
        "model": config.model.preferred,
        "duration_seconds": round(time.time() - started, 2),
        "corpora": scan["corpora"],
        "scan": {
            "queries": scan["queries"],
            "summary": scan["summary"],
        },
        "generated": generated,
        "query_results": query_results,
        "summary": {
            "query_count": len(query_results),
            "passed": passed,
            "failed": len(query_results) - passed,
            "min_pass": min_pass,
            "batch_size": effective_batch_size,
            "resolved_query_count": scan["summary"]["resolved_query_count"],
            "total_files_scanned": scan["summary"]["total_files_scanned"],
            "ollama_ps_after": ollama_ps.strip(),
        },
    }
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if output_md:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(render_full_corpus_markdown(payload), encoding="utf-8")
    if passed < min_pass:
        raise RuntimeError(f"Only {passed}/{len(query_results)} edge queries passed; required {min_pass}")
    return payload


def generate_full_corpus_batches(
    scan: Dict[str, Any],
    provider: EdgeProvider,
    model: EdgeModelConfig,
    batch_size: Optional[int] = None,
) -> Dict[str, Any]:
    if batch_size is None:
        limits = load_workbench_limits()
        batch_size = limits.int_value("semantic", "full_corpus_batch_size", minimum=1)
    if batch_size is None:
        raise ValueError("semantic.fullCorpusBatchSize is missing from workbench limits")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    all_cases: List[Dict[str, Any]] = []
    errors: List[Dict[str, Any]] = []
    queries = scan["queries"]
    for start in range(0, len(queries), batch_size):
        batch_scan = dict(scan)
        batch_scan["queries"] = queries[start : start + batch_size]
        prompt = build_full_corpus_prompt(batch_scan)
        try:
            batch_generated = normalize_generated_cases(provider.generate(prompt, model))
        except Exception as exc:
            batch_queries = [query["id"] for query in batch_scan["queries"]]
            errors.append({"queries": batch_queries, "error": str(exc)})
            batch_generated = {
                "cases": [
                    {"id": query_id, "edges": [], "error": str(exc)}
                    for query_id in batch_queries
                ]
            }
        all_cases.extend(batch_generated.get("cases", []))
    return {"cases": all_cases, "errors": errors}


def normalize_generated_cases(generated: Any) -> Dict[str, Any]:
    if isinstance(generated, dict) and isinstance(generated.get("cases"), list):
        return generated
    if isinstance(generated, list):
        return {"cases": generated}
    if isinstance(generated, dict) and "id" in generated and "edges" in generated:
        return {"cases": [generated]}
    return {"cases": []}


def render_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# Real Semantic Edge Generation QA",
        "",
        f"Model: `{payload['model']}`",
        f"Repository: `{payload['repo']['url']}` at `{payload['repo']['commit']}`",
        f"Duration: `{payload['duration_seconds']}s`",
        "",
        "## Summary",
        "",
        f"- Query count: `{payload['summary']['query_count']}`",
        f"- Passed: `{payload['summary']['passed']}`",
        f"- Failed: `{payload['summary']['failed']}`",
        f"- Ollama after run: `{payload['summary']['ollama_ps_after']}`",
        "",
        "## Query Results",
        "",
    ]
    for item in payload["query_results"]:
        status = "PASS" if item["passed"] else "FAIL"
        missing = ", ".join(item["missing"])
        lines.append(f"- `{status}` `{item['id']}` edges=`{item['edge_count']}` missing=`{missing}`")
    lines.append("")
    return "\n".join(lines)


def render_full_corpus_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# Full-Corpus Semantic Edge Generation QA",
        "",
        f"Model: `{payload['model']}`",
        f"Duration: `{payload['duration_seconds']}s`",
        "",
        "## Corpora",
        "",
    ]
    for corpus_id, corpus in payload["corpora"].items():
        lines.append(
            f"- `{corpus_id}` `{corpus['repo']}` commit=`{corpus['commit']}` "
            f"files=`{corpus['file_count']}` scan_root=`{corpus['scan_root']}`"
        )
    lines.extend(
        [
            "",
            "## Summary",
            "",
            f"- Query count: `{payload['summary']['query_count']}`",
            f"- Resolved query count: `{payload['summary']['resolved_query_count']}`",
            f"- Total files scanned: `{payload['summary']['total_files_scanned']}`",
            f"- Passed: `{payload['summary']['passed']}`",
            f"- Failed: `{payload['summary']['failed']}`",
            f"- Ollama after run: `{payload['summary']['ollama_ps_after']}`",
            "",
            "## Query Results",
            "",
        ]
    )
    for item in payload["query_results"]:
        status = "PASS" if item["passed"] else "FAIL"
        missing = ", ".join(item["missing"])
        missing_in_sources = ", ".join(item.get("missing_in_sources", []))
        ungrounded = ", ".join(item.get("ungrounded_edges", []))
        sources = "; ".join(item["sources"])
        lines.append(
            f"- `{status}` `{item['id']}` corpus=`{item['corpus']}` "
            f"edges=`{item['edge_count']}` sources=`{item['source_hit_count']}` "
            f"missing=`{missing}` missing_in_sources=`{missing_in_sources}` "
            f"ungrounded_edges=`{ungrounded}` source_refs=`{sources}`"
        )
    lines.append("")
    return "\n".join(lines)


def stop_ollama_model(model_name: str) -> None:
    try:
        subprocess.run(["ollama", "stop", model_name], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        return


def ollama_ps_output() -> str:
    try:
        result = subprocess.run(["ollama", "ps"], check=False, capture_output=True, text=True)
    except FileNotFoundError:
        return "ollama not found"
    return result.stdout


def provider_status_after_run(provider: EdgeProvider, model: EdgeModelConfig) -> str:
    if not isinstance(provider, OllamaEdgeProvider):
        return f"{provider.__class__.__name__} cleanup not applicable"
    for model_name in provider.cleanup_model_names(model):
        stop_ollama_model(model_name)
    return ollama_ps_output()


def git_short_commit(path: Path) -> str:
    result = subprocess.run(["git", "-C", str(path), "rev-parse", "--short", "HEAD"], check=False, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def parse_ollama_json_message(data: Dict[str, Any]) -> Dict[str, Any]:
    message = data.get("message", {})
    content = message.get("content") or ""
    if content.strip():
        parsed = _parse_json_text(content)
        if parsed is not None:
            return parsed
    thinking = message.get("thinking") or ""
    parsed = _parse_json_text(thinking)
    if parsed is not None:
        return parsed
    preview = (content or thinking)[:240].replace("\n", "\\n")
    raise ValueError(f"Ollama returned no parseable JSON content: {preview}")


def parse_openai_compatible_json_message(data: Dict[str, Any]) -> Dict[str, Any]:
    choices = data.get("choices") or []
    if choices:
        message = choices[0].get("message", {})
        content = message.get("content") or ""
        parsed = _parse_json_text(content)
        if parsed is not None:
            return parsed
    preview = json.dumps(data)[:240].replace("\n", "\\n")
    raise ValueError(f"OpenAI-compatible provider returned no parseable JSON content: {preview}")


def _parse_json_text(text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        extracted = _extract_json_object(_strip_json_fence(text))
        if not extracted:
            return None
        try:
            return json.loads(extracted)
        except json.JSONDecodeError:
            return None


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    if start == -1:
        return ""
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return ""


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines)
    return text


def _iter_source_files(root: Path, include: Iterable[str]) -> Iterable[Path]:
    if not root.exists():
        return []
    patterns = tuple(include) or ("**/*.c", "**/*.h")
    files: List[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts:
            continue
        if _matches_include(path.relative_to(root).as_posix(), patterns):
            files.append(path)
    return sorted(files)


def _matches_include(relative_path: str, include: Iterable[str]) -> bool:
    path = PurePosixPath(relative_path)
    for pattern in include:
        normalized = pattern.replace("\\", "/")
        if path.match(normalized):
            return True
        if normalized.startswith("**/") and path.match(normalized[3:]):
            return True
    return False


def _resolve_query_snippets(
    query: FullCorpusQuery,
    files: List[Path],
    source_root: Path,
    scan_root: Path,
) -> List[Dict[str, Any]]:
    ranked: List[Tuple[int, int, int, str, Path, str]] = []
    for file_path in files:
        text = file_path.read_text(encoding="utf-8", errors="replace")
        found_count = sum(1 for term in query.terms if term in text)
        if found_count == 0:
            continue
        all_found = 1 if found_count == len(query.terms) else 0
        source_priority = 1 if file_path.suffix.lower() in {".c", ".cc", ".cpp"} else 0
        ranked.append((all_found, found_count, source_priority, str(file_path), file_path, text))
    ranked.sort(key=lambda item: (-item[0], -item[1], -item[2], item[3]))

    snippets: List[Dict[str, Any]] = []
    for _all_found, _found_count, _source_priority, _sort_key, file_path, text in ranked:
        for snippet in _snippets_from_text(query, file_path, text, source_root, scan_root):
            snippets.append(snippet)
            if len(snippets) >= query.max_snippets:
                return snippets
    return snippets


def _snippets_from_text(
    query: FullCorpusQuery,
    file_path: Path,
    text: str,
    source_root: Path,
    scan_root: Path,
) -> Iterable[Dict[str, Any]]:
    lines = text.splitlines()
    match_indexes = [
        index
        for index, line in enumerate(lines)
        if any(term in line for term in query.terms)
    ]
    candidates: List[Tuple[int, int, int, int, str]] = []
    for index in match_indexes:
        start = max(0, index - query.context_before)
        end = min(len(lines), index + query.context_after + 1)
        window_text = "\n".join(lines[start:end])
        term_hits = sum(1 for term in query.terms if term in window_text)
        candidates.append((term_hits, -len(window_text), start, end, window_text))
    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))

    emitted_ranges: List[Tuple[int, int]] = []
    for _term_hits, _negative_length, start, end, _window_text in candidates:
        if any(not (end <= prev_start or start >= prev_end) for prev_start, prev_end in emitted_ranges):
            continue
        emitted_ranges.append((start, end))
        selected = lines[start:end]
        yield {
            "path": _display_source_path(file_path, source_root, scan_root),
            "line_start": start + 1,
            "line_end": end,
            "text": "\n".join(f"{start + offset + 1}: {line}" for offset, line in enumerate(selected)),
        }


def _display_source_path(file_path: Path, source_root: Path, scan_root: Path) -> str:
    try:
        return str(file_path.relative_to(source_root))
    except ValueError:
        try:
            return str(file_path.relative_to(scan_root))
        except ValueError:
            return str(file_path)


def _extract_identifiers(text: str) -> List[str]:
    identifiers: List[str] = []
    token = ""
    for char in text:
        if char.isalnum() or char in "_->":
            token += char
        else:
            if _looks_like_identifier(token):
                identifiers.append(token)
            token = ""
    if _looks_like_identifier(token):
        identifiers.append(token)
    return identifiers


def _looks_like_identifier(token: str) -> bool:
    return len(token) > 2 and any(char == "_" or char.isupper() for char in token)


def _looks_like_source_line(line: str) -> bool:
    prefix = line.split(":", 1)[0].strip()
    return bool(prefix) and prefix.isdigit()


def _ungrounded_edge_labels(edges: Iterable[Mapping[str, Any]], source_text: str) -> List[str]:
    ungrounded: List[str] = []
    for edge in edges:
        src = str(edge.get("src", ""))
        dst = str(edge.get("dst", ""))
        missing = [
            endpoint
            for endpoint in (src, dst)
            if _looks_like_identifier(endpoint) and endpoint not in source_text
        ]
        if missing:
            ungrounded.append(f"{src}->{dst}")
    return ungrounded


def _fake_case(case_id: str, terms: List[str]) -> Dict[str, Any]:
    unique_terms = list(dict.fromkeys(terms))
    if len(unique_terms) < 2:
        unique_terms = unique_terms + unique_terms
    edges = [
        {
            "src": unique_terms[0],
            "relation": "relates_to",
            "dst": unique_terms[index],
            "confidence": 1.0,
            "evidence": "deterministic test edge",
        }
        for index in range(1, len(unique_terms))
    ]
    return {"id": case_id, "edges": edges}
