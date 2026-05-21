# ASIP Graph Integration Plan

Date: 2026-05-19
Status: Design and execution plan with targeted resolver/profile normalization fixes landed; full clean/browser/e2e gate remains open

## Purpose

This document consolidates the latest graph, schema, indexing, UI, and
performance decisions after the 2026-05-19 subagent audit. It is now the
working source of truth for the next implementation slice.

The companion current final gate is
[`2026-05-19-current-graph-finalization-plan.md`](2026-05-19-current-graph-finalization-plan.md).
Use that document when deciding whether the current tree has enough QA/test
evidence to claim closure.

The user-visible goal is simple: the ASIP graph must look and behave like a
real global relationship graph, while the underlying data remains auditable
from indexed AMD/MxGPU code, register headers, Markdown/PDF documentation, and
LLM-generated semantic overlays.

## 2026-05-19 User Requirement Consolidation

This document also folds in the latest user requirements from the current gap,
spec, and QA review. The contract below supersedes older wording in gap or QA
files when they still describe `doc_section`, `pdf_section`, `doc_box`, macro
wrappers, resolver helpers, fields, or source paths as visible graph entities.

The product graph has one visible entity contract across CLI, API, MCP, Web,
browser QA, and acceptance output:

- Stage 1 deterministic graph output exposes only `function`, `register`, and
  `doc` nodes.
- Macro calls, resolver wrapper calls, callback slot names, field-only symbols,
  source paths, provider names, model names, corpus ids, local variables, and
  helper expressions never become product nodes.
- Macro/resolver/callback facts are still first-class evidence. They must be
  preserved in edge provenance, `edge.attr`, node `attr`, inspector expansion,
  resolved chains, and QA artifacts.
- Stage 2 LLM work can only add semantic edges and BoxMatrix-style doc boxes
  that project back to the same three node kinds.
- Register and function normalization are product projection rules, not raw
  fact rewrites. Raw SQLite evidence remains lossless and expandable.
- A single logical corpus can include multiple repo subfolders, including code
  roots and sibling register-header roots.
- Graph size, progressive loading, and weight filtering are configuration and
  UI concerns. They must not be hidden hardcoded defaults.
- Web implementation uses shadcn/Radix primitives for standard controls and a
  maintained graph renderer package for the graph surface, with per-route
  visual-anchor QA in light and dark themes.

Execution implication: the next implementation pass must prove this contract
with schema validation and no-mock browser evidence before any "graph gap
closed" claim.

Evidence implication: 2026-05-18 clean-final artifacts are candidate evidence
for the current branch, not an automatic 2026-05-19 close. Current closure
requires a fresh final package that names the DB path, provider, schema
validator result, no-mock browser/e2e result, API/MCP/Web parity, visual QA,
performance profile, and accepted residuals. Current clean semantic provider
evidence is `gemma4:e4b`; qwen artifacts are historical comparison evidence.

## Current Implementation Status

This plan is the target contract, not a completion claim. The active
implementation slice is currently focused on two no-mock closure items:

- product projection must convert legacy document subtypes
  `doc_section`/`pdf_section`/`doc_box` to `kind: "doc"` with
  `attr.doc_kind`;
- Web/Playwright no-mock e2e must pass an explicit DB path through URL/API
  controls so `/graph` can be verified against a real SQLite DB instead of a
  mock, fixture shortcut, or stale default DB.

Existing Stage 1, Stage 2, package renderer, acceptance, and visual QA evidence
remains useful, but this document must not be read as saying the integrated
three-kind product schema and URL `dbPath` e2e gate are already fully closed.

## Subagent Inputs

- Archimedes audited the product graph schema and found that the current spec
  mixes five visible node kinds with the newer user requirement for three
  conceptual entity kinds. This plan resolves that mismatch.
- Wegener audited Stage 1 extraction and found the current code is a pragmatic
  clang command plus text-span/callback pipeline, not full clangd/libclang
  cross-translation-unit type flow. This plan keeps that distinction explicit.
- Copernicus audited Web/performance/e2e and found the profiling must be
  layered across browser rendering, Next BFF spawn/JSON parsing, Python query,
  SQLite/NetworkX graph extraction, and acceptance aggregation.
- Plato audited the resolver/profile-scoped normalization slice and found three
  P1 issues: concept ids needed profile namespace, disabled DB aliases had to
  disable the loaded profile id too, and `graph.register_normalization` had to
  affect product register identity rather than only parse.

## External Baselines

The design follows these outside references:

- Joern Code Property Graph: use a typed, labeled, attributed multigraph and
  derived overlays instead of mutating raw facts into one lossy graph:
  <https://docs.joern.io/code-property-graph/>.
- Sourcegraph SCIP: start with minimal source occurrences, then add semantic
  features progressively with snapshot-style tests:
  <https://sourcegraph.com/docs/code-search/code-navigation/writing_an_indexer>.
- Clang JSON Compilation Database: AST-based tooling needs the exact compile
  command, working directory, source file, and include/define context for each
  translation unit:
  <https://clang.llvm.org/docs/JSONCompilationDatabase.html>.
- Sigma/Graphology: large interactive graph rendering benefits from a graph
  model plus renderer-level reducers/filters instead of mutating the source
  graph for every visual interaction:
  <https://www.sigmajs.org/docs/advanced/data/>.
- Cytoscape.js performance guidance: large graph interaction should avoid
  unnecessary style/layout recomputation and should treat viewport-time visual
  simplification as renderer state, not as source graph mutation:
  <https://js.cytoscape.org/>.

## Adopted Architecture After 2026-05-19 Audit

The current design decision is a three-layer graph, not one overloaded graph:

1. **Raw fact graph** in SQLite keeps every deterministic and LLM-produced fact
   that is useful for audit: raw function names, resolver wrapper names,
   fields, callback slots, table/receiver provenance, source paths, line
   ranges, provider/model/job ids, and original relation/access strings.
2. **Product graph projection** turns raw facts into the default ASIP entity
   contract: only `function`, `register`, and `doc` nodes, enum-bound edges,
   and BoxMatrix-style `in`, `out`, and `attr` payloads. Projection is
   resolver-profile-controlled and never deletes raw facts.
3. **View graph** is the Web/API rendering budget over the product graph. It
   decides loaded budget, visible budget, weight threshold, relation/stage/source
   filters, label density, and global/full modes. A view graph is never allowed
   to change what the source graph means.

This structure is the answer to the latest graph-quality issues:

- Macro and resolver wrappers such as `WREG32`, `RREG32`, `REG_SET_FIELD`,
  `SOC15_REG_OFFSET`, `amdgv_wreg32`, and `gpu_register` are resolver evidence,
  not nodes.
- Register fields such as `ENABLE_L2_CACHE` are folded into
  `register.attr.fields`, `edge.attr.fields`, and function `out` summaries; a
  field operation must still create a traceable `function -> register` edge.
- Callback slots, ops table names, source files, corpus ids, provider names,
  model names, and local variables are provenance only.
- Same-register bridges across linux-amdgpu and MxGPU are preserved by
  `register:{ip}:{symbol}` product identity; `ip_version` is an attribute and
  per-source provenance unless a resolver profile explicitly says otherwise.
- Function variants may collapse into concept functions only through resolver
  YAML rules. Divergent register neighborhoods are preserved as union edges and
  marked `divergent` or `split_recommended` according to merge-policy
  thresholds.

Implementation ownership:

- Core schema constants and relation normalization should move into a shared
  Python module such as `packages/core/src/asip/graph_schema.py`, then be reused
  by deterministic extraction, semantic persistence, storage projection,
  acceptance validation, FastAPI, MCP, and Web tests.
- The current Stage 1 extractor remains truthfully named as source-span,
  clang-preprocess, selective `clang_ast_json`, direct-call, and conservative
  callback evidence. It is not full clangd/libclang cross-translation-unit type
  flow until a typed extractor lands with compile-database coverage metrics.
- Register prefix handling belongs in resolver/profile configuration. AMD
  forms including `reg*`, `mm*`, `smn*`, offset/mask/default namespaces, and
  mixed-case examples such as `smnMP1_FIRMWARE_FLAGS` should be accepted only
  when they match configured register inventory rules; low-signal lowercase
  locals such as `tmp`, `adapt`, and `value` stay rejected.
- Stage 2 doc and semantic generation uses LLM calls through the configured
  provider. BoxMatrix is the schema inspiration (`inputs`, `outputs`,
  `constraints`, relationships), not a runtime skill dependency for ASIP.
- Acceptance surface labels are not enough. The runner must record per-surface
  probe results for CLI/core, FastAPI, MCP, and Web BFF or explicitly label a
  Web probe as covered by a no-mock Playwright browser test with the DB path.
- Global graph performance is handled by profile-first optimization:
  browser timing, Next BFF spawn/JSON time, Python query/global-graph time,
  SQLite/NetworkX time, payload size, and canvas readiness must be measured
  before changing budgets or renderer settings.

## Immediate Implementation Slices

The next implementation work should proceed in this order:

1. **Schema module and validator.** Centralize allowed node kinds, relation
   enum, provenance-only relation names, endpoint rejection, and relation
   normalization. Add tests that fail if `macro`, `field`, `source`, provider,
   or local-variable endpoints reach default product output.
2. **Stage 1 truth and register inventory.** Keep current deterministic graph
   extraction but expose exact provenance mode per edge. Add configurable
   register inventory rules for AMD `reg/mm/smn` families and prove helper-only
   calls do not create fake register nodes.
3. **Typed callback roadmap.** Add red tests for same slot name on different
   receiver types, cross-file initializer tables, and ambiguous dispatch.
   Implement only typed evidence that can be proven; mark ambiguous callback
   edges with lower-confidence provenance instead of presenting them as exact.
4. **Function/register normalization hardening.** Keep resolver-profile-scoped
   concept ids, union raw implementations, keep shared-register bridges, and
   split or flag low-overlap variants instead of hiding differences.
5. **Doc and LLM semantic projection.** Convert Markdown/PDF sections into
   `kind=doc`; make doc-box extraction produce BoxMatrix-style `doc` nodes;
   restrict LLM edge endpoints to product entities; make prompts use the same
   edge enum as storage.
6. **Real acceptance surfaces.** Extend the acceptance runner from
   `surfaces_checked` labels to `surface_results` with transport, DB path,
   row count, graph count, schema status, and failure reason.
7. **Global graph UI controls.** Keep package rendering. Expose budgeted/global
   and explicit full/all modes, relation/stage/source filters, weight slider,
   visible node/edge budgets, function view, and loaded/visible/total counts
   through shadcn/Radix controls.
8. **Profile before optimizing.** Capture baseline profiles for one slow query
   and one global graph load before adding cache, precomputed summaries,
   streamed/paged graph payloads, warm workers, or renderer-level reducers.

Each slice must land with RED/GREEN tests and current QA notes. Historical
qwen artifacts or static visual mocks cannot close these slices.

## Product Entity Contract

The product graph has exactly three conceptual node kinds:

- `function`
- `register`
- `doc`

This applies to both the Stage 1 deterministic product projection and the
Stage 2 semantic overlay. Stage-specific producers may store richer raw facts,
but the default product payload may not expose any additional node kind.

Existing document subtypes are preserved as attributes, not separate top-level
entity kinds:

- `doc.attr.doc_kind = "markdown_section"`
- `doc.attr.doc_kind = "pdf_section"`
- `doc.attr.doc_kind = "boxmatrix_box"`

Backward-compatible API payloads may temporarily contain legacy
`doc_section`, `pdf_section`, or `doc_box` kinds only inside explicit debug or
migration views. The default Web `/graph`, query graph, and acceptance output
must project them to `kind: "doc"` before declaring the product graph valid.

Migration map:

| Legacy/raw kind | Product kind | Required product attr |
| --- | --- | --- |
| `doc_section` | `doc` | `attr.doc_kind = "markdown_section"` |
| `pdf_section` | `doc` | `attr.doc_kind = "pdf_section"` |
| `doc_box` | `doc` | `attr.doc_kind = "boxmatrix_box"` |

Disallowed visible nodes:

- resolver wrapper macros such as `WREG32`, `RREG32`, `REG_SET_FIELD`,
  `SOC15_REG_OFFSET`, `amdgv_wreg32`, and `gpu_register`
- macro-expansion helper names
- resolver helper calls and register-address helper calls when they are only
  evidence for a register access
- callback slot/table names such as `hw_init`, `funcs`, `ops`, `callbacks`
- field-only symbols such as `ENABLE_L2_CACHE`
- local variables, temporary names, provider names, model names, source paths,
  files, or corpus ids

Those details remain in node/edge attributes and provenance. For example,
`REG_SET_FIELD(tmp, GCVM_L2_CNTL, ENABLE_L2_CACHE, 1)` produces or reinforces
a `function -> register` edge with relation `sets_field`; `REG_SET_FIELD`,
`tmp`, and `ENABLE_L2_CACHE` are not nodes. The field name is retained in
`edge.attr.fields` and/or `register.attr.fields`, while the wrapper call and
source span remain in `edge.attr.resolver_wrappers` and `edge.attr.source`.

## Node Schema

Every product node must have:

```json
{
  "id": "stable canonical id",
  "kind": "function|register|doc",
  "label": "human readable label",
  "in": ["incoming relationship summaries"],
  "out": ["outgoing relationship summaries"],
  "attr": {
    "source": [
      {
        "corpus_id": "linux-amdgpu",
        "repo": "https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git",
        "path": "drivers/gpu/drm/amd/amdgpu/gfx_v11_0.c",
        "line_start": 10,
        "line_end": 20,
        "commit": "unknown"
      }
    ]
  }
}
```

Required `attr` by kind:

- `function`: `function_name`, `language`, `source`,
  `raw_implementations`, and `merge_status`.
- `register`: `symbol`, `ip`, `ip_versions`, and `source`.
- `doc`: `doc_kind`, `title` or `summary`, `source`; `page` is required for
  PDF-derived nodes when known; `inputs`, `outputs`, and `constraints` are
  required for BoxMatrix-style boxes.

`source` is a required attribute, not a graph node. Product payloads should
prefer `attr.source` for node provenance and `edge.attr.source` for edge
provenance. Any temporary top-level `source` field on an edge is compatibility
metadata and must not be treated as an entity or relation.

## Merge Rules

Register merge key:

```text
register:{ip}:{symbol}
```

Register merge behavior:

- Same `ip` and same `symbol` merge across repos.
- Same `ip` and same `symbol` merge across IP versions; versions move to
  `attr.ip_versions` and per-source `source[].ip_version`.
- Different `ip` values never merge.
- Same raw symbol with unknown IP remains separate from a known-IP register
  until resolver/profile evidence proves the IP. It may be displayed near the
  known node through inspector hints, but it is not silently merged.
- `unknown` IP does not merge into a known IP unless a resolver profile proves
  the IP.
- Fields are folded into `register.attr.fields` and edge attributes.

Function merge key by default:

```text
function:{corpus_id}:{repo_relative_path}:{function_name}
```

Function concept merge key when a resolver profile enables a rule:

```text
function:{corpus_id}:concept:{resolver_profile_id}:{rule_id}:{canonical_function_name}
```

Function merge behavior:

- No YAML rule means no merge.
- Merge rules live in resolver YAML and must be parsed from committed config,
  not hardcoded in the graph projector.
- `rule_id` is scoped to the resolver profile. Two profiles may reuse a local
  rule id without accidentally merging into the same concept node.
- A merged concept node must preserve `attr.raw_implementations`.
- Same function name in different files, subfolders, or repos is kept as a
  separate implementation node unless an explicit resolver normalization rule
  opts into a concept merge and preserves the raw locations.
- If merged implementations access different registers, ASIP must keep the
  union of all function-to-register product edges and attach
  `edge.attr.implementations`.
- If register-neighbor overlap is below `warn_register_overlap_below`, mark
  `attr.merge_status = "divergent"`.
- If overlap is below `split_register_overlap_below`, project split variants
  and record `attr.merge_status = "split_recommended"` until the UI exposes
  an explicit split view.

Doc merge key:

```text
doc:{corpus_id}:{path}:{doc_kind}:{anchor_or_page_or_box_id}
```

Doc nodes are not merged across repos unless a future resolver explicitly
declares a documentation identity rule.

## Edge Schema

Allowed product `edge.relation` enum:

- `reads`
- `writes`
- `sets_field`
- `maps_base`
- `calls`
- `contains`
- `documents`
- `relates_to`
- `depends_on`
- `configures`
- `resets`

Every product edge must have:

```json
{
  "src": "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gfxhub_gart_enable",
  "dst": "register:GC:GCVM_L2_CNTL",
  "relation": "sets_field",
  "weight": 6.0,
  "confidence": 0.9,
  "stage": "deterministic|semantic|evidence|mixed",
  "sources": ["clang_preprocess", "clang_ast_json"],
  "attr": {
    "source": [
      {
        "corpus_id": "linux-amdgpu",
        "path": "drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c",
        "line_start": 120
      }
    ],
    "accesses": ["field_set", "write"],
    "fields": ["ENABLE_L2_CACHE"],
    "resolver_wrappers": ["REG_SET_FIELD"],
    "implementations": [
      {
        "raw_function_name": "gfxhub_v11_5_0_gart_enable",
        "path": "drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c",
        "ip_version": "11_5_0"
      }
    ]
  }
}
```

Relation normalization:

- `read`, `field_read`, `field_mask`, and `field_shift` normalize to `reads`.
- `write` and `field_write` normalize to `writes`.
- `read_modify_write` or `read_modify_writes` must not become a separate enum;
  project it as both `reads` and `writes`, or as `sets_field` when field
  provenance proves a field update.
- `field_set`, `REG_SET_FIELD`, and provider wording such as "sets field"
  normalize to `sets_field`.
- `address`, base-offset, and register-base helper facts normalize to
  `maps_base`.
- `contains_box` normalizes to `contains`.
- `mentions`, `explains`, `documents_register`, and `documented_by`
  normalize to `documents` when one endpoint is `doc`.
- Unknown valid endpoint semantic relations normalize to `relates_to` and keep
  `attr.original_relation`.
- `wraps`, `has_field`, `defined_in`, macro expansion edges, and resolver
  helper relations are provenance-only and do not become product edges.

## Stage 0: Corpus And Inventory

Corpus registration must support a single repo with multiple allowed
subfolders. For linux-amdgpu, source and register-header folders must be
tracked separately inside one logical corpus when that better represents the
repo:

- `drivers/gpu/drm/amd/amdgpu`
- `drivers/gpu/drm/amd/include/asic_reg`

Each subfolder must record:

- `source_type`: `code`, `register_header`, `docs`, or `pdf`
- include/exclude globs
- resolver profile id
- scan status and file count
- compile database coverage when applicable
- repo-relative provenance, so graph cleanup and QA can prove which subfolder
  produced each deterministic edge or register inventory entry

Register headers must not be indexed by generic token extraction. They need a
register inventory/indexer that accepts known AMD register forms such as
`reg*`, `mm*`, `smn*`, offset/mask/default families, and known IP namespace
patterns, while rejecting low-signal tokens like `A`, `tmp`, or local variable
names.

Acceptance for this layer requires one corpus entry with multiple safe
subfolders, unsafe path rejection for absolute or parent-traversal roots, and
separate file counts for code and register-header roots. A same-repo sibling
subfolder must not require pretending it is a separate corpus just to be
indexed.

## Stage 1: Deterministic Code Graph

Stage 1 is deterministic and code-aware. It owns:

- function nodes
- register nodes
- doc nodes created from deterministic documentation extraction when docs/PDF
  have already been converted into sections
- `function -> function` `calls` edges
- `function -> register` `reads`, `writes`, `sets_field`, and `maps_base`
  edges

Stage 1 product output still uses only `function`, `register`, and `doc`
nodes. Macro invocations, resolver calls, callback slot/table names, register
fields, source files, and helper expressions are evidence for the edges above.
They are persisted as provenance/attrs, not projected as product entities.

The next implementation slice should add a separate `TypedAstGraphExtractor`
instead of overloading the current text-span extractor.

`TypedAstGraphExtractor` input:

- corpus source root
- source subfolders
- resolver profile
- `compile_commands.json` or `compile_flags.txt`
- optional generated include roots

`TypedAstGraphExtractor` output:

- the same raw `CodeGraphEdge` shape as the current extractor
- function definition identity and source span
- call expression callee identity when resolvable
- member-call receiver type when resolvable
- designated initializer field-to-callback mapping
- macro expansion source and spelling locations
- compile database quality metrics

Required provenance modes:

- `libclang_cursor`
- `clangd_index`
- `scip_index`
- `clang_ast_json`
- `clang_preprocess`
- `text_fallback`

The current `code_graph.py` pipeline remains a fallback and must be described
truthfully as source-span plus selective clang probes. `clang_callback` must
not be described as full clangd/libclang vtable parsing.

Callback/vtable policy:

- Exact typed AST or index evidence may create higher-confidence callback
  `calls` edges.
- Conservative slot dispatch may create lower-confidence `vtable_dispatch`
  edges only with `*_ambiguous` provenance when the receiver cannot be proven.
- Callback table names, slot names, receiver aliases, and table types remain
  edge provenance, not product nodes.

## Stage 1.5: Product Projection

Projection turns raw facts into the default product graph:

- apply resolver-configured function normalization
- apply resolver-configured register normalization
- normalize edge relations through the enum map
- fold fields, wrappers, callbacks, sources, provider/model/job ids into attrs
- project all document subtypes to `kind=doc` with `attr.doc_kind`
- reject or quarantine edges whose endpoints cannot project to `function`,
  `register`, or `doc`
- expose `function_view=concept` by default
- expose `function_view=implementation` for inspector/debug views

This layer must never rewrite or delete raw persisted facts. It only projects
them.

## Stage 2: Docs And LLM Semantic Edges

Documentation processing:

- Markdown headings become `doc` nodes with `doc_kind=markdown_section`.
- PDF is converted to Markdown/text first, then split by page and section; PDF
  sections become `doc` nodes with `doc_kind=pdf_section`.
- LLM doc-node extraction produces BoxMatrix-style `doc` nodes with
  `doc_kind=boxmatrix_box`, `inputs`, `outputs`, `constraints`, and source.

Semantic-edge generation:

- Runs only after Stage 1 and doc extraction.
- Consumes indexed function/register/doc candidates.
- Uses the configured provider, supporting local Ollama and OpenAI-compatible
  APIs.
- Must accept configured base URL, model, API path, timeout, extra headers, and
  JSON schema.
- Must persist `stage=semantic`, provider/model/job provenance, candidate ids,
  and source snippets.
- Must reject endpoints that do not project to `function`, `register`, or
  `doc`.
- Must not invent local variables, wrappers, IP-only tokens, or provider names
  as nodes.

## Stage 3: Query And Global Graph

Query graph:

- User controls result limit, hops, seed budget, function view, source type,
  IP, ASIC, and semantic layer inclusion.
- Query API must accept those controls instead of hiding fixed limits.
- The graph panel must show loaded totals and visible totals separately.

Global graph:

- Default route behavior is a global graph, not a fixed seed or historical
  fixture graph.
- Default global graph is budgeted, but not hardcoded. Budgets come from
  `configs/workbench-limits.json` plus visible user overrides and documented
  API parameters.
- Full graph loading needs an explicit `all/full` action with timing and size
  disclosure.
- Weight filter, relation filter, stage filter, and source filter should be
  visible UI controls.
- Progressive loading is the default large-graph interaction model: load an
  initial useful backbone, report total/loaded/visible counts, then let the
  user request more edges or the full graph.
- Weight filtering is a renderer/filter state, not a hidden mutation of the
  stored graph. The API can support server-side filtering for performance, but
  the UI must show the active threshold.
- Bridge preservation should keep shared registers and callback backbones
  visible by default so linux-amdgpu and MxGPU do not appear disconnected.

Renderer policy:

- Prefer maintained npm graph packages over hand-written graph rendering.
- Current `react-force-graph-2d` can remain for the existing slice, but dense
  graph work should profile Sigma/Graphology because it supports graph-model
  level data handling plus renderer reducers.
- Custom canvas/SVG code is acceptable only as package adapter glue and
  product-specific labeling/inspection.

## Web UI And Visual QA Contract

Standard workbench controls must use shadcn/Radix primitives and composition:

- `Table`/table primitives for dense evidence and acceptance rows
- `Card` only for individual framed items, not page-within-card layouts
- `Accordion`/`Collapsible` for expandable evidence, acceptance details, and
  inspector provenance
- `Dialog`/`Sheet` for focused inspect/edit flows
- `Alert`/empty states for truthful no-data/error states
- `Badge`, `Button`, `Input`, `Select`, `Checkbox`, `Slider`, and equivalent
  Radix-backed controls for filters and graph budgets

Custom CSS should be limited to app layout, graph/canvas adapters, and
ASIP-specific density/inspection surfaces. Do not rebuild generic controls by
hand when a shadcn/Radix primitive exists.

Visual QA requirements:

- Each route has its own visual anchor; no combined multi-panel anchor sheet.
- QA captures 2K desktop screenshots for light and dark themes after
  UI-affecting changes.
- `/graph` screenshots must be compared against the graph-specific anchor and
  must show a nonblank package-rendered graph, visible graph controls, loaded
  versus visible counts, and no text overlap in compact panels.
- Browser QA must use the in-app browser or Computer Use path requested by the
  user for visual inspection, with Playwright/browser artifacts recorded in
  `docs/qa` when relevant.

## Performance Profile Plan

Do not optimize blind. Every performance change needs before/after evidence.

Required profile layers:

- browser: fetch timing, JSON size, canvas ready time, layout profile, visible
  node/edge counts
- Next BFF: CLI spawn time, stdout size, JSON parse time, error/maxBuffer path
- Python query: FTS, vector/provider search, scoring, candidate overfetch,
  graph expansion
- SQLite/NetworkX: edge scan, aggregation, component selection, subgraph
  extraction, node metadata hydration
- acceptance: per-query elapsed time, surfaces, graph counts, provider checks

Baseline commands:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src \
  python3 -m cProfile -o /tmp/asip-query.prof \
  -m asip.cli query --db data/asip.db --q 'GCVM_L2_CNTL' --limit 24

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src \
  python3 -m cProfile -o /tmp/asip-graph.prof \
  -m asip.cli graph --db data/asip.db --limit 3000

python3 - <<'PY'
import pstats
for path in ["/tmp/asip-query.prof", "/tmp/asip-graph.prof"]:
    print("\\n", path)
    pstats.Stats(path).strip_dirs().sort_stats("cumtime").print_stats(30)
PY

curl -w '\nconnect=%{time_connect} start=%{time_starttransfer} total=%{time_total} size=%{size_download}\n' \
  'http://127.0.0.1:3100/api/workbench/graph?limit=3000'
```

Candidate optimizations must be driven by profile evidence:

- cache graph summaries by DB mtime/job id/config budget
- precompute register/function degree and component membership
- stream or page global graph payloads for very large graphs
- move expensive metadata hydration after edge selection
- avoid spawning Python per small UI poll where an API worker can stay warm
- use renderer reducers for visual filtering instead of rebuilding graph data
  for every UI-only filter

## TDD Implementation Order

1. Schema validator tests
   - Assert default product graph only exposes `function`, `register`, `doc`.
   - Assert wrapper/field/source/provider names are rejected as endpoints.
   - Assert unknown semantic relations normalize or are dropped by policy.

2. Register inventory tests
   - Index an `asic_reg` fixture.
   - Assert `mm*`, `reg*`, and `smn*` registers enter the inventory.
   - Assert `A`, `tmp`, `adapt`, wrappers, and local variables do not become
     evidence symbols or graph endpoints.

3. Typed AST extractor red tests
   - Two `.c` files plus `compile_commands.json`.
   - Assert direct calls, member receiver type, macro expansion location, and
     function-to-register writes are emitted without using `text_fallback`.

4. Callback/vtable precision tests
   - Same receiver leaf name with two different struct types must not overlink.
   - Cross-file callback table and callback implementation must keep distinct
     `callback_path` and `callee_path`.
   - Ambiguous dynamic dispatch remains `vtable_dispatch` with lowered
     confidence.

5. Function/register merge tests
   - Versioned AMD functions merge only through YAML rules.
   - Low register-overlap concepts become `divergent` or split.
   - linux-amdgpu and MxGPU connect through the same `register:{ip}:{symbol}`
     node.

6. Docs and semantic tests
   - Markdown and PDF sections project to `kind=doc`.
   - LLM doc-node extraction writes BoxMatrix-style doc nodes.
   - Stage 2 semantic edges reject invalid endpoints and persist provider/model
     provenance.

7. API/Web control tests
   - Query route accepts user result limit, hops, seed budget, and filters.
   - Graph route clamps oversized budgets and exposes `all/full` explicitly.
   - UI sliders/selects update request parameters and loaded/visible counts.

8. No-mock browser/e2e tests
   - Open `/graph` against a real SQLite DB.
   - Wait for package graph `data-ready=true`.
   - Assert node/edge totals are nonzero and only product kinds are visible.
   - Switch function view and assert request/data changes.
   - Run at least one free query and verify graph changes.
   - Run `/acceptance` and expand per-query details.

9. Performance gate
   - Run fixture smoke.
   - Run more than five real queries.
   - Profile global graph and one slow query.
   - Capture `/graph` browser timing and screenshot at 2048 x 1280.

## Remaining Gaps And Acceptance Criteria

The current docs and QA show meaningful progress, but the following gaps remain
open until the listed acceptance criteria are met with current no-mock
artifacts.

| Gap | Why it remains open | Acceptance criteria |
| --- | --- | --- |
| Product node schema projection | Older raw/debug and historical QA paths still mention `doc_section`, `pdf_section`, and `doc_box` as node kinds. | CLI/API/MCP/Web default graph payloads expose only `function`, `register`, and `doc`; document subtype is preserved in `attr.doc_kind`; schema validator rejects wrapper, field, source, provider, callback-slot, local-variable, and corpus-id endpoints. |
| Stage 1 deterministic truthfulness | Current extractor is a pragmatic span/preprocess/callback pipeline with selective clang AST JSON hints, not full clangd/libclang cross-TU type flow. | Stage 1 provenance names the exact mode used per edge; typed extractor coverage metrics report parsed/fallback files; full clangd/libclang remains explicitly deferred unless implemented and tested. |
| Macro/resolver evidence folding | Macro/resolver names can be useful evidence but dangerous as graph mega-nodes. | Resolver wrappers, helper calls, callback slots, and fields appear only in `attr`, provenance, resolved chains, and inspector expansion; no default graph endpoint can be a wrapper/helper/field token. |
| Register inventory and normalization | Multi-subfolder corpus support exists, but register headers need dedicated inventory semantics rather than generic token promotion. | Same logical repo corpus indexes code and register-header subfolders; register inventory accepts `reg*`, `mm*`, `smn*`, offset/mask/default/IP namespace forms; rejects low-signal tokens; register merge key is `register:{ip}:{symbol}` with IP versions as attrs/provenance. |
| Function normalization and variants | Versioned AMD functions can be conceptually merged only when behavior remains auditable. The deterministic graph projection now applies function normalization only through resolver profile provenance on the edge/node metadata, concept ids include `resolver_profile_id`, DB resolver profile config overrides committed defaults for the same id, and disabled DB alias rows also disable the loaded YAML profile id. Evidence-derived fallback rows still need structured resolver-profile provenance before that path can claim the same scope. | Resolver YAML controls every concept merge; no YAML/profile metadata means no merge; duplicate rule ids across profiles remain isolated; merged concepts keep `raw_implementations`; identical/high-overlap register neighborhoods stay `merged`; partial low overlap becomes `divergent`; disjoint overlap becomes `split_recommended`; implementation view still exposes raw nodes; follow-up must add structured resolver-profile provenance to evidence-derived graph rows. |
| Register normalization profile scope | Register identity was previously hardcoded in projection even though profiles parsed `graph.register_normalization`. Product projection now consumes the resolver profile identity template, while the default remains `register:{ip}:{symbol}` with IP versions as attrs/provenance. | Resolver YAML/DB profile can change register identity without code edits; default keeps cross-repo same-IP register bridges; profile ids and disabled aliases are honored by both index profile selection and graph projection; register-header inventory filtering remains separate. |
| Edge enum validation | Existing producers can emit raw access names or provider wording that must not leak as product relations. | Default output relation is one of `reads`, `writes`, `sets_field`, `maps_base`, `calls`, `contains`, `documents`, `relates_to`, `depends_on`, `configures`, `resets`; `read_modify_write` is projected to read/write or field set; invalid wrapper/source relations are provenance-only. |
| Stage 2 semantic and doc boxes | LLM outputs must enrich the graph without inventing non-product nodes. | Semantic/doc-box jobs run after Stage 1/doc extraction; endpoints project to `function`, `register`, or `doc`; provider/model/job/snippet provenance persists; invalid local/IP/helper/provider endpoints are rejected or quarantined. |
| Global graph loading and filters | Default graph should be global and progressive, not a hidden hardcoded slice. | `/graph` requests a global graph by default; limits come from `configs/workbench-limits.json`, URL/API params, and visible shadcn/Radix controls; UI shows loaded/visible/total counts, weight threshold, relation/stage/source filters, and explicit full/all action. |
| Web visual contract | The UI must remain a real workbench surface as graph semantics evolve. | Standard UI uses shadcn/Radix primitives; graph uses a maintained package; 2K light/dark route visual QA compares each page to its own anchor; `/graph` screenshot proves nonblank package rendering, no overlap, and visible controls. |
| Final evidence package | Historical QA contains useful but stale counts and shapes. | Final package records clean DB path/counts, Stage 1 and Stage 2 edge counts, AQ01-AQ09, free queries, schema validator pass, API/MCP/Web parity, no-mock browser QA, performance profile, visual QA, and explicit accepted residuals. |

## Completion Gate

This work cannot be called complete until the final QA package includes:

- clean current DB path and counts
- Stage 1 deterministic edge counts by source/provenance
- Stage 2 semantic edge counts by provider/model/job
- product schema validator pass
- AQ01-AQ09 pass/fail artifact
- more than five real free-query results
- no-mock `/graph` browser QA
- performance profile before/after notes
- 2K light/dark visual QA against per-page anchors
- explicit residual list for any remaining clangd/libclang/cross-TU limits
- git diff review, commit, and push
