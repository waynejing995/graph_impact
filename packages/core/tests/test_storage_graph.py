import json
import sqlite3
import importlib.util
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from asip.graph_schema import ALLOWED_PRODUCT_RELATIONS
from asip.index_artifacts import index_full_corpus_run
from asip.storage import AsipStore, _function_merge_policy_for_rule, _snippet_has_callable_symbol


class StorageGraphTests(unittest.TestCase):
    def _add_function_register_edge(
        self,
        store: AsipStore,
        raw_function_name: str,
        register_symbol: str,
        *,
        path: str,
        ip: str = "GC",
        ip_version: str = "unknown",
        relation: str = "writes",
        field: str = "",
        resolver_profile: str = "linux-amdgpu",
        corpus_id: str = "linux-amdgpu",
        repo: str = "linux",
    ) -> None:
        provenance = {
            "extractor": "code_graph",
            "function": raw_function_name,
            "corpus_id": corpus_id,
            "repo": repo,
            "path": path,
            "line_start": 10,
            "line_end": 10,
            "ip": ip,
            "ip_version": ip_version,
        }
        if resolver_profile:
            provenance["resolver_profile"] = resolver_profile
        if field:
            provenance["field"] = field
        store.add_edge(
            raw_function_name,
            register_symbol,
            relation,
            0.95,
            stage="deterministic",
            source="clang_text_spans",
            path=path,
            line_start=10,
            line_end=10,
            provenance=provenance,
        )

    def _add_linux_amdgpu_resolver_profile(self, store: AsipStore) -> None:
        store.upsert_resolver_profile(
            "linux-amdgpu",
            "cpp",
            ["WREG32"],
            "write",
            "configs/resolvers/linux-amdgpu.yaml",
            config={
                "id": "linux-amdgpu",
                "language": "cpp",
                "wrappers": {"WREG32": {"symbol_arg": 0, "access": "write"}},
                "graph": {
                    "function_normalization": {
                        "enabled": True,
                        "rules": [
                            {
                                "id": "amd-ip-versioned-functions",
                                "enabled": True,
                                "match": r"^(?P<ip_block>gfxhub|mmhub|gfx|sdma|gmc|nbio|df|ih)_v(?P<ip_version>\d+_\d+(?:_\d+)?)_(?P<operation>.+)$",
                                "canonical": "{ip_block}_{operation}",
                                "merge_policy": {
                                    "mode": "concept_with_implementations",
                                    "warn_register_overlap_below": 0.35,
                                    "split_register_overlap_below": 0.10,
                                },
                            }
                        ],
                    }
                },
            },
        )

    def test_callable_symbol_scan_avoids_regex_compile_hot_path(self):
        with patch("asip.storage.re.search", side_effect=AssertionError("regex search should not run")):
            self.assertTrue(_snippet_has_callable_symbol("status = gfx_v11_0_hw_init (adev);", "gfx_v11_0_hw_init"))
            self.assertFalse(_snippet_has_callable_symbol("status = gfx_v11_0_hw_init_extra(adev);", "gfx_v11_0_hw_init"))
            self.assertFalse(_snippet_has_callable_symbol("status = gfx_v11_0_hw_init;", "gfx_v11_0_hw_init"))

    def test_unknown_function_merge_policy_uses_default_thresholds(self):
        policy = _function_merge_policy_for_rule("missing-rule")

        self.assertEqual(policy.warn_register_overlap_below, 0.35)
        self.assertEqual(policy.split_register_overlap_below, 0.10)

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

    def test_function_concept_nodes_merge_versioned_implementations(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        self._add_linux_amdgpu_resolver_profile(store)
        self._add_function_register_edge(
            store,
            "gfxhub_v11_5_0_gart_enable",
            "GCVM_L2_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c",
            ip_version="11_5_0",
            relation="sets_field",
            field="ENABLE_L2_CACHE",
        )
        self._add_function_register_edge(
            store,
            "gfxhub_v12_0_gart_enable",
            "GCVM_L2_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
            ip_version="12_0",
            relation="sets_field",
            field="ENABLE_L2_CACHE",
        )

        graph = store.global_graph_networkx(limit=100, function_view="concept")

        function_nodes = [node for node in graph["nodes"] if node["kind"] == "function"]
        self.assertEqual(len(function_nodes), 1)
        self.assertEqual(function_nodes[0]["attr"]["function_name"], "gfxhub_gart_enable")
        self.assertCountEqual(
            function_nodes[0]["attr"]["raw_function_names"],
            ["gfxhub_v11_5_0_gart_enable", "gfxhub_v12_0_gart_enable"],
        )
        self.assertEqual(len(function_nodes[0]["attr"]["raw_implementations"]), 2)
        self.assertIn(
            (
                "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gfxhub_gart_enable",
                "sets_field",
                "register:GC:GCVM_L2_CNTL",
            ),
            {(edge["src"], edge["relation"], edge["dst"]) for edge in graph["edges"]},
        )

    def test_function_concept_without_profile_metadata_does_not_use_global_rules(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        self._add_linux_amdgpu_resolver_profile(store)
        self._add_function_register_edge(
            store,
            "gfxhub_v11_5_0_gart_enable",
            "GCVM_L2_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c",
            ip_version="11_5_0",
            resolver_profile="",
            corpus_id="unknown-driver",
            repo="unknown",
        )
        self._add_function_register_edge(
            store,
            "gfxhub_v12_0_gart_enable",
            "GCVM_L2_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
            ip_version="12_0",
            resolver_profile="",
            corpus_id="unknown-driver",
            repo="unknown",
        )

        graph = store.global_graph_networkx(limit=100, function_view="concept")

        function_ids = {node["id"] for node in graph["nodes"] if node["kind"] == "function"}
        self.assertEqual(
            function_ids,
            {
                "function:unknown-driver:drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c:gfxhub_v11_5_0_gart_enable",
                "function:unknown-driver:drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c:gfxhub_v12_0_gart_enable",
            },
        )

    def test_function_concept_infers_profile_from_corpus_for_call_edges(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        self._add_linux_amdgpu_resolver_profile(store)
        store.add_edge(
            "gfxhub_v12_0_gart_enable",
            "gfxhub_v12_0_init_cache_regs",
            "calls",
            0.95,
            stage="deterministic",
            source="clang_text_spans",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
            line_start=20,
            line_end=20,
            provenance={
                "extractor": "code_graph",
                "function": "gfxhub_v12_0_gart_enable",
                "callee": "gfxhub_v12_0_init_cache_regs",
                "corpus_id": "linux-amdgpu",
                "repo": "linux",
                "path": "drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
                "callee_path": "drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
            },
        )

        graph = store.global_graph_networkx(limit=100, function_view="concept")

        function_ids = {node["id"] for node in graph["nodes"] if node["kind"] == "function"}
        self.assertEqual(
            function_ids,
            {
                "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gfxhub_gart_enable",
                "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gfxhub_init_cache_regs",
            },
        )
        self.assertIn(
            (
                "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gfxhub_gart_enable",
                "calls",
                "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gfxhub_init_cache_regs",
            ),
            {(edge["src"], edge["relation"], edge["dst"]) for edge in graph["edges"]},
        )

    def test_function_concept_node_label_uses_canonical_name(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        self._add_linux_amdgpu_resolver_profile(store)
        self._add_function_register_edge(
            store,
            "gfxhub_v12_0_gart_enable",
            "GCVM_L2_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
            ip_version="12_0",
        )

        graph = store.global_graph_networkx(limit=100, function_view="concept")

        function_node = next(node for node in graph["nodes"] if node["kind"] == "function")
        self.assertEqual(function_node["label"], "gfxhub_gart_enable")
        self.assertEqual(function_node["attr"]["function_name"], "gfxhub_gart_enable")

    def test_function_concept_infers_mxgpu_profile_from_configured_alias(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        self._add_function_register_edge(
            store,
            "gmc_v6_0_enable_bif_mgls",
            "GCVM_L2_CNTL",
            path="libgv/core/hw/CI/gmc_v6_0.c",
            ip_version="6_0",
            resolver_profile="",
            corpus_id="mxgpu",
            repo="https://github.com/amd/MxGPU-Virtualization",
        )

        graph = store.global_graph_networkx(limit=100, function_view="concept")

        function_node = next(node for node in graph["nodes"] if node["kind"] == "function")
        self.assertEqual(
            function_node["id"],
            "function:mxgpu:concept:amd-mxgpu:amd-ip-versioned-functions:gmc_enable_bif_mgls",
        )
        self.assertEqual(function_node["label"], "gmc_enable_bif_mgls")
        self.assertEqual(function_node["attr"]["normalization_profile_id"], "amd-mxgpu")

    def test_function_concept_normalization_is_scoped_to_edge_resolver_profile(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.upsert_resolver_profile(
            "custom-no-normalization",
            "cpp",
            ["CUSTOM_WRITE"],
            "write",
            "custom-no-normalization.yaml",
            config={
                "id": "custom-no-normalization",
                "language": "cpp",
                "wrappers": {"CUSTOM_WRITE": {"symbol_arg": 0, "access": "write"}},
            },
        )
        store.add_edge(
            "gfxhub_v12_0_gart_enable",
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
                "function": "gfxhub_v12_0_gart_enable",
                "resolver_profile": "custom-no-normalization",
                "corpus_id": "custom-driver",
                "repo": "local",
                "path": "drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
            },
        )

        graph = store.global_graph_networkx(limit=100, function_view="concept")

        function_ids = {node["id"] for node in graph["nodes"] if node["kind"] == "function"}
        self.assertEqual(
            function_ids,
            {
                "function:custom-driver:drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c:gfxhub_v12_0_gart_enable",
            },
        )
        self.assertFalse(any(":concept:linux-amdgpu:amd-ip-versioned-functions:" in node_id for node_id in function_ids))
        function_node = next(node for node in graph["nodes"] if node["kind"] == "function")
        self.assertEqual(function_node["attr"]["resolver_profile_ids"], ["custom-no-normalization"])
        graph_edge = next(edge for edge in graph["edges"] if edge["relation"] == "writes")
        self.assertEqual(graph_edge["attr"]["resolver_profile_ids"], ["custom-no-normalization"])

    def test_default_resolver_profile_rules_survive_db_profile_overrides(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.upsert_resolver_profile(
            "custom-no-normalization",
            "cpp",
            ["CUSTOM_WRITE"],
            "write",
            "custom-no-normalization.yaml",
            config={
                "id": "custom-no-normalization",
                "language": "cpp",
                "wrappers": {"CUSTOM_WRITE": {"symbol_arg": 0, "access": "write"}},
            },
        )
        self._add_function_register_edge(
            store,
            "gfxhub_v12_0_gart_enable",
            "GCVM_L2_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
            ip_version="12_0",
            resolver_profile="linux-amdgpu",
        )

        graph = store.global_graph_networkx(limit=100, function_view="concept")

        function_node = next(node for node in graph["nodes"] if node["kind"] == "function")
        self.assertEqual(
            function_node["id"],
            "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gfxhub_gart_enable",
        )
        self.assertEqual(function_node["attr"]["resolver_profile_ids"], ["linux-amdgpu"])

    def test_function_concept_node_ids_are_profile_namespaced_when_rule_ids_overlap(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        for profile_id in ("profile-a", "profile-b"):
            store.upsert_resolver_profile(
                profile_id,
                "cpp",
                ["CUSTOM_WRITE"],
                "write",
                f"{profile_id}.yaml",
                config={
                    "id": profile_id,
                    "language": "cpp",
                    "wrappers": {"CUSTOM_WRITE": {"symbol_arg": 0, "access": "write"}},
                    "graph": {
                        "function_normalization": {
                            "enabled": True,
                            "rules": [
                                {
                                    "id": "shared-rule",
                                    "enabled": True,
                                    "match": r"^(?P<ip_block>gfxhub)_v(?P<ip_version>\d+_\d+_\d+)_(?P<operation>.+)$",
                                    "canonical": "shared_{operation}",
                                }
                            ],
                        }
                    },
                },
            )
        self._add_function_register_edge(
            store,
            "gfxhub_v11_5_0_gart_enable",
            "GCVM_L2_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c",
            ip_version="11_5_0",
            resolver_profile="profile-a",
        )
        self._add_function_register_edge(
            store,
            "gfxhub_v12_0_0_gart_enable",
            "GCVM_CONTEXT0_PAGE_TABLE_BASE",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
            ip_version="12_0_0",
            resolver_profile="profile-b",
        )

        graph = store.global_graph_networkx(limit=100, function_view="concept")

        function_ids = {node["id"] for node in graph["nodes"] if node["kind"] == "function"}
        self.assertEqual(
            function_ids,
            {
                "function:linux-amdgpu:concept:profile-a:shared-rule:shared_gart_enable",
                "function:linux-amdgpu:concept:profile-b:shared-rule:shared_gart_enable",
            },
        )

    def test_disabled_db_resolver_profile_overrides_default_rules(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.upsert_resolver_profile(
            "linux-amdgpu",
            "cpp",
            ["WREG32"],
            "write",
            "configs/resolvers/linux-amdgpu.yaml",
            enabled=False,
        )
        self._add_function_register_edge(
            store,
            "gfxhub_v12_0_gart_enable",
            "GCVM_L2_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
            ip_version="12_0",
            resolver_profile="linux-amdgpu",
        )

        graph = store.global_graph_networkx(limit=100, function_view="concept")

        function_node = next(node for node in graph["nodes"] if node["kind"] == "function")
        self.assertEqual(
            function_node["id"],
            "function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c:gfxhub_v12_0_gart_enable",
        )

    def test_disabled_db_resolver_profile_alias_overrides_loaded_default_rules(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.upsert_resolver_profile(
            "alias-linux",
            "cpp",
            ["WREG32"],
            "write",
            "configs/resolvers/linux-amdgpu.yaml",
            enabled=False,
        )
        self._add_function_register_edge(
            store,
            "gfxhub_v12_0_gart_enable",
            "GCVM_L2_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
            ip_version="12_0",
            resolver_profile="linux-amdgpu",
        )

        graph = store.global_graph_networkx(limit=100, function_view="concept")

        function_node = next(node for node in graph["nodes"] if node["kind"] == "function")
        self.assertEqual(
            function_node["id"],
            "function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c:gfxhub_v12_0_gart_enable",
        )

    def test_function_concept_normalization_uses_db_resolver_profile_rule(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.upsert_resolver_profile(
            "custom-normalization",
            "cpp",
            ["CUSTOM_WRITE"],
            "write",
            "custom-normalization.yaml",
            config={
                "id": "custom-normalization",
                "language": "cpp",
                "wrappers": {"CUSTOM_WRITE": {"symbol_arg": 0, "access": "write"}},
                "graph": {
                    "function_normalization": {
                        "enabled": True,
                        "rules": [
                            {
                                "id": "custom-gfxhub-functions",
                                "enabled": True,
                                "match": r"^(?P<ip_block>gfxhub)_v(?P<ip_version>\d+_\d+_\d+)_(?P<operation>.+)$",
                                "canonical": "custom_{operation}",
                                "merge_policy": {
                                    "mode": "concept_with_implementations",
                                    "warn_register_overlap_below": 0.5,
                                    "split_register_overlap_below": 0.25,
                                },
                            }
                        ],
                    }
                },
            },
        )
        store.add_edge(
            "gfxhub_v12_0_0_gart_enable",
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
                "function": "gfxhub_v12_0_0_gart_enable",
                "resolver_profile": "custom-normalization",
                "corpus_id": "custom-driver",
                "repo": "local",
                "path": "drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
            },
        )

        graph = store.global_graph_networkx(limit=100, function_view="concept")

        function_node = next(node for node in graph["nodes"] if node["kind"] == "function")
        self.assertEqual(
            function_node["id"],
            "function:custom-driver:concept:custom-normalization:custom-gfxhub-functions:custom_gart_enable",
        )
        self.assertEqual(function_node["attr"]["normalization_rule"], "custom-gfxhub-functions")
        self.assertEqual(function_node["attr"]["resolver_profile_ids"], ["custom-normalization"])

    def test_function_concept_normalization_loads_db_profile_path_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_path = root / "path-normalization.yaml"
            profile_path.write_text(
                "\n".join(
                    [
                        "id: path-normalization",
                        "language: cpp",
                        "wrappers:",
                        "  CUSTOM_WRITE:",
                        "    symbol_arg: 0",
                        "    access: write",
                        "graph:",
                        "  function_normalization:",
                        "    enabled: true",
                        "    rules:",
                        "      - id: path-gfxhub-functions",
                        "        enabled: true",
                        "        match: \"^(?P<ip_block>gfxhub)_v(?P<ip_version>\\\\d+_\\\\d+_\\\\d+)_(?P<operation>.+)$\"",
                        "        canonical: \"path_{operation}\"",
                    ]
                ),
                encoding="utf-8",
            )
            store = AsipStore.connect(":memory:")
            store.migrate()
            store.upsert_resolver_profile(
                "path-normalization",
                "cpp",
                ["CUSTOM_WRITE"],
                "write",
                str(profile_path),
            )
            store.add_edge(
                "gfxhub_v12_0_0_gart_enable",
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
                    "function": "gfxhub_v12_0_0_gart_enable",
                    "resolver_profile": "path-normalization",
                    "corpus_id": "custom-driver",
                    "repo": "local",
                    "path": "drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
                },
            )

            graph = store.global_graph_networkx(limit=100, function_view="concept")

        function_node = next(node for node in graph["nodes"] if node["kind"] == "function")
        self.assertEqual(
            function_node["id"],
            "function:custom-driver:concept:path-normalization:path-gfxhub-functions:path_gart_enable",
        )
        self.assertEqual(function_node["attr"]["resolver_profile_ids"], ["path-normalization"])

    def test_function_concept_normalization_keys_path_profile_by_loaded_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            profile_path = root / "loaded-normalization.yaml"
            profile_path.write_text(
                "\n".join(
                    [
                        "id: loaded-normalization",
                        "language: cpp",
                        "wrappers:",
                        "  CUSTOM_WRITE:",
                        "    symbol_arg: 0",
                        "    access: write",
                        "graph:",
                        "  function_normalization:",
                        "    enabled: true",
                        "    rules:",
                        "      - id: loaded-gfxhub-functions",
                        "        enabled: true",
                        "        match: \"^(?P<ip_block>gfxhub)_v(?P<ip_version>\\\\d+_\\\\d+_\\\\d+)_(?P<operation>.+)$\"",
                        "        canonical: \"loaded_{operation}\"",
                    ]
                ),
                encoding="utf-8",
            )
            store = AsipStore.connect(":memory:")
            store.migrate()
            store.upsert_resolver_profile(
                "alias-normalization",
                "cpp",
                ["CUSTOM_WRITE"],
                "write",
                str(profile_path),
            )
            store.add_edge(
                "gfxhub_v12_0_0_gart_enable",
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
                    "function": "gfxhub_v12_0_0_gart_enable",
                    "resolver_profile": "loaded-normalization",
                    "corpus_id": "custom-driver",
                    "repo": "local",
                    "path": "drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
                },
            )

            graph = store.global_graph_networkx(limit=100, function_view="concept")

        function_node = next(node for node in graph["nodes"] if node["kind"] == "function")
        self.assertEqual(
            function_node["id"],
            "function:custom-driver:concept:loaded-normalization:loaded-gfxhub-functions:loaded_gart_enable",
        )
        self.assertEqual(function_node["attr"]["resolver_profile_ids"], ["loaded-normalization"])

    def test_register_normalization_uses_resolver_profile_identity(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.upsert_resolver_profile(
            "flat-register-profile",
            "cpp",
            ["CUSTOM_WRITE"],
            "write",
            "flat-register-profile.yaml",
            config={
                "id": "flat-register-profile",
                "language": "cpp",
                "wrappers": {"CUSTOM_WRITE": {"symbol_arg": 0, "access": "write"}},
                "graph": {
                    "register_normalization": {
                        "identity": "register:{symbol}",
                        "merge_across_repos_when_ip_and_symbol_match": True,
                        "merge_across_ip_versions": True,
                        "merge_across_ip_blocks": True,
                    }
                },
            },
        )
        self._add_function_register_edge(
            store,
            "write_gc_register",
            "GCVM_L2_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/gc.c",
            ip="GC",
            resolver_profile="flat-register-profile",
        )
        self._add_function_register_edge(
            store,
            "write_cp_register",
            "GCVM_L2_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/cp.c",
            ip="CP",
            resolver_profile="flat-register-profile",
        )

        graph = store.global_graph_networkx(limit=100, function_view="concept")

        register_ids = {node["id"] for node in graph["nodes"] if node["kind"] == "register"}
        self.assertEqual(register_ids, {"register:GCVM_L2_CNTL"})

    def test_function_merge_policy_is_scoped_when_rule_ids_overlap(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        for profile_id, warn_below, split_below in (
            ("a-split-profile", 0.5, 0.25),
            ("z-merge-profile", 0.0, 0.0),
        ):
            store.upsert_resolver_profile(
                profile_id,
                "cpp",
                ["CUSTOM_WRITE"],
                "write",
                f"{profile_id}.yaml",
                config={
                    "id": profile_id,
                    "language": "cpp",
                    "wrappers": {"CUSTOM_WRITE": {"symbol_arg": 0, "access": "write"}},
                    "graph": {
                        "function_normalization": {
                            "enabled": True,
                            "rules": [
                                {
                                    "id": "shared-gfxhub-functions",
                                    "enabled": True,
                                    "match": r"^(?P<ip_block>gfxhub)_v(?P<ip_version>\d+_\d+(?:_\d+)?)_(?P<operation>.+)$",
                                    "canonical": "shared_{operation}",
                                    "merge_policy": {
                                        "mode": "concept_with_implementations",
                                        "warn_register_overlap_below": warn_below,
                                        "split_register_overlap_below": split_below,
                                    },
                                }
                            ],
                        }
                    },
                },
            )
        for raw_function_name, register_symbol, path, ip_version in (
            (
                "gfxhub_v11_5_0_gart_enable",
                "GCVM_L2_CNTL",
                "drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c",
                "11_5_0",
            ),
            (
                "gfxhub_v12_0_gart_enable",
                "GCVM_CONTEXT0_PAGE_TABLE_BASE",
                "drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
                "12_0",
            ),
        ):
            self._add_function_register_edge(
                store,
                raw_function_name,
                register_symbol,
                path=path,
                ip_version=ip_version,
                resolver_profile="z-merge-profile",
            )

        graph = store.global_graph_networkx(limit=100, function_view="concept")

        function_node = next(node for node in graph["nodes"] if node["kind"] == "function")
        self.assertEqual(function_node["attr"]["normalization_rule"], "shared-gfxhub-functions")
        self.assertEqual(function_node["attr"]["resolver_profile_ids"], ["z-merge-profile"])
        self.assertEqual(function_node["attr"]["register_neighbor_overlap"], 0.0)
        self.assertEqual(function_node["attr"]["merge_status"], "merged")

    def test_function_concept_marks_disjoint_register_accesses_split_recommended(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        self._add_linux_amdgpu_resolver_profile(store)
        self._add_function_register_edge(
            store,
            "gfxhub_v11_5_0_gart_enable",
            "GCVM_L2_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c",
            ip_version="11_5_0",
        )
        self._add_function_register_edge(
            store,
            "gfxhub_v12_0_gart_enable",
            "GCVM_CONTEXT0_PAGE_TABLE_BASE",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
            ip_version="12_0",
        )

        graph = store.global_graph_networkx(limit=100, function_view="concept")

        node = next(node for node in graph["nodes"] if node["kind"] == "function")
        self.assertEqual(node["attr"]["merge_status"], "split_recommended")
        destinations = {edge["dst"] for edge in graph["edges"] if edge["src"] == node["id"]}
        self.assertIn("register:GC:GCVM_L2_CNTL", destinations)
        self.assertIn("register:GC:GCVM_CONTEXT0_PAGE_TABLE_BASE", destinations)
        for edge in graph["edges"]:
            if edge["src"] == node["id"]:
                self.assertIn("implementations", edge["attr"])

    def test_function_concept_marks_low_overlap_register_accesses_divergent(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        self._add_linux_amdgpu_resolver_profile(store)
        self._add_function_register_edge(
            store,
            "gfxhub_v11_5_0_gart_enable",
            "GCVM_L2_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c",
            ip_version="11_5_0",
        )
        self._add_function_register_edge(
            store,
            "gfxhub_v11_5_0_gart_enable",
            "GCVM_CONTEXT0_PAGE_TABLE_BASE",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c",
            ip_version="11_5_0",
        )
        self._add_function_register_edge(
            store,
            "gfxhub_v12_0_gart_enable",
            "GCVM_L2_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
            ip_version="12_0",
        )
        self._add_function_register_edge(
            store,
            "gfxhub_v12_0_gart_enable",
            "GCVM_L2_PROTECTION_FAULT_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
            ip_version="12_0",
        )

        graph = store.global_graph_networkx(limit=100, function_view="concept")

        node = next(node for node in graph["nodes"] if node["kind"] == "function")
        self.assertEqual(node["attr"]["merge_status"], "divergent")
        self.assertEqual(node["attr"]["register_neighbor_overlap"], 0.3333)

    def test_function_concept_keeps_high_overlap_register_accesses_merged(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        self._add_linux_amdgpu_resolver_profile(store)
        for raw_function_name, path, ip_version in (
            (
                "gfxhub_v11_5_0_gart_enable",
                "drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c",
                "11_5_0",
            ),
            (
                "gfxhub_v12_0_gart_enable",
                "drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
                "12_0",
            ),
        ):
            self._add_function_register_edge(
                store,
                raw_function_name,
                "GCVM_L2_CNTL",
                path=path,
                ip_version=ip_version,
            )
            self._add_function_register_edge(
                store,
                raw_function_name,
                "GCVM_CONTEXT0_PAGE_TABLE_BASE",
                path=path,
                ip_version=ip_version,
            )

        graph = store.global_graph_networkx(limit=100, function_view="concept")

        node = next(node for node in graph["nodes"] if node["kind"] == "function")
        self.assertEqual(node["attr"]["merge_status"], "merged")
        self.assertEqual(node["attr"]["register_neighbor_overlap"], 1.0)

    def test_function_implementation_view_keeps_versioned_function_nodes(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        self._add_linux_amdgpu_resolver_profile(store)
        self._add_function_register_edge(
            store,
            "gfxhub_v11_5_0_gart_enable",
            "GCVM_L2_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c",
            ip_version="11_5_0",
        )
        self._add_function_register_edge(
            store,
            "gfxhub_v12_0_gart_enable",
            "GCVM_L2_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
            ip_version="12_0",
        )

        graph = store.global_graph_networkx(limit=100, function_view="implementation")

        function_ids = {node["id"] for node in graph["nodes"] if node["kind"] == "function"}
        self.assertEqual(
            function_ids,
            {
                "function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c:gfxhub_v11_5_0_gart_enable",
                "function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c:gfxhub_v12_0_gart_enable",
            },
        )
        self.assertFalse(any(":concept:" in node_id for node_id in function_ids))

    def test_query_expansion_can_request_implementation_function_view(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        self._add_linux_amdgpu_resolver_profile(store)
        self._add_function_register_edge(
            store,
            "gfxhub_v11_5_0_gart_enable",
            "GCVM_L2_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c",
            ip_version="11_5_0",
        )
        self._add_function_register_edge(
            store,
            "gfxhub_v12_0_gart_enable",
            "GCVM_L2_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
            ip_version="12_0",
        )

        graph = store.expand_graph_networkx("GCVM_L2_CNTL", hops=1, function_view="implementation")

        function_ids = {node["id"] for node in graph["nodes"] if node["kind"] == "function"}
        self.assertEqual(
            function_ids,
            {
                "function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c:gfxhub_v11_5_0_gart_enable",
                "function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c:gfxhub_v12_0_gart_enable",
            },
        )

    def test_find_evidence_candidates_avoids_like_scan_for_sparse_exact_symbol_query(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        document_id = store.add_document("mxgpu", "code", "mxgpu/gfx.c")
        chunk_id = store.add_chunk(document_id, "REG_SET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE, 1)", 10, 10)
        store.add_evidence(
            chunk_id=chunk_id,
            corpus_id="mxgpu",
            source_type="code",
            repo="local",
            path="mxgpu/gfx.c",
            symbol="GCVM_L2_CNTL",
            entity_type="register",
            access_type="write",
            confidence=0.95,
            snippet="GCVM_L2_CNTL",
            resolved_chain="register GCVM_L2_CNTL",
        )

        traced_sql = []
        store.con.set_trace_callback(traced_sql.append)

        rows = store.find_evidence_candidates(["gcvm_l2_cntl"], [chunk_id], limit=8)

        store.con.set_trace_callback(None)
        self.assertEqual([row["symbol"] for row in rows], ["GCVM_L2_CNTL"])
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

    def test_query_graph_expansion_uses_frontier_edge_lookup_instead_of_full_graph_scan(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        self._add_linux_amdgpu_resolver_profile(store)
        store.add_edge("program_cache", "GCVM_L2_CNTL", "writes", 0.98)
        store.add_edge(
            "gmc_v11_0_init_golden_registers",
            "GCVM_L2_CNTL",
            "writes",
            0.94,
            provenance={
                "extractor": "code_graph",
                "function": "gmc_v11_0_init_golden_registers",
                "resolver_profile": "linux-amdgpu",
            },
        )
        store.add_edge("unrelated_func", "UNRELATED_REG", "writes", 0.94)

        with patch.object(store, "to_networkx", side_effect=AssertionError("query expansion should not scan all edges")):
            neighborhood = store.expand_graph_networkx_many(["GCVM_L2_CNTL"], hops=1)

        edge_pairs = {(edge["src"], edge["dst"]) for edge in neighborhood["edges"]}
        self.assertIn(("function:unknown:unknown:program_cache", "register:GC:GCVM_L2_CNTL"), edge_pairs)
        self.assertIn(
            (
                "function:unknown:concept:linux-amdgpu:amd-ip-versioned-functions:gmc_init_golden_registers",
                "register:GC:GCVM_L2_CNTL",
            ),
            edge_pairs,
        )
        self.assertNotIn(("function:unknown:unknown:unrelated_func", "register:unknown:UNRELATED_REG"), edge_pairs)

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

    def test_networkx_multi_seed_expansion_without_edges_returns_seed_nodes(self):
        store = AsipStore.connect(":memory:")
        store.migrate()

        graph = store.expand_graph_networkx_many(["GCVM_L2_CNTL", "SDMA0_QUEUE0_RB_CNTL"], hops=1)

        self.assertEqual(graph["edges"], [])
        self.assertEqual(
            [node["id"] for node in graph["nodes"]],
            [
                "register:GC:GCVM_L2_CNTL",
                "register:SDMA:SDMA0_QUEUE0_RB_CNTL",
            ],
        )

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
        self.assertEqual(node_kinds["docs/guide.md#box-cache-policy"], "doc")
        box_node = next(node for node in graph["nodes"] if node["id"] == "docs/guide.md#box-cache-policy")
        self.assertEqual(box_node["attr"]["doc_kind"], "boxmatrix_box")

    def test_product_graph_projects_document_subtypes_to_doc_nodes(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.add_edge(
            "docs/guide.md#programming-gcvm-l2",
            "GCVM_L2_CNTL",
            "documents_register",
            0.91,
            stage="semantic",
            source="ollama",
            path="docs/guide.md",
            provenance={"ip": "GC", "title": "Programming GCVM L2"},
        )
        store.add_edge(
            "docs/mi300.pdf#page-4",
            "GCVM_CONTEXT0_PAGE_TABLE_BASE",
            "documents_register",
            0.9,
            stage="semantic",
            source="ollama",
            path="docs/mi300.pdf",
            provenance={"ip": "GC", "page": 4, "title": "MI300 page 4"},
        )
        store.add_edge(
            "docs/guide.md#programming-gcvm-l2",
            "docs/guide.md#box-cache-policy",
            "contains_box",
            0.89,
            stage="semantic",
            source="ollama",
            path="docs/guide.md",
            provenance={"box_id": "box-cache-policy", "summary": "cache policy inputs and outputs"},
        )

        graph = store.global_graph_networkx(limit=20)

        node_by_id = {node["id"]: node for node in graph["nodes"]}
        for node in graph["nodes"]:
            self.assertIn(node["kind"], {"function", "register", "doc"})
        self.assertEqual(node_by_id["docs/guide.md#programming-gcvm-l2"]["kind"], "doc")
        self.assertEqual(node_by_id["docs/guide.md#programming-gcvm-l2"]["attr"]["doc_kind"], "markdown_section")
        self.assertEqual(node_by_id["docs/mi300.pdf#page-4"]["kind"], "doc")
        self.assertEqual(node_by_id["docs/mi300.pdf#page-4"]["attr"]["doc_kind"], "pdf_section")
        self.assertEqual(node_by_id["docs/mi300.pdf#page-4"]["attr"]["page"], 4)
        self.assertEqual(node_by_id["docs/guide.md#box-cache-policy"]["kind"], "doc")
        self.assertEqual(node_by_id["docs/guide.md#box-cache-policy"]["attr"]["doc_kind"], "boxmatrix_box")

    def test_global_graph_budget_preserves_function_call_backbone_edges(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        for index in range(10):
            store.add_edge(f"program_{index}", f"GCVM_L2_CNTL_{index}", "writes", 0.99 - index * 0.01)
        for index in range(3):
            store.add_edge(f"common_dispatch_{index}", f"callback_{index}", "calls", 0.72)

        graph = store.global_graph_networkx(limit=4)

        relations = [edge["relation"] for edge in graph["edges"]]
        self.assertIn("calls", relations)
        self.assertLessEqual(len(graph["edges"]), 4)

    def test_global_graph_budget_preserves_callback_operation_edges(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        self._add_linux_amdgpu_resolver_profile(store)
        for index in range(10):
            store.add_edge(f"isolated_writer_{index}", f"ISOLATED_CNTL_{index}", "writes", 0.99 - index * 0.001)
        store.add_edge(
            "amdgpu_device_hw_init",
            "gfx_v11_0_hw_init",
            "calls",
            0.72,
            source="clang_callback",
            provenance={
                "extractor": "code_graph",
                "function": "amdgpu_device_hw_init",
                "callee": "gfx_v11_0_hw_init",
                "resolver_profile": "linux-amdgpu",
            },
        )
        store.add_edge(
            "gfx_v11_0_hw_init",
            "GCVM_L2_CNTL",
            "writes",
            0.71,
            source="clang_text_spans",
            provenance={
                "extractor": "code_graph",
                "function": "gfx_v11_0_hw_init",
                "resolver_profile": "linux-amdgpu",
            },
        )

        graph = store.global_graph_networkx(limit=3)

        edge_triples = {(edge["src"], edge["relation"], edge["dst"]) for edge in graph["edges"]}
        self.assertIn(
            (
                "function:unknown:unknown:amdgpu_device_hw_init",
                "calls",
                "function:unknown:concept:linux-amdgpu:amd-ip-versioned-functions:gfx_hw_init",
            ),
            edge_triples,
        )
        self.assertIn(
            (
                "function:unknown:concept:linux-amdgpu:amd-ip-versioned-functions:gfx_hw_init",
                "writes",
                "register:GC:GCVM_L2_CNTL",
            ),
            edge_triples,
        )
        self.assertLessEqual(len(graph["edges"]), 3)

    def test_global_graph_defers_node_metadata_merge_for_unselected_edges(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        for index in range(40):
            store.add_edge(f"isolated_writer_{index}", f"ISOLATED_CNTL_{index}", "writes", 0.99 - index * 0.001)

        from asip import storage as storage_module

        calls = 0
        original = storage_module._merge_boxmatrix_metadata

        def counting_merge(*args, **kwargs):
            nonlocal calls
            calls += 1
            return original(*args, **kwargs)

        with patch("asip.storage._merge_boxmatrix_metadata", counting_merge):
            graph = store.global_graph_networkx(limit=3)

        self.assertEqual(len(graph["edges"]), 3)
        self.assertLessEqual(calls, 12)

    def test_global_graph_budget_preserves_cross_repo_register_bridge_edges(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        for index in range(20):
            store.add_edge(
                f"isolated_writer_{index}",
                f"ISOLATED_CNTL_{index}",
                "writes",
                0.99 - index * 0.001,
                stage="deterministic",
                path=f"isolated/{index}.c",
                provenance={
                    "function": f"isolated_writer_{index}",
                    "corpus_id": "linux-amdgpu",
                    "ip": "GC",
                },
            )
        for corpus_id, function_name, path in [
            ("linux-amdgpu", "linux_irq_init", "drivers/gpu/drm/amd/amdgpu/cik_ih.c"),
            ("mxgpu", "mxgpu_irq_init", "libgv/core/hw/AI/mi200/mi200_irqmgr.c"),
        ]:
            store.add_edge(
                function_name,
                "IH_RB_CNTL",
                "writes",
                0.61,
                stage="deterministic",
                path=path,
                provenance={
                    "function": function_name,
                    "corpus_id": corpus_id,
                    "ip": "IH",
                },
            )

        graph = store.global_graph_networkx(limit=4)

        edge_triples = {(edge["src"], edge["relation"], edge["dst"]) for edge in graph["edges"]}
        register_id = "register:IH:IH_RB_CNTL"
        self.assertIn(("function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/cik_ih.c:linux_irq_init", "writes", register_id), edge_triples)
        self.assertIn(("function:mxgpu:libgv/core/hw/AI/mi200/mi200_irqmgr.c:mxgpu_irq_init", "writes", register_id), edge_triples)
        register_node = next(node for node in graph["nodes"] if node["id"] == register_id)
        self.assertEqual({source["corpus_id"] for source in register_node["attr"]["source"]}, {"linux-amdgpu", "mxgpu"})
        self.assertLessEqual(len(graph["edges"]), 4)

    def test_global_graph_budget_preserves_largest_connected_backbone(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        for index in range(20):
            store.add_edge(f"isolated_writer_{index}", f"ISOLATED_CNTL_{index}", "writes", 0.99 - index * 0.001)
        for index in range(8):
            store.add_edge(f"common_dispatch_{index}", f"common_dispatch_{index + 1}", "calls", 0.62)

        graph = store.global_graph_networkx(limit=6)

        relations = [edge["relation"] for edge in graph["edges"]]
        self.assertGreaterEqual(relations.count("calls"), 5)
        self.assertGreaterEqual(_largest_component_size(graph), 6)
        self.assertLessEqual(len(graph["edges"]), 6)

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
        self.assertIn("register:GC:GCVM_L2_CNTL", node_by_id)
        register_node = node_by_id["register:GC:GCVM_L2_CNTL"]
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
            ("function:mxgpu:mxgpu/gfx.c:program_l2_cache", "sets_field", "register:GC:GCVM_L2_CNTL"),
            {(edge["src"], edge["relation"], edge["dst"]) for edge in graph["edges"]},
        )
        field_edge = next(edge for edge in graph["edges"] if edge["relation"] == "sets_field")
        self.assertIn("source", field_edge["attr"])
        self.assertIn("ENABLE_L2_CACHE", field_edge["attr"]["fields"])
        self.assertEqual(field_edge["attr"]["resolver_wrappers"], ["REG_SET_FIELD"])

    def test_expand_graph_keeps_mm_prefixed_functions_as_functions_with_field_attr(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        self._add_linux_amdgpu_resolver_profile(store)
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
                "resolver_profile": "linux-amdgpu",
            },
        )

        graph = store.expand_graph_networkx("VML2PF0_VM_L2_PROTECTION_FAULT_CNTL", hops=1)

        node_by_id = {node["id"]: node for node in graph["nodes"]}
        self.assertIn(
            "function:unknown:concept:linux-amdgpu:amd-ip-versioned-functions:mmhub_set_fault_enable_default",
            node_by_id,
        )
        self.assertEqual(
            node_by_id[
                "function:unknown:concept:linux-amdgpu:amd-ip-versioned-functions:mmhub_set_fault_enable_default"
            ]["attr"]["raw_function_names"],
            ["mmhub_v9_4_set_fault_enable_default"],
        )
        self.assertNotIn("register:unknown:9.4:mmhub_v9_4_set_fault_enable_default", node_by_id)
        edge = graph["edges"][0]
        self.assertEqual(edge["relation"], "sets_field")
        self.assertIn("RANGE_PROTECTION_FAULT_ENABLE_DEFAULT", edge["attr"]["fields"])

    def test_global_graph_keeps_smn_prefixed_registers_without_keyword_hints(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.add_edge(
            "program_mp1_flags",
            "smnMP1_FIRMWARE_FLAGS",
            "writes",
            0.97,
            stage="deterministic",
            source="clang_ast",
            path="drivers/gpu/drm/amd/pm/swsmu/smu.c",
            line_start=41,
            line_end=41,
            provenance={
                "extractor": "code_graph",
                "function": "program_mp1_flags",
                "wrapper": "WREG32",
                "corpus_id": "linux-amdgpu",
            },
        )

        graph = store.global_graph_networkx(limit=20)

        node_by_id = {node["id"]: node for node in graph["nodes"]}
        self.assertIn("register:unknown:MP1_FIRMWARE_FLAGS", node_by_id)
        register_node = node_by_id["register:unknown:MP1_FIRMWARE_FLAGS"]
        self.assertEqual(register_node["kind"], "register")
        self.assertEqual(register_node["label"], "MP1_FIRMWARE_FLAGS")
        self.assertIn(
            ("function:linux-amdgpu:drivers/gpu/drm/amd/pm/swsmu/smu.c:program_mp1_flags", "writes", register_node["id"]),
            {(edge["src"], edge["relation"], edge["dst"]) for edge in graph["edges"]},
        )

    def test_global_graph_does_not_promote_generic_reg_words_to_register_nodes(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.add_edge("REG_SET", "register", "writes", 0.92, stage="semantic", source="ollama")
        store.add_edge(
            "program_queue",
            "registers",
            "writes",
            0.91,
            stage="semantic",
            source="ollama",
            path="drivers/gpu/drm/amd/amdgpu/gfx.c",
            provenance={"function": "program_queue", "corpus_id": "linux-amdgpu"},
        )
        store.add_edge("program_cache", "regGCVM_L2_CNTL", "writes", 0.97, stage="deterministic")

        graph = store.global_graph_networkx(limit=20)

        node_labels = {node["label"] for node in graph["nodes"]}
        edge_labels = {(edge["src"], edge["relation"], edge["dst"]) for edge in graph["edges"]}
        self.assertNotIn("REG_SET", node_labels)
        self.assertNotIn("register", node_labels)
        self.assertNotIn("registers", node_labels)
        self.assertIn("GCVM_L2_CNTL", node_labels)
        self.assertTrue(any("GCVM_L2_CNTL" in dst for _src, _relation, dst in edge_labels))

    def test_global_graph_edge_attr_preserves_semantic_provider_provenance(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        settings = {"edge": {"provider": "ollama", "model": "gemma4:e4b"}}
        store.save_provider_settings(settings)
        index_job = store.start_job("index", "indexed corpus")
        store.finish_job(index_job, "indexed", "indexed corpus")
        graph_job = store.start_job("graph_rebuild", "rebuilt deterministic graph")
        store.finish_job(graph_job, "rebuilt", "rebuilt deterministic graph")
        doc_node_job = store.start_job(
            "doc_nodes_batch",
            "generated doc-node provenance fixture",
            metadata={"provider_settings": settings},
        )
        store.finish_job(doc_node_job, "generated", "generated doc-node provenance fixture")
        store.add_edge(
            "docs/guide.md#box-cache-policy",
            "GCVM_L2_CNTL",
            "documents_register",
            0.91,
            stage="semantic",
            source="ollama",
            path="docs/guide.md",
            provenance={
                "box_node_id": "docs/guide.md#box-cache-policy",
                "extractor": "doc_nodes",
                "provider": "ollama",
                "model": "gemma4:e4b",
                "job_id": doc_node_job,
                "corpus_id": "docs",
            },
        )

        graph = store.global_graph_networkx(limit=20)

        edge = next(edge for edge in graph["edges"] if edge["relation"] == "documents")
        self.assertEqual(edge["stage"], "semantic")
        self.assertEqual(edge["sources"], ["ollama"])
        self.assertEqual(edge["attr"]["providers"], ["ollama"])
        self.assertEqual(edge["attr"]["models"], ["gemma4:e4b"])
        self.assertEqual(edge["attr"]["job_ids"], [str(doc_node_job)])

    def test_runtime_graph_filters_stale_semantic_edges_after_graph_rebuild(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        settings = {"edge": {"provider": "ollama", "model": "gemma4:e4b"}}
        store.save_provider_settings(settings)
        index_job = store.start_job("index", "indexed corpus")
        store.finish_job(index_job, "indexed", "indexed corpus")
        semantic_job = store.start_job(
            "semantic_edges_batch",
            "generated semantic edges",
            metadata={"provider_settings": settings},
        )
        store.finish_job(semantic_job, "generated", "generated semantic edges")
        store.add_edge(
            "docs/guide.md#programming-local-registers",
            "GCVM_L2_CNTL",
            "documents_register",
            0.91,
            stage="semantic",
            source="ollama",
            provenance={
                "extractor": "semantic_edges",
                "provider": "ollama",
                "model": "gemma4:e4b",
                "job_id": semantic_job,
            },
        )
        graph_job = store.start_job("graph_rebuild", "rebuilt deterministic graph")
        store.finish_job(graph_job, "rebuilt", "rebuilt deterministic graph")
        self._add_function_register_edge(
            store,
            "program_cache",
            "GCVM_L2_CNTL",
            path="drivers/gpu/drm/amd/amdgpu/gfx.c",
        )

        global_graph = store.global_graph_networkx(limit=20)
        expanded_graph = store.expand_graph_networkx("GCVM_L2_CNTL", hops=1)

        self.assertFalse(any(edge["stage"] == "semantic" for edge in global_graph["edges"]))
        self.assertFalse(any(edge["stage"] == "semantic" for edge in expanded_graph["edges"]))
        self.assertTrue(any(edge["relation"] == "writes" for edge in global_graph["edges"]))

    def test_runtime_graph_keeps_fresh_semantic_edges_after_graph_rebuild(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        settings = {"edge": {"provider": "ollama", "model": "gemma4:e4b"}}
        store.save_provider_settings(settings)
        index_job = store.start_job("index", "indexed corpus")
        store.finish_job(index_job, "indexed", "indexed corpus")
        graph_job = store.start_job("graph_rebuild", "rebuilt deterministic graph")
        store.finish_job(graph_job, "rebuilt", "rebuilt deterministic graph")
        semantic_job = store.start_job(
            "semantic_edges_batch",
            "generated fresh semantic edges",
            metadata={"provider_settings": settings},
        )
        store.finish_job(semantic_job, "generated", "generated fresh semantic edges")
        store.add_edge(
            "docs/guide.md#programming-local-registers",
            "GCVM_L2_CNTL",
            "documents_register",
            0.91,
            stage="semantic",
            source="ollama",
            provenance={
                "extractor": "semantic_edges",
                "provider": "ollama",
                "model": "gemma4:e4b",
                "job_id": semantic_job,
            },
        )

        graph = store.global_graph_networkx(limit=20)

        self.assertIn("semantic", {edge["stage"] for edge in graph["edges"]})
        self.assertIn(
            ("docs/guide.md#programming-local-registers", "documents", "register:GC:GCVM_L2_CNTL"),
            {(edge["src"], edge["relation"], edge["dst"]) for edge in graph["edges"]},
        )

    def test_runtime_graph_keeps_fresh_doc_node_edges_after_graph_rebuild(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        settings = {"edge": {"provider": "ollama", "model": "gemma4:e4b"}}
        store.save_provider_settings(settings)
        index_job = store.start_job("index", "indexed corpus")
        store.finish_job(index_job, "indexed", "indexed corpus")
        graph_job = store.start_job("graph_rebuild", "rebuilt deterministic graph")
        store.finish_job(graph_job, "rebuilt", "rebuilt deterministic graph")
        doc_node_job = store.start_job(
            "doc_nodes_batch",
            "generated fresh doc-node edges",
            metadata={"provider_settings": settings},
        )
        store.finish_job(doc_node_job, "generated", "generated fresh doc-node edges")
        store.add_edge(
            "docs/guide.md#box-cache-policy",
            "GCVM_L2_CNTL",
            "documents_register",
            0.91,
            stage="semantic",
            source="ollama",
            provenance={
                "extractor": "doc_nodes",
                "provider": "ollama",
                "model": "gemma4:e4b",
                "job_id": doc_node_job,
                "box_node_id": "docs/guide.md#box-cache-policy",
            },
        )

        graph = store.global_graph_networkx(limit=20)

        self.assertIn("semantic", {edge["stage"] for edge in graph["edges"]})
        self.assertIn(
            ("docs/guide.md#box-cache-policy", "documents", "register:GC:GCVM_L2_CNTL"),
            {(edge["src"], edge["relation"], edge["dst"]) for edge in graph["edges"]},
        )

    def test_runtime_graph_filters_doc_node_edges_from_semantic_edge_jobs(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        settings = {"edge": {"provider": "ollama", "model": "gemma4:e4b"}}
        store.save_provider_settings(settings)
        index_job = store.start_job("index", "indexed corpus")
        store.finish_job(index_job, "indexed", "indexed corpus")
        graph_job = store.start_job("graph_rebuild", "rebuilt deterministic graph")
        store.finish_job(graph_job, "rebuilt", "rebuilt deterministic graph")
        semantic_job = store.start_job(
            "semantic_edges_batch",
            "generated semantic edges",
            metadata={"provider_settings": settings},
        )
        store.finish_job(semantic_job, "generated", "generated semantic edges")
        store.add_edge(
            "docs/guide.md#box-cache-policy",
            "GCVM_L2_CNTL",
            "documents_register",
            0.91,
            stage="semantic",
            source="ollama",
            provenance={
                "extractor": "doc_nodes",
                "provider": "ollama",
                "model": "gemma4:e4b",
                "job_id": semantic_job,
                "box_node_id": "docs/guide.md#box-cache-policy",
            },
        )

        graph = store.global_graph_networkx(limit=20)

        self.assertEqual(graph["edges"], [])
        self.assertEqual(graph["nodes"], [])

    def test_runtime_graph_filters_semantic_edges_from_doc_node_jobs(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        settings = {"edge": {"provider": "ollama", "model": "gemma4:e4b"}}
        store.save_provider_settings(settings)
        index_job = store.start_job("index", "indexed corpus")
        store.finish_job(index_job, "indexed", "indexed corpus")
        graph_job = store.start_job("graph_rebuild", "rebuilt deterministic graph")
        store.finish_job(graph_job, "rebuilt", "rebuilt deterministic graph")
        doc_node_job = store.start_job(
            "doc_nodes_batch",
            "generated doc-node edges",
            metadata={"provider_settings": settings},
        )
        store.finish_job(doc_node_job, "generated", "generated doc-node edges")
        store.add_edge(
            "docs/guide.md#programming-local-registers",
            "GCVM_L2_CNTL",
            "documents_register",
            0.91,
            stage="semantic",
            source="ollama",
            provenance={
                "extractor": "semantic_edges",
                "provider": "ollama",
                "model": "gemma4:e4b",
                "job_id": doc_node_job,
            },
        )

        graph = store.global_graph_networkx(limit=20)

        self.assertEqual(graph["edges"], [])
        self.assertEqual(graph["nodes"], [])

    def test_runtime_graph_filters_semantic_edges_from_previous_provider_settings(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        current_settings = {"edge": {"provider": "ollama", "model": "gemma4:e4b"}}
        stale_settings = {"edge": {"provider": "ollama", "model": "qwen3.5:4b"}}
        store.save_provider_settings(current_settings)
        semantic_job = store.start_job(
            "semantic_edges_batch",
            "generated stale-provider semantic edges",
            metadata={"provider_settings": stale_settings},
        )
        store.finish_job(semantic_job, "generated", "generated stale-provider semantic edges")
        store.add_edge(
            "docs/guide.md#old-provider",
            "GCVM_L2_CNTL",
            "documents_register",
            0.91,
            stage="semantic",
            source="ollama",
            provenance={
                "extractor": "semantic_edges",
                "provider": "ollama",
                "model": "qwen3.5:4b",
                "job_id": semantic_job,
            },
        )

        graph = store.global_graph_networkx(limit=20)

        self.assertEqual(graph["edges"], [])
        self.assertEqual(graph["nodes"], [])

    def test_runtime_graph_filters_semantic_edge_extractor_rows_without_job_provenance(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.save_provider_settings({"edge": {"provider": "ollama", "model": "gemma4:e4b"}})
        store.add_edge(
            "docs/guide.md#unproven-provider-edge",
            "GCVM_L2_CNTL",
            "documents_register",
            0.91,
            stage="semantic",
            source="ollama",
            provenance={
                "extractor": "semantic_edges",
                "provider": "ollama",
                "model": "gemma4:e4b",
            },
        )

        graph = store.global_graph_networkx(limit=20)

        self.assertEqual(graph["edges"], [])
        self.assertEqual(graph["nodes"], [])

    def test_runtime_graph_filters_doc_node_extractor_rows_without_job_provenance(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.save_provider_settings({"edge": {"provider": "ollama", "model": "gemma4:e4b"}})
        store.add_edge(
            "docs/guide.md#unproven-doc-box",
            "GCVM_L2_CNTL",
            "documents_register",
            0.91,
            stage="semantic",
            source="ollama",
            provenance={
                "extractor": "doc_nodes",
                "provider": "ollama",
                "model": "gemma4:e4b",
                "box_node_id": "docs/guide.md#unproven-doc-box",
            },
        )

        graph = store.global_graph_networkx(limit=20)

        self.assertEqual(graph["edges"], [])
        self.assertEqual(graph["nodes"], [])

    def test_global_graph_normalizes_edge_relation_enum(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        settings = {"edge": {"provider": "ollama", "model": "gemma4:e4b"}}
        store.save_provider_settings(settings)
        index_job = store.start_job("index", "indexed corpus")
        store.finish_job(index_job, "indexed", "indexed corpus")
        graph_job = store.start_job("graph_rebuild", "rebuilt deterministic graph")
        store.finish_job(graph_job, "rebuilt", "rebuilt deterministic graph")
        doc_node_job = store.start_job(
            "doc_nodes_batch",
            "generated doc-node relation fixtures",
            metadata={"provider_settings": settings},
        )
        store.finish_job(doc_node_job, "generated", "generated doc-node relation fixtures")
        store.add_edge(
            "docs/guide.md#overview",
            "docs/guide.md#box-cache-policy",
            "contains_box",
            0.9,
            stage="semantic",
            source="ollama",
            path="docs/guide.md",
            provenance={
                "extractor": "doc_nodes",
                "provider": "ollama",
                "model": "gemma4:e4b",
                "job_id": doc_node_job,
                "box_node_id": "docs/guide.md#box-cache-policy",
            },
        )
        store.add_edge(
            "docs/guide.md#box-cache-policy",
            "GCVM_L2_CNTL",
            "documents_register",
            0.88,
            stage="semantic",
            source="ollama",
            path="docs/guide.md",
            provenance={
                "extractor": "doc_nodes",
                "provider": "ollama",
                "model": "gemma4:e4b",
                "job_id": doc_node_job,
                "box_node_id": "docs/guide.md#box-cache-policy",
                "ip": "GC",
                "ip_version": "11.0",
            },
        )
        store.add_edge(
            "docs/guide.md#box-cache-policy",
            "GCVM_L2_CNTL",
            "explains_runtime_implication",
            0.77,
            stage="semantic",
            source="ollama",
            path="docs/guide.md",
            provenance={
                "extractor": "doc_nodes",
                "provider": "ollama",
                "model": "gemma4:e4b",
                "job_id": doc_node_job,
                "box_node_id": "docs/guide.md#box-cache-policy",
                "ip": "GC",
                "ip_version": "11.0",
            },
        )

        graph = store.global_graph_networkx(limit=20)

        relation_by_original = {
            edge["attr"].get("original_relation", edge["relation"]): edge["relation"] for edge in graph["edges"]
        }
        self.assertEqual(relation_by_original["contains_box"], "contains")
        self.assertEqual(relation_by_original["documents_register"], "documents")
        self.assertEqual(relation_by_original["explains_runtime_implication"], "relates_to")

    def test_global_graph_relation_normalization_uses_shared_schema(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.add_edge(
            "program_schema_probe",
            "SCHEMA_PROBE_CNTL",
            "schema_probe",
            0.88,
            stage="semantic",
            source="ollama",
            path="src/schema_probe.c",
            provenance={"function": "program_schema_probe", "path": "src/schema_probe.c"},
        )

        with patch("asip.storage.normalize_product_relation", return_value="configures") as normalize:
            graph = store.global_graph_networkx(limit=20)

        normalize.assert_any_call("schema_probe")
        self.assertEqual({edge["relation"] for edge in graph["edges"]}, {"configures"})
        self.assertTrue({edge["relation"] for edge in graph["edges"]}.issubset(ALLOWED_PRODUCT_RELATIONS))

    def test_evidence_macro_symbols_do_not_become_register_product_nodes(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        semantic_job = store.start_job(
            "semantic_edges_batch",
            "semantic evidence macro fixture",
            metadata={"provider_settings": {"edge": {"provider": "ollama", "model": "gemma4:e4b"}}},
        )
        store.finish_job(semantic_job, "generated", "generated fixture semantic edges")
        store.upsert_corpus(
            "linux-amdgpu",
            "https://github.com/torvalds/linux",
            "/tmp/linux",
            ["**/*.c"],
            status="indexed",
            file_count=1,
        )
        document_id = store.add_document("linux-amdgpu", "code", "drivers/gpu/drm/amd/amdgpu/macro.c")
        chunk_id = store.add_chunk(
            document_id,
            "void init_macro(void) {\n    MACRO_HELPER();\n}",
            line_start=10,
            line_end=12,
        )
        store.add_evidence(
            chunk_id,
            "linux-amdgpu",
            "code",
            "https://github.com/torvalds/linux",
            "drivers/gpu/drm/amd/amdgpu/macro.c",
            "MACRO_HELPER",
            "macro",
            "mention",
            0.93,
            "MACRO_HELPER();",
            "",
            line_start=11,
            line_end=11,
        )

        graph = store.global_graph_networkx(limit=20, include_evidence_derived=True, evidence_row_cap=10)

        node_labels = {str(node["label"]) for node in graph["nodes"]}
        node_ids = {str(node["id"]) for node in graph["nodes"]}
        edge_endpoints = {endpoint for edge in graph["edges"] for endpoint in (edge["src"], edge["dst"])}
        self.assertNotIn("MACRO_HELPER", node_labels)
        self.assertFalse(any("MACRO_HELPER" in node_id for node_id in node_ids))
        self.assertFalse(any("MACRO_HELPER" in endpoint for endpoint in edge_endpoints))

    def test_semantic_code_edges_do_not_promote_local_variables_to_function_nodes(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        semantic_job = store.start_job(
            "semantic_edges_batch",
            "semantic code edge fixture",
            metadata={"provider_settings": {"edge": {"provider": "ollama", "model": "gemma4:e4b"}}},
        )
        store.finish_job(semantic_job, "generated", "generated fixture semantic edges")
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
            provenance={"extractor": "semantic_edges", "provider": "ollama", "model": "gemma4:e4b", "job_id": semantic_job},
        )
        store.add_edge(
            "real_handler",
            "ih_ring_entry",
            "reads",
            0.9,
            stage="semantic",
            source="ollama",
            provenance={"extractor": "semantic_edges", "provider": "ollama", "model": "gemma4:e4b", "job_id": semantic_job},
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

    def test_register_nodes_merge_by_symbol_and_ip_with_ip_versions_as_attrs(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        self._add_linux_amdgpu_resolver_profile(store)
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
                    **({"resolver_profile": "linux-amdgpu"} if corpus_id == "linux-amdgpu" else {}),
                },
            )
        for corpus_id, repo, function_name, path in [
            (
                "mxgpu",
                "https://github.com/amd/MxGPU-Virtualization",
                "mxgpu_irq_init",
                "libgv/core/hw/AI/mi200/mi200_irqmgr.c",
            ),
            (
                "linux-amdgpu",
                "https://github.com/torvalds/linux",
                "linux_irq_init",
                "drivers/gpu/drm/amd/amdgpu/cik_ih.c",
            ),
        ]:
            store.add_edge(
                function_name,
                "IH_RB_CNTL",
                "writes",
                0.91,
                stage="deterministic",
                source="clang_ast",
                path=path,
                line_start=8,
                provenance={
                    "extractor": "code_graph",
                    "function": function_name,
                    "ip": "IH",
                    "corpus_id": corpus_id,
                    "repo": repo,
                },
            )

        graph = store.global_graph_networkx(limit=20)

        registers = [node for node in graph["nodes"] if node["kind"] == "register"]
        register_ids = {node["id"] for node in registers}
        edge_triples = {(edge["src"], edge["relation"], edge["dst"]) for edge in graph["edges"]}
        self.assertEqual(
            register_ids,
            {"register:GC:GCVM_L2_CNTL", "register:IH:IH_RB_CNTL"},
        )
        self.assertIn(
            ("function:mxgpu:mxgpu/gfx.c:program_l2_cache", "writes", "register:GC:GCVM_L2_CNTL"),
            edge_triples,
        )
        self.assertIn(
            (
                "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gmc_init",
                "writes",
                "register:GC:GCVM_L2_CNTL",
            ),
            edge_triples,
        )
        concept_node = next(
            node
            for node in graph["nodes"]
            if node["id"] == "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gmc_init"
        )
        self.assertCountEqual(concept_node["attr"]["raw_function_names"], ["gmc_v11_0_init", "gmc_v12_0_init"])
        merged_node = next(node for node in registers if node["id"] == "register:GC:GCVM_L2_CNTL")
        self.assertEqual(merged_node["attr"]["ip_versions"], ["11.0", "12.0"])
        merged_sources = merged_node["attr"]["source"]
        self.assertEqual({source["corpus_id"] for source in merged_sources}, {"mxgpu", "linux-amdgpu"})
        self.assertEqual({source["ip_version"] for source in merged_sources}, {"11.0", "12.0"})
        unknown_sources = next(node for node in registers if node["id"] == "register:IH:IH_RB_CNTL")["attr"]["source"]
        self.assertEqual({source["corpus_id"] for source in unknown_sources}, {"mxgpu", "linux-amdgpu"})

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

    def test_add_embeddings_upserts_multiple_rows_in_one_commit(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        document_id = store.add_document("docs", "doc", "Documentation/gpu/amdgpu.rst")
        first_chunk = store.add_chunk(document_id, "GCVM_L2_CNTL enables L2 cache", 10, 10)
        second_chunk = store.add_chunk(document_id, "SDMA queue ring buffer control", 20, 20)

        store.add_embeddings(
            [
                {
                    "chunk_id": first_chunk,
                    "provider": "ollama",
                    "model": "nomic-embed-text",
                    "vector": [1.0, 0.0],
                    "metadata": {"source": "provider"},
                },
                {
                    "chunk_id": second_chunk,
                    "provider": "ollama",
                    "model": "nomic-embed-text",
                    "vector": [0.0, 1.0],
                    "metadata": {"source": "provider"},
                },
            ]
        )
        store.add_embeddings(
            [
                {
                    "chunk_id": first_chunk,
                    "provider": "ollama",
                    "model": "nomic-embed-text",
                    "vector": [0.5, 0.5],
                    "metadata": {"source": "provider", "updated": True},
                }
            ]
        )

        rows = {
            chunk_id: (json.loads(vector_json), json.loads(metadata_json))
            for chunk_id, vector_json, metadata_json in store.con.execute(
                "select chunk_id, vector_json, metadata_json from embeddings"
            )
        }
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[first_chunk][0], [0.5, 0.5])
        self.assertTrue(rows[first_chunk][1]["updated"])
        self.assertEqual(rows[second_chunk][0], [0.0, 1.0])

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

    def test_search_vector_uses_sqlite_vec_when_runtime_supports_extensions(self):
        if importlib.util.find_spec("sqlite_vec") is None:
            self.skipTest("sqlite_vec package is not installed in this Python runtime")
        con = sqlite3.connect(":memory:")
        if not hasattr(con, "enable_load_extension"):
            self.skipTest("this sqlite3 build cannot load extensions")
        con.close()

        store = AsipStore.connect(":memory:")
        store.migrate()
        document_id = store.add_document("docs", "doc", "Documentation/gpu/amdgpu.rst")
        gc_chunk = store.add_chunk(document_id, "GCVM_L2_CNTL enables L2 cache", 10, 10)
        sdma_chunk = store.add_chunk(document_id, "SDMA queue ring buffer control", 20, 20)
        store.add_embedding(gc_chunk, provider="ollama", model="nomic-embed-text", vector=[1.0, 0.0, 0.0])
        store.add_embedding(sdma_chunk, provider="ollama", model="nomic-embed-text", vector=[0.0, 1.0, 0.0])

        matches = store.search_vector([0.9, 0.1, 0.0], limit=1)

        self.assertEqual(matches[0]["chunk_id"], gc_chunk)
        self.assertEqual(matches[0]["retrieval_runtime"], "sqlite-vec")
        self.assertGreater(matches[0]["score"], 0.9)
        self.assertIn("distance", matches[0])


def _largest_component_size(graph):
    adjacency = {}
    for edge in graph["edges"]:
        src = edge["src"]
        dst = edge["dst"]
        adjacency.setdefault(src, set()).add(dst)
        adjacency.setdefault(dst, set()).add(src)
    node_ids = {node["id"] for node in graph["nodes"]}
    seen = set()
    largest = 0
    for node_id in node_ids:
        if node_id in seen:
            continue
        stack = [node_id]
        seen.add(node_id)
        size = 0
        while stack:
            current = stack.pop()
            size += 1
            for neighbor in adjacency.get(current, ()):
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        largest = max(largest, size)
    return largest


if __name__ == "__main__":
    unittest.main()
