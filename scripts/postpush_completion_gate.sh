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
browser_json="docs/qa/2026-05-21-browser-e2e-current.json"
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
pre_no_server_completion_json="$out_dir/completion-pre-no-server.json"
pre_no_server_completion_md="$out_dir/completion-pre-no-server.md"
no_server_json="$out_dir/ui-no-server-smoke.json"
completion_json="$out_dir/completion-gate.json"
completion_md="$out_dir/completion-gate.md"

echo "[postpush-gate] output directory: $out_dir"

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
echo "[postpush-gate] committed docs/qa completion input was only used for no-server preflight: $committed_completion_json"
