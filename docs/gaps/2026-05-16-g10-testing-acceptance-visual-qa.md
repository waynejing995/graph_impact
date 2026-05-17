# G10 Testing Acceptance And Visual QA

Status: Current package-backed graph, acceptance detail, and visual QA pass recorded; final completion gate remains in G11

## Requirement

Completion requires TDD, automated tests, all nine MVP acceptance queries, acceptance QA, and post-functional-change visual QA against individual anchors.

Every page must support light and dark themes. Visual QA targets a 2K desktop baseline.

After the 2026-05-17 user review, visual/functional QA must also prove:

- `/graph` is rendered through a maintained React/npm graph package, not a hand-written SVG layout.
- Acceptance failures and partial results can be expanded to show query-level details, including failure reasons, missing surfaces, source paths/types, row counts, graph counts, and provider checks when present.
- Standard workbench UI uses shadcn-native components or documented package primitives for standard controls.
- Global graph QA must verify the graph contains code function operation nodes/edges, document/PDF section nodes, and batch semantic edges when the indexed corpus contains those inputs.

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
- Current clean AMD acceptance artifact `docs/qa/2026-05-17-acceptance-clean-amd-gemma4-provider-current.json` and `.md` records AQ01-AQ09 against `/tmp/asip-clean-amd-gemma4-provider-2026-05-17-final.db`: 9 total, 9 passed, DB health pass, surfaces `CLI/API/Web/MCP`, provider-sourced embeddings `ollama/nomic-embed-text:latest` count 32, and semantic-edge smoke `ollama/gemma4:e4b`.
- Current free-query QA artifact `docs/qa/2026-05-17-clean-amd-gemma4-free-query-and-edge-qa.json` and `.md` records six non-empty free-form queries, source types `code/doc/pdf/register`, and NetworkX graph runtime for all query graphs and the global graph.
- RED/GREEN fixes from this pass: PDF fixture extraction failed at 0 chunks before regenerating the reduced AMD PDF and adding fallback compressed-stream coverage; `dev:api` and MCP tool matrix failed before product route/server registration fixes; AQ06 failed at 8/9 before diverse selection protected injected `register` rows; historical qwen3.5 semantic-edge generation failed with truncated JSON until edge `num_predict` was raised to 1024; continuation tests caught `smn` prefix handling, generic `register` word promotion, `sdma_rlc_reg_offset` helper-node leakage, `REG_FIELD_SHIFT` field endpoints, `relative_root` scan scope, and PDF candidate starvation before the current green pass.
- Current visual QA `docs/qa/visual-qa-2026-05-17/visual-qa.md` records 2K route screenshots for six routes in dark and light themes: 6 passed, 0 failed. `/graph` shows 12 nodes and 4 weighted edges in both themes. This is now stale for `/graph` after the package-first renderer decision.
- 2026-05-17 user review found the Acceptance page pass/fail rows unclear because failures could not be expanded to see details. This is a G10/G14 blocker even if the backend artifact has the details.
- Latest automated verification after the package/shadcn/static-data pass: core unittest 90 OK with 1 sqlite-vec skip; API/MCP unittest 41 OK with 1 optional MCP runtime skip; Web API Playwright 21 passed; Web smoke Playwright 39 passed; visual route Playwright 14 passed; `pnpm --filter web run lint` passed; `pnpm --filter web run build` passed; `pnpm --filter web exec tsc --noEmit --incremental false --pretty false` passed; `git diff --check` passed.
- 2026-05-17 graph semantic QA passed for core function edges, doc section nodes, batch semantic-edge core/API/MCP/Web paths, package-backed graph API behavior, batch UI action, shadcn styled-control regression, browser `/graph` rendering with `react-force-graph-2d`, and light/dark visual route checks. Evidence is recorded in `docs/qa/2026-05-17-graph-function-section-batch-qa.md`.
- Existing visual QA documents that say `PASS` before `docs/qa/2026-05-17-graph-function-section-batch-qa.md` are historical evidence; the current fresh route-level visual pass is the 14-test Playwright route suite plus the 2K graph screenshot in that QA doc.
- The [MVP Acceptance Query Matrix](2026-05-16-mvp-acceptance-query-matrix.md) now tracks all nine acceptance queries individually.
- 2026-05-17 provider-check detail correction: `/api/workbench/acceptance` now preserves AQ detail `provider_checks` from `asip.acceptance` artifacts, and the Acceptance page expandable details show embedding and semantic-edge provider status/provider/model/message when present.
- 2026-05-17 Acceptance page runner correction: `/acceptance` now has its own shadcn/Radix runner panel for configurable `queryIds`, surfaces (`CLI`, `API`, `Web`, `MCP`), DB path, output JSON path, and output Markdown path. In-app Browser QA at `http://127.0.0.1:3102/acceptance` verified the rendered page posts `{"dbPath":"/tmp/asip-ui-acceptance.db","queryIds":["AQ01","AQ09"],"surfaces":["CLI","API","Web","MCP"],"outputJson":"docs/qa/ui-acceptance.json","outputMd":"docs/qa/ui-acceptance.md"}` and renders `Acceptance run passed: 2/2`.
- 2026-05-17 QA infrastructure correction: `apps/web/playwright.config.ts` now supports `PLAYWRIGHT_BASE_URL` and `PLAYWRIGHT_SKIP_WEB_SERVER=1`, so e2e tests can target a known-good dev server instead of hanging on a stale port. Ports `3100` and `3101` were observed accepting connections but returning zero bytes during this pass; browser QA used a fresh `3102` server.
- 2026-05-17 backend/API/MCP re-verification: core unittest discovery is now 129 OK with 1 sqlite-vec skip; FastAPI/MCP regression is 41 OK with 1 optional MCP runtime skip; `pnpm --filter web exec tsc --noEmit` passes after the Acceptance runner and Playwright config changes.
- 2026-05-17 final verification rerun, superseding the older permission-policy blocker:
  - Core: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v` ran 150 tests, OK, 1 sqlite-vec skip.
  - API/MCP: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest apps.api.tests.test_app apps.api.tests.test_runtime apps.mcp.tests.test_tools apps.mcp.tests.test_server -v` ran 41 tests, OK, 1 optional MCP runtime skip.
  - TypeScript: `pnpm --filter web exec tsc --noEmit` passed.
  - Lint: `pnpm --filter web run lint` passed.
  - Web API + smoke: `pnpm --filter web exec playwright test tests/workbench-api.spec.ts tests/workbench-smoke.spec.ts --reporter=list` passed 65 tests using 1 worker.
  - Visual anchors/routes: `pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts --reporter=list` passed 15 tests.
  - `git diff --check` passed.
- 2026-05-17 Playwright config correction: workers are fixed at 1 because the e2e suite uses real shared SQLite state and provider settings. A 2-worker run exposed a real race where concurrent settings tests overwrote the provider model during reload.
- 2026-05-17 current graph QA: after deterministic rebuild and gemma4 semantic/doc-node jobs, `global_graph(limit=1500)` has 1,123 nodes, 1,500 edges, node kinds `function=523`, `register=593`, `doc_box=6`, `doc_section=1`, and 15 visible semantic edges.

## Remaining Gap

The test suite now proves the user-review blockers for this pass: package-backed graph rendering, expandable acceptance details, shadcn/Radix styled-control regression, batch semantic-edge generation, function-operation graph edges, document section nodes, no static default graph/query rows, and real add-index-query UI flow. The remaining gate is G11/G17 reconciliation and final user/commit/push workflow, not another missing package-graph implementation.

`add corpus -> index raw inputs in a clean DB -> query live index -> inspect evidence -> render weighted graph -> verify visual anchors`.

Visual QA has been rerun after the graph package replacement, shadcn-native UI pass, final graph/query performance fixes, resolver edit flow, live global search, source-type filters, semantic generation controls, and graph layer provenance. The old note about not being able to relaunch headless Playwright is superseded by the 69-test Web API/smoke run and 15-test visual route run above.

Graph QA must not pass only because a canvas or SVG is nonblank. The data assertions must prove that the graph is built from the indexed corpus and includes the required graph layers: evidence-derived relations, function-to-register/field operations, document section nodes, and semantic edges generated by the configured LLM provider.

The final acceptance run must use a clean named SQLite database. The dirty local `data/asip.db` is used only for live browser/dev graph evidence because it contains local test corpora and provider settings from E2E runs.

The old clean provider AQ01-AQ09 pass is superseded by the source-gated failure artifact. The current clean AMD artifact now provides the healthy source-diverse DB evidence, current screenshots/visual-anchor review, and current automated suite evidence. Final QA still needs design/spec reconciliation and git hygiene review.

Final QA must follow [Final Clean Evidence Package Gate](2026-05-17-final-clean-evidence-package.md); this pass closes the package/shadcn/graph/acceptance-detail G10 slice, while G11 owns the final completion claim and git gate.

## Acceptance Criteria

- Each production code change has RED/GREEN evidence or a documented reason when the change is docs-only.
- Full Web, core, API, MCP, build, lint, and diff checks pass.
- All nine MVP acceptance queries from `docs/specs/2026-05-16-asip-mvp1-design.md` are run and recorded, with source diversity limitations called out instead of hidden.
- No-match query, provider failure, invalid corpus, and resolver validation failure states are tested.
- Acceptance page reads current artifacts or runs the acceptance runner.
- Acceptance page exposes expandable run/query details for partial/fail states instead of only compressed summary rows.
- `/graph` has package-backed rendering with nonblank visual evidence, visible weighted edges, and interaction smoke for pan/zoom/drag or the selected package's equivalent.
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
- Web API/UI test: AQ09 provider acceptance exposes independently configured edge and embedding provider provenance through `/api/workbench/acceptance/run` and the Settings page. Implemented for isolated DB/UI plumbing; the clean gemma provider rerun now proves local Ollama `gemma4:e4b`/`nomic-embed-text:latest` provider checks in the runner artifact, while credentialed OpenAI-compatible closure remains a G06/G13 boundary.
- Web UI test: provider status remains `unverified` after save/backend hydration and changes to `verified` only after mocked provider smoke or mocked AQ09 success. Implemented for UI state semantics; live provider QA remains open.
- Web UI test: Settings can run AQ09 against a user-supplied DB path through the real Web BFF/core runner and a local fake edge HTTP endpoint. Implemented for isolated DB product wiring; final clean AMD corpus and credentialed live provider QA remain open.
- Core/API/Web test: semantic-edge generation can read indexed evidence, call the configured edge provider, persist generated edges into SQLite, and refresh the `/graph` page. Implemented with an isolated DB and local fake Ollama-compatible HTTP endpoint.
- Core/API/Web test: batch semantic-edge generation reads indexed candidates beyond a selected query, calls the configured provider, persists edges with job provenance, and refreshes the global graph.
- Core/API/Web test: global graph includes function operation edges and document section nodes when fixture inputs contain C functions and Markdown/PDF sections.
- FastAPI/MCP tests: semantic-edge generation calls the same workbench job from `POST /semantic-edges` and `semantic_edges_generate()`. Implemented with isolated DBs and a local fake Ollama-compatible HTTP endpoint.
- Web/MCP agreement test: implemented for Web BFF query/evidence/entity and MCP search/detail/entity functions against the same SQLite DB.
- FastAPI live HTTP smoke: implemented with direct Uvicorn startup, root `pnpm dev:api`, and a read-only provider settings request against an explicit missing DB.
- MCP server tool matrix: implemented with a fake FastMCP runtime proving all implemented product tools are registered by `apps/mcp/server.py`.
- Web E2E test: acceptance failures expand and show query-level failure reasons, missing surfaces, source paths/types, row/graph counts, provider checks, and artifact path.
- Web E2E/browser test: package-backed graph renderer is visible, nonblank, weight-aware, and no longer tested by private hand-written SVG class names.
- Web E2E/browser test: graph detail/summary exposes node-kind counts or labels proving functions, registers/fields, document sections, and semantic edges are present in the default global graph.
- Visual screenshot capture at 2048 x 1280 after final functional changes.
- E2E test for the full loop: add corpus, index, query unique symbol, graph changes, inspector shows source/snippet/resolved chain.
- Design-review checklist mapping ASIP MVP-1 G1-G6 and all nine acceptance queries to evidence.

## Not Closed Until

The final QA document contains command output summaries, screenshot paths, anchor paths, pass/fail per route, all nine acceptance query outcomes, and known residual risks.
