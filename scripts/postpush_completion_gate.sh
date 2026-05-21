#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

export PYTHONDONTWRITEBYTECODE="${PYTHONDONTWRITEBYTECODE:-1}"
export PYTHONPATH="packages/core/src:${PYTHONPATH:-.}"

head_short="$(git rev-parse --short=12 HEAD)"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
out_dir="${ASIP_POSTPUSH_OUT_DIR:-/tmp/asip-postpush-gate-${head_short}-${timestamp}}"
mkdir -p "$out_dir"

acceptance_json="docs/qa/2026-05-21-acceptance-data-asip-live-web-current.json"
web_acceptance_json="docs/qa/2026-05-21-acceptance-data-asip-live-web-current.json"
committed_browser_json="docs/qa/2026-05-21-browser-e2e-current.json"
in_app_browser_json="docs/qa/2026-05-20-in-app-browser-probe.json"
runtime_semantic_json="docs/qa/2026-05-21-runtime-semantic-freshness-qa.json"
semantic_quality_json="docs/qa/2026-05-21-semantic-rerank-labeled-eval.json"
callback_audit_json="docs/qa/2026-05-21-callback-edge-audit-current.json"
performance_json="docs/qa/2026-05-20-performance-smoke-fixture-current.json"
residual_acceptance_json="docs/qa/2026-05-20-residual-acceptance-gate.json"
committed_completion_json="docs/qa/2026-05-21-current-goal-completion-gate.json"

provider_json="$out_dir/provider-gate.json"
hosted_openai_json="$out_dir/hosted-openai-compatible.json"
git_gate_json="$out_dir/git-gate.json"
browser_preflight_json="$out_dir/browser-e2e-preflight.json"
browser_json="$out_dir/browser-e2e-current-live.json"
browser_report_json="${browser_json%.json}.playwright-report.json"
pre_no_server_completion_json="$out_dir/completion-pre-no-server.json"
pre_no_server_completion_md="$out_dir/completion-pre-no-server.md"
no_server_json="$out_dir/ui-no-server-smoke.json"
completion_json="$out_dir/completion-gate.json"
completion_md="$out_dir/completion-gate.md"

echo "[postpush-gate] output directory: $out_dir"

urlencode() {
  python3 - "$1" <<'PY'
from urllib.parse import quote
import sys

print(quote(sys.argv[1], safe=""))
PY
}

read_current_db_job_ids() {
  python3 - "$1" <<'PY'
import sqlite3
import sys

db_path = sys.argv[1]
connection = sqlite3.connect(db_path)
try:
    latest_index_job_id = connection.execute(
        "select id from jobs where kind='index' and status in ('succeeded','indexed') order by id desc limit 1"
    ).fetchone()
    latest_graph_rebuild_job_id = connection.execute(
        "select id from jobs where kind='graph_rebuild' and status='succeeded' order by id desc limit 1"
    ).fetchone()
finally:
    connection.close()

print("" if latest_index_job_id is None else str(latest_index_job_id[0]))
print("" if latest_graph_rebuild_job_id is None else str(latest_graph_rebuild_job_id[0]))
PY
}

pick_clean_browser_base_url() {
  local host="${ASIP_POSTPUSH_BROWSER_HOST:-127.0.0.1}"
  local start_port="${ASIP_POSTPUSH_BROWSER_PORT:-3130}"

  if [[ ! "$start_port" =~ ^[0-9]+$ ]]; then
    echo "[postpush-gate] ASIP_POSTPUSH_BROWSER_PORT must be numeric: $start_port" >&2
    return 1
  fi

  local port
  for ((port = start_port; port < start_port + 20; port += 1)); do
    local candidate_url="http://${host}:${port}"
    local candidate_json="$out_dir/browser-e2e-preflight-${port}.json"
    if node apps/web/scripts/browser-gate-preflight.mjs \
      --base-url "$candidate_url" \
      --timeout-ms 1000 \
      --output-json "$candidate_json" >/dev/null; then
      cp "$candidate_json" "$browser_preflight_json"
      echo "$candidate_url"
      return 0
    fi
  done

  echo "[postpush-gate] no clean browser port found in ${start_port}..$((start_port + 19))" >&2
  return 1
}

run_live_browser_e2e() {
  local browser_db_path="${ASIP_POSTPUSH_BROWSER_DB_PATH:-data/asip.db}"
  local browser_base_url
  browser_base_url="$(pick_clean_browser_base_url)"
  local encoded_db_path
  encoded_db_path="$(urlencode "$browser_db_path")"
  local browser_target_url="${browser_base_url}/graph?dbPath=${encoded_db_path}"
  local latest_index_job_id
  local latest_graph_rebuild_job_id
  {
    IFS= read -r latest_index_job_id
    IFS= read -r latest_graph_rebuild_job_id
  } < <(read_current_db_job_ids "$browser_db_path")
  local browser_e2e_grep
  browser_e2e_grep="acceptance page runs no-mock AQ01 through the real workbench API|graph page uses URL dbPath for no-mock graph and query requests|graph page loads current data/asip.db through browser and API|graph page filters no-mock graph layers and shows edge provenance|evidence page initial query uses URL dbPath without default DB fallback"

  if [[ -z "$latest_index_job_id" || -z "$latest_graph_rebuild_job_id" ]]; then
    echo "[postpush-gate] current DB is missing latest index or graph_rebuild job id: $browser_db_path" >&2
    return 1
  fi

  echo "[postpush-gate] live browser e2e base URL: $browser_base_url"
  echo "[postpush-gate] live browser e2e target: $browser_target_url"

  node apps/web/scripts/browser-e2e-artifact.mjs \
    --output-json "$browser_json" \
    --base-url "$browser_base_url" \
    --db-path "$browser_db_path" \
    --latest-index-job-id "$latest_index_job_id" \
    --latest-graph-rebuild-job-id "$latest_graph_rebuild_job_id" \
    --target-url "$browser_target_url" \
    -- tests/workbench-smoke.spec.ts -g "$browser_e2e_grep"
}

python3 -m asip.cli git-gate \
  --repo-root . \
  --output-json "$git_gate_json" \
  --full

python3 - "$git_gate_json" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if payload.get("gate_status") != "pass":
    print("[postpush-gate] git gate must pass before running expensive checks")
    for reason in payload.get("failure_reasons", []):
        print(f"[postpush-gate] git gate blocker: {reason}")
    sys.exit(1)
PY

python3 -m asip.cli provider-gate \
  --db data/asip.db \
  --output-json "$provider_json" \
  --full

python3 -m asip.cli openai-compatible-smoke \
  --base-url "${ASIP_HOSTED_OPENAI_BASE_URL:-https://api.openai.com}" \
  --embedding-model "${ASIP_HOSTED_OPENAI_EMBEDDING_MODEL:-text-embedding-3-small}" \
  --chat-model "${ASIP_HOSTED_OPENAI_CHAT_MODEL:-gpt-4.1-mini}" \
  --api-key-env "${ASIP_HOSTED_OPENAI_API_KEY_ENV:-OPENAI_API_KEY}" \
  --require-credentialed \
  --output-json "$hosted_openai_json" \
  --full

run_live_browser_e2e

# This preflight completion intentionally uses the committed no-server artifact.
# It gives current-artifact-invariants-smoke a complete completion artifact to
# inspect before the fresh no-server artifact exists. The final aggregate below
# consumes the fresh no-server artifact generated from the same provider file.
python3 -m asip.cli completion-gate \
  --db data/asip.db \
  --acceptance-json "$acceptance_json" \
  --web-acceptance-json "$web_acceptance_json" \
  --provider-json "$provider_json" \
  --runtime-semantic-json "$runtime_semantic_json" \
  --semantic-quality-json "$semantic_quality_json" \
  --callback-audit-json "$callback_audit_json" \
  --browser-json "$browser_json" \
  --in-app-browser-json "$in_app_browser_json" \
  --no-server-json docs/qa/2026-05-21-ui-no-server-smoke.json \
  --performance-json "$performance_json" \
  --hosted-openai-json "$hosted_openai_json" \
  --residual-acceptance-json "$residual_acceptance_json" \
  --git-gate-json "$git_gate_json" \
  --output-json "$pre_no_server_completion_json" \
  --output-md "$pre_no_server_completion_md" \
  --full

node apps/web/scripts/no-server-smoke.mjs \
  --output-json "$no_server_json" \
  --browser-json "$browser_json" \
  --in-app-browser-json "$in_app_browser_json" \
  --provider-json "$provider_json" \
  --runtime-semantic-json "$runtime_semantic_json" \
  --semantic-quality-json "$semantic_quality_json" \
  --callback-audit-json "$callback_audit_json" \
  --acceptance-json "$acceptance_json" \
  --web-acceptance-json "$web_acceptance_json" \
  --completion-json "$pre_no_server_completion_json" \
  --web-package-json apps/web/package.json

python3 -m asip.cli completion-gate \
  --db data/asip.db \
  --acceptance-json "$acceptance_json" \
  --web-acceptance-json "$web_acceptance_json" \
  --provider-json "$provider_json" \
  --runtime-semantic-json "$runtime_semantic_json" \
  --semantic-quality-json "$semantic_quality_json" \
  --callback-audit-json "$callback_audit_json" \
  --browser-json "$browser_json" \
  --in-app-browser-json "$in_app_browser_json" \
  --no-server-json "$no_server_json" \
  --performance-json "$performance_json" \
  --hosted-openai-json "$hosted_openai_json" \
  --residual-acceptance-json "$residual_acceptance_json" \
  --git-gate-json "$git_gate_json" \
  --output-json "$completion_json" \
  --output-md "$completion_md" \
  --full

python3 - "$completion_json" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload = json.loads(path.read_text(encoding="utf-8"))
requirements = {item["id"]: item for item in payload.get("requirements", [])}
allowed_blockers = {"hosted_openai_compatible", "residual_acceptance"}
unexpected = [
    f"{item_id}={item.get('status')}"
    for item_id, item in sorted(requirements.items())
    if item.get("status") != "pass" and item_id not in allowed_blockers
]
summary = payload.get("summary", {})
if summary.get("failed", 0) != 0 or summary.get("missing", 0) != 0 or unexpected:
    print("[postpush-gate] unexpected blockers:", ", ".join(unexpected) or "none")
    print(json.dumps(summary, indent=2))
    sys.exit(1)
print(
    "[postpush-gate] final summary:",
    f"gate_status={payload.get('gate_status')}",
    f"passed={summary.get('passed')}/{summary.get('total')}",
    f"blocked={summary.get('blocked')}",
)
for item_id in sorted(allowed_blockers):
    item = requirements.get(item_id, {})
    print(f"[postpush-gate] {item_id}: {item.get('status')} - {item.get('evidence')}")
PY

echo "[postpush-gate] completion json: $completion_json"
echo "[postpush-gate] completion md: $completion_md"
echo "[postpush-gate] live browser e2e json: $browser_json"
echo "[postpush-gate] live browser e2e report: $browser_report_json"
echo "[postpush-gate] browser preflight json: $browser_preflight_json"
echo "[postpush-gate] committed browser e2e input was not used: $committed_browser_json"
echo "[postpush-gate] committed docs/qa completion input was only used for no-server preflight: $committed_completion_json"
