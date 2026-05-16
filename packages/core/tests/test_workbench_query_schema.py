import tempfile
import unittest
from pathlib import Path

from asip import workbench
from asip.storage import AsipStore
from asip.workbench import index_configured_corpora, query_evidence

from workbench_fixture import write_live_fixture


REQUIRED_EVIDENCE_FIELDS = {
    "id",
    "source_type",
    "repo",
    "path",
    "line_start",
    "line_end",
    "symbol",
    "entity_type",
    "ip_block",
    "asic_or_generation",
    "access_type",
    "confidence",
    "snippet",
    "resolved_chain",
}


class WorkbenchQuerySchemaTests(unittest.TestCase):
    def test_query_rows_include_mvp_evidence_schema_and_empty_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            config_path, _corpus_root = write_live_fixture(root)
            db_path = root / "asip.db"
            index_configured_corpora(config_path, db_path)

            matched = query_evidence(db_path, "doorbell interrupt disable")
            no_match = query_evidence(db_path, "totally absent symbol")

            self.assertFalse(matched["empty"])
            for row in matched["rows"]:
                self.assertTrue(REQUIRED_EVIDENCE_FIELDS.issubset(row.keys()), row)
            self.assertTrue(no_match["empty"])
            self.assertEqual(no_match["rows"], [])
            self.assertIn("No evidence matched", no_match["empty_state"])

    def test_query_can_filter_evidence_by_ip_block_and_asic_generation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            document_id = store.add_document("fixture", "code", "driver.c")
            cp_chunk = store.add_chunk(document_id, "CP_INT_CNTL_RING0 CNTX_BUSY_INT_ENABLE", 1, 1)
            sdma_chunk = store.add_chunk(document_id, "CP_INT_CNTL_RING0 shadow copy", 2, 2)
            store.add_evidence(
                cp_chunk,
                "fixture",
                "code",
                "local",
                "driver.c",
                "CP_INT_CNTL_RING0",
                "register",
                "field_set",
                0.95,
                "CP_INT_CNTL_RING0 CNTX_BUSY_INT_ENABLE",
                "source mention -> CP_INT_CNTL_RING0",
                line_start=1,
                line_end=1,
                ip_block="CP",
                asic_or_generation="gfx1100",
            )
            store.add_evidence(
                sdma_chunk,
                "fixture",
                "code",
                "local",
                "driver.c",
                "CP_INT_CNTL_RING0",
                "register",
                "mention",
                0.75,
                "CP_INT_CNTL_RING0 shadow copy",
                "source mention -> CP_INT_CNTL_RING0",
                line_start=2,
                line_end=2,
                ip_block="SDMA",
                asic_or_generation="gfx900",
            )

            filtered = query_evidence(
                db_path,
                "CP_INT_CNTL_RING0",
                ip_block="CP",
                asic_or_generation="gfx1100",
            )

            self.assertEqual(len(filtered["rows"]), 1)
            self.assertEqual(filtered["rows"][0]["ip_block"], "CP")
            self.assertEqual(filtered["rows"][0]["asic_or_generation"], "gfx1100")

    def test_query_evidence_merges_vector_backed_evidence_without_lexical_overlap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            document_id = store.add_document("fixture", "doc", "docs/alpha-notes.md")
            chunk_id = store.add_chunk(document_id, "alpha beta gamma hardware timing note", 4, 4)
            store.add_evidence(
                chunk_id,
                "fixture",
                "doc",
                "local",
                "docs/alpha-notes.md",
                "REG_ALPHA_STATUS",
                "register",
                "mention",
                0.71,
                "alpha beta gamma hardware timing note",
                "source mention -> REG_ALPHA_STATUS",
                line_start=4,
                line_end=4,
            )
            store.add_embedding(
                chunk_id,
                provider="test",
                model="unit-vector",
                vector=[1.0, 0.0, 0.0],
            )
            original_embedding = workbench._deterministic_embedding
            workbench._deterministic_embedding = lambda text: [1.0, 0.0, 0.0]
            try:
                result = query_evidence(db_path, "semantic nearest lookup")
            finally:
                workbench._deterministic_embedding = original_embedding

            self.assertFalse(result["empty"])
            self.assertEqual(result["rows"][0]["symbol"], "REG_ALPHA_STATUS")
            sources = result["rows"][0].get("retrieval_sources", [])
            sources_text = (
                sources.lower()
                if isinstance(sources, str)
                else " ".join(str(source).lower() for source in sources)
            )
            self.assertTrue("vector_score" in result["rows"][0] or "vector" in sources_text, result["rows"][0])

    def test_documentation_queries_preserve_matching_doc_rows_when_code_scores_dominate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            code_document_id = store.add_document("fixture", "code", "drivers/gpu/drm/amd/amdgpu/amdgpu.h")
            for index in range(12):
                chunk_id = store.add_chunk(
                    code_document_id,
                    f"AMDGPU_DRIVER_SOURCE_TREE_{index} driver source tree token-heavy code row",
                    index + 1,
                    index + 1,
                )
                store.add_evidence(
                    chunk_id,
                    "fixture",
                    "code",
                    "local",
                    "drivers/gpu/drm/amd/amdgpu/amdgpu.h",
                    f"AMDGPU_DRIVER_SOURCE_TREE_{index}",
                    "register",
                    "mention",
                    0.95,
                    f"AMDGPU_DRIVER_SOURCE_TREE_{index} driver source tree token-heavy code row",
                    f"source mention -> AMDGPU_DRIVER_SOURCE_TREE_{index}",
                    line_start=index + 1,
                    line_end=index + 1,
                )
            doc_document_id = store.add_document("fixture", "doc", "docs/amdgpu-driver-overview.md")
            doc_chunk_id = store.add_chunk(
                doc_document_id,
                "AMDGPU documentation connects the driver source tree to scheduling behavior.",
                1,
                1,
            )
            store.add_evidence(
                doc_chunk_id,
                "fixture",
                "doc",
                "local",
                "docs/amdgpu-driver-overview.md",
                "amdgpu-driver-overview.md",
                "doc_section",
                "mention",
                0.8,
                "AMDGPU documentation connects the driver source tree to scheduling behavior.",
                "doc chunk -> amdgpu-driver-overview.md",
                line_start=1,
                line_end=1,
            )

            result = query_evidence(db_path, "amdgpu documentation driver source tree", limit=5)

            self.assertIn("doc", {row["source_type"] for row in result["rows"]})
            self.assertLessEqual(len(result["rows"]), 5)

    def test_register_queries_preserve_matching_register_header_rows_when_code_scores_dominate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            code_document_id = store.add_document("fixture", "code", "drivers/gpu/drm/amd/amdgpu/gfx_v11_0.c")
            for index in range(12):
                chunk_id = store.add_chunk(
                    code_document_id,
                    f"regGCVM_L2_CNTL ENABLE_L2_CACHE generated code row {index}",
                    index + 1,
                    index + 1,
                )
                store.add_evidence(
                    chunk_id,
                    "fixture",
                    "code",
                    "local",
                    "drivers/gpu/drm/amd/amdgpu/gfx_v11_0.c",
                    f"GCVM_L2_CNTL_CODE_{index}",
                    "register",
                    "write",
                    0.95,
                    f"regGCVM_L2_CNTL ENABLE_L2_CACHE generated code row {index}",
                    f"write wrapper -> GCVM_L2_CNTL_CODE_{index}",
                    line_start=index + 1,
                    line_end=index + 1,
                )
            register_document_id = store.add_document("fixture", "register", "include/asic_reg/gc_11_0_0_offset.h")
            register_chunk_id = store.add_chunk(
                register_document_id,
                "#define regGCVM_L2_CNTL 0x1430\n#define GCVM_L2_CNTL_BASE_IDX 0",
                1,
                2,
            )
            store.add_evidence(
                register_chunk_id,
                "fixture",
                "register",
                "local",
                "include/asic_reg/gc_11_0_0_offset.h",
                "regGCVM_L2_CNTL",
                "register",
                "mention",
                0.8,
                "#define regGCVM_L2_CNTL 0x1430",
                "register header -> regGCVM_L2_CNTL",
                line_start=1,
                line_end=2,
            )

            result = query_evidence(db_path, "regGCVM_L2_CNTL ENABLE_L2_CACHE", limit=5)

            self.assertIn("register", {row["source_type"] for row in result["rows"]})
            self.assertLessEqual(len(result["rows"]), 5)

    def test_diverse_selection_preserves_multiple_injected_source_types(self):
        rows = [
            {"id": index, "source_type": "code", "rank_score": 10 - index}
            for index in range(1, 6)
        ] + [
            {"id": 6, "source_type": "register", "rank_score": 1},
            {"id": 7, "source_type": "doc", "rank_score": 1},
        ]

        selected = workbench._select_diverse_rows(rows, limit=5)

        source_types = {row["source_type"] for row in selected}
        self.assertIn("register", source_types)
        self.assertIn("doc", source_types)
        self.assertLessEqual(len(selected), 5)

    def test_query_diverse_selection_preserves_multiple_injected_source_types(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            code_document_id = store.add_document("fixture", "code", "driver.c")
            for index in range(12):
                chunk_id = store.add_chunk(
                    code_document_id,
                    f"GCVM_L2_CNTL macro expansion code row {index}",
                    index + 1,
                    index + 1,
                )
                store.add_evidence(
                    chunk_id,
                    "fixture",
                    "code",
                    "local",
                    "driver.c",
                    f"GCVM_CODE_{index}",
                    "register",
                    "write",
                    0.95,
                    f"GCVM_L2_CNTL macro expansion code row {index}",
                    f"write wrapper -> GCVM_CODE_{index}",
                    line_start=index + 1,
                    line_end=index + 1,
                )
            register_document_id = store.add_document("fixture", "register", "asic_reg/gc_offset.h")
            register_chunk_id = store.add_chunk(register_document_id, "#define regGCVM_L2_CNTL 0x1430", 1, 1)
            store.add_evidence(
                register_chunk_id,
                "fixture",
                "register",
                "local",
                "asic_reg/gc_offset.h",
                "regGCVM_L2_CNTL",
                "register",
                "mention",
                0.8,
                "#define regGCVM_L2_CNTL 0x1430",
                "register header -> regGCVM_L2_CNTL",
                line_start=1,
                line_end=1,
            )
            doc_document_id = store.add_document("fixture", "doc", "docs/register-macros.md")
            doc_chunk_id = store.add_chunk(doc_document_id, "GCVM_L2_CNTL macro expansion documentation", 1, 1)
            store.add_evidence(
                doc_chunk_id,
                "fixture",
                "doc",
                "local",
                "docs/register-macros.md",
                "register-macros.md",
                "doc_section",
                "mention",
                0.8,
                "GCVM_L2_CNTL macro expansion documentation",
                "doc chunk -> register-macros.md",
                line_start=1,
                line_end=1,
            )

            result = query_evidence(db_path, "GCVM_L2_CNTL macro expansion", limit=5)

            source_types = {row["source_type"] for row in result["rows"]}
            self.assertIn("register", source_types)
            self.assertIn("doc", source_types)
            self.assertLessEqual(len(result["rows"]), 5)


if __name__ == "__main__":
    unittest.main()
