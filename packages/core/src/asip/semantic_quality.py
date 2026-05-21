"""Labeled semantic retrieval quality evaluation for ASIP."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .providers import EmbeddingTransport
from .workbench import query_evidence


def run_semantic_quality_eval(
    db_path: Path,
    eval_set_path: Path,
    *,
    output_json: Optional[Path] = None,
    output_md: Optional[Path] = None,
    embedding_transport: Optional[EmbeddingTransport] = None,
) -> Dict[str, Any]:
    cases = _load_eval_cases(eval_set_path)
    case_results = [
        _run_case(db_path, case, embedding_transport=embedding_transport)
        for case in cases
    ]
    passed = sum(1 for case in case_results if case["status"] == "pass")
    failed = len(case_results) - passed
    target_ranks = [
        int(case["first_expected_rank"])
        for case in case_results
        if case.get("first_expected_rank")
    ]
    result: Dict[str, Any] = {
        "source": "asip.semantic_quality_eval",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repo_head": _repo_head(Path.cwd()),
        "db_path": str(db_path),
        "db_sha256": _sha256(db_path),
        "eval_set_path": str(eval_set_path),
        "eval_set_sha256": _sha256(eval_set_path),
        "summary": {
            "total": len(case_results),
            "passed": passed,
            "failed": failed,
            "provider_vector_cases": sum(1 for case in case_results if case["provider_vector_rows"] > 0),
            "graph_target_cases": sum(1 for case in case_results if case["expected_graph_node_terms_found"]),
            "mean_reciprocal_rank": round(
                sum(1 / rank for rank in target_ranks) / len(target_ranks),
                4,
            )
            if target_ranks
            else 0,
        },
        "gate_status": "pass" if failed == 0 and case_results else "blocked",
        "cases": case_results,
        "boundary": (
            "This evaluates a labeled current-corpus semantic retrieval set. "
            "It does not claim quality across arbitrary future corpora."
        ),
    }
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if output_md:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(_render_markdown(result), encoding="utf-8")
    return result


def _load_eval_cases(path: Path) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL case at {path}:{line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise ValueError(f"semantic quality case must be an object at {path}:{line_number}")
        if not str(value.get("id") or "").strip():
            raise ValueError(f"semantic quality case id is missing at {path}:{line_number}")
        if not str(value.get("query") or "").strip():
            raise ValueError(f"semantic quality case query is missing at {path}:{line_number}")
        cases.append(value)
    if not cases:
        raise ValueError(f"semantic quality eval set has no cases: {path}")
    return cases


def _run_case(
    db_path: Path,
    case: Mapping[str, Any],
    *,
    embedding_transport: Optional[EmbeddingTransport] = None,
) -> Dict[str, Any]:
    limit = int(case.get("limit") or 24)
    payload = query_evidence(
        db_path,
        str(case["query"]),
        limit=limit,
        compact_graph=bool(case.get("compact_graph", True)),
        embedding_transport=embedding_transport,
    )
    rows = list(payload.get("rows") or [])
    graph = payload.get("graph") if isinstance(payload.get("graph"), Mapping) else {}
    source_types = sorted(
        {
            str(row.get("source_type") or row.get("source") or "")
            for row in rows
            if row.get("source_type") or row.get("source")
        }
    )
    retrieval_sources = sorted(
        {
            str(source)
            for row in rows
            for source in row.get("retrieval_sources", [])
        }
    )
    provider_vector_rows = [
        row for row in rows if "provider-vector" in row.get("retrieval_sources", [])
    ]
    failures = []
    if len(rows) < int(case.get("min_rows") or 1):
        failures.append(f"row_count {len(rows)} is below min_rows {case.get('min_rows') or 1}")
    for source_type in _list(case.get("expected_source_types")):
        if source_type not in source_types:
            failures.append(f"missing source_type: {source_type}")
    for source in _list(case.get("required_retrieval_sources")):
        if source not in retrieval_sources:
            failures.append(f"missing retrieval_source: {source}")
    min_provider_vector_rows = int(case.get("min_provider_vector_rows") or 0)
    if len(provider_vector_rows) < min_provider_vector_rows:
        failures.append(
            f"provider-vector rows {len(provider_vector_rows)} below required {min_provider_vector_rows}"
        )
    expected_embedding_source = str(case.get("expected_query_embedding_source") or "").strip()
    query_embedding = payload.get("query_embedding") if isinstance(payload.get("query_embedding"), Mapping) else {}
    if expected_embedding_source and str(query_embedding.get("source") or "") != expected_embedding_source:
        failures.append(
            f"query_embedding.source={query_embedding.get('source')} expected {expected_embedding_source}"
        )
    first_rank = _first_expected_rank(rows, case)
    if _has_rank_target(case) and first_rank is None:
        failures.append("no expected symbol/path target returned")
    max_expected_rank = case.get("max_expected_rank")
    if first_rank is not None and max_expected_rank is not None and first_rank > int(max_expected_rank):
        failures.append(f"first expected target rank {first_rank} exceeds {max_expected_rank}")
    min_graph_nodes = int(case.get("min_graph_nodes") or 0)
    graph_node_count = len(graph.get("nodes", [])) if isinstance(graph, Mapping) else 0
    if graph_node_count < min_graph_nodes:
        failures.append(f"graph_node_count {graph_node_count} below {min_graph_nodes}")
    graph_nodes = list(graph.get("nodes", [])) if isinstance(graph, Mapping) else []
    graph_node_matches = _graph_node_term_matches(graph_nodes, case)
    for term, matched in graph_node_matches["required_all"].items():
        if not matched:
            failures.append(f"missing graph node term: {term}")
    if graph_node_matches["required_any"] and not any(graph_node_matches["required_any"].values()):
        failures.append(
            "missing any graph node term: "
            + ", ".join(graph_node_matches["required_any"].keys())
        )
    for kind in _list(case.get("expected_graph_node_kinds")):
        if kind not in graph_node_matches["kinds"]:
            failures.append(f"missing graph node kind: {kind}")
    return {
        "id": str(case["id"]),
        "query": str(case["query"]),
        "status": "pass" if not failures else "fail",
        "failure_reasons": failures,
        "row_count": len(rows),
        "first_expected_rank": first_rank,
        "source_types": source_types,
        "retrieval_sources": retrieval_sources,
        "provider_vector_rows": len(provider_vector_rows),
        "query_embedding": {key: value for key, value in query_embedding.items() if key != "vector"},
        "graph_node_count": graph_node_count,
        "graph_edge_count": len(graph.get("edges", [])) if isinstance(graph, Mapping) else 0,
        "expected_graph_node_terms_found": {
            **graph_node_matches["required_all"],
            **graph_node_matches["required_any"],
        },
        "graph_node_kinds": sorted(graph_node_matches["kinds"]),
        "top_rows": [
            {
                "rank": index,
                "symbol": row.get("symbol"),
                "source_type": row.get("source_type") or row.get("source"),
                "path": row.get("path"),
                "retrieval_sources": row.get("retrieval_sources", []),
                "vector_score": row.get("vector_score"),
            }
            for index, row in enumerate(rows[: int(case.get("top_rows") or 5)], start=1)
        ],
    }


def _first_expected_rank(rows: Iterable[Mapping[str, Any]], case: Mapping[str, Any]) -> Optional[int]:
    expected_symbols = set(_list(case.get("expected_symbols_any")))
    expected_path_suffixes = _list(case.get("expected_path_suffixes"))
    for index, row in enumerate(rows, start=1):
        symbol = str(row.get("symbol") or "")
        path = str(row.get("path") or "")
        if symbol in expected_symbols:
            return index
        if any(path.endswith(suffix) for suffix in expected_path_suffixes):
            return index
    return None


def _graph_node_term_matches(
    graph_nodes: Iterable[Mapping[str, Any]],
    case: Mapping[str, Any],
) -> Dict[str, Any]:
    nodes = list(graph_nodes)
    searchable = [
        " ".join(
            str(node.get(field) or "")
            for field in ("id", "label", "kind")
        )
        for node in nodes
    ]
    required_all = {
        term: any(term in value for value in searchable)
        for term in _list(case.get("expected_graph_node_terms_all"))
    }
    required_any = {
        term: any(term in value for value in searchable)
        for term in _list(case.get("expected_graph_node_terms_any"))
    }
    return {
        "required_all": required_all,
        "required_any": required_any,
        "kinds": {str(node.get("kind") or "") for node in nodes if node.get("kind")},
    }


def _has_rank_target(case: Mapping[str, Any]) -> bool:
    return bool(_list(case.get("expected_symbols_any")) or _list(case.get("expected_path_suffixes")))


def _list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        return [str(item) for item in value if str(item)]
    return [str(value)]


def _render_markdown(result: Mapping[str, Any]) -> str:
    summary = result.get("summary", {})
    lines = [
        "# Semantic Quality Evaluation",
        "",
        f"Generated: `{result.get('generated_at', '')}`",
        f"Repo head: `{result.get('repo_head', '')}`",
        f"DB: `{result.get('db_path', '')}`",
        f"Eval set: `{result.get('eval_set_path', '')}`",
        f"Gate: `{result.get('gate_status', '')}`",
        "",
        "## Summary",
        "",
        f"- Total: {summary.get('total', 0)}",
        f"- Passed: {summary.get('passed', 0)}",
        f"- Failed: {summary.get('failed', 0)}",
        f"- Provider-vector cases: {summary.get('provider_vector_cases', 0)}",
        f"- Graph-target cases: {summary.get('graph_target_cases', 0)}",
        f"- Mean reciprocal rank: {summary.get('mean_reciprocal_rank', 0)}",
        "",
        "## Cases",
        "",
        "| Case | Status | Rows | First expected rank | Sources | Retrieval | Failures |",
        "| --- | --- | ---: | ---: | --- | --- | --- |",
    ]
    for case in result.get("cases", []):
        lines.append(
            "| {id} | {status} | {rows} | {rank} | {sources} | {retrieval} | {failures} |".format(
                id=case.get("id", ""),
                status=case.get("status", ""),
                rows=case.get("row_count", 0),
                rank=case.get("first_expected_rank") or "-",
                sources=", ".join(case.get("source_types", [])) or "-",
                retrieval=", ".join(case.get("retrieval_sources", [])) or "-",
                failures="; ".join(case.get("failure_reasons", [])) or "-",
            )
        )
    lines.extend(["", f"Boundary: {result.get('boundary', '')}", ""])
    return "\n".join(lines)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_head(cwd: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""
