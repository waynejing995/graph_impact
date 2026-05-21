"""Final closure gates that should not silently pass."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def run_residual_acceptance_gate(
    residual_doc: Path,
    *,
    accepted: bool = False,
    accepted_residuals: Optional[List[str]] = None,
    output_json: Optional[Path] = None,
) -> Dict[str, Any]:
    """Record whether G13 residual boundaries have explicit user acceptance."""

    accepted_items = [item for item in (accepted_residuals or []) if item.strip()]
    failure_reasons: List[str] = []
    ledger_items = []
    status_line = ""
    if not residual_doc.exists():
        failure_reasons.append(f"residual document is missing: {residual_doc}")
    else:
        text = residual_doc.read_text(encoding="utf-8")
        status_line = _first_status_line(text)
        ledger_items = _markdown_table_rows(text)
        if "acceptance" not in text.lower():
            failure_reasons.append("residual document does not mention acceptance")
        if not ledger_items:
            failure_reasons.append("residual deferral ledger has no parsed rows")
        if "blocking" in status_line.lower() or "partial" in status_line.lower():
            failure_reasons.append(f"residual document status remains open: {status_line}")

    rows_requiring_acceptance = _rows_requiring_explicit_acceptance(ledger_items)
    if not accepted:
        failure_reasons.append("explicit user acceptance has not been recorded")
    if accepted and not accepted_items:
        failure_reasons.append("accepted_residuals is empty")
    if accepted:
        for row in rows_requiring_acceptance:
            label = _residual_row_label(row)
            if label and not _accepted_residual_matches(label, accepted_items):
                failure_reasons.append(
                    f"residual row needs acceptance but is not listed in accepted_residuals: {label}"
                )

    result: Dict[str, Any] = {
        "source": "asip.residual_acceptance",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "residual_doc_path": str(residual_doc),
        "status_line": status_line,
        "accepted": accepted,
        "accepted_residuals": accepted_items,
        "ledger_items_count": len(ledger_items),
        "ledger_items": ledger_items,
        "acceptance_required_rows": [_residual_row_label(row) for row in rows_requiring_acceptance],
        "gate_status": "pass" if not failure_reasons else "blocked",
        "failure_reasons": failure_reasons,
    }
    _write_json(output_json, result)
    return result


def run_git_gate(repo_root: Path, *, output_json: Optional[Path] = None) -> Dict[str, Any]:
    """Record whether the final diff/commit/push closure gate is satisfied."""

    repo_root = repo_root.resolve()
    diff_check = _run_git(repo_root, ["diff", "--check"])
    status = _run_git(repo_root, ["status", "--porcelain=v1"])
    branch = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    head = _run_git(repo_root, ["rev-parse", "HEAD"])
    upstream = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    ahead_behind = _run_git(repo_root, ["rev-list", "--left-right", "--count", "HEAD...@{u}"])

    status_lines = [line for line in status.stdout.splitlines() if line.strip()] if status.returncode == 0 else []
    ahead = None
    behind = None
    if ahead_behind.returncode == 0:
        parts = ahead_behind.stdout.strip().split()
        if len(parts) == 2:
            ahead = int(parts[0])
            behind = int(parts[1])

    failure_reasons: List[str] = []
    if diff_check.returncode != 0:
        failure_reasons.append("git diff --check failed")
    if status.returncode != 0:
        failure_reasons.append("git status failed")
    elif status_lines:
        failure_reasons.append(f"worktree has {len(status_lines)} changed/untracked paths")
    if upstream.returncode != 0:
        failure_reasons.append("branch has no upstream tracking branch")
    elif ahead is None or behind is None:
        failure_reasons.append("could not compute upstream ahead/behind counts")
    else:
        if ahead != 0:
            failure_reasons.append(f"local branch is {ahead} commit(s) ahead of upstream")
        if behind != 0:
            failure_reasons.append(f"local branch is {behind} commit(s) behind upstream")

    result: Dict[str, Any] = {
        "source": "asip.git_gate",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repo_root": str(repo_root),
        "branch": branch.stdout.strip() if branch.returncode == 0 else "",
        "head": head.stdout.strip() if head.returncode == 0 else "",
        "upstream": upstream.stdout.strip() if upstream.returncode == 0 else "",
        "ahead": ahead,
        "behind": behind,
        "diff_check": "pass" if diff_check.returncode == 0 else "fail",
        "diff_check_output": _combined_output(diff_check),
        "worktree_status": "clean" if status.returncode == 0 and not status_lines else "dirty",
        "changed_paths": status_lines,
        "committed": status.returncode == 0 and not status_lines,
        "pushed": ahead == 0 and behind == 0 if ahead is not None and behind is not None else False,
        "gate_status": "pass" if not failure_reasons else "blocked",
        "failure_reasons": failure_reasons,
    }
    _write_json(output_json, result)
    return result


def _run_git(repo_root: Path, args: List[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _first_status_line(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("Status:"):
            return line.strip()
    return ""


def _markdown_table_rows(text: str) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    in_table = False
    headers: List[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            if in_table:
                break
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not in_table:
            headers = [_slug(cell) for cell in cells]
            in_table = True
            continue
        if all(set(cell) <= {"-", ":", " "} for cell in cells):
            continue
        if len(cells) == len(headers):
            rows.append(dict(zip(headers, cells)))
    return rows


def _slug(value: str) -> str:
    return value.lower().replace(" ", "_").replace("/", "_")


def _rows_requiring_explicit_acceptance(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    markers = (
        "needs acceptance",
        "needing acceptance",
        "requires acceptance",
        "acceptance required",
        "not separately accepted",
        "not accepted",
        "unaccepted",
    )
    result = []
    for row in rows:
        values = " | ".join(str(value).lower() for value in row.values())
        if any(marker in values for marker in markers):
            result.append(row)
    return result


def _residual_row_label(row: Dict[str, str]) -> str:
    if row.get("spec_area"):
        return row["spec_area"]
    for value in row.values():
        if value.strip():
            return value.strip()
    return ""


def _accepted_residual_matches(label: str, accepted_items: List[str]) -> bool:
    accepted_normalized = [_normalize_residual_text(item) for item in accepted_items]
    if any(item in {"*", "all", "all_residuals", "all_residual_boundaries"} for item in accepted_normalized):
        return True
    label_normalized = _normalize_residual_text(label)
    return any(
        item == label_normalized or item in label_normalized or label_normalized in item
        for item in accepted_normalized
        if item
    )


def _normalize_residual_text(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return re.sub(r"_+", "_", normalized)


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    return "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())


def _write_json(path: Optional[Path], payload: Dict[str, Any]) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
