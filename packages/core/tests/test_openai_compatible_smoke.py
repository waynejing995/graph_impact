import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asip.openai_compatible_smoke import run_openai_compatible_live_smoke


class FakeEmbeddingTransport:
    def __init__(self):
        self.requests = []

    def post_json(self, url, payload, headers, timeout):
        self.requests.append(
            {
                "url": url,
                "payload": dict(payload),
                "headers": dict(headers),
                "timeout": timeout,
            }
        )
        return {"data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}]}


class FakeEdgeProvider:
    def __init__(self):
        self.calls = []

    def generate(self, prompt, model):
        self.calls.append({"prompt": prompt, "model": model})
        return {
            "cases": [
                {
                    "id": "openai_compatible_smoke",
                    "edges": [
                        {
                            "src": "GCVM_L2_CNTL",
                            "relation": "has_field",
                            "dst": "ENABLE_L2_CACHE",
                            "confidence": 1.0,
                            "evidence": "GCVM_L2_CNTL has field ENABLE_L2_CACHE.",
                        }
                    ],
                }
            ]
        }


class OpenAICompatibleSmokeTests(unittest.TestCase):
    def test_openai_compatible_smoke_passes_with_hosted_credential(self):
        embedding_transport = FakeEmbeddingTransport()
        edge_provider = FakeEdgeProvider()

        with patch.dict(os.environ, {"ASIP_TEST_OPENAI_KEY": "secret"}, clear=False):
            result = run_openai_compatible_live_smoke(
                base_url="https://openai-compatible.example.test",
                embedding_model="text-embedding-3-small",
                chat_model="gpt-4.1-mini",
                api_key_env="ASIP_TEST_OPENAI_KEY",
                require_credentialed=True,
                timeout_seconds=17,
                embedding_transport=embedding_transport,
                edge_provider=edge_provider,
            )

        self.assertEqual(result["gate_status"], "pass")
        self.assertEqual(result["credential_mode"], "hosted-credentialed")
        self.assertEqual(result["summary"], {"total": 2, "passed": 2, "failed": 0})
        self.assertEqual(embedding_transport.requests[0]["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(edge_provider.calls[0]["model"].extra_headers["Authorization"], "Bearer secret")

    def test_openai_compatible_smoke_blocks_when_required_credential_is_missing(self):
        embedding_transport = FakeEmbeddingTransport()
        edge_provider = FakeEdgeProvider()

        with patch.dict(os.environ, {}, clear=True):
            result = run_openai_compatible_live_smoke(
                base_url="https://openai-compatible.example.test",
                embedding_model="text-embedding-3-small",
                chat_model="gpt-4.1-mini",
                api_key_env="ASIP_MISSING_OPENAI_KEY",
                require_credentialed=True,
                embedding_transport=embedding_transport,
                edge_provider=edge_provider,
            )

        self.assertEqual(result["gate_status"], "blocked")
        self.assertEqual(result["credential_mode"], "hosted-missing-credential")
        self.assertIn("credential env var is missing: ASIP_MISSING_OPENAI_KEY", result["failure_reasons"])
        self.assertEqual(embedding_transport.requests, [])
        self.assertEqual(edge_provider.calls, [])

    def test_openai_compatible_smoke_cli_writes_blocked_json_without_secret(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_json = Path(tmpdir) / "smoke.json"
            env = dict(os.environ)
            repo_root = Path(__file__).resolve().parents[3]
            env["PYTHONPATH"] = str(repo_root / "packages/core/src")
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "asip.cli",
                    "openai-compatible-smoke",
                    "--base-url",
                    "https://openai-compatible.example.test",
                    "--embedding-model",
                    "text-embedding-3-small",
                    "--chat-model",
                    "gpt-4.1-mini",
                    "--api-key-env",
                    "ASIP_MISSING_OPENAI_KEY",
                    "--require-credentialed",
                    "--output-json",
                    str(output_json),
                ],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertEqual(json.loads(result.stdout)["failed"], 0)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["gate_status"], "blocked")
            self.assertEqual(payload["credential_mode"], "hosted-missing-credential")
