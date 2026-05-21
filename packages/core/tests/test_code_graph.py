import json
import tempfile
import unittest
from pathlib import Path

from asip.code_graph import CodeGraphFunctionLocation, _function_spans_from_text, build_deterministic_code_graph
from asip.resolver_profiles import GraphNormalizationConfig, ResolverProfile, WrapperRule


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
            self.assertIn(graph.analysis_mode, {"clang_text_spans", "clang_preprocess"})
            self.assertNotEqual(graph.analysis_mode, "clang_ast")
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

    def test_resolver_access_relation_map_controls_deterministic_graph_relation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "doorbell.c"
            source.write_text(
                "\n".join(
                    [
                        "static void ring_doorbell(void) {",
                        "  DOORBELL_WRITE(mmCP_HQD_PQ_DOORBELL_CONTROL, 1);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="custom-doorbell",
                language="cpp",
                symbol_prefixes=["mm"],
                wrappers={"DOORBELL_WRITE": WrapperRule(symbol_arg=0, access="doorbell_write")},
                graph=GraphNormalizationConfig(access_relation_map={"doorbell_write": "writes"}),
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge = next(
                edge
                for edge in graph.edges
                if edge.src == "ring_doorbell" and edge.dst == "CP_HQD_PQ_DOORBELL_CONTROL"
            )
            self.assertEqual(edge.relation, "writes")
            self.assertEqual(edge.provenance.get("access"), "doorbell_write")
            self.assertEqual(edge.provenance.get("mapped_relation"), "writes")
            self.assertEqual(edge.provenance.get("resolver_profile"), "custom-doorbell")

    def test_stage1_ignores_direct_and_slot_calls_in_comments_strings_and_disabled_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "struct amdgpu_ip_funcs { int (*hw_init)(void *adev); };",
                        "static int real_helper(void *adev) { return 0; }",
                        "static int fake_helper(void *adev) { return 0; }",
                        "static const struct amdgpu_ip_funcs gfx_funcs = {",
                        "  .hw_init = fake_helper,",
                        "};",
                        "static int caller(void *adev) {",
                        "  /* fake_helper(adev); */",
                        "  const char *text = \"fake_helper(adev); adev->gfx.funcs->hw_init(adev);\";",
                        "#if 0",
                        "  fake_helper(adev);",
                        "  adev->gfx.funcs->hw_init(adev);",
                        "#endif",
                        "  return real_helper(adev);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[])

            call_edges = {(edge.src, edge.relation, edge.dst) for edge in graph.edges if edge.relation == "calls"}
            self.assertIn(("caller", "calls", "real_helper"), call_edges)
            self.assertNotIn(("caller", "calls", "fake_helper"), call_edges)

    def test_stage1_ignores_function_spans_inside_disabled_preprocessor_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "static int helper(void *adev) { return 0; }",
                        "#if 0",
                        "static int disabled_caller(void *adev) {",
                        "  return helper(adev);",
                        "}",
                        "#endif",
                        "static int active_caller(void *adev) {",
                        "  return helper(adev);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[])

            call_edges = {(edge.src, edge.relation, edge.dst) for edge in graph.edges if edge.relation == "calls"}
            self.assertIn(("active_caller", "calls", "helper"), call_edges)
            self.assertNotIn(("disabled_caller", "calls", "helper"), call_edges)

    def test_stage1_treats_undefined_config_preprocessor_branches_as_disabled(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "static int helper(void *adev) { return 0; }",
                        "static int disabled_helper(void *adev) { return 0; }",
                        "#ifdef CONFIG_ASIP_DISABLED",
                        "static int disabled_ifdef_caller(void *adev) {",
                        "  return disabled_helper(adev);",
                        "}",
                        "#endif",
                        "#if defined(CONFIG_ASIP_DISABLED)",
                        "static int disabled_defined_caller(void *adev) {",
                        "  return disabled_helper(adev);",
                        "}",
                        "#endif",
                        "#if IS_ENABLED(CONFIG_ASIP_DISABLED)",
                        "static int disabled_is_enabled_caller(void *adev) {",
                        "  return disabled_helper(adev);",
                        "}",
                        "#endif",
                        "#if defined(CONFIG_ASIP_DISABLED) || IS_ENABLED(CONFIG_ASIP_OTHER_DISABLED)",
                        "static int disabled_compound_or_caller(void *adev) {",
                        "  return disabled_helper(adev);",
                        "}",
                        "#endif",
                        "#ifndef CONFIG_ASIP_DISABLED",
                        "static int active_ifndef_caller(void *adev) {",
                        "  return helper(adev);",
                        "}",
                        "#endif",
                        "#if !defined(CONFIG_ASIP_DISABLED)",
                        "static int active_not_defined_caller(void *adev) {",
                        "  return helper(adev);",
                        "}",
                        "#endif",
                        "#if !defined(CONFIG_ASIP_DISABLED) && !IS_ENABLED(CONFIG_ASIP_OTHER_DISABLED)",
                        "static int active_compound_negated_caller(void *adev) {",
                        "  return helper(adev);",
                        "}",
                        "#endif",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[])

            call_edges = {(edge.src, edge.relation, edge.dst) for edge in graph.edges if edge.relation == "calls"}
            self.assertIn(("active_ifndef_caller", "calls", "helper"), call_edges)
            self.assertIn(("active_not_defined_caller", "calls", "helper"), call_edges)
            self.assertIn(("active_compound_negated_caller", "calls", "helper"), call_edges)
            self.assertNotIn(("disabled_ifdef_caller", "calls", "disabled_helper"), call_edges)
            self.assertNotIn(("disabled_defined_caller", "calls", "disabled_helper"), call_edges)
            self.assertNotIn(("disabled_is_enabled_caller", "calls", "disabled_helper"), call_edges)
            self.assertNotIn(("disabled_compound_or_caller", "calls", "disabled_helper"), call_edges)

    def test_stage1_honors_compile_defined_config_branches_for_callback_initializers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "struct amdgpu_ip_funcs { int (*hw_init)(void *adev); };",
                        "#ifdef CONFIG_ASIP_ENABLED",
                        "static int enabled_hw_init(void *adev) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amdgpu_ip_funcs enabled_funcs = {",
                        "  .hw_init = enabled_hw_init,",
                        "};",
                        "static int enabled_direct_caller(void *adev) {",
                        "  return enabled_hw_init(adev);",
                        "}",
                        "#endif",
                        "int common_hw_init(struct amdgpu_ip_funcs *funcs) {",
                        "  return funcs->hw_init(0);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-compile-defined-config",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(
                source,
                source_root=root,
                resolver_profiles=[profile],
                clang_args=["-DCONFIG_ASIP_ENABLED=1"],
            )

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("enabled_direct_caller", "calls", "enabled_hw_init"), edge_triples)
            self.assertIn(("common_hw_init", "calls", "enabled_hw_init"), edge_triples)
            self.assertIn(("enabled_hw_init", "writes", "GCVM_L2_CNTL"), edge_triples)

    def test_stage1_honors_module_config_for_is_enabled_branches(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "struct amdgpu_ip_funcs { int (*hw_init)(void *adev); };",
                        "static int disabled_hw_init(void *adev) {",
                        "  WREG32(mmSDMA0_QUEUE0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "#if IS_ENABLED(CONFIG_ASIP_ENABLED)",
                        "static int enabled_hw_init(void *adev) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amdgpu_ip_funcs enabled_funcs = {",
                        "  .hw_init = enabled_hw_init,",
                        "};",
                        "#endif",
                        "#if IS_BUILTIN(CONFIG_ASIP_ENABLED)",
                        "static int builtin_only_hw_init(void *adev) {",
                        "  WREG32(mmCP_HQD_PQ_CONTROL, 1);",
                        "  return 0;",
                        "}",
                        "#endif",
                        "#if IS_REACHABLE(CONFIG_ASIP_ENABLED)",
                        "static int reachable_helper(void *adev) { return 0; }",
                        "int reachable_caller(void *adev) { return reachable_helper(adev); }",
                        "#endif",
                        "int common_hw_init(struct amdgpu_ip_funcs *funcs, void *adev) {",
                        "#if IS_ENABLED(CONFIG_ASIP_ENABLED)",
                        "  return funcs->hw_init(adev);",
                        "#else",
                        "  return disabled_hw_init(adev);",
                        "#endif",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-module-config",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(
                source,
                source_root=root,
                resolver_profiles=[profile],
                clang_args=["-DCONFIG_ASIP_ENABLED_MODULE=1"],
            )

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("common_hw_init", "calls", "enabled_hw_init"), edge_triples)
            self.assertIn(("enabled_hw_init", "writes", "GCVM_L2_CNTL"), edge_triples)
            self.assertNotIn(("reachable_caller", "calls", "reachable_helper"), edge_triples)
            self.assertNotIn(("common_hw_init", "calls", "disabled_hw_init"), edge_triples)
            self.assertNotIn(("builtin_only_hw_init", "writes", "CP_HQD_PQ_CONTROL"), edge_triples)

    def test_stage1_honors_is_reachable_for_module_build_units(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "#if IS_REACHABLE(CONFIG_ASIP_ENABLED)",
                        "static int reachable_helper(void *adev) { return 0; }",
                        "int reachable_caller(void *adev) { return reachable_helper(adev); }",
                        "#endif",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(
                source,
                source_root=root,
                clang_args=["-DCONFIG_ASIP_ENABLED_MODULE=1", "-DMODULE=1"],
            )

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("reachable_caller", "calls", "reachable_helper"), edge_triples)

    def test_stage1_honors_config_macros_from_forced_include_header(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            autoconf = root / "autoconf.h"
            autoconf.write_text("#define CONFIG_ASIP_ENABLED_MODULE 1\n", encoding="utf-8")
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "struct amdgpu_ip_funcs { int (*hw_init)(void *adev); };",
                        "#if IS_ENABLED(CONFIG_ASIP_ENABLED)",
                        "static int enabled_hw_init(void *adev) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amdgpu_ip_funcs enabled_funcs = {",
                        "  .hw_init = enabled_hw_init,",
                        "};",
                        "#endif",
                        "int common_hw_init(struct amdgpu_ip_funcs *funcs, void *adev) {",
                        "#if IS_ENABLED(CONFIG_ASIP_ENABLED)",
                        "  return funcs->hw_init(adev);",
                        "#else",
                        "  return 0;",
                        "#endif",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-forced-include-config",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(
                source,
                source_root=root,
                resolver_profiles=[profile],
                clang_args=["-include", str(autoconf)],
            )

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("common_hw_init", "calls", "enabled_hw_init"), edge_triples)
            self.assertIn(("enabled_hw_init", "writes", "GCVM_L2_CNTL"), edge_triples)

    def test_stage1_honors_compile_defined_config_branches_for_slot_calls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "struct amdgpu_ip_funcs { int (*hw_init)(void *adev); };",
                        "static int enabled_hw_init(void *adev) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amdgpu_ip_funcs enabled_funcs = {",
                        "  .hw_init = enabled_hw_init,",
                        "};",
                        "int common_hw_init(struct amdgpu_ip_funcs *funcs, void *adev) {",
                        "#ifdef CONFIG_ASIP_ENABLED",
                        "  return funcs->hw_init(adev);",
                        "#else",
                        "  return 0;",
                        "#endif",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-compile-defined-config-slot-call",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(
                source,
                source_root=root,
                resolver_profiles=[profile],
                clang_args=["-DCONFIG_ASIP_ENABLED=1"],
            )

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("common_hw_init", "calls", "enabled_hw_init"), edge_triples)
            self.assertIn(("enabled_hw_init", "writes", "GCVM_L2_CNTL"), edge_triples)

    def test_stage1_ignores_numeric_false_config_branches_for_calls_callbacks_and_slots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "struct amdgpu_ip_funcs { int (*hw_init)(void *adev); };",
                        "static int helper(void *adev) { return 0; }",
                        "static int disabled_helper(void *adev) { return 0; }",
                        "#if CONFIG_ASIP_DISABLED == 1",
                        "static int disabled_eq_caller(void *adev) {",
                        "  return disabled_helper(adev);",
                        "}",
                        "#endif",
                        "#if CONFIG_ASIP_ENABLED",
                        "static int disabled_by_zero_caller(void *adev) {",
                        "  return disabled_helper(adev);",
                        "}",
                        "#endif",
                        "#if CONFIG_ASIP_ENABLED == 1",
                        "static int disabled_hw_init(void *adev) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amdgpu_ip_funcs disabled_funcs = {",
                        "  .hw_init = disabled_hw_init,",
                        "};",
                        "#endif",
                        "static int active_hw_init(void *adev) {",
                        "  WREG32(mmSDMA0_QUEUE0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amdgpu_ip_funcs active_funcs = {",
                        "  .hw_init = active_hw_init,",
                        "};",
                        "int common_hw_init(struct amdgpu_ip_funcs *funcs, void *adev) {",
                        "#if CONFIG_ASIP_ENABLED != 0",
                        "  return funcs->hw_init(adev);",
                        "#else",
                        "  return helper(adev);",
                        "#endif",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-numeric-config-false",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(
                source,
                source_root=root,
                resolver_profiles=[profile],
                clang_args=["-DCONFIG_ASIP_ENABLED=0"],
            )

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("common_hw_init", "calls", "helper"), edge_triples)
            self.assertIn(("active_hw_init", "writes", "SDMA0_QUEUE0_RB_CNTL"), edge_triples)
            self.assertNotIn(("disabled_eq_caller", "calls", "disabled_helper"), edge_triples)
            self.assertNotIn(("disabled_by_zero_caller", "calls", "disabled_helper"), edge_triples)
            self.assertNotIn(("disabled_hw_init", "writes", "GCVM_L2_CNTL"), edge_triples)
            self.assertNotIn(("common_hw_init", "calls", "disabled_hw_init"), edge_triples)

    def test_stage1_honors_numeric_true_config_branches_for_equality_expressions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "struct amdgpu_ip_funcs { int (*hw_init)(void *adev); };",
                        "#if CONFIG_ASIP_ENABLED == 1",
                        "static int eq_one_hw_init(void *adev) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amdgpu_ip_funcs eq_one_funcs = {",
                        "  .hw_init = eq_one_hw_init,",
                        "};",
                        "#endif",
                        "#if CONFIG_ASIP_ENABLED == 0",
                        "static int eq_zero_hw_init(void *adev) {",
                        "  WREG32(mmSDMA0_QUEUE0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "#endif",
                        "int common_hw_init(struct amdgpu_ip_funcs *funcs, void *adev) {",
                        "#if CONFIG_ASIP_ENABLED == 1",
                        "  return funcs->hw_init(adev);",
                        "#elif CONFIG_ASIP_ENABLED == 0",
                        "  return eq_zero_hw_init(adev);",
                        "#else",
                        "  return 0;",
                        "#endif",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-numeric-config-true",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            enabled_graph = build_deterministic_code_graph(
                source,
                source_root=root,
                resolver_profiles=[profile],
                clang_args=["-DCONFIG_ASIP_ENABLED=1"],
            )
            enabled_edges = {(edge.src, edge.relation, edge.dst) for edge in enabled_graph.edges}
            self.assertIn(("common_hw_init", "calls", "eq_one_hw_init"), enabled_edges)
            self.assertIn(("eq_one_hw_init", "writes", "GCVM_L2_CNTL"), enabled_edges)
            self.assertNotIn(("common_hw_init", "calls", "eq_zero_hw_init"), enabled_edges)
            self.assertNotIn(("eq_zero_hw_init", "writes", "SDMA0_QUEUE0_RB_CNTL"), enabled_edges)

            disabled_graph = build_deterministic_code_graph(
                source,
                source_root=root,
                resolver_profiles=[profile],
                clang_args=["-DCONFIG_ASIP_ENABLED=0"],
            )
            disabled_edges = {(edge.src, edge.relation, edge.dst) for edge in disabled_graph.edges}
            self.assertIn(("common_hw_init", "calls", "eq_zero_hw_init"), disabled_edges)
            self.assertIn(("eq_zero_hw_init", "writes", "SDMA0_QUEUE0_RB_CNTL"), disabled_edges)
            self.assertNotIn(("common_hw_init", "calls", "eq_one_hw_init"), disabled_edges)
            self.assertNotIn(("eq_one_hw_init", "writes", "GCVM_L2_CNTL"), disabled_edges)

    def test_stage1_tracks_disabled_preprocessor_branches_with_parenthesized_zero_and_else(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "static int helper(void *adev) { return 0; }",
                        "#if (0)",
                        "static int disabled_parenthesized(void *adev) {",
                        "  return helper(adev);",
                        "}",
                        "#else",
                        "static int enabled_else(void *adev) {",
                        "  return helper(adev);",
                        "}",
                        "#endif",
                        "#if 1",
                        "static int enabled_if(void *adev) {",
                        "  return helper(adev);",
                        "}",
                        "#else",
                        "static int disabled_else(void *adev) {",
                        "  return helper(adev);",
                        "}",
                        "#endif",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[])

            call_edges = {(edge.src, edge.relation, edge.dst) for edge in graph.edges if edge.relation == "calls"}
            self.assertIn(("enabled_else", "calls", "helper"), call_edges)
            self.assertIn(("enabled_if", "calls", "helper"), call_edges)
            self.assertNotIn(("disabled_parenthesized", "calls", "helper"), call_edges)
            self.assertNotIn(("disabled_else", "calls", "helper"), call_edges)

    def test_stage1_ignores_elif_branch_after_taken_if_branch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "static int helper(void *adev) { return 0; }",
                        "static int disabled_elif_helper(void *adev) { return 0; }",
                        "#if 1",
                        "static int active_if(void *adev) {",
                        "  return helper(adev);",
                        "}",
                        "#elif 1",
                        "static int inactive_elif(void *adev) {",
                        "  return disabled_elif_helper(adev);",
                        "}",
                        "#else",
                        "static int inactive_else(void *adev) {",
                        "  return disabled_elif_helper(adev);",
                        "}",
                        "#endif",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[])

            call_edges = {(edge.src, edge.relation, edge.dst) for edge in graph.edges if edge.relation == "calls"}
            self.assertIn(("active_if", "calls", "helper"), call_edges)
            self.assertNotIn(("inactive_elif", "calls", "disabled_elif_helper"), call_edges)
            self.assertNotIn(("inactive_else", "calls", "disabled_elif_helper"), call_edges)

    def test_stage1_ignores_callback_initializer_inside_inactive_elif_branch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "struct amdgpu_ip_funcs { int (*hw_init)(void *adev); };",
                        "static int active_hw_init(void *adev) { return 0; }",
                        "static int disabled_hw_init(void *adev) { return 0; }",
                        "static const struct amdgpu_ip_funcs active_funcs = {",
                        "  .hw_init = active_hw_init,",
                        "};",
                        "#if 1",
                        "static int enabled_marker(void *adev) { return active_hw_init(adev); }",
                        "#elif 1",
                        "static const struct amdgpu_ip_funcs disabled_funcs = {",
                        "  .hw_init = disabled_hw_init,",
                        "};",
                        "#endif",
                        "int common_hw_init(struct amdgpu_ip_funcs *funcs) {",
                        "  return funcs->hw_init(0);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[])

            call_edges = {(edge.src, edge.relation, edge.dst) for edge in graph.edges if edge.relation == "calls"}
            self.assertIn(("common_hw_init", "calls", "active_hw_init"), call_edges)
            self.assertNotIn(("common_hw_init", "calls", "disabled_hw_init"), call_edges)

    def test_stage1_ignores_callback_initializers_inside_disabled_preprocessor_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "struct amdgpu_ip_funcs { int (*hw_init)(void *adev); };",
                        "static int active_hw_init(void *adev) { return 0; }",
                        "static int disabled_hw_init(void *adev) { return 0; }",
                        "static const struct amdgpu_ip_funcs active_funcs = {",
                        "  .hw_init = active_hw_init,",
                        "};",
                        "#if 0",
                        "static const struct amdgpu_ip_funcs disabled_funcs = {",
                        "  .hw_init = disabled_hw_init,",
                        "};",
                        "#endif",
                        "int common_hw_init(struct amdgpu_ip_funcs *funcs) {",
                        "  return funcs->hw_init(0);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[])

            call_edges = {(edge.src, edge.relation, edge.dst) for edge in graph.edges if edge.relation == "calls"}
            self.assertIn(("common_hw_init", "calls", "active_hw_init"), call_edges)
            self.assertNotIn(("common_hw_init", "calls", "disabled_hw_init"), call_edges)

    def test_stage1_ignores_callback_initializers_inside_undefined_config_branches(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "struct amdgpu_ip_funcs { int (*hw_init)(void *adev); };",
                        "static int active_hw_init(void *adev) { return 0; }",
                        "static int disabled_hw_init(void *adev) { return 0; }",
                        "static const struct amdgpu_ip_funcs active_funcs = {",
                        "  .hw_init = active_hw_init,",
                        "};",
                        "#ifdef CONFIG_ASIP_DISABLED",
                        "static const struct amdgpu_ip_funcs disabled_ifdef_funcs = {",
                        "  .hw_init = disabled_hw_init,",
                        "};",
                        "#endif",
                        "#if IS_ENABLED(CONFIG_ASIP_DISABLED)",
                        "static const struct amdgpu_ip_funcs disabled_is_enabled_funcs = {",
                        "  .hw_init = disabled_hw_init,",
                        "};",
                        "#endif",
                        "int common_hw_init(struct amdgpu_ip_funcs *funcs) {",
                        "  return funcs->hw_init(0);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[])

            call_edges = {(edge.src, edge.relation, edge.dst) for edge in graph.edges if edge.relation == "calls"}
            self.assertIn(("common_hw_init", "calls", "active_hw_init"), call_edges)
            self.assertNotIn(("common_hw_init", "calls", "disabled_hw_init"), call_edges)

    def test_stage1_ignores_global_receiver_aliases_inside_disabled_preprocessor_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "struct amdgpu_ip_funcs { int (*hw_init)(void *adev); };",
                        "struct amdgpu_device { const struct amdgpu_ip_funcs *funcs; };",
                        "static int active_hw_init(void *adev) { return 0; }",
                        "static int disabled_hw_init(void *adev) { return 0; }",
                        "static const struct amdgpu_ip_funcs active_funcs = {",
                        "  .hw_init = active_hw_init,",
                        "};",
                        "static const struct amdgpu_ip_funcs disabled_funcs = {",
                        "  .hw_init = disabled_hw_init,",
                        "};",
                        "static void wire_active(struct amdgpu_device *adev) {",
                        "  adev->funcs = &active_funcs;",
                        "}",
                        "#if 0",
                        "static void wire_disabled(struct amdgpu_device *adev) {",
                        "  adev->funcs = &disabled_funcs;",
                        "}",
                        "#endif",
                        "int common_hw_init(struct amdgpu_device *adev) {",
                        "  return adev->funcs->hw_init(adev);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[])

            call_edges = {(edge.src, edge.relation, edge.dst) for edge in graph.edges if edge.relation == "calls"}
            self.assertIn(("common_hw_init", "calls", "active_hw_init"), call_edges)
            self.assertNotIn(("common_hw_init", "calls", "disabled_hw_init"), call_edges)

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

    def test_compile_commands_preprocess_ignores_register_calls_inside_strings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            include = root / "include"
            include.mkdir()
            (include / "regops.h").write_text(
                "#define WRITE_REAL() WREG32(regREAL_REG, 1)\n",
                encoding="utf-8",
            )
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        '#include "regops.h"',
                        "static void program(void) {",
                        '  const char *debug = "WREG32(mmFAKE_REG, 1)";',
                        "  WRITE_REAL();",
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
                            "command": f"clang -I include -c {source}",
                            "file": str(source),
                        }
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="compile-db-strings",
                language="cpp",
                symbol_prefixes=["reg", "mm"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("program", "writes", "REAL_REG"), edge_triples)
            self.assertNotIn(("program", "writes", "FAKE_REG"), edge_triples)

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
            self.assertEqual(callback_edge.provenance.get("call_kind"), "vtable_dispatch")
            self.assertEqual(callback_edge.provenance.get("slot"), "hw_init")
            self.assertEqual(callback_edge.provenance.get("callback_candidate_count"), 1)
            self.assertEqual(callback_edge.provenance.get("callee_line"), 4)
            self.assertEqual(callback_edge.provenance.get("callback_line"), 9)
            graph_node_ids = {edge.src for edge in graph.edges} | {edge.dst for edge in graph.edges}
            self.assertNotIn("hw_init", graph_node_ids)
            self.assertNotIn("gfx_v11_0_ip_funcs", graph_node_ids)

    def test_stage1_clang_ast_json_resolves_macro_wrapped_callback_initializer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "#define ASIP_CB(fn) fn",
                        "struct amd_ip_funcs {",
                        "  int (*hw_init)(void *);",
                        "};",
                        "static int gfx_v11_0_hw_init(void *adev) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = ASIP_CB(gfx_v11_0_hw_init),",
                        "};",
                        "int amdgpu_common_hw_init(struct amd_ip_funcs *funcs) {",
                        "  return funcs->hw_init(0);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-macro-callback",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("gfx_v11_0_hw_init", "writes", "GCVM_L2_CNTL"), edge_triples)
            self.assertIn(("amdgpu_common_hw_init", "calls", "gfx_v11_0_hw_init"), edge_triples)
            callback_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("amdgpu_common_hw_init", "calls", "gfx_v11_0_hw_init")
            )
            self.assertEqual(callback_edge.source, "clang_callback")
            self.assertEqual(callback_edge.provenance.get("slot"), "hw_init")
            self.assertEqual(callback_edge.provenance.get("receiver"), "funcs")
            self.assertEqual(callback_edge.provenance.get("receiver_type"), "amd_ip_funcs")
            self.assertEqual(callback_edge.provenance.get("type_flow"), "clang_ast_json")
            self.assertEqual(callback_edge.provenance.get("callback_initializer_flow"), "clang_ast_json")
            self.assertEqual(callback_edge.provenance.get("callback_table"), "gfx_v11_0_ip_funcs")
            self.assertEqual(callback_edge.provenance.get("callback_table_type"), "amd_ip_funcs")
            self.assertEqual(callback_edge.provenance.get("callee_line"), 5)
            self.assertEqual(callback_edge.provenance.get("callback_line"), 10)
            graph_node_ids = {edge.src for edge in graph.edges} | {edge.dst for edge in graph.edges}
            self.assertNotIn("ASIP_CB", graph_node_ids)
            self.assertNotIn("hw_init", graph_node_ids)

    def test_stage1_clang_ast_json_resolves_macro_wrapped_slot_initializer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "#define ASIP_SLOT(slot, fn) .slot = fn",
                        "struct amd_ip_funcs {",
                        "  int (*hw_init)(void *);",
                        "};",
                        "static int gfx_v11_0_hw_init(void *adev) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  ASIP_SLOT(hw_init, gfx_v11_0_hw_init),",
                        "};",
                        "int amdgpu_common_hw_init(struct amd_ip_funcs *funcs) {",
                        "  return funcs->hw_init(0);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-macro-slot-callback",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("gfx_v11_0_hw_init", "writes", "GCVM_L2_CNTL"), edge_triples)
            self.assertIn(("amdgpu_common_hw_init", "calls", "gfx_v11_0_hw_init"), edge_triples)
            callback_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("amdgpu_common_hw_init", "calls", "gfx_v11_0_hw_init")
            )
            self.assertEqual(callback_edge.provenance.get("slot"), "hw_init")
            self.assertEqual(callback_edge.provenance.get("callback_initializer_flow"), "clang_ast_json")
            graph_node_ids = {edge.src for edge in graph.edges} | {edge.dst for edge in graph.edges}
            self.assertNotIn("ASIP_SLOT", graph_node_ids)
            self.assertNotIn("hw_init", graph_node_ids)

    def test_stage1_records_clang_ast_json_type_flow_for_nested_vtable_receiver(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "struct amd_ip_funcs {",
                        "  int (*hw_init)(void *);",
                        "};",
                        "struct amdgpu_ip_block_version {",
                        "  const struct amd_ip_funcs *funcs;",
                        "};",
                        "struct amdgpu_ip_block {",
                        "  const struct amdgpu_ip_block_version *version;",
                        "};",
                        "static int gfx_v11_0_hw_init(void *block) {",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = gfx_v11_0_hw_init,",
                        "};",
                        "int amdgpu_common_hw_init(struct amdgpu_ip_block *block) {",
                        "  return block->version->funcs->hw_init(block);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(source, source_root=root)

            callback_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("amdgpu_common_hw_init", "calls", "gfx_v11_0_hw_init")
            )
            self.assertEqual(callback_edge.provenance.get("receiver"), "block->version->funcs")
            self.assertEqual(callback_edge.provenance.get("receiver_type"), "amd_ip_funcs")
            self.assertEqual(callback_edge.provenance.get("type_flow"), "clang_ast_json")

    def test_stage1_clang_ast_receiver_type_overrides_generic_funcs_leaf(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "typed.c"
            source.write_text(
                "\n".join(
                    [
                        "struct amd_ip_funcs {",
                        "  int (*hw_init)(void *);",
                        "};",
                        "struct unrelated_ops {",
                        "  int (*hw_init)(void *);",
                        "};",
                        "struct unrelated_holder {",
                        "  const struct unrelated_ops *funcs;",
                        "};",
                        "static int gfx_v11_0_hw_init(void *block) {",
                        "  return 0;",
                        "}",
                        "static int unrelated_hw_init(void *block) {",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = gfx_v11_0_hw_init,",
                        "};",
                        "static const struct unrelated_ops unrelated_funcs = {",
                        "  .hw_init = unrelated_hw_init,",
                        "};",
                        "int common_unrelated_hw_init(struct unrelated_holder *block) {",
                        "  return block->funcs->hw_init(block);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(source, source_root=root)

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("common_unrelated_hw_init", "calls", "unrelated_hw_init"), edge_triples)
            self.assertNotIn(("common_unrelated_hw_init", "calls", "gfx_v11_0_hw_init"), edge_triples)
            callback_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("common_unrelated_hw_init", "calls", "unrelated_hw_init")
            )
            self.assertEqual(callback_edge.provenance.get("receiver"), "block->funcs")
            self.assertEqual(callback_edge.provenance.get("receiver_type"), "unrelated_ops")
            self.assertEqual(callback_edge.provenance.get("type_flow"), "clang_ast_json")
            self.assertEqual(callback_edge.provenance.get("callback_table_type"), "unrelated_ops")

    def test_stage1_cross_file_callback_initializer_resolves_known_external_function(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "table.c"
            source.write_text(
                "\n".join(
                    [
                        "struct amd_ip_funcs {",
                        "  int (*hw_init)(void *);",
                        "};",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = gfx_v11_0_hw_init,",
                        "};",
                        "int amdgpu_common_hw_init(struct amd_ip_funcs *funcs) {",
                        "  return funcs->hw_init(0);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(
                source,
                source_root=root,
                known_function_locations={
                    "gfx_v11_0_hw_init": [
                        CodeGraphFunctionLocation(
                            name="gfx_v11_0_hw_init",
                            path="callbacks.c",
                            line_start=7,
                            line_end=10,
                        )
                    ]
                },
            )

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("amdgpu_common_hw_init", "calls", "gfx_v11_0_hw_init"), edge_triples)
            callback_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("amdgpu_common_hw_init", "calls", "gfx_v11_0_hw_init")
            )
            self.assertEqual(callback_edge.provenance.get("callback_table"), "gfx_v11_0_ip_funcs")
            self.assertEqual(callback_edge.provenance.get("callback_path"), "table.c")
            self.assertEqual(callback_edge.provenance.get("callee_line"), 7)

    def test_stage1_address_of_callback_initializer_resolves_known_external_function(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "table.c"
            source.write_text(
                "\n".join(
                    [
                        "struct amd_ip_funcs {",
                        "  int (*hw_init)(void *);",
                        "};",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = &gfx_v11_0_hw_init,",
                        "};",
                        "int amdgpu_common_hw_init(struct amd_ip_funcs *funcs) {",
                        "  return funcs->hw_init(0);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(
                source,
                source_root=root,
                known_function_locations={
                    "gfx_v11_0_hw_init": [
                        CodeGraphFunctionLocation(
                            name="gfx_v11_0_hw_init",
                            path="callbacks.c",
                            line_start=7,
                            line_end=10,
                        )
                    ]
                },
            )

            callback_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("amdgpu_common_hw_init", "calls", "gfx_v11_0_hw_init")
            )
            self.assertEqual(callback_edge.provenance.get("callback_table"), "gfx_v11_0_ip_funcs")
            self.assertEqual(callback_edge.provenance.get("callback_path"), "table.c")
            self.assertEqual(callback_edge.provenance.get("callee_line"), 7)
            self.assertEqual(callback_edge.provenance.get("slot"), "hw_init")

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

    def test_text_span_parser_does_not_promote_all_caps_macros_to_functions(self):
        source_text = "\n".join(
            [
                "static int helper(void) {",
                "  return 0;",
                "}",
                "static int outer(int version) {",
                "  switch (version) {",
                "  case IP_VERSION(4, 0, 6):",
                "    if (helper()) {",
                "      return helper();",
                "    }",
                "    break;",
                "  }",
                "  return 0;",
                "}",
            ]
        )

        spans = _function_spans_from_text(source_text)

        self.assertIn("outer", {span.name for span in spans})
        self.assertIn("helper", {span.name for span in spans})
        self.assertNotIn("IP_VERSION", {span.name for span in spans})

    def test_stage1_does_not_link_all_caps_macros_as_call_nodes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "macro.c"
            source.write_text(
                "\n".join(
                    [
                        "static int helper(void) {",
                        "  return 0;",
                        "}",
                        "static int outer(int version) {",
                        "  switch (version) {",
                        "  case IP_VERSION(4, 0, 6):",
                        "    if (helper()) {",
                        "      return helper();",
                        "    }",
                        "    break;",
                        "  }",
                        "  return 0;",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(source, source_root=root)

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("outer", "calls", "helper"), edge_triples)
            self.assertNotIn(("IP_VERSION", "calls", "helper"), edge_triples)
            self.assertNotIn(("outer", "calls", "IP_VERSION"), edge_triples)

    def test_stage1_generic_slot_call_links_common_dispatch_to_callbacks(self):
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
            self.assertIn(("amdgpu_common_hw_init", "calls", "gfx_v11_0_hw_init"), edge_triples)
            self.assertIn(("amdgpu_common_hw_init", "calls", "sdma_v5_0_hw_init"), edge_triples)
            dispatch_edges = [
                edge
                for edge in graph.edges
                if edge.src == "amdgpu_common_hw_init" and edge.relation == "calls"
            ]
            self.assertEqual({edge.provenance.get("call_kind") for edge in dispatch_edges}, {"vtable_dispatch"})
            self.assertEqual({edge.provenance.get("dispatch_scope") for edge in dispatch_edges}, {"ambiguous"})
            self.assertTrue(all(edge.provenance.get("callback_ambiguous") for edge in dispatch_edges))
            self.assertTrue(all(edge.confidence < 0.84 for edge in dispatch_edges))

    def test_stage1_ip_block_receiver_name_prefix_limits_callback_candidates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_v11_0_power(void *adev) {",
                        "  return 0;",
                        "}",
                        "static int sdma_v5_0_power(void *adev) {",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .set_powergating_state = gfx_v11_0_power,",
                        "};",
                        "static const struct amd_ip_funcs sdma_v5_0_ip_funcs = {",
                        "  .set_powergating_state = sdma_v5_0_power,",
                        "};",
                        "int set_gfx_power(struct amd_ip_block *gfx_block) {",
                        "  return gfx_block->version->funcs->set_powergating_state(gfx_block);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(source, source_root=root)

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("set_gfx_power", "calls", "gfx_v11_0_power"), edge_triples)
            self.assertNotIn(("set_gfx_power", "calls", "sdma_v5_0_power"), edge_triples)
            dispatch = next(edge for edge in graph.edges if edge.src == "set_gfx_power" and edge.dst == "gfx_v11_0_power")
            self.assertEqual(dispatch.provenance["callback_candidate_count"], 1)

    def test_stage1_table_alias_limits_generic_slot_dispatch_to_assigned_table(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_v11_0_hw_init(void *adev) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static int sdma_v5_0_hw_init(void *adev) {",
                        "  WREG32(mmSDMA0_RLC0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = gfx_v11_0_hw_init,",
                        "};",
                        "static const struct amd_ip_funcs sdma_v5_0_ip_funcs = {",
                        "  .hw_init = sdma_v5_0_hw_init,",
                        "};",
                        "int exact_table_hw_init(void) {",
                        "  const struct amd_ip_funcs *funcs = &gfx_v11_0_ip_funcs;",
                        "  return funcs->hw_init(0);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-alias",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("exact_table_hw_init", "calls", "gfx_v11_0_hw_init"), edge_triples)
            self.assertNotIn(("exact_table_hw_init", "calls", "sdma_v5_0_hw_init"), edge_triples)
            dispatch_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("exact_table_hw_init", "calls", "gfx_v11_0_hw_init")
            )
            self.assertEqual(dispatch_edge.provenance.get("call_kind"), "vtable_table_alias")
            self.assertEqual(dispatch_edge.provenance.get("receiver_tables"), ["gfx_v11_0_ip_funcs"])
            self.assertEqual(dispatch_edge.provenance.get("callback_table"), "gfx_v11_0_ip_funcs")

    def test_stage1_table_alias_is_scoped_to_each_slot_call_site(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_v11_0_hw_init(void *adev) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static int sdma_v5_0_hw_init(void *adev) {",
                        "  WREG32(mmSDMA0_RLC0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = gfx_v11_0_hw_init,",
                        "};",
                        "static const struct amd_ip_funcs sdma_v5_0_ip_funcs = {",
                        "  .hw_init = sdma_v5_0_hw_init,",
                        "};",
                        "int sequential_table_hw_init(void) {",
                        "  const struct amd_ip_funcs *funcs = &gfx_v11_0_ip_funcs;",
                        "  funcs->hw_init(0);",
                        "  funcs = &sdma_v5_0_ip_funcs;",
                        "  return funcs->hw_init(0);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-sequential-alias",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            callback_edges = [
                edge
                for edge in graph.edges
                if edge.src == "sequential_table_hw_init"
                and edge.relation == "calls"
                and edge.provenance.get("call_kind") == "vtable_table_alias"
            ]
            edges_by_line = {
                edge.line_start: (edge.dst, edge.provenance.get("callback_table"))
                for edge in callback_edges
            }
            self.assertEqual(edges_by_line[17], ("gfx_v11_0_hw_init", "gfx_v11_0_ip_funcs"))
            self.assertEqual(edges_by_line[19], ("sdma_v5_0_hw_init", "sdma_v5_0_ip_funcs"))
            self.assertEqual(len(callback_edges), 2)

    def test_stage1_returned_table_alias_limits_same_type_callbacks(self):
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
                        "const struct amd_ip_funcs *select_gfx_funcs(void) {",
                        "  return &gfx_v11_0_ip_funcs;",
                        "}",
                        "int common_hw_init(void) {",
                        "  const struct amd_ip_funcs *funcs = select_gfx_funcs();",
                        "  return funcs->hw_init(0);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(source, source_root=root)

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("common_hw_init", "calls", "gfx_v11_0_hw_init"), edge_triples)
            self.assertNotIn(("common_hw_init", "calls", "sdma_v5_0_hw_init"), edge_triples)
            dispatch_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("common_hw_init", "calls", "gfx_v11_0_hw_init")
            )
            self.assertEqual(dispatch_edge.provenance.get("call_kind"), "vtable_table_alias")
            self.assertEqual(dispatch_edge.provenance.get("receiver_tables"), ["gfx_v11_0_ip_funcs"])
            self.assertEqual(dispatch_edge.provenance.get("callback_table"), "gfx_v11_0_ip_funcs")
            self.assertEqual(dispatch_edge.provenance.get("type_flow"), "source_return_table_alias")

    def test_stage1_local_receiver_table_alias_does_not_leak_across_functions(self):
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
                        "int exact_table_hw_init(void) {",
                        "  const struct amd_ip_funcs *funcs = &gfx_v11_0_ip_funcs;",
                        "  return funcs->hw_init(0);",
                        "}",
                        "int generic_common_hw_init(struct amd_ip_funcs *funcs) {",
                        "  return funcs->hw_init(0);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(source, source_root=root)

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("exact_table_hw_init", "calls", "gfx_v11_0_hw_init"), edge_triples)
            self.assertNotIn(("exact_table_hw_init", "calls", "sdma_v5_0_hw_init"), edge_triples)
            self.assertIn(("generic_common_hw_init", "calls", "gfx_v11_0_hw_init"), edge_triples)
            self.assertIn(("generic_common_hw_init", "calls", "sdma_v5_0_hw_init"), edge_triples)

    def test_stage1_local_receiver_alias_from_indexed_field_load_limits_same_type_callbacks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "amdgpu_userq.c"
            source.write_text(
                "\n".join(
                    [
                        "static int userq_mes_map(void *queue) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static int userq_debug_map(void *queue) {",
                        "  WREG32(mmSDMA0_RLC0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amdgpu_userq_funcs userq_mes_funcs = {",
                        "  .map = userq_mes_map,",
                        "};",
                        "static const struct amdgpu_userq_funcs userq_debug_funcs = {",
                        "  .map = userq_debug_map,",
                        "};",
                        "int gfx_userq_sw_init(struct amdgpu_device *adev) {",
                        "  adev->userq_funcs[AMDGPU_HW_IP_GFX] = &userq_mes_funcs;",
                        "  return 0;",
                        "}",
                        "int amdgpu_userq_post_reset(struct amdgpu_device *adev, struct queue *queue) {",
                        "  const struct amdgpu_userq_funcs *uq_funcs = adev->userq_funcs[queue->queue_type];",
                        "  return uq_funcs->map(queue);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-userq",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("amdgpu_userq_post_reset", "calls", "userq_mes_map"), edge_triples)
            self.assertNotIn(("amdgpu_userq_post_reset", "calls", "userq_debug_map"), edge_triples)
            dispatch_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("amdgpu_userq_post_reset", "calls", "userq_mes_map")
            )
            self.assertEqual(dispatch_edge.provenance.get("call_kind"), "vtable_table_alias")
            self.assertEqual(dispatch_edge.provenance.get("receiver"), "uq_funcs")
            self.assertEqual(dispatch_edge.provenance.get("receiver_tables"), ["userq_mes_funcs"])
            self.assertEqual(dispatch_edge.provenance.get("type_flow"), "source_receiver_table_alias")

    def test_stage1_dynamic_receiver_alias_keeps_multiple_array_slot_candidates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "amdgpu_userq.c"
            source.write_text(
                "\n".join(
                    [
                        "static int userq_gfx_map(void *queue) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static int userq_compute_map(void *queue) {",
                        "  WREG32(mmSDMA0_RLC0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amdgpu_userq_funcs userq_gfx_funcs = {",
                        "  .map = userq_gfx_map,",
                        "};",
                        "static const struct amdgpu_userq_funcs userq_compute_funcs = {",
                        "  .map = userq_compute_map,",
                        "};",
                        "int gfx_userq_sw_init(struct amdgpu_device *adev) {",
                        "  adev->userq_funcs[AMDGPU_HW_IP_GFX] = &userq_gfx_funcs;",
                        "  adev->userq_funcs[AMDGPU_HW_IP_COMPUTE] = &userq_compute_funcs;",
                        "  return 0;",
                        "}",
                        "int amdgpu_userq_post_reset(struct amdgpu_device *adev, struct queue *queue) {",
                        "  const struct amdgpu_userq_funcs *uq_funcs = adev->userq_funcs[queue->queue_type];",
                        "  return uq_funcs->map(queue);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-userq-dynamic",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("amdgpu_userq_post_reset", "calls", "userq_gfx_map"), edge_triples)
            self.assertIn(("amdgpu_userq_post_reset", "calls", "userq_compute_map"), edge_triples)
            dispatch_edges = [
                edge
                for edge in graph.edges
                if edge.src == "amdgpu_userq_post_reset" and edge.relation == "calls"
            ]
            self.assertEqual(
                {edge.provenance.get("callback_table") for edge in dispatch_edges},
                {"userq_gfx_funcs", "userq_compute_funcs"},
            )
            self.assertEqual(
                {edge.provenance.get("call_kind") for edge in dispatch_edges},
                {"vtable_dispatch"},
            )
            self.assertEqual(
                {tuple(edge.provenance.get("receiver_tables", ())) for edge in dispatch_edges},
                {("userq_gfx_funcs", "userq_compute_funcs")},
            )
            self.assertEqual(
                {edge.provenance.get("type_flow") for edge in dispatch_edges},
                {"source_receiver_table_alias_ambiguous"},
            )

    def test_stage1_ambiguous_receiver_alias_keeps_dispatch_kind_with_single_slot_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "amdgpu_userq.c"
            source.write_text(
                "\n".join(
                    [
                        "static int userq_gfx_map(void *queue) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static int userq_compute_unmap(void *queue) {",
                        "  WREG32(mmSDMA0_RLC0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amdgpu_userq_funcs userq_gfx_funcs = {",
                        "  .map = userq_gfx_map,",
                        "};",
                        "static const struct amdgpu_userq_funcs userq_compute_funcs = {",
                        "  .unmap = userq_compute_unmap,",
                        "};",
                        "int gfx_userq_sw_init(struct amdgpu_device *adev) {",
                        "  adev->userq_funcs[AMDGPU_HW_IP_GFX] = &userq_gfx_funcs;",
                        "  adev->userq_funcs[AMDGPU_HW_IP_COMPUTE] = &userq_compute_funcs;",
                        "  return 0;",
                        "}",
                        "int amdgpu_userq_post_reset(struct amdgpu_device *adev, struct queue *queue) {",
                        "  const struct amdgpu_userq_funcs *uq_funcs = adev->userq_funcs[queue->queue_type];",
                        "  return uq_funcs->map(queue);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-userq-dynamic-single-slot",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            dispatch_edges = [
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("amdgpu_userq_post_reset", "calls", "userq_gfx_map")
            ]
            self.assertEqual(len(dispatch_edges), 1)
            self.assertEqual(dispatch_edges[0].provenance.get("call_kind"), "vtable_dispatch")
            self.assertEqual(
                dispatch_edges[0].provenance.get("receiver_tables"),
                ["userq_gfx_funcs", "userq_compute_funcs"],
            )
            self.assertEqual(
                dispatch_edges[0].provenance.get("type_flow"),
                "source_receiver_table_alias_ambiguous",
            )

    def test_stage1_field_path_table_alias_does_not_pollute_other_funcs_receivers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_rlc_resume(void *adev) {",
                        "  WREG32(mmCP_RLC_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static int gfx_ip_resume(void *adev) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amdgpu_rlc_funcs gfx_rlc_funcs = {",
                        "  .resume = gfx_rlc_resume,",
                        "};",
                        "static const struct amd_ip_funcs gfx_ip_funcs = {",
                        "  .resume = gfx_ip_resume,",
                        "};",
                        "int mixed_resume(struct amdgpu_device *adev, struct amd_ip_block *block) {",
                        "  adev->gfx.rlc.funcs = &gfx_rlc_funcs;",
                        "  adev->gfx.rlc.funcs->resume(adev);",
                        "  block->version->funcs->resume(block);",
                        "  return 0;",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-field-alias",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            rlc_edges = [
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("mixed_resume", "calls", "gfx_rlc_resume")
            ]
            ip_edges = [
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("mixed_resume", "calls", "gfx_ip_resume")
            ]
            self.assertEqual(len(rlc_edges), 1)
            self.assertEqual(len(ip_edges), 1)
            self.assertEqual(rlc_edges[0].provenance.get("receiver"), "adev->gfx.rlc.funcs")
            self.assertEqual(rlc_edges[0].provenance.get("receiver_tables"), ["gfx_rlc_funcs"])
            self.assertEqual(rlc_edges[0].provenance.get("call_kind"), "vtable_table_alias")
            self.assertEqual(ip_edges[0].provenance.get("receiver"), "block->version->funcs")
            self.assertEqual(ip_edges[0].provenance.get("callback_table"), "gfx_ip_funcs")
            self.assertNotEqual(ip_edges[0].provenance.get("receiver_tables"), ["gfx_rlc_funcs"])

    def test_stage1_field_path_type_hint_maps_rlc_funcs_without_local_assignment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_rlc_resume(void *adev) {",
                        "  WREG32(mmCP_RLC_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static int gfx_ip_resume(void *adev) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amdgpu_rlc_funcs gfx_rlc_funcs = {",
                        "  .resume = gfx_rlc_resume,",
                        "};",
                        "static const struct amd_ip_funcs gfx_ip_funcs = {",
                        "  .resume = gfx_ip_resume,",
                        "};",
                        "int resume_rlc_only(struct amdgpu_device *adev) {",
                        "  return adev->gfx.rlc.funcs->resume(adev);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-rlc-path",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("resume_rlc_only", "calls", "gfx_rlc_resume"), edge_triples)
            self.assertNotIn(("resume_rlc_only", "calls", "gfx_ip_resume"), edge_triples)
            rlc_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("resume_rlc_only", "calls", "gfx_rlc_resume")
            )
            self.assertEqual(rlc_edge.provenance.get("receiver"), "adev->gfx.rlc.funcs")
            self.assertEqual(rlc_edge.provenance.get("callback_table_type"), "amdgpu_rlc_funcs")

    def test_stage1_known_field_path_does_not_fallback_to_unrelated_slot_when_type_has_no_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_ip_get_clockgating_state(void *adev) {",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_ip_funcs = {",
                        "  .get_clockgating_state = gfx_ip_get_clockgating_state,",
                        "};",
                        "static const struct amdgpu_df_funcs df_funcs = {",
                        "  .sw_init = gfx_ip_get_clockgating_state,",
                        "};",
                        "int read_df_clockgating(struct amdgpu_device *adev) {",
                        "  return adev->df.funcs->get_clockgating_state(adev);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )

            graph = build_deterministic_code_graph(source, source_root=root)

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertNotIn(("read_df_clockgating", "calls", "gfx_ip_get_clockgating_state"), edge_triples)

    def test_stage1_ip_block_version_funcs_alias_resolves_nested_dispatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_v11_0_hw_init(void *block) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static int sdma_v5_0_hw_init(void *block) {",
                        "  WREG32(mmSDMA0_RLC0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = gfx_v11_0_hw_init,",
                        "};",
                        "static const struct amd_ip_funcs sdma_v5_0_ip_funcs = {",
                        "  .hw_init = sdma_v5_0_hw_init,",
                        "};",
                        "static const struct amdgpu_ip_block_version gfx_v11_0_ip_block = {",
                        "  .funcs = &gfx_v11_0_ip_funcs,",
                        "};",
                        "int exact_ip_block_init(struct amd_ip_block *block) {",
                        "  block->version = &gfx_v11_0_ip_block;",
                        "  return block->version->funcs->hw_init(block);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-ip-block",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("exact_ip_block_init", "calls", "gfx_v11_0_hw_init"), edge_triples)
            self.assertNotIn(("exact_ip_block_init", "calls", "sdma_v5_0_hw_init"), edge_triples)
            dispatch_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("exact_ip_block_init", "calls", "gfx_v11_0_hw_init")
            )
            self.assertEqual(dispatch_edge.provenance.get("call_kind"), "vtable_table_alias")
            self.assertEqual(dispatch_edge.provenance.get("receiver"), "block->version->funcs")
            self.assertEqual(dispatch_edge.provenance.get("receiver_tables"), ["gfx_v11_0_ip_funcs"])
            self.assertEqual(dispatch_edge.provenance.get("callback_table"), "gfx_v11_0_ip_funcs")

    def test_stage1_ip_block_add_argument_flow_resolves_registered_version_funcs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_v11_0_hw_init(void *block) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static int sdma_v5_0_hw_init(void *block) {",
                        "  WREG32(mmSDMA0_RLC0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = gfx_v11_0_hw_init,",
                        "};",
                        "static const struct amd_ip_funcs sdma_v5_0_ip_funcs = {",
                        "  .hw_init = sdma_v5_0_hw_init,",
                        "};",
                        "static const struct amdgpu_ip_block_version gfx_v11_0_ip_block = {",
                        "  .funcs = &gfx_v11_0_ip_funcs,",
                        "};",
                        "int amdgpu_device_ip_block_add(struct amdgpu_device *adev,",
                        "                               const struct amdgpu_ip_block_version *ip_block_version) {",
                        "  adev->ip_blocks[adev->num_ip_blocks++].version = ip_block_version;",
                        "  return 0;",
                        "}",
                        "int setup_and_hw_init(struct amdgpu_device *adev) {",
                        "  amdgpu_device_ip_block_add(adev, &gfx_v11_0_ip_block);",
                        "  return adev->ip_blocks[0].version->funcs->hw_init(&adev->ip_blocks[0]);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-ip-block-add",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("setup_and_hw_init", "calls", "amdgpu_device_ip_block_add"), edge_triples)
            self.assertIn(("setup_and_hw_init", "calls", "gfx_v11_0_hw_init"), edge_triples)
            self.assertNotIn(("setup_and_hw_init", "calls", "sdma_v5_0_hw_init"), edge_triples)
            dispatch_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("setup_and_hw_init", "calls", "gfx_v11_0_hw_init")
            )
            self.assertEqual(dispatch_edge.provenance.get("call_kind"), "vtable_table_alias")
            self.assertEqual(dispatch_edge.provenance.get("receiver"), "adev->ip_blocks[0].version->funcs")
            self.assertEqual(dispatch_edge.provenance.get("receiver_tables"), ["gfx_v11_0_ip_funcs"])
            self.assertEqual(dispatch_edge.provenance.get("callback_table"), "gfx_v11_0_ip_funcs")

    def test_stage1_ip_block_add_registration_flow_resolves_common_loop_dispatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "amdgpu_device.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_v11_0_hw_init(void *block) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static int sdma_v5_0_hw_init(void *block) {",
                        "  WREG32(mmSDMA0_RLC0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = gfx_v11_0_hw_init,",
                        "};",
                        "static const struct amd_ip_funcs sdma_v5_0_ip_funcs = {",
                        "  .hw_init = sdma_v5_0_hw_init,",
                        "};",
                        "static const struct amdgpu_ip_block_version gfx_v11_0_ip_block = {",
                        "  .funcs = &gfx_v11_0_ip_funcs,",
                        "};",
                        "int amdgpu_device_ip_block_add(struct amdgpu_device *adev,",
                        "                               const struct amdgpu_ip_block_version *ip_block_version) {",
                        "  adev->ip_blocks[adev->num_ip_blocks++].version = ip_block_version;",
                        "  return 0;",
                        "}",
                        "int setup_registered_blocks(struct amdgpu_device *adev) {",
                        "  amdgpu_device_ip_block_add(adev, &gfx_v11_0_ip_block);",
                        "  return 0;",
                        "}",
                        "int amdgpu_device_hw_init(struct amdgpu_device *adev) {",
                        "  return adev->ip_blocks[0].version->funcs->hw_init(&adev->ip_blocks[0]);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-ip-block-registration",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("setup_registered_blocks", "calls", "amdgpu_device_ip_block_add"), edge_triples)
            self.assertIn(("amdgpu_device_hw_init", "calls", "gfx_v11_0_hw_init"), edge_triples)
            self.assertNotIn(("amdgpu_device_hw_init", "calls", "sdma_v5_0_hw_init"), edge_triples)
            dispatch_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("amdgpu_device_hw_init", "calls", "gfx_v11_0_hw_init")
            )
            self.assertEqual(dispatch_edge.provenance.get("call_kind"), "vtable_table_alias")
            self.assertEqual(dispatch_edge.provenance.get("receiver_tables"), ["gfx_v11_0_ip_funcs"])
            self.assertEqual(dispatch_edge.provenance.get("callback_table"), "gfx_v11_0_ip_funcs")

    def test_stage1_ip_block_version_suffix_registration_flow_resolves_common_loop_dispatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "amdgpu_device.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_v11_0_hw_init(void *block) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static int sdma_v5_0_hw_init(void *block) {",
                        "  WREG32(mmSDMA0_RLC0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = gfx_v11_0_hw_init,",
                        "};",
                        "static const struct amd_ip_funcs sdma_v5_0_ip_funcs = {",
                        "  .hw_init = sdma_v5_0_hw_init,",
                        "};",
                        "static const struct amdgpu_ip_block_version gfx_v11_0_ip_block_version = {",
                        "  .funcs = &gfx_v11_0_ip_funcs,",
                        "};",
                        "int amdgpu_device_ip_block_add(struct amdgpu_device *adev,",
                        "                               const struct amdgpu_ip_block_version *ip_block_version) {",
                        "  adev->ip_blocks[adev->num_ip_blocks++].version = ip_block_version;",
                        "  return 0;",
                        "}",
                        "int setup_registered_blocks(struct amdgpu_device *adev) {",
                        "  amdgpu_device_ip_block_add(adev, &gfx_v11_0_ip_block_version);",
                        "  return 0;",
                        "}",
                        "int amdgpu_device_hw_init(struct amdgpu_device *adev) {",
                        "  return adev->ip_blocks[0].version->funcs->hw_init(&adev->ip_blocks[0]);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-ip-block-version-registration",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("setup_registered_blocks", "calls", "amdgpu_device_ip_block_add"), edge_triples)
            self.assertIn(("amdgpu_device_hw_init", "calls", "gfx_v11_0_hw_init"), edge_triples)
            self.assertNotIn(("amdgpu_device_hw_init", "calls", "sdma_v5_0_hw_init"), edge_triples)
            dispatch_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("amdgpu_device_hw_init", "calls", "gfx_v11_0_hw_init")
            )
            self.assertEqual(dispatch_edge.provenance.get("call_kind"), "vtable_table_alias")
            self.assertEqual(dispatch_edge.provenance.get("receiver_tables"), ["gfx_v11_0_ip_funcs"])
            self.assertEqual(dispatch_edge.provenance.get("callback_table"), "gfx_v11_0_ip_funcs")

    def test_stage1_direct_ip_block_version_assignment_resolves_nested_dispatch_without_overlink(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "amdgpu_device.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_v11_0_hw_init(void *block) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static int sdma_v5_0_hw_init(void *block) {",
                        "  WREG32(mmSDMA0_RLC0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = gfx_v11_0_hw_init,",
                        "};",
                        "static const struct amd_ip_funcs sdma_v5_0_ip_funcs = {",
                        "  .hw_init = sdma_v5_0_hw_init,",
                        "};",
                        "static const struct amdgpu_ip_block_version gfx_v11_0_ip_block_version = {",
                        "  .funcs = &gfx_v11_0_ip_funcs,",
                        "};",
                        "static const struct amdgpu_ip_block_version sdma_v5_0_ip_block_version = {",
                        "  .funcs = &sdma_v5_0_ip_funcs,",
                        "};",
                        "int setup_registered_blocks(struct amdgpu_device *adev) {",
                        "  adev->ip_blocks[0].version = &gfx_v11_0_ip_block_version;",
                        "  return 0;",
                        "}",
                        "int amdgpu_device_hw_init(struct amdgpu_device *adev) {",
                        "  return adev->ip_blocks[0].version->funcs->hw_init(&adev->ip_blocks[0]);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-ip-block-version-direct-assignment",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("amdgpu_device_hw_init", "calls", "gfx_v11_0_hw_init"), edge_triples)
            self.assertNotIn(("amdgpu_device_hw_init", "calls", "sdma_v5_0_hw_init"), edge_triples)
            dispatch_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("amdgpu_device_hw_init", "calls", "gfx_v11_0_hw_init")
            )
            self.assertEqual(dispatch_edge.provenance.get("call_kind"), "vtable_table_alias")
            self.assertEqual(dispatch_edge.provenance.get("receiver_tables"), ["gfx_v11_0_ip_funcs"])
            self.assertEqual(dispatch_edge.provenance.get("callback_table"), "gfx_v11_0_ip_funcs")

    def test_stage1_ip_block_local_alias_resolves_registered_loop_dispatch(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "amdgpu_device.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_v11_0_hw_init(void *block) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static int sdma_v5_0_hw_init(void *block) {",
                        "  WREG32(mmSDMA0_RLC0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = gfx_v11_0_hw_init,",
                        "};",
                        "static const struct amd_ip_funcs sdma_v5_0_ip_funcs = {",
                        "  .hw_init = sdma_v5_0_hw_init,",
                        "};",
                        "static const struct amdgpu_ip_block_version gfx_v11_0_ip_block = {",
                        "  .funcs = &gfx_v11_0_ip_funcs,",
                        "};",
                        "int amdgpu_device_ip_block_add(struct amdgpu_device *adev,",
                        "                               const struct amdgpu_ip_block_version *ip_block_version) {",
                        "  adev->ip_blocks[adev->num_ip_blocks++].version = ip_block_version;",
                        "  return 0;",
                        "}",
                        "int setup_registered_blocks(struct amdgpu_device *adev) {",
                        "  amdgpu_device_ip_block_add(adev, &gfx_v11_0_ip_block);",
                        "  return 0;",
                        "}",
                        "int amdgpu_device_hw_init(struct amdgpu_device *adev, int i) {",
                        "  struct amd_ip_block *ip_block = &adev->ip_blocks[i];",
                        "  return ip_block->version->funcs->hw_init(ip_block);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-ip-block-local-alias",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("amdgpu_device_hw_init", "calls", "gfx_v11_0_hw_init"), edge_triples)
            self.assertNotIn(("amdgpu_device_hw_init", "calls", "sdma_v5_0_hw_init"), edge_triples)
            dispatch_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("amdgpu_device_hw_init", "calls", "gfx_v11_0_hw_init")
            )
            self.assertEqual(dispatch_edge.provenance.get("call_kind"), "vtable_table_alias")
            self.assertEqual(dispatch_edge.provenance.get("receiver"), "ip_block->version->funcs")
            self.assertEqual(dispatch_edge.provenance.get("receiver_tables"), ["gfx_v11_0_ip_funcs"])
            self.assertEqual(dispatch_edge.provenance.get("type_flow"), "local_receiver_path_alias")

    def test_stage1_ip_block_local_alias_keeps_multiple_registered_candidates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "amdgpu_device.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_v11_0_hw_init(void *block) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static int sdma_v5_0_hw_init(void *block) {",
                        "  WREG32(mmSDMA0_RLC0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = gfx_v11_0_hw_init,",
                        "};",
                        "static const struct amd_ip_funcs sdma_v5_0_ip_funcs = {",
                        "  .hw_init = sdma_v5_0_hw_init,",
                        "};",
                        "static const struct amdgpu_ip_block_version gfx_v11_0_ip_block = {",
                        "  .funcs = &gfx_v11_0_ip_funcs,",
                        "};",
                        "static const struct amdgpu_ip_block_version sdma_v5_0_ip_block = {",
                        "  .funcs = &sdma_v5_0_ip_funcs,",
                        "};",
                        "int amdgpu_device_ip_block_add(struct amdgpu_device *adev,",
                        "                               const struct amdgpu_ip_block_version *ip_block_version) {",
                        "  adev->ip_blocks[adev->num_ip_blocks++].version = ip_block_version;",
                        "  return 0;",
                        "}",
                        "int setup_registered_blocks(struct amdgpu_device *adev) {",
                        "  amdgpu_device_ip_block_add(adev, &gfx_v11_0_ip_block);",
                        "  amdgpu_device_ip_block_add(adev, &sdma_v5_0_ip_block);",
                        "  return 0;",
                        "}",
                        "int amdgpu_device_hw_init(struct amdgpu_device *adev, int i) {",
                        "  struct amd_ip_block *ip_block = &adev->ip_blocks[i];",
                        "  return ip_block->version->funcs->hw_init(ip_block);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-ip-block-local-alias-ambiguous",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("amdgpu_device_hw_init", "calls", "gfx_v11_0_hw_init"), edge_triples)
            self.assertIn(("amdgpu_device_hw_init", "calls", "sdma_v5_0_hw_init"), edge_triples)
            dispatch_edges = [
                edge
                for edge in graph.edges
                if edge.src == "amdgpu_device_hw_init" and edge.relation == "calls"
            ]
            self.assertEqual(
                {edge.provenance.get("callback_table") for edge in dispatch_edges},
                {"gfx_v11_0_ip_funcs", "sdma_v5_0_ip_funcs"},
            )
            self.assertEqual(
                {edge.provenance.get("call_kind") for edge in dispatch_edges},
                {"vtable_dispatch"},
            )
            self.assertEqual(
                {tuple(edge.provenance.get("receiver_tables", ())) for edge in dispatch_edges},
                {("gfx_v11_0_ip_funcs", "sdma_v5_0_ip_funcs")},
            )
            self.assertEqual(
                {edge.provenance.get("type_flow") for edge in dispatch_edges},
                {"local_receiver_path_alias_ambiguous"},
            )

    def test_stage1_exact_ip_block_registration_does_not_fallback_when_slot_is_absent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "amdgpu_device.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_v11_0_hw_init(void *block) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static int sdma_v5_0_sw_fini(void *block) {",
                        "  WREG32(mmSDMA0_RLC0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amd_ip_funcs gfx_v11_0_ip_funcs = {",
                        "  .hw_init = gfx_v11_0_hw_init,",
                        "};",
                        "static const struct amd_ip_funcs sdma_v5_0_ip_funcs = {",
                        "  .sw_fini = sdma_v5_0_sw_fini,",
                        "};",
                        "static const struct amdgpu_ip_block_version gfx_v11_0_ip_block = {",
                        "  .funcs = &gfx_v11_0_ip_funcs,",
                        "};",
                        "int amdgpu_device_ip_block_add(struct amdgpu_device *adev,",
                        "                               const struct amdgpu_ip_block_version *ip_block_version) {",
                        "  adev->ip_blocks[adev->num_ip_blocks++].version = ip_block_version;",
                        "  return 0;",
                        "}",
                        "int setup_registered_blocks(struct amdgpu_device *adev) {",
                        "  amdgpu_device_ip_block_add(adev, &gfx_v11_0_ip_block);",
                        "  return 0;",
                        "}",
                        "int amdgpu_device_sw_fini(struct amdgpu_device *adev) {",
                        "  return adev->ip_blocks[0].version->funcs->sw_fini(&adev->ip_blocks[0]);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-ip-block-registration",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertNotIn(("amdgpu_device_sw_fini", "calls", "sdma_v5_0_sw_fini"), edge_triples)

    def test_stage1_uses_receiver_declared_type_to_filter_generic_ops_callbacks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_ring_start(void *ring) {",
                        "  WREG32(mmCP_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static int unrelated_ring_start(void *ring) {",
                        "  WREG32(mmSDMA0_RLC0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amdgpu_ring_funcs gfx_ring_funcs = {",
                        "  .start = gfx_ring_start,",
                        "};",
                        "static const struct unrelated_ops unrelated_ops = {",
                        "  .start = unrelated_ring_start,",
                        "};",
                        "int common_ring_start(struct amdgpu_ring_funcs *ops) {",
                        "  return (*ops->start)(0);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-ring",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("common_ring_start", "calls", "gfx_ring_start"), edge_triples)
            self.assertNotIn(("common_ring_start", "calls", "unrelated_ring_start"), edge_triples)
            callback_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("common_ring_start", "calls", "gfx_ring_start")
            )
            self.assertEqual(callback_edge.provenance.get("receiver_type"), "amdgpu_ring_funcs")
            self.assertEqual(callback_edge.provenance.get("callback_table_type"), "amdgpu_ring_funcs")

    def test_stage1_does_not_generic_dispatch_non_callback_struct_receiver(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_ring_start(void *ring) {",
                        "  WREG32(mmCP_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amdgpu_ring_funcs gfx_ring_funcs = {",
                        "  .start = gfx_ring_start,",
                        "};",
                        "struct holder { int (*start)(void *); };",
                        "int holder_start(struct holder *ops) {",
                        "  return ops->start(0);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-non-callback-holder",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertNotIn(("holder_start", "calls", "gfx_ring_start"), edge_triples)

    def test_stage1_does_not_generic_dispatch_nested_non_callback_ops_receiver(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "gfx.c"
            source.write_text(
                "\n".join(
                    [
                        "struct amdgpu_ring_funcs { int (*start)(void *); };",
                        "static int gfx_ring_start(void *ring) {",
                        "  WREG32(mmCP_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static const struct amdgpu_ring_funcs gfx_ring_funcs = {",
                        "  .start = gfx_ring_start,",
                        "};",
                        "struct holder_methods { int (*start)(void *ctx); };",
                        "struct holder { struct holder_methods *ops; };",
                        "int holder_start(struct holder *holder) {",
                        "  return holder->ops->start(holder);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-amd-nested-non-callback-holder",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertNotIn(("holder_start", "calls", "gfx_ring_start"), edge_triples)

    def test_stage1_links_mxgpu_init_func_dispatch_to_callback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "mxgpu.c"
            source.write_text(
                "\n".join(
                    [
                        "static int vmhub_sw_init(void *adapt) {",
                        "  return 0;",
                        "}",
                        "static const struct vmhub_funcs vmhub_funcs = {",
                        "  .sw_init = vmhub_sw_init,",
                        "};",
                        "static int gfx_v11_hw_init(void *adapt) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static struct amdgv_init_func gfx_v11_func = {",
                        "  .hw_init = gfx_v11_hw_init,",
                        "};",
                        "int amdgv_device_init(struct amdgv_adapter *adapt) {",
                        "  struct amdgv_init_func *init_func = adapt->init_funcs[0];",
                        "  return init_func->hw_init(adapt);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-mxgpu",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("gfx_v11_hw_init", "writes", "GCVM_L2_CNTL"), edge_triples)
            self.assertIn(("amdgv_device_init", "calls", "gfx_v11_hw_init"), edge_triples)
            callback = next(item for item in graph.callback_slots if item.function == "gfx_v11_hw_init")
            self.assertEqual(callback.table, "gfx_v11_func")
            self.assertEqual(callback.table_type, "amdgv_init_func")
            dispatch_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("amdgv_device_init", "calls", "gfx_v11_hw_init")
            )
            self.assertEqual(dispatch_edge.provenance.get("call_kind"), "vtable_dispatch")
            self.assertEqual(dispatch_edge.provenance.get("callback_table_type"), "amdgv_init_func")

    def test_stage1_links_macro_wrapped_mxgpu_init_func_dispatch_to_callback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "mxgpu.c"
            source.write_text(
                "\n".join(
                    [
                        "#define AMDGV_SLOT(slot, fn) .slot = fn",
                        "#define WREG32(reg, value)",
                        "#define mmGCVM_L2_CNTL 0",
                        "struct amdgv_init_func { int (*hw_init)(void *); };",
                        "struct amdgv_adapter { struct amdgv_init_func *init_funcs[1]; };",
                        "static int gfx_v11_hw_init(void *adapt) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static struct amdgv_init_func gfx_v11_func = {",
                        "  AMDGV_SLOT(hw_init, gfx_v11_hw_init),",
                        "};",
                        "int amdgv_device_init(struct amdgv_adapter *adapt) {",
                        "  struct amdgv_init_func *init_func = adapt->init_funcs[0];",
                        "  return init_func->hw_init(adapt);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-mxgpu-macro-init-func",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("gfx_v11_hw_init", "writes", "GCVM_L2_CNTL"), edge_triples)
            self.assertIn(("amdgv_device_init", "calls", "gfx_v11_hw_init"), edge_triples)
            callback_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("amdgv_device_init", "calls", "gfx_v11_hw_init")
            )
            self.assertEqual(callback_edge.provenance.get("call_kind"), "vtable_dispatch")
            self.assertEqual(callback_edge.provenance.get("callback_initializer_flow"), "clang_ast_json")
            self.assertEqual(callback_edge.provenance.get("callback_table"), "gfx_v11_func")
            self.assertEqual(callback_edge.provenance.get("callback_table_type"), "amdgv_init_func")

    def test_stage1_links_direct_indexed_mxgpu_init_funcs_receiver_to_callback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "mxgpu.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_v11_hw_init(void *adapt) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static struct amdgv_init_func gfx_v11_func = {",
                        "  .hw_init = gfx_v11_hw_init,",
                        "};",
                        "static int sdma_v5_hw_init(void *adapt) {",
                        "  WREG32(mmSDMA0_RLC0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static struct amdgv_init_func sdma_v5_func = {",
                        "  .hw_init = sdma_v5_hw_init,",
                        "};",
                        "int amdgv_device_init(struct amdgv_adapter *adapt) {",
                        "  adapt->init_funcs[0] = &gfx_v11_func;",
                        "  return adapt->init_funcs[0]->hw_init(adapt);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-mxgpu-direct-indexed-init-funcs",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("gfx_v11_hw_init", "writes", "GCVM_L2_CNTL"), edge_triples)
            self.assertIn(("amdgv_device_init", "calls", "gfx_v11_hw_init"), edge_triples)
            self.assertNotIn(("amdgv_device_init", "calls", "sdma_v5_hw_init"), edge_triples)
            dispatch_edge = next(
                edge
                for edge in graph.edges
                if (edge.src, edge.relation, edge.dst) == ("amdgv_device_init", "calls", "gfx_v11_hw_init")
            )
            self.assertEqual(dispatch_edge.provenance.get("call_kind"), "vtable_table_alias")
            self.assertEqual(dispatch_edge.provenance.get("receiver"), "adapt->init_funcs[0]")
            self.assertEqual(dispatch_edge.provenance.get("receiver_tables"), ["gfx_v11_func"])
            self.assertEqual(dispatch_edge.provenance.get("callback_table"), "gfx_v11_func")

    def test_stage1_direct_indexed_mxgpu_receiver_alias_does_not_leak_between_functions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "mxgpu.c"
            source.write_text(
                "\n".join(
                    [
                        "static int gfx_v11_hw_init(void *adapt) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static struct amdgv_init_func gfx_v11_func = {",
                        "  .hw_init = gfx_v11_hw_init,",
                        "};",
                        "static int sdma_v5_hw_init(void *adapt) {",
                        "  WREG32(mmSDMA0_RLC0_RB_CNTL, 1);",
                        "  return 0;",
                        "}",
                        "static struct amdgv_init_func sdma_v5_func = {",
                        "  .hw_init = sdma_v5_hw_init,",
                        "};",
                        "int setup_only(struct amdgv_adapter *adapt) {",
                        "  adapt->init_funcs[0] = &gfx_v11_func;",
                        "  return 0;",
                        "}",
                        "int unrelated_init(struct amdgv_adapter *adapt) {",
                        "  return adapt->init_funcs[0]->hw_init(adapt);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            profile = ResolverProfile(
                id="test-mxgpu-direct-indexed-init-funcs-no-leak",
                language="cpp",
                symbol_prefixes=["mm", "reg"],
                wrappers={"WREG32": WrapperRule(symbol_arg=0, access="write")},
            )

            graph = build_deterministic_code_graph(source, source_root=root, resolver_profiles=[profile])

            edge_triples = {(edge.src, edge.relation, edge.dst) for edge in graph.edges}
            self.assertIn(("gfx_v11_hw_init", "writes", "GCVM_L2_CNTL"), edge_triples)
            self.assertIn(("sdma_v5_hw_init", "writes", "SDMA0_RLC0_RB_CNTL"), edge_triples)
            self.assertNotIn(("unrelated_init", "calls", "gfx_v11_hw_init"), edge_triples)
            self.assertNotIn(("unrelated_init", "calls", "sdma_v5_hw_init"), edge_triples)

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
