import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import asip.acceptance as acceptance
from asip.acceptance import DEFAULT_ACCEPTANCE_QUERIES, run_acceptance_queries, run_provider_gate
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


class FailingEmbeddingTransport:
    def post_json(self, url, payload, headers, timeout):
        raise RuntimeError("embedding provider is unreachable")


class FakeOpenAIEmbeddingTransport:
    def post_json(self, url, payload, headers, timeout):
        return {"data": [{"index": index, "embedding": [0.1 + index, 0.2, 0.3]} for index, _ in enumerate(payload["input"])]}


class FakeEdgeProvider:
    def generate(self, prompt, model):
        self.model = model
        return {
            "cases": [
                {
                    "id": "provider-smoke",
                    "edges": [
                        {
                            "src": "GCVM_L2_CNTL",
                            "relation": "documents",
                            "dst": "doc:provider-smoke",
                            "confidence": 0.9,
                            "evidence": "fixture",
                        }
                    ],
                }
            ]
        }


class AcceptanceRunnerTests(unittest.TestCase):
    def _add_doc_node_edge(self, store: AsipStore, provider: str = "ollama", model: str = "gemma4:e4b") -> int:
        job_id = store.start_job(
            "doc_nodes_batch",
            "provider gate doc-node job",
            metadata={
                "provider_settings": {
                    "edge": {
                        "provider": provider,
                        "model": model,
                    }
                }
            },
        )
        store.finish_job(job_id, "generated", "Generated 1 doc-node edge")
        store.add_edge(
            "docs/guide.md#cache-policy",
            "GCVM_L2_CNTL",
            "documents",
            0.9,
            stage="semantic",
            source=provider,
            provenance={
                "provider": provider,
                "model": model,
                "job_id": job_id,
                "extractor": "doc_nodes",
            },
        )
        return job_id

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
            self.assertEqual(result["gate_status"], "blocked")
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

    def test_runner_records_real_surface_probe_results(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path, _corpus_root = write_live_fixture(root)
            db_path = root / "clean-acceptance.db"
            index_configured_corpora(config_path, db_path)

            result = run_acceptance_queries(
                db_path,
                queries=[
                    {
                        "id": "AQ-SURFACES",
                        "query": "doorbell interrupt disable",
                        "gap_ids": ["G07"],
                        "required_surfaces": ["CLI", "API", "MCP"],
                    }
                ],
                surfaces_checked=["CLI", "API", "MCP"],
            )

            surface_results = result["queries"][0]["surface_results"]
            self.assertEqual({item["surface"] for item in surface_results}, {"CLI", "API", "MCP"})
            self.assertEqual({item["status"] for item in surface_results}, {"pass"})
            self.assertEqual(
                {item["transport"] for item in surface_results},
                {"core.query_evidence", "fastapi.testclient.query", "mcp.tool-direct.search_evidence"},
            )
            self.assertTrue(all(item["db_path"] == str(db_path) for item in surface_results))
            mcp_result = next(item for item in surface_results if item["surface"] == "MCP")
            self.assertTrue(mcp_result["server_registered"])

    def test_runner_records_malformed_surface_rows_as_failure_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "malformed-surface.db"
            AsipStore.connect(str(db_path)).migrate()

            with patch.object(
                acceptance,
                "query_evidence",
                return_value={"rows": ["bad-row"], "graph": {"nodes": [], "edges": []}},
            ):
                result = run_acceptance_queries(
                    db_path,
                    queries=[
                        {
                            "id": "AQ-MALFORMED",
                            "query": "malformed rows",
                            "gap_ids": ["G10"],
                            "required_surfaces": ["CLI"],
                        }
                    ],
                    surfaces_checked=["CLI"],
                )

            record = result["queries"][0]
            self.assertEqual(record["status"], "fail")
            self.assertEqual(record["row_count"], 0)
            self.assertTrue(any("malformed rows payload" in reason for reason in record["failure_reasons"]))
            self.assertTrue(any("malformed rows payload" in surface["message"] for surface in record["surface_results"]))

    def test_web_surface_probe_requires_payload_db_path_binding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "web-surface.db"
            payload = {
                "db_path": str(Path(tmpdir) / "wrong.db"),
                "rows": [{"id": 1, "source_type": "code", "symbol": "GCVM_L2_CNTL", "path": "driver.c"}],
                "graph": {"nodes": [{"id": "register:GC:GCVM_L2_CNTL", "kind": "register"}], "edges": []},
            }

            result = acceptance._surface_probe_result("Web", "next-bff.query", db_path, payload)

            self.assertEqual(result["status"], "fail")
            self.assertIn("Web surface payload db_path mismatch", result["message"])

    def test_web_surface_probe_requires_payload_db_path_presence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "web-surface.db"
            payload = {
                "rows": [{"id": 1, "source_type": "code", "symbol": "GCVM_L2_CNTL", "path": "driver.c"}],
                "graph": {"nodes": [{"id": "register:GC:GCVM_L2_CNTL", "kind": "register"}], "edges": []},
            }

            result = acceptance._surface_probe_result("Web", "next-bff.query", db_path, payload)

            self.assertEqual(result["status"], "fail")
            self.assertIn("Web surface payload db_path is missing", result["message"])

    def test_api_live_surface_probe_requires_payload_db_path_binding(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "api-live-surface.db"
            payload = {
                "db_path": str(Path(tmpdir) / "wrong.db"),
                "rows": [{"id": 1, "source_type": "code", "symbol": "GCVM_L2_CNTL", "path": "driver.c"}],
                "graph": {"nodes": [{"id": "register:GC:GCVM_L2_CNTL", "kind": "register"}], "edges": []},
            }

            result = acceptance._surface_probe_result("API_LIVE", "fastapi.uvicorn.http.query", db_path, payload)

            self.assertEqual(result["status"], "fail")
            self.assertIn("API_LIVE surface payload db_path mismatch", result["message"])

    def test_api_live_surface_probe_requires_payload_db_path_presence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "api-live-surface.db"
            payload = {
                "rows": [{"id": 1, "source_type": "code", "symbol": "GCVM_L2_CNTL", "path": "driver.c"}],
                "graph": {"nodes": [{"id": "register:GC:GCVM_L2_CNTL", "kind": "register"}], "edges": []},
            }

            result = acceptance._surface_probe_result("API_LIVE", "fastapi.uvicorn.http.query", db_path, payload)

            self.assertEqual(result["status"], "fail")
            self.assertIn("API_LIVE surface payload db_path is missing", result["message"])

    def test_runner_records_product_graph_schema_status_per_query(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "schema-status.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.upsert_corpus("fixture", "local", str(Path(tmpdir)), ["**/*.c"], status="indexed", file_count=1)
            original_query_evidence = acceptance.query_evidence

            def fake_query_evidence(db_path, query, limit=None, **kwargs):
                return {
                    "rows": [
                        {
                            "id": 1,
                            "source_type": "code",
                            "symbol": "GCVM_L2_CNTL",
                            "path": "driver.c",
                        }
                    ],
                    "graph": {
                        "nodes": [{"id": "macro:WREG32", "kind": "macro"}],
                        "edges": [{"source": "macro:WREG32", "target": "register:GCVM_L2_CNTL", "relation": "wraps"}],
                    },
                }

            try:
                acceptance.query_evidence = fake_query_evidence
                result = run_acceptance_queries(
                    db_path,
                    queries=[
                        {
                            "id": "AQ-SCHEMA",
                            "query": "GCVM_L2_CNTL",
                            "gap_ids": ["G10"],
                            "required_surfaces": ["CLI"],
                        }
                    ],
                    surfaces_checked=["CLI"],
                )
            finally:
                acceptance.query_evidence = original_query_evidence

            record = result["queries"][0]
            self.assertEqual(record["schema_status"], "fail")
            self.assertIn("non-product graph node kind: macro", record["schema_failure_reasons"])
            self.assertIn("non-product graph relation: wraps", record["schema_failure_reasons"])
            self.assertEqual(record["status"], "fail")

    def test_runner_fails_product_graph_schema_when_kind_or_relation_is_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "schema-missing-fields.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.upsert_corpus("fixture", "local", str(Path(tmpdir)), ["**/*.c"], status="indexed", file_count=1)
            original_query_evidence = acceptance.query_evidence

            def fake_query_evidence(db_path, query, limit=None, **kwargs):
                return {
                    "rows": [{"id": 1, "source_type": "code", "symbol": "GCVM_L2_CNTL", "path": "driver.c"}],
                    "graph": {
                        "nodes": [{"id": "register:GC:GCVM_L2_CNTL"}],
                        "edges": [{"source": "function:driver:program", "target": "register:GC:GCVM_L2_CNTL"}],
                    },
                }

            try:
                acceptance.query_evidence = fake_query_evidence
                result = run_acceptance_queries(
                    db_path,
                    queries=[
                        {
                            "id": "AQ-SCHEMA-MISSING",
                            "query": "GCVM_L2_CNTL",
                            "gap_ids": ["G10"],
                            "required_surfaces": ["CLI"],
                        }
                    ],
                    surfaces_checked=["CLI"],
                )
            finally:
                acceptance.query_evidence = original_query_evidence

            record = result["queries"][0]
            self.assertEqual(record["schema_status"], "fail")
            self.assertIn("missing graph node kind", record["schema_failure_reasons"])
            self.assertIn("missing graph relation", record["schema_failure_reasons"])
            self.assertEqual(record["status"], "fail")

    def test_runner_marks_web_surface_not_configured_without_base_url(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path, _corpus_root = write_live_fixture(root)
            db_path = root / "clean-acceptance.db"
            index_configured_corpora(config_path, db_path)

            result = run_acceptance_queries(
                db_path,
                queries=[
                    {
                        "id": "AQ-WEB",
                        "query": "doorbell interrupt disable",
                        "gap_ids": ["G10"],
                        "required_surfaces": ["CLI", "Web"],
                    }
                ],
                surfaces_checked=["CLI", "Web"],
            )

            query = result["queries"][0]
            web_result = next(item for item in query["surface_results"] if item["surface"] == "Web")
            self.assertEqual(web_result["status"], "not_configured")
            self.assertEqual(result["summary"]["failed"], 1)
            self.assertTrue(any("Web surface failed" in reason for reason in query["failure_reasons"]))

    def test_runner_marks_api_live_surface_not_configured_without_base_url(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path, _corpus_root = write_live_fixture(root)
            db_path = root / "clean-acceptance.db"
            index_configured_corpora(config_path, db_path)

            with patch.dict(os.environ, {}, clear=True):
                result = run_acceptance_queries(
                    db_path,
                    queries=[
                        {
                            "id": "AQ-API-LIVE",
                            "query": "doorbell interrupt disable",
                            "gap_ids": ["G10"],
                            "required_surfaces": ["CLI", "API_LIVE"],
                        }
                    ],
                    surfaces_checked=["CLI", "API_LIVE"],
                )

            query = result["queries"][0]
            live_result = next(item for item in query["surface_results"] if item["surface"] == "API_LIVE")
            self.assertEqual(live_result["status"], "not_configured")
            self.assertEqual(live_result["transport"], "fastapi.uvicorn.http.query")
            self.assertTrue(any("API_LIVE surface failed" in reason for reason in query["failure_reasons"]))

    def test_runner_marks_mcp_protocol_surface_not_configured_without_python(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path, _corpus_root = write_live_fixture(root)
            db_path = root / "clean-acceptance.db"
            index_configured_corpora(config_path, db_path)

            with patch.dict(os.environ, {}, clear=True):
                result = run_acceptance_queries(
                    db_path,
                    queries=[
                        {
                            "id": "AQ-MCP-PROTOCOL",
                            "query": "doorbell interrupt disable",
                            "gap_ids": ["G10"],
                            "required_surfaces": ["CLI", "MCP_PROTOCOL"],
                        }
                    ],
                    surfaces_checked=["CLI", "MCP_PROTOCOL"],
                )

            query = result["queries"][0]
            protocol_result = next(item for item in query["surface_results"] if item["surface"] == "MCP_PROTOCOL")
            self.assertEqual(protocol_result["status"], "not_configured")
            self.assertEqual(protocol_result["transport"], "mcp.stdio.protocol.search_evidence")
            self.assertTrue(any("MCP_PROTOCOL surface failed" in reason for reason in query["failure_reasons"]))

    def test_api_live_surface_uses_http_base_url_and_db_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "api-live.db"
            seen_urls = []

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, exc_type, exc, tb):
                    return False

                def read(self):
                    return json.dumps(
                        {
                            "db_path": str(db_path),
                            "rows": [{"id": 1, "source_type": "code"}],
                            "graph": {"nodes": [{"id": "n", "kind": "function"}], "edges": []},
                        }
                    ).encode("utf-8")

            def fake_urlopen(request, timeout):
                seen_urls.append(request.full_url)
                self.assertEqual(timeout, 30)
                return FakeResponse()

            with patch.dict(
                os.environ,
                {"ASIP_API_BASE_URL": "http://127.0.0.1:8123", "ASIP_LIVE_QUERY_TIMEOUT_SECONDS": "30"},
                clear=True,
            ):
                with patch.object(acceptance.urllib.request, "urlopen", side_effect=fake_urlopen):
                    result = acceptance._run_surface_probe("API_LIVE", db_path, "doorbell interrupt disable")

            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["transport"], "fastapi.uvicorn.http.query")
            self.assertEqual(result["db_path"], str(db_path))
            self.assertEqual(result["row_count"], 1)
            parsed = acceptance.urllib.parse.urlparse(seen_urls[0])
            params = acceptance.urllib.parse.parse_qs(parsed.query)
            self.assertEqual(parsed.path, "/query")
            self.assertEqual(params["q"], ["doorbell interrupt disable"])
            self.assertEqual(params["db_path"], [str(db_path)])
            self.assertEqual(params["compact_graph"], ["true"])

    def test_mcp_protocol_surface_uses_stdio_client_and_db_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "mcp-protocol.db"
            payload = {
                "db_path": str(db_path),
                "rows": [{"id": 1, "source_type": "code"}],
                "graph": {"nodes": [{"id": "n", "kind": "function"}], "edges": []},
            }

            with patch.dict(os.environ, {"ASIP_MCP_PROTOCOL_PYTHON": "/fake/python"}, clear=True):
                with patch.object(
                    acceptance,
                    "_query_mcp_protocol",
                    return_value={"payload": payload, "tool_count": 22, "tool_registered": True},
                ) as protocol_probe:
                    result = acceptance._run_surface_probe("MCP_PROTOCOL", db_path, "doorbell interrupt disable")

            protocol_probe.assert_called_once_with("/fake/python", db_path, "doorbell interrupt disable")
            self.assertEqual(result["status"], "pass")
            self.assertEqual(result["transport"], "mcp.stdio.protocol.search_evidence")
            self.assertEqual(result["db_path"], str(db_path))
            self.assertEqual(result["row_count"], 1)
            self.assertEqual(result["tool_count"], 22)
            self.assertTrue(result["server_registered"])

    def test_runner_uses_workbench_configured_query_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "acceptance.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.upsert_corpus("fixture", "local", str(Path(tmpdir)), ["**/*.c"], status="indexed", file_count=1)
            observed_limits = []
            original_query_evidence = acceptance.query_evidence

            def fake_query_evidence(db_path, query, limit=None, **kwargs):
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
                    "graph": {"nodes": [{"id": "GCVM_L2_CNTL", "kind": "register"}], "edges": []},
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

    def test_runner_fails_when_index_job_is_unfinished(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "unfinished-job.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.upsert_corpus("fixture", "local", str(Path(tmpdir)), ["**/*.c"], status="indexed", file_count=1)
            job_id = store.start_job("index", "stale index")
            store.update_job_status(job_id, "indexing", "stale index")
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
                        "id": "AQ-STALLED",
                        "query": "GCVM_L2_CNTL ENABLE_L2_CACHE",
                        "gap_ids": ["G10"],
                        "required_surfaces": ["CLI"],
                    }
                ],
                surfaces_checked=["CLI"],
            )

            record = result["queries"][0]
            self.assertEqual(record["status"], "fail")
            self.assertIn("index job 1 indexing: stale index", record["failure_reasons"])

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
            store = AsipStore.connect(str(db_path))
            job_id = store.start_job(
                "semantic_edges_batch",
                "semantic edge provider provenance",
                metadata={
                    "provider_settings": {
                        "edge": {
                            "provider": "ollama",
                            "model": "gemma4:e4b",
                        }
                    }
                },
            )
            store.finish_job(job_id, "generated", "Generated 1 semantic edge")
            doc_node_job_id = store.start_job(
                "doc_nodes_batch",
                "provider acceptance doc-node edge job",
                metadata={
                    "provider_settings": {
                        "edge": {
                            "provider": "ollama",
                            "model": "gemma4:e4b",
                        }
                    }
                },
            )
            store.finish_job(doc_node_job_id, "generated", "Generated 1 doc-node edge")
            AsipStore.connect(str(db_path)).add_edge(
                "GCVM_L2_CNTL",
                "ENABLE_L2_CACHE",
                "sets_field",
                0.91,
                stage="semantic",
                source="ollama",
                provenance={
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "job_id": job_id,
                    "extractor": "semantic_edges",
                },
            )
            AsipStore.connect(str(db_path)).add_edge(
                "GCVM_L2_CNTL",
                "GCVM_L2_CNTL#doc",
                "documents",
                0.88,
                stage="semantic",
                source="ollama",
                provenance={
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "job_id": doc_node_job_id,
                    "extractor": "doc_nodes",
                },
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
                embedding_transport=FakeEmbeddingTransport(),
            )

            record = result["queries"][0]
            self.assertEqual(record["status"], "pass")
            self.assertEqual(record["provider_checks"]["embedding"]["status"], "pass")
            self.assertEqual(record["provider_checks"]["embedding"]["coverage_status"], "pass")
            self.assertEqual(record["provider_checks"]["embedding"]["model"], "nomic-embed-text")
            self.assertEqual(record["provider_checks"]["embedding"]["embedding_count"], 1)
            self.assertEqual(record["provider_checks"]["embedding"]["embedded_chunks"], 1)
            self.assertEqual(record["provider_checks"]["embedding"]["total_chunks"], 1)
            self.assertEqual(record["provider_checks"]["embedding"]["missing_embedding_chunks"], 0)
            self.assertEqual(record["provider_checks"]["embedding_live"]["status"], "pass")
            self.assertEqual(record["provider_checks"]["embedding_live"]["provider"], "ollama")
            self.assertEqual(record["provider_checks"]["embedding_live"]["model"], "nomic-embed-text")
            self.assertEqual(record["provider_checks"]["embedding_live"]["embedding_count"], 1)
            self.assertEqual(record["provider_checks"]["embedding_live"]["vector_dimension"], 3)
            self.assertEqual(record["provider_checks"]["semantic_edge_provenance"]["status"], "pass")
            self.assertEqual(record["provider_checks"]["semantic_edge_provenance"]["edge_count"], 1)
            self.assertEqual(record["provider_checks"]["semantic_edge_provenance"]["job_ids"], [job_id])
            self.assertEqual(record["provider_checks"]["semantic_edge_provenance"]["ignored_edge_count"], 1)
            self.assertEqual(record["provider_checks"]["doc_node_provenance"]["status"], "pass")
            self.assertEqual(record["provider_checks"]["doc_node_provenance"]["edge_count"], 1)
            self.assertEqual(record["provider_checks"]["doc_node_provenance"]["job_ids"], [doc_node_job_id])
            self.assertEqual(record["provider_checks"]["doc_node_provenance"]["ignored_edge_count"], 1)
            self.assertEqual(record["provider_checks"]["semantic_edge"]["status"], "pass")
            self.assertEqual(record["provider_checks"]["semantic_edge"]["edge_count"], 1)
            self.assertEqual(record["provider_checks"]["semantic_edge"]["persistable_edge_count"], 1)
            self.assertEqual(record["failure_reasons"], [])

    def test_semantic_edge_live_smoke_rejects_non_persistable_product_edges(self):
        class InvalidEdgeProvider:
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
                                }
                            ],
                        }
                    ]
                }

        check = acceptance._semantic_edge_smoke(
            {"edge": {"provider": "ollama", "model": "gemma4:e4b"}},
            InvalidEdgeProvider(),
        )

        self.assertEqual(check["status"], "fail")
        self.assertEqual(check["edge_count"], 1)
        self.assertEqual(check["persistable_edge_count"], 0)
        self.assertIn("product-schema-persistable", check["message"])

    def test_semantic_edge_live_smoke_prompt_uses_product_schema_endpoints(self):
        class RecordingEdgeProvider:
            prompt = ""

            def generate(self, prompt, model):
                self.prompt = prompt
                return {
                    "cases": [
                        {
                            "id": "provider-smoke",
                            "edges": [
                                {
                                    "src": "program_gcvm_l2",
                                    "relation": "writes",
                                    "dst": "GCVM_L2_CNTL",
                                }
                            ],
                        }
                    ]
                }

        provider = RecordingEdgeProvider()
        check = acceptance._semantic_edge_smoke(
            {"edge": {"provider": "ollama", "model": "gemma4:e4b"}},
            provider,
        )

        self.assertEqual(check["status"], "pass")
        self.assertIn("program_gcvm_l2", provider.prompt)
        self.assertIn("GCVM_L2_CNTL", provider.prompt)
        self.assertNotIn("ENABLE_L2_CACHE", provider.prompt)

    def test_provider_gate_passes_with_provider_provenance_and_live_smokes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "provider-gate.db"
            corpus_root = root / "docs"
            corpus_root.mkdir()
            (corpus_root / "note.md").write_text(
                "GCVM_L2_CNTL has field ENABLE_L2_CACHE in this provider gate fixture.",
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
                    },
                },
            )
            add_corpus(db_path, "provider-docs", "local", str(corpus_root), ["**/*.md"], "doc")
            index_registered_corpora(db_path, corpus_ids=["provider-docs"], embedding_transport=FakeEmbeddingTransport())
            store = AsipStore.connect(str(db_path))
            job_id = store.start_job(
                "semantic_edges_batch",
                "provider gate semantic edge job",
                metadata={
                    "provider_settings": {
                        "edge": {
                            "provider": "ollama",
                            "model": "gemma4:e4b",
                        }
                    }
                },
            )
            store.finish_job(job_id, "generated", "Generated 1 semantic edge")
            store.add_edge(
                "GCVM_L2_CNTL",
                "ENABLE_L2_CACHE",
                "sets_field",
                0.91,
                stage="semantic",
                source="ollama",
                provenance={
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "job_id": job_id,
                    "extractor": "semantic_edges",
                },
            )
            doc_node_job_id = self._add_doc_node_edge(store)

            result = run_provider_gate(
                db_path,
                edge_provider=FakeEdgeProvider(),
                embedding_transport=FakeEmbeddingTransport(),
            )

            self.assertEqual(result["source"], "asip.provider_gate")
            self.assertEqual(result["gate_status"], "pass")
            self.assertEqual(result["summary"], {"total": 5, "passed": 5, "partial": 0, "failed": 0})
            self.assertEqual(result["failure_reasons"], [])
            self.assertEqual(result["provider_checks"]["embedding_live"]["vector_dimension"], 3)
            self.assertEqual(result["provider_checks"]["semantic_edge_provenance"]["job_ids"], [job_id])
            self.assertEqual(result["provider_checks"]["doc_node_provenance"]["job_ids"], [doc_node_job_id])

    def test_provider_gate_writes_blocked_artifact_when_live_embedding_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "provider-gate-blocked.db"
            output_json = root / "provider-gate.json"
            corpus_root = root / "docs"
            corpus_root.mkdir()
            (corpus_root / "note.md").write_text(
                "GCVM_L2_CNTL has field ENABLE_L2_CACHE in this provider gate fixture.",
                encoding="utf-8",
            )
            save_provider_settings(
                db_path,
                {
                    "embedding": {"provider": "ollama", "base_url": "http://embed.local", "model": "nomic-embed-text"},
                    "edge": {"provider": "ollama", "base_url": "http://edge.local", "model": "gemma4:e4b"},
                },
            )
            add_corpus(db_path, "provider-docs", "local", str(corpus_root), ["**/*.md"], "doc")
            index_registered_corpora(db_path, corpus_ids=["provider-docs"], embedding_transport=FakeEmbeddingTransport())
            store = AsipStore.connect(str(db_path))
            job_id = store.start_job(
                "semantic_edges_batch",
                "provider gate semantic edge job",
                metadata={
                    "provider_settings": {
                        "edge": {
                            "provider": "ollama",
                            "model": "gemma4:e4b",
                        }
                    }
                },
            )
            store.finish_job(job_id, "generated", "Generated 1 semantic edge")
            store.add_edge(
                "GCVM_L2_CNTL",
                "ENABLE_L2_CACHE",
                "sets_field",
                0.91,
                stage="semantic",
                source="ollama",
                provenance={
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "job_id": job_id,
                    "extractor": "semantic_edges",
                },
            )
            self._add_doc_node_edge(store)

            result = run_provider_gate(
                db_path,
                output_json=output_json,
                edge_provider=FakeEdgeProvider(),
                embedding_transport=FailingEmbeddingTransport(),
            )

            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(result["summary"], {"total": 5, "passed": 4, "partial": 0, "failed": 1})
            self.assertTrue(
                any("embedding_live provider check failed" in reason for reason in result["failure_reasons"])
            )
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["source"], "asip.provider_gate")
            self.assertEqual(payload["provider_checks"]["embedding_live"]["status"], "fail")
            self.assertIn("embedding provider failed", payload["provider_checks"]["embedding_live"]["message"])

    def test_provider_gate_artifact_reports_stale_semantic_edge_provenance_as_blocked(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "provider-gate-stale-semantic.db"
            output_json = root / "provider-gate-stale-semantic.json"
            corpus_root = root / "docs"
            corpus_root.mkdir()
            (corpus_root / "note.md").write_text(
                "GCVM_L2_CNTL has field ENABLE_L2_CACHE in this provider gate fixture.",
                encoding="utf-8",
            )
            save_provider_settings(
                db_path,
                {
                    "embedding": {"provider": "ollama", "base_url": "http://embed.local", "model": "nomic-embed-text"},
                    "edge": {"provider": "ollama", "base_url": "http://edge.local", "model": "gemma4:e4b"},
                },
            )
            add_corpus(db_path, "provider-docs", "local", str(corpus_root), ["**/*.md"], "doc")
            index_registered_corpora(db_path, corpus_ids=["provider-docs"], embedding_transport=FakeEmbeddingTransport())
            store = AsipStore.connect(str(db_path))
            semantic_job = store.start_job(
                "semantic_edges_batch",
                "provider gate stale semantic edge job",
                metadata={
                    "provider_settings": {
                        "edge": {
                            "provider": "ollama",
                            "model": "gemma4:e4b",
                        }
                    }
                },
            )
            store.finish_job(semantic_job, "succeeded", "Generated 1 semantic edge")
            store.add_edge(
                "GCVM_L2_CNTL",
                "ENABLE_L2_CACHE",
                "sets_field",
                0.91,
                stage="semantic",
                source="ollama",
                provenance={
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "job_id": semantic_job,
                    "extractor": "semantic_edges",
                },
            )
            latest_index_job = store.start_job("index", "new index after provider semantic edge")
            store.finish_job(latest_index_job, "succeeded", "indexed newer corpus")
            self._add_doc_node_edge(store)

            result = run_provider_gate(
                db_path,
                output_json=output_json,
                edge_provider=FakeEdgeProvider(),
                embedding_transport=FakeEmbeddingTransport(),
            )

            self.assertEqual(result["gate_status"], "blocked")
            self.assertEqual(result["summary"], {"total": 5, "passed": 4, "partial": 1, "failed": 0})
            self.assertTrue(
                any("semantic_edge_provenance provider check failed" in reason for reason in result["failure_reasons"])
            )
            payload = json.loads(output_json.read_text(encoding="utf-8"))
            provenance_check = payload["provider_checks"]["semantic_edge_provenance"]
            self.assertEqual(provenance_check["status"], "partial")
            self.assertEqual(provenance_check["stale_job_ids"], [semantic_job])
            self.assertEqual(provenance_check["latest_index_job_id"], latest_index_job)
            self.assertIn("older than latest succeeded index or graph rebuild job", provenance_check["message"])
            self.assertEqual(payload["gate_status"], "blocked")

    def test_acceptance_artifact_reports_stale_semantic_edge_provenance_as_aq09_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "acceptance-stale-semantic.db"
            output_json = root / "acceptance-stale-semantic.json"
            corpus_root = root / "docs"
            corpus_root.mkdir()
            (corpus_root / "note.md").write_text(
                "GCVM_L2_CNTL has field ENABLE_L2_CACHE in this acceptance fixture.",
                encoding="utf-8",
            )
            save_provider_settings(
                db_path,
                {
                    "embedding": {"provider": "ollama", "base_url": "http://embed.local", "model": "nomic-embed-text"},
                    "edge": {"provider": "ollama", "base_url": "http://edge.local", "model": "gemma4:e4b"},
                },
            )
            add_corpus(db_path, "provider-docs", "local", str(corpus_root), ["**/*.md"], "doc")
            index_registered_corpora(db_path, corpus_ids=["provider-docs"], embedding_transport=FakeEmbeddingTransport())
            store = AsipStore.connect(str(db_path))
            semantic_job = store.start_job(
                "semantic_edges_batch",
                "acceptance stale semantic edge job",
                metadata={
                    "provider_settings": {
                        "edge": {
                            "provider": "ollama",
                            "model": "gemma4:e4b",
                        }
                    }
                },
            )
            store.finish_job(semantic_job, "succeeded", "Generated 1 semantic edge")
            store.add_edge(
                "GCVM_L2_CNTL",
                "ENABLE_L2_CACHE",
                "sets_field",
                0.91,
                stage="semantic",
                source="ollama",
                provenance={
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "job_id": semantic_job,
                    "extractor": "semantic_edges",
                },
            )
            latest_index_job = store.start_job("index", "new index after acceptance semantic edge")
            store.finish_job(latest_index_job, "succeeded", "indexed newer corpus")

            result = run_acceptance_queries(
                db_path,
                output_json=output_json,
                queries=[
                    {
                        "id": "AQ09",
                        "query": "GCVM_L2_CNTL ENABLE_L2_CACHE",
                        "gap_ids": ["G06", "G10"],
                        "required_surfaces": ["CLI"],
                        "requires_provider_settings": True,
                    }
                ],
                surfaces_checked=["CLI"],
                edge_provider=FakeEdgeProvider(),
                embedding_transport=FakeEmbeddingTransport(),
            )

            self.assertEqual(result["gate_status"], "blocked")
            record = result["queries"][0]
            self.assertEqual(record["status"], "fail")
            self.assertTrue(
                any(
                    "semantic_edge_provenance provider check failed" in reason
                    for reason in record["failure_reasons"]
                )
            )
            provenance_check = record["provider_checks"]["semantic_edge_provenance"]
            self.assertEqual(provenance_check["status"], "partial")
            self.assertEqual(provenance_check["stale_job_ids"], [semantic_job])
            self.assertEqual(provenance_check["latest_index_job_id"], latest_index_job)

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["gate_status"], "blocked")
            payload_record = payload["queries"][0]
            self.assertEqual(payload_record["status"], "fail")
            payload_provenance = payload_record["provider_checks"]["semantic_edge_provenance"]
            self.assertEqual(payload_provenance["status"], "partial")
            self.assertEqual(payload_provenance["stale_job_ids"], [semantic_job])
            self.assertIn("older than latest succeeded index or graph rebuild job", payload_provenance["message"])

    def test_provider_embedding_check_reports_partial_coverage_when_fallback_rows_remain(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "embedding-coverage.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            save_provider_settings(
                db_path,
                {
                    "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
                    "edge": {"provider": "ollama", "model": "gemma4:e4b"},
                },
            )
            store.upsert_corpus("fixture", "local", str(root), ["**/*.md"], status="indexed", file_count=1)
            document_id = store.add_document("fixture", "doc", "doc.md")
            provider_chunk_id = store.add_chunk(document_id, "provider chunk", 1, 1)
            fallback_chunk_id = store.add_chunk(document_id, "fallback chunk", 2, 2)
            store.add_embedding(
                provider_chunk_id,
                "ollama",
                "nomic-embed-text",
                [0.1, 0.2],
                metadata={"source": "provider"},
            )
            store.add_embedding(
                fallback_chunk_id,
                "hash",
                "deterministic",
                [0.3, 0.4],
                metadata={"source": "deterministic-fallback"},
            )

            checks = acceptance._run_provider_checks(
                db_path,
                acceptance.load_provider_settings(db_path),
                FakeEdgeProvider(),
                FakeEmbeddingTransport(),
            )

            embedding = checks["embedding"]
            self.assertEqual(embedding["status"], "partial")
            self.assertEqual(embedding["provenance_status"], "pass")
            self.assertEqual(embedding["coverage_status"], "partial")
            self.assertEqual(embedding["embedding_count"], 1)
            self.assertEqual(embedding["fallback_count"], 1)
            self.assertEqual(embedding["total_count"], 2)
            self.assertEqual(embedding["embedded_chunks"], 2)
            self.assertEqual(embedding["total_chunks"], 2)
            self.assertEqual(embedding["missing_embedding_chunks"], 0)

    def test_provider_embedding_check_reports_partial_coverage_when_chunks_have_no_embeddings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "missing-embedding-coverage.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            save_provider_settings(
                db_path,
                {
                    "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
                    "edge": {"provider": "ollama", "model": "gemma4:e4b"},
                },
            )
            store.upsert_corpus("fixture", "local", str(root), ["**/*.md"], status="indexed", file_count=1)
            document_id = store.add_document("fixture", "doc", "doc.md")
            provider_chunk_id = store.add_chunk(document_id, "provider chunk", 1, 1)
            store.add_chunk(document_id, "missing embedding chunk", 2, 2)
            store.add_embedding(
                provider_chunk_id,
                "ollama",
                "nomic-embed-text",
                [0.1, 0.2],
                metadata={"source": "provider"},
            )

            checks = acceptance._run_provider_checks(
                db_path,
                acceptance.load_provider_settings(db_path),
                FakeEdgeProvider(),
                FakeEmbeddingTransport(),
            )

            embedding = checks["embedding"]
            self.assertEqual(embedding["status"], "partial")
            self.assertEqual(embedding["provenance_status"], "pass")
            self.assertEqual(embedding["coverage_status"], "partial")
            self.assertEqual(embedding["embedding_count"], 1)
            self.assertEqual(embedding["provider_embedding_count"], 1)
            self.assertEqual(embedding["fallback_count"], 0)
            self.assertEqual(embedding["total_count"], 1)
            self.assertEqual(embedding["embedded_chunks"], 1)
            self.assertEqual(embedding["total_chunks"], 2)
            self.assertEqual(embedding["missing_embedding_chunks"], 1)
            self.assertIn("chunks have no embeddings", embedding["message"])

    def test_embedding_live_smoke_fails_when_provider_is_unreachable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "embedding-live-smoke.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            save_provider_settings(
                db_path,
                {
                    "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
                    "edge": {"provider": "ollama", "model": "gemma4:e4b"},
                },
            )

            checks = acceptance._run_provider_checks(
                db_path,
                acceptance.load_provider_settings(db_path),
                FakeEdgeProvider(),
                FailingEmbeddingTransport(),
            )

            self.assertEqual(checks["embedding_live"]["status"], "fail")
            self.assertIn("embedding provider failed", checks["embedding_live"]["message"])
            self.assertEqual(checks["embedding_live"]["provider"], "ollama")
            self.assertEqual(checks["embedding_live"]["model"], "nomic-embed-text")

    def test_semantic_edge_provenance_requires_succeeded_matching_job(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "semantic-provenance-job.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            save_provider_settings(
                db_path,
                {
                    "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
                    "edge": {"provider": "ollama", "model": "gemma4:e4b"},
                },
            )
            failed_job = store.start_job(
                "semantic_edges_batch",
                "failed semantic edge job",
                metadata={
                    "provider_settings": {
                        "edge": {
                            "provider": "ollama",
                            "model": "gemma4:e4b",
                        }
                    }
                },
            )
            store.finish_job(failed_job, "failed", "provider failed")
            store.add_edge(
                "GCVM_L2_CNTL",
                "ENABLE_L2_CACHE",
                "sets_field",
                0.91,
                stage="semantic",
                source="ollama",
                provenance={
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "job_id": failed_job,
                    "extractor": "semantic_edges",
                },
            )

            check = acceptance._semantic_edge_provenance_check(db_path, acceptance.load_provider_settings(db_path))

            self.assertEqual(check["status"], "fail")
            self.assertEqual(check["edge_count"], 0)
            self.assertEqual(check["missing_or_invalid_job_edge_count"], 1)

    def test_semantic_edge_provenance_normalizes_legacy_success_job_statuses(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "semantic-provenance-legacy-status.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            save_provider_settings(
                db_path,
                {
                    "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
                    "edge": {"provider": "ollama", "model": "gemma4:e4b"},
                },
            )
            index_job = store.start_job("index", "legacy indexed corpus")
            semantic_job = store.start_job(
                "semantic_edges_batch",
                "legacy generated semantic edge job",
                metadata={
                    "provider_settings": {
                        "edge": {
                            "provider": "ollama",
                            "model": "gemma4:e4b",
                        }
                    }
                },
            )
            store.con.execute("update jobs set status = 'indexed' where id = ?", (index_job,))
            store.con.execute("update jobs set status = 'generated' where id = ?", (semantic_job,))
            store.con.commit()
            store.add_edge(
                "GCVM_L2_CNTL",
                "doc:provider-smoke",
                "documents",
                0.91,
                stage="semantic",
                source="ollama",
                provenance={
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "job_id": semantic_job,
                    "extractor": "semantic_edges",
                },
            )

            check = acceptance._semantic_edge_provenance_check(db_path, acceptance.load_provider_settings(db_path))

            self.assertEqual(check["status"], "pass")
            self.assertEqual(check["edge_count"], 1)
            self.assertEqual(check["job_ids"], [semantic_job])
            self.assertEqual(check["latest_index_job_id"], index_job)

    def test_semantic_edge_provenance_reports_stale_edges_after_new_index_job(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "semantic-provenance-stale.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            save_provider_settings(
                db_path,
                {
                    "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
                    "edge": {"provider": "ollama", "model": "gemma4:e4b"},
                },
            )
            semantic_job = store.start_job(
                "semantic_edges_batch",
                "old semantic edge job",
                metadata={
                    "provider_settings": {
                        "edge": {
                            "provider": "ollama",
                            "model": "gemma4:e4b",
                        }
                    }
                },
            )
            store.finish_job(semantic_job, "succeeded", "generated old semantic edges")
            store.add_edge(
                "GCVM_L2_CNTL",
                "ENABLE_L2_CACHE",
                "sets_field",
                0.91,
                stage="semantic",
                source="ollama",
                provenance={
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "job_id": semantic_job,
                    "extractor": "semantic_edges",
                },
            )
            latest_index_job = store.start_job("index", "new index after semantic edges")
            store.finish_job(latest_index_job, "succeeded", "indexed newer corpus")

            check = acceptance._semantic_edge_provenance_check(db_path, acceptance.load_provider_settings(db_path))

            self.assertEqual(check["status"], "partial")
            self.assertEqual(check["edge_count"], 0)
            self.assertEqual(check["stale_edge_count"], 1)
            self.assertEqual(check["latest_index_job_id"], latest_index_job)
            self.assertEqual(check["stale_job_ids"], [semantic_job])
            self.assertIn("older than latest succeeded index or graph rebuild job", check["message"])

    def test_semantic_edge_provenance_reports_stale_edges_after_new_graph_rebuild_job(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "semantic-provenance-stale-graph.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            save_provider_settings(
                db_path,
                {
                    "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
                    "edge": {"provider": "ollama", "model": "gemma4:e4b"},
                },
            )
            index_job = store.start_job("index", "indexed before semantic edges")
            store.finish_job(index_job, "succeeded", "indexed corpus")
            semantic_job = store.start_job(
                "semantic_edges_batch",
                "semantic edge job before graph rebuild",
                metadata={
                    "provider_settings": {
                        "edge": {
                            "provider": "ollama",
                            "model": "gemma4:e4b",
                        }
                    }
                },
            )
            store.finish_job(semantic_job, "succeeded", "generated semantic edges")
            store.add_edge(
                "GCVM_L2_CNTL",
                "ENABLE_L2_CACHE",
                "sets_field",
                0.91,
                stage="semantic",
                source="ollama",
                provenance={
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "job_id": semantic_job,
                    "extractor": "semantic_edges",
                },
            )
            graph_job = store.start_job("graph_rebuild", "rebuilt graph after semantic edges")
            store.finish_job(graph_job, "succeeded", "rebuilt deterministic graph")

            check = acceptance._semantic_edge_provenance_check(db_path, acceptance.load_provider_settings(db_path))

            self.assertEqual(check["status"], "partial")
            self.assertEqual(check["edge_count"], 0)
            self.assertEqual(check["stale_edge_count"], 1)
            self.assertEqual(check["latest_index_job_id"], index_job)
            self.assertEqual(check["latest_graph_rebuild_job_id"], graph_job)
            self.assertEqual(check["stale_job_ids"], [semantic_job])
            self.assertIn("older than latest succeeded index or graph rebuild job", check["message"])

    def test_semantic_edge_provenance_blocks_stale_edges_even_when_current_edges_exist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "semantic-provenance-current-plus-stale.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            save_provider_settings(
                db_path,
                {
                    "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
                    "edge": {"provider": "ollama", "model": "gemma4:e4b"},
                },
            )
            old_job = store.start_job(
                "semantic_edges_batch",
                "old semantic edge job",
                metadata={"provider_settings": {"edge": {"provider": "ollama", "model": "gemma4:e4b"}}},
            )
            store.finish_job(old_job, "generated", "generated old semantic edge")
            store.add_edge(
                "old_program",
                "OLD_CNTL",
                "writes",
                0.91,
                stage="semantic",
                source="ollama",
                provenance={
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "job_id": old_job,
                    "extractor": "semantic_edges",
                },
            )
            graph_job = store.start_job("graph_rebuild", "rebuilt graph after old semantic edge")
            store.finish_job(graph_job, "succeeded", "rebuilt deterministic graph")
            current_job = store.start_job(
                "semantic_edges_batch",
                "current semantic edge job",
                metadata={"provider_settings": {"edge": {"provider": "ollama", "model": "gemma4:e4b"}}},
            )
            store.finish_job(current_job, "generated", "generated current semantic edge")
            store.add_edge(
                "program_gcvm_l2",
                "GCVM_L2_CNTL",
                "writes",
                0.95,
                stage="semantic",
                source="ollama",
                provenance={
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "job_id": current_job,
                    "extractor": "semantic_edges",
                },
            )

            check = acceptance._semantic_edge_provenance_check(db_path, acceptance.load_provider_settings(db_path))

            self.assertEqual(check["status"], "partial")
            self.assertEqual(check["edge_count"], 1)
            self.assertEqual(check["stale_edge_count"], 1)
            self.assertEqual(check["stale_job_ids"], [old_job])
            self.assertEqual(check["latest_graph_rebuild_job_id"], graph_job)
            self.assertIn("older than latest succeeded index or graph rebuild job", check["message"])

    def test_doc_node_provenance_reports_stale_edges_after_new_graph_rebuild_job(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "doc-node-provenance-stale-graph.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            save_provider_settings(
                db_path,
                {
                    "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
                    "edge": {"provider": "ollama", "model": "gemma4:e4b"},
                },
            )
            index_job = store.start_job("index", "indexed before doc nodes")
            store.finish_job(index_job, "indexed", "indexed corpus")
            doc_node_job = store.start_job(
                "doc_nodes_batch",
                "doc-node job before graph rebuild",
                metadata={
                    "provider_settings": {
                        "edge": {
                            "provider": "ollama",
                            "model": "gemma4:e4b",
                        }
                    }
                },
            )
            store.finish_job(doc_node_job, "generated", "generated doc-node edges")
            store.add_edge(
                "doc:guide#cache-policy",
                "GCVM_L2_CNTL",
                "documents",
                0.91,
                stage="semantic",
                source="ollama",
                provenance={
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "job_id": doc_node_job,
                    "extractor": "doc_nodes",
                },
            )
            graph_job = store.start_job("graph_rebuild", "rebuilt graph after doc nodes")
            store.finish_job(graph_job, "rebuilt", "rebuilt deterministic graph")

            check = acceptance._doc_node_provenance_check(db_path, acceptance.load_provider_settings(db_path))

            self.assertEqual(check["status"], "partial")
            self.assertEqual(check["edge_count"], 0)
            self.assertEqual(check["extractor_edge_count"], 1)
            self.assertEqual(check["stale_edge_count"], 1)
            self.assertEqual(check["latest_index_job_id"], index_job)
            self.assertEqual(check["latest_graph_rebuild_job_id"], graph_job)
            self.assertEqual(check["stale_job_ids"], [doc_node_job])
            self.assertIn("doc-node semantic edges are older", check["message"])

    def test_doc_node_provenance_fails_when_no_doc_node_edges_exist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "doc-node-provenance-empty.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            save_provider_settings(
                db_path,
                {
                    "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
                    "edge": {"provider": "ollama", "model": "gemma4:e4b"},
                },
            )
            index_job = store.start_job("index", "indexed before doc nodes")
            store.finish_job(index_job, "indexed", "indexed corpus")
            graph_job = store.start_job("graph_rebuild", "rebuilt graph before doc nodes")
            store.finish_job(graph_job, "rebuilt", "rebuilt deterministic graph")

            check = acceptance._doc_node_provenance_check(db_path, acceptance.load_provider_settings(db_path))

            self.assertEqual(check["status"], "fail")
            self.assertEqual(check["edge_count"], 0)
            self.assertEqual(check["extractor_edge_count"], 0)
            self.assertEqual(check["latest_index_job_id"], index_job)
            self.assertEqual(check["latest_graph_rebuild_job_id"], graph_job)
            self.assertIn("no persisted doc-node semantic edges", check["message"])

    def test_semantic_edge_provenance_blocks_mixed_fresh_and_stale_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "semantic-provenance-mixed-stale-fresh.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            save_provider_settings(
                db_path,
                {
                    "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
                    "edge": {"provider": "ollama", "model": "gemma4:e4b"},
                },
            )
            stale_job = store.start_job(
                "semantic_edges_batch",
                "old semantic edge job",
                metadata={
                    "provider_settings": {
                        "edge": {
                            "provider": "ollama",
                            "model": "gemma4:e4b",
                        }
                    }
                },
            )
            store.finish_job(stale_job, "succeeded", "generated old semantic edges")
            store.add_edge(
                "GCVM_L2_CNTL",
                "ENABLE_L2_CACHE",
                "sets_field",
                0.91,
                stage="semantic",
                source="ollama",
                provenance={
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "job_id": stale_job,
                    "extractor": "semantic_edges",
                },
            )
            index_job = store.start_job("index", "new index after old semantic edges")
            store.finish_job(index_job, "succeeded", "indexed newer corpus")
            graph_job = store.start_job("graph_rebuild", "new graph after old semantic edges")
            store.finish_job(graph_job, "succeeded", "rebuilt graph")
            fresh_job = store.start_job(
                "semantic_edges_batch",
                "fresh semantic edge job",
                metadata={
                    "provider_settings": {
                        "edge": {
                            "provider": "ollama",
                            "model": "gemma4:e4b",
                        }
                    }
                },
            )
            store.finish_job(fresh_job, "succeeded", "generated fresh semantic edges")
            store.add_edge(
                "SDMA0_QUEUE0_RB_CNTL",
                "sdma_v5_0_ring_init",
                "configured_by",
                0.93,
                stage="semantic",
                source="ollama",
                provenance={
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "job_id": fresh_job,
                    "extractor": "semantic_edges",
                },
            )

            check = acceptance._semantic_edge_provenance_check(db_path, acceptance.load_provider_settings(db_path))

            self.assertEqual(check["status"], "partial")
            self.assertEqual(check["edge_count"], 1)
            self.assertEqual(check["job_ids"], [fresh_job])
            self.assertEqual(check["stale_edge_count"], 1)
            self.assertEqual(check["stale_job_ids"], [stale_job])
            self.assertEqual(check["latest_index_job_id"], index_job)
            self.assertEqual(check["latest_graph_rebuild_job_id"], graph_job)
            self.assertIn("older than latest succeeded index or graph rebuild job", check["message"])

    def test_semantic_edge_provenance_blocks_mixed_fresh_and_invalid_job_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "semantic-provenance-mixed-invalid-fresh.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            save_provider_settings(
                db_path,
                {
                    "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
                    "edge": {"provider": "ollama", "model": "gemma4:e4b"},
                },
            )
            index_job = store.start_job("index", "indexed before semantic edges")
            store.finish_job(index_job, "indexed", "indexed corpus")
            graph_job = store.start_job("graph_rebuild", "rebuilt graph before semantic edges")
            store.finish_job(graph_job, "rebuilt", "rebuilt deterministic graph")
            fresh_job = store.start_job(
                "semantic_edges_batch",
                "fresh semantic edge job",
                metadata={
                    "provider_settings": {
                        "edge": {
                            "provider": "ollama",
                            "model": "gemma4:e4b",
                        }
                    }
                },
            )
            store.finish_job(fresh_job, "generated", "generated fresh semantic edges")
            store.add_edge(
                "SDMA0_QUEUE0_RB_CNTL",
                "sdma_v5_0_ring_init",
                "configured_by",
                0.93,
                stage="semantic",
                source="ollama",
                provenance={
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "job_id": fresh_job,
                    "extractor": "semantic_edges",
                },
            )
            store.add_edge(
                "GCVM_L2_CNTL",
                "ENABLE_L2_CACHE",
                "sets_field",
                0.91,
                stage="semantic",
                source="ollama",
                provenance={
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "extractor": "semantic_edges",
                },
            )

            check = acceptance._semantic_edge_provenance_check(db_path, acceptance.load_provider_settings(db_path))

            self.assertEqual(check["status"], "partial")
            self.assertEqual(check["edge_count"], 1)
            self.assertEqual(check["extractor_edge_count"], 2)
            self.assertEqual(check["job_ids"], [fresh_job])
            self.assertEqual(check["missing_or_invalid_job_edge_count"], 1)
            self.assertEqual(check["latest_index_job_id"], index_job)
            self.assertEqual(check["latest_graph_rebuild_job_id"], graph_job)
            self.assertIn("missing or invalid semantic job provenance", check["message"])

    def test_doc_node_provenance_blocks_mixed_fresh_and_wrong_kind_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "doc-node-provenance-mixed-wrong-kind.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            save_provider_settings(
                db_path,
                {
                    "embedding": {"provider": "ollama", "model": "nomic-embed-text"},
                    "edge": {"provider": "ollama", "model": "gemma4:e4b"},
                },
            )
            index_job = store.start_job("index", "indexed before doc nodes")
            store.finish_job(index_job, "indexed", "indexed corpus")
            graph_job = store.start_job("graph_rebuild", "rebuilt graph before doc nodes")
            store.finish_job(graph_job, "rebuilt", "rebuilt deterministic graph")
            doc_node_job = self._add_doc_node_edge(store)
            wrong_kind_job = store.start_job(
                "semantic_edges_batch",
                "semantic edge job should not validate doc-node extractor rows",
                metadata={
                    "provider_settings": {
                        "edge": {
                            "provider": "ollama",
                            "model": "gemma4:e4b",
                        }
                    }
                },
            )
            store.finish_job(wrong_kind_job, "generated", "generated semantic edges")
            store.add_edge(
                "docs/guide.md#cache-policy-2",
                "IH_RB_CNTL",
                "documents",
                0.88,
                stage="semantic",
                source="ollama",
                provenance={
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "job_id": wrong_kind_job,
                    "extractor": "doc_nodes",
                },
            )

            check = acceptance._doc_node_provenance_check(db_path, acceptance.load_provider_settings(db_path))

            self.assertEqual(check["status"], "partial")
            self.assertEqual(check["edge_count"], 1)
            self.assertEqual(check["extractor_edge_count"], 2)
            self.assertEqual(check["job_ids"], [doc_node_job])
            self.assertEqual(check["missing_or_invalid_job_edge_count"], 1)
            self.assertEqual(check["latest_index_job_id"], index_job)
            self.assertEqual(check["latest_graph_rebuild_job_id"], graph_job)
            self.assertIn("missing or invalid semantic job provenance", check["message"])

    def test_provider_smoke_caps_acceptance_timeout_without_rewriting_settings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "timeout-cap.db"
            corpus_root = root / "docs"
            corpus_root.mkdir()
            (corpus_root / "note.md").write_text("GCVM_L2_CNTL has field ENABLE_L2_CACHE.", encoding="utf-8")
            save_provider_settings(
                db_path,
                {
                    "embedding": {"provider": "ollama", "base_url": "http://embed.local", "model": "nomic-embed-text"},
                    "edge": {
                        "provider": "ollama",
                        "base_url": "http://edge.local",
                        "model": "gemma4:e4b",
                        "timeout_seconds": 900,
                    },
                },
            )
            add_corpus(db_path, "provider-docs", "local", str(corpus_root), ["**/*.md"], "doc")
            index_registered_corpora(db_path, corpus_ids=["provider-docs"], embedding_transport=FakeEmbeddingTransport())
            store = AsipStore.connect(str(db_path))
            job_id = store.start_job(
                "semantic_edges_batch",
                "markdown semantic edge job",
                metadata={
                    "provider_settings": {
                        "edge": {
                            "provider": "ollama",
                            "model": "gemma4:e4b",
                        }
                    }
                },
            )
            store.finish_job(job_id, "generated", "Generated 1 semantic edge")
            store.add_edge(
                "GCVM_L2_CNTL",
                "ENABLE_L2_CACHE",
                "sets_field",
                0.91,
                stage="semantic",
                source="ollama",
                provenance={"provider": "ollama", "model": "gemma4:e4b", "job_id": 10},
            )
            provider = FakeEdgeProvider()

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
                edge_provider=provider,
                embedding_transport=FakeEmbeddingTransport(),
            )

            self.assertEqual(result["provider_settings"]["edge"]["timeout_seconds"], 900)
            self.assertEqual(provider.model.timeout_seconds, 120)

    def test_provider_smoke_timeout_ignores_invalid_persisted_and_env_values(self):
        previous = os.environ.get("ASIP_ACCEPTANCE_PROVIDER_TIMEOUT_SECONDS")
        os.environ.pop("ASIP_ACCEPTANCE_PROVIDER_TIMEOUT_SECONDS", None)
        try:
            self.assertEqual(
                acceptance._acceptance_provider_timeout_seconds({"timeout_seconds": "not-an-int"}),
                60,
            )
            os.environ["ASIP_ACCEPTANCE_PROVIDER_TIMEOUT_SECONDS"] = "also-not-an-int"
            self.assertEqual(
                acceptance._acceptance_provider_timeout_seconds({"timeout_seconds": "5"}),
                5,
            )
            os.environ["ASIP_ACCEPTANCE_PROVIDER_TIMEOUT_SECONDS"] = "0"
            self.assertEqual(
                acceptance._acceptance_provider_timeout_seconds({"timeout_seconds": "5"}),
                1,
            )
        finally:
            if previous is None:
                os.environ.pop("ASIP_ACCEPTANCE_PROVIDER_TIMEOUT_SECONDS", None)
            else:
                os.environ["ASIP_ACCEPTANCE_PROVIDER_TIMEOUT_SECONDS"] = previous

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
            store = AsipStore.connect(str(db_path))
            job_id = store.start_job(
                "semantic_edges_batch",
                "markdown semantic edge job",
                metadata={
                    "provider_settings": {
                        "edge": {
                            "provider": "ollama",
                            "model": "gemma4:e4b",
                        }
                    }
                },
            )
            store.finish_job(job_id, "generated", "Generated 1 semantic edge")
            doc_node_job_id = store.start_job(
                "doc_nodes_batch",
                "markdown doc-node edge job",
                metadata={
                    "provider_settings": {
                        "edge": {
                            "provider": "ollama",
                            "model": "gemma4:e4b",
                        }
                    }
                },
            )
            store.finish_job(doc_node_job_id, "generated", "Generated 1 doc-node edge")
            store.add_edge(
                "GCVM_L2_CNTL",
                "ENABLE_L2_CACHE",
                "sets_field",
                0.91,
                stage="semantic",
                source="ollama",
                provenance={
                    "provider": "ollama",
                    "model": "gemma4:e4b",
                    "job_id": job_id,
                    "extractor": "semantic_edges",
                },
            )
            store.add_edge(
                "GCVM_L2_CNTL",
                "GCVM_L2_CNTL#doc",
                "documents",
                0.88,
                stage="semantic",
                source="ollama",
                provenance={"provider": "ollama", "model": "gemma4:e4b", "job_id": doc_node_job_id, "extractor": "doc_nodes"},
            )

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
                embedding_transport=FakeEmbeddingTransport(),
            )

            text = output_md.read_text(encoding="utf-8")
            self.assertIn("Provider Checks", text)
            self.assertIn("embedding", text)
            self.assertIn("semantic_edge", text)
            self.assertIn(f"jobs={job_id}", text)
            self.assertIn("ignored=1", text)

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
            store = AsipStore.connect(str(db_path))
            job_id = store.start_job(
                "semantic_edges_batch",
                "openai-compatible semantic edge job",
                metadata={
                    "provider_settings": {
                        "edge": {
                            "provider": "openai-compatible",
                            "model": "local-chat",
                        }
                    }
                },
            )
            store.finish_job(job_id, "generated", "Generated 1 semantic edge")
            store.add_edge(
                "GCVM_L2_CNTL",
                "ENABLE_L2_CACHE",
                "sets_field",
                0.91,
                stage="semantic",
                source="openai-compatible",
                provenance={
                    "provider": "openai-compatible",
                    "model": "local-chat",
                    "job_id": job_id,
                    "extractor": "semantic_edges",
                },
            )
            self._add_doc_node_edge(store, provider="openai-compatible", model="local-chat")

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
                embedding_transport=FakeOpenAIEmbeddingTransport(),
            )

            record = result["queries"][0]
            self.assertEqual(record["status"], "pass")
            self.assertEqual(record["provider_checks"]["embedding"]["provider"], "openai-compatible")
            self.assertEqual(record["provider_checks"]["embedding"]["model"], "local-embed")
            self.assertEqual(record["provider_checks"]["embedding_live"]["provider"], "openai-compatible")
            self.assertEqual(record["provider_checks"]["embedding_live"]["model"], "local-embed")
            self.assertEqual(record["provider_checks"]["embedding_live"]["status"], "pass")
            self.assertEqual(record["provider_checks"]["semantic_edge_provenance"]["provider"], "openai-compatible")
            self.assertEqual(record["provider_checks"]["semantic_edge_provenance"]["model"], "local-chat")
            self.assertEqual(record["provider_checks"]["semantic_edge_provenance"]["edge_count"], 1)
            self.assertEqual(record["provider_checks"]["semantic_edge"]["provider"], "openai-compatible")
            self.assertEqual(record["provider_checks"]["semantic_edge"]["model"], "local-chat")


if __name__ == "__main__":
    unittest.main()
