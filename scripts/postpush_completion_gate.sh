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

committed_acceptance_json="docs/qa/2026-05-21-acceptance-data-asip-live-web-current.json"
committed_browser_json="docs/qa/2026-05-21-browser-e2e-current.json"
in_app_browser_json="docs/qa/2026-05-20-in-app-browser-probe.json"
committed_runtime_semantic_json="docs/qa/2026-05-21-runtime-semantic-freshness-qa.json"
committed_semantic_quality_json="docs/qa/2026-05-21-semantic-rerank-labeled-eval.json"
committed_callback_audit_json="docs/qa/2026-05-21-callback-edge-audit-current.json"
committed_performance_json="docs/qa/2026-05-20-performance-smoke-fixture-current.json"
residual_acceptance_json="docs/qa/2026-05-20-residual-acceptance-gate.json"
committed_completion_json="docs/qa/2026-05-21-current-goal-completion-gate.json"

provider_json="$out_dir/provider-gate.json"
runtime_preflight_json="$out_dir/runtime-preflight.json"
acceptance_json="$out_dir/acceptance-current-live.json"
acceptance_md="$out_dir/acceptance-current-live.md"
web_acceptance_json="$acceptance_json"
semantic_quality_json="$out_dir/semantic-rerank-labeled-eval-current-live.json"
semantic_quality_md="$out_dir/semantic-rerank-labeled-eval-current-live.md"
callback_audit_json="$out_dir/callback-edge-audit-current-live.json"
runtime_semantic_json="$out_dir/runtime-semantic-freshness-current-live.json"
blackbox_provider_json="$out_dir/blackbox-provider-gate-current-live.json"
blackbox_provider_md="$out_dir/blackbox-provider-gate-current-live.md"
blackbox_ledger_json="$out_dir/blackbox-ledger-qa-current-live.json"
blackbox_ledger_md="$out_dir/blackbox-ledger-qa-current-live.md"
blackbox_coverage_json="$out_dir/blackbox-coverage-qa-current-live.json"
blackbox_coverage_md="$out_dir/blackbox-coverage-qa-current-live.md"
blackbox_residual_json="$out_dir/blackbox-residual-qa-current-live.json"
blackbox_residual_md="$out_dir/blackbox-residual-qa-current-live.md"
blackbox_full_generation_json="${ASIP_BLACKBOX_FULL_GENERATION_JSON:-}"
hosted_openai_json="$out_dir/hosted-openai-compatible.json"
performance_json="$out_dir/performance-smoke-current.json"
performance_db="$out_dir/performance-smoke.db"
git_gate_json="$out_dir/git-gate.json"
browser_preflight_json="$out_dir/browser-e2e-preflight.json"
browser_json="$out_dir/browser-e2e-current-live.json"
browser_report_json="${browser_json%.json}.playwright-report.json"
pre_no_server_completion_json="$out_dir/completion-pre-no-server.json"
pre_no_server_completion_md="$out_dir/completion-pre-no-server.md"
pre_no_server_completion_stdout="$out_dir/completion-pre-no-server.summary.json"
no_server_json="$out_dir/ui-no-server-smoke.json"
completion_json="$out_dir/completion-gate.json"
completion_md="$out_dir/completion-gate.md"
live_browser_base_url=""
live_api_base_url=""
live_api_pid=""
mcp_protocol_python="${ASIP_MCP_PROTOCOL_PYTHON:-}"

cleanup_live_api() {
  if [[ -n "$live_api_pid" ]] && kill -0 "$live_api_pid" 2>/dev/null; then
    kill "$live_api_pid" 2>/dev/null || true
    wait "$live_api_pid" 2>/dev/null || true
  fi
}
trap cleanup_live_api EXIT

echo "[postpush-gate] output directory: $out_dir"

urlencode() {
  python3 - "$1" <<'PY'
from urllib.parse import quote
import sys

print(quote(sys.argv[1], safe=""))
PY
}

write_runtime_preflight() {
  python3 - "$runtime_preflight_json" "data/asip.db" <<'PY'
import importlib.util
import json
import os
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

output_path = Path(sys.argv[1])
db_path = Path(sys.argv[2])

try:
    from asip.workbench import load_provider_settings
except Exception:
    load_provider_settings = None


def import_status(module):
    return {
        "module": module,
        "status": "pass" if importlib.util.find_spec(module) is not None else "missing",
    }


def python_module_status(module, python_executable):
    if not python_executable:
        return import_status(module)
    try:
        subprocess.check_call(
            [
                python_executable,
                "-c",
                f"import importlib.util; raise SystemExit(0 if importlib.util.find_spec({module!r}) else 1)",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        return {
            "module": module,
            "status": "missing",
            "python": python_executable,
            "message": str(exc),
        }
    return {"module": module, "status": "pass", "python": python_executable}


def bind_status(host, start_port, count):
    attempts = []
    permission_denied = False
    for port in range(start_port, start_port + count):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((host, port))
        except PermissionError as exc:
            permission_denied = True
            attempts.append({"port": port, "status": "permission_denied", "message": str(exc)})
            continue
        except OSError as exc:
            attempts.append({"port": port, "status": "unavailable", "message": str(exc)})
            continue
        finally:
            sock.close()
        attempts.append({"port": port, "status": "pass", "message": "bind ok"})
        return {"status": "pass", "host": host, "selected_port": port, "attempts": attempts}
    status = "blocked" if permission_denied else "fail"
    return {"status": status, "host": host, "selected_port": None, "attempts": attempts}


def connect_status(base_url):
    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        sock.connect((host, port))
    except PermissionError as exc:
        return {"status": "blocked", "base_url": base_url, "host": host, "port": port, "message": str(exc)}
    except OSError as exc:
        return {"status": "fail", "base_url": base_url, "host": host, "port": port, "message": str(exc)}
    finally:
        sock.close()
    return {"status": "pass", "base_url": base_url, "host": host, "port": port, "message": "connect ok"}


def configured_provider_sockets():
    if load_provider_settings is None:
        return {
            "status": "fail",
            "db_path": str(db_path),
            "message": "asip.workbench.load_provider_settings is unavailable",
            "checks": [],
        }
    settings = load_provider_settings(db_path)
    checks = []
    for name in ("edge", "embedding"):
        value = settings.get(name)
        if not isinstance(value, dict):
            checks.append({"name": name, "status": "missing", "message": f"{name} provider settings are missing"})
            continue
        base_url = str(value.get("base_url") or value.get("api_base_url") or "").strip()
        if not base_url:
            checks.append({"name": name, "status": "missing", "message": f"{name} provider base_url is missing"})
            continue
        socket_check = connect_status(base_url)
        socket_check["name"] = name
        socket_check["provider"] = str(value.get("provider") or "")
        socket_check["model"] = str(value.get("model") or value.get("embedding_model") or "")
        checks.append(socket_check)
    status = "pass" if checks and all(item.get("status") == "pass" for item in checks) else "blocked"
    return {
        "status": status,
        "db_path": str(db_path),
        "checks": checks,
    }


api_host = os.environ.get("ASIP_POSTPUSH_API_HOST", "127.0.0.1")
api_start_port = int(os.environ.get("ASIP_POSTPUSH_API_PORT", "8230"))
browser_host = os.environ.get("ASIP_POSTPUSH_BROWSER_HOST", "127.0.0.1")
browser_start_port = int(os.environ.get("ASIP_POSTPUSH_BROWSER_PORT", "3130"))
provider_base_url = os.environ.get("ASIP_HOSTED_OPENAI_BASE_URL", "http://localhost:11434")
mcp_protocol_python = os.environ.get("ASIP_MCP_PROTOCOL_PYTHON", "").strip()

checks = {
    "python_modules": [import_status(module) for module in ("fastapi", "uvicorn", "mcp")],
    "mcp_protocol_runtime": python_module_status("mcp", mcp_protocol_python),
    "api_port_bind": bind_status(api_host, api_start_port, 20),
    "browser_port_bind": bind_status(browser_host, browser_start_port, 20),
    "provider_socket": connect_status(provider_base_url),
    "configured_provider_sockets": configured_provider_sockets(),
}
blocked = []
if checks["mcp_protocol_runtime"]["status"] != "pass":
    blocked.append("MCP_PROTOCOL proof needs ASIP_MCP_PROTOCOL_PYTHON with mcp installed")
if checks["api_port_bind"]["status"] != "pass" and not os.environ.get("ASIP_API_BASE_URL"):
    blocked.append("local API bind is unavailable and ASIP_API_BASE_URL is not configured")
if checks["browser_port_bind"]["status"] != "pass":
    blocked.append("local browser/dev-server bind is unavailable")
if checks["provider_socket"]["status"] != "pass":
    blocked.append(f"hosted/OpenAI-compatible provider socket is not reachable: {checks['provider_socket']['message']}")
if checks["configured_provider_sockets"]["status"] != "pass":
    for item in checks["configured_provider_sockets"].get("checks", []):
        if item.get("status") != "pass":
            blocked.append(
                f"configured {item.get('name', 'provider')} provider socket is not reachable: "
                f"{item.get('message', item.get('status'))}"
            )

payload = {
    "source": "asip.postpush_runtime_preflight",
    "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "gate_status": "blocked" if blocked else "pass",
    "checks": checks,
    "failure_reasons": blocked,
}
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(f"[postpush-gate] runtime preflight: gate_status={payload['gate_status']} artifact={output_path}")
for reason in blocked:
    print(f"[postpush-gate] runtime preflight blocker: {reason}")
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

pick_clean_api_base_url() {
  local host="${ASIP_POSTPUSH_API_HOST:-127.0.0.1}"
  local start_port="${ASIP_POSTPUSH_API_PORT:-8230}"

  if [[ ! "$start_port" =~ ^[0-9]+$ ]]; then
    echo "[postpush-gate] ASIP_POSTPUSH_API_PORT must be numeric: $start_port" >&2
    return 1
  fi

  python3 - "$host" "$start_port" <<'PY'
import socket
import sys

host = sys.argv[1]
start_port = int(sys.argv[2])
permission_denied = False
for port in range(start_port, start_port + 20):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
    except PermissionError:
        permission_denied = True
        continue
    except OSError:
        continue
    finally:
        sock.close()
    print(f"http://{host}:{port}")
    raise SystemExit(0)
if permission_denied:
    print(
        f"[postpush-gate] local API port bind was denied for {host}:{start_port}..{start_port + 19}; "
        "run in an environment allowed to bind localhost or provide ASIP_API_BASE_URL",
        file=sys.stderr,
    )
    raise SystemExit(1)
print(f"[postpush-gate] no clean API port found in {start_port}..{start_port + 19}", file=sys.stderr)
raise SystemExit(1)
PY
}

wait_for_live_api() {
  local base_url="$1"
  python3 - "$base_url" <<'PY'
import sys
import time
import urllib.error
import urllib.request

base_url = sys.argv[1].rstrip("/")
url = f"{base_url}/docs"
deadline = time.time() + 30
last_error = ""
while time.time() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=1) as response:
            if response.status < 500:
                raise SystemExit(0)
    except Exception as exc:
        last_error = str(exc)
        time.sleep(0.5)
print(f"[postpush-gate] live API did not become ready at {url}: {last_error}", file=sys.stderr)
raise SystemExit(1)
PY
}

run_live_api_server() {
  if [[ -n "${ASIP_API_BASE_URL:-}" ]]; then
    live_api_base_url="${ASIP_API_BASE_URL%/}"
    echo "[postpush-gate] live API base URL: $live_api_base_url"
    wait_for_live_api "$live_api_base_url"
    return 0
  fi

  live_api_base_url="$(pick_clean_api_base_url)"
  local host_port="${live_api_base_url#http://}"
  local host="${host_port%:*}"
  local port="${host_port##*:}"
  local api_log="$out_dir/api-live.log"

  echo "[postpush-gate] live API base URL: $live_api_base_url"
  PYTHONPATH="packages/core/src:." python3 -m uvicorn apps.api.main:app \
    --host "$host" \
    --port "$port" \
    --log-level warning \
    >"$api_log" 2>&1 &
  live_api_pid="$!"
  wait_for_live_api "$live_api_base_url"
}

detect_mcp_protocol_python() {
  if [[ -n "$mcp_protocol_python" ]]; then
    return 0
  fi
  if python3 - <<'PY' >/dev/null 2>&1
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("mcp") else 1)
PY
  then
    mcp_protocol_python="$(command -v python3)"
    return 0
  fi
  echo "[postpush-gate] MCP protocol runtime not detected; install the optional mcp package or set ASIP_MCP_PROTOCOL_PYTHON" >&2
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
  live_browser_base_url="$browser_base_url"

  node apps/web/scripts/browser-e2e-artifact.mjs \
    --output-json "$browser_json" \
    --base-url "$browser_base_url" \
    --db-path "$browser_db_path" \
    --latest-index-job-id "$latest_index_job_id" \
    --latest-graph-rebuild-job-id "$latest_graph_rebuild_job_id" \
    --target-url "$browser_target_url" \
    -- tests/workbench-smoke.spec.ts -g "$browser_e2e_grep"
}

write_runtime_preflight

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

if [[ -z "$blackbox_full_generation_json" || ! -f "$blackbox_full_generation_json" ]]; then
  echo "[postpush-gate] ASIP_BLACKBOX_FULL_GENERATION_JSON must point to a current blackbox-full-generation-run.json" >&2
  echo "[postpush-gate] run scripts/blackbox_full_generation.sh first and pass its run json path" >&2
  exit 2
fi

python3 -m asip.cli provider-gate \
  --db data/asip.db \
  --output-json "$provider_json" \
  --full

python3 scripts/audit_callback_edges.py \
  --db data/asip.db \
  --output-json "$callback_audit_json" \
  --assert-no-parser-pollution \
  --require-version-funcs-receiver-table \
  --max-ambiguous-fanout 2 \
  --require-real-oracle drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c:gfx_v10_0_ring_preempt_ib \
  --require-real-oracle drivers/gpu/drm/amd/amdgpu/amdgpu_device.c:amdgpu_device_fw_loading \
  --require-real-oracle drivers/gpu/drm/amd/amdgpu/amdgpu_pmu.c:amdgpu_perf_start \
  --require-real-oracle libgv/core/amdgv_device.c:amdgv_device_func_hw_init \
  --require-real-oracle libgv/core/amdgv_sched_switch.c:amdgv_sched_world_switch_init \
  --require-real-oracle libgv/core/amdgv_ecc.c:amdgv_ecc_import_live_data \
  --require-real-oracle gim/gim_shim/sysfs/gim_debugfs.c:snprintf_realloc

python3 -m asip.cli semantic-quality \
  --db data/asip.db \
  --eval-set docs/qa/semantic-rerank-eval-set.jsonl \
  --output-json "$semantic_quality_json" \
  --output-md "$semantic_quality_md" \
  --full

python3 -m asip.cli runtime-semantic-freshness \
  --db data/asip.db \
  --output-json "$runtime_semantic_json" \
  --full

python3 -m asip.cli performance-smoke \
  --db "$performance_db" \
  --source-root docs/fixtures/performance-smoke \
  --output-json "$performance_json" >/dev/null

python3 -m asip.cli blackbox-provider-gate \
  --db data/asip.db \
  --output-json "$blackbox_provider_json" \
  --output-md "$blackbox_provider_md" \
  --full

python3 -m asip.cli blackbox-ledger-qa \
  --db data/asip.db \
  --output-json "$blackbox_ledger_json" \
  --output-md "$blackbox_ledger_md" \
  --full

python3 -m asip.cli blackbox-coverage-qa \
  --db data/asip.db \
  --min-coverage 1.0 \
  --output-json "$blackbox_coverage_json" \
  --output-md "$blackbox_coverage_md" \
  --full

python3 -m asip.cli blackbox-residual-qa \
  --db data/asip.db \
  --output-json "$blackbox_residual_json" \
  --output-md "$blackbox_residual_md" \
  --full

openai_compatible_smoke_args=(
  --base-url "${ASIP_HOSTED_OPENAI_BASE_URL:-http://localhost:11434}"
  --embedding-model "${ASIP_HOSTED_OPENAI_EMBEDDING_MODEL:-nomic-embed-text:latest}"
  --chat-model "${ASIP_HOSTED_OPENAI_CHAT_MODEL:-gemma4:e4b}"
  --output-json "$hosted_openai_json"
  --full
)
if [[ -n "${ASIP_HOSTED_OPENAI_API_KEY_ENV:-}" ]]; then
  openai_compatible_smoke_args+=(
    --api-key-env "${ASIP_HOSTED_OPENAI_API_KEY_ENV}"
    --require-credentialed
  )
fi
python3 -m asip.cli openai-compatible-smoke "${openai_compatible_smoke_args[@]}"

run_live_api_server
detect_mcp_protocol_python
run_live_browser_e2e

ASIP_API_BASE_URL="$live_api_base_url" \
ASIP_WEB_BASE_URL="$live_browser_base_url" \
ASIP_MCP_PROTOCOL_PYTHON="$mcp_protocol_python" \
python3 -m asip.cli acceptance \
  --db data/asip.db \
  --surface API \
  --surface API_LIVE \
  --surface MCP \
  --surface MCP_PROTOCOL \
  --surface Web \
  --output-json "$acceptance_json" \
  --output-md "$acceptance_md" \
  --full >/dev/null

# This preflight completion intentionally uses the committed no-server artifact.
# It gives current-artifact-invariants-smoke a complete completion artifact to
# inspect before the fresh no-server artifact exists. The final aggregate below
# consumes the fresh no-server artifact generated from the same provider file.
# Keep this internal bootstrap summary out of the main terminal stream so it is
# not mistaken for the post-push result.
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
  --blackbox-provider-json "$blackbox_provider_json" \
  --blackbox-ledger-json "$blackbox_ledger_json" \
  --blackbox-coverage-json "$blackbox_coverage_json" \
  --blackbox-residual-json "$blackbox_residual_json" \
  --blackbox-full-generation-json "$blackbox_full_generation_json" \
  --require-blackbox-provider \
  --require-blackbox-ledger \
  --require-blackbox-coverage \
  --require-blackbox-residual \
  --require-blackbox-full-generation \
  --min-blackbox-coverage 1.0 \
  --output-json "$pre_no_server_completion_json" \
  --output-md "$pre_no_server_completion_md" \
  >"$pre_no_server_completion_stdout"

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
  --blackbox-provider-json "$blackbox_provider_json" \
  --blackbox-ledger-json "$blackbox_ledger_json" \
  --blackbox-coverage-json "$blackbox_coverage_json" \
  --blackbox-residual-json "$blackbox_residual_json" \
  --blackbox-full-generation-json "$blackbox_full_generation_json" \
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
  --blackbox-provider-json "$blackbox_provider_json" \
  --blackbox-ledger-json "$blackbox_ledger_json" \
  --blackbox-coverage-json "$blackbox_coverage_json" \
  --blackbox-residual-json "$blackbox_residual_json" \
  --blackbox-full-generation-json "$blackbox_full_generation_json" \
  --require-blackbox-provider \
  --require-blackbox-ledger \
  --require-blackbox-coverage \
  --require-blackbox-residual \
  --require-blackbox-full-generation \
  --min-blackbox-coverage 1.0 \
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
echo "[postpush-gate] runtime preflight json: $runtime_preflight_json"
echo "[postpush-gate] live browser e2e json: $browser_json"
echo "[postpush-gate] live browser e2e report: $browser_report_json"
echo "[postpush-gate] browser preflight json: $browser_preflight_json"
echo "[postpush-gate] live acceptance json: $acceptance_json"
echo "[postpush-gate] live acceptance md: $acceptance_md"
echo "[postpush-gate] live callback audit json: $callback_audit_json"
echo "[postpush-gate] live semantic quality json: $semantic_quality_json"
echo "[postpush-gate] live semantic quality md: $semantic_quality_md"
echo "[postpush-gate] live performance smoke json: $performance_json"
echo "[postpush-gate] live blackbox provider json: $blackbox_provider_json"
echo "[postpush-gate] live blackbox ledger json: $blackbox_ledger_json"
echo "[postpush-gate] live blackbox coverage json: $blackbox_coverage_json"
echo "[postpush-gate] live blackbox residual json: $blackbox_residual_json"
echo "[postpush-gate] blackbox full generation json: $blackbox_full_generation_json"
echo "[postpush-gate] committed acceptance input was not used: $committed_acceptance_json"
echo "[postpush-gate] committed browser e2e input was not used: $committed_browser_json"
echo "[postpush-gate] committed runtime semantic input was not used: $committed_runtime_semantic_json"
echo "[postpush-gate] committed semantic quality input was not used: $committed_semantic_quality_json"
echo "[postpush-gate] committed callback audit input was not used: $committed_callback_audit_json"
echo "[postpush-gate] committed performance input was not used: $committed_performance_json"
echo "[postpush-gate] committed docs/qa completion input was only used for no-server preflight: $committed_completion_json"
