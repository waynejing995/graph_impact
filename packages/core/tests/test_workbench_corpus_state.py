import sqlite3
import tempfile
import unittest
from pathlib import Path

from asip.storage import AsipStore
from asip.workbench import add_corpus, get_job, index_registered_corpora, list_indexed_corpora, list_jobs, query_evidence


class WorkbenchCorpusStateTests(unittest.TestCase):
    def test_add_corpus_persists_backend_state(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"

            added = add_corpus(
                db_path,
                corpus_id="local-amd-docs",
                repo="local",
                source_root="/docs/amd",
                include=["**/*.md", "**/*.pdf"],
                corpus_type="doc",
            )
            corpora = list_indexed_corpora(db_path)

            self.assertEqual(added["status"], "not_indexed")
            self.assertEqual(corpora[0]["id"], "local-amd-docs")
            self.assertEqual(corpora[0]["include"], ["**/*.md", "**/*.pdf"])
            self.assertEqual(corpora[0]["metadata"]["type"], "doc")

    def test_registered_corpus_indexes_multiple_subfolder_filters(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            source_root = root / "linux"
            amdgpu_root = source_root / "drivers/gpu/drm/amd/amdgpu"
            asic_reg_root = source_root / "drivers/gpu/drm/amd/include/asic_reg"
            display_root = source_root / "drivers/gpu/drm/amd/display"
            amdgpu_root.mkdir(parents=True)
            asic_reg_root.mkdir(parents=True)
            display_root.mkdir(parents=True)
            (amdgpu_root / "gfx.c").write_text("void program(void) { WREG32(regGCVM_L2_CNTL, 1); }\n", encoding="utf-8")
            (asic_reg_root / "gc_11_0_0_offset.h").write_text("#define regHEADER_ONLY_REGISTER 0x1234\n", encoding="utf-8")
            (display_root / "display.c").write_text("void display(void) { WREG32(regDISPLAY_ONLY_REGISTER, 1); }\n", encoding="utf-8")

            add_corpus(
                db_path,
                corpus_id="linux-amdgpu",
                repo="local",
                source_root=str(source_root),
                include=["**/*.c"],
                corpus_type="code",
                subfolders=[
                    {"relative_root": "drivers/gpu/drm/amd/amdgpu", "include": ["**/*.c"]},
                    {"relative_root": "drivers/gpu/drm/amd/include/asic_reg", "include": ["**/*.h"]},
                ],
            )
            summary = index_registered_corpora(db_path, corpus_ids=["linux-amdgpu"])
            corpora = list_indexed_corpora(db_path)
            con = sqlite3.connect(db_path)
            paths = {row[0] for row in con.execute("select path from documents order by path")}

            self.assertEqual(summary["files"], 2)
            self.assertEqual(corpora[0]["metadata"]["subfolders"][0]["relative_root"], "drivers/gpu/drm/amd/amdgpu")
            self.assertIn("drivers/gpu/drm/amd/amdgpu/gfx.c", paths)
            self.assertIn("drivers/gpu/drm/amd/include/asic_reg/gc_11_0_0_offset.h", paths)
            self.assertNotIn("drivers/gpu/drm/amd/display/display.c", paths)

    def test_registered_corpus_accepts_camel_case_subfolder_filters_without_repo_wide_scan(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            source_root = root / "linux"
            amdgpu_root = source_root / "drivers/gpu/drm/amd/amdgpu"
            display_root = source_root / "drivers/gpu/drm/amd/display"
            amdgpu_root.mkdir(parents=True)
            display_root.mkdir(parents=True)
            (amdgpu_root / "gfx.c").write_text("void program(void) { WREG32(regGCVM_L2_CNTL, 1); }\n", encoding="utf-8")
            (display_root / "display.c").write_text("void display(void) { WREG32(regDISPLAY_ONLY_REGISTER, 1); }\n", encoding="utf-8")

            add_corpus(
                db_path,
                corpus_id="linux-amdgpu",
                repo="local",
                source_root=str(source_root),
                include=["**/*.c"],
                corpus_type="code",
                subfolders=[
                    {"relativeRoot": "drivers/gpu/drm/amd/amdgpu", "include": ["**/*.c"]},
                ],
            )
            summary = index_registered_corpora(db_path, corpus_ids=["linux-amdgpu"])
            con = sqlite3.connect(db_path)
            paths = {row[0] for row in con.execute("select path from documents order by path")}

            self.assertEqual(summary["files"], 1)
            self.assertIn("drivers/gpu/drm/amd/amdgpu/gfx.c", paths)
            self.assertNotIn("drivers/gpu/drm/amd/display/display.c", paths)

    def test_registered_corpus_rejects_subfolder_filters_outside_source_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            source_root = root / "linux"
            source_root.mkdir()

            with self.assertRaises(ValueError) as parent_path:
                add_corpus(
                    db_path,
                    corpus_id="linux-parent-escape",
                    repo="local",
                    source_root=str(source_root),
                    include=["**/*.c"],
                    subfolders=["../outside:**/*.c"],
                )
            self.assertIn("repo-relative", str(parent_path.exception))

            with self.assertRaises(ValueError) as absolute_path:
                add_corpus(
                    db_path,
                    corpus_id="linux-absolute-escape",
                    repo="local",
                    source_root=str(source_root),
                    include=["**/*.c"],
                    subfolders=[{"relative_root": str(root / "outside"), "include": ["**/*.c"]}],
                )
            self.assertIn("repo-relative", str(absolute_path.exception))

            with self.assertRaises(ValueError) as missing_root:
                add_corpus(
                    db_path,
                    corpus_id="linux-missing-subfolder-root",
                    repo="local",
                    source_root=str(source_root),
                    include=["**/*.c"],
                    subfolders=[{"include": ["**/*.c"]}],
                )
            self.assertIn("repo-relative", str(missing_root.exception))

    def test_registered_doc_and_pdf_corpus_indexes_plain_text_as_queryable_evidence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            corpus_root = root / "corpus"
            rst_path = corpus_root / "Documentation/gpu/amdgpu.rst"
            pdf_path = corpus_root / "docs/architecture.pdf"
            rst_path.parent.mkdir(parents=True)
            pdf_path.parent.mkdir(parents=True)
            rst_path.write_text(
                "amdgpu documentation connects to driver source tree",
                encoding="utf-8",
            )
            pdf_path.write_text(
                "%PDF-1.4\n"
                "BT\n"
                "(amdgpu documentation connects to driver source tree) Tj\n"
                "ET\n",
                encoding="latin-1",
            )

            add_corpus(
                db_path,
                corpus_id="registered-amdgpu-docs",
                repo="local",
                source_root=str(corpus_root),
                include=["**/*.rst", "**/*.pdf"],
                corpus_type="doc",
            )
            index_registered_corpora(db_path, corpus_ids=["registered-amdgpu-docs"])

            result = query_evidence(db_path, "amdgpu documentation driver source tree")
            source_types = {row["source_type"] for row in result["rows"]}

            self.assertFalse(result["empty"], result)
            self.assertIn("doc", source_types)
            self.assertIn("pdf", source_types)

    def test_index_job_lifecycle_persists_queued_indexing_and_succeeded_events(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            corpus_root = root / "corpus"
            note_path = corpus_root / "docs" / "note.md"
            note_path.parent.mkdir(parents=True)
            note_path.write_text("LOCAL_JOB_LIFECYCLE_REGISTER is documented here.", encoding="utf-8")

            add_corpus(
                db_path,
                corpus_id="job-docs",
                repo="local",
                source_root=str(corpus_root),
                include=["**/*.md"],
                corpus_type="doc",
            )

            summary = index_registered_corpora(db_path, corpus_ids=["job-docs"])
            job = get_job(db_path, int(summary["job_id"]))
            jobs = list_jobs(db_path)

            self.assertEqual(summary["job_status"], "succeeded")
            self.assertEqual(job["status"], "succeeded")
            self.assertEqual(job["metadata"]["result_status"], "indexed")
            self.assertEqual([event["status"] for event in job["events"]], ["queued", "indexing", "succeeded"])
            self.assertEqual(jobs[0]["id"], summary["job_id"])
            self.assertEqual([event["status"] for event in jobs[0]["events"]], ["queued", "indexing", "succeeded"])

    def test_legacy_success_job_status_reads_as_canonical_lifecycle_with_result_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"
            store = AsipStore.connect(str(db_path))
            store.migrate()
            store.con.execute(
                """
                insert into jobs(kind, status, message, metadata_json, started_at, finished_at)
                values ('index', 'indexed', 'Indexed 1 documents', '{}', '2026-05-17 16:00:00', '2026-05-17 16:00:01')
                """
            )
            store.con.commit()

            job = get_job(db_path, 1)
            jobs = list_jobs(db_path)

            self.assertEqual(job["status"], "succeeded")
            self.assertEqual(job["metadata"]["result_status"], "indexed")
            self.assertEqual([event["status"] for event in job["events"]], ["succeeded"])
            self.assertEqual(jobs[0]["status"], "succeeded")
            self.assertEqual([event["status"] for event in jobs[0]["events"]], ["succeeded"])

    def test_missing_registered_corpus_root_fails_index_and_marks_status_failed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            missing_root = root / "missing-corpus"

            add_corpus(
                db_path,
                corpus_id="missing-docs",
                repo="local",
                source_root=str(missing_root),
                include=["**/*.md"],
                corpus_type="doc",
            )

            with self.assertRaises(FileNotFoundError):
                index_registered_corpora(db_path, corpus_ids=["missing-docs"])

            corpora = list_indexed_corpora(db_path)
            missing = next(corpus for corpus in corpora if corpus["id"] == "missing-docs")
            self.assertEqual(missing["status"], "failed")
            self.assertEqual(missing["file_count"], 0)
            self.assertIn("source root not found", missing["metadata"]["error"])

    def test_unknown_registered_corpus_id_fails_instead_of_indexed_zero_docs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            corpus_root = root / "corpus"
            corpus_root.mkdir()

            add_corpus(
                db_path,
                corpus_id="known-docs",
                repo="local",
                source_root=str(corpus_root),
                include=["**/*.md"],
                corpus_type="doc",
            )

            with self.assertRaises(ValueError) as raised:
                index_registered_corpora(db_path, corpus_ids=["missing-docs"])

            self.assertIn("unknown corpus id", str(raised.exception))
            con = sqlite3.connect(db_path)
            self.assertEqual(con.execute("select status from jobs order by id desc limit 1").fetchone()[0], "failed")


if __name__ == "__main__":
    unittest.main()
