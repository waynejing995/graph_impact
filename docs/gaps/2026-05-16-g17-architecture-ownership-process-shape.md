# G17 Architecture Ownership And Process Shape

Status: Blocking

## Requirement

The implementation must preserve the architecture locks from the MVP-1 design:

- `packages/core/src/asip` owns reusable ingestion, resolver, indexing, retrieval, graph, PDF, and provider logic.
- `apps/api` and `apps/mcp` are thin application packages over the core.
- Next.js routes are BFF/product routes, not the only home of ASIP retrieval logic.
- `sqlite-vec` or vector-extension SQL is accessed only through an adapter boundary.
- NetworkX is loaded from SQLite graph data for runtime graph computation; SQLite remains the persistent graph store.
- `apps/mcp` can run as a separate MCP server process and imports core logic directly for local operation.
- Production code changes follow TDD and final verification, not progress-only claims.

## Current Evidence

- Core logic now exists under `packages/core/src/asip` for storage, workbench services, documents, resolver profiles, providers, and indexing artifacts.
- Next.js API routes call the core CLI path rather than embedding all retrieval logic directly in React.
- FastAPI and MCP packages exist and have tests over live SQLite query/graph behavior.
- NetworkX-backed graph expansion exists in core.
- Native `sqlite-vec` is still skipped when the extension cannot load, and vector fallback behavior remains partial.
- Final-candidate architecture review is recorded in `docs/qa/2026-05-17-final-clean-evidence-package.md`, mapping corpus/indexing, PDF conversion, resolver profiles, retrieval, SQLite/FTS/vector, NetworkX, semantic-edge generation, provider settings, FastAPI, MCP, Web BFF, and React UI to their owning layers and tests.
- `apps/mcp/server.py` now has a tool-matrix registration test covering all implemented product tools; the optional external `mcp` runtime package remains skipped when absent.

## Remaining Gap

The repo now has an explicit architecture review in the final-candidate QA package. Completion still requires the final git gate, and any later architecture-affecting edits must update that review.

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

## Acceptance Criteria

- Final review maps each major capability to its owning layer: core, API, MCP, Web BFF, or React UI.
- Shared retrieval/resolver/indexing/PDF/provider logic is not implemented only inside Web routes or UI components.
- Vector extension access is isolated behind the storage/vector adapter contract, or native vector work is explicitly deferred in G09/G13.
- MCP server tools are tested as tool functions and, where dependencies permit, as a runnable server process.
- API routes and MCP tools avoid unexpected state mutation in read-style operations, or the initialization behavior is explicitly accepted and documented.
- TDD evidence exists for production code changes, and docs-only changes are clearly identified as docs-only.

## Required Tests And Checks

- Architecture review checklist in the final QA doc.
- `git diff --check` plus full test/build/lint suite before completion.
- API/MCP tests proving app layers call core behavior rather than duplicated fixture-only code.
- Review of generated/local artifacts before staging.

## Not Closed Until

The final review can point to the core owner for every ASIP capability, show that app layers are thin, and identify any consciously deferred architecture lock.
