# ASIP Product Graph Normalization Design

Date: 2026-05-18
Status: Initial implementation landed for resolver-configured function concept projection and API/Web view switching; superseded by 2026-05-19 three-kind product graph contract for final closure

2026-05-19 superseding note: the integrated source of truth for the next graph
implementation slice is
[`docs/specs/2026-05-19-asip-graph-integration-plan.md`](2026-05-19-asip-graph-integration-plan.md).
That newer plan resolves the product-node contract to exactly three conceptual
node kinds: `function`, `register`, and `doc`. The older references below to
`doc_section`, `pdf_section`, and `doc_box` remain useful implementation
history, but default product graph output must now project those as `kind=doc`
with `attr.doc_kind`.

## Purpose

The product graph must stop exposing resolver wrappers, macro-expansion helper
names, field-only symbols, source paths, provider names, and duplicate
IP-versioned implementation functions as first-class nodes. Those facts remain
auditable, but the 2026-05-19 final contract says the default graph is a compact
BoxMatrix-style concept graph over exactly:

- `function`
- `register`
- `doc`

Historical/raw document shapes `doc_section`, `pdf_section`, and `doc_box`
remain valid as persisted implementation details or debug output only when they
project to `kind=doc` with `attr.doc_kind=markdown_section|pdf_section|boxmatrix_box`
before default CLI/API/MCP/Web product output.

The key design decision is a two-view graph model:

- The raw fact graph stays lossless. SQLite edge rows keep raw function names,
  raw endpoints, source path/line, resolver wrapper, access kind, callback/type
  flow, provider, model, job, and source provenance.
- The product graph is a resolver-configured projection. It can collapse noisy
  raw facts into stable concept nodes, but every collapsed node and edge must
  expose an inspector path back to the raw implementations and access records.

This answers the current concern about AMD function variants such as
`gfxhub_v11_5_0_gart_enable`, `gfxhub_v12_0_gart_enable`, and
`gfxhub_v3_0_gart_enable`: they can be normalized into one concept only when a
resolver profile explicitly opts in and the merge guard proves the variants are
compatible enough.

## Implementation Slice Landed

The 2026-05-18 implementation slice covers the first production path:

- `configs/resolvers/linux-amdgpu.yaml` now defines `graph.function_normalization`
  for AMD versioned function names and `graph.register_normalization.identity`.
- `packages/core/src/asip/resolver_profiles.py` parses the optional `graph:`
  YAML contract and round-trips it from committed resolver profiles.
- `packages/core/src/asip/storage.py` projects versioned raw functions into
  `function:{scope}:concept:{resolver_profile_id}:{rule_id}:{canonical_function_name}`
  by default, preserves `attr.raw_function_names` and
  `attr.raw_implementations`, and keeps all function-to-register edges when
  normalized implementations touch different registers.
- The 2026-05-19 follow-up fixed profile scoping: duplicate local rule ids from
  different resolver profiles no longer merge, disabled DB alias rows disable
  the loaded YAML profile id too, and product register ids consume
  `graph.register_normalization.identity`.
- `function_view=implementation` remains available for raw/debug inspection.
- CLI, Next BFF graph/query routes, FastAPI query/graph, MCP search/graph, and
  the Web graph controls expose `concept|implementation` function views.

This slice does not claim the full clangd/vtable or LLM semantic-edge pipeline
is complete. It removes a major product-graph noise source while keeping raw
facts recoverable for the remaining Stage 1 and Stage 2 work.

## External Experience

The online scan supports the layered approach:

- Joern describes the Code Property Graph as a source-code property graph with
  overlays for derived layers, which maps well to "raw facts plus product
  overlay" instead of mutating raw evidence into a lossy display graph:
  <https://docs.joern.io/code-property-graph/> and <https://cpg.joern.io/>.
- The original Code Property Graph paper combines AST, control flow, and data
  flow into one queryable representation, which supports keeping syntax-aware
  Stage 1 facts separate from semantic Stage 2 LLM edges:
  <https://fabianyamaguchi.com/files/2014-ieeesp.pdf>.
- CodeQL separates local and global data-flow reasoning and calls out the
  precision/cost tradeoff. The ASIP graph should therefore expose conservative
  product summaries by default while preserving raw/inspector expansion for
  harder alias and callback cases:
  <https://codeql.github.com/docs/writing-codeql-queries/about-data-flow-analysis/>.
- Clone-detection literature distinguishes exact, syntactic, near-miss, and
  semantic clones. That is the warning against merging functions by a regex
  name rewrite alone. ASIP needs behavior/register-overlap guards before
  claiming two versioned functions are one concept:
  <https://arxiv.org/abs/2109.12079>.

## Node Identity

Raw Stage 1 extraction keeps concrete implementation identity:

```text
function:{repo_or_corpus}:{repo_relative_path}:{raw_function_name}
raw_doc_section:{repo_or_corpus}:{path}:{anchor_or_page}
raw_doc_box:{repo_or_corpus}:{path}:{box_id}
```

Raw function names and source paths are never rewritten in persisted provenance.

Product node IDs are stable concept IDs:

```text
function:{repo_or_corpus}:concept:{resolver_profile_id}:{rule_id}:{canonical_function_name}
function:{repo_or_corpus}:{repo_relative_path}:{raw_function_name}
register:{ip}:{symbol}
doc:{repo_or_corpus}:{path}:{doc_kind}:{anchor_or_page_or_box_id}
```

Function nodes use the raw path/name identity unless a resolver profile enables
a normalization rule. Register nodes merge across repos and IP versions only
within the same IP block and symbol. `ip_version` is metadata/provenance, not
part of product register identity. Document sections, PDF sections, and
BoxMatrix boxes are all `doc` nodes in product output; the subtype lives in
`attr.doc_kind`.

## Function Concept Node Schema

Every normalized function node keeps the standard BoxMatrix fields:

```json
{
  "id": "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gfxhub_gart_enable",
  "kind": "function",
  "label": "gfxhub_gart_enable",
  "in": ["calls from amdgpu_device_init"],
  "out": ["writes register:GC:GCVM_L2_CNTL"],
  "attr": {
    "function_name": "gfxhub_gart_enable",
    "raw_function_names": ["gfxhub_v11_5_0_gart_enable", "gfxhub_v12_0_gart_enable"],
    "ip_block": "gfxhub",
    "ip_versions": ["11_5_0", "12_0"],
    "language": "c",
    "merge_status": "merged",
    "source": [
      {
        "corpus_id": "linux-amdgpu",
        "repo": "https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git",
        "path": "drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c",
        "line_start": 120,
        "line_end": 180,
        "ip_version": "11_5_0",
        "raw_function_name": "gfxhub_v11_5_0_gart_enable"
      }
    ],
    "raw_implementations": [
      {
        "raw_function_name": "gfxhub_v11_5_0_gart_enable",
        "canonical_function_name": "gfxhub_gart_enable",
        "path": "drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c",
        "line_start": 120,
        "line_end": 180,
        "language": "c",
        "ip_block": "gfxhub",
        "ip_version": "11_5_0",
        "extractor": "clang_text_spans"
      }
    ]
  }
}
```

If a function is not normalized, it still uses this node payload shape with
`raw_function_names` and `raw_implementations` containing one implementation.

## Merge Policy

Function normalization is explicit and conservative:

- No resolver rule match means no merge.
- Different `ip_block` values do not merge.
- Different canonical operation names do not merge.
- Different languages do not merge unless the rule explicitly allows it.
- Static/local functions from different paths do not merge unless a rule names
  the path pattern and the implementation overlap guard passes.
- A function concept may aggregate multiple IP versions only when each raw
  implementation remains recoverable from `attr.raw_implementations`.

When two normalized implementations touch different registers, ASIP must not
drop either access. The default policy is:

- Keep one concept node if the configured guard passes.
- Union function-to-register edges onto the concept.
- Put the exact raw implementation list on each product edge in
  `edge.attr.implementations`.
- Set `node.attr.merge_status = "divergent"` when the register/action overlap
  is below the warning threshold but above the split threshold.
- Split into deterministic variants when overlap is below the split threshold
  or when the rule marks specific registers/actions as non-mergeable.

Different register access is therefore not automatically a bug. It is a reason
to preserve per-implementation provenance and possibly split the concept if the
behavior diverges too far.

## Edge Schema

Product edge relations remain enum-bound:

```text
reads
writes
sets_field
maps_base
calls
contains
documents
relates_to
depends_on
configures
resets
```

Merged concept edges must retain access detail:

```json
{
  "src": "function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gfxhub_gart_enable",
  "dst": "register:GC:GCVM_L2_CNTL",
  "relation": "sets_field",
  "weight": 6.0,
  "stage": "deterministic",
  "attr": {
    "accesses": ["field_set", "write"],
    "fields": ["ENABLE_L2_CACHE"],
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

If one function-register pair has both read and write access, the raw graph and
inspector keep both records. The default graph may visually aggregate the edge
only when `attr.accesses` and raw edge expansion expose the distinct facts.

## Resolver YAML Contract

Resolver profiles are not only wrapper lookup tables. They define the product
graph normalization contract for the corpus.

```yaml
id: linux-amdgpu
language: cpp
context_vars: [adev]
symbol_prefixes: [reg, mm, smn]

graph:
  function_normalization:
    enabled: true
    default_identity: "function:{repo_or_corpus}:{normalized_path}:{function_name}"
    rules:
      - id: amd-ip-versioned-functions
        enabled: true
        match: "^(?P<ip_block>gfxhub|mmhub|gfx|sdma|gmc|nbio|df|ih)_v(?P<ip_version>\\d+_\\d+(?:_\\d+)?)_(?P<operation>.+)$"
        canonical: "{ip_block}_{operation}"
        attrs:
          ip_block: "{ip_block}"
          ip_version: "{ip_version}"
        merge_policy:
          mode: concept_with_implementations
          warn_register_overlap_below: 0.35
          split_register_overlap_below: 0.10
          split_when:
            different_ip_block: true
            different_language: true
            conflicting_relation_family: true
          preserve:
            raw_implementations: true
            source: true
            signature: true
            extractor: true

  register_normalization:
    identity: "register:{ip}:{symbol}"
    merge_across_repos_when_ip_and_symbol_match: true
    merge_across_ip_versions: true
    merge_across_ip_blocks: false
    preserve:
      ip_version_attr: true
      ip_versions_attr: true
      source_ip_version: true

  access_relation_map:
    read:
      relation: reads
      preserve_access: true
    write:
      relation: writes
      preserve_access: true
    field_set:
      relation: sets_field
      field_args_required: true
      preserve_access: true
    field_write:
      relation: writes
      preserve_access: true
    field_read:
      relation: reads
      preserve_access: true
    field_mask:
      relation: reads
      preserve_access: true
    field_shift:
      relation: reads
      preserve_access: true
    field_value:
      relation: writes
      preserve_access: true
    address:
      relation: maps_base
      preserve_access: true

  graph_profiles:
    default_global:
      include_stages: [deterministic, semantic]
      hide_raw_implementations: true
      hide_wrappers: true
      hide_field_nodes: true
      protect_bridge_edges:
        - shared_registers
        - callback_backbone
      expose_totals: true
    inspector:
      include_raw_implementations: true
      include_raw_edges: true
      include_access_records: true
      include_source_provenance: true
      include_callback_provenance: true
```

The same schema can later support Python repositories by adding a different
`function_normalization.rules` entry or by disabling function normalization.
Nothing in the product graph should assume C macros are the only source of
hardware relationships.

## Implementation Placement

Recommended first implementation slice:

- Keep `packages/core/src/asip/code_graph.py` focused on Stage 1 raw facts.
- Add product projection helpers in `packages/core/src/asip/storage.py`, near
  `_product_graph_node()` and `_function_graph_node()`.
- Load resolver graph normalization config through
  `packages/core/src/asip/resolver_profiles.py`.
- Add a graph view parameter such as `function_view="concept|implementation"`.
  Default `/graph` uses `concept`; debug/inspector paths can request
  `implementation`.
- Do not rewrite persisted `edges.src`, `edges.dst`, or
  `edges.provenance_json` into concept names.

## Acceptance Criteria

- YAML profile can configure function normalization. By default, same-name
  functions in different files/repos do not merge.
- Default product graph node kinds are exactly `function`, `register`, and
  `doc`; older `doc_section`, `pdf_section`, and `doc_box` names are raw/debug
  shapes and must project to `kind=doc` with `attr.doc_kind`.
- Register product identity is `register:{ip}:{symbol}`. `ip_version` is
  stored in `attr.ip_versions` and `source[].ip_version`, not in the product
  node id.
- Different IP blocks never merge, even when register symbols match.
- Versioned functions that match a configured rule can collapse into a concept
  node with `attr.raw_implementations`.
- If normalized functions access different registers, all access edges remain
  visible through unioned product edges and raw inspector expansion.
- Product edges keep enum relations and preserve original access names in
  `edge.attr.accesses` / provenance.
- Default global graph hides wrappers, macro helpers, field-only symbols, and
  raw implementation duplicates, while preserving shared-register bridges and
  callback backbones.
- Inspector expansion for a merged function or register returns raw
  implementations, raw accesses, source records, callback/type-flow provenance,
  and IP/version evidence.
