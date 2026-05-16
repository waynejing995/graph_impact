# G03 Dynamic Weighted Graph

Status: Partial; global and seed weighted graph data paths exist, final browser visual QA remains blocking

## Requirement

ASIP must provide weighted relationship graph output. The user explicitly wants a global graph comparable to an Obsidian wiki relation graph, with connection weight reflected in the rendering.

SQLite is the persistent graph store. NetworkX is the in-memory graph runtime for traversal, subgraph extraction, and metrics.

Scope note: the original MVP-1 design deferred a full interactive graph canvas until the evidence workbench stabilized. The later active user request supersedes that deferral for this branch: a global weighted graph is now required for completion, while query/inspector views can still use bounded subgraphs.

## Current Evidence

- `packages/core/src/asip/workbench.py` has `expand_query_graph()` backed by persisted SQLite edges and NetworkX-derived hop-bounded subgraph extraction.
- `packages/core/src/asip/workbench.py` has `global_graph()` for no-seed global weighted graph output.
- `packages/core/src/asip/storage.py` has `expand_graph()`, `expand_graph_networkx()`, `global_graph_networkx()`, and `to_networkx()`.
- `apps/web/app/api/workbench/graph/route.ts`, FastAPI `/graph`, and MCP `graph_expand()` call the live graph service.
- `apps/web/app/api/workbench/graph/route.ts` supports both selected-seed subgraphs and no-seed global graph output through `asip.cli graph`.
- `apps/web/components/workbench-page.tsx` requests `/api/workbench/graph` without a default seed on `/graph` load and treats an API graph, including an empty graph, as authoritative.
- Evidence Workbench query results now keep table rows, query-scoped graph payload, and right inspector derived from the same live API query payload.
- `apps/web/tests/workbench-smoke.spec.ts` verifies live query rows and graph edges update together with inspector resolved-chain content, and that selecting a different row changes inspector content.
- `apps/web/tests/visual-anchor-routes.spec.ts` verifies the graph route renders API-provided nodes/edges, exposes edge `data-weight`, and reflects weight through stroke width instead of asserting the old fixed seed shape.
- `packages/core/tests/test_workbench_live.py` verifies `expand_query_graph()` returns `source: networkx`, `graph_runtime: networkx`, preserves edge weight, and respects hop bounds.
- `packages/core/tests/test_workbench_live.py` verifies `global_graph()` returns top weighted edges without a seed and excludes lower-confidence edges by limit.
- `apps/web/tests/visual-anchor-routes.spec.ts` verifies the `/graph` page requests `/api/workbench/graph` without `seed`, `queryId`, or the old `DOORBELL_INTERRUPT_DISABLE` default.
- `packages/core/src/asip/workbench.py` now has a semantic-edge job that can generate edges from indexed evidence rows and persist them into the same SQLite graph store.
- `asip.cli semantic-edges`, Web BFF `POST /api/workbench/semantic-edges`, and the `/graph` page `Generate semantic edges` action expose semantic-edge generation as a product path rather than only an offline QA artifact.
- Core, Web API, and Web smoke tests verify generated semantic edges update the weighted graph through a supplied isolated DB and local fake Ollama-compatible HTTP provider.
- Clean AMD free-query QA `docs/qa/2026-05-17-clean-amd-free-query-and-edge-qa.json` records six query-scoped graphs and one no-seed global graph with `graph_runtime: networkx`; global graph summary was `nodes=42`, `edges=75`.
- The same clean AMD QA records two real qwen3.5 semantic-edge jobs generated from indexed evidence rows and persisted into the SQLite graph store.
- Verification on 2026-05-17:
  - `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests python3 -m unittest packages.core.tests.test_workbench_live packages.core.tests.test_storage_graph packages.core.tests.test_workbench_cli -v`: 10 run, OK, 1 sqlite-vec skip.
  - `pnpm test:ui tests/visual-anchor-routes.spec.ts --reporter=list`: 13 passed.
  - `pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts --reporter=list`: 34 passed.
  - `pnpm --filter web exec playwright test tests/workbench-api.spec.ts --reporter=list`: 18 passed.

## Remaining Gap

The graph API is live-data backed and now supports a no-seed global graph plus an explicit semantic-edge generation action. Clean AMD CLI/core graph QA is recorded. The remaining product gap is browser visual review against the graph anchor and final UI proof that the rendered graph is legible with the live graph payload.

The final product must prove that `/graph` and query-scoped graph panels render data from indexed ASIP graph output rather than fixed page rows, fixed edge counts, or hardcoded layout assumptions across the final clean acceptance database.

Post-change visual QA against the `/graph` anchor is still open, and the Web page still needs final browser QA to prove the rendered global graph stays legible with the live NetworkX-backed graph payload.

## Acceptance Criteria

- Graph API reads persisted graph data or core graph runtime output.
- `/graph` renders the full indexed weighted relation graph, while query/inspector views can render bounded 1-2 hop subgraphs.
- The `/graph` route must be treated as an active product feature, not a post-MVP visual-only deferral.
- Edge width, opacity, or emphasis reflects edge weight/confidence.
- Querying changes graph nodes and edges.
- The graph remains visible and legible in light and dark themes.
- NetworkX-derived traversal/subgraph output is used by the product graph API, or this is explicitly accepted as a post-MVP deferral.

## Required Tests

- Core test: graph API returns a different graph after indexing different fixture data.
- Core test: NetworkX traversal and weighted subgraph extraction from SQLite edges.
- Core test: global graph returns weighted edges without a seed.
- Web API test: selected seed returns weighted nodes/edges from SQLite.
- Web E2E test: `/graph` requests global graph without a default seed.
- E2E test: query changes graph labels and edge weights. Implemented for query-scoped API graph labels plus live inspector linkage; final clean-corpus graph QA remains open.
- Visual QA: `/graph` compared with its individual 2K anchor after functional changes.

## Not Closed Until

The graph shown in Web is generated from indexed ASIP graph data, and tests no longer assert a fixed static graph shape as the primary behavior.
