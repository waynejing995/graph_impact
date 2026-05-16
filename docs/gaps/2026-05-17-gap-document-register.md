# Gap Document Register Before Code

Date: 2026-05-17
Status: Docs-only rolling gate before further implementation

## Purpose

This is the register to read before writing more product code. It is a rolling
status gate, not a frozen historical baseline. It lists every
active gap document, what product promise it owns, the current truth, and the
next proof required before that gap can close.

No functional code should be written from this point forward unless the change
names one of these gap IDs, starts with a failing test, and updates the same gap
document with verification evidence.

## Complete Gap Document Set

| ID | Document | Product promise owned | Current truth | Next proof before closure |
| --- | --- | --- | --- | --- |
| G01 | [Real Ingestion And Indexing](2026-05-16-g01-real-ingestion-indexing.md) | Index real AMD code, docs, register headers, and PDF/text docs from raw inputs. | Partial. Clean AMD DB `/tmp/asip-clean-amd-qwen35-provider-2026-05-17.db` now has `documents=124`, `chunks=21884`, `evidence=860543`, source counts `code/doc/pdf/register`, and AQ01-AQ09 9/9. | Browser/API citation QA, performance/determinism review, and final completion gate must verify this DB through product surfaces. |
| G02 | [Live Retrieval And Evidence Schema](2026-05-16-g02-live-retrieval-evidence-schema.md) | Free-form hybrid retrieval with evidence schema, snippets, resolved chains, graph seeds, and truthful no-match behavior. | Partial. Clean AMD AQ01-AQ09 is 9/9, six real free-form queries are recorded, schema/no-match/live inspector tests exist, and source diversity is now proven in CLI/core artifacts. Rerank/provider-vector semantics and final route/visual closure remain incomplete. | Browser QA must prove user-entered queries, rows, graph, and inspector update from the same clean DB payload. |
| G03 | [Dynamic Weighted Graph](2026-05-16-g03-dynamic-weighted-graph.md) | Obsidian-style global graph and query-scoped graph rendered from weighted stored relationships. | Partial. NetworkX-backed API paths and query graph/table/inspector linkage exist; final clean-corpus graph QA is open. | `/graph` loads no-seed global graph from API; query graph changes with query; browser QA confirms weights and labels are visible. |
| G04 | [Corpus Management](2026-05-16-g04-corpus-management.md) | Users can add/select/index corpora without editing code. | Partial. Backend/API/MCP add/list/index paths exist; UI selected-corpus indexing, invalid-source/zero-doc false-success prevention, and a real Web add-index-query loop are proven. Clean-DB final closure and durable job state remain open. | Repeat add-index-query against a clean DB/corpus, then prove inspector/graph evidence and durable queued/indexing/failed job state. |
| G05 | [Resolver Profiles](2026-05-16-g05-resolver-profiles.md) | Resolver profiles are configurable per repo/language and are not macro-only. | Partial. YAML configs, backend/API/MCP add/list/validate, UI validation, disabled status, and minimal changed-extraction proof exist; edit-in-place/per-job selection and richer extraction semantics remain open. | Workflow edits or selects a wrapper/profile, re-indexes, and proves changed evidence without resolver code edits; richer Linux/MxGPU/Python semantics are implemented or explicitly bounded. |
| G06 | [Provider Settings And Ollama Detection](2026-05-16-g06-provider-settings-ollama.md) | Edge and embedding providers are independently configurable, Ollama can be detected, and OpenAI-compatible formats work. | Partial. Settings persist across Web/API/MCP, Ollama detection reports requested URL, Settings status no longer claims verified until checks pass, semantic-edge jobs are callable from core/CLI/Web BFF, and clean DB local Ollama QA proves `qwen3.5:4b` semantic edges plus `nomic-embed-text:latest` embeddings with fallback metadata. Query reranking and credentialed/safe OpenAI-compatible secret/header handling remain open. | Final provider closure records accepted OpenAI-compatible credential/secret handling or an explicit user-approved local-compatible boundary, plus query-time provider/rerank behavior if kept in MVP. |
| G07 | [API And MCP Product Surfaces](2026-05-16-g07-api-mcp.md) | FastAPI, MCP, and Web BFF expose the product features, not only artifact listing. | Partial. Query/graph/listing, selected acceptance execution, corpus/resolver/provider control-plane slices, evidence/entity detail slices, semantic-edge generation parity, key read-route no-mutation coverage, FastAPI live HTTP smoke including `pnpm dev:api`, MCP server tool-matrix registration, and Web/MCP query/evidence/entity agreement now exist across FastAPI/MCP/Web BFF. Richer resolved-chain UX and optional real MCP runtime smoke remain incomplete. | Final review with tests for query, graph, semantic-edge generation, corpus, index jobs, provider status, resolver validation, entity/evidence detail, acceptance execution, real MCP runtime smoke when available, and read-only mutation boundaries. |
| G08 | [PDF And Document Ingestion](2026-05-16-g08-pdf-document-ingestion.md) | PDF/text docs are converted, page-aware, indexed, and visible as cited evidence. | Partial. Reduced AMD amdgpu PDF is indexed in clean AMD SQLite evidence and AQ05 passes with `pdf`; fallback extraction now handles ReportLab compressed streams. | UI/API/browser evidence must show PDF source/page metadata to the user. |
| G09 | [SQLite FTS5 Vector And NetworkX Runtime](2026-05-16-g09-storage-vector-graph-runtime.md) | SQLite owns storage, FTS5/vector retrieval works, and NetworkX is the graph runtime. | Partial. FTS5/fallback vector/NetworkX are live; native sqlite-vec remains skipped or needs explicit deferral. | Native sqlite-vec verification or accepted fallback boundary; final query/graph artifacts report retrieval sources and `graph_runtime: networkx`. |
| G10 | [Testing Acceptance And Visual QA](2026-05-16-g10-testing-acceptance-visual-qa.md) | Tests, acceptance queries, browser E2E, and visual-anchor QA prove the product. | Partial/blocking. Clean AMD AQ01-AQ09 is 9/9, six free-form queries plus two semantic-edge jobs are recorded, full automated checks pass, and 2K visual QA is 6/6. | Final design/spec review and git gate must reconcile all evidence before completion. |
| G11 | [Completion Gate And Documentation Review](2026-05-16-g11-completion-gate.md) | Nothing is claimed complete, committed, or pushed until docs, tests, QA, and git hygiene agree. | Blocking. Active goal is not complete. | Final review reconciles spec, gap docs, QA artifacts, tests, `git diff`, commit, and push. |
| G12 | [ASIC And IP Metadata Filtering](2026-05-16-g12-asic-ip-metadata-filtering.md) | ASIC/IP filters affect retrieval and remain visible/stable in UI. | Partial. Core/API/UI filter plumbing exists; final real AMD filtered acceptance is open. | Real AMD filtered queries prove result-set changes and stable layout in browser QA. |
| G13 | [MVP Boundary And Full-Spec Deferrals](2026-05-16-g13-mvp-boundary-deferrals.md) | Full-spec items outside MVP are explicitly deferred rather than silently omitted. | Blocking. Deferral ledger exists but must be checked before final completion. | Full technical spec is reviewed line-by-line against MVP, implemented gaps, and explicit deferrals. |
| G14 | [Static Data And Truthful Empty States](2026-05-16-g14-static-data-and-truthful-empty-states.md) | Static fixture/fallback data cannot mask real failures or pretend features are live. | Partial. Query/graph error paths, initial live query, stale query response suppression, row-only graph fallback, live inspector linkage, acceptance failure, empty corpus/resolver responses, graph relationship-panel data, provider hydration race, Web BFF query/graph no-mutation, MCP/FastAPI no-auto-index read behavior, and status/list no-migration behavior are covered. Remaining blockers are live server smoke and any route-specific demo/fallback states not yet audited. | Route-by-route audit proves query, graph, corpus, resolver, provider, acceptance, and inspector states are either live or explicitly marked as fallback/demo, and read routes do not mutate state unless accepted. |
| G15 | [Performance Smoke And Deterministic Rebuild](2026-05-16-g15-performance-smoke-deterministic-rebuild.md) | Rebuild and query performance are measured, deterministic, and documented. | Blocking. Correctness evidence exists, but timing/rebuild proof is incomplete. | Fixture rebuild determinism, first real-corpus indexing timing, query latency, and provider timing are recorded. |
| G16 | [Workbench IA Theme And Visual Fidelity](2026-05-16-g16-workbench-ia-theme-visual-fidelity.md) | Next.js/shadcn workbench matches per-page visual anchors in light and dark themes. | Partial/blocking. Current visual QA captures six routes in light/dark at 2K with 6/6 pass and visible weighted `/graph` edges. | Final design-review checklist remains before completion; recapture if more UI-affecting changes land. |
| G17 | [Architecture Ownership And Process Shape](2026-05-16-g17-architecture-ownership-process-shape.md) | Core/API/MCP/Web boundaries, vector adapters, graph runtime, TDD, and subagent review are explicit. | Blocking. Boundaries exist in code but still need review against the design and process promises. | Architecture review names ownership for each surface and records TDD/subagent evidence before completion. |
| AQ | [MVP Acceptance Query Matrix](2026-05-16-mvp-acceptance-query-matrix.md) | Query-level closure for AQ01-AQ09. | Partial/blocking support matrix. Current clean AMD artifact records AQ01-AQ09 9/9 with healthy DB path, CLI/API/Web/MCP labels, source diversity, graph counts, and provider checks. | Final G10/G11 review must link this artifact with screenshots, full-suite results, timing, architecture/design review, and stale-doc reconciliation. |

## Support Gate Documents

| Document | Purpose | Closure relationship |
| --- | --- | --- |
| [Final Clean Evidence Package Gate](2026-05-17-final-clean-evidence-package.md) | Lists the exact final QA package fields for clean DB, source roots, AQ, free queries, graph, provider, API/Web/MCP, visual QA, performance, architecture, commit, and push. | No gap is finally closed unless its evidence appears in that package or is explicitly accepted as deferred by the user. |

## Latest User Complaint Mapping

| User-visible problem | Owning gaps | Required next action |
| --- | --- | --- |
| "I cannot freely run queries." | G02, G10, G14, AQ01-AQ09 | Six clean AMD free-form queries now prove non-empty SQLite-backed rows and NetworkX graph payloads; browser QA still must prove the visible UI path. |
| "The graph still does not look complete/global." | G03, G09, G16 | Current tests and visual QA prove no-seed global NetworkX data and visible weighted connections; final design review remains. |
| "It still feels hardcoded/static." | G14, G02, G03, G04, G05, G06, G07 | Remove or demote fallback data from product paths; every route must show live data, explicit empty state, or explicit error. |
| "Corpus cannot really be added/indexed from the UI." | G04, G07, G10 | E2E add/index/query workflow against a clean DB. |
| "Resolver profiles cannot be freely configured." | G05, G07, AQ07, AQ08 | UI/API edit/validate/toggle/re-index path with wrapper change and non-macro toy Python profile proof. |
| "Edge and embedding provider settings may have different base URLs and need auto-detection." | G06, G07, AQ09 | Split provider status/actions and acceptance execution for edge and embedding settings, including Ollama tags and OpenAI-compatible settings. |
| "Acceptance should run for real from the repo, not list stale artifacts." | G07, G10, G11, AQ | Add acceptance execution API/Web control, then record current artifacts from a clean DB. |
| "Every page needs visual anchor QA in light and dark themes." | G16, G10 | Current visual QA re-ran page-by-page 2K dark/light captures for six routes with 6/6 pass; recapture if more UI changes land. |

## Implementation Order After This Register

The next code pass should close gaps in this order because later proof depends
on earlier surfaces:

1. G14/G07: finish the remaining truthfulness and surface-policy review, especially optional real MCP runtime smoke and any remaining fallback/demo states.
2. G02/G03/AQ: reconcile the clean AMD AQ01-AQ09 artifact and six free-form query records with browser graph/inspector evidence.
3. G04/G05/G06: finish or explicitly bound the user-facing control plane for corpus, resolver profiles, provider settings, and OpenAI-compatible secrets.
4. G01/G08/G09/G12/G15: finish product-surface citation, vector/runtime boundary, and performance proof beyond the current clean AMD counts/timings.
5. G16/G10/G11/G17: final architecture/design/documentation review, git hygiene, commit, and push.

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
