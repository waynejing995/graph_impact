import unittest
import json
import socket
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient
import uvicorn

from apps.api.main import app


class ApiAppTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_query_endpoint_returns_real_evidence(self):
        response = self.client.get("/query", params={"q": "doorbell interrupt disable"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["query_id"], "mxgpu_doorbell_interrupt_disable")
        self.assertEqual(payload["source"], "sqlite")
        self.assertTrue(any("DOORBELL_INTERRUPT_DISABLE" in row["symbol"] for row in payload["rows"]))

    def test_live_uvicorn_server_serves_http_without_testclient(self):
        with TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "missing.db")
            server, thread, base_url = _start_uvicorn_server()
            try:
                with urllib.request.urlopen(
                    f"{base_url}/providers/settings?db_path={db_path}",
                    timeout=5,
                ) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.should_exit = True
                thread.join(timeout=5)

            self.assertEqual(payload, {})
            self.assertFalse(Path(db_path).exists())

    def test_graph_endpoint_expands_query_edges(self):
        response = self.client.get("/graph", params={"query_id": "GCVM_L2_CNTL"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(any(edge["relation"] == "sets_field" for edge in payload["edges"]))

    def test_graph_endpoint_honors_explicit_empty_db_path_without_default_fallback(self):
        with TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "empty.db")
            _create_empty_sqlite_db(db_path)

            response = self.client.get("/graph", params={"query_id": "GCVM_L2_CNTL", "db_path": db_path})

            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["edges"], [])
            self.assertEqual([node["id"] for node in payload["nodes"]], ["GCVM_L2_CNTL"])

    def test_query_endpoint_explicit_missing_db_does_not_create_or_default_index(self):
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "missing.db"

            response = self.client.get("/query", params={"q": "GCVM_L2_CNTL", "db_path": str(db_path)})

            self.assertEqual(response.status_code, 200)
            self.assertFalse(db_path.exists())
            self.assertEqual(response.json()["rows"], [])

    def test_evidence_endpoint_explicit_missing_db_returns_404_without_creating_db(self):
        with TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "missing.db"

            response = self.client.get("/evidence/1", params={"db_path": str(db_path)})

            self.assertEqual(response.status_code, 404)
            self.assertFalse(db_path.exists())

    def test_semantic_edges_endpoint_generates_edges_from_live_db(self):
        server = _start_fake_edge_server()
        try:
            with TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                corpus_root = root / "corpus"
                corpus_root.mkdir()
                (corpus_root / "note.md").write_text(
                    "GCVM_L2_CNTL has field ENABLE_L2_CACHE for FastAPI semantic edge generation.",
                    encoding="utf-8",
                )
                db_path = str(root / "asip.db")
                self.client.post(
                    "/providers/settings",
                    json={
                        "db_path": db_path,
                        "settings": {
                            "edge": {
                                "provider": "ollama",
                                "base_url": server.base_url,
                                "api_path": "/api/chat",
                                "model": "gemma4:e4b",
                                "timeout_seconds": 2,
                            }
                        },
                    },
                )
                self.client.post(
                    "/corpora",
                    json={
                        "db_path": db_path,
                        "id": "api-edge-docs",
                        "repo": "local",
                        "source_root": str(corpus_root),
                        "include": ["**/*.md"],
                        "type": "doc",
                    },
                )
                self.client.post("/index", json={"db_path": db_path, "corpus_ids": ["api-edge-docs"]})

                response = self.client.post(
                    "/semantic-edges",
                    json={"db_path": db_path, "q": "GCVM_L2_CNTL ENABLE_L2_CACHE"},
                )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["source"], "semantic_edge_job")
                self.assertEqual(payload["edge_count"], 1)
                self.assertTrue(any(edge["dst"] == "ENABLE_L2_CACHE" for edge in payload["graph"]["edges"]))
        finally:
            server.shutdown()
            server.server_close()

    def test_semantic_edges_endpoint_runs_batch_generation(self):
        server = _start_fake_edge_server()
        try:
            with TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                corpus_root = root / "corpus"
                corpus_root.mkdir()
                (corpus_root / "note.md").write_text(
                    "# FastAPI semantic batch\n"
                    "GCVM_L2_CNTL has field ENABLE_L2_CACHE for FastAPI batch semantic edge generation.",
                    encoding="utf-8",
                )
                db_path = str(root / "asip.db")
                self.client.post(
                    "/providers/settings",
                    json={
                        "db_path": db_path,
                        "settings": {
                            "edge": {
                                "provider": "ollama",
                                "base_url": server.base_url,
                                "api_path": "/api/chat",
                                "model": "gemma4:e4b",
                                "timeout_seconds": 2,
                            }
                        },
                    },
                )
                self.client.post(
                    "/corpora",
                    json={
                        "db_path": db_path,
                        "id": "api-edge-batch-docs",
                        "repo": "local",
                        "source_root": str(corpus_root),
                        "include": ["**/*.md"],
                        "type": "doc",
                    },
                )
                self.client.post("/index", json={"db_path": db_path, "corpus_ids": ["api-edge-batch-docs"]})

                response = self.client.post(
                    "/semantic-edges",
                    json={"db_path": db_path, "mode": "batch", "limit": 4, "batch_size": 2},
                )

                self.assertEqual(response.status_code, 200)
                payload = response.json()
                self.assertEqual(payload["source"], "semantic_edge_batch_job")
                self.assertEqual(payload["edge_count"], 1)
                self.assertGreaterEqual(payload["candidate_count"], 1)
                self.assertTrue(any(node["kind"] == "doc_section" for node in payload["graph"]["nodes"]))
        finally:
            server.shutdown()
            server.server_close()

    def test_resolver_and_acceptance_endpoints_are_available(self):
        resolver = self.client.get("/resolver-profiles/linux-amdgpu")
        acceptance = self.client.get("/acceptance/runs")

        self.assertEqual(resolver.status_code, 200)
        self.assertIn("WREG32_SOC15", resolver.json()["wrappers"])
        self.assertEqual(acceptance.status_code, 200)
        self.assertTrue(any(run["id"] == "qwen35-strict-batch1" for run in acceptance.json()["runs"]))
        self.assertTrue(any(run["id"] == "acceptance-clean-qwen35" for run in acceptance.json()["runs"]))

    def test_acceptance_run_endpoint_executes_single_query_for_api_and_mcp_surfaces(self):
        response = self.client.post(
            "/acceptance/run",
            json={"query_ids": ["AQ01"], "surfaces": ["API", "MCP"]},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["source"], "asip.acceptance")
        self.assertEqual(payload["summary"]["total"], 1)
        self.assertEqual(payload["queries"][0]["id"], "AQ01")
        self.assertIn("API", payload["surfaces_checked"])
        self.assertIn("MCP", payload["surfaces_checked"])
        self.assertIn("API", payload["queries"][0]["surfaces_checked"])
        self.assertIn("MCP", payload["queries"][0]["surfaces_checked"])

    def test_corpus_endpoints_add_list_index_and_query_user_corpus(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            corpus_root = root / "corpus"
            corpus_root.mkdir()
            (corpus_root / "note.md").write_text(
                "API_ENDPOINT_REGISTER sets API_ENDPOINT_FIELD for FastAPI corpus indexing.",
                encoding="utf-8",
            )
            db_path = str(root / "asip.db")

            create = self.client.post(
                "/corpora",
                json={
                    "db_path": db_path,
                    "id": "api-local-docs",
                    "repo": "local",
                    "source_root": str(corpus_root),
                    "include": ["**/*.md"],
                    "type": "doc",
                },
            )
            listed = self.client.get("/corpora", params={"db_path": db_path})
            indexed = self.client.post("/index", json={"db_path": db_path, "corpus_ids": ["api-local-docs"]})
            queried = self.client.get("/query", params={"db_path": db_path, "q": "API_ENDPOINT_REGISTER"})

            self.assertEqual(create.status_code, 200)
            self.assertEqual(listed.status_code, 200)
            self.assertEqual(indexed.status_code, 200)
            self.assertEqual(queried.status_code, 200)
            self.assertTrue(any(corpus["id"] == "api-local-docs" for corpus in listed.json()["corpora"]))
            self.assertEqual(indexed.json()["source"], "registered_corpus")
            self.assertEqual(indexed.json()["corpus_ids"], ["api-local-docs"])
            self.assertTrue(any(row["symbol"] == "API_ENDPOINT_REGISTER" for row in queried.json()["rows"]))

    def test_evidence_and_entity_endpoints_return_live_detail_and_resolved_chain(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            corpus_root = root / "corpus"
            corpus_root.mkdir()
            (corpus_root / "note.md").write_text(
                "API_DETAIL_REGISTER sets API_DETAIL_FIELD for FastAPI evidence detail.",
                encoding="utf-8",
            )
            db_path = str(root / "asip.db")

            self.client.post(
                "/corpora",
                json={
                    "db_path": db_path,
                    "id": "api-detail-docs",
                    "repo": "local",
                    "source_root": str(corpus_root),
                    "include": ["**/*.md"],
                    "type": "doc",
                },
            )
            self.client.post("/index", json={"db_path": db_path, "corpus_ids": ["api-detail-docs"]})
            query = self.client.get("/query", params={"db_path": db_path, "q": "API_DETAIL_REGISTER"}).json()
            evidence_id = query["rows"][0]["id"]

            detail = self.client.get(f"/evidence/{evidence_id}", params={"db_path": db_path})
            entity = self.client.get("/entities/API_DETAIL_REGISTER", params={"db_path": db_path})

            self.assertEqual(detail.status_code, 200)
            self.assertEqual(entity.status_code, 200)
            self.assertEqual(detail.json()["id"], evidence_id)
            self.assertEqual(detail.json()["symbol"], "API_DETAIL_REGISTER")
            self.assertIn("resolved_chain", detail.json())
            self.assertTrue(any(row["id"] == evidence_id for row in entity.json()["evidence"]))
            self.assertIn("graph", entity.json())

    def test_provider_settings_endpoints_round_trip_edge_and_embedding_settings(self):
        with TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "asip.db")
            settings = {
                "edge": {
                    "provider": "openai-compatible",
                    "base_url": "https://api-edge.example.test",
                    "api_path": "/v1/chat/completions",
                    "model": "api-edge-model",
                },
                "embedding": {
                    "provider": "ollama",
                    "base_url": "http://localhost:11434",
                    "api_path": "/api/embeddings",
                    "model": "api-embed-model",
                },
            }

            save = self.client.post("/providers/settings", json={"db_path": db_path, "settings": settings})
            show = self.client.get("/providers/settings", params={"db_path": db_path})

            self.assertEqual(save.status_code, 200)
            self.assertEqual(show.status_code, 200)
            self.assertEqual(show.json()["edge"]["model"], "api-edge-model")
            self.assertEqual(show.json()["embedding"]["model"], "api-embed-model")

    def test_ollama_detection_endpoint_reports_requested_url_and_failure(self):
        response = self.client.get(
            "/providers/ollama-tags",
            params={"base_url": "http://127.0.0.1:9", "timeout_seconds": 1},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["requested_url"], "http://127.0.0.1:9/api/tags")
        self.assertIn("error", payload)

    def test_resolver_profile_endpoints_add_list_and_validate_dynamic_profile(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = str(root / "asip.db")
            resolver_config = root / "api-python.yaml"
            resolver_config.write_text(
                "\n".join(
                    [
                        "id: api-python",
                        "language: python",
                        "context_vars: []",
                        "symbol_prefixes: []",
                        "python_extractors: [gpu_register]",
                        "wrappers: {}",
                    ]
                ),
                encoding="utf-8",
            )

            create = self.client.post(
                "/resolver-profiles",
                json={
                    "db_path": db_path,
                    "id": "api-python",
                    "language": "python",
                    "wrappers": ["gpu_register"],
                    "strategy": "python-call",
                    "path": str(resolver_config),
                    "enabled": True,
                },
            )
            listed = self.client.get("/resolver-profiles", params={"db_path": db_path})
            validation = self.client.post(
                "/resolver-profiles/api-python/validate",
                json={"db_path": db_path, "source": '@gpu_register("API_DYNAMIC_REGISTER")'},
            )

            self.assertEqual(create.status_code, 200)
            self.assertEqual(listed.status_code, 200)
            self.assertEqual(validation.status_code, 200)
            self.assertTrue(any(profile["id"] == "api-python" for profile in listed.json()["profiles"]))
            self.assertTrue(validation.json()["valid"])
            self.assertEqual(validation.json()["symbols"][0]["symbol"], "API_DYNAMIC_REGISTER")


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


def _start_uvicorn_server():
    port = _free_port()
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        lifespan="off",
        ws="none",
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 5
    while not server.started:
        if time.time() > deadline:
            server.should_exit = True
            thread.join(timeout=5)
            raise RuntimeError("uvicorn test server did not start")
        if not thread.is_alive():
            raise RuntimeError("uvicorn test server stopped before startup")
        time.sleep(0.05)
    return server, thread, f"http://127.0.0.1:{port}"


def _free_port() -> int:
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])
    finally:
        sock.close()


def _create_empty_sqlite_db(db_path: str) -> None:
    import sqlite3

    con = sqlite3.connect(db_path)
    con.execute("create table marker(id integer)")
    con.commit()
    con.close()


if __name__ == "__main__":
    unittest.main()
