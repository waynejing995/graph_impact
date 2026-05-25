import unittest

from asip.graph_schema import (
    ALLOWED_PRODUCT_NODE_KINDS,
    ALLOWED_PRODUCT_RELATIONS,
    is_product_node_kind,
    is_register_symbol,
    normalize_product_relation,
    product_endpoint_kind,
)


class GraphSchemaTests(unittest.TestCase):
    def test_product_schema_allows_only_three_node_kinds(self):
        self.assertEqual(ALLOWED_PRODUCT_NODE_KINDS, {"function", "register", "doc"})
        for bad_kind in ["macro", "field", "source", "provider", "doc_box", "pdf_section"]:
            self.assertFalse(is_product_node_kind(bad_kind))

    def test_relation_normalization_is_enum_bound(self):
        self.assertEqual(normalize_product_relation("field_set"), "sets_field")
        self.assertEqual(normalize_product_relation("REG_SET_FIELD"), "sets_field")
        self.assertEqual(normalize_product_relation("contains_box"), "contains")
        self.assertEqual(normalize_product_relation("checks_mask"), "relates_to")
        self.assertIsNone(normalize_product_relation("wraps"))
        self.assertTrue(set(ALLOWED_PRODUCT_RELATIONS).issuperset({"reads", "writes", "sets_field"}))

    def test_endpoint_kind_rejects_macro_field_and_local_tokens(self):
        self.assertEqual(product_endpoint_kind("gfx_v11_0_hw_init"), "function")
        self.assertEqual(product_endpoint_kind("function:linux-amdgpu:gfx.c:gfx_v11_0_hw_init"), "function")
        self.assertEqual(product_endpoint_kind("GCVM_L2_CNTL"), "register")
        self.assertEqual(product_endpoint_kind("register:GC:GCVM_L2_CNTL"), "register")
        self.assertEqual(product_endpoint_kind("docs/guide.md#programming-registers"), "doc")
        self.assertEqual(product_endpoint_kind("doc:docs/guide.md#programming-registers"), "doc")
        for bad_endpoint in [
            "WREG32",
            "REG_SET_FIELD",
            "ENABLE_L2_CACHE",
            "tmp",
            "value",
            "ops",
            "callbacks",
            "init_func",
            "init_funcs",
            "tmp_value",
            "context:tmp",
        ]:
            self.assertIsNone(product_endpoint_kind(bad_endpoint))

    def test_is_register_symbol_accepts_amd_prefix_forms(self):
        for symbol in ["regGCVM_L2_CNTL", "mmGCVM_L2_CNTL", "smnMP1_FIRMWARE_FLAGS", "regBIF_RB_CNTL"]:
            self.assertTrue(is_register_symbol(symbol), f"{symbol} should be a register")

    def test_is_register_symbol_rejects_short_or_naked_prefix(self):
        for symbol in ["reg", "mm", "smn", "reg_", "mm_"]:
            self.assertFalse(is_register_symbol(symbol), f"{symbol} should not be a register")

    def test_is_register_symbol_rejects_local_and_wrapper_tokens(self):
        for symbol in ["tmp", "value", "adapt", "data", "ops", "funcs", "ret", "reg", "local", "ring", "init_func"]:
            self.assertFalse(is_register_symbol(symbol), f"{symbol} should not be a register")


if __name__ == "__main__":
    unittest.main()
