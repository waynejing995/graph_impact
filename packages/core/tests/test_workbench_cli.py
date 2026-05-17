import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from workbench_fixture import write_live_fixture


class WorkbenchCliTests(unittest.TestCase):
    def test_graph_command_uses_configured_budget_unless_user_requests_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            budget_path = root / "graph-budget.json"
            budget_path.write_text(json.dumps({"globalGraph": {"edgeBudget": 1, "evidenceRowCap": 0}}), encoding="utf-8")
            common = [sys.executable, "-m", "asip.cli"]

            setup = (
                "from asip.storage import AsipStore;"
                f"store=AsipStore.connect({str(db_path)!r});"
                "store.migrate();"
                "store.add_edge('program_a','GCVM_L2_CNTL','reads',0.99);"
                "store.add_edge('program_b','CP_INT_CNTL_RING0','writes',0.98)"
            )
            subprocess.run([sys.executable, "-c", setup], check=True, capture_output=True, text=True)

            configured = subprocess.run(
                [*common, "graph", "--db", str(db_path), "--budget-config", str(budget_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            all_edges = subprocess.run(
                [*common, "graph", "--db", str(db_path), "--budget-config", str(budget_path), "--all"],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertEqual(len(json.loads(configured.stdout)["edges"]), 1)
            self.assertEqual(len(json.loads(all_edges.stdout)["edges"]), 2)

    def test_index_query_and_graph_commands_use_live_sqlite_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path, _corpus_root = write_live_fixture(root)
            db_path = root / "asip.db"
            common = [sys.executable, "-m", "asip.cli"]

            index = subprocess.run(
                [*common, "index", "--config", str(config_path), "--db", str(db_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            query = subprocess.run(
                [*common, "query", "--db", str(db_path), "--q", "doorbell interrupt disable"],
                check=True,
                capture_output=True,
                text=True,
            )
            graph = subprocess.run(
                [*common, "graph", "--db", str(db_path), "--seed", "BIF_DOORBELL_INT_CNTL", "--hops", "1"],
                check=True,
                capture_output=True,
                text=True,
            )

            index_payload = json.loads(index.stdout)
            query_payload = json.loads(query.stdout)
            graph_payload = json.loads(graph.stdout)

            self.assertEqual(index_payload["source"], "raw_corpus")
            self.assertEqual(query_payload["source"], "sqlite")
            self.assertTrue(any(row["symbol"] == "DOORBELL_INTERRUPT_DISABLE" for row in query_payload["rows"]))
            self.assertTrue(any(edge["dst"].endswith(":BIF_DOORBELL_INT_CNTL") for edge in graph_payload["edges"]))
            self.assertTrue(
                any("DOORBELL_INTERRUPT_DISABLE" in edge.get("attr", {}).get("fields", []) for edge in graph_payload["edges"])
            )

    def test_graph_rebuild_command_restores_stage1_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "mxgpu"
            source_root.mkdir()
            (source_root / "gfx.c").write_text(
                "\n".join(
                    [
                        "typedef unsigned int uint32_t;",
                        "static void cli_program_cache(uint32_t data) {",
                        "  WREG32(regGCVM_L2_CNTL, data);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            db_path = root / "asip.db"
            setup = (
                "from asip.storage import AsipStore;"
                f"store=AsipStore.connect({str(db_path)!r});"
                "store.migrate();"
                f"store.upsert_corpus('mxgpu','local',{str(source_root)!r},['**/*.c'],status='indexed',file_count=1)"
            )
            subprocess.run([sys.executable, "-c", setup], check=True, capture_output=True, text=True)

            rebuild = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "asip.cli",
                    "graph-rebuild",
                    "--db",
                    str(db_path),
                    "--corpus-id",
                    "mxgpu",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(rebuild.stdout)
            self.assertEqual(payload["source"], "deterministic_graph_rebuild")
            self.assertEqual(payload["files"], 1)
            self.assertGreaterEqual(payload["edges"], 1)

    def test_index_command_accepts_explicit_source_root_override(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path, corpus_root = write_live_fixture(root)
            override_root = root / "override-mxgpu"
            corpus_root.rename(override_root)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["corpora"][0]["default_source_root"] = str(root / "missing-mxgpu")
            config_path.write_text(json.dumps(config), encoding="utf-8")
            db_path = root / "asip.db"
            common = [sys.executable, "-m", "asip.cli"]

            index = subprocess.run(
                [
                    *common,
                    "index",
                    "--config",
                    str(config_path),
                    "--db",
                    str(db_path),
                    "--source-root",
                    f"mxgpu={override_root}",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            index_payload = json.loads(index.stdout)
            self.assertEqual(index_payload["source"], "raw_corpus")
            self.assertGreater(index_payload["documents"], 0)

    def test_acceptance_command_writes_json_and_markdown_artifacts(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path, _corpus_root = write_live_fixture(root)
            db_path = root / "asip.db"
            output_json = root / "acceptance.json"
            output_md = root / "acceptance.md"
            common = [sys.executable, "-m", "asip.cli"]

            subprocess.run(
                [*common, "index", "--config", str(config_path), "--db", str(db_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            acceptance = subprocess.run(
                [
                    *common,
                    "acceptance",
                    "--db",
                    str(db_path),
                    "--output-json",
                    str(output_json),
                    "--output-md",
                    str(output_md),
                    "--surface",
                    "CLI",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            summary = json.loads(acceptance.stdout)
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(summary["total"], 9)
            self.assertEqual(payload["summary"]["total"], 9)
            self.assertTrue(output_md.read_text(encoding="utf-8").startswith("# ASIP Acceptance Query Run"))

    def test_acceptance_command_can_filter_query_and_print_full_payload(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path, _corpus_root = write_live_fixture(root)
            db_path = root / "asip.db"
            common = [sys.executable, "-m", "asip.cli"]

            subprocess.run(
                [*common, "index", "--config", str(config_path), "--db", str(db_path)],
                check=True,
                capture_output=True,
                text=True,
            )
            acceptance = subprocess.run(
                [
                    *common,
                    "acceptance",
                    "--db",
                    str(db_path),
                    "--query-id",
                    "AQ01",
                    "--surface",
                    "CLI",
                    "--surface",
                    "API",
                    "--surface",
                    "Web",
                    "--surface",
                    "MCP",
                    "--full",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            payload = json.loads(acceptance.stdout)
            self.assertEqual(payload["source"], "asip.acceptance")
            self.assertEqual(payload["summary"]["total"], 1)
            self.assertEqual(payload["queries"][0]["id"], "AQ01")
            self.assertEqual(payload["queries"][0]["missing_surfaces"], [])
            self.assertEqual(payload["surfaces_checked"], ["CLI", "API", "Web", "MCP"])


if __name__ == "__main__":
    unittest.main()
