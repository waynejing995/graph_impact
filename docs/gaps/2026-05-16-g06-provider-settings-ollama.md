# G06 Provider Settings And Ollama Detection

Status: Batch/query semantic-edge, query-time provider rerank wiring, and full local temp-copy provider backfill verified; credentialed OpenAI-compatible live QA remains an explicit boundary

## Requirement

Embedding and semantic-edge providers must be configurable independently and support local Ollama plus OpenAI-compatible APIs.

The UI must avoid forcing the user to edit code for base URL, model, API path, or extra headers.

Semantic-edge generation must support both query-scoped generation and batch corpus generation. Query-scoped generation is useful for a selected search result, but it is not enough for the global graph. Batch generation must read indexed code/doc/PDF/register candidates, call the configured edge provider in bounded batches, persist generated edges with provenance, and expose job status and failure evidence.

## Current Evidence

- Settings UI has separate edge provider, edge base URL/path/model, embedding provider, embedding base URL/model, timeout/context fields, and extra headers JSON.
- Ollama detection uses the currently configured Settings base URL and calls `/api/tags`.
- Provider smoke makes a real Ollama `/api/tags` attempt and returns requested URL, status, model list, or structured failure evidence.
- `provider_settings` are persisted in SQLite and exposed through `asip.cli provider-save/provider-show`.
- Index jobs record saved provider settings in job metadata.
- Web API tests cover provider save, provider settings recorded on selected corpus indexing, and a real failed Ollama probe target.
- `apps/web/tests/workbench-smoke.spec.ts` verifies a fresh browser session hydrates Settings from backend provider settings without relying on localStorage.
- `packages/core/tests/test_workbench_backend_state.py` verifies indexing can record embedding provider/model provenance for chunks when embedding settings are configured.
- `packages/core/src/asip/providers.py` adds injectable Ollama and OpenAI-compatible embedding clients for `/api/embeddings` and `/v1/embeddings`.
- `packages/core/tests/test_providers.py` verifies embedding request format, extra headers, timeout, path override, provider factory behavior, and response validation.
- `packages/core/tests/test_workbench_backend_state.py` verifies registered-corpus indexing can call the configured embedding provider transport and store the returned vector with `metadata_json.source = provider`.
- Settings UI now exposes independent embedding API path and embedding extra headers, and persists them through backend state.
- FastAPI exposes `GET /providers/settings`, `POST /providers/settings`, and `GET /providers/ollama-tags`.
- MCP exposes `provider_settings_show()`, `provider_settings_save()`, and `ollama_models()`.
- FastAPI and MCP tests verify edge/embedding provider settings roundtrip through a temp SQLite DB.
- FastAPI and MCP tests verify Ollama detection uses the supplied base URL and reports `requested_url` plus structured failure evidence for an unreachable endpoint.
- Local Ollama smoke evidence is recorded in `docs/qa/2026-05-17-ollama-provider-smoke.md`: `nomic-embed-text:latest` and `qwen3-embedding:4b` returned embeddings; `qwen3.5:4b` required `think:false` to avoid spending the response budget in thinking; `gemma4:e4b` returned compact JSON but used materially more memory.
- AQ09 provider-specific acceptance smoke is recorded in `docs/qa/2026-05-17-aq09-provider-smoke-ollama.md`: a registered corpus was indexed with live Ollama embedding settings, embedding provenance was provider-sourced with zero deterministic fallbacks, and the semantic-edge smoke returned one edge through `gemma4:e4b`.
- Core acceptance tests verify the same provider acceptance path also supports `openai-compatible` embedding and edge providers by changing settings, not code.
- Web BFF `POST /api/workbench/acceptance/run` now has an AQ09 API test that uses an isolated SQLite DB with independently configured edge and embedding provider settings. It verifies provider-sourced OpenAI-compatible embedding provenance, distinct edge/embedding base URLs, and explicit semantic-edge failure evidence when the edge endpoint is unreachable. This is deterministic API plumbing/provenance evidence, not credentialed live OpenAI-compatible QA.
- Settings UI now has a `Run AQ09 acceptance` action that saves the current provider settings and calls the same Web BFF acceptance endpoint with `queryIds: ["AQ09"]` and `surfaces: ["CLI", "API", "Web"]`, then displays the embedding and semantic-edge provider/model checks. The Playwright smoke test mocks that endpoint, so it is UI wiring evidence rather than final clean-DB Web acceptance evidence.
- Settings UI can also run AQ09 against a user-supplied SQLite DB path through the real Web BFF acceptance endpoint. The smoke test seeds an isolated DB with provider-sourced OpenAI-compatible embedding provenance and uses a local HTTP fake Ollama edge endpoint, then verifies the UI receives a passing AQ09 provider check without mocking the BFF route.
- Provider status in the top bar and Settings metrics is now `unverified` after settings save/hydration/edit/detection, becomes `verified` only after provider smoke or AQ09 provider checks pass, and becomes `failed` on provider smoke/AQ09 failure.
- `packages/core/src/asip/workbench.py` exposes `generate_semantic_edges_for_query()` and `generate_semantic_edges_batch()`, which read indexed SQLite evidence rows/candidates, call the configured edge provider, persist generated edges into the SQLite graph store, and record semantic-edge jobs.
- `asip.cli semantic-edges`, `asip.cli semantic-edges-batch`, Web BFF `POST /api/workbench/semantic-edges`, FastAPI `POST /semantic-edges`, MCP `semantic_edges_generate()`, MCP `semantic_edges_generate_batch()`, and the `/graph` page query/batch actions now call those workbench semantic-edge jobs. Tests cover real UI/API paths with supplied DBs and local fake Ollama-compatible HTTP endpoints.
- Clean AMD local Ollama evidence is now recorded in `docs/qa/2026-05-17-acceptance-clean-amd-gemma4-provider-current.json` and `.md`: AQ09 provider checks pass with `ollama/nomic-embed-text:latest` provider embeddings (`embedding_count=32`, `fallback_count=0`) plus `gemma4:e4b` semantic-edge smoke (`edge_count=1`).
- `asip.cli provider-embeddings` and `backfill_provider_embeddings()` can batch provider embeddings for already indexed chunks using the current provider settings. `packages/core/tests/test_workbench_backend_state.py` covers post-index provider embedding backfill, and `packages/core/tests/test_providers.py` covers Ollama `/api/embed` batch request shape.
- Historical live qwen3.5 semantic-edge generation required increasing edge `num_predict` from 256 to 1024 for real query prompts; current clean provider settings keep that larger response budget for `gemma4:e4b`.
- `docs/qa/2026-05-17-clean-amd-gemma4-free-query-and-edge-qa.json` records six real free-form queries against the clean gemma DB. Persisted Stage 2 graph proof remains the live `data/asip.db` `gemma4:e4b` semantic/doc-node jobs, while one clean-DB query-scoped and one batch gemma attempt are documented as robustness failures because they produced no persistable edges or truncated JSON.
- 2026-05-17 targeted batch QA `docs/qa/2026-05-17-graph-function-section-batch-qa.md` records a real `asip.cli semantic-edges-batch --db data/asip.db --limit 2 --batch-size 1` run using `ollama/gemma4:e4b`: `candidate_count=2`, `edge_count=11`, `job_id=10`.
- Provider extra headers now support late-bound secret expansion for both embedding and semantic-edge providers: `env:VAR` for whole-header values and `${ENV:VAR}` inside strings such as `Bearer ${ENV:OPENAI_API_KEY}`. Expansion happens only when the request is built, leaves the saved provider settings unchanged, and raises a clear `unset environment variable` error before transport if the variable is missing.
- Targeted regression coverage: `packages.core.tests.test_providers.EmbeddingProviderTests.test_extra_headers_expand_environment_placeholders_without_persisting_secret`, `packages.core.tests.test_providers.EmbeddingProviderTests.test_extra_header_env_placeholder_requires_existing_variable`, `packages.core.tests.test_providers.EmbeddingProviderTests.test_extra_headers_expand_direct_environment_reference`, `packages.core.tests.test_semantic_edges.SemanticEdgeFeatureTests.test_edge_provider_extra_headers_expand_environment_placeholders`, and `packages.core.tests.test_semantic_edges.SemanticEdgeFeatureTests.test_edge_provider_extra_header_missing_environment_stops_before_transport`.
- 2026-05-18 bounded provider-backfill smoke is recorded in `docs/qa/2026-05-18-g06-provider-backfill-smoke.md` and `.json`. A SQLite backup copy of live `data/asip.db` ran `python3 -m asip.cli provider-embeddings --limit 128 --batch-size 8` through local Ollama `nomic-embed-text:latest`: `exit_code=0`, `embedded_chunks=128`, elapsed `17.703s`, and provider embedding count increased from `32` to `160` in the temp DB. This is product CLI/provider evidence, not full provider-vector coverage.
- 2026-05-18 full local temp-copy provider backfill is recorded in `docs/qa/2026-05-18-g06-full-provider-backfill-tempdb-qa.md` and `.json`. A backup copy of current `data/asip.db` ended with `21884 / 21884` chunks covered by `ollama/nomic-embed-text:latest`, `missing_provider_embeddings=0`, and `10770` long chunks marked with truncation metadata after fixing batch splitting and context-length handling. The resumed full job embedded `12572` remaining chunks in `2388.07s`; earlier failed job 9 exposed the Ollama context-limit issue. The same artifact records a real `gemma4:e4b` query semantic-edge call after dedupe hardening: job 12 generated one persisted edge for `GCVM_L2_CNTL` in `51.44s`.
- 2026-05-18 query-time provider rerank wiring is recorded in `docs/qa/2026-05-18-g06-query-time-provider-rerank-qa.md`. A RED/GREEN test proves `query_evidence()` embeds the query through the configured provider, filters vector search to the same stored `provider/model`, and returns `retrieval_sources=["provider-vector"]` plus provider/model/source metadata. A local Ollama smoke over a throwaway SQLite DB proves real `ollama/nomic-embed-text:latest` query embedding and stored provider embedding participation with `vector_score=1.0`.

## Remaining Gap

Saved embedding settings can drive the provider client in indexing, post-index backfill, and query-time provider-vector rerank. Failed live indexing/query embedding calls fall back to deterministic vectors with explicit metadata. Local Ollama semantic-edge model calls are now proven against the clean AMD DB with `gemma4:e4b` provider smoke and against the live graph DB with persisted `gemma4:e4b` semantic/doc-node jobs. Credentialed live OpenAI-compatible QA is still open.

Local Ollama availability, a small job-level AQ09 provider path, isolated Web BFF AQ09 provenance, Settings UI AQ09 wiring, one real UI-to-BFF isolated-DB AQ09 run, callable semantic-edge product jobs, and clean DB local Ollama AQ09 provider checks are now proven. Credentialed live OpenAI-compatible switching still needs credentials or an explicit user-accepted local-compatible endpoint boundary.

The batch semantic-edge product path is now implemented and tested for indexed candidates and graph refresh. Remaining provider risk is operational: local Ollama generation is slow/heavy on `gemma4:e4b`, and a credentialed live OpenAI-compatible endpoint has not been supplied.

The current full local coverage proof is a named temp-copy artifact, not a credentialed hosted provider proof. Provider status must still not imply that `qwen`, `gemma`, `nomic`, or any OpenAI-compatible model generated every current default-DB vector unless job metadata proves it for that DB. Query-time provider-vector wiring is proven, but semantic ranking quality at production scale still depends on corpus coverage and model quality.

OpenAI-compatible smoke currently validates request shape and safe secret/env header expansion, but does not perform a credentialed live OpenAI-compatible endpoint check because no live credentialed endpoint has been supplied.

## Acceptance Criteria

- Edge provider and embedding provider can use different base URLs, API paths, models, and headers.
- Ollama detection uses the currently configured base URL, not a hardcoded local URL.
- Provider smoke performs a real lightweight request or returns an explicit failure with evidence.
- OpenAI-compatible headers support environment variable expansion or a documented safe secret path.
- Query/index jobs receive, record, and use the provider settings for embeddings or semantic-edge extraction.
- Batch semantic-edge jobs receive, record, and use the configured edge provider settings, including base URL, API path, model, extra headers, timeout, and local Ollama options such as `think:false`.
- UI/API status distinguishes query-scoped semantic-edge jobs from batch corpus semantic-edge jobs and shows provider/model provenance for each.
- UI status is `unverified` until a smoke/index/query check succeeds.
- Settings hydrate from backend state in a fresh browser session, not only localStorage.

## Required Tests

- Core test: saved provider settings are passed into an embedding or semantic-edge job, not only metadata.
- API/E2E test: different edge and embedding base URLs persist and are used.
- Web test: Settings can run AQ09 through the acceptance endpoint and display provider check provenance.
- API test: provider smoke reports success/failure based on real or mocked backend response.
- Ollama detection test: changing base URL changes the called `/api/tags` target.
- MCP test: Ollama detection returns `requested_url`, models, and structured error evidence.
- UI test: fresh browser session loads backend provider settings.
- Core/API/Web test: batch semantic-edge generation uses the saved edge provider settings, persists graph edges, and reports structured failure details when the provider fails or times out.
- Regression test: the model label shown in the Web top bar/settings is hydrated from backend settings and matches the provider/model recorded on the last edge job; stale localStorage must not override backend state.
- QA smoke: bounded `provider-embeddings` backfill on a temp copy records elapsed time, provider/model, embedded chunk count, and no full-coverage claim.

## Not Closed Until

The model shown in Settings is the model actually called by the job that generated embeddings or semantic edges, with fallback metadata visible and live model QA recorded.
