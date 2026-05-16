# ASIP MVP-1 Design

Date: 2026-05-16
Status: Ready for MVP-1 implementation

## 1. Summary

ASIP MVP-1 is a register/symbol-centered hybrid evidence retrieval system for AMD GPU engineering corpora.

MVP-1 is not a root-cause analysis system. Its job is to ingest real AMD GPU code, documentation, generated register headers, and text-based PDFs; normalize hardware/code/doc entities; retrieve ranked evidence; and explain how evidence items relate.

The first product surfaces are:

- Web UI: an engineering evidence workbench.
- MCP server: agent-facing access to ASIP retrieval and evidence APIs.

## 2. Goals

G1. Ingest real AMD GPU engineering corpora:

- Linux `amdgpu` subtree.
- `amd/MxGPU-Virtualization`.
- Aligned repo docs.
- Generated AMD register headers.
- At least one text-based AMD PDF.

G2. Normalize hardware/code/doc symbols:

- Register names.
- Register fields.
- Register access wrappers.
- Macro chains.
- Function references.
- Documentation sections.
- PDF page/section references.
- IP hints.
- ASIC/version hints.

G3. Provide hybrid evidence retrieval:

Given a register, field, function, ASIC term, or documentation term, return ranked evidence from code, docs, PDFs, and register headers.

G4. Explain relationships:

Show why evidence items are related, including resolved macro/wrapper chains, register-field relationships, and doc/code links.

G5. Expose two first-class interfaces:

- Web UI for exploration.
- MCP server for AI/coding-agent workflows.

G6. Keep resolver and model backends configurable:

- Resolver profiles support repo/language-specific rules.
- Embedding and semantic-edge models support local Ollama and OpenAI-compatible providers.

## 3. Non-Goals

NG1. No full root-cause analysis.

NG2. No firmware deep modeling.

NG3. No runtime log reasoning.

NG4. No scanned-PDF OCR as a hard MVP-1 requirement.

NG5. No hardcoded AMD-only resolver architecture.

NG6. No requirement to infer hidden hardware dependencies beyond evidence-supported relationships.

## 4. First Corpus

### Code

Linux source tree:

```text
drivers/gpu/drm/amd/amdgpu
```

AMD MxGPU/GIM:

```text
https://github.com/amd/MxGPU-Virtualization
```

### Documentation

Linux kernel `amdgpu` docs:

```text
Documentation/gpu/amdgpu.rst
```

MxGPU/GIM repo docs:

```text
README.md
docs/
```

Inline kernel-doc and meaningful source comments are captured as code evidence.

### PDF

MVP-1 supports text-based PDF ingestion. PDF conversion may use MarkItDown or a similar document-to-Markdown/text pipeline. Converted output should preserve page metadata and feed into the same documentation chunking/evidence pipeline used for `.rst`, Markdown, and repo docs.

Public AMD PDF smoke-test candidate:

```text
AMD Instinct MI300/CDNA3 Instruction Set Architecture
https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/instruction-set-architectures/amd-instinct-mi300-cdna3-instruction-set-architecture.pdf
```

### Register Headers

MVP-1 uses generated AMD register headers and a macro-aware resolver.

Initial header patterns:

```text
*_offset.h
*_d.h
*_sh_mask.h
*_default.h
```

The parser should capture:

- `mm*` and `reg*` aliases.
- `*_BASE_IDX` symbols.
- Register offsets.
- Field masks and shifts.
- Default values when present.
- IP/version hints from path and filename.
- Source path and line references.

## 5. Architecture

MVP-1 is organized into five layers.

```text
1. Ingestion Layer
   Clone/load repositories, documentation, PDFs, generated register headers, and local user-provided corpora.

2. Resolver Layer
   Run repository/language-specific resolver profiles, including C/C++ register/macro resolvers and future Python/non-macro resolvers.

3. Index Layer
   Maintain the symbol index, evidence store, vector index, and graph edges.

4. Retrieval Layer
   Combine exact symbol lookup, resolver output, graph expansion, vector search, and reranking.

5. Interface Layer
   Expose the Web UI and MCP server as first-class product surfaces.
```

This split keeps PDF ingestion, macro-aware register resolution, embedding/model providers, Web UI, and MCP tools loosely coupled.

## 6. Repository Layout

```text
apps/web        Next.js + shadcn/ui Web UI
apps/api        Python FastAPI service
apps/mcp        MCP server, reusing API/core logic where possible
packages/core   Shared Python ASIP core modules, or equivalent src/asip package if the Python toolchain prefers a flatter layout
data/           Local SQLite database, caches, downloaded corpora, converted PDFs
configs/        Resolver profiles, model provider configs, corpus configs
```

Ownership:

- `apps/web` owns only the Web UI and UI-specific BFF glue.
- `apps/api` exposes ASIP backend service endpoints.
- `apps/mcp` exposes agent-facing tools.
- `packages/core` or equivalent Python package owns reusable ingestion, resolver, indexing, retrieval, graph, and provider logic.
- `configs` keeps resolver/model/corpus behavior editable without code changes.

## 7. Toolchain

```text
Python: uv
Web: pnpm
Task runner: just
```

Expected top-level commands:

```text
just setup
just dev
just api
just web
just mcp
just index
just test
just lint
```

## 8. Storage And Indexing

MVP-1 is SQLite-first.

```text
SQLite
SQLite FTS5
sqlite-vec
```

SQLite owns:

- Corpora.
- Documents.
- Chunks.
- Symbols.
- Evidence items.
- Resolver profiles.
- Graph entities and edges.
- Indexing jobs.
- Provider configuration.

FTS5 owns:

- Keyword/full-text search across code snippets, docs, PDF text, register headers, symbol names, and resolved-chain text.

`sqlite-vec` owns:

- Embedding search over evidence chunks and documentation/code/register text.

Vector search must go through an adapter so ASIP can later support `sqlite-vss`, libSQL vector search, or another compatible backend.

## 9. Graph Model

SQLite is the persistent graph store. NetworkX is the in-memory graph runtime.

Suggested persistent tables:

```text
entities(id, type, name, canonical_name, repo, metadata)
edges(id, src_entity_id, dst_entity_id, relation_type, confidence, evidence_id, metadata)
```

NetworkX may be used for:

- Traversal.
- Subgraph extraction.
- Shortest paths.
- Connected components.
- Metrics.
- Future reasoning utilities.

Derived graph outputs can be written back to SQLite. NetworkX pickles are not the primary graph storage format.

## 10. Resolver Profiles

Resolver behavior must be configurable, not hardcoded.

Initial resolver profiles:

- Linux `amdgpu`.
- AMD MxGPU/GIM.

The C/C++ register resolver should support:

- `WREG32` / `RREG32`.
- `WREG32_SOC15` / `RREG32_SOC15`.
- `WREG32_SOC15_OFFSET` / `RREG32_SOC15_OFFSET`.
- `SOC15_REG_OFFSET`.
- `SOC15_REG_ENTRY`.
- `WREG32_FIELD15`.
- `REG_SET_FIELD` / `REG_GET_FIELD`.
- `adev->reg_offset[...]` and `adapt->reg_offset[...]` forms.

The profile config should define:

- Wrapper names.
- Argument positions and meanings.
- Symbol prefixes such as `mm` and `reg`.
- Base-index companion suffixes.
- Context variable names.
- Register base-offset expression templates.
- Field set/get rules.

Resolver profiles must also support non-macro languages. A future Python profile may extract imports, function calls, decorators, config keys, schema references, string constants, or framework-specific APIs.

## 11. Evidence Schema

Each evidence item includes at least:

```text
id
source_type: code | doc | register | pdf
repo
path
line_start
line_end
symbol
entity_type: function | register | field | macro | doc_section
ip_block
asic_or_generation
access_type: read | write | read_modify_write | field_set | field_get | mention
confidence
snippet
resolved_chain
```

`resolved_chain` explains how ASIP normalized an indirect code reference into a hardware/doc entity.

Example:

```text
WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp)
-> adev->reg_offset[GC_HWIP][0][regGCVM_L2_CNTL_BASE_IDX] + regGCVM_L2_CNTL
-> register GCVM_L2_CNTL
```

## 12. Model Backends

MVP-1 uses a local-first provider strategy.

Default direction:

- Embeddings through locally deployed Ollama models.
- Optional semantic-edge detection/classification through Ollama.
- OpenAI-compatible embedding/chat endpoints through the same provider abstraction.

Retrieval, embedding, and semantic-edge extraction must not hardcode Ollama-specific request/response logic.

Local model deployment lock for this development machine:

- Machine inspected on 2026-05-16: Apple M4, 24GB memory.
- Default low-memory embedding model: `nomic-embed-text`, verified through Ollama HTTP embeddings API with 768-dimensional output.
- Default low-memory semantic-edge model: `qwen2.5:1.5b`, verified through Ollama chat JSON mode for a simple register-field edge extraction.
- Semantic-edge extraction is disabled by default and loaded only for explicit acceptance tests or configured extraction jobs.
- Ollama `keep_alive` should be short (`30s` for embeddings, `0s` for semantic-edge smoke tests) so models are not kept resident unnecessarily.
- Existing larger models such as `qwen3-embedding:4b` and `qwen3.5:4b` may remain optional profiles, but they are not the MVP-1 default because they use more memory.

## 13. Web UI

Technology:

```text
Next.js + shadcn/ui
```

The UI is an evidence workbench, not a landing page.

Layout:

```text
Top bar:
Project/corpus selector, global symbol search, model backend status, indexing status.

Left rail:
Evidence Search
Graph Explorer
Corpus
Resolver Profiles
Acceptance Tests
Settings

Main center:
Query composer and filters
Evidence result list grouped by code / register / doc / PDF
Each result shows symbol, source path, lines/page, access type, confidence.

Right inspector:
Selected evidence detail
Resolved chain
Register fields
Related entities
Source preview
Mini relationship graph
```

Design direction:

- Linear/Warp-style precise dark engineering workspace.
- NVIDIA-style restrained hardware accent.
- ClickHouse/VoltAgent-style dense code and evidence panels.
- Ollama-style local model/provider clarity.

Color system:

```text
canvas:         #080A0B
surface-1:      #0F1214
surface-2:      #151A1D
surface-3:      #1B2226
hairline:       #263036
hairline-strong:#39464D

ink:            #F3F7F8
ink-muted:      #AAB6BC
ink-subtle:     #6F7D84

primary:        #39D98A
primary-soft:   #A7F3D0
primary-deep:   #10B981

code:           #7DD3FC
register:       #FACC15
doc:            #C084FC
pdf:            #FB7185
graph-edge:     #60A5FA

success:        #22C55E
warning:        #F59E0B
error:          #EF4444
```

Rules:

- Use shadcn/ui components and semantic theme tokens.
- Avoid custom one-off primitives unless a local component abstraction is clearly justified.
- Keep results dense and scannable like an IDE/search panel.
- Use source-type colors as small indicators, not large fills.
- Do not use large gradients, decorative blobs, or marketing-style color fields.

## 14. API And MCP

FastAPI should expose stable service endpoints for:

- Corpus registration.
- Indexing jobs.
- Query/retrieval.
- Evidence lookup.
- Entity lookup.
- Graph expansion.
- Resolver profile validation.
- Provider configuration and status.

The MCP server should reuse core service logic and expose agent-facing tools such as:

- Search evidence.
- Explain symbol.
- Get resolved chain.
- Expand graph neighborhood.
- Inspect resolver profile.
- Run acceptance test query.

## 15. Testing Strategy

Testing is a first-class MVP-1 requirement.

### Unit Tests

Register header parser:

- Parse `*_offset.h`, `*_d.h`, `*_sh_mask.h`, and `*_default.h` fixtures.
- Extract `mm*` and `reg*` aliases.
- Pair registers with `*_BASE_IDX`.
- Extract field masks/shifts.
- Preserve source path and line numbers.

Resolver profiles:

- Load wrapper definitions from config.
- Resolve `WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp)` into `GCVM_L2_CNTL`.
- Resolve `REG_SET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE, 1)` into field evidence.
- Verify wrapper rename/addition works without code changes.
- Verify Linux `adev` and MxGPU `adapt` context patterns.
- Verify a toy Python resolver profile can extract a configured call/string symbol without macro logic.

PDF/document ingestion:

- Convert a small text-based PDF fixture into normalized text/Markdown.
- Preserve page metadata.
- Chunk sections deterministically.
- Ensure PDF chunks enter the same evidence pipeline as Markdown/RST docs.

Model providers:

- Mock Ollama embedding/chat responses.
- Mock OpenAI-compatible embedding/chat responses.
- Verify provider switching does not affect retrieval code paths.

Storage/indexing:

- Create and migrate SQLite schema.
- Insert evidence/entities/edges.
- Query FTS5 index.
- Query sqlite-vec adapter through a small embedding fixture.
- Build a NetworkX graph from SQLite edges and compute a small traversal.

### Integration Tests

Use a small deterministic fixture corpus derived from representative AMDGPU/MxGPU patterns. The fixture should be small enough for CI and should not require network access.

Integration tests should cover:

- Ingest fixture code, docs, register headers, and one PDF fixture.
- Run resolver profiles.
- Build SQLite tables, FTS5 indexes, vector indexes, and graph edges.
- Execute hybrid retrieval.
- Return evidence items with the minimum schema.
- Return resolved chains.
- Expand 1-2 hop graph neighborhoods.
- Switch vector/provider adapters through config.

### Acceptance Tests

The first acceptance query/test set:

```text
1. Who reads or writes regGCVM_L2_CNTL?

2. Which fields of GCVM_L2_CNTL are set in MxGPU gfx_v11_0.c?

3. Where is IH_RB_CNTL configured, and which fields are modified?

4. Which code paths reference SDMA0_QUEUE0_RB_CNTL or SDMA1_QUEUE0_RB_CNTL?

5. Show evidence connecting amdgpu documentation to the amdgpu driver source tree.

6. Given WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp), explain the resolved register entity and macro expansion chain.

7. Change the resolver profile to add or rename one C/C++ register access wrapper, then verify the same resolver engine can resolve it without code changes.

8. Add a toy Python resolver profile that extracts a configured function-call or string-symbol reference, proving resolver profiles are not limited to macro expansion.

9. Run embedding and optional semantic-edge extraction through a configured Ollama provider, then switch to an OpenAI-compatible provider without changing retrieval or resolver code.
```

### API And MCP Tests

FastAPI:

- Query endpoint returns evidence schema.
- Evidence detail endpoint returns source location and resolved chain.
- Graph endpoint returns entity/edge neighborhood.
- Provider status endpoint reflects configured backend.

MCP:

- Tool schema validation.
- Search evidence tool returns structured evidence.
- Explain symbol tool includes resolved chain.
- Graph expansion tool returns bounded graph neighborhoods.
- Acceptance test runner tool reports pass/fail with evidence links.

### Web UI Tests

Use Playwright for the Web UI once the app exists.

Browser-controlled QA is required for Web UI completion. The implementation workflow must open the real local app in a browser, inspect desktop and narrow viewports, capture a screenshot or accessibility snapshot, and verify the workbench is not a marketing landing page.

UI tests should verify:

- The first screen is the evidence workbench, not a landing page.
- Left rail navigation renders.
- Query composer and filters work.
- Evidence list groups code/register/doc/PDF results.
- Right inspector shows selected evidence, resolved chain, source preview, and related entities.
- Provider/indexing status is visible.
- Resolver profile screen can preview a config change.
- Responsive layout remains usable on laptop and narrow widths.

Visual checks should ensure:

- ASIP color tokens are applied.
- Source-type colors are indicators, not large background fills.
- Text does not overflow compact panels.
- Dense evidence rows remain scannable.

### Performance Smoke Tests

Initial local smoke targets:

- Small fixture indexing completes in seconds.
- Query over fixture corpus returns in under one second on a developer machine.
- SQLite database can be deleted and rebuilt deterministically.

Real-corpus performance targets should be set after first indexing benchmarks.

## 16. Implementation Phases

Phase 0: Project scaffold

- Monorepo layout.
- `uv`, `pnpm`, `just`.
- SQLite schema skeleton.
- shadcn/Next.js app shell.

Phase 1: Ingestion and storage

- Corpus config.
- Repo/docs/PDF ingestion.
- SQLite evidence/doc/chunk tables.
- FTS5 setup.

Phase 2: Register and resolver core

- Register header parser.
- Configurable resolver profiles.
- Linux amdgpu and MxGPU initial profiles.
- Evidence and resolved-chain output.

Phase 3: Retrieval

- Exact symbol search.
- FTS5 search.
- sqlite-vec adapter.
- NetworkX graph expansion.
- Hybrid merge/rank.

Phase 4: Interfaces

- FastAPI endpoints.
- MCP tools.
- Web UI workbench.

Phase 5: Tests and acceptance hardening

- Unit/integration/acceptance tests.
- Playwright UI checks.
- Provider-switching tests.
- Real-corpus smoke run.

## 17. Implementation Locks

These choices close the MVP-1 design plan and are reflected in the implementation plan.

Python package layout:

- `packages/core/src/asip` is the reusable Python core package.
- `apps/api` and `apps/mcp` are thin application packages that import `asip`.
- Shared retrieval, resolver, indexing, graph, PDF, and provider logic must not live only inside `apps/api` or `apps/web`.

SQLite vector packaging:

- MVP-1 uses `sqlite-vec` through a `VectorStore` adapter.
- Tests use a deterministic small embedding fixture and exercise the adapter contract.
- The adapter is the only code path allowed to call extension-specific vector SQL.

Ollama provider default:

- The default local provider profile is named `ollama-local`.
- The embedding model name is configured in `configs/models/ollama-local.yaml`; the shipped sample value is `nomic-embed-text`.
- Provider tests mock HTTP responses so unit and integration tests do not require a running local model.

MCP process shape:

- `apps/mcp` runs as a separate MCP server process.
- It imports `packages/core` directly for local operation and may call the FastAPI service only for UI/session-specific state.

Graph UI scope:

- MVP-1 starts with a bounded relationship panel inside the right inspector.
- The panel shows selected entity, 1-2 hop neighbors, edge labels, confidence, and evidence links.
- A full interactive graph canvas is deferred until the evidence workbench and retrieval flow are stable.

Browser QA scope:

- The design preview and future Web UI must be validated with real browser control.
- QA must check desktop and narrow viewports, left rail, global search, evidence rows, inspector, relationship panel, provider/index status, and source-type indicators.
- QA evidence should be recorded under `docs/qa/`.

Executable implementation plan:

```text
docs/superpowers/plans/2026-05-16-asip-mvp1-implementation.md
```
