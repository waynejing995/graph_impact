import json
import tempfile
import unittest
from pathlib import Path

from asip.code_graph import build_deterministic_code_graph
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


if __name__ == "__main__":
    unittest.main()
