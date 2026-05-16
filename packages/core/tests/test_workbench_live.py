import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from asip.storage import AsipStore
from asip import workbench
from asip.workbench import (
    add_corpus,
    expand_query_graph,
    generate_semantic_edges_for_query,
    index_configured_corpora,
    index_registered_corpora,
    query_evidence,
    save_provider_settings,
)

from workbench_fixture import write_live_fixture


class FakeSemanticEdgeProvider:
    def generate(self, prompt, model):
        self.prompt = prompt
        return {
            "cases": [
                {
                    "id": "workbench-query",
                    "edges": [
                        {
                            "src": "GCVM_L2_CNTL",
                            "relation": "sets_field",
                            "dst": "ENABLE_L2_CACHE",
                            "confidence": 0.91,
                            "evidence": "fixture",
                        }
                    ],
                }
            ]
        }


class WorkbenchLiveTests(unittest.TestCase):
    def test_indexes_raw_corpus_files_and_queries_schema_from_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path, _corpus_root = write_live_fixture(root)
            db_path = root / "asip.db"

            summary = index_configured_corpora(config_path, db_path)
            result = query_evidence(db_path, "doorbell interrupt disable")
            graph = expand_query_graph(db_path, "DOORBELL_INTERRUPT_DISABLE", hops=1)

            self.assertEqual(summary["source"], "raw_corpus")
            self.assertEqual(summary["documents"], 3)
            self.assertGreaterEqual(summary["chunks"], 3)
            self.assertGreaterEqual(summary["evidence"], 2)
            self.assertGreaterEqual(summary["edges"], 1)
            self.assertEqual(result["query"], "doorbell interrupt disable")
            self.assertGreaterEqual(len(result["rows"]), 2)
            row = next(item for item in result["rows"] if item["symbol"] == "DOORBELL_INTERRUPT_DISABLE")
            self.assertEqual(row["source_type"], "code")
            self.assertEqual(row["repo"], "local-fixture")
            self.assertEqual(row["path"], "libgv/core/hw/AI/mi200/nbio_v7_4.c")
            self.assertEqual(row["entity_type"], "field")
            self.assertEqual(row["access_type"], "field_set")
            self.assertIn("REG_SET_FIELD", row["resolved_chain"])
            self.assertIn("snippet", row)
            self.assertTrue(any(item["source_type"] == "pdf" and item["page"] == 1 for item in result["rows"]))
            self.assertTrue(any(edge["dst"] == "DOORBELL_INTERRUPT_DISABLE" for edge in graph["edges"]))

            con = sqlite3.connect(db_path)
            self.assertEqual(con.execute("select count(*) from corpora").fetchone()[0], 1)
            self.assertEqual(con.execute("select count(*) from jobs where status = 'indexed'").fetchone()[0], 1)

    def test_configured_index_includes_non_query_docs_and_pdfs_from_globs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path, corpus_root = write_live_fixture(root)
            db_path = root / "asip.db"
            (corpus_root / "docs" / "driver-overview.md").write_text(
                "AMDGPU documentation connects the driver source tree to scheduler behavior.",
                encoding="utf-8",
            )
            (corpus_root / "docs" / "driver-overview.pdf").write_text(
                "%PDF-1.4\nBT\n(AMDGPU PDF documentation connects driver source tree evidence) Tj\nET\n",
                encoding="latin-1",
            )

            summary = index_configured_corpora(config_path, db_path)
            result = query_evidence(db_path, "AMDGPU documentation driver source tree")

            source_types = {row["source_type"] for row in result["rows"]}
            source_paths = {row["path"] for row in result["rows"]}
            self.assertGreaterEqual(summary["documents"], 5)
            self.assertIn("doc", source_types)
            self.assertIn("pdf", source_types)
            self.assertIn("docs/driver-overview.md", source_paths)
            self.assertIn("docs/driver-overview.pdf", source_paths)
            pdf_symbols = {row["symbol"] for row in result["rows"] if row["source_type"] == "pdf"}
            self.assertNotIn("BT", pdf_symbols)
            self.assertNotIn("ET", pdf_symbols)

    def test_generated_register_headers_are_indexed_as_register_source_type(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path, corpus_root = write_live_fixture(root)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["corpora"][0]["include"].append("**/*.h")
            config_path.write_text(json.dumps(config), encoding="utf-8")
            db_path = root / "asip.db"
            register_dir = corpus_root / "include" / "asic_reg"
            register_dir.mkdir(parents=True)
            (register_dir / "gc_11_0_0_offset.h").write_text(
                "#define regGCVM_L2_CNTL 0x1430\n#define GCVM_L2_CNTL_BASE_IDX 0\n",
                encoding="utf-8",
            )
            (register_dir / "gc_11_0_0_sh_mask.h").write_text(
                "#define GCVM_L2_CNTL__ENABLE_L2_CACHE__SHIFT 0x0\n"
                "#define GCVM_L2_CNTL__ENABLE_L2_CACHE_MASK 0x00000001L\n",
                encoding="utf-8",
            )

            index_configured_corpora(config_path, db_path)
            result = query_evidence(db_path, "regGCVM_L2_CNTL ENABLE_L2_CACHE", limit=12)

            register_rows = [row for row in result["rows"] if row["source_type"] == "register"]
            self.assertTrue(register_rows, result["rows"])
            self.assertTrue(any(row["path"].endswith("_offset.h") for row in register_rows))
            self.assertTrue(any(row["path"].endswith("_sh_mask.h") for row in register_rows))

    def test_configured_index_missing_source_root_fails_instead_of_indexed_zero_docs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            missing_root = root / "missing-source"
            config_path = root / "missing-corpus.json"
            db_path = root / "asip.db"
            config_path.write_text(
                json.dumps(
                    {
                        "name": "missing-corpus-fixture",
                        "model": {"preferred": "fixture-edge", "fallback": ""},
                        "corpora": [
                            {
                                "id": "missing-corpus",
                                "repo": "local-fixture",
                                "default_source_root": str(missing_root),
                                "include": ["**/*.c", "**/*.md"],
                            }
                        ],
                        "queries": [
                            {
                                "id": "missing-query",
                                "corpus": "missing-corpus",
                                "question": "Where is MISSING_REGISTER referenced?",
                                "terms": ["MISSING_REGISTER"],
                                "expected_terms": ["MISSING_REGISTER"],
                                "max_snippets": 1,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(FileNotFoundError):
                index_configured_corpora(config_path, db_path)

            con = sqlite3.connect(db_path)
            self.assertEqual(con.execute("select status from jobs order by id desc limit 1").fetchone()[0], "failed")
            corpus = con.execute(
                "select status, file_count, metadata_json from corpora where id = 'missing-corpus'"
            ).fetchone()
            self.assertIsNotNone(corpus)
            self.assertEqual(corpus[0], "failed")
            self.assertEqual(corpus[1], 0)
            self.assertIn("source root not found", corpus[2])

    def test_expand_query_graph_uses_networkx_runtime_for_weighted_hops(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.add_edge("GCVM_L2_CNTL", "ENABLE_L2_CACHE", "has_field", 0.98)
            store.add_edge("ENABLE_L2_CACHE", "gmc_v11_0_init_golden_registers", "used_by", 0.84)
            store.add_edge("gmc_v11_0_init_golden_registers", "OUT_OF_SCOPE", "calls", 0.12)

            graph = expand_query_graph(db_path, "GCVM_L2_CNTL", hops=2)

            self.assertEqual(graph["source"], "networkx")
            self.assertEqual(graph["graph_runtime"], "networkx")
            edges = {(edge["src"], edge["dst"]): edge for edge in graph["edges"]}
            self.assertEqual(edges[("GCVM_L2_CNTL", "ENABLE_L2_CACHE")]["weight"], 0.98)
            self.assertEqual(edges[("ENABLE_L2_CACHE", "gmc_v11_0_init_golden_registers")]["weight"], 0.84)
            self.assertNotIn(("gmc_v11_0_init_golden_registers", "OUT_OF_SCOPE"), edges)

    def test_global_graph_returns_weighted_edges_without_seed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.add_edge("API_GLOBAL_REGISTER", "API_GLOBAL_FIELD", "sets_field", 0.99)
            store.add_edge("API_GLOBAL_REGISTER", "API_GLOBAL_DOC", "documented_by", 0.87)
            store.add_edge("LOW_CONFIDENCE_REGISTER", "LOW_CONFIDENCE_FIELD", "mentions", 0.11)

            graph = workbench.global_graph(db_path, limit=2)

            self.assertIn(graph["source"], {"networkx", "sqlite"})
            self.assertIn(graph["graph_runtime"], {"networkx", "sqlite"})
            self.assertEqual([edge["confidence"] for edge in graph["edges"]], [0.99, 0.87])
            self.assertEqual([edge["weight"] for edge in graph["edges"]], [0.99, 0.87])
            self.assertEqual(
                {node["id"] for node in graph["nodes"]},
                {"API_GLOBAL_REGISTER", "API_GLOBAL_FIELD", "API_GLOBAL_DOC"},
            )
            self.assertNotIn(
                ("LOW_CONFIDENCE_REGISTER", "LOW_CONFIDENCE_FIELD"),
                {(edge["src"], edge["dst"]) for edge in graph["edges"]},
            )

    def test_semantic_edge_job_generates_edges_from_indexed_evidence_and_provider_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            corpus_root = root / "docs"
            corpus_root.mkdir()
            (corpus_root / "note.md").write_text(
                "GCVM_L2_CNTL has field ENABLE_L2_CACHE in the indexed workbench document.",
                encoding="utf-8",
            )
            save_provider_settings(
                db_path,
                {
                    "edge": {
                        "provider": "ollama",
                        "base_url": "http://edge.local",
                        "api_path": "/api/chat",
                        "model": "gemma4:e4b",
                        "timeout_seconds": 2,
                    }
                },
            )
            add_corpus(db_path, "edge-docs", "local", str(corpus_root), ["**/*.md"], "doc")
            index_registered_corpora(db_path, corpus_ids=["edge-docs"])
            provider = FakeSemanticEdgeProvider()

            summary = generate_semantic_edges_for_query(
                db_path,
                "GCVM_L2_CNTL ENABLE_L2_CACHE",
                edge_provider=provider,
            )
            graph = expand_query_graph(db_path, "GCVM_L2_CNTL")

            self.assertEqual(summary["source"], "semantic_edge_job")
            self.assertEqual(summary["provider"], "ollama")
            self.assertEqual(summary["model"], "gemma4:e4b")
            self.assertEqual(summary["edge_count"], 1)
            self.assertIn("GCVM_L2_CNTL", provider.prompt)
            self.assertIn("ENABLE_L2_CACHE", provider.prompt)
            self.assertIn(
                ("GCVM_L2_CNTL", "sets_field", "ENABLE_L2_CACHE"),
                {(edge["src"], edge["relation"], edge["dst"]) for edge in graph["edges"]},
            )


if __name__ == "__main__":
    unittest.main()
