"""Blackbox profile ledger QA artifact generation."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from .storage import AsipStore, normalize_job_status


_REQUIRED_BLACKBOX_PROVENANCE_KEYS = (
    "job_id",
    "batch_id",
    "attempt_id",
    "candidate_id",
    "prompt_sha256",
    "response_sha256",
    "validator_version",
    "provider",
    "model",
)


def run_blackbox_ledger_qa(
    db_path: Path,
    *,
    output_json: Optional[Path] = None,
    output_md: Optional[Path] = None,
    limits_config: Path = Path("configs/workbench-limits.json"),
) -> Dict[str, Any]:
    store = AsipStore.connect(str(db_path))
    store.migrate()
    try:
        inventory = store.product_endpoint_inventory(function_view="both", stages=("deterministic",))
        latest_jobs = _latest_job_ids(store.con)
        latest_blackbox_job_id = latest_jobs.get("latest_blackbox_profiles_job_id")
        blackbox_jobs = _blackbox_job_rows(store.con)
        ledger = store.llm_batch_ledger(int(latest_blackbox_job_id)) if latest_blackbox_job_id else []
        entity_ledger = store.blackbox_entity_ledger(int(latest_blackbox_job_id)) if latest_blackbox_job_id else {
            "manifests": [],
            "candidates": [],
            "provider_responses": [],
            "validation_failures": [],
            "io_facts": [],
        }
        profile_table_rows = store.blackbox_profiles_for_job(int(latest_blackbox_job_id)) if latest_blackbox_job_id else []
        semantic_rows = _semantic_edge_rows(store.con)
        blackbox_rows = [
            row
            for row in semantic_rows
            if str(_provenance(row).get("extractor") or "") == "blackbox_profiles"
        ]
        latest_blackbox_rows = [
            row
            for row in blackbox_rows
            if latest_blackbox_job_id is not None
            and _int_value(_provenance(row).get("job_id")) == int(latest_blackbox_job_id)
        ]
        latest_blackbox_row_ids = {int(row["id"]) for row in latest_blackbox_rows}
        visible_rows = [row for row in latest_blackbox_rows if store._runtime_graph_edge_row_is_usable(row)]
        stale_filtered_rows = [
            row
            for row in blackbox_rows
            if int(row["id"]) not in latest_blackbox_row_ids and not store._runtime_graph_edge_row_is_usable(row)
        ]
        manifest_groups = _manifest_group_summaries(store, blackbox_jobs, blackbox_rows)
        latest_manifest_group = _latest_manifest_group(manifest_groups, latest_blackbox_job_id)
        settings = store.load_provider_settings() if store._table_exists("provider_settings") else {}
    finally:
        store.con.close()

    inventory_candidate_ids = sorted(str(candidate.get("candidate_id") or "") for candidate in inventory)
    inventory_counts = _inventory_counts(inventory)
    attempt_status_counts = Counter()
    validator_status_counts = Counter()
    reason_code_counts = Counter()
    manifest_hashes: set[str] = set()
    attempted_candidate_ids: list[str] = []
    attempt_count = 0
    for batch in ledger:
        attempted_candidate_ids.extend(str(item) for item in batch.get("candidate_ids", []) if str(item))
        metadata = batch.get("metadata") if isinstance(batch.get("metadata"), Mapping) else {}
        manifest_sha = str(metadata.get("manifest_sha256") or "").strip()
        if manifest_sha:
            manifest_hashes.add(manifest_sha)
        attempts = batch.get("attempts") if isinstance(batch.get("attempts"), list) else []
        attempt_count += len(attempts)
        for attempt in attempts:
            if isinstance(attempt, Mapping):
                attempt_status_counts[str(attempt.get("status") or "unknown")] += 1
                attempt_metadata = attempt.get("metadata") if isinstance(attempt.get("metadata"), Mapping) else {}
                validator_status_counts[str(attempt_metadata.get("validator_status") or "unknown")] += 1
                for reason_code in attempt_metadata.get("reason_codes", []) if isinstance(attempt_metadata.get("reason_codes"), list) else []:
                    reason_code_counts[str(reason_code or "unknown")] += 1
    attempted_count = len(attempted_candidate_ids)
    terminal_count = sum(
        attempt_status_counts[status]
        for status in ("accepted", "rejected", "failed", "skipped", "persisted")
    )
    profile_rows = [row for row in latest_blackbox_rows if str(row["src"]) == str(row["dst"])]
    relationship_rows = [row for row in latest_blackbox_rows if str(row["src"]) != str(row["dst"])]
    provenance_failures = _blackbox_provenance_failures(latest_blackbox_rows)
    profile_table_failures = _blackbox_profile_table_failures(profile_table_rows)
    content_grounded_count = sum(
        1
        for profile in profile_table_rows
        if str(profile.get("status") or "") in {"accepted", "repaired", "persisted"}
        and _blackbox_profile_has_content_grounding(profile)
    )
    latest_group_expected_shards = int(latest_manifest_group.get("expected_shard_count") or 0) if latest_manifest_group else 0
    latest_group_observed_shards = int(latest_manifest_group.get("observed_shard_count") or 0) if latest_manifest_group else 0
    latest_group_attempted = int(latest_manifest_group.get("attempted_count") or 0) if latest_manifest_group else 0
    latest_group_terminal = int(latest_manifest_group.get("terminal_attempt_count") or 0) if latest_manifest_group else 0
    entity_candidates = entity_ledger.get("candidates") if isinstance(entity_ledger.get("candidates"), list) else []
    entity_candidate_status_counts = Counter(
        str(candidate.get("status") or "unknown")
        for candidate in entity_candidates
        if isinstance(candidate, Mapping)
    )
    entity_candidate_terminal_count = sum(
        entity_candidate_status_counts[status]
        for status in ("accepted", "rejected", "failed", "skipped", "persisted")
    )
    entity_manifests = entity_ledger.get("manifests") if isinstance(entity_ledger.get("manifests"), list) else []
    entity_provider_responses = (
        entity_ledger.get("provider_responses") if isinstance(entity_ledger.get("provider_responses"), list) else []
    )
    entity_validation_failures = (
        entity_ledger.get("validation_failures") if isinstance(entity_ledger.get("validation_failures"), list) else []
    )
    entity_io_facts = entity_ledger.get("io_facts") if isinstance(entity_ledger.get("io_facts"), list) else []
    checks = [
        _check("blackbox_job_present", latest_blackbox_job_id is not None, f"latest job id={latest_blackbox_job_id}"),
        _check("inventory_non_empty", len(inventory) > 0, f"inventory_total={len(inventory)}"),
        _check("ledger_present", bool(ledger), f"batch_count={len(ledger)}"),
        _check(
            "entity_manifest_present",
            len(entity_manifests) > 0,
            f"manifest_rows={len(entity_manifests)}",
        ),
        _check(
            "entity_candidate_terminal_status",
            len(entity_candidates) > 0 and entity_candidate_terminal_count == len(entity_candidates),
            f"candidates={len(entity_candidates)}; terminal={entity_candidate_terminal_count}; statuses={dict(entity_candidate_status_counts)}",
        ),
        _check(
            "entity_provider_response_present",
            len(entity_provider_responses) > 0,
            f"provider_responses={len(entity_provider_responses)}",
        ),
        _check(
            "entity_io_facts_present",
            len(profile_table_rows) == 0 or len(entity_io_facts) > 0,
            f"io_facts={len(entity_io_facts)}; profile_table_rows={len(profile_table_rows)}",
        ),
        _check(
            "manifest_group_present",
            latest_manifest_group is not None and bool(latest_manifest_group.get("manifest_group_sha256")),
            f"group={latest_manifest_group.get('manifest_group_sha256') if latest_manifest_group else None}; latest_job={latest_blackbox_job_id}",
        ),
        _check(
            "manifest_group_shard_coverage",
            latest_manifest_group is not None
            and latest_group_expected_shards > 0
            and latest_group_observed_shards == latest_group_expected_shards,
            f"observed_shards={latest_group_observed_shards}; expected_shards={latest_group_expected_shards}",
        ),
        _check(
            "manifest_group_ledger_completeness",
            latest_manifest_group is not None
            and latest_group_attempted > 0
            and latest_group_terminal == latest_group_attempted,
            f"attempted={latest_group_attempted}; terminal={latest_group_terminal}",
        ),
        _check(
            "ledger_completeness",
            attempted_count > 0 and terminal_count == attempted_count,
            f"attempted={attempted_count}; terminal={terminal_count}; statuses={dict(attempt_status_counts)}",
        ),
        _check("profile_edges_persisted", len(profile_rows) > 0, f"profile_edges={len(profile_rows)}"),
        _check(
            "profile_table_persisted",
            len(profile_table_rows) > 0,
            f"profile_table_rows={len(profile_table_rows)}",
        ),
        _check(
            "content_validator_present",
            content_grounded_count == len(profile_table_rows) and len(profile_table_rows) > 0,
            f"grounded={content_grounded_count}; profile_table_rows={len(profile_table_rows)}; reasons={dict(reason_code_counts)}",
            profile_table_failures,
        ),
        _check(
            "blackbox_provenance_backrefs",
            not provenance_failures,
            f"checked_edges={len(latest_blackbox_rows)}; failures={len(provenance_failures)}",
            provenance_failures,
        ),
        _check(
            "runtime_freshness_visible",
            len(visible_rows) == len(latest_blackbox_rows) and len(visible_rows) > 0,
            f"visible={len(visible_rows)}; latest_stored={len(latest_blackbox_rows)}; stale_filtered={len(stale_filtered_rows)}",
        ),
    ]
    passed = sum(1 for check in checks if check["status"] == "pass")
    payload: Dict[str, Any] = {
        "source": "asip.blackbox_ledger_qa",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_head": _repo_head(Path.cwd()),
        "db_path": str(db_path),
        "db_sha256": _sha256_file(db_path),
        "limits_config_path": str(limits_config),
        "limits_config_sha256": _sha256_file(limits_config),
        "provider_settings": settings,
        "latest_jobs": latest_jobs,
        "inventory": {
            "total": len(inventory),
            "sha256": _sha256_text("\n".join(inventory_candidate_ids)),
            "counts": inventory_counts,
        },
        "ledger": {
            "batch_count": len(ledger),
            "attempt_count": attempt_count,
            "attempted_count": attempted_count,
            "attempt_status_counts": dict(attempt_status_counts),
            "validator_status_counts": dict(validator_status_counts),
            "reason_code_counts": dict(reason_code_counts),
            "manifest_sha256_values": sorted(manifest_hashes),
        },
        "entity_ledger": {
            "manifest_count": len(entity_manifests),
            "candidate_count": len(entity_candidates),
            "candidate_status_counts": dict(entity_candidate_status_counts),
            "provider_response_count": len(entity_provider_responses),
            "validation_failure_count": len(entity_validation_failures),
            "io_fact_count": len(entity_io_facts),
        },
        "manifest_groups": manifest_groups,
        "latest_manifest_group": latest_manifest_group or {},
        "profiles": {
            "storage_mode": "canonical_table_with_self_edge_projection",
            "profile_table_count": len(profile_table_rows),
            "stored_edge_count": len(latest_blackbox_rows),
            "all_stored_edge_count": len(blackbox_rows),
            "profile_edge_count": len(profile_rows),
            "relationship_edge_count": len(relationship_rows),
            "runtime_visible_count": len(visible_rows),
            "stale_filtered_count": len(stale_filtered_rows),
            "provenance_failure_count": len(provenance_failures),
            "provenance_failures": provenance_failures,
            "content_grounded_count": content_grounded_count,
            "profile_table_failures": profile_table_failures,
        },
        "surface_results": [
            {
                "surface": "storage",
                "transport": "sqlite",
                "dbPath": str(db_path),
                "status": "pass" if len(visible_rows) > 0 else "fail",
                "schema_checks": [
                    "llm_batches",
                    "llm_attempts",
                    "blackbox_profiles",
                    "blackbox_manifests",
                    "blackbox_manifest_candidates",
                    "llm_provider_responses",
                    "blackbox_validation_failures",
                    "blackbox_io_facts",
                    "edges.provenance_json",
                ],
            },
            {
                "surface": "cli",
                "transport": "python -m asip.cli blackbox-ledger-qa",
                "dbPath": str(db_path),
                "status": "pass",
            },
        ],
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
    if output_md is not None:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(_markdown_summary(payload), encoding="utf-8")
    return payload


def _semantic_edge_rows(connection: sqlite3.Connection) -> list[sqlite3.Row]:
    if not _table_exists(connection, "edges"):
        return []
    return list(
        connection.execute(
            """
            select id, src, dst, relation, confidence, stage, source, path, line_start, line_end, provenance_json
            from edges
            where stage = 'semantic'
            order by id asc
            """
        )
    )


def _blackbox_provenance_failures(rows: Iterable[sqlite3.Row]) -> list[Dict[str, Any]]:
    failures: list[Dict[str, Any]] = []
    for row in rows:
        provenance = _provenance(row)
        if str(provenance.get("extractor") or "") != "blackbox_profiles":
            continue
        missing = [
            key
            for key in _REQUIRED_BLACKBOX_PROVENANCE_KEYS
            if provenance.get(key) in ("", None, 0)
        ]
        if missing:
            failures.append({"edge_id": int(row["id"]), "missing": missing})
    return failures


def _blackbox_profile_table_failures(rows: Iterable[Mapping[str, Any]]) -> list[Dict[str, Any]]:
    failures: list[Dict[str, Any]] = []
    for row in rows:
        missing = [
            key
            for key in (
                "endpoint_id",
                "provider",
                "model",
                "job_id",
                "batch_id",
                "attempt_id",
                "candidate_id",
                "prompt_sha256",
                "response_sha256",
                "validator_version",
            )
            if row.get(key) in ("", None, 0)
        ]
        if missing:
            failures.append({"profile_id": row.get("id"), "missing": missing})
        if not _blackbox_profile_has_content_grounding(row):
            failures.append({"profile_id": row.get("id"), "missing": ["content_grounding"]})
    return failures


def _blackbox_profile_has_content_grounding(row: Mapping[str, Any]) -> bool:
    profile = row.get("profile") if isinstance(row.get("profile"), Mapping) else {}
    if not profile:
        return False
    refs = profile.get("evidence_refs")
    reason_codes = profile.get("reason_codes")
    status = str(profile.get("validator_status") or row.get("status") or "")
    if status not in {"accepted", "repaired", "persisted"}:
        return False
    if isinstance(refs, list) and any(str(ref or "").strip() for ref in refs):
        return True
    if isinstance(reason_codes, list) and any(str(code or "").startswith("repaired_") for code in reason_codes):
        return True
    return False


def _inventory_counts(inventory: Iterable[Mapping[str, Any]]) -> Dict[str, Dict[str, int]]:
    by_kind = Counter()
    by_view = Counter()
    by_bucket = Counter()
    for candidate in inventory:
        by_kind[str(candidate.get("kind") or "unknown")] += 1
        by_view[str(candidate.get("view") or "unknown")] += 1
        by_bucket[str(candidate.get("coverage_bucket") or "unknown")] += 1
    return {
        "by_kind": dict(by_kind),
        "by_view": dict(by_view),
        "by_bucket": dict(by_bucket),
    }


def _latest_job_ids(connection: sqlite3.Connection) -> Dict[str, Optional[int]]:
    result: Dict[str, Optional[int]] = {
        "latest_index_job_id": None,
        "latest_graph_rebuild_job_id": None,
        "latest_blackbox_profiles_job_id": None,
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
        elif kind == "blackbox_profiles_batch":
            result["latest_blackbox_profiles_job_id"] = job_id
    return result


def _blackbox_job_rows(connection: sqlite3.Connection) -> list[Dict[str, Any]]:
    if not _table_exists(connection, "jobs"):
        return []
    rows = connection.execute(
        """
        select id, kind, status, metadata_json, started_at, finished_at
        from jobs
        where kind = 'blackbox_profiles_batch'
        order by id asc
        """
    ).fetchall()
    result: list[Dict[str, Any]] = []
    for row in rows:
        metadata = json.loads(str(row["metadata_json"] or "{}"))
        result.append(
            {
                "id": int(row["id"]),
                "status": normalize_job_status(str(row["status"] or "")),
                "metadata": metadata if isinstance(metadata, dict) else {},
                "started_at": row["started_at"],
                "finished_at": row["finished_at"],
            }
        )
    return result


def _manifest_group_summaries(
    store: AsipStore,
    blackbox_jobs: Iterable[Mapping[str, Any]],
    blackbox_rows: Iterable[sqlite3.Row],
) -> list[Dict[str, Any]]:
    rows_by_job: Dict[int, list[sqlite3.Row]] = {}
    for row in blackbox_rows:
        job_id = _int_value(_provenance(row).get("job_id"))
        if job_id is not None:
            rows_by_job.setdefault(job_id, []).append(row)
    groups: Dict[str, Dict[str, Any]] = {}
    for job in blackbox_jobs:
        if str(job.get("status") or "") != "succeeded":
            continue
        job_id = int(job.get("id") or 0)
        if job_id <= 0:
            continue
        ledger = store.llm_batch_ledger(job_id)
        metadata = job.get("metadata") if isinstance(job.get("metadata"), Mapping) else {}
        group_sha = _manifest_group_sha(metadata, ledger)
        if not group_sha:
            continue
        group = groups.setdefault(
            group_sha,
            {
                "manifest_group_sha256": group_sha,
                "job_ids": [],
                "manifest_sha256_values": set(),
                "shard_indexes": set(),
                "expected_shard_count": 0,
                "batch_count": 0,
                "attempt_count": 0,
                "attempted_count": 0,
                "terminal_attempt_count": 0,
                "attempt_status_counts": Counter(),
                "profile_table_count": 0,
                "stored_edge_count": 0,
                "profile_edge_count": 0,
                "relationship_edge_count": 0,
                "runtime_visible_count": 0,
            },
        )
        group["job_ids"].append(job_id)
        manifest_sha = str(metadata.get("manifest_sha256") or "").strip()
        if manifest_sha:
            group["manifest_sha256_values"].add(manifest_sha)
        shard_index = _int_value(metadata.get("shard_index"))
        if shard_index is not None:
            group["shard_indexes"].add(shard_index)
        shard_count = _int_value(metadata.get("shard_count"))
        if shard_count is not None:
            group["expected_shard_count"] = max(int(group["expected_shard_count"]), shard_count)
        group["batch_count"] = int(group["batch_count"]) + len(ledger)
        profile_rows = store.blackbox_profiles_for_job(job_id)
        group["profile_table_count"] = int(group["profile_table_count"]) + len(profile_rows)
        job_rows = rows_by_job.get(job_id, [])
        group["stored_edge_count"] = int(group["stored_edge_count"]) + len(job_rows)
        group["profile_edge_count"] = int(group["profile_edge_count"]) + sum(1 for row in job_rows if str(row["src"]) == str(row["dst"]))
        group["relationship_edge_count"] = int(group["relationship_edge_count"]) + sum(1 for row in job_rows if str(row["src"]) != str(row["dst"]))
        group["runtime_visible_count"] = int(group["runtime_visible_count"]) + sum(
            1 for row in job_rows if store._runtime_graph_edge_row_is_usable(row)
        )
        for batch in ledger:
            group["attempted_count"] = int(group["attempted_count"]) + len(
                [item for item in batch.get("candidate_ids", []) if str(item)]
            )
            batch_metadata = batch.get("metadata") if isinstance(batch.get("metadata"), Mapping) else {}
            batch_manifest_sha = str(batch_metadata.get("manifest_sha256") or "").strip()
            if batch_manifest_sha:
                group["manifest_sha256_values"].add(batch_manifest_sha)
            batch_shard_index = _int_value(batch_metadata.get("shard_index"))
            if batch_shard_index is not None:
                group["shard_indexes"].add(batch_shard_index)
            batch_shard_count = _int_value(batch_metadata.get("shard_count"))
            if batch_shard_count is not None:
                group["expected_shard_count"] = max(int(group["expected_shard_count"]), batch_shard_count)
            attempts = batch.get("attempts") if isinstance(batch.get("attempts"), list) else []
            group["attempt_count"] = int(group["attempt_count"]) + len(attempts)
            for attempt in attempts:
                if not isinstance(attempt, Mapping):
                    continue
                status = str(attempt.get("status") or "unknown")
                group["attempt_status_counts"][status] += 1
                if status in {"accepted", "rejected", "failed", "skipped", "persisted"}:
                    group["terminal_attempt_count"] = int(group["terminal_attempt_count"]) + 1
    normalized: list[Dict[str, Any]] = []
    for group in groups.values():
        shard_indexes = sorted(int(value) for value in group.pop("shard_indexes"))
        manifest_values = sorted(str(value) for value in group.pop("manifest_sha256_values"))
        status_counts = dict(group.pop("attempt_status_counts"))
        expected_shards = int(group.get("expected_shard_count") or 0)
        normalized.append(
            {
                **group,
                "job_ids": sorted(int(job_id) for job_id in group.get("job_ids", [])),
                "manifest_sha256_values": manifest_values,
                "shard_indexes": shard_indexes,
                "observed_shard_count": len(shard_indexes),
                "expected_shard_count": expected_shards,
                "complete": expected_shards > 0 and len(shard_indexes) == expected_shards,
                "attempt_status_counts": status_counts,
            }
        )
    return sorted(normalized, key=lambda item: (max(item.get("job_ids") or [0]), item["manifest_group_sha256"]))


def _manifest_group_sha(job_metadata: Mapping[str, Any], ledger: Iterable[Mapping[str, Any]]) -> str:
    for source in [job_metadata, *[batch.get("metadata") for batch in ledger if isinstance(batch, Mapping)]]:
        if not isinstance(source, Mapping):
            continue
        value = str(source.get("manifest_group_sha256") or "").strip()
        if value:
            return value
    for source in [job_metadata, *[batch.get("metadata") for batch in ledger if isinstance(batch, Mapping)]]:
        if not isinstance(source, Mapping):
            continue
        value = str(source.get("manifest_sha256") or "").strip()
        if value:
            return value
    return ""


def _latest_manifest_group(
    groups: Iterable[Mapping[str, Any]],
    latest_blackbox_job_id: Optional[int],
) -> Optional[Dict[str, Any]]:
    if latest_blackbox_job_id is None:
        return None
    for group in groups:
        job_ids = group.get("job_ids") if isinstance(group.get("job_ids"), list) else []
        if int(latest_blackbox_job_id) in {int(job_id) for job_id in job_ids}:
            return dict(group)
    return None


def _int_value(value: object) -> Optional[int]:
    try:
        return int(value) if value not in ("", None) else None
    except (TypeError, ValueError):
        return None


def _check(
    check_id: str,
    ok: bool,
    evidence: str,
    failures: Optional[list[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "id": check_id,
        "status": "pass" if ok else "fail",
        "evidence": evidence,
    }
    if failures:
        payload["failures"] = failures
    return payload


def _provenance(row: sqlite3.Row) -> Dict[str, Any]:
    try:
        value = json.loads(str(row["provenance_json"] or "{}"))
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _table_exists(connection: sqlite3.Connection, name: str) -> bool:
    return connection.execute(
        "select 1 from sqlite_master where type = 'table' and name = ?",
        (name,),
    ).fetchone() is not None


def _sha256_file(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _repo_head(cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(cwd),
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return result.stdout.strip()


def _markdown_summary(payload: Mapping[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    profiles = payload.get("profiles") if isinstance(payload.get("profiles"), Mapping) else {}
    ledger = payload.get("ledger") if isinstance(payload.get("ledger"), Mapping) else {}
    latest_group = payload.get("latest_manifest_group") if isinstance(payload.get("latest_manifest_group"), Mapping) else {}
    lines = [
        "# Blackbox Ledger QA",
        "",
        f"- Status: {payload.get('gate_status')}",
        f"- DB: `{payload.get('db_path')}`",
        f"- Checks: {summary.get('passed', 0)}/{summary.get('checks', 0)} passed",
        f"- Manifest group: `{latest_group.get('manifest_group_sha256', '')}`",
        f"- Manifest shards: {latest_group.get('observed_shard_count', 0)}/{latest_group.get('expected_shard_count', 0)}",
        f"- Manifest jobs: {latest_group.get('job_ids', [])}",
        f"- Batches: {ledger.get('batch_count', 0)}",
        f"- Attempts: {ledger.get('attempt_count', 0)}",
        f"- Stored blackbox edges: {profiles.get('stored_edge_count', 0)}",
        f"- Runtime visible blackbox edges: {profiles.get('runtime_visible_count', 0)}",
        "",
        "## Checks",
    ]
    for check in payload.get("checks", []) if isinstance(payload.get("checks"), list) else []:
        if isinstance(check, Mapping):
            lines.append(f"- {check.get('status')}: {check.get('id')} - {check.get('evidence')}")
    lines.append("")
    return "\n".join(lines)
