# G09 SQLite FTS5 Vector And NetworkX Runtime

Status: Partial; SQLite, FTS5, native sqlite-vec adapter with fallback vector retrieval, and NetworkX graph are live; production provider-vector quality remains a boundary

## Requirement

MVP-1 is SQLite-first:

- SQLite owns corpora, documents, chunks, symbols, evidence, resolver profiles, graph entities/edges, jobs, and provider config.
- FTS5 owns keyword/full-text search.
- sqlite-vec owns embedding search through an adapter.
- NetworkX is the in-memory graph runtime loaded from SQLite edges.

## Current Evidence

- `packages/core/src/asip/storage.py` creates SQLite tables for corpora, jobs, documents, chunks, FTS5, edges, evidence, resolver profiles, provider settings, and embeddings.
- `search_text()` uses FTS5, and `query_evidence()` uses FTS matches in ranking.
- `search_vector()` stores vectors as JSON as the durable source of truth, tries a temp-table sqlite-vec native adapter when the runtime can load the extension, and falls back to Python cosine when sqlite-vec is unavailable.
- `query_evidence()` calls the vector adapter with a configured provider query embedding when provider settings exist and the provider call succeeds; otherwise it falls back to the deterministic query embedding with explicit source metadata. It merges high-similarity chunk evidence into ranked results with `vector_score`, `vector_runtime`, `retrieval_sources`, `query_embedding_source`, `vector_provider`, `vector_model`, and `vector_embedding_source`.
- Indexing can call a configured embedding provider transport and store returned vectors; failed live calls use deterministic fallback embeddings with explicit metadata.
- `sqlite-vec` appears in requirements and an optional runtime smoke test. System Python 3.9 lacks `sqlite3.Connection.enable_load_extension`, so that runtime still skips the extension smoke, while the bundled Codex Python 3.12 runtime loads and executes the native sqlite-vec smoke successfully.
- `to_networkx()` exists and has core test coverage.
- Graph API output now uses NetworkX-derived hop-bounded subgraph extraction and no-seed global graph extraction from SQLite edges.
- `packages/core/tests/test_workbench_query_schema.py` covers vector-backed evidence retrieval without lexical overlap.
- Clean AMD DB `/tmp/asip-clean-amd-gemma4-provider-2026-05-17-final.db` stores 32 provider-sourced embeddings from `ollama/nomic-embed-text:latest` and zero deterministic fallback embeddings for those rows. This proves AQ09/provider provenance only; it is not full provider-vector coverage for every chunk.
- `packages/core/src/asip/providers.py` now supports Ollama `/api/embed` batch embeddings in addition to `/api/embeddings`, and `asip.cli provider-embeddings` can backfill provider embeddings for existing chunks.
- Clean AMD free-query QA records NetworkX for all six query graphs and the no-seed global graph.
- Native sqlite-vec extension proof: `/Users/chenjingwen/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3` reports Python 3.12.13, SQLite 3.50.4, `enable_load_extension=True`, `sqlite_vec` installed, and passes `packages.core.tests.test_storage_graph.StorageGraphTests.test_sqlite_vec_extension_can_run_when_runtime_supports_extensions`.
- Native retrieval adapter proof: the same bundled runtime passes `packages.core.tests.test_storage_graph.StorageGraphTests.test_search_vector_uses_sqlite_vec_when_runtime_supports_extensions`, which verifies `AsipStore.search_vector()` returns `retrieval_runtime=sqlite-vec`, a native distance, and the same top semantic neighbor shape as the fallback path.
- Fallback proof: system Python 3.9 lacks loadable extension support, so the core suite still exercises JSON + Python cosine fallback and query evidence now reports `vector_runtime=python-cosine` for vector-only retrieval rows.
- Query-time provider rerank proof: `docs/qa/2026-05-18-g06-query-time-provider-rerank-qa.md` records RED/GREEN coverage for provider query embedding, same-provider/model vector filtering, `provider-vector` retrieval-source metadata, and a local Ollama smoke over a throwaway DB.
- Current default-DB quality proxy: `docs/qa/2026-05-21-semantic-rerank-quality-eval.json` and `.md` confirm full provider embedding coverage (`147841 / 147841` chunks), AQ01-AQ09 live acceptance consistency across product surfaces, and explicit `provider-vector` participation in AQ05.
- Provider-vector preservation proof: `docs/qa/2026-05-21-provider-vector-preservation-qa.md` records a regression fix for lexical/FTS candidate pressure plus AQ05 six-surface QA with visible `provider-vector` retrieval source and code/doc/pdf/register diversity.

## Remaining Gap

Storage pieces exist, graph expansion now uses NetworkX, and the product retrieval path now combines vector adapter matches into ranking.

The deterministic fallback and provider embedding paths prove schema/provenance wiring and retrieval integration. Query-time provider-vector wiring is now proven, the current default workbench DB has full local provider embedding coverage, and provider-vector evidence is preserved when lexical rows otherwise fill the candidate window. Semantic rerank quality at scale remains a product-quality boundary. The bundled Python runtime proves the native sqlite-vec extension can load and the product `search_vector()` path can use it. The native adapter is intentionally temp-table based for now, with JSON vectors retained as source of truth; a persistent sqlite-vec sidecar/table-per-dimension remains a future performance improvement rather than an MVP requirement.

## Acceptance Criteria

- FTS5 search is used by query retrieval.
- Vector adapter has a documented fallback; native sqlite-vec retrieval is used when the runtime supports loadable extensions, otherwise the adapter reports Python cosine fallback.
- Embeddings are generated or loaded for indexed chunks with provider/model provenance.
- Query retrieval combines FTS and vector results through the adapter and exposes `vector_runtime` so QA can distinguish `sqlite-vec` from `python-cosine`.
- NetworkX graph extraction is used by graph API or documented as a post-MVP deferral accepted by the user.
- DB schema includes enough state for jobs, provider config, evidence, entities, resolver profiles, and graph edges.

## Required Tests

- Core test: query combines FTS and vector-backed results from the same store and exposes `vector_runtime`.
- sqlite-vec runtime test in the Python runtime used for ASIP, native adapter test, plus an explicit fallback-path test.
- Integration test: indexing creates embeddings or records why embedding generation is disabled.
- Integration test: graph API returns NetworkX-derived subgraph from SQLite edges, or a de-scope test/document states the chosen MVP boundary.
- Migration/schema test for core MVP tables.

## Not Closed Until

The Web/API/MCP query and graph routes read from SQLite-backed retrieval/graph services, and vector/NetworkX gaps are either implemented or explicitly accepted as MVP deferrals.
