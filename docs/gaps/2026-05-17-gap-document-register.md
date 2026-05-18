# Gap Document Register Before Code

Date: 2026-05-17
Status: Rolling gate updated after current user-review blocker pass

## Purpose

This is the register to read before writing more product code. It is a rolling
status gate, not a frozen historical baseline. It lists every
active gap document, what product promise it owns, the current truth, and the
next proof required before that gap can close.

No functional code should be written from this point forward unless the change
names one of these gap IDs, starts with a failing test, and updates the same gap
document with verification evidence.

2026-05-17 current pass update: the user-review blockers around static-looking
UI, incomplete global graph, hand-rolled graph, shadcn/Radix usage, function
operation edges, document section nodes, batch semantic-edge generation,
acceptance detail expansion, and real add-index-query UI flow now have
implementation and verification evidence in
`docs/qa/2026-05-17-graph-function-section-batch-qa.md`. G11 remains the
final commit/push and residual-deferral gate.

## Complete Gap Document Set

| ID | Document | Product promise owned | Current truth | Next proof before closure |
| --- | --- | --- | --- | --- |
| G01 | [Real Ingestion And Indexing](2026-05-16-g01-real-ingestion-indexing.md) | Index real AMD code, docs, register headers, and PDF/text docs from raw inputs. | Current clean-final DB `/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db` has `documents=124`, `chunks=21884`, `evidence=860516`, `edges=41893`, source counts `code/doc/pdf/register`, all clean jobs succeeded, and AQ01-AQ09 9/9 with `gemma4:e4b` provider smoke. | Final browser/default-DB QA and completion gate must preserve this artifact through product surfaces. |
| G02 | [Live Retrieval And Evidence Schema](2026-05-16-g02-live-retrieval-evidence-schema.md) | Free-form hybrid retrieval with evidence schema, snippets, resolved chains, graph seeds, and truthful no-match behavior. | Partial. Clean AMD AQ01-AQ09 is 9/9, more than five real free-form queries are recorded, schema/no-match/live inspector tests exist, source diversity is proven, and provider-vector query-time wiring/fallback metadata is tested. Production semantic ranking quality and final route/visual closure remain incomplete. | Browser QA must prove user-entered queries, rows, graph, and inspector update from the same clean DB payload. |
| G03 | [Dynamic Weighted Graph](2026-05-16-g03-dynamic-weighted-graph.md) | Obsidian-style global graph and query-scoped graph rendered from weighted stored relationships. | Current graph pass verified with explicit residual. NetworkX-backed graph data includes persisted/evidence edges, function operation edges, conservative direct/callback call edges, cross-file unique direct common-helper calls, cross-file callback initializer calls, generic `vtable_dispatch` callback candidates, receiver type-hint filtering, local/field-path/device-field callback table-alias precision, local receiver-path alias flow, dynamic receiver multi-candidate `*_ambiguous` dispatch provenance, cross-repo register nodes merged by canonical symbol/IP/IP-version with source as attr, default-budget preservation of representative shared-register bridge edges, bounded returned-table aliases with ambiguous selector rejection, receiver-path table-type hints, IP-block `.funcs` table-field alias propagation, corpus-level IP-block registration aliases, selective Clang AST JSON receiver-type hints, selective Clang AST JSON macro-wrapped callback-initializer hints, MxGPU `amdgv_init_func` dispatch coverage, document section nodes, doc boxes, and filtered batch semantic edges; `/graph` uses `react-force-graph-2d`. Latest QA adds 11 real CLI/core queries, exact function-node graph fallback, empty-DB raw graph export with only `function/register/doc_box/doc_section` node kinds, default `limit=3000` cross-repo `IH_RB_CNTL` Web BFF proof, and browser 2K screenshots. Full clangd/libclang cross-TU vtable type-flow is still not complete. | Preserve clean-final QA through G11; full clangd/libclang type-flow callback resolution remains a named residual unless implemented; rerun visual tests if UI changes again. |
| G04 | [Corpus Management](2026-05-16-g04-corpus-management.md) | Users can add/select/index corpora without editing code. | Current clean corpus flow verified. Backend/API/MCP add/list/index paths exist; UI selected-corpus indexing, invalid-source/zero-doc false-success prevention, durable job events, clean named DB BFF add-index-query graph proof, and real Web add-index-query graph/inspector proof are recorded. Jobs expose canonical `queued/indexing/succeeded/failed` events through core, CLI, Web BFF, FastAPI, MCP, and the Corpus page. | Preserve evidence through G11; background workers, cancellation, remote clone orchestration, and arbitrary UI DB selection remain outside this MVP slice. |
| G05 | [Resolver Profiles](2026-05-16-g05-resolver-profiles.md) | Resolver profiles are configurable per repo/language and are not macro-only. | Current pass verified. YAML configs, backend/API/MCP add/list/validate, UI validation, disabled status, edit/load existing profile, per-index profile selection, CLI/API/MCP/Web BFF passthrough, and selected-profile changed graph output are proven. UI only lists profiles backed by real YAML config or backend state pointing at existing YAML. | Preserve evidence through final G11; richer unmatched-span diagnostics and broader non-C strategies remain explicit boundaries unless implemented. |
| G06 | [Provider Settings And Ollama Detection](2026-05-16-g06-provider-settings-ollama.md) | Edge and embedding providers are independently configurable, Ollama can be detected, OpenAI-compatible formats work, and semantic-edge jobs can run query-scoped or batch corpus generation. | Current local/batch/full-temp-backfill/query-rerank pass verified. Settings persist across Web/API/MCP, Ollama detection reports requested URL, safe env-based extra headers work, query-scoped and batch semantic-edge jobs are callable across surfaces, local Ollama QA proves `gemma4:e4b` semantic edges plus prior `qwen3.5:4b` evidence, bounded provider backfill embedded `128` chunks in `17.703s`, full local temp-copy provider backfill covered `21884 / 21884` chunks with missing `0` in `2388.07s`, and query-time provider-vector wiring is proven with a local Ollama throwaway DB. Credentialed live OpenAI-compatible endpoint QA and ranking-quality evaluation remain explicit boundaries. | Final provider closure records either credentialed OpenAI-compatible live QA or an explicit user-approved local-compatible boundary, plus broader ranking-quality acceptance if kept in MVP. |
| G07 | [API And MCP Product Surfaces](2026-05-16-g07-api-mcp.md) | FastAPI, MCP, and Web BFF expose the product features, not only artifact listing. | Deterministic product-surface and real MCP runtime pass verified. Query/graph/listing, selected acceptance execution, corpus/resolver/provider control-plane slices, evidence/entity detail slices, deterministic structured resolved-chain explanations, semantic-edge generation parity, key read-route no-mutation coverage, FastAPI live HTTP smoke including `pnpm dev:api`, MCP server tool-matrix registration, Web/MCP query/evidence/entity/graph agreement, and bundled-Python real MCP runtime smoke now exist across FastAPI/MCP/Web BFF. | Preserve G07 evidence through G11; external client interoperability beyond FastMCP construction/tool execution remains future deployment QA. |
| G08 | [PDF And Document Ingestion](2026-05-16-g08-pdf-document-ingestion.md) | PDF/text docs are converted, page-aware, indexed, visible as cited evidence, and available as graph section nodes. | Current pass verified with a content-depth boundary. Reduced AMD amdgpu PDF is indexed in clean AMD SQLite evidence and AQ05 passes with `pdf`; fallback extraction handles ReportLab compressed streams; Markdown/doc section nodes, section edges, and clean-final API/browser proof for `amdgpu-driver-source-tree.pdf#page-1` as `kind=pdf_section` with page provenance are recorded. | Preserve G08 through G11; richer real AMD PDF content depth remains outside this slice unless a larger PDF corpus is added. |
| G09 | [SQLite FTS5 Vector And NetworkX Runtime](2026-05-16-g09-storage-vector-graph-runtime.md) | SQLite owns storage, FTS5/vector retrieval works, and NetworkX is the graph runtime. | Partial. FTS5, native sqlite-vec adapter, fallback vector retrieval, query-time provider-vector wiring, `vector_runtime`, and NetworkX are live. Native sqlite-vec extension and product `search_vector()` adapter are verified in the bundled Python runtime; system Python keeps the documented fallback. | Final query/graph artifacts report retrieval sources, `vector_runtime`, and `graph_runtime: networkx`; current-DB full provider-vector coverage and semantic ranking quality remain separate boundaries. |
| G10 | [Testing Acceptance And Visual QA](2026-05-16-g10-testing-acceptance-visual-qa.md) | Tests, acceptance queries, browser E2E, and visual-anchor QA prove the product. | Current clean-final acceptance and browser QA are recorded: DB health pass, AQ01-AQ09 9/9, CLI/API/Web/MCP labels, provider checks pass, Stage 2/doc-node/macro QA, latest in-app browser screenshots for global graph/function-node fallback/cross-repo register bridge, and a current six-route dark/light 2K visual pack. Final automated rerun is recorded: core 236 OK, API/MCP 47 OK, bundled MCP 29 OK, lint/tsc pass, visual routes 15 passed, combined Web 90 passed, and diff check passed. | Preserve this evidence through commit/push; rerun if UI or graph behavior changes again. |
| G11 | [Completion Gate And Documentation Review](2026-05-16-g11-completion-gate.md) | Nothing is claimed complete, committed, or pushed until docs, tests, QA, and git hygiene agree. | Final gate open. Current user-review blockers and latest design/visual audit are verified, but explicit residual-boundary acceptance and commit/push of the latest audit changes still remain. | Final review reconciles spec, gap docs, QA artifacts, tests, `git diff`, commit, push, and residual-boundary acceptance. |
| G12 | [ASIC And IP Metadata Filtering](2026-05-16-g12-asic-ip-metadata-filtering.md) | ASIC/IP filters affect retrieval and remain visible/stable in UI. | Current real AMD filter pass verified. Core/Web BFF/UI, FastAPI, and MCP filter plumbing exists; targeted RED/GREEN tests prove result-set changes on same-symbol evidence; clean-final QA proves `CP_INT_CNTL_RING0` filtered by `CP` and `SDMA` through API and browser. | Preserve evidence through G11; path/symbol heuristic inference limits remain the MVP boundary. |
| G13 | [MVP Boundary And Full-Spec Deferrals](2026-05-16-g13-mvp-boundary-deferrals.md) | Full-spec items outside MVP are explicitly deferred rather than silently omitted. | Blocking. Deferral ledger exists but must be checked before final completion. | Full technical spec is reviewed line-by-line against MVP, implemented gaps, and explicit deferrals. |
| G14 | [Static Data And Truthful Empty States](2026-05-16-g14-static-data-and-truthful-empty-states.md) | Static fixture/fallback data cannot mask real failures or pretend features are live. | Current pass verified with audit residual. Static default query/graph rows are removed from product paths, unused artifact query/graph helpers were deleted, package-backed live graph rendering is used, acceptance run details are expandable, row-only graph fallback no longer fabricates graph data, and query metrics no longer invent graph counts. | Complete final route-by-route truth audit before commit/push; do not reconnect old artifact query helpers. |
| G15 | [Performance Smoke And Deterministic Rebuild](2026-05-16-g15-performance-smoke-deterministic-rebuild.md) | Rebuild and query performance are measured, deterministic, and documented. | Current performance pass with explicit residuals. Fixture proof exists; AMD query-graph performance QA records more than five real queries; repeat real-corpus deterministic graph rebuild ran twice with stable counts; bounded provider backfill embedded `128` chunks in `17.703s`; full local temp-copy provider backfill covered `21884 / 21884` chunks in `2388.07s`; two empty-DB raw re-index runs completed in `506.75s` and `507.07s` with matching counts; edge-count summary/table counting is fixed. | Semantic ranking quality, local model latency, and hosted-provider throughput remain residuals. |
| G16 | [Workbench IA Theme And Visual Fidelity](2026-05-16-g16-workbench-ia-theme-visual-fidelity.md) | Next.js/shadcn workbench matches per-page visual anchors in light and dark themes. | Current pass verified. shadcn/Radix standard controls, package graph rendering, and light/dark route visual tests are recorded. | Rerun visual QA if more UI-affecting changes land before commit/push. |
| G17 | [Architecture Ownership And Process Shape](2026-05-16-g17-architecture-ownership-process-shape.md) | Core/API/MCP/Web boundaries, vector adapters, graph runtime, package-first policy, TDD, and subagent review are explicit. | Current pass recorded. Core owns graph enrichment and batch semantic-edge generation, including deterministic register operations, direct calls, exact callback calls, and generic dispatch-candidate edges; API/MCP/Web trigger thin jobs; Web owns graph package adapter/shadcn composition; subagent review found no P0 and several residuals were fixed. | Carry this architecture evidence through final G11 review and document any accepted deferrals, especially full clangd/libclang callback type-flow and native sqlite-vec retrieval. |
| AQ | [MVP Acceptance Query Matrix](2026-05-16-mvp-acceptance-query-matrix.md) | Query-level closure for AQ01-AQ09. | Partial/blocking support matrix. Current clean AMD artifact records AQ01-AQ09 9/9 with healthy DB path, CLI/API/Web/MCP labels, source diversity, graph counts, and provider checks. | Final G10/G11 review must link this artifact with screenshots, full-suite results, timing, architecture/design review, and stale-doc reconciliation. |

## Support Gate Documents

| Document | Purpose | Closure relationship |
| --- | --- | --- |
| [Final Clean Evidence Package Gate](2026-05-17-final-clean-evidence-package.md) | Lists the exact final QA package fields for clean DB, source roots, AQ, free queries, graph, provider, API/Web/MCP, visual QA, performance, architecture, commit, and push. | No gap is finally closed unless its evidence appears in that package or is explicitly accepted as deferred by the user. |

## Latest User Complaint Mapping

| User-visible problem | Owning gaps | Required next action |
| --- | --- | --- |
| "I cannot freely run queries." | G02, G10, G14, AQ01-AQ09 | Six clean AMD free-form queries and browser/API tests now prove live SQLite-backed query behavior; G11 keeps final evidence packaging and residual rerank/provider-vector boundaries explicit. |
| "The graph still does not look complete/global." | G03, G08, G09, G16 | Package-backed global graph, function/register/doc node classes, conservative callback/common call edges, and layer provenance are implemented and QA-recorded; G11 preserves evidence and G09 still tracks native vector adapter, not graph rendering. |
| "It still feels hardcoded/static." | G14, G02, G03, G04, G05, G06, G07 | Product paths now use live data, explicit empty states, or explicit errors; final route audit remains in G11/G14. |
| "Corpus cannot really be added/indexed from the UI." | G04, G07, G10 | Real Web add-index-query loop, durable job-state UX, clean named DB BFF proof, and graph/inspector evidence from the newly indexed corpus are recorded; G11 preserves the evidence and non-MVP orchestration boundaries. |
| "Resolver profiles cannot be freely configured." | G05, G07, AQ07, AQ08 | YAML-backed rows, validation, edit/load, and non-macro Python profile proof exist; richer per-job resolver selection remains G05 residual. |
| "Edge and embedding provider settings may have different base URLs and need auto-detection." | G06, G07, AQ09 | Split provider settings, Ollama detection, AQ09 execution, semantic-edge triggers, and safe env-based extra headers are implemented; credentialed live OpenAI-compatible QA remains G06 residual. |
| "Acceptance should run for real from the repo, not list stale artifacts." | G07, G10, G11, AQ | Acceptance execution API/UI paths and current clean artifacts exist; G11 owns final package consistency. |
| "Every page needs visual anchor QA in light and dark themes." | G16, G10 | Page-by-page 2K light/dark route QA is recorded; rerun only if UI-affecting changes land. |
| "Do not hand-roll components; use React/npm packages first." | G03, G16, G17 | `/graph` uses `react-force-graph-2d`, and standard UI controls use shadcn/Radix wrappers; remaining custom code is ASIP-specific layout/adapter logic. |
| "Acceptance failures are unclear and cannot expand." | G10, G14, G16 | Full acceptance details are preserved and expandable in API/UI. |
| "Should functions and docs connect the graph?" | G03, G08, G17 | Core-owned function operation edges, direct/helper callback calls, document/PDF section nodes, and doc boxes are implemented and rendered. |
| "Do we batch-generate potential semantic edges with an LLM?" | G03, G06, G17 | Batch semantic-edge pipeline over indexed candidates is implemented across core/CLI/Web/API/MCP with provider settings and job provenance. |

## Historical Implementation Order From This Register

The sequence below is preserved as the pre-code order that guided the
implementation. Current completion review should use the G01-G17 table above,
`docs/gaps/README.md`, `docs/qa/2026-05-17-final-clean-evidence-package.md`,
and `docs/qa/2026-05-18-design-review-closure-matrix.md`.

The next code pass should close gaps in this order because later proof depends
on earlier surfaces:

1. G03/G06/G08/G16/G17: finish the maintained graph package for `/graph`, add function/document graph layers, and add batch semantic-edge generation; remove hand-written SVG graph assumptions from tests.
2. G14/G10/G16: remove/demote remaining static product data and add expandable acceptance failure/detail UI.
3. G05/G04/G06/G07: finish truthful control-plane UI for resolver YAML profiles, corpus/index jobs, provider settings, and API/MCP surfaces.
4. G02/G03/AQ: reconcile clean AMD AQ01-AQ09 and free-form query records with browser graph/inspector evidence.
5. G01/G08/G09/G12/G15: finish product-surface citation, vector/runtime boundary, and performance proof beyond fixture smoke and current clean AMD counts/timings.
6. G16/G10/G11/G17: rerun visual QA, final architecture/design/documentation review, git hygiene, commit, and push.

## Historical No-Code Gate

This register intentionally does not claim completion. It is a pre-code gate.
The next implementation step must:

- name the gap ID it closes,
- write the failing test first,
- implement the smallest product change that makes that test pass,
- rerun the relevant checks,
- update the same gap document with exact evidence,
- keep the active goal open until G01-G17 and AQ closure are genuinely verified
  or explicitly deferred by the user.
