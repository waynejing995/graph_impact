# G06 Query-Time Provider Rerank QA

Date: 2026-05-18

Status: pass for provider-backed query embedding and same-provider vector rerank wiring; semantic ranking quality and credentialed hosted OpenAI-compatible QA remain residuals.

## Scope

This slice closes the previous product wiring hole where `query_evidence()` always used the deterministic SHA fallback vector for query-time vector search even when provider embeddings existed in SQLite.

Implemented behavior:

- `query_evidence()` accepts an optional embedding transport and reads persisted embedding provider settings.
- When embedding settings exist and the provider call succeeds, the query text is embedded through the configured provider.
- Vector search is filtered to the same stored embedding `provider` and `model`.
- Evidence rows expose `retrieval_sources: ["provider-vector"]`, `vector_provider`, `vector_model`, `query_embedding_source`, and `vector_embedding_source` when provider rerank participates.
- If the query embedding provider fails, the code falls back to deterministic vector search and exposes top-level `query_embedding.source=deterministic-fallback` plus the provider error instead of claiming provider rerank.
- That fallback path does not compare the deterministic query vector against stored provider vectors; it only uses stored deterministic/deterministic-fallback vectors.

## RED/GREEN Tests

Initial RED:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_query_evidence_reranks_with_configured_provider_query_embedding \
  -v

TypeError: query_evidence() got an unexpected keyword argument 'embedding_transport'
```

Final GREEN:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_query_schema \
  packages.core.tests.test_workbench_backend_state \
  packages.core.tests.test_storage_graph \
  -v

Ran 58 tests in 0.597s
OK (skipped=2)
```

Continuation fallback GREEN:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_query_evidence_reports_provider_query_embedding_fallback_metadata \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_query_evidence_does_not_compare_fallback_query_vector_to_provider_vectors \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_query_evidence_reranks_with_configured_provider_query_embedding \
  -v

Ran 3 tests
OK
```

Full core rerun:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v

Ran 224 tests in 23.515s
OK (skipped=2)
```

## Local Ollama Smoke

A throwaway SQLite DB under `/var/folders/.../T/asip-provider-query-rerank-8aik2keh/asip.db` was created with one evidence chunk. The DB saved local Ollama embedding settings:

```json
{
  "provider": "ollama",
  "model": "nomic-embed-text:latest",
  "api_base_url": "http://localhost:11434",
  "api_path": "/api/embed"
}
```

`backfill_provider_embeddings()` embedded the chunk through local Ollama:

```json
{
  "source": "provider_embedding_backfill",
  "provider": "ollama",
  "model": "nomic-embed-text:latest",
  "embedded_chunks": 1,
  "truncated_chunks": 0,
  "batch_size": 1,
  "limit": 1,
  "job_id": 1
}
```

Then `query_evidence()` embedded the query text through the same provider and returned:

```json
{
  "symbol": "REG_PROVIDER_RERANK_REAL",
  "retrieval_sources": ["lexical", "fts5", "provider-vector"],
  "vector_provider": "ollama",
  "vector_model": "nomic-embed-text:latest",
  "query_embedding_source": "provider",
  "vector_embedding_source": "provider",
  "vector_score": 1.0
}
```

## Residual

This proves product wiring and local Ollama provider-vector participation. It does not prove hosted credentialed OpenAI-compatible live QA, full production-scale semantic ranking quality, or that every current `data/asip.db` chunk has provider embeddings.
