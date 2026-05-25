"""Blackbox residual QA artifact generation."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .blackbox_coverage_qa import _repo_head, _sha256_file, run_blackbox_coverage_qa
from .limits import DEFAULT_WORKBENCH_LIMITS_PATH
from .storage import AsipStore


TERMINAL_STATUSES = {"failed", "rejected", "abstained"}


def run_blackbox_residual_qa(
    db_path: Path,
    *,
    output_json: Optional[Path] = None,
    output_md: Optional[Path] = None,
    residual_limit: int = 50,
) -> Dict[str, Any]:
    coverage = run_blackbox_coverage_qa(db_path, min_coverage=1.0, missing_sample_limit=residual_limit)
    store = AsipStore.connect(str(db_path))
    store.migrate()
    try:
        usable_keys = store.usable_blackbox_profile_keys()
        terminal_samples, terminal_count, terminal_breakdown = _terminal_residuals(
            store,
            usable_keys,
            limit=residual_limit,
        )
    finally:
        store.con.close()

    coverage_summary = coverage.get("coverage") if isinstance(coverage.get("coverage"), Mapping) else {}
    missing_count = int(coverage_summary.get("missing_count") or 0)
    gate_status = "pass" if missing_count == 0 and terminal_count == 0 else "blocked"
    payload: Dict[str, Any] = {
        "source": "asip.blackbox_residual_qa",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_head": _repo_head(Path.cwd()),
        "gate_status": gate_status,
        "db_path": str(db_path),
        "db_sha256": _sha256_file(db_path),
        "limits_config_path": str(DEFAULT_WORKBENCH_LIMITS_PATH),
        "limits_config_sha256": _sha256_file(DEFAULT_WORKBENCH_LIMITS_PATH),
        "coverage": {
            "inventory_total": int(coverage_summary.get("inventory_total") or 0),
            "covered_count": int(coverage_summary.get("covered_count") or 0),
            "missing_count": missing_count,
            "coverage_ratio": coverage_summary.get("coverage_ratio", 0),
        },
        "residuals": {
            "terminal_count": terminal_count,
            "terminal_sample_count": len(terminal_samples),
            "pending_count": max(0, missing_count - terminal_count),
            "terminal_status_counts": terminal_breakdown["status_counts"],
            "failure_gate_counts": terminal_breakdown["gate_counts"],
            "failure_reason_counts": terminal_breakdown["reason_counts"],
            "terminal_samples": terminal_samples,
            "missing_samples": coverage.get("missing_samples", []),
        },
        "summary": {
            "status": gate_status,
            "covered": int(coverage_summary.get("covered_count") or 0),
            "total": int(coverage_summary.get("inventory_total") or 0),
            "missing": missing_count,
            "terminal": terminal_count,
            "pending": max(0, missing_count - terminal_count),
            "terminal_status_counts": terminal_breakdown["status_counts"],
            "top_failure_reasons": terminal_breakdown["top_reasons"],
        },
    }
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if output_md:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(_markdown_summary(payload), encoding="utf-8")
    return payload


def run_blackbox_residual_delta(
    before_json: Path,
    after_json: Path,
    *,
    output_json: Optional[Path] = None,
    output_md: Optional[Path] = None,
    round_number: Optional[int] = None,
    scope: str = "",
) -> Dict[str, Any]:
    before = _load_json_file(before_json)
    after = _load_json_file(after_json)
    before_summary = before.get("summary") if isinstance(before.get("summary"), Mapping) else {}
    after_summary = after.get("summary") if isinstance(after.get("summary"), Mapping) else {}
    before_residuals = before.get("residuals") if isinstance(before.get("residuals"), Mapping) else {}
    after_residuals = after.get("residuals") if isinstance(after.get("residuals"), Mapping) else {}
    before_reasons = _string_int_map(before_residuals.get("failure_reason_counts"))
    after_reasons = _string_int_map(after_residuals.get("failure_reason_counts"))
    reason_deltas = {
        reason: int(after_reasons.get(reason, 0)) - int(before_reasons.get(reason, 0))
        for reason in sorted(set(before_reasons) | set(after_reasons))
    }
    terminal_delta = int(after_summary.get("terminal") or 0) - int(before_summary.get("terminal") or 0)
    pending_delta = int(after_summary.get("pending") or 0) - int(before_summary.get("pending") or 0)
    missing_delta = int(after_summary.get("missing") or 0) - int(before_summary.get("missing") or 0)
    covered_delta = int(after_summary.get("covered") or 0) - int(before_summary.get("covered") or 0)
    if terminal_delta < 0 or missing_delta < 0 or covered_delta > 0:
        status = "improved"
    elif terminal_delta > 0 or missing_delta > 0 or covered_delta < 0:
        status = "regressed"
    else:
        status = "no_change"
    payload: Dict[str, Any] = {
        "source": "asip.blackbox_residual_delta",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "round": round_number,
        "scope": str(scope or ""),
        "before_json": str(before_json),
        "after_json": str(after_json),
        "status": status,
        "before": before_summary,
        "after": after_summary,
        "delta": {
            "covered": covered_delta,
            "missing": missing_delta,
            "pending": pending_delta,
            "terminal": terminal_delta,
            "failure_reasons": reason_deltas,
        },
        "summary": {
            "status": status,
            "covered_delta": covered_delta,
            "missing_delta": missing_delta,
            "pending_delta": pending_delta,
            "terminal_delta": terminal_delta,
            "failure_reason_deltas": reason_deltas,
        },
    }
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if output_md:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(_delta_markdown_summary(payload), encoding="utf-8")
    return payload


def _terminal_residuals(
    store: AsipStore,
    usable_keys: set[tuple[str, str]],
    *,
    limit: int,
) -> tuple[list[Dict[str, Any]], int, Dict[str, Any]]:
    if not store._table_exists("blackbox_manifest_candidates"):
        return [], 0, _terminal_breakdown_from_counters(Counter(), Counter(), Counter())
    rows = store.con.execute(
        """
        select id, job_id, candidate_id, endpoint_id, view, endpoint_kind, coverage_bucket,
          status, metadata_json, candidate_json, updated_at
        from blackbox_manifest_candidates
        where status in ('failed', 'rejected', 'abstained')
        order by id desc
        """
    ).fetchall()
    failures_by_candidate = _latest_validation_failures(store)
    selected: list[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    status_counts: Counter[str] = Counter()
    gate_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    total = 0
    for row in rows:
        key = (str(row["view"] or ""), str(row["endpoint_id"] or ""))
        if key in seen or key in usable_keys:
            continue
        seen.add(key)
        total += 1
        metadata = _load_json_object(row["metadata_json"])
        failure = failures_by_candidate.get(str(row["candidate_id"] or ""), {})
        _add_terminal_breakdown(
            status_counts,
            gate_counts,
            reason_counts,
            status=str(row["status"] or ""),
            failure=failure,
            reason_codes=metadata.get("reason_codes", []),
        )
        if len(selected) >= max(0, int(limit)):
            continue
        candidate_json = _load_json_object(row["candidate_json"])
        selected.append(
            {
                "job_id": int(row["job_id"] or 0),
                "candidate_id": str(row["candidate_id"] or ""),
                "endpoint_id": str(row["endpoint_id"] or ""),
                "view": str(row["view"] or ""),
                "kind": str(row["endpoint_kind"] or ""),
                "coverage_bucket": str(row["coverage_bucket"] or ""),
                "status": str(row["status"] or ""),
                "reason_codes": metadata.get("reason_codes", []),
                "validator_status": metadata.get("validator_status", ""),
                "failure": failure,
                "neighbor_count": len(candidate_json.get("neighbors") if isinstance(candidate_json.get("neighbors"), list) else []),
                "updated_at": str(row["updated_at"] or ""),
            }
        )
    return selected, total, _terminal_breakdown_from_counters(status_counts, gate_counts, reason_counts)


def _add_terminal_breakdown(
    status_counts: Counter[str],
    gate_counts: Counter[str],
    reason_counts: Counter[str],
    *,
    status: str,
    failure: Mapping[str, Any],
    reason_codes: object,
) -> None:
    status_counts[str(status or "unknown")] += 1
    gate = str(failure.get("gate") or "unknown")
    reason = str(failure.get("reason_code") or "")
    if gate:
        gate_counts[gate] += 1
    if reason:
        reason_counts[reason] += 1
        return
    for item in reason_codes if isinstance(reason_codes, list) else []:
        text = str(item or "").strip()
        if text:
            reason_counts[text] += 1


def _terminal_breakdown_from_counters(
    status_counts: Counter[str],
    gate_counts: Counter[str],
    reason_counts: Counter[str],
) -> Dict[str, Any]:
    return {
        "status_counts": dict(sorted(status_counts.items())),
        "gate_counts": dict(sorted(gate_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "top_reasons": [
            {"reason_code": reason, "count": count}
            for reason, count in reason_counts.most_common(10)
        ],
    }


def _latest_validation_failures(store: AsipStore) -> Dict[str, Dict[str, Any]]:
    if not store._table_exists("blackbox_validation_failures"):
        return {}
    rows = store.con.execute(
        """
        select candidate_id, gate, reason_code, detail_json, created_at
        from blackbox_validation_failures
        order by id desc
        """
    ).fetchall()
    failures: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        candidate_id = str(row["candidate_id"] or "")
        if not candidate_id or candidate_id in failures:
            continue
        failures[candidate_id] = {
            "gate": str(row["gate"] or ""),
            "reason_code": str(row["reason_code"] or ""),
            "detail": _load_json_object(row["detail_json"]),
            "created_at": str(row["created_at"] or ""),
        }
    return failures


def _load_json_object(value: Any) -> Dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)
    try:
        decoded = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return dict(decoded) if isinstance(decoded, Mapping) else {}


def _load_json_file(path: Path) -> Dict[str, Any]:
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(decoded) if isinstance(decoded, Mapping) else {}


def _string_int_map(value: Any) -> Dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    result: Dict[str, int] = {}
    for key, raw_count in value.items():
        try:
            result[str(key)] = int(raw_count or 0)
        except (TypeError, ValueError):
            result[str(key)] = 0
    return result


def _markdown_summary(payload: Mapping[str, Any]) -> str:
    coverage = payload.get("coverage") if isinstance(payload.get("coverage"), Mapping) else {}
    residuals = payload.get("residuals") if isinstance(payload.get("residuals"), Mapping) else {}
    lines = [
        "# Blackbox Residual QA",
        "",
        f"- Status: {payload.get('gate_status')}",
        f"- DB: `{payload.get('db_path')}`",
        f"- Coverage: {coverage.get('covered_count', 0)}/{coverage.get('inventory_total', 0)} ({coverage.get('coverage_ratio', 0)})",
        f"- Missing: {coverage.get('missing_count', 0)}",
        f"- Pending: {residuals.get('pending_count', 0)}",
        f"- Terminal: {residuals.get('terminal_count', 0)}",
        f"- Terminal samples: {residuals.get('terminal_sample_count', 0)}",
        "",
        "## Terminal Breakdown",
        "",
        f"- Status counts: `{json.dumps(residuals.get('terminal_status_counts', {}), sort_keys=True)}`",
        f"- Failure gates: `{json.dumps(residuals.get('failure_gate_counts', {}), sort_keys=True)}`",
        f"- Failure reasons: `{json.dumps(residuals.get('failure_reason_counts', {}), sort_keys=True)}`",
        "",
        "## Terminal Samples",
    ]
    for sample in residuals.get("terminal_samples", []) if isinstance(residuals.get("terminal_samples"), list) else []:
        if not isinstance(sample, Mapping):
            continue
        failure = sample.get("failure") if isinstance(sample.get("failure"), Mapping) else {}
        lines.append(
            f"- {sample.get('status')} `{sample.get('endpoint_id')}` "
            f"reason={failure.get('reason_code') or sample.get('reason_codes')}"
        )
    lines.append("")
    return "\n".join(lines)


def _delta_markdown_summary(payload: Mapping[str, Any]) -> str:
    summary = payload.get("summary") if isinstance(payload.get("summary"), Mapping) else {}
    lines = [
        "# Blackbox Terminal Warmup Delta",
        "",
        f"- Status: {payload.get('status')}",
        f"- Round: {payload.get('round')}",
        f"- Scope: `{payload.get('scope')}`",
        f"- Covered delta: {summary.get('covered_delta', 0)}",
        f"- Missing delta: {summary.get('missing_delta', 0)}",
        f"- Pending delta: {summary.get('pending_delta', 0)}",
        f"- Terminal delta: {summary.get('terminal_delta', 0)}",
        f"- Failure reason deltas: `{json.dumps(summary.get('failure_reason_deltas', {}), sort_keys=True)}`",
        "",
    ]
    return "\n".join(lines)
