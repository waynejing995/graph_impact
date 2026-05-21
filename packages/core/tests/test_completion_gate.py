import hashlib
import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from asip.acceptance import PROVIDER_CHECK_IDS
from asip.cli import main as cli_main
from asip.completion_gate import run_completion_gate


class CompletionGateTests(unittest.TestCase):
    def test_completion_gate_passes_when_all_artifacts_prove_the_goal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            semantic_quality_json = self._write_json(root / "semantic-quality.json", self._semantic_quality_payload("pass", db_path=db_path))
            callback_audit_json = self._write_json(root / "callback-audit.json", self._callback_audit_payload("pass", db_path=db_path))
            browser_json = self._write_json(
                root / "browser.json",
                self._browser_e2e_payload("pass", db_path=db_path),
            )
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                semantic_quality_json=semantic_quality_json,
                callback_audit_json=callback_audit_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            self.assertEqual(result["gate_status"], "pass")
            self.assertEqual(result["summary"]["passed"], result["summary"]["total"])
            self.assertEqual(result["summary"]["blocked"], 0)
            self.assertEqual(result["database"]["counts"]["linux_amdgpu_chunks"], 1)
            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertIn("9/9 required artifacts loaded", by_id["artifact_binding"]["evidence"])
            self.assertIn("4/4 DB/job-bound artifacts checked", by_id["artifact_binding"]["evidence"])
            self.assertEqual(by_id["semantic_quality"]["status"], "pass")
            self.assertEqual(by_id["callback_edge_audit"]["status"], "pass")

    def test_completion_gate_blocks_callback_audit_without_real_oracles(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            payload = self._callback_audit_payload("pass", db_path=db_path)
            payload["summary"]["real_oracle_total"] = 0
            payload["summary"]["real_oracle_passed"] = 0
            callback_audit_json = self._write_json(root / "callback-audit.json", payload)

            result = run_completion_gate(
                db_path,
                callback_audit_json=callback_audit_json,
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(by_id["callback_edge_audit"]["status"], "blocked")
            self.assertIn("real_oracle_total=0", by_id["callback_edge_audit"]["failure_reasons"])

    def test_completion_gate_blocks_real_final_mode_without_semantic_quality_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(by_id["semantic_quality"]["status"], "missing")
            self.assertIn("semantic-quality artifact is missing", by_id["semantic_quality"]["failure_reasons"])
            self.assertEqual(by_id["callback_edge_audit"]["status"], "missing")
            self.assertIn("callback audit artifact is missing", by_id["callback_edge_audit"]["failure_reasons"])

    def test_completion_gate_blocks_non_indexed_corpus_status_in_current_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            with sqlite3.connect(db_path) as connection:
                connection.execute(
                    "insert into corpora (id, status) values (?, ?)",
                    ("local-amd-docs", "not_indexed"),
                )
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["real_index_db"]["status"], "fail")
            self.assertIn("corpus local-amd-docs status is not_indexed", by_id["real_index_db"]["failure_reasons"])
            self.assertEqual(
                result["database"]["corpora_statuses"],
                [
                    {"id": "linux-amdgpu", "status": "indexed"},
                    {"id": "local-amd-docs", "status": "not_indexed"},
                ],
            )

    def test_completion_gate_blocks_stale_git_gate_head_binding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            repo_root = root / "repo"
            repo_root.mkdir()
            self._run_git(repo_root, ["init", "-b", "main"])
            self._run_git(repo_root, ["config", "user.email", "asip-test@example.com"])
            self._run_git(repo_root, ["config", "user.name", "ASIP Test"])
            (repo_root / "tracked.txt").write_text("initial\n", encoding="utf-8")
            self._run_git(repo_root, ["add", "tracked.txt"])
            self._run_git(repo_root, ["commit", "-m", "initial"])
            old_head = self._run_git(repo_root, ["rev-parse", "HEAD"]).stdout.strip()

            (repo_root / "tracked.txt").write_text("current\n", encoding="utf-8")
            self._run_git(repo_root, ["add", "tracked.txt"])
            self._run_git(repo_root, ["commit", "-m", "current"])

            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(
                root / "git.json",
                self._git_payload("pass", repo_root=repo_root, branch="main", head=old_head),
            )

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["git_gate"]["status"], "blocked")
            self.assertTrue(any("head does not match current HEAD" in reason for reason in by_id["git_gate"]["failure_reasons"]))

    def test_completion_gate_blocks_tiny_db_with_default_expanded_thresholds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            browser_json = self._write_json(
                root / "browser.json",
                {"source": "asip.web.browser_e2e", "gate_status": "pass", "e2e_status": "pass"},
            )

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                browser_json=browser_json,
            )

            self.assertEqual(result["gate_status"], "blocked")
            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(by_id["real_index_db"]["status"], "blocked")
            self.assertTrue(any("below required expanded count" in reason for reason in by_id["real_index_db"]["failure_reasons"]))

    def test_completion_gate_blocks_unproven_provider_web_and_browser_runtime(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(
                root / "web-acceptance.json",
                self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path, web_status="not_configured"),
            )
            provider_json = self._write_json(root / "provider.json", self._provider_payload("blocked", db_path=db_path))
            browser_json = self._write_json(
                root / "browser.json",
                {
                    "source": "asip.web.browser_gate_preflight",
                    "gate_status": "blocked",
                    "failure_reasons": ["local listen capability blocked: EPERM"],
                },
            )

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                browser_json=browser_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            self.assertEqual(result["gate_status"], "blocked")
            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(by_id["real_index_db"]["status"], "pass")
            self.assertEqual(by_id["stage1_deterministic_graph"]["status"], "pass")
            self.assertEqual(by_id["cli_api_mcp_surfaces"]["status"], "pass")
            self.assertEqual(by_id["web_surface"]["status"], "blocked")
            self.assertEqual(by_id["provider_live_gate"]["status"], "blocked")
            self.assertEqual(by_id["stage2_semantic_edges"]["status"], "blocked")
            self.assertEqual(by_id["browser_e2e"]["status"], "blocked")
            self.assertTrue(any("EPERM" in reason for reason in result["failure_reasons"]))

    def test_completion_gate_keeps_core_acceptance_separate_from_web_surface_blocker(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(
                root / "web-acceptance.json",
                self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path, web_status="not_configured"),
            )
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["acceptance_gate"]["status"], "pass")
            self.assertEqual(by_id["web_surface"]["status"], "blocked")
            self.assertTrue(
                any("Web status=not_configured" in reason for reason in by_id["web_surface"]["failure_reasons"])
            )

    def test_completion_gate_blocks_acceptance_without_live_api_surface(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_payload = self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path)
            acceptance_payload["surfaces_checked"] = [
                surface for surface in acceptance_payload["surfaces_checked"] if surface != "API_LIVE"
            ]
            for query in acceptance_payload["queries"]:
                query["surface_results"] = [
                    result for result in query["surface_results"] if result["surface"] != "API_LIVE"
                ]
            acceptance_json = self._write_json(root / "acceptance.json", acceptance_payload)
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["cli_api_mcp_surfaces"]["status"], "pass")
            self.assertEqual(by_id["api_live_surface"]["status"], "blocked")
            self.assertIn("API_LIVE was not listed in surfaces_checked", by_id["api_live_surface"]["failure_reasons"])

    def test_completion_gate_blocks_acceptance_without_mcp_protocol_surface(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_payload = self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path)
            acceptance_payload["surfaces_checked"] = [
                surface for surface in acceptance_payload["surfaces_checked"] if surface != "MCP_PROTOCOL"
            ]
            for query in acceptance_payload["queries"]:
                query["surface_results"] = [
                    result for result in query["surface_results"] if result["surface"] != "MCP_PROTOCOL"
                ]
            acceptance_json = self._write_json(root / "acceptance.json", acceptance_payload)
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["cli_api_mcp_surfaces"]["status"], "pass")
            self.assertEqual(by_id["mcp_protocol_surface"]["status"], "blocked")
            self.assertIn(
                "MCP_PROTOCOL was not listed in surfaces_checked",
                by_id["mcp_protocol_surface"]["failure_reasons"],
            )

    def test_completion_gate_blocks_spoofed_or_empty_live_api_surface(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))
            variants = {
                "testclient_transport": (
                    {"transport": "fastapi.testclient.query"},
                    "API_LIVE transport=fastapi.testclient.query",
                ),
                "wrong_db": (
                    {"db_path": str(root / "wrong.db")},
                    "does not match current db_path",
                ),
                "empty_result": (
                    {"row_count": 0, "graph_node_count": 0},
                    "API_LIVE row_count=0",
                ),
                "failed_status": (
                    {"status": "not_configured", "message": "ASIP_API_BASE_URL missing"},
                    "API_LIVE status=not_configured",
                ),
                "missing_base_url": (
                    {"base_url": ""},
                    "API_LIVE base_url is missing",
                ),
                "missing_url": (
                    {"url": ""},
                    "API_LIVE url is missing",
                ),
                "wrong_url_db_path": (
                    {"url": f"http://127.0.0.1:8124/query?db_path={root / 'wrong.db'}&compact_graph=true"},
                    "API_LIVE url db_path",
                ),
            }

            for name, (updates, expected_reason) in variants.items():
                with self.subTest(name=name):
                    acceptance_payload = self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path)
                    live_result = next(
                        result
                        for result in acceptance_payload["queries"][0]["surface_results"]
                        if result["surface"] == "API_LIVE"
                    )
                    live_result.update(updates)
                    acceptance_json = self._write_json(root / f"acceptance-{name}.json", acceptance_payload)

                    result = run_completion_gate(
                        db_path,
                        acceptance_json=acceptance_json,
                        web_acceptance_json=web_json,
                        provider_json=provider_json,
                        runtime_semantic_json=runtime_json,
                        browser_json=browser_json,
                        no_server_json=no_server_json,
                        performance_json=performance_json,
                        residual_acceptance_json=residual_json,
                        git_gate_json=git_json,
                        minimum_counts=self._fixture_minimum_counts(),
                    )

                    by_id = {item["id"]: item for item in result["requirements"]}
                    self.assertEqual(result["gate_status"], "blocked")
                    self.assertEqual(by_id["api_live_surface"]["status"], "blocked")
                    self.assertTrue(
                        any(expected_reason in reason for reason in by_id["api_live_surface"]["failure_reasons"]),
                        by_id["api_live_surface"]["failure_reasons"],
                    )

    def test_completion_gate_blocks_spoofed_or_empty_mcp_protocol_surface(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))
            variants = {
                "tool_direct_transport": (
                    {"transport": "mcp.tool-direct.search_evidence"},
                    "MCP_PROTOCOL transport=mcp.tool-direct.search_evidence",
                ),
                "wrong_db": (
                    {"db_path": str(root / "wrong.db")},
                    "does not match current db_path",
                ),
                "empty_result": (
                    {"row_count": 0, "graph_node_count": 0},
                    "MCP_PROTOCOL row_count=0",
                ),
                "failed_status": (
                    {"status": "not_configured", "message": "ASIP_MCP_PROTOCOL_PYTHON missing"},
                    "MCP_PROTOCOL status=not_configured",
                ),
                "unregistered_tool": (
                    {"server_registered": False},
                    "MCP_PROTOCOL search_evidence was not registered",
                ),
                "missing_command": (
                    {"command": ""},
                    "MCP_PROTOCOL command is missing",
                ),
                "wrong_tool": (
                    {"tool": "query_evidence"},
                    "MCP_PROTOCOL tool=query_evidence",
                ),
                "wrong_server_args": (
                    {"server_args": ["apps.mcp.server"]},
                    "MCP_PROTOCOL server_args",
                ),
            }

            for name, (updates, expected_reason) in variants.items():
                with self.subTest(name=name):
                    acceptance_payload = self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path)
                    protocol_result = next(
                        result
                        for result in acceptance_payload["queries"][0]["surface_results"]
                        if result["surface"] == "MCP_PROTOCOL"
                    )
                    protocol_result.update(updates)
                    acceptance_json = self._write_json(root / f"acceptance-mcp-{name}.json", acceptance_payload)

                    result = run_completion_gate(
                        db_path,
                        acceptance_json=acceptance_json,
                        web_acceptance_json=web_json,
                        provider_json=provider_json,
                        runtime_semantic_json=runtime_json,
                        browser_json=browser_json,
                        no_server_json=no_server_json,
                        performance_json=performance_json,
                        residual_acceptance_json=residual_json,
                        git_gate_json=git_json,
                        minimum_counts=self._fixture_minimum_counts(),
                    )

                    by_id = {item["id"]: item for item in result["requirements"]}
                    self.assertEqual(result["gate_status"], "blocked")
                    self.assertEqual(by_id["mcp_protocol_surface"]["status"], "blocked")
                    self.assertTrue(
                        any(expected_reason in reason for reason in by_id["mcp_protocol_surface"]["failure_reasons"]),
                        by_id["mcp_protocol_surface"]["failure_reasons"],
                    )

    def test_completion_gate_blocks_web_surface_pass_without_next_bff_db_binding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_payload = self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path)
            first_web_result = next(
                result
                for result in web_payload["queries"][0]["surface_results"]
                if result["surface"] == "Web"
            )
            first_web_result["transport"] = "fixture.mock"
            first_web_result["db_path"] = str(root / "wrong.db")
            first_web_result["row_count"] = 0
            first_web_result["graph_node_count"] = 0
            web_json = self._write_json(root / "web-acceptance.json", web_payload)
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["web_surface"]["status"], "blocked")
            self.assertIn("AQ01: Web transport=fixture.mock", by_id["web_surface"]["failure_reasons"])
            self.assertTrue(any("Web db_path=" in reason for reason in by_id["web_surface"]["failure_reasons"]))
            self.assertIn("AQ01: Web row_count=0", by_id["web_surface"]["failure_reasons"])
            self.assertIn("AQ01: Web graph_node_count=0", by_id["web_surface"]["failure_reasons"])

    def test_completion_gate_blocks_web_surface_pass_without_graph_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_payload = self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path)
            first_web_result = next(
                result
                for result in web_payload["queries"][0]["surface_results"]
                if result["surface"] == "Web"
            )
            first_web_result["graph_edge_count"] = 0
            web_json = self._write_json(root / "web-acceptance.json", web_payload)
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["web_surface"]["status"], "blocked")
            self.assertIn("AQ01: Web graph_edge_count=0", by_id["web_surface"]["failure_reasons"])

    def test_completion_gate_blocks_web_surface_when_web_acceptance_artifact_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_payload = self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path)
            web_payload["gate_status"] = "blocked"
            web_payload["summary"]["passed"] = 8
            web_payload["summary"]["failed"] = 1
            web_payload["queries"][-1]["status"] = "fail"
            web_payload["queries"][-1]["failure_reasons"] = ["embedding provider check failed: fallback embeddings remain"]
            web_json = self._write_json(root / "web-acceptance.json", web_payload)
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["web_surface"]["status"], "blocked")
            self.assertIn(
                "web acceptance gate_status=blocked; summary passed=8/9 failed=1",
                by_id["web_surface"]["failure_reasons"],
            )
            self.assertTrue(
                any("AQ09: web acceptance query status=fail" in reason for reason in by_id["web_surface"]["failure_reasons"])
            )

    def test_completion_gate_allows_web_surface_row_only_queries_when_all_surfaces_have_no_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_payload = self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path)
            for result in web_payload["queries"][0]["surface_results"]:
                result["graph_edge_count"] = 0
            web_json = self._write_json(root / "web-acceptance.json", web_payload)
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(by_id["web_surface"]["status"], "pass")

    def test_completion_gate_blocks_when_acceptance_artifact_is_not_aq01_to_aq09(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(
                root / "acceptance.json",
                self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path, query_ids=["AQ01"]),
            )
            web_json = self._write_json(
                root / "web-acceptance.json",
                self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path, query_ids=["AQ01"]),
            )
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            browser_json = self._write_json(
                root / "browser.json",
                {"source": "asip.web.browser_e2e", "gate_status": "pass", "e2e_status": "pass"},
            )

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                browser_json=browser_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["acceptance_gate"]["status"], "blocked")
            self.assertTrue(any("missing acceptance query id(s): AQ02" in reason for reason in by_id["acceptance_gate"]["failure_reasons"]))

    def test_completion_gate_blocks_stale_stage1_graph_rebuild(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            with sqlite3.connect(db_path) as connection:
                connection.execute("insert into jobs (id, kind, status) values (9, 'index', 'succeeded')")

            result = run_completion_gate(db_path, minimum_counts=self._fixture_minimum_counts())

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["stage1_deterministic_graph"]["status"], "blocked")
            self.assertIn(
                "latest graph_rebuild job id 2 is older than latest index job id 9",
                by_id["stage1_deterministic_graph"]["failure_reasons"],
            )

    def test_completion_gate_blocks_current_db_failed_or_running_jobs_even_with_old_pass_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            with sqlite3.connect(db_path) as connection:
                connection.execute(
                    "insert into jobs (id, kind, status, message) values (99, 'index', 'failed', 'newer failure')"
                )
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["real_index_db"]["status"], "fail")
            self.assertIn("job 99 index is failed: newer failure", by_id["real_index_db"]["failure_reasons"])

    def test_completion_gate_blocks_mismatched_artifact_db_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            other_db_path = root / "old-clean.db"
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=other_db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            browser_json = self._write_json(
                root / "browser.json",
                {"source": "asip.web.browser_e2e", "gate_status": "pass", "e2e_status": "pass"},
            )

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                browser_json=browser_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["artifact_binding"]["status"], "blocked")
            self.assertTrue(any("does not match current db_path" in reason for reason in by_id["artifact_binding"]["failure_reasons"]))

    def test_completion_gate_blocks_stale_provider_graph_job_binding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_payload = self._provider_payload("pass", db_path=db_path)
            provider_payload["provider_checks"]["semantic_edge_provenance"]["latest_graph_rebuild_job_id"] = 1
            provider_json = self._write_json(root / "provider.json", provider_payload)
            browser_json = self._write_json(
                root / "browser.json",
                {"source": "asip.web.browser_e2e", "gate_status": "pass", "e2e_status": "pass"},
            )

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                browser_json=browser_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["artifact_binding"]["status"], "blocked")
            self.assertIn(
                "provider_gate semantic_edge_provenance.latest_graph_rebuild_job_id=1 does not match current latest_graph_rebuild_job_id=2",
                by_id["artifact_binding"]["failure_reasons"],
            )

    def test_completion_gate_blocks_stale_provider_index_job_binding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_payload = self._provider_payload("pass", db_path=db_path)
            provider_payload["provider_checks"]["semantic_edge_provenance"]["latest_index_job_id"] = 0
            provider_json = self._write_json(root / "provider.json", provider_payload)
            browser_json = self._write_json(
                root / "browser.json",
                {"source": "asip.web.browser_e2e", "gate_status": "pass", "e2e_status": "pass"},
            )

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                browser_json=browser_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["artifact_binding"]["status"], "blocked")
            self.assertIn(
                "provider_gate semantic_edge_provenance.latest_index_job_id=0 does not match current latest_index_job_id=1",
                by_id["artifact_binding"]["failure_reasons"],
            )

    def test_completion_gate_blocks_stale_doc_node_provider_job_binding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_payload = self._provider_payload("pass", db_path=db_path)
            provider_payload["provider_checks"]["doc_node_provenance"]["latest_graph_rebuild_job_id"] = 1
            provider_json = self._write_json(root / "provider.json", provider_payload)
            browser_json = self._write_json(
                root / "browser.json",
                {"source": "asip.web.browser_e2e", "gate_status": "pass", "e2e_status": "pass"},
            )

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                browser_json=browser_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["artifact_binding"]["status"], "blocked")
            self.assertIn(
                "provider_gate doc_node_provenance.latest_graph_rebuild_job_id=1 does not match current latest_graph_rebuild_job_id=2",
                by_id["artifact_binding"]["failure_reasons"],
            )

    def test_completion_gate_blocks_malformed_provider_job_binding_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_payload = self._provider_payload("pass", db_path=db_path)
            provider_payload["provider_checks"]["semantic_edge_provenance"]["latest_index_job_id"] = "not-a-number"
            provider_json = self._write_json(root / "provider.json", provider_payload)

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["artifact_binding"]["status"], "blocked")
            self.assertIn(
                "provider_gate semantic_edge_provenance.latest_index_job_id is not an integer: not-a-number",
                by_id["artifact_binding"]["failure_reasons"],
            )

    def test_completion_gate_blocks_provider_artifact_job_ids_missing_from_current_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_payload = self._provider_payload("pass", db_path=db_path)
            provider_payload["provider_checks"]["semantic_edge_provenance"]["job_ids"] = [99]
            provider_json = self._write_json(root / "provider.json", provider_payload)
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["artifact_binding"]["status"], "blocked")
            self.assertIn(
                "provider_gate semantic_edge_provenance.job_id=99 is not recorded in current DB",
                by_id["artifact_binding"]["failure_reasons"],
            )

    def test_completion_gate_blocks_provider_artifact_job_ids_with_wrong_kind(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_payload = self._provider_payload("pass", db_path=db_path)
            provider_payload["provider_checks"]["semantic_edge_provenance"]["job_ids"] = [4]
            provider_json = self._write_json(root / "provider.json", provider_payload)
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["artifact_binding"]["status"], "blocked")
            self.assertIn(
                "provider_gate semantic_edge_provenance.job_id=4 kind=doc_nodes_batch is not one of semantic_edges, semantic_edges_batch",
                by_id["artifact_binding"]["failure_reasons"],
            )

    def test_completion_gate_allows_pass_status_with_superseded_stale_semantic_edge_count(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_payload = self._provider_payload("pass", db_path=db_path)
            provider_payload["provider_checks"]["semantic_edge_provenance"]["stale_edge_count"] = 1
            provider_json = self._write_json(root / "provider.json", provider_payload)
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(
                root / "browser.json",
                {"source": "asip.web.browser_e2e", "gate_status": "pass", "e2e_status": "pass"},
            )
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(by_id["artifact_binding"]["status"], "pass")
            self.assertEqual(by_id["stage2_semantic_edges"]["status"], "pass")
            self.assertNotIn(
                "semantic_edge_provenance: pass artifact still reports stale_edge_count=1",
                by_id["stage2_semantic_edges"]["failure_reasons"],
            )

    def test_completion_gate_blocks_stage2_pass_artifact_without_edge_count_or_jobs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_payload = self._provider_payload("pass", db_path=db_path)
            provider_payload["provider_checks"]["semantic_edge_provenance"]["edge_count"] = 0
            provider_payload["provider_checks"]["semantic_edge_provenance"]["job_ids"] = []
            provider_json = self._write_json(root / "provider.json", provider_payload)
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["stage2_semantic_edges"]["status"], "blocked")
            self.assertIn(
                "semantic_edge_provenance: pass artifact reports edge_count=0",
                by_id["stage2_semantic_edges"]["failure_reasons"],
            )
            self.assertIn(
                "semantic_edge_provenance: pass artifact job_ids are missing",
                by_id["stage2_semantic_edges"]["failure_reasons"],
            )

    def test_completion_gate_blocks_pass_provider_artifact_with_missing_or_invalid_job_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_payload = self._provider_payload("pass", db_path=db_path)
            provider_payload["provider_checks"]["semantic_edge_provenance"]["missing_or_invalid_job_edge_count"] = 1
            provider_json = self._write_json(root / "provider.json", provider_payload)
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["stage2_semantic_edges"]["status"], "blocked")
            self.assertIn(
                "semantic_edge_provenance: pass artifact still reports missing_or_invalid_job_edge_count=1",
                by_id["stage2_semantic_edges"]["failure_reasons"],
            )

    def test_completion_gate_blocks_runtime_semantic_freshness_failures(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("blocked", db_path=db_path))
            browser_json = self._write_json(
                root / "browser.json",
                {"source": "asip.web.browser_e2e", "gate_status": "pass", "e2e_status": "pass"},
            )
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["artifact_binding"]["status"], "pass")
            self.assertEqual(by_id["runtime_semantic_freshness"]["status"], "blocked")
            self.assertIn("gate_status=blocked", by_id["runtime_semantic_freshness"]["failure_reasons"])
            self.assertTrue(
                any("storage_runtime_stale_semantic_filter" in reason for reason in by_id["runtime_semantic_freshness"]["failure_reasons"])
            )

    def test_completion_gate_blocks_stale_runtime_semantic_freshness_job_binding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_payload = self._runtime_semantic_payload("pass", db_path=db_path)
            runtime_payload["latest_graph_rebuild_job_id"] = 1
            runtime_json = self._write_json(root / "runtime-semantic.json", runtime_payload)
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertIn(
                "runtime_semantic_freshness latest_graph_rebuild_job_id=1 does not match current latest_graph_rebuild_job_id=2",
                by_id["artifact_binding"]["failure_reasons"],
            )

    def test_completion_gate_blocks_no_server_smoke_with_stale_artifact_input_hash(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_payload = self._no_server_payload("pass")
            no_server_payload["current_artifact_inputs"] = [
                self._artifact_input("--browser-json", browser_json),
                self._artifact_input("--provider-json", provider_json, sha256="not-the-current-provider-hash"),
                self._artifact_input("--runtime-semantic-json", runtime_json),
                self._artifact_input("--acceptance-json", acceptance_json),
                self._artifact_input("--web-acceptance-json", web_json),
            ]
            no_server_json = self._write_json(root / "no-server.json", no_server_payload)
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["web_no_server_smoke"]["status"], "blocked")
            self.assertIn(
                "no-server --provider-json sha256 does not match current artifact",
                by_id["web_no_server_smoke"]["failure_reasons"],
            )

    def test_completion_gate_blocks_stale_runtime_semantic_generation_job_binding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            with sqlite3.connect(db_path) as connection:
                connection.execute("insert into jobs (id, kind, status) values (9, 'doc_nodes_batch', 'succeeded')")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertIn(
                "runtime_semantic_freshness latest_doc_nodes_job_id=4 does not match current latest_doc_nodes_job_id=9",
                by_id["artifact_binding"]["failure_reasons"],
            )

    def test_completion_gate_blocks_stale_runtime_semantic_query_job_binding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            with sqlite3.connect(db_path) as connection:
                connection.execute("insert into jobs (id, kind, status) values (9, 'semantic_edges', 'succeeded')")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertIn(
                "runtime_semantic_freshness latest_semantic_edges_job_id=3 does not match current latest_semantic_edges_job_id=9",
                by_id["artifact_binding"]["failure_reasons"],
            )

    def test_completion_gate_normalizes_legacy_generated_semantic_job_binding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            with sqlite3.connect(db_path) as connection:
                connection.execute("insert into jobs (id, kind, status) values (9, 'semantic_edges_batch', 'generated')")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertIn(
                "runtime_semantic_freshness latest_semantic_edges_job_id=3 does not match current latest_semantic_edges_job_id=9",
                by_id["artifact_binding"]["failure_reasons"],
            )

    def test_completion_gate_blocks_missing_required_provider_checks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(
                root / "provider.json",
                {
                    "source": "asip.provider_gate",
                    "db_path": str(db_path),
                    "gate_status": "pass",
                    "provider_checks": {
                        "embedding": {"status": "pass", "message": "ok"},
                        "semantic_edge_provenance": {
                            "status": "pass",
                            "message": "ok",
                            "latest_index_job_id": 1,
                            "latest_graph_rebuild_job_id": 2,
                        },
                        "semantic_edge": {"status": "pass", "message": "ok"},
                    },
                    "summary": {"total": 3, "passed": 3, "partial": 0, "failed": 0},
                },
            )
            browser_json = self._write_json(
                root / "browser.json",
                {"source": "asip.web.browser_e2e", "gate_status": "pass", "e2e_status": "pass"},
            )

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                browser_json=browser_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["provider_live_gate"]["status"], "blocked")
            self.assertIn("embedding_live provider check is missing", by_id["provider_live_gate"]["failure_reasons"])

    def test_completion_gate_blocks_malformed_provider_checks_without_crashing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(
                root / "provider.json",
                {
                    "source": "asip.provider_gate",
                    "db_path": str(db_path),
                    "gate_status": "pass",
                    "provider_checks": ["embedding", "semantic_edge"],
                    "summary": {"total": 5, "passed": 5, "partial": 0, "failed": 0},
                },
            )
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                browser_json=browser_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertIn("provider_gate provider_checks is not an object", by_id["artifact_binding"]["failure_reasons"])
            self.assertIn("provider_checks is not an object", by_id["provider_live_gate"]["failure_reasons"])
            self.assertIn("provider_checks is not an object", by_id["stage2_semantic_edges"]["failure_reasons"])

    def test_completion_gate_blocks_missing_aq09_acceptance_provider_check_detail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_payload = self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path)
            aq09 = next(query for query in acceptance_payload["queries"] if query["id"] == "AQ09")
            aq09["provider_checks"].pop("doc_node_provenance")
            acceptance_json = self._write_json(root / "acceptance.json", acceptance_payload)
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                browser_json=browser_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["acceptance_gate"]["status"], "blocked")
            self.assertIn(
                "AQ09 provider check doc_node_provenance is missing",
                by_id["acceptance_gate"]["failure_reasons"],
            )

    def test_completion_gate_blocks_preflight_artifact_as_browser_e2e_proof(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            browser_json = self._write_json(
                root / "browser.json",
                {
                    "source": "asip.web.browser_gate_preflight",
                    "gate_status": "pass",
                    "e2e_status": "pass",
                },
            )
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["browser_e2e"]["status"], "blocked")
            self.assertIn(
                "browser artifact source=asip.web.browser_gate_preflight is not no-mock browser e2e proof",
                by_id["browser_e2e"]["failure_reasons"],
            )

    def test_completion_gate_blocks_browser_e2e_artifact_without_required_no_mock_tests(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(
                root / "browser.json",
                {
                    "source": "asip.web.browser_e2e",
                    "gate_status": "pass",
                    "e2e_status": "pass",
                    "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 105},
                    "required_tests": [
                        {
                            "title": "graph page uses URL dbPath for no-mock graph and query requests",
                            "status": "pass",
                        }
                    ],
                },
            )
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["artifact_binding"]["status"], "pass")
            self.assertEqual(by_id["browser_e2e"]["status"], "blocked")
            self.assertTrue(
                any("required browser e2e test is missing" in reason for reason in by_id["browser_e2e"]["failure_reasons"])
            )

    def test_completion_gate_blocks_browser_e2e_artifact_without_raw_playwright_report_binding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_payload = self._browser_e2e_payload("pass", db_path=db_path)
            browser_payload.pop("report_json", None)
            browser_payload.pop("report_sha256", None)
            browser_json = self._write_json(root / "browser.json", browser_payload)
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertIn(
                "browser e2e raw Playwright report path is missing",
                by_id["browser_e2e"]["failure_reasons"],
            )

    def test_completion_gate_blocks_offline_playwright_json_report_as_final_browser_proof(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_payload = self._browser_e2e_payload("pass", db_path=db_path)
            browser_payload["command"] = ["playwright-json-report", browser_payload["report_json"]]
            browser_json = self._write_json(root / "browser.json", browser_payload)
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertIn(
                "browser e2e command is not a live Playwright test run",
                by_id["browser_e2e"]["failure_reasons"][0],
            )

    def test_completion_gate_blocks_browser_e2e_artifact_without_current_db_binding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_payload = self._browser_e2e_payload("pass", db_path=db_path)
            browser_payload["db_path"] = str(root / "old.db")
            browser_payload["latest_graph_rebuild_job_id"] = 1
            browser_payload["target_urls"] = ["http://127.0.0.1:3100/graph?dbPath=/tmp/old.db"]
            browser_json = self._write_json(root / "browser.json", browser_payload)
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["browser_e2e"]["status"], "blocked")
            self.assertTrue(any("browser e2e db_path=" in reason for reason in by_id["browser_e2e"]["failure_reasons"]))
            self.assertIn("browser e2e latest_graph_rebuild_job_id=1 does not match current latest_graph_rebuild_job_id=2", by_id["browser_e2e"]["failure_reasons"])
            self.assertIn("browser e2e target_urls do not include current dbPath", by_id["browser_e2e"]["failure_reasons"])

    def test_completion_gate_blocks_browser_e2e_artifact_without_current_db_probes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_payload = self._browser_e2e_payload("pass", db_path=db_path)
            browser_payload.pop("current_db_probes", None)
            browser_json = self._write_json(root / "browser.json", browser_payload)
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["browser_e2e"]["status"], "blocked")
            self.assertIn("browser e2e current_db_probes are missing", by_id["browser_e2e"]["failure_reasons"])

    def test_completion_gate_blocks_browser_e2e_artifact_without_current_db_concept_detail_probe(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_payload = self._browser_e2e_payload("pass", db_path=db_path)
            browser_payload["current_db_probes"] = [
                probe
                for probe in browser_payload["current_db_probes"]
                if probe["surface"] != "graph_page_concept_detail_selection"
            ]
            browser_json = self._write_json(root / "browser.json", browser_payload)
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["browser_e2e"]["status"], "blocked")
            self.assertIn(
                "browser e2e current_db_probes missing surface: graph_page_concept_detail_selection",
                by_id["browser_e2e"]["failure_reasons"],
            )

    def test_completion_gate_blocks_browser_e2e_artifact_when_raw_report_lacks_required_tests(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_payload = self._browser_e2e_payload("pass", db_path=db_path)
            raw_report = json.dumps(
                {
                    "stats": {"expected": 1, "unexpected": 0, "flaky": 0, "skipped": 0, "duration": 1},
                    "suites": [
                        {
                            "title": "workbench-smoke.spec.ts",
                            "specs": [
                                {
                                    "title": "graph page uses URL dbPath for no-mock graph and query requests",
                                    "tests": [{"outcome": "expected"}],
                                }
                            ],
                        }
                    ],
                },
                sort_keys=True,
            )
            raw_report_path = root / "raw-playwright.json"
            raw_report_path.write_text(raw_report, encoding="utf-8")
            browser_payload["report_json"] = str(raw_report_path)
            browser_payload["report_sha256"] = hashlib.sha256(raw_report.encode("utf-8")).hexdigest()
            browser_payload["report_bytes"] = len(raw_report.encode("utf-8"))
            browser_json = self._write_json(root / "browser.json", browser_payload)
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["browser_e2e"]["status"], "blocked")
            self.assertTrue(
                any(
                    "raw Playwright report missing required browser e2e test" in reason
                    for reason in by_id["browser_e2e"]["failure_reasons"]
                )
            )

    def test_completion_gate_blocks_browser_e2e_artifact_when_raw_report_has_extra_failures(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_payload = self._browser_e2e_payload("pass", db_path=db_path)
            raw_report = json.dumps(
                {
                    "stats": {"expected": len(browser_payload["required_tests"]), "unexpected": 1, "flaky": 0, "skipped": 0, "duration": 1},
                    "errors": [],
                    "suites": [
                        {
                            "title": "workbench-smoke.spec.ts",
                            "specs": [
                                {
                                    "title": item["title"],
                                    "tests": [{"outcome": "expected"}],
                                }
                                for item in browser_payload["required_tests"]
                            ]
                            + [
                                {
                                    "title": "unrelated no-mock browser regression",
                                    "tests": [{"outcome": "unexpected"}],
                                }
                            ],
                        }
                    ],
                },
                sort_keys=True,
            )
            raw_report_path = root / "raw-playwright.json"
            raw_report_path.write_text(raw_report, encoding="utf-8")
            browser_payload["report_json"] = str(raw_report_path)
            browser_payload["report_sha256"] = hashlib.sha256(raw_report.encode("utf-8")).hexdigest()
            browser_payload["report_bytes"] = len(raw_report.encode("utf-8"))
            browser_payload["summary"] = {
                "total": len(browser_payload["required_tests"]),
                "passed": len(browser_payload["required_tests"]),
                "failed": 0,
                "skipped": 0,
            }
            browser_json = self._write_json(root / "browser.json", browser_payload)
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["browser_e2e"]["status"], "blocked")
            self.assertIn(
                "raw Playwright report unexpected=1",
                by_id["browser_e2e"]["failure_reasons"],
            )
            self.assertIn(
                "raw Playwright summary total=6 does not match artifact total=5",
                by_id["browser_e2e"]["failure_reasons"],
            )

    def test_completion_gate_blocks_browser_e2e_required_tests_from_wrong_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_payload = self._browser_e2e_payload("pass", db_path=db_path)
            raw_report = json.dumps(
                {
                    "stats": {"expected": len(browser_payload["required_tests"]), "unexpected": 0, "flaky": 0, "skipped": 0, "duration": 1},
                    "errors": [],
                    "suites": [
                        {
                            "title": "other-smoke.spec.ts",
                            "file": "tests/other-smoke.spec.ts",
                            "specs": [
                                {
                                    "title": item["title"],
                                    "file": "tests/other-smoke.spec.ts",
                                    "tests": [{"outcome": "expected"}],
                                }
                                for item in browser_payload["required_tests"]
                            ],
                        }
                    ],
                },
                sort_keys=True,
            )
            raw_report_path = root / "raw-playwright.json"
            raw_report_path.write_text(raw_report, encoding="utf-8")
            browser_payload["report_json"] = str(raw_report_path)
            browser_payload["report_sha256"] = hashlib.sha256(raw_report.encode("utf-8")).hexdigest()
            browser_payload["report_bytes"] = len(raw_report.encode("utf-8"))
            browser_payload["required_tests"] = [
                {**item, "file": "tests/other-smoke.spec.ts"}
                for item in browser_payload["required_tests"]
            ]
            browser_json = self._write_json(root / "browser.json", browser_payload)
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(by_id["browser_e2e"]["status"], "blocked")
            self.assertIn(
                "required browser e2e test source mismatch: acceptance page runs no-mock AQ01 through the real workbench API",
                by_id["browser_e2e"]["failure_reasons"],
            )
            self.assertIn(
                "raw Playwright report required browser e2e test source mismatch: acceptance page runs no-mock AQ01 through the real workbench API",
                by_id["browser_e2e"]["failure_reasons"],
            )

    def test_completion_gate_includes_in_app_browser_blocker_details(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            browser_json = self._write_json(
                root / "browser.json",
                {
                    "source": "asip.web.browser_gate_preflight",
                    "gate_status": "blocked",
                    "failure_reasons": ["local listen capability blocked: EPERM"],
                },
            )
            in_app_json = self._write_json(root / "in-app-browser.json", self._in_app_browser_payload())
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                browser_json=browser_json,
                in_app_browser_json=in_app_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(result["artifacts"]["in_app_browser"]["source"], "asip.web.in_app_browser_probe")
            self.assertEqual(by_id["browser_e2e"]["status"], "blocked")
            self.assertTrue(any("ERR_BLOCKED_BY_CLIENT" in reason for reason in by_id["browser_e2e"]["failure_reasons"]))
            self.assertIn(
                "in-app browser artifact source=asip.web.in_app_browser_probe is not no-mock browser e2e proof",
                by_id["browser_e2e"]["failure_reasons"],
            )

    def test_completion_gate_uses_real_browser_e2e_proof_over_supplemental_in_app_blocker(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(root / "browser.json", self._browser_e2e_payload("pass", db_path=db_path))
            in_app_json = self._write_json(root / "in-app-browser.json", self._in_app_browser_payload())
            no_server_json = self._write_json(root / "no-server.json", self._no_server_payload("pass"))
            performance_json = self._write_json(root / "performance.json", self._performance_payload("pass"))
            residual_json = self._write_json(root / "residual.json", self._residual_payload("pass"))
            git_json = self._write_json(root / "git.json", self._git_payload("pass"))

            result = run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                runtime_semantic_json=runtime_json,
                browser_json=browser_json,
                in_app_browser_json=in_app_json,
                no_server_json=no_server_json,
                performance_json=performance_json,
                residual_acceptance_json=residual_json,
                git_gate_json=git_json,
                minimum_counts=self._fixture_minimum_counts(),
            )

            by_id = {item["id"]: item for item in result["requirements"]}
            self.assertEqual(result["gate_status"], "pass")
            self.assertEqual(by_id["browser_e2e"]["status"], "pass")
            self.assertEqual(by_id["browser_e2e"]["failure_reasons"], [])

    def test_completion_gate_cli_writes_json_and_markdown_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(root / "web-acceptance.json", self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path))
            provider_json = self._write_json(root / "provider.json", self._provider_payload("pass", db_path=db_path))
            runtime_json = self._write_json(root / "runtime-semantic.json", self._runtime_semantic_payload("pass", db_path=db_path))
            browser_json = self._write_json(
                root / "browser.json",
                {"source": "asip.web.browser_e2e", "gate_status": "pass", "e2e_status": "pass"},
            )
            in_app_json = self._write_json(root / "in-app-browser.json", self._in_app_browser_payload())
            output_json = root / "completion.json"
            output_md = root / "completion.md"

            exit_code = cli_main(
                [
                    "completion-gate",
                    "--db",
                    str(db_path),
                    "--acceptance-json",
                    str(acceptance_json),
                    "--web-acceptance-json",
                    str(web_json),
                    "--provider-json",
                    str(provider_json),
                    "--runtime-semantic-json",
                    str(runtime_json),
                    "--browser-json",
                    str(browser_json),
                    "--in-app-browser-json",
                    str(in_app_json),
                    "--output-json",
                    str(output_json),
                    "--output-md",
                    str(output_md),
                ]
            )

            self.assertEqual(exit_code, 0)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["gate_status"], "blocked")
            self.assertEqual(payload["artifacts"]["in_app_browser"]["source"], "asip.web.in_app_browser_probe")
            self.assertEqual(payload["artifacts"]["runtime_semantic_freshness"]["source"], "asip.runtime_semantic_freshness_qa")
            self.assertIn("ASIP Current Completion Gate", output_md.read_text(encoding="utf-8"))

    def test_completion_gate_markdown_keeps_full_blocking_reasons(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = self._write_gate_db(root / "asip.db")
            acceptance_json = self._write_json(root / "acceptance.json", self._acceptance_payload(["CLI", "API", "MCP"], db_path=db_path))
            web_json = self._write_json(
                root / "web-acceptance.json",
                self._acceptance_payload(["CLI", "API", "Web", "MCP"], db_path=db_path, web_status="not_configured"),
            )
            long_reason = "Operation not permitted while backfilling provider embeddings for all expanded chunks"
            provider_json = self._write_json(
                root / "provider.json",
                {
                    "source": "asip.provider_gate",
                    "db_path": str(db_path),
                    "gate_status": "blocked",
                    "provider_checks": {
                        "embedding": {"status": "partial", "message": long_reason},
                        "embedding_live": {"status": "fail", "message": long_reason},
                        "semantic_edge_provenance": {
                            "status": "pass",
                            "message": "ok",
                            "latest_index_job_id": 1,
                            "latest_graph_rebuild_job_id": 2,
                        },
                        "semantic_edge": {"status": "fail", "message": long_reason},
                    },
                    "summary": {"total": 4, "passed": 1, "partial": 1, "failed": 2},
                },
            )
            browser_json = self._write_json(
                root / "browser.json",
                {
                    "source": "asip.web.browser_gate_preflight",
                    "gate_status": "blocked",
                    "failure_reasons": ["local listen capability blocked: EPERM"],
                },
            )
            output_md = root / "completion.md"

            run_completion_gate(
                db_path,
                acceptance_json=acceptance_json,
                web_acceptance_json=web_json,
                provider_json=provider_json,
                browser_json=browser_json,
                output_md=output_md,
                minimum_counts=self._fixture_minimum_counts(),
            )

            markdown = output_md.read_text(encoding="utf-8")
            self.assertIn(long_reason, markdown)
            self.assertNotIn("...", markdown)

    def _write_gate_db(self, db_path: Path) -> Path:
        with sqlite3.connect(db_path) as connection:
            connection.executescript(
                """
                create table corpora (
                    id text primary key,
                    status text not null default 'indexed'
                );
                create table documents (
                    id integer primary key,
                    corpus_id text not null,
                    source_type text not null,
                    path text not null
                );
                create table chunks (
                    id integer primary key,
                    document_id integer not null references documents(id),
                    text text not null,
                    line_start integer,
                    line_end integer,
                    page integer
                );
                create table evidence (id integer primary key);
                create table edges (id integer primary key);
                create table embeddings (id integer primary key);
                create table jobs (
                    id integer primary key,
                    kind text not null,
                    status text not null,
                    message text not null default '',
                    metadata_json text not null default '{}',
                    started_at text not null default current_timestamp,
                    finished_at text
                );
                insert into corpora (id, status) values ('linux-amdgpu', 'indexed');
                insert into documents values (1, 'linux-amdgpu', 'register', 'drivers/gpu/drm/amd/include/asic_reg/reg.h');
                insert into chunks values (1, 1, 'text', 1, 1, null);
                insert into evidence values (1);
                insert into edges values (1);
                insert into embeddings values (1);
                insert into jobs (id, kind, status) values (1, 'index', 'succeeded');
                insert into jobs (id, kind, status) values (2, 'graph_rebuild', 'succeeded');
                insert into jobs (id, kind, status) values (3, 'semantic_edges_batch', 'succeeded');
                insert into jobs (id, kind, status) values (4, 'doc_nodes_batch', 'succeeded');
                """
            )
        return db_path

    def _write_json(self, path: Path, payload):
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def _acceptance_payload(self, surfaces, *, db_path, web_status="pass", query_ids=None):
        surfaces = list(surfaces)
        if "API" in surfaces and "API_LIVE" not in surfaces:
            surfaces.insert(surfaces.index("API") + 1, "API_LIVE")
        if "MCP" in surfaces and "MCP_PROTOCOL" not in surfaces:
            surfaces.insert(surfaces.index("MCP") + 1, "MCP_PROTOCOL")
        query_ids = query_ids or [f"AQ{index:02d}" for index in range(1, 10)]
        queries = []
        passed = 0
        failed = 0
        for query_id in query_ids:
            surface_results = []
            for surface in surfaces:
                status = web_status if surface == "Web" else "pass"
                transport = f"{surface.lower()}.query"
                if surface == "Web":
                    transport = "next-bff.query"
                elif surface == "API_LIVE":
                    transport = "fastapi.uvicorn.http.query"
                elif surface == "MCP_PROTOCOL":
                    transport = "mcp.stdio.protocol.search_evidence"
                surface_results.append(
                    {
                        "surface": surface,
                        "transport": transport,
                        "db_path": str(db_path),
                        "status": status,
                        "message": "ok" if status == "pass" else "ASIP_WEB_BASE_URL is not configured",
                        "row_count": 1 if status == "pass" else 0,
                        "graph_node_count": 1 if status == "pass" else 0,
                        "graph_edge_count": 1 if status == "pass" else 0,
                        "server_registered": True if surface == "MCP_PROTOCOL" else None,
                        "base_url": "http://127.0.0.1:8124" if surface == "API_LIVE" else None,
                        "url": (
                            f"http://127.0.0.1:8124/query?db_path={db_path}&compact_graph=true"
                            if surface == "API_LIVE"
                            else None
                        ),
                        "endpoint": "/query" if surface == "API_LIVE" else None,
                        "command": "/usr/bin/python3" if surface == "MCP_PROTOCOL" else None,
                        "server_args": ["-m", "apps.mcp.server"] if surface == "MCP_PROTOCOL" else None,
                        "tool": "search_evidence" if surface == "MCP_PROTOCOL" else None,
                    }
                )
            query_status = "pass" if all(result["status"] == "pass" for result in surface_results) else "fail"
            if query_status == "pass":
                passed += 1
            else:
                failed += 1
            queries.append(
                {
                    "id": query_id,
                    "status": query_status,
                    "schema_status": "pass",
                    "schema_failure_reasons": [],
                    "surface_results": surface_results,
                    "provider_checks": self._provider_payload("pass", db_path=db_path)["provider_checks"] if query_id == "AQ09" else {},
                }
            )
        return {
            "source": "asip.acceptance",
            "db_path": str(db_path),
            "gate_status": "pass" if failed == 0 else "blocked",
            "database_health": {"status": "pass", "failure_reasons": []},
            "surfaces_checked": surfaces,
            "summary": {
                "total": len(query_ids),
                "passed": passed,
                "partial": 0,
                "failed": failed,
            },
            "queries": queries,
        }

    def _provider_payload(self, gate_status, *, db_path):
        if gate_status == "pass":
            checks = {
                "embedding": {"status": "pass", "message": "ok"},
                "embedding_live": {"status": "pass", "message": "ok"},
                "semantic_edge_provenance": {
                    "status": "pass",
                    "message": "ok",
                    "edge_count": 1,
                    "job_ids": [3],
                    "stale_edge_count": 0,
                    "latest_index_job_id": 1,
                    "latest_graph_rebuild_job_id": 2,
                },
                "doc_node_provenance": {
                    "status": "pass",
                    "message": "ok",
                    "edge_count": 1,
                    "job_ids": [4],
                    "latest_index_job_id": 1,
                    "latest_graph_rebuild_job_id": 2,
                    "stale_edge_count": 0,
                },
                "semantic_edge": {"status": "pass", "message": "ok"},
            }
            summary = {"total": 5, "passed": 5, "partial": 0, "failed": 0}
        else:
            checks = {
                "embedding": {"status": "partial", "message": "fallback embeddings remain"},
                "embedding_live": {"status": "fail", "message": "Operation not permitted"},
                "semantic_edge_provenance": {
                    "status": "partial",
                    "message": "stale semantic edges",
                    "latest_index_job_id": 1,
                    "latest_graph_rebuild_job_id": 2,
                },
                "doc_node_provenance": {
                    "status": "partial",
                    "message": "stale doc-node semantic edges",
                    "latest_index_job_id": 1,
                    "latest_graph_rebuild_job_id": 2,
                    "stale_edge_count": 1,
                },
                "semantic_edge": {"status": "fail", "message": "Operation not permitted"},
            }
            summary = {"total": 5, "passed": 0, "partial": 3, "failed": 2}
        return {
            "source": "asip.provider_gate",
            "db_path": str(db_path),
            "gate_status": gate_status,
            "provider_checks": checks,
            "summary": summary,
        }

    def test_provider_payload_helper_tracks_required_provider_check_ids(self):
        checks = self._provider_payload("pass", db_path=Path("/tmp/asip.db"))["provider_checks"]

        self.assertEqual(tuple(checks), PROVIDER_CHECK_IDS)

    def _runtime_semantic_payload(self, gate_status, *, db_path):
        check_ids = [
            "storage_runtime_stale_semantic_filter",
            "storage_runtime_fresh_semantic_keep",
            "storage_runtime_fresh_doc_node_keep",
            "storage_runtime_extractor_job_kind_binding",
            "storage_runtime_provider_mismatch_filter",
            "real_db_global_graph_semantic_leak_probe",
            "real_db_query_graph_semantic_leak_probe",
        ]
        checks = [{"id": check_id, "status": "pass", "message": "ok"} for check_id in check_ids]
        if gate_status != "pass":
            checks[0]["status"] = "fail"
            checks[0]["message"] = "stale semantic rows leaked"
        passed = sum(1 for check in checks if check["status"] == "pass")
        return {
            "source": "asip.runtime_semantic_freshness_qa",
            "db_path": str(db_path),
            "latest_index_job_id": 1,
            "latest_graph_rebuild_job_id": 2,
            "latest_semantic_edges_job_id": 3,
            "latest_doc_nodes_job_id": 4,
            "gate_status": gate_status,
            "summary": {"checks": len(checks), "passed": passed, "failed": len(checks) - passed},
            "checks": checks,
        }

    def _semantic_quality_payload(self, gate_status, *, db_path):
        case_status = "pass" if gate_status == "pass" else "fail"
        return {
            "source": "asip.semantic_quality_eval",
            "db_path": str(db_path),
            "gate_status": gate_status,
            "summary": {
                "total": 2,
                "passed": 2 if gate_status == "pass" else 1,
                "failed": 0 if gate_status == "pass" else 1,
                "provider_vector_cases": 1,
                "graph_target_cases": 1,
                "mean_reciprocal_rank": 1.0,
            },
            "cases": [
                {"id": "SQ01", "status": "pass", "row_count": 1},
                {"id": "SQ02", "status": case_status, "row_count": 1 if gate_status == "pass" else 0},
            ],
        }

    def _callback_audit_payload(self, gate_status, *, db_path):
        return {
            "source": "asip.callback_edge_audit",
            "db_path": str(db_path),
            "gate_status": gate_status,
            "failure_reasons": [] if gate_status == "pass" else ["unexplained ambiguous callback fanout exceeds 2"],
            "summary": {
                "callback_edge_count": 3,
                "ambiguous_callback_edge_count": 3,
                "explained_dynamic_dispatch_edge_count": 3 if gate_status == "pass" else 1,
                "unexplained_ambiguous_callback_edge_count": 0 if gate_status == "pass" else 2,
                "unique_ambiguous_callers": 1,
                "unique_unexplained_ambiguous_callers": 0 if gate_status == "pass" else 1,
                "parser_pollution_candidate_count": 0,
                "real_oracle_total": 3,
                "real_oracle_passed": 3 if gate_status == "pass" else 2,
            },
        }

    def _browser_e2e_payload(self, gate_status, *, db_path):
        required_tests = [
            {
                "title": "acceptance page runs no-mock AQ01 through the real workbench API",
                "status": "pass",
                "file": "tests/workbench-smoke.spec.ts",
            },
            {
                "title": "graph page uses URL dbPath for no-mock graph and query requests",
                "status": "pass",
                "file": "tests/workbench-smoke.spec.ts",
            },
            {
                "title": "graph page loads current data/asip.db through browser and API",
                "status": "pass",
                "file": "tests/workbench-smoke.spec.ts",
            },
            {
                "title": "graph page filters no-mock graph layers and shows edge provenance",
                "status": "pass",
                "file": "tests/workbench-smoke.spec.ts",
            },
            {
                "title": "evidence page initial query uses URL dbPath without default DB fallback",
                "status": "pass",
                "file": "tests/workbench-smoke.spec.ts",
            },
        ]
        if gate_status != "pass":
            required_tests[0]["status"] = "fail"
        passed = len([item for item in required_tests if item["status"] == "pass"])
        raw_report = json.dumps(
            {
                "stats": {
                    "expected": passed,
                    "unexpected": len(required_tests) - passed,
                    "flaky": 0,
                    "skipped": 0,
                    "duration": 1,
                },
                "suites": [
                    {
                        "title": "workbench-smoke.spec.ts",
                        "file": "tests/workbench-smoke.spec.ts",
                        "specs": [
                            {
                                "title": item["title"],
                                "file": "tests/workbench-smoke.spec.ts",
                                "tests": [{"outcome": "expected" if item["status"] == "pass" else "unexpected"}],
                            }
                            for item in required_tests
                        ],
                    }
                ],
            },
            sort_keys=True,
        )
        report = Path(tempfile.NamedTemporaryFile(prefix="asip-browser-e2e-", suffix=".json", delete=False).name)
        report.write_text(raw_report, encoding="utf-8")
        return {
            "source": "asip.web.browser_e2e",
            "gate_status": gate_status,
            "e2e_status": gate_status,
            "db_path": str(db_path),
            "latest_index_job_id": 1,
            "latest_graph_rebuild_job_id": 2,
            "target_urls": [f"http://127.0.0.1:3100/graph?dbPath={db_path}"],
            "command": ["pnpm", "exec", "playwright", "test", "--reporter=json"],
            "report_json": str(report),
            "report_sha256": hashlib.sha256(raw_report.encode("utf-8")).hexdigest(),
            "report_bytes": len(raw_report.encode("utf-8")),
            "summary": {"total": len(required_tests), "passed": passed, "failed": len(required_tests) - passed, "skipped": 0},
            "required_tests": required_tests,
            "current_db_probes": [
                {
                    "surface": "graph_page_api_request",
                    "url": f"http://127.0.0.1:3100/api/workbench/graph?dbPath={db_path}",
                    "db_path": str(db_path),
                    "status": 200,
                    "node_count": 2,
                    "edge_count": 1,
                    "response_sha256": "a" * 64,
                    "latest_index_job_id": 1,
                    "latest_graph_rebuild_job_id": 2,
                },
                {
                    "surface": "direct_api_document_request",
                    "url": f"http://127.0.0.1:3100/api/workbench/graph?dbPath={db_path}",
                    "db_path": str(db_path),
                    "status": 200,
                    "node_count": 2,
                    "edge_count": 1,
                    "response_sha256": "b" * 64,
                    "latest_index_job_id": 1,
                    "latest_graph_rebuild_job_id": 2,
                },
                {
                    "surface": "graph_page_concept_detail_selection",
                    "url": f"http://127.0.0.1:3100/graph?dbPath={db_path}",
                    "db_path": str(db_path),
                    "status": 200,
                    "node_count": 2,
                    "edge_count": 1,
                    "response_sha256": "c" * 64,
                    "latest_index_job_id": 1,
                    "latest_graph_rebuild_job_id": 2,
                    "selected_node_id": "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gfx_hw_init",
                    "selected_kind": "function",
                    "selected_label": "gfx_hw_init",
                    "implementation_count": 2,
                    "listed_implementation_count": 2,
                    "raw_implementation_record_count": 3,
                    "selected_implementation": "gfx_v11_0_hw_init",
                    "detail_heading": "Concept Generated From",
                    "detail_truncated": False,
                },
            ],
            "failure_reasons": [] if gate_status == "pass" else ["browser e2e failed"],
        }

    def _fixture_minimum_counts(self):
        return {
            "documents": 1,
            "chunks": 1,
            "evidence": 1,
            "edges": 1,
            "embeddings": 1,
            "linux_amdgpu_documents": 1,
            "linux_amdgpu_chunks": 1,
            "linux_asic_reg_documents": 1,
        }

    def _no_server_payload(self, gate_status):
        checks = [
            {"label": "dbPath no-fallback route smoke", "status": "pass", "exit_code": 0},
            {"label": "current artifact invariants smoke", "status": "pass", "exit_code": 0},
        ]
        if gate_status != "pass":
            checks[-1]["status"] = "fail"
        passed = len([check for check in checks if check["status"] == "pass"])
        return {
            "source": "asip.web.no_server_smoke",
            "gate_status": gate_status,
            "summary": {"total": len(checks), "passed": passed, "failed": len(checks) - passed},
            "checks": checks,
            "failure_reasons": [] if gate_status == "pass" else ["current artifact invariants smoke failed"],
        }

    def _artifact_input(self, option, path, *, sha256=None):
        content = path.read_bytes()
        return {
            "option": option,
            "path": str(path),
            "resolved_path": str(path),
            "status": "loaded",
            "bytes": len(content),
            "sha256": hashlib.sha256(content).hexdigest() if sha256 is None else sha256,
        }

    def _performance_payload(self, gate_status):
        queries = [
            {
                "query": f"Q{index}",
                "under_threshold": True,
                "row_count": 1,
                "graph_runtime": "networkx",
            }
            for index in range(5)
        ]
        if gate_status != "pass":
            queries[0]["under_threshold"] = False
        return {
            "source": "fixture_performance_smoke",
            "deterministic_counts_match": gate_status == "pass",
            "all_queries_under_threshold": gate_status == "pass",
            "queries": queries,
        }

    def _residual_payload(self, gate_status):
        return {
            "source": "asip.residual_acceptance",
            "gate_status": gate_status,
            "accepted": gate_status == "pass",
            "accepted_residuals": ["full clangd/libclang cross-TU type-flow"],
        }

    def _git_payload(self, gate_status, *, repo_root=None, branch=None, head=None):
        return {
            "source": "asip.git_gate",
            "gate_status": gate_status,
            "repo_root": str(repo_root) if repo_root is not None else "",
            "branch": branch or "",
            "head": head or "",
            "diff_check": "pass" if gate_status == "pass" else "fail",
            "worktree_status": "clean" if gate_status == "pass" else "dirty",
            "committed": gate_status == "pass",
            "pushed": gate_status == "pass",
        }

    def _run_git(self, cwd, args):
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)

    def _in_app_browser_payload(self):
        return {
            "source": "asip.web.in_app_browser_probe",
            "gate_status": "blocked",
            "browser_surface": "codex-in-app-browser",
            "target_urls": [
                "http://127.0.0.1:3100/graph?dbPath=data/asip.db",
                "http://localhost:3100/graph?dbPath=data/asip.db",
            ],
            "attempts": [
                {
                    "url": "http://127.0.0.1:3100/graph?dbPath=data/asip.db",
                    "ok": False,
                    "message": "Browser reported: net::ERR_BLOCKED_BY_CLIENT",
                }
            ],
            "failure_reasons": [
                "in-app browser cannot open http://127.0.0.1:3100/graph: net::ERR_BLOCKED_BY_CLIENT"
            ],
        }


if __name__ == "__main__":
    unittest.main()
