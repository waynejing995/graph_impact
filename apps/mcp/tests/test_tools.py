import unittest
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from apps.mcp.tools import (
    acceptance_runs,
    corpus_add,
    corpora_index,
    corpora_list,
    entity_explain,
    evidence_detail,
    graph_rebuild,
    graph_expand,
    job_detail,
    jobs_list,
    ollama_models,
    provider_settings_save,
    provider_settings_show,
    resolver_inspect,
    resolver_profile_add,
    resolver_profile_validate,
    resolver_profiles_list,
    run_acceptance,
    search_evidence,
    semantic_edges_generate_batch,
    semantic_edges_generate,
)


class McpToolsTests(unittest.TestCase):
    def test_search_evidence_returns_live_sqlite_rows(self):
        result = search_evidence("doorbell interrupt disable")

        self.assertTrue(result["query_id"].endswith("doorbell_interrupt_disable"))
        self.assertEqual(result["source"], "sqlite")
        self.assertTrue(any("DOORBELL" in row["symbol"] for row in result["rows"]))

    def test_search_evidence_reads_explicit_empty_db_without_default_index_fallback(self):
        with TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "empty.db")
            _create_empty_sqlite_db(db_path)

            result = search_evidence("GCVM_L2_CNTL", db_path=db_path)

            self.assertEqual(result["source"], "sqlite")
            self.assertEqual(result["rows"], [])
            self.assertTrue(result["empty"])

    def test_search_evidence_explicit_missing_db_does_not_auto_index_or_create_db(self):
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "missing.db"

            result = search_evidence("GCVM_L2_CNTL", db_path=str(db_path))

            self.assertFalse(db_path.exists())
            self.assertEqual(result["rows"], [])
            self.assertTrue(result["empty"])

    def test_graph_expand_returns_live_weighted_edges(self):
        result = graph_expand("GCVM_L2_CNTL")

        self.assertTrue(any(edge["relation"] == "sets_field" for edge in result["edges"]))
        self.assertTrue(any(node["kind"] == "register" and node["label"] == "GCVM_L2_CNTL" for node in result["nodes"]))

    def test_graph_expand_reads_explicit_empty_db_without_default_index_fallback(self):
        with TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "empty.db")
            _create_empty_sqlite_db(db_path)

            result = graph_expand("GCVM_L2_CNTL", db_path=db_path)

            self.assertEqual(result["query_id"], "GCVM_L2_CNTL")
            self.assertEqual(result["edges"], [])
            self.assertEqual([node["id"] for node in result["nodes"]], ["GCVM_L2_CNTL"])

    def test_graph_expand_explicit_missing_db_does_not_auto_index_or_create_db(self):
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "missing.db"

            result = graph_expand("GCVM_L2_CNTL", db_path=str(db_path))

            self.assertFalse(db_path.exists())
            self.assertEqual(result["query_id"], "GCVM_L2_CNTL")
            self.assertEqual(result["edges"], [])
            self.assertEqual([node["id"] for node in result["nodes"]], ["GCVM_L2_CNTL"])

    def test_semantic_edges_tool_generates_edges_from_live_db(self):
        server = _start_fake_edge_server()
        try:
            with TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                corpus_root = root / "corpus"
                corpus_root.mkdir()
                (corpus_root / "note.md").write_text(
                    "GCVM_L2_CNTL has field ENABLE_L2_CACHE for MCP semantic edge generation.",
                    encoding="utf-8",
                )
                db_path = str(root / "asip.db")
                provider_settings_save(
                    {
                        "edge": {
                            "provider": "ollama",
                            "base_url": server.base_url,
                            "api_path": "/api/chat",
                            "model": "gemma4:e4b",
                            "timeout_seconds": 2,
                        }
                    },
                    db_path=db_path,
                )
                corpus_add(
                    db_path=db_path,
                    corpus_id="mcp-edge-docs",
                    repo="local",
                    source_root=str(corpus_root),
                    include=["**/*.md"],
                    corpus_type="doc",
                )
                corpora_index(db_path=db_path, corpus_ids=["mcp-edge-docs"])

                result = semantic_edges_generate("GCVM_L2_CNTL ENABLE_L2_CACHE", db_path=db_path)

                self.assertEqual(result["source"], "semantic_edge_job")
                self.assertEqual(result["edge_count"], 1)
                register_nodes = [
                    node
                    for node in result["graph"]["nodes"]
                    if node["kind"] == "register" and node["label"] == "GCVM_L2_CNTL"
                ]
                self.assertTrue(register_nodes)
                self.assertIn("ENABLE_L2_CACHE", register_nodes[0]["attr"]["fields"])
                self.assertFalse(any(edge["dst"] == "ENABLE_L2_CACHE" for edge in result["graph"]["edges"]))
        finally:
            server.shutdown()
            server.server_close()

    def test_semantic_edges_batch_tool_generates_edges_from_indexed_candidates(self):
        server = _start_fake_edge_server()
        try:
            with TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                corpus_root = root / "corpus"
                corpus_root.mkdir()
                (corpus_root / "note.md").write_text(
                    "# MCP semantic batch\n"
                    "GCVM_L2_CNTL has field ENABLE_L2_CACHE for MCP batch semantic edge generation.",
                    encoding="utf-8",
                )
                db_path = str(root / "asip.db")
                provider_settings_save(
                    {
                        "edge": {
                            "provider": "ollama",
                            "base_url": server.base_url,
                            "api_path": "/api/chat",
                            "model": "gemma4:e4b",
                            "timeout_seconds": 2,
                        }
                    },
                    db_path=db_path,
                )
                corpus_add(
                    db_path=db_path,
                    corpus_id="mcp-edge-batch-docs",
                    repo="local",
                    source_root=str(corpus_root),
                    include=["**/*.md"],
                    corpus_type="doc",
                )
                corpora_index(db_path=db_path, corpus_ids=["mcp-edge-batch-docs"])

                result = semantic_edges_generate_batch(db_path=db_path, limit=4, batch_size=2)

                self.assertEqual(result["source"], "semantic_edge_batch_job")
                self.assertEqual(result["edge_count"], 1)
                self.assertGreaterEqual(result["candidate_count"], 1)
                register_nodes = [
                    node
                    for node in result["graph"]["nodes"]
                    if node["kind"] == "register" and node["label"] == "GCVM_L2_CNTL"
                ]
                self.assertTrue(register_nodes)
                self.assertIn("ENABLE_L2_CACHE", register_nodes[0]["attr"]["fields"])
        finally:
            server.shutdown()
            server.server_close()

    def test_resolver_inspect_reads_committed_profile(self):
        result = resolver_inspect("linux-amdgpu")

        self.assertEqual(result["id"], "linux-amdgpu")
        self.assertIn("WREG32_SOC15", result["wrappers"])
        self.assertIn("REG_SET_FIELD", result["wrappers"])

    def test_acceptance_runs_lists_real_qa_artifacts(self):
        runs = acceptance_runs()

        self.assertTrue(any(run["id"] == "qwen35-strict-batch1" for run in runs))
        self.assertTrue(any(run["id"] == "gemma4-e4b-strict-batch1" for run in runs))
        acceptance = next(run for run in runs if run["id"] == "acceptance-clean-qwen35")
        self.assertEqual(acceptance["model"], "asip.acceptance")
        self.assertEqual(acceptance["partial"], 8)
        self.assertEqual(acceptance["failed"], 1)

    def test_run_acceptance_executes_single_query_for_mcp_surface(self):
        result = run_acceptance(query_ids=["AQ01"], surfaces=["MCP"])

        self.assertEqual(result["source"], "asip.acceptance")
        self.assertEqual(result["summary"]["total"], 1)
        self.assertEqual(result["queries"][0]["id"], "AQ01")
        self.assertIn("MCP", result["surfaces_checked"])
        self.assertIn("MCP", result["queries"][0]["surfaces_checked"])

    def test_run_acceptance_explicit_missing_db_reports_failure_without_creating_db(self):
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "missing.db"

            result = run_acceptance(query_ids=["AQ01"], surfaces=["MCP"], db_path=str(db_path))

            self.assertFalse(db_path.exists())
            self.assertEqual(result["summary"]["failed"], 1)
            self.assertIn("database does not exist", result["database_health"]["failure_reasons"][0])

    def test_corpus_tools_add_list_index_and_query_user_corpus(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            corpus_root = root / "corpus"
            corpus_root.mkdir()
            (corpus_root / "note.md").write_text(
                "API_CONTROL_REGISTER sets API_CONTROL_FIELD for MCP corpus indexing.",
                encoding="utf-8",
            )
            db_path = str(root / "asip.db")

            created = corpus_add(
                db_path=db_path,
                corpus_id="mcp-local-docs",
                repo="local",
                source_root=str(corpus_root),
                include=["**/*.md"],
                corpus_type="doc",
            )
            listed = corpora_list(db_path=db_path)
            indexed = corpora_index(db_path=db_path, corpus_ids=["mcp-local-docs"])
            queried = search_evidence("API_CONTROL_REGISTER", db_path=db_path)

            self.assertEqual(created["id"], "mcp-local-docs")
            self.assertTrue(any(corpus["id"] == "mcp-local-docs" for corpus in listed["corpora"]))
            self.assertEqual(indexed["source"], "registered_corpus")
            self.assertEqual(indexed["corpus_ids"], ["mcp-local-docs"])
            self.assertTrue(any(row["symbol"] == "API_CONTROL_REGISTER" for row in queried["rows"]))

    def test_corpora_index_passes_resolver_profile_ids_to_job_metadata(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            corpus_root = root / "corpus"
            corpus_root.mkdir()
            (corpus_root / "driver.py").write_text('@gpu_register("MCP_PROFILE_REGISTER")\n', encoding="utf-8")
            resolver_config = root / "mcp-profile.yaml"
            resolver_config.write_text(
                "\n".join(
                    [
                        "id: mcp-profile",
                        "language: python",
                        "context_vars: []",
                        "symbol_prefixes: []",
                        "python_extractors: [gpu_register]",
                        "wrappers: {}",
                    ]
                ),
                encoding="utf-8",
            )
            db_path = str(root / "asip.db")

            resolver_profile_add(
                db_path=db_path,
                profile_id="mcp-profile",
                language="python",
                wrappers=["gpu_register"],
                strategy="python-call",
                path=str(resolver_config),
                enabled=True,
            )
            corpus_add(
                db_path=db_path,
                corpus_id="mcp-profile-docs",
                repo="local",
                source_root=str(corpus_root),
                include=["**/*.py"],
                corpus_type="code",
            )

            indexed = corpora_index(
                db_path=db_path,
                corpus_ids=["mcp-profile-docs"],
                resolverProfileIds=["mcp-profile"],
            )
            detail = job_detail(indexed["job_id"], db_path=db_path)

            self.assertEqual(indexed["resolver_profile_ids"], ["mcp-profile"])
            self.assertEqual(detail["metadata"]["resolver_profile_ids"], ["mcp-profile"])

    def test_graph_rebuild_passes_resolver_profile_ids(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            corpus_root = root / "corpus"
            corpus_root.mkdir()
            (corpus_root / "driver.py").write_text('@gpu_register("MCP_REBUILD_REGISTER")\n', encoding="utf-8")
            resolver_config = root / "mcp-rebuild.yaml"
            resolver_config.write_text(
                "\n".join(
                    [
                        "id: mcp-rebuild",
                        "language: python",
                        "context_vars: []",
                        "symbol_prefixes: []",
                        "python_extractors: [gpu_register]",
                        "wrappers: {}",
                    ]
                ),
                encoding="utf-8",
            )
            db_path = str(root / "asip.db")
            resolver_profile_add(
                db_path=db_path,
                profile_id="mcp-rebuild",
                language="python",
                wrappers=["gpu_register"],
                strategy="python-call",
                path=str(resolver_config),
                enabled=True,
            )
            corpus_add(
                db_path=db_path,
                corpus_id="mcp-rebuild-docs",
                repo="local",
                source_root=str(corpus_root),
                include=["**/*.py"],
                corpus_type="code",
            )
            corpora_index(db_path=db_path, corpus_ids=["mcp-rebuild-docs"])

            rebuilt = graph_rebuild(
                db_path=db_path,
                corpus_ids=["mcp-rebuild-docs"],
                resolverProfileIds=["mcp-rebuild"],
            )

            self.assertEqual(rebuilt["source"], "deterministic_graph_rebuild")
            self.assertEqual(rebuilt["resolver_profile_ids"], ["mcp-rebuild"])

    def test_job_tools_expose_index_lifecycle_events(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            corpus_root = root / "corpus"
            corpus_root.mkdir()
            (corpus_root / "note.md").write_text(
                "MCP_JOB_REGISTER appears in durable job tests.",
                encoding="utf-8",
            )
            db_path = str(root / "asip.db")

            corpus_add(
                db_path=db_path,
                corpus_id="mcp-job-docs",
                repo="local",
                source_root=str(corpus_root),
                include=["**/*.md"],
                corpus_type="doc",
            )
            indexed = corpora_index(db_path=db_path, corpus_ids=["mcp-job-docs"])
            listed = jobs_list(db_path=db_path)
            detail = job_detail(indexed["job_id"], db_path=db_path)

            self.assertEqual(indexed["job_status"], "succeeded")
            self.assertEqual(detail["status"], "succeeded")
            self.assertEqual(detail["metadata"]["result_status"], "indexed")
            event_statuses = [event["status"] for event in detail["events"]]
            self.assertEqual(event_statuses[0], "queued")
            self.assertIn("indexing", event_statuses)
            self.assertEqual(event_statuses[-1], "succeeded")
            self.assertTrue(any(job["id"] == indexed["job_id"] for job in listed["jobs"]))

    def test_evidence_detail_and_entity_explain_use_live_sqlite_rows(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            corpus_root = root / "corpus"
            corpus_root.mkdir()
            (corpus_root / "note.md").write_text(
                "DETAIL_REGISTER sets DETAIL_FIELD for evidence detail inspection.",
                encoding="utf-8",
            )
            db_path = str(root / "asip.db")

            corpus_add(
                db_path=db_path,
                corpus_id="mcp-detail-docs",
                repo="local",
                source_root=str(corpus_root),
                include=["**/*.md"],
                corpus_type="doc",
            )
            corpora_index(db_path=db_path, corpus_ids=["mcp-detail-docs"])
            queried = search_evidence("DETAIL_REGISTER", db_path=db_path)
            evidence_id = int(queried["rows"][0]["id"])

            detail = evidence_detail(evidence_id=evidence_id, db_path=db_path)
            explained = entity_explain(symbol="DETAIL_REGISTER", db_path=db_path)

            self.assertEqual(detail["id"], evidence_id)
            self.assertEqual(detail["symbol"], "DETAIL_REGISTER")
            self.assertIn("resolved_chain", detail)
            self.assertEqual(explained["symbol"], "DETAIL_REGISTER")
            self.assertTrue(any(row["id"] == evidence_id for row in explained["evidence"]))
            self.assertIn("graph", explained)

    def test_evidence_detail_explicit_missing_db_returns_not_found_without_creating_db(self):
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "missing.db"

            with self.assertRaises(ValueError):
                evidence_detail(evidence_id=1, db_path=str(db_path))

            self.assertFalse(db_path.exists())

    def test_entity_explain_explicit_missing_db_returns_empty_without_creating_db(self):
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "missing.db"

            result = entity_explain(symbol="GCVM_L2_CNTL", db_path=str(db_path))

            self.assertFalse(db_path.exists())
            self.assertEqual(result["symbol"], "GCVM_L2_CNTL")
            self.assertEqual(result["evidence"], [])
            self.assertEqual(result["resolved_chains"], [])
            self.assertEqual(result["graph"]["edges"], [])

    def test_provider_settings_tools_round_trip_edge_and_embedding_settings(self):
        with TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "asip.db")
            settings = {
                "edge": {
                    "provider": "openai-compatible",
                    "base_url": "https://edge.example.test",
                    "api_path": "/v1/chat/completions",
                    "model": "edge-model",
                    "extra_headers": {"X-Edge": "yes"},
                },
                "embedding": {
                    "provider": "ollama",
                    "base_url": "http://localhost:11434",
                    "api_path": "/api/embeddings",
                    "model": "nomic-embed-text:latest",
                    "extra_headers": {"X-Embed": "yes"},
                },
            }

            saved = provider_settings_save(settings, db_path=db_path)
            loaded = provider_settings_show(db_path=db_path)

            self.assertEqual(saved["edge"]["model"], "edge-model")
            self.assertEqual(loaded["embedding"]["model"], "nomic-embed-text:latest")
            self.assertEqual(loaded["edge"]["extra_headers"]["X-Edge"], "yes")

    def test_provider_settings_show_empty_db_does_not_migrate_schema(self):
        with TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "empty.db")
            _create_empty_sqlite_db(db_path)

            loaded = provider_settings_show(db_path=db_path)

            self.assertEqual(loaded, {})
            self.assertFalse(_sqlite_table_exists(db_path, "provider_settings"))

    def test_ollama_detection_tool_reports_requested_url_and_failure(self):
        result = ollama_models(base_url="http://127.0.0.1:9", timeout_seconds=1)

        self.assertFalse(result["ok"])
        self.assertEqual(result["requested_url"], "http://127.0.0.1:9/api/tags")
        self.assertIn("error", result)

    def test_resolver_profile_tools_add_list_and_validate_dynamic_profile(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = str(root / "asip.db")
            resolver_config = root / "mcp-python.yaml"
            resolver_config.write_text(
                "\n".join(
                    [
                        "id: mcp-python",
                        "language: python",
                        "context_vars: []",
                        "symbol_prefixes: []",
                        "python_extractors: [gpu_register]",
                        "wrappers: {}",
                    ]
                ),
                encoding="utf-8",
            )

            created = resolver_profile_add(
                db_path=db_path,
                profile_id="mcp-python",
                language="python",
                wrappers=["gpu_register"],
                strategy="python-call",
                path=str(resolver_config),
                enabled=True,
            )
            listed = resolver_profiles_list(db_path=db_path)
            validation = resolver_profile_validate(
                db_path=db_path,
                profile_id="mcp-python",
                source='@gpu_register("MCP_DYNAMIC_REGISTER")',
            )

            self.assertEqual(created["id"], "mcp-python")
            self.assertTrue(any(profile["id"] == "mcp-python" for profile in listed["profiles"]))
            self.assertTrue(validation["valid"])
            self.assertEqual(validation["symbols"][0]["symbol"], "MCP_DYNAMIC_REGISTER")

    def test_resolver_profiles_list_empty_db_does_not_migrate_schema(self):
        with TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "empty.db")
            _create_empty_sqlite_db(db_path)

            listed = resolver_profiles_list(db_path=db_path)

            self.assertEqual(listed["profiles"], [])
            self.assertFalse(_sqlite_table_exists(db_path, "resolver_profiles"))

    def test_resolver_profile_validate_missing_db_does_not_create_schema(self):
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "missing.db"

            with self.assertRaises(KeyError):
                resolver_profile_validate(
                    db_path=str(db_path),
                    profile_id="missing-profile",
                    source='@gpu_register("MCP_DYNAMIC_REGISTER")',
                )

            self.assertFalse(db_path.exists())

    def test_corpora_list_empty_db_uses_config_fallback_without_migrating_schema(self):
        with TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "empty.db")
            _create_empty_sqlite_db(db_path)

            listed = corpora_list(db_path=db_path)

            self.assertTrue(any(corpus["id"] == "mxgpu" for corpus in listed["corpora"]))
            self.assertFalse(_sqlite_table_exists(db_path, "corpora"))


class _FakeEdgeServer(HTTPServer):
    base_url: str


class _FakeEdgeHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/api/chat":
            self.send_response(404)
            self.end_headers()
            return
        body = (
            b'{"message":{"content":"{\\"cases\\":[{\\"id\\":\\"workbench-query\\",'
            b'\\"edges\\":[{\\"src\\":\\"GCVM_L2_CNTL\\",\\"relation\\":\\"sets_field\\",'
            b'\\"dst\\":\\"ENABLE_L2_CACHE\\",\\"confidence\\":0.91,\\"evidence\\":\\"fixture\\"}]}]}"}}'
        )
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        return


def _start_fake_edge_server() -> _FakeEdgeServer:
    server = _FakeEdgeServer(("127.0.0.1", 0), _FakeEdgeHandler)
    server.base_url = f"http://127.0.0.1:{server.server_port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _create_empty_sqlite_db(db_path: str) -> None:
    import sqlite3

    con = sqlite3.connect(db_path)
    con.execute("create table marker(id integer)")
    con.commit()
    con.close()


def _sqlite_table_exists(db_path: str, table_name: str) -> bool:
    import sqlite3

    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        row = con.execute(
            "select count(*) from sqlite_master where type='table' and name=?",
            (table_name,),
        ).fetchone()
        return bool(row and int(row[0]) > 0)
    finally:
        con.close()


if __name__ == "__main__":
    unittest.main()
