"""OpenAI-compatible live provider smoke checks."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

from .providers import EmbeddingProviderConfig, EmbeddingTransport, OpenAICompatibleEmbeddingProvider
from .semantic_edges import EdgeModelConfig, OpenAICompatibleEdgeProvider


def run_openai_compatible_live_smoke(
    *,
    base_url: str,
    embedding_model: str,
    chat_model: str,
    embedding_api_path: str = "/v1/embeddings",
    chat_api_path: str = "/v1/chat/completions",
    api_key_env: str = "",
    require_credentialed: bool = False,
    timeout_seconds: int = 60,
    output_json: Optional[Path] = None,
    embedding_transport: Optional[EmbeddingTransport] = None,
    edge_provider: Optional[OpenAICompatibleEdgeProvider] = None,
) -> Dict[str, Any]:
    """Run live embedding and chat checks through OpenAI-compatible endpoints."""

    checks = []
    failure_reasons = []
    headers: Dict[str, str] = {}
    api_key_env = api_key_env.strip()
    if api_key_env:
        api_key = os.environ.get(api_key_env, "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        else:
            failure_reasons.append(f"credential env var is missing: {api_key_env}")
    elif require_credentialed:
        failure_reasons.append("--require-credentialed requires --api-key-env")

    credential_mode = _credential_mode(base_url, api_key_env=api_key_env, has_key=bool(headers))
    if require_credentialed and credential_mode != "hosted-credentialed":
        failure_reasons.append(f"credential_mode={credential_mode} does not satisfy hosted-credentialed")

    if not failure_reasons:
        checks.append(
            _run_embedding_check(
                base_url=base_url,
                model=embedding_model,
                api_path=embedding_api_path,
                headers=headers,
                timeout_seconds=timeout_seconds,
                transport=embedding_transport,
            )
        )
        checks.append(
            _run_chat_check(
                base_url=base_url,
                model=chat_model,
                api_path=chat_api_path,
                headers=headers,
                timeout_seconds=timeout_seconds,
                provider=edge_provider,
            )
        )
        failure_reasons.extend(
            f"{check['id']}: {reason}"
            for check in checks
            if check.get("status") != "pass"
            for reason in check.get("failure_reasons", [])
        )

    passed = sum(1 for check in checks if check.get("status") == "pass")
    failed = sum(1 for check in checks if check.get("status") != "pass")
    result: Dict[str, Any] = {
        "source": "asip.openai_compatible_live_smoke",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "repo_head": _repo_head(Path.cwd()),
        "base_url": base_url.rstrip("/"),
        "credential_mode": credential_mode,
        "api_key_env": api_key_env,
        "require_credentialed": require_credentialed,
        "note": _note_for_credential_mode(credential_mode),
        "summary": {
            "total": len(checks),
            "passed": passed,
            "failed": failed,
        },
        "gate_status": "pass" if not failure_reasons and checks else "blocked",
        "checks": checks,
        "failure_reasons": failure_reasons,
    }
    if output_json:
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _run_embedding_check(
    *,
    base_url: str,
    model: str,
    api_path: str,
    headers: Mapping[str, str],
    timeout_seconds: int,
    transport: Optional[EmbeddingTransport],
) -> Dict[str, Any]:
    check: Dict[str, Any] = {
        "id": "openai_compatible_embeddings_live",
        "status": "blocked",
        "provider": "openai-compatible",
        "base_url": base_url.rstrip("/"),
        "api_path": api_path,
        "model": model,
        "failure_reasons": [],
    }
    try:
        vectors = OpenAICompatibleEmbeddingProvider(transport=transport).embed(
            ["ASIP OpenAI-compatible embedding smoke"],
            EmbeddingProviderConfig(
                provider="openai-compatible",
                model=model,
                api_base_url=base_url,
                api_path=api_path,
                extra_headers=dict(headers),
                timeout_seconds=timeout_seconds,
            ),
        )
        vector = vectors[0] if vectors else []
        check.update(
            {
                "status": "pass",
                "embedding_count": len(vectors),
                "vector_dimension": len(vector),
            }
        )
    except Exception as exc:
        check["failure_reasons"].append(str(exc))
    return check


def _run_chat_check(
    *,
    base_url: str,
    model: str,
    api_path: str,
    headers: Mapping[str, str],
    timeout_seconds: int,
    provider: Optional[OpenAICompatibleEdgeProvider],
) -> Dict[str, Any]:
    check: Dict[str, Any] = {
        "id": "openai_compatible_chat_completions_live",
        "status": "blocked",
        "provider": "openai-compatible",
        "base_url": base_url.rstrip("/"),
        "api_path": api_path,
        "model": model,
        "failure_reasons": [],
    }
    try:
        edge_provider = provider or OpenAICompatibleEdgeProvider()
        response = edge_provider.generate(
            (
                "CASE openai_compatible_smoke\n"
                "TERMS: GCVM_L2_CNTL ENABLE_L2_CACHE\n"
                "SNIPPET:\n"
                "1: GCVM_L2_CNTL has field ENABLE_L2_CACHE.\n"
            ),
            EdgeModelConfig(
                preferred=model,
                fallback="",
                provider="openai-compatible",
                api_base_url=base_url,
                api_path=api_path,
                extra_headers=dict(headers),
                format="json",
                num_predict=256,
                temperature=0,
                timeout_seconds=timeout_seconds,
            ),
        )
        edges = [
            edge
            for case in response.get("cases", [])
            if isinstance(case, Mapping)
            for edge in case.get("edges", [])
            if isinstance(edge, Mapping)
        ]
        check.update(
            {
                "status": "pass" if edges else "blocked",
                "edge_count": len(edges),
                "persistable_edge_count": sum(1 for edge in edges if edge.get("src") and edge.get("dst")),
                "sample_edge": edges[0] if edges else {},
            }
        )
        if not edges:
            check["failure_reasons"].append("chat completion returned no semantic edges")
    except Exception as exc:
        check["failure_reasons"].append(str(exc))
    return check


def _credential_mode(base_url: str, *, api_key_env: str, has_key: bool) -> str:
    host = base_url.rstrip("/").lower()
    is_local = any(token in host for token in ("localhost", "127.0.0.1", "::1"))
    if has_key and not is_local:
        return "hosted-credentialed"
    if has_key:
        return "local-compatible-credentialed"
    if is_local:
        return "local-compatible-no-secret"
    if api_key_env:
        return "hosted-missing-credential"
    return "hosted-no-secret"


def _note_for_credential_mode(mode: str) -> str:
    if mode == "hosted-credentialed":
        return "Uses a non-local OpenAI-compatible endpoint with an environment-provided credential."
    if mode == "local-compatible-no-secret":
        return "Uses a local OpenAI-compatible endpoint without a secret; this is not hosted credentialed QA."
    if mode == "hosted-missing-credential":
        return "Hosted endpoint requested but the configured credential environment variable is missing."
    if mode == "hosted-no-secret":
        return "Non-local endpoint configured without a credential; this does not satisfy hosted credentialed QA."
    return "OpenAI-compatible provider smoke completed with the recorded credential mode."


def _repo_head(cwd: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=cwd,
        text=True,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""
