"""Semantic edge generation and query verification for ASIP."""

from __future__ import annotations

import json
import subprocess
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol, Tuple


@dataclass(frozen=True)
class EdgeModelConfig:
    preferred: str
    fallback: str
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
class FullCorpus:
    id: str
    repo: str
    default_source_root: str
    relative_root: str = ""
    include: List[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.include is None:
            object.__setattr__(self, "include", ["**/*.c", "**/*.h"])


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
            elif ":" in line:
                terms.extend(_extract_identifiers(line))
        if current_id:
            cases.append(_fake_case(current_id, terms))
        return {"cases": cases}


class OllamaEdgeProvider:
    """Ollama HTTP provider for semantic edge generation."""

    def __init__(self, base_url: str = "http://localhost:11434") -> None:
        self.base_url = base_url.rstrip("/")

    def generate(self, prompt: str, model: EdgeModelConfig) -> Dict[str, Any]:
        body = {
            "model": model.preferred,
            "stream": False,
            "format": model.format,
            "think": model.think,
            "keep_alive": model.keep_alive,
            "options": {
                "num_ctx": model.num_ctx,
                "num_predict": model.num_predict,
                "temperature": model.temperature,
            },
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "/no_think "
                        "Return only valid JSON. Preserve exact C identifiers. "
                        "For every case, include edges that mention every supplied TERMS identifier when the snippets support it. "
                        "Emit at most four edges per case. Keep evidence under 12 words and include line numbers when available. "
                        "Do not use markdown fences. "
                        "Use relation names from: reads, writes, sets_field, checks_mask, "
                        "maps_base, assigns_doorbell, waits_for. "
                        "Schema: {\"cases\":[{\"id\":string,\"edges\":[{\"src\":string,"
                        "\"relation\":string,\"dst\":string,\"confidence\":number,"
                        "\"evidence\":string}]}]}"
                    ),
                },
                {"role": "user", "content": f"/no_think\n{prompt}"},
            ],
        }
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=model.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        return parse_ollama_json_message(data)


def load_edge_case_config(path: Path) -> EdgeCaseConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    model_data = data.get("model", {})
    repo_data = data.get("repo", {})
    return EdgeCaseConfig(
        name=data["name"],
        repo=EdgeRepoConfig(
            url=repo_data["url"],
            default_source_root=repo_data["default_source_root"],
        ),
        model=EdgeModelConfig(
            preferred=model_data["preferred"],
            fallback=model_data.get("fallback", ""),
            format=model_data.get("format", "json"),
            num_ctx=int(model_data.get("num_ctx", 8192)),
            num_predict=int(model_data.get("num_predict", 512)),
            temperature=float(model_data.get("temperature", 0)),
            keep_alive=model_data.get("keep_alive", "0s"),
            think=bool(model_data.get("think", False)),
            timeout_seconds=int(model_data.get("timeout_seconds", 600)),
        ),
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


def load_full_corpus_edge_config(path: Path) -> FullCorpusEdgeConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    model_data = data.get("model", {})
    return FullCorpusEdgeConfig(
        name=data["name"],
        model=EdgeModelConfig(
            preferred=model_data["preferred"],
            fallback=model_data.get("fallback", ""),
            format=model_data.get("format", "json"),
            num_ctx=int(model_data.get("num_ctx", 8192)),
            num_predict=int(model_data.get("num_predict", 512)),
            temperature=float(model_data.get("temperature", 0)),
            keep_alive=model_data.get("keep_alive", "0s"),
            think=bool(model_data.get("think", False)),
            timeout_seconds=int(model_data.get("timeout_seconds", 600)),
        ),
        corpora=[
            FullCorpus(
                id=item["id"],
                repo=item["repo"],
                default_source_root=item["default_source_root"],
                relative_root=item.get("relative_root", ""),
                include=list(item.get("include", ["**/*.c", "**/*.h"])),
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
        scan_root = source_root / corpus.relative_root if corpus.relative_root else source_root
        files = list(_iter_source_files(scan_root, corpus.include))
        scanned_files[corpus.id] = files
        corpus_summary[corpus.id] = {
            "repo": corpus.repo,
            "source_root": str(source_root),
            "scan_root": str(scan_root),
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
            scan_root=source_root / corpus.relative_root if corpus.relative_root else source_root,
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
        haystack = json.dumps(generated_case.get("edges", []), sort_keys=True)
        missing = [term for term in query.expected_terms if term not in haystack]
        source_hits = scan_by_query[query.id]["snippets"]
        results.append(
            {
                "id": f"query_{query.id}",
                "case": query.id,
                "corpus": query.corpus,
                "passed": bool(source_hits) and not missing,
                "missing": missing,
                "edge_count": len(generated_case.get("edges", [])),
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
    edge_provider = provider or OllamaEdgeProvider()
    started = time.time()
    prompt = build_prompt(config, actual_source_root)
    generated = edge_provider.generate(prompt, config.model)
    stop_ollama_model(config.model.preferred)
    ollama_ps = ollama_ps_output()
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
    batch_size: int = 3,
) -> Dict[str, Any]:
    config = load_full_corpus_edge_config(config_path)
    actual_source_roots = source_roots or {}
    edge_provider = provider or OllamaEdgeProvider()
    started = time.time()
    scan = scan_full_corpus_queries(config, actual_source_roots)
    generated = generate_full_corpus_batches(scan, edge_provider, config.model, batch_size=batch_size)
    stop_ollama_model(config.model.preferred)
    ollama_ps = ollama_ps_output()
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
            "batch_size": batch_size,
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
    batch_size: int = 3,
) -> Dict[str, Any]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    all_cases: List[Dict[str, Any]] = []
    queries = scan["queries"]
    for start in range(0, len(queries), batch_size):
        batch_scan = dict(scan)
        batch_scan["queries"] = queries[start : start + batch_size]
        prompt = build_full_corpus_prompt(batch_scan)
        batch_generated = normalize_generated_cases(provider.generate(prompt, model))
        all_cases.extend(batch_generated.get("cases", []))
    return {"cases": all_cases}


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
        sources = "; ".join(item["sources"])
        lines.append(
            f"- `{status}` `{item['id']}` corpus=`{item['corpus']}` "
            f"edges=`{item['edge_count']}` sources=`{item['source_hit_count']}` "
            f"missing=`{missing}` source_refs=`{sources}`"
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
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return ""
    return text[start : end + 1]


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
    suffixes = _suffixes_for_include(include)
    files: List[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts:
            continue
        if path.suffix.lower() in suffixes:
            files.append(path)
    return sorted(files)


def _suffixes_for_include(include: Iterable[str]) -> Tuple[str, ...]:
    suffixes: List[str] = []
    for pattern in include:
        suffix = Path(pattern).suffix
        if suffix:
            suffixes.append(suffix.lower())
    return tuple(dict.fromkeys(suffixes)) or (".c", ".h")


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


def _fake_case(case_id: str, terms: List[str]) -> Dict[str, Any]:
    unique_terms = list(dict.fromkeys(terms))
    if len(unique_terms) < 2:
        unique_terms = unique_terms + unique_terms
    edges = [
        {
            "src": unique_terms[0],
            "relation": "mentions",
            "dst": unique_terms[index],
            "confidence": 1.0,
            "evidence": "deterministic test edge",
        }
        for index in range(1, len(unique_terms))
    ]
    return {"id": case_id, "edges": edges}
