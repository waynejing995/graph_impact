import unittest

from asip.providers import (
    EmbeddingProviderConfig,
    OllamaEmbeddingProvider,
    OpenAICompatibleEmbeddingProvider,
    create_embedding_provider,
)


class FakeTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def post_json(self, url, payload, headers, timeout):
        self.requests.append(
            {
                "url": url,
                "payload": payload,
                "headers": dict(headers),
                "timeout": timeout,
            }
        )
        if not self.responses:
            raise AssertionError("fake transport received an unexpected request")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class EmbeddingProviderTests(unittest.TestCase):
    def test_ollama_embeddings_uses_api_embeddings_prompt_format(self):
        transport = FakeTransport(
            [
                {"embedding": [0.1, 0.2]},
                {"embedding": [0.3, 0.4]},
            ]
        )
        provider = OllamaEmbeddingProvider(transport=transport)

        embeddings = provider.embed(
            ["REG_A", "REG_B"],
            EmbeddingProviderConfig(
                provider="ollama",
                model="nomic-embed-text",
                api_base_url="http://ollama.test/",
                extra_headers={"X-ASIP-Workspace": "amd-mvp1"},
                timeout_seconds=11,
            ),
        )

        self.assertEqual(embeddings, [[0.1, 0.2], [0.3, 0.4]])
        self.assertEqual(len(transport.requests), 2)
        self.assertEqual(transport.requests[0]["url"], "http://ollama.test/api/embeddings")
        self.assertEqual(
            transport.requests[0]["payload"],
            {"model": "nomic-embed-text", "prompt": "REG_A"},
        )
        self.assertEqual(
            transport.requests[1]["payload"],
            {"model": "nomic-embed-text", "prompt": "REG_B"},
        )
        self.assertEqual(transport.requests[0]["headers"]["Content-Type"], "application/json")
        self.assertEqual(transport.requests[0]["headers"]["X-ASIP-Workspace"], "amd-mvp1")
        self.assertEqual(transport.requests[0]["timeout"], 11)

    def test_ollama_embed_path_batches_input_format(self):
        transport = FakeTransport([{"embeddings": [[0.1, 0.2], [0.3, 0.4]]}])
        provider = OllamaEmbeddingProvider(transport=transport)

        embeddings = provider.embed(
            ["REG_A", "REG_B"],
            EmbeddingProviderConfig(
                provider="ollama",
                model="nomic-embed-text",
                api_base_url="http://ollama.test/",
                api_path="/api/embed",
                timeout_seconds=11,
            ),
        )

        self.assertEqual(embeddings, [[0.1, 0.2], [0.3, 0.4]])
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(transport.requests[0]["url"], "http://ollama.test/api/embed")
        self.assertEqual(
            transport.requests[0]["payload"],
            {"model": "nomic-embed-text", "input": ["REG_A", "REG_B"]},
        )

    def test_openai_compatible_embeddings_uses_v1_embeddings_input_format(self):
        transport = FakeTransport(
            [
                {
                    "data": [
                        {"index": 1, "embedding": [0.3, 0.4]},
                        {"index": 0, "embedding": [0.1, 0.2]},
                    ]
                }
            ]
        )
        provider = OpenAICompatibleEmbeddingProvider(transport=transport)

        embeddings = provider.embed(
            ["REG_A", "REG_B"],
            EmbeddingProviderConfig(
                provider="openai-compatible",
                model="text-embedding-3-small",
                api_base_url="https://embeddings.example.test/base",
                extra_headers={"Authorization": "Bearer test-token"},
                timeout_seconds=23,
            ),
        )

        self.assertEqual(embeddings, [[0.1, 0.2], [0.3, 0.4]])
        self.assertEqual(len(transport.requests), 1)
        self.assertEqual(transport.requests[0]["url"], "https://embeddings.example.test/base/v1/embeddings")
        self.assertEqual(
            transport.requests[0]["payload"],
            {"model": "text-embedding-3-small", "input": ["REG_A", "REG_B"]},
        )
        self.assertEqual(transport.requests[0]["headers"]["Authorization"], "Bearer test-token")
        self.assertEqual(transport.requests[0]["headers"]["Content-Type"], "application/json")
        self.assertEqual(transport.requests[0]["timeout"], 23)

    def test_configured_api_path_overrides_provider_default(self):
        transport = FakeTransport([{"data": [{"embedding": [1.0]}]}])
        provider = OpenAICompatibleEmbeddingProvider(transport=transport)

        embeddings = provider.embed(
            ["REG_A"],
            EmbeddingProviderConfig(
                provider="openai",
                model="embedder",
                api_base_url="https://proxy.example.test",
                api_path="custom/embeddings",
            ),
        )

        self.assertEqual(embeddings, [[1.0]])
        self.assertEqual(transport.requests[0]["url"], "https://proxy.example.test/custom/embeddings")

    def test_empty_input_does_not_call_transport(self):
        transport = FakeTransport([])
        provider = OllamaEmbeddingProvider(transport=transport)

        embeddings = provider.embed([], EmbeddingProviderConfig(model="embedder"))

        self.assertEqual(embeddings, [])
        self.assertEqual(transport.requests, [])

    def test_create_embedding_provider_normalizes_ids(self):
        self.assertIsInstance(
            create_embedding_provider(EmbeddingProviderConfig(provider="ollama", model="embedder")),
            OllamaEmbeddingProvider,
        )
        self.assertIsInstance(
            create_embedding_provider(EmbeddingProviderConfig(provider="openai_compatible", model="embedder")),
            OpenAICompatibleEmbeddingProvider,
        )

    def test_invalid_response_shape_raises_value_error(self):
        transport = FakeTransport([{"data": [{"embedding": "not-a-vector"}]}])
        provider = OpenAICompatibleEmbeddingProvider(transport=transport)

        with self.assertRaises(ValueError):
            provider.embed(["REG_A"], EmbeddingProviderConfig(provider="openai", model="embedder"))


if __name__ == "__main__":
    unittest.main()
