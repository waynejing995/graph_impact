# ASIP Brainstorming Decisions

Date: 2026-05-16

## Project

- Project name: Graph Impact
- Concept: ASIC Semantic Intelligence Platform (ASIP)
- Repository: https://github.com/waynejing995/graph_impact
- Local folder: `/Volumes/data/User/wayne/Code/graph_impact`
- This is a new project and is not part of the PageIndex project.

## Source Idea

ASIP is intended to become a hardware semantic graph intelligence platform for GPU ASIC engineering. The long-term vision combines:

- Code
- Firmware
- Registers
- IP and ASIC topology
- Tests
- Runtime logs
- Documentation

The core premise is that traditional RAG cannot recover hidden hardware dependencies such as register ownership, execution ordering, power or clock dependencies, firmware-driver interactions, and ASIC-version-specific behavior.

## MVP Direction Chosen

We chose option 3 from the initial decomposition:

**Hybrid Retrieval MVP**

This MVP should focus on retrieval first, before attempting full ASIC semantic reasoning or root-cause analysis.

## First Data Sources

We chose option B:

**Documentation + code + register tables**

The first version should ingest and retrieve across these three source categories:

- Engineering documentation
- Source code
- Register tables/specs

Test logs, firmware deep modeling, and full RCA workflows are deferred.

## First Code Corpus Chosen

We chose to use real AMD GPU driver code for MVP-1 instead of a synthetic/private-safe corpus.

The first code corpus should include:

- The `amdgpu` driver subtree from the Linux source tree.
- The AMD MxGPU/GIM codebase at `https://github.com/amd/MxGPU-Virtualization`.

The exact Linux source tree location is expected to be:

```text
drivers/gpu/drm/amd/amdgpu
```

The exact MxGPU/GIM GitHub repository is:

```text
https://github.com/amd/MxGPU-Virtualization
```

This makes MVP-1 a real-code retrieval system from the start. Synthetic examples may still be used for unit tests, but not as the primary sample corpus.

## First Documentation Corpus Chosen

We chose documentation sources that align directly with the first code corpus:

- Linux kernel `amdgpu` documentation:

```text
Documentation/gpu/amdgpu.rst
```

- Documentation shipped in the AMD MxGPU/GIM repository:

```text
https://github.com/amd/MxGPU-Virtualization
README.md
docs/
```

- Inline kernel-doc and meaningful source comments near relevant `amdgpu` code paths should be captured as code evidence, not treated as a separate formal documentation source.

PDF documentation ingestion is in scope for MVP-1. The first implementation should support text-based PDFs with page-level citations and section-aware chunking. Complex scanned PDFs that require OCR can be deferred behind the same PDF ingestion interface.

PDF ingestion can use tools such as MarkItDown or a similar document-to-Markdown/text conversion pipeline. The preferred shape is to convert text-based PDFs into normalized Markdown/text with page metadata, then feed that output through the same documentation chunking and evidence pipeline used for `.rst`, Markdown, and repository docs.

A public AMD PDF candidate for MVP-1 smoke testing is:

```text
AMD Instinct MI300/CDNA3 Instruction Set Architecture
https://www.amd.com/content/dam/amd/en/documents/instinct-tech-docs/instruction-set-architectures/amd-instinct-mi300-cdna3-instruction-set-architecture.pdf
```

The user may also provide private or local AMD PDF documents later for additional testing.

## MVP-1 Goals Chosen

We confirmed the MVP-1 goals:

```text
G1. Ingest real AMD GPU engineering corpora:
Linux amdgpu subtree, amd/MxGPU-Virtualization, aligned docs, generated register headers, and at least one text-based AMD PDF.

G2. Normalize hardware/code/doc symbols:
Resolve register names, fields, wrappers, macro chains, function references, doc sections, PDF page/section references, IP hints, and ASIC/version hints into stable entities.

G3. Provide hybrid evidence retrieval:
Given a register, field, function, ASIC term, or documentation term, return ranked evidence from code, docs, PDFs, and register headers.

G4. Explain relationships:
Show why evidence items are related, including resolved macro/wrapper chains, register-field relationships, and doc/code links.

G5. Expose two first-class interfaces:
Web UI for exploration, MCP server for AI/coding-agent workflows.

G6. Keep resolver and model backends configurable:
Resolver profiles support repo/language-specific rules; embedding and semantic-edge models support local Ollama and OpenAI-compatible providers.
```

## MVP-1 Non-Goals Chosen

We confirmed the MVP-1 non-goals:

```text
NG1. No full root-cause analysis.
NG2. No firmware deep modeling.
NG3. No runtime log reasoning.
NG4. No scanned-PDF OCR as a hard MVP-1 requirement.
NG5. No hardcoded AMD-only resolver architecture.
NG6. No requirement to infer hidden hardware dependencies beyond evidence-supported relationships.
```

## First Register Source And Resolver Chosen

We confirmed that MVP-1 register ingestion is not a table-parser-only problem.

MVP-1 should use generated AMD register headers plus a macro-aware register resolver.

The first register sources should include generated register header files from the selected corpora, including these patterns where present:

```text
*_offset.h
*_d.h
*_sh_mask.h
*_default.h
```

The resolver must handle both Linux `amdgpu` and MxGPU/GIM register naming and access patterns:

- `mm*` and `reg*` register symbol aliases.
- `*_BASE_IDX` companion symbols.
- Field macros used by `REG_SET_FIELD` and `REG_GET_FIELD`.
- Direct register access wrappers such as `WREG32` and `RREG32`.
- SOC15 wrappers such as `WREG32_SOC15`, `RREG32_SOC15`, `WREG32_SOC15_OFFSET`, `RREG32_SOC15_OFFSET`, `SOC15_REG_OFFSET`, and `SOC15_REG_ENTRY`.
- Field write wrappers such as `WREG32_FIELD15`.
- MxGPU/GIM equivalents that use `adapt->reg_offset[...]` instead of Linux `adev->reg_offset[...]`.

The macro/access wrapper list must be configurable, not hardcoded. Different repositories may use different register access names, wrapper signatures, symbol prefixes, base-offset expressions, and device context variable names. MVP-1 should ship with initial resolver profiles for Linux `amdgpu` and AMD MxGPU/GIM, but the resolver engine should load these patterns from configuration.

The resolver system should be extensible beyond C/C++ macro expansion. Future corpora may be Python repositories or other non-macro codebases. In those cases, resolver profiles should be able to define language-appropriate extraction rules, such as imports, function calls, decorators, config keys, schema references, string constants, or framework-specific APIs. Macro expansion is one resolver strategy, not the whole ASIP resolver architecture.

This is required because many real register references are hidden behind macro expansion and wrapper layers. MVP-1 must resolve these layers well enough to answer "who reads/writes this register or field?" for the first supported corpus.

## Minimum Evidence Schema Chosen

We confirmed the minimum evidence schema for MVP-1 results.

Each returned evidence item should include at least:

```text
id
source_type: code | doc | pdf | register
repo
path
line_start
line_end
page
symbol
entity_type: function | register | field | macro | doc_section | pdf_section | doc_box
ip_block
asic_or_generation
access_type: read | write | read_modify_write | field_set | field_get | mention
confidence
snippet
resolved_chain
```

2026-05-18 implementation reconciliation: the original minimum schema above was
expanded by the final graph/evidence implementation. `pdf` is now a first-class
source type, and page-aware PDF evidence can surface as `pdf_section` nodes.
LLM-extracted document boxes use `doc_box` nodes. Product graph entity nodes
are intentionally narrower than raw evidence entities: visible graph nodes are
`function`, `register`, `doc_section`, `pdf_section`, and `doc_box`; fields,
macros, wrappers, source files, and callback slots are attributes/provenance,
not graph nodes.

`resolved_chain` is required because many useful register references are not direct symbols. It should explain how ASIP normalized a code reference into a hardware entity.

Example:

```text
WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp)
-> adev->reg_offset[GC_HWIP][0][regGCVM_L2_CNTL_BASE_IDX] + regGCVM_L2_CNTL
-> register GCVM_L2_CNTL
```

## MVP-1 Non-Negotiable Capability Chosen

We confirmed the first non-negotiable MVP capability:

Given a register name, function name, or ASIC term, return relevant evidence from documentation, code, and register tables, then explain the relationship between those evidence items.

Example query:

```text
What is SDMA0_RB_CNTL, where is it documented, and which code references it?
```

This keeps the first version focused enough to validate graph/vector/symbol hybrid retrieval without prematurely expanding into full debugging intelligence.

MVP-1 is not a root-cause analysis system. It is a register/symbol-centered hybrid evidence retrieval system that returns normalized evidence and explains relationships across docs, code, and register tables.

## First Interface Shape Chosen

We chose:

**Web UI + MCP server**

The first product surface should include:

- A Web UI for interactive engineering exploration, evidence browsing, and relationship inspection.
- An MCP server so ASIP can be used directly by coding agents and AI assistants inside engineering workflows.

CLI / Python API can still exist as internal developer utilities, but they are not the primary MVP user interface.

## Model Backend Direction Chosen

We chose a local-first model backend strategy for MVP-1.

Embedding should consider locally deployed Ollama models first.

If MVP-1 needs a small model to detect or classify semantic edges, such as inferred relationships between code, registers, fields, docs, and IP blocks, that model should also be deployable through Ollama.

The model integration layer must also support OpenAI-compatible API formats. This means ASIP should not hardcode Ollama-specific request and response handling into retrieval, embedding, or semantic-edge extraction logic. The implementation should use a provider abstraction that can target:

- Local Ollama deployments.
- OpenAI-compatible embedding/chat endpoints.

This keeps MVP-1 usable in local/private engineering environments while leaving room to switch to hosted or enterprise OpenAI-format services when needed.

## MVP-1 Architecture Direction Chosen

We confirmed that MVP-1 should be organized into five layers:

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

This separation is required so PDF ingestion, macro-aware register resolution, embedding/model providers, Web UI, and MCP tools do not become tightly coupled.

## Storage And Indexing Direction Chosen

We confirmed an SQLite-first storage and indexing direction for MVP-1.

MVP-1 should use:

```text
SQLite
SQLite FTS5
SQLite vector extension
```

The intended split is:

- SQLite tables for corpora, documents, symbols, evidence items, resolver profiles, graph edges, indexing jobs, and provider configuration.
- FTS5 for keyword/full-text search across code snippets, docs, PDF text, register headers, symbol names, and resolved-chain text.
- A SQLite vector extension for embedding search over evidence chunks and documentation/code/register text.

This keeps MVP-1 local-first, easy to inspect, easy to reset, and aligned with the Ollama/local deployment direction. It also avoids prematurely introducing a separate external graph database or vector service.

The default SQLite vector extension should be:

```text
sqlite-vec
```

The implementation should still use a vector-extension adapter so ASIP is not permanently tied to one SQLite vector implementation. Future adapters may target `sqlite-vss`, libSQL vector search, or another compatible backend.

## Graph Storage And Runtime Chosen

We confirmed that MVP-1 graph persistence should stay SQLite-first.

The persistent graph model should use SQLite tables such as:

```text
entities(id, type, name, canonical_name, repo, metadata)
edges(id, src_entity_id, dst_entity_id, relation_type, confidence, evidence_id, metadata)
```

NetworkX may be used as an in-memory graph runtime for traversal, subgraph extraction, metrics, and future reasoning utilities.

The intended split is:

- SQLite is the source of truth for persisted graph entities and edges.
- NetworkX is loaded from SQLite for local graph computation.
- Derived graph outputs can be written back to SQLite when useful.
- NetworkX pickles are not the primary graph storage format.

This preserves inspectability and SQL querying while still allowing practical graph algorithms during retrieval and analysis.

## Backend Service Shape Chosen

We confirmed the MVP-1 backend service shape:

```text
Python/FastAPI core + Next.js Web UI/BFF
```

Python/FastAPI should own:

- Corpus ingestion.
- PDF conversion and document chunking.
- Register header parsing.
- Resolver profiles and resolver execution.
- SQLite/FTS5/sqlite-vec indexing.
- NetworkX graph runtime.
- Embedding/model provider abstraction for Ollama and OpenAI-compatible APIs.
- Retrieval and reranking.
- MCP server integration or shared service logic used by MCP tools.

Next.js should own:

- The Web UI workbench.
- Client-side interaction state.
- Thin BFF routes if needed for UI-specific aggregation.

The core ASIP retrieval and indexing logic should not live only inside Next.js API routes.

## Repository Structure Direction Chosen

We confirmed a monorepo-style MVP-1 repository structure:

```text
apps/web        Next.js + shadcn/ui Web UI
apps/api        Python FastAPI service
apps/mcp        MCP server, reusing API/core logic where possible
packages/core   Shared Python ASIP core modules, or equivalent src/asip package if the Python toolchain prefers a flatter layout
data/           Local SQLite database, caches, downloaded corpora, converted PDFs
configs/        Resolver profiles, model provider configs, corpus configs
```

The intended ownership boundaries are:

- `apps/web` owns only the Web UI and UI-specific BFF glue.
- `apps/api` exposes ASIP backend service endpoints.
- `apps/mcp` exposes agent-facing tools.
- `packages/core` or the equivalent Python package owns reusable ingestion, resolver, indexing, retrieval, graph, and provider logic.
- `configs` keeps resolver/model/corpus behavior editable without code changes.

## Development Toolchain Chosen

We confirmed the MVP-1 development toolchain:

```text
Python: uv
Web: pnpm
Task runner: just
```

Expected command ownership:

- `uv` manages Python dependencies, virtual environments, scripts, and tests.
- `pnpm` manages the Next.js/shadcn UI workspace.
- `just` provides top-level project commands for setup, dev, indexing, tests, linting, and common workflows.

## MVP-1 Implementation Locks Chosen

We closed the remaining implementation choices required to make the design plan executable.

Python package layout:

```text
packages/core/src/asip
```

`packages/core` owns the reusable ASIP Python core. `apps/api` and `apps/mcp` are thin application packages that import the core. Retrieval, resolver, indexing, graph, PDF, and provider logic should not live only inside FastAPI routes, Next.js routes, or MCP tool handlers.

SQLite vector integration:

```text
sqlite-vec behind a VectorStore adapter
```

The adapter is the only layer that should contain extension-specific vector SQL. Unit and integration tests should use deterministic embedding fixtures and validate the adapter contract.

Ollama provider default:

```text
profile: ollama-local
sample embedding model: nomic-embed-text
```

The exact model name is configured in `configs/models/ollama-local.yaml`. Provider tests should mock Ollama and OpenAI-compatible HTTP responses so normal test runs do not require a running model server.

MCP server shape:

```text
apps/mcp as a separate process importing packages/core
```

The MCP server should reuse ASIP core logic directly for local operation and only call FastAPI when UI/session-specific service state is required.

Graph UI scope:

```text
right-inspector relationship panel first
```

MVP-1 should start with a bounded 1-2 hop relationship panel that shows entity neighbors, edge labels, confidence, and evidence links. A full interactive graph canvas is deferred until the evidence workbench and retrieval flow are stable.

The executable implementation plan is:

```text
docs/superpowers/plans/2026-05-16-asip-mvp1-implementation.md
```

## Local Ollama Model Deployment Chosen

We inspected the local development machine:

```text
CPU: Apple M4
Memory: 24GB
Ollama: installed
```

Existing larger models were present:

```text
qwen3-embedding:4b
qwen3.5:4b
```

`qwen3-embedding:4b` worked for embeddings but loaded with a much larger resident footprint than needed for MVP-1 smoke testing. `qwen3.5:4b` was too slow for the low-memory semantic-edge smoke path.

We deployed and verified smaller Ollama defaults:

```text
embedding: nomic-embed-text
semantic-edge JSON smoke: qwen2.5:1.5b
```

Verification results:

- `nomic-embed-text` returned a 768-dimensional embedding for `GCVM_L2_CNTL register field evidence`.
- `qwen2.5:1.5b` returned valid JSON in Ollama chat JSON mode for `GCVM_L2_CNTL has field ENABLE_L2_CACHE`.
- After the smoke tests, `ollama ps` was empty, confirming no model remained resident.

Default MVP-1 model policy:

- Use `nomic-embed-text` for low-memory local embeddings.
- Keep semantic-edge extraction disabled by default.
- Use `qwen2.5:1.5b` only for explicit semantic-edge tests/jobs.
- Configure short keep-alive values to avoid unnecessary memory pressure.
- Keep larger local models as optional profiles, not defaults.

## Browser-Controlled QA Chosen

We added browser-controlled QA as a required part of the design and implementation workflow.

The current design-plan QA target is a static workbench preview:

```text
docs/qa/asip-workbench-design-preview.html
```

The QA record is:

```text
docs/qa/2026-05-16-asip-browser-and-ollama-qa.md
```

Implementation must later run browser-controlled QA against the real Next.js app, not only the static design preview.

## Superpowers Execution Workflow Chosen

We confirmed that MVP-1 implementation should follow the Superpowers workflow:

- Use `superpowers:using-git-worktrees` before implementation begins.
- Use `superpowers:test-driven-development` for production code changes.
- Use `superpowers:subagent-driven-development` to execute the implementation plan.
- Dispatch one fresh implementer subagent per plan task.
- Give each implementer the exact task text and required context instead of making it rediscover the whole plan.
- Require RED/GREEN verification in every task: write the failing test, run it and confirm the expected failure, implement the minimal code, then run the passing test.
- After each implementation task, run two review gates: spec compliance review first, then code quality review.
- Do not move to the next task while either review gate still has open issues.

## Web UI Design Direction Chosen

We confirmed that the ASIP Web UI should be an engineering evidence workbench, not a marketing landing page.

We used GitHub search to inspect `VoltAgent/awesome-design-md` and reviewed several relevant `DESIGN.md` references, especially NVIDIA, ClickHouse, Linear, Ollama, Warp, VoltAgent, Cursor, and Vercel. The chosen ASIP direction combines:

- Linear/Warp-style precise dark engineering workspace.
- NVIDIA-style restrained hardware/accelerator accent.
- ClickHouse/VoltAgent-style dense code and evidence panels.
- Ollama-style local model/provider clarity.

The first screen should be the actual working product:

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

The UI should feel like an IDE/search workbench: dense, technical, fast to scan, and evidence-first.

## Web UI Technology Stack Chosen

We locked the Web UI technology stack:

```text
Next.js + shadcn/ui
```

Implementation should use shadcn/ui components and semantic theme tokens rather than custom one-off UI primitives. Expected component families include:

- Sidebar / navigation for the left rail.
- Command / input group for global search and query composition.
- Tabs / toggle groups for evidence filters.
- Table / scroll area / resizable panels for dense evidence browsing.
- Badge for source type, access type, confidence, provider status, and index status.
- Sheet or dialog for focused source preview and resolver-profile editing.
- Chart or graph-compatible container for relationship views.

## ASIP Color System Chosen

We locked a restrained ASIP color system for the first Web UI.

The palette should be dark-first, technical, and evidence-focused:

```text
canvas:        #080A0B
surface-1:     #0F1214
surface-2:     #151A1D
surface-3:     #1B2226
hairline:      #263036
hairline-strong:#39464D

ink:           #F3F7F8
ink-muted:     #AAB6BC
ink-subtle:    #6F7D84

primary:       #39D98A
primary-soft:  #A7F3D0
primary-deep:  #10B981

code:          #7DD3FC
register:      #FACC15
doc:           #C084FC
pdf:           #FB7185
graph-edge:    #60A5FA

success:       #22C55E
warning:       #F59E0B
error:         #EF4444
```

Color roles:

- `primary` is reserved for active navigation, primary actions, successfully resolved entities, and live provider/index status.
- `code`, `register`, `doc`, and `pdf` are small source-type indicators only, not large background fills.
- `graph-edge` highlights selected relationship paths.
- Error/warning/success colors are used only for operational status and validation.
- The UI should not use large gradients, decorative blobs, or marketing-style color fields.

## Acceptance Test Query Set Chosen

We confirmed the first MVP-1 acceptance test query set.

The first acceptance tests should cover register retrieval, field extraction, documentation evidence, macro/wrapper resolution, configurable resolver profiles, non-macro resolver extensibility, and model backend switching.

The initial acceptance queries/tests are:

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

## Package-First Frontend And Graph Decision

Decision date: 2026-05-17

We clarified an implementation rule after reviewing the Web graph route:

- All substantial frontend functionality should first look for an existing React/npm package or shadcn primitive before custom implementation.
- Hand-written components are allowed only for product-specific composition, state wiring, or small glue around package/shadcn primitives.
- The global graph must not be a hand-rolled SVG graph. It should use a maintained React graph visualization package and render live ASIP graph data with weight-aware edges.
- Candidate graph packages checked on 2026-05-17:
  - `react-force-graph-2d` 1.29.1, MIT, force-directed React graph component. Preferred first candidate for the Obsidian-style global graph.
  - `sigma` 3.0.3 with `graphology`, MIT, strong candidate for larger graph density/performance.
  - `@xyflow/react` 12.10.2, MIT, useful for node editors/flow charts but less directly aligned with an Obsidian-style relation graph.
- Next implementation should spike `react-force-graph-2d` first unless package/runtime evidence shows Sigma is the better fit.

This rule also applies outside graph rendering: resolver/profile editors, acceptance tables, accordions, settings forms, dialogs, empty states, and page layout should prefer shadcn/native package primitives over hand-built UI widgets.

## Global Graph Semantic Layers Decision

Decision date: 2026-05-17

The global ASIP graph must be more than a small relation preview or a direct dump of manually persisted graph edges. A useful default graph should connect the layers ASIC engineers reason across:

- code function nodes,
- register, field, macro, and wrapper nodes,
- source file nodes,
- Markdown/PDF document section nodes,
- semantic concept nodes generated by an LLM provider when that job has run.

Core graph generation should derive function operation edges from indexed code evidence. For example, an enclosing C/C++ function that reads, writes, or sets a register/field should produce a weighted `function -> register/field` edge with operation provenance.

Converted docs and PDFs should produce section/page nodes with heading, page, source path, and converter provenance. LLM semantic-edge generation should be able to use those section nodes as candidates, then persist generated semantic edges back into the same SQLite graph store.

Batch semantic-edge generation is a product feature, not only an offline QA helper. Query-scoped generation is still useful, but it cannot be the only path because the global graph needs potential semantic edges across the indexed corpus before a user selects one query seed.

## Open Questions

Open implementation questions:

- confirm the package spike result for `/graph` after testing `react-force-graph-2d` against the live global graph payload and the 2K visual anchor;
- confirm whether the batch semantic-edge default should run over all indexed candidates or over a capped, high-signal queue for MVP-1;
- confirm the minimum document-section granularity for converted PDFs: page nodes only, heading nodes only, or page-plus-heading nodes.

## Product Graph V2 Contract Decision

Decision date: 2026-05-19

This supersedes the earlier wording that allowed field, macro, wrapper, source
file, `doc_section`, `pdf_section`, or `doc_box` as visible product graph
nodes.

The default ASIP product graph is now exactly three node kinds:

- `function`
- `register`
- `doc`

Everything else is evidence or metadata:

- resolver wrappers and macros such as `WREG32`, `RREG32`, `REG_SET_FIELD`,
  `SOC15_REG_OFFSET`, `amdgv_wreg32`, and `gpu_register` live in provenance;
- register fields such as `ENABLE_L2_CACHE` live in node/edge attributes, and
  every field operation must still link the function to the owning register;
- callback slot/table names, source paths, corpus ids, provider names, model
  names, and local variables are not product nodes;
- Markdown sections, PDF sections, and BoxMatrix doc boxes are `kind=doc` with
  `attr.doc_kind=markdown_section|pdf_section|boxmatrix_box`.

The accepted graph architecture is three-layered:

1. Raw fact graph in SQLite, lossless and auditable.
2. Resolver-configured product projection over `function/register/doc`.
3. Web/API view graph with explicit budgets, filters, loaded counts, visible
   counts, and global/full controls.

Register identity defaults to `register:{ip}:{symbol}`. `ip_version` is an
attribute/provenance item, so linux-amdgpu and MxGPU can connect through the
same register when IP and symbol match. Different IP blocks do not merge.

Function normalization is allowed only through resolver YAML. Versioned
functions such as `gfxhub_v11_5_0_gart_enable` can merge into a concept
function only when the rule preserves raw implementations and edge provenance.
Different register neighborhoods are not discarded; they become union edges
and may mark the concept `divergent` or `split_recommended`.

Stage 1 and Stage 2 remain separate:

- Stage 1 deterministic graph owns code-aware function/register/callback facts
  and must describe its actual provenance, such as source spans, preprocessor
  expansion, selective `clang_ast_json`, or typed extractor. It must not claim
  full clangd/libclang cross-TU flow until implemented and tested.
- Stage 2 LLM graph owns doc boxes and semantic edges over existing product
  endpoints. It uses configured Ollama/OpenAI-compatible calls, not BoxMatrix
  skills. BoxMatrix only provides the schema inspiration: `inputs`, `outputs`,
  `constraints`, and explicit relationships.

The immediate implementation plan is
`docs/superpowers/plans/2026-05-19-product-graph-v2-implementation.md`.

## Brainstorming Method

We installed the `grill-me` skill and will use it to stress-test decisions one question at a time. Each question should include a recommended answer, then wait for confirmation before moving deeper.
