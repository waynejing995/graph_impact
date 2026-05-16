"""Embedding provider clients for ASIP retrieval workflows."""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence


Vector = List[float]


@dataclass(frozen=True)
class EmbeddingProviderConfig:
    model: str
    provider: str = "ollama"
    api_base_url: str = "http://localhost:11434"
    api_path: str = ""
    extra_headers: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 60


class EmbeddingTransport(Protocol):
    def post_json(
        self,
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: int,
    ) -> Mapping[str, Any]:
        """Send a JSON POST request and return the decoded JSON response."""


class UrlLibEmbeddingTransport:
    def post_json(
        self,
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str],
        timeout: int,
    ) -> Mapping[str, Any]:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=dict(headers),
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("embedding response must be a JSON object")
        return data


class EmbeddingProvider(Protocol):
    def embed(self, texts: Sequence[str], config: EmbeddingProviderConfig) -> List[Vector]:
        """Return one embedding vector per input text."""


class OllamaEmbeddingProvider:
    """Client for Ollama's /api/embeddings endpoint."""

    def __init__(self, transport: Optional[EmbeddingTransport] = None) -> None:
        self.transport = transport or UrlLibEmbeddingTransport()

    def embed(self, texts: Sequence[str], config: EmbeddingProviderConfig) -> List[Vector]:
        if not texts:
            return []
        if _uses_ollama_embed_endpoint(config):
            response = self.transport.post_json(
                _request_url(config, "/api/embed"),
                {"model": config.model, "input": list(texts)},
                _request_headers(config),
                config.timeout_seconds,
            )
            return _parse_ollama_embed_embeddings(response, len(texts))

        embeddings: List[Vector] = []
        for text in texts:
            response = self.transport.post_json(
                _request_url(config, "/api/embeddings"),
                {"model": config.model, "prompt": text},
                _request_headers(config),
                config.timeout_seconds,
            )
            embeddings.append(_parse_embedding_vector(response.get("embedding"), "embedding"))
        return embeddings


class OpenAICompatibleEmbeddingProvider:
    """Client for OpenAI-compatible /v1/embeddings endpoints."""

    def __init__(self, transport: Optional[EmbeddingTransport] = None) -> None:
        self.transport = transport or UrlLibEmbeddingTransport()

    def embed(self, texts: Sequence[str], config: EmbeddingProviderConfig) -> List[Vector]:
        if not texts:
            return []
        response = self.transport.post_json(
            _request_url(config, "/v1/embeddings"),
            {"model": config.model, "input": list(texts)},
            _request_headers(config),
            config.timeout_seconds,
        )
        return _parse_openai_embeddings(response, len(texts))


def create_embedding_provider(config: EmbeddingProviderConfig) -> EmbeddingProvider:
    provider = _normalize_provider_id(config.provider)
    if provider == "ollama":
        return OllamaEmbeddingProvider()
    if provider in {"openai", "openai-compatible"}:
        return OpenAICompatibleEmbeddingProvider()
    raise ValueError(f"Unsupported embedding provider: {config.provider}")


def _normalize_provider_id(provider: Any) -> str:
    return str(provider or "ollama").strip().lower().replace("_", "-")


def _request_headers(config: EmbeddingProviderConfig) -> Dict[str, str]:
    return {"Content-Type": "application/json", **config.extra_headers}


def _request_url(config: EmbeddingProviderConfig, default_path: str) -> str:
    base_url = config.api_base_url.rstrip("/")
    api_path = config.api_path or default_path
    if not api_path.startswith("/"):
        api_path = f"/{api_path}"
    return f"{base_url}{api_path}"


def _uses_ollama_embed_endpoint(config: EmbeddingProviderConfig) -> bool:
    return str(config.api_path or "").strip().rstrip("/") == "/api/embed"


def _parse_embedding_vector(value: Any, field_name: str) -> Vector:
    if not isinstance(value, list) or not all(isinstance(item, (int, float)) for item in value):
        raise ValueError(f"{field_name} must be a numeric embedding vector")
    return [float(item) for item in value]


def _parse_ollama_embed_embeddings(response: Mapping[str, Any], expected_count: int) -> List[Vector]:
    embeddings = response.get("embeddings")
    if not isinstance(embeddings, list):
        raise ValueError("Ollama /api/embed response must include an embeddings list")
    if len(embeddings) != expected_count:
        raise ValueError("Ollama /api/embed embedding count does not match input count")
    return [_parse_embedding_vector(item, "embeddings[]") for item in embeddings]


def _parse_openai_embeddings(response: Mapping[str, Any], expected_count: int) -> List[Vector]:
    data = response.get("data")
    if not isinstance(data, list):
        raise ValueError("OpenAI-compatible embedding response must include a data list")

    if len(data) != expected_count:
        raise ValueError("OpenAI-compatible embedding response count does not match input count")

    indexed: Dict[int, Vector] = {}
    for position, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError("OpenAI-compatible embedding data items must be objects")
        vector = _parse_embedding_vector(item.get("embedding"), "data[].embedding")
        index = item.get("index", position)
        if isinstance(index, int):
            indexed[index] = vector
        else:
            raise ValueError("OpenAI-compatible embedding data index must be an integer")

    missing = [index for index in range(expected_count) if index not in indexed]
    if missing:
        raise ValueError(f"OpenAI-compatible embedding response missing indexes: {missing}")
    return [indexed[index] for index in range(expected_count)]
