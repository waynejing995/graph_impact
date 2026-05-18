import tempfile
import unittest
from pathlib import Path

from asip.performance_smoke import run_fixture_performance_smoke


class PerformanceSmokeTests(unittest.TestCase):
    def test_fixture_smoke_rebuilds_from_empty_db_twice_and_times_queries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source_root = root / "fixture"
            source_root.mkdir()
            (source_root / "gfx.c").write_text(
                "\n".join(
                    [
                        "static void program_gcvm_l2(void) {",
                        "  WREG32(mmGCVM_L2_CNTL, 1);",
                        "}",
                        "static void program_ih_ring(void) {",
                        "  WREG32(mmIH_RB_CNTL, 2);",
                        "}",
                        "static void program_sdma_queue(void) {",
                        "  WREG32(mmSDMA0_QUEUE0_RB_CNTL, 3);",
                        "}",
                    ]
                ),
                encoding="utf-8",
            )
            (source_root / "guide.md").write_text(
                "\n".join(
                    [
                        "# Fixture guide",
                        "GCVM_L2_CNTL controls the L2 cache path.",
                        "IH_RB_CNTL configures the interrupt ring buffer.",
                        "SDMA0_QUEUE0_RB_CNTL documents queue setup.",
                    ]
                ),
                encoding="utf-8",
            )

            result = run_fixture_performance_smoke(
                root / "fixture-smoke.db",
                source_root=source_root,
                queries=[
                    "GCVM_L2_CNTL",
                    "IH_RB_CNTL",
                    "SDMA0_QUEUE0_RB_CNTL",
                    "program_gcvm_l2",
                    "interrupt ring buffer",
                ],
                max_query_seconds=1.0,
            )

            self.assertEqual(result["source"], "fixture_performance_smoke")
            self.assertTrue(result["deterministic_counts_match"])
            self.assertEqual(len(result["runs"]), 2)
            self.assertEqual(result["runs"][0]["counts"], result["runs"][1]["counts"])
            self.assertGreater(result["runs"][0]["counts"]["documents"], 0)
            self.assertGreater(result["runs"][0]["counts"]["chunks"], 0)
            self.assertGreater(result["runs"][0]["counts"]["evidence"], 0)
            self.assertGreater(result["runs"][0]["counts"]["edges"], 0)
            self.assertEqual(len(result["queries"]), 5)
            self.assertTrue(all(item["row_count"] > 0 for item in result["queries"]))
            self.assertTrue(all(item["elapsed_seconds"] < 1.0 for item in result["queries"]))


if __name__ == "__main__":
    unittest.main()
