# G06 Provider Settings And Ollama Detection

Status: Partial; settings persist/hydrate, embedding provider calls are wired, qwen3.5 semantic-edge QA is proven locally, and OpenAI-compatible/secret/rerank boundaries remain blocking

## Requirement

Embedding and semantic-edge providers must be configurable independently and support local Ollama plus OpenAI-compatible APIs.

The UI must avoid forcing the user to edit code for base URL, model, API path, or extra headers.

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
- `packages/core/src/asip/workbench.py` exposes `generate_semantic_edges_for_query()`, which reads indexed SQLite evidence rows, calls the configured edge provider, persists generated edges into the SQLite graph store, and records a `semantic_edges` job.
- `asip.cli semantic-edges`, Web BFF `POST /api/workbench/semantic-edges`, and the `/graph` page `Generate semantic edges` action now call that workbench semantic-edge job. Tests cover a real UI/API call path with a supplied DB and local fake Ollama-compatible HTTP endpoint.
- Clean AMD local Ollama evidence is now recorded in `docs/qa/2026-05-17-acceptance-clean-amd-qwen35-provider-current.json` and `.md`: AQ09 provider checks pass with `ollama/nomic-embed-text:latest` provider embeddings (`embedding_count=961`, `fallback_count=0`) plus qwen3.5 semantic-edge smoke (`edge_count=1`).
- `asip.cli provider-embeddings` and `backfill_provider_embeddings()` can batch provider embeddings for already indexed chunks using the current provider settings. `packages/core/tests/test_workbench_backend_state.py` covers post-index provider embedding backfill, and `packages/core/tests/test_providers.py` covers Ollama `/api/embed` batch request shape.
- Live qwen3.5 semantic-edge generation required increasing edge `num_predict` from 256 to 1024 for real query prompts; this is now recorded in the clean AMD provider settings and explains the earlier truncated fenced JSON failure.
- `docs/qa/2026-05-17-clean-amd-free-query-and-edge-qa.json` records two real `asip.cli semantic-edges` jobs generated by `ollama/qwen3.5:4b` against clean AMD evidence rows.

## Remaining Gap

Saved embedding settings can drive the provider client in indexing or post-index backfill, and failed live indexing calls fall back to deterministic vectors with explicit metadata. Local Ollama semantic-edge model calls are now proven against the clean AMD DB with qwen3.5. Query-time provider reranking and credentialed live OpenAI-compatible QA are still open.

Local Ollama availability, a small job-level AQ09 provider path, isolated Web BFF AQ09 provenance, Settings UI AQ09 wiring, one real UI-to-BFF isolated-DB AQ09 run, callable semantic-edge product jobs, and clean DB local Ollama AQ09 provider checks are now proven. Credentialed live OpenAI-compatible switching still needs credentials or an explicit user-accepted local-compatible endpoint boundary.

The current clean AMD DB has partial provider embeddings, not full provider-vector coverage for all chunks. Provider status must not imply that `qwen`, `gemma`, `nomic`, or any OpenAI-compatible model generated every current index vector unless job metadata proves it.

OpenAI-compatible smoke currently validates request shape but does not perform a credentialed live check. Extra headers do not yet support a documented safe secret/env expansion path.

## Acceptance Criteria

- Edge provider and embedding provider can use different base URLs, API paths, models, and headers.
- Ollama detection uses the currently configured base URL, not a hardcoded local URL.
- Provider smoke performs a real lightweight request or returns an explicit failure with evidence.
- OpenAI-compatible headers support environment variable expansion or a documented safe secret path.
- Query/index jobs receive, record, and use the provider settings for embeddings or semantic-edge extraction.
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

## Not Closed Until

The model shown in Settings is the model actually called by the job that generated embeddings or semantic edges, with fallback metadata visible and live model QA recorded.
