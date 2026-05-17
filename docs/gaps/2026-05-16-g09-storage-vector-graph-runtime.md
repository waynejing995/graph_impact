# G09 SQLite FTS5 Vector And NetworkX Runtime

Status: Partial; SQLite, FTS5, fallback vector retrieval, and NetworkX graph are live; native sqlite-vec remains blocking/deferred

## Requirement

MVP-1 is SQLite-first:

- SQLite owns corpora, documents, chunks, symbols, evidence, resolver profiles, graph entities/edges, jobs, and provider config.
- FTS5 owns keyword/full-text search.
- sqlite-vec owns embedding search through an adapter.
- NetworkX is the in-memory graph runtime loaded from SQLite edges.

## Current Evidence

- `packages/core/src/asip/storage.py` creates SQLite tables for corpora, jobs, documents, chunks, FTS5, edges, evidence, resolver profiles, provider settings, and embeddings.
- `search_text()` uses FTS5, and `query_evidence()` uses FTS matches in ranking.
- `search_vector()` stores vectors as JSON and computes cosine similarity in Python.
- `query_evidence()` now calls the vector adapter with a deterministic fallback query embedding and merges high-similarity chunk evidence into ranked results with `vector_score` and `retrieval_sources`.
- Indexing can call a configured embedding provider transport and store returned vectors; failed live calls use deterministic fallback embeddings with explicit metadata.
- `sqlite-vec` appears in requirements and an optional runtime smoke test, but the test can skip when native extension loading is unavailable.
- `to_networkx()` exists and has core test coverage.
- Graph API output now uses NetworkX-derived hop-bounded subgraph extraction and no-seed global graph extraction from SQLite edges.
- `packages/core/tests/test_workbench_query_schema.py` covers vector-backed evidence retrieval without lexical overlap.
- Clean AMD DB `/tmp/asip-clean-amd-gemma4-provider-2026-05-17-final.db` stores 32 provider-sourced embeddings from `ollama/nomic-embed-text:latest` and zero deterministic fallback embeddings for those rows. This proves AQ09/provider provenance only; it is not full provider-vector coverage for every chunk.
- `packages/core/src/asip/providers.py` now supports Ollama `/api/embed` batch embeddings in addition to `/api/embeddings`, and `asip.cli provider-embeddings` can backfill provider embeddings for existing chunks.
- Clean AMD free-query QA records NetworkX for all six query graphs and the no-seed global graph.

## Remaining Gap

Storage pieces exist, graph expansion now uses NetworkX, and the product retrieval path now combines vector adapter matches into ranking.

The deterministic fallback and provider embedding paths prove schema/provenance wiring and retrieval integration. The current clean AMD DB has partial provider embeddings, not full provider-vector coverage or semantic rerank quality proof. Native sqlite-vec availability remains skipped/deferred in this runtime.

## Acceptance Criteria

- FTS5 search is used by query retrieval.
- Vector adapter supports native sqlite-vec when available and has a documented fallback.
- Embeddings are generated or loaded for indexed chunks with provider/model provenance.
- Query retrieval combines FTS and vector results through the adapter; native sqlite-vec acceleration remains unavailable in this runtime unless the extension load succeeds.
- NetworkX graph extraction is used by graph API or documented as a post-MVP deferral accepted by the user.
- DB schema includes enough state for jobs, provider config, evidence, entities, resolver profiles, and graph edges.

## Required Tests

- Core test: query combines FTS and vector-backed results from the same store. Implemented through fallback vector adapter.
- sqlite-vec runtime test in the Python runtime used for ASIP, plus an explicit fallback-path test.
- Integration test: indexing creates embeddings or records why embedding generation is disabled.
- Integration test: graph API returns NetworkX-derived subgraph from SQLite edges, or a de-scope test/document states the chosen MVP boundary.
- Migration/schema test for core MVP tables.

## Not Closed Until

The Web/API/MCP query and graph routes read from SQLite-backed retrieval/graph services, and vector/NetworkX gaps are either implemented or explicitly accepted as MVP deferrals.
