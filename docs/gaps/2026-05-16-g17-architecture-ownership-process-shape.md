# G17 Architecture Ownership And Process Shape

Status: Partial; package-first ownership and graph stage separation are recorded and real graph rebuild/browser QA exists, but final architecture closure is still open

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
- Stage 1 deterministic code graph generation is a core/indexing capability. For C/C++ corpora it must use a code-aware AST/preprocessor/macro-expansion path where available, persist deterministic edge provenance, and never be hidden inside React or a query-specific UI fallback.
- Graph entity and edge normalization is a core/storage capability. The default graph node contract allows only `function`, `register`, `doc_section`, `pdf_section`, and `doc_box`; resolver macros, macro-expansion helpers, field-only symbols, raw source paths, temporary variables, and provider/config names stay in provenance or BoxMatrix-style node attributes. Product edge relations are normalized to a small enum before Web/API rendering.
- Batch semantic-edge generation is a core/provider capability. Core owns candidate extraction, prompt batching, provider calls, persistence, and job provenance; API/MCP/Web only trigger the job and render status/results.
- Stage 2 LLM semantic-edge generation is an overlay on top of indexed Stage 1/document candidates. It must be stored/provenanced separately enough that QA can tell deterministic edges from provider-generated semantic edges.
- Document section graph extraction is a core document/indexing capability. Web may display section nodes, but it must not be the only place where PDF/Markdown sections are interpreted.

## Current Evidence

- Core logic now exists under `packages/core/src/asip` for storage, workbench services, documents, resolver profiles, providers, and indexing artifacts.
- Next.js API routes call the core CLI path rather than embedding all retrieval logic directly in React.
- FastAPI and MCP packages exist and have tests over live SQLite query/graph behavior.
- NetworkX-backed graph expansion exists in core.
- Native `sqlite-vec` extension smoke passes in the bundled Python runtime, but product retrieval still uses the fallback JSON-vector/Python-cosine adapter until native retrieval acceleration is wired.
- Final-candidate architecture review is recorded in `docs/qa/2026-05-17-final-clean-evidence-package.md`, mapping corpus/indexing, PDF conversion, resolver profiles, retrieval, SQLite/FTS/vector, NetworkX, semantic-edge generation, provider settings, FastAPI, MCP, Web BFF, and React UI to their owning layers and tests.
- `apps/mcp/server.py` now has a tool-matrix registration test covering all implemented product tools; the optional external `mcp` runtime package remains skipped when absent.
- 2026-05-17 package reconnaissance for the global graph checked npm metadata for `react-force-graph-2d`, `sigma`/`graphology`, and `@xyflow/react`. `react-force-graph-2d` is the current first spike candidate for the Obsidian-like `/graph` route.
- 2026-05-17 implementation now keeps graph enrichment in core/storage/workbench: function operation edges and document section nodes are derived before Web rendering, and CLI/Web BFF/FastAPI/MCP batch semantic-edge surfaces call the same core job.
- `/graph` now uses `react-force-graph-2d` through `apps/web/components/weighted-force-graph.tsx`; Web owns only the package adapter and visual accessibility summary, while core owns graph calculation, relation weights, node kinds, function-operation edges, document section nodes, node attribute payloads, and persisted semantic edges.
- 2026-05-17 user review found this graph ownership is still too vague: current function-operation edges are regex/resolver-derived from evidence rows, not a real Stage 1 AST/preprocessor graph. The architecture remains blocking until Stage 1 deterministic code graph generation is a named core capability with tests and provenance, and Stage 2 LLM semantic edges are stored as overlay edges.
- 2026-05-17 correction slice made Stage 1 a named core/indexing capability in `packages/core/src/asip/code_graph.py`. It invokes clang AST parsing where available, uses committed YAML resolver profiles as deterministic macro/wrapper configuration, persists path/line/provenance on `stage=deterministic` edges, and keeps LLM output as `stage=semantic`.
- 2026-05-17 callback/callgraph correction keeps more Stage 1 graph connectivity in core without pretending to be full clangd/libclang: `code_graph.py` now extracts conservative direct helper calls, C ops/vtable initializer callback slots, and slot-call sites; `workbench.py` batches all code files in a corpus so safe callback joins can cross file boundaries; `storage.py` reads endpoint-specific callback path/line provenance so callback function nodes stay attached to the defining file rather than the caller file. Specific table calls are constrained to the matching table when the receiver is known; generic `funcs/ops/callbacks` receivers connect only when the slot has a single known candidate, preventing one same-named slot from fabricating edges to every callback in the corpus.
- Evidence/query-term graph aids are now `stage=evidence` and are only used as an explicit overlay or small-DB fallback; they are not accepted as Stage 1 closure.
- NetworkX graph traversal now uses a multi-edge graph so the core can preserve separate read/write/set operations between the same function and register.
- 2026-05-17 real rebuild QA in `docs/qa/2026-05-17-two-stage-graph-real-rebuild-qa.md` proved the owner split on live AMD data, but the visible graph still exposed noisy field/source-style nodes. The current architecture correction keeps that owner split while tightening the core graph entity contract to function/register/doc nodes with BoxMatrix-style `in`/`out`/`attr` payloads.
- 2026-05-17 resolver-operator ownership hardening keeps wrapper classification in core. `packages/core/src/asip/graph_filters.py` reads committed resolver YAML operators, `AsipStore.add_edge()` enforces the entity boundary at the storage write path, and generated artifact import counts only accepted graph-entity edges. Web and API layers do not decide whether `WREG32`/`REG_SET_FIELD`/`gpu_register` are nodes.
- 2026-05-17 continuation after subagent audit: backend ownership now includes scoped Stage 1 rebuild cleanup by corpus provenance; Web ownership now includes package graph layer-provenance display, live top-bar query dispatch, source-type filter controls, and user-configurable semantic generation limits; tests cover each behavior before the implementation is treated as current evidence.
- 2026-05-17 LLM doc-node ownership keeps BoxMatrix-style extraction in core/provider code. `generate_doc_nodes_batch()` selects indexed doc/PDF chunks, calls the configured Ollama/OpenAI-compatible provider, persists `doc_box` nodes as semantic graph edges, and exposes the feature through CLI/Web API/UI without depending on a skill implementation.
- Standard controls now use shadcn/Radix wrappers for buttons, inputs, textareas, badges, cards, checkboxes, labels, fields, tables, accordions, select, separator, and scroll area. Remaining custom UI is ASIP-specific layout, status mapping, graph package adapter, and evidence/relationship rendering.
- Subagent review after implementation found no P0 UI/package blocker. It flagged and this pass fixed the hardcoded top-bar index status, unused graph types, and unused static artifact search/graph helpers.

## Remaining Gap

The repo has an explicit architecture review in the final-candidate QA package, and this gap document records the package ownership changes from the 2026-05-17 package-first decision. The Stage 1/Stage 2 split is now represented in code and tests, including deterministic register operations plus conservative direct/callback callgraph edges, but completion still requires refreshing the final architecture matrix so deterministic Stage 1 code graph generation, graph entity normalization, evidence overlay, and Stage 2 LLM semantic-edge overlay are separate owner rows with linked tests and provenance.

The vector adapter boundary and MCP process shape are especially important because they affect future sqlite-vector extensions, local agent workflows, and API/BFF responsibilities.

The final architecture review includes a capability-to-owner matrix with these
capabilities:

- corpus registration and indexing,
- document/PDF conversion,
- register/header extraction and resolver profiles,
- hybrid query retrieval and rerank/provider boundaries,
- SQLite/FTS/vector storage,
- NetworkX graph runtime,
- deterministic C/C++ code graph extraction,
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
- Stage 1 code graph pipeline: clang/preprocessor or compile-context strategy, direct helper call extraction, C ops/vtable callback slot extraction, fallback/error behavior, graph schema fields, node/edge kinds, deterministic provenance, tests, and Web rendering expectations. Full clangd/libclang cursor/type-flow callback resolution remains separate future ownership and must not be claimed by the current conservative extractor.
- Graph entity and edge normalization pipeline: allowed node kinds, allowed relation enum, BoxMatrix-style node/edge payloads, field/macro/source attr folding, and tests proving noisy resolver/macro/field/source endpoints or free-form provider relations do not leak to product graph output.
- Evidence overlay pipeline: row-count cap, explicit UI/API flag, section/source/co-occurrence derivation, and clear exclusion from default Stage 1/Stage 2 graph claims.
- Stage 2 semantic-edge pipeline: provider adapter owner, batching limits, job status schema, failure handling, provider/model provenance, and API/MCP/Web trigger boundaries.

## Acceptance Criteria

- Final review maps each major capability to its owning layer: core, API, MCP, Web BFF, or React UI.
- Shared retrieval/resolver/indexing/PDF/provider logic is not implemented only inside Web routes or UI components.
- Standard UI and graph functionality is not hand-rolled when a maintained React/npm package or shadcn primitive fits.
- Graph data enrichment, including deterministic function operation edges and document section nodes, lives in core/indexing/graph services instead of React components.
- Core normalizes product graph nodes to `function`, `register`, `doc_section`, `pdf_section`, and `doc_box`, and product graph relations to the documented enum, with macro/field/source/provider wording carried in BoxMatrix-style attributes instead of rendered as nodes or relation drift.
- Stage 1 deterministic code graph generation is not conflated with Stage 2 LLM semantic-edge generation.
- Batch semantic-edge generation is exposed through core and thin API/MCP/Web routes rather than only a UI button or test helper, and generated semantic edges remain provenance-distinguishable from deterministic edges.
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
