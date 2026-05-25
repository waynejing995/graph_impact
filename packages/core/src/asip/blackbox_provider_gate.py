"""Blackbox provider reachability gate artifact generation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .blackbox_coverage_qa import _repo_head, _sha256_file
from .workbench import _edge_provider_config, _preflight_blackbox_provider_reachability, load_provider_settings


def run_blackbox_provider_gate(
    db_path: Path,
    *,
    output_json: Optional[Path] = None,
    output_md: Optional[Path] = None,
) -> Dict[str, Any]:
    provider_settings = load_provider_settings(db_path)
    config = _edge_provider_config(provider_settings)
    failure_reasons: list[str] = []
    provider_check: Dict[str, Any]
    if config is None:
        provider_check = {
            "status": "fail",
            "message": "blackbox edge provider settings are missing",
            "failure_class": "missing_provider_settings",
        }
        failure_reasons.append(provider_check["message"])
    else:
        provider_check = {
            "status": "pass",
            "message": "ok",
            "provider": config.provider,
            "model": config.preferred,
            "api_base_url": config.api_base_url,
            "timeout_seconds": config.timeout_seconds,
        }
        try:
            _preflight_blackbox_provider_reachability(config)
        except Exception as exc:
            message = str(exc)
            provider_check["status"] = "fail"
            provider_check["message"] = message
            provider_check["failure_class"] = _classify_provider_failure(message)
            provider_check["recovery_hint"] = _provider_recovery_hint(provider_check["failure_class"])
            failure_reasons.append(message)

    payload: Dict[str, Any] = {
        "source": "asip.blackbox_provider_gate",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_head": _repo_head(Path.cwd()),
        "db_path": str(db_path),
        "db_sha256": _sha256_file(db_path),
        "provider_check": provider_check,
        "provider_settings_present": bool(provider_settings),
        "gate_status": "blocked" if failure_reasons else "pass",
        "failure_reasons": failure_reasons,
        "summary": {
            "status": "blocked" if failure_reasons else "pass",
            "provider": provider_check.get("provider", ""),
            "model": provider_check.get("model", ""),
            "message": provider_check.get("message", ""),
            "failure_class": provider_check.get("failure_class", ""),
        },
    }
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if output_md:
        output_md.parent.mkdir(parents=True, exist_ok=True)
        output_md.write_text(_markdown_summary(payload), encoding="utf-8")
    return payload


def _markdown_summary(payload: Mapping[str, Any]) -> str:
    check = payload.get("provider_check") if isinstance(payload.get("provider_check"), Mapping) else {}
    lines = [
        "# Blackbox Provider Gate",
        "",
        f"- Status: {payload.get('gate_status')}",
        f"- DB: `{payload.get('db_path')}`",
        f"- DB sha256: `{payload.get('db_sha256')}`",
        f"- Provider: `{check.get('provider', '')}`",
        f"- Model: `{check.get('model', '')}`",
        f"- Base URL: `{check.get('api_base_url', '')}`",
        f"- Check: {check.get('status')}",
        f"- Failure class: {check.get('failure_class', '')}",
        f"- Message: {check.get('message')}",
        f"- Recovery hint: {check.get('recovery_hint', '')}",
        "",
    ]
    return "\n".join(lines)


def _classify_provider_failure(message: str) -> str:
    normalized = message.lower()
    if "operation not permitted" in normalized or "errno 1" in normalized:
        return "local_network_permission"
    if "connection refused" in normalized or "failed to establish" in normalized:
        return "provider_not_listening"
    if "timed out" in normalized or "timeout" in normalized:
        return "provider_timeout"
    if "no such file" in normalized or "not found" in normalized:
        return "provider_missing"
    return "provider_unreachable"


def _provider_recovery_hint(failure_class: str) -> str:
    if failure_class == "local_network_permission":
        return "run the gate in an environment allowed to reach the local provider socket or expose a permitted OpenAI-compatible endpoint"
    if failure_class == "provider_not_listening":
        return "start the configured provider service and rerun blackbox-provider-gate"
    if failure_class == "provider_timeout":
        return "increase provider timeout or use a responsive model endpoint"
    if failure_class == "provider_missing":
        return "install or configure the requested provider/model before full generation"
    if failure_class == "missing_provider_settings":
        return "save blackbox edge provider settings before full generation"
    return "check provider base URL, model name, and local network permissions"
