"""Tool functions backing the ASIP MCP surface."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

from asip.acceptance import DEFAULT_ACCEPTANCE_QUERIES, run_acceptance_queries
from asip.workbench import (
    add_corpus,
    add_resolver_profile,
    explain_entity,
    expand_query_graph,
    generate_semantic_edges_for_query,
    get_evidence_detail,
    index_registered_corpora,
    list_indexed_corpora,
    list_resolver_profiles,
    load_provider_settings,
    query_evidence,
    save_provider_settings,
    validate_resolver_profile,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO_ROOT / "configs/edge_cases/full-corpus-qwen35.json"
DEFAULT_DB = REPO_ROOT / "data/asip.db"


def search_evidence(query: str, db_path: str | None = None) -> Dict[str, Any]:
    db = Path(db_path) if db_path else DEFAULT_DB
    payload = query_evidence(db, query)
    payload["query_id"] = payload.get("queryId", "")
    return payload


def graph_expand(seed: str, db_path: str | None = None) -> Dict[str, Any]:
    db = Path(db_path) if db_path else DEFAULT_DB
    payload = expand_query_graph(db, seed)
    payload["query_id"] = payload.get("queryId", seed)
    return payload


def semantic_edges_generate(query: str, db_path: str | None = None, limit: int = 8) -> Dict[str, Any]:
    db = Path(db_path) if db_path else DEFAULT_DB
    return generate_semantic_edges_for_query(db, query, limit=limit)


def resolver_inspect(profile_id: str) -> Dict[str, Any]:
    path = REPO_ROOT / "configs/resolvers" / f"{profile_id}.yaml"
    text = path.read_text(encoding="utf-8")
    wrappers = re.findall(r"^  ([A-Za-z_][A-Za-z0-9_]*):$", text, flags=re.MULTILINE)
    extractors = _parse_inline_list(re.search(r"^python_extractors:\s*(\[.*\])$", text, flags=re.MULTILINE))
    return {
        "id": re.search(r"^id:\s*(.+)$", text, flags=re.MULTILINE).group(1).strip(),
        "language": re.search(r"^language:\s*(.+)$", text, flags=re.MULTILINE).group(1).strip(),
        "wrappers": wrappers or extractors,
        "path": str(path.relative_to(REPO_ROOT)),
    }


def acceptance_runs() -> List[Dict[str, Any]]:
    runs = []
    patterns = [
        "2026-05-16-full-corpus-edge-generation-*.json",
        "????-??-??-acceptance-*.json",
    ]
    paths = sorted({path for pattern in patterns for path in (REPO_ROOT / "docs/qa").glob(pattern)})
    for path in paths:
        payload = _read_json(path)
        if payload.get("source") == "asip.acceptance":
            summary = payload["summary"]
            runs.append(
                {
                    "id": _run_id_from_artifact(path),
                    "model": payload["source"],
                    "passed": summary["passed"],
                    "partial": summary["partial"],
                    "failed": summary["failed"],
                    "query_count": summary["total"],
                    "artifact_path": str(path.relative_to(REPO_ROOT)),
                    "db_path": payload.get("db_path", ""),
                }
            )
            continue
        runs.append(
            {
                "id": _run_id_from_artifact(path),
                "model": payload["model"],
                "passed": payload["summary"]["passed"],
                "failed": payload["summary"]["failed"],
                "query_count": payload["summary"]["query_count"],
                "artifact_path": str(path.relative_to(REPO_ROOT)),
            }
        )
    return runs


def run_acceptance(
    query_ids: List[str] | None = None,
    surfaces: List[str] | None = None,
    db_path: str | None = None,
) -> Dict[str, Any]:
    db = Path(db_path) if db_path else DEFAULT_DB
    return run_acceptance_queries(
        db,
        queries=_select_acceptance_queries(query_ids),
        surfaces_checked=surfaces or ["MCP"],
    )


def corpora_list(db_path: str | None = None, config_path: str | None = None) -> Dict[str, Any]:
    db = Path(db_path) if db_path else DEFAULT_DB
    config = Path(config_path) if config_path else DEFAULT_CONFIG
    return {"corpora": list_indexed_corpora(db, config)}


def corpus_add(
    corpus_id: str,
    repo: str,
    source_root: str,
    include: List[str],
    corpus_type: str = "code",
    db_path: str | None = None,
) -> Dict[str, Any]:
    return add_corpus(
        Path(db_path) if db_path else DEFAULT_DB,
        corpus_id=corpus_id,
        repo=repo,
        source_root=source_root,
        include=include,
        corpus_type=corpus_type,
    )


def corpora_index(corpus_ids: List[str] | None = None, db_path: str | None = None) -> Dict[str, Any]:
    return index_registered_corpora(Path(db_path) if db_path else DEFAULT_DB, corpus_ids=corpus_ids)


def evidence_detail(evidence_id: int, db_path: str | None = None) -> Dict[str, Any]:
    db = Path(db_path) if db_path else DEFAULT_DB
    return get_evidence_detail(db, evidence_id)


def entity_explain(symbol: str, db_path: str | None = None) -> Dict[str, Any]:
    db = Path(db_path) if db_path else DEFAULT_DB
    return explain_entity(db, symbol)


def provider_settings_save(settings: Dict[str, object], db_path: str | None = None) -> Dict[str, object]:
    return save_provider_settings(Path(db_path) if db_path else DEFAULT_DB, settings)


def provider_settings_show(db_path: str | None = None) -> Dict[str, object]:
    return load_provider_settings(Path(db_path) if db_path else DEFAULT_DB)


def ollama_models(base_url: str = "http://localhost:11434", timeout_seconds: int = 5) -> Dict[str, Any]:
    requested_url = f"{base_url.rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(requested_url, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = [str(item.get("name")) for item in payload.get("models", []) if item.get("name")]
        return {"ok": True, "requested_url": requested_url, "models": models}
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {"ok": False, "requested_url": requested_url, "models": [], "error": str(exc)}


def resolver_profiles_list(db_path: str | None = None) -> Dict[str, Any]:
    return {"profiles": list_resolver_profiles(Path(db_path) if db_path else DEFAULT_DB)}


def resolver_profile_add(
    profile_id: str,
    language: str,
    wrappers: List[str],
    strategy: str,
    path: str,
    enabled: bool = True,
    db_path: str | None = None,
) -> Dict[str, Any]:
    return add_resolver_profile(
        Path(db_path) if db_path else DEFAULT_DB,
        profile_id=profile_id,
        language=language,
        wrappers=wrappers,
        strategy=strategy,
        path=path,
        enabled=enabled,
    )


def resolver_profile_validate(profile_id: str, source: str, db_path: str | None = None) -> Dict[str, Any]:
    return validate_resolver_profile(Path(db_path) if db_path else DEFAULT_DB, profile_id, source)


def _run_id_from_artifact(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"^\d{4}-\d{2}-\d{2}-full-corpus-edge-generation-", "", stem)
    stem = re.sub(r"^\d{4}-\d{2}-\d{2}-acceptance-", "acceptance-", stem)
    return stem


def _select_acceptance_queries(query_ids: List[str] | None) -> List[Dict[str, Any]] | None:
    if not query_ids:
        return None
    by_id = {str(query["id"]): query for query in DEFAULT_ACCEPTANCE_QUERIES}
    missing = [query_id for query_id in query_ids if query_id not in by_id]
    if missing:
        raise ValueError(f"unknown acceptance query id(s): {', '.join(missing)}")
    return [by_id[query_id] for query_id in query_ids]


def _parse_inline_list(match: re.Match[str] | None) -> List[str]:
    if not match:
        return []
    return [item.strip().strip("'\"") for item in match.group(1)[1:-1].split(",") if item.strip()]


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
