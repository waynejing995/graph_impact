import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asip import workbench
from asip.storage import AsipStore
from asip.workbench import graph_for_rows, index_configured_corpora, query_evidence

from workbench_fixture import write_live_fixture


REQUIRED_EVIDENCE_FIELDS = {
    "id",
    "source_type",
    "repo",
    "path",
    "line_start",
    "line_end",
    "symbol",
    "entity_type",
    "ip_block",
    "asic_or_generation",
    "access_type",
    "confidence",
    "snippet",
    "resolved_chain",
}


class WorkbenchQuerySchemaTests(unittest.TestCase):
    def test_graph_for_rows_returns_empty_multi_seed_graph_without_second_networkx_build(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.add_edge(
                "unrelated_writer",
                "UNRELATED_CNTL",
                "writes",
                0.95,
                stage="deterministic",
                source="clang_text_spans",
                path="driver.c",
                line_start=10,
                provenance={"extractor": "code_graph", "function": "unrelated_writer", "corpus_id": "fixture"},
            )

            calls = 0
            original = AsipStore.to_networkx

            def counting_to_networkx(instance, *args, **kwargs):
                nonlocal calls
                calls += 1
                return original(instance, *args, **kwargs)

            rows = [{"symbol": "MISSING_CNTL_A"}, {"symbol": "MISSING_CNTL_B"}]
            with patch.object(AsipStore, "to_networkx", counting_to_networkx):
                graph = graph_for_rows(rows, db_path)

            self.assertEqual(calls, 1)
            self.assertEqual(graph["queryId"], "MISSING_CNTL_A, MISSING_CNTL_B")
            self.assertEqual(graph["edges"], [])
            self.assertEqual(
                [node["id"] for node in graph["nodes"]],
                [
                    "register:unknown:unknown:MISSING_CNTL_A",
                    "register:unknown:unknown:MISSING_CNTL_B",
                ],
            )

    def test_graph_for_rows_expands_multiple_query_seeds_with_single_networkx_build(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            for index in range(4):
                register = f"TEST_REG_CNTL_{index}"
                store.add_edge(
                    f"writer_{index}",
                    register,
                    "writes",
                    0.95,
                    stage="deterministic",
                    source="clang_text_spans",
                    path=f"driver_{index}.c",
                    line_start=10 + index,
                    provenance={
                        "extractor": "code_graph",
                        "function": f"writer_{index}",
                        "corpus_id": "fixture",
                        "path": f"driver_{index}.c",
                    },
                )

            calls = 0
            original = AsipStore.to_networkx

            def counting_to_networkx(instance, *args, **kwargs):
                nonlocal calls
                calls += 1
                return original(instance, *args, **kwargs)

            rows = [{"symbol": f"TEST_REG_CNTL_{index}"} for index in range(4)]
            with patch.object(AsipStore, "to_networkx", counting_to_networkx):
                graph = graph_for_rows(rows, db_path)

            self.assertEqual(calls, 1)
            edge_triples = {(edge["src"], edge["relation"], edge["dst"]) for edge in graph["edges"]}
            for index in range(4):
                self.assertIn(
                    (
                        f"function:fixture:driver_{index}.c:writer_{index}",
                        "writes",
                        f"register:unknown:unknown:TEST_REG_CNTL_{index}",
                    ),
                    edge_triples,
                )

    def test_register_query_graph_expands_to_common_callback_backbone(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.add_edge(
                "amdgpu_device_init",
                "gfx_v11_0_hw_init",
                "calls",
                0.72,
                stage="deterministic",
                source="clang_callback",
                path="drivers/gpu/drm/amd/amdgpu/amdgpu_device.c",
                line_start=20,
                provenance={
                    "extractor": "code_graph",
                    "function": "amdgpu_device_init",
                    "callee": "gfx_v11_0_hw_init",
                    "call_kind": "vtable_dispatch",
                    "corpus_id": "linux-amdgpu",
                    "repo": "https://github.com/torvalds/linux",
                    "callee_path": "drivers/gpu/drm/amd/amdgpu/gfx_v11_0.c",
                    "callee_line": 4,
                },
            )
            store.add_edge(
                "gfx_v11_0_hw_init",
                "GCVM_L2_CNTL",
                "writes",
                0.97,
                stage="deterministic",
                source="clang_text_spans",
                path="drivers/gpu/drm/amd/amdgpu/gfx_v11_0.c",
                line_start=6,
                provenance={
                    "extractor": "code_graph",
                    "function": "gfx_v11_0_hw_init",
                    "ip": "GC",
                    "ip_version": "11.0",
                    "corpus_id": "linux-amdgpu",
                    "repo": "https://github.com/torvalds/linux",
                },
            )

            graph = graph_for_rows([{"symbol": "GCVM_L2_CNTL"}], db_path)

            edge_triples = {(edge["src"], edge["relation"], edge["dst"]) for edge in graph["edges"]}
            self.assertIn(
                (
                    "function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/amdgpu_device.c:amdgpu_device_init",
                    "calls",
                    "function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/gfx_v11_0.c:gfx_v11_0_hw_init",
                ),
                edge_triples,
            )
            self.assertIn(
                (
                    "function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/gfx_v11_0.c:gfx_v11_0_hw_init",
                    "writes",
                    "register:GC:11.0:GCVM_L2_CNTL",
                ),
                edge_triples,
            )

    def test_query_rows_include_mvp_evidence_schema_and_empty_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path, _corpus_root = write_live_fixture(root)
            db_path = root / "asip.db"
            index_configured_corpora(config_path, db_path)

            matched = query_evidence(db_path, "doorbell interrupt disable")
            no_match = query_evidence(db_path, "totally absent symbol")

            self.assertFalse(matched["empty"])
            for row in matched["rows"]:
                self.assertTrue(REQUIRED_EVIDENCE_FIELDS.issubset(row.keys()), row)
            self.assertTrue(no_match["empty"])
            self.assertEqual(no_match["rows"], [])
            self.assertIn("No evidence matched", no_match["empty_state"])

    def test_query_can_filter_evidence_by_ip_block_and_asic_generation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            document_id = store.add_document("fixture", "code", "driver.c")
            cp_chunk = store.add_chunk(document_id, "CP_INT_CNTL_RING0 CNTX_BUSY_INT_ENABLE", 1, 1)
            sdma_chunk = store.add_chunk(document_id, "CP_INT_CNTL_RING0 shadow copy", 2, 2)
            store.add_evidence(
                cp_chunk,
                "fixture",
                "code",
                "local",
                "driver.c",
                "CP_INT_CNTL_RING0",
                "register",
                "field_set",
                0.95,
                "CP_INT_CNTL_RING0 CNTX_BUSY_INT_ENABLE",
                "source mention -> CP_INT_CNTL_RING0",
                line_start=1,
                line_end=1,
                ip_block="CP",
                asic_or_generation="gfx1100",
            )
            store.add_evidence(
                sdma_chunk,
                "fixture",
                "code",
                "local",
                "driver.c",
                "CP_INT_CNTL_RING0",
                "register",
                "mention",
                0.75,
                "CP_INT_CNTL_RING0 shadow copy",
                "source mention -> CP_INT_CNTL_RING0",
                line_start=2,
                line_end=2,
                ip_block="SDMA",
                asic_or_generation="gfx900",
            )

            filtered = query_evidence(
                db_path,
                "CP_INT_CNTL_RING0",
                ip_block="CP",
                asic_or_generation="gfx1100",
            )

            self.assertEqual(len(filtered["rows"]), 1)
            self.assertEqual(filtered["rows"][0]["ip_block"], "CP")
            self.assertEqual(filtered["rows"][0]["asic_or_generation"], "gfx1100")

    def test_query_can_filter_evidence_by_source_type(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            code_document_id = store.add_document("fixture", "code", "driver.c")
            doc_document_id = store.add_document("fixture", "doc", "docs/registers.md")
            code_chunk = store.add_chunk(code_document_id, "LOCAL_TEST_CNTL code evidence", 1, 1)
            doc_chunk = store.add_chunk(doc_document_id, "LOCAL_TEST_CNTL doc evidence", 1, 1)
            store.add_evidence(
                code_chunk,
                "fixture",
                "code",
                "local",
                "driver.c",
                "LOCAL_TEST_CNTL",
                "register",
                "write",
                0.95,
                "LOCAL_TEST_CNTL code evidence",
                "code -> LOCAL_TEST_CNTL",
            )
            store.add_evidence(
                doc_chunk,
                "fixture",
                "doc",
                "local",
                "docs/registers.md",
                "LOCAL_TEST_CNTL",
                "register",
                "mention",
                0.95,
                "LOCAL_TEST_CNTL doc evidence",
                "doc -> LOCAL_TEST_CNTL",
            )

            filtered = query_evidence(db_path, "LOCAL_TEST_CNTL", source_types=["doc"])

            self.assertEqual({row["source_type"] for row in filtered["rows"]}, {"doc"})
            self.assertEqual(filtered["filters"]["source_types"], ["doc"])

    def test_query_evidence_merges_vector_backed_evidence_without_lexical_overlap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            document_id = store.add_document("fixture", "doc", "docs/alpha-notes.md")
            chunk_id = store.add_chunk(document_id, "alpha beta gamma hardware timing note", 4, 4)
            store.add_evidence(
                chunk_id,
                "fixture",
                "doc",
                "local",
                "docs/alpha-notes.md",
                "REG_ALPHA_STATUS",
                "register",
                "mention",
                0.71,
                "alpha beta gamma hardware timing note",
                "source mention -> REG_ALPHA_STATUS",
                line_start=4,
                line_end=4,
            )
            store.add_embedding(
                chunk_id,
                provider="test",
                model="unit-vector",
                vector=[1.0, 0.0, 0.0],
            )
            original_embedding = workbench._deterministic_embedding
            workbench._deterministic_embedding = lambda text: [1.0, 0.0, 0.0]
            try:
                result = query_evidence(db_path, "semantic nearest lookup")
            finally:
                workbench._deterministic_embedding = original_embedding

            self.assertFalse(result["empty"])
            self.assertEqual(result["rows"][0]["symbol"], "REG_ALPHA_STATUS")
            sources = result["rows"][0].get("retrieval_sources", [])
            sources_text = (
                sources.lower()
                if isinstance(sources, str)
                else " ".join(str(source).lower() for source in sources)
            )
            self.assertTrue("vector_score" in result["rows"][0] or "vector" in sources_text, result["rows"][0])
            self.assertIn(result["rows"][0].get("vector_runtime"), {"python-cosine", "sqlite-vec"})

    def test_query_evidence_reranks_with_configured_provider_query_embedding(self):
        class QueryEmbeddingTransport:
            def __init__(self):
                self.requests = []

            def post_json(self, url, payload, headers, timeout):
                self.requests.append({"url": url, "payload": payload, "headers": headers, "timeout": timeout})
                return {"embeddings": [[1.0, 0.0]]}

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
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
            provider_doc = store.add_document("fixture", "doc", "docs/provider.md")
            provider_chunk = store.add_chunk(provider_doc, "provider-only semantic relationship note", 4, 4)
            store.add_evidence(
                provider_chunk,
                "fixture",
                "doc",
                "local",
                "docs/provider.md",
                "REG_PROVIDER_RERANK",
                "register",
                "mention",
                0.71,
                "provider-only semantic relationship note",
                "provider vector -> REG_PROVIDER_RERANK",
                line_start=4,
                line_end=4,
            )
            store.add_embedding(
                provider_chunk,
                provider="ollama",
                model="provider-rerank",
                vector=[1.0, 0.0],
                metadata={"source": "provider"},
            )
            stale_doc = store.add_document("fixture", "doc", "docs/stale.md")
            stale_chunk = store.add_chunk(stale_doc, "stale vector from old provider", 5, 5)
            store.add_evidence(
                stale_chunk,
                "fixture",
                "doc",
                "local",
                "docs/stale.md",
                "REG_STALE_VECTOR",
                "register",
                "mention",
                0.99,
                "stale vector from old provider",
                "old vector -> REG_STALE_VECTOR",
                line_start=5,
                line_end=5,
            )
            store.add_embedding(
                stale_chunk,
                provider="ollama",
                model="old-model",
                vector=[1.0, 0.0],
                metadata={"source": "provider"},
            )

            transport = QueryEmbeddingTransport()
            result = query_evidence(
                db_path,
                "semantic nearest lookup",
                limit=5,
                embedding_transport=transport,
            )

            self.assertFalse(result["empty"])
            self.assertEqual(result["rows"][0]["symbol"], "REG_PROVIDER_RERANK")
            self.assertEqual([row["symbol"] for row in result["rows"]], ["REG_PROVIDER_RERANK"])
            self.assertEqual(transport.requests[0]["payload"]["input"], ["semantic nearest lookup"])
            self.assertIn("/api/embed", transport.requests[0]["url"])
            self.assertIn("provider-vector", result["rows"][0]["retrieval_sources"])
            self.assertEqual(result["rows"][0]["query_embedding_source"], "provider")
            self.assertEqual(result["rows"][0]["vector_provider"], "ollama")
            self.assertEqual(result["rows"][0]["vector_model"], "provider-rerank")

    def test_query_evidence_reports_provider_query_embedding_fallback_metadata(self):
        class FailingQueryEmbeddingTransport:
            def post_json(self, url, payload, headers, timeout):
                raise RuntimeError("embedding provider unavailable")

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
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
            document_id = store.add_document("fixture", "code", "driver.c")
            chunk_id = store.add_chunk(document_id, "GCVM_L2_CNTL lexical fallback evidence", 1, 1)
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
                "GCVM_L2_CNTL lexical fallback evidence",
                "source mention -> GCVM_L2_CNTL",
                line_start=1,
                line_end=1,
            )

            result = query_evidence(
                db_path,
                "GCVM_L2_CNTL fallback",
                embedding_transport=FailingQueryEmbeddingTransport(),
            )

            self.assertFalse(result["empty"])
            self.assertEqual(result["query_embedding"]["source"], "deterministic-fallback")
            self.assertIn("embedding provider unavailable", result["query_embedding"]["error"])

    def test_query_evidence_does_not_compare_fallback_query_vector_to_provider_vectors(self):
        class FailingQueryEmbeddingTransport:
            def post_json(self, url, payload, headers, timeout):
                raise RuntimeError("embedding provider unavailable")

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
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
            document_id = store.add_document("fixture", "doc", "docs/provider.md")
            chunk_id = store.add_chunk(document_id, "provider-only vector row", 7, 7)
            store.add_evidence(
                chunk_id,
                "fixture",
                "doc",
                "local",
                "docs/provider.md",
                "REG_PROVIDER_ONLY",
                "register",
                "mention",
                0.71,
                "provider-only vector row",
                "provider vector -> REG_PROVIDER_ONLY",
                line_start=7,
                line_end=7,
            )
            store.add_embedding(
                chunk_id,
                provider="ollama",
                model="provider-rerank",
                vector=workbench._deterministic_embedding("semantic nearest lookup"),
                metadata={"source": "provider"},
            )

            result = query_evidence(
                db_path,
                "semantic nearest lookup",
                limit=5,
                embedding_transport=FailingQueryEmbeddingTransport(),
            )

            self.assertTrue(result["empty"])
            self.assertEqual(result["query_embedding"]["source"], "deterministic-fallback")
            self.assertEqual(result["rows"], [])

    def test_documentation_queries_preserve_matching_doc_rows_when_code_scores_dominate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            code_document_id = store.add_document("fixture", "code", "drivers/gpu/drm/amd/amdgpu/amdgpu.h")
            for index in range(12):
                chunk_id = store.add_chunk(
                    code_document_id,
                    f"AMDGPU_DRIVER_SOURCE_TREE_{index} driver source tree token-heavy code row",
                    index + 1,
                    index + 1,
                )
                store.add_evidence(
                    chunk_id,
                    "fixture",
                    "code",
                    "local",
                    "drivers/gpu/drm/amd/amdgpu/amdgpu.h",
                    f"AMDGPU_DRIVER_SOURCE_TREE_{index}",
                    "register",
                    "mention",
                    0.95,
                    f"AMDGPU_DRIVER_SOURCE_TREE_{index} driver source tree token-heavy code row",
                    f"source mention -> AMDGPU_DRIVER_SOURCE_TREE_{index}",
                    line_start=index + 1,
                    line_end=index + 1,
                )
            doc_document_id = store.add_document("fixture", "doc", "docs/amdgpu-driver-overview.md")
            doc_chunk_id = store.add_chunk(
                doc_document_id,
                "AMDGPU documentation connects the driver source tree to scheduling behavior.",
                1,
                1,
            )
            store.add_evidence(
                doc_chunk_id,
                "fixture",
                "doc",
                "local",
                "docs/amdgpu-driver-overview.md",
                "amdgpu-driver-overview.md",
                "doc_section",
                "mention",
                0.8,
                "AMDGPU documentation connects the driver source tree to scheduling behavior.",
                "doc chunk -> amdgpu-driver-overview.md",
                line_start=1,
                line_end=1,
            )

            result = query_evidence(db_path, "amdgpu documentation driver source tree", limit=5)

            self.assertIn("doc", {row["source_type"] for row in result["rows"]})
            self.assertLessEqual(len(result["rows"]), 5)

    def test_documentation_queries_preserve_matching_pdf_rows_before_candidate_cap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            register_document_id = store.add_document("fixture", "register", "registers.h")
            register_chunk_id = store.add_chunk(
                register_document_id,
                "amdgpu documentation driver source tree register references",
                1,
                1,
            )
            for index in range(2100):
                store.add_evidence(
                    register_chunk_id,
                    "fixture",
                    "register",
                    "local",
                    "registers.h",
                    f"AMDGPU_DRIVER_SOURCE_TREE_{index}",
                    "register",
                    "mention",
                    0.95,
                    "amdgpu documentation driver source tree register references",
                    f"register -> AMDGPU_DRIVER_SOURCE_TREE_{index}",
                    line_start=1,
                    line_end=1,
                )
            pdf_document_id = store.add_document("fixture", "pdf", "amdgpu-driver-source-tree.pdf")
            pdf_chunk_id = store.add_chunk(
                pdf_document_id,
                "amdgpu documentation connects the AMD GPU driver source tree to Linux amdgpu.",
                1,
                1,
                page=1,
            )
            store.add_evidence(
                pdf_chunk_id,
                "fixture",
                "pdf",
                "local",
                "amdgpu-driver-source-tree.pdf",
                "amdgpu-driver-source-tree.pdf#page-1",
                "pdf_section",
                "mention",
                0.8,
                "amdgpu documentation connects the AMD GPU driver source tree to Linux amdgpu.",
                "pdf chunk -> amdgpu-driver-source-tree.pdf#page-1",
                line_start=1,
                line_end=1,
                page=1,
            )

            result = query_evidence(db_path, "amdgpu documentation driver source tree", limit=5)

            self.assertIn("pdf", {row["source_type"] for row in result["rows"]})
            self.assertLessEqual(len(result["rows"]), 5)

    def test_query_graph_keeps_pdf_section_node_from_matching_pdf_row_when_edges_exist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.add_edge("UNRELATED_HELPER", "UNRELATED_REG", "writes", 0.8)
            pdf_document_id = store.add_document("fixture", "pdf", "docs/manual.pdf")
            pdf_chunk_id = store.add_chunk(
                pdf_document_id,
                "GCVM_L2_CNTL is described on this PDF page.",
                1,
                1,
                page=3,
            )
            store.add_evidence(
                pdf_chunk_id,
                "fixture",
                "pdf",
                "local",
                "docs/manual.pdf",
                "GCVM_L2_CNTL",
                "register",
                "mention",
                0.9,
                "GCVM_L2_CNTL is described on this PDF page.",
                "pdf page -> GCVM_L2_CNTL",
                line_start=1,
                line_end=1,
                page=3,
            )

            result = query_evidence(db_path, "GCVM_L2_CNTL PDF page", limit=5)

            nodes = {node["id"]: node for node in result["graph"]["nodes"]}
            edges = {(edge["src"], edge["relation"], edge["dst"]) for edge in result["graph"]["edges"]}
            self.assertEqual(nodes["docs/manual.pdf#page-3"]["kind"], "pdf_section")
            self.assertEqual(nodes["docs/manual.pdf#page-3"]["attr"]["source"][0]["page"], 3)
            self.assertIn(
                ("docs/manual.pdf#page-3", "documents", "register:GC:unknown:GCVM_L2_CNTL"),
                edges,
            )

    def test_register_queries_preserve_matching_register_header_rows_when_code_scores_dominate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            code_document_id = store.add_document("fixture", "code", "drivers/gpu/drm/amd/amdgpu/gfx_v11_0.c")
            for index in range(12):
                chunk_id = store.add_chunk(
                    code_document_id,
                    f"regGCVM_L2_CNTL ENABLE_L2_CACHE generated code row {index}",
                    index + 1,
                    index + 1,
                )
                store.add_evidence(
                    chunk_id,
                    "fixture",
                    "code",
                    "local",
                    "drivers/gpu/drm/amd/amdgpu/gfx_v11_0.c",
                    f"GCVM_L2_CNTL_CODE_{index}",
                    "register",
                    "write",
                    0.95,
                    f"regGCVM_L2_CNTL ENABLE_L2_CACHE generated code row {index}",
                    f"write wrapper -> GCVM_L2_CNTL_CODE_{index}",
                    line_start=index + 1,
                    line_end=index + 1,
                )
            register_document_id = store.add_document("fixture", "register", "include/asic_reg/gc_11_0_0_offset.h")
            register_chunk_id = store.add_chunk(
                register_document_id,
                "#define regGCVM_L2_CNTL 0x1430\n#define GCVM_L2_CNTL_BASE_IDX 0",
                1,
                2,
            )
            store.add_evidence(
                register_chunk_id,
                "fixture",
                "register",
                "local",
                "include/asic_reg/gc_11_0_0_offset.h",
                "regGCVM_L2_CNTL",
                "register",
                "mention",
                0.8,
                "#define regGCVM_L2_CNTL 0x1430",
                "register header -> regGCVM_L2_CNTL",
                line_start=1,
                line_end=2,
            )

            result = query_evidence(db_path, "regGCVM_L2_CNTL ENABLE_L2_CACHE", limit=5)

            self.assertIn("register", {row["source_type"] for row in result["rows"]})
            self.assertLessEqual(len(result["rows"]), 5)

    def test_diverse_selection_preserves_multiple_injected_source_types(self):
        rows = [
            {"id": index, "source_type": "code", "rank_score": 10 - index}
            for index in range(1, 6)
        ] + [
            {"id": 6, "source_type": "register", "rank_score": 1},
            {"id": 7, "source_type": "doc", "rank_score": 1},
        ]

        selected = workbench._select_diverse_rows(rows, limit=5)

        source_types = {row["source_type"] for row in selected}
        self.assertIn("register", source_types)
        self.assertIn("doc", source_types)
        self.assertLessEqual(len(selected), 5)

    def test_query_diverse_selection_preserves_multiple_injected_source_types(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            code_document_id = store.add_document("fixture", "code", "driver.c")
            for index in range(12):
                chunk_id = store.add_chunk(
                    code_document_id,
                    f"GCVM_L2_CNTL macro expansion code row {index}",
                    index + 1,
                    index + 1,
                )
                store.add_evidence(
                    chunk_id,
                    "fixture",
                    "code",
                    "local",
                    "driver.c",
                    f"GCVM_CODE_{index}",
                    "register",
                    "write",
                    0.95,
                    f"GCVM_L2_CNTL macro expansion code row {index}",
                    f"write wrapper -> GCVM_CODE_{index}",
                    line_start=index + 1,
                    line_end=index + 1,
                )
            register_document_id = store.add_document("fixture", "register", "asic_reg/gc_offset.h")
            register_chunk_id = store.add_chunk(register_document_id, "#define regGCVM_L2_CNTL 0x1430", 1, 1)
            store.add_evidence(
                register_chunk_id,
                "fixture",
                "register",
                "local",
                "asic_reg/gc_offset.h",
                "regGCVM_L2_CNTL",
                "register",
                "mention",
                0.8,
                "#define regGCVM_L2_CNTL 0x1430",
                "register header -> regGCVM_L2_CNTL",
                line_start=1,
                line_end=1,
            )
            doc_document_id = store.add_document("fixture", "doc", "docs/register-macros.md")
            doc_chunk_id = store.add_chunk(doc_document_id, "GCVM_L2_CNTL macro expansion documentation", 1, 1)
            store.add_evidence(
                doc_chunk_id,
                "fixture",
                "doc",
                "local",
                "docs/register-macros.md",
                "register-macros.md",
                "doc_section",
                "mention",
                0.8,
                "GCVM_L2_CNTL macro expansion documentation",
                "doc chunk -> register-macros.md",
                line_start=1,
                line_end=1,
            )

            result = query_evidence(db_path, "GCVM_L2_CNTL macro expansion", limit=5)

            source_types = {row["source_type"] for row in result["rows"]}
            self.assertIn("register", source_types)
            self.assertIn("doc", source_types)
            self.assertLessEqual(len(result["rows"]), 5)


if __name__ == "__main__":
    unittest.main()
