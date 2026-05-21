"""Summarize the current ASIP goal closure state from gate artifacts."""

from __future__ import annotations

import glob
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional


_HOSTED_ID = "hosted_openai_compatible"
_RESIDUAL_ID = "residual_acceptance"


def run_goal_status(
    *,
    repo_root: Path,
    completion_json: Optional[Path] = None,
    latest_glob: str = "/tmp/asip-postpush-gate-*/completion-gate.json",
    output_json: Optional[Path] = None,
) -> Dict[str, Any]:
    """Read the latest completion gate and explain whether the active goal is closed."""

    repo_root = repo_root.resolve()
    current_git = _current_git_state(repo_root)
    artifact_path = completion_json or _latest_completion_gate(latest_glob)
    failure_reasons: List[str] = []
    completion_payload: Dict[str, Any] = {}
    if artifact_path is None:
        failure_reasons.append(f"no completion-gate artifact matched {latest_glob}")
    elif not artifact_path.exists():
        failure_reasons.append(f"completion-gate artifact is missing: {artifact_path}")
    else:
        try:
            completion_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failure_reasons.append(f"completion-gate artifact is invalid JSON: {exc}")

    requirements = {
        str(item.get("id")): item
        for item in completion_payload.get("requirements", [])
        if isinstance(item, dict) and item.get("id")
    }
    nonpass_requirements = [
        _requirement_summary(item_id, item)
        for item_id, item in sorted(requirements.items())
        if item.get("status") != "pass"
    ]
    blockers = [item for item in nonpass_requirements if item.get("status") == "blocked"]
    missing = [item for item in nonpass_requirements if item.get("status") == "missing"]
    failed = [item for item in nonpass_requirements if item.get("status") == "fail"]

    git_gate_payload = _load_git_gate_payload(completion_payload)
    artifact_head = str(git_gate_payload.get("head") or "")
    current_head = current_git.get("head", "")
    artifact_matches_current_head = bool(artifact_head and current_head and artifact_head == current_head)
    if artifact_path and completion_payload and not artifact_matches_current_head:
        failure_reasons.append(
            f"completion artifact head {artifact_head or 'missing'} does not match current head {current_head or 'missing'}"
        )
    if current_git.get("worktree_status") != "clean":
        failure_reasons.append(f"current worktree is {current_git.get('worktree_status')}")
    if current_git.get("ahead") not in (None, 0):
        failure_reasons.append(f"current branch is {current_git.get('ahead')} commit(s) ahead of upstream")
    if current_git.get("behind") not in (None, 0):
        failure_reasons.append(f"current branch is {current_git.get('behind')} commit(s) behind upstream")

    completion_gate_status = str(completion_payload.get("gate_status") or "missing")
    if completion_gate_status != "pass":
        failure_reasons.append(f"completion gate status is {completion_gate_status}")
    if missing:
        failure_reasons.append(f"completion gate has {len(missing)} missing requirement(s)")
    if failed:
        failure_reasons.append(f"completion gate has {len(failed)} failed requirement(s)")
    if blockers:
        failure_reasons.append(f"completion gate has {len(blockers)} blocked requirement(s)")

    goal_status = "pass" if not failure_reasons else "blocked"
    result: Dict[str, Any] = {
        "source": "asip.goal_status",
        "repo_root": str(repo_root),
        "current_git": current_git,
        "completion_artifact": str(artifact_path) if artifact_path else "",
        "completion_generated_at": completion_payload.get("generated_at", ""),
        "completion_gate_status": completion_gate_status,
        "completion_summary": completion_payload.get("summary", {}),
        "artifact_head": artifact_head,
        "artifact_branch": git_gate_payload.get("branch", ""),
        "artifact_matches_current_head": artifact_matches_current_head,
        "nonpass_requirements": nonpass_requirements,
        "blockers": blockers,
        "next_actions": _next_actions(requirements),
        "goal_status": goal_status,
        "failure_reasons": failure_reasons,
    }
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _latest_completion_gate(pattern: str) -> Optional[Path]:
    paths = [Path(path) for path in glob.glob(pattern)]
    if not paths:
        return None
    return max(paths, key=lambda path: path.stat().st_mtime)


def _current_git_state(repo_root: Path) -> Dict[str, Any]:
    head = _run_git(repo_root, ["rev-parse", "HEAD"])
    branch = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    status = _run_git(repo_root, ["status", "--porcelain=v1"])
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

    return {
        "head": head.stdout.strip() if head.returncode == 0 else "",
        "branch": branch.stdout.strip() if branch.returncode == 0 else "",
        "upstream": upstream.stdout.strip() if upstream.returncode == 0 else "",
        "ahead": ahead,
        "behind": behind,
        "worktree_status": "clean" if status.returncode == 0 and not status_lines else "dirty",
        "changed_paths": status_lines,
    }


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


def _load_git_gate_payload(completion_payload: Dict[str, Any]) -> Dict[str, Any]:
    git_record = completion_payload.get("artifacts", {}).get("git_gate", {})
    path = git_record.get("path") if isinstance(git_record, dict) else ""
    if not path:
        return {}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _requirement_summary(item_id: str, item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": item_id,
        "title": item.get("title", ""),
        "status": item.get("status", ""),
        "evidence": item.get("evidence", ""),
        "failure_reasons": item.get("failure_reasons", []),
    }


def _next_actions(requirements: Dict[str, Dict[str, Any]]) -> List[Dict[str, str]]:
    actions: List[Dict[str, str]] = []
    hosted = requirements.get(_HOSTED_ID, {})
    if hosted.get("status") != "pass":
        actions.append(
            {
                "id": _HOSTED_ID,
                "action": "Set a hosted OpenAI-compatible credential, then rerun pnpm gate:postpush.",
                "command": (
                    "OPENAI_API_KEY=... "
                    "ASIP_HOSTED_OPENAI_BASE_URL=https://api.openai.com "
                    "pnpm gate:postpush"
                ),
            }
        )
    residual = requirements.get(_RESIDUAL_ID, {})
    if residual.get("status") != "pass":
        actions.append(
            {
                "id": _RESIDUAL_ID,
                "action": "Record explicit G13 residual-boundary acceptance, then rerun pnpm gate:postpush.",
                "command": (
                    "python3 -m asip.cli residual-gate --accepted "
                    "--accepted-residual 'Hybrid retrieval over exact, resolver, FTS5, vector, graph, rerank' "
                    "--accepted-residual 'Embedding provider and optional semantic-edge provider via Ollama/OpenAI-compatible APIs'"
                ),
            }
        )
    return actions
