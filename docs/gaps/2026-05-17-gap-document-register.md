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
| G01 | [Real Ingestion And Indexing](2026-05-16-g01-real-ingestion-indexing.md) | Index real AMD code, docs, register headers, and PDF/text docs from raw inputs. | Partial. Clean AMD DB `/tmp/asip-clean-amd-qwen35-provider-2026-05-17.db` now has `documents=124`, `chunks=21884`, `evidence=860543`, source counts `code/doc/pdf/register`, and AQ01-AQ09 9/9. | Browser/API citation QA, performance/determinism review, and final completion gate must verify this DB through product surfaces. |
| G02 | [Live Retrieval And Evidence Schema](2026-05-16-g02-live-retrieval-evidence-schema.md) | Free-form hybrid retrieval with evidence schema, snippets, resolved chains, graph seeds, and truthful no-match behavior. | Partial. Clean AMD AQ01-AQ09 is 9/9, six real free-form queries are recorded, schema/no-match/live inspector tests exist, and source diversity is now proven in CLI/core artifacts. Rerank/provider-vector semantics and final route/visual closure remain incomplete. | Browser QA must prove user-entered queries, rows, graph, and inspector update from the same clean DB payload. |
| G03 | [Dynamic Weighted Graph](2026-05-16-g03-dynamic-weighted-graph.md) | Obsidian-style global graph and query-scoped graph rendered from weighted stored relationships. | Current pass verified. NetworkX-backed graph data includes persisted/evidence edges, function operation edges, document section nodes, and batch semantic edges; `/graph` uses `react-force-graph-2d`. | Preserve current QA evidence through final G11 review; rerun visual tests if UI changes again. |
| G04 | [Corpus Management](2026-05-16-g04-corpus-management.md) | Users can add/select/index corpora without editing code. | Partial. Backend/API/MCP add/list/index paths exist; UI selected-corpus indexing, invalid-source/zero-doc false-success prevention, and a real Web add-index-query loop are proven. Clean-DB final closure and durable job state remain open. | Repeat add-index-query against a clean DB/corpus, then prove inspector/graph evidence and durable queued/indexing/failed job state. |
| G05 | [Resolver Profiles](2026-05-16-g05-resolver-profiles.md) | Resolver profiles are configurable per repo/language and are not macro-only. | Partial. YAML configs, backend/API/MCP add/list/validate, UI validation, disabled status, and minimal changed-extraction proof exist; UI must not show resolver rows without real YAML config. | Workflow edits or selects a wrapper/profile, re-indexes, and proves changed evidence without resolver code edits; every listed resolver maps to an existing YAML config; richer Linux/MxGPU/Python semantics are implemented or explicitly bounded. |
| G06 | [Provider Settings And Ollama Detection](2026-05-16-g06-provider-settings-ollama.md) | Edge and embedding providers are independently configurable, Ollama can be detected, OpenAI-compatible formats work, and semantic-edge jobs can run query-scoped or batch corpus generation. | Current local/batch pass verified. Settings persist across Web/API/MCP, Ollama detection reports requested URL, Settings status no longer claims verified until checks pass, query-scoped and batch semantic-edge jobs are callable from core/CLI/Web BFF/FastAPI/MCP, and local Ollama QA proves `gemma4:e4b` batch edges plus prior `qwen3.5:4b`/`nomic-embed-text` evidence. Query reranking and credentialed/safe OpenAI-compatible secret/header handling remain explicit boundaries. | Final provider closure records accepted OpenAI-compatible credential/secret handling or an explicit user-approved local-compatible boundary, plus query-time provider/rerank behavior if kept in MVP. |
| G07 | [API And MCP Product Surfaces](2026-05-16-g07-api-mcp.md) | FastAPI, MCP, and Web BFF expose the product features, not only artifact listing. | Partial. Query/graph/listing, selected acceptance execution, corpus/resolver/provider control-plane slices, evidence/entity detail slices, semantic-edge generation parity, key read-route no-mutation coverage, FastAPI live HTTP smoke including `pnpm dev:api`, MCP server tool-matrix registration, and Web/MCP query/evidence/entity agreement now exist across FastAPI/MCP/Web BFF. Richer resolved-chain UX and optional real MCP runtime smoke remain incomplete. | Final review with tests for query, graph, semantic-edge generation, corpus, index jobs, provider status, resolver validation, entity/evidence detail, acceptance execution, real MCP runtime smoke when available, and read-only mutation boundaries. |
| G08 | [PDF And Document Ingestion](2026-05-16-g08-pdf-document-ingestion.md) | PDF/text docs are converted, page-aware, indexed, visible as cited evidence, and available as graph section nodes. | Partial with narrowed residual. Reduced AMD amdgpu PDF is indexed in clean AMD SQLite evidence and AQ05 passes with `pdf`; fallback extraction handles ReportLab compressed streams; Markdown/doc section nodes and section edges are proven. | UI/API/browser evidence must still isolate a real PDF-derived `pdf_section` node with page provenance, or explicitly accept Markdown/doc section proof plus PDF evidence as the MVP boundary. |
| G09 | [SQLite FTS5 Vector And NetworkX Runtime](2026-05-16-g09-storage-vector-graph-runtime.md) | SQLite owns storage, FTS5/vector retrieval works, and NetworkX is the graph runtime. | Partial. FTS5/fallback vector/NetworkX are live; native sqlite-vec remains skipped or needs explicit deferral. | Native sqlite-vec verification or accepted fallback boundary; final query/graph artifacts report retrieval sources and `graph_runtime: networkx`. |
| G10 | [Testing Acceptance And Visual QA](2026-05-16-g10-testing-acceptance-visual-qa.md) | Tests, acceptance queries, browser E2E, and visual-anchor QA prove the product. | Current pass verified. Expandable acceptance details, package-backed graph rendering/nonblank interaction, full Web/API/MCP/core suites, build/lint/tsc/diff, and fresh visual route QA are recorded. | Preserve evidence through G11; rerun if more UI-affecting changes land. |
| G11 | [Completion Gate And Documentation Review](2026-05-16-g11-completion-gate.md) | Nothing is claimed complete, committed, or pushed until docs, tests, QA, and git hygiene agree. | Final gate open. Current user-review blocker pass is verified, but commit/push and generated artifact hygiene still remain. | Final review reconciles spec, gap docs, QA artifacts, tests, `git diff`, commit, and push. |
| G12 | [ASIC And IP Metadata Filtering](2026-05-16-g12-asic-ip-metadata-filtering.md) | ASIC/IP filters affect retrieval and remain visible/stable in UI. | Partial. Core/API/UI filter plumbing exists; final real AMD filtered acceptance is open. | Real AMD filtered queries prove result-set changes and stable layout in browser QA. |
| G13 | [MVP Boundary And Full-Spec Deferrals](2026-05-16-g13-mvp-boundary-deferrals.md) | Full-spec items outside MVP are explicitly deferred rather than silently omitted. | Blocking. Deferral ledger exists but must be checked before final completion. | Full technical spec is reviewed line-by-line against MVP, implemented gaps, and explicit deferrals. |
| G14 | [Static Data And Truthful Empty States](2026-05-16-g14-static-data-and-truthful-empty-states.md) | Static fixture/fallback data cannot mask real failures or pretend features are live. | Current pass verified with audit residual. Static default query/graph rows are removed from product paths, unused artifact query/graph helpers were deleted, package-backed live graph rendering is used, and acceptance run details are expandable. | Complete final route-by-route truth audit before commit/push; do not reconnect old artifact query helpers. |
| G15 | [Performance Smoke And Deterministic Rebuild](2026-05-16-g15-performance-smoke-deterministic-rebuild.md) | Rebuild and query performance are measured, deterministic, and documented. | Blocking. Correctness evidence exists, but timing/rebuild proof is incomplete. | Fixture rebuild determinism, first real-corpus indexing timing, query latency, and provider timing are recorded. |
| G16 | [Workbench IA Theme And Visual Fidelity](2026-05-16-g16-workbench-ia-theme-visual-fidelity.md) | Next.js/shadcn workbench matches per-page visual anchors in light and dark themes. | Current pass verified. shadcn/Radix standard controls, package graph rendering, and light/dark route visual tests are recorded. | Rerun visual QA if more UI-affecting changes land before commit/push. |
| G17 | [Architecture Ownership And Process Shape](2026-05-16-g17-architecture-ownership-process-shape.md) | Core/API/MCP/Web boundaries, vector adapters, graph runtime, package-first policy, TDD, and subagent review are explicit. | Current pass recorded. Core owns graph enrichment and batch semantic-edge generation; API/MCP/Web trigger thin jobs; Web owns graph package adapter/shadcn composition; subagent review found no P0 and several residuals were fixed. | Carry this architecture evidence through final G11 review and document any accepted deferrals. |
| AQ | [MVP Acceptance Query Matrix](2026-05-16-mvp-acceptance-query-matrix.md) | Query-level closure for AQ01-AQ09. | Partial/blocking support matrix. Current clean AMD artifact records AQ01-AQ09 9/9 with healthy DB path, CLI/API/Web/MCP labels, source diversity, graph counts, and provider checks. | Final G10/G11 review must link this artifact with screenshots, full-suite results, timing, architecture/design review, and stale-doc reconciliation. |

## Support Gate Documents

| Document | Purpose | Closure relationship |
| --- | --- | --- |
| [Final Clean Evidence Package Gate](2026-05-17-final-clean-evidence-package.md) | Lists the exact final QA package fields for clean DB, source roots, AQ, free queries, graph, provider, API/Web/MCP, visual QA, performance, architecture, commit, and push. | No gap is finally closed unless its evidence appears in that package or is explicitly accepted as deferred by the user. |

## Latest User Complaint Mapping

| User-visible problem | Owning gaps | Required next action |
| --- | --- | --- |
| "I cannot freely run queries." | G02, G10, G14, AQ01-AQ09 | Six clean AMD free-form queries now prove non-empty SQLite-backed rows and NetworkX graph payloads; browser QA still must prove the visible UI path. |
| "The graph still does not look complete/global." | G03, G08, G09, G16 | Live no-seed NetworkX data exists, but the renderer is rejected and the graph must include function-operation and document-section layers, not only a small register relation sample. Replace the hand-written SVG with a package-backed graph, enrich graph data, and rerun browser/visual QA. |
| "It still feels hardcoded/static." | G14, G02, G03, G04, G05, G06, G07 | Remove or demote fallback data from product paths; every route must show live data, explicit empty state, or explicit error. |
| "Corpus cannot really be added/indexed from the UI." | G04, G07, G10 | E2E add/index/query workflow against a clean DB. |
| "Resolver profiles cannot be freely configured." | G05, G07, AQ07, AQ08 | UI/API edit/validate/toggle/re-index path with wrapper change and non-macro toy Python profile proof. |
| "Edge and embedding provider settings may have different base URLs and need auto-detection." | G06, G07, AQ09 | Split provider status/actions and acceptance execution for edge and embedding settings, including Ollama tags and OpenAI-compatible settings. |
| "Acceptance should run for real from the repo, not list stale artifacts." | G07, G10, G11, AQ | Add acceptance execution API/Web control, then record current artifacts from a clean DB. |
| "Every page needs visual anchor QA in light and dark themes." | G16, G10 | Previous page-by-page 2K dark/light captures are stale after the graph/UI review; recapture after package-backed graph and shadcn-native UI changes. |
| "Do not hand-roll components; use React/npm packages first." | G03, G16, G17 | Select package-backed graph renderer, use shadcn-native primitives for standard UI, document any custom component exceptions. |
| "Acceptance failures are unclear and cannot expand." | G10, G14, G16 | Preserve full `asip.acceptance` details in the API/UI and render fail/partial runs with expandable shadcn details. |
| "Should functions and docs connect the graph?" | G03, G08, G17 | Add core-owned function operation edges and document/PDF section nodes, then verify Web renders mixed node kinds. |
| "Do we batch-generate potential semantic edges with an LLM?" | G03, G06, G17 | Add a batch semantic-edge pipeline over indexed candidates with provider settings, job provenance, failure evidence, and graph refresh. |

## Implementation Order After This Register

The next code pass should close gaps in this order because later proof depends
on earlier surfaces:

1. G03/G06/G08/G16/G17: finish the maintained graph package for `/graph`, add function/document graph layers, and add batch semantic-edge generation; remove hand-written SVG graph assumptions from tests.
2. G14/G10/G16: remove/demote remaining static product data and add expandable acceptance failure/detail UI.
3. G05/G04/G06/G07: finish truthful control-plane UI for resolver YAML profiles, corpus/index jobs, provider settings, and API/MCP surfaces.
4. G02/G03/AQ: reconcile clean AMD AQ01-AQ09 and free-form query records with browser graph/inspector evidence.
5. G01/G08/G09/G12/G15: finish product-surface citation, vector/runtime boundary, and performance proof beyond current clean AMD counts/timings.
6. G16/G10/G11/G17: rerun visual QA, final architecture/design/documentation review, git hygiene, commit, and push.

## No-Code Gate

This register intentionally does not claim completion. It is a pre-code gate.
The next implementation step must:

- name the gap ID it closes,
- write the failing test first,
- implement the smallest product change that makes that test pass,
- rerun the relevant checks,
- update the same gap document with exact evidence,
- keep the active goal open until G01-G17 and AQ closure are genuinely verified
  or explicitly deferred by the user.
