"""Acceptance query runner for ASIP clean-DB QA artifacts."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .graph_schema import (
    ALLOWED_PRODUCT_NODE_KINDS,
    ALLOWED_PRODUCT_RELATIONS,
    normalize_product_relation,
    product_endpoint_kind,
)
from .providers import EmbeddingProviderConfig, EmbeddingTransport, create_embedding_provider
from .semantic_edges import EdgeModelConfig, EdgeProvider, create_edge_provider
from .storage import normalize_job_status
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
        "required_surfaces": ["CLI", "API", "MCP"],
        "requires_provider_settings": True,
    },
]

PROVIDER_CHECK_IDS = (
    "embedding",
    "embedding_live",
    "semantic_edge_provenance",
    "doc_node_provenance",
    "semantic_edge",
)


def run_acceptance_queries(
    db_path: Path,
    output_json: Optional[Path] = None,
    output_md: Optional[Path] = None,
    queries: Optional[Iterable[Dict[str, Any]]] = None,
    surfaces_checked: Optional[Iterable[str]] = None,
    edge_provider: Optional[EdgeProvider] = None,
    embedding_transport: Optional[EmbeddingTransport] = None,
) -> Dict[str, Any]:
    checked = _unique_ordered(str(surface) for surface in (surfaces_checked or ["CLI"]))
    provider_settings = load_provider_settings(db_path)
    provider_checks = _run_provider_checks(db_path, provider_settings, edge_provider, embedding_transport)
    database_health = _database_health_failures(db_path)
    records = [
        _run_one_acceptance_query(db_path, query, checked, provider_settings, provider_checks, database_health)
        for query in (list(queries) if queries is not None else DEFAULT_ACCEPTANCE_QUERIES)
    ]
    summary = {
        "total": len(records),
        "passed": sum(1 for record in records if record["status"] == "pass"),
        "partial": sum(1 for record in records if record["status"] == "partial"),
        "failed": sum(1 for record in records if record["status"] == "fail"),
    }
    result = {
        "source": "asip.acceptance",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "db_path": str(db_path),
        "database_health": {"status": "fail" if database_health else "pass", "failure_reasons": database_health},
        "provider_settings": provider_settings,
        "provider_checks": provider_checks,
        "surfaces_checked": checked,
        "summary": summary,
        "gate_status": "pass" if summary["passed"] == summary["total"] and summary["partial"] == 0 and summary["failed"] == 0 else "blocked",
        "queries": records,
    }
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if output_md:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(_render_markdown(result), encoding="utf-8")
    return result


def run_provider_gate(
    db_path: Path,
    output_json: Optional[Path] = None,
    edge_provider: Optional[EdgeProvider] = None,
    embedding_transport: Optional[EmbeddingTransport] = None,
) -> Dict[str, Any]:
    provider_settings = load_provider_settings(db_path)
    provider_checks = _run_provider_checks(db_path, provider_settings, edge_provider, embedding_transport)
    database_health = _database_health_failures(db_path)
    status_counts = {
        "total": len(provider_checks),
        "passed": sum(1 for check in provider_checks.values() if check.get("status") == "pass"),
        "partial": sum(1 for check in provider_checks.values() if check.get("status") == "partial"),
        "failed": sum(1 for check in provider_checks.values() if check.get("status") == "fail"),
    }
    failure_reasons = list(database_health)
    if not provider_settings:
        failure_reasons.append("provider settings are missing")
    for check_name, check in provider_checks.items():
        if check.get("status") != "pass":
            failure_reasons.append(f"{check_name} provider check failed: {check.get('message', 'unknown error')}")
    result = {
        "source": "asip.provider_gate",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "db_path": str(db_path),
        "database_health": {"status": "fail" if database_health else "pass", "failure_reasons": database_health},
        "provider_settings": provider_settings,
        "provider_checks": provider_checks,
        "summary": status_counts,
        "gate_status": "blocked" if failure_reasons else "pass",
        "failure_reasons": failure_reasons,
    }
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _run_one_acceptance_query(
    db_path: Path,
    query: Dict[str, Any],
    surfaces_checked: List[str],
    provider_settings: Dict[str, object],
    provider_checks: Dict[str, Any],
    database_health: List[str],
) -> Dict[str, Any]:
    query_text = str(query["query"])
    surface_probes = [_run_surface_probe(surface, db_path, query_text) for surface in surfaces_checked]
    payload = next(
        (probe["payload"] for probe in surface_probes if isinstance(probe.get("payload"), Mapping)),
        {"rows": [], "graph": {}},
    )
    rows, graph, payload_shape_failures = _validated_surface_payload(payload)
    schema_failure_reasons = _surface_graph_contract_failures(graph)
    required_surfaces = [str(surface) for surface in query.get("required_surfaces", [])]
    missing_surfaces = [surface for surface in required_surfaces if surface not in surfaces_checked]
    failure_reasons = list(database_health)
    failure_reasons.extend(payload_shape_failures)
    if schema_failure_reasons:
        failure_reasons.append(f"product graph schema failed: {'; '.join(schema_failure_reasons)}")
    surface_results = []
    for probe in surface_probes:
        result = {key: value for key, value in probe.items() if key != "payload"}
        surface_results.append(result)
        if result.get("status") != "pass":
            failure_reasons.append(
                f"{result.get('surface', 'surface')} surface failed: {result.get('message', 'unknown error')}"
            )
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
        "query": query_text,
        "gap_ids": [str(item) for item in query.get("gap_ids", [])],
        "required_surfaces": required_surfaces,
        "required_source_types": required_source_types,
        "surfaces_checked": surfaces_checked,
        "surface_results": surface_results,
        "missing_surfaces": missing_surfaces,
        "failure_reasons": failure_reasons,
        "provider_checks": query_provider_checks,
        "status": status,
        "row_count": row_count,
        "schema_status": "fail" if schema_failure_reasons else "pass",
        "schema_failure_reasons": schema_failure_reasons,
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


def _run_surface_probe(surface: str, db_path: Path, query_text: str) -> Dict[str, Any]:
    normalized = surface.strip()
    normalized_key = normalized.lower()
    try:
        if normalized_key in {"cli", "core"}:
            payload = query_evidence(db_path, query_text, compact_graph=True)
            return _surface_probe_result(normalized, "core.query_evidence", db_path, payload)
        if normalized_key == "api":
            from apps.api import main as api_main
            from fastapi.testclient import TestClient

            response = TestClient(api_main.app).get(
                "/query",
                params={"q": query_text, "db_path": str(db_path), "compact_graph": "true"},
            )
            if response.status_code >= 400:
                raise ValueError(f"FastAPI query returned HTTP {response.status_code}: {response.text}")
            payload = response.json()
            return _surface_probe_result(normalized, "fastapi.testclient.query", db_path, payload)
        if normalized_key in {"api_live", "api-live"}:
            base_url = os.environ.get("ASIP_API_BASE_URL", "").strip()
            if not base_url:
                return {
                    "surface": normalized,
                    "transport": "fastapi.uvicorn.http.query",
                    "status": "not_configured",
                    "db_path": str(db_path),
                    "base_url": "",
                    "url": "",
                    "endpoint": "/query",
                    "row_count": 0,
                    "graph_node_count": 0,
                    "graph_edge_count": 0,
                    "message": "ASIP_API_BASE_URL is not configured; start a live uvicorn API server for API_LIVE proof",
                }
            payload = _query_live_api(base_url, db_path, query_text)
            result = _surface_probe_result(normalized, "fastapi.uvicorn.http.query", db_path, payload)
            result["base_url"] = base_url.rstrip("/")
            result["url"] = _live_api_query_url(base_url, db_path, query_text)
            result["endpoint"] = "/query"
            return result
        if normalized_key == "mcp":
            from apps.mcp import server as mcp_server
            from apps.mcp import tools as mcp_tools

            payload = mcp_tools.search_evidence(query_text, db_path=str(db_path), compact_graph=True)
            result = _surface_probe_result(normalized, "mcp.tool-direct.search_evidence", db_path, payload)
            result["server_registered"] = any(tool.__name__ == "search_evidence" for tool in mcp_server.MCP_PRODUCT_TOOLS)
            return result
        if normalized_key in {"mcp_protocol", "mcp-protocol"}:
            protocol_python = os.environ.get("ASIP_MCP_PROTOCOL_PYTHON", "").strip()
            if not protocol_python:
                return {
                    "surface": normalized,
                    "transport": "mcp.stdio.protocol.search_evidence",
                    "status": "not_configured",
                    "db_path": str(db_path),
                    "command": "",
                    "server_args": ["-m", "apps.mcp.server"],
                    "tool": "search_evidence",
                    "row_count": 0,
                    "graph_node_count": 0,
                    "graph_edge_count": 0,
                    "message": (
                        "ASIP_MCP_PROTOCOL_PYTHON is not configured; point it at a Python runtime "
                        "with the optional mcp package installed"
                    ),
                }
            protocol_result = _query_mcp_protocol(protocol_python, db_path, query_text)
            payload = protocol_result["payload"]
            result = _surface_probe_result(normalized, "mcp.stdio.protocol.search_evidence", db_path, payload)
            result["tool_count"] = protocol_result.get("tool_count", 0)
            result["server_registered"] = bool(protocol_result.get("tool_registered"))
            result["command"] = protocol_python
            result["server_args"] = ["-m", "apps.mcp.server"]
            result["tool"] = "search_evidence"
            return result
        if normalized_key == "web":
            base_url = os.environ.get("ASIP_WEB_BASE_URL", "").strip()
            if not base_url:
                return {
                    "surface": normalized,
                    "transport": "next-bff.query",
                    "status": "not_configured",
                    "db_path": str(db_path),
                    "row_count": 0,
                    "graph_node_count": 0,
                    "graph_edge_count": 0,
                    "message": "ASIP_WEB_BASE_URL is not configured; use no-mock browser e2e for Web surface proof",
                }
            payload = _query_web_bff(base_url, db_path, query_text)
            return _surface_probe_result(normalized, "next-bff.query", db_path, payload)
        return {
            "surface": normalized,
            "transport": "unknown",
            "status": "fail",
            "db_path": str(db_path),
            "row_count": 0,
            "graph_node_count": 0,
            "graph_edge_count": 0,
            "message": f"unsupported acceptance surface: {surface}",
        }
    except Exception as exc:
        return {
            "surface": normalized,
            "transport": _surface_transport_name(normalized_key),
            "status": "fail",
            "db_path": str(db_path),
            "row_count": 0,
            "graph_node_count": 0,
            "graph_edge_count": 0,
            "message": str(exc),
        }


def _query_web_bff(base_url: str, db_path: Path, query_text: str) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/api/workbench/query?{urllib.parse.urlencode({'q': query_text, 'dbPath': str(db_path)})}"
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=_live_query_timeout_seconds()) as response:
        return json.loads(response.read().decode("utf-8"))


def _query_live_api(base_url: str, db_path: Path, query_text: str) -> Dict[str, Any]:
    url = _live_api_query_url(base_url, db_path, query_text)
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=_live_query_timeout_seconds()) as response:
        return json.loads(response.read().decode("utf-8"))


def _live_api_query_url(base_url: str, db_path: Path, query_text: str) -> str:
    return (
        f"{base_url.rstrip('/')}/query?"
        f"{urllib.parse.urlencode({'q': query_text, 'db_path': str(db_path), 'compact_graph': 'true'})}"
    )


def _live_query_timeout_seconds() -> int:
    raw = os.environ.get("ASIP_LIVE_QUERY_TIMEOUT_SECONDS", "90").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 90


def _query_mcp_protocol(protocol_python: str, db_path: Path, query_text: str) -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[4]
    timeout_seconds = int(os.environ.get("ASIP_MCP_PROTOCOL_TIMEOUT_SECONDS", "60") or "60")
    script = r'''
import asyncio
import json
import os
import sys
from pathlib import Path

repo_root = Path(sys.argv[1])
db_path = sys.argv[2]
query_text = sys.argv[3]
sys.path.insert(0, str(repo_root / "packages/core/src"))
sys.path.insert(0, str(repo_root))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    env = os.environ.copy()
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "apps.mcp.server"],
        env=env,
    )
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            tool_names = [tool.name for tool in tools.tools]
            result = await session.call_tool(
                "search_evidence",
                {"query": query_text, "db_path": db_path, "compact_graph": True},
            )
            payload = None
            structured = getattr(result, "structuredContent", None)
            if isinstance(structured, dict):
                payload = structured.get("result", structured)
            if payload is None and result.content:
                text = getattr(result.content[0], "text", "")
                payload = json.loads(text)
            print(json.dumps({
                "tool_count": len(tool_names),
                "tool_registered": "search_evidence" in tool_names,
                "payload": payload,
            }, sort_keys=True))


asyncio.run(main())
'''
    env = os.environ.copy()
    python_path_parts = [str(repo_root / "packages/core/src"), str(repo_root)]
    if env.get("PYTHONPATH"):
        python_path_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(python_path_parts)
    completed = subprocess.run(
        [protocol_python, "-c", script, str(repo_root), str(db_path), query_text],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        detail = stderr or stdout or f"exit code {completed.returncode}"
        raise RuntimeError(f"MCP protocol probe failed: {detail}")
    for line in reversed(completed.stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        result = json.loads(line)
        if not result.get("tool_registered"):
            raise RuntimeError("MCP protocol server did not register search_evidence")
        payload = result.get("payload")
        if not isinstance(payload, Mapping):
            raise RuntimeError("MCP protocol search_evidence returned no structured payload")
        return result
    raise RuntimeError("MCP protocol probe returned no JSON payload")


def _surface_probe_result(surface: str, transport: str, db_path: Path, payload: Mapping[str, Any]) -> Dict[str, Any]:
    rows, graph, payload_shape_failures = _validated_surface_payload(payload)
    graph_failures = _surface_graph_contract_failures(graph)
    db_path_failures = _surface_payload_db_path_failures(surface, db_path, payload)
    failures = [*payload_shape_failures, *graph_failures, *db_path_failures]
    message = "; ".join(failures) if failures else "ok"
    if not rows:
        message = "query returned no rows" if message == "ok" else f"query returned no rows; {message}"
    return {
        "surface": surface,
        "transport": transport,
        "status": "pass" if rows and not failures else "fail",
        "db_path": str(db_path),
        "row_count": len(rows),
        "graph_node_count": len(graph.get("nodes", [])),
        "graph_edge_count": len(graph.get("edges", [])),
        "message": message,
        "payload": payload,
    }


def _surface_payload_db_path_failures(surface: str, db_path: Path, payload: Mapping[str, Any]) -> List[str]:
    normalized = surface.strip().lower()
    if normalized not in {"web", "api_live", "api-live", "mcp_protocol", "mcp-protocol"}:
        return []
    label = "Web" if normalized == "web" else ("MCP_PROTOCOL" if normalized in {"mcp_protocol", "mcp-protocol"} else "API_LIVE")
    payload_db_path = str(payload.get("db_path") or payload.get("dbPath") or "").strip()
    if not payload_db_path:
        return [f"{label} surface payload db_path is missing"]
    if payload_db_path != str(db_path):
        return [f"{label} surface payload db_path mismatch: expected {db_path}, got {payload_db_path}"]
    return []


def _validated_surface_payload(payload: Mapping[str, Any]) -> tuple[List[Mapping[str, Any]], Mapping[str, Any], List[str]]:
    failures: List[str] = []
    rows_value = payload.get("rows", [])
    if not isinstance(rows_value, list):
        failures.append(f"malformed rows payload: expected list, got {type(rows_value).__name__}")
        rows: List[Mapping[str, Any]] = []
    else:
        rows = []
        for index, row in enumerate(rows_value):
            if isinstance(row, Mapping):
                rows.append(row)
            else:
                failures.append(f"malformed rows payload: row {index} is {type(row).__name__}, expected object")
    graph_value = payload.get("graph", {})
    graph: Mapping[str, Any]
    if not isinstance(graph_value, Mapping):
        failures.append(f"malformed graph payload: expected object, got {type(graph_value).__name__}")
        graph = {}
    else:
        graph = graph_value
    return rows, graph, failures


def _surface_graph_contract_failures(graph: Mapping[str, Any]) -> List[str]:
    failures: List[str] = []
    for node in graph.get("nodes", []) or []:
        if not isinstance(node, Mapping):
            failures.append("invalid graph node payload")
            break
        kind = str(node.get("kind") or "").strip()
        if not kind:
            failures.append("missing graph node kind")
            break
        if kind not in ALLOWED_PRODUCT_NODE_KINDS:
            failures.append(f"non-product graph node kind: {kind}")
            break
        failures.extend(_concept_function_node_contract_failures(node))
    for edge in graph.get("edges", []) or []:
        if not isinstance(edge, Mapping):
            failures.append("invalid graph edge payload")
            continue
        relation = str(edge.get("relation") or "").strip()
        if not relation:
            failures.append("missing graph relation")
            break
        if relation not in ALLOWED_PRODUCT_RELATIONS:
            failures.append(f"non-product graph relation: {relation}")
            break
    return failures


def _concept_function_node_contract_failures(node: Mapping[str, Any]) -> List[str]:
    if str(node.get("kind") or "").strip() != "function":
        return []
    attr = node.get("attr") if isinstance(node.get("attr"), Mapping) else {}
    node_id = str(node.get("id") or "")
    is_concept = attr.get("is_concept") is True or ":concept:" in node_id
    if not is_concept:
        return []
    implementations = attr.get("concept_implementations")
    raw_implementations = attr.get("raw_implementations")
    raw_function_names = attr.get("raw_function_names")
    implementation_records = (
        implementations
        if isinstance(implementations, list) and implementations
        else raw_implementations
        if isinstance(raw_implementations, list) and raw_implementations
        else []
    )
    implementation_count = _int_or_default(
        attr.get("concept_implementation_count") or attr.get("raw_implementation_count"),
        len(implementation_records),
    )
    if not implementation_records and not (isinstance(raw_function_names, list) and raw_function_names):
        return [f"concept function node missing implementation list: {node_id}"]
    if implementation_count < len(implementation_records):
        return [f"concept function node implementation count is below listed implementations: {node_id}"]
    for item in implementation_records:
        if not isinstance(item, Mapping) or not str(item.get("function_name") or "").strip():
            return [f"concept function node implementation missing function_name: {node_id}"]
    if isinstance(raw_function_names, list) and any(not str(item or "").strip() for item in raw_function_names):
        return [f"concept function node raw_function_names contains blank item: {node_id}"]
    return []


def _surface_transport_name(surface: str) -> str:
    return {
        "api": "fastapi.query",
        "api_live": "fastapi.uvicorn.http.query",
        "api-live": "fastapi.uvicorn.http.query",
        "cli": "core.query_evidence",
        "core": "core.query_evidence",
        "mcp": "mcp.search_evidence",
        "mcp_protocol": "mcp.stdio.protocol.search_evidence",
        "mcp-protocol": "mcp.stdio.protocol.search_evidence",
        "web": "next-bff.query",
    }.get(surface, "unknown")


def _run_provider_checks(
    db_path: Path,
    provider_settings: Mapping[str, object],
    edge_provider: Optional[EdgeProvider],
    embedding_transport: Optional[EmbeddingTransport] = None,
) -> Dict[str, Any]:
    if not provider_settings:
        return {}
    checks = {
        PROVIDER_CHECK_IDS[0]: _embedding_provenance_check(db_path, provider_settings),
        PROVIDER_CHECK_IDS[1]: _embedding_live_smoke(provider_settings, embedding_transport),
        PROVIDER_CHECK_IDS[2]: _semantic_edge_provenance_check(db_path, provider_settings),
        PROVIDER_CHECK_IDS[3]: _doc_node_provenance_check(db_path, provider_settings),
        PROVIDER_CHECK_IDS[4]: _semantic_edge_smoke(provider_settings, edge_provider),
    }
    return {check_id: checks[check_id] for check_id in PROVIDER_CHECK_IDS}


def _database_health_failures(db_path: Path) -> List[str]:
    failures: List[str] = []
    if not db_path.exists():
        return [f"database does not exist: {db_path}"]
    try:
        con = sqlite3.connect(str(db_path), timeout=5.0)
        con.execute("pragma query_only = on")
        con.row_factory = sqlite3.Row
        for row in con.execute("select id, status from corpora order by id").fetchall():
            status = str(row["status"])
            if status != "indexed":
                failures.append(f"corpus {row['id']} status is {status}")
        for row in con.execute("select id, status, message from jobs where kind = 'index' order by id").fetchall():
            status = str(row["status"])
            if status in {"failed", "running", "queued", "indexing"}:
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
        total_chunks = int(con.execute("select count(*) from chunks").fetchone()[0] or 0)
        embedded_chunks = int(con.execute("select count(distinct chunk_id) from embeddings").fetchone()[0] or 0)
        missing_embedding_chunks = int(
            con.execute(
                """
                select count(*)
                from chunks c
                where not exists (
                  select 1 from embeddings e where e.chunk_id = c.id
                )
                """
            ).fetchone()[0]
            or 0
        )
    except sqlite3.DatabaseError as exc:
        return {"status": "fail", "message": f"embedding provenance query failed: {exc}"}

    provider_rows = []
    fallback_rows = 0
    total_rows = 0
    for provider, model, metadata_json in rows:
        total_rows += 1
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
            "provenance_status": "fail",
            "coverage_status": "fail",
            "total_count": total_rows,
            "embedding_count": len(provider_rows),
            "fallback_count": fallback_rows,
            "total_chunks": total_chunks,
            "embedded_chunks": embedded_chunks,
            "missing_embedding_chunks": missing_embedding_chunks,
        }
    coverage_status = (
        "pass"
        if fallback_rows == 0
        and len(matching_rows) == total_rows
        and missing_embedding_chunks == 0
        and embedded_chunks == total_chunks
        else "partial"
    )
    message = "provider embedding provenance exists"
    if coverage_status != "pass":
        coverage_notes = []
        if fallback_rows:
            coverage_notes.append(f"{fallback_rows} deterministic fallback embeddings remain")
        if len(matching_rows) != total_rows:
            coverage_notes.append(f"{len(matching_rows)}/{total_rows} embeddings match the configured provider")
        if missing_embedding_chunks:
            coverage_notes.append(f"{missing_embedding_chunks} chunks have no embeddings")
        if embedded_chunks != total_chunks:
            coverage_notes.append(f"{embedded_chunks}/{total_chunks} chunks have embeddings")
        message = f"provider embedding provenance exists but {'; '.join(coverage_notes)}"
    return {
        "status": coverage_status,
        "provenance_status": "pass",
        "coverage_status": coverage_status,
        "message": message,
        "provider": expected_provider,
        "model": expected_model,
        "embedding_count": len(matching_rows),
        "total_count": total_rows,
        "provider_embedding_count": len(provider_rows),
        "fallback_count": fallback_rows,
        "total_chunks": total_chunks,
        "embedded_chunks": embedded_chunks,
        "missing_embedding_chunks": missing_embedding_chunks,
    }


def _embedding_live_smoke(
    provider_settings: Mapping[str, object],
    embedding_transport: Optional[EmbeddingTransport] = None,
) -> Dict[str, Any]:
    embedding = provider_settings.get("embedding")
    if not isinstance(embedding, Mapping):
        return {"status": "fail", "message": "embedding provider settings are missing"}
    model_name = str(embedding.get("model") or embedding.get("embedding_model") or "").strip()
    if not model_name:
        return {"status": "fail", "message": "embedding model is missing"}
    edge = provider_settings.get("edge") if isinstance(provider_settings.get("edge"), Mapping) else {}
    headers = embedding.get("extra_headers")
    if not isinstance(headers, Mapping):
        headers = edge.get("extra_headers") if isinstance(edge, Mapping) else {}
    config = EmbeddingProviderConfig(
        provider=str(embedding.get("provider") or "ollama"),
        model=model_name,
        api_base_url=str(embedding.get("api_base_url") or embedding.get("base_url") or "http://localhost:11434"),
        api_path=str(embedding.get("api_path") or ""),
        extra_headers={str(key): str(value) for key, value in dict(headers or {}).items()},
        timeout_seconds=_acceptance_provider_timeout_seconds(embedding),
    )
    try:
        provider = create_embedding_provider(config)
        if embedding_transport is not None and hasattr(provider, "transport"):
            provider.transport = embedding_transport  # type: ignore[attr-defined]
        vectors = provider.embed(["ASIP embedding provider smoke"], config)
    except Exception as exc:
        return {
            "status": "fail",
            "message": f"embedding provider failed: {exc}",
            "provider": config.provider,
            "model": config.model,
        }
    if not vectors:
        return {
            "status": "fail",
            "message": "embedding provider returned no embeddings",
            "provider": config.provider,
            "model": config.model,
            "embedding_count": 0,
        }
    vector_dimension = len(vectors[0]) if vectors and isinstance(vectors[0], list) else 0
    if vector_dimension <= 0:
        return {
            "status": "fail",
            "message": "embedding provider returned an empty vector",
            "provider": config.provider,
            "model": config.model,
            "embedding_count": len(vectors),
            "vector_dimension": vector_dimension,
        }
    return {
        "status": "pass",
        "provider": config.provider,
        "model": config.model,
        "embedding_count": len(vectors),
        "vector_dimension": vector_dimension,
    }


def _semantic_edge_provenance_check(db_path: Path, provider_settings: Mapping[str, object]) -> Dict[str, Any]:
    return _semantic_extractor_provenance_check(
        db_path,
        provider_settings,
        extractor="semantic_edges",
        job_kinds={"semantic_edges", "semantic_edges_batch"},
        label="semantic edges",
        no_rows_pass=False,
    )


def _doc_node_provenance_check(db_path: Path, provider_settings: Mapping[str, object]) -> Dict[str, Any]:
    return _semantic_extractor_provenance_check(
        db_path,
        provider_settings,
        extractor="doc_nodes",
        job_kinds={"doc_nodes_batch"},
        label="doc-node semantic edges",
        no_rows_pass=False,
    )


def _semantic_extractor_provenance_check(
    db_path: Path,
    provider_settings: Mapping[str, object],
    *,
    extractor: str,
    job_kinds: set[str],
    label: str,
    no_rows_pass: bool,
) -> Dict[str, Any]:
    edge = provider_settings.get("edge")
    if not isinstance(edge, Mapping):
        return {"status": "fail", "message": "edge provider settings are missing"}
    expected_provider = str(edge.get("provider") or "ollama").strip()
    expected_model = str(edge.get("model") or edge.get("preferred") or "").strip()
    if not expected_model:
        return {"status": "fail", "message": "edge model is missing"}
    try:
        con = sqlite3.connect(str(db_path), timeout=5.0)
        con.execute("pragma query_only = on")
        con.row_factory = sqlite3.Row
        rows = con.execute(
            """
            select source, provenance_json
            from edges
            where stage = 'semantic'
            """
        ).fetchall()
        job_rows = con.execute("select id, kind, status, metadata_json from jobs").fetchall()
    except sqlite3.DatabaseError as exc:
        return {"status": "fail", "message": f"semantic edge provenance query failed: {exc}"}

    latest_index_job_id = _latest_succeeded_job_id(job_rows, "index")
    latest_graph_rebuild_job_id = _latest_succeeded_job_id(job_rows, "graph_rebuild")
    freshness_floor_job_id = max(
        job_id
        for job_id in (latest_index_job_id, latest_graph_rebuild_job_id)
        if job_id is not None
    ) if latest_index_job_id is not None or latest_graph_rebuild_job_id is not None else None
    valid_job_ids = _valid_semantic_job_ids(job_rows, expected_provider, expected_model, job_kinds)
    matching_edges = 0
    total_extractor_edges = 0
    ignored_edges = 0
    missing_or_invalid_job_edges = 0
    stale_edges = 0
    job_ids: set[int] = set()
    stale_job_ids: set[int] = set()
    for source, provenance_json in rows:
        try:
            provenance = json.loads(str(provenance_json or "{}"))
        except json.JSONDecodeError:
            provenance = {}
        provider = str(provenance.get("provider") or source or "").strip()
        model = str(provenance.get("model") or "").strip()
        if provider != expected_provider or model != expected_model:
            continue
        if str(provenance.get("extractor") or "") != extractor:
            ignored_edges += 1
            continue
        total_extractor_edges += 1
        job_id = _optional_int(provenance.get("job_id"))
        if job_id is None or job_id not in valid_job_ids:
            missing_or_invalid_job_edges += 1
            continue
        if freshness_floor_job_id is not None and job_id < freshness_floor_job_id:
            stale_edges += 1
            stale_job_ids.add(job_id)
            continue
        matching_edges += 1
        job_ids.add(job_id)
    if stale_edges:
        return {
            "status": "partial",
            "message": f"persisted {label} are older than latest succeeded index or graph rebuild job",
            "provider": expected_provider,
            "model": expected_model,
            "edge_count": matching_edges,
            "extractor_edge_count": total_extractor_edges,
            "job_ids": sorted(job_ids),
            "stale_edge_count": stale_edges,
            "stale_job_ids": sorted(stale_job_ids),
            "latest_index_job_id": latest_index_job_id,
            "latest_graph_rebuild_job_id": latest_graph_rebuild_job_id,
            "ignored_edge_count": ignored_edges,
            "missing_or_invalid_job_edge_count": missing_or_invalid_job_edges,
        }
    if total_extractor_edges <= 0 and no_rows_pass:
        return {
            "status": "pass",
            "message": f"no persisted {label} are present",
            "provider": expected_provider,
            "model": expected_model,
            "edge_count": 0,
            "extractor_edge_count": 0,
            "job_ids": [],
            "latest_index_job_id": latest_index_job_id,
            "latest_graph_rebuild_job_id": latest_graph_rebuild_job_id,
            "stale_edge_count": 0,
            "stale_job_ids": [],
            "ignored_edge_count": ignored_edges,
            "missing_or_invalid_job_edge_count": 0,
        }
    if matching_edges <= 0:
        return {
            "status": "fail",
            "message": f"no persisted {label} were generated by the configured provider from a succeeded semantic job",
            "provider": expected_provider,
            "model": expected_model,
            "edge_count": 0,
            "extractor_edge_count": total_extractor_edges,
            "job_ids": sorted(job_ids),
            "latest_index_job_id": latest_index_job_id,
            "latest_graph_rebuild_job_id": latest_graph_rebuild_job_id,
            "stale_edge_count": stale_edges,
            "stale_job_ids": sorted(stale_job_ids),
            "ignored_edge_count": ignored_edges,
            "missing_or_invalid_job_edge_count": missing_or_invalid_job_edges,
        }
    if missing_or_invalid_job_edges:
        return {
            "status": "partial",
            "message": f"some persisted {label} have missing or invalid semantic job provenance",
            "provider": expected_provider,
            "model": expected_model,
            "edge_count": matching_edges,
            "extractor_edge_count": total_extractor_edges,
            "job_ids": sorted(job_ids),
            "stale_edge_count": stale_edges,
            "stale_job_ids": sorted(stale_job_ids),
            "latest_index_job_id": latest_index_job_id,
            "latest_graph_rebuild_job_id": latest_graph_rebuild_job_id,
            "ignored_edge_count": ignored_edges,
            "missing_or_invalid_job_edge_count": missing_or_invalid_job_edges,
        }
    return {
        "status": "pass",
        "provider": expected_provider,
        "model": expected_model,
        "edge_count": matching_edges,
        "extractor_edge_count": total_extractor_edges,
        "job_ids": sorted(job_ids),
        "latest_index_job_id": latest_index_job_id,
        "latest_graph_rebuild_job_id": latest_graph_rebuild_job_id,
        "stale_edge_count": stale_edges,
        "stale_job_ids": sorted(stale_job_ids),
        "ignored_edge_count": ignored_edges,
        "missing_or_invalid_job_edge_count": missing_or_invalid_job_edges,
    }


def _latest_succeeded_job_id(rows: Iterable[sqlite3.Row], kind: str) -> Optional[int]:
    latest: Optional[int] = None
    for row in rows:
        try:
            job_id = int(row["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if str(row["kind"] or "") != kind:
            continue
        if normalize_job_status(str(row["status"] or "")) != "succeeded":
            continue
        latest = job_id if latest is None else max(latest, job_id)
    return latest


def _valid_semantic_edge_job_ids(rows: Iterable[sqlite3.Row], expected_provider: str, expected_model: str) -> set[int]:
    return _valid_semantic_job_ids(rows, expected_provider, expected_model, {"semantic_edges", "semantic_edges_batch"})


def _valid_semantic_job_ids(
    rows: Iterable[sqlite3.Row],
    expected_provider: str,
    expected_model: str,
    job_kinds: set[str],
) -> set[int]:
    valid: set[int] = set()
    for row in rows:
        try:
            job_id = int(row["id"])
        except (KeyError, TypeError, ValueError):
            continue
        if str(row["kind"] or "") not in job_kinds:
            continue
        if normalize_job_status(str(row["status"] or "")) != "succeeded":
            continue
        try:
            metadata = json.loads(str(row["metadata_json"] or "{}"))
        except json.JSONDecodeError:
            metadata = {}
        provider_settings = metadata.get("provider_settings")
        edge = provider_settings.get("edge") if isinstance(provider_settings, Mapping) else None
        if not isinstance(edge, Mapping):
            continue
        provider = str(edge.get("provider") or "ollama").strip()
        model = str(edge.get("model") or edge.get("preferred") or "").strip()
        if provider == expected_provider and model == expected_model:
            valid.add(job_id)
    return valid


def _optional_int(value: object) -> Optional[int]:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


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
        timeout_seconds=_acceptance_provider_timeout_seconds(edge),
    )
    provider = edge_provider or create_edge_provider(config)
    prompt = (
        "CASE provider-smoke\n"
        "TERMS: program_gcvm_l2, GCVM_L2_CNTL\n"
        "SNIPPET:\n"
        "1: program_gcvm_l2 writes register GCVM_L2_CNTL\n"
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
    edge_count, persistable_edge_count = _semantic_smoke_edge_counts(generated)
    if edge_count <= 0:
        return {
            "status": "fail",
            "message": "semantic edge provider returned no edges",
            "provider": config.provider,
            "model": config.preferred,
            "edge_count": 0,
        }
    if persistable_edge_count <= 0:
        return {
            "status": "fail",
            "message": "semantic edge provider returned no product-schema-persistable edges",
            "provider": config.provider,
            "model": config.preferred,
            "edge_count": edge_count,
            "persistable_edge_count": 0,
        }
    return {
        "status": "pass",
        "provider": config.provider,
        "model": config.preferred,
        "edge_count": edge_count,
        "persistable_edge_count": persistable_edge_count,
    }


def _semantic_smoke_edge_counts(generated: Mapping[str, Any]) -> tuple[int, int]:
    cases = generated.get("cases", []) if isinstance(generated, Mapping) else []
    edge_count = 0
    persistable_edge_count = 0
    for case in cases:
        if not isinstance(case, Mapping):
            continue
        for edge in case.get("edges", []):
            if not isinstance(edge, Mapping):
                continue
            edge_count += 1
            if _semantic_smoke_edge_is_persistable(edge):
                persistable_edge_count += 1
    return edge_count, persistable_edge_count


def _semantic_smoke_edge_is_persistable(edge: Mapping[str, Any]) -> bool:
    src = str(edge.get("src") or "").strip()
    dst = str(edge.get("dst") or "").strip()
    relation = normalize_product_relation(str(edge.get("relation") or "relates_to"))
    if not src or not dst or src == dst or not relation:
        return False
    if product_endpoint_kind(src) not in ALLOWED_PRODUCT_NODE_KINDS:
        return False
    if product_endpoint_kind(dst) not in ALLOWED_PRODUCT_NODE_KINDS:
        return False
    return True


def _acceptance_provider_timeout_seconds(edge_settings: Mapping[str, object]) -> int:
    configured = _int_or_default(edge_settings.get("timeout_seconds"), 60)
    override = os.environ.get("ASIP_ACCEPTANCE_PROVIDER_TIMEOUT_SECONDS", "").strip()
    if override:
        configured = _int_or_default(override, configured)
    return max(1, min(configured, 120))


def _int_or_default(value: object, default: int) -> int:
    try:
        return int(value or default)
    except (TypeError, ValueError):
        return default


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
        "| ID | Status | Schema | Rows | Source types | Graph | Surfaces | Missing surfaces | Failure reasons | Query |",
        "| --- | --- | --- | ---: | --- | ---: | --- | --- | --- | --- |",
        ]
    )
    for item in result["queries"]:
        missing = ", ".join(item["missing_surfaces"]) if item["missing_surfaces"] else "-"
        source_types = ", ".join(item.get("source_types", [])) if item.get("source_types") else "-"
        failures = ", ".join(str(reason) for reason in item.get("failure_reasons", [])) if item.get("failure_reasons") else "-"
        graph = f"{item['graph_node_count']} nodes / {item['graph_edge_count']} edges"
        surfaces = "; ".join(_format_surface_result(surface) for surface in item.get("surface_results", [])) or "-"
        query = str(item["query"]).replace("|", "\\|")
        lines.append(
            f"| {item['id']} | {item['status']} | {item.get('schema_status', '')} | "
            f"{item['row_count']} | {source_types} | "
            f"{graph} | {surfaces} | {missing} | {failures} | {query} |"
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
            if "vector_dimension" in check:
                details.append(f"vector_dim={check['vector_dimension']}")
            if "fallback_count" in check:
                details.append(f"fallback={check['fallback_count']}")
            if "missing_embedding_chunks" in check:
                details.append(f"missing_chunk_embeddings={check['missing_embedding_chunks']}")
            if "embedded_chunks" in check and "total_chunks" in check:
                details.append(f"embedded_chunks={check['embedded_chunks']}/{check['total_chunks']}")
            if "edge_count" in check:
                details.append(f"edges={check['edge_count']}")
            if "stale_edge_count" in check:
                details.append(f"stale_edges={check['stale_edge_count']}")
            if "job_ids" in check:
                job_ids = check.get("job_ids") or []
                if isinstance(job_ids, list) and job_ids:
                    details.append(f"jobs={','.join(str(job_id) for job_id in job_ids)}")
            if "stale_job_ids" in check:
                stale_job_ids = check.get("stale_job_ids") or []
                if isinstance(stale_job_ids, list) and stale_job_ids:
                    details.append(f"stale_jobs={','.join(str(job_id) for job_id in stale_job_ids)}")
            if "latest_index_job_id" in check and check.get("latest_index_job_id") is not None:
                details.append(f"latest_index_job={check['latest_index_job_id']}")
            if "ignored_edge_count" in check:
                details.append(f"ignored={check['ignored_edge_count']}")
            if check.get("message"):
                details.append(str(check["message"]))
            lines.append(
                f"| {name} | {check.get('status', '')} | {check.get('provider', '')} | "
                f"{check.get('model', '')} | {', '.join(details) or '-'} |"
            )
    lines.append("")
    return "\n".join(lines)


def _format_surface_result(surface: Mapping[str, Any]) -> str:
    graph = f"{surface.get('graph_node_count', 0)}n/{surface.get('graph_edge_count', 0)}e"
    return (
        f"{surface.get('surface', '')} {surface.get('status', '')} "
        f"{surface.get('transport', '')} rows={surface.get('row_count', 0)} graph={graph}"
    ).strip()


def _unique_ordered(items: Iterable[str]) -> List[str]:
    seen = set()
    unique: List[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique
