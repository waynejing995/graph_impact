# ASIP Workbench Gap Review

Date: 2026-05-16
Status: Historical implementation checklist; superseded by current gap and QA
evidence

> Current source of truth: this file is now superseded as the completion gate by
> `docs/gaps/README.md` and the individual `docs/gaps/2026-05-16-g*.md`
> documents. This older review mixes initial gaps, partial implementation
> progress, and stale red-test notes. Use it as historical context only until it
> is reconciled after the gap documents are closed.
>
> Do not use the verification counts or `PASS` language in this file as
> completion evidence. Final completion evidence must come from
> `docs/gaps/2026-05-17-final-clean-evidence-package.md` and the final QA docs.
>
> 2026-05-18 reconciliation: the auditable current design review is
> `docs/qa/2026-05-18-design-review-closure-matrix.md`. The gap matrix and
> workstream sections below intentionally remain as the early static-prototype
> review snapshot; when they conflict with the current gap ledger, the current
> gap ledger and design-review closure matrix win.

## Why This Exists

This document records the gap between the ASIP MVP-1 design documents and the current repository implementation.

The current Web UI is visually close to the intended workbench, but too much of it is still a static prototype. It must not be treated as complete until the gaps below are closed and verified with automated tests, browser E2E, design-doc review, and visual-anchor QA.

Primary references:

- `docs/specs/2026-05-16-asip-mvp1-design.md`
- `docs/specs/2026-05-16-asip-full-technical-spec.md`
- `docs/visual-anchors/README.md`
- `docs/superpowers/plans/2026-05-16-asip-mvp1-implementation.md`

## Current State Summary

### 2026-05-16 Implementation Progress

Verified in the current worktree:

- Web BFF routes now exist under `apps/web/app/api/workbench/*` for corpora, query, graph, acceptance, resolver profiles, Ollama model detection, and provider smoke.
- Web query now calls `/api/workbench/query` and updates evidence rows plus graph from API data.
- Corpus, Resolver Profiles, and Acceptance pages now load API data instead of relying only on `page-data.ts`.
- Settings split edge provider and embedding provider fields, supports extra headers, uses a BFF proxy for Ollama model detection, and calls a provider smoke API.
- Resolver profile configs now exist under `configs/resolvers/`, with core tests proving wrapper addition and toy Python extraction work without code changes.
- Core storage now has SQLite documents/chunks, FTS5 search, embedding-vector fallback search, persisted graph edges, and NetworkX graph construction.
- Core PDF conversion now has a text-based PDF fallback with page metadata and MarkItDown as the preferred optional path.
- MCP-facing tool functions now exist under `apps/mcp`, with tests for search evidence, graph expansion, resolver inspection, and acceptance runs.

Historical initial verification from this worktree:

- This block is preserved as an early implementation snapshot only.
- Current verification counts are tracked in `docs/gaps/README.md`, `docs/gaps/2026-05-16-g10-testing-acceptance-visual-qa.md`, and `docs/qa/2026-05-16-asip-real-workbench-progress.md`.
- Latest recorded targeted counts include Web API 18 passed, API/MCP 39 run OK with 1 optional live MCP skip, and targeted core 35 OK with 1 native sqlite-vec skip.

Still not fully closed:

- Full indexing job orchestration is partially wired from Web actions to SQLite ingestion, but final clean-DB add/index/query evidence and durable job-state UX remain open.
- FastAPI `apps/api` and MCP tool functions now exist and are covered by TestClient/tool tests; live server/runtime smoke and final route/tool matrix review remain open.
- MCP server entrypoint exists, but the optional external `mcp` Python package is not installed or smoke-tested as a live MCP process.
- sqlite-vec is represented by a SQLite-backed vector fallback; native sqlite-vec extension loading is not yet verified.
- Visual QA screenshots need to be regenerated/reviewed after these functional changes before final commit/push.

### Working Tree Guardrail

There are intentional red-test and partial Web edits in the current working tree while this gap review is being written:

- `apps/web/tests/workbench-smoke.spec.ts` contains failing E2E expectations for real query, corpus add, resolver profile add, Ollama detection, and split edge/embedding settings.
- `apps/web/components/workbench-page.tsx` contains partial local-state work that must not be treated as a completed feature until it compiles, passes tests, and is connected to real data.

These changes are useful as gap evidence, but they are not shippable completion evidence.

### What Exists

- Next.js + shadcn-style web shell in `apps/web`.
- Left rail routes for Evidence Search, Graph Explorer, Corpus, Resolver Profiles, Acceptance Tests, and Settings.
- Canonical visual anchor prompts and images under `docs/visual-anchors`.
- Python semantic-edge runner and real full-corpus QA artifacts under `packages/core` and `docs/qa`.
- Configurable semantic-edge provider support exists in Python core for Ollama and OpenAI-compatible chat-completions APIs, including model API base/path and extra headers.
- Some browser and Playwright tests for route rendering, theme switching, visual anchor geometry, graph presence, and provider settings persistence.

### Historical Initial Gaps Now Superseded

The bullets below describe the initial static-prototype state from this historical review. They are not the current source of truth:

- Web query was not backed by a retrieval/index/graph API.
- Web graph was mostly hand-rendered static SVG data.
- Corpus page did not register or index corpora.
- Resolver Profiles page did not load, edit, validate, or apply resolver profile config.
- Settings only partially modeled provider configuration and did not properly separate edge provider and embedding provider.
- Python provider config was not exposed as a real Web product flow.
- Web UI did not read real QA JSON, SQLite, FTS5, sqlite-vec, NetworkX output, or core retrieval results.
- At that initial snapshot, API and MCP interface work from the design was still pending.
- Visual anchors existed, but visual QA had not been re-run after every functional change.

Current status is tracked in `docs/gaps/README.md`: most of these items now have partial live implementation and tests, but the final clean AMD DB, live server smoke, route-by-route truth audit, page-by-page visual QA, and design/architecture completion gate remain open.

## Gap Matrix

| Area | Design Requirement | Current Implementation | Gap | Acceptance Evidence Required |
| --- | --- | --- | --- | --- |
| Corpus ingestion | Ingest Linux `amdgpu`, `amd/MxGPU-Virtualization`, docs, register headers, and at least one text-based AMD PDF | Web Corpus route displays static rows and counts from `apps/web/lib/page-data.ts`; Python semantic-edge tests scan real source roots only for edge-generation QA | No web/API corpus registration, no index job, no persisted corpus state, no PDF ingestion path in Web UI | Corpus API or BFF can add/list corpora; UI adds a corpus; E2E verifies new corpus appears; integration test verifies fixture corpus ingestion with docs/PDF/register headers |
| Evidence schema | Evidence item includes source type, repo, path, line/page, symbol, entity type, IP/ASIC hints, access type, confidence, snippet, resolved chain | Web rows only have `source`, `symbol`, `relation`, `score`, `path`; right inspector is static | Minimum evidence schema is missing in Web data model and UI | Unit/API test returns schema fields; Playwright verifies selected evidence detail shows source location, snippet, resolved chain, related entities |
| Query/retrieval | Hybrid evidence retrieval over exact symbol, resolver output, graph expansion, FTS5, vector search, rerank | Web BFF, FastAPI, and MCP query paths now read SQLite-backed evidence; Web rows, graph, and inspector can update from live API payloads | Final healthy clean AMD DB, source diversity, reranker/boundary decision, and full final browser evidence remain open | Playwright enters multiple queries and verifies rows/inspector/graph change; backend/API test verifies query endpoint returns ranked evidence |
| Graph model | SQLite persistent graph store; NetworkX in-memory graph runtime; graph expansion returns bounded neighborhoods | Core graph expansion/global graph use persisted edges and report NetworkX runtime; `/graph` requests no-seed global API graph data | Final clean indexed graph browser QA and route-by-route fallback audit remain open | Core test builds NetworkX from persisted edges; graph API returns nodes/edges; UI renders graph from returned data; E2E verifies query changes graph nodes |
| Resolver profiles | Configurable repo/language-specific resolver profiles; wrapper names, argument positions, prefixes, base-index suffixes, context vars, field rules; support non-macro profile | Resolver page displays static profile-like rows; referenced `configs/resolvers/*.yaml` are not actually loaded; no add/edit/validate | Resolver profile system is not exposed in Web and is only partially represented in tests | Real resolver config files exist; UI can add/edit a profile; validation uses core resolver; tests prove wrapper rename/addition works without code change and toy Python profile is supported |
| Model providers | Embeddings and semantic-edge providers support local Ollama and OpenAI-compatible providers; retrieval code must not hardcode Ollama | Python semantic-edge provider is configurable; Web Settings has one shared API base for edge and embedding and does not auto-detect local Ollama models | Settings model is incomplete and too manual | UI separates edge chat provider and embedding provider; detect button calls Ollama tags endpoint; provider status/smoke reflects actual backend; E2E verifies different edge/embed base URLs |
| Storage/indexing | SQLite owns corpora, documents, chunks, symbols, evidence, resolver profiles, graph entities/edges, jobs, provider config; FTS5 and sqlite-vec used | No Web/API storage layer; no SQLite schema migration visible in Web; page state is local or static | Storage/indexing layer missing from product path | Migration/unit tests for SQLite/FTS5/sqlite-vec adapter; API endpoints list indexed corpora/evidence; index job status is real |
| PDF support | Text-based PDF conversion via MarkItDown or similar; page metadata preserved; PDF chunks enter evidence pipeline | PDF appears as static row and QA note; no Web/API PDF conversion path | PDF ingestion not implemented end-to-end | PDF fixture conversion test; evidence row includes PDF page metadata; Web query returns PDF evidence |
| Acceptance tests | Nine acceptance queries including resolver profile change, toy Python resolver, provider switching | Core/CLI acceptance runner exists; Web BFF/FastAPI/MCP can list and run selected acceptance queries | Final AQ01-AQ09 healthy clean AMD pass/fail evidence and source diversity remain open | Acceptance page reads QA JSON or API; Playwright verifies pass/fail table; CLI/API acceptance runner produces current artifacts |
| API | FastAPI endpoints for corpus registration, indexing jobs, query, evidence, entity, graph, resolver validation, provider status | FastAPI app now exposes query, graph, corpus, resolver, provider, semantic-edge, evidence/entity, and acceptance paths with tests | Live server smoke and final route matrix remain open | FastAPI route tests; Web consumes BFF/API instead of `page-data.ts` for live data |
| MCP | MCP server exposing search evidence, explain symbol, graph expansion, resolver inspect, acceptance runner | MCP tool functions now expose search, graph, evidence/entity, corpus, resolver, provider, semantic-edge, and acceptance paths with tests | Optional live MCP runtime smoke and server-exposed tool matrix remain open | MCP tool schema tests and tool calls over fixture corpus |
| Visual anchors | Every page has individual prompt/image; implementation must match anchors and support light/dark | Anchor prompts/images exist; route geometry tests exist; no recent post-change visual QA after functional changes | Visual QA must be rerun after final implementation, not only earlier prototype | Capture desktop/narrow screenshots for all routes; compare against anchors for layout role, density, active nav, source colors, graph visibility; record in `docs/qa` |

## Static-Hardcode Inventory

2026-05-17 update: this document is historical context and is superseded by
`docs/gaps/README.md` plus `docs/gaps/2026-05-17-gap-document-register.md`.
The current rule is stricter than the notes below: the primary Web graph must
use a maintained React/npm graph visualization package. A hand-coded SVG graph
is not acceptable as the final `/graph` implementation.

These are the current high-risk static areas that must be removed or demoted to fallback/empty-state data:

- `apps/web/lib/page-data.ts`: page queries, filters, metrics, rows, inspector chains, relationship lines, and action labels.
- `apps/web/components/workbench-page.tsx`: `GlobalNetworkGraph` hand-coded SVG coordinates, labels, and weights.
- `Run query` button in `WorkbenchPage`: currently not connected to retrieval.
- Global symbol search: currently a `defaultValue` input with no state or action.
- Filter badges: currently non-interactive.
- Corpus rows/counts: static `703`, `625`, commits, and paths.
- Resolver profile rows: static wrappers and config paths.
- Acceptance page: static pass/fail/duration data.
- Settings: provider form persists local values, but provider status/index status are not real and edge/embedding provider concerns are not fully separated.

## Cross-Check Notes From Read-Only Review

- Web app status: the current route shell is a high-fidelity static prototype. `apps/web/lib/page-data.ts` still owns the main page content, and `WorkbenchPage` mostly renders that data rather than loading live product state.
- Query status: `Run query` must be considered unimplemented until at least five different free-form queries change ranked rows, selected evidence, and graph data in a reproducible E2E run.
- Graph status: superseded by G03/G16/G17. The global graph must be data-driven and package-backed; a hand-coded SVG graph is not acceptable as the primary `/graph` implementation.
- Provider status: Python core can express chat model provider configuration, but Web Settings still needs split edge-vs-embedding configuration, Ollama model detection, smoke/status endpoints, and real application of saved settings to query/index workflows.
- Anchor status: canonical anchors in `docs/visual-anchors/images/` are normalized to `2048 x 1280`; raw imagegen outputs in `docs/visual-anchors/imagegen-raw/images/` are preserved but must not be used for QA geometry. Every post-implementation visual QA report must compare live pages to the canonical per-route anchor and logo.
- Subagent limit: the current collaboration thread has a full subagent pool. Future implementation should reuse/close completed agents before dispatching more review workers.

## Required Implementation Workstreams

### W1. Real Local Data Surface

Build a minimal real data surface before further UI polish.

Required:

- Add API/BFF routes under `apps/web/app/api/workbench/*` or add `apps/api` if choosing the full architecture now.
- Load at least:
  - `configs/edge_cases/full-corpus-*.json`
  - `docs/qa/*full-corpus*.json`
  - resolver profile config files once created
  - visual anchor metadata
- Return structured corpora, evidence, graph nodes/edges, provider settings, and acceptance results.

Acceptance:

- No route depends solely on `page-data.ts` for core product data.
- `page-data.ts` is only layout fallback or seed data for empty states.

### W2. Query And Retrieval

Required:

- Query composer must submit text and update evidence rows.
- Results must be ranked and grouped by code/register/doc/PDF.
- Right inspector must show selected evidence detail, snippet/source preview, resolved chain, and related entities.
- Graph panel must update from query result entities/edges.

Acceptance:

- E2E query examples:
  - `regGCVM_L2_CNTL`
  - `doorbell interrupt disable`
  - `WREG32_SOC15`
  - `CP_INT_CNTL_RING0`
  - a no-match query with an explicit empty state
- Tests assert rows, inspector, and graph change together.

### W3. Dynamic Graph

Required:

- Graph must render from nodes/edges data, not hand-coded SVG constants.
- Edge width/opacity reflects edge confidence/weight.
- A bounded 1-2 hop graph is shown in the workbench; full graph route shows a larger weighted relation graph.
- Graph should be driven by NetworkX/core graph output when backend is available.

Acceptance:

- Unit/API test returns graph nodes/edges.
- Playwright verifies query changes graph node labels and edge weights.
- Visual QA verifies graph remains visible in dark and light themes.

### W4. Corpus Management

Required:

- UI can add/list corpus entries.
- Corpus entries include id, repo/path, include globs, type, and indexing status.
- Index action must call a real endpoint or show a truthful local-only state.
- PDF corpus type must be represented.

Acceptance:

- E2E adds a corpus and sees it in the table.
- If indexing is not implemented, UI must say `not indexed` or `pending`, not `ready`.
- Integration test ingests deterministic fixture corpus.

### W5. Resolver Profile Management

Required:

- Add real resolver config files under `configs/resolvers/`.
- UI can add/edit/select/enable resolver profiles.
- Validation action calls resolver validation or a truthful local validation stub backed by config parsing.
- Support at least Linux amdgpu, AMD MxGPU, and toy Python/non-macro profile.

Acceptance:

- Unit tests load resolver profiles from config.
- E2E adds a wrapper/profile and validates it.
- Acceptance query 7 and 8 are represented in test output.

### W6. Settings And Provider Status

Required:

- Split edge chat provider from embedding provider.
- Allow different base URLs and models for edge and embedding.
- Extra headers are provider-specific or clearly shared.
- Detect Ollama models via `/api/tags`.
- Provider smoke/status action must call a real endpoint or show a clear failure.
- Index/provider status in top bar must not show `ready` unless verified.

Acceptance:

- E2E configures different edge and embedding base URLs.
- E2E mocks/detects Ollama models and verifies auto-filled edge/embed model fields.
- Provider smoke test reports success/failure with evidence.

### W7. Acceptance Page

Required:

- Load real QA artifacts from `docs/qa/*.json` or API.
- Show run model, corpora, query count, pass/fail, failed query details, and source refs.
- Link or surface generated JSON/Markdown artifacts.

Acceptance:

- E2E verifies latest Gemma/Qwen QA data is visible.
- Page must not display stale hardcoded pass/fail counts.

### W8. API And MCP

Required:

- Implement `apps/api` FastAPI endpoints from the design unless the user explicitly de-scopes the full API in writing.
- Implement `apps/mcp` tools from the design unless the user explicitly de-scopes MCP in writing.
- Web should consume API/BFF data for query, graph, corpus, resolver, acceptance, and provider status.

Acceptance:

- FastAPI tests cover query/evidence/graph/provider endpoints.
- MCP tests cover search evidence, explain symbol, graph expansion, resolver inspect, and acceptance runner.

### W9. Visual Anchor QA

Required:

- After functional implementation, rerun visual QA for all pages.
- Confirm each page still matches its individual anchor, not a combined board.
- Confirm 2K baseline geometry and narrow viewport.
- Confirm light/dark support after route navigation.

Acceptance artifacts:

- Updated screenshots or QA report under `docs/qa/`.
- Explicit page-by-page pass/fail notes:
  - Evidence Workbench
  - Graph Explorer
  - Corpus
  - Resolver Profiles
  - Acceptance Tests
  - Settings
  - Logo

## Current Red Tests Added As Gap Evidence

The following Playwright tests were added while exposing the gap and currently fail until implementation catches up:

- `settings page persists configurable provider model api and headers`
  - Expected: separate `Edge API base URL`, `Edge API path`, `Embedding provider`, and `Embedding API base URL`.
- `ollama detection fills edge and embedding models`
  - Expected: `Detect Ollama models` button calls `/api/tags` and fills edge/embedding models.
- `free evidence query updates result rows and graph`
  - Expected: query `doorbell interrupt disable` updates results and graph.
- `corpus page adds user corpus rows`
  - Expected: user can add a corpus row through UI.
- `resolver page adds configurable profiles`
  - Expected: user can add a resolver profile row through UI.

These tests should remain red until the matching functionality is implemented. They should not be weakened to match static behavior.

## Design Review Checklist Before Completion

Do not mark the goal complete until every item below is checked with evidence.

- [ ] Design goals G1-G6 reviewed against implementation.
- [ ] First corpus requirements reviewed against implemented corpus/indexing path.
- [ ] Evidence schema minimum fields verified in API/UI.
- [ ] Resolver profile configurability verified with config files and tests.
- [ ] Model backend configurability verified for edge and embedding providers.
- [ ] Query/retrieval verified with at least five real query examples.
- [ ] Dynamic graph verified as data-driven, not hand-coded-only.
- [ ] Corpus add/index workflow verified.
- [ ] Acceptance page verified against real QA JSON or runner output.
- [ ] API endpoints verified, unless explicitly de-scoped by the user.
- [ ] MCP tools verified, unless explicitly de-scoped by the user.
- [ ] Visual anchor QA rerun for every route and logo.
- [ ] Desktop 2K and narrow viewport browser QA recorded.
- [ ] All unit/integration/E2E tests pass.
- [ ] `git diff --check` passes.
- [ ] Gap document updated from `Blocking` to `Closed` or remaining gaps are explicitly accepted by the user.

## Proposed Execution Order

1. Confirm this gap document with the user.
2. Decide whether the first real data surface is:
   - Web BFF routes only, reading repo artifacts directly, or
   - Full `apps/api` FastAPI service now.
3. Implement W1-W3 first: data surface, query, graph.
4. Implement W4-W6: corpus, resolver profiles, settings/provider detection.
5. Implement W7-W8: acceptance page, API/MCP tests.
6. Rerun W9 visual anchor QA.
7. Perform final design-doc checklist review.
8. Only then commit/push and mark the goal complete.
