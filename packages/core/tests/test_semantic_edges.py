import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asip import cli
from asip.cli import parse_source_roots
from asip.semantic_edges import (
    EdgeModelConfig,
    FakeEdgeProvider,
    FullCorpus,
    FullCorpusEdgeConfig,
    FullCorpusQuery,
    OllamaEdgeProvider,
    OpenAICompatibleEdgeProvider,
    build_full_corpus_prompt,
    build_prompt,
    create_edge_provider,
    load_full_corpus_edge_config,
    load_edge_case_config,
    parse_ollama_json_message,
    normalize_generated_cases,
    generate_full_corpus_batches,
    run_full_corpus_generation,
    run_generation,
    scan_full_corpus_queries,
    verify_full_corpus_queries,
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
        mxgpu = next(corpus for corpus in config.corpora if corpus.id == "mxgpu")
        self.assertTrue({"**/*.md", "**/*.rst", "**/*.pdf"}.issubset(set(mxgpu.include)))
        self.assertGreaterEqual(
            len([query for query in config.queries if query.corpus == "mxgpu"]),
            3,
        )
        self.assertGreaterEqual(
            len([query for query in config.queries if query.corpus == "linux-amdgpu"]),
            3,
        )

    def test_committed_gemma_full_corpus_config_uses_single_model(self):
        config = load_full_corpus_edge_config(Path("configs/edge_cases/full-corpus-gemma4-e4b.json"))

        self.assertEqual(config.name, "full-corpus-gemma4-e4b")
        self.assertEqual(config.model.preferred, "gemma4:e4b")
        self.assertEqual(config.model.fallback, "")
        self.assertEqual(config.model.format, "json")
        self.assertFalse(config.model.think)
        self.assertGreaterEqual(config.model.timeout_seconds, 900)
        self.assertEqual({corpus.id for corpus in config.corpora}, {"mxgpu", "linux-amdgpu"})
        mxgpu = next(corpus for corpus in config.corpora if corpus.id == "mxgpu")
        self.assertTrue({"**/*.md", "**/*.rst", "**/*.pdf"}.issubset(set(mxgpu.include)))
        self.assertGreaterEqual(len(config.queries), 6)

    def test_committed_clean_amd_gemma_config_keeps_docs_pdf_fixture(self):
        config = load_full_corpus_edge_config(Path("configs/edge_cases/clean-amd-gemma4-e4b.json"))

        self.assertEqual(config.name, "clean-amd-gemma4-e4b")
        self.assertEqual(config.model.preferred, "gemma4:e4b")
        self.assertEqual(config.model.fallback, "")
        self.assertFalse(config.model.think)
        self.assertGreaterEqual(config.model.timeout_seconds, 900)
        self.assertEqual({corpus.id for corpus in config.corpora}, {"mxgpu", "linux-amdgpu", "amd-amdgpu-docs"})
        docs = next(corpus for corpus in config.corpora if corpus.id == "amd-amdgpu-docs")
        self.assertTrue({"**/*.md", "**/*.pdf"}.issubset(set(docs.include)))
        self.assertGreaterEqual(len(config.queries), 9)

    def test_committed_openai_compatible_example_config_uses_chat_completions(self):
        config = load_full_corpus_edge_config(Path("configs/edge_cases/full-corpus-openai-compatible-example.json"))

        self.assertEqual(config.model.provider, "openai-compatible")
        self.assertEqual(config.model.api_path, "/v1/chat/completions")
        self.assertEqual(config.model.fallback, "")
        self.assertIsInstance(create_edge_provider(config.model), OpenAICompatibleEdgeProvider)

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

    def test_ollama_json_parser_uses_first_complete_object(self):
        payload = {
            "message": {
                "content": "{\"cases\":[{\"id\":\"case1\",\"edges\":[]}]} trailing {bad"
            }
        }

        parsed = parse_ollama_json_message(payload)

        self.assertEqual(parsed["cases"][0]["id"], "case1")

    def test_ollama_provider_retries_fallback_model(self):
        calls = []

        class FakeResponse:
            def __init__(self, payload):
                self.payload = payload

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return json.dumps(self.payload).encode("utf-8")

        def fake_urlopen(request, timeout):
            body = json.loads(request.data.decode("utf-8"))
            calls.append((body["model"], timeout))
            if body["model"] == "qwen3.5:4b":
                raise TimeoutError("preferred model timed out")
            return FakeResponse({"message": {"content": "{\"cases\":[{\"id\":\"ok\",\"edges\":[]}]}"}}
            )

        import urllib.request

        original_urlopen = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            provider = OllamaEdgeProvider()
            result = provider.generate(
                "CASE ok\nSNIPPET:\n1: REG_A",
                EdgeModelConfig(preferred="qwen3.5:4b", fallback="qwen3.6", timeout_seconds=42),
            )
        finally:
            urllib.request.urlopen = original_urlopen

        self.assertEqual([model for model, _timeout in calls], ["qwen3.5:4b", "qwen3.6"])
        self.assertEqual(calls[-1][1], 42)
        self.assertEqual(result["cases"][0]["id"], "ok")

    def test_full_corpus_model_config_loads_api_endpoint_and_headers(self):
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "name": "provider-config",
                        "model": {
                            "preferred": "gemma4:e4b",
                            "fallback": "",
                            "api_base_url": "https://llm.example.test",
                            "api_path": "/api/chat",
                            "extra_headers": {
                                "Authorization": "Bearer test-token",
                                "X-ASIP-Workspace": "amd-mvp1",
                            },
                        },
                        "corpora": [
                            {
                                "id": "mxgpu",
                                "repo": "fixture",
                                "default_source_root": str(Path(tmp)),
                            }
                        ],
                        "queries": [
                            {
                                "id": "case1",
                                "corpus": "mxgpu",
                                "question": "Which register?",
                                "terms": ["REG_A"],
                                "expected_terms": ["REG_A"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            config = load_full_corpus_edge_config(config_path)

        self.assertEqual(config.model.api_base_url, "https://llm.example.test")
        self.assertEqual(config.model.api_path, "/api/chat")
        self.assertEqual(config.model.extra_headers["Authorization"], "Bearer test-token")
        self.assertEqual(config.model.extra_headers["X-ASIP-Workspace"], "amd-mvp1")

    def test_ollama_provider_sends_configured_endpoint_and_extra_headers(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"message":{"content":"{\\"cases\\":[{\\"id\\":\\"ok\\",\\"edges\\":[]}]}"}}'

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return FakeResponse()

        import urllib.request

        original_urlopen = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            provider = OllamaEdgeProvider()
            provider.generate(
                "CASE ok\nSNIPPET:\n1: REG_A",
                EdgeModelConfig(
                    preferred="gemma4:e4b",
                    fallback="",
                    api_base_url="https://llm.example.test/",
                    api_path="/custom/chat",
                    extra_headers={"Authorization": "Bearer test-token", "X-ASIP-Workspace": "amd-mvp1"},
                    timeout_seconds=17,
                ),
            )
        finally:
            urllib.request.urlopen = original_urlopen

        self.assertEqual(captured["url"], "https://llm.example.test/custom/chat")
        headers = {key.lower(): value for key, value in captured["headers"].items()}
        self.assertEqual(headers["authorization"], "Bearer test-token")
        self.assertEqual(headers["x-asip-workspace"], "amd-mvp1")
        self.assertEqual(headers["content-type"], "application/json")
        self.assertEqual(captured["timeout"], 17)

    def test_edge_provider_extra_headers_expand_environment_placeholders(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"choices":[{"message":{"content":"{\\"cases\\":[{\\"id\\":\\"ok\\",\\"edges\\":[]}]}"}}]}'

        def fake_urlopen(request, timeout):
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return FakeResponse()

        import urllib.request

        original_urlopen = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            provider = OpenAICompatibleEdgeProvider()
            with patch.dict("os.environ", {"ASIP_TEST_EDGE_KEY": "edge-secret"}, clear=False):
                provider.generate(
                    "CASE ok\nSNIPPET:\n1: REG_A",
                    EdgeModelConfig(
                        preferred="edge-model",
                        fallback="",
                        provider="openai-compatible",
                        api_base_url="https://edge.example.test",
                        extra_headers={"Authorization": "Bearer ${ENV:ASIP_TEST_EDGE_KEY}"},
                        timeout_seconds=19,
                    ),
                )
        finally:
            urllib.request.urlopen = original_urlopen

        headers = {key.lower(): value for key, value in captured["headers"].items()}
        self.assertEqual(headers["authorization"], "Bearer edge-secret")
        self.assertEqual(captured["timeout"], 19)

    def test_edge_provider_extra_header_missing_environment_stops_before_transport(self):
        calls = []

        def fake_urlopen(_request, _timeout):
            calls.append("called")
            raise AssertionError("transport should not be called when header env is missing")

        import urllib.request

        original_urlopen = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            provider = OpenAICompatibleEdgeProvider()
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "ASIP_MISSING_EDGE_KEY"):
                    provider.generate(
                        "CASE ok\nSNIPPET:\n1: REG_A",
                        EdgeModelConfig(
                            preferred="edge-model",
                            fallback="",
                            provider="openai-compatible",
                            api_base_url="https://edge.example.test",
                            extra_headers={"Authorization": "Bearer ${ENV:ASIP_MISSING_EDGE_KEY}"},
                        ),
                    )
        finally:
            urllib.request.urlopen = original_urlopen

        self.assertEqual(calls, [])

    def test_ollama_provider_does_not_retry_when_fallback_is_empty(self):
        calls = []

        def fake_urlopen(request, timeout):
            body = json.loads(request.data.decode("utf-8"))
            calls.append((body["model"], timeout))
            raise TimeoutError("single model timed out")

        import urllib.request

        original_urlopen = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            provider = OllamaEdgeProvider()
            with self.assertRaises(RuntimeError) as error:
                provider.generate(
                    "CASE ok\nSNIPPET:\n1: REG_A",
                    EdgeModelConfig(preferred="gemma4:e4b", fallback="", timeout_seconds=7),
                )
        finally:
            urllib.request.urlopen = original_urlopen

        self.assertEqual(calls, [("gemma4:e4b", 7)])
        self.assertIn("gemma4:e4b", str(error.exception))
        self.assertNotIn("qwen", str(error.exception))

    def test_provider_factory_uses_openai_compatible_config(self):
        provider = create_edge_provider(
            EdgeModelConfig(
                preferred="qwen3.6",
                fallback="",
                provider="openai-compatible",
                api_base_url="https://llm.example.test",
                api_path="/v1/chat/completions",
            )
        )

        self.assertIsInstance(provider, OpenAICompatibleEdgeProvider)

    def test_provider_name_is_normalized_for_defaults_and_factory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "full.json"
            config_path.write_text(
                json.dumps(
                    {
                        "name": "provider-normalization",
                        "model": {
                            "preferred": "qwen3.6",
                            "fallback": "",
                            "provider": " OpenAI-Compatible ",
                            "api_base_url": "https://llm.example.test",
                        },
                        "corpora": [
                            {
                                "id": "fixture",
                                "repo": "fixture",
                                "default_source_root": str(root),
                            }
                        ],
                        "queries": [
                            {
                                "id": "q1",
                                "corpus": "fixture",
                                "question": "Which register is touched?",
                                "terms": ["REG_A"],
                                "expected_terms": ["REG_A"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            config = load_full_corpus_edge_config(config_path)

        self.assertEqual(config.model.provider, "openai-compatible")
        self.assertEqual(config.model.api_path, "/v1/chat/completions")
        self.assertIsInstance(create_edge_provider(config.model), OpenAICompatibleEdgeProvider)

    def test_openai_compatible_provider_sends_chat_completions_request_and_headers(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"choices":[{"message":{"content":"{\\"cases\\":[{\\"id\\":\\"ok\\",\\"edges\\":[]}]}"}}]}'

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            captured["body"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        import urllib.request

        original_urlopen = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            provider = OpenAICompatibleEdgeProvider()
            result = provider.generate(
                "CASE ok\nSNIPPET:\n1: REG_A",
                EdgeModelConfig(
                    preferred="qwen3.6",
                    fallback="",
                    provider="openai-compatible",
                    api_base_url="https://llm.example.test/",
                    api_path="v1/chat/completions",
                    extra_headers={"Authorization": "Bearer test-token", "X-ASIP-Workspace": "amd-mvp1"},
                    num_predict=321,
                    temperature=0.25,
                    timeout_seconds=23,
                ),
            )
        finally:
            urllib.request.urlopen = original_urlopen

        self.assertEqual(captured["url"], "https://llm.example.test/v1/chat/completions")
        headers = {key.lower(): value for key, value in captured["headers"].items()}
        self.assertEqual(headers["authorization"], "Bearer test-token")
        self.assertEqual(headers["x-asip-workspace"], "amd-mvp1")
        self.assertEqual(captured["timeout"], 23)
        self.assertEqual(captured["body"]["model"], "qwen3.6")
        self.assertEqual(captured["body"]["max_tokens"], 321)
        self.assertEqual(captured["body"]["temperature"], 0.25)
        self.assertEqual(captured["body"]["response_format"], {"type": "json_object"})
        self.assertNotIn("options", captured["body"])
        self.assertEqual(result["cases"][0]["id"], "ok")

    def test_openai_compatible_provider_does_not_retry_when_fallback_is_empty(self):
        calls = []

        def fake_urlopen(request, timeout):
            body = json.loads(request.data.decode("utf-8"))
            calls.append((body["model"], timeout))
            raise TimeoutError("single model timed out")

        import urllib.request

        original_urlopen = urllib.request.urlopen
        urllib.request.urlopen = fake_urlopen
        try:
            provider = OpenAICompatibleEdgeProvider()
            with self.assertRaises(RuntimeError) as error:
                provider.generate(
                    "CASE ok\nSNIPPET:\n1: REG_A",
                    EdgeModelConfig(
                        preferred="qwen3.6",
                        fallback="",
                        provider="openai-compatible",
                        timeout_seconds=11,
                    ),
                )
        finally:
            urllib.request.urlopen = original_urlopen

        self.assertEqual(calls, [("qwen3.6", 11)])
        self.assertIn("qwen3.6", str(error.exception))

    def test_openai_provider_does_not_run_ollama_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src.c"
            source.write_text("REG_A\n", encoding="utf-8")
            config_path = root / "cases.json"
            config_path.write_text(
                json.dumps(
                    {
                        "name": "openai-fixture",
                        "repo": {"url": "fixture", "default_source_root": str(root)},
                        "model": {
                            "preferred": "qwen3.6",
                            "fallback": "",
                            "provider": "openai-compatible",
                        },
                        "cases": [
                            {
                                "id": "case1",
                                "question": "Which register is touched?",
                                "path": "src.c",
                                "start": 1,
                                "end": 1,
                                "expected_terms": ["REG_A"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            import asip.semantic_edges as semantic_edges

            cleanup_calls = []
            ps_calls = []
            original_stop = semantic_edges.stop_ollama_model
            original_ps = semantic_edges.ollama_ps_output
            semantic_edges.stop_ollama_model = lambda model_name: cleanup_calls.append(model_name)
            semantic_edges.ollama_ps_output = lambda: ps_calls.append("ps") or "ollama should not be queried"
            try:
                run_generation(
                    config_path=config_path,
                    source_root=root,
                    provider=FakeEdgeProvider(),
                    min_pass=1,
                )
            finally:
                semantic_edges.stop_ollama_model = original_stop
                semantic_edges.ollama_ps_output = original_ps

        self.assertEqual(cleanup_calls, [])
        self.assertEqual(ps_calls, [])

    def test_injected_fake_provider_does_not_run_ollama_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src.c"
            source.write_text("REG_A\n", encoding="utf-8")
            config_path = root / "cases.json"
            config_path.write_text(
                json.dumps(
                    {
                        "name": "fake-provider-fixture",
                        "repo": {"url": "fixture", "default_source_root": str(root)},
                        "model": {"preferred": "gemma4:e4b", "fallback": ""},
                        "cases": [
                            {
                                "id": "case1",
                                "question": "Which register is touched?",
                                "path": "src.c",
                                "start": 1,
                                "end": 1,
                                "expected_terms": ["REG_A"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            import asip.semantic_edges as semantic_edges

            cleanup_calls = []
            ps_calls = []
            original_stop = semantic_edges.stop_ollama_model
            original_ps = semantic_edges.ollama_ps_output
            semantic_edges.stop_ollama_model = lambda model_name: cleanup_calls.append(model_name)
            semantic_edges.ollama_ps_output = lambda: ps_calls.append("ps") or "ollama should not be queried"
            try:
                payload = run_generation(
                    config_path=config_path,
                    source_root=root,
                    provider=FakeEdgeProvider(),
                    min_pass=1,
                )
            finally:
                semantic_edges.stop_ollama_model = original_stop
                semantic_edges.ollama_ps_output = original_ps

        self.assertEqual(cleanup_calls, [])
        self.assertEqual(ps_calls, [])
        self.assertEqual(payload["summary"]["ollama_ps_after"], "FakeEdgeProvider cleanup not applicable")

    def test_ollama_cleanup_stops_fallback_attempted_model(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"message":{"content":"{\\"cases\\":[{\\"id\\":\\"case1\\",\\"edges\\":[{\\"src\\":\\"tmp\\",\\"relation\\":\\"writes\\",\\"dst\\":\\"REG_A\\",\\"confidence\\":0.9,\\"evidence\\":\\"1\\"}]}]}"}}'

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "src.c"
            source.write_text("REG_A\n", encoding="utf-8")
            config_path = root / "cases.json"
            config_path.write_text(
                json.dumps(
                    {
                        "name": "ollama-fallback-fixture",
                        "repo": {"url": "fixture", "default_source_root": str(root)},
                        "model": {"preferred": "preferred-model", "fallback": "fallback-model"},
                        "cases": [
                            {
                                "id": "case1",
                                "question": "Which register is touched?",
                                "path": "src.c",
                                "start": 1,
                                "end": 1,
                                "expected_terms": ["REG_A"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            import urllib.request
            import asip.semantic_edges as semantic_edges

            def fake_urlopen(request, timeout):
                body = json.loads(request.data.decode("utf-8"))
                if body["model"] == "preferred-model":
                    raise TimeoutError("preferred timed out")
                return FakeResponse()

            cleanup_calls = []
            original_urlopen = urllib.request.urlopen
            original_stop = semantic_edges.stop_ollama_model
            original_ps = semantic_edges.ollama_ps_output
            urllib.request.urlopen = fake_urlopen
            semantic_edges.stop_ollama_model = lambda model_name: cleanup_calls.append(model_name)
            semantic_edges.ollama_ps_output = lambda: "NAME ID SIZE PROCESSOR UNTIL\n"
            try:
                payload = run_generation(
                    config_path=config_path,
                    source_root=root,
                    provider=OllamaEdgeProvider(),
                    min_pass=1,
                )
            finally:
                urllib.request.urlopen = original_urlopen
                semantic_edges.stop_ollama_model = original_stop
                semantic_edges.ollama_ps_output = original_ps

        self.assertEqual(cleanup_calls, ["preferred-model", "fallback-model"])
        self.assertEqual(payload["summary"]["passed"], 1)

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

    def test_full_corpus_include_patterns_use_real_glob_semantics(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            keep = root / "src" / "gpu" / "keep.c"
            skip_c = root / "other" / "skip.c"
            skip_h = root / "src" / "gpu" / "skip.h"
            keep.parent.mkdir(parents=True)
            skip_c.parent.mkdir(parents=True)
            keep.write_text("REG_A\n", encoding="utf-8")
            skip_c.write_text("REG_A\n", encoding="utf-8")
            skip_h.write_text("REG_A\n", encoding="utf-8")
            config = FullCorpusEdgeConfig(
                name="glob-fixture",
                model=EdgeModelConfig(preferred="qwen3.5:4b", fallback="qwen3.6"),
                corpora=[
                    FullCorpus(
                        id="fixture",
                        repo="fixture",
                        default_source_root=str(root),
                        include=["src/**/*.c"],
                    )
                ],
                queries=[
                    FullCorpusQuery(
                        id="q",
                        corpus="fixture",
                        question="Where is REG_A?",
                        terms=["REG_A"],
                        expected_terms=["REG_A"],
                    )
                ],
            )

            scanned = scan_full_corpus_queries(config, {})

            self.assertEqual(scanned["summary"]["corpora"]["fixture"]["file_count"], 1)
            self.assertEqual(scanned["queries"][0]["snippets"][0]["path"], "src/gpu/keep.c")

    def test_full_corpus_prompt_forbids_file_path_edge_endpoints(self):
        prompt = build_full_corpus_prompt(
            {
                "corpora": {
                    "fixture": {
                        "repo": "fixture",
                        "file_count": 1,
                        "source_root": "/tmp/fixture",
                        "scan_root": "/tmp/fixture",
                    }
                },
                "queries": [
                    {
                        "id": "q",
                        "corpus": "fixture",
                        "question": "Which register field is set?",
                        "terms": ["REG_A", "FIELD_B"],
                        "snippets": [
                            {
                                "path": "src/gpu/file.c",
                                "line_start": 10,
                                "line_end": 11,
                                "text": "10: tmp = REG_SET_FIELD(tmp, REG_A, FIELD_B, 1);",
                            }
                        ],
                    }
                ],
            }
        )

        self.assertIn("Do not use file paths as src or dst.", prompt)
        self.assertIn("Every supplied TERMS identifier", prompt)

    def test_full_corpus_verification_rejects_ungrounded_edges(self):
        config = FullCorpusEdgeConfig(
            name="grounding-fixture",
            model=EdgeModelConfig(preferred="qwen3.5:4b", fallback="qwen3.6"),
            corpora=[FullCorpus(id="fixture", repo="fixture", default_source_root="/tmp/fixture")],
            queries=[
                FullCorpusQuery(
                    id="q",
                    corpus="fixture",
                    question="Which terms are linked?",
                    terms=["REG_A", "FIELD_B"],
                    expected_terms=["REG_A", "FIELD_B"],
                )
            ],
        )
        scan = {
            "queries": [
                {
                    "id": "q",
                    "snippets": [
                        {
                            "path": "src.c",
                            "line_start": 1,
                            "line_end": 2,
                            "text": "1: REG_A\n2: FIELD_B",
                        }
                    ],
                }
            ]
        }

        results = verify_full_corpus_queries(
            config,
            scan,
            {
                "cases": [
                    {
                        "id": "q",
                        "edges": [
                            {
                                "src": "REG_A",
                                "relation": "sets_field",
                                "dst": "FIELD_B",
                                "confidence": 0.9,
                                "evidence": "REG_A FIELD_B",
                            },
                            {
                                "src": "INVENTED_REG",
                                "relation": "sets_field",
                                "dst": "FIELD_B",
                                "confidence": 0.1,
                                "evidence": "not in source",
                            },
                        ],
                    }
                ]
            },
        )

        self.assertFalse(results[0]["passed"])
        self.assertEqual(results[0]["ungrounded_edges"], ["INVENTED_REG->FIELD_B"])

    def test_full_corpus_batches_record_provider_errors_and_continue(self):
        class FailingProvider:
            def generate(self, prompt, model):
                if "CASE q1" in prompt:
                    raise ValueError("bad json")
                return {"cases": [{"id": "q2", "edges": []}]}

        generated = generate_full_corpus_batches(
            {
                "corpora": {},
                "queries": [
                    {"id": "q1", "corpus": "fixture", "question": "q1", "terms": [], "snippets": []},
                    {"id": "q2", "corpus": "fixture", "question": "q2", "terms": [], "snippets": []},
                ],
            },
            FailingProvider(),
            EdgeModelConfig(preferred="qwen3.5:4b", fallback="qwen3.6"),
            batch_size=1,
        )

        self.assertEqual([case["id"] for case in generated["cases"]], ["q1", "q2"])
        self.assertEqual(generated["errors"][0]["queries"], ["q1"])
        self.assertIn("bad json", generated["cases"][0]["error"])


if __name__ == "__main__":
    unittest.main()
