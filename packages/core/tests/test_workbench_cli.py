import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from workbench_fixture import write_live_fixture


class WorkbenchCliTests(unittest.TestCase):
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
                [*common, "graph", "--db", str(db_path), "--seed", "DOORBELL_INTERRUPT_DISABLE", "--hops", "1"],
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
            self.assertTrue(any(edge["dst"] == "DOORBELL_INTERRUPT_DISABLE" for edge in graph_payload["edges"]))

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
