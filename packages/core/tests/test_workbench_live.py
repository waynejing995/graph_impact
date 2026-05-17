import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from asip.storage import AsipStore
from asip import workbench
from asip.workbench import (
    add_corpus,
    expand_query_graph,
    generate_semantic_edges_batch,
    generate_semantic_edges_for_query,
    index_configured_corpora,
    index_registered_corpora,
    query_evidence,
    rebuild_deterministic_graph,
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
                        },
                        {
                            "src": "GCVM_L2_CNTL",
                            "relation": "mentions",
                            "dst": "GCVM_L2_CNTL",
                            "confidence": 0.7,
                            "evidence": "self-loop should be ignored",
                        }
                    ],
                }
            ]
        }


class FailingSecondBatchSemanticEdgeProvider:
    def __init__(self):
        self.calls = 0

    def generate(self, prompt, model):
        self.calls += 1
        if self.calls > 1:
            raise RuntimeError("second batch failed")
        return {
            "cases": [
                {
                    "id": "first-batch",
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


class DocSectionSemanticEdgeProvider:
    def generate(self, prompt, model):
        self.prompt = prompt
        return {
            "cases": [
                {
                    "id": "doc-section-batch",
                    "edges": [
                        {
                            "src": "docs/guide.md#programming-local-registers",
                            "relation": "documents_register",
                            "dst": "GCVM_L2_CNTL",
                            "confidence": 0.9,
                            "evidence": "doc section fixture",
                        }
                    ],
                }
            ]
        }


class DocNodeProvider:
    def generate(self, prompt, model):
        self.prompt = prompt
        return {
            "documents": [
                {
                    "id": "docs/guide.md#programming-local-registers",
                    "boxes": [
                        {
                            "id": "l2-cache-control",
                            "name": "L2 cache control",
                            "summary": "Programs GCVM_L2_CNTL and ENABLE_L2_CACHE.",
                            "inputs": ["GCVM_L2_CNTL"],
                            "outputs": ["ENABLE_L2_CACHE"],
                            "constraints": ["cache must be enabled before use"],
                            "confidence": 0.92,
                            "evidence": "GCVM_L2_CNTL controls ENABLE_L2_CACHE",
                        }
                    ],
                    "relationships": [
                        {
                            "src": "l2-cache-control",
                            "relation": "documents_register",
                            "dst": "GCVM_L2_CNTL",
                            "confidence": 0.9,
                            "evidence": "register section",
                        }
                    ],
                }
            ]
        }


class WorkbenchLiveTests(unittest.TestCase):
    def test_edge_provider_config_reads_ollama_options_block(self):
        config = workbench._edge_provider_config(
            {
                "edge": {
                    "provider": "ollama",
                    "base_url": "http://localhost:11434",
                    "model": "gemma4:e4b",
                    "options": {
                        "num_ctx": 4096,
                        "num_predict": 2048,
                        "temperature": 0.2,
                    },
                }
            }
        )

        self.assertEqual(config.num_ctx, 4096)
        self.assertEqual(config.num_predict, 2048)
        self.assertEqual(config.temperature, 0.2)

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
            self.assertTrue(all(edge["dst"] != "DOORBELL_INTERRUPT_DISABLE" for edge in graph["edges"]))

            con = sqlite3.connect(db_path)
            self.assertEqual(con.execute("select count(*) from corpora").fetchone()[0], 1)
            self.assertEqual(con.execute("select count(*) from jobs where status = 'indexed'").fetchone()[0], 1)
            edge_stages = {row[0] for row in con.execute("select distinct stage from edges")}
            self.assertIn("deterministic", edge_stages)
            self.assertIn("evidence", edge_stages)

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
            store.add_edge("program_cache", "GCVM_L2_CNTL", "reads", 0.98)
            store.add_edge("program_cache", "GCVM_L2_CNTL", "sets_field", 0.84, provenance={"field": "ENABLE_L2_CACHE"})
            store.add_edge("program_cache", "OUT_OF_SCOPE", "calls", 0.12)

            graph = expand_query_graph(db_path, "GCVM_L2_CNTL", hops=2)

            self.assertEqual(graph["source"], "networkx")
            self.assertEqual(graph["graph_runtime"], "networkx")
            edges = {(edge["src"], edge["relation"], edge["dst"]): edge for edge in graph["edges"]}
            function_id = "function:unknown:unknown:program_cache"
            register_id = "register:GC:unknown:unknown:GCVM_L2_CNTL"
            self.assertEqual(edges[(function_id, "reads", register_id)]["weight"], 0.98)
            self.assertEqual(edges[(function_id, "sets_field", register_id)]["weight"], 0.84)
            self.assertNotIn((function_id, "calls", "OUT_OF_SCOPE"), edges)

    def test_expand_query_graph_canonicalizes_register_seed_aliases(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.add_edge("program_cache", "GCVM_L2_CNTL", "sets_field", 0.91, provenance={"field": "ENABLE_L2_CACHE"})

            graph = expand_query_graph(db_path, "regGCVM_L2_CNTL", hops=1)
            mm_graph = expand_query_graph(db_path, "mmGCVM_L2_CNTL", hops=1)
            smn_graph = expand_query_graph(db_path, "smnGCVM_L2_CNTL", hops=1)

            for candidate in (graph, mm_graph, smn_graph):
                self.assertTrue(any(edge["relation"] == "sets_field" for edge in candidate["edges"]))
                self.assertTrue(
                    any(node["kind"] == "register" and node["label"] == "GCVM_L2_CNTL" for node in candidate["nodes"])
                )

    def test_expand_query_graph_does_not_expand_through_wrapper_hubs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.add_edge("program_cache", "GCVM_L2_CNTL", "reads", 0.97)
            store.add_edge("program_cache", "ENABLE_L2_CACHE", "sets_field", 0.97)
            store.add_edge("REG_SET_FIELD", "GCVM_L2_CNTL", "wraps", 0.93)
            store.add_edge("REG_SET_FIELD", "UNRELATED_FIELD", "wraps", 0.93)

            graph = expand_query_graph(db_path, "GCVM_L2_CNTL", hops=2)

            node_ids = {node["id"] for node in graph["nodes"]}
            edge_endpoints = {endpoint for edge in graph["edges"] for endpoint in (edge["src"], edge["dst"])}
            self.assertNotIn("REG_SET_FIELD", node_ids)
            self.assertNotIn("REG_SET_FIELD", edge_endpoints)
            self.assertNotIn("ENABLE_L2_CACHE", node_ids)
            self.assertIn("register:GC:unknown:unknown:GCVM_L2_CNTL", node_ids)
            self.assertNotIn("UNRELATED_FIELD", node_ids)

    def test_expand_query_graph_rejects_wrapper_seed_nodes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.add_edge("GCVM_L2_CNTL", "ENABLE_L2_CACHE", "has_field", 0.98)

            graph = expand_query_graph(db_path, "REG_SET_FIELD", hops=2)

            self.assertEqual(graph["queryId"], "REG_SET_FIELD")
            self.assertEqual(graph["nodes"], [])
            self.assertEqual(graph["edges"], [])

    def test_global_graph_returns_weighted_edges_without_seed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.add_edge(
                "program_global_register",
                "API_GLOBAL_REGISTER",
                "sets_field",
                0.99,
                path="src/global.c",
                provenance={"function": "program_global_register", "field": "API_GLOBAL_FIELD", "corpus_id": "api"},
            )
            store.add_edge(
                "docs/global.md#overview",
                "API_GLOBAL_REGISTER",
                "documented_by",
                0.87,
                path="docs/global.md",
                provenance={"ip": "unknown", "ip_version": "unknown", "corpus_id": "docs"},
            )
            store.add_edge(
                "LOW_CONFIDENCE_REGISTER",
                "LOW_CONFIDENCE_FIELD",
                "mentions",
                0.11,
                provenance={"field": "LOW_CONFIDENCE_FIELD"},
            )

            graph = workbench.global_graph(db_path, limit=2)

            self.assertIn(graph["source"], {"networkx", "sqlite"})
            self.assertIn(graph["graph_runtime"], {"networkx", "sqlite"})
            self.assertEqual(sorted(edge["confidence"] for edge in graph["edges"]), [0.87, 0.99])
            self.assertEqual(sorted(edge["weight"] for edge in graph["edges"]), [0.87, 0.99])
            self.assertEqual(
                {node["id"] for node in graph["nodes"]},
                {
                    "function:api:src/global.c:program_global_register",
                    "register:unknown:unknown:api:API_GLOBAL_REGISTER",
                    "register:unknown:unknown:docs:API_GLOBAL_REGISTER",
                    "docs/global.md#overview",
                },
            )
            self.assertNotIn(
                ("LOW_CONFIDENCE_REGISTER", "LOW_CONFIDENCE_FIELD"),
                {(edge["src"], edge["dst"]) for edge in graph["edges"]},
            )

    def test_global_graph_derives_weighted_connections_from_indexed_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            document_id = store.add_document("docs", "doc", "docs/note.md")
            chunk_id = store.add_chunk(
                document_id,
                "UI_GLOBAL_REGISTER sets UI_GLOBAL_FIELD while WITHOUT is license text.",
                1,
                1,
            )
            store.add_evidence(
                chunk_id=chunk_id,
                corpus_id="docs",
                source_type="doc",
                repo="local",
                path="docs/note.md",
                symbol="UI_GLOBAL_REGISTER",
                entity_type="register",
                access_type="mention",
                confidence=0.95,
                snippet="UI_GLOBAL_REGISTER sets UI_GLOBAL_FIELD",
                resolved_chain="source mention -> UI_GLOBAL_REGISTER",
            )
            store.add_evidence(
                chunk_id=chunk_id,
                corpus_id="docs",
                source_type="doc",
                repo="local",
                path="docs/note.md",
                symbol="UI_GLOBAL_FIELD",
                entity_type="field",
                access_type="mention",
                confidence=0.94,
                snippet="UI_GLOBAL_REGISTER sets UI_GLOBAL_FIELD",
                resolved_chain="source mention -> UI_GLOBAL_FIELD",
            )
            store.add_evidence(
                chunk_id=chunk_id,
                corpus_id="docs",
                source_type="doc",
                repo="local",
                path="docs/note.md",
                symbol="WITHOUT",
                entity_type="function",
                access_type="mention",
                confidence=0.95,
                snippet="WITHOUT warranty",
                resolved_chain="source mention -> WITHOUT",
            )

            graph = workbench.global_graph(db_path, limit=20)

            node_ids = {node["id"] for node in graph["nodes"]}
            edge_pairs = {(edge["src"], edge["dst"], edge["relation"]) for edge in graph["edges"]}
            self.assertIn("register:unknown:unknown:docs:UI_GLOBAL_REGISTER", node_ids)
            self.assertNotIn("WITHOUT", node_ids)
            self.assertNotIn("UI_GLOBAL_FIELD", node_ids)
            self.assertIn(("docs/note.md#section", "register:unknown:unknown:docs:UI_GLOBAL_REGISTER", "documents"), edge_pairs)
            self.assertTrue(all(edge["weight"] > 0 for edge in graph["edges"]))

    def test_global_graph_evidence_overlay_is_explicit_when_persisted_edges_exist(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            document_id = store.add_document("docs", "doc", "docs/guide.md")
            chunk_id = store.add_chunk(
                document_id,
                "# Programming local registers\n"
                "GCVM_L2_CNTL has field ENABLE_L2_CACHE in this section.",
                1,
                2,
            )
            for symbol, entity_type in [("GCVM_L2_CNTL", "register"), ("ENABLE_L2_CACHE", "field")]:
                store.add_evidence(
                    chunk_id=chunk_id,
                    corpus_id="docs",
                    source_type="doc",
                    repo="local",
                    path="docs/guide.md",
                    line_start=2,
                    line_end=2,
                    symbol=symbol,
                    entity_type=entity_type,
                    access_type="mention",
                    confidence=0.95,
                    snippet="GCVM_L2_CNTL has field ENABLE_L2_CACHE",
                    resolved_chain=f"doc section -> {symbol}",
                )
            store.add_edge(
                "GCVM_L2_CNTL",
                "ENABLE_L2_CACHE",
                "sets_field",
                0.91,
                stage="semantic",
                source="ollama",
            )

            default_graph = workbench.global_graph(db_path, limit=20)
            overlay_graph = workbench.global_graph(db_path, limit=20, include_evidence_derived=True)

            self.assertNotIn(
                "docs/guide.md#programming-local-registers",
                {node["id"] for node in default_graph["nodes"]},
            )
            self.assertIn(
                "docs/guide.md#programming-local-registers",
                {node["id"] for node in overlay_graph["nodes"]},
            )

    def test_global_graph_links_code_functions_to_register_operations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "corpus"
            source_root.mkdir()
            (source_root / "gfx.c").write_text(
                "\n".join(
                    [
                        "void program_local_register(void) {",
                        "  uint32_t tmp = RREG32(regLOCAL_TEST_CNTL);",
                        "  tmp = REG_SET_FIELD(tmp, LOCAL_TEST_CNTL, ENABLE_LOCAL_FIELD, 1);",
                        "  WREG32(regLOCAL_TEST_CNTL, tmp);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            db_path = root / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.upsert_corpus("code", "local", str(source_root), ["**/*.c"], status="indexed", file_count=1)
            document_id = store.add_document("code", "code", "gfx.c")
            chunk_id = store.add_chunk(
                document_id,
                "1: void program_local_register(void) {\n"
                "2:   uint32_t tmp = RREG32(regLOCAL_TEST_CNTL);\n"
                "3:   tmp = REG_SET_FIELD(tmp, LOCAL_TEST_CNTL, ENABLE_LOCAL_FIELD, 1);\n"
                "4:   WREG32(regLOCAL_TEST_CNTL, tmp);\n"
                "5: }",
                1,
                5,
            )
            store.add_evidence(
                chunk_id=chunk_id,
                corpus_id="code",
                source_type="code",
                repo="local",
                path="gfx.c",
                line_start=3,
                line_end=3,
                symbol="LOCAL_TEST_CNTL",
                entity_type="register",
                access_type="read_modify_write",
                confidence=0.95,
                snippet="tmp = REG_SET_FIELD(tmp, LOCAL_TEST_CNTL, ENABLE_LOCAL_FIELD, 1);",
                resolved_chain="REG_SET_FIELD -> register LOCAL_TEST_CNTL",
            )
            store.add_evidence(
                chunk_id=chunk_id,
                corpus_id="code",
                source_type="code",
                repo="local",
                path="gfx.c",
                line_start=3,
                line_end=3,
                symbol="ENABLE_LOCAL_FIELD",
                entity_type="field",
                access_type="field_set",
                confidence=0.95,
                snippet="tmp = REG_SET_FIELD(tmp, LOCAL_TEST_CNTL, ENABLE_LOCAL_FIELD, 1);",
                resolved_chain="REG_SET_FIELD -> field ENABLE_LOCAL_FIELD",
            )

            graph = workbench.global_graph(db_path, limit=40)

            node_ids = {node["id"] for node in graph["nodes"]}
            edges = {(edge["src"], edge["relation"], edge["dst"]) for edge in graph["edges"]}
            function_id = "function:code:gfx.c:program_local_register"
            register_id = "register:unknown:unknown:code:LOCAL_TEST_CNTL"
            self.assertIn(function_id, node_ids)
            self.assertIn(register_id, node_ids)
            self.assertIn((function_id, "sets_field", register_id), edges)
            register_node = next(node for node in graph["nodes"] if node["id"] == register_id)
            self.assertIn("ENABLE_LOCAL_FIELD", register_node["attr"]["fields"])

    def test_index_registered_corpus_persists_stage1_deterministic_code_graph_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "corpus"
            source_root.mkdir()
            (source_root / "gfx.c").write_text(
                "\n".join(
                    [
                        "#define SOC15_REG_OFFSET(ip, inst, reg) reg",
                        "typedef unsigned int uint32_t;",
                        "static void program_local_register(void) {",
                        "  uint32_t tmp = RREG32(SOC15_REG_OFFSET(GC, 0, GCVM_L2_CNTL));",
                        "  tmp = REG_SET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE, 1);",
                        "  WREG32(SOC15_REG_OFFSET(GC, 0, GCVM_L2_CNTL), tmp);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            db_path = root / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.upsert_corpus("code", "local", str(source_root), ["**/*.c"], status="not_indexed", file_count=0)
            store.upsert_resolver_profile(
                "test-amd",
                "cpp",
                ["RREG32", "WREG32", "REG_SET_FIELD", "SOC15_REG_OFFSET"],
                "reference",
                "test.yaml",
                config={
                    "id": "test-amd",
                    "language": "cpp",
                    "symbol_prefixes": ["reg", "mm"],
                    "wrappers": {
                        "RREG32": {"symbol_arg": 0, "access": "read"},
                        "WREG32": {"symbol_arg": 0, "access": "write"},
                        "REG_SET_FIELD": {"symbol_args": [1, 2], "access": "field_set"},
                        "SOC15_REG_OFFSET": {"symbol_arg": 2, "access": "address"},
                    },
                },
            )

            summary = workbench.index_registered_corpora(db_path, corpus_ids=["code"])
            rows = [
                dict(row)
                for row in AsipStore.connect(str(db_path)).con.execute(
                    "select src, relation, dst, stage, source, provenance_json from edges order by src, relation, dst"
                )
            ]
            edge_triples = {(row["src"], row["relation"], row["dst"]) for row in rows}

            self.assertGreater(summary["edges"], 0)
            self.assertIn(("program_local_register", "reads", "GCVM_L2_CNTL"), edge_triples)
            self.assertIn(("program_local_register", "writes", "GCVM_L2_CNTL"), edge_triples)
            self.assertIn(("program_local_register", "sets_field", "GCVM_L2_CNTL"), edge_triples)
            field_edge = next(row for row in rows if (row["src"], row["relation"], row["dst"]) == ("program_local_register", "sets_field", "GCVM_L2_CNTL"))
            self.assertIn('"field": "ENABLE_L2_CACHE"', field_edge["provenance_json"])
            self.assertIn('"corpus_id": "code"', field_edge["provenance_json"])
            self.assertNotIn("RREG32", {endpoint for src, _, dst in edge_triples for endpoint in (src, dst)})
            self.assertNotIn("WREG32", {endpoint for src, _, dst in edge_triples for endpoint in (src, dst)})
            self.assertNotIn("REG_SET_FIELD", {endpoint for src, _, dst in edge_triples for endpoint in (src, dst)})
            self.assertNotIn("SOC15_REG_OFFSET", {endpoint for src, _, dst in edge_triples for endpoint in (src, dst)})
            self.assertTrue(all(row["stage"] == "deterministic" for row in rows))
            self.assertTrue(any(row["source"] == "clang_ast" for row in rows))
            self.assertTrue(any("code_graph" in row["provenance_json"] for row in rows))

    def test_index_registered_corpus_links_cross_file_vtable_callbacks_to_registers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "corpus"
            source_root.mkdir()
            (source_root / "gfx_v11.c").write_text(
                "\n".join(
                    [
                        "static int gfx_v11_0_hw_init(void *adev) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = gfx_v11_0_hw_init,",
                        "};",
                    ]
                ),
                encoding="utf-8",
            )
            (source_root / "amdgpu_device.c").write_text(
                "\n".join(
                    [
                        "int amdgpu_device_init(struct amd_ip_block *block) {",
                        "  return block->version->funcs->hw_init(block);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            db_path = root / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.upsert_corpus("linux-amdgpu", "https://github.com/torvalds/linux", str(source_root), ["**/*.c"])
            store.upsert_resolver_profile(
                "test-amd-callbacks",
                "cpp",
                ["WREG32"],
                "reference",
                "test.yaml",
                config={
                    "id": "test-amd-callbacks",
                    "language": "cpp",
                    "symbol_prefixes": ["reg", "mm"],
                    "wrappers": {"WREG32": {"symbol_arg": 0, "access": "write"}},
                },
            )

            workbench.index_registered_corpora(db_path, corpus_ids=["linux-amdgpu"])
            graph = workbench.global_graph(db_path, limit=40, all_edges=True)

            edges = {(edge["src"], edge["relation"], edge["dst"]) for edge in graph["edges"]}
            callback_id = "function:linux-amdgpu:gfx_v11.c:gfx_v11_0_hw_init"
            common_id = "function:linux-amdgpu:amdgpu_device.c:amdgpu_device_init"
            register_id = "register:GC:unknown:linux-amdgpu:GCVM_L2_CNTL"
            self.assertIn((common_id, "calls", callback_id), edges)
            self.assertIn((callback_id, "writes", register_id), edges)
            call_row = AsipStore.connect(str(db_path)).con.execute(
                "select provenance_json from edges where src = ? and dst = ? and relation = 'calls'",
                ("amdgpu_device_init", "gfx_v11_0_hw_init"),
            ).fetchone()
            self.assertIsNotNone(call_row)
            call_provenance = json.loads(str(call_row["provenance_json"]))
            self.assertEqual(call_provenance["callee_path"], "gfx_v11.c")
            self.assertEqual(call_provenance["callee_line"], 1)
            self.assertEqual(call_provenance["callback_line"], 6)

    def test_stage1_specific_vtable_call_does_not_connect_every_same_named_slot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "corpus"
            source_root.mkdir()
            (source_root / "gfx.c").write_text(
                "\n".join(
                    [
                        "static int gfx_v11_0_hw_init(void *adev) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = gfx_v11_0_hw_init,",
                        "};",
                    ]
                ),
                encoding="utf-8",
            )
            (source_root / "sdma.c").write_text(
                "\n".join(
                    [
                        "static int sdma_v5_0_hw_init(void *adev) {",
                        "  WREG32(mmSDMA0_RLC0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs sdma_v5_0_ip_funcs = {",
                        "  .hw_init = sdma_v5_0_hw_init,",
                        "};",
                    ]
                ),
                encoding="utf-8",
            )
            (source_root / "amdgpu_device.c").write_text(
                "\n".join(
                    [
                        "int direct_gfx_init(void) {",
                        "  return gfx_v11_0_ip_funcs.hw_init(0);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            db_path = root / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.upsert_corpus("linux-amdgpu", "https://github.com/torvalds/linux", str(source_root), ["**/*.c"])
            store.upsert_resolver_profile(
                "test-amd-callbacks",
                "cpp",
                ["WREG32"],
                "reference",
                "test.yaml",
                config={
                    "id": "test-amd-callbacks",
                    "language": "cpp",
                    "symbol_prefixes": ["reg", "mm"],
                    "wrappers": {"WREG32": {"symbol_arg": 0, "access": "write"}},
                },
            )

            workbench.index_registered_corpora(db_path, corpus_ids=["linux-amdgpu"])

            rows = [
                (row["src"], row["relation"], row["dst"])
                for row in AsipStore.connect(str(db_path)).con.execute(
                    "select src, relation, dst from edges where src = 'direct_gfx_init' order by dst"
                )
            ]
            self.assertIn(("direct_gfx_init", "calls", "gfx_v11_0_hw_init"), rows)
            self.assertNotIn(("direct_gfx_init", "calls", "sdma_v5_0_hw_init"), rows)

    def test_index_registered_corpus_uses_compile_commands_for_project_macro_expansion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "corpus"
            include_dir = source_root / "include"
            include_dir.mkdir(parents=True)
            (include_dir / "regops.h").write_text(
                "#define WRITE_GCVM(symbol) WREG32(reg##symbol, 1)\n",
                encoding="utf-8",
            )
            source = source_root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        '#include "regops.h"',
                        "static void program_from_project_macro(void) {",
                        "  WRITE_GCVM(GCVM_L2_CNTL);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            (source_root / "compile_commands.json").write_text(
                json.dumps(
                    [
                        {
                            "directory": str(source_root),
                            "command": f"clang -I include -c {source}",
                            "file": str(source),
                        }
                    ]
                ),
                encoding="utf-8",
            )
            db_path = root / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.upsert_corpus("code", "local", str(source_root), ["**/*.c"], status="not_indexed", file_count=0)
            store.upsert_resolver_profile(
                "compile-db-amd",
                "cpp",
                ["WREG32"],
                "reference",
                "test.yaml",
                config={
                    "id": "compile-db-amd",
                    "language": "cpp",
                    "symbol_prefixes": ["reg", "mm"],
                    "wrappers": {"WREG32": {"symbol_arg": 0, "access": "write"}},
                },
            )

            summary = workbench.index_registered_corpora(db_path, corpus_ids=["code"])
            rows = [
                dict(row)
                for row in AsipStore.connect(str(db_path)).con.execute(
                    "select src, relation, dst, stage, source, line_start, provenance_json from edges order by id"
                )
            ]

            macro_edge = next(
                row
                for row in rows
                if (row["src"], row["relation"], row["dst"]) == (
                    "program_from_project_macro",
                    "writes",
                    "GCVM_L2_CNTL",
                )
            )
            self.assertGreater(summary["edges"], 0)
            self.assertEqual(macro_edge["stage"], "deterministic")
            self.assertEqual(macro_edge["source"], "clang_preprocess")
            self.assertEqual(macro_edge["line_start"], 3)
            self.assertIn('"wrapper": "WREG32"', macro_edge["provenance_json"])

    def test_index_configured_corpus_limits_stage1_rebuild_to_relative_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "linux"
            amdgpu_root = source_root / "drivers/gpu/drm/amd/amdgpu"
            outside_root = source_root / "drivers/gpu/drm/amd/display"
            amdgpu_root.mkdir(parents=True)
            outside_root.mkdir(parents=True)
            (amdgpu_root / "gfx.c").write_text(
                "\n".join(
                    [
                        "static void program_amdgpu(void) {",
                        "  WREG32(regGCVM_L2_CNTL, 1);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            (outside_root / "display.c").write_text(
                "\n".join(
                    [
                        "static void program_display(void) {",
                        "  WREG32(regOUTSIDE_DISPLAY_CNTL, 1);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            config_path = root / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "name": "relative-root-fixture",
                        "model": {"preferred": "gemma4:e4b", "fallback": ""},
                        "corpora": [
                            {
                                "id": "linux-amdgpu",
                                "repo": "local",
                                "default_source_root": str(source_root),
                                "relative_root": "drivers/gpu/drm/amd/amdgpu",
                                "include": ["**/*.c"],
                            }
                        ],
                        "queries": [
                            {
                                "id": "local_gcvm",
                                "corpus": "linux-amdgpu",
                                "question": "Which local register is written?",
                                "terms": ["GCVM_L2_CNTL"],
                                "expected_terms": ["GCVM_L2_CNTL"],
                                "max_snippets": 1,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            db_path = root / "asip.db"

            summary = index_configured_corpora(config_path, db_path)
            rows = [
                dict(row)
                for row in AsipStore.connect(str(db_path)).con.execute(
                    "select src, relation, dst, path from edges order by id"
                )
            ]
            edge_triples = {(row["src"], row["relation"], row["dst"]) for row in rows}

            self.assertGreater(summary["edges"], 0)
            self.assertIn(("program_amdgpu", "writes", "GCVM_L2_CNTL"), edge_triples)
            self.assertNotIn(("program_display", "writes", "OUTSIDE_DISPLAY_CNTL"), edge_triples)

    def test_rebuild_deterministic_graph_restores_stage1_edges_for_indexed_corpus(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "mxgpu"
            source_root.mkdir()
            (source_root / "gfx.c").write_text(
                "\n".join(
                    [
                        "typedef unsigned int uint32_t;",
                        "static void program_cache(uint32_t data) {",
                        "  WREG32(regGCVM_L2_CNTL, data);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            db_path = root / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.upsert_corpus(
                "mxgpu",
                "local",
                str(source_root),
                ["**/*.c"],
                status="indexed",
                file_count=1,
                metadata={},
            )

            summary = rebuild_deterministic_graph(db_path, corpus_ids=["mxgpu"])

            rows = [
                dict(row)
                for row in AsipStore.connect(str(db_path)).con.execute(
                    "select src, relation, dst, stage, source from edges order by id"
                )
            ]
            self.assertEqual(summary["source"], "deterministic_graph_rebuild")
            self.assertEqual(summary["files"], 1)
            self.assertGreaterEqual(summary["edges"], 1)
            self.assertIn(("program_cache", "writes", "GCVM_L2_CNTL"), {(row["src"], row["relation"], row["dst"]) for row in rows})
            self.assertTrue(all(row["stage"] == "deterministic" for row in rows))

    def test_rebuild_deterministic_graph_with_corpus_id_preserves_other_corpus_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mxgpu_root = root / "mxgpu"
            linux_root = root / "linux"
            mxgpu_root.mkdir()
            linux_root.mkdir()
            (mxgpu_root / "gfx.c").write_text(
                "static void program_mxgpu(void) {\n"
                "  WREG32(regMXGPU_KEEP_CNTL, 1);\n"
                "}\n",
                encoding="utf-8",
            )
            (linux_root / "amdgpu.c").write_text(
                "static void program_linux(void) {\n"
                "  WREG32(regLINUX_REBUILD_CNTL, 1);\n"
                "}\n",
                encoding="utf-8",
            )
            db_path = root / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.upsert_corpus("mxgpu", "local", str(mxgpu_root), ["**/*.c"], status="indexed", file_count=1)
            store.upsert_corpus("linux-amdgpu", "local", str(linux_root), ["**/*.c"], status="indexed", file_count=1)
            store.add_edge(
                "program_mxgpu",
                "MXGPU_KEEP_CNTL",
                "writes",
                confidence=0.97,
                stage="deterministic",
                source="clang_ast",
                path="gfx.c",
                provenance={"corpus_id": "mxgpu", "repo": "local"},
            )

            summary = rebuild_deterministic_graph(db_path, corpus_ids=["linux-amdgpu"])

            rows = [
                dict(row)
                for row in AsipStore.connect(str(db_path)).con.execute(
                    "select src, relation, dst, stage, json_extract(provenance_json, '$.corpus_id') as corpus_id "
                    "from edges where stage = 'deterministic' order by dst"
                )
            ]
            self.assertEqual(summary["corpus_ids"], ["linux-amdgpu"])
            self.assertIn(
                ("program_mxgpu", "writes", "MXGPU_KEEP_CNTL", "mxgpu"),
                {(row["src"], row["relation"], row["dst"], row["corpus_id"]) for row in rows},
            )
            self.assertIn(
                ("program_linux", "writes", "LINUX_REBUILD_CNTL", "linux-amdgpu"),
                {(row["src"], row["relation"], row["dst"], row["corpus_id"]) for row in rows},
            )

    def test_index_registered_corpus_uses_committed_yaml_resolver_profiles_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "corpus"
            source_root.mkdir()
            (source_root / "gfx.c").write_text(
                "\n".join(
                    [
                        "typedef unsigned int uint32_t;",
                        "static void program_default_yaml_register(void) {",
                        "  uint32_t tmp = RREG32_SOC15(GC, 0, regGCVM_L2_CNTL);",
                        "  tmp = REG_SET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE, 1);",
                        "  WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            db_path = root / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.upsert_corpus("code", "local", str(source_root), ["**/*.c"], status="not_indexed", file_count=0)

            summary = workbench.index_registered_corpora(db_path, corpus_ids=["code"])
            rows = [
                dict(row)
                for row in AsipStore.connect(str(db_path)).con.execute(
                    "select src, relation, dst, stage, source, provenance_json from edges order by src, relation, dst"
                )
            ]
            edge_triples = {(row["src"], row["relation"], row["dst"]) for row in rows}

            self.assertGreater(summary["edges"], 0)
            self.assertIn(("program_default_yaml_register", "reads", "GCVM_L2_CNTL"), edge_triples)
            self.assertIn(("program_default_yaml_register", "sets_field", "GCVM_L2_CNTL"), edge_triples)
            self.assertTrue(all(row["stage"] == "deterministic" for row in rows))
            self.assertTrue(any('"resolver_profile": "linux-amdgpu"' in row["provenance_json"] for row in rows))

    def test_index_registered_corpus_skips_low_signal_firmware_blobs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "corpus"
            (source_root / "ucode").mkdir(parents=True)
            (source_root / "ucode" / "gpu_ucode_signed.h").write_text(
                "static const unsigned int firmware_blob[] = {" + ",".join(["0xdeadbeef"] * 20000) + "};\n",
                encoding="utf-8",
            )
            (source_root / "driver.c").write_text(
                "static void useful_driver_function(void) {\n"
                "  WREG32(regUSEFUL_REGISTER, 1);\n"
                "}\n",
                encoding="utf-8",
            )
            db_path = root / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.upsert_corpus("code", "local", str(source_root), ["**/*.c", "**/*.h"], status="not_indexed", file_count=0)
            store.upsert_resolver_profile(
                "test-amd",
                "cpp",
                ["WREG32"],
                "reference",
                "test.yaml",
                config={
                    "id": "test-amd",
                    "language": "cpp",
                    "symbol_prefixes": ["reg"],
                    "wrappers": {"WREG32": {"symbol_arg": 0, "access": "write"}},
                },
            )

            summary = workbench.index_registered_corpora(db_path, corpus_ids=["code"])
            paths = {
                row["path"]
                for row in AsipStore.connect(str(db_path)).con.execute("select path from documents")
            }

            self.assertEqual(summary["documents"], 1)
            self.assertIn("driver.c", paths)
            self.assertNotIn("ucode/gpu_ucode_signed.h", paths)

    def test_global_graph_creates_document_section_nodes_from_indexed_chunks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            document_id = store.add_document("docs", "doc", "docs/guide.md")
            chunk_id = store.add_chunk(
                document_id,
                "# Programming local registers\n"
                "LOCAL_TEST_CNTL controls ENABLE_LOCAL_FIELD in this section.",
                1,
                2,
            )
            store.add_evidence(
                chunk_id=chunk_id,
                corpus_id="docs",
                source_type="doc",
                repo="local",
                path="docs/guide.md",
                line_start=2,
                line_end=2,
                symbol="LOCAL_TEST_CNTL",
                entity_type="register",
                access_type="mention",
                confidence=0.95,
                snippet="LOCAL_TEST_CNTL controls ENABLE_LOCAL_FIELD",
                resolved_chain="doc section -> LOCAL_TEST_CNTL",
            )

            graph = workbench.global_graph(db_path, limit=20)

            nodes = {node["id"]: node for node in graph["nodes"]}
            edges = {(edge["src"], edge["relation"], edge["dst"]) for edge in graph["edges"]}
            self.assertEqual(nodes["docs/guide.md#programming-local-registers"]["kind"], "doc_section")
            self.assertIn(
                ("docs/guide.md#programming-local-registers", "documents", "register:unknown:unknown:docs:LOCAL_TEST_CNTL"),
                edges,
            )

    def test_global_graph_exposes_pdf_section_node_provenance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            document_id = store.add_document("docs", "pdf", "docs/manual.pdf")
            chunk_id = store.add_chunk(
                document_id,
                "GCVM_L2_CNTL is described in the page text.",
                1,
                1,
                page=3,
            )
            store.add_evidence(
                chunk_id=chunk_id,
                corpus_id="docs",
                source_type="pdf",
                repo="local",
                path="docs/manual.pdf",
                line_start=1,
                line_end=1,
                page=3,
                symbol="GCVM_L2_CNTL",
                entity_type="register",
                access_type="mention",
                confidence=0.95,
                snippet="GCVM_L2_CNTL is described in the page text.",
                resolved_chain="pdf page -> GCVM_L2_CNTL",
            )

            graph = workbench.global_graph(db_path, limit=20)

            nodes = {node["id"]: node for node in graph["nodes"]}
            pdf_node = nodes["docs/manual.pdf#page-3"]
            self.assertEqual(pdf_node["kind"], "pdf_section")
            self.assertEqual(pdf_node["attr"]["source"][0]["path"], "docs/manual.pdf")
            self.assertEqual(pdf_node["attr"]["source"][0]["page"], 3)
            self.assertEqual(pdf_node["attr"]["anchor"], "page-3")
            self.assertEqual(pdf_node["label"], "manual.pdf page 3")

    def test_evidence_symbols_skip_resolver_operators_from_expected_terms(self):
        query = SimpleNamespace(
            id="wrapper-heavy-query",
            expected_terms=[
                "WREG32_SOC15",
                "REG_SET_FIELD",
                "SOC15_REG_OFFSET",
                "gpu_register",
                "amdgv_wreg32",
                "GCVM_L2_CNTL",
                "ENABLE_L2_CACHE",
            ],
        )

        symbols = workbench._evidence_symbols_for_chunk(
            "REG_SET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE, 1); "
            "WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp);",
            [query],
            [],
        )

        symbol_ids = {symbol for symbol, *_rest in symbols}
        self.assertIn("GCVM_L2_CNTL", symbol_ids)
        self.assertIn("ENABLE_L2_CACHE", symbol_ids)
        self.assertNotIn("WREG32_SOC15", symbol_ids)
        self.assertNotIn("REG_SET_FIELD", symbol_ids)
        self.assertNotIn("SOC15_REG_OFFSET", symbol_ids)
        self.assertNotIn("gpu_register", symbol_ids)
        self.assertNotIn("amdgv_wreg32", symbol_ids)

    def test_query_evidence_filters_stale_wrapper_symbols(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            document_id = store.add_document("code", "code", "gfx.c")
            chunk_id = store.add_chunk(
                document_id,
                "REG_SET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE, 1);",
                1,
                1,
            )
            for symbol in ["REG_SET_FIELD", "GCVM_L2_CNTL"]:
                store.add_evidence(
                    chunk_id=chunk_id,
                    corpus_id="code",
                    source_type="code",
                    repo="local",
                    path="gfx.c",
                    symbol=symbol,
                    entity_type="macro" if symbol == "REG_SET_FIELD" else "register",
                    access_type="mention",
                    confidence=0.95,
                    snippet="REG_SET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE, 1);",
                    resolved_chain=f"fixture -> {symbol}",
                )

            result = query_evidence(db_path, "REG_SET_FIELD GCVM_L2_CNTL", limit=10)

            self.assertIn("GCVM_L2_CNTL", {row["symbol"] for row in result["rows"]})
            self.assertNotIn("REG_SET_FIELD", {row["symbol"] for row in result["rows"]})

    def test_batch_semantic_edge_job_generates_edges_from_indexed_candidates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            document_id = store.add_document("docs", "doc", "docs/guide.md")
            chunk_id = store.add_chunk(
                document_id,
                "# Programming local registers\n"
                "GCVM_L2_CNTL and ENABLE_L2_CACHE are connected by this documentation section.",
                1,
                2,
            )
            for symbol, entity_type in [("GCVM_L2_CNTL", "register"), ("ENABLE_L2_CACHE", "field")]:
                store.add_evidence(
                    chunk_id=chunk_id,
                    corpus_id="docs",
                    source_type="doc",
                    repo="local",
                    path="docs/guide.md",
                    line_start=2,
                    line_end=2,
                    symbol=symbol,
                    entity_type=entity_type,
                    access_type="mention",
                    confidence=0.95,
                    snippet="GCVM_L2_CNTL and ENABLE_L2_CACHE are connected",
                    resolved_chain=f"doc section -> {symbol}",
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
            provider = FakeSemanticEdgeProvider()

            summary = generate_semantic_edges_batch(db_path, limit=4, batch_size=2, edge_provider=provider)
            graph = workbench.global_graph(db_path, limit=40)

            self.assertEqual(summary["source"], "semantic_edge_batch_job")
            self.assertEqual(summary["provider"], "ollama")
            self.assertEqual(summary["model"], "gemma4:e4b")
            self.assertGreaterEqual(summary["candidate_count"], 1)
            self.assertEqual(summary["edge_count"], 1)
            self.assertIn("CASE docs/guide.md#programming-local-registers", provider.prompt)
            self.assertNotIn(
                "ENABLE_L2_CACHE",
                {node["id"] for node in graph["nodes"]},
            )
            edge_row = AsipStore.connect(str(db_path)).con.execute(
                """
                select stage, source, provenance_json
                from edges
                where src = 'GCVM_L2_CNTL' and dst = 'ENABLE_L2_CACHE' and relation = 'sets_field'
                order by id desc
                limit 1
                """
            ).fetchone()
            self.assertEqual(edge_row["stage"], "semantic")
            self.assertEqual(edge_row["source"], "ollama")
            self.assertIn("gemma4:e4b", edge_row["provenance_json"])
            self.assertIn("\"mode\": \"batch\"", edge_row["provenance_json"])

    def test_semantic_batch_candidate_overfetch_multiplier_is_configurable(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        shared_doc = store.add_document("docs", "doc", "docs/shared.md")
        other_doc = store.add_document("docs", "doc", "docs/other.md")
        shared_chunk = store.add_chunk(shared_doc, "# Shared\nREG_A and REG_B configure the same block.", 1, 2)
        other_chunk = store.add_chunk(other_doc, "# Other\nREG_C configures another block.", 1, 2)
        for symbol in ("REG_A", "REG_B"):
            store.add_evidence(
                chunk_id=shared_chunk,
                corpus_id="docs",
                source_type="doc",
                repo="local",
                path="docs/shared.md",
                symbol=symbol,
                entity_type="register",
                access_type="mention",
                confidence=0.99,
                snippet=f"shared {symbol}",
                resolved_chain=f"shared -> {symbol}",
                line_start=2,
                line_end=2,
            )
        store.add_evidence(
            chunk_id=other_chunk,
            corpus_id="docs",
            source_type="doc",
            repo="local",
            path="docs/other.md",
            symbol="REG_C",
            entity_type="register",
            access_type="mention",
            confidence=0.98,
            snippet="other REG_C",
            resolved_chain="other -> REG_C",
            line_start=2,
            line_end=2,
        )

        low_overfetch = workbench._semantic_edge_batch_candidates(store, limit=2, overfetch_multiplier=1)
        high_overfetch = workbench._semantic_edge_batch_candidates(store, limit=2, overfetch_multiplier=2)

        self.assertEqual([candidate["id"] for candidate in low_overfetch], ["docs/shared.md#shared"])
        self.assertEqual(
            [candidate["id"] for candidate in high_overfetch],
            ["docs/shared.md#shared", "docs/other.md#other"],
        )

    def test_batch_semantic_edge_job_promotes_doc_section_nodes_into_default_global_graph(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.add_edge(
                "program_local_register",
                "GCVM_L2_CNTL",
                "writes",
                0.97,
                stage="deterministic",
                source="clang_ast",
            )
            document_id = store.add_document("docs", "doc", "docs/guide.md")
            chunk_id = store.add_chunk(
                document_id,
                "# Programming local registers\nGCVM_L2_CNTL is documented by this section.",
                1,
                2,
            )
            store.add_evidence(
                chunk_id=chunk_id,
                corpus_id="docs",
                source_type="doc",
                repo="local",
                path="docs/guide.md",
                line_start=2,
                line_end=2,
                symbol="GCVM_L2_CNTL",
                entity_type="register",
                access_type="mention",
                confidence=0.95,
                snippet="GCVM_L2_CNTL is documented by this section.",
                resolved_chain="doc section -> GCVM_L2_CNTL",
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
            provider = DocSectionSemanticEdgeProvider()

            summary = generate_semantic_edges_batch(db_path, limit=4, batch_size=2, edge_provider=provider)
            graph = workbench.global_graph(db_path, limit=40)

            nodes = {node["id"]: node for node in graph["nodes"]}
            edges = {(edge["src"], edge["relation"], edge["dst"]): edge for edge in graph["edges"]}
            self.assertEqual(summary["edge_count"], 1)
            self.assertIn("CASE docs/guide.md#programming-local-registers", provider.prompt)
            self.assertEqual(nodes["docs/guide.md#programming-local-registers"]["kind"], "doc_section")
            target_edge = edges[
                (
                    "docs/guide.md#programming-local-registers",
                    "documents",
                    "register:GC:unknown:unknown:GCVM_L2_CNTL",
                )
            ]
            self.assertEqual(target_edge["stage"], "semantic")
            self.assertEqual(target_edge["attr"]["original_relation"], "documents_register")

    def test_llm_doc_node_job_extracts_boxmatrix_style_doc_boxes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            document_id = store.add_document("docs", "doc", "docs/guide.md")
            store.add_chunk(
                document_id,
                "# Programming local registers\n"
                "GCVM_L2_CNTL controls ENABLE_L2_CACHE. The section describes the L2 cache control box.",
                1,
                2,
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
            provider = DocNodeProvider()

            summary = workbench.generate_doc_nodes_batch(db_path, limit=1, batch_size=1, edge_provider=provider)
            graph = workbench.global_graph(db_path, limit=20)

            box_id = "docs/guide.md#box-l2-cache-control"
            nodes = {node["id"]: node for node in graph["nodes"]}
            edges = {(edge["src"], edge["relation"], edge["dst"]): edge for edge in graph["edges"]}
            self.assertEqual(summary["source"], "doc_node_batch_job")
            self.assertEqual(summary["box_count"], 1)
            self.assertIn("BoxMatrix", provider.prompt)
            self.assertIn("Do not use a skill", provider.prompt)
            self.assertEqual(nodes[box_id]["kind"], "doc_box")
            self.assertEqual(nodes[box_id]["label"], "L2 cache control")
            self.assertEqual(nodes[box_id]["attr"]["source"][0]["path"], "docs/guide.md")
            self.assertEqual(edges[("docs/guide.md#programming-local-registers", "contains", box_id)]["stage"], "semantic")
            doc_edge = next(
                edge
                for (src, relation, dst), edge in edges.items()
                if src == box_id and relation == "documents" and dst.endswith(":GCVM_L2_CNTL")
            )
            self.assertEqual(doc_edge["stage"], "semantic")

    def test_batch_semantic_edge_job_rolls_back_partial_edges_on_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            for index, path in enumerate(["docs/guide-a.md", "docs/guide-b.md"], start=1):
                document_id = store.add_document("docs", "doc", path)
                chunk_id = store.add_chunk(
                    document_id,
                    f"# Section {index}\nGCVM_L2_CNTL ENABLE_L2_CACHE candidate {index}",
                    1,
                    2,
                )
                for symbol, entity_type in [("GCVM_L2_CNTL", "register"), ("ENABLE_L2_CACHE", "field")]:
                    store.add_evidence(
                        chunk_id=chunk_id,
                        corpus_id="docs",
                        source_type="doc",
                        repo="local",
                        path=path,
                        line_start=2,
                        line_end=2,
                        symbol=symbol,
                        entity_type=entity_type,
                        access_type="mention",
                        confidence=0.95,
                        snippet="GCVM_L2_CNTL ENABLE_L2_CACHE",
                        resolved_chain=f"doc section -> {symbol}",
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

            with self.assertRaises(RuntimeError):
                generate_semantic_edges_batch(
                    db_path,
                    limit=2,
                    batch_size=1,
                    edge_provider=FailingSecondBatchSemanticEdgeProvider(),
                )

            store_after = AsipStore.connect(str(db_path))
            self.assertEqual(store_after.con.execute("select count(*) from edges").fetchone()[0], 0)
            job = store_after.con.execute("select status from jobs order by id desc limit 1").fetchone()
            self.assertEqual(job["status"], "failed")

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
            graph = summary["graph"]

            self.assertEqual(summary["source"], "semantic_edge_job")
            self.assertEqual(summary["provider"], "ollama")
            self.assertEqual(summary["model"], "gemma4:e4b")
            self.assertEqual(summary["edge_count"], 1)
            self.assertIn("GCVM_L2_CNTL", provider.prompt)
            self.assertIn("ENABLE_L2_CACHE", provider.prompt)
            self.assertEqual([], graph["edges"])
            self.assertNotIn("ENABLE_L2_CACHE", {node["id"] for node in graph["nodes"]})
            register_node = next(node for node in graph["nodes"] if node["kind"] == "register")
            self.assertEqual(register_node["label"], "GCVM_L2_CNTL")
            self.assertIn("ENABLE_L2_CACHE", register_node["attr"]["fields"])


if __name__ == "__main__":
    unittest.main()
