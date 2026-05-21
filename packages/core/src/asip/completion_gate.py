"""Aggregate ASIP final-goal proof artifacts into one gate."""

from __future__ import annotations

import json
import sqlite3
import hashlib
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from .acceptance import DEFAULT_ACCEPTANCE_QUERIES, PROVIDER_CHECK_IDS
from .storage import normalize_job_status


_COUNT_TABLES = ("corpora", "documents", "chunks", "evidence", "edges", "embeddings")
_EXPECTED_AQ_IDS = tuple(str(query["id"]) for query in DEFAULT_ACCEPTANCE_QUERIES)
_EXPANDED_MIN_COUNTS = {
    "documents": 1000,
    "chunks": 100000,
    "evidence": 1000000,
    "edges": 10000,
    "embeddings": 100000,
    "linux_amdgpu_documents": 1000,
    "linux_amdgpu_chunks": 100000,
    "linux_asic_reg_documents": 400,
}
_PASS = {"pass", "passed", "ok", "succeeded"}
_REQUIRED_PROVIDER_CHECKS = PROVIDER_CHECK_IDS
_REQUIRED_ARTIFACT_SOURCES = {
    "acceptance": ("asip.acceptance",),
    "web_acceptance": ("asip.acceptance",),
    "provider_gate": ("asip.provider_gate",),
    "runtime_semantic_freshness": ("asip.runtime_semantic_freshness_qa",),
    "browser_gate": ("asip.web.browser_gate_preflight", "asip.web.browser_e2e"),
    "no_server_smoke": ("asip.web.no_server_smoke",),
    "performance_smoke": ("fixture_performance_smoke",),
    "residual_acceptance": ("asip.residual_acceptance",),
    "git_gate": ("asip.git_gate",),
}
_OPTIONAL_ARTIFACT_SOURCES = {
    "in_app_browser": ("asip.web.in_app_browser_probe", "asip.web.browser_e2e"),
}
_REQUIRED_BROWSER_E2E_TESTS = (
    "acceptance page runs no-mock AQ01 through the real workbench API",
    "graph page uses URL dbPath for no-mock graph and query requests",
    "graph page loads current data/asip.db through browser and API",
    "graph page filters no-mock graph layers and shows edge provenance",
    "evidence page initial query uses URL dbPath without default DB fallback",
)
_REQUIRED_BROWSER_E2E_TEST_FILE = "workbench-smoke.spec.ts"
_REQUIRED_BROWSER_CURRENT_DB_PROBE_SURFACES = (
    "graph_page_api_request",
    "direct_api_document_request",
    "graph_page_concept_detail_selection",
)
_NO_SERVER_ARTIFACT_INPUT_OPTIONS = {
    "--browser-json": "browser_gate",
    "--in-app-browser-json": "in_app_browser",
    "--provider-json": "provider_gate",
    "--runtime-semantic-json": "runtime_semantic_freshness",
    "--semantic-quality-json": "semantic_quality",
    "--callback-audit-json": "callback_audit",
    "--acceptance-json": "acceptance",
    "--web-acceptance-json": "web_acceptance",
}
_PROVIDER_CHECK_JOB_KINDS = {
    "semantic_edge_provenance": ("semantic_edges", "semantic_edges_batch"),
    "doc_node_provenance": ("doc_nodes_batch",),
}


def run_completion_gate(
    db_path: Path,
    *,
    acceptance_json: Optional[Path] = None,
    web_acceptance_json: Optional[Path] = None,
    provider_json: Optional[Path] = None,
    runtime_semantic_json: Optional[Path] = None,
    semantic_quality_json: Optional[Path] = None,
    callback_audit_json: Optional[Path] = None,
    browser_json: Optional[Path] = None,
    in_app_browser_json: Optional[Path] = None,
    no_server_json: Optional[Path] = None,
    performance_json: Optional[Path] = None,
    residual_acceptance_json: Optional[Path] = None,
    git_gate_json: Optional[Path] = None,
    output_json: Optional[Path] = None,
    output_md: Optional[Path] = None,
    full_integrity_check: bool = False,
    minimum_counts: Optional[Mapping[str, int]] = None,
) -> Dict[str, Any]:
    """Build a machine-readable completion audit from current local evidence."""

    required_counts = dict(_EXPANDED_MIN_COUNTS if minimum_counts is None else minimum_counts)
    db_health = _database_health(db_path, full_integrity_check=full_integrity_check)
    artifacts = {
        "acceptance": _load_json_artifact(acceptance_json),
        "web_acceptance": _load_json_artifact(web_acceptance_json),
        "provider_gate": _load_json_artifact(provider_json),
        "runtime_semantic_freshness": _load_json_artifact(runtime_semantic_json),
        "semantic_quality": _load_json_artifact(semantic_quality_json),
        "callback_audit": _load_json_artifact(callback_audit_json),
        "browser_gate": _load_json_artifact(browser_json),
        "in_app_browser": _load_json_artifact(in_app_browser_json),
        "no_server_smoke": _load_json_artifact(no_server_json),
        "performance_smoke": _load_json_artifact(performance_json),
        "residual_acceptance": _load_json_artifact(residual_acceptance_json),
        "git_gate": _load_json_artifact(git_gate_json),
    }
    acceptance_payload = artifacts["acceptance"].get("payload")
    web_payload = artifacts["web_acceptance"].get("payload")
    provider_payload = artifacts["provider_gate"].get("payload")
    runtime_semantic_payload = artifacts["runtime_semantic_freshness"].get("payload")
    semantic_quality_payload = artifacts["semantic_quality"].get("payload")
    callback_audit_payload = artifacts["callback_audit"].get("payload")
    browser_payload = artifacts["browser_gate"].get("payload")
    in_app_browser_payload = artifacts["in_app_browser"].get("payload")
    no_server_payload = artifacts["no_server_smoke"].get("payload")
    performance_payload = artifacts["performance_smoke"].get("payload")
    residual_payload = artifacts["residual_acceptance"].get("payload")
    git_payload = artifacts["git_gate"].get("payload")

    requirements = [
        _real_index_requirement(db_health, required_counts),
        _artifact_binding_requirement(db_path, db_health, artifacts),
        _stage1_requirement(db_health),
        _schema_requirement([acceptance_payload, web_payload]),
        _surface_requirement(acceptance_payload, ("CLI", "API", "MCP")),
        _api_live_surface_requirement(acceptance_payload, db_path),
        _mcp_protocol_surface_requirement(acceptance_payload, db_path),
        _web_surface_requirement(web_payload, db_path),
        _acceptance_gate_requirement(acceptance_payload),
        _provider_requirement(provider_payload),
        _stage2_requirement(provider_payload),
        _runtime_semantic_freshness_requirement(runtime_semantic_payload),
        _semantic_quality_requirement(semantic_quality_payload, required=minimum_counts is None),
        _callback_audit_requirement(callback_audit_payload, required=minimum_counts is None),
        _browser_requirement(browser_payload, in_app_browser_payload, db_path, db_health),
        _no_server_requirement(no_server_payload, artifacts),
        _performance_requirement(performance_payload),
        _residual_acceptance_requirement(residual_payload),
        _git_gate_requirement(git_payload),
    ]
    summary = _status_summary(requirements)
    gate_status = "pass" if summary["passed"] == summary["total"] else "blocked"
    failure_reasons = [
        f"{item['id']}: {reason}"
        for item in requirements
        if item["status"] != "pass"
        for reason in item["failure_reasons"]
    ]

    result: Dict[str, Any] = {
        "source": "asip.completion_gate",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "db_path": str(db_path),
        "database": db_health,
        "artifacts": {name: _artifact_record(artifact) for name, artifact in artifacts.items()},
        "requirements": requirements,
        "summary": summary,
        "gate_status": gate_status,
        "failure_reasons": failure_reasons,
    }

    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if output_md:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(_render_markdown(result), encoding="utf-8")
    return result


def _database_health(db_path: Path, *, full_integrity_check: bool) -> Dict[str, Any]:
    if not db_path.exists():
        return {
            "status": "missing",
            "path": str(db_path),
            "integrity_check_type": "integrity_check" if full_integrity_check else "quick_check",
            "integrity_check": "",
            "counts": {},
            "jobs": {},
            "corpora_statuses": [],
            "failure_reasons": ["database file is missing"],
        }
    try:
        with sqlite3.connect(str(db_path), timeout=5.0) as connection:
            connection.execute("pragma query_only = on")
            connection.execute("pragma busy_timeout = 5000")
            integrity_pragma = "integrity_check" if full_integrity_check else "quick_check"
            integrity = str(connection.execute(f"pragma {integrity_pragma}").fetchone()[0])
            counts = {table: _count_table(connection, table) for table in _COUNT_TABLES}
            counts["linux_amdgpu_documents"] = _count_where(
                connection,
                "documents",
                "corpus_id = ?",
                ("linux-amdgpu",),
            )
            counts["linux_amdgpu_chunks"] = _count_joined_linux_chunks(connection)
            counts["linux_asic_reg_documents"] = _count_where(
                connection,
                "documents",
                "corpus_id = ? and path like ?",
                ("linux-amdgpu", "%include/asic_reg%"),
            )
            jobs = {
                "latest_index_job_id": _latest_job_id(connection, "index"),
                "latest_graph_rebuild_job_id": _latest_job_id(connection, "graph_rebuild"),
                "latest_semantic_edges_job_id": _latest_job_id(
                    connection,
                    "semantic_edges",
                    "semantic_edges_batch",
                ),
                "latest_doc_nodes_job_id": _latest_job_id(connection, "doc_nodes_batch"),
            }
            corpora_statuses, corpus_status_failures = _corpus_status_failures(connection)
            blocking_job_failures = _blocking_job_failures(connection)
    except sqlite3.Error as exc:
        return {
            "status": "fail",
            "path": str(db_path),
            "integrity_check_type": "integrity_check" if full_integrity_check else "quick_check",
            "integrity_check": "",
            "counts": {},
            "jobs": {},
            "corpora_statuses": [],
            "failure_reasons": [f"database read failed: {exc}"],
        }

    failure_reasons: List[str] = []
    if integrity != "ok":
        failure_reasons.append(f"sqlite integrity_check returned {integrity}")
    for table in ("documents", "chunks", "evidence"):
        if counts.get(table, 0) <= 0:
            failure_reasons.append(f"{table} has no rows")
    failure_reasons.extend(corpus_status_failures)
    failure_reasons.extend(blocking_job_failures)
    status = "pass" if not failure_reasons else "fail"
    return {
        "status": status,
        "path": str(db_path),
        "integrity_check_type": integrity_pragma,
        "integrity_check": integrity,
        "counts": counts,
        "jobs": jobs,
        "corpora_statuses": corpora_statuses,
        "failure_reasons": failure_reasons,
    }


def _count_table(connection: sqlite3.Connection, table: str) -> int:
    if not _table_exists(connection, table):
        return 0
    return int(connection.execute(f"select count(*) from {table}").fetchone()[0])


def _coerce_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _count_where(
    connection: sqlite3.Connection,
    table: str,
    where: str,
    parameters: Tuple[Any, ...],
) -> int:
    if not _table_exists(connection, table):
        return 0
    return int(connection.execute(f"select count(*) from {table} where {where}", parameters).fetchone()[0])


def _count_joined_linux_chunks(connection: sqlite3.Connection) -> int:
    if not _table_exists(connection, "documents") or not _table_exists(connection, "chunks"):
        return 0
    query = """
        select count(*)
        from chunks
        join documents on documents.id = chunks.document_id
        where documents.corpus_id = ?
    """
    return int(connection.execute(query, ("linux-amdgpu",)).fetchone()[0])


def _latest_job_id(connection: sqlite3.Connection, *kinds: str) -> Optional[int]:
    if not _table_exists(connection, "jobs"):
        return None
    if not kinds:
        return None
    placeholders = ", ".join("?" for _kind in kinds)
    rows = connection.execute(
        f"""
        select id, kind, status from jobs
        where kind in ({placeholders})
        order by id desc
        """,
        kinds,
    ).fetchall()
    for row in rows:
        if normalize_job_status(str(row[2] or "")) == "succeeded":
            return int(row[0])
    return None


def _blocking_job_failures(connection: sqlite3.Connection) -> List[str]:
    if not _table_exists(connection, "jobs"):
        return []
    failures: List[str] = []
    rows = connection.execute("select id, kind, status, message from jobs order by id").fetchall()
    for row in rows:
        normalized_status = normalize_job_status(str(row[2] or ""))
        if normalized_status not in {"failed", "indexing", "queued"}:
            continue
        message = str(row[3] or "")
        suffix = f": {message}" if message else ""
        failures.append(f"job {row[0]} {row[1]} is {row[2]}{suffix}")
    return failures


def _corpus_status_failures(connection: sqlite3.Connection) -> Tuple[List[Dict[str, str]], List[str]]:
    if not _table_exists(connection, "corpora"):
        return [], ["corpora table is missing"]
    if "status" not in _table_columns(connection, "corpora"):
        return [], ["corpora.status column is missing"]

    statuses: List[Dict[str, str]] = []
    failures: List[str] = []
    rows = connection.execute("select id, status from corpora order by id").fetchall()
    for row in rows:
        corpus_id = str(row[0])
        status = str(row[1] or "")
        statuses.append({"id": corpus_id, "status": status})
        if status != "indexed":
            failures.append(f"corpus {corpus_id} status is {status}")
    return statuses, failures


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "select 1 from sqlite_master where type = 'table' and name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    rows = connection.execute(f"pragma table_info({table})").fetchall()
    return {str(row[1]) for row in rows}


def _load_json_artifact(path: Optional[Path]) -> Dict[str, Any]:
    if path is None:
        return {"status": "missing", "path": "", "payload": None, "failure_reasons": ["artifact path was not provided"]}
    if not path.exists():
        return {"status": "missing", "path": str(path), "payload": None, "failure_reasons": ["artifact file is missing"]}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "fail", "path": str(path), "payload": None, "failure_reasons": [f"artifact read failed: {exc}"]}
    return {"status": "loaded", "path": str(path), "payload": payload, "failure_reasons": []}


def _artifact_record(artifact: Mapping[str, Any]) -> Dict[str, Any]:
    payload = artifact.get("payload")
    return {
        "status": artifact.get("status", "missing"),
        "path": artifact.get("path", ""),
        "source": payload.get("source", "") if isinstance(payload, Mapping) else "",
        "gate_status": payload.get("gate_status", "") if isinstance(payload, Mapping) else "",
        "summary": payload.get("summary", {}) if isinstance(payload, Mapping) else {},
        "failure_reasons": list(artifact.get("failure_reasons", [])),
    }


def _real_index_requirement(db_health: Mapping[str, Any], minimum_counts: Mapping[str, int]) -> Dict[str, Any]:
    counts = db_health.get("counts", {})
    failure_reasons = list(db_health.get("failure_reasons", []))
    for name, minimum in minimum_counts.items():
        observed = int(counts.get(name, 0) or 0)
        if observed < minimum:
            failure_reasons.append(f"{name}={observed} is below required expanded count {minimum}")
    if db_health.get("status") != "pass":
        evidence = "database health did not pass"
        status = "fail" if db_health.get("status") == "fail" else "missing"
    else:
        evidence = (
            f"{db_health.get('integrity_check_type')}={db_health.get('integrity_check')}; "
            f"documents={counts.get('documents', 0)}, chunks={counts.get('chunks', 0)}, "
            f"evidence={counts.get('evidence', 0)}, edges={counts.get('edges', 0)}, "
            f"linux_asic_reg_documents={counts.get('linux_asic_reg_documents', 0)}"
        )
        status = "pass" if not failure_reasons else "blocked"
    return _requirement(
        "real_index_db",
        "Real expanded indexed SQLite corpus",
        status,
        evidence,
        failure_reasons,
    )


def _artifact_binding_requirement(
    db_path: Path,
    db_health: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
) -> Dict[str, Any]:
    binding_artifact_names = tuple(_REQUIRED_ARTIFACT_SOURCES)
    db_bound_artifacts = ("acceptance", "web_acceptance", "provider_gate", "runtime_semantic_freshness")
    failures: List[str] = []
    loaded = 0
    db_bound_loaded = 0
    for name in binding_artifact_names:
        artifact = artifacts.get(name, {})
        payload = artifact.get("payload")
        if not isinstance(payload, Mapping):
            failures.append(f"{name} artifact is not loaded")
            continue
        loaded += 1
        expected_source = _REQUIRED_ARTIFACT_SOURCES.get(name, ())
        source = str(payload.get("source", ""))
        if expected_source and source not in expected_source:
            failures.append(
                f"{name} source={source or 'missing'} does not match one of {', '.join(expected_source)}"
            )
        if name in db_bound_artifacts:
            db_bound_loaded += 1
            artifact_db_path = payload.get("db_path")
            if not artifact_db_path:
                failures.append(f"{name} db_path is missing")
            elif not _same_path(db_path, Path(str(artifact_db_path))):
                failures.append(f"{name} db_path={artifact_db_path} does not match current db_path={db_path}")

    provider_payload = artifacts.get("provider_gate", {}).get("payload")
    if isinstance(provider_payload, Mapping):
        provider_checks_value = provider_payload.get("provider_checks", {})
        if not isinstance(provider_checks_value, Mapping):
            failures.append("provider_gate provider_checks is not an object")
            provider_checks: Mapping[str, Any] = {}
        else:
            provider_checks = provider_checks_value
        current_job_rows = _load_current_job_rows(db_path)
        current_index_job = db_health.get("jobs", {}).get("latest_index_job_id")
        current_graph_job = db_health.get("jobs", {}).get("latest_graph_rebuild_job_id")
        for check_name in ("semantic_edge_provenance", "doc_node_provenance"):
            check = provider_checks.get(check_name, {})
            artifact_index_job = check.get("latest_index_job_id")
            artifact_graph_job = check.get("latest_graph_rebuild_job_id")
            failures.extend(_provider_check_job_id_failures(check_name, check, current_job_rows))
            if artifact_index_job is None:
                failures.append(f"provider_gate {check_name}.latest_index_job_id is missing")
            else:
                artifact_index_int = _coerce_int(artifact_index_job)
                if artifact_index_int is None:
                    failures.append(f"provider_gate {check_name}.latest_index_job_id is not an integer: {artifact_index_job}")
                elif current_index_job is not None and artifact_index_int != int(current_index_job):
                    failures.append(
                        f"provider_gate {check_name}.latest_index_job_id={artifact_index_job} does not match current latest_index_job_id={current_index_job}"
                    )
            if artifact_graph_job is None:
                failures.append(f"provider_gate {check_name}.latest_graph_rebuild_job_id is missing")
            else:
                artifact_graph_int = _coerce_int(artifact_graph_job)
                if artifact_graph_int is None:
                    failures.append(f"provider_gate {check_name}.latest_graph_rebuild_job_id is not an integer: {artifact_graph_job}")
                elif current_graph_job is not None and artifact_graph_int != int(current_graph_job):
                    failures.append(
                        f"provider_gate {check_name}.latest_graph_rebuild_job_id={artifact_graph_job} does not match current latest_graph_rebuild_job_id={current_graph_job}"
                    )

    runtime_payload = artifacts.get("runtime_semantic_freshness", {}).get("payload")
    if isinstance(runtime_payload, Mapping):
        current_jobs = db_health.get("jobs", {})
        for artifact_key, current_key in (
            ("latest_index_job_id", "latest_index_job_id"),
            ("latest_graph_rebuild_job_id", "latest_graph_rebuild_job_id"),
            ("latest_semantic_edges_job_id", "latest_semantic_edges_job_id"),
            ("latest_doc_nodes_job_id", "latest_doc_nodes_job_id"),
        ):
            current_job = current_jobs.get(current_key)
            artifact_job = runtime_payload.get(artifact_key)
            if artifact_job is None:
                failures.append(f"runtime_semantic_freshness {artifact_key} is missing")
                continue
            artifact_job_int = _coerce_int(artifact_job)
            if artifact_job_int is None:
                failures.append(f"runtime_semantic_freshness {artifact_key} is not an integer: {artifact_job}")
            elif current_job is not None and artifact_job_int != int(current_job):
                failures.append(
                    f"runtime_semantic_freshness {artifact_key}={artifact_job} does not match current {current_key}={current_job}"
                )

    status = "pass" if loaded == len(binding_artifact_names) and not failures else "blocked"
    evidence = (
        f"{loaded}/{len(binding_artifact_names)} required artifacts loaded; "
        f"{db_bound_loaded}/{len(db_bound_artifacts)} DB/job-bound artifacts checked"
    )
    return _requirement("artifact_binding", "Artifact DB/job binding", status, evidence, failures)


def _load_current_job_rows(db_path: Path) -> Dict[int, Tuple[str, str]]:
    try:
        with sqlite3.connect(str(db_path), timeout=5.0) as connection:
            connection.execute("pragma query_only = on")
            if not _table_exists(connection, "jobs"):
                return {}
            rows = connection.execute("select id, kind, status from jobs").fetchall()
    except sqlite3.Error:
        return {}
    return {int(row[0]): (str(row[1] or ""), str(row[2] or "")) for row in rows}


def _provider_check_job_id_failures(
    check_name: str,
    check: Mapping[str, Any],
    current_job_rows: Mapping[int, Tuple[str, str]],
) -> List[str]:
    expected_kinds = _PROVIDER_CHECK_JOB_KINDS.get(check_name, ())
    if not expected_kinds:
        return []
    job_ids = check.get("job_ids", [])
    if job_ids in (None, []):
        return []
    if not isinstance(job_ids, list):
        return [f"provider_gate {check_name}.job_ids is not a list"]
    failures: List[str] = []
    for raw_job_id in job_ids:
        job_id = _coerce_int(raw_job_id)
        if job_id is None:
            failures.append(f"provider_gate {check_name}.job_id is not an integer: {raw_job_id}")
            continue
        row = current_job_rows.get(job_id)
        if row is None:
            failures.append(f"provider_gate {check_name}.job_id={job_id} is not recorded in current DB")
            continue
        kind, status = row
        if kind not in expected_kinds:
            failures.append(
                f"provider_gate {check_name}.job_id={job_id} kind={kind} is not one of {', '.join(expected_kinds)}"
            )
        if normalize_job_status(status) != "succeeded":
            failures.append(f"provider_gate {check_name}.job_id={job_id} status={status} is not succeeded")
    return failures


def _same_path(left: Path, right: Path) -> bool:
    return left.expanduser().resolve() == right.expanduser().resolve()


def _stage1_requirement(db_health: Mapping[str, Any]) -> Dict[str, Any]:
    counts = db_health.get("counts", {})
    jobs = db_health.get("jobs", {})
    failure_reasons: List[str] = []
    if counts.get("edges", 0) <= 0:
        failure_reasons.append("deterministic graph edge table has no rows")
    latest_index_job_id = jobs.get("latest_index_job_id")
    latest_graph_rebuild_job_id = jobs.get("latest_graph_rebuild_job_id")
    if not latest_graph_rebuild_job_id:
        failure_reasons.append("no succeeded graph_rebuild job is recorded")
    elif latest_index_job_id is not None and int(latest_graph_rebuild_job_id) < int(latest_index_job_id):
        failure_reasons.append(
            f"latest graph_rebuild job id {latest_graph_rebuild_job_id} is older than latest index job id {latest_index_job_id}"
        )
    status = "pass" if not failure_reasons else "blocked"
    evidence = (
        f"edges={counts.get('edges', 0)}; "
        f"latest_graph_rebuild_job_id={latest_graph_rebuild_job_id}; "
        f"latest_index_job_id={latest_index_job_id}"
    )
    return _requirement("stage1_deterministic_graph", "Stage 1 deterministic graph rebuild", status, evidence, failure_reasons)


def _schema_requirement(payloads: Iterable[Optional[Mapping[str, Any]]]) -> Dict[str, Any]:
    queries = [query for payload in payloads if isinstance(payload, Mapping) for query in payload.get("queries", [])]
    if not queries:
        return _requirement(
            "product_graph_schema",
            "Product graph schema in acceptance payloads",
            "missing",
            "no acceptance queries were available",
            ["acceptance artifacts are missing or empty"],
        )
    failures = [
        f"{query.get('id', 'unknown')}: {', '.join(query.get('schema_failure_reasons') or ['schema_status is not pass'])}"
        for query in queries
        if query.get("schema_status") != "pass"
    ]
    status = "pass" if not failures else "fail"
    evidence = f"{len(queries)} acceptance query schema records checked"
    return _requirement("product_graph_schema", "Product graph schema in acceptance payloads", status, evidence, failures)


def _surface_requirement(payload: Optional[Mapping[str, Any]], surfaces: Tuple[str, ...]) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return _requirement(
            "cli_api_mcp_surfaces",
            "CLI/API/MCP surface probes",
            "missing",
            "acceptance artifact is missing",
            ["CLI/API/MCP acceptance artifact is missing"],
        )
    missing_checked = [surface for surface in surfaces if surface not in payload.get("surfaces_checked", [])]
    failures = [f"{surface} was not listed in surfaces_checked" for surface in missing_checked]
    query_count = 0
    for query in payload.get("queries", []):
        query_count += 1
        by_surface = {result.get("surface"): result for result in query.get("surface_results", [])}
        for surface in surfaces:
            result = by_surface.get(surface)
            if not result:
                failures.append(f"{query.get('id', 'unknown')}: missing {surface} result")
            elif result.get("status") != "pass":
                failures.append(f"{query.get('id', 'unknown')}: {surface} status={result.get('status')}")
    status = "pass" if query_count and not failures else "blocked"
    evidence = f"{query_count} queries checked for {', '.join(surfaces)}"
    return _requirement("cli_api_mcp_surfaces", "CLI/API/MCP surface probes", status, evidence, failures)


def _api_live_surface_requirement(payload: Optional[Mapping[str, Any]], db_path: Path) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return _requirement(
            "api_live_surface",
            "Live FastAPI HTTP surface",
            "missing",
            "acceptance artifact is missing",
            ["API_LIVE acceptance artifact is missing"],
        )
    failures: List[str] = []
    query_count = 0
    if "API_LIVE" not in payload.get("surfaces_checked", []):
        failures.append("API_LIVE was not listed in surfaces_checked")
    for query in payload.get("queries", []):
        query_count += 1
        live_result = next(
            (result for result in query.get("surface_results", []) if result.get("surface") == "API_LIVE"),
            None,
        )
        if not live_result:
            failures.append(f"{query.get('id', 'unknown')}: missing API_LIVE result")
            continue
        if live_result.get("transport") != "fastapi.uvicorn.http.query":
            failures.append(
                f"{query.get('id', 'unknown')}: API_LIVE transport={live_result.get('transport', 'missing')}"
            )
        if live_result.get("status") != "pass":
            message = live_result.get("message") or "no message"
            failures.append(f"{query.get('id', 'unknown')}: API_LIVE status={live_result.get('status')} ({message})")
        result_db_path = live_result.get("db_path")
        if not result_db_path:
            failures.append(f"{query.get('id', 'unknown')}: API_LIVE db_path is missing")
        elif not _same_path(db_path, Path(str(result_db_path))):
            failures.append(
                f"{query.get('id', 'unknown')}: API_LIVE db_path={result_db_path} does not match current db_path={db_path}"
            )
        base_url = str(live_result.get("base_url") or "").strip()
        url = str(live_result.get("url") or "").strip()
        if not base_url:
            failures.append(f"{query.get('id', 'unknown')}: API_LIVE base_url is missing")
        if not url:
            failures.append(f"{query.get('id', 'unknown')}: API_LIVE url is missing")
        else:
            parsed_url = urlparse(url)
            if parsed_url.path != "/query":
                failures.append(f"{query.get('id', 'unknown')}: API_LIVE url path={parsed_url.path or 'missing'}")
            params = parse_qs(parsed_url.query)
            url_db_path = (params.get("db_path") or [""])[0]
            if not url_db_path:
                failures.append(f"{query.get('id', 'unknown')}: API_LIVE url db_path is missing")
            elif not _same_path(db_path, Path(str(url_db_path))):
                failures.append(
                    f"{query.get('id', 'unknown')}: API_LIVE url db_path={url_db_path} "
                    f"does not match current db_path={db_path}"
                )
            if (params.get("compact_graph") or [""])[0] != "true":
                failures.append(f"{query.get('id', 'unknown')}: API_LIVE url compact_graph is not true")
            if base_url:
                parsed_base = urlparse(base_url)
                if parsed_base.scheme and parsed_url.scheme != parsed_base.scheme:
                    failures.append(f"{query.get('id', 'unknown')}: API_LIVE url scheme does not match base_url")
                if parsed_base.netloc and parsed_url.netloc != parsed_base.netloc:
                    failures.append(f"{query.get('id', 'unknown')}: API_LIVE url host does not match base_url")
        row_count = _coerce_int(live_result.get("row_count"))
        graph_node_count = _coerce_int(live_result.get("graph_node_count"))
        if row_count is None or row_count <= 0:
            failures.append(f"{query.get('id', 'unknown')}: API_LIVE row_count={live_result.get('row_count', 'missing')}")
        if graph_node_count is None or graph_node_count <= 0:
            failures.append(
                f"{query.get('id', 'unknown')}: API_LIVE graph_node_count={live_result.get('graph_node_count', 'missing')}"
            )
    status = "pass" if query_count and not failures else "blocked"
    evidence = f"{query_count} API_LIVE surface query records checked"
    return _requirement("api_live_surface", "Live FastAPI HTTP surface", status, evidence, failures)


def _mcp_protocol_surface_requirement(payload: Optional[Mapping[str, Any]], db_path: Path) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return _requirement(
            "mcp_protocol_surface",
            "MCP stdio protocol surface",
            "missing",
            "acceptance artifact is missing",
            ["MCP_PROTOCOL acceptance artifact is missing"],
        )
    failures: List[str] = []
    query_count = 0
    if "MCP_PROTOCOL" not in payload.get("surfaces_checked", []):
        failures.append("MCP_PROTOCOL was not listed in surfaces_checked")
    for query in payload.get("queries", []):
        query_count += 1
        protocol_result = next(
            (result for result in query.get("surface_results", []) if result.get("surface") == "MCP_PROTOCOL"),
            None,
        )
        if not protocol_result:
            failures.append(f"{query.get('id', 'unknown')}: missing MCP_PROTOCOL result")
            continue
        if protocol_result.get("transport") != "mcp.stdio.protocol.search_evidence":
            failures.append(
                f"{query.get('id', 'unknown')}: MCP_PROTOCOL transport={protocol_result.get('transport', 'missing')}"
            )
        if protocol_result.get("status") != "pass":
            message = protocol_result.get("message") or "no message"
            failures.append(
                f"{query.get('id', 'unknown')}: MCP_PROTOCOL status={protocol_result.get('status')} ({message})"
            )
        result_db_path = protocol_result.get("db_path")
        if not result_db_path:
            failures.append(f"{query.get('id', 'unknown')}: MCP_PROTOCOL db_path is missing")
        elif not _same_path(db_path, Path(str(result_db_path))):
            failures.append(
                f"{query.get('id', 'unknown')}: MCP_PROTOCOL db_path={result_db_path} "
                f"does not match current db_path={db_path}"
            )
        row_count = _coerce_int(protocol_result.get("row_count"))
        graph_node_count = _coerce_int(protocol_result.get("graph_node_count"))
        if row_count is None or row_count <= 0:
            failures.append(
                f"{query.get('id', 'unknown')}: MCP_PROTOCOL row_count={protocol_result.get('row_count', 'missing')}"
            )
        if graph_node_count is None or graph_node_count <= 0:
            failures.append(
                f"{query.get('id', 'unknown')}: MCP_PROTOCOL graph_node_count="
                f"{protocol_result.get('graph_node_count', 'missing')}"
            )
        command = str(protocol_result.get("command") or "").strip()
        if not command:
            failures.append(f"{query.get('id', 'unknown')}: MCP_PROTOCOL command is missing")
        server_args = protocol_result.get("server_args")
        if not isinstance(server_args, list) or server_args != ["-m", "apps.mcp.server"]:
            failures.append(f"{query.get('id', 'unknown')}: MCP_PROTOCOL server_args={server_args or 'missing'}")
        tool = str(protocol_result.get("tool") or "").strip()
        if tool != "search_evidence":
            failures.append(f"{query.get('id', 'unknown')}: MCP_PROTOCOL tool={tool or 'missing'}")
        if protocol_result.get("server_registered") is not True:
            failures.append(f"{query.get('id', 'unknown')}: MCP_PROTOCOL search_evidence was not registered")
    status = "pass" if query_count and not failures else "blocked"
    evidence = f"{query_count} MCP_PROTOCOL surface query records checked"
    return _requirement("mcp_protocol_surface", "MCP stdio protocol surface", status, evidence, failures)


def _web_surface_requirement(payload: Optional[Mapping[str, Any]], db_path: Path) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return _requirement(
            "web_surface",
            "Web acceptance surface",
            "missing",
            "Web acceptance artifact is missing",
            ["Web acceptance artifact is missing"],
        )
    failures: List[str] = []
    query_count = 0
    if payload.get("gate_status") not in _PASS:
        summary = payload.get("summary", {})
        summary_text = ""
        if isinstance(summary, Mapping):
            summary_text = (
                f"; summary passed={summary.get('passed', 0)}/"
                f"{summary.get('total', 0)} failed={summary.get('failed', 0)}"
            )
        failures.append(f"web acceptance gate_status={payload.get('gate_status', 'missing')}{summary_text}")
    if "Web" not in payload.get("surfaces_checked", []):
        failures.append("Web was not listed in surfaces_checked")
    for query in payload.get("queries", []):
        query_count += 1
        if query.get("status") not in _PASS:
            reasons = query.get("failure_reasons") or []
            detail = f": {'; '.join(str(reason) for reason in reasons[:3])}" if reasons else ""
            failures.append(
                f"{query.get('id', 'unknown')}: web acceptance query status={query.get('status', 'missing')}{detail}"
            )
        web_result = next(
            (result for result in query.get("surface_results", []) if result.get("surface") == "Web"),
            None,
        )
        if not web_result:
            failures.append(f"{query.get('id', 'unknown')}: missing Web result")
        elif web_result.get("status") != "pass":
            message = web_result.get("message") or "no message"
            failures.append(f"{query.get('id', 'unknown')}: Web status={web_result.get('status')} ({message})")
        else:
            non_web_graph_edge_counts = [
                _coerce_int(result.get("graph_edge_count"))
                for result in query.get("surface_results", [])
                if result.get("surface") != "Web"
            ]
            query_has_surface_graph_edges = any(
                edge_count is not None and edge_count > 0 for edge_count in non_web_graph_edge_counts
            )
            if web_result.get("transport") != "next-bff.query":
                failures.append(f"{query.get('id', 'unknown')}: Web transport={web_result.get('transport', 'missing')}")
            result_db_path = web_result.get("db_path")
            if not result_db_path:
                failures.append(f"{query.get('id', 'unknown')}: Web db_path is missing")
            elif not _same_path(db_path, Path(str(result_db_path))):
                failures.append(f"{query.get('id', 'unknown')}: Web db_path={result_db_path} does not match current db_path={db_path}")
            row_count = _coerce_int(web_result.get("row_count"))
            graph_node_count = _coerce_int(web_result.get("graph_node_count"))
            graph_edge_count = _coerce_int(web_result.get("graph_edge_count"))
            if row_count is None or row_count <= 0:
                failures.append(f"{query.get('id', 'unknown')}: Web row_count={web_result.get('row_count', 'missing')}")
            if graph_node_count is None or graph_node_count <= 0:
                failures.append(f"{query.get('id', 'unknown')}: Web graph_node_count={web_result.get('graph_node_count', 'missing')}")
            if query_has_surface_graph_edges and (graph_edge_count is None or graph_edge_count <= 0):
                failures.append(f"{query.get('id', 'unknown')}: Web graph_edge_count={web_result.get('graph_edge_count', 'missing')}")
    status = "pass" if query_count and not failures else "blocked"
    evidence = f"{query_count} Web surface query records checked"
    return _requirement("web_surface", "Web acceptance surface", status, evidence, failures)


def _acceptance_gate_requirement(payload: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return _requirement(
            "acceptance_gate",
            "AQ01-AQ09 final acceptance gate",
            "missing",
            "acceptance artifact is missing",
            ["acceptance artifact is missing"],
        )
    summary = payload.get("summary", {})
    total = int(summary.get("total", 0) or 0)
    passed = int(summary.get("passed", 0) or 0)
    queries = [query for query in payload.get("queries", []) if isinstance(query, Mapping)]
    query_ids = [str(query.get("id", "")) for query in queries]
    failures = list(payload.get("failure_reasons", []))
    missing_ids = [query_id for query_id in _EXPECTED_AQ_IDS if query_id not in query_ids]
    unexpected_ids = [query_id for query_id in query_ids if query_id not in _EXPECTED_AQ_IDS]
    duplicate_ids = sorted({query_id for query_id in query_ids if query_ids.count(query_id) > 1})
    if missing_ids:
        failures.append(f"missing acceptance query id(s): {', '.join(missing_ids)}")
    if unexpected_ids:
        failures.append(f"unexpected acceptance query id(s): {', '.join(unexpected_ids)}")
    if duplicate_ids:
        failures.append(f"duplicate acceptance query id(s): {', '.join(duplicate_ids)}")
    for query in queries:
        if str(query.get("id", "")) != "AQ09":
            continue
        provider_checks = query.get("provider_checks", {})
        if not isinstance(provider_checks, Mapping):
            failures.append("AQ09 provider_checks is missing")
            continue
        for check_name in _REQUIRED_PROVIDER_CHECKS:
            check = provider_checks.get(check_name)
            if not isinstance(check, Mapping):
                failures.append(f"AQ09 provider check {check_name} is missing")
                continue
            if check.get("status") != "pass":
                failures.append(
                    f"AQ09 provider check {check_name}={check.get('status')} ({check.get('message', 'no message')})"
                )
    if total != len(_EXPECTED_AQ_IDS):
        failures.append(f"summary total={total} does not match required AQ count {len(_EXPECTED_AQ_IDS)}")
    status = (
        "pass"
        if payload.get("gate_status") == "pass"
        and total == len(_EXPECTED_AQ_IDS)
        and passed == total
        and not missing_ids
        and not unexpected_ids
        and not duplicate_ids
        and not failures
        else "blocked"
    )
    if status != "pass" and not failures:
        failures.append(
            f"gate_status={payload.get('gate_status')}; passed={passed}/{total}, partial={summary.get('partial', 0)}, failed={summary.get('failed', 0)}"
        )
    evidence = f"gate_status={payload.get('gate_status')}; passed={passed}/{total}; query_ids={','.join(query_ids)}"
    return _requirement("acceptance_gate", "AQ01-AQ09 final acceptance gate", status, evidence, failures)


def _provider_requirement(payload: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return _requirement(
            "provider_live_gate",
            "Provider provenance and live checks",
            "missing",
            "provider-gate artifact is missing",
            ["provider-gate artifact is missing"],
        )
    checks_value = payload.get("provider_checks", {})
    failures: List[str] = []
    if not isinstance(checks_value, Mapping):
        failures.append("provider_checks is not an object")
        checks: Mapping[str, Any] = {}
    else:
        checks = checks_value
    missing_checks = [name for name in _REQUIRED_PROVIDER_CHECKS if name not in checks]
    for name, check in checks.items():
        if not isinstance(check, Mapping):
            failures.append(f"{name} provider check is not an object")
        elif check.get("status") != "pass":
            failures.append(f"{name}: {check.get('status')} ({check.get('message', 'no message')})")
    failures.extend(f"{name} provider check is missing" for name in missing_checks)
    if payload.get("gate_status") != "pass" and not failures:
        failures.extend(payload.get("failure_reasons", []))
    status = "pass" if payload.get("gate_status") == "pass" and not failures and not missing_checks else "blocked"
    evidence = f"gate_status={payload.get('gate_status')}; checks={len(checks)}"
    return _requirement("provider_live_gate", "Provider provenance and live checks", status, evidence, failures)


def _stage2_requirement(payload: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return _requirement(
            "stage2_semantic_edges",
            "Stage 2 semantic edge freshness and live generation",
            "missing",
            "provider-gate artifact is missing",
            ["provider-gate artifact is missing"],
        )
    checks_value = payload.get("provider_checks", {})
    checks = checks_value if isinstance(checks_value, Mapping) else {}
    required = ("semantic_edge_provenance", "doc_node_provenance", "semantic_edge")
    failures = [] if isinstance(checks_value, Mapping) else ["provider_checks is not an object"]
    for name in required:
        check = checks.get(name)
        if not check:
            failures.append(f"{name} check is missing")
        elif not isinstance(check, Mapping):
            failures.append(f"{name} check is not an object")
        elif check.get("status") != "pass":
            failures.append(f"{name}: {check.get('status')} ({check.get('message', 'no message')})")
        elif name in {"semantic_edge_provenance", "doc_node_provenance"}:
            stale_count = _coerce_int(check.get("stale_edge_count", 0) or 0)
            edge_count = _coerce_int(check.get("edge_count"))
            job_ids = check.get("job_ids", [])
            if stale_count is None:
                failures.append(f"{name}: stale_edge_count is not an integer: {check.get('stale_edge_count')}")
            invalid_job_count = _coerce_int(check.get("missing_or_invalid_job_edge_count", 0) or 0)
            if invalid_job_count is None:
                failures.append(
                    f"{name}: missing_or_invalid_job_edge_count is not an integer: {check.get('missing_or_invalid_job_edge_count')}"
                )
            elif invalid_job_count > 0:
                failures.append(
                    f"{name}: pass artifact still reports missing_or_invalid_job_edge_count={check.get('missing_or_invalid_job_edge_count')}"
                )
            if edge_count is None:
                failures.append(f"{name}: edge_count is missing or not an integer")
            elif edge_count <= 0:
                failures.append(f"{name}: pass artifact reports edge_count={edge_count}")
            if not isinstance(job_ids, list) or not job_ids:
                failures.append(f"{name}: pass artifact job_ids are missing")
    status = "pass" if not failures else "blocked"
    evidence = "; ".join(f"{name}={checks.get(name, {}).get('status', 'missing')}" for name in required)
    return _requirement("stage2_semantic_edges", "Stage 2 semantic edge freshness and live generation", status, evidence, failures)


def _runtime_semantic_freshness_requirement(payload: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    required_check_ids = (
        "storage_runtime_stale_semantic_filter",
        "storage_runtime_fresh_semantic_keep",
        "storage_runtime_fresh_doc_node_keep",
        "storage_runtime_extractor_job_kind_binding",
        "storage_runtime_provider_mismatch_filter",
        "real_db_global_graph_semantic_leak_probe",
        "real_db_query_graph_semantic_leak_probe",
    )
    if not isinstance(payload, Mapping):
        return _requirement(
            "runtime_semantic_freshness",
            "Runtime semantic graph freshness and provenance binding",
            "missing",
            "runtime semantic freshness artifact is missing",
            ["runtime semantic freshness artifact is missing"],
        )
    failures: List[str] = []
    if payload.get("source") != "asip.runtime_semantic_freshness_qa":
        failures.append(
            f"source={payload.get('source', 'missing')} does not match asip.runtime_semantic_freshness_qa"
        )
    if payload.get("gate_status") != "pass":
        failures.append(f"gate_status={payload.get('gate_status')}")
    checks = payload.get("checks", [])
    checks_by_id = {
        str(check.get("id") or ""): check
        for check in checks
        if isinstance(check, Mapping)
    }
    for check_id in required_check_ids:
        check = checks_by_id.get(check_id)
        if check is None:
            failures.append(f"{check_id} check is missing")
        elif check.get("status") != "pass":
            failures.append(f"{check_id}: status={check.get('status')} ({check.get('message', 'no message')})")
    summary = payload.get("summary", {})
    if int(summary.get("failed", 0) or 0) > 0:
        failures.append(f"summary failed={summary.get('failed')}")
    if summary.get("passed") != summary.get("checks"):
        failures.append(f"summary passed={summary.get('passed')} does not match checks={summary.get('checks')}")
    status = "pass" if not failures else "blocked"
    evidence = f"gate_status={payload.get('gate_status')}; checks={summary.get('passed', 0)}/{summary.get('checks', len(checks))}"
    return _requirement(
        "runtime_semantic_freshness",
        "Runtime semantic graph freshness and provenance binding",
        status,
        evidence,
        failures,
    )


def _semantic_quality_requirement(payload: Optional[Mapping[str, Any]], *, required: bool) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        if not required:
            return _requirement(
                "semantic_quality",
                "Labeled semantic retrieval quality gate",
                "pass",
                "semantic-quality artifact is optional for fixture completion gates",
                [],
            )
        return _requirement(
            "semantic_quality",
            "Labeled semantic retrieval quality gate",
            "missing",
            "semantic-quality artifact is missing",
            ["semantic-quality artifact is missing"],
        )
    failures: List[str] = []
    if payload.get("source") != "asip.semantic_quality_eval":
        failures.append(f"source={payload.get('source', 'missing')} does not match asip.semantic_quality_eval")
    if payload.get("gate_status") != "pass":
        failures.append(f"gate_status={payload.get('gate_status')}")
        failures.extend(str(reason) for reason in payload.get("failure_reasons", []))
    summary = payload.get("summary", {})
    total = _coerce_int(summary.get("total"))
    passed = _coerce_int(summary.get("passed"))
    failed = _coerce_int(summary.get("failed", 0) or 0)
    provider_vector_cases = _coerce_int(summary.get("provider_vector_cases", 0) or 0)
    graph_target_cases = _coerce_int(summary.get("graph_target_cases", 0) or 0)
    if total is None or total <= 0:
        failures.append(f"summary total is missing or zero: {summary.get('total')}")
    if passed is None or total is None or passed != total:
        failures.append(f"summary passed={summary.get('passed')} does not match total={summary.get('total')}")
    if failed is None or failed != 0:
        failures.append(f"summary failed={summary.get('failed')}")
    if provider_vector_cases is None or provider_vector_cases <= 0:
        failures.append(f"provider_vector_cases={summary.get('provider_vector_cases')} does not prove vector participation")
    if graph_target_cases is None or graph_target_cases <= 0:
        failures.append(f"graph_target_cases={summary.get('graph_target_cases')} does not prove graph-target retrieval")
    cases = payload.get("cases", [])
    if not isinstance(cases, list) or not cases:
        failures.append("cases are missing")
    else:
        for case in cases:
            if not isinstance(case, Mapping):
                failures.append("semantic quality case is not an object")
                continue
            if case.get("status") != "pass":
                failures.append(f"{case.get('id', 'unknown')}: status={case.get('status')}")
            if int(case.get("row_count", 0) or 0) <= 0:
                failures.append(f"{case.get('id', 'unknown')}: row_count={case.get('row_count')}")
    status = "pass" if not failures else "blocked"
    evidence = (
        f"gate_status={payload.get('gate_status')}; "
        f"passed={summary.get('passed', 0)}/{summary.get('total', 0)}; "
        f"provider_vector_cases={summary.get('provider_vector_cases', 0)}; "
        f"graph_target_cases={summary.get('graph_target_cases', 0)}; "
        f"mrr={summary.get('mean_reciprocal_rank', 0)}"
    )
    return _requirement(
        "semantic_quality",
        "Labeled semantic retrieval quality gate",
        status,
        evidence,
        failures,
    )


def _callback_audit_requirement(payload: Optional[Mapping[str, Any]], *, required: bool) -> Dict[str, Any]:
    minimum_real_oracles = 3 if required else 0
    if not isinstance(payload, Mapping):
        if not required:
            return _requirement(
                "callback_edge_audit",
                "Callback/vtable parser and overlink audit",
                "pass",
                "callback audit artifact is optional for fixture completion gates",
                [],
            )
        return _requirement(
            "callback_edge_audit",
            "Callback/vtable parser and overlink audit",
            "missing",
            "callback audit artifact is missing",
            ["callback audit artifact is missing"],
        )
    failures: List[str] = []
    if payload.get("source") != "asip.callback_edge_audit":
        failures.append(f"source={payload.get('source', 'missing')} does not match asip.callback_edge_audit")
    if payload.get("gate_status") != "pass":
        failures.append(f"gate_status={payload.get('gate_status')}")
        failures.extend(str(reason) for reason in payload.get("failure_reasons", []))
    summary = payload.get("summary", {})
    callback_count = _coerce_int(summary.get("callback_edge_count"))
    parser_pollution = _coerce_int(summary.get("parser_pollution_candidate_count", 0) or 0)
    unexplained_ambiguous = _coerce_int(summary.get("unexplained_ambiguous_callback_edge_count", 0) or 0)
    real_oracle_total = _coerce_int(summary.get("real_oracle_total", 0) or 0)
    real_oracle_passed = _coerce_int(summary.get("real_oracle_passed", 0) or 0)
    if callback_count is None or callback_count <= 0:
        failures.append(f"callback_edge_count={summary.get('callback_edge_count')}")
    if parser_pollution is None or parser_pollution != 0:
        failures.append(f"parser_pollution_candidate_count={summary.get('parser_pollution_candidate_count')}")
    if unexplained_ambiguous is None or unexplained_ambiguous != 0:
        failures.append(
            f"unexplained_ambiguous_callback_edge_count={summary.get('unexplained_ambiguous_callback_edge_count')}"
        )
    if real_oracle_total is None or real_oracle_total < minimum_real_oracles:
        failures.append(f"real_oracle_total={summary.get('real_oracle_total')}")
    if real_oracle_passed is None or real_oracle_total is None or real_oracle_passed != real_oracle_total:
        failures.append(
            f"real_oracle_passed={summary.get('real_oracle_passed')} does not match "
            f"real_oracle_total={summary.get('real_oracle_total')}"
        )
    status = "pass" if not failures else "blocked"
    evidence = (
        f"gate_status={payload.get('gate_status')}; "
        f"callback_edges={summary.get('callback_edge_count', 0)}; "
        f"parser_pollution={summary.get('parser_pollution_candidate_count', 0)}; "
        f"unexplained_ambiguous={summary.get('unexplained_ambiguous_callback_edge_count', 0)}; "
        f"real_oracles={summary.get('real_oracle_passed', 0)}/{summary.get('real_oracle_total', 0)}"
    )
    return _requirement(
        "callback_edge_audit",
        "Callback/vtable parser and overlink audit",
        status,
        evidence,
        failures,
    )


def _browser_requirement(
    payload: Optional[Mapping[str, Any]],
    in_app_payload: Optional[Mapping[str, Any]] = None,
    db_path: Optional[Path] = None,
    db_health: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    blocker_reasons: List[str] = []
    evidence_parts: List[str] = []
    browser_proof_passed = False

    if isinstance(payload, Mapping):
        source = str(payload.get("source", ""))
        e2e_status = payload.get("e2e_status") or payload.get("browser_e2e_status") or payload.get("test_status")
        artifact_failures = list(payload.get("failure_reasons", []))
        if source != "asip.web.browser_e2e":
            artifact_failures.append(f"browser artifact source={source or 'missing'} is not no-mock browser e2e proof")
        else:
            artifact_failures.extend(_browser_e2e_artifact_failures(payload, db_path, db_health))
        browser_proof_passed = (
            payload.get("gate_status") in _PASS
            and e2e_status in _PASS
            and source == "asip.web.browser_e2e"
            and not artifact_failures
        )
        blocker_reasons.extend(artifact_failures)
        evidence_parts.append(f"browser gate_status={payload.get('gate_status')}; e2e_status={e2e_status or 'missing'}")
    else:
        blocker_reasons.append("browser artifact is missing")
        evidence_parts.append("browser artifact is missing")

    if isinstance(in_app_payload, Mapping):
        in_app_source = str(in_app_payload.get("source", ""))
        in_app_e2e_status = (
            in_app_payload.get("e2e_status")
            or in_app_payload.get("browser_e2e_status")
            or in_app_payload.get("test_status")
        )
        in_app_gate_status = in_app_payload.get("gate_status")
        in_app_failures: List[str] = []
        if in_app_source != "asip.web.browser_e2e":
            in_app_failures.append(
                f"in-app browser artifact source={in_app_source or 'missing'} is not no-mock browser e2e proof"
            )
        else:
            in_app_failures.extend(_browser_e2e_artifact_failures(in_app_payload, db_path, db_health))
        for reason in in_app_payload.get("failure_reasons", []):
            in_app_failures.append(f"in-app browser: {reason}")
        for attempt in in_app_payload.get("attempts", []):
            if attempt.get("ok") is True:
                continue
            message = attempt.get("message") or attempt.get("failure_reason") or attempt.get("error")
            url = attempt.get("url")
            if message:
                in_app_failures.append(f"in-app browser attempt {url or 'unknown URL'}: {message}")
        if (
            in_app_gate_status in _PASS
            and in_app_e2e_status in _PASS
            and in_app_source == "asip.web.browser_e2e"
            and not in_app_failures
        ):
            browser_proof_passed = True
        blocker_reasons.extend(in_app_failures)
        evidence_parts.append(
            f"in-app gate_status={in_app_gate_status}; e2e_status={in_app_e2e_status or 'missing'}"
        )

    if browser_proof_passed:
        status = "pass"
        failure_reasons: List[str] = []
    else:
        status = "blocked"
        failure_reasons = blocker_reasons or ["; ".join(evidence_parts)]
    return _requirement(
        "browser_e2e",
        "No-mock browser QA and e2e proof",
        status,
        "; ".join(evidence_parts),
        failure_reasons,
    )


def _browser_e2e_artifact_failures(
    payload: Mapping[str, Any],
    db_path: Optional[Path],
    db_health: Optional[Mapping[str, Any]],
) -> List[str]:
    failures: List[str] = []
    command = payload.get("command", [])
    if not isinstance(command, list) or not command:
        failures.append("browser e2e command is missing")
    elif command[:4] != ["pnpm", "exec", "playwright", "test"]:
        failures.append(f"browser e2e command is not a live Playwright test run: {command}")
    if db_path is not None:
        artifact_db_path = payload.get("db_path")
        if not artifact_db_path:
            failures.append("browser e2e db_path is missing")
        elif not _same_path(db_path, Path(str(artifact_db_path))):
            failures.append(f"browser e2e db_path={artifact_db_path} does not match current db_path={db_path}")
        target_urls = payload.get("target_urls", [])
        if not isinstance(target_urls, list) or not any(_url_has_matching_db_path(str(url), db_path) for url in target_urls):
            failures.append("browser e2e target_urls do not include current dbPath")
    if db_health is not None:
        current_jobs = db_health.get("jobs", {})
        for artifact_key, current_key in (
            ("latest_index_job_id", "latest_index_job_id"),
            ("latest_graph_rebuild_job_id", "latest_graph_rebuild_job_id"),
        ):
            current_job = current_jobs.get(current_key)
            artifact_job = payload.get(artifact_key)
            if artifact_job is None:
                failures.append(f"browser e2e {artifact_key} is missing")
                continue
            artifact_job_int = _coerce_int(artifact_job)
            if artifact_job_int is None:
                failures.append(f"browser e2e {artifact_key} is not an integer: {artifact_job}")
            elif current_job is not None and artifact_job_int != int(current_job):
                failures.append(f"browser e2e {artifact_key}={artifact_job} does not match current {current_key}={current_job}")
    report_json = str(payload.get("report_json") or "").strip()
    report_sha256 = str(payload.get("report_sha256") or "").strip()
    report_payload: Optional[Mapping[str, Any]] = None
    if not report_json:
        failures.append("browser e2e raw Playwright report path is missing")
    elif not report_sha256:
        failures.append("browser e2e raw Playwright report sha256 is missing")
    else:
        report_path = Path(report_json).expanduser()
        if not report_path.is_absolute():
            report_path = Path.cwd() / report_path
        try:
            report_bytes = report_path.read_bytes()
        except OSError as exc:
            failures.append(f"browser e2e raw Playwright report is unreadable: {exc}")
        else:
            actual_sha256 = hashlib.sha256(report_bytes).hexdigest()
            if actual_sha256 != report_sha256:
                failures.append("browser e2e raw Playwright report sha256 does not match artifact")
            try:
                parsed_report = json.loads(report_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                failures.append(f"browser e2e raw Playwright report is invalid JSON: {exc}")
            else:
                if isinstance(parsed_report, Mapping):
                    report_payload = parsed_report
                else:
                    failures.append("browser e2e raw Playwright report root is not an object")
    summary = payload.get("summary", {})
    if not isinstance(summary, Mapping):
        failures.append("browser e2e summary is missing")
        summary = {}
    total = int(summary.get("total", 0) or 0)
    passed = int(summary.get("passed", 0) or 0)
    failed = int(summary.get("failed", 0) or 0)
    if total <= 0:
        failures.append("browser e2e summary total is zero")
    if passed <= 0:
        failures.append("browser e2e summary passed is zero")
    if failed != 0:
        failures.append(f"browser e2e summary failed={failed}")
    required_tests = payload.get("required_tests", [])
    if not isinstance(required_tests, list) or not required_tests:
        failures.append("browser e2e required_tests are missing")
        required_tests = []
    required_by_title = {
        str(item.get("title") or ""): item
        for item in required_tests
        if isinstance(item, Mapping)
    }
    for title in _REQUIRED_BROWSER_E2E_TESTS:
        item = required_by_title.get(title)
        if item is None:
            failures.append(f"required browser e2e test is missing: {title}")
            continue
        if item.get("status") != "pass":
            failures.append(f"required browser e2e test did not pass: {title} ({item.get('status')})")
        if not _browser_required_test_file_matches(item.get("file") or item.get("source") or item.get("path")):
            failures.append(f"required browser e2e test source mismatch: {title}")
    if report_payload is not None:
        failures.extend(_raw_playwright_summary_failures(report_payload, summary))
        failures.extend(_raw_playwright_required_test_failures(report_payload))
    failures.extend(_browser_current_db_probe_failures(payload, db_path, db_health))
    return failures


def _browser_current_db_probe_failures(
    payload: Mapping[str, Any],
    db_path: Optional[Path],
    db_health: Optional[Mapping[str, Any]],
) -> List[str]:
    if db_path is None:
        return []
    failures: List[str] = []
    probes = payload.get("current_db_probes", [])
    if not isinstance(probes, list) or not probes:
        return ["browser e2e current_db_probes are missing"]
    by_surface = {
        str(item.get("surface") or ""): item
        for item in probes
        if isinstance(item, Mapping)
    }
    current_jobs = db_health.get("jobs", {}) if isinstance(db_health, Mapping) else {}
    latest_index_job_id = current_jobs.get("latest_index_job_id")
    latest_graph_rebuild_job_id = current_jobs.get("latest_graph_rebuild_job_id")
    for surface in _REQUIRED_BROWSER_CURRENT_DB_PROBE_SURFACES:
        probe = by_surface.get(surface)
        if probe is None:
            failures.append(f"browser e2e current_db_probes missing surface: {surface}")
            continue
        if _coerce_int(probe.get("status")) != 200:
            failures.append(f"browser e2e {surface} status={probe.get('status')}")
        probe_db_path = probe.get("db_path")
        if not probe_db_path or not _same_path(db_path, Path(str(probe_db_path))):
            failures.append(f"browser e2e {surface} db_path does not match current dbPath")
        if not _url_has_matching_db_path(str(probe.get("url") or ""), db_path):
            failures.append(f"browser e2e {surface} url does not include current dbPath")
        if _coerce_int(probe.get("node_count")) is None or int(probe.get("node_count") or 0) <= 0:
            failures.append(f"browser e2e {surface} node_count is zero")
        if _coerce_int(probe.get("edge_count")) is None or int(probe.get("edge_count") or 0) <= 0:
            failures.append(f"browser e2e {surface} edge_count is zero")
        response_sha256 = str(probe.get("response_sha256") or "")
        if len(response_sha256) != 64 or any(char not in "0123456789abcdef" for char in response_sha256):
            failures.append(f"browser e2e {surface} response_sha256 is missing or invalid")
        if latest_index_job_id is not None and _coerce_int(probe.get("latest_index_job_id")) != int(latest_index_job_id):
            failures.append(
                f"browser e2e {surface} latest_index_job_id={probe.get('latest_index_job_id')} "
                f"does not match current latest_index_job_id={latest_index_job_id}"
            )
        if latest_graph_rebuild_job_id is not None and _coerce_int(probe.get("latest_graph_rebuild_job_id")) != int(latest_graph_rebuild_job_id):
            failures.append(
                f"browser e2e {surface} latest_graph_rebuild_job_id={probe.get('latest_graph_rebuild_job_id')} "
                f"does not match current latest_graph_rebuild_job_id={latest_graph_rebuild_job_id}"
            )
        if surface == "graph_page_concept_detail_selection":
            failures.extend(_browser_concept_detail_probe_failures(probe))
    return failures


def _browser_concept_detail_probe_failures(probe: Mapping[str, Any]) -> List[str]:
    failures: List[str] = []
    selected_node_id = str(probe.get("selected_node_id") or "")
    if ":concept:" not in selected_node_id:
        failures.append("browser e2e concept detail selected_node_id is not a concept node")
    if str(probe.get("selected_kind") or "") != "function":
        failures.append(f"browser e2e concept detail selected_kind={probe.get('selected_kind')}")
    if not str(probe.get("selected_label") or "").strip():
        failures.append("browser e2e concept detail selected_label is missing")
    implementation_count = _coerce_int(probe.get("implementation_count"))
    if implementation_count is None or implementation_count <= 1:
        failures.append(f"browser e2e concept detail implementation_count={probe.get('implementation_count')}")
    listed_implementation_count = _coerce_int(probe.get("listed_implementation_count"))
    if listed_implementation_count is None or listed_implementation_count != implementation_count:
        failures.append(
            f"browser e2e concept detail listed_implementation_count={probe.get('listed_implementation_count')} "
            f"does not match implementation_count={probe.get('implementation_count')}"
        )
    raw_record_count = _coerce_int(probe.get("raw_implementation_record_count"))
    if raw_record_count is not None and implementation_count is not None and raw_record_count < implementation_count:
        failures.append(
            f"browser e2e concept detail raw_implementation_record_count={probe.get('raw_implementation_record_count')} "
            f"is below implementation_count={probe.get('implementation_count')}"
        )
    if not str(probe.get("selected_implementation") or "").strip():
        failures.append("browser e2e concept detail selected_implementation is missing")
    if str(probe.get("detail_heading") or "") != "Concept Generated From":
        failures.append(f"browser e2e concept detail heading={probe.get('detail_heading')}")
    if probe.get("detail_truncated") is not False:
        failures.append(f"browser e2e concept detail_truncated={probe.get('detail_truncated')}")
    return failures


def _url_has_matching_db_path(url: str, db_path: Path) -> bool:
    try:
        values = parse_qs(urlparse(url).query).get("dbPath", [])
    except ValueError:
        return False
    return any(_same_path(db_path, Path(value)) for value in values if value)


def _raw_playwright_required_test_failures(report: Mapping[str, Any]) -> List[str]:
    outcomes: Dict[str, List[Tuple[str, bool]]] = {}

    def visit_suite(suite: Any, parent_sources: Tuple[str, ...] = ()) -> None:
        if not isinstance(suite, Mapping):
            return
        suite_sources = parent_sources + _playwright_source_values(suite)
        for child in suite.get("suites", []) or []:
            visit_suite(child, suite_sources)
        for spec in suite.get("specs", []) or []:
            if not isinstance(spec, Mapping):
                continue
            title = str(spec.get("title") or "").strip()
            if not title:
                continue
            spec_sources = suite_sources + _playwright_source_values(spec)
            for test in spec.get("tests", []) or []:
                if not isinstance(test, Mapping):
                    continue
                outcome = str(test.get("outcome") or test.get("status") or "").strip() or "unknown"
                test_sources = spec_sources + _playwright_source_values(test)
                outcomes.setdefault(title, []).append(
                    (outcome, any(_browser_required_test_file_matches(source) for source in test_sources))
                )

    for suite in report.get("suites", []) or []:
        visit_suite(suite)

    failures: List[str] = []
    for title in _REQUIRED_BROWSER_E2E_TESTS:
        records = outcomes.get(title, [])
        if not records:
            failures.append(f"raw Playwright report missing required browser e2e test: {title}")
            continue
        if any(outcome == "expected" and source_matches for outcome, source_matches in records):
            continue
        source_matched = [outcome for outcome, source_matches in records if source_matches]
        if source_matched:
            outcome = source_matched[0] or "unknown"
            failures.append(f"raw Playwright report required browser e2e test did not pass: {title} ({outcome})")
        elif any(outcome == "expected" for outcome, _source_matches in records):
            failures.append(f"raw Playwright report required browser e2e test source mismatch: {title}")
        else:
            outcome = records[0][0] or "unknown"
            failures.append(f"raw Playwright report required browser e2e test did not pass: {title} ({outcome})")
    return failures


def _playwright_source_values(item: Mapping[str, Any]) -> Tuple[str, ...]:
    values: List[str] = []
    for key in ("file", "path", "title"):
        value = item.get(key)
        if value:
            values.append(str(value))
    location = item.get("location")
    if isinstance(location, Mapping) and location.get("file"):
        values.append(str(location.get("file")))
    return tuple(values)


def _browser_required_test_file_matches(value: Any) -> bool:
    return _REQUIRED_BROWSER_E2E_TEST_FILE in str(value or "")


def _raw_playwright_summary_failures(report: Mapping[str, Any], artifact_summary: Mapping[str, Any]) -> List[str]:
    raw_summary = _raw_playwright_summary(report)
    failures: List[str] = []
    if raw_summary["failed"] > 0:
        failures.append(f"raw Playwright report unexpected={raw_summary['failed']}")
    if raw_summary["flaky"] > 0:
        failures.append(f"raw Playwright report flaky={raw_summary['flaky']}")
    errors = report.get("errors", [])
    if isinstance(errors, list) and errors:
        failures.append(f"raw Playwright report errors={len(errors)}")
    elif errors not in (None, []):
        failures.append("raw Playwright report errors is not a list")

    for key in ("total", "passed", "failed", "flaky", "skipped"):
        raw_value = raw_summary[key]
        artifact_value = _coerce_int(artifact_summary.get(key, 0 if key in {"flaky", "skipped"} else None))
        if artifact_value is None:
            failures.append(f"browser e2e summary {key} is missing or invalid")
        elif raw_value != artifact_value:
            failures.append(f"raw Playwright summary {key}={raw_value} does not match artifact {key}={artifact_value}")
    return failures


def _raw_playwright_summary(report: Mapping[str, Any]) -> Dict[str, int]:
    stats = report.get("stats", {})
    if isinstance(stats, Mapping):
        expected = _coerce_int(stats.get("expected")) or 0
        unexpected = _coerce_int(stats.get("unexpected")) or 0
        flaky = _coerce_int(stats.get("flaky")) or 0
        skipped = _coerce_int(stats.get("skipped")) or 0
        total = expected + unexpected + flaky + skipped
        if total > 0:
            return {
                "total": total,
                "passed": expected,
                "failed": unexpected,
                "flaky": flaky,
                "skipped": skipped,
            }

    summary = {"total": 0, "passed": 0, "failed": 0, "flaky": 0, "skipped": 0}

    def visit_suite(suite: Any) -> None:
        if not isinstance(suite, Mapping):
            return
        for child in suite.get("suites", []) or []:
            visit_suite(child)
        for spec in suite.get("specs", []) or []:
            if not isinstance(spec, Mapping):
                continue
            for test in spec.get("tests", []) or []:
                if not isinstance(test, Mapping):
                    continue
                summary["total"] += 1
                outcome = str(test.get("outcome") or "").strip()
                if outcome == "expected":
                    summary["passed"] += 1
                elif outcome == "skipped":
                    summary["skipped"] += 1
                elif outcome == "flaky":
                    summary["flaky"] += 1
                else:
                    summary["failed"] += 1

    for suite in report.get("suites", []) or []:
        visit_suite(suite)
    return summary


def _no_server_requirement(
    payload: Optional[Mapping[str, Any]],
    artifacts: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return _requirement(
            "web_no_server_smoke",
            "Web no-server static/no-mock hygiene gate",
            "missing",
            "no-server smoke artifact is missing",
            ["no-server smoke artifact is missing"],
        )
    failures: List[str] = []
    if payload.get("source") != "asip.web.no_server_smoke":
        failures.append(f"source={payload.get('source', 'missing')} does not match asip.web.no_server_smoke")
    checks = payload.get("checks", [])
    summary = payload.get("summary", {})
    if payload.get("gate_status") != "pass":
        failures.extend(payload.get("failure_reasons", []) or [f"gate_status={payload.get('gate_status')}"])
    if not checks:
        failures.append("no-server smoke checks are missing")
    for check in checks:
        if check.get("status") != "pass":
            failures.append(f"{check.get('label', 'unknown check')}: status={check.get('status')}")
    if summary.get("passed") != summary.get("total"):
        failures.append(f"summary passed={summary.get('passed')} does not match total={summary.get('total')}")
    if artifacts is not None:
        failures.extend(_no_server_current_artifact_input_failures(payload, artifacts))
    status = "pass" if not failures else "blocked"
    evidence = f"gate_status={payload.get('gate_status')}; checks={summary.get('passed', 0)}/{summary.get('total', len(checks))}"
    return _requirement("web_no_server_smoke", "Web no-server static/no-mock hygiene gate", status, evidence, failures)


def _no_server_current_artifact_input_failures(
    payload: Mapping[str, Any],
    artifacts: Mapping[str, Mapping[str, Any]],
) -> List[str]:
    inputs_value = payload.get("current_artifact_inputs", [])
    if inputs_value in (None, []):
        return []
    if not isinstance(inputs_value, list):
        return ["no-server current_artifact_inputs is not a list"]
    inputs_by_option: Dict[str, Mapping[str, Any]] = {}
    failures: List[str] = []
    for item in inputs_value:
        if not isinstance(item, Mapping):
            failures.append("no-server current_artifact_inputs contains a non-object item")
            continue
        option = str(item.get("option") or "").strip()
        if not option:
            failures.append("no-server current_artifact_inputs item is missing option")
            continue
        inputs_by_option[option] = item
    for option, artifact_name in _NO_SERVER_ARTIFACT_INPUT_OPTIONS.items():
        artifact = artifacts.get(artifact_name, {})
        artifact_path = str(artifact.get("path") or "").strip()
        if not artifact_path:
            continue
        item = inputs_by_option.get(option)
        if item is None:
            failures.append(f"no-server current_artifact_inputs missing {option}")
            continue
        status = str(item.get("status") or "").strip()
        if status != "loaded":
            failures.append(f"no-server {option} input status={status or 'missing'}")
            continue
        input_path = str(item.get("path") or item.get("resolved_path") or "").strip()
        if not input_path:
            failures.append(f"no-server {option} input path is missing")
        elif not _same_path(Path(input_path), Path(artifact_path)):
            failures.append(f"no-server {option} path={input_path} does not match completion artifact path={artifact_path}")
        expected_sha = _file_sha256(Path(artifact_path))
        recorded_sha = str(item.get("sha256") or "").strip()
        if not recorded_sha:
            failures.append(f"no-server {option} sha256 is missing")
        elif expected_sha and recorded_sha != expected_sha:
            failures.append(f"no-server {option} sha256 does not match current artifact")
    return failures


def _file_sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.expanduser().resolve().read_bytes()).hexdigest()
    except OSError:
        return ""


def _performance_requirement(payload: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return _requirement(
            "performance_smoke",
            "Deterministic rebuild and query performance smoke",
            "missing",
            "performance smoke artifact is missing",
            ["performance smoke artifact is missing"],
        )
    failures: List[str] = []
    if payload.get("source") != "fixture_performance_smoke":
        failures.append(f"source={payload.get('source', 'missing')} does not match fixture_performance_smoke")
    if payload.get("deterministic_counts_match") is not True:
        failures.append("deterministic_counts_match is not true")
    if payload.get("all_queries_under_threshold") is not True:
        failures.append("all_queries_under_threshold is not true")
    queries = payload.get("queries", [])
    if len(queries) < 5:
        failures.append(f"query count {len(queries)} is below required performance smoke count 5")
    for query in queries:
        if query.get("under_threshold") is not True:
            failures.append(f"{query.get('query', 'unknown query')}: under_threshold is not true")
        if int(query.get("row_count", 0) or 0) <= 0:
            failures.append(f"{query.get('query', 'unknown query')}: row_count is empty")
        if query.get("graph_runtime") != "networkx":
            failures.append(f"{query.get('query', 'unknown query')}: graph_runtime={query.get('graph_runtime')}")
    status = "pass" if not failures else "blocked"
    evidence = (
        f"deterministic_counts_match={payload.get('deterministic_counts_match')}; "
        f"all_queries_under_threshold={payload.get('all_queries_under_threshold')}; queries={len(queries)}"
    )
    return _requirement("performance_smoke", "Deterministic rebuild and query performance smoke", status, evidence, failures)


def _residual_acceptance_requirement(payload: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return _requirement(
            "residual_acceptance",
            "Explicit residual-boundary acceptance",
            "blocked",
            "residual acceptance artifact is missing",
            ["G13 residual-boundary acceptance artifact is missing"],
        )
    accepted = payload.get("accepted") is True
    residuals = payload.get("accepted_residuals", [])
    failures: List[str] = []
    if payload.get("source") != "asip.residual_acceptance":
        failures.append(f"source={payload.get('source', 'missing')} does not match asip.residual_acceptance")
    if payload.get("gate_status") != "pass":
        failures.append(f"gate_status={payload.get('gate_status')}")
        failures.extend(str(reason) for reason in payload.get("failure_reasons", []))
    if not accepted:
        failures.append("accepted is not true")
    if not residuals:
        failures.append("accepted_residuals is empty")
    status = "pass" if not failures else "blocked"
    evidence = f"gate_status={payload.get('gate_status')}; accepted_residuals={len(residuals)}"
    return _requirement("residual_acceptance", "Explicit residual-boundary acceptance", status, evidence, failures)


def _git_gate_requirement(payload: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if not isinstance(payload, Mapping):
        return _requirement(
            "git_gate",
            "Final diff, commit, and push gate",
            "blocked",
            "git gate artifact is missing",
            ["final git gate artifact is missing"],
        )
    failures: List[str] = []
    if payload.get("source") != "asip.git_gate":
        failures.append(f"source={payload.get('source', 'missing')} does not match asip.git_gate")
    if payload.get("gate_status") != "pass":
        failures.append(f"gate_status={payload.get('gate_status')}")
        failures.extend(str(reason) for reason in payload.get("failure_reasons", []))
    if payload.get("diff_check") != "pass":
        failures.append(f"diff_check={payload.get('diff_check', 'missing')}")
    if payload.get("worktree_status") != "clean":
        failures.append(f"worktree_status={payload.get('worktree_status', 'missing')}")
    if payload.get("committed") is not True:
        failures.append("committed is not true")
    if payload.get("pushed") is not True:
        failures.append("pushed is not true")
    binding_failures, binding_evidence = _current_git_binding_failures(payload)
    failures.extend(binding_failures)
    status = "pass" if not failures else "blocked"
    evidence = (
        f"diff_check={payload.get('diff_check')}; worktree_status={payload.get('worktree_status')}; "
        f"committed={payload.get('committed')}; pushed={payload.get('pushed')}"
    )
    if binding_evidence:
        evidence = f"{evidence}; {binding_evidence}"
    return _requirement("git_gate", "Final diff, commit, and push gate", status, evidence, failures)


def _current_git_binding_failures(payload: Mapping[str, Any]) -> Tuple[List[str], str]:
    repo_root_value = payload.get("repo_root")
    if not isinstance(repo_root_value, str) or not repo_root_value.strip():
        return [], ""

    repo_root = Path(repo_root_value)
    failures: List[str] = []
    evidence: List[str] = []
    if not repo_root.exists():
        return [f"repo_root does not exist: {repo_root_value}"], f"repo_root={repo_root_value}"

    current_head = _git_stdout(repo_root, ["rev-parse", "HEAD"], failures, "HEAD")
    artifact_head = str(payload.get("head") or "").strip()
    if artifact_head:
        evidence.append(f"artifact_head={_short_sha(artifact_head)}")
        if current_head and current_head != artifact_head:
            failures.append(
                f"head does not match current HEAD: artifact={artifact_head} current={current_head}"
            )
    elif payload.get("gate_status") == "pass":
        failures.append("head is missing from git gate artifact")
    if current_head:
        evidence.append(f"current_head={_short_sha(current_head)}")

    current_branch = _git_stdout(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"], failures, "branch")
    artifact_branch = str(payload.get("branch") or "").strip()
    if artifact_branch:
        evidence.append(f"artifact_branch={artifact_branch}")
        if current_branch and current_branch != artifact_branch:
            failures.append(
                f"branch does not match current branch: artifact={artifact_branch} current={current_branch}"
            )
    if current_branch:
        evidence.append(f"current_branch={current_branch}")

    diff_check = _run_git(repo_root, ["diff", "--check"])
    if diff_check.returncode != 0:
        failures.append("current git diff --check failed")
    status = _run_git(repo_root, ["status", "--porcelain=v1"])
    if status.returncode != 0:
        failures.append("current git status failed")
    else:
        changed_paths = [line for line in status.stdout.splitlines() if line.strip()]
        if changed_paths:
            failures.append(f"current worktree has {len(changed_paths)} changed/untracked paths")
        evidence.append("current_worktree=clean" if not changed_paths else f"current_worktree=dirty:{len(changed_paths)}")

    artifact_upstream = str(payload.get("upstream") or "").strip()
    should_check_upstream = artifact_upstream or payload.get("ahead") is not None or payload.get("behind") is not None
    if should_check_upstream:
        current_upstream = _git_stdout(
            repo_root,
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            failures,
            "upstream",
        )
        if artifact_upstream:
            evidence.append(f"artifact_upstream={artifact_upstream}")
            if current_upstream and current_upstream != artifact_upstream:
                failures.append(
                    f"upstream does not match current upstream: artifact={artifact_upstream} current={current_upstream}"
                )
        if current_upstream:
            evidence.append(f"current_upstream={current_upstream}")
            ahead_behind = _git_stdout(repo_root, ["rev-list", "--left-right", "--count", "HEAD...@{u}"], failures, "ahead/behind")
            if ahead_behind:
                parts = ahead_behind.split()
                if len(parts) == 2:
                    current_ahead = int(parts[0])
                    current_behind = int(parts[1])
                    if payload.get("ahead") is not None and int(payload.get("ahead") or 0) != current_ahead:
                        failures.append(f"ahead does not match current upstream count: artifact={payload.get('ahead')} current={current_ahead}")
                    if payload.get("behind") is not None and int(payload.get("behind") or 0) != current_behind:
                        failures.append(f"behind does not match current upstream count: artifact={payload.get('behind')} current={current_behind}")
                    if current_ahead != 0:
                        failures.append(f"current branch is {current_ahead} commit(s) ahead of upstream")
                    if current_behind != 0:
                        failures.append(f"current branch is {current_behind} commit(s) behind upstream")
                    evidence.append(f"current_ahead={current_ahead}")
                    evidence.append(f"current_behind={current_behind}")
                else:
                    failures.append(f"current ahead/behind output is malformed: {ahead_behind}")

    return failures, "; ".join(evidence)


def _run_git(repo_root: Path, args: List[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(["git", *args], 1, "", str(exc))


def _git_stdout(repo_root: Path, args: List[str], failures: List[str], label: str) -> str:
    result = _run_git(repo_root, args)
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "").strip()
        failures.append(f"current git {label} check failed" + (f": {message}" if message else ""))
        return ""
    return result.stdout.strip()


def _short_sha(value: str) -> str:
    return value[:12] if len(value) > 12 else value


def _requirement(
    requirement_id: str,
    title: str,
    status: str,
    evidence: str,
    failure_reasons: List[str],
) -> Dict[str, Any]:
    return {
        "id": requirement_id,
        "title": title,
        "status": status,
        "evidence": evidence,
        "failure_reasons": failure_reasons,
    }


def _status_summary(requirements: Iterable[Mapping[str, Any]]) -> Dict[str, int]:
    counts = {"total": 0, "passed": 0, "blocked": 0, "failed": 0, "missing": 0}
    for item in requirements:
        counts["total"] += 1
        status = str(item.get("status", "fail"))
        if status == "pass":
            counts["passed"] += 1
        elif status == "missing":
            counts["missing"] += 1
        elif status == "fail":
            counts["failed"] += 1
        else:
            counts["blocked"] += 1
    return counts


def _render_markdown(result: Mapping[str, Any]) -> str:
    lines = [
        "# ASIP Current Completion Gate",
        "",
        f"- Generated: `{result.get('generated_at')}`",
        f"- Database: `{result.get('db_path')}`",
        f"- Gate status: `{result.get('gate_status')}`",
        "",
        "## Summary",
        "",
    ]
    summary = result.get("summary", {})
    lines.append(
        f"- Requirements: `{summary.get('passed', 0)}/{summary.get('total', 0)}` passed, "
        f"`{summary.get('blocked', 0)}` blocked, `{summary.get('failed', 0)}` failed, "
        f"`{summary.get('missing', 0)}` missing."
    )
    lines.extend(["", "## Requirements", "", "| Requirement | Status | Evidence |", "| --- | --- | --- |"])
    for item in result.get("requirements", []):
        lines.append(
            f"| `{item.get('id')}` | `{item.get('status')}` | {_escape_table(_shorten(str(item.get('evidence', ''))))} |"
        )
    if result.get("failure_reasons"):
        lines.extend(["", "## Blocking Reasons", ""])
        for reason in result.get("failure_reasons", []):
            lines.append(f"- {reason}")
    lines.append("")
    return "\n".join(lines)


def _shorten(text: str, limit: int = 180) -> str:
    return text if len(text) <= limit else f"{text[: limit - 3]}..."


def _escape_table(text: str) -> str:
    return text.replace("|", "\\|")
