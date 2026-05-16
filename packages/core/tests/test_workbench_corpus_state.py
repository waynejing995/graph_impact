import sqlite3
import tempfile
import unittest
from pathlib import Path

from asip.workbench import add_corpus, index_registered_corpora, list_indexed_corpora, query_evidence


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
