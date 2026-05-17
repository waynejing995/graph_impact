import sqlite3
import tempfile
import unittest
from pathlib import Path

from asip.index_artifacts import index_full_corpus_run


REPO_ROOT = Path(__file__).resolve().parents[3]
RUN_PATH = REPO_ROOT / "docs/qa/2026-05-16-full-corpus-edge-generation-qwen35-strict-batch1.json"


class IndexArtifactsTests(unittest.TestCase):
    def test_indexes_full_corpus_run_into_sqlite(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "asip.db"

            summary = index_full_corpus_run(RUN_PATH, db_path)

            self.assertEqual(summary["documents"], 5)
            self.assertEqual(summary["chunks"], 9)
            self.assertEqual(summary["edges"], 13)
            con = sqlite3.connect(db_path)
            search_rows = list(
                con.execute(
                    """
                    select chunks.text
                    from chunks_fts
                    join chunks on chunks.id = chunks_fts.rowid
                    where chunks_fts match 'ENABLE_L2_CACHE'
                    """
                )
            )
            edge_rows = list(con.execute("select relation from edges where relation = 'sets_field'"))
            wrapper_rows = list(
                con.execute(
                    """
                    select src, dst
                    from edges
                    where src like 'WREG%' or dst like 'WREG%' or src like 'RREG%' or dst like 'RREG%'
                    """
                )
            )

            self.assertTrue(search_rows)
            self.assertTrue(edge_rows)
            self.assertEqual(wrapper_rows, [])


if __name__ == "__main__":
    unittest.main()
