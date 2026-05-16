import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from asip import cli
from asip.cli import parse_source_roots
from asip.semantic_edges import (
    FakeEdgeProvider,
    build_prompt,
    load_full_corpus_edge_config,
    load_edge_case_config,
    parse_ollama_json_message,
    normalize_generated_cases,
    run_full_corpus_generation,
    run_generation,
    scan_full_corpus_queries,
)


class SemanticEdgeFeatureTests(unittest.TestCase):
    def test_committed_real_case_config_has_more_than_five_queries(self):
        config = load_edge_case_config(Path("configs/edge_cases/mxgpu-real-qwen35.json"))

        self.assertGreaterEqual(len(config.cases), 6)
        self.assertEqual(config.model.preferred, "qwen3.5:4b")
        self.assertEqual(config.model.fallback, "qwen3.6")

    def test_committed_full_corpus_config_covers_mxgpu_and_linux_amdgpu(self):
        config = load_full_corpus_edge_config(Path("configs/edge_cases/full-corpus-qwen35.json"))

        self.assertEqual(config.model.preferred, "qwen3.5:4b")
        self.assertEqual(config.model.fallback, "qwen3.6")
        self.assertFalse(config.model.think)
        self.assertEqual(config.model.num_predict, 1024)
        self.assertGreaterEqual(config.model.timeout_seconds, 600)
        self.assertGreaterEqual(len(config.queries), 6)
        self.assertEqual({corpus.id for corpus in config.corpora}, {"mxgpu", "linux-amdgpu"})
        self.assertGreaterEqual(
            len([query for query in config.queries if query.corpus == "mxgpu"]),
            3,
        )
        self.assertGreaterEqual(
            len([query for query in config.queries if query.corpus == "linux-amdgpu"]),
            3,
        )

    def test_cli_parses_named_full_corpus_source_roots(self):
        roots = parse_source_roots(["mxgpu=/tmp/mxgpu", "linux-amdgpu=/tmp/linux"])

        self.assertEqual(roots["mxgpu"], Path("/tmp/mxgpu"))
        self.assertEqual(roots["linux-amdgpu"], Path("/tmp/linux"))

    def test_cli_edges_full_forwards_batch_size(self):
        captured = {}

        def fake_run_full_corpus_generation(**kwargs):
            captured.update(kwargs)
            return {"summary": {"passed": 0}}

        original = cli.run_full_corpus_generation
        cli.run_full_corpus_generation = fake_run_full_corpus_generation
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = cli.main(
                    [
                        "edges-full",
                        "--config",
                        "config.json",
                        "--source-root",
                        "mxgpu=/tmp/mxgpu",
                        "--output-json",
                        "out.json",
                        "--output-md",
                        "out.md",
                        "--batch-size",
                        "1",
                    ]
                )
        finally:
            cli.run_full_corpus_generation = original

        self.assertEqual(exit_code, 0)
        self.assertEqual(captured["batch_size"], 1)

    def test_ollama_json_parser_extracts_json_from_wrapped_content(self):
        payload = {
            "message": {
                "content": "Here is the JSON:\n{\"cases\":[{\"id\":\"case1\",\"edges\":[]}]}"
            }
        }

        parsed = parse_ollama_json_message(payload)

        self.assertEqual(parsed["cases"][0]["id"], "case1")

    def test_generated_case_normalizer_accepts_list_shape(self):
        normalized = normalize_generated_cases([{"id": "case1", "edges": []}])

        self.assertEqual(normalized, {"cases": [{"id": "case1", "edges": []}]})

    def test_prompt_uses_real_source_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src.c"
            source.write_text("\n".join([f"line {i}" for i in range(1, 9)]), encoding="utf-8")
            config_path = root / "cases.json"
            config_path.write_text(
                json.dumps(
                    {
                        "name": "fixture",
                        "repo": {"url": "fixture", "default_source_root": str(root)},
                        "model": {"preferred": "qwen3.5:4b", "fallback": "qwen3.6"},
                        "cases": [
                            {
                                "id": "case1",
                                "question": "Which register is touched?",
                                "path": "src.c",
                                "start": 3,
                                "end": 5,
                                "expected_terms": ["line 3", "line 5"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            config = load_edge_case_config(config_path)

            prompt = build_prompt(config, root)

            self.assertIn("3: line 3", prompt)
            self.assertIn("5: line 5", prompt)
            self.assertNotIn("2: line 2", prompt)

    def test_fake_provider_generation_writes_graph_and_verifies_queries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src.c"
            source.write_text("REG_A\nFIELD_B\n", encoding="utf-8")
            config_path = root / "cases.json"
            output_json = root / "edges.json"
            output_md = root / "edges.md"
            config_path.write_text(
                json.dumps(
                    {
                        "name": "fixture",
                        "repo": {"url": "fixture", "default_source_root": str(root)},
                        "model": {"preferred": "qwen3.5:4b", "fallback": "qwen3.6"},
                        "cases": [
                            {
                                "id": "case1",
                                "question": "Which register field is linked?",
                                "path": "src.c",
                                "start": 1,
                                "end": 2,
                                "expected_terms": ["REG_A", "FIELD_B"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = run_generation(
                config_path=config_path,
                source_root=root,
                output_json=output_json,
                output_md=output_md,
                provider=FakeEdgeProvider(),
                min_pass=1,
            )

            self.assertEqual(result["summary"]["passed"], 1)
            self.assertTrue(output_json.exists())
            self.assertTrue(output_md.exists())

    def test_full_corpus_generation_scans_multiple_realistic_repos(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mxgpu = root / "mxgpu"
            amdgpu = root / "linux" / "drivers" / "gpu" / "drm" / "amd" / "amdgpu"
            mxgpu.mkdir(parents=True)
            amdgpu.mkdir(parents=True)
            (mxgpu / "gfx_v11_0.c").write_text(
                "\n".join(
                    [
                        "uint32_t tmp = RREG32_SOC15(GC, 0, regGCVM_L2_CNTL);",
                        "tmp = REG_SET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE, 1);",
                        "WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp);",
                    ]
                ),
                encoding="utf-8",
            )
            (amdgpu / "gfx_v10_0.c").write_text(
                "\n".join(
                    [
                        "WREG32_SOC15(GC, 0, mmGDS_VMID0_BASE, 0);",
                        "WREG32_SOC15(GC, 0, mmGDS_VMID0_SIZE, 0);",
                        "WREG32_SOC15(GC, 0, mmGDS_GWS_VMID0, 0);",
                    ]
                ),
                encoding="utf-8",
            )
            config_path = root / "full.json"
            output_json = root / "edges.json"
            output_md = root / "edges.md"
            config_path.write_text(
                json.dumps(
                    {
                        "name": "full-fixture",
                        "model": {"preferred": "qwen3.5:4b", "fallback": "qwen3.6"},
                        "corpora": [
                            {
                                "id": "mxgpu",
                                "repo": "amd/MxGPU-Virtualization",
                                "default_source_root": str(mxgpu),
                            },
                            {
                                "id": "linux-amdgpu",
                                "repo": "torvalds/linux",
                                "default_source_root": str(root / "linux"),
                                "relative_root": "drivers/gpu/drm/amd/amdgpu",
                            },
                        ],
                        "queries": [
                            {
                                "id": "mxgpu_l2",
                                "corpus": "mxgpu",
                                "question": "Which field enables L2 cache?",
                                "terms": ["regGCVM_L2_CNTL", "ENABLE_L2_CACHE"],
                                "expected_terms": ["regGCVM_L2_CNTL", "ENABLE_L2_CACHE"],
                            },
                            {
                                "id": "linux_gds",
                                "corpus": "linux-amdgpu",
                                "question": "Which GDS VMID registers are written?",
                                "terms": ["mmGDS_VMID0_BASE", "mmGDS_VMID0_SIZE", "mmGDS_GWS_VMID0"],
                                "expected_terms": ["mmGDS_VMID0_BASE", "mmGDS_VMID0_SIZE", "mmGDS_GWS_VMID0"],
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            config = load_full_corpus_edge_config(config_path)
            scanned = scan_full_corpus_queries(config, {})
            result = run_full_corpus_generation(
                config_path=config_path,
                source_roots={},
                output_json=output_json,
                output_md=output_md,
                provider=FakeEdgeProvider(),
                min_pass=2,
                batch_size=1,
            )

            self.assertEqual(scanned["summary"]["corpora"]["mxgpu"]["file_count"], 1)
            self.assertEqual(scanned["summary"]["corpora"]["linux-amdgpu"]["file_count"], 1)
            self.assertEqual(scanned["summary"]["resolved_query_count"], 2)
            self.assertIn("ENABLE_L2_CACHE", scanned["queries"][0]["snippets"][0]["text"])
            self.assertEqual(result["summary"]["passed"], 2)
            self.assertEqual(result["summary"]["total_files_scanned"], 2)
            self.assertTrue(output_json.exists())
            self.assertTrue(output_md.exists())


if __name__ == "__main__":
    unittest.main()
