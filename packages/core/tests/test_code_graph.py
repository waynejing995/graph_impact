import json
import tempfile
import unittest
from pathlib import Path

from asip.code_graph import _function_spans_from_text, build_deterministic_code_graph
from asip.resolver_profiles import ResolverProfile, WrapperRule


class DeterministicCodeGraphTests(unittest.TestCase):
    def test_clang_stage_extracts_function_wrapper_and_register_edges(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "#define ASIC_REG_OFFSET(x) mm##x",
                        "#define SOC15_REG_OFFSET(ip, inst, reg) ASIC_REG_OFFSET(reg)",
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
            profile = ResolverProfile(
                id="test-amd",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={
                    "RREG32": WrapperRule(symbol_arg=0, access="read"),
                    "WREG32": WrapperRule(symbol_arg=0, access="write"),
                    "REG_SET_FIELD": WrapperRule(symbol_args=(1, 2), access="field_set"),
                    "SOC15_REG_OFFSET": WrapperRule(symbol_arg=2, access="address"),
                },
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            self.assertEqual(graph.stage, "deterministic")
            self.assertIn(graph.analysis_mode, {"clang_ast", "clang_preprocess"})
            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            graph_node_ids = {edge.src for edge in graph.edges} | {edge.dst for edge in graph.edges}
            self.assertIn(("program_local_register", "reads", "GCVM_L2_CNTL"), edge_triples)
            self.assertIn(("program_local_register", "writes", "GCVM_L2_CNTL"), edge_triples)
            self.assertIn(("program_local_register", "sets_field", "GCVM_L2_CNTL"), edge_triples)
            field_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("program_local_register", "sets_field", "GCVM_L2_CNTL")
            )
            self.assertEqual(field_edge.provenance.get("field"), "ENABLE_L2_CACHE")
            self.assertNotIn("RREG32", graph_node_ids)
            self.assertNotIn("WREG32", graph_node_ids)
            self.assertNotIn("REG_SET_FIELD", graph_node_ids)
            self.assertNotIn("SOC15_REG_OFFSET", graph_node_ids)
            self.assertNotIn("ENABLE_L2_CACHE", graph_node_ids)
            self.assertTrue(all(edge.stage == "deterministic" for edge in graph.edges))
            self.assertTrue(all(edge.provenance.get("extractor") == "code_graph" for edge in graph.edges))

    def test_compile_commands_preprocess_expands_project_macro_wrappers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            include = root / "include"
            include.mkdir()
            (include / "regops.h").write_text(
                "#define WRITE_GCVM(symbol) WREG32(reg##symbol, 1)\n",
                encoding="utf-8",
            )
            source = root / "gfx.c"
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
            (root / "compile_commands.json").write_text(
                json.dumps(
                    [
                        {
                            "directory": str(root),
                            "command": f"clang -I include -DASIP_TEST_BUILD -c {source}",
                            "file": str(source),
                        }
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="compile-db-amd",
                language="cpp",
                symbol_prefixes=["reg", "mm"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("program_from_project_macro", "writes", "GCVM_L2_CNTL"), edge_triples)
            macro_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("program_from_project_macro", "writes", "GCVM_L2_CNTL")
            )
            self.assertEqual(macro_edge.source, "clang_preprocess")
            self.assertEqual(macro_edge.line_start, 3)
            self.assertEqual(macro_edge.provenance.get("wrapper"), "WREG32")
            self.assertEqual(macro_edge.provenance.get("analysis_mode"), "clang_preprocess")

    def test_field_shift_macro_links_function_to_register_with_field_provenance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "static unsigned int read_l2_cache_shift(void) {",
                        "  return REG_FIELD_SHIFT(GCVM_L2_CNTL, ENABLE_L2_CACHE);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-field-shift",
                language="cpp",
                symbol_prefixes=["reg", "mm", "smn"],
                wrappers={"REG_FIELD_SHIFT": WrapperRule(symbol_args=(0, 1), access="field_shift")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            graph_node_ids = {edge.src for edge in graph.edges} | {edge.dst for edge in graph.edges}
            self.assertIn(("read_l2_cache_shift", "reads", "GCVM_L2_CNTL"), edge_triples)
            self.assertNotIn("ENABLE_L2_CACHE", graph_node_ids)
            field_edge = next(edge for edge in graph.edges if edge.dst == "GCVM_L2_CNTL")
            self.assertEqual(field_edge.provenance.get("field"), "ENABLE_L2_CACHE")

    def test_stage1_links_vtable_slot_calls_to_callbacks_and_common_helpers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "static void program_gcvm_l2(void) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "}",
                        "static int gfx_v11_0_hw_init(void *adev) {",
                        "  program_gcvm_l2();",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = gfx_v11_0_hw_init,",
                        "};",
                        "int amdgpu_common_hw_init(struct amd_ip_block *block) {",
                        "  return block->version->funcs->hw_init(block);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-callbacks",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("program_gcvm_l2", "writes", "GCVM_L2_CNTL"), edge_triples)
            self.assertIn(("gfx_v11_0_hw_init", "calls", "program_gcvm_l2"), edge_triples)
            self.assertIn(("amdgpu_common_hw_init", "calls", "gfx_v11_0_hw_init"), edge_triples)
            callback_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("amdgpu_common_hw_init", "calls", "gfx_v11_0_hw_init")
            )
            self.assertEqual(callback_edge.provenance.get("call_kind"), "vtable_callback")
            self.assertEqual(callback_edge.provenance.get("slot"), "hw_init")
            self.assertEqual(callback_edge.provenance.get("callee_line"), 4)
            self.assertEqual(callback_edge.provenance.get("callback_line"), 9)
            graph_node_ids = {edge.src for edge in graph.edges} | {edge.dst for edge in graph.edges}
            self.assertNotIn("hw_init", graph_node_ids)
            self.assertNotIn("gfx_v11_0_ip_funcs", graph_node_ids)

    def test_text_fallback_does_not_promote_control_keywords_to_functions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "fallback.c"
            source.write_text(
                "\n".join(
                    [
                        "static void helper(void) {",
                        "}",
                        "static void outer(int value) {",
                        "  if (value == 1) {",
                        "    helper();",
                        "  } else",
                        "  if (value == 2) {",
                        "    helper();",
                        "  }",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(source)

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("outer", "calls", "helper"), edge_triples)
            self.assertNotIn(("if", "calls", "helper"), edge_triples)
            graph_node_ids = {edge.src for edge in graph.edges} | {edge.dst for edge in graph.edges}
            self.assertNotIn("if", graph_node_ids)

    def test_text_span_parser_does_not_promote_control_keywords_to_functions(self):
        source_text = "\n".join(
            [
                "static void outer(int value) {",
                "  if (value == 1) {",
                "    helper();",
                "  }",
                "  else if (value == 2) {",
                "    helper();",
                "  }",
                "}",
            ]
        )

        spans = _function_spans_from_text(source_text)

        self.assertNotIn("if", {span.name for span in spans})

    def test_stage1_generic_slot_call_does_not_connect_unbounded_callbacks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_v11_0_hw_init(void *adev) {",
                        "  return 0;",
                        "}",
                        "static int sdma_v5_0_hw_init(void *adev) {",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = gfx_v11_0_hw_init,",
                        "};",
                        "static const struct amd_ip_funcs sdma_v5_0_ip_funcs = {",
                        "  .hw_init = sdma_v5_0_hw_init,",
                        "};",
                        "int amdgpu_common_hw_init(struct amd_ip_funcs *funcs) {",
                        "  return funcs->hw_init(0);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(source)

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertNotIn(("amdgpu_common_hw_init", "calls", "gfx_v11_0_hw_init"), edge_triples)
            self.assertNotIn(("amdgpu_common_hw_init", "calls", "sdma_v5_0_hw_init"), edge_triples)

    def test_stage1_slot_call_line_uses_call_site_not_function_name(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_v11_0_hw_init(void *adev) {",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = gfx_v11_0_hw_init,",
                        "};",
                        "int common_hw_init(void) {",
                        "  return gfx_v11_0_ip_funcs.hw_init(0);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(source)

            callback_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("common_hw_init", "calls", "gfx_v11_0_hw_init")
            )
            self.assertEqual(callback_edge.line_start, 8)


if __name__ == "__main__":
    unittest.main()
