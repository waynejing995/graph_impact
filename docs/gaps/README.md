# ASIP Gap Documents Before More Code

Date: 2026-05-16
Status: Current user-review blocker pass verified; final G11/git gate remains

## Purpose

This folder is the source of truth for the ASIP workbench gap inventory before any more feature code is written.

The current repository contains useful partial work, but it is not yet a finished ASIP MVP-1 product. These documents separate what exists from what must still be implemented and verified.

Do not write more product code until this gap ledger is stable. Do not mark the active goal complete, commit, or push until every blocking gap below is closed or explicitly accepted as out of scope by the user.

Current final-candidate evidence is recorded in
`docs/qa/2026-05-17-final-clean-evidence-package.md`. Historical `PASS`,
provider smoke, fixture acceptance, or older visual-anchor artifacts remain
non-closing evidence unless they are linked from that package. The active goal
is still not complete until the final git gate, commit, push, and any residual
boundary acceptance are done.

2026-05-17 update: the previous final-candidate UI evidence is not sufficient.
The user rejected the hand-written graph renderer and custom-looking UI
surfaces. Completion now additionally requires:

- package-backed React graph rendering for `/graph`,
- shadcn/native package primitives for standard UI surfaces where available,
- expandable acceptance failure/partial details,
- fresh 2K light/dark visual QA after those UI changes.

2026-05-17 current pass: those user-review blockers now have implementation
and verification evidence in
`docs/qa/2026-05-17-graph-function-section-batch-qa.md`: package-backed
`react-force-graph-2d`, shadcn/Radix standard controls, expandable
acceptance details, no static default query/graph rows, function-operation graph
edges, document section graph nodes, batch semantic-edge jobs, real add-index-query
UI loop, and fresh light/dark route QA. G11 remains the final gate for artifact
hygiene, commit, push, and explicit deferrals.

Supporting acceptance matrix:

- [Gap Document Register Before Code](2026-05-17-gap-document-register.md): complete G01-G17/AQ register, current truth, user-visible complaint mapping, and implementation order before more code.
- [MVP Acceptance Query Matrix](2026-05-16-mvp-acceptance-query-matrix.md): nine query-level closure rules for G10.
- [Gap Inventory Before Code](2026-05-17-gap-inventory-before-code.md): one-page inventory of every gap document, current state, and the next evidence required before implementation resumes.
- [Final Clean Evidence Package Gate](2026-05-17-final-clean-evidence-package.md): required final QA package that prevents fixture, historical, provider-only, or visual-only artifacts from being mistaken for completion.
- [Final Clean Evidence Package](../qa/2026-05-17-final-clean-evidence-package.md): current final-candidate package with clean AMD DB counts, AQ01-AQ09 9/9, six free queries, semantic-edge jobs, visual QA, automated verification, and architecture review.

## Gap Document Index

| ID | Gap document | Status | Why it blocks |
| --- | --- | --- | --- |
| G01 | [Real Ingestion And Indexing](2026-05-16-g01-real-ingestion-indexing.md) | Partial; blocking | Raw-corpus SQLite indexing covers more MVP queries and configs include doc/PDF globs, but one clean AMD corpus run across code/docs/register/PDF still needs final verification. |
| G02 | [Live Retrieval And Evidence Schema](2026-05-16-g02-live-retrieval-evidence-schema.md) | Partial; blocking | SQLite evidence schema, FTS, vector fallback retrieval, no-match/failure states, live inspector linkage, and clean AQ runner mechanics exist; rerank, cross-source evidence, and final visual/design closure remain open. |
| G03 | [Dynamic Weighted Graph](2026-05-16-g03-dynamic-weighted-graph.md) | Partial; blocking | `/graph` uses `react-force-graph-2d` over live no-seed graph data, with function-operation edges, cross-file common-helper/direct/callback call edges, callback alias/type hints, IP-block registration aliases, selective Clang AST JSON receiver hints, section nodes, doc boxes, and batch semantic edges. Current clean-final DB `/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db` has `41,880` deterministic rebuild edges, `25` real `gemma4:e4b` semantic edges, zero raw macro/wrapper endpoints for `IP_VERSION/WREG32/RREG32/REG_SET_FIELD/SOC15_REG_OFFSET/funcs/ops/hw_init`, and a 20k graph sample with `15,154` nodes plus `function/register/doc_box/doc_section` only. This is still not full clangd/libclang cross-TU vtable/type-flow; a full typed extractor remains a named residual before full closure. |
| G04 | [Corpus Management](2026-05-16-g04-corpus-management.md) | Partial; blocking | Backend/API/MCP corpus add/list/index, UI selected-corpus indexing, invalid-source failure, durable job lifecycle visibility, and a real Web add-index-query loop exist; clean-DB closure and graph/inspector proof for the newly indexed corpus remain open. |
| G05 | [Resolver Profiles](2026-05-16-g05-resolver-profiles.md) | Current pass verified; final gate | YAML-backed profiles, backend/API/MCP add/list/validate, UI validation, disabled/edit state, per-index selection, and selected-profile changed graph output are proven. Richer unmatched-span diagnostics and broader non-C strategies remain open boundaries. |
| G06 | [Provider Settings And Ollama Detection](2026-05-16-g06-provider-settings-ollama.md) | Current local/batch pass verified; explicit deferrals | Settings persist/hydrate, embedding provider calls, safe env-based extra-header expansion, isolated AQ09 Web API provenance, Settings AQ09 UI/BFF wiring, query-scoped and batch semantic-edge jobs, and local Ollama `gemma4:e4b`/`qwen3.5`/`nomic` QA are tested; credentialed OpenAI-compatible live endpoint QA and query reranking remain open boundaries. |
| G07 | [API And MCP Product Surfaces](2026-05-16-g07-api-mcp.md) | Partial; blocking | Query/graph, selected acceptance execution, corpus/resolver/provider control-plane slices, evidence/entity detail slices, semantic-edge FastAPI/MCP parity, key read-route no-mutation coverage, FastAPI live HTTP smoke including `pnpm dev:api`, MCP server tool-matrix registration, and Web/MCP query/evidence/entity agreement exist; richer resolved-chain UX and optional real MCP runtime smoke remain open. |
| G08 | [PDF And Document Ingestion](2026-05-16-g08-pdf-document-ingestion.md) | Partial; narrowed residual | PDF conversion/page evidence and Markdown/doc section graph nodes are proven; a separate browser proof for a real PDF-derived `pdf_section` node remains narrower residual evidence. |
| G09 | [SQLite FTS5 Vector And NetworkX Runtime](2026-05-16-g09-storage-vector-graph-runtime.md) | Partial; provider-quality boundary open | FTS5, provider embeddings, NetworkX graph, native sqlite-vec extension smoke, native `search_vector()` adapter path, and JSON/Python-cosine fallback are tested; full provider-vector coverage and semantic rerank quality remain boundaries. |
| G10 | [Testing Acceptance And Visual QA](2026-05-16-g10-testing-acceptance-visual-qa.md) | Current clean-final acceptance and final suite verified | Clean-final AQ01-AQ09 acceptance over `/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db` is DB health pass and `9/9`, with CLI/API/Web/MCP surface labels and `gemma4:e4b`/`nomic-embed-text:latest` provider checks. Final automated rerun after the latest code/doc slice: core unittest 202 OK with 2 optional sqlite-vec skips, API/MCP unittest 45 OK with 1 optional MCP runtime skip, TypeScript check passed, lint passed, Web API+smoke Playwright 73 passed, visual route Playwright 15 passed, and `git diff --check` passed. |
| G11 | [Completion Gate And Documentation Review](2026-05-16-g11-completion-gate.md) | Final gate open | Current blocker pass is verified; completion still requires generated artifact cleanup, final diff review, commit, push, and explicit residual deferral acceptance. |
| G12 | [ASIC And IP Metadata Filtering](2026-05-16-g12-asic-ip-metadata-filtering.md) | Partial; blocking | Core/API/UI filters now affect query behavior; final acceptance and visual QA still need closure. |
| G13 | [MVP Boundary And Full-Spec Deferrals](2026-05-16-g13-mvp-boundary-deferrals.md) | Blocking | Long-range full-spec items must be explicitly deferred so they do not masquerade as silent failures. |
| G14 | [Static Data And Truthful Empty States](2026-05-16-g14-static-data-and-truthful-empty-states.md) | Current pass verified; audit residual | Static default query/graph rows are removed from product paths, unused static artifact query/graph helpers were deleted, and empty/error states have E2E/API coverage; broader route audit remains tracked for final review. |
| G15 | [Performance Smoke And Deterministic Rebuild](2026-05-16-g15-performance-smoke-deterministic-rebuild.md) | Partial; blocking | Fixture-side smoke is automated and documented, and the dirty local AMD DB now has query-graph performance QA over six real queries plus AQ01 Web acceptance under the 30s e2e timeout. Real AMD repeat timing and full provider embedding/backfill timing remain open before final closure. |
| G16 | [Workbench IA Theme And Visual Fidelity](2026-05-16-g16-workbench-ia-theme-visual-fidelity.md) | Current pass verified; final review | shadcn/Radix standard control pass, package graph renderer, light/dark persistence, and route visual tests are verified. |
| G17 | [Architecture Ownership And Process Shape](2026-05-16-g17-architecture-ownership-process-shape.md) | Current pass recorded; final review | Core owns graph enrichment/batch semantic edges; API/MCP/Web are thin triggers; Web owns package adapter/shadcn UI composition; subagent review recorded residuals and fixes. |

## Final Evidence Package Gate

The final completion review must use
[2026-05-17-final-clean-evidence-package.md](2026-05-17-final-clean-evidence-package.md)
as the package checklist. In particular:

- Fixture evidence can prove implementation slices, but it cannot close the final goal.
- Historical AQ artifacts can provide comparison, but the current gate owns pass/fail status.
- A provider-only pass does not prove source diversity, graph correctness, UI truthfulness, or visual fidelity.
- A visual pass does not prove live data behavior.
- The final package must connect clean DB counts, AQ01-AQ09, more than five free-form queries, API/Web/MCP surfaces, provider settings, graph evidence, visual anchors, performance, architecture review, commit, and push.

## Pre-Code Register

The complete gap document register is [2026-05-17-gap-document-register.md](2026-05-17-gap-document-register.md).
It is the current first-stop document before any more implementation work. It
maps every gap to:

- the product promise it owns,
- current truth,
- next proof before closure,
- the latest user-visible complaints,
- the required implementation order.

The user-visible complaints currently mapped there are: free query not feeling
real, incomplete global graph, hand-rolled graph/UI components, hardcoded/static
data, corpus control-plane gaps, resolver profile configurability gaps, split
provider/Ollama detection gaps, acceptance execution/detail gaps, and final
per-page visual-anchor QA.

## Current Truth Snapshot

- The UI is no longer only a static shell, but fallback/seed display data still exists in `apps/web/lib/page-data.ts` and `WorkbenchPage` fallback helpers. Product paths must not depend on these as the primary data source.
- Static seed/fallback data is now tracked as its own blocking gap in G14 because it can hide real product failures if it is silently merged into live routes.
- G14 now has Playwright coverage for query API HTTP 500, graph API HTTP 500, initial live default query loading, stale query response suppression, row-only graph fallback truthfulness, acceptance API failure, empty corpus/resolver API responses, graph relationship-panel truthfulness, and provider smoke hydration races.
- `/api/workbench/query`, FastAPI query, and MCP search now call the SQLite-backed `asip.workbench` live service instead of fixed QA artifact query wrappers.
- `/api/workbench/index` now builds `data/asip.db` from configured raw corpora through `asip.cli index`; selected user-added corpora can be indexed through `--corpus-id`.
- Corpus additions, selected corpus indexing, resolver additions, resolver validation, provider settings, evidence detail, entity explain, and selected acceptance execution now have backend/API/MCP paths backed by SQLite.
- Provider settings are saved, recorded on index jobs, can drive embedding provider calls in the indexing path, can be checked through isolated AQ09 Web API/UI plumbing, and can drive a workbench semantic-edge generation job. The current clean local Ollama artifact proves `gemma4:e4b` semantic-edge provider smoke and `nomic-embed-text` embeddings with explicit fallback metadata; query reranking still is not a normal product path.
- PDF conversion exists, fixture PDF evidence can enter the query path, and a real AMD MI300 PDF was extracted into page chunks in a converter smoke; indexed UI page-citation QA remains open.
- Configured raw-corpus indexing now supplements query-focused code/register snippets with full-file doc/PDF ingestion from include globs, so non-query Markdown/PDF files can become queryable evidence.
- The React global graph now requests no-seed global API graph data on `/graph` load, while selected-seed graph expansion remains available for query/inspector paths.
- The active branch now treats the Obsidian-style global weighted graph as required because the user explicitly requested it after the original MVP design deferred a full graph canvas.
- The core graph API now uses NetworkX-derived hop-bounded subgraph extraction and exposes `graph_runtime: networkx`.
- Resolver profiles can influence indexed evidence for a simple configured wrapper path, but the UI/profile lifecycle is not yet feature-complete.
- Provider settings hydrate from backend state in a fresh browser session, edge and embedding API path/header settings are independently configurable, indexing can call a configured embedding provider transport, Settings can trigger AQ09 provider acceptance through Web BFF including a user-supplied DB path, Graph can trigger semantic-edge generation, and UI status now remains `unverified` until smoke/AQ09 passes. Local Ollama live model QA is proven for `gemma4:e4b`/`nomic-embed-text:latest` on the clean DB, and safe env-based extra-header expansion is tested; credentialed OpenAI-compatible live endpoint QA remains open.
- Query ranking now merges vector adapter matches with lexical/FTS evidence rows and marks vector-backed results with `vector_score` / `retrieval_sources`.
- Query filters for `ip_block` and `asic_or_generation` are wired through core, Web API, and UI query controls.
- Default full-corpus config now includes real IH_RB_CNTL and SDMA queue acceptance-oriented MxGPU queries; a temp SQLite verification found non-empty rows for both against `/tmp/asip-mxgpu`.
- Current default full-corpus configs include `**/*.md`, `**/*.rst`, and `**/*.pdf` globs. A clean CLI run now proves doc evidence enters the configured index; final UI citation and broader doc-to-code acceptance are still open.
- Current default `data/asip.db` has been reset to the clean-final DB and is byte-identical to `/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db`; the previous dirty local dev DB was backed up to `/tmp/asip-dirty-dev-before-final-default-2026-05-18.db`. Future local API or Playwright runs may dirty the default DB again, so the named clean-final artifact remains the stable final QA reference.
- Visual anchor artifacts exist, but post-functional-change page-by-page QA still needs to be rerun before completion.
- Performance smoke, final UI fidelity review, and architecture ownership review are now first-class gap items rather than implicit G10/G11 subpoints.

## Design Requirement Coverage

| Design requirement | Gap owner | Current closure state | Final proof artifact |
| --- | --- | --- | --- |
| G1. Ingest real AMD code/docs/register/PDF corpora | G01, G08, AQ01-AQ05 | Partial | Clean named SQLite DB with counts by source type and source roots. |
| G2. Normalize registers, fields, wrappers, docs, PDF pages, IP/ASIC hints | G02, G05, G12, AQ01-AQ08 | Partial | Evidence rows with resolved chains, source citations, and filterable metadata. |
| G3. Free-form hybrid retrieval over code/docs/PDF/register headers | G02, G09, AQ01-AQ09 | Partial | Acceptance query artifact showing ranked rows, retrieval sources, graph seeds, and failures. |
| G4. Relationship explanations and graph paths | G03, G05, G14, AQ06 | Partial | Weighted graph output plus inspector resolved-chain evidence from the same index. |
| G5. Web UI and MCP first-class surfaces | G04, G07, G10, G16, G17 | Partial | Web/API/MCP route/tool matrix and browser QA after final code. |
| G6. Configurable resolvers and providers | G05, G06, AQ07-AQ09 | Partial | UI/API workflow that changes resolver/provider behavior without code edits. |
| SQLite/FTS5/sqlite-vec/vector adapter | G09, G17 | Partial | Native sqlite-vec extension smoke, temp-table `search_vector()` adapter proof, and fallback adapter proof; full provider-vector coverage/rerank quality remains open. |
| NetworkX graph runtime over SQLite graph store | G03, G09, G17 | Partial | Clean-corpus graph command/API/UI proof with `graph_runtime: networkx`. |
| Next.js + shadcn UI with dark/light themes | G16 | Partial | Per-route 2K anchor QA in both themes and persistent light-theme navigation test. |
| Testing, performance, deterministic rebuild, completion gate | G10, G11, G15 | Blocking | Final QA report with commands, fixture and real-corpus timings, screenshots, and git hygiene review. |
| Full-spec future capabilities and deferrals | G13 | Blocking | Deferral ledger mapping full-spec items to MVP/deferred/user-accepted status. |

## Known Stale Or Historical Documents

- `docs/specs/2026-05-16-asip-workbench-gap-review.md` is historical context. It contains older static-prototype findings and early red-test notes that are now partly superseded by this gap ledger.
- `docs/qa/*PASS*` style visual or browser QA notes created before the latest functional changes are historical evidence only. Final completion requires fresh page-by-page QA.
- `data/asip.db` is a dirty development database and must not be used as final completion evidence. Final QA must use a clean, explicitly named SQLite database.

## Verified Progress Snapshot

2026-05-16 live workbench slice:

- Added `packages/core/src/asip/workbench.py` for raw corpus indexing, SQLite evidence query, graph expansion, corpus state, resolver state, provider settings, and CLI-backed JSON output.
- Extended SQLite storage with `corpora`, `jobs`, `evidence`, `resolver_profiles`, `provider_settings`, and MVP evidence schema fields.
- Added core tests for raw corpus indexing, evidence schema/no-match behavior, CLI `index/query/graph/acceptance`, persisted corpus state, resolver backend state, provider settings, PDF conversion, FTS5, vector fallback, and NetworkX conversion.
- Switched Next.js BFF `index/query/graph/corpora/resolver-profiles/providers/settings/acceptance` routes to the core CLI/live SQLite path.
- Switched FastAPI/MCP query, graph, corpus, resolver, provider, evidence/entity detail, and acceptance execution tools to the same live SQLite service.
- G07 semantic-edge generation parity for FastAPI and MCP is now implemented and tested.
- Last known automated verification after source-gated acceptance/register-header changes:
  - `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v`: 77 run, OK, 1 skipped for native sqlite-vec extension loading.
  - `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest apps/api/tests/test_app.py apps/api/tests/test_runtime.py apps/mcp/tests/test_tools.py apps/mcp/tests/test_server.py -v`: 39 run, OK, 1 skipped for optional live `mcp` package.
  - `pnpm --filter web exec tsc --noEmit`: passed.
  - `pnpm --filter web exec playwright test tests/workbench-api.spec.ts --reporter=list`: 18 passed.
  - `pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts --reporter=list`: 34 passed.
  - `pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts --reporter=list`: 13 passed.
  - Earlier combined smoke/visual run: `pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts tests/visual-anchor-routes.spec.ts --reporter=list`: 27 passed.
  - Targeted additions after this ledger update:
    - `packages.core.tests.test_workbench_backend_state.WorkbenchBackendStateTests.test_indexing_calls_configured_embedding_provider_transport`: passed.
    - `packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_query_can_filter_evidence_by_ip_block_and_asic_generation`: passed.
    - `pnpm --filter web exec playwright test tests/workbench-api.spec.ts -g "query API applies ASIC" --reporter=list`: passed.
    - `pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts -g "sends IP and ASIC" --reporter=list`: passed.
    - `pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts -g "settings page persists configurable" --reporter=list`: passed.
    - `pnpm test:ui tests/workbench-smoke.spec.ts -g "evidence query API failure|graph API failure"`: 2 passed.
    - `packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_global_graph_returns_weighted_edges_without_seed`: passed.
    - `pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts -g "graph route requests global graph without a default seed and renders API_GLOBAL nodes" --reporter=list`: passed.
    - `packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_query_evidence_merges_vector_backed_evidence_without_lexical_overlap`: passed.
    - `packages.core.tests.test_acceptance_runner.AcceptanceRunnerTests`: 3 passed.
    - `packages.core.tests.test_workbench_cli.WorkbenchCliTests.test_acceptance_command_writes_json_and_markdown_artifacts`: passed.
    - `packages.core.tests.test_workbench_cli.WorkbenchCliTests.test_acceptance_command_can_filter_query_and_print_full_payload`: passed.
    - `apps.api.tests.test_app.ApiAppTests.test_acceptance_run_executes_selected_query`: passed.
    - `apps.mcp.tests.test_tools.McpToolTests.test_run_acceptance_executes_selected_query`: passed.
    - `apps.web.tests.workbench-api.spec.ts`: selected acceptance execution API test passed.
    - `apps.web.tests.workbench-smoke.spec.ts`: initial live query and row-only graph fallback truthfulness tests passed.
    - `apps.web.tests.workbench-smoke.spec.ts`: selected Corpus UI indexing sends only checked corpus ids and shows returned `indexed` status.
    - `packages.core.tests.test_workbench_corpus_state.WorkbenchCorpusStateTests.test_missing_registered_corpus_root_fails_index_and_marks_status_failed`: passed.
    - `packages.core.tests.test_workbench_corpus_state.WorkbenchCorpusStateTests.test_unknown_registered_corpus_id_fails_instead_of_indexed_zero_docs`: passed.
    - `packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_configured_index_missing_source_root_fails_instead_of_indexed_zero_docs`: passed.
    - `apps.web.tests.workbench-smoke.spec.ts`: Corpus failure UI marks selected rows `failed`, and real Web add-index-query flow returns a unique symbol from the indexed local corpus.
    - `apps.web.tests.workbench-smoke.spec.ts`: Resolver profile UI validates dynamic Python source and shows disabled profile status.
    - `apps.web.tests.workbench-smoke.spec.ts`: live query rows drive table, graph, and inspector resolved-chain/source-preview content, including selected-row inspector changes.
    - `apps.web.tests.workbench-api.spec.ts`: AQ09 provider acceptance exposes independently configured edge and embedding provider provenance from an isolated DB.
    - `apps.web.tests.workbench-smoke.spec.ts`: Settings `Run AQ09 acceptance` calls Web BFF selected acceptance execution and displays provider/model checks.
    - `apps.web.tests.workbench-smoke.spec.ts`: Provider status remains `unverified` after Settings save/hydration and becomes `verified` only after provider smoke or AQ09 success.
    - `apps.web.tests.workbench-smoke.spec.ts`: Settings can run AQ09 against a user-supplied isolated DB through the real Web BFF/core runner and local fake Ollama edge HTTP server.
    - `packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_semantic_edge_job_generates_edges_from_indexed_evidence_and_provider_settings`: passed.
    - `apps.web.tests.workbench-api.spec.ts`: semantic-edge API generates graph edges from a supplied DB.
    - `apps.web.tests.workbench-smoke.spec.ts`: Graph page `Generate semantic edges` action calls the workbench API and refreshes the rendered graph.
- First clean CLI acceptance artifact after runner implementation:
  - Clean DB: `/tmp/asip-acceptance-clean-2026-05-17.db`
  - Index command result: 26 documents, 351 chunks, 5812 evidence rows, 23 edges, 1347 scanned files.
  - Artifact files: `docs/qa/2026-05-17-acceptance-clean-qwen35.json` and `docs/qa/2026-05-17-acceptance-clean-qwen35.md`.
  - AQ summary: 9 total, 0 pass, 8 partial, 1 fail. Partial means CLI rows existed but API/Web/MCP surfaces are not yet proven; AQ09 fails because provider settings are required.
- AQ09 provider-specific smoke artifact after runner implementation:
  - Artifact files: `docs/qa/2026-05-17-aq09-provider-smoke-ollama.json` and `docs/qa/2026-05-17-aq09-provider-smoke-ollama.md`.
  - Provider checks: embedding provider `ollama` / `nomic-embed-text:latest` pass with 1 provider-sourced embedding and 0 fallbacks; semantic-edge provider `ollama` / `gemma4:e4b` pass with 1 edge.
  - AQ09 remains partial because final clean AMD corpus API/Web/MCP evidence and credentialed OpenAI-compatible/live semantic-edge product QA remain open, even though Web API/UI and FastAPI/MCP semantic-edge paths now have isolated-DB proof.
- Clean provider rerun after qwen3.5 semantic-edge generation:
  - Artifact files: `docs/qa/2026-05-17-acceptance-clean-qwen35-provider-rerun.json` and `docs/qa/2026-05-17-acceptance-clean-qwen35-provider-rerun.md`.
  - Historical AQ summary under the older gate: 9 total, 9 pass, 0 partial, 0 failed across CLI/API/Web/MCP surface labels in the runner artifact.
  - Provider checks: embedding provider `ollama` / `nomic-embed-text:latest` pass with 9058 provider-sourced embeddings and 382 deterministic fallbacks; semantic-edge provider `ollama` / `qwen3.5:4b` pass with 1 edge.
  - All AQ01-AQ09 results in this artifact currently report `source_types: ["code"]`, including AQ05. This closes clean AQ runner mechanics, but not cross-source G01/G08 evidence.
  - This does not close G10/G11 completion because visual QA, performance, architecture, design-doc review, and source-diversity evidence remain separate gates.
- Source-gated acceptance rerun under the current gate:
  - Artifact files: `docs/qa/2026-05-17-acceptance-clean-qwen35-source-gated-current.json` and `docs/qa/2026-05-17-acceptance-clean-qwen35-source-gated-current.md`.
  - AQ summary: 9 total, 0 pass, 0 partial, 9 failed.
  - Database health fails because `mxgpu` is still `indexing` and index job 3 failed after the interrupted provider reindex.
  - AQ05 also fails with `required source types missing: pdf`.
  - This is the current authoritative acceptance result for `/tmp/asip-acceptance-clean-2026-05-17.db`.
- Current clean AMD gemma provider acceptance:
  - Artifact files: `docs/qa/2026-05-18-acceptance-clean-amd-gemma4-final-current.json` and `docs/qa/2026-05-18-acceptance-clean-amd-gemma4-final-current.md`.
  - DB path: `/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db`.
  - AQ summary: 9 total, 9 pass, 0 partial, 0 failed.
  - Counts: documents 124, chunks 21884, evidence 860516, graph edges 41893, provider embeddings 32, semantic edges 25 after the clean-final graph rebuild and Stage 2/doc-node jobs.
  - Provider checks: `ollama/nomic-embed-text:latest` embeddings with zero fallback rows and `ollama/gemma4:e4b` semantic-edge smoke.
- Synthetic multi-source fixture acceptance proof:
  - Artifact files: `docs/qa/2026-05-17-acceptance-multisource-fixture.json` and `docs/qa/2026-05-17-acceptance-multisource-fixture.md`.
  - DB path: `/tmp/asip-multisource-clean-2026-05-17.db`.
  - DB health passes and the fixture contains 5 documents, 6 chunks, 34 evidence rows, 7 edges, 1 corpus, and 1 index job.
  - Document source counts: `code=1`, `doc=1`, `pdf=1`, `register=2`; evidence source counts: `code=23`, `doc=3`, `pdf=4`, `register=4`.
  - AQ05 passes with `code`, `doc`, `pdf`, and `register`; AQ06 passes with `code` and `register`; graph runtime is `networkx`.
  - This is fixture evidence only. It proves the multi-source path and source-diversity gate can work, but it does not close real AMD corpus ingestion, all AQ01-AQ09, live provider closure, browser visual QA, or performance.
- Final verification already recorded before staging:
  - Core unittest: 202 OK with 2 optional sqlite-vec skips.
  - API/MCP unittest: 45 OK with 1 optional MCP runtime skip.
  - `pnpm --filter web exec tsc --noEmit` passed.
  - `pnpm --filter web run lint` passed.
  - Web API+smoke Playwright: 73 passed.
  - Visual route Playwright: 15 passed.
  - Browser/default-DB `/graph` QA and `git diff --check` passed.

## Code Freeze Rule

Before writing more feature code, use this folder to choose the next workstream and write the failing test first. Each code change must close a named gap ID and update the corresponding gap document with:

- the failing test added first,
- the implementation evidence,
- the exact verification commands run,
- remaining risks or explicit user-approved deferrals.
