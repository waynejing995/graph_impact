"""Acceptance query runner for ASIP clean-DB QA artifacts."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .semantic_edges import EdgeModelConfig, EdgeProvider, create_edge_provider
from .workbench import load_provider_settings, query_evidence


DEFAULT_ACCEPTANCE_QUERIES: List[Dict[str, Any]] = [
    {
        "id": "AQ01",
        "query": "Who reads or writes regGCVM_L2_CNTL?",
        "gap_ids": ["G01", "G02", "G03", "G10"],
        "required_surfaces": ["CLI", "API", "Web", "MCP"],
    },
    {
        "id": "AQ02",
        "query": "Which fields of GCVM_L2_CNTL are set in MxGPU gfx_v11_0.c?",
        "gap_ids": ["G01", "G02", "G05", "G10"],
        "required_surfaces": ["CLI", "API", "Web"],
    },
    {
        "id": "AQ03",
        "query": "Where is IH_RB_CNTL configured, and which fields are modified?",
        "gap_ids": ["G01", "G02", "G03", "G10"],
        "required_surfaces": ["CLI", "API", "Web"],
    },
    {
        "id": "AQ04",
        "query": "Which code paths reference SDMA0_QUEUE0_RB_CNTL or SDMA1_QUEUE0_RB_CNTL?",
        "gap_ids": ["G01", "G02", "G03", "G10"],
        "required_surfaces": ["CLI", "API", "Web"],
    },
    {
        "id": "AQ05",
        "query": "Show evidence connecting amdgpu documentation to the amdgpu driver source tree.",
        "gap_ids": ["G01", "G02", "G08", "G10"],
        "required_surfaces": ["CLI", "API", "Web"],
        "required_source_types": ["code", "doc", "pdf"],
    },
    {
        "id": "AQ06",
        "query": "Given WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp), explain the resolved register entity and macro expansion chain.",
        "gap_ids": ["G02", "G05", "G07", "G10"],
        "required_surfaces": ["CLI", "API", "Web", "MCP"],
        "required_source_types": ["code", "register"],
    },
    {
        "id": "AQ07",
        "query": "Change resolver profile to add or rename one C/C++ register access wrapper, then verify the same resolver engine resolves it without code changes.",
        "gap_ids": ["G05", "G07", "G10", "G14"],
        "required_surfaces": ["CLI", "API", "Web"],
    },
    {
        "id": "AQ08",
        "query": "Add a toy Python resolver profile extracting a configured function-call or string-symbol reference, proving profiles are not macro-only.",
        "gap_ids": ["G05", "G07", "G10", "G13"],
        "required_surfaces": ["CLI", "API", "Web"],
    },
    {
        "id": "AQ09",
        "query": "Run embedding and optional semantic-edge extraction through a configured Ollama provider, then switch to an OpenAI-compatible provider without changing retrieval or resolver code.",
        "gap_ids": ["G06", "G09", "G10", "G17"],
        "required_surfaces": ["CLI", "API", "Web"],
        "requires_provider_settings": True,
    },
]


def run_acceptance_queries(
    db_path: Path,
    output_json: Optional[Path] = None,
    output_md: Optional[Path] = None,
    queries: Optional[Iterable[Dict[str, Any]]] = None,
    surfaces_checked: Optional[Iterable[str]] = None,
    edge_provider: Optional[EdgeProvider] = None,
) -> Dict[str, Any]:
    checked = _unique_ordered(str(surface) for surface in (surfaces_checked or ["CLI"]))
    provider_settings = load_provider_settings(db_path)
    provider_checks = _run_provider_checks(db_path, provider_settings, edge_provider)
    database_health = _database_health_failures(db_path)
    records = [
        _run_one_acceptance_query(db_path, query, checked, provider_settings, provider_checks, database_health)
        for query in (list(queries) if queries is not None else DEFAULT_ACCEPTANCE_QUERIES)
    ]
    result = {
        "source": "asip.acceptance",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "db_path": str(db_path),
        "database_health": {"status": "fail" if database_health else "pass", "failure_reasons": database_health},
        "provider_settings": provider_settings,
        "provider_checks": provider_checks,
        "surfaces_checked": checked,
        "summary": {
            "total": len(records),
            "passed": sum(1 for record in records if record["status"] == "pass"),
            "partial": sum(1 for record in records if record["status"] == "partial"),
            "failed": sum(1 for record in records if record["status"] == "fail"),
        },
        "queries": records,
    }
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if output_md:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(_render_markdown(result), encoding="utf-8")
    return result


def _run_one_acceptance_query(
    db_path: Path,
    query: Dict[str, Any],
    surfaces_checked: List[str],
    provider_settings: Dict[str, object],
    provider_checks: Dict[str, Any],
    database_health: List[str],
) -> Dict[str, Any]:
    payload = query_evidence(db_path, str(query["query"]))
    rows = list(payload.get("rows", []))
    graph = dict(payload.get("graph", {}))
    required_surfaces = [str(surface) for surface in query.get("required_surfaces", [])]
    missing_surfaces = [surface for surface in required_surfaces if surface not in surfaces_checked]
    failure_reasons = list(database_health)
    query_provider_checks: Dict[str, Any] = {}
    if query.get("requires_provider_settings"):
        if not provider_settings:
            failure_reasons.append("provider settings are required for this acceptance query")
        query_provider_checks = provider_checks
        for check_name, check in provider_checks.items():
            if check.get("status") != "pass":
                failure_reasons.append(f"{check_name} provider check failed: {check.get('message', 'unknown error')}")
    row_count = len(rows)
    source_types = sorted({str(row.get("source_type") or row.get("source")) for row in rows if row.get("source_type") or row.get("source")})
    required_source_types = [str(source_type) for source_type in query.get("required_source_types", [])]
    missing_source_types = [source_type for source_type in required_source_types if source_type not in source_types]
    if missing_source_types:
        failure_reasons.append(f"required source types missing: {', '.join(missing_source_types)}")
    status = "fail" if row_count == 0 or failure_reasons else ("partial" if missing_surfaces else "pass")
    return {
        "id": str(query["id"]),
        "query": str(query["query"]),
        "gap_ids": [str(item) for item in query.get("gap_ids", [])],
        "required_surfaces": required_surfaces,
        "required_source_types": required_source_types,
        "surfaces_checked": surfaces_checked,
        "missing_surfaces": missing_surfaces,
        "failure_reasons": failure_reasons,
        "provider_checks": query_provider_checks,
        "status": status,
        "row_count": row_count,
        "evidence_ids": [row.get("id") for row in rows if row.get("id") is not None],
        "source_paths": sorted({str(row.get("path")) for row in rows if row.get("path")}),
        "source_types": source_types,
        "retrieval_sources": sorted(
            {
                str(source)
                for row in rows
                for source in row.get("retrieval_sources", [])
            }
        ),
        "graph_node_count": len(graph.get("nodes", [])),
        "graph_edge_count": len(graph.get("edges", [])),
        "graph_runtime": graph.get("graph_runtime", graph.get("source", "")),
        "empty_state": payload.get("empty_state", ""),
    }


def _run_provider_checks(
    db_path: Path,
    provider_settings: Mapping[str, object],
    edge_provider: Optional[EdgeProvider],
) -> Dict[str, Any]:
    if not provider_settings:
        return {}
    return {
        "embedding": _embedding_provenance_check(db_path, provider_settings),
        "semantic_edge": _semantic_edge_smoke(provider_settings, edge_provider),
    }


def _database_health_failures(db_path: Path) -> List[str]:
    failures: List[str] = []
    if not db_path.exists():
        return [f"database does not exist: {db_path}"]
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        for row in con.execute("select id, status from corpora order by id").fetchall():
            status = str(row["status"])
            if status != "indexed":
                failures.append(f"corpus {row['id']} status is {status}")
        for row in con.execute("select id, status, message from jobs where kind = 'index' order by id").fetchall():
            status = str(row["status"])
            if status in {"failed", "running"}:
                message = str(row["message"] or "")
                suffix = f": {message}" if message else ""
                failures.append(f"index job {row['id']} {status}{suffix}")
    except sqlite3.DatabaseError as exc:
        failures.append(f"database health check failed: {exc}")
    return failures


def _embedding_provenance_check(db_path: Path, provider_settings: Mapping[str, object]) -> Dict[str, Any]:
    embedding = provider_settings.get("embedding")
    if not isinstance(embedding, Mapping):
        return {"status": "fail", "message": "embedding provider settings are missing"}
    expected_provider = str(embedding.get("provider") or "ollama")
    expected_model = str(embedding.get("model") or "").strip()
    if not expected_model:
        return {"status": "fail", "message": "embedding model is missing"}
    try:
        con = sqlite3.connect(db_path)
        rows = con.execute("select provider, model, metadata_json from embeddings").fetchall()
    except sqlite3.DatabaseError as exc:
        return {"status": "fail", "message": f"embedding provenance query failed: {exc}"}

    provider_rows = []
    fallback_rows = 0
    for provider, model, metadata_json in rows:
        try:
            metadata = json.loads(str(metadata_json))
        except json.JSONDecodeError:
            metadata = {}
        if metadata.get("source") == "provider":
            provider_rows.append({"provider": provider, "model": model})
        else:
            fallback_rows += 1
    matching_rows = [
        row for row in provider_rows if row["provider"] == expected_provider and row["model"] == expected_model
    ]
    if not matching_rows:
        return {
            "status": "fail",
            "message": "no embedding rows were generated by the configured provider",
            "provider": expected_provider,
            "model": expected_model,
            "embedding_count": len(provider_rows),
            "fallback_count": fallback_rows,
        }
    return {
        "status": "pass",
        "provider": expected_provider,
        "model": expected_model,
        "embedding_count": len(matching_rows),
        "fallback_count": fallback_rows,
    }


def _semantic_edge_smoke(
    provider_settings: Mapping[str, object],
    edge_provider: Optional[EdgeProvider],
) -> Dict[str, Any]:
    edge = provider_settings.get("edge")
    if not isinstance(edge, Mapping):
        return {"status": "fail", "message": "edge provider settings are missing"}
    model_name = str(edge.get("model") or edge.get("preferred") or "").strip()
    if not model_name:
        return {"status": "fail", "message": "edge model is missing"}
    config = EdgeModelConfig(
        preferred=model_name,
        fallback=str(edge.get("fallback_model") or edge.get("fallback") or ""),
        provider=str(edge.get("provider") or "ollama"),
        api_base_url=str(edge.get("api_base_url") or edge.get("base_url") or "http://localhost:11434"),
        api_path=str(edge.get("api_path") or ""),
        extra_headers={str(key): str(value) for key, value in dict(edge.get("extra_headers") or {}).items()},
        format=str(edge.get("format") or "json"),
        num_ctx=int(edge.get("num_ctx") or 2048),
        num_predict=int(edge.get("num_predict") or 128),
        temperature=float(edge.get("temperature") or 0),
        keep_alive=str(edge.get("keep_alive") or "0s"),
        think=bool(edge.get("think", False)),
        timeout_seconds=int(edge.get("timeout_seconds") or 60),
    )
    provider = edge_provider or create_edge_provider(config)
    prompt = (
        "CASE provider-smoke\n"
        "TERMS: GCVM_L2_CNTL, ENABLE_L2_CACHE\n"
        "SNIPPET:\n"
        "1: GCVM_L2_CNTL has field ENABLE_L2_CACHE\n"
    )
    try:
        generated = provider.generate(prompt, config)
    except Exception as exc:
        return {
            "status": "fail",
            "message": f"semantic edge provider failed: {exc}",
            "provider": config.provider,
            "model": config.preferred,
        }
    cases = generated.get("cases", []) if isinstance(generated, Mapping) else []
    edge_count = sum(len(case.get("edges", [])) for case in cases if isinstance(case, Mapping))
    if edge_count <= 0:
        return {
            "status": "fail",
            "message": "semantic edge provider returned no edges",
            "provider": config.provider,
            "model": config.preferred,
            "edge_count": 0,
        }
    return {
        "status": "pass",
        "provider": config.provider,
        "model": config.preferred,
        "edge_count": edge_count,
    }


def _render_markdown(result: Dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        "# ASIP Acceptance Query Run",
        "",
        f"Generated: {result['generated_at']}",
        f"DB: `{result['db_path']}`",
        f"Surfaces checked: {', '.join(result['surfaces_checked'])}",
        "",
        "## Summary",
        "",
        f"- Total: {summary['total']}",
        f"- Passed: {summary['passed']}",
        f"- Partial: {summary['partial']}",
        f"- Failed: {summary['failed']}",
        "",
    ]
    health = result.get("database_health") or {}
    if health:
        failures = health.get("failure_reasons") or []
        lines.extend(
            [
                "## Database Health",
                "",
                f"- Status: {health.get('status', '')}",
                f"- Failure reasons: {', '.join(str(item) for item in failures) if failures else '-'}",
                "",
            ]
        )
    lines.extend(
        [
        "## Queries",
        "",
        "| ID | Status | Rows | Source types | Graph | Missing surfaces | Failure reasons | Query |",
        "| --- | --- | ---: | --- | ---: | --- | --- | --- |",
        ]
    )
    for item in result["queries"]:
        missing = ", ".join(item["missing_surfaces"]) if item["missing_surfaces"] else "-"
        source_types = ", ".join(item.get("source_types", [])) if item.get("source_types") else "-"
        failures = ", ".join(str(reason) for reason in item.get("failure_reasons", [])) if item.get("failure_reasons") else "-"
        graph = f"{item['graph_node_count']} nodes / {item['graph_edge_count']} edges"
        query = str(item["query"]).replace("|", "\\|")
        lines.append(
            f"| {item['id']} | {item['status']} | {item['row_count']} | {source_types} | "
            f"{graph} | {missing} | {failures} | {query} |"
        )
    if result.get("provider_checks"):
        lines.extend(
            [
                "",
                "## Provider Checks",
                "",
                "| Check | Status | Provider | Model | Details |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for name, check in result["provider_checks"].items():
            details = []
            if "embedding_count" in check:
                details.append(f"embeddings={check['embedding_count']}")
            if "fallback_count" in check:
                details.append(f"fallback={check['fallback_count']}")
            if "edge_count" in check:
                details.append(f"edges={check['edge_count']}")
            if check.get("message"):
                details.append(str(check["message"]))
            lines.append(
                f"| {name} | {check.get('status', '')} | {check.get('provider', '')} | "
                f"{check.get('model', '')} | {', '.join(details) or '-'} |"
            )
    lines.append("")
    return "\n".join(lines)


def _unique_ordered(items: Iterable[str]) -> List[str]:
    seen = set()
    unique: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique
