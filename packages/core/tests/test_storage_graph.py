import sqlite3
import importlib.util
import unittest

from asip.storage import AsipStore


class StorageGraphTests(unittest.TestCase):
    def test_sqlite_fts5_indexes_and_queries_evidence_chunks(self):
        store = AsipStore.connect(":memory:")
        store.migrate()

        document_id = store.add_document(
            corpus_id="mxgpu",
            source_type="code",
            path="libgv/core/hw/navi3/gfx_v11_0.c",
        )
        store.add_chunk(
            document_id=document_id,
            text="tmp = REG_SET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE, 1);",
            line_start=322,
            line_end=323,
        )

        matches = store.search_text("ENABLE_L2_CACHE")

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["path"], "libgv/core/hw/navi3/gfx_v11_0.c")
        self.assertEqual(matches[0]["line_start"], 322)

    def test_graph_expansion_reads_persisted_edges(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.add_edge("GCVM_L2_CNTL", "ENABLE_L2_CACHE", "has_field", 0.98)
        store.add_edge("gmc_v11_0_init_golden_registers", "GCVM_L2_CNTL", "writes", 0.94)

        neighborhood = store.expand_graph("GCVM_L2_CNTL", hops=1)

        self.assertEqual(
            {edge["src"] for edge in neighborhood["edges"]} | {edge["dst"] for edge in neighborhood["edges"]},
            {"GCVM_L2_CNTL", "ENABLE_L2_CACHE", "gmc_v11_0_init_golden_registers"},
        )
        self.assertEqual(len(neighborhood["edges"]), 2)

    def test_networkx_graph_is_built_from_sqlite_edges(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        store.add_edge("GCVM_L2_CNTL", "ENABLE_L2_CACHE", "has_field", 0.98)
        store.add_edge("gmc_v11_0_init_golden_registers", "GCVM_L2_CNTL", "writes", 0.94)

        graph = store.to_networkx()

        self.assertTrue(graph.has_edge("GCVM_L2_CNTL", "ENABLE_L2_CACHE"))
        self.assertEqual(graph["GCVM_L2_CNTL"]["ENABLE_L2_CACHE"]["relation"], "has_field")

    def test_embedding_vectors_are_queryable_with_sqlite_backed_fallback(self):
        store = AsipStore.connect(":memory:")
        store.migrate()
        document_id = store.add_document("docs", "doc", "Documentation/gpu/amdgpu.rst")
        gc_chunk = store.add_chunk(document_id, "GCVM_L2_CNTL enables L2 cache", 10, 10)
        sdma_chunk = store.add_chunk(document_id, "SDMA queue ring buffer control", 20, 20)
        store.add_embedding(gc_chunk, provider="ollama", model="nomic-embed-text", vector=[1.0, 0.0, 0.0])
        store.add_embedding(sdma_chunk, provider="ollama", model="nomic-embed-text", vector=[0.0, 1.0, 0.0])

        matches = store.search_vector([0.9, 0.1, 0.0], limit=1)

        self.assertEqual(matches[0]["chunk_id"], gc_chunk)
        self.assertGreater(matches[0]["score"], 0.9)

    def test_fts5_extension_is_available_in_runtime_sqlite(self):
        con = sqlite3.connect(":memory:")
        con.execute("create virtual table chunks_fts using fts5(text)")
        con.execute("insert into chunks_fts(text) values (?)", ("GCVM_L2_CNTL ENABLE_L2_CACHE",))

        rows = list(con.execute("select text from chunks_fts where chunks_fts match 'ENABLE_L2_CACHE'"))

        self.assertEqual(rows, [("GCVM_L2_CNTL ENABLE_L2_CACHE",)])

    def test_sqlite_vec_extension_can_run_when_runtime_supports_extensions(self):
        if importlib.util.find_spec("sqlite_vec") is None:
            self.skipTest("sqlite_vec package is not installed in this Python runtime")
        con = sqlite3.connect(":memory:")
        if not hasattr(con, "enable_load_extension"):
            self.skipTest("this sqlite3 build cannot load extensions")

        import sqlite_vec

        con.enable_load_extension(True)
        sqlite_vec.load(con)
        con.execute("create virtual table vec_items using vec0(embedding float[3])")
        con.execute("insert into vec_items(rowid, embedding) values (?, ?)", (1, sqlite_vec.serialize_float32([1, 0, 0])))
        con.execute("insert into vec_items(rowid, embedding) values (?, ?)", (2, sqlite_vec.serialize_float32([0, 1, 0])))

        rows = list(
            con.execute(
                "select rowid from vec_items where embedding match ? order by distance limit 1",
                (sqlite_vec.serialize_float32([0.9, 0.1, 0]),),
            )
        )

        self.assertEqual(rows, [(1,)])


if __name__ == "__main__":
    unittest.main()
