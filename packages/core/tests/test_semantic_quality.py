import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from asip.semantic_quality import run_semantic_quality_eval
from asip.storage import AsipStore


class SemanticQualityTests(unittest.TestCase):
    def test_semantic_quality_eval_passes_labeled_provider_vector_case(self):
        class QueryEmbeddingTransport:
            def post_json(self, url, payload, headers, timeout):
                return {"embeddings": [[1.0, 0.0]]}

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            eval_set = root / "eval.jsonl"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.save_provider_settings(
                {
                    "embedding": {
                        "provider": "ollama",
                        "model": "provider-rerank",
                        "api_base_url": "http://localhost:11434",
                        "api_path": "/api/embed",
                    }
                }
            )
            doc = store.add_document("fixture", "doc", "docs/provider.md")
            chunk = store.add_chunk(doc, "provider semantic evidence", 1, 1)
            store.add_evidence(
                chunk,
                "fixture",
                "doc",
                "local",
                "docs/provider.md",
                "REG_PROVIDER_QUALITY",
                "register",
                "mention",
                0.75,
                "provider semantic evidence",
                "provider vector -> REG_PROVIDER_QUALITY",
                line_start=1,
                line_end=1,
            )
            store.add_embedding(
                chunk,
                provider="ollama",
                model="provider-rerank",
                vector=[1.0, 0.0],
                metadata={"source": "provider"},
            )
            eval_set.write_text(
                json.dumps(
                    {
                        "id": "SQ_UNIT",
                        "query": "semantic nearest lookup",
                        "limit": 5,
                        "min_rows": 1,
                        "expected_symbols_any": ["REG_PROVIDER_QUALITY"],
                        "expected_source_types": ["doc"],
                        "required_retrieval_sources": ["provider-vector"],
                        "min_provider_vector_rows": 1,
                        "expected_query_embedding_source": "provider",
                        "max_expected_rank": 1,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = run_semantic_quality_eval(
                db_path,
                eval_set,
                embedding_transport=QueryEmbeddingTransport(),
            )

            self.assertEqual(result["gate_status"], "pass")
            self.assertEqual(result["summary"]["passed"], 1)
            self.assertEqual(result["summary"]["mean_reciprocal_rank"], 1.0)
            self.assertEqual(result["cases"][0]["provider_vector_rows"], 1)

    def test_semantic_quality_cli_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            eval_set = root / "eval.jsonl"
            output_json = root / "quality.json"
            output_md = root / "quality.md"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            doc = store.add_document("fixture", "code", "driver.c")
            chunk = store.add_chunk(doc, "GCVM_L2_CNTL setup", 1, 1)
            store.add_evidence(
                chunk,
                "fixture",
                "code",
                "local",
                "driver.c",
                "GCVM_L2_CNTL",
                "register",
                "mention",
                0.9,
                "GCVM_L2_CNTL setup",
                "source mention -> GCVM_L2_CNTL",
                line_start=1,
                line_end=1,
            )
            eval_set.write_text(
                json.dumps(
                    {
                        "id": "SQ_CLI",
                        "query": "GCVM_L2_CNTL",
                        "limit": 5,
                        "expected_symbols_any": ["GCVM_L2_CNTL"],
                        "expected_source_types": ["code"],
                        "required_retrieval_sources": ["fts5", "lexical"],
                        "expected_query_embedding_source": "skipped-symbol-token",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "asip.cli",
                    "semantic-quality",
                    "--db",
                    str(db_path),
                    "--eval-set",
                    str(eval_set),
                    "--output-json",
                    str(output_json),
                    "--output-md",
                    str(output_md),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertEqual(json.loads(result.stdout)["passed"], 1)
            self.assertEqual(json.loads(output_json.read_text(encoding="utf-8"))["gate_status"], "pass")
            self.assertIn("# Semantic Quality Evaluation", output_md.read_text(encoding="utf-8"))

    def test_semantic_quality_eval_checks_expected_graph_nodes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            eval_set = root / "eval.jsonl"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            doc = store.add_document("fixture", "code", "driver.c")
            chunk = store.add_chunk(doc, "writer touches CP HQD", 1, 1)
            store.add_evidence(
                chunk,
                "fixture",
                "code",
                "local",
                "driver.c",
                "hqd_writer",
                "function",
                "mention",
                0.9,
                "hqd_writer touches CP HQD",
                "source mention -> hqd_writer",
                line_start=1,
                line_end=1,
            )
            store.add_edge(
                "hqd_writer",
                "CP_HQD_ACTIVE",
                "writes",
                0.9,
                path="driver.c",
                line_start=1,
                line_end=1,
            )
            eval_set.write_text(
                json.dumps(
                    {
                        "id": "SQ_GRAPH",
                        "query": "hqd_writer",
                        "limit": 5,
                        "expected_symbols_any": ["hqd_writer"],
                        "expected_graph_node_terms_all": ["CP_HQD_ACTIVE"],
                        "expected_graph_node_kinds": ["register"],
                        "min_graph_nodes": 2,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            result = run_semantic_quality_eval(db_path, eval_set)

            self.assertEqual(result["gate_status"], "pass")
            self.assertEqual(result["summary"]["graph_target_cases"], 1)
            self.assertTrue(result["cases"][0]["expected_graph_node_terms_found"]["CP_HQD_ACTIVE"])
