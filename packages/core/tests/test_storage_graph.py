import json
import sqlite3
import importlib.util
import tempfile
from pathlib import Path
import unittest

from asip.index_artifacts import index_full_corpus_run
from asip.storage import AsipStore


class StorageGraphTests(unittest.TestCase):
    def test_sqlite_fts5_indexes_and_queries_evidence_chunks(self):
        store = AsipStore.connect(":memory:")
        store.migrate()

        document_id = store.add_document(
            corpus_id="mxgpu",
            source_type="code",
            path="libgv/core/hw/navi3/gfx_v11_0.c",
        )
        store.add_chunk(
            document_id=document_id,
            text="tmp = REG_SET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE, 1);",
            line_start=322,
            line_end=323,
        )

        matches = store.search_text("ENABLE_L2_CACHE")

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["path"], "libgv/core/hw/navi3/gfx_v11_0.c")
        self.assertEqual(matches[0]["line_start"], 322)

    def test_migrate_adds_evidence_chunk_lookup_index(self):
        store = AsipStore.connect(":memory:")
        store.migrate()

        plan = " ".join(
            str(row["detail"])
            for row in store.con.execute(
                """
                explain query plan
                select id, chunk_id, corpus_id, source_type, repo, path, line_start, line_end, page,
                  symbol, entity_type, ip_block, asic_or_generation, access_type,
                  confidence, snippet, resolved_chain, query_id
                from evidence
                where chunk_id in (1, 2, 3)
                order by confidence desc, id asc
                limit 24
                """
            )
        )

        self.assertIn("idx_evidence_chunk_confidence", plan)
        self.assertNotIn("SCAN evidence", plan)

    def test_find_evidence_candidates_prefers_fts_chunk_lookup(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        document_id = store.add_document("docs", "doc", "docs/doorbell.md")
        chunk_id = store.add_chunk(document_id, "doorbell interrupt disable", 1, 1)
        store.add_evidence(
            chunk_id=chunk_id,
            corpus_id="docs",
            source_type="doc",
            repo="local",
            path="docs/doorbell.md",
            symbol="BIF_DOORBELL_INT_CNTL",
            entity_type="register",
            access_type="mention",
            confidence=0.95,
            snippet="BIF_DOORBELL_INT_CNTL",
            resolved_chain="register mention",
        )

        traced_sql = []
        store.con.set_trace_callback(traced_sql.append)

        rows = store.find_evidence_candidates(["doorbell"], [chunk_id], limit=1)

        store.con.set_trace_callback(None)
        self.assertEqual([row["symbol"] for row in rows], ["BIF_DOORBELL_INT_CNTL"])
        self.assertFalse(any("lower(symbol) like" in sql.lower() for sql in traced_sql))

    def test_graph_expansion_reads_persisted_edges(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.add_edge("GCVM_L2_CNTL", "ENABLE_L2_CACHE", "has_field", 0.98)
        store.add_edge("gmc_v11_0_init_golden_registers", "GCVM_L2_CNTL", "writes", 0.94)

        neighborhood = store.expand_graph("GCVM_L2_CNTL", hops=1)

        self.assertEqual(
            {edge["src"] for edge in neighborhood["edges"]} | {edge["dst"] for edge in neighborhood["edges"]},
            {"GCVM_L2_CNTL", "ENABLE_L2_CACHE", "gmc_v11_0_init_golden_registers"},
        )
        self.assertEqual(len(neighborhood["edges"]), 2)

    def test_add_edge_rejects_configured_resolver_wrapper_endpoints(self):
        store = AsipStore.connect(":memory:")
        store.migrate()

        wrapper_source_id = store.add_edge("AMDGV_WRITE_REG", "GCVM_L2_CNTL", "wraps", 0.93)
        wrapper_target_id = store.add_edge("GCVM_L2_CNTL", "gpu_register", "wraps", 0.93)
        real_edge_id = store.add_edge("GCVM_L2_CNTL", "ENABLE_L2_CACHE", "has_field", 0.98)

        rows = store.con.execute("select src, dst from edges order by id").fetchall()
        self.assertEqual(wrapper_source_id, 0)
        self.assertEqual(wrapper_target_id, 0)
        self.assertGreater(real_edge_id, 0)
        self.assertEqual([(row["src"], row["dst"]) for row in rows], [("GCVM_L2_CNTL", "ENABLE_L2_CACHE")])

    def test_deleting_one_corpus_index_preserves_other_corpus_edges(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.upsert_corpus("mxgpu", "local", "/tmp/mxgpu", ["**/*.c"], status="indexed", file_count=1)
        store.upsert_corpus("linux-amdgpu", "local", "/tmp/linux", ["**/*.c"], status="indexed", file_count=1)
        mxgpu_doc = store.add_document("mxgpu", "code", "mxgpu.c")
        linux_doc = store.add_document("linux-amdgpu", "code", "linux.c")
        store.add_chunk(mxgpu_doc, "MXGPU_REG", 1, 1)
        store.add_chunk(linux_doc, "LINUX_REG", 1, 1)
        store.add_edge("mxgpu_func", "MXGPU_REG", "writes", 0.97, path="mxgpu.c")
        store.add_edge("linux_func", "LINUX_REG", "writes", 0.97, path="linux.c")

        store.delete_index_for_corpora(["mxgpu"])

        rows = store.con.execute("select src, dst, path from edges order by id").fetchall()
        self.assertEqual([(row["src"], row["dst"], row["path"]) for row in rows], [("linux_func", "LINUX_REG", "linux.c")])

    def test_legacy_graph_expansion_omits_persisted_wrapper_hubs(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.add_edge("program_cache", "GCVM_L2_CNTL", "writes", 0.97)
        store.con.execute(
            """
            insert into edges(src, dst, relation, confidence, stage, source, path, provenance_json)
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("AMDGV_WRITE_REG", "GCVM_L2_CNTL", "wraps", 0.93, "deterministic", "", "", "{}"),
        )

        neighborhood = store.expand_graph("GCVM_L2_CNTL", hops=1)

        node_ids = {node["id"] for node in neighborhood["nodes"]}
        edge_endpoints = {endpoint for edge in neighborhood["edges"] for endpoint in (edge["src"], edge["dst"])}
        self.assertNotIn("AMDGV_WRITE_REG", node_ids)
        self.assertNotIn("AMDGV_WRITE_REG", edge_endpoints)
        self.assertIn("program_cache", node_ids)

    def test_networkx_graph_is_built_from_sqlite_edges(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.add_edge("GCVM_L2_CNTL", "ENABLE_L2_CACHE", "has_field", 0.98)
        store.add_edge("GCVM_L2_CNTL", "ENABLE_L2_CACHE", "documents_field", 0.88)
        store.add_edge("gmc_v11_0_init_golden_registers", "GCVM_L2_CNTL", "writes", 0.94)

        graph = store.to_networkx()

        self.assertTrue(graph.has_edge("GCVM_L2_CNTL", "ENABLE_L2_CACHE"))
        edge_payloads = graph.get_edge_data("GCVM_L2_CNTL", "ENABLE_L2_CACHE")
        relations = {payload["relation"] for payload in edge_payloads.values()}
        self.assertEqual(relations, {"has_field", "documents_field"})

    def test_networkx_graph_expansion_skips_function_metadata_scan_without_edges(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store._known_graph_function_metadata = lambda: (_ for _ in ()).throw(AssertionError("unexpected metadata scan"))

        graph = store.expand_graph_networkx("GCVM_L2_CNTL", hops=1)

        self.assertEqual(graph["edges"], [])
        self.assertEqual(len(graph["nodes"]), 1)
        self.assertEqual(graph["nodes"][0]["label"], "GCVM_L2_CNTL")

    def test_networkx_graph_expansion_skips_function_metadata_scan_for_deterministic_edges(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.add_edge(
            "program_cache",
            "GCVM_L2_CNTL",
            "writes",
            0.97,
            stage="deterministic",
            source="clang_ast",
            path="driver.c",
            provenance={"function": "program_cache"},
        )
        store._known_graph_function_metadata = lambda: (_ for _ in ()).throw(AssertionError("unexpected metadata scan"))

        graph = store.expand_graph_networkx("GCVM_L2_CNTL", hops=1)

        self.assertEqual(len(graph["edges"]), 1)
        self.assertIn("program_cache", graph["edges"][0]["src"])

    def test_global_graph_budget_preserves_semantic_doc_box_edges(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        for index in range(5):
            store.add_edge(f"program_{index}", f"REG_{index}", "writes", 0.99 - index * 0.01)
        store.add_edge(
            "docs/guide.md#overview",
            "docs/guide.md#box-cache-policy",
            "contains_box",
            0.9,
            stage="semantic",
            source="ollama",
        )

        graph = store.global_graph_networkx(limit=2)

        edge_triples = {(edge["src"], edge["relation"], edge["dst"]) for edge in graph["edges"]}
        node_kinds = {node["id"]: node["kind"] for node in graph["nodes"]}
        self.assertIn(("docs/guide.md#overview", "contains", "docs/guide.md#box-cache-policy"), edge_triples)
        self.assertEqual(node_kinds["docs/guide.md#box-cache-policy"], "doc_box")

    def test_global_graph_skips_function_metadata_scan_for_deterministic_edges(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.add_edge(
            "program_cache",
            "GCVM_L2_CNTL",
            "writes",
            0.97,
            stage="deterministic",
            source="clang_ast",
            path="driver.c",
            provenance={"function": "program_cache"},
        )
        store._known_graph_function_metadata = lambda: (_ for _ in ()).throw(AssertionError("unexpected metadata scan"))

        graph = store.global_graph_networkx(limit=10)

        self.assertEqual(len(graph["edges"]), 1)
        self.assertIn("program_cache", graph["edges"][0]["src"])

    def test_global_graph_uses_boxmatrix_node_schema_and_folds_fields_into_register_attrs(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.add_edge(
            "program_l2_cache",
            "GCVM_L2_CNTL",
            "sets_field",
            0.97,
            stage="deterministic",
            source="clang_preprocess",
            path="mxgpu/gfx.c",
            line_start=12,
            line_end=12,
            provenance={
                "extractor": "code_graph",
                "function": "program_l2_cache",
                "field": "ENABLE_L2_CACHE",
                "wrapper": "REG_SET_FIELD",
                "ip": "GC",
                "ip_version": "11.0",
                "corpus_id": "mxgpu",
                "repo": "https://github.com/amd/MxGPU-Virtualization",
            },
        )
        store.con.execute(
            """
            insert into edges(src, dst, relation, confidence, stage, source, path, provenance_json)
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("program_l2_cache", "ENABLE_L2_CACHE", "sets_field", 0.5, "deterministic", "legacy", "mxgpu/gfx.c", "{}"),
        )

        graph = store.global_graph_networkx(limit=20)

        node_by_id = {node["id"]: node for node in graph["nodes"]}
        self.assertNotIn("ENABLE_L2_CACHE", node_by_id)
        self.assertIn("function:mxgpu:mxgpu/gfx.c:program_l2_cache", node_by_id)
        self.assertIn("register:GC:11.0:GCVM_L2_CNTL", node_by_id)
        register_node = node_by_id["register:GC:11.0:GCVM_L2_CNTL"]
        function_node = node_by_id["function:mxgpu:mxgpu/gfx.c:program_l2_cache"]
        for node in (register_node, function_node):
            self.assertIn("label", node)
            self.assertIsInstance(node["in"], list)
            self.assertIsInstance(node["out"], list)
            self.assertIsInstance(node["attr"], dict)
            self.assertGreaterEqual(len(node["attr"]["source"]), 1)
        self.assertEqual(register_node["kind"], "register")
        self.assertIn("ENABLE_L2_CACHE", register_node["attr"]["fields"])
        self.assertTrue(
            any("GCVM_L2_CNTL" in item and "ENABLE_L2_CACHE" in item for item in function_node["out"])
        )
        self.assertIn(
            ("function:mxgpu:mxgpu/gfx.c:program_l2_cache", "sets_field", "register:GC:11.0:GCVM_L2_CNTL"),
            {(edge["src"], edge["relation"], edge["dst"]) for edge in graph["edges"]},
        )
        field_edge = next(edge for edge in graph["edges"] if edge["relation"] == "sets_field")
        self.assertIn("source", field_edge["attr"])
        self.assertIn("ENABLE_L2_CACHE", field_edge["attr"]["fields"])
        self.assertEqual(field_edge["attr"]["resolver_wrappers"], ["REG_SET_FIELD"])

    def test_expand_graph_keeps_mm_prefixed_functions_as_functions_with_field_attr(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.add_edge(
            "mmhub_v9_4_set_fault_enable_default",
            "VML2PF0_VM_L2_PROTECTION_FAULT_CNTL",
            "sets_field",
            0.97,
            stage="deterministic",
            source="clang_ast",
            path="drivers/gpu/drm/amd/amdgpu/mmhub_v9_4.c",
            line_start=488,
            line_end=488,
            provenance={
                "extractor": "code_graph",
                "function": "mmhub_v9_4_set_fault_enable_default",
                "field": "RANGE_PROTECTION_FAULT_ENABLE_DEFAULT",
                "wrapper": "REG_SET_FIELD",
                "ip_version": "9.4",
            },
        )

        graph = store.expand_graph_networkx("VML2PF0_VM_L2_PROTECTION_FAULT_CNTL", hops=1)

        node_by_id = {node["id"]: node for node in graph["nodes"]}
        self.assertIn(
            "function:unknown:drivers/gpu/drm/amd/amdgpu/mmhub_v9_4.c:mmhub_v9_4_set_fault_enable_default",
            node_by_id,
        )
        self.assertNotIn("register:unknown:9.4:mmhub_v9_4_set_fault_enable_default", node_by_id)
        edge = graph["edges"][0]
        self.assertEqual(edge["relation"], "sets_field")
        self.assertIn("RANGE_PROTECTION_FAULT_ENABLE_DEFAULT", edge["attr"]["fields"])

    def test_global_graph_normalizes_edge_relation_enum(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.add_edge(
            "docs/guide.md#overview",
            "docs/guide.md#box-cache-policy",
            "contains_box",
            0.9,
            stage="semantic",
            source="ollama",
            path="docs/guide.md",
            provenance={"extractor": "doc_nodes", "box_node_id": "docs/guide.md#box-cache-policy"},
        )
        store.add_edge(
            "docs/guide.md#box-cache-policy",
            "GCVM_L2_CNTL",
            "documents_register",
            0.88,
            stage="semantic",
            source="ollama",
            path="docs/guide.md",
            provenance={"model": "gemma4:e4b", "job_id": 7, "ip": "GC", "ip_version": "11.0"},
        )
        store.add_edge(
            "docs/guide.md#box-cache-policy",
            "GCVM_L2_CNTL",
            "explains_runtime_implication",
            0.77,
            stage="semantic",
            source="ollama",
            path="docs/guide.md",
            provenance={"model": "gemma4:e4b", "job_id": 7, "ip": "GC", "ip_version": "11.0"},
        )

        graph = store.global_graph_networkx(limit=20)

        relation_by_original = {
            edge["attr"].get("original_relation", edge["relation"]): edge["relation"] for edge in graph["edges"]
        }
        self.assertEqual(relation_by_original["contains_box"], "contains")
        self.assertEqual(relation_by_original["documents_register"], "documents")
        self.assertEqual(relation_by_original["explains_runtime_implication"], "relates_to")

    def test_semantic_code_edges_do_not_promote_local_variables_to_function_nodes(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        document_id = store.add_document(
            "linux-amdgpu",
            "code",
            "drivers/gpu/drm/amd/amdgpu/irq.c",
        )
        chunk_id = store.add_chunk(
            document_id,
            "void real_handler(const void *ih_ring_entry) { callee_func(ih_ring_entry); }",
            line_start=10,
            line_end=12,
        )
        store.add_evidence(
            chunk_id,
            "linux-amdgpu",
            "code",
            "https://github.com/torvalds/linux",
            "drivers/gpu/drm/amd/amdgpu/irq.c",
            "real_handler",
            "function",
            "mention",
            0.95,
            "void real_handler(const void *ih_ring_entry)",
            "",
            line_start=10,
        )
        store.add_evidence(
            chunk_id,
            "linux-amdgpu",
            "code",
            "https://github.com/torvalds/linux",
            "drivers/gpu/drm/amd/amdgpu/irq.c",
            "callee_func",
            "function",
            "mention",
            0.92,
            "callee_func(ih_ring_entry);",
            "",
            line_start=11,
        )
        store.add_evidence(
            chunk_id,
            "linux-amdgpu",
            "code",
            "https://github.com/torvalds/linux",
            "drivers/gpu/drm/amd/amdgpu/irq.c",
            "ih_ring_entry",
            "function",
            "mention",
            0.7,
            "void real_handler(const void *ih_ring_entry)",
            "",
            line_start=10,
        )
        store.add_edge(
            "real_handler",
            "callee_func",
            "calls",
            0.9,
            stage="semantic",
            source="ollama",
            provenance={"extractor": "semantic_edges", "model": "gemma4:e4b"},
        )
        store.add_edge(
            "real_handler",
            "ih_ring_entry",
            "reads",
            0.9,
            stage="semantic",
            source="ollama",
            provenance={"extractor": "semantic_edges", "model": "gemma4:e4b"},
        )

        graph = store.global_graph_networkx(limit=20)

        node_ids = {node["id"] for node in graph["nodes"]}
        edge_triples = {(edge["src"], edge["relation"], edge["dst"]) for edge in graph["edges"]}
        self.assertIn(
            (
                "function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/irq.c:real_handler",
                "calls",
                "function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/irq.c:callee_func",
            ),
            edge_triples,
        )
        self.assertNotIn("function:unknown:unknown:ih_ring_entry", node_ids)
        self.assertFalse(any(edge["dst"].endswith(":ih_ring_entry") for edge in graph["edges"]))

    def test_register_nodes_merge_only_when_ip_version_matches(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        for corpus_id, repo, ip_version, function_name, path in [
            ("mxgpu", "https://github.com/amd/MxGPU-Virtualization", "11.0", "program_l2_cache", "mxgpu/gfx.c"),
            ("linux-amdgpu", "https://github.com/torvalds/linux", "11.0", "gmc_v11_0_init", "linux/gmc_v11.c"),
            ("linux-amdgpu", "https://github.com/torvalds/linux", "12.0", "gmc_v12_0_init", "linux/gmc_v12.c"),
        ]:
            store.add_edge(
                function_name,
                "GCVM_L2_CNTL",
                "writes",
                0.91,
                stage="deterministic",
                source="clang_ast",
                path=path,
                line_start=8,
                provenance={
                    "extractor": "code_graph",
                    "function": function_name,
                    "ip": "GC",
                    "ip_version": ip_version,
                    "corpus_id": corpus_id,
                    "repo": repo,
                },
            )

        graph = store.global_graph_networkx(limit=20)

        registers = [node for node in graph["nodes"] if node["kind"] == "register"]
        register_ids = {node["id"] for node in registers}
        self.assertEqual(register_ids, {"register:GC:11.0:GCVM_L2_CNTL", "register:GC:12.0:GCVM_L2_CNTL"})
        merged_sources = next(node for node in registers if node["id"] == "register:GC:11.0:GCVM_L2_CNTL")["attr"][
            "source"
        ]
        self.assertEqual({source["corpus_id"] for source in merged_sources}, {"mxgpu", "linux-amdgpu"})

    def test_edges_record_graph_build_stage_and_provenance(self):
        store = AsipStore.connect(":memory:")
        store.migrate()

        deterministic_id = store.add_edge(
            "program_local_register",
            "GCVM_L2_CNTL",
            "reads",
            0.97,
            stage="deterministic",
            source="clang_ast",
            path="gfx.c",
            line_start=12,
            line_end=12,
            provenance={"extractor": "code_graph", "function": "program_local_register"},
        )
        semantic_id = store.add_edge(
            "GCVM_L2_CNTL",
            "ENABLE_L2_CACHE",
            "semantically_controls",
            0.82,
            stage="semantic",
            source="ollama",
            provenance={"provider": "ollama", "model": "gemma4:e4b", "job_id": 7},
        )

        rows = {
            row["id"]: dict(row)
            for row in store.con.execute(
                "select id, stage, source, path, line_start, line_end, provenance_json from edges"
            )
        }

        self.assertEqual(rows[deterministic_id]["stage"], "deterministic")
        self.assertEqual(rows[deterministic_id]["source"], "clang_ast")
        self.assertEqual(rows[deterministic_id]["path"], "gfx.c")
        self.assertIn("code_graph", rows[deterministic_id]["provenance_json"])
        self.assertEqual(rows[semantic_id]["stage"], "semantic")
        self.assertIn("gemma4:e4b", rows[semantic_id]["provenance_json"])

    def test_artifact_import_skips_resolver_wrapper_edges(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_path = root / "run.json"
            db_path = root / "asip.db"
            run_path.write_text(
                json.dumps(
                    {
                        "scan": {
                            "queries": [
                                {
                                    "corpus": "mxgpu",
                                    "snippets": [
                                        {
                                            "path": "src/gfx.c",
                                            "text": "REG_SET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE, 1);",
                                            "line_start": 12,
                                            "line_end": 12,
                                        }
                                    ],
                                }
                            ]
                        },
                        "generated": {
                            "cases": [
                                {
                                    "edges": [
                                        {
                                            "src": "REG_SET_FIELD",
                                            "dst": "GCVM_L2_CNTL",
                                            "relation": "wraps",
                                            "confidence": 0.91,
                                        },
                                        {
                                            "src": "GCVM_L2_CNTL",
                                            "dst": "ENABLE_L2_CACHE",
                                            "relation": "has_field",
                                            "confidence": 0.98,
                                        },
                                    ]
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )

            summary = index_full_corpus_run(run_path, db_path)
            store = AsipStore.connect(str(db_path))
            rows = store.con.execute("select src, dst, relation from edges order by id").fetchall()

        self.assertEqual(summary["edges"], 1)
        self.assertEqual(
            [(row["src"], row["dst"], row["relation"]) for row in rows],
            [("GCVM_L2_CNTL", "ENABLE_L2_CACHE", "has_field")],
        )

    def test_edge_insert_can_be_batched_before_one_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()

            store.add_edge("program_cache", "GCVM_L2_CNTL", "writes", 0.97, commit=False)

            self.assertEqual(store.con.execute("select count(*) from edges").fetchone()[0], 1)
            with sqlite3.connect(db_path) as observer:
                self.assertEqual(observer.execute("select count(*) from edges").fetchone()[0], 0)

            store.con.commit()
            with sqlite3.connect(db_path) as observer:
                self.assertEqual(observer.execute("select count(*) from edges").fetchone()[0], 1)

    def test_evidence_insert_can_be_batched_before_one_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            document_id = store.add_document("mxgpu", "code", "src/gfx.c")
            chunk_id = store.add_chunk(document_id, "GCVM_L2_CNTL ENABLE_L2_CACHE", 1, 1)

            store.add_evidence(
                chunk_id=chunk_id,
                corpus_id="mxgpu",
                source_type="code",
                repo="local",
                path="src/gfx.c",
                symbol="GCVM_L2_CNTL",
                entity_type="register",
                access_type="write",
                confidence=0.9,
                snippet="GCVM_L2_CNTL",
                resolved_chain="resolved",
                commit=False,
            )

            self.assertEqual(store.con.execute("select count(*) from evidence").fetchone()[0], 1)
            with sqlite3.connect(db_path) as observer:
                self.assertEqual(observer.execute("select count(*) from evidence").fetchone()[0], 0)

            store.con.commit()
            with sqlite3.connect(db_path) as observer:
                self.assertEqual(observer.execute("select count(*) from evidence").fetchone()[0], 1)

    def test_embedding_vectors_are_queryable_with_sqlite_backed_fallback(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        document_id = store.add_document("docs", "doc", "Documentation/gpu/amdgpu.rst")
        gc_chunk = store.add_chunk(document_id, "GCVM_L2_CNTL enables L2 cache", 10, 10)
        sdma_chunk = store.add_chunk(document_id, "SDMA queue ring buffer control", 20, 20)
        store.add_embedding(gc_chunk, provider="ollama", model="nomic-embed-text", vector=[1.0, 0.0, 0.0])
        store.add_embedding(sdma_chunk, provider="ollama", model="nomic-embed-text", vector=[0.0, 1.0, 0.0])

        matches = store.search_vector([0.9, 0.1, 0.0], limit=1)

        self.assertEqual(matches[0]["chunk_id"], gc_chunk)
        self.assertGreater(matches[0]["score"], 0.9)

    def test_fts5_extension_is_available_in_runtime_sqlite(self):
        con = sqlite3.connect(":memory:")
        con.execute("create virtual table chunks_fts using fts5(text)")
        con.execute("insert into chunks_fts(text) values (?)", ("GCVM_L2_CNTL ENABLE_L2_CACHE",))

        rows = list(con.execute("select text from chunks_fts where chunks_fts match 'ENABLE_L2_CACHE'"))

        self.assertEqual(rows, [("GCVM_L2_CNTL ENABLE_L2_CACHE",)])

    def test_sqlite_vec_extension_can_run_when_runtime_supports_extensions(self):
        if importlib.util.find_spec("sqlite_vec") is None:
            self.skipTest("sqlite_vec package is not installed in this Python runtime")
        con = sqlite3.connect(":memory:")
        if not hasattr(con, "enable_load_extension"):
            self.skipTest("this sqlite3 build cannot load extensions")

        import sqlite_vec

        con.enable_load_extension(True)
        sqlite_vec.load(con)
        con.execute("create virtual table vec_items using vec0(embedding float[3])")
        con.execute("insert into vec_items(rowid, embedding) values (?, ?)", (1, sqlite_vec.serialize_float32([1, 0, 0])))
        con.execute("insert into vec_items(rowid, embedding) values (?, ?)", (2, sqlite_vec.serialize_float32([0, 1, 0])))

        rows = list(
            con.execute(
                "select rowid from vec_items where embedding match ? order by distance limit 1",
                (sqlite_vec.serialize_float32([0.9, 0.1, 0]),),
            )
        )

        self.assertEqual(rows, [(1,)])


if __name__ == "__main__":
    unittest.main()
