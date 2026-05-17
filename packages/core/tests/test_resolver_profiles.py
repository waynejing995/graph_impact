import tempfile
import textwrap
import unittest
from pathlib import Path

from asip.resolver_profiles import (
    load_resolver_profiles,
    resolve_cpp_register_call,
    resolve_python_symbol,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


class ResolverProfileTests(unittest.TestCase):
    def test_loads_committed_resolver_profiles(self):
        profiles = load_resolver_profiles(REPO_ROOT / "configs/resolvers")

        self.assertIn("linux-amdgpu", profiles)
        self.assertIn("amd-mxgpu", profiles)
        self.assertIn("initial", profiles)
        self.assertIn("toy-python", profiles)
        self.assertIn("RREG32", profiles["initial"].wrappers)
        self.assertIn("WREG32_SOC15", profiles["linux-amdgpu"].wrappers)
        self.assertEqual(profiles["toy-python"].language, "python")

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


if __name__ == "__main__":
    unittest.main()
