#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

export PYTHONDONTWRITEBYTECODE="${PYTHONDONTWRITEBYTECODE:-1}"
export PYTHONPATH="packages/core/src:${PYTHONPATH:-.}"

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
db_path="${ASIP_BLACKBOX_DB_PATH:-data/asip.db}"
out_dir="${ASIP_BLACKBOX_OUT_DIR:-/tmp/asip-blackbox-full-generation-${timestamp}}"
phase="${ASIP_BLACKBOX_PHASE:-full-generation-${timestamp}}"
selection_seed="${ASIP_BLACKBOX_SELECTION_SEED:-${phase}}"
shard_count="${ASIP_BLACKBOX_SHARDS:-8}"
limit_per_shard="${ASIP_BLACKBOX_LIMIT_PER_SHARD:-8}"
batch_size="${ASIP_BLACKBOX_BATCH_SIZE:-1}"
sample_count="${ASIP_BLACKBOX_SAMPLE_COUNT:-3}"
retry_count="${ASIP_BLACKBOX_RETRY_COUNT:-3}"
retry_limit_per_shard="${ASIP_BLACKBOX_RETRY_LIMIT_PER_SHARD:-$limit_per_shard}"
retry_batch_size="${ASIP_BLACKBOX_RETRY_BATCH_SIZE:-$batch_size}"
retry_sample_count="${ASIP_BLACKBOX_RETRY_SAMPLE_COUNT:-5}"
retry_retry_count="${ASIP_BLACKBOX_RETRY_RETRY_COUNT:-$retry_count}"
ramp_enabled="${ASIP_BLACKBOX_RAMP:-1}"
ramp_after_progress_rounds="${ASIP_BLACKBOX_RAMP_AFTER_PROGRESS_ROUNDS:-1}"
ramp_shard_count="${ASIP_BLACKBOX_RAMP_SHARDS:-16}"
ramp_limit_per_shard="${ASIP_BLACKBOX_RAMP_LIMIT_PER_SHARD:-16}"
max_rounds="${ASIP_BLACKBOX_MAX_ROUNDS:-0}"
max_no_progress_rounds="${ASIP_BLACKBOX_MAX_NO_PROGRESS_ROUNDS:-3}"
primary_scope="${ASIP_BLACKBOX_PRIMARY_SCOPE:-pending}"
retry_scope="${ASIP_BLACKBOX_RETRY_SCOPE:-retry-terminal}"
retry_consensus_scope="${ASIP_BLACKBOX_RETRY_CONSENSUS_SCOPE:-retry-terminal-consensus}"
retry_parse_scope="${ASIP_BLACKBOX_RETRY_PARSE_SCOPE:-retry-terminal-parse}"
terminal_warmup_rounds="${ASIP_BLACKBOX_TERMINAL_WARMUP_ROUNDS:-2}"
adaptive_retry_enabled="${ASIP_BLACKBOX_ADAPTIVE_RETRY:-1}"
adaptive_failure_ratio_percent="${ASIP_BLACKBOX_ADAPTIVE_FAILURE_RATIO_PERCENT:-80}"
adaptive_min_candidates="${ASIP_BLACKBOX_ADAPTIVE_MIN_CANDIDATES:-8}"
adaptive_retry_scope="${ASIP_BLACKBOX_ADAPTIVE_RETRY_SCOPE:-$retry_parse_scope}"
adaptive_retry_batch_size="${ASIP_BLACKBOX_ADAPTIVE_RETRY_BATCH_SIZE:-1}"
adaptive_retry_sample_count="${ASIP_BLACKBOX_ADAPTIVE_RETRY_SAMPLE_COUNT:-$retry_sample_count}"
adaptive_retry_retry_count="${ASIP_BLACKBOX_ADAPTIVE_RETRY_RETRY_COUNT:-$retry_retry_count}"
skip_smoke="${ASIP_BLACKBOX_SKIP_SMOKE:-0}"
run_postpush="${ASIP_BLACKBOX_RUN_POSTPUSH:-1}"
require_clean_worktree="${ASIP_BLACKBOX_REQUIRE_CLEAN_WORKTREE:-1}"

mkdir -p "$out_dir"

echo "[blackbox-full] db: $db_path"
echo "[blackbox-full] out: $out_dir"
echo "[blackbox-full] phase: $phase"
echo "[blackbox-full] seed: $selection_seed"
echo "[blackbox-full] shards: $shard_count"
echo "[blackbox-full] limit per shard: $limit_per_shard"
echo "[blackbox-full] batch size: $batch_size"
echo "[blackbox-full] sample/retry: ${sample_count}/${retry_count}"
echo "[blackbox-full] retry limit per shard: $retry_limit_per_shard"
echo "[blackbox-full] retry batch size: $retry_batch_size"
echo "[blackbox-full] retry sample/retry: ${retry_sample_count}/${retry_retry_count}"
echo "[blackbox-full] ramp: enabled=${ramp_enabled} after_progress_rounds=${ramp_after_progress_rounds} shards=${ramp_shard_count} limit=${ramp_limit_per_shard}"
echo "[blackbox-full] max no-progress rounds: $max_no_progress_rounds"
echo "[blackbox-full] scopes: primary=${primary_scope}, retry=${retry_scope}"
echo "[blackbox-full] retry sub-scopes: consensus=${retry_consensus_scope}, parse=${retry_parse_scope}"
echo "[blackbox-full] terminal warmup rounds: $terminal_warmup_rounds"
echo "[blackbox-full] adaptive retry: enabled=${adaptive_retry_enabled} scope=${adaptive_retry_scope} min_candidates=${adaptive_min_candidates} failure_ratio_percent=${adaptive_failure_ratio_percent} batch=${adaptive_retry_batch_size} sample/retry=${adaptive_retry_sample_count}/${adaptive_retry_retry_count}"
echo "[blackbox-full] require clean worktree: $require_clean_worktree"

coverage_json="$out_dir/blackbox-coverage-latest.json"
ledger_json="$out_dir/blackbox-ledger-latest.json"
ledger_md="$out_dir/blackbox-ledger-latest.md"
residual_json="$out_dir/blackbox-residual-latest.json"
residual_md="$out_dir/blackbox-residual-latest.md"
provider_gate_json="$out_dir/blackbox-provider-gate.json"
provider_gate_md="$out_dir/blackbox-provider-gate.md"
preflight_json="$out_dir/blackbox-full-preflight.json"
preflight_md="$out_dir/blackbox-full-preflight.md"
full_generation_json="$out_dir/blackbox-full-generation-run.json"
full_generation_md="$out_dir/blackbox-full-generation-run.md"

json_field() {
  python3 - "$1" "$2" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
cursor = payload
for part in sys.argv[2].split("."):
    cursor = cursor.get(part, {}) if isinstance(cursor, dict) else {}
print(cursor if cursor not in ({}, None) else "")
PY
}

write_coverage() {
  local output_json="$1"
  local output_md="${output_json%.json}.md"
  python3 -m asip.cli blackbox-coverage-qa \
    --db "$db_path" \
    --min-coverage 1.0 \
    --output-json "$output_json" \
    --output-md "$output_md" \
    --full >/dev/null
}

write_ledger() {
  python3 -m asip.cli blackbox-ledger-qa \
    --db "$db_path" \
    --output-json "$ledger_json" \
    --output-md "$ledger_md" \
    --full >/dev/null
}

write_residual() {
  python3 -m asip.cli blackbox-residual-qa \
    --db "$db_path" \
    --output-json "$residual_json" \
    --output-md "$residual_md" \
    --full >/dev/null
}

write_residual_to() {
  local output_json="$1"
  local output_md="${output_json%.json}.md"
  python3 -m asip.cli blackbox-residual-qa \
    --db "$db_path" \
    --output-json "$output_json" \
    --output-md "$output_md" \
    --full >/dev/null
}

write_current_qa_artifacts() {
  write_ledger
  write_coverage "$coverage_json"
  write_residual
  echo "[blackbox-full] ledger json: $ledger_json"
  echo "[blackbox-full] coverage json: $coverage_json"
  echo "[blackbox-full] residual json: $residual_json"
}

write_run_artifact() {
  local gate_status="$1"
  local failure_stage="$2"
  python3 - "$db_path" "$out_dir" "$phase" "$selection_seed" "$gate_status" "$failure_stage" "$full_generation_json" "$full_generation_md" \
    "$preflight_json" "$provider_gate_json" "$ledger_json" "$coverage_json" "$residual_json" <<'PY'
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

db_path = Path(sys.argv[1])
out_dir = Path(sys.argv[2])
phase = sys.argv[3]
selection_seed = sys.argv[4]
gate_status = sys.argv[5]
failure_stage = sys.argv[6]
output_json = Path(sys.argv[7])
output_md = Path(sys.argv[8])
artifact_paths = {
    "blackbox_full_generation_preflight": Path(sys.argv[9]),
    "blackbox_provider_gate": Path(sys.argv[10]),
    "blackbox_ledger_qa": Path(sys.argv[11]),
    "blackbox_coverage_qa": Path(sys.argv[12]),
    "blackbox_residual_qa": Path(sys.argv[13]),
}

def sha256_file(path: Path) -> str:
    try:
        digest = hashlib.sha256()
        with path.expanduser().resolve().open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return ""

def git_output(args):
    try:
        return subprocess.check_output(["git", *args], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""

def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

artifacts = {}
for name, path in artifact_paths.items():
    payload = load_json(path)
    artifacts[name] = {
        "path": str(path),
        "sha256": sha256_file(path),
        "source": payload.get("source", ""),
        "gate_status": payload.get("gate_status", payload.get("summary", {}).get("status", "")),
    }

payload = {
    "source": "asip.blackbox_full_generation_run",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "repo_head": git_output(["rev-parse", "HEAD"]),
    "db_path": str(db_path),
    "db_sha256": sha256_file(db_path),
    "out_dir": str(out_dir),
    "phase": phase,
    "selection_seed": selection_seed,
    "gate_status": gate_status,
    "failure_stage": failure_stage,
    "artifacts": artifacts,
    "summary": {
        "status": gate_status,
        "failure_stage": failure_stage,
        "coverage": load_json(artifact_paths["blackbox_coverage_qa"]).get("summary", {}),
        "residual": load_json(artifact_paths["blackbox_residual_qa"]).get("summary", {}),
        "provider": load_json(artifact_paths["blackbox_provider_gate"]).get("summary", {}),
    },
}
output_json.parent.mkdir(parents=True, exist_ok=True)
output_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
lines = [
    "# Blackbox Full Generation Run",
    "",
    f"- Status: {gate_status}",
    f"- Failure stage: `{failure_stage}`",
    f"- DB: `{db_path}`",
    f"- DB sha256: `{payload['db_sha256']}`",
    f"- Provider gate: `{artifacts['blackbox_provider_gate']['gate_status']}`",
    f"- Coverage gate: `{artifacts['blackbox_coverage_qa']['gate_status']}`",
    f"- Residual gate: `{artifacts['blackbox_residual_qa']['gate_status']}`",
    "",
]
output_md.write_text("\n".join(lines), encoding="utf-8")
PY
}

write_preflight_checklist() {
  local selection_json="$1"
  ASIP_PREFLIGHT_SHARD_COUNT="$shard_count" \
  ASIP_PREFLIGHT_LIMIT_PER_SHARD="$limit_per_shard" \
  ASIP_PREFLIGHT_BATCH_SIZE="$batch_size" \
  ASIP_PREFLIGHT_SAMPLE_COUNT="$sample_count" \
  ASIP_PREFLIGHT_RETRY_COUNT="$retry_count" \
  ASIP_PREFLIGHT_RETRY_LIMIT_PER_SHARD="$retry_limit_per_shard" \
  ASIP_PREFLIGHT_RETRY_BATCH_SIZE="$retry_batch_size" \
  ASIP_PREFLIGHT_RETRY_SAMPLE_COUNT="$retry_sample_count" \
  ASIP_PREFLIGHT_RETRY_RETRY_COUNT="$retry_retry_count" \
  ASIP_PREFLIGHT_RAMP_ENABLED="$ramp_enabled" \
  ASIP_PREFLIGHT_RAMP_AFTER_PROGRESS_ROUNDS="$ramp_after_progress_rounds" \
  ASIP_PREFLIGHT_RAMP_SHARD_COUNT="$ramp_shard_count" \
  ASIP_PREFLIGHT_RAMP_LIMIT_PER_SHARD="$ramp_limit_per_shard" \
  ASIP_PREFLIGHT_MAX_ROUNDS="$max_rounds" \
  ASIP_PREFLIGHT_MAX_NO_PROGRESS_ROUNDS="$max_no_progress_rounds" \
  ASIP_PREFLIGHT_PRIMARY_SCOPE="$primary_scope" \
  ASIP_PREFLIGHT_RETRY_SCOPE="$retry_scope" \
  ASIP_PREFLIGHT_RETRY_CONSENSUS_SCOPE="$retry_consensus_scope" \
  ASIP_PREFLIGHT_RETRY_PARSE_SCOPE="$retry_parse_scope" \
  ASIP_PREFLIGHT_TERMINAL_WARMUP_ROUNDS="$terminal_warmup_rounds" \
  ASIP_PREFLIGHT_ADAPTIVE_RETRY_ENABLED="$adaptive_retry_enabled" \
  ASIP_PREFLIGHT_ADAPTIVE_FAILURE_RATIO_PERCENT="$adaptive_failure_ratio_percent" \
  ASIP_PREFLIGHT_ADAPTIVE_MIN_CANDIDATES="$adaptive_min_candidates" \
  ASIP_PREFLIGHT_ADAPTIVE_RETRY_SCOPE="$adaptive_retry_scope" \
  ASIP_PREFLIGHT_ADAPTIVE_RETRY_BATCH_SIZE="$adaptive_retry_batch_size" \
  ASIP_PREFLIGHT_ADAPTIVE_RETRY_SAMPLE_COUNT="$adaptive_retry_sample_count" \
  ASIP_PREFLIGHT_ADAPTIVE_RETRY_RETRY_COUNT="$adaptive_retry_retry_count" \
  ASIP_PREFLIGHT_SKIP_SMOKE="$skip_smoke" \
  ASIP_PREFLIGHT_RUN_POSTPUSH="$run_postpush" \
  ASIP_PREFLIGHT_REQUIRE_CLEAN_WORKTREE="$require_clean_worktree" \
  python3 - "$db_path" "$out_dir" "$phase" "$selection_seed" "$selection_json" "$preflight_json" "$preflight_md" <<'PY'
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from asip.blackbox_coverage_qa import run_blackbox_coverage_qa
from asip.blackbox_residual_qa import run_blackbox_residual_qa
from asip.workbench import load_provider_settings

db_path = Path(sys.argv[1])
out_dir = Path(sys.argv[2])
phase = sys.argv[3]
selection_seed = sys.argv[4]
selection_json = Path(sys.argv[5])
output_json = Path(sys.argv[6])
output_md = Path(sys.argv[7])

def sha256_file(path):
    try:
        digest = hashlib.sha256()
        with path.expanduser().resolve().open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return ""

def git_output(args):
    try:
        return subprocess.check_output(["git", *args], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""

def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

git_status_lines = [line for line in git_output(["status", "--porcelain"]).splitlines() if line]
coverage = run_blackbox_coverage_qa(db_path, min_coverage=1.0, missing_sample_limit=5)
residual = run_blackbox_residual_qa(db_path, residual_limit=5)
selection = load_json(selection_json)
provider_settings = load_provider_settings(db_path)
def env_int(name):
    try:
        return int(os.environ.get(name, "0"))
    except ValueError:
        return 0

payload = {
    "source": "asip.blackbox_full_generation_preflight",
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "repo_head": git_output(["rev-parse", "HEAD"]),
    "git_dirty": bool(git_status_lines),
    "git_status_count": len(git_status_lines),
    "git_status_samples": git_status_lines[:25],
    "db_path": str(db_path),
    "db_sha256": sha256_file(db_path),
    "out_dir": str(out_dir),
    "phase": phase,
    "selection_seed": selection_seed,
    "provider_settings": provider_settings,
    "runner": {
        "shard_count": env_int("ASIP_PREFLIGHT_SHARD_COUNT"),
        "limit_per_shard": env_int("ASIP_PREFLIGHT_LIMIT_PER_SHARD"),
        "batch_size": env_int("ASIP_PREFLIGHT_BATCH_SIZE"),
        "sample_count": env_int("ASIP_PREFLIGHT_SAMPLE_COUNT"),
        "retry_count": env_int("ASIP_PREFLIGHT_RETRY_COUNT"),
        "retry_limit_per_shard": env_int("ASIP_PREFLIGHT_RETRY_LIMIT_PER_SHARD"),
        "retry_batch_size": env_int("ASIP_PREFLIGHT_RETRY_BATCH_SIZE"),
        "retry_sample_count": env_int("ASIP_PREFLIGHT_RETRY_SAMPLE_COUNT"),
        "retry_retry_count": env_int("ASIP_PREFLIGHT_RETRY_RETRY_COUNT"),
        "ramp_enabled": os.environ.get("ASIP_PREFLIGHT_RAMP_ENABLED") == "1",
        "ramp_after_progress_rounds": env_int("ASIP_PREFLIGHT_RAMP_AFTER_PROGRESS_ROUNDS"),
        "ramp_shard_count": env_int("ASIP_PREFLIGHT_RAMP_SHARD_COUNT"),
        "ramp_limit_per_shard": env_int("ASIP_PREFLIGHT_RAMP_LIMIT_PER_SHARD"),
        "max_rounds": env_int("ASIP_PREFLIGHT_MAX_ROUNDS"),
        "max_no_progress_rounds": env_int("ASIP_PREFLIGHT_MAX_NO_PROGRESS_ROUNDS"),
        "primary_scope": os.environ.get("ASIP_PREFLIGHT_PRIMARY_SCOPE", ""),
        "retry_scope": os.environ.get("ASIP_PREFLIGHT_RETRY_SCOPE", ""),
        "retry_consensus_scope": os.environ.get("ASIP_PREFLIGHT_RETRY_CONSENSUS_SCOPE", ""),
        "retry_parse_scope": os.environ.get("ASIP_PREFLIGHT_RETRY_PARSE_SCOPE", ""),
        "terminal_warmup_rounds": env_int("ASIP_PREFLIGHT_TERMINAL_WARMUP_ROUNDS"),
        "adaptive_retry_enabled": os.environ.get("ASIP_PREFLIGHT_ADAPTIVE_RETRY_ENABLED") == "1",
        "adaptive_failure_ratio_percent": env_int("ASIP_PREFLIGHT_ADAPTIVE_FAILURE_RATIO_PERCENT"),
        "adaptive_min_candidates": env_int("ASIP_PREFLIGHT_ADAPTIVE_MIN_CANDIDATES"),
        "adaptive_retry_scope": os.environ.get("ASIP_PREFLIGHT_ADAPTIVE_RETRY_SCOPE", ""),
        "adaptive_retry_batch_size": env_int("ASIP_PREFLIGHT_ADAPTIVE_RETRY_BATCH_SIZE"),
        "adaptive_retry_sample_count": env_int("ASIP_PREFLIGHT_ADAPTIVE_RETRY_SAMPLE_COUNT"),
        "adaptive_retry_retry_count": env_int("ASIP_PREFLIGHT_ADAPTIVE_RETRY_RETRY_COUNT"),
        "skip_smoke": os.environ.get("ASIP_PREFLIGHT_SKIP_SMOKE") == "1",
        "run_postpush": os.environ.get("ASIP_PREFLIGHT_RUN_POSTPUSH") == "1",
        "require_clean_worktree": os.environ.get("ASIP_PREFLIGHT_REQUIRE_CLEAN_WORKTREE") == "1",
    },
    "selection_preflight": {
        "candidate_count": selection.get("candidate_count"),
        "candidate_scope": selection.get("candidate_scope"),
        "selection_inventory_total": selection.get("selection_inventory_total"),
        "profiled_inventory_total": selection.get("profiled_inventory_total"),
        "terminal_inventory_total": selection.get("terminal_inventory_total"),
        "selection_manifest": {
            key: value
            for key, value in (selection.get("selection_manifest") or {}).items()
            if key != "candidates"
        },
    },
    "coverage_summary": coverage.get("summary", {}),
    "residual_summary": residual.get("summary", {}),
}
payload["summary"] = {
    "status": (
        "blocked"
        if payload["coverage_summary"].get("status") != "pass" or payload["residual_summary"].get("status") != "pass"
        else "pass"
    ),
    "git_dirty": payload["git_dirty"],
    "db_sha256": payload["db_sha256"],
    "candidate_count": payload["selection_preflight"].get("candidate_count"),
    "coverage": payload["coverage_summary"],
    "residual": payload["residual_summary"],
}
failure_reasons = []
if payload["coverage_summary"].get("status") != "pass":
    failure_reasons.append(f"coverage status is {payload['coverage_summary'].get('status')}")
if payload["residual_summary"].get("status") != "pass":
    failure_reasons.append(f"residual status is {payload['residual_summary'].get('status')}")
if payload["git_dirty"] and payload["runner"]["require_clean_worktree"]:
    failure_reasons.append("worktree is dirty and clean worktree is required")
payload["gate_status"] = payload["summary"]["status"]
payload["failure_reasons"] = failure_reasons
output_json.parent.mkdir(parents=True, exist_ok=True)
output_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
lines = [
    "# Blackbox Full Generation Preflight",
    "",
    f"- Status: {payload['summary']['status']}",
    f"- DB: `{payload['db_path']}`",
    f"- DB sha256: `{payload['db_sha256']}`",
    f"- Git dirty: `{payload['git_dirty']}` ({payload['git_status_count']} entries)",
    f"- Provider: `{(provider_settings.get('edge') or {}).get('provider', '')}`",
    f"- Model: `{(provider_settings.get('edge') or {}).get('model', '')}`",
    f"- Candidate count: {payload['selection_preflight'].get('candidate_count')}",
    f"- Coverage: {payload['coverage_summary'].get('covered')}/{payload['coverage_summary'].get('total')}",
    f"- Missing: {payload['coverage_summary'].get('missing')}",
    f"- Residual pending: {payload['residual_summary'].get('pending')}",
    f"- Residual terminal: {payload['residual_summary'].get('terminal')}",
    f"- Runner primary: {payload['runner']['primary_scope']} {payload['runner']['shard_count']}x{payload['runner']['limit_per_shard']}",
    f"- Runner batch size: {payload['runner']['batch_size']}",
    f"- Runner retry batch size: {payload['runner']['retry_batch_size']}",
    f"- Adaptive retry: {payload['runner']['adaptive_retry_enabled']} {payload['runner']['adaptive_retry_scope']}",
    f"- Runner ramp: {payload['runner']['ramp_enabled']} -> {payload['runner']['ramp_shard_count']}x{payload['runner']['ramp_limit_per_shard']}",
    f"- Require clean worktree: {payload['runner']['require_clean_worktree']}",
    "",
]
output_md.write_text("\\n".join(lines), encoding="utf-8")
PY
}

echo "[blackbox-full] provider/inventory preflight"
python3 -m asip.cli blackbox-profiles-batch \
  --db "$db_path" \
  --limit 1 \
  --candidate-scope "$primary_scope" \
  --dry-run-selection \
  --summary-only \
  --output-json "$out_dir/preflight-selection.json" >/dev/null
write_preflight_checklist "$out_dir/preflight-selection.json"
echo "[blackbox-full] preflight json: $preflight_json"
echo "[blackbox-full] preflight md: $preflight_md"

echo "[blackbox-full] blackbox provider gate"
if ! python3 -m asip.cli blackbox-provider-gate \
    --db "$db_path" \
    --output-json "$provider_gate_json" \
    --output-md "$provider_gate_md" \
    --require-pass \
    --full >/dev/null; then
  write_current_qa_artifacts
  write_run_artifact "blocked" "provider_gate"
  echo "[blackbox-full] run json: $full_generation_json"
  echo "[blackbox-full] run md: $full_generation_md"
  echo "[blackbox-full] provider gate failed" >&2
  echo "[blackbox-full] provider gate json: $provider_gate_json" >&2
  echo "[blackbox-full] provider gate md: $provider_gate_md" >&2
  exit 2
fi
echo "[blackbox-full] provider gate json: $provider_gate_json"
echo "[blackbox-full] provider gate md: $provider_gate_md"

if [[ "$require_clean_worktree" == "1" && -n "$(git status --porcelain)" ]]; then
  write_current_qa_artifacts
  write_run_artifact "blocked" "clean_worktree"
  echo "[blackbox-full] run json: $full_generation_json"
  echo "[blackbox-full] run md: $full_generation_md"
  echo "[blackbox-full] refusing to start generation because ASIP_BLACKBOX_REQUIRE_CLEAN_WORKTREE=1 and worktree is dirty" >&2
  echo "[blackbox-full] preflight json: $preflight_json" >&2
  exit 2
fi

if [[ "$skip_smoke" != "1" ]]; then
  echo "[blackbox-full] 1-node smoke"
  python3 -m asip.cli blackbox-profiles-batch \
    --db "$db_path" \
    --limit 1 \
    --batch-size 1 \
    --sample-count "$sample_count" \
    --retry-count "$retry_count" \
    --candidate-scope missing \
    --phase "${phase}-smoke" \
    --selection-seed "${selection_seed}-smoke" \
    --omit-graph \
    --summary-only \
    --output-json "$out_dir/smoke.json"
fi

round=0
no_progress_rounds=0
progress_rounds=0
while true; do
  round=$((round + 1))
  active_shard_count="$shard_count"
  active_limit_per_shard="$limit_per_shard"
  if [[ "$ramp_enabled" == "1" && "$progress_rounds" -ge "$ramp_after_progress_rounds" ]]; then
    active_shard_count="$ramp_shard_count"
    active_limit_per_shard="$ramp_limit_per_shard"
  fi
  round_phase="${phase}-round-${round}"
  round_seed="${selection_seed}-round-${round}"
  before_coverage="$out_dir/coverage-round-${round}-before.json"
  after_coverage="$out_dir/coverage-round-${round}-after.json"
  before_residual="$out_dir/residual-round-${round}-before.json"
  after_residual="$out_dir/residual-round-${round}-after.json"
  warmup_delta_json="$out_dir/terminal-warmup-round-${round}-delta.json"
  warmup_delta_md="$out_dir/terminal-warmup-round-${round}-delta.md"
  write_coverage "$before_coverage"
  write_residual_to "$before_residual"
  gate_status="$(json_field "$before_coverage" "gate_status")"
  before_missing="$(json_field "$before_coverage" "coverage.missing_count")"
  before_covered="$(json_field "$before_coverage" "coverage.covered_count")"
  inventory_total="$(json_field "$before_coverage" "coverage.inventory_total")"
  pending_count="$(json_field "$before_residual" "residuals.pending_count")"
  terminal_count="$(json_field "$before_residual" "residuals.terminal_count")"
  echo "[blackbox-full] round=$round active_shards=${active_shard_count} active_limit=${active_limit_per_shard} before covered=${before_covered}/${inventory_total} missing=${before_missing} pending=${pending_count} terminal=${terminal_count} status=${gate_status}"

  if [[ "$gate_status" == "pass" ]]; then
    cp "$before_coverage" "$coverage_json"
    break
  fi
  if [[ -z "$before_missing" || "$before_missing" == "0" ]]; then
    cp "$before_coverage" "$coverage_json"
    break
  fi
  if [[ "$max_rounds" != "0" && "$round" -gt "$max_rounds" ]]; then
    cp "$before_coverage" "$coverage_json"
    echo "[blackbox-full] reached max rounds before generation: $max_rounds" >&2
    exit 2
  fi

  generated_shards=0
  active_scope=""
  round_scopes=()
  if [[ "${terminal_count:-0}" != "0" && "$terminal_warmup_rounds" =~ ^[0-9]+$ && "$round" -le "$terminal_warmup_rounds" ]]; then
    if (( round % 2 == 1 )); then
      round_scopes=("$retry_consensus_scope" "$retry_parse_scope" "$retry_scope" "$primary_scope")
      echo "[blackbox-full] round=$round terminal warmup mode: consensus-first terminal=${terminal_count} pending=${pending_count}"
    else
      round_scopes=("$retry_parse_scope" "$retry_consensus_scope" "$retry_scope" "$primary_scope")
      echo "[blackbox-full] round=$round terminal warmup mode: parse-first terminal=${terminal_count} pending=${pending_count}"
    fi
  elif [[ "${pending_count:-0}" == "0" && "${terminal_count:-0}" != "0" ]]; then
    round_scopes=("$retry_consensus_scope" "$retry_parse_scope" "$retry_scope")
    echo "[blackbox-full] round=$round residual-only mode: pending=0 terminal=${terminal_count}"
  else
    round_scopes=("$primary_scope")
    for retry_candidate_scope in "$retry_consensus_scope" "$retry_parse_scope" "$retry_scope"; do
      if [[ "$retry_candidate_scope" != "$primary_scope" ]]; then
        round_scopes+=("$retry_candidate_scope")
      fi
    done
  fi
  deduped_scopes=()
  for scope_item in "${round_scopes[@]}"; do
    already_seen=0
    for seen_scope in ${deduped_scopes+"${deduped_scopes[@]}"}; do
      if [[ "$seen_scope" == "$scope_item" ]]; then
        already_seen=1
        break
      fi
    done
    if [[ "$already_seen" == "0" ]]; then
      deduped_scopes+=("$scope_item")
    fi
  done
  round_scopes=("${deduped_scopes[@]}")

  for scope in "${round_scopes[@]}"; do
    scope_generated_shards=0
    scope_limit_per_shard="$active_limit_per_shard"
    scope_batch_size="$batch_size"
    scope_sample_count="$sample_count"
    scope_retry_count="$retry_count"
    if [[ "$scope" == "$retry_scope" || "$scope" == "$retry_consensus_scope" || "$scope" == "$retry_parse_scope" ]]; then
      scope_limit_per_shard="$retry_limit_per_shard"
      scope_batch_size="$retry_batch_size"
      scope_sample_count="$retry_sample_count"
      scope_retry_count="$retry_retry_count"
    fi
    for ((shard = 0; shard < active_shard_count; shard += 1)); do
      printf -v shard_label "%04d" "$shard"
      selection_json="$out_dir/selection-round-${round}-${scope}-shard-${shard_label}.json"
      python3 -m asip.cli blackbox-profiles-batch \
        --db "$db_path" \
        --limit "$scope_limit_per_shard" \
        --candidate-scope "$scope" \
        --phase "$round_phase" \
        --selection-seed "$round_seed" \
        --shard-count "$active_shard_count" \
        --shard-index "$shard" \
        --dry-run-selection \
        --summary-only \
        --output-json "$selection_json" >/dev/null
      shard_candidates="$(json_field "$selection_json" "candidate_count")"
      if [[ -z "$shard_candidates" || "$shard_candidates" == "0" ]]; then
        echo "[blackbox-full] round=$round scope=$scope shard=$shard/$active_shard_count has no candidates"
        continue
      fi
      echo "[blackbox-full] round=$round scope=$scope shard=$shard/$active_shard_count candidates=$shard_candidates limit=$scope_limit_per_shard batch=$scope_batch_size sample/retry=${scope_sample_count}/${scope_retry_count} seed=$round_seed"
      batch_json="$out_dir/batch-round-${round}-${scope}-shard-${shard_label}.json"
      python3 -m asip.cli blackbox-profiles-batch \
        --db "$db_path" \
        --limit "$scope_limit_per_shard" \
        --batch-size "$scope_batch_size" \
        --sample-count "$scope_sample_count" \
        --retry-count "$scope_retry_count" \
        --candidate-scope "$scope" \
        --phase "$round_phase" \
        --selection-seed "$round_seed" \
        --shard-count "$active_shard_count" \
        --shard-index "$shard" \
        --omit-graph \
        --summary-only \
        --output-json "$batch_json"
      scope_generated_shards=$((scope_generated_shards + 1))
      batch_candidate_count="$(json_field "$batch_json" "candidate_count")"
      batch_profile_count="$(json_field "$batch_json" "profile_count")"
      batch_failed_count="$(json_field "$batch_json" "failed_count")"
      batch_rejected_count="$(json_field "$batch_json" "rejected_count")"
      batch_abstained_count="$(json_field "$batch_json" "abstained_count")"
      batch_terminal_count=$(( ${batch_failed_count:-0} + ${batch_rejected_count:-0} + ${batch_abstained_count:-0} ))
      if [[ "$adaptive_retry_enabled" == "1" \
        && "${scope_batch_size:-1}" -gt 1 \
        && "${batch_candidate_count:-0}" -ge "$adaptive_min_candidates" \
        && "${batch_profile_count:-0}" == "0" \
        && $(( batch_terminal_count * 100 )) -ge $(( ${batch_candidate_count:-0} * adaptive_failure_ratio_percent )) ]]; then
        adaptive_json="$out_dir/adaptive-retry-round-${round}-${scope}-shard-${shard_label}.json"
        adaptive_seed="${round_seed}-adaptive-${scope}-${shard_label}"
        echo "[blackbox-full] round=$round scope=$scope shard=$shard/$active_shard_count triggered adaptive retry: terminal=${batch_terminal_count}/${batch_candidate_count} retry_scope=${adaptive_retry_scope} batch=${adaptive_retry_batch_size} sample/retry=${adaptive_retry_sample_count}/${adaptive_retry_retry_count}"
        python3 -m asip.cli blackbox-profiles-batch \
          --db "$db_path" \
          --limit "$batch_candidate_count" \
          --batch-size "$adaptive_retry_batch_size" \
          --sample-count "$adaptive_retry_sample_count" \
          --retry-count "$adaptive_retry_retry_count" \
          --candidate-scope "$adaptive_retry_scope" \
          --phase "${round_phase}-adaptive" \
          --selection-seed "$adaptive_seed" \
          --shard-count "$active_shard_count" \
          --shard-index "$shard" \
          --omit-graph \
          --summary-only \
          --output-json "$adaptive_json"
      fi
    done
    if [[ "$scope_generated_shards" -gt 0 ]]; then
      generated_shards="$scope_generated_shards"
      active_scope="$scope"
      break
    fi
  done

  if [[ "$generated_shards" == "0" ]]; then
    cp "$before_coverage" "$coverage_json"
    echo "[blackbox-full] no candidates available in primary or retry scopes" >&2
    exit 2
  fi

  write_coverage "$after_coverage"
  write_residual_to "$after_residual"
  after_missing="$(json_field "$after_coverage" "coverage.missing_count")"
  after_covered="$(json_field "$after_coverage" "coverage.covered_count")"
  echo "[blackbox-full] round=$round scope=${active_scope} generated_shards=${generated_shards} after covered=${after_covered}/${inventory_total} missing=${after_missing}"
  if [[ "$round" -le "$terminal_warmup_rounds" || "$active_scope" == "$retry_scope" || "$active_scope" == "$retry_consensus_scope" || "$active_scope" == "$retry_parse_scope" ]]; then
    python3 -m asip.cli blackbox-residual-delta \
      --before-json "$before_residual" \
      --after-json "$after_residual" \
      --round "$round" \
      --scope "$active_scope" \
      --output-json "$warmup_delta_json" \
      --output-md "$warmup_delta_md" >/dev/null
    echo "[blackbox-full] round=$round terminal delta json: $warmup_delta_json"
  fi
  cp "$after_coverage" "$coverage_json"

  if [[ "$after_missing" == "0" ]]; then
    break
  fi
  if [[ "$after_missing" -ge "$before_missing" ]]; then
    no_progress_rounds=$((no_progress_rounds + 1))
    echo "[blackbox-full] no coverage progress in round $round (${no_progress_rounds}/${max_no_progress_rounds})" >&2
    if [[ "$no_progress_rounds" -ge "$max_no_progress_rounds" ]]; then
      echo "[blackbox-full] stopping after consecutive no-progress rounds" >&2
      exit 2
    fi
  else
    no_progress_rounds=0
    progress_rounds=$((progress_rounds + 1))
  fi
  if [[ "$max_rounds" != "0" && "$round" -ge "$max_rounds" ]]; then
    echo "[blackbox-full] reached max rounds: $max_rounds" >&2
    exit 2
  fi
done

write_ledger
coverage_exit=0
python3 -m asip.cli blackbox-coverage-qa \
  --db "$db_path" \
  --min-coverage 1.0 \
  --output-json "$coverage_json" \
  --output-md "${coverage_json%.json}.md" \
  --full \
  --require-pass >/dev/null || coverage_exit=$?

residual_exit=0
python3 -m asip.cli blackbox-residual-qa \
  --db "$db_path" \
  --output-json "$residual_json" \
  --output-md "$residual_md" \
  --full \
  --require-pass >/dev/null || residual_exit=$?

final_status="$(json_field "$coverage_json" "gate_status")"
final_covered="$(json_field "$coverage_json" "coverage.covered_count")"
final_total="$(json_field "$coverage_json" "coverage.inventory_total")"
final_missing="$(json_field "$coverage_json" "coverage.missing_count")"
residual_status="$(json_field "$residual_json" "gate_status")"
residual_pending="$(json_field "$residual_json" "residuals.pending_count")"
residual_terminal="$(json_field "$residual_json" "residuals.terminal_count")"
echo "[blackbox-full] final coverage status=${final_status} covered=${final_covered}/${final_total} missing=${final_missing}"
echo "[blackbox-full] final residual status=${residual_status} pending=${residual_pending} terminal=${residual_terminal}"
echo "[blackbox-full] ledger json: $ledger_json"
echo "[blackbox-full] coverage json: $coverage_json"
echo "[blackbox-full] residual json: $residual_json"

if [[ "$coverage_exit" != "0" || "$residual_exit" != "0" ]]; then
  write_run_artifact "blocked" "final_blackbox_qa"
  echo "[blackbox-full] run json: $full_generation_json"
  echo "[blackbox-full] run md: $full_generation_md"
  exit 2
fi

write_run_artifact "pass" ""
echo "[blackbox-full] run json: $full_generation_json"
echo "[blackbox-full] run md: $full_generation_md"

if [[ "$run_postpush" == "1" ]]; then
  if [[ -n "$(git status --porcelain)" ]]; then
    echo "[blackbox-full] skipping postpush gate because worktree is dirty" >&2
    echo "[blackbox-full] rerun with ASIP_BLACKBOX_RUN_POSTPUSH=1 after committing/stashing unrelated changes" >&2
    exit 2
  fi
  ASIP_POSTPUSH_OUT_DIR="$out_dir/postpush" pnpm gate:postpush
fi
