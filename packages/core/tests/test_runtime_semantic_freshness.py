import json
import tempfile
import unittest
from pathlib import Path

from asip.cli import main as cli_main
from asip.runtime_semantic_freshness import run_runtime_semantic_freshness_qa
from asip.storage import AsipStore


class RuntimeSemanticFreshnessTests(unittest.TestCase):
    def test_runtime_semantic_freshness_artifact_binds_current_jobs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            job_ids = self._write_runtime_semantic_db(db_path)
            output_json = root / "runtime-semantic.json"

            payload = run_runtime_semantic_freshness_qa(db_path, output_json=output_json)

            self.assertEqual(payload["gate_status"], "pass")
            self.assertEqual(payload["latest_index_job_id"], job_ids["index"])
            self.assertEqual(payload["latest_graph_rebuild_job_id"], job_ids["graph"])
            self.assertEqual(payload["latest_semantic_edges_job_id"], job_ids["semantic"])
            self.assertEqual(payload["latest_doc_nodes_job_id"], job_ids["doc_nodes"])
            self.assertEqual(payload["latest_blackbox_profiles_job_id"], job_ids["blackbox"])
            self.assertEqual(
                payload["db_semantic_edge_counts"],
                {"blackbox_profiles": 1, "doc_nodes": 1, "semantic_edges": 1},
            )
            self.assertGreater(payload["query_graph_probe"]["row_count"], 0)
            self.assertGreater(
                payload["query_graph_probe"]["stage_counts"].get("semantic", 0)
                + payload["query_graph_probe"]["stage_counts"].get("mixed", 0),
                0,
            )
            self.assertTrue(output_json.exists())
            self.assertEqual(json.loads(output_json.read_text(encoding="utf-8"))["source"], "asip.runtime_semantic_freshness_qa")

    def test_runtime_semantic_freshness_cli_writes_current_artifact(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            db_path = root / "asip.db"
            self._write_runtime_semantic_db(db_path)
            output_json = root / "cli-runtime-semantic.json"

            exit_code = cli_main([
                "runtime-semantic-freshness",
                "--db",
                str(db_path),
                "--output-json",
                str(output_json),
            ])

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["gate_status"], "pass")
            self.assertEqual(payload["source"], "asip.runtime_semantic_freshness_qa")

    def _write_runtime_semantic_db(self, db_path: Path) -> dict[str, int]:
        store = AsipStore.connect(str(db_path))
        store.migrate()
        settings = {"edge": {"provider": "ollama", "model": "gemma4:e4b"}}
        store.save_provider_settings(settings)
        index_job = store.start_job("index", "indexed corpus")
        store.finish_job(index_job, "indexed", "indexed corpus")
        graph_job = store.start_job("graph_rebuild", "rebuilt deterministic graph")
        store.finish_job(graph_job, "rebuilt", "rebuilt deterministic graph")
        semantic_job = store.start_job(
            "semantic_edges_batch",
            "generated fresh semantic edges",
            metadata={"provider_settings": settings},
        )
        store.finish_job(semantic_job, "generated", "generated fresh semantic edges")
        doc_node_job = store.start_job(
            "doc_nodes_batch",
            "generated fresh doc-node edges",
            metadata={"provider_settings": settings},
        )
        store.finish_job(doc_node_job, "generated", "generated fresh doc-node edges")
        blackbox_job = store.start_job(
            "blackbox_profiles_batch",
            "generated fresh blackbox profiles",
            metadata={"provider_settings": settings},
        )
        store.finish_job(blackbox_job, "generated", "generated fresh blackbox profiles")
        document_id = store.add_document("linux-amdgpu", "code", "drivers/gpu/drm/amd/amdgpu/gfx.c")
        chunk_id = store.add_chunk(
            document_id,
            "void gfx_v10_0_program_cache(void) { WREG32(GCVM_L2_CNTL, 1); }",
            10,
            10,
        )
        store.add_evidence(
            chunk_id,
            "linux-amdgpu",
            "code",
            "linux",
            "drivers/gpu/drm/amd/amdgpu/gfx.c",
            "GCVM_L2_CNTL",
            "register",
            "write",
            0.95,
            "WREG32(GCVM_L2_CNTL, 1)",
            "gfx_v10_0_program_cache writes GCVM_L2_CNTL",
            line_start=10,
            line_end=10,
        )
        store.add_edge(
            "gfx_v10_0_program_cache",
            "GCVM_L2_CNTL",
            "writes",
            0.95,
            stage="deterministic",
            source="clang_text_spans",
            path="drivers/gpu/drm/amd/amdgpu/gfx.c",
            line_start=10,
            line_end=10,
            provenance={
                "extractor": "code_graph",
                "function": "gfx_v10_0_program_cache",
                "corpus_id": "linux-amdgpu",
                "repo": "linux",
                "path": "drivers/gpu/drm/amd/amdgpu/gfx.c",
                "line_start": 10,
                "line_end": 10,
                "ip": "GC",
                "ip_version": "gfx_v10_0",
            },
        )
        store.add_edge(
            "docs/guide.md#programming-local-registers",
            "GCVM_L2_CNTL",
            "documents_register",
            0.91,
            stage="semantic",
            source="ollama",
            provenance={
                "extractor": "semantic_edges",
                "provider": "ollama",
                "model": "gemma4:e4b",
                "job_id": semantic_job,
            },
        )
        store.add_edge(
            "docs/guide.md#box-cache-policy",
            "GCVM_L2_CNTL",
            "documents_register",
            0.91,
            stage="semantic",
            source="ollama",
            provenance={
                "extractor": "doc_nodes",
                "provider": "ollama",
                "model": "gemma4:e4b",
                "job_id": doc_node_job,
                "box_node_id": "docs/guide.md#box-cache-policy",
            },
        )
        function_id = "function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/gfx.c:gfx_v10_0_program_cache"
        store.add_edge(
            function_id,
            function_id,
            "relates_to",
            0.86,
            stage="semantic",
            source="ollama",
            path="drivers/gpu/drm/amd/amdgpu/gfx.c",
            provenance={
                "extractor": "blackbox_profiles",
                "provider": "ollama",
                "model": "gemma4:e4b",
                "job_id": blackbox_job,
                "batch_id": 1,
                "attempt_id": 1,
                "candidate_id": f"concept:{function_id}",
                "prompt_sha256": "a" * 64,
                "response_sha256": "b" * 64,
                "validator_version": "blackbox_profiles_v1",
                "endpoint_id": function_id,
                "endpoint_kind": "function",
                "function": "gfx_v10_0_program_cache",
                "function_name": "gfx_v10_0_program_cache",
                "corpus_id": "linux-amdgpu",
                "repo": "linux",
                "blackbox": {
                    "method": "blackbox_io",
                    "inputs": ["GCVM_L2_CNTL"],
                    "outputs": ["writes GCVM_L2_CNTL"],
                    "observed_behavior": "writes the L2 control register",
                },
            },
        )
        store.con.close()
        return {
            "index": index_job,
            "graph": graph_job,
            "semantic": semantic_job,
            "doc_nodes": doc_node_job,
            "blackbox": blackbox_job,
        }
