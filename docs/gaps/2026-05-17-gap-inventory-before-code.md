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
- Current pass verified but final G11/git gate remains: G03, G10, G14, G16, G17 slices touched by the latest graph/UI/backend work.
- Partial or explicitly deferred boundaries: G01-G09, G12, G13, G15, AQ.
- Blocking gate: G11 final documentation, artifact hygiene, commit, push, and explicit residual-boundary acceptance.
- 2026-05-17 user-review update: `/graph` must use a maintained React/npm graph package, standard UI must prefer shadcn/native package primitives, and Acceptance fail/partial rows must expand into real details.
- 2026-05-17 graph-architecture correction: graph build must be two-stage. Stage 1 is deterministic code graph extraction from source using an AST/preprocessor/macro-expansion style path where available. Stage 2 is LLM semantic-edge overlay on top of indexed code/doc/register candidates. Evidence/query-term overlay is explicitly separate and cannot be counted as Stage 1.
- 2026-05-18 vtable correction: full clangd/libclang vtable type-flow parsing is not done. Current callback/common links come from source-span table initializer and slot-call matching plus shallow receiver type hints. The AST JSON slice adds selective `clang -Xclang -ast-dump=json` receiver-type provenance (`type_flow=clang_ast_json`) for 2,220 callback edges in rebuild job 78, but `source=clang_callback` still must not be read as full clangd output. The IP-block registration-flow slice adds provable `amdgpu_device_ip_block_add(adev, &*_ip_block)` aliases into common `adev->ip_blocks[i].version->funcs` loops, recorded in rebuild job 80. The next proof must either add a true typed clangd/libclang cross-TU extractor or keep this as an explicit residual, while query graphs show `common -> callback -> register` backbones and cross-repo graph connectivity through shared normalized register nodes.
- 2026-05-18 query performance correction: query-scoped graph expansion now uses one multi-seed NetworkX build, empty/no-edge multi-seed paths return seed nodes instead of raising or rebuilding, and callable-symbol metadata checks avoid regex compilation hot paths. Six real dirty-DB queries and AQ01 Web acceptance timing are recorded in `docs/qa/2026-05-18-query-graph-performance-qa.md`.
- 2026-05-17 graph-budget and resolver-node correction: graph/retrieval/semantic budgets must come from `configs/workbench-limits.json` plus explicit user overrides, not hidden CLI/API/UI constants. Resolver wrapper/extractor names are operations/provenance, not graph entity nodes, so `WREG32`, `REG_SET_FIELD`, `SOC15_REG_OFFSET`, `amdgv_wreg32`, and `gpu_register` must not become mega-nodes through graph endpoints, selected seeds, query expected terms, stale evidence rows, or UI resolver tables.
- Support/index documents: README, gap register, compact inventory, final clean evidence package gate.

## Inventory

| ID | Document | Status | Next proof before closure |
| --- | --- | --- | --- |
| G01 | [Real Ingestion And Indexing](2026-05-16-g01-real-ingestion-indexing.md) | Partial; blocking | Clean AMD DB `/tmp/asip-clean-amd-gemma4-provider-2026-05-17-final.db` now proves code/doc/pdf/register counts from raw AMD roots and reduced AMD PDF with `gemma4:e4b` provider smoke; browser/product-surface proof and final full-suite gate remain open. |
| G02 | [Live Retrieval And Evidence Schema](2026-05-16-g02-live-retrieval-evidence-schema.md) | Partial; blocking | Live inspector linkage and clean AQ runner mechanics are proven; rerank/source-diversity/final route evidence remains open. |
| G03 | [Dynamic Weighted Graph](2026-05-16-g03-dynamic-weighted-graph.md) | Partial; blocking | Fresh real AMD rebuild and 2K browser QA now prove a real Stage 1 deterministic graph plus small Stage 2 `gemma4:e4b` overlay. This pass adds shared graph-budget config, compile_commands-driven macro preprocessing, conservative direct/callback callgraph edges, cross-file unique direct common-helper calls, generic common `vtable_dispatch` candidate edges, receiver type-hint filtering for `struct <type> *ops` and `(*ops->slot)(...)`, local/field-path callback table aliases, IP-block version/function-table aliases, corpus-level IP-block registration aliases for provable `adev->ip_blocks[i].version->funcs` flows, selective Clang AST JSON receiver-type hints, MxGPU `amdgv_init_func` dispatch coverage, query-scoped multi-seed performance fixes, config-driven resolver-operator mega-node rejection at storage/import boundaries, Markdown section semantic endpoint proof, and BoxMatrix-style LLM doc boxes. Latest rebuild job 80 produced `41,998` graph-rebuild edges; a 20k-edge product graph sample has `15,170` nodes, `261` components, and largest component `9,864`. Six dirty-DB real queries now return graph payloads in `0.878s` to `4.161s`. Provenance now uses `clang_text_spans` instead of falsely implying full `clang_ast` parsing, and AST JSON typed hints are separated from conservative callback overlay rows. Remaining proof is full Linux-kernel compile DB/clangd-quality cross-TU type-flow coverage, larger robust semantic batches, final-corpus PDF/page browser coverage, ranking review, and design-doc closure. |
| G04 | [Corpus Management](2026-05-16-g04-corpus-management.md) | Partial; blocking | Selected UI indexing, invalid-source/zero-doc false-success prevention, durable `queued/indexing/succeeded/failed` job events, and a real Web add-index-query loop are proven; final proof must repeat against a clean DB and show inspector/graph evidence from the newly indexed corpus. |
| G05 | [Resolver Profiles](2026-05-16-g05-resolver-profiles.md) | Current pass verified; final gate | YAML-backed listing, add/validate/enable-disable/edit, per-index selection, CLI/API/MCP/Web BFF passthrough, and changed extraction without resolver code edits are proven. QA is recorded in `docs/qa/2026-05-18-resolver-profile-selection-qa.md`. Remaining boundary is richer unmatched-span diagnostics and broader non-C strategies beyond configured Python call extractors. |
| G06 | [Provider Settings And Ollama Detection](2026-05-16-g06-provider-settings-ollama.md) | Partial; blocking | Local Ollama settings now drive embeddings and query/batch semantic-edge jobs with provenance. The clean AMD provider artifact now uses `gemma4:e4b` instead of stale qwen rows, and safe env-based extra-header expansion is tested for embedding and edge providers; remaining proof is credentialed OpenAI-compatible live endpoint QA or explicit local-compatible deferral plus query-time rerank boundary. |
| G07 | [API And MCP Product Surfaces](2026-05-16-g07-api-mcp.md) | Partial; blocking | API/MCP expose corpus, index jobs, provider status, evidence/entity detail, resolver validation, acceptance execution, semantic-edge generation, key read-route no-mutation/status-list no-migration behavior, FastAPI live HTTP smoke including `pnpm dev:api`, MCP server tool-matrix registration, and Web/MCP query/evidence/entity agreement; optional real MCP runtime smoke remains open. |
| G08 | [PDF And Document Ingestion](2026-05-16-g08-pdf-document-ingestion.md) | Partial; blocking | Reduced AMD amdgpu PDF is indexed in the clean AMD DB (`documents.pdf=1`, `evidence.pdf=5`) and AQ05 passes with `pdf`; Markdown/doc section graph nodes, semantic section endpoints, PDF section provenance, and LLM doc boxes are covered. Final browser/API page-citation QA against the final corpus remains open. |
| G09 | [SQLite FTS5 Vector And NetworkX Runtime](2026-05-16-g09-storage-vector-graph-runtime.md) | Partial; provider-quality boundary open | Native sqlite-vec extension smoke and native `search_vector()` adapter are verified in the bundled Python runtime; system Python keeps the documented JSON/Python cosine fallback path; query evidence exposes `vector_runtime`; NetworkX graph runtime is proven in final QA. Remaining proof is full provider-vector coverage/semantic rerank quality, not native adapter wiring. |
| G10 | [Testing Acceptance And Visual QA](2026-05-16-g10-testing-acceptance-visual-qa.md) | Current pass verified; final gate | Package-backed graph, expandable acceptance details, source filters, global search, semantic generation controls, visual routes, and Web API/smoke now pass; G11 owns final closure. |
| G11 | [Completion Gate And Documentation Review](2026-05-16-g11-completion-gate.md) | Blocking | Design docs, gap docs, QA docs, git diff, tests, commit, and push are reviewed in one final completion gate. |
| G12 | [ASIC And IP Metadata Filtering](2026-05-16-g12-asic-ip-metadata-filtering.md) | Partial; blocking | Real AMD filtered queries prove IP/ASIC filters affect result sets and UI layout remains stable. |
| G13 | [MVP Boundary And Full-Spec Deferrals](2026-05-16-g13-mvp-boundary-deferrals.md) | Blocking | Full-spec non-MVP features are mapped to explicit deferrals instead of silent omissions. |
| G14 | [Static Data And Truthful Empty States](2026-05-16-g14-static-data-and-truthful-empty-states.md) | Current pass verified; audit residual | Empty/error/no-mutation paths, source filters, live global search, package graph, and expandable acceptance details are covered; remaining work is final route audit consistency in G11. |
| G15 | [Performance Smoke And Deterministic Rebuild](2026-05-16-g15-performance-smoke-deterministic-rebuild.md) | Partial; blocking | Fixture stable-count smoke is implemented and documented: two empty-DB rebuilds over `docs/fixtures/performance-smoke` match counts, and five live fixture queries return rows under one second. Dirty local AMD query-graph performance QA now records six real query timings and AQ01 Web acceptance under the 30s e2e timeout. Real mxgpu + linux-amdgpu graph rebuild still records `7:00.02` for `1340` files after batched evidence/edge commits; remaining proof is repeat real-corpus rebuild determinism and embedding-backfill timing. |
| G16 | [Workbench IA Theme And Visual Fidelity](2026-05-16-g16-workbench-ia-theme-visual-fidelity.md) | Current pass verified; final gate | shadcn/Radix controls, package-backed graph rendering, live global search, source filters, semantic controls, light/dark persistence, and visual route QA are verified; recapture only if further UI changes land. |
| G17 | [Architecture Ownership And Process Shape](2026-05-16-g17-architecture-ownership-process-shape.md) | Current pass recorded; final review | Core/API/MCP/Web ownership now splits Stage 1 deterministic code graph including direct/callback/generic dispatch call edges, evidence overlay, Stage 2 LLM semantic-edge overlay, resolver boundaries, package graph adapter, and shadcn UI composition; full clangd/libclang type-flow callback resolution remains explicit future ownership, and final G11 review owns residual boundary acceptance. |
| AQ | [MVP Acceptance Query Matrix](2026-05-16-mvp-acceptance-query-matrix.md) | Current pass recorded; final gate | Current clean AMD gemma artifact records AQ01-AQ09 9/9 with DB health pass, source diversity, provider checks, and CLI/API/Web/MCP labels; final G11 closure still needs stale-doc reconciliation and git gate. |

## Support Gates

| Document | Role | Required use |
| --- | --- | --- |
| [Final Clean Evidence Package Gate](2026-05-17-final-clean-evidence-package.md) | Defines the final QA package required before completion. | Every G01-G17 closure claim must link to this package or explicitly explain a user-accepted deferral. |

## Audit Findings To Preserve

- P0: The historical clean provider AQ artifact proves provider plumbing, not cross-source retrieval. Current source-gated rerun is 0/9 and correctly exposes DB health failures plus missing PDF on AQ05.
- P0: G01 and G08 now have clean DB counts and PDF evidence; they remain blocked on UI/API/browser citation QA and final completion gate review.
- P0: The multisource fixture artifact proves the source-diversity path on a synthetic corpus only; it must not be promoted to real AMD closure.
- P0: G16 now has fresh visual QA; it remains blocked only on final design/spec review and any future UI-affecting changes requiring recapture.
- P1: G06/AQ09 still needs credentialed OpenAI-compatible live endpoint QA or an explicit user-approved local-compatible boundary; safe env-based header expansion is implemented and tested.
- P1: G09 native sqlite-vec extension smoke and native `search_vector()` adapter path are verified in the bundled Python runtime; remaining G09 risk is full provider-vector coverage and semantic rerank quality, not adapter wiring.
- P1: G15 now has fixture stable-count rebuild and sub-second query evidence; it still needs repeat real-corpus timing and provider embedding/backfill timing, not only correctness and one-off AMD timings.
- P1: G07/G14 still need optional real MCP runtime smoke and remaining fallback/demo-state audit.
- P0: `/graph` live API data is not enough; Stage 1 deterministic code graph extraction and Stage 2 semantic-edge overlay must be separate, visible in provenance, and visually/interaction tested as a real global graph with function-operation, direct/callback call, document-section, and semantic-edge layers. Resolver macro/wrapper names and callback slot names must remain provenance only, never central graph nodes.
- P0: Acceptance rows must expose fail/partial detail; compressed counts alone are not usable QA.
- P1: Standard frontend controls should use shadcn/native package primitives before custom markup.

## No-Code Pause Checklist

- Product code is paused until this inventory and the individual gap docs are the planning source of truth.
- Docs-only edits may continue to correct stale facts or clarify acceptance evidence.
- The next code task must name the gap ID it closes and must start with a failing test.
- No commit, push, or goal completion claim is allowed while any row above is still blocking.

## Immediate Next Workstream Candidates

1. G03/G06/G08/G16/G17: harden the proven two-stage graph path: full compile-command/libclang-quality extraction, robust larger `gemma4:e4b` semantic batches, doc/PDF semantic coverage, ranking review, and design-doc closure.
2. G14/G10/G16: remove/demote remaining static product data and add expandable acceptance detail UI.
3. G04/G05/G06/G07: finish or explicitly bound corpus, resolver profile, provider, and OpenAI-compatible secret handling.
4. G02/G03/AQ: reconcile clean AMD 9/9 and free-form query records with browser graph/inspector evidence.
5. G01/G08/G09/G12/G15: finish remaining clean AMD UI/API citation, vector/runtime boundary, and performance proof beyond the current counts/timings.
6. G16/G10/G11/G17: rerun visual QA, finish architecture/design/documentation review, git hygiene, commit, and push.
