import json
import tempfile
import unittest
from pathlib import Path

import asip.acceptance as acceptance
from asip.acceptance import DEFAULT_ACCEPTANCE_QUERIES, run_acceptance_queries
from asip.storage import AsipStore
from asip.workbench import (
    add_corpus,
    index_configured_corpora,
    index_registered_corpora,
    save_provider_settings,
)
from workbench_fixture import write_live_fixture


class FakeEmbeddingTransport:
    def post_json(self, url, payload, headers, timeout):
        return {"embedding": [0.11, 0.22, 0.33]}


class FakeOpenAIEmbeddingTransport:
    def post_json(self, url, payload, headers, timeout):
        return {"data": [{"index": index, "embedding": [0.1 + index, 0.2, 0.3]} for index, _ in enumerate(payload["input"])]}


class FakeEdgeProvider:
    def generate(self, prompt, model):
        return {
            "cases": [
                {
                    "id": "provider-smoke",
                    "edges": [
                        {
                            "src": "GCVM_L2_CNTL",
                            "relation": "sets_field",
                            "dst": "ENABLE_L2_CACHE",
                            "confidence": 0.9,
                            "evidence": "fixture",
                        }
                    ],
                }
            ]
        }


class AcceptanceRunnerTests(unittest.TestCase):
    def test_default_acceptance_matrix_has_nine_queries_with_gap_and_surface_metadata(self):
        self.assertEqual([item["id"] for item in DEFAULT_ACCEPTANCE_QUERIES], [f"AQ{index:02d}" for index in range(1, 10)])
        for item in DEFAULT_ACCEPTANCE_QUERIES:
            self.assertTrue(item["query"])
            self.assertTrue(item["gap_ids"])
            self.assertTrue(item["required_surfaces"])
        aq05 = next(item for item in DEFAULT_ACCEPTANCE_QUERIES if item["id"] == "AQ05")
        self.assertEqual(aq05["required_source_types"], ["code", "doc", "pdf"])
        aq06 = next(item for item in DEFAULT_ACCEPTANCE_QUERIES if item["id"] == "AQ06")
        self.assertEqual(aq06["required_source_types"], ["code", "register"])

    def test_runner_writes_pass_fail_artifacts_from_clean_db(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path, _corpus_root = write_live_fixture(root)
            db_path = root / "clean-acceptance.db"
            output_json = root / "acceptance.json"
            output_md = root / "acceptance.md"

            index_configured_corpora(config_path, db_path)

            result = run_acceptance_queries(
                db_path,
                output_json=output_json,
                output_md=output_md,
                queries=[
                    {
                        "id": "AQ-PASS",
                        "query": "doorbell interrupt disable",
                        "gap_ids": ["G02", "G03"],
                        "required_surfaces": ["core"],
                    },
                    {
                        "id": "AQ-FAIL",
                        "query": "missing symbol no match",
                        "gap_ids": ["G10"],
                        "required_surfaces": ["core"],
                    },
                ],
                surfaces_checked=["core"],
            )

            self.assertEqual(result["summary"]["total"], 2)
            self.assertEqual(result["summary"]["passed"], 1)
            self.assertEqual(result["summary"]["failed"], 1)
            self.assertEqual(result["db_path"], str(db_path))
            self.assertTrue(output_json.exists())
            self.assertTrue(output_md.exists())

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            passing = next(item for item in payload["queries"] if item["id"] == "AQ-PASS")
            failing = next(item for item in payload["queries"] if item["id"] == "AQ-FAIL")
            self.assertEqual(passing["status"], "pass")
            self.assertGreater(passing["row_count"], 0)
            self.assertTrue(passing["evidence_ids"])
            self.assertTrue(passing["source_paths"])
            self.assertGreaterEqual(passing["graph_node_count"], 1)
            self.assertEqual(failing["status"], "fail")
            self.assertEqual(failing["row_count"], 0)
            self.assertIn("AQ-FAIL", output_md.read_text(encoding="utf-8"))

    def test_runner_deduplicates_surfaces_checked_without_reordering(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path, _corpus_root = write_live_fixture(root)
            db_path = root / "clean-acceptance.db"
            index_configured_corpora(config_path, db_path)

            result = run_acceptance_queries(
                db_path,
                queries=[
                    {
                        "id": "AQ-PASS",
                        "query": "doorbell interrupt disable",
                        "gap_ids": ["G02"],
                        "required_surfaces": ["CLI", "Web"],
                    }
                ],
                surfaces_checked=["CLI", "CLI", "Web"],
            )

            self.assertEqual(result["surfaces_checked"], ["CLI", "Web"])
            self.assertEqual(result["queries"][0]["surfaces_checked"], ["CLI", "Web"])
            self.assertEqual(result["queries"][0]["missing_surfaces"], [])

    def test_runner_uses_workbench_configured_query_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "acceptance.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.upsert_corpus("fixture", "local", str(Path(tmpdir)), ["**/*.c"], status="indexed", file_count=1)
            observed_limits = []
            original_query_evidence = acceptance.query_evidence

            def fake_query_evidence(db_path, query, limit=None):
                observed_limits.append(limit)
                return {
                    "rows": [
                        {
                            "id": 1,
                            "source_type": "code",
                            "symbol": "GCVM_L2_CNTL",
                            "path": "driver.c",
                        }
                    ],
                    "graph": {"nodes": [{"id": "GCVM_L2_CNTL"}], "edges": []},
                }

            try:
                acceptance.query_evidence = fake_query_evidence
                result = run_acceptance_queries(
                    db_path,
                    queries=[
                        {
                            "id": "AQ-CONFIG-LIMIT",
                            "query": "GCVM_L2_CNTL",
                            "gap_ids": ["G10"],
                            "required_surfaces": ["CLI"],
                        }
                    ],
                    surfaces_checked=["CLI"],
                )
            finally:
                acceptance.query_evidence = original_query_evidence

            self.assertEqual(result["queries"][0]["status"], "pass")
            self.assertEqual(observed_limits, [None])

    def test_runner_fails_when_required_source_types_are_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path, _corpus_root = write_live_fixture(root)
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["corpora"][0]["include"] = ["**/*.c"]
            config_path.write_text(json.dumps(config), encoding="utf-8")
            db_path = root / "clean-acceptance.db"
            output_md = root / "acceptance.md"
            index_configured_corpora(config_path, db_path)

            result = run_acceptance_queries(
                db_path,
                output_md=output_md,
                queries=[
                    {
                        "id": "AQ-DOCS",
                        "query": "doorbell interrupt disable",
                        "gap_ids": ["G01", "G08"],
                        "required_surfaces": ["CLI"],
                        "required_source_types": ["doc", "pdf"],
                    }
                ],
                surfaces_checked=["CLI"],
            )

            record = result["queries"][0]
            self.assertEqual(record["status"], "fail")
            self.assertEqual(record["source_types"], ["code"])
            self.assertIn("required source types missing: doc, pdf", record["failure_reasons"])
            markdown = output_md.read_text(encoding="utf-8")
            self.assertIn("Source types", markdown)
            self.assertIn("required source types missing: doc, pdf", markdown)

    def test_runner_fails_when_index_state_is_not_healthy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "unhealthy.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.upsert_corpus("fixture", "local", str(Path(tmpdir)), ["**/*.c"], status="indexing", file_count=1)
            job_id = store.start_job("index", "interrupted index")
            store.finish_job(job_id, "failed", "interrupted index")
            document_id = store.add_document("fixture", "code", "driver.c")
            chunk_id = store.add_chunk(document_id, "GCVM_L2_CNTL ENABLE_L2_CACHE", 1, 1)
            store.add_evidence(
                chunk_id,
                "fixture",
                "code",
                "local",
                "driver.c",
                "GCVM_L2_CNTL",
                "register",
                "mention",
                0.95,
                "GCVM_L2_CNTL ENABLE_L2_CACHE",
                "source mention -> GCVM_L2_CNTL",
                line_start=1,
                line_end=1,
            )

            result = run_acceptance_queries(
                db_path,
                queries=[
                    {
                        "id": "AQ-UNHEALTHY",
                        "query": "GCVM_L2_CNTL ENABLE_L2_CACHE",
                        "gap_ids": ["G10"],
                        "required_surfaces": ["CLI"],
                    }
                ],
                surfaces_checked=["CLI"],
            )

            record = result["queries"][0]
            self.assertEqual(record["status"], "fail")
            self.assertIn("corpus fixture status is indexing", record["failure_reasons"])
            self.assertIn("index job 1 failed: interrupted index", record["failure_reasons"])

    def test_runner_fails_provider_acceptance_when_provider_settings_are_absent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path, _corpus_root = write_live_fixture(root)
            db_path = root / "clean-acceptance.db"
            index_configured_corpora(config_path, db_path)

            result = run_acceptance_queries(
                db_path,
                queries=[
                    {
                        "id": "AQ-PROVIDER",
                        "query": "doorbell interrupt disable",
                        "gap_ids": ["G06"],
                        "required_surfaces": ["CLI"],
                        "requires_provider_settings": True,
                    }
                ],
                surfaces_checked=["CLI"],
            )

            record = result["queries"][0]
            self.assertEqual(record["status"], "fail")
            self.assertIn("provider settings", record["failure_reasons"][0])

    def test_runner_passes_provider_acceptance_with_embedding_and_edge_job_provenance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "clean-acceptance.db"
            corpus_root = root / "docs"
            corpus_root.mkdir()
            (corpus_root / "note.md").write_text(
                "GCVM_L2_CNTL has field ENABLE_L2_CACHE in this provider smoke fixture.",
                encoding="utf-8",
            )
            save_provider_settings(
                db_path,
                {
                    "embedding": {
                        "provider": "ollama",
                        "base_url": "http://embed.local",
                        "api_path": "/api/embeddings",
                        "model": "nomic-embed-text",
                    },
                    "edge": {
                        "provider": "ollama",
                        "base_url": "http://edge.local",
                        "api_path": "/api/chat",
                        "model": "gemma4:e4b",
                        "think": False,
                        "timeout_seconds": 7,
                    },
                },
            )
            add_corpus(
                db_path,
                corpus_id="provider-docs",
                repo="local",
                source_root=str(corpus_root),
                include=["**/*.md"],
                corpus_type="doc",
            )
            index_registered_corpora(
                db_path,
                corpus_ids=["provider-docs"],
                embedding_transport=FakeEmbeddingTransport(),
            )

            result = run_acceptance_queries(
                db_path,
                queries=[
                    {
                        "id": "AQ-PROVIDER",
                        "query": "GCVM_L2_CNTL ENABLE_L2_CACHE",
                        "gap_ids": ["G06"],
                        "required_surfaces": ["CLI"],
                        "requires_provider_settings": True,
                    }
                ],
                surfaces_checked=["CLI"],
                edge_provider=FakeEdgeProvider(),
            )

            record = result["queries"][0]
            self.assertEqual(record["status"], "pass")
            self.assertEqual(record["provider_checks"]["embedding"]["status"], "pass")
            self.assertEqual(record["provider_checks"]["embedding"]["model"], "nomic-embed-text")
            self.assertEqual(record["provider_checks"]["embedding"]["embedding_count"], 1)
            self.assertEqual(record["provider_checks"]["semantic_edge"]["status"], "pass")
            self.assertEqual(record["provider_checks"]["semantic_edge"]["edge_count"], 1)
            self.assertEqual(record["failure_reasons"], [])

    def test_markdown_includes_provider_checks_for_provider_acceptance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "clean-acceptance.db"
            output_md = root / "acceptance.md"
            corpus_root = root / "docs"
            corpus_root.mkdir()
            (corpus_root / "note.md").write_text("GCVM_L2_CNTL has field ENABLE_L2_CACHE.", encoding="utf-8")
            save_provider_settings(
                db_path,
                {
                    "embedding": {"provider": "ollama", "base_url": "http://embed.local", "model": "nomic-embed-text"},
                    "edge": {"provider": "ollama", "base_url": "http://edge.local", "model": "gemma4:e4b"},
                },
            )
            add_corpus(db_path, "provider-docs", "local", str(corpus_root), ["**/*.md"], "doc")
            index_registered_corpora(db_path, corpus_ids=["provider-docs"], embedding_transport=FakeEmbeddingTransport())

            run_acceptance_queries(
                db_path,
                output_md=output_md,
                queries=[
                    {
                        "id": "AQ-PROVIDER",
                        "query": "GCVM_L2_CNTL ENABLE_L2_CACHE",
                        "gap_ids": ["G06"],
                        "required_surfaces": ["CLI"],
                        "requires_provider_settings": True,
                    }
                ],
                surfaces_checked=["CLI"],
                edge_provider=FakeEdgeProvider(),
            )

            text = output_md.read_text(encoding="utf-8")
            self.assertIn("Provider Checks", text)
            self.assertIn("embedding", text)
            self.assertIn("semantic_edge", text)

    def test_provider_acceptance_supports_openai_compatible_switch_without_code_changes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "clean-acceptance.db"
            corpus_root = root / "docs"
            corpus_root.mkdir()
            (corpus_root / "note.md").write_text(
                "GCVM_L2_CNTL has field ENABLE_L2_CACHE in this provider switch fixture.",
                encoding="utf-8",
            )
            save_provider_settings(
                db_path,
                {
                    "embedding": {
                        "provider": "openai-compatible",
                        "base_url": "http://openai-compatible.local",
                        "api_path": "/v1/embeddings",
                        "model": "local-embed",
                    },
                    "edge": {
                        "provider": "openai-compatible",
                        "base_url": "http://openai-compatible.local",
                        "api_path": "/v1/chat/completions",
                        "model": "local-chat",
                    },
                },
            )
            add_corpus(
                db_path,
                corpus_id="provider-docs",
                repo="local",
                source_root=str(corpus_root),
                include=["**/*.md"],
                corpus_type="doc",
            )
            index_registered_corpora(
                db_path,
                corpus_ids=["provider-docs"],
                embedding_transport=FakeOpenAIEmbeddingTransport(),
            )

            result = run_acceptance_queries(
                db_path,
                queries=[
                    {
                        "id": "AQ-PROVIDER",
                        "query": "GCVM_L2_CNTL ENABLE_L2_CACHE",
                        "gap_ids": ["G06"],
                        "required_surfaces": ["CLI"],
                        "requires_provider_settings": True,
                    }
                ],
                surfaces_checked=["CLI"],
                edge_provider=FakeEdgeProvider(),
            )

            record = result["queries"][0]
            self.assertEqual(record["status"], "pass")
            self.assertEqual(record["provider_checks"]["embedding"]["provider"], "openai-compatible")
            self.assertEqual(record["provider_checks"]["embedding"]["model"], "local-embed")
            self.assertEqual(record["provider_checks"]["semantic_edge"]["provider"], "openai-compatible")
            self.assertEqual(record["provider_checks"]["semantic_edge"]["model"], "local-chat")


if __name__ == "__main__":
    unittest.main()
