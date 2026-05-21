"""Runtime semantic graph freshness QA artifact generation."""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from .storage import AsipStore, normalize_job_status
from .workbench import global_graph, query_evidence


CHECK_IDS = (
    "storage_runtime_stale_semantic_filter",
    "storage_runtime_fresh_semantic_keep",
    "storage_runtime_fresh_doc_node_keep",
    "storage_runtime_extractor_job_kind_binding",
    "storage_runtime_provider_mismatch_filter",
    "real_db_global_graph_semantic_leak_probe",
    "real_db_query_graph_semantic_leak_probe",
)


def run_runtime_semantic_freshness_qa(
    db_path: Path,
    *,
    output_json: Optional[Path] = None,
    query: str = "GCVM_L2_CNTL",
) -> Dict[str, Any]:
    db_path = db_path.resolve()
    with sqlite3.connect(str(db_path)) as connection:
        connection.row_factory = sqlite3.Row
        latest_jobs = _latest_job_ids(connection)
        job_kinds = _job_kinds_by_id(connection)

    store = AsipStore.connect(str(db_path))
    try:
        policy = store._runtime_semantic_graph_policy()
        semantic_rows = _semantic_rows(store)
        runtime_rows = [
            row
            for row in semantic_rows
            if store._runtime_graph_edge_row_is_usable(row)
        ]
    finally:
        store.con.close()

    freshness_floor_job_id = policy.get("freshness_floor_job_id")
    expected_provider = str(policy.get("expected_provider") or "")
    expected_model = str(policy.get("expected_model") or "")

    stale_visible_count = _count_stale_visible_semantic_rows(runtime_rows, freshness_floor_job_id)
    fresh_semantic_count = _count_extractor_rows(runtime_rows, "semantic_edges")
    fresh_doc_node_count = _count_extractor_rows(runtime_rows, "doc_nodes")
    bad_extractor_job_kind_count = _count_bad_extractor_job_kind_rows(runtime_rows, job_kinds)
    provider_mismatch_count = _count_provider_mismatch_rows(
        runtime_rows,
        expected_provider=expected_provider,
        expected_model=expected_model,
    )

    global_graph_payload = global_graph(db_path, all_edges=True, function_view="concept")
    global_stage_counts = _stage_counts(global_graph_payload.get("edges", []))
    query_payload = query_evidence(db_path, query, function_view="concept")
    query_graph = query_payload.get("graph", {})
    query_stage_counts = _stage_counts(query_graph.get("edges", []) if isinstance(query_graph, Mapping) else [])
    query_row_count = len(query_payload.get("rows", []))

    checks = [
        _check(
            "storage_runtime_stale_semantic_filter",
            stale_visible_count == 0,
            f"stale extractor edge count={stale_visible_count}",
        ),
        _check(
            "storage_runtime_fresh_semantic_keep",
            fresh_semantic_count > 0,
            f"fresh semantic edge count={fresh_semantic_count}",
        ),
        _check(
            "storage_runtime_fresh_doc_node_keep",
            fresh_doc_node_count > 0,
            f"fresh doc-node edge count={fresh_doc_node_count}",
        ),
        _check(
            "storage_runtime_extractor_job_kind_binding",
            bad_extractor_job_kind_count == 0,
            f"bad extractor/job binding count={bad_extractor_job_kind_count}",
        ),
        _check(
            "storage_runtime_provider_mismatch_filter",
            provider_mismatch_count == 0,
            f"provider/model mismatch count={provider_mismatch_count}",
        ),
        _check(
            "real_db_global_graph_semantic_leak_probe",
            bool(global_stage_counts) and _semantic_or_mixed_count(global_stage_counts) > 0,
            f"global graph stage counts={dict(global_stage_counts)}",
        ),
        _check(
            "real_db_query_graph_semantic_leak_probe",
            query_row_count > 0 and bool(query_stage_counts) and _semantic_or_mixed_count(query_stage_counts) > 0,
            f"query {query} rows={query_row_count}; stage counts={dict(query_stage_counts)}",
        ),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    payload = {
        "source": "asip.runtime_semantic_freshness_qa",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "db_path": str(db_path),
        "latest_index_job_id": latest_jobs.get("latest_index_job_id"),
        "latest_graph_rebuild_job_id": latest_jobs.get("latest_graph_rebuild_job_id"),
        "latest_semantic_edges_job_id": latest_jobs.get("latest_semantic_edges_job_id"),
        "latest_doc_nodes_job_id": latest_jobs.get("latest_doc_nodes_job_id"),
        "freshness_floor_job_id": freshness_floor_job_id,
        "db_semantic_edge_counts": {
            "doc_nodes": fresh_doc_node_count,
            "semantic_edges": fresh_semantic_count,
        },
        "global_graph_stage_counts": dict(global_stage_counts),
        "query_graph_probe": {
            "query": query,
            "row_count": query_row_count,
            "stage_counts": dict(query_stage_counts),
        },
        "gate_status": "pass" if passed == len(checks) else "blocked",
        "summary": {
            "checks": len(checks),
            "passed": passed,
            "failed": len(checks) - passed,
        },
        "checks": checks,
    }
    if output_json is not None:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def _latest_job_ids(connection: sqlite3.Connection) -> Dict[str, Optional[int]]:
    result: Dict[str, Optional[int]] = {
        "latest_index_job_id": None,
        "latest_graph_rebuild_job_id": None,
        "latest_semantic_edges_job_id": None,
        "latest_doc_nodes_job_id": None,
    }
    if not _table_exists(connection, "jobs"):
        return result
    for row in connection.execute("select id, kind, status from jobs order by id asc"):
        if normalize_job_status(str(row["status"] or "")) != "succeeded":
            continue
        job_id = int(row["id"])
        kind = str(row["kind"] or "")
        if kind == "index":
            result["latest_index_job_id"] = job_id
        elif kind == "graph_rebuild":
            result["latest_graph_rebuild_job_id"] = job_id
        elif kind in {"semantic_edges", "semantic_edges_batch"}:
            result["latest_semantic_edges_job_id"] = job_id
        elif kind == "doc_nodes_batch":
            result["latest_doc_nodes_job_id"] = job_id
    return result


def _job_kinds_by_id(connection: sqlite3.Connection) -> Dict[int, str]:
    if not _table_exists(connection, "jobs"):
        return {}
    return {
        int(row["id"]): str(row["kind"] or "")
        for row in connection.execute("select id, kind from jobs")
    }


def _semantic_rows(store: AsipStore) -> list[sqlite3.Row]:
    if not _table_exists(store.con, "edges"):
        return []
    return list(
        store.con.execute(
            """
            select id, src, dst, relation, confidence, stage, source, path, line_start, line_end, provenance_json
            from edges
            where stage = 'semantic'
            order by id asc
            """
        )
    )


def _count_stale_visible_semantic_rows(rows: Iterable[sqlite3.Row], freshness_floor_job_id: object) -> int:
    floor = _int_value(freshness_floor_job_id)
    count = 0
    for row in rows:
        provenance = _provenance(row)
        if _extractor(provenance) not in {"semantic_edges", "doc_nodes"}:
            continue
        job_id = _int_value(provenance.get("job_id"))
        if not job_id or (floor is not None and job_id < floor):
            count += 1
    return count


def _count_extractor_rows(rows: Iterable[sqlite3.Row], extractor: str) -> int:
    return sum(1 for row in rows if _extractor(_provenance(row)) == extractor)


def _count_bad_extractor_job_kind_rows(rows: Iterable[sqlite3.Row], job_kinds: Mapping[int, str]) -> int:
    count = 0
    for row in rows:
        provenance = _provenance(row)
        extractor = _extractor(provenance)
        if extractor not in {"semantic_edges", "doc_nodes"}:
            continue
        job_id = _int_value(provenance.get("job_id"))
        if not job_id or not _job_kind_matches_extractor(extractor, job_kinds.get(job_id, "")):
            count += 1
    return count


def _count_provider_mismatch_rows(
    rows: Iterable[sqlite3.Row],
    *,
    expected_provider: str,
    expected_model: str,
) -> int:
    count = 0
    for row in rows:
        provenance = _provenance(row)
        extractor = _extractor(provenance)
        if extractor not in {"semantic_edges", "doc_nodes"}:
            continue
        provider = str(provenance.get("provider") or row["source"] or "").strip()
        model = str(provenance.get("model") or "").strip()
        if expected_provider and provider != expected_provider:
            count += 1
            continue
        if expected_model and model != expected_model:
            count += 1
    return count


def _job_kind_matches_extractor(extractor: str, kind: str) -> bool:
    if extractor == "semantic_edges":
        return kind in {"semantic_edges", "semantic_edges_batch"}
    if extractor == "doc_nodes":
        return kind == "doc_nodes_batch"
    return True


def _stage_counts(edges: Iterable[Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for edge in edges:
        if isinstance(edge, Mapping):
            stage = str(edge.get("stage") or "deterministic")
            counts[stage] += 1
    return counts


def _semantic_or_mixed_count(stage_counts: Mapping[str, int]) -> int:
    return int(stage_counts.get("semantic", 0) or 0) + int(stage_counts.get("mixed", 0) or 0)


def _check(check_id: str, passed: bool, message: str) -> Dict[str, str]:
    return {
        "id": check_id,
        "status": "pass" if passed else "fail",
        "message": message,
    }


def _provenance(row: sqlite3.Row) -> Dict[str, Any]:
    try:
        payload = json.loads(str(row["provenance_json"] or "{}"))
    except json.JSONDecodeError:
        payload = {}
    return payload if isinstance(payload, dict) else {}


def _extractor(provenance: Mapping[str, Any]) -> str:
    return str(provenance.get("extractor") or "").strip()


def _int_value(value: object) -> Optional[int]:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "select 1 from sqlite_master where type='table' and name=?",
        (table,),
    ).fetchone()
    return row is not None
