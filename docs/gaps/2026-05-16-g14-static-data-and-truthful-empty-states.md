# G14 Static Data And Truthful Empty States

Status: Partial/blocking; static data removal, package graph renderer, and acceptance detail truthfulness remain open

## Requirement

The Web product must not present static seed data, historical QA artifacts, localStorage rows, or design-anchor content as if they were live ASIP results.

Static content may remain only as:

- explicit empty-state guidance,
- deterministic test fixtures under test control,
- design-preview or visual-anchor reference material,
- clearly labeled demo/seed data that is never merged into live query/index/provider responses.

Implementation truthfulness also applies to UI widgets: a custom visualization or custom table must not make static/test-only structure look like a live product feature. Standard graph/table/detail behavior should use a maintained package or shadcn primitive where available, with ASIP-specific data clearly wired from live API payloads.

This gap exists because the user explicitly challenged earlier completion claims after seeing hardcoded-looking graph/query behavior. Closing the MVP requires proving the UI is truthful when live data is missing, failing, or empty.

Truthfulness for `/graph` now includes graph-source truthfulness. The UI must not present a tiny persisted-edge sample as the full global graph. It must expose whether the graph includes evidence-derived edges, function operation edges, document section nodes, and batch semantic edges, or show a clear incomplete/empty state while those jobs have not run.

## Current Evidence

- `apps/web/lib/page-data.ts` still contains route metrics, rows, relationship lines, corpus counts, resolver-profile-like rows, and acceptance-style data used by the page shell.
- `apps/web/components/workbench-page.tsx` still defines `defaultCorpora`, `defaultResolverProfiles`, and `evidenceIndex`.
- `apps/web/components/workbench-page.tsx` still has fallback merge helpers for corpora, resolver profiles, evidence rows, metrics, and selected evidence detail.
- API-backed query and graph paths now exist, and no-match UI tests cover one important failure mode, but broader network/API failure paths still need review.
- `apps/web/app/api/workbench/query/route.ts` and `apps/web/app/api/workbench/graph/route.ts` now accept an explicit `dbPath` and do not call `ensureWorkbenchIndex()` in read-style routes.
- 2026-05-17 G14 RED/GREEN slice:
  - Added Playwright tests for query API HTTP 500 and graph API HTTP 500.
  - Query failure now renders an explicit error state, clears live rows, and does not merge `evidenceIndex` seed rows into the result table or query graph.
  - Graph API failure now stores an authoritative empty graph payload and renders a visible graph status instead of falling back to static seed nodes.
  - `GlobalNetworkGraph` now renders a dedicated empty/error panel when graph data is empty.
  - Verification: `pnpm test:ui tests/workbench-smoke.spec.ts -g "evidence query API failure|graph API failure"` passed 2 tests.
  - Verification: `pnpm test:ui tests/workbench-smoke.spec.ts --reporter=list` passed 18 tests.
  - Verification: `pnpm --filter web exec tsc --noEmit` passed.
  - Verification: `pnpm test:ui tests/visual-anchor-routes.spec.ts --reporter=list` passed 12 tests.
- 2026-05-17 G14 initial-query/static-graph slice:
  - Added Playwright coverage proving the first Evidence Workbench screen issues a live default query before showing success rows.
  - The initial Evidence Workbench state now clears rows/graph to loading/empty state instead of rendering `evidenceIndex` as a success table.
  - Added query request sequencing so a slower initial default query cannot overwrite a later user query or no-match empty state.
  - Added Playwright coverage proving row-derived graph fallback uses only live API rows when the API omits `graph`, instead of merging `evidenceIndex`.
  - Verification: `pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts --reporter=list` passed 20 tests.
  - Verification: `pnpm --filter web exec tsc --noEmit` passed.
- 2026-05-17 G04/G14 corpus truthfulness slice:
  - Core registered corpus indexing now fails missing `source_root` instead of reporting `indexed` with zero documents.
  - Core registered corpus indexing now fails unknown selected corpus ids instead of reporting `indexed` with zero documents.
  - Core configured raw-corpus indexing now fails missing configured scan roots instead of reporting `indexed` with zero documents.
  - The selected Corpus UI row is marked `failed` when `/api/workbench/index` returns a failed response.
  - A real Web UI add-index-query test now proves a temporary local corpus can enter the live SQLite query path through the Corpus page.
  - Verification: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages/core/tests/test_workbench_corpus_state.py packages/core/tests/test_workbench_live.py -v` passed 9 tests.
  - Verification: `pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts --reporter=list` passed 23 tests.
- 2026-05-17 G05 resolver truthfulness slice:
  - Resolver Profiles validation now calls the live backend validation path from the UI instead of only adding/displaying profile rows.
  - Disabled profiles now render a visible `disabled` status in the results table.
  - Verification: `pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts --reporter=list` passed 25 tests.
  - Verification: `pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts --reporter=list` passed 13 tests.
- 2026-05-17 G02/G03 live inspector slice:
  - Right inspector chain, source preview, and relationship panel now derive from selected live evidence rows when the Evidence Workbench query succeeds.
  - Selecting a different live result row updates inspector content instead of leaving the static detail panel in place.
  - Verification: `pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts --reporter=list` passed 27 tests.
  - Verification: `pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts --reporter=list` passed 13 tests.
- 2026-05-17 G14 acceptance/corpus/graph truthfulness slice:
  - Acceptance API failure now renders an explicit empty state and `runs: 0` metrics instead of falling back to static `qwen3.5` QA rows from `page-data.ts`.
  - Corpus API success with `corpora: []` now renders an empty state and `corpora: 0` metrics instead of substituting default `mxgpu`, `linux-amdgpu`, or `amd-pdf-mi300` rows.
  - Resolver API success with `profiles: []` now renders an empty state and `profiles: 0` metrics instead of substituting default `WREG32_SOC15`, `adapt->reg_offset`, or `toy-python` rows.
  - Graph Explorer relationship panel now derives from the successful API graph payload when a global graph is returned, instead of keeping static relationship lines from the visual shell.
  - Provider smoke now marks the settings form dirty before the smoke call so late backend hydration cannot overwrite a successful provider check with `unverified`.
  - Verification: `pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts -g "acceptance API failure" --reporter=list` passed.
  - Verification: `pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts -g "relationship panel is API-backed" --reporter=list` passed.
  - Verification: `pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts -g "empty API corpora" --reporter=list` passed.
  - Verification: `pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts -g "empty API profiles" --reporter=list` passed.
  - Verification: `pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts --reporter=list` passed 34 tests.
- 2026-05-17 G14/G07 read-route no-mutation slice:
  - Added Web API tests proving `/api/workbench/query` and `/api/workbench/graph` can read an explicit empty SQLite DB without falling back to default indexed data.
  - Removed implicit `ensureWorkbenchIndex()` calls from Web BFF query and graph GET routes.
  - Query GET now returns the core empty result for an explicit empty DB instead of seeding default evidence.
  - Graph GET now returns the core isolated seed graph for an explicit empty DB instead of seeding default weighted edges.
  - `/api/workbench/index` now returns the actual indexed `dbPath` for custom index jobs, and the raw-index API test uses a small isolated fixture instead of a slow dirty default DB.
  - Verification: `pnpm --filter web exec playwright test tests/workbench-api.spec.ts --reporter=list` passed 17 tests.
  - Verification: `pnpm --filter web exec tsc --noEmit` passed.
  - Verification: `git diff --check` passed.
- 2026-05-17 G14/G07 MCP/API read-route no-mutation slice:
  - Removed MCP `_ensure_index()` usage from read-style tools and deleted the dead helper.
  - `search_evidence`, `graph_expand`, `run_acceptance`, `evidence_detail`, and `entity_explain` now respect explicit missing/empty DBs without creating the DB or indexing default corpora.
  - Core `query_evidence`, `expand_query_graph`, `global_graph`, and `load_provider_settings` now check for required tables through a read-only SQLite connection before reading, instead of migrating missing/empty DBs.
  - FastAPI `/graph` now accepts `db_path` and honors it like `/query`, `/evidence`, and `/entities`.
  - Verification before the later status/list read-migration tests used the same API/MCP command and covered the read-route subset; the status/list slice result is recorded below as 36 tests with 1 optional MCP runtime skip.
  - Verification: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_workbench_query_schema packages.core.tests.test_acceptance_runner packages.core.tests.test_workbench_live packages.core.tests.test_storage_graph -v` passed 27 tests with 1 native sqlite-vec skip.
- 2026-05-17 G14/G07 status/list read-migration slice:
  - `provider_settings_show`, `resolver_profiles_list`, `resolver_profile_validate`, and `corpora_list` now handle explicit missing or empty DBs without creating DB files or migrating status/list schemas.
  - Core `list_indexed_corpora`, `list_resolver_profiles`, and `validate_resolver_profile` now use read-only table checks before opening write-capable store operations.
  - Verification: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest apps/api/tests/test_app.py apps/mcp/tests/test_tools.py apps/mcp/tests/test_server.py -v` passed 36 tests with 1 optional MCP runtime skip.
  - Verification: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_workbench_query_schema packages.core.tests.test_acceptance_runner packages.core.tests.test_workbench_live packages.core.tests.test_storage_graph packages.core.tests.test_workbench_backend_state packages.core.tests.test_workbench_corpus_state -v` passed 35 tests with 1 native sqlite-vec skip.
- 2026-05-17 G07 runtime/surface slice:
  - Root `pnpm dev:api` now starts the FastAPI Uvicorn server with the project Python path and a configurable `PORT`.
  - FastAPI live HTTP smoke covers both direct Uvicorn startup and the root `pnpm dev:api` script.
  - MCP server registration now exposes all implemented product tools through the FastMCP entrypoint under a fake runtime.
  - Verification: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest apps/api/tests/test_app.py apps/api/tests/test_runtime.py apps/mcp/tests/test_tools.py apps/mcp/tests/test_server.py -v` passed 39 tests with 1 optional MCP runtime skip.
- 2026-05-17 user review reopened frontend truthfulness for graph and acceptance:
  - The current `/graph` renderer is live-data backed but visually behaves like a small hand-written SVG preview, not a real global graph product surface.
  - The Acceptance page compresses fail/partial runs into rows without expandable query-level detail, even though `asip.acceptance` artifacts contain `failure_reasons`, `missing_surfaces`, `source_paths`, `source_types`, provider checks, row counts, and graph counts.
- Product truth now requires deleting hidden/static UI fallbacks, replacing the graph renderer with a package-backed React graph, and showing acceptance details through a real expandable UI.
- 2026-05-17 graph semantic slice proves the default `/graph` can render live API payloads with 400 edges from the dirty local DB and exposes the batch semantic-edge action. Final route-by-route static/demo audit is still open.

## Remaining Gap

The UI has become partially live, and query/graph/backend empty/failure paths plus selected Corpus failure, acceptance failure, empty corpus API, empty resolver API, graph relationship-panel paths, Web BFF query/graph read-route no-mutation, MCP/FastAPI default-corpus no-auto-index behavior, status/list no-migration behavior, FastAPI live HTTP smoke including `pnpm dev:api`, MCP server tool-matrix registration, and Web/MCP query/evidence/entity agreement are now explicitly covered. Initial Evidence Workbench success rows now come from the live query API, row-derived graph fallback no longer mixes `evidenceIndex` into API results, live query rows now drive the right inspector, user-added corpora can reach live query results through the Web UI, resolver validation now uses live backend state, and acceptance/corpus/resolver/graph routes no longer silently fall back to their most misleading static rows in the covered states.

This gap remains open because static/default data and custom UI can still hide the truth:

- `/graph` must not use hand-written fixed-layout SVG as the primary product renderer.
- `/acceptance` must expose the real artifact/run detail behind fail/partial counts.
- route-level fallback rows, static metrics, and demo labels must be audited again after the shadcn/package pass.
- provider failure nuance, optional real MCP runtime smoke, and remaining route-specific demo states still need route-by-route truth audit before this gap can close.
- graph provenance must be visible enough to distinguish raw explicit edges, indexed-evidence edges, function-operation edges, document-section edges, and LLM semantic edges. Missing graph layers must not be hidden behind a generic `ready` label.

The product needs a clear data truth policy:

- live API data,
- explicit empty/error/unverified states,
- fixture/demo data only when intentionally selected and visibly labeled.

No route should silently merge fallback rows into live query results, corpus state, resolver state, graph state, provider status, or acceptance results.

Final route-by-route truthfulness audit must classify every route and state as
one of:

- live data,
- explicit empty state,
- explicit error/unverified state,
- visibly labeled demo or fixture state.

The audit must cover `/`, `/graph`, `/corpus`, `/resolver-profiles`,
`/acceptance`, `/settings`, and the matching Web BFF/API/MCP surfaces. Query,
graph, status, provider, corpus, resolver, and acceptance read-style endpoints
must not implicitly mutate/index state unless that behavior is visibly labeled
and explicitly accepted in G07/G17.

## Acceptance Criteria

- Free query results come only from the live query API for normal product use.
- Initial Evidence Workbench results come from the live default query API, not from static `evidenceIndex`.
- Query graph fallback never merges static evidence rows into live API rows when the API omits graph data.
- A backend error shows an explicit error state and does not replace rows with seed evidence.
- A no-match query shows an explicit empty state and does not merge `evidenceIndex`.
- Corpus and resolver pages distinguish backend-persisted rows from local draft/demo rows.
- Acceptance page distinguishes current-run artifacts from bundled historical QA artifacts.
- Acceptance page expands fail/partial rows into live artifact/run details instead of making the user infer meaning from compressed counts.
- Global graph route renders live API graph data or an explicit empty/error state, never a hidden static relation graph.
- Global graph route uses a package-backed renderer for the live graph, not a static-looking hand SVG preview.
- Global graph route labels or summarizes graph provenance so users can tell whether function, document-section, and semantic-edge layers are present.
- Semantic-edge buttons/statuses distinguish no job run, running, succeeded with edge count, failed with provider evidence, and skipped due missing settings/candidates.
- Read-style query/graph/status endpoints do not mutate index state unless the endpoint and UI explicitly say they are initializing/indexing.
- Playwright tests cover backend empty, backend failure, no-match, and normal live-data states.

## Required Tests

- UI E2E test: query API returns `rows: []`; page renders empty state with zero evidence rows.
- UI E2E test: initial Evidence Workbench render calls the live query API and does not show static success rows.
- UI E2E test: stale query responses cannot overwrite a newer user query.
- UI E2E test: query API returns rows without graph; row-derived graph does not merge static seed nodes.
- UI E2E test: query API returns HTTP 500; page renders an error state with no seed rows.
- UI E2E test: graph API returns empty graph; `/graph` renders an empty graph state instead of hardcoded nodes.
- UI E2E test: graph API returns HTTP 500; `/graph` renders an error state instead of hardcoded nodes.
- UI E2E test: acceptance API returns HTTP 500; `/acceptance` renders an empty state instead of static historical QA rows.
- UI E2E test: acceptance fail/partial run expands and shows failure reasons, missing surfaces, source paths/types, graph counts, and artifact path.
- UI E2E test: corpus API returns `corpora: []`; `/corpus` renders an empty state instead of default corpus rows.
- UI E2E test: resolver API returns `profiles: []`; `/resolver-profiles` renders an empty state instead of default resolver rows.
- UI E2E test: graph API success updates the relationship panel from the API graph payload.
- UI/browser test: graph package renderer receives the API payload and paints a nonblank weighted graph; tests must avoid private hand-written SVG selectors.
- UI/API test: graph payload/provenance proves the default global graph is not a hardcoded/static sample and reports missing graph layers truthfully.
- UI/API test: batch semantic-edge status and failure states do not show stale generated edges as if they came from the current provider/model.
- API/architecture test or review checklist: `query` and `graph` read endpoints do not implicitly index/mutate state, or the implicit initialization is explicitly documented and accepted.
- Design QA check: all visual anchors are treated as reference artifacts, not runtime data sources.

## Not Closed Until

The final QA doc proves that static data cannot mask failed live query, graph, corpus, resolver, provider, or acceptance paths.
