# G10 Testing Acceptance And Visual QA

Status: Blocking

## Requirement

Completion requires TDD, automated tests, all nine MVP acceptance queries, acceptance QA, and post-functional-change visual QA against individual anchors.

Every page must support light and dark themes. Visual QA targets a 2K desktop baseline.

## Current Evidence

- There are core tests for storage, documents, resolver profiles, workbench indexing/query/schema, CLI, corpus state, and provider settings.
- There are FastAPI/MCP tests for live SQLite query and graph behavior.
- There are Playwright API and smoke tests for query, graph, corpus, resolver profile, provider settings, Ollama smoke, and route rendering.
- There are independent visual anchor prompts/images for `/`, `/graph`, `/corpus`, `/resolver-profiles`, `/acceptance`, `/settings`, and logo.
- Existing QA artifacts show Qwen and Gemma full-corpus runs, but latest strict runs are not all passing.
- Latest verification recorded in the gap ledger includes core unittest 77 run with 1 native sqlite-vec skip, API/MCP unittest 39 run with 1 optional live MCP skip, TypeScript check pass, Web API 18 passed, Web smoke 34 passed, and visual route tests 13 passed. Additional targeted tests cover embedding provider transport integration, vector-backed retrieval without lexical overlap, IP/ASIC filtering, independent embedding API path/header settings, G14 query/graph HTTP 500 truthfulness, G14 initial live query/static graph fallback truthfulness, G14 Web BFF query/graph read-route no-mutation, G14 MCP/FastAPI no-auto-index read behavior, G14 status/list no-migration behavior, G14 acceptance failure/corpus empty/resolver empty/graph relationship-panel truthfulness, G02 live evidence inspector linkage, G03 no-seed global weighted graph behavior, semantic-edge product job wiring, configured non-query doc/PDF/register ingestion, provider acceptance provenance, G04/G05/G06 API/MCP control-plane parity, G04 selected Corpus UI indexing, G04 invalid-source and zero-document false-success prevention, G04 real UI add-index-query flow, G05 resolver UI validation and disabled status, G07 evidence/entity detail parity, G07 Web/MCP query/evidence/entity agreement, G07 semantic-edge API/MCP parity, G07 FastAPI live HTTP smoke, G07 root `pnpm dev:api` startup smoke, G07 MCP server tool-matrix registration, and G10 acceptance artifact generation/execution.
- G10 now has a core acceptance runner in `packages/core/src/asip/acceptance.py` with a default AQ01-AQ09 matrix, gap IDs, required surfaces, clean DB path, provider settings, row counts, evidence ids, source paths, graph counts, and JSON/Markdown artifact writing.
- `asip.cli acceptance --db ... --output-json ... --output-md ...` now exposes that runner for repeatable CLI QA.
- `asip.cli acceptance --query-id AQ01 --full` can execute a selected acceptance query and print the full `asip.acceptance` payload for product surfaces.
- A clean CLI acceptance run against `/tmp/asip-acceptance-clean-2026-05-17.db` wrote `docs/qa/2026-05-17-acceptance-clean-qwen35.json` and `docs/qa/2026-05-17-acceptance-clean-qwen35.md`: 9 total, 0 pass, 8 partial, 1 fail. The partial rows are intentionally not treated as full passes because API/Web/MCP surfaces are not yet proven; AQ09 fails because provider settings are required.
- Web BFF, FastAPI, MCP acceptance listing, and the `/acceptance` page can now read/display the new `asip.acceptance` artifact shape, including `partial` counts. Web BFF `POST /api/workbench/acceptance/run`, FastAPI `POST /acceptance/run`, and MCP `run_acceptance()` can execute selected AQ IDs and return the full runner payload. This proves runner execution plumbing across surfaces, not final clean AMD pass status.
- `docs/qa/2026-05-17-aq09-provider-smoke-ollama.json` proves CLI-level provider checks for AQ09: provider-sourced embedding, zero deterministic embedding fallback, and one semantic edge from the configured Ollama edge model. Web API now also verifies AQ09 provider provenance from an isolated SQLite DB, Settings UI wiring can trigger AQ09 through the same Web BFF acceptance endpoint, a non-mocked UI smoke can run AQ09 against a user-supplied isolated DB through the real BFF/core runner plus local fake edge HTTP server, and FastAPI/MCP semantic-edge parity is tested. Final clean AMD corpus API/Web/MCP QA remains open.
- Historical provider artifact `docs/qa/2026-05-17-acceptance-clean-qwen35-provider-rerun.json` and `.md` used the older acceptance gate and reported AQ01-AQ09 pass across CLI/API/Web/MCP surface labels, with provider checks passing for `ollama/nomic-embed-text:latest` embeddings and `ollama/qwen3.5:4b` semantic-edge smoke.
- That historical clean provider artifact reports `source_types: ["code"]` for every AQ01-AQ09 result, including AQ05. It is provider/provenance evidence only, not final acceptance.
- Current source-gated rerun `docs/qa/2026-05-17-acceptance-clean-qwen35-source-gated-current.json` and `.md` is the authoritative current artifact for that DB: 9 total, 0 passed, 9 failed. It fails because the DB has `mxgpu` stuck in `indexing`, a failed index job, and AQ05 is missing `pdf`.
- Synthetic multi-source fixture artifact `docs/qa/2026-05-17-acceptance-multisource-fixture.json` and `.md` proves the current source-gated runner can pass on a healthy source-diverse fixture: 2 total, 2 passed, DB health pass, AQ05 with `code/doc/pdf/register`, AQ06 with `code/register`, and `graph_runtime: networkx`. This is not final acceptance because it covers only AQ05/AQ06 and a synthetic fixture DB.
- Current clean AMD acceptance artifact `docs/qa/2026-05-17-acceptance-clean-amd-qwen35-provider-current.json` and `.md` records AQ01-AQ09 against `/tmp/asip-clean-amd-qwen35-provider-2026-05-17.db`: 9 total, 9 passed, DB health pass, surfaces `CLI/API/Web/MCP`, provider-sourced embeddings `ollama/nomic-embed-text:latest` count 961, and semantic-edge smoke `ollama/qwen3.5:4b`.
- Current free-query and semantic-edge QA artifact `docs/qa/2026-05-17-clean-amd-free-query-and-edge-qa.json` and `.md` records six non-empty free-form queries, source types `code/doc/pdf/register`, NetworkX graph runtime for all query graphs and global graph, and two generated qwen3.5 semantic-edge jobs.
- RED/GREEN fixes from this pass: PDF fixture extraction failed at 0 chunks before regenerating the reduced AMD PDF and adding fallback compressed-stream coverage; `dev:api` and MCP tool matrix failed before product route/server registration fixes; AQ06 failed at 8/9 before diverse selection protected injected `register` rows; qwen3.5 semantic-edge generation failed with truncated JSON until edge `num_predict` was raised to 1024.
- Current visual QA `docs/qa/visual-qa-2026-05-17/visual-qa.md` records 2K route screenshots for six routes in dark and light themes: 6 passed, 0 failed. `/graph` shows 12 nodes and 4 weighted edges in both themes.
- Latest automated verification after these changes: core unittest 85 OK with 1 sqlite-vec skip; API/MCP unittest 39 OK with 1 optional MCP runtime skip; TypeScript `pnpm --filter web exec tsc --noEmit` passed; Web API 18 passed; Web smoke 35 passed; visual route tests 13 passed.
- Existing visual QA documents that say `PASS` predate later functional changes. They are historical evidence only until fresh page-by-page browser QA is recorded.
- The [MVP Acceptance Query Matrix](2026-05-16-mvp-acceptance-query-matrix.md) now tracks all nine acceptance queries individually.

## Remaining Gap

The test suite now proves important pieces, including API-backed graph rendering, backend Settings hydration, no-match UI behavior, minimal resolver-profile indexing influence, a repeatable core/CLI acceptance artifact runner, qwen3.5 semantic-edge generation, clean AMD AQ01-AQ09, six real free-form queries, and 2K visual route QA. It still needs final G11/G17 design/spec reconciliation before completion:

`add corpus -> index raw inputs in a clean DB -> query live index -> inspect evidence -> render weighted graph -> verify visual anchors`.

Visual QA has been rerun after the latest functional changes; it must be rerun again if more UI-affecting changes land before commit.

The final acceptance run must use a clean named SQLite database. The dirty local `data/asip.db` can be useful for development, but it must not be treated as final QA evidence if it contains local test corpora or provider settings.

The old clean provider AQ01-AQ09 pass is superseded by the source-gated failure artifact. The current clean AMD artifact now provides the healthy source-diverse DB evidence, current screenshots/visual-anchor review, and current automated suite evidence. Final QA still needs design/spec reconciliation and git hygiene review.

Final QA must follow [Final Clean Evidence Package Gate](2026-05-17-final-clean-evidence-package.md); a narrower test pass cannot close G10/G11.

## Acceptance Criteria

- Each production code change has RED/GREEN evidence or a documented reason when the change is docs-only.
- Full Web, core, API, MCP, build, lint, and diff checks pass.
- All nine MVP acceptance queries from `docs/specs/2026-05-16-asip-mvp1-design.md` are run and recorded, with source diversity limitations called out instead of hidden.
- No-match query, provider failure, invalid corpus, and resolver validation failure states are tested.
- Acceptance page reads current artifacts or runs the acceptance runner.
- Visual QA compares every live route to its own canonical anchor, not a combined board.
- QA covers `/`, `/graph`, `/corpus`, `/resolver-profiles`, `/acceptance`, `/settings`, logo, light theme, dark theme, and route navigation persistence.

## Required Tests

- Full Playwright suite.
- Core unit/integration suite.
- FastAPI and MCP tests, including live runtime smoke when required.
- Core/CLI acceptance runner tests for AQ01-AQ09 artifact shape and pass/fail truthfulness. Implemented for fixture DB; final AMD clean DB run remains open.
- Core/CLI acceptance runner tests now fail when required source types are missing and when corpus/job health is not clean.
- API/MCP/Web test: acceptance listing includes the new `acceptance-clean-qwen35` artifact and displays partial counts. Implemented for listing/UI visibility.
- API/MCP/Web test: selected acceptance execution returns a full `asip.acceptance` payload for `AQ01`. Implemented for plumbing; final AQ01-AQ09 clean AMD pass/fail evidence remains open.
- Core test: provider acceptance fails without provider settings and passes only when embedding provenance and semantic-edge smoke both pass.
- Core test: provider acceptance can switch to OpenAI-compatible embedding/edge settings without code changes.
- Web API/UI test: AQ09 provider acceptance exposes independently configured edge and embedding provider provenance through `/api/workbench/acceptance/run` and the Settings page. Implemented for isolated DB/UI plumbing; clean provider rerun now proves local Ollama qwen3.5/nomic provider checks in the runner artifact, while credentialed OpenAI-compatible closure remains a G06/G13 boundary.
- Web UI test: provider status remains `unverified` after save/backend hydration and changes to `verified` only after mocked provider smoke or mocked AQ09 success. Implemented for UI state semantics; live provider QA remains open.
- Web UI test: Settings can run AQ09 against a user-supplied DB path through the real Web BFF/core runner and a local fake edge HTTP endpoint. Implemented for isolated DB product wiring; final clean AMD corpus and credentialed live provider QA remain open.
- Core/API/Web test: semantic-edge generation can read indexed evidence, call the configured edge provider, persist generated edges into SQLite, and refresh the `/graph` page. Implemented with an isolated DB and local fake Ollama-compatible HTTP endpoint.
- FastAPI/MCP tests: semantic-edge generation calls the same workbench job from `POST /semantic-edges` and `semantic_edges_generate()`. Implemented with isolated DBs and a local fake Ollama-compatible HTTP endpoint.
- Web/MCP agreement test: implemented for Web BFF query/evidence/entity and MCP search/detail/entity functions against the same SQLite DB.
- FastAPI live HTTP smoke: implemented with direct Uvicorn startup, root `pnpm dev:api`, and a read-only provider settings request against an explicit missing DB.
- MCP server tool matrix: implemented with a fake FastMCP runtime proving all implemented product tools are registered by `apps/mcp/server.py`.
- Visual screenshot capture at 2048 x 1280 after final functional changes.
- E2E test for the full loop: add corpus, index, query unique symbol, graph changes, inspector shows source/snippet/resolved chain.
- Design-review checklist mapping ASIP MVP-1 G1-G6 and all nine acceptance queries to evidence.

## Not Closed Until

The final QA document contains command output summaries, screenshot paths, anchor paths, pass/fail per route, all nine acceptance query outcomes, and known residual risks.
