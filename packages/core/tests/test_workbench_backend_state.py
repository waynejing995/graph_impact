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
    _resolver_profiles_from_store,
)
from asip.storage import AsipStore


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


class FailingSecondBatchEmbeddingTransport:
    def __init__(self):
        self.requests = []

    def post_json(self, url, payload, headers, timeout):
        self.requests.append({"url": url, "payload": payload, "headers": dict(headers), "timeout": timeout})
        if len(self.requests) > 1:
            raise RuntimeError("provider stopped mid-backfill")
        return {"embeddings": [[float(index), float(index) + 0.5] for index, _ in enumerate(payload["input"])]}


class FakeContextLimitedBatchEmbeddingTransport:
    def __init__(self, max_inputs: int):
        self.max_inputs = max_inputs
        self.requests = []

    def post_json(self, url, payload, headers, timeout):
        self.requests.append({"url": url, "payload": payload, "headers": dict(headers), "timeout": timeout})
        if len(payload["input"]) > self.max_inputs:
            raise RuntimeError("embedding request failed with HTTP 400: the input length exceeds the context length")
        return {"embeddings": [[float(index), float(index) + 0.5] for index, _ in enumerate(payload["input"])]}


class FakeTextLengthLimitedEmbeddingTransport:
    def __init__(self, max_chars: int):
        self.max_chars = max_chars
        self.requests = []

    def post_json(self, url, payload, headers, timeout):
        self.requests.append({"url": url, "payload": payload, "headers": dict(headers), "timeout": timeout})
        too_long = [text for text in payload["input"] if len(text) > self.max_chars]
        if too_long:
            raise RuntimeError("embedding request failed with HTTP 400: the input length exceeds the context length")
        return {"embeddings": [[float(len(text)), float(len(text)) + 0.5] for text in payload["input"]]}


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

    def test_inline_resolver_profile_config_controls_function_concept_normalization(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            added = add_resolver_profile(
                db_path,
                profile_id="inline-concepts",
                language="cpp",
                wrappers=["CUSTOM_WRITE"],
                strategy="macro",
                path="inline:inline-concepts",
                enabled=True,
                config={
                    "id": "inline-concepts",
                    "language": "cpp",
                    "wrappers": {"CUSTOM_WRITE": {"symbol_arg": 0, "access": "write"}},
                    "graph": {
                        "function_normalization": {
                            "enabled": True,
                            "rules": [
                                {
                                    "id": "inline-ip-versioned-functions",
                                    "enabled": True,
                                    "match": r"^(?P<ip_block>gfxhub)_rev(?P<ip_version>\d+)_(?P<operation>.+)$",
                                    "canonical": "inline_{operation}",
                                }
                            ],
                        }
                    },
                },
            )
            store = AsipStore.connect(str(db_path))
            store.add_edge(
                "gfxhub_rev12_gart_enable",
                "GCVM_L2_CNTL",
                "writes",
                0.95,
                stage="deterministic",
                source="clang_text_spans",
                path="drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
                line_start=10,
                line_end=10,
                provenance={
                    "extractor": "code_graph",
                    "function": "gfxhub_rev12_gart_enable",
                    "resolver_profile": "inline-concepts",
                    "corpus_id": "custom-driver",
                    "repo": "local",
                    "path": "drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
                },
            )

            graph = store.global_graph_networkx(limit=100, function_view="concept")

            function_node = next(node for node in graph["nodes"] if node["kind"] == "function")
            self.assertEqual(added["path"], "inline:inline-concepts")
            self.assertEqual(
                function_node["id"],
                "function:custom-driver:concept:inline-concepts:inline-ip-versioned-functions:inline_gart_enable",
            )
            self.assertEqual(function_node["attr"]["normalization_rule"], "inline-ip-versioned-functions")
            self.assertEqual(function_node["attr"]["normalization_profile_id"], "inline-concepts")

    def test_resolver_profile_migrates_old_table_without_config_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            profile_path = root / "legacy-c.yaml"
            profile_path.write_text(
                "\n".join(
                    [
                        "id: legacy-c",
                        "language: cpp",
                        "context_vars: []",
                        "symbol_prefixes: [reg, mm]",
                        "wrappers:",
                        "  CUSTOM_WRITE:",
                        "    symbol_arg: 0",
                        "    access: write",
                    ]
                ),
                encoding="utf-8",
            )
            con = sqlite3.connect(db_path)
            con.execute(
                """
                create table resolver_profiles (
                  id text primary key,
                  language text not null,
                  wrappers_json text not null,
                  strategy text not null,
                  path text not null,
                  enabled integer not null default 1
                )
                """
            )
            con.commit()
            con.close()

            add_resolver_profile(
                db_path,
                profile_id="legacy-c",
                language="cpp",
                wrappers=["CUSTOM_WRITE"],
                strategy="write",
                path=str(profile_path),
                enabled=True,
            )
            validation = validate_resolver_profile(db_path, "legacy-c", "CUSTOM_WRITE(regGCVM_L2_CNTL, 1);")

            self.assertTrue(validation["valid"])
            self.assertEqual(validation["symbols"][0]["symbol"], "GCVM_L2_CNTL")

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

    def test_selected_resolver_profiles_limit_registered_index_evidence_and_graph(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            corpus_root = root / "driver"
            corpus_root.mkdir()
            selected_profile = root / "custom-a.yaml"
            selected_profile.write_text(
                "\n".join(
                    [
                        "id: custom-a",
                        "language: cpp",
                        "context_vars: []",
                        "symbol_prefixes: []",
                        "wrappers:",
                        "  CUSTOM_A:",
                        "    symbol_arg: 0",
                        "    access: write",
                    ]
                ),
                encoding="utf-8",
            )
            unselected_profile = root / "custom-b.yaml"
            unselected_profile.write_text(
                "\n".join(
                    [
                        "id: custom-b",
                        "language: cpp",
                        "context_vars: []",
                        "symbol_prefixes: []",
                        "wrappers:",
                        "  CUSTOM_B:",
                        "    symbol_arg: 0",
                        "    access: write",
                    ]
                ),
                encoding="utf-8",
            )
            (corpus_root / "custom.c").write_text(
                "void program(void) {\n"
                "  CUSTOM_A(SelectedReg, 1);\n"
                "  CUSTOM_B(UnselectedReg, 1);\n"
                "}\n",
                encoding="utf-8",
            )
            add_resolver_profile(
                db_path,
                profile_id="custom-a",
                language="cpp",
                wrappers=["CUSTOM_A"],
                strategy="write",
                path=str(selected_profile),
                enabled=True,
            )
            add_resolver_profile(
                db_path,
                profile_id="custom-b",
                language="cpp",
                wrappers=["CUSTOM_B"],
                strategy="write",
                path=str(unselected_profile),
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

            summary = index_registered_corpora(
                db_path,
                corpus_ids=["custom-driver"],
                resolver_profile_ids=["custom-a"],
            )
            selected_query = query_evidence(db_path, "SelectedReg")
            unselected_query = query_evidence(db_path, "UnselectedReg")

            self.assertEqual(summary["resolver_profile_ids"], ["custom-a"])
            self.assertTrue(
                any(row["symbol"] == "SelectedReg" and "custom-a" in row["resolved_chain"] for row in selected_query["rows"]),
                selected_query["rows"],
            )
            self.assertFalse(
                any(row["symbol"] == "UnselectedReg" and "custom-b" in row["resolved_chain"] for row in unselected_query["rows"]),
                unselected_query["rows"],
            )
            con = sqlite3.connect(db_path)
            graph_edges = {
                (row[0], row[1], row[2], row[3])
                for row in con.execute(
                    """
                    select src, relation, dst, json_extract(provenance_json, '$.resolver_profile')
                    from edges
                    where source in ('clang_text_spans', 'clang_preprocess', 'text_fallback')
                    """
                )
            }
            self.assertIn(("program", "writes", "SelectedReg", "custom-a"), graph_edges)
            self.assertNotIn(("program", "writes", "UnselectedReg", "custom-b"), graph_edges)
            job_metadata = json.loads(
                con.execute("select metadata_json from jobs order by id desc limit 1").fetchone()[0]
            )
            self.assertEqual(job_metadata["resolver_profile_ids"], ["custom-a"])

    def test_disabled_db_resolver_profile_overrides_default_index_profiles(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.upsert_resolver_profile(
                "linux-amdgpu",
                "cpp",
                ["WREG32"],
                "write",
                "configs/resolvers/linux-amdgpu.yaml",
                enabled=False,
            )

            profiles = _resolver_profiles_from_store(store)

            self.assertNotIn("linux-amdgpu", {profile.id for profile in profiles})

    def test_disabled_db_resolver_profile_alias_overrides_loaded_default_index_profile(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.upsert_resolver_profile(
                "alias-linux",
                "cpp",
                ["WREG32"],
                "write",
                "configs/resolvers/linux-amdgpu.yaml",
                enabled=False,
            )

            profiles = _resolver_profiles_from_store(store)

            profile_ids = {profile.id for profile in profiles}
            self.assertNotIn("alias-linux", profile_ids)
            self.assertNotIn("linux-amdgpu", profile_ids)

    def test_persisted_resolver_profile_keeps_configured_argument_positions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            corpus_root = root / "driver"
            corpus_root.mkdir()
            profile_path = root / "custom-field.yaml"
            profile_path.write_text(
                "\n".join(
                    [
                        "id: custom-field",
                        "language: cpp",
                        "context_vars: []",
                        "symbol_prefixes: [reg, mm]",
                        "wrappers:",
                        "  CUSTOM_FIELD_SET:",
                        "    symbol_args: [1, 2]",
                        "    access: field_set",
                    ]
                ),
                encoding="utf-8",
            )
            (corpus_root / "custom.c").write_text(
                "void program(void) {\n"
                "  CUSTOM_FIELD_SET(tmp, regGCVM_L2_CNTL, ENABLE_L2_CACHE, 1);\n"
                "}\n",
                encoding="utf-8",
            )

            add_resolver_profile(
                db_path,
                profile_id="custom-field",
                language="cpp",
                wrappers=["CUSTOM_FIELD_SET"],
                strategy="field_set",
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
            query = query_evidence(db_path, "GCVM_L2_CNTL ENABLE_L2_CACHE")
            rows_by_symbol = {row["symbol"]: row for row in query["rows"]}

            self.assertIn("GCVM_L2_CNTL", rows_by_symbol)
            self.assertIn("ENABLE_L2_CACHE", rows_by_symbol)
            self.assertEqual(rows_by_symbol["GCVM_L2_CNTL"]["access_type"], "field_set")
            self.assertIn("CUSTOM_FIELD_SET", rows_by_symbol["GCVM_L2_CNTL"]["resolved_chain"])

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

    def test_backfill_provider_embeddings_splits_context_too_large_batches(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            document_id = store.add_document("docs", "doc", "docs/note.md")
            for index in range(4):
                store.add_chunk(document_id, f"chunk {index} GCVM_L2_CNTL ENABLE_L2_CACHE", index + 1, index + 1)
            save_provider_settings(
                db_path,
                {
                    "embedding": {
                        "provider": "ollama",
                        "base_url": "http://embed.local",
                        "api_path": "/api/embed",
                        "model": "nomic-embed-text",
                    },
                },
            )
            transport = FakeContextLimitedBatchEmbeddingTransport(max_inputs=2)

            summary = backfill_provider_embeddings(db_path, batch_size=4, embedding_transport=transport)

            self.assertEqual(summary["embedded_chunks"], 4)
            self.assertEqual(summary["provider_input_count"], 4)
            self.assertEqual(summary["provider_request_count"], 3)
            self.assertEqual(summary["provider_input_attempt_count"], 8)
            self.assertEqual([len(request["payload"]["input"]) for request in transport.requests], [4, 2, 2])
            con = sqlite3.connect(db_path)
            self.assertEqual(con.execute("select count(*) from embeddings").fetchone()[0], 4)
            status, message, metadata_json = con.execute(
                "select status, message, metadata_json from jobs order by id desc limit 1"
            ).fetchone()
            metadata = json.loads(metadata_json)
            self.assertEqual(status, "succeeded")
            self.assertIn("provider attempts 8 inputs/3 requests", message)
            self.assertEqual(metadata["provider_request_count"], 3)
            self.assertEqual(metadata["provider_input_attempt_count"], 8)

    def test_backfill_provider_embeddings_shortens_single_context_too_large_input(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            document_id = store.add_document("docs", "doc", "docs/long.md")
            store.add_chunk(document_id, "GCVM_L2_CNTL " + ("very_long_code_token " * 20), 1, 1)
            save_provider_settings(
                db_path,
                {
                    "embedding": {
                        "provider": "ollama",
                        "base_url": "http://embed.local",
                        "api_path": "/api/embed",
                        "model": "nomic-embed-text",
                    },
                },
            )
            transport = FakeTextLengthLimitedEmbeddingTransport(max_chars=64)

            summary = backfill_provider_embeddings(db_path, batch_size=1, embedding_transport=transport)

            self.assertEqual(summary["embedded_chunks"], 1)
            self.assertEqual(summary["context_retry_chunks"], 1)
            self.assertEqual(summary["provider_request_count"], len(transport.requests))
            self.assertEqual(summary["provider_input_attempt_count"], len(transport.requests))
            self.assertGreater(len(transport.requests), 1)
            self.assertLessEqual(len(transport.requests[-1]["payload"]["input"][0]), 64)
            con = sqlite3.connect(db_path)
            metadata_json, vector_json = con.execute("select metadata_json, vector_json from embeddings").fetchone()
            metadata = json.loads(metadata_json)
            self.assertEqual(metadata["source"], "provider")
            self.assertTrue(metadata["embedding_context_retry"])
            self.assertTrue(metadata["embedding_text_truncated"])
            self.assertLessEqual(metadata["embedding_text_chars"], 64)
            self.assertGreater(metadata["original_embedding_text_chars"], metadata["embedding_text_chars"])
            self.assertEqual(json.loads(vector_json)[0], float(metadata["embedding_text_chars"]))

    def test_backfill_provider_embeddings_replaces_deterministic_fallback_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            document_id = store.add_document("docs", "doc", "docs/note.md")
            fallback_chunk_id = store.add_chunk(document_id, "fallback GCVM_L2_CNTL evidence", 1, 1)
            provider_chunk_id = store.add_chunk(document_id, "already provider-backed evidence", 2, 2)
            store.add_embedding(
                fallback_chunk_id,
                provider="ollama",
                model="nomic-embed-text",
                vector=[0.1, 0.2],
                metadata={"source": "deterministic-fallback"},
            )
            store.add_embedding(
                provider_chunk_id,
                provider="ollama",
                model="nomic-embed-text",
                vector=[0.3, 0.4],
                metadata={"source": "provider"},
            )
            save_provider_settings(
                db_path,
                {
                    "embedding": {
                        "provider": "ollama",
                        "base_url": "http://embed.local",
                        "api_path": "/api/embed",
                        "model": "nomic-embed-text",
                    },
                },
            )
            transport = FakeBatchEmbeddingTransport()

            summary = backfill_provider_embeddings(db_path, batch_size=2, embedding_transport=transport)

            self.assertEqual(summary["embedded_chunks"], 1)
            self.assertEqual(summary["requested_limit"], 0)
            self.assertIsNone(summary["applied_limit"])
            self.assertTrue(summary["limit_is_unlimited"])
            self.assertEqual(len(transport.requests), 1)
            self.assertEqual(transport.requests[0]["payload"]["input"], ["fallback GCVM_L2_CNTL evidence"])
            con = sqlite3.connect(db_path)
            rows = {
                chunk_id: json.loads(metadata_json)["source"]
                for chunk_id, metadata_json in con.execute("select chunk_id, metadata_json from embeddings")
            }
            self.assertEqual(rows[fallback_chunk_id], "provider")
            self.assertEqual(rows[provider_chunk_id], "provider")

    def test_backfill_provider_embeddings_dedupes_identical_inputs_within_run(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            document_id = store.add_document("docs", "doc", "docs/note.md")
            first_chunk_id = store.add_chunk(document_id, "duplicate GCVM_L2_CNTL evidence", 1, 1)
            second_chunk_id = store.add_chunk(document_id, "duplicate GCVM_L2_CNTL evidence", 2, 2)
            third_chunk_id = store.add_chunk(document_id, "unique CP_INT_CNTL_RING0 evidence", 3, 3)
            save_provider_settings(
                db_path,
                {
                    "embedding": {
                        "provider": "ollama",
                        "base_url": "http://embed.local",
                        "api_path": "/api/embed",
                        "model": "nomic-embed-text",
                    },
                },
            )
            transport = FakeBatchEmbeddingTransport()

            summary = backfill_provider_embeddings(db_path, batch_size=8, embedding_transport=transport)

            self.assertEqual(summary["embedded_chunks"], 3)
            self.assertEqual(summary["provider_input_count"], 2)
            self.assertEqual(summary["deduped_chunks"], 1)
            self.assertEqual(len(transport.requests), 1)
            self.assertEqual(
                transport.requests[0]["payload"]["input"],
                ["duplicate GCVM_L2_CNTL evidence", "unique CP_INT_CNTL_RING0 evidence"],
            )
            con = sqlite3.connect(db_path)
            rows = {
                chunk_id: json.loads(vector_json)
                for chunk_id, vector_json in con.execute("select chunk_id, vector_json from embeddings")
            }
            self.assertEqual(rows[first_chunk_id], rows[second_chunk_id])
            self.assertNotEqual(rows[first_chunk_id], rows[third_chunk_id])

    def test_backfill_provider_embeddings_persists_completed_batches_before_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            document_id = store.add_document("docs", "doc", "docs/note.md")
            first_chunk_id = store.add_chunk(document_id, "first GCVM_L2_CNTL evidence", 1, 1)
            second_chunk_id = store.add_chunk(document_id, "second GCVM_L2_CNTL evidence", 2, 2)
            third_chunk_id = store.add_chunk(document_id, "third GCVM_L2_CNTL evidence", 3, 3)
            save_provider_settings(
                db_path,
                {
                    "embedding": {
                        "provider": "ollama",
                        "base_url": "http://embed.local",
                        "api_path": "/api/embed",
                        "model": "nomic-embed-text",
                    },
                },
            )
            transport = FailingSecondBatchEmbeddingTransport()

            with self.assertRaises(RuntimeError):
                backfill_provider_embeddings(db_path, batch_size=2, embedding_transport=transport)

            con = sqlite3.connect(db_path)
            embedded_chunk_ids = {
                row[0] for row in con.execute("select chunk_id from embeddings order by chunk_id").fetchall()
            }
            self.assertEqual(embedded_chunk_ids, {first_chunk_id, second_chunk_id})
            self.assertNotIn(third_chunk_id, embedded_chunk_ids)
            job = con.execute("select status, message, metadata_json from jobs order by id desc limit 1").fetchone()
            self.assertEqual(job[0], "failed")
            self.assertIn("provider stopped mid-backfill", job[1])
            metadata = json.loads(job[2])
            self.assertEqual(metadata["embedded_chunks"], 2)
            self.assertEqual(metadata["total_candidates"], 3)
            self.assertEqual(metadata["provider_request_count"], 2)
            self.assertEqual(metadata["provider_input_attempt_count"], 3)

    def test_backfill_provider_embeddings_truncates_long_inputs_with_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            document_id = store.add_document("docs", "doc", "docs/large-section.md")
            store.add_chunk(document_id, "A" * 5000, 1, 200)
            save_provider_settings(
                db_path,
                {
                    "embedding": {
                        "provider": "ollama",
                        "base_url": "http://embed.local",
                        "api_path": "/api/embed",
                        "model": "nomic-embed-text",
                    },
                },
            )
            transport = FakeBatchEmbeddingTransport()

            summary = backfill_provider_embeddings(db_path, batch_size=1, embedding_transport=transport)

            self.assertEqual(summary["embedded_chunks"], 1)
            self.assertEqual(summary["truncated_chunks"], 1)
            self.assertEqual(len(transport.requests[0]["payload"]["input"][0]), 4096)
            con = sqlite3.connect(db_path)
            metadata_json = con.execute("select metadata_json from embeddings").fetchone()[0]
            metadata = json.loads(metadata_json)
            self.assertEqual(metadata["source"], "provider")
            self.assertTrue(metadata["embedding_text_truncated"])
            self.assertEqual(metadata["embedding_text_chars"], 4096)
            self.assertEqual(metadata["original_text_chars"], 5000)

    def test_query_evidence_uses_configured_vector_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            document_id = store.add_document("docs", "doc", "docs/vector.md")
            chunk_id = store.add_chunk(document_id, "GCVM_L2_CNTL ENABLE_L2_CACHE", 1, 1)
            store.add_evidence(
                chunk_id=chunk_id,
                corpus_id="docs",
                source_type="doc",
                repo="local",
                path="docs/vector.md",
                symbol="GCVM_L2_CNTL",
                entity_type="register",
                access_type="mention",
                confidence=0.9,
                snippet="GCVM_L2_CNTL ENABLE_L2_CACHE",
                resolved_chain="doc -> GCVM_L2_CNTL",
            )
            observed_limits = []
            original_search_vector = AsipStore.search_vector

            def recording_search_vector(self, vector, limit):
                observed_limits.append(limit)
                return []

            try:
                AsipStore.search_vector = recording_search_vector
                query_evidence(db_path, "cache enable flow")
            finally:
                AsipStore.search_vector = original_search_vector

            self.assertEqual(observed_limits, [5])


if __name__ == "__main__":
    unittest.main()
