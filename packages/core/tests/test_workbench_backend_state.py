import sqlite3
import tempfile
import unittest
import json
from pathlib import Path

from asip.workbench import (
    add_corpus,
    add_resolver_profile,
    backfill_provider_embeddings,
    index_registered_corpora,
    list_resolver_profiles,
    load_provider_settings,
    query_evidence,
    save_provider_settings,
    validate_resolver_profile,
)


class FakeEmbeddingTransport:
    def __init__(self):
        self.requests = []

    def post_json(self, url, payload, headers, timeout):
        self.requests.append({"url": url, "payload": payload, "headers": dict(headers), "timeout": timeout})
        return {"embedding": [0.42, 0.24, 0.12]}


class FakeBatchEmbeddingTransport:
    def __init__(self):
        self.requests = []

    def post_json(self, url, payload, headers, timeout):
        self.requests.append({"url": url, "payload": payload, "headers": dict(headers), "timeout": timeout})
        return {"embeddings": [[float(index), float(index) + 0.5] for index, _ in enumerate(payload["input"])]}


class WorkbenchBackendStateTests(unittest.TestCase):
    def test_resolver_profile_is_persisted_and_validated_in_backend(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            profile_path = Path(tmpdir) / "local-python.yaml"
            profile_path.write_text(
                "\n".join(
                    [
                        "id: local-python",
                        "language: python",
                        "context_vars: []",
                        "symbol_prefixes: []",
                        "python_extractors: [gpu_register]",
                        "wrappers: {}",
                    ]
                ),
                encoding="utf-8",
            )

            added = add_resolver_profile(
                db_path,
                profile_id="local-python",
                language="python",
                wrappers=["gpu_register"],
                strategy="python-call",
                path=str(profile_path),
                enabled=True,
            )
            validation = validate_resolver_profile(db_path, "local-python", '@gpu_register("CP_INT_CNTL_RING0")')
            profiles = list_resolver_profiles(db_path)

            self.assertEqual(added["id"], "local-python")
            self.assertTrue(validation["valid"])
            self.assertEqual(validation["symbols"][0]["symbol"], "CP_INT_CNTL_RING0")
            self.assertEqual(profiles[0]["wrappers"], ["gpu_register"])

    def test_resolver_profile_requires_existing_yaml_config(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"

            with self.assertRaises(FileNotFoundError):
                add_resolver_profile(
                    db_path,
                    profile_id="missing-yaml",
                    language="cpp",
                    wrappers=["MISSING_WRAPPER"],
                    strategy="macro",
                    path=str(Path(tmpdir) / "missing-yaml.yaml"),
                    enabled=True,
                )

    def test_provider_settings_persist_and_are_recorded_on_selected_corpus_index_job(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            corpus_root = root / "docs"
            corpus_root.mkdir()
            profile_path = root / "custom-c.yaml"
            profile_path.write_text(
                "\n".join(
                    [
                        "id: custom-c",
                        "language: cpp",
                        "context_vars: []",
                        "symbol_prefixes: []",
                        "wrappers:",
                        "  CUSTOM_WRITE:",
                        "    symbol_arg: 0",
                        "    access: write",
                    ]
                ),
                encoding="utf-8",
            )
            (corpus_root / "note.md").write_text(
                "CP_INT_CNTL_RING0 sets CNTX_BUSY_INT_ENABLE before interrupt tests.",
                encoding="utf-8",
            )

            save_provider_settings(
                db_path,
                {
                    "edge": {"provider": "ollama", "base_url": "http://edge.local", "model": "gemma4:e4b"},
                    "embedding": {
                        "provider": "ollama",
                        "base_url": "http://127.0.0.1:9",
                        "model": "nomic-embed-text",
                        "timeout_seconds": 1,
                    },
                },
            )
            add_corpus(
                db_path,
                corpus_id="local-docs",
                repo="local",
                source_root=str(corpus_root),
                include=["**/*.md"],
                corpus_type="doc",
            )

            summary = index_registered_corpora(db_path, corpus_ids=["local-docs"])
            settings = load_provider_settings(db_path)
            query = query_evidence(db_path, "CP_INT_CNTL_RING0")

            self.assertEqual(summary["source"], "registered_corpus")
            self.assertEqual(summary["corpus_ids"], ["local-docs"])
            self.assertEqual(summary["provider_settings"]["edge"]["model"], "gemma4:e4b")
            self.assertEqual(settings["embedding"]["base_url"], "http://127.0.0.1:9")
            self.assertTrue(any(row["corpus_id"] == "local-docs" for row in query["rows"]))

    def test_resolver_profile_drives_indexed_evidence_and_embedding_provenance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            corpus_root = root / "driver"
            corpus_root.mkdir()
            profile_path = root / "custom-c.yaml"
            profile_path.write_text(
                "\n".join(
                    [
                        "id: custom-c",
                        "language: cpp",
                        "context_vars: []",
                        "symbol_prefixes: []",
                        "wrappers:",
                        "  CUSTOM_WRITE:",
                        "    symbol_arg: 0",
                        "    access: write",
                    ]
                ),
                encoding="utf-8",
            )
            (corpus_root / "custom.c").write_text(
                "void program(void) {\n"
                "  CUSTOM_WRITE(DoorbellRegister, 1);\n"
                "}\n",
                encoding="utf-8",
            )

            save_provider_settings(
                db_path,
                {
                    "edge": {"provider": "ollama", "base_url": "http://edge.local", "model": "gemma4:e4b"},
                    "embedding": {
                        "provider": "ollama",
                        "base_url": "http://127.0.0.1:9",
                        "model": "nomic-embed-text",
                        "timeout_seconds": 1,
                    },
                },
            )
            add_resolver_profile(
                db_path,
                profile_id="custom-c",
                language="cpp",
                wrappers=["CUSTOM_WRITE"],
                strategy="write",
                path=str(profile_path),
                enabled=True,
            )
            add_corpus(
                db_path,
                corpus_id="custom-driver",
                repo="local",
                source_root=str(corpus_root),
                include=["**/*.c"],
                corpus_type="code",
            )

            index_registered_corpora(db_path, corpus_ids=["custom-driver"])
            query = query_evidence(db_path, "DoorbellRegister")

            self.assertTrue(
                any(row["symbol"] == "DoorbellRegister" and row["access_type"] == "write" for row in query["rows"]),
                query["rows"],
            )
            self.assertTrue(any("custom-c" in row["resolved_chain"] for row in query["rows"]), query["rows"])

            con = sqlite3.connect(db_path)
            embedding = con.execute("select provider, model from embeddings").fetchone()
            self.assertEqual(embedding, ("ollama", "nomic-embed-text"))

    def test_indexing_calls_configured_embedding_provider_transport(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            corpus_root = root / "docs"
            corpus_root.mkdir()
            (corpus_root / "note.md").write_text(
                "CP_INT_CNTL_RING0 sets CNTX_BUSY_INT_ENABLE before interrupt tests.",
                encoding="utf-8",
            )
            transport = FakeEmbeddingTransport()

            save_provider_settings(
                db_path,
                {
                    "embedding": {
                        "provider": "ollama",
                        "base_url": "http://embed.local",
                        "api_path": "/api/embeddings",
                        "model": "nomic-embed-text",
                        "extra_headers": {"X-ASIP-Test": "transport"},
                        "timeout_seconds": 7,
                    },
                },
            )
            add_corpus(
                db_path,
                corpus_id="local-docs",
                repo="local",
                source_root=str(corpus_root),
                include=["**/*.md"],
                corpus_type="doc",
            )

            index_registered_corpora(db_path, corpus_ids=["local-docs"], embedding_transport=transport)

            self.assertEqual(len(transport.requests), 1)
            self.assertEqual(transport.requests[0]["url"], "http://embed.local/api/embeddings")
            self.assertEqual(transport.requests[0]["payload"]["model"], "nomic-embed-text")
            self.assertIn("CP_INT_CNTL_RING0", transport.requests[0]["payload"]["prompt"])
            self.assertEqual(transport.requests[0]["headers"]["X-ASIP-Test"], "transport")
            self.assertEqual(transport.requests[0]["timeout"], 7)

            con = sqlite3.connect(db_path)
            provider, model, vector_json, metadata_json = con.execute(
                "select provider, model, vector_json, metadata_json from embeddings"
            ).fetchone()
            self.assertEqual((provider, model), ("ollama", "nomic-embed-text"))
            self.assertEqual(json.loads(vector_json), [0.42, 0.24, 0.12])
            self.assertEqual(json.loads(metadata_json)["source"], "provider")

    def test_backfill_provider_embeddings_batches_existing_chunks_after_settings_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            corpus_root = root / "docs"
            corpus_root.mkdir()
            (corpus_root / "note.md").write_text(
                "CP_INT_CNTL_RING0 sets CNTX_BUSY_INT_ENABLE before interrupt tests.\n"
                "GCVM_L2_CNTL has ENABLE_L2_CACHE evidence.",
                encoding="utf-8",
            )
            add_corpus(
                db_path,
                corpus_id="local-docs",
                repo="local",
                source_root=str(corpus_root),
                include=["**/*.md"],
                corpus_type="doc",
            )
            index_registered_corpora(db_path, corpus_ids=["local-docs"])
            save_provider_settings(
                db_path,
                {
                    "embedding": {
                        "provider": "ollama",
                        "base_url": "http://embed.local",
                        "api_path": "/api/embed",
                        "model": "nomic-embed-text",
                        "timeout_seconds": 7,
                    },
                },
            )
            transport = FakeBatchEmbeddingTransport()

            summary = backfill_provider_embeddings(db_path, batch_size=2, embedding_transport=transport)

            self.assertEqual(summary["source"], "provider_embedding_backfill")
            self.assertEqual(summary["provider"], "ollama")
            self.assertEqual(summary["model"], "nomic-embed-text")
            self.assertEqual(summary["embedded_chunks"], 1)
            self.assertEqual(len(transport.requests), 1)
            self.assertEqual(transport.requests[0]["url"], "http://embed.local/api/embed")
            self.assertIn("CP_INT_CNTL_RING0", transport.requests[0]["payload"]["input"][0])

            con = sqlite3.connect(db_path)
            provider, model, metadata_json = con.execute(
                "select provider, model, metadata_json from embeddings"
            ).fetchone()
            self.assertEqual((provider, model), ("ollama", "nomic-embed-text"))
            self.assertEqual(json.loads(metadata_json)["source"], "provider")


if __name__ == "__main__":
    unittest.main()
