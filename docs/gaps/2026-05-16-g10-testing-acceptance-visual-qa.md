# G10 Testing Acceptance And Visual QA

Status: Historical and scoped package-backed graph, acceptance-detail, and visual QA pass evidence is recorded; the current 2026-05-20 browser/provider/Web acceptance gates remain blocked. The active closure slice is URL `dbPath` no-mock e2e plus live provider proof or explicit residual acceptance, so this file must not be read as a full integrated-graph completion claim.

## Requirement

Completion requires TDD, automated tests, all nine MVP acceptance queries, acceptance QA, and post-functional-change visual QA against individual anchors.

Every page must support light and dark themes. Visual QA targets a 2K desktop baseline.

2026-05-19 update: graph QA must also follow
[`docs/specs/2026-05-19-asip-graph-integration-plan.md`](../specs/2026-05-19-asip-graph-integration-plan.md).
The next browser/e2e gate must be no-mock for the graph path: open `/graph`
against a real SQLite DB, wait for package graph `data-ready=true`, assert
nonzero nodes/edges, assert only `function`, `register`, and `doc` product
kinds are visible, switch function view, run at least one free query, and expand
acceptance details.

This gate must pass the DB path through explicit URL/API state, not by relying
on whatever `data/asip.db` currently contains. Historical screenshots and
acceptance artifacts remain evidence for their named DBs, but the current
closure target is a reproducible no-mock browser path with a declared DB path.

2026-05-19 acceptance-surface clarification: `surfaces_checked` labels are not
enough for the final gate. The acceptance runner must record `surface_results`
per query, including `surface`, `transport`, `status`, `db_path`, row count,
graph node/edge counts, schema status, and failure reason. CLI/core, FastAPI,
and MCP probes should execute their real transport paths against the same DB.
Web may be a real BFF HTTP probe when `ASIP_WEB_BASE_URL` is configured; if it
is not configured, the report must say Web is covered by the no-mock
Playwright/browser DB-path test instead of marking Web passed by label alone.

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
- Historical early verification in this ledger included core unittest 77, API/MCP unittest 39, Web API 18, Web smoke 34, and visual route 13. Those early counts are superseded by the current 2026-05-18 verification below. Targeted tests added since then cover embedding provider transport integration, vector-backed retrieval without lexical overlap, IP/ASIC filtering, independent embedding API path/header settings, G14 query/graph HTTP 500 truthfulness, G14 initial live query/static graph fallback truthfulness, G14 Web BFF query/graph read-route no-mutation, G14 MCP/FastAPI no-auto-index read behavior, G14 status/list no-migration behavior, G14 acceptance failure/corpus empty/resolver empty/graph relationship-panel truthfulness, G02 live evidence inspector linkage, G03 no-seed global weighted graph behavior, semantic-edge product job wiring, configured non-query doc/PDF/register ingestion, provider acceptance provenance, G04/G05/G06 API/MCP control-plane parity, G04 selected Corpus UI indexing, G04 invalid-source and zero-document false-success prevention, G04 real UI add-index-query flow, G05 resolver UI validation and disabled status, G07 evidence/entity detail parity, G07 Web/MCP query/evidence/entity/graph agreement, G07 semantic-edge API/MCP parity, G07 FastAPI live HTTP smoke, G07 root `pnpm dev:api` startup smoke, G07 MCP server tool-matrix registration, and G10 acceptance artifact generation/execution.
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
- Latest automated verification after the register ip-version merge, query performance pass, shared-register bridge, and doc-overlay provenance pass: core unittest 239 OK with 2 optional sqlite-vec skips; API/MCP unittest 47 OK with 1 optional MCP runtime skip under system Python 3.9; bundled-Python real MCP runtime suite 29 OK with 0 skips from the previous G07 runtime pass; visual route Playwright 15 passed; combined Web API+smoke+visual Playwright 90 passed from the previous Web gate; `pnpm --filter web run lint` passed; `pnpm --filter web exec tsc --noEmit` passed; `git diff --check` must be rerun after final doc edits.
- 2026-05-18 clean-final acceptance rerun: `/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db` records DB health `pass`, AQ01-AQ09 `9/9`, surfaces `CLI/API/Web/MCP`, provider embedding `ollama/nomic-embed-text:latest` with `embedding_count=32` and `fallback_count=0`, and provider semantic-edge smoke `ollama/gemma4:e4b`. Artifacts: `docs/qa/2026-05-18-acceptance-clean-amd-gemma4-final-current.json` and `.md`. The same QA pass also records real Stage 2 batch edges, doc boxes, and macro-node endpoint checks in `docs/qa/2026-05-18-clean-final-stage2-and-macro-qa.md`.
- Final automated rerun after the clean-final Stage 2, macro-node, G06/G07/G15 continuation fixes, register ip-version merge, query graph performance pass, shared-register bridge pass, and doc-overlay provenance fix: core unittest 239 OK with 2 optional sqlite-vec skips; API/MCP unittest 47 OK with 1 optional MCP runtime skip under system Python 3.9; bundled-Python real MCP runtime suite 29 OK with 0 skips from the previous G07 runtime pass; `pnpm --filter web run lint` passed; `pnpm --filter web exec tsc --noEmit` passed; visual route Playwright 15 passed.
- 2026-05-18 multi-subfolder corpus TDD pass: targeted core tests prove configured and registered corpus multi-subfolder indexing plus unsafe path rejection; Web API/UI Playwright tests prove structured `metadata.subfolders` persistence, multiline Corpus page submission, and 400 responses for unsafe `../` filters. TypeScript `pnpm --filter web exec tsc --noEmit` passed after the route validation change. Evidence is recorded in `docs/qa/2026-05-18-g01-g04-amdgpu-subfolder-corpus-qa.md`.
- 2026-05-18 docs-only function-normalization planning pass: subagent review and online research were folded into `docs/specs/2026-05-18-product-graph-normalization.md` and `docs/superpowers/plans/2026-05-18-product-graph-normalization.md`. This records the TDD path for resolver-configured function concept nodes, divergent access preservation, and inspector raw-implementation expansion. It does not count as implementation evidence until the planned RED/GREEN tests run.
- Default in-app browser QA after copying the clean-final DB to `data/asip.db` shows `/graph` with `Edge: Ollama / gemma4:e4b`, `3000` graph edges, layer provenance `deterministic: 2989 semantic: 11`, `1000 / 2883` visible nodes, node-kind summary `doc_box=6`, `doc_section=1`, `function=836`, `register=157`, and no page errors. Screenshot and snapshot are stored under `docs/qa/browser/graph-clean-final-default-3100-*`.
- 2026-05-18 latest browser QA after the full backfill/static-cleanup/function-query slice is recorded in `docs/qa/2026-05-18-g03-real-query-graph-function-fallback-qa.md`. In-app browser at 2048 x 1280 shows `/graph` with `graph edges: 3000`, `layers deterministic: 2989 semantic: 11`, and `visible nodes: 1000 / 2805`; querying `gfx_v11_0_hw_init` shows `matches: 0` but `graph edges: 36` and a relationship panel containing live function-call edges. Screenshots are `docs/qa/browser/graph-after-full-backfill-and-query-fallback-2k.png` and `docs/qa/browser/graph-function-query-fallback-2k.png`.
- 2026-05-17 graph semantic QA passed for core function edges, doc section nodes, batch semantic-edge core/API/MCP/Web paths, package-backed graph API behavior, batch UI action, shadcn styled-control regression, browser `/graph` rendering with `react-force-graph-2d`, and light/dark visual route checks. Evidence is recorded in `docs/qa/2026-05-17-graph-function-section-batch-qa.md`.
- 2026-05-18 final Web visual pack captures the current live app in the in-app browser at 2048 x 1280 for `/`, `/graph`, `/corpus`, `/resolver-profiles`, `/acceptance`, and `/settings`, in both dark and light themes. Evidence is recorded in `docs/qa/visual-qa-2026-05-18-final-web-pack/visual-qa.md`.
- Existing visual QA documents that say `PASS` before `docs/qa/2026-05-17-graph-function-section-batch-qa.md` are historical evidence; the current fresh route-level visual pass is the 14-test Playwright route suite plus the 2K graph screenshot in that QA doc.
- The [MVP Acceptance Query Matrix](2026-05-16-mvp-acceptance-query-matrix.md) now tracks all nine acceptance queries individually.
- 2026-05-17 provider-check detail correction: `/api/workbench/acceptance` now preserves AQ detail `provider_checks` from `asip.acceptance` artifacts, and the Acceptance page expandable details show embedding and semantic-edge provider status/provider/model/message when present.
- 2026-05-17 Acceptance page runner correction: `/acceptance` now has its own shadcn/Radix runner panel for configurable `queryIds`, surfaces (`CLI`, `API`, `Web`, `MCP`), DB path, output JSON path, and output Markdown path. In-app Browser QA at `http://127.0.0.1:3102/acceptance` verified the rendered page posts `{"dbPath":"/tmp/asip-ui-acceptance.db","queryIds":["AQ01","AQ09"],"surfaces":["CLI","API","Web","MCP"],"outputJson":"docs/qa/ui-acceptance.json","outputMd":"docs/qa/ui-acceptance.md"}` and renders `Acceptance run passed: 2/2`.
- 2026-05-19 acceptance surface-probe correction: the core runner now records
  per-query `surface_results` instead of only `surfaces_checked` labels.
  Targeted tests prove `CLI/core` and FastAPI `TestClient` `/query` execute
  against the requested DB path. MCP currently records registered tool-surface
  execution as `mcp.tool-direct.search_evidence` plus
  `server_registered=true`; it is intentionally not mislabeled as an MCP
  protocol-client smoke because the current Python runtime does not have the
  optional `mcp` package installed. Web requires `ASIP_WEB_BASE_URL` for a real
  BFF HTTP probe; otherwise the run records `not_configured` and the final Web
  proof must come from the no-mock browser/e2e gate. The Acceptance page
  default runner now includes CLI/API/MCP, leaves Web opt-in/configured, and
  displays surface transport/status details in expanded query rows.
- 2026-05-19 AQ09 surface alignment: AQ09 now requires `CLI/API/MCP` in the
  runner matrix because the Settings action intentionally exercises provider
  plumbing through those transports. Web is proved by the Settings/browser
  e2e and `/graph?dbPath=...` no-mock semantic-edge gate, not by a hidden
  runner surface label.
- 2026-05-20 explicit `dbPath` false-positive correction: all DB-backed
  Workbench API routes now reject explicitly blank `dbPath` values with `400`
  instead of silently falling back to default `data/asip.db`. This includes
  index, query, graph, acceptance-run, corpora, resolver profiles, jobs,
  evidence detail, entity detail, provider settings, and semantic-edge jobs.
  The Workbench UI preserves an explicit blank URL parameter through request
  helpers so `/graph?dbPath=%20` and `/acceptance?dbPath=%20` can fail
  truthfully rather than trimming the evidence path away. Static no-fallback
  smoke, Playwright config smoke, TypeScript, and eslint passed. Web API test
  definitions now cover blank `dbPath` HTTP `400` across DB-backed routes, and
  the no-mock graph e2e definition now asserts function-view and free-query
  graph data changes.
  Fresh browser execution is still blocked in this environment by local
  `listen EPERM`.
- 2026-05-20 browser-gate preflight: `apps/web/scripts/browser-gate-preflight.mjs`
  now checks local listen capability and the target Playwright port before
  browser claims. It exits nonzero by default when the environment is blocked,
  and the explicit `--allow-blocked` artifact
  `docs/qa/2026-05-20-browser-gate-preflight.json` records
  `gate_status: blocked` with `EPERM` for both `127.0.0.1` listen capability
  and target port `3100`. This is blocker evidence, not a browser pass.
- 2026-05-20 Playwright server-mode correction:
  `apps/web/playwright.config.ts` now starts a fresh server by default and
  requires explicit `PLAYWRIGHT_REUSE_EXISTING_SERVER=1` opt-in for reuse.
  `PLAYWRIGHT_BASE_URL`, `PLAYWRIGHT_SKIP_WEB_SERVER=1`, and
  `PLAYWRIGHT_WEB_SERVER_COMMAND` remain available for targeting or supplying
  a known-good external dev server. The final no-mock browser gate should use a
  fresh server unless the run log names the reused server and why it is safe.
- 2026-05-17 QA infrastructure correction: `apps/web/playwright.config.ts` now supports `PLAYWRIGHT_BASE_URL` and `PLAYWRIGHT_SKIP_WEB_SERVER=1`, so e2e tests can target a known-good dev server instead of hanging on a stale port. Ports `3100` and `3101` were observed accepting connections but returning zero bytes during this pass; browser QA used a fresh `3102` server.
- 2026-05-17 backend/API/MCP re-verification: core unittest discovery is now 129 OK with 1 sqlite-vec skip; FastAPI/MCP regression is 41 OK with 1 optional MCP runtime skip; `pnpm --filter web exec tsc --noEmit` passes after the Acceptance runner and Playwright config changes.
- 2026-05-17 final verification rerun, superseding the older permission-policy blocker:
  - Core: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v` ran 162 tests, OK, 1 sqlite-vec skip.
  - API/MCP: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest apps.api.tests.test_app apps.api.tests.test_runtime apps.mcp.tests.test_tools apps.mcp.tests.test_server -v` ran 41 tests, OK, 1 optional MCP runtime skip.
  - TypeScript: `pnpm --filter web exec tsc --noEmit` passed.
  - Lint: `pnpm --filter web run lint` passed.
  - Web API + smoke: `pnpm --filter web exec playwright test tests/workbench-api.spec.ts tests/workbench-smoke.spec.ts --reporter=list` passed 65 tests using 1 worker.
  - Visual anchors/routes: `pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts --reporter=list` passed 15 tests.
  - `git diff --check` passed.
- 2026-05-17 Playwright config correction: workers are fixed at 1 because the e2e suite uses real shared SQLite state and provider settings. A 2-worker run exposed a real race where concurrent settings tests overwrote the provider model during reload.
- 2026-05-17 current graph QA: after deterministic rebuild and gemma4 semantic/doc-node jobs, `global_graph(limit=1500)` has 1,123 nodes, 1,500 edges, node kinds `function=523`, `register=593`, `doc_box=6`, `doc_section=1`, and 15 visible semantic edges.

Historical/current evidence rows above may report raw document subtypes such as
`doc_box` and `doc_section`. The 2026-05-19 product-schema gate is stricter:
default Web/API/MCP graph output must expose those as `kind=doc` with
`attr.doc_kind`, while raw/debug summaries may keep subtype labels for audit.

## Remaining Gap

The test suite proves the earlier user-review blockers for package-backed graph rendering, expandable acceptance details, shadcn/Radix styled-control regression, batch semantic-edge generation, function-operation graph edges, document section nodes, no static default graph/query rows, and real add-index-query UI flow. The remaining gates now include fresh no-mock browser/e2e, live provider smoke or explicit residual acceptance, and G11/G17 reconciliation; this is not merely a final user/commit/push workflow.

The 2026-05-19 contract adds a new QA boundary before future completion claims:
schema and data assertions must be as important as canvas visibility. A
nonblank canvas does not prove the graph is correct. The e2e test must verify
real node kinds, real edge counts, real query-driven graph changes, and real
acceptance detail expansion.

2026-05-20 expanded-DB status: the current default `data/asip.db` acceptance
artifact is `docs/qa/2026-05-20-acceptance-data-asip-expanded.md`, not the older
`9/9` default-DB artifact. It records DB health pass, schema pass for AQ01-AQ09,
AQ05 source diversity restored, and AQ09 persisted semantic-edge provenance
reported as `partial/stale`: `14` `ollama/gemma4:e4b` `semantic_edges` rows
exist from succeeded job `4`, but latest index job `10` is newer. The overall
result remains `0 passed / 8 partial / 1 failed` with `gate_status: blocked`.
AQ09 embedding coverage is now explicitly partial
because the DB has `27` provider embeddings and `125962` deterministic fallback
embeddings plus `21852` chunks with no embedding rows. Live semantic-edge
provider smoke fails with `Operation not permitted`, and fresh browser/e2e is
blocked here by local `listen`/connect `EPERM`.

2026-05-20 Web-included acceptance blocker: the supplemental artifact
`docs/qa/2026-05-20-acceptance-data-asip-expanded-web-blocked.md` explicitly
requests CLI/API/Web/MCP for all AQ01-AQ09 queries. CLI/API/MCP probes return
rows and product schema `pass`, but every Web probe is `not_configured` because
`ASIP_WEB_BASE_URL` is absent and the local browser/server gate is blocked. The
summary is therefore `0 passed / 0 partial / 9 failed`, which is stronger
blocking evidence than merely omitting Web from the current expanded acceptance
run.

This new boundary is still active work: package rendering, previous acceptance
detail display, and visual screenshots are recorded, but the integrated
three-kind schema plus URL `dbPath` no-mock browser gate is not yet a final
completion claim.

2026-05-20 subagent follow-up: Web e2e review found that the no-mock
`/graph?dbPath=...` test proved API payload changes more strongly than rendered
graph changes. The test definition now also checks `force-graph`
`data-node-total` / `data-edge-total` and accessibility summary text after
global graph load, function implementation view, and free-query transitions.
This still remains a listed/compiled definition until browser execution is
unblocked.

2026-05-19 continuation update: the three-kind schema gate has core coverage
now. `asip.graph_schema` is shared by acceptance, storage projection, semantic
edge prompts, and workbench semantic-edge persistence. Targeted RED/GREEN tests
proved the prompt no longer asks for `checks_mask`/`assigns_doorbell`/`waits_for`,
storage calls the shared relation normalizer, and `entity_type=macro` evidence
does not become a visible register node. The broader core graph/workbench sweep
ran 155 tests OK with 2 optional sqlite-vec skips, acceptance/API/MCP ran 14
tests OK, TypeScript passed, and `git diff --check` passed.

Browser evidence also improved but remains scoped: a stale 3100 server returned
zero bytes and had a hot `next-server` process, so QA relaunched a clean server
on 3111 and opened `/graph` in the in-app browser at 2048 x 1280. The page
loaded a real default-DB graph with `graph edges: 3000`, layers
`deterministic: 2989 semantic: 11`, and visible summary `doc 7`,
`function 696`, `register 297`. Screenshots are
`docs/qa/browser/asip-graph-schema-v2-2026-05-19-2k.png` and
`docs/qa/browser/asip-graph-schema-v2-loaded-2026-05-19-2k.png`; snapshot notes
are in
`docs/qa/browser/asip-graph-schema-v2-loaded-2026-05-19-snapshot.md`.
This does not replace the final no-mock `/graph?dbPath=...` Playwright gate.

The Product Graph V2 implementation plan also adds a stricter UI/e2e boundary:
visual anchor tests may use mocked layout data, but they must be named and
reported as visual/layout tests. Final graph acceptance must cite a real
SQLite-backed `/graph?dbPath=...` or equivalent no-mock scenario, and must fail
if the page silently falls back to default `data/asip.db`, static rows, or a
mocked graph payload.

`add corpus -> index raw inputs in a clean DB -> query live index -> inspect evidence -> render weighted graph -> verify visual anchors`.

Visual QA was rerun for the earlier graph package replacement, shadcn-native UI pass, graph/query performance fixes, resolver edit flow, live global search, source-type filters, semantic generation controls, and graph layer provenance. That scoped pass does not cover the latest 2026-05-20 explicit `dbPath`, browser-gate, provider-gate, or Web-included acceptance blockers; those still require fresh browser/e2e when local listening is available.

Graph QA must not pass only because a canvas or SVG is nonblank. The data assertions must prove that the graph is built from the indexed corpus and includes the required graph layers: evidence-derived relations, function-to-register/field operations, document section nodes, and semantic edges generated by the configured LLM provider.

The final acceptance run must use a clean named SQLite database. The default `data/asip.db` was reset to the clean-final DB for the G01/G10 gate and later intentionally rebuilt for G03 typed-callback graph QA; the previous dirty local dev DB was backed up to `/tmp/asip-dirty-dev-before-final-default-2026-05-18.db`. Future local browser/API runs may dirty or rebuild the default DB again, so the named clean-final artifact `/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db` remains the stable final QA reference.

The old clean provider AQ01-AQ09 pass is superseded for current closure by source-gated and expanded-DB artifacts. The clean AMD artifacts still provide scoped source-diverse DB, screenshot/visual-anchor, and automated-suite evidence, but G10 remains open for the current 2026-05-20 browser/provider/Web acceptance blockers unless those blockers are resolved or explicitly accepted as residuals.

Final QA must follow [Final Clean Evidence Package Gate](2026-05-17-final-clean-evidence-package.md). The earlier pass closes the package/shadcn/graph/acceptance-detail slice, but it does not close current G10; G11 owns the final completion claim, residual acceptance, and git gate.

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
- Core/CLI acceptance runner tests for AQ01-AQ09 artifact shape and pass/fail truthfulness. Implemented for fixture DB and the 2026-05-18 clean-final AMD artifact.
- Core/CLI acceptance runner test: per-query `surface_results` records real
  CLI/API/MCP probes with transport name, DB path, graph counts, schema status,
  and failure reason; Web is real HTTP when `ASIP_WEB_BASE_URL` is configured
  or explicitly delegated to the no-mock Playwright/browser gate.
- Core/CLI acceptance runner tests now fail when required source types are missing and when corpus/job health is not clean.
- API/MCP/Web test: acceptance listing includes the new `acceptance-clean-qwen35` artifact and displays partial counts. Implemented for listing/UI visibility.
- API/MCP/Web test: selected acceptance execution returns a full `asip.acceptance` payload for `AQ01`. Implemented for plumbing; clean-final AQ01-AQ09 pass/fail evidence is recorded in `docs/qa/2026-05-18-acceptance-clean-amd-gemma4-final-current.md/json`.
- Core test: provider acceptance fails without provider settings and passes only when embedding provenance and semantic-edge smoke both pass.
- Core test: provider acceptance can switch to OpenAI-compatible embedding/edge settings without code changes.
- Web API/UI test: AQ09 provider acceptance exposes independently configured edge and embedding provider provenance through `/api/workbench/acceptance/run` and the Settings page. Implemented for isolated DB/UI plumbing; the clean gemma provider rerun now proves local Ollama `gemma4:e4b`/`nomic-embed-text:latest` provider checks in the runner artifact, while credentialed OpenAI-compatible closure remains a G06/G13 boundary.
- Web UI test: provider status remains `unverified` after save/backend hydration and changes to `verified` only after mocked provider smoke or mocked AQ09 success. Implemented for UI state semantics; live provider QA remains open.
- Web UI test: Settings can run AQ09 against a user-supplied DB path through the real Web BFF/core runner and a local fake edge HTTP endpoint. Implemented for isolated DB product wiring; clean-final local Ollama provider QA is recorded, while credentialed live OpenAI-compatible provider QA remains open.
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
- Core/Web TDD slice: resolver-configured function normalization must prove concept function nodes with raw implementations, divergent access preservation, and implementation-view/inspector expansion before it can be marked implemented.
- Core/Web TDD slice: product graph schema validator must prove default output
  contains only `function`, `register`, and `doc`; legacy doc subtypes must be
  projected into `doc.attr.doc_kind`.
- Web no-mock e2e: `/graph` opens against a real SQLite DB, graph package marks
  `data-ready=true`, node/edge totals are nonzero, product node-kind assertions
  pass, function-view switch changes data, and a free query changes the graph.
- Web no-mock e2e: `/graph?dbPath=...` or the equivalent routed API state uses
  the requested real SQLite DB for graph, query, and acceptance checks; the test
  must fail if the page silently falls back to a mock DB or stale default DB.
- Web no-mock e2e: graph controls for loaded edge budget, visible node/edge
  budgets, minimum edge weight, relation/stage/source filters, and function
  view change request parameters; tests must fail if these controls only alter
  component-local hardcoded constants.
- Web no-mock e2e: graph details expose deterministic and semantic layer
  counts plus provider/model/job provenance for semantic edges when present.
- Performance-aware e2e: route-level timing records graph API total time,
  payload size, and canvas readiness for the selected DB.
- Visual screenshot capture at 2048 x 1280 after final functional changes.
- E2E test for the full loop: add corpus, index, query unique symbol, graph changes, inspector shows source/snippet/resolved chain.
- Design-review checklist mapping ASIP MVP-1 G1-G6 and all nine acceptance queries to evidence.

## Not Closed Until

The final QA document contains command output summaries, screenshot paths, anchor paths, pass/fail per route, all nine acceptance query outcomes, and known residual risks.
