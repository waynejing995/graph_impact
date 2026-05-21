# ASIP Gap Documents Before More Code

Date: 2026-05-16
Status: Current user-review blocker pass verified; 2026-05-19 graph
integration and finalization contracts added; 2026-05-21 expanded-DB
acceptance/browser/provider/Stage 2/callback gates pass, with residual
acceptance and current git closure still blocking final completion

## Purpose

This folder is the source of truth for the ASIP workbench gap inventory before any more feature code is written.

The current repository contains useful partial work, but it is not yet a finished ASIP MVP-1 product. These documents separate what exists from what must still be implemented and verified.

Do not write more product code until this gap ledger is stable. Do not mark the active goal complete, commit, or push until every blocking gap below is closed or explicitly accepted as out of scope by the user.

Current final-candidate evidence is recorded in
`docs/qa/2026-05-17-final-clean-evidence-package.md`. Historical `PASS`,
provider smoke, fixture acceptance, or older visual-anchor artifacts remain
non-closing evidence unless they are linked from that package. The active goal
is still not complete until final residual-boundary acceptance and the latest
audit changes are committed and pushed through G11.

2026-05-19 integration update: the current graph/source-of-truth plan is
[`docs/specs/2026-05-19-asip-graph-integration-plan.md`](../specs/2026-05-19-asip-graph-integration-plan.md).
The current final-gate execution checklist is
[`docs/specs/2026-05-19-current-graph-finalization-plan.md`](../specs/2026-05-19-current-graph-finalization-plan.md).
It reconciles the latest user direction into one contract:

- default product graph has exactly three conceptual node kinds:
  `function`, `register`, and `doc`;
- Markdown sections, PDF sections, and BoxMatrix boxes are `doc` nodes with
  `attr.doc_kind`, not separate top-level product kinds;
- macros, resolver wrappers, fields, callback slots/tables, source files,
  providers, and models are provenance/attributes only;
- Stage 1 deterministic extraction and Stage 2 LLM semantic edges are separate
  gates with separate proof;
- same-repo multi-subfolder corpora, resolver YAML, register inventory, and
  function/register normalization are product projection rules with provenance,
  not hardcoded graph rewrites;
- default/global graph budgets come from config plus visible UI filters; hidden
  hardcoded graph limits are not closing evidence;
- Web standard controls use shadcn/Radix composition and browser QA must use
  the in-app browser or Computer Use route requested by the user;
- final graph closure requires a real SQLite DB and no-mock API/Web/e2e gate,
  not fixture-only, stale default DB, or static artifact evidence;
- performance optimization must start with layered profiling before changing
  query/global graph loading.

Important gate distinction: 2026-05-18 clean-final artifacts remain valuable
historical/current-candidate evidence, and they establish the current clean
provider as `gemma4:e4b`. They do not by themselves close the 2026-05-19
integrated product graph contract until fresh schema validation, no-mock
`/graph` browser/e2e evidence, API/MCP/Web parity, and residual-boundary
acceptance are recorded against the current tree.

2026-05-20 expanded-DB update: current default `data/asip.db` re-indexed
`linux-amdgpu` with `1101` documents, including `476` register-header docs, and
superseded the interrupted job `9`. The current artifact
`docs/qa/2026-05-20-acceptance-data-asip-expanded.md` reports database health
`pass`, schema `pass` for AQ01-AQ09, AQ05 source diversity restored, and summary
`0 passed / 8 partial / 1 failed`. AQ09 now distinguishes persisted
`ollama/gemma4:e4b` semantic-edge rows from current provenance freshness:
`14` matching `semantic_edges` rows exist from job `4`, but latest index job
`10` is newer, so `semantic_edge_provenance` is `partial/stale`, not pass.
Live semantic-edge provider reachability also fails with `Operation not
permitted`. Fresh browser/e2e remains blocked by local `listen`/connect
`EPERM`, so older `9/9` artifacts must stay labeled historical or
final-candidate rather than current completion proof.

Supplemental Web-included acceptance
`docs/qa/2026-05-20-acceptance-data-asip-expanded-web-blocked.md` explicitly
requests CLI/API/Web/MCP for AQ01-AQ09. It records `0 passed / 0 partial / 9
failed`: CLI/API/MCP probes return rows and schema `pass`, while every Web probe
is `not_configured` because no reachable `ASIP_WEB_BASE_URL`/browser server is
available in this environment.

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
UI loop, and fresh light/dark route QA. The 2026-05-18 continuation adds the
default-budget cross-repo register bridge proof, a six-route dark/light browser
visual pack, and a design-review closure matrix. G11 remains the final gate for
artifact hygiene, commit/push of the latest audit changes, and explicit
residual-boundary acceptance.

Supporting acceptance matrix:

- [Gap Document Register Before Code](2026-05-17-gap-document-register.md): complete G01-G17/AQ register, current truth, user-visible complaint mapping, and implementation order before more code.
- [MVP Acceptance Query Matrix](2026-05-16-mvp-acceptance-query-matrix.md): nine query-level closure rules for G10.
- [Gap Inventory Before Code](2026-05-17-gap-inventory-before-code.md): one-page inventory of every gap document, current state, and the next evidence required before implementation resumes.
- [Final Clean Evidence Package Gate](2026-05-17-final-clean-evidence-package.md): required final QA package that prevents fixture, historical, provider-only, or visual-only artifacts from being mistaken for completion.
- [Final Clean Evidence Package](../qa/2026-05-17-final-clean-evidence-package.md): historical/final-candidate package with clean AMD DB counts, AQ01-AQ09 9/9, six free queries plus later 10-query graph QA, semantic-edge jobs, visual QA, automated verification, and architecture review. It is not the current 2026-05-20 expanded-DB completion proof.
- [Design Review Closure Matrix](../qa/2026-05-18-design-review-closure-matrix.md): explicit MVP G1-G6 and AQ01-AQ09 mapping to current evidence and residual boundaries.

## Gap Document Index

| ID | Gap document | Status | Why it blocks |
| --- | --- | --- | --- |
| G01 | [Real Ingestion And Indexing](2026-05-16-g01-real-ingestion-indexing.md) | Historical clean-final pass; expanded default-DB gate open | The named clean-final artifact `/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db` records `documents=124`, `chunks=21884`, `evidence=860516`, source counts across code/doc/pdf/register, all clean jobs succeeded, and AQ01-AQ09 9/9. Current default `data/asip.db` was expanded on 2026-05-20 to include `1101` `linux-amdgpu` documents, including `476` register headers; final closure still depends on G11 residual review, browser/provider proof, commit, and push. |
| G02 | [Live Retrieval And Evidence Schema](2026-05-16-g02-live-retrieval-evidence-schema.md) | Partial; quality boundary open | SQLite evidence schema, FTS, vector fallback retrieval, query-time provider-vector wiring/fallback metadata, no-match/failure states, live inspector linkage, and clean AQ runner mechanics exist; production semantic ranking quality, cross-source ranking, and final visual/design closure remain open. |
| G03 | [Dynamic Weighted Graph](2026-05-16-g03-dynamic-weighted-graph.md) | Partial; 2026-05-19 integrated contract added; typed AST/type-flow, schema validator, and no-mock final gate residuals | `/graph` uses `react-force-graph-2d` over live no-seed graph data, with function-operation edges, cross-file common-helper/direct/callback call edges, callback alias/type hints, bounded return-table aliases, local receiver alias flow, dynamic receiver multi-candidate `*_ambiguous` dispatch provenance, cross-repo register nodes merged by canonical symbol/IP with IP versions as attrs/source provenance, ambiguous returned-table alias rejection, IP-block registration aliases, selective Clang AST JSON receiver hints, selective Clang AST JSON macro-wrapped callback-initializer hints, document subtype raw facts, filtered batch semantic edges, resolver-profile-scoped function concept ids, and resolver-profile-owned register identity. The 2026-05-19 contract now requires the default product graph to project document subtypes into `kind=doc`, keep macros/wrappers/fields/source/provider names out of visible nodes, prove Stage 1 deterministic extraction separately from Stage 2 LLM semantic edges, and rerun a current real-DB/no-mock `/graph` gate before closure. Full clangd/libclang cross-TU vtable/type-flow remains a named residual until a typed extractor and tests land. |
| G04 | [Corpus Management](2026-05-16-g04-corpus-management.md) | Current clean corpus flow verified; orchestration boundary | Backend/API/MCP corpus add/list/index, UI selected-corpus indexing, invalid-source failure, durable job lifecycle visibility, clean named DB BFF add-index-query graph proof, and real Web add-index-query graph/inspector proof exist. Background workers, cancellation, and remote clone orchestration remain outside this MVP slice. |
| G05 | [Resolver Profiles](2026-05-16-g05-resolver-profiles.md) | Current pass verified; function/register/access graph normalization operational | YAML-backed profiles, backend/API/MCP add/list/validate, UI validation, disabled/edit state, per-index selection, and selected-profile changed graph output are proven. Resolver-owned `graph.function_normalization`, `graph.register_normalization`, and `graph.access_relation_map` now affect product projection with TDD coverage for profile namespaces, disabled aliases, path fallback, custom register identity, and custom access-to-edge mapping. Remaining graph-profile work is graph profile presets, plus richer unmatched-span diagnostics and broader non-C strategies. |
| G06 | [Provider Settings And Ollama Detection](2026-05-16-g06-provider-settings-ollama.md) | Current local/batch/full-temp-backfill/query-rerank pass verified; explicit OpenAI-live boundary | Settings persist/hydrate, embedding provider calls, safe env-based extra-header expansion, isolated AQ09 Web API provenance, Settings AQ09 UI/BFF wiring, query-scoped and batch semantic-edge jobs, query-time provider-vector rerank wiring, current clean local Ollama `gemma4:e4b`/`nomic` QA, historical `qwen3.5` comparison artifacts, bounded 128-chunk provider backfill, and full local temp-copy provider embedding coverage (`21884 / 21884`, missing 0) are tested; credentialed OpenAI-compatible live endpoint QA and production-scale semantic ranking quality remain open boundaries. |
| G07 | [API And MCP Product Surfaces](2026-05-16-g07-api-mcp.md) | Deterministic product-surface and real MCP runtime pass verified | Query/graph, selected acceptance execution, corpus/resolver/provider control-plane slices, evidence/entity detail slices, deterministic structured resolved-chain explanations, semantic-edge FastAPI/MCP parity, key read-route no-mutation coverage, FastAPI live HTTP smoke including `pnpm dev:api`, MCP server tool-matrix registration, Web/MCP query/evidence/entity/graph agreement, and bundled-Python real MCP runtime smoke exist. |
| G08 | [PDF And Document Ingestion](2026-05-16-g08-pdf-document-ingestion.md) | Current pass verified; 2026-05-19 product projection gate open | PDF conversion/page evidence and Markdown/PDF document raw facts are recorded. Older QA mentions a PDF-derived `pdf_section` node; the current product graph contract requires default output to expose that as `kind=doc` with `attr.doc_kind=pdf_section`. The remaining boundary is richer PDF corpus content depth plus current schema/no-mock proof, not page-aware product plumbing. |
| G09 | [SQLite FTS5 Vector And NetworkX Runtime](2026-05-16-g09-storage-vector-graph-runtime.md) | Partial; provider-quality boundary open | FTS5, provider embeddings, query-time provider-vector rerank wiring, NetworkX graph, native sqlite-vec extension smoke, native `search_vector()` adapter path, and JSON/Python-cosine fallback are tested; full current-DB provider-vector coverage and semantic rerank quality remain boundaries. |
| G10 | [Testing Acceptance And Visual QA](2026-05-16-g10-testing-acceptance-visual-qa.md) | Current expanded-DB acceptance and browser QA pass | Clean-final and 2026-05-19 browser artifacts remain candidate/historical. The current 2026-05-21 `data/asip.db` artifacts pass AQ01-AQ09 across CLI/API/API_LIVE/Web/MCP/MCP_PROTOCOL, pass browser e2e `109/109`, pass Web no-server smoke `9/9`, and include concept-detail browser proof for selecting a real `:concept:` function node and viewing `Concept Generated From` implementation details. |
| G11 | [Completion Gate And Documentation Review](2026-05-16-g11-completion-gate.md) | Final gate open | The current 2026-05-21 aggregate completion gate records `17/19` pass before commit: expanded DB, artifact binding, Stage 1 graph, product graph schema, CLI/API/API_LIVE/Web/MCP/MCP_PROTOCOL, provider live checks, Stage 2 semantic freshness/live generation, labeled semantic quality, callback/vtable audit, browser e2e, no-server smoke, and performance smoke pass. Explicit residual-boundary acceptance and current git closure remain blocking. |
| G12 | [ASIC And IP Metadata Filtering](2026-05-16-g12-asic-ip-metadata-filtering.md) | Current real AMD filter pass verified; heuristic boundary | Core, Web BFF/UI, FastAPI, and MCP filters now affect query behavior. Real clean-final QA proves representative `ipBlock=CP` and `ipBlock=SDMA` result-set changes; path/symbol heuristic inference limits remain documented as the MVP boundary. |
| G13 | [MVP Boundary And Full-Spec Deferrals](2026-05-16-g13-mvp-boundary-deferrals.md) | Blocking | Long-range full-spec items must be explicitly deferred so they do not masquerade as silent failures. |
| G14 | [Static Data And Truthful Empty States](2026-05-16-g14-static-data-and-truthful-empty-states.md) | Current pass verified; audit residual | Static default query/graph rows are removed from product paths, unused static artifact query/graph helpers were deleted, row-only graph fallback no longer fabricates graph data, query metrics no longer invent graph counts, and empty/error states have E2E/API coverage; broader route audit remains tracked for final review. |
| G15 | [Performance Smoke And Deterministic Rebuild](2026-05-16-g15-performance-smoke-deterministic-rebuild.md) | Current performance pass with explicit residuals; layered profiling plan added | Fixture-side smoke is automated and documented; the local AMD DB has query-graph performance QA over more than five real queries, AQ01 Web acceptance under the 30s e2e timeout, repeat deterministic graph rebuild timings (`131.639s`, `126.034s`) with stable counts, bounded 128-chunk provider backfill timing, full local temp-copy provider backfill timing (`2388.07s`), two empty-DB raw re-index timings (`506.75s`, `507.07s`), and edge-count summary/table counting fixed. The 2026-05-19 plan requires layered profiling across browser, Next BFF, Python query, SQLite/NetworkX, and acceptance before optimizing global graph loading or slow queries. Semantic ranking quality, local model latency, and hosted-provider throughput remain residuals. |
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

- Product paths now use live API/core data, explicit empty states, or explicit errors. Static route copy in `apps/web/lib/page-data.ts` is limited to chrome labels and empty defaults, not seeded result rows.
- G14 now has Playwright coverage for query API HTTP 500, graph API HTTP 500, stale query response suppression, row-only graph fallback truthfulness, acceptance API failure, empty corpus/resolver API responses, graph relationship-panel truthfulness, and provider smoke hydration races.
- `/api/workbench/query`, FastAPI query, and MCP search now call the SQLite-backed `asip.workbench` live service instead of fixed QA artifact query wrappers.
- `/api/workbench/index` now builds `data/asip.db` from configured raw corpora through `asip.cli index`; selected user-added corpora can be indexed through `--corpus-id`.
- Corpus additions, selected corpus indexing, resolver additions, resolver validation, provider settings, evidence detail, entity explain, and selected acceptance execution now have backend/API/MCP paths backed by SQLite.
- Provider settings are saved, recorded on index jobs, can drive embedding provider calls in the indexing path, can be checked through isolated AQ09 Web API/UI plumbing, can drive query-time provider-vector rerank, and can drive a workbench semantic-edge generation job. The current clean local Ollama artifacts prove `gemma4:e4b` semantic-edge provider smoke, full temp-copy `nomic-embed-text` provider embedding coverage, explicit truncation/fallback metadata, and a local provider-vector query smoke; credentialed OpenAI-compatible live QA and production-scale semantic ranking quality remain explicit boundaries.
- PDF conversion exists, fixture PDF evidence can enter the query path, a real AMD MI300 PDF was extracted into page chunks in a converter smoke, and clean-final API/browser QA proves indexed PDF page citation plus historical `pdf_section` raw/debug shape. Current final graph proof must project it to `kind=doc` with `attr.doc_kind=pdf_section`.
- Configured raw-corpus indexing now supplements query-focused code/register snippets with full-file doc/PDF ingestion from include globs, so non-query Markdown/PDF files can become queryable evidence.
- The React global graph now requests no-seed global API graph data on `/graph` load, while selected-seed graph expansion remains available for query/inspector paths.
- The active branch now treats the Obsidian-style global weighted graph as required because the user explicitly requested it after the original MVP design deferred a full graph canvas.
- The core graph API now uses NetworkX-derived hop-bounded subgraph extraction and exposes `graph_runtime: networkx`.
- Resolver profiles can influence indexed evidence for a simple configured wrapper path, but the UI/profile lifecycle is not yet feature-complete.
- Provider settings hydrate from backend state in a fresh browser session, edge and embedding API path/header settings are independently configurable, indexing can call a configured embedding provider transport, Settings can trigger AQ09 provider acceptance through Web BFF including a user-supplied DB path, Graph can trigger semantic-edge generation, and UI status now remains `unverified` until smoke/AQ09 passes. Local Ollama live model QA is proven for `gemma4:e4b`/`nomic-embed-text:latest` on the clean DB, and safe env-based extra-header expansion is tested; credentialed OpenAI-compatible live endpoint QA remains open.
- Query ranking now merges vector adapter matches with lexical/FTS evidence rows and marks vector-backed results with `vector_score` / `retrieval_sources`.
- Query filters for `ip_block` and `asic_or_generation` are wired through core, Web API/UI query controls, FastAPI `/query`, and MCP `search_evidence()`.
- Default full-corpus config now includes real IH_RB_CNTL and SDMA queue acceptance-oriented MxGPU queries; a temp SQLite verification found non-empty rows for both against `/tmp/asip-mxgpu`.
- Current default full-corpus configs include `**/*.md`, `**/*.rst`, and `**/*.pdf` globs. Clean-final QA proves doc/PDF evidence enters the configured index, and browser/API QA proves PDF page citation plus historical PDF-section graph evidence; the 2026-05-19 product graph gate must expose that as `kind=doc`.
- Current default `data/asip.db` was reset to the clean-final DB for G01/G10, then intentionally rebuilt for the G03 typed-callback graph slice. The named clean-final artifact `/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db` remains the stable acceptance reference; default `data/asip.db` is now the live graph workbench DB.
- Visual anchor artifacts and post-functional-change page-by-page QA exist, including 2K route checks in light/dark mode and route baseline tests.
- Performance smoke, final UI fidelity review, and architecture ownership review are now first-class gap items rather than implicit G10/G11 subpoints.

## Design Requirement Coverage

| Design requirement | Gap owner | Current closure state | Final proof artifact |
| --- | --- | --- | --- |
| G1. Ingest real AMD code/docs/register/PDF corpora | G01, G08, AQ01-AQ05 | Current pass verified; final gate | Clean named SQLite DB with counts by source type and source roots. |
| G2. Normalize registers, fields, wrappers, docs, PDF pages, IP/ASIC hints | G02, G05, G12, AQ01-AQ08 | Current pass with heuristic/provider residuals | Evidence rows with resolved chains, structured resolved-chain explanations, source citations, and filterable metadata. |
| G3. Free-form hybrid retrieval over code/docs/PDF/register headers | G02, G09, AQ01-AQ09 | Backend/current local retrieval pass; current expanded final gate still blocked by Web/provider AQ09 evidence | Acceptance query artifact showing ranked rows, retrieval sources, graph seeds, and failures. |
| G4. Relationship explanations and graph paths | G03, G05, G14, AQ06 | Current pass with full clangd/libclang residual | Weighted graph output plus inspector resolved-chain evidence from the same index. |
| G5. Web UI and MCP first-class surfaces | G04, G07, G10, G16, G17 | Current Web/API/MCP/browser pass | Web/API/MCP route/tool matrix, bundled-Python MCP runtime smoke, Web acceptance surface, and browser QA after final code. |
| G6. Configurable resolvers and providers | G05, G06, AQ07-AQ09 | Current local provider/provenance pass with hosted-provider residual | UI/API workflow that changes resolver/provider behavior without code edits; hosted credentialed OpenAI-compatible QA remains a residual boundary. |
| SQLite/FTS5/sqlite-vec/vector adapter | G09, G17 | Adapter and provider-rerank wiring pass; quality boundary | Native sqlite-vec extension smoke, temp-table `search_vector()` adapter proof, fallback adapter proof, and query-time provider-vector wiring proof; full current-DB provider-vector coverage and semantic ranking quality remain open. |
| NetworkX graph runtime over SQLite graph store | G03, G09, G17 | Current pass verified | Clean-corpus graph command/API/UI proof with `graph_runtime: networkx`. |
| Next.js + shadcn UI with dark/light themes | G16 | Current pass verified | Per-route 2K anchor QA in both themes and persistent light-theme navigation test. |
| Testing, performance, deterministic rebuild, completion gate | G10, G11, G15 | Current test/perf/browser/callback pass; git gate in progress | Final QA report with commands, fixture and real-corpus timings, screenshots, callback audit, and git hygiene review. |
| Full-spec future capabilities and deferrals | G13 | Deferral ledger exists; user acceptance pending | Deferral ledger mapping full-spec items to MVP/deferred/user-accepted status. |

## Known Stale Or Historical Documents

- `docs/specs/2026-05-16-asip-workbench-gap-review.md` is historical context. It contains older static-prototype findings and early red-test notes that are now partly superseded by this gap ledger.
- `docs/qa/*PASS*` style visual or browser QA notes created before the latest functional changes are historical evidence only. Final completion requires fresh page-by-page QA.
- Current default `data/asip.db` is not the byte-identity artifact after the G03 typed-callback rebuild. Final QA should continue to cite the named clean-final SQLite artifact for acceptance, and cite `data/asip.db` for the live graph workbench proof after the latest graph rebuild.

## Historical Verified Progress Snapshot

2026-05-16 live workbench slice:

- Added `packages/core/src/asip/workbench.py` for raw corpus indexing, SQLite evidence query, graph expansion, corpus state, resolver state, provider settings, and CLI-backed JSON output.
- Extended SQLite storage with `corpora`, `jobs`, `evidence`, `resolver_profiles`, `provider_settings`, and MVP evidence schema fields.
- Added core tests for raw corpus indexing, evidence schema/no-match behavior, CLI `index/query/graph/acceptance`, persisted corpus state, resolver backend state, provider settings, PDF conversion, FTS5, vector fallback, and NetworkX conversion.
- Switched Next.js BFF `index/query/graph/corpora/resolver-profiles/providers/settings/acceptance` routes to the core CLI/live SQLite path.
- Switched FastAPI/MCP query, graph, corpus, resolver, provider, evidence/entity detail, and acceptance execution tools to the same live SQLite service.
- G07 semantic-edge generation parity for FastAPI and MCP is now implemented and tested.
- Historical automated verification after source-gated acceptance/register-header changes, superseded by the current 2026-05-18 suite above:
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
  - Empty-DB raw re-index proof: `docs/qa/2026-05-18-g15-empty-db-raw-corpus-reindex.md` records two fresh raw rebuilds with matching counts and fixed Stage 2 endpoint filtering.
  - Provider checks: `ollama/nomic-embed-text:latest` embeddings with zero fallback rows and `ollama/gemma4:e4b` semantic-edge smoke.
- Synthetic multi-source fixture acceptance proof:
  - Artifact files: `docs/qa/2026-05-17-acceptance-multisource-fixture.json` and `docs/qa/2026-05-17-acceptance-multisource-fixture.md`.
  - DB path: `/tmp/asip-multisource-clean-2026-05-17.db`.
  - DB health passes and the fixture contains 5 documents, 6 chunks, 34 evidence rows, 7 edges, 1 corpus, and 1 index job.
  - Document source counts: `code=1`, `doc=1`, `pdf=1`, `register=2`; evidence source counts: `code=23`, `doc=3`, `pdf=4`, `register=4`.
  - AQ05 passes with `code`, `doc`, `pdf`, and `register`; AQ06 passes with `code` and `register`; graph runtime is `networkx`.
  - This is fixture evidence only. It proves the multi-source path and source-diversity gate can work, but it does not close real AMD corpus ingestion, all AQ01-AQ09, live provider closure, browser visual QA, or performance.
- Final verification already recorded before staging:
- Core unittest: 235 OK with 2 optional sqlite-vec skips.
  - API/MCP unittest: 47 OK with 1 optional MCP runtime skip.
  - Bundled-Python MCP runtime: 29 OK with 0 skips.
  - `pnpm --filter web run lint` passed.
  - `pnpm --filter web exec tsc --noEmit` passed.
  - Visual route Playwright: 15 passed.
  - Combined Web API+smoke+visual Playwright: 90 passed.
  - Browser/default-DB `/graph` QA and `git diff --check` passed.

## Code Freeze Rule

Before writing more feature code, use this folder to choose the next workstream and write the failing test first. Each code change must close a named gap ID and update the corresponding gap document with:

- the failing test added first,
- the implementation evidence,
- the exact verification commands run,
- remaining risks or explicit user-approved deferrals.
