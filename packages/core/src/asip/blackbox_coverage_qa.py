"""Blackbox profile coverage QA artifact generation."""

from __future__ import annotations

import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

from .limits import DEFAULT_WORKBENCH_LIMITS_PATH
from .storage import AsipStore


def run_blackbox_coverage_qa(
    db_path: Path,
    *,
    output_json: Optional[Path] = None,
    output_md: Optional[Path] = None,
    min_coverage: float = 1.0,
    missing_sample_limit: int = 25,
) -> Dict[str, Any]:
    store = AsipStore.connect(str(db_path))
    store.migrate()
    try:
        inventory = store.product_endpoint_inventory(function_view="both", stages=("deterministic",))
        usable_profiles = _usable_profile_keys(store)
        terminal_status_counts = _terminal_status_counts(store)
        profile_status_counts = _profile_status_counts(store)
        latest_manifest_scope = _latest_manifest_scope(store, usable_profiles)
    finally:
        store.con.close()

    inventory_keys = {
        (str(candidate.get("view") or ""), str(candidate.get("endpoint_id") or ""))
        for candidate in inventory
        if str(candidate.get("view") or "") and str(candidate.get("endpoint_id") or "")
    }
    covered_keys = inventory_keys & usable_profiles
    missing = [
        candidate
        for candidate in inventory
        if (str(candidate.get("view") or ""), str(candidate.get("endpoint_id") or "")) not in covered_keys
    ]
    total = len(inventory_keys)
    covered = len(covered_keys)
    coverage_ratio = covered / total if total else 0.0
    required_ratio = max(0.0, min(1.0, float(min_coverage)))
    gate_status = "pass" if total > 0 and coverage_ratio >= required_ratio else "blocked"
    payload: Dict[str, Any] = {
        "source": "asip.blackbox_coverage_qa",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_head": _repo_head(Path.cwd()),
        "gate_status": gate_status,
        "db_path": str(db_path),
        "db_sha256": _sha256_file(db_path),
        "limits_config_path": str(DEFAULT_WORKBENCH_LIMITS_PATH),
        "limits_config_sha256": _sha256_file(DEFAULT_WORKBENCH_LIMITS_PATH),
        "min_coverage": required_ratio,
        "coverage": {
            "inventory_total": total,
            "covered_count": covered,
            "missing_count": max(0, total - covered),
            "coverage_ratio": round(coverage_ratio, 6),
            "accepted_count": int(profile_status_counts.get("accepted", 0)),
            "repaired_count": int(profile_status_counts.get("repaired", 0)),
            "abstained_count": int(terminal_status_counts.get("abstained", 0)),
            "rejected_count": int(terminal_status_counts.get("rejected", 0)),
            "failed_count": int(terminal_status_counts.get("failed", 0)),
        },
        "terminal_status_counts": terminal_status_counts,
        "profile_status_counts": profile_status_counts,
        "latest_manifest_scope": latest_manifest_scope,
        "by_view": _coverage_counts(inventory, covered_keys, key_name="view"),
        "by_kind": _coverage_counts(inventory, covered_keys, key_name="kind"),
        "by_bucket": _coverage_counts(inventory, covered_keys, key_name="coverage_bucket"),
        "missing_samples": [
            {
                "candidate_id": str(candidate.get("candidate_id") or ""),
                "view": str(candidate.get("view") or ""),
                "kind": str(candidate.get("kind") or ""),
                "endpoint_id": str(candidate.get("endpoint_id") or ""),
                "coverage_bucket": str(candidate.get("coverage_bucket") or ""),
                "neighbor_count": len(candidate.get("neighbors") if isinstance(candidate.get("neighbors"), list) else []),
            }
            for candidate in missing[: max(0, int(missing_sample_limit))]
        ],
    }
    payload["summary"] = {
        "status": gate_status,
        "coverage_ratio": payload["coverage"]["coverage_ratio"],
        "covered": covered,
        "total": total,
        "missing": max(0, total - covered),
        "min_coverage": required_ratio,
        "latest_manifest_scope": _scope_summary(latest_manifest_scope),
    }
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if output_md:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(_markdown_summary(payload), encoding="utf-8")
    return payload


def _sha256_file(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.expanduser().resolve().open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return ""


def _repo_head(cwd: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(cwd), text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _usable_profile_keys(store: AsipStore) -> set[tuple[str, str]]:
    return store.usable_blackbox_profile_keys()


def _terminal_status_counts(store: AsipStore) -> Dict[str, int]:
    counts: Counter[str] = Counter()
    if store._table_exists("blackbox_manifest_candidates"):
        rows = store.con.execute("select status, count(*) from blackbox_manifest_candidates group by status").fetchall()
        for row in rows:
            counts[str(row[0] or "unknown")] += int(row[1] or 0)
    if store._table_exists("llm_attempts"):
        rows = store.con.execute("select status, count(*) from llm_attempts group by status").fetchall()
        for row in rows:
            status = str(row[0] or "unknown")
            counts.setdefault(status, int(row[1] or 0))
    return dict(sorted(counts.items()))


def _profile_status_counts(store: AsipStore) -> Dict[str, int]:
    counts: Counter[str] = Counter()
    if store._table_exists("blackbox_profiles"):
        rows = store.con.execute("select status, count(*) from blackbox_profiles group by status").fetchall()
        for row in rows:
            counts[str(row[0] or "unknown")] += int(row[1] or 0)
    return dict(sorted(counts.items()))


def _latest_manifest_scope(store: AsipStore, usable_profiles: set[tuple[str, str]]) -> Dict[str, Any]:
    if not store._table_exists("blackbox_manifests") or not store._table_exists("blackbox_manifest_candidates"):
        return {}
    latest = store.con.execute(
        """
        select manifest_group_sha256
        from blackbox_manifests
        where manifest_group_sha256 <> ''
        order by id desc
        limit 1
        """
    ).fetchone()
    if latest is None:
        return {}
    manifest_group = str(latest["manifest_group_sha256"] or "")
    manifest_rows = store.con.execute(
        """
        select id, job_id, manifest_sha256, shard_count, shard_index
        from blackbox_manifests
        where manifest_group_sha256 = ?
        order by id asc
        """,
        (manifest_group,),
    ).fetchall()
    manifest_ids = [int(row["id"]) for row in manifest_rows]
    if not manifest_ids:
        return {}
    placeholders = ",".join("?" for _ in manifest_ids)
    candidate_rows = store.con.execute(
        f"""
        select candidate_id, endpoint_id, view, endpoint_kind, coverage_bucket, status
        from blackbox_manifest_candidates
        where manifest_id in ({placeholders})
        order by job_id asc, selection_rank asc, id asc
        """,
        tuple(manifest_ids),
    ).fetchall()
    selected_keys = {
        (str(row["view"] or ""), str(row["endpoint_id"] or ""))
        for row in candidate_rows
        if str(row["view"] or "") and str(row["endpoint_id"] or "")
    }
    covered_keys = selected_keys & usable_profiles
    status_counts: Counter[str] = Counter(str(row["status"] or "unknown") for row in candidate_rows)
    terminal_statuses = {"accepted", "rejected", "failed", "abstained", "skipped"}
    terminal_count = sum(count for status, count in status_counts.items() if status in terminal_statuses)
    selected_candidate_ids = sorted(str(row["candidate_id"] or "") for row in candidate_rows)
    expected_shards = max((int(row["shard_count"] or 1) for row in manifest_rows), default=1)
    observed_shards = sorted({int(row["shard_index"] or 0) for row in manifest_rows})
    selected_count = len(candidate_rows)
    covered_count = len(covered_keys)
    selected_key_count = len(selected_keys)
    return {
        "scope_type": "latest_manifest_group",
        "explicit_not_full_goal": True,
        "manifest_group_sha256": manifest_group,
        "manifest_sha256_values": sorted({str(row["manifest_sha256"] or "") for row in manifest_rows if str(row["manifest_sha256"] or "")}),
        "job_ids": sorted({int(row["job_id"] or 0) for row in manifest_rows if int(row["job_id"] or 0)}),
        "expected_shard_count": expected_shards,
        "observed_shard_count": len(observed_shards),
        "shard_indexes": observed_shards,
        "complete": len(observed_shards) >= expected_shards,
        "selected_candidate_count": selected_count,
        "selected_candidate_ids_sha256": hashlib.sha256("\n".join(selected_candidate_ids).encode("utf-8")).hexdigest()
        if selected_candidate_ids
        else "",
        "terminal_candidate_count": terminal_count,
        "selected_covered_count": covered_count,
        "selected_missing_count": max(0, selected_key_count - covered_count),
        "selected_coverage_ratio": round(covered_count / selected_key_count, 6) if selected_key_count else 0.0,
        "status_counts": dict(sorted(status_counts.items())),
        "by_kind": _candidate_scope_counts(candidate_rows, covered_keys, key_name="endpoint_kind"),
        "by_bucket": _candidate_scope_counts(candidate_rows, covered_keys, key_name="coverage_bucket"),
    }


def _candidate_scope_counts(
    candidates: Iterable[Mapping[str, Any]],
    covered_keys: set[tuple[str, str]],
    *,
    key_name: str,
) -> Dict[str, Dict[str, Any]]:
    totals: Counter[str] = Counter()
    covered: Counter[str] = Counter()
    for candidate in candidates:
        group = str(candidate[key_name] or "unknown")
        key = (str(candidate["view"] or ""), str(candidate["endpoint_id"] or ""))
        totals[group] += 1
        if key in covered_keys:
            covered[group] += 1
    return {
        group: {
            "total": totals[group],
            "covered": covered[group],
            "missing": totals[group] - covered[group],
            "coverage_ratio": round(covered[group] / totals[group], 6) if totals[group] else 0.0,
        }
        for group in sorted(totals)
    }


def _scope_summary(scope: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(scope, Mapping) or not scope:
        return {}
    return {
        "scope_type": scope.get("scope_type"),
        "explicit_not_full_goal": scope.get("explicit_not_full_goal"),
        "manifest_group_sha256": scope.get("manifest_group_sha256"),
        "selected": scope.get("selected_candidate_count"),
        "covered": scope.get("selected_covered_count"),
        "missing": scope.get("selected_missing_count"),
        "coverage_ratio": scope.get("selected_coverage_ratio"),
        "terminal": scope.get("terminal_candidate_count"),
        "complete": scope.get("complete"),
    }


def _coverage_counts(
    inventory: Iterable[Mapping[str, Any]],
    covered_keys: set[tuple[str, str]],
    *,
    key_name: str,
) -> Dict[str, Dict[str, Any]]:
    totals: Counter[str] = Counter()
    covered: Counter[str] = Counter()
    for candidate in inventory:
        group = str(candidate.get(key_name) or "unknown")
        key = (str(candidate.get("view") or ""), str(candidate.get("endpoint_id") or ""))
        totals[group] += 1
        if key in covered_keys:
            covered[group] += 1
    result: Dict[str, Dict[str, Any]] = {}
    for group in sorted(totals):
        total = totals[group]
        count = covered[group]
        result[group] = {
            "total": total,
            "covered": count,
            "missing": total - count,
            "coverage_ratio": round(count / total if total else 0.0, 6),
        }
    return result


def _markdown_summary(payload: Mapping[str, Any]) -> str:
    coverage = payload.get("coverage") if isinstance(payload.get("coverage"), Mapping) else {}
    lines = [
        "# Blackbox Coverage QA",
        "",
        f"- Status: {payload.get('gate_status')}",
        f"- DB: `{payload.get('db_path')}`",
        f"- Coverage: {coverage.get('covered_count', 0)}/{coverage.get('inventory_total', 0)} ({coverage.get('coverage_ratio', 0)})",
        f"- Missing: {coverage.get('missing_count', 0)}",
        f"- Required ratio: {payload.get('min_coverage')}",
        f"- Terminal statuses: `{json.dumps(payload.get('terminal_status_counts') or {}, sort_keys=True)}`",
        f"- Profile statuses: `{json.dumps(payload.get('profile_status_counts') or {}, sort_keys=True)}`",
    ]
    scope = payload.get("latest_manifest_scope") if isinstance(payload.get("latest_manifest_scope"), Mapping) else {}
    if scope:
        lines.extend(
            [
                f"- Latest scope: {scope.get('selected_covered_count', 0)}/{scope.get('selected_candidate_count', 0)} "
                f"({scope.get('selected_coverage_ratio', 0)})",
                f"- Latest scope full-goal substitute: `{not bool(scope.get('explicit_not_full_goal'))}`",
            ]
        )
    lines.extend(["", "## Missing Samples"])
    for sample in payload.get("missing_samples", []) if isinstance(payload.get("missing_samples"), list) else []:
        if isinstance(sample, Mapping):
            lines.append(
                f"- {sample.get('view')} {sample.get('kind')} `{sample.get('endpoint_id')}` "
                f"bucket={sample.get('coverage_bucket')}"
            )
    lines.append("")
    return "\n".join(lines)
