import tempfile
import textwrap
import unittest
from pathlib import Path

from asip.resolver_profiles import (
    load_resolver_profiles,
    resolve_cpp_register_call,
    resolve_cpp_register_calls,
    resolve_python_symbol,
)
from asip.graph_filters import is_graph_entity_endpoint, is_resolver_wrapper_name


REPO_ROOT = Path(__file__).resolve().parents[3]


class ResolverProfileTests(unittest.TestCase):
    def test_loads_committed_resolver_profiles(self):
        profiles = load_resolver_profiles(REPO_ROOT / "configs/resolvers")

        self.assertIn("linux-amdgpu", profiles)
        self.assertIn("amd-mxgpu", profiles)
        self.assertIn("initial", profiles)
        self.assertIn("toy-python", profiles)
        self.assertIn("amd-direct-mmio", profiles)
        self.assertIn("amd-soc15", profiles)
        self.assertIn("amd-field-macros", profiles)
        self.assertIn("amdgv-mxgpu-context", profiles)
        self.assertIn("python-hw-symbols", profiles)
        self.assertGreaterEqual(len(profiles), 9)
        self.assertIn("RREG32", profiles["initial"].wrappers)
        self.assertIn("WREG32_SOC15", profiles["linux-amdgpu"].wrappers)
        self.assertEqual(profiles["toy-python"].language, "python")
        self.assertGreaterEqual(len(profiles["linux-amdgpu"].wrappers), 20)
        self.assertGreaterEqual(len(profiles["amd-mxgpu"].wrappers), 16)
        self.assertIn("SOC15_REG_ENTRY", profiles["linux-amdgpu"].wrappers)
        self.assertIn("WREG32_FIELD15_PREREG", profiles["linux-amdgpu"].wrappers)
        self.assertIn("WREG32_P", profiles["amd-mxgpu"].wrappers)
        self.assertIn("RREG32_PCIE", profiles["amd-mxgpu"].wrappers)
        for profile_id, profile in profiles.items():
            if profile.language in {"c", "cpp", "c++"}:
                with self.subTest(profile_id=profile_id):
                    self.assertIn("reg", profile.symbol_prefixes)
                    self.assertIn("mm", profile.symbol_prefixes)
                    self.assertIn("smn", profile.symbol_prefixes)

    def test_committed_resolver_operators_are_not_graph_entities(self):
        profiles = load_resolver_profiles(REPO_ROOT / "configs/resolvers")

        operators = {
            operator
            for profile in profiles.values()
            for operator in [*profile.wrappers.keys(), *profile.python_extractors]
        }

        self.assertIn("AMDGV_WRITE_REG", operators)
        self.assertIn("gpu_register", operators)
        for operator in operators:
            with self.subTest(operator=operator):
                self.assertTrue(is_resolver_wrapper_name(operator))
                self.assertFalse(is_graph_entity_endpoint(operator))

    def test_resolves_soc15_register_from_configured_wrapper(self):
        profiles = load_resolver_profiles(REPO_ROOT / "configs/resolvers")

        resolved = resolve_cpp_register_call(
            "WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp);",
            profiles["linux-amdgpu"],
        )

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.profile_id, "linux-amdgpu")
        self.assertEqual(resolved.wrapper, "WREG32_SOC15")
        self.assertEqual(resolved.symbol, "GCVM_L2_CNTL")
        self.assertEqual(resolved.symbol_argument, 2)

    def test_resolves_common_mm_and_smn_register_prefixes(self):
        profiles = load_resolver_profiles(REPO_ROOT / "configs/resolvers")

        cases = [
            ("WREG32(mmGCVM_L2_CNTL, tmp);", "GCVM_L2_CNTL"),
            ("WREG32(smnGCVM_L2_CNTL, tmp);", "GCVM_L2_CNTL"),
        ]

        for source, expected_symbol in cases:
            with self.subTest(source=source):
                resolved = resolve_cpp_register_call(source, profiles["linux-amdgpu"])
                self.assertIsNotNone(resolved)
                self.assertEqual(resolved.symbol, expected_symbol)

    def test_resolves_previous_amdgpu_and_mxgpu_wrapper_cases(self):
        profiles = load_resolver_profiles(REPO_ROOT / "configs/resolvers")

        cases = [
            ("linux-amdgpu", "SOC15_REG_OFFSET(GC, 0, regGCVM_L2_CNTL)", "GCVM_L2_CNTL", "address"),
            ("linux-amdgpu", "SOC15_REG_ENTRY(GC, 0, regCP_INT_CNTL_RING0)", "CP_INT_CNTL_RING0", "address"),
            ("linux-amdgpu", "WREG32_FIELD15(GC, 0, CP_INT_CNTL_RING0, CNTX_BUSY_INT_ENABLE, 1)", "CP_INT_CNTL_RING0", "field_write"),
            ("linux-amdgpu", "WREG32_SOC15_IP(GC, 0, regGRBM_SOFT_RESET, value)", "GRBM_SOFT_RESET", "write"),
            ("amd-mxgpu", "WREG32_P(regIH_RB_CNTL, value, 0xffffffff)", "IH_RB_CNTL", "write"),
            ("amd-mxgpu", "RREG32_PCIE(regBIF_DOORBELL_INT_CNTL)", "BIF_DOORBELL_INT_CNTL", "read"),
            ("amd-mxgpu", "WREG32_FIELD(RB_ENABLE, ENABLE_INTR, 1)", "RB_ENABLE", "field_write"),
        ]

        for profile_id, source, expected_symbol, expected_access in cases:
            with self.subTest(profile_id=profile_id, source=source):
                resolved = resolve_cpp_register_call(source, profiles[profile_id])
                self.assertIsNotNone(resolved)
                self.assertEqual(resolved.symbol, expected_symbol)
                self.assertEqual(resolved.access, expected_access)

    def test_resolves_multiple_symbols_from_field_macro_and_multiple_calls(self):
        profiles = load_resolver_profiles(REPO_ROOT / "configs/resolvers")

        resolved = resolve_cpp_register_calls(
            """
            tmp = REG_SET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE, 1);
            WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp);
            """,
            profiles["linux-amdgpu"],
        )

        symbols = {(item.wrapper, item.symbol, item.access) for item in resolved}
        self.assertIn(("REG_SET_FIELD", "GCVM_L2_CNTL", "field_set"), symbols)
        field_set = next(item for item in resolved if item.wrapper == "REG_SET_FIELD")
        self.assertEqual(field_set.field_symbol, "ENABLE_L2_CACHE")
        self.assertIn(("WREG32_SOC15", "GCVM_L2_CNTL", "write"), symbols)

    def test_resolves_nested_address_macro_as_outer_write_symbol(self):
        profiles = load_resolver_profiles(REPO_ROOT / "configs/resolvers")

        resolved = resolve_cpp_register_calls(
            "WREG32(SOC15_REG_OFFSET(GC, 0, regGCVM_L2_CNTL), value);",
            profiles["linux-amdgpu"],
        )

        symbols = {(item.wrapper, item.symbol, item.access) for item in resolved}
        self.assertIn(("WREG32", "GCVM_L2_CNTL", "write"), symbols)
        self.assertIn(("SOC15_REG_OFFSET", "GCVM_L2_CNTL", "address"), symbols)

    def test_wrapper_addition_works_without_code_change(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            profile_dir = Path(tmpdir)
            (profile_dir / "custom.yaml").write_text(
                textwrap.dedent(
                    """
                    id: custom
                    language: cpp
                    context_vars: [adev]
                    symbol_prefixes: [reg, mm]
                    wrappers:
                      CUSTOM_WRITE:
                        symbol_arg: 0
                        access: write
                    """
                ).strip(),
                encoding="utf-8",
            )
            profiles = load_resolver_profiles(profile_dir)

        resolved = resolve_cpp_register_call("CUSTOM_WRITE(mmCP_INT_CNTL_RING0, value);", profiles["custom"])

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.wrapper, "CUSTOM_WRITE")
        self.assertEqual(resolved.symbol, "CP_INT_CNTL_RING0")

    def test_toy_python_profile_extracts_configured_string_symbol(self):
        profiles = load_resolver_profiles(REPO_ROOT / "configs/resolvers")

        resolved = resolve_python_symbol('@gpu_register("SDMA0_QUEUE0_RB_CNTL")', profiles["toy-python"])

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.profile_id, "toy-python")
        self.assertEqual(resolved.symbol, "SDMA0_QUEUE0_RB_CNTL")

    def test_python_hw_symbols_profile_extracts_non_macro_calls(self):
        profiles = load_resolver_profiles(REPO_ROOT / "configs/resolvers")

        resolved = resolve_python_symbol('field_ref("ENABLE_L2_CACHE")', profiles["python-hw-symbols"])

        self.assertIsNotNone(resolved)
        self.assertEqual(resolved.profile_id, "python-hw-symbols")
        self.assertEqual(resolved.symbol, "ENABLE_L2_CACHE")


if __name__ == "__main__":
    unittest.main()
