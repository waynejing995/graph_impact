# Gap Inventory Before Code

Date: 2026-05-17
Status: Blocking inventory before more product code

## Purpose

This file is the first-stop checklist before any more implementation work. It is a rolling status inventory, not a frozen historical baseline. It lists every current gap document, the truth status, and the evidence that must exist before the active goal can be called complete.

For the complete product-promise register and user-visible complaint mapping,
read [Gap Document Register Before Code](2026-05-17-gap-document-register.md)
first. This inventory is the compact checklist; the register is the execution
map.

Rule for the next implementation pass: pick one gap ID, write the failing test first, make the smallest code change to close that test, then update that same gap document with verification evidence.

## Current Count

- Gap documents listed here: 22 Markdown files in `docs/gaps`.
- Product gap IDs: G01-G17, plus the AQ support matrix.
- Closed gaps: 0.
- Partial but still blocking: G01-G09, G12, G14, AQ.
- Blocking gates: G10, G11, G13, G15, G16, G17.
- Support/index documents: README, gap register, compact inventory, final clean evidence package gate.

## Inventory

| ID | Document | Status | Next proof before closure |
| --- | --- | --- | --- |
| G01 | [Real Ingestion And Indexing](2026-05-16-g01-real-ingestion-indexing.md) | Partial; blocking | Clean AMD DB `/tmp/asip-clean-amd-qwen35-provider-2026-05-17.db` now proves code/doc/pdf/register counts from raw AMD roots and reduced AMD PDF; browser/product-surface proof and final full-suite gate remain open. |
| G02 | [Live Retrieval And Evidence Schema](2026-05-16-g02-live-retrieval-evidence-schema.md) | Partial; blocking | Live inspector linkage and clean AQ runner mechanics are proven; rerank/source-diversity/final route evidence remains open. |
| G03 | [Dynamic Weighted Graph](2026-05-16-g03-dynamic-weighted-graph.md) | Partial; blocking | Clean free-query QA and browser visual QA now show NetworkX global/query graphs and visible weighted `/graph` edges; final design/spec review remains open. |
| G04 | [Corpus Management](2026-05-16-g04-corpus-management.md) | Partial; blocking | Selected UI indexing, invalid-source/zero-doc false-success prevention, and a real Web add-index-query loop are proven; final proof must repeat against a clean DB and show durable queued/indexing/failed/succeeded job state plus inspector/graph evidence. |
| G05 | [Resolver Profiles](2026-05-16-g05-resolver-profiles.md) | Partial; blocking | UI validation and enabled/disabled creation are proven; edit-in-place/per-job selection plus changed extraction without resolver code edits still need final proof. |
| G06 | [Provider Settings And Ollama Detection](2026-05-16-g06-provider-settings-ollama.md) | Partial; blocking | Local Ollama settings now drive clean-DB embeddings and qwen3.5 semantic-edge jobs with provenance; OpenAI-compatible credential/secret handling and query-time rerank behavior remain open or need explicit boundary. |
| G07 | [API And MCP Product Surfaces](2026-05-16-g07-api-mcp.md) | Partial; blocking | API/MCP expose corpus, index jobs, provider status, evidence/entity detail, resolver validation, acceptance execution, semantic-edge generation, key read-route no-mutation/status-list no-migration behavior, FastAPI live HTTP smoke including `pnpm dev:api`, MCP server tool-matrix registration, and Web/MCP query/evidence/entity agreement; optional real MCP runtime smoke remains open. |
| G08 | [PDF And Document Ingestion](2026-05-16-g08-pdf-document-ingestion.md) | Partial; blocking | Reduced AMD amdgpu PDF is indexed in the clean AMD DB (`documents.pdf=1`, `evidence.pdf=5`) and AQ05 passes with `pdf`; final browser/API page-citation QA remains open. |
| G09 | [SQLite FTS5 Vector And NetworkX Runtime](2026-05-16-g09-storage-vector-graph-runtime.md) | Partial; blocking/deferred | Native sqlite-vec is verified or the fallback adapter boundary is explicitly accepted; NetworkX graph runtime is proven in final QA. |
| G10 | [Testing Acceptance And Visual QA](2026-05-16-g10-testing-acceptance-visual-qa.md) | Partial; blocking | Clean AMD AQ01-AQ09 passes 9/9, six free-form queries are recorded, full core/API/MCP/Web/TypeScript checks pass, and 2K visual QA is 6/6; final design/spec and git gates remain. |
| G11 | [Completion Gate And Documentation Review](2026-05-16-g11-completion-gate.md) | Blocking | Design docs, gap docs, QA docs, git diff, tests, commit, and push are reviewed in one final completion gate. |
| G12 | [ASIC And IP Metadata Filtering](2026-05-16-g12-asic-ip-metadata-filtering.md) | Partial; blocking | Real AMD filtered queries prove IP/ASIC filters affect result sets and UI layout remains stable. |
| G13 | [MVP Boundary And Full-Spec Deferrals](2026-05-16-g13-mvp-boundary-deferrals.md) | Blocking | Full-spec non-MVP features are mapped to explicit deferrals instead of silent omissions. |
| G14 | [Static Data And Truthful Empty States](2026-05-16-g14-static-data-and-truthful-empty-states.md) | Partial; blocking | Query/graph, live inspector, acceptance failure, empty corpus/resolver, graph relationship-panel, provider hydration race, Web BFF query/graph no-mutation, MCP/FastAPI no-auto-index, and status/list no-migration coverage exists; live server smoke and remaining fallback/demo-state audit still need closure. |
| G15 | [Performance Smoke And Deterministic Rebuild](2026-05-16-g15-performance-smoke-deterministic-rebuild.md) | Blocking | Fixture rebuild determinism, query latency, and first real-corpus timing are recorded. |
| G16 | [Workbench IA Theme And Visual Fidelity](2026-05-16-g16-workbench-ia-theme-visual-fidelity.md) | Partial; blocking | Current visual QA captures all six routes in dark/light at 2048x1280 with 6/6 pass and `/graph` nodes/edges visible; final design-review checklist remains. |
| G17 | [Architecture Ownership And Process Shape](2026-05-16-g17-architecture-ownership-process-shape.md) | Blocking | Core/API/MCP/Web ownership, adapter boundaries, NetworkX role, TDD evidence, and subagent review are checked before completion. |
| AQ | [MVP Acceptance Query Matrix](2026-05-16-mvp-acceptance-query-matrix.md) | Partial; blocking support matrix | Current clean AMD artifact records AQ01-AQ09 9/9 with DB health pass, source diversity, provider checks, and CLI/API/Web/MCP labels; final G10/G11 closure still needs screenshots, full-suite timing, architecture/design review, and stale-doc reconciliation. |

## Support Gates

| Document | Role | Required use |
| --- | --- | --- |
| [Final Clean Evidence Package Gate](2026-05-17-final-clean-evidence-package.md) | Defines the final QA package required before completion. | Every G01-G17 closure claim must link to this package or explicitly explain a user-accepted deferral. |

## Audit Findings To Preserve

- P0: The historical clean provider AQ artifact proves provider plumbing, not cross-source retrieval. Current source-gated rerun is 0/9 and correctly exposes DB health failures plus missing PDF on AQ05.
- P0: G01 and G08 now have clean DB counts and PDF evidence; they remain blocked on UI/API/browser citation QA and final completion gate review.
- P0: The multisource fixture artifact proves the source-diversity path on a synthetic corpus only; it must not be promoted to real AMD closure.
- P0: G16 now has fresh visual QA; it remains blocked only on final design/spec review and any future UI-affecting changes requiring recapture.
- P1: G06/AQ09 still needs credentialed OpenAI-compatible secret/header handling or an explicit user-approved local-only boundary.
- P1: G09 native sqlite-vec remains skipped or needs explicit fallback acceptance.
- P1: G15 needs deterministic rebuild and performance evidence, not only correctness and six slow query timings.
- P1: G07/G14 still need optional real MCP runtime smoke and remaining fallback/demo-state audit.

## No-Code Pause Checklist

- Product code is paused until this inventory and the individual gap docs are the planning source of truth.
- Docs-only edits may continue to correct stale facts or clarify acceptance evidence.
- The next code task must name the gap ID it closes and must start with a failing test.
- No commit, push, or goal completion claim is allowed while any row above is still blocking.

## Immediate Next Workstream Candidates

1. G14/G07: finish truthfulness and surface-policy review, especially optional real MCP runtime smoke and any remaining fallback/demo states.
2. G02/G03/AQ: reconcile the new clean AMD 9/9 artifact and six real free-form query records with graph/inspector/browser evidence.
3. G04/G05/G06: finish or explicitly bound corpus, resolver profile, provider, and OpenAI-compatible secret handling.
4. G01/G08/G09/G12/G15: finish remaining clean AMD UI/API citation, vector/runtime boundary, and performance proof beyond the current counts/timings.
5. G16/G10/G11/G17: finish architecture/design/documentation review, git hygiene, commit, and push.
