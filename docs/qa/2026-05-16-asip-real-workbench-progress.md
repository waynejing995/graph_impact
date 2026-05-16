# ASIP Real Workbench Progress QA

Date: 2026-05-16
Status: partial pass; goal remains open

## 2026-05-16 Live SQLite Workbench Update

Implemented and verified after the gap document split:

- Core live service: `packages/core/src/asip/workbench.py`
- CLI commands: `asip.cli index`, `asip.cli query`, `asip.cli graph`, `asip.cli corpus-add`
- Next BFF routes now call live core/CLI paths for index, query, graph, and corpus add/list.
- FastAPI and MCP query/graph paths now use the same live SQLite workbench service.
- FastAPI and MCP corpus control-plane paths can add/list/index a temp corpus, then query a unique symbol from it.
- FastAPI and MCP evidence/entity paths can fetch evidence detail by id and explain an entity with evidence rows, resolved chains, and graph data from a temp DB.
- FastAPI and MCP resolver-profile control-plane paths can add/list/validate a dynamic profile against a temp DB.
- FastAPI and MCP provider-settings paths can round-trip independent edge/embedding settings and run Ollama `/api/tags` detection against a supplied base URL.
- Corpus add now persists backend SQLite state.
- Ollama provider smoke now performs a real `/api/tags` request attempt and reports requested URL/status/error evidence.
- `/graph` now requests `/api/workbench/graph` on page load and renders API-provided weighted edges with `data-weight` and stroke-width emphasis.
- `/graph` now requests a no-seed global graph instead of silently sending the old `DOORBELL_INTERRUPT_DISABLE` seed; selected-seed graph expansion remains available through API/CLI.
- Query empty results now render a deliberate no-match empty state instead of silently falling back to seed evidence rows.
- Query API HTTP 500 now renders a deliberate error state, clears rows, and does not merge static seed evidence into the table or query graph.
- The initial Evidence Workbench route now issues a live default query before showing success rows instead of using static `evidenceIndex` as the first successful state.
- Query request sequencing now prevents a slower initial default query from overwriting a later user query or no-match result.
- Query graph fallback now derives from live API rows only when a graph payload is omitted, instead of mixing in static evidence rows.
- Graph API HTTP 500 now renders a deliberate graph error/empty state and does not fall back to static seed graph nodes.
- Web BFF query and graph GET routes no longer call implicit index initialization; they accept explicit `dbPath` and read from that DB without falling back to default indexed data.
- MCP read tools no longer call `_ensure_index()`. `search_evidence`, `graph_expand`, `run_acceptance`, `evidence_detail`, and `entity_explain` respect explicit missing/empty DBs without creating the DB or indexing default corpora.
- FastAPI `/graph` now accepts `db_path`; `/query`, `/graph`, and `/evidence/{id}` have regression coverage for explicit DB/no-default-fallback behavior.
- Settings now hydrates from backend provider settings in a fresh browser session, while guarding against async hydration overwriting user edits.
- A minimal resolver-profile indexing path now proves a saved wrapper profile can change generated evidence, including access type and resolved-chain metadata.
- Indexing can record deterministic fallback embedding provenance for configured embedding provider/model settings. This proves storage/job wiring only, not real model quality.
- NetworkX now backs `expand_query_graph()` for hop-bounded weighted subgraphs and reports `graph_runtime: networkx`.
- Indexing can call a configured embedding provider transport and store returned vectors with provider metadata; failed live calls are marked as deterministic fallback.
- Query retrieval now merges vector adapter matches into ranked evidence, including `vector_score` / `retrieval_sources` metadata for vector-backed rows.
- Query filtering by IP block and ASIC/generation is wired through core, Web API, and UI controls.
- Settings now separately configures embedding API path and embedding extra headers.
- Default full-corpus configs include real MxGPU IH_RB_CNTL and SDMA queue acceptance-oriented queries.
- Core/CLI acceptance runner now records AQ01-AQ09 artifact shape, gap IDs, required surfaces, pass/fail/partial status, row counts, evidence ids, source paths, graph counts, provider settings, and clean DB path.
- Core/CLI acceptance runner can now filter selected AQ IDs with `--query-id` and print the full runner payload with `--full`.
- Web BFF, FastAPI, and MCP can now execute selected acceptance queries instead of only listing historical artifacts.
- Corpus UI rows now have explicit index-selection checkboxes; `Run index` sends only selected corpus ids and updates selected rows with the returned status.
- Registered corpus indexing now treats a missing `source_root` as a failure instead of reporting `indexed` with zero documents.
- Registered corpus indexing now treats unknown selected corpus ids as failed index jobs instead of reporting zero-document success.
- Configured raw-corpus indexing now treats missing configured scan roots as failed index jobs instead of reporting zero-document success.
- Corpus UI now marks selected rows `failed` when indexing fails, and the error remains visible in action feedback.
- A Web UI full-loop smoke test creates a temporary local Markdown corpus, adds it on `/corpus`, indexes only that corpus, then queries its unique symbol from Evidence Search.
- Resolver Profiles UI now validates a user-created Python profile against dynamic source text and shows disabled profile status when `Enable resolver profile` is unchecked.
- Evidence Workbench inspector now renders source preview, resolved chain, and relationship lines from selected live query rows instead of static page config.
- Selecting a different live evidence row updates the inspector to that row's resolved chain and snippet.
- Web BFF AQ09 acceptance can run against an isolated provider-configured SQLite DB and reports independently configured edge and embedding provider provenance.
- Settings UI now has `Run AQ09 acceptance`, saves the current provider settings, calls Web BFF selected acceptance execution for `AQ09`, and displays embedding plus semantic-edge provider/model checks.
- Settings UI can run AQ09 against a user-supplied SQLite DB path through the real Web BFF/core runner.
- Provider status now stays `unverified` after settings save/backend hydration/edit/detection, becomes `verified` only after provider smoke or AQ09 checks pass, and becomes `failed` on provider smoke/AQ09 failure.
- Semantic-edge generation is now a workbench product path: core reads indexed evidence rows, calls the configured edge provider, persists generated edges into SQLite, CLI exposes `asip semantic-edges`, Web BFF exposes `POST /api/workbench/semantic-edges`, and `/graph` can run `Generate semantic edges`.
- FastAPI live runtime smoke now starts a Uvicorn server and verifies an HTTP provider-settings read without TestClient or missing-DB mutation.
- MCP server registration now exposes the full implemented product tool set through the FastMCP entrypoint, verified with a fake FastMCP matrix test.

Verification:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest apps/api/tests/test_app.py apps/api/tests/test_runtime.py apps/mcp/tests/test_tools.py apps/mcp/tests/test_server.py -v
pnpm --filter web exec tsc --noEmit
pnpm --filter web exec playwright test tests/workbench-api.spec.ts --reporter=list
pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts --reporter=list
pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts --reporter=list
```

Results:

- Core unittest: 77 run, OK, 1 skipped because the system Python sqlite3 build cannot load native sqlite-vec extensions. Latest run includes source-type gated acceptance, DB-health gated acceptance, register-header source typing, and doc-row diversity tests.
- FastAPI + MCP unittest: 39 run, OK, 1 skipped because the optional live `mcp` package is not installed.
- TypeScript check: passed.
- Web API Playwright: 18 passed.
- Web smoke Playwright: 34 passed.
- Visual anchor route tests: 13 passed.
- Combined Web smoke + visual route tests: 27 passed.
- Targeted NetworkX graph/provider/filter/settings tests passed after the latest changes:
  - provider transport integration core test: passed.
  - IP/ASIC core filter test: passed.
  - Web API IP filter test: passed.
  - Web UI IP/ASIC filter test: passed.
  - Settings embedding path/header smoke test: passed.
  - G14 query/graph HTTP 500 truthfulness tests: passed.
  - G14 initial live query, stale response suppression, and row-only graph fallback tests: passed.
  - G03 global weighted graph without default seed tests: passed.
  - G02/G09 vector-backed evidence retrieval without lexical overlap test: passed.
  - G10 acceptance runner fixture tests: passed.
  - G04 selected Corpus UI indexing test: passed.
  - G04 missing registered corpus root failure test: passed.
  - G04 unknown registered corpus id failure test: passed.
  - G04 configured missing source root failure test: passed.
  - G04 real Web UI add-index-query full-loop test: passed.
  - G05 resolver profile UI validation test: passed.
  - G05 resolver disabled status UI test: passed.
  - G02 live evidence inspector linkage test: passed.
  - G02 selected evidence row inspector update test: passed.
  - G06/AQ09 Web API provider provenance test: passed.
  - G06/AQ09 Settings provider acceptance action test: passed.
  - G06 provider status semantics test: passed for save/hydration unverified and smoke/AQ09 verified transitions.
  - G06 non-mocked AQ09 Settings DB-path test: passed with real Web BFF/core runner and a local fake Ollama edge HTTP server.
  - G03/G06 semantic-edge product job core/API/UI tests: passed with indexed evidence, configured provider settings, persisted SQLite graph edges, and `/graph` refresh.
  - G07 semantic-edge FastAPI/MCP parity tests: passed after RED failures for FastAPI 404 and missing MCP import.
  - G14 acceptance failure, corpus/resolver empty API, graph relationship-panel, and provider smoke hydration-race truthfulness tests: passed.
- Clean CLI acceptance artifact run:
  - DB: `/tmp/asip-acceptance-clean-2026-05-17.db`
  - Index summary: 26 documents, 351 chunks, 5812 evidence rows, 23 edges, 1347 scanned files.
  - Artifacts: `docs/qa/2026-05-17-acceptance-clean-qwen35.json`, `docs/qa/2026-05-17-acceptance-clean-qwen35.md`
  - AQ summary: 9 total, 0 pass, 8 partial, 1 fail.
  - AQ09 failure reason: provider settings are required for this acceptance query.
- Acceptance artifact visibility:
  - Web BFF `/api/workbench/acceptance` lists `acceptance-clean-qwen35` first.
  - FastAPI `/acceptance/runs` and MCP `acceptance_runs()` include the new artifact.
  - `/acceptance` page metrics display `partial` counts.
- Acceptance selected-runner execution:
  - CLI `asip acceptance --query-id AQ01 --full` returns a full `asip.acceptance` payload.
  - Web BFF `POST /api/workbench/acceptance/run` executes `AQ01` with `CLI` and `Web` surfaces.
  - FastAPI `POST /acceptance/run` executes `AQ01` with `API` and `MCP` surfaces.
  - MCP `run_acceptance(query_ids=["AQ01"], surfaces=["MCP"])` executes the same core runner.
- API/MCP control-plane parity:
  - FastAPI and MCP add/list/index a temp corpus and query a unique symbol from the indexed corpus.
  - FastAPI and MCP fetch evidence detail by evidence id and explain an entity with evidence rows/resolved chains/graph data.
  - FastAPI and MCP add/list/validate a temp resolver profile.
  - FastAPI and MCP persist edge/embedding provider settings through temp SQLite DBs.
  - FastAPI and MCP Ollama detection reports `requested_url` and structured failure evidence for an unreachable supplied base URL.
- API/MCP read-route no-mutation:
  - MCP explicit missing/empty DB tests for search, graph, acceptance, evidence detail, and entity explain pass without creating DB files or indexing default corpora.
  - FastAPI explicit missing/empty DB tests for query, graph, and evidence detail pass without default DB fallback.
  - Core workbench read functions now avoid migrating missing/empty DBs for query, graph, global graph, and provider settings reads.
  - Provider settings show, resolver profile list/validate, and corpus list now handle explicit missing/empty DBs without creating DB files or migrating status/list schemas.
- FastAPI/MCP surface runtime:
  - Uvicorn live HTTP smoke serves `/providers/settings` without TestClient.
  - Root `pnpm dev:api` starts the Uvicorn server and serves `/providers/settings` over HTTP.
  - MCP server registration exposes search, graph, semantic-edge generation, evidence/entity detail, corpus, resolver, provider, Ollama detection, acceptance listing, and acceptance execution tools through the FastMCP entrypoint.
- Ollama provider smoke:
  - `nomic-embed-text:latest` returned 768-dimensional embeddings.
  - `qwen3-embedding:4b` returned 2560-dimensional embeddings.
  - `qwen3.5:4b` needed `think:false` to produce JSON instead of only thinking.
  - `gemma4:e4b` produced compact JSON but used roughly 12.96 GB resident model memory during the smoke.
  - Details: `docs/qa/2026-05-17-ollama-provider-smoke.md`.
- AQ09 provider acceptance smoke:
  - Artifact: `docs/qa/2026-05-17-aq09-provider-smoke-ollama.json`
  - Embedding provider check: `ollama` / `nomic-embed-text:latest`, 1 provider-sourced embedding, 0 deterministic fallbacks.
  - Semantic-edge provider check: `ollama` / `gemma4:e4b`, 1 edge.
  - Summary: 1 total, 0 pass, 1 partial, 0 failed because final clean API/Web surfaces were unchecked in that artifact.
- Web AQ09 provider acceptance:
  - `pnpm --filter web exec playwright test tests/workbench-api.spec.ts --reporter=list`: 18 passed, including Web/MCP query/evidence/entity agreement, explicit-empty-DB query/graph no-fallback tests, isolated raw-index fixture DB, an isolated DB AQ09 run with OpenAI-compatible embedding provenance, explicit unreachable Ollama semantic-edge failure evidence, and semantic-edge API graph generation.
  - `pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts --reporter=list`: 34 passed, including the Settings `Run AQ09 acceptance` action, a non-mocked user-supplied DB path run through the real Web BFF/core runner, G14 route truthfulness, and the `/graph` semantic-edge action.
- Historical clean provider acceptance rerun under the older gate:
  - Artifacts: `docs/qa/2026-05-17-acceptance-clean-qwen35-provider-rerun.json` and `docs/qa/2026-05-17-acceptance-clean-qwen35-provider-rerun.md`.
  - DB: `/tmp/asip-acceptance-clean-2026-05-17.db`.
  - Provider settings: edge `ollama/qwen3.5:4b`, embedding `ollama/nomic-embed-text:latest`.
  - Real semantic-edge generation: `asip.cli semantic-edges` generated 5 persisted edges from 6 evidence rows for `GCVM_L2_CNTL ENABLE_L2_CACHE regGCVM_L2_CNTL`.
  - Historical acceptance summary: 9 total, 9 passed, 0 partial, 0 failed across CLI/API/Web/MCP surface labels, but this artifact predates the source-type and DB-health gates.
  - Provider checks: 9058 provider-sourced embeddings, 382 explicit deterministic fallbacks, and qwen3.5 semantic-edge smoke with 1 edge.
  - Six real clean-DB query timings: 3.782s, 5.927s, 4.726s, 4.378s, 5.403s, and 4.822s, each returning 12 rows and NetworkX graph metadata. This is functional evidence but keeps G15 open for performance.
- Current source-gated acceptance rerun:
  - Artifacts: `docs/qa/2026-05-17-acceptance-clean-qwen35-source-gated-current.json` and `docs/qa/2026-05-17-acceptance-clean-qwen35-source-gated-current.md`.
  - Summary: 9 total, 0 passed, 0 partial, 9 failed.
  - Database health: `mxgpu` remained `indexing`, and index job 3 failed after the interrupted provider embedding reindex.
  - AQ05 additionally fails with `required source types missing: pdf`.
  - This is now the authoritative acceptance status for `/tmp/asip-acceptance-clean-2026-05-17.db`.
- Synthetic multi-source fixture acceptance:
  - Artifacts: `docs/qa/2026-05-17-acceptance-multisource-fixture.json` and `docs/qa/2026-05-17-acceptance-multisource-fixture.md`.
  - DB: `/tmp/asip-multisource-clean-2026-05-17.db`.
  - Summary: 2 total, 2 passed, 0 partial, 0 failed.
  - DB health: pass; 5 documents, 6 chunks, 34 evidence rows, 7 graph edges, 1 corpus, and 1 index job.
  - Document source counts: `code=1`, `doc=1`, `pdf=1`, `register=2`; evidence source counts: `code=23`, `doc=3`, `pdf=4`, `register=4`.
  - AQ05 passes with `code`, `doc`, `pdf`, and `register`; AQ06 passes with `code` and `register`; graph runtime is `networkx`.
  - This proves the source-diverse fixture path and source-gated runner mechanics, but it does not prove real AMD source roots, AQ01-AQ09, live provider closure, final browser visual QA, or performance.
- Manual temp-DB verification against local `/tmp/asip-mxgpu` and `/tmp/asip-linux-amdgpu`: default raw index produced 7 documents, 13 chunks, 153 evidence rows, 23 edges, 1328 scanned files; `IH_RB_CNTL` and `SDMA0_QUEUE0_RB_CNTL SDMA1_QUEUE0_RB_CNTL` both returned non-empty query results.

The goal remains open because the current source-gated acceptance artifact is 0/9 on the old DB, final real AMD indexed PDF/page citation and source diversity are still missing, credentialed OpenAI-compatible boundaries remain unresolved, native sqlite-vec verification in the target Python runtime is still open, performance/rebuild evidence is incomplete, full visual screenshot recapture is stale, and final design/architecture review is not closed.

## Verified Changes

- Web BFF reads real repo artifacts:
  - `configs/edge_cases/full-corpus-qwen35.json`
  - `docs/qa/2026-05-16-full-corpus-edge-generation-qwen35-strict-batch1.json`
  - `docs/qa/2026-05-16-full-corpus-edge-generation-gemma4-e4b-strict-batch1.json`
  - `configs/resolvers/*.yaml`
- Evidence query calls `/api/workbench/query` and updates table plus graph.
- Evidence Workbench initial render calls `/api/workbench/query` for the default query before showing success rows.
- More than five real ASIP queries return evidence and generated graph edges through the API.
- The no-match UI path displays an explicit empty state and keeps the graph empty for an API empty graph response.
- Stale query responses are ignored so the latest user query owns the displayed rows/graph.
- If a query API response omits graph data, the temporary graph derives only from that response's rows and does not merge static seed evidence.
- Query and graph backend failure paths display explicit error/empty states and do not render seed evidence/graph nodes.
- The `/graph` route is API-backed in Playwright and no longer validated by fixed seed labels/edge counts.
- The `/graph` route now requests global graph data without a default seed; Playwright verifies the request has no `seed`, no `queryId`, and no `DOORBELL_INTERRUPT_DISABLE` default.
- Corpus, resolver profile, and acceptance pages load API data.
- Corpus page can unselect one API corpus, index only the checked corpus, and show the returned `indexed` status for that row.
- Corpus page can mark a selected row `failed` when index fails, and can add/index/query a temporary local corpus through the real BFF/Core/SQLite path.
- Resolver profile page can add/validate a Python-style profile through the real BFF/Core path and can visibly show disabled profiles.
- Evidence Search keeps table rows, query graph, and inspector content tied to the same live query response; clicking another live row changes inspector content.
- Acceptance execution is available through Web BFF, FastAPI, and MCP for selected AQ IDs.
- Settings separates edge chat and embedding provider fields, supports extra headers, Ollama detection, and provider smoke.
- Settings can run AQ09 provider acceptance through Web BFF and display provider/model provenance.
- Settings loads backend provider settings in a fresh browser session without relying on localStorage.
- Resolver profile core tests cover configurable C/C++ wrappers and a toy Python profile.
- Resolver profile indexing test proves a configured wrapper can change generated evidence for a user-added corpus.
- SQLite storage tests cover FTS5, vector fallback search, graph edges, and NetworkX graph construction.
- Workbench query tests now cover vector-backed evidence retrieval through the storage vector adapter, not only vector storage.
- Provider/embedding provenance test proves configured embedding provider/model can be recorded on indexed chunks through a deterministic fallback vector.
- PDF conversion test covers a text-based PDF fixture with page metadata.
- MCP-facing tool functions are tested for evidence search, evidence detail, entity explain, graph expansion, corpus add/list/index, resolver inspect/list/add/validate, provider settings/Ollama detection, acceptance run listing, and selected acceptance execution.

## Broader Commands Still Required Before Final Completion

```bash
pnpm --filter web exec playwright test --reporter=list
PYTHONPATH=packages/core/src python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v
PYTHONPATH=. python3 -m unittest apps/mcp/tests/test_tools.py -v
pnpm --filter web build
pnpm --filter web lint
git diff --check
```

## Remaining Work Before Final Completion

- Run the full Web Playwright suite after the latest functional changes, not only the targeted smoke/API/visual slices.
- Run Web production build, lint, and diff whitespace checks after generated artifacts are cleaned.
- Verify native sqlite-vec extension loading or document the fallback adapter boundary as user-accepted deferral.
- Replace deterministic fallback embeddings with real configured Ollama/OpenAI-compatible embedding calls, or document that model-backed embeddings are deferred.
- Run semantic-edge generation against the final clean AMD corpus and record live model/provider evidence rather than relying only on local fake endpoint tests.
- Prove the final graph API/UI uses NetworkX-backed graph evidence from the healthy clean DB, not only fixture or mocked Playwright payloads.
- Run a real or accepted reduced AMD text-based PDF smoke through the index/query/API/UI path and record source/page citation evidence.
- Prove ASIC/IP metadata filtering against representative real AMD queries, or explicitly defer the remaining metadata depth.
- Regenerate or re-review 2K visual QA screenshots for every route after the functional changes.
- Review every gap document and the MVP design doc before any commit/push or goal completion claim.
