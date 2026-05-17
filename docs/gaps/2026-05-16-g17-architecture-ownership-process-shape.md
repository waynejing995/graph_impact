# G17 Architecture Ownership And Process Shape

Status: Current package-first ownership pass recorded; final architecture review remains part of G11

## Requirement

The implementation must preserve the architecture locks from the MVP-1 design:

- `packages/core/src/asip` owns reusable ingestion, resolver, indexing, retrieval, graph, PDF, and provider logic.
- `apps/api` and `apps/mcp` are thin application packages over the core.
- Next.js routes are BFF/product routes, not the only home of ASIP retrieval logic.
- `sqlite-vec` or vector-extension SQL is accessed only through an adapter boundary.
- NetworkX is loaded from SQLite graph data for runtime graph computation; SQLite remains the persistent graph store.
- `apps/mcp` can run as a separate MCP server process and imports core logic directly for local operation.
- Production code changes follow TDD and final verification, not progress-only claims.
- Product features should prefer maintained packages/libraries before custom implementations. Custom code should be the glue, adapter, or ASIP-specific behavior around those packages, not a reinvention of standard graph/UI/form/table behavior.
- The React graph renderer is a frontend visualization package responsibility. Core still owns graph storage/traversal/weight calculation; Web owns adapting `GraphPayload` into the selected graph package.
- Batch semantic-edge generation is a core/provider capability. Core owns candidate extraction, prompt batching, provider calls, persistence, and job provenance; API/MCP/Web only trigger the job and render status/results.
- Document section graph extraction is a core document/indexing capability. Web may display section nodes, but it must not be the only place where PDF/Markdown sections are interpreted.

## Current Evidence

- Core logic now exists under `packages/core/src/asip` for storage, workbench services, documents, resolver profiles, providers, and indexing artifacts.
- Next.js API routes call the core CLI path rather than embedding all retrieval logic directly in React.
- FastAPI and MCP packages exist and have tests over live SQLite query/graph behavior.
- NetworkX-backed graph expansion exists in core.
- Native `sqlite-vec` is still skipped when the extension cannot load, and vector fallback behavior remains partial.
- Final-candidate architecture review is recorded in `docs/qa/2026-05-17-final-clean-evidence-package.md`, mapping corpus/indexing, PDF conversion, resolver profiles, retrieval, SQLite/FTS/vector, NetworkX, semantic-edge generation, provider settings, FastAPI, MCP, Web BFF, and React UI to their owning layers and tests.
- `apps/mcp/server.py` now has a tool-matrix registration test covering all implemented product tools; the optional external `mcp` runtime package remains skipped when absent.
- 2026-05-17 package reconnaissance for the global graph checked npm metadata for `react-force-graph-2d`, `sigma`/`graphology`, and `@xyflow/react`. `react-force-graph-2d` is the current first spike candidate for the Obsidian-like `/graph` route.
- 2026-05-17 implementation now keeps graph enrichment in core/storage/workbench: function operation edges and document section nodes are derived before Web rendering, and CLI/Web BFF/FastAPI/MCP batch semantic-edge surfaces call the same core job.
- `/graph` now uses `react-force-graph-2d` through `apps/web/components/weighted-force-graph.tsx`; Web owns only the package adapter and visual accessibility summary, while core owns graph calculation, relation weights, node kinds, function-operation edges, document section nodes, and persisted semantic edges.
- Standard controls now use shadcn/Radix wrappers for buttons, inputs, textareas, badges, cards, checkboxes, labels, fields, tables, accordions, select, separator, and scroll area. Remaining custom UI is ASIP-specific layout, status mapping, graph package adapter, and evidence/relationship rendering.
- Subagent review after implementation found no P0 UI/package blocker. It flagged and this pass fixed the hardcoded top-bar index status, unused graph types, and unused static artifact search/graph helpers.

## Remaining Gap

The repo has an explicit architecture review in the final-candidate QA package, and this gap document now records the package ownership changes from the 2026-05-17 package-first decision. Completion still requires carrying this evidence through the final G11 review before commit/push.

The vector adapter boundary and MCP process shape are especially important because they affect future sqlite-vector extensions, local agent workflows, and API/BFF responsibilities.

The final architecture review includes a capability-to-owner matrix with these
capabilities:

- corpus registration and indexing,
- document/PDF conversion,
- register/header extraction and resolver profiles,
- hybrid query retrieval and rerank/provider boundaries,
- SQLite/FTS/vector storage,
- NetworkX graph runtime,
- semantic-edge generation,
- provider settings and Ollama/OpenAI-compatible transports,
- FastAPI routes,
- MCP tools/server process,
- Next.js BFF routes,
- React workbench UI state and visual anchors.

Each row must name the owning layer (`core`, `apps/api`, `apps/mcp`, Web BFF,
or React UI), tests that cover it, and any accepted deferral.

Package-first review rows now covered by implementation and QA evidence:

- `/graph` visualization package: selected package, why it fits, data adapter boundary, interaction/visual QA evidence.
- shadcn UI primitives: where native shadcn components are used, which custom components remain, and why each remaining custom component is ASIP-specific.
- Acceptance detail UI: shadcn table/accordion/card primitives or a documented package choice for expandable run details.
- Function/document graph layers: core extraction owner, graph schema fields, node/edge kinds, tests, and Web rendering expectations.
- Batch semantic-edge pipeline: provider adapter owner, batching limits, job status schema, failure handling, and API/MCP/Web trigger boundaries.

## Acceptance Criteria

- Final review maps each major capability to its owning layer: core, API, MCP, Web BFF, or React UI.
- Shared retrieval/resolver/indexing/PDF/provider logic is not implemented only inside Web routes or UI components.
- Standard UI and graph functionality is not hand-rolled when a maintained React/npm package or shadcn primitive fits.
- Graph data enrichment, including function operation edges and document section nodes, lives in core/indexing/graph services instead of React components.
- Batch semantic-edge generation is exposed through core and thin API/MCP/Web routes rather than only a UI button or test helper.
- Vector extension access is isolated behind the storage/vector adapter contract, or native vector work is explicitly deferred in G09/G13.
- MCP server tools are tested as tool functions and, where dependencies permit, as a runnable server process.
- API routes and MCP tools avoid unexpected state mutation in read-style operations, or the initialization behavior is explicitly accepted and documented.
- TDD evidence exists for production code changes, and docs-only changes are clearly identified as docs-only.

## Required Tests And Checks

- Architecture review checklist in the final QA doc.
- `git diff --check` plus full test/build/lint suite before completion.
- API/MCP tests proving app layers call core behavior rather than duplicated fixture-only code.
- Frontend package audit for graph/UI components: selected packages, rejected alternatives, and tests/QA tied to them.
- Review of generated/local artifacts before staging.

## Not Closed Until

The final review can point to the core owner for every ASIP capability, show that app layers are thin, and identify any consciously deferred architecture lock.
