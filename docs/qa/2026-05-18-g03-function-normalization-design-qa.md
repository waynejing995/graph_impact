# G03 Function Normalization Design QA

Date: 2026-05-18
Status: PASS for documentation planning and initial implementation slice

## Scope

This QA note records the design and first implementation pass for
resolver-configured function normalization. It now covers both the original
documentation review and the implemented concept/implementation graph views.

## Subagent Review

Two read-only subagents reviewed the proposal before the docs were updated.

- Storage/code-path review found the current function node id is still produced
  by `packages/core/src/asip/storage.py` as
  `function:{scope}:{path}:{function_name}`. The recommended implementation
  point is the product projection layer around `_product_graph_node()` and
  `_function_graph_node()`, not the raw Stage 1 extractor.
- Gap/YAML review found G03 had stale register identity wording. The docs now
  align with the current product identity `register:{ip}:{symbol}`, with
  `ip_version` carried in `attr.ip_versions` and `source[].ip_version`.
- Both reviews recommended preserving raw implementation records and adding a
  default concept graph plus an inspector/debug implementation view.

## Web Research Used

- Joern Code Property Graph docs: <https://docs.joern.io/code-property-graph/>
- CPG schema reference: <https://cpg.joern.io/>
- Code Property Graph paper: <https://fabianyamaguchi.com/files/2014-ieeesp.pdf>
- CodeQL data-flow analysis docs: <https://codeql.github.com/docs/writing-codeql-queries/about-data-flow-analysis/>
- Clone-detection survey context for semantic clone risk:
  <https://arxiv.org/abs/2109.12079>

The main design takeaway is layered graph projection: raw facts remain
lossless, while product views can be simplified through a documented overlay.
The clone-detection source is treated as a caution against pure regex/name
merging; the plan therefore requires register/action overlap guards.

## Updated Documents

- `docs/specs/2026-05-18-product-graph-normalization.md`
- `docs/superpowers/plans/2026-05-18-product-graph-normalization.md`
- `docs/gaps/2026-05-16-g03-dynamic-weighted-graph.md`
- `docs/gaps/2026-05-16-g05-resolver-profiles.md`
- `docs/gaps/2026-05-16-g10-testing-acceptance-visual-qa.md`
- `docs/gaps/2026-05-17-gap-document-register.md`
- `docs/gaps/README.md`

## Decisions Captured

- Raw SQLite graph facts are never rewritten into concept names.
- Default graph can project versioned function names into concept nodes only
  through resolver YAML.
- A concept function node must preserve `attr.raw_implementations`,
  `attr.raw_function_names`, source records, language, IP block/version attrs,
  and merge status.
- Product register identity is `register:{ip}:{symbol}`. `ip_version` is
  provenance and aggregated attr, not a node-id split.
- If normalized functions access different registers, the default graph keeps
  all product edges and annotates divergence; it splits only when configured
  thresholds or non-mergeable relation rules require it.
- Product edge relations stay enum-bound. Original access kinds remain in
  edge provenance or `edge.attr.accesses`.
- The next implementation slice must start with RED tests for config parsing,
  concept function projection, divergent access preservation, and
  inspector/debug raw implementation expansion.

## Verification

Implementation validation:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_resolver_profiles packages.core.tests.test_storage_graph packages.core.tests.test_workbench_query_schema -v
```

Result: PASS, 72 tests, 2 sqlite-vec optional skips.

```text
pnpm --filter web exec tsc --noEmit
```

Result: PASS.

```text
pnpm --filter web exec playwright test apps/web/tests/workbench-api.spec.ts --grep "function views|data-driven weighted edges|resolver operators"
```

Result: PASS, 3 Playwright API tests.

Browser check:

```text
In-app browser at http://127.0.0.1:3100/graph, 2048x1280 viewport
```

Result: PASS. The shadcn `Function view` select is visible in Graph display
controls. Default value is `Concept`; switching to `Implementation` reloads the
live graph and changes visible graph totals from 2581 nodes to 2687 nodes on
the current local DB, proving the UI control reaches the graph API rather than
being only local decoration.

Docs/patch validation:

```text
git diff --check
```

Result: PASS, no whitespace or patch formatting errors.

## Implementation Notes

- Default graph view now collapses configured AMD versioned functions into
  concept function nodes while preserving raw implementation provenance.
- `function_view=implementation` can still return raw path/function nodes for
  debugging and inspector-style workflows.
- Concept edges retain implementation records in `edge.attr.implementations`.
- Divergent normalized implementations keep all register edges and mark the
  concept node as `attr.merge_status = "divergent"`.
- The view switch is exposed through core storage, workbench graph/query
  functions, CLI `--function-view`, Next BFF `functionView`, FastAPI
  `function_view`/`functionView`, MCP tools, and the Web graph control.

## 2026-05-19 Concept Truth Review

Status: PASS after fixes.

The review found that concept view was real but incomplete on the live DB:
resolver-profile metadata was present on register operation edges, but many
`calls`/callback edges only carried `corpus_id` and `repo`. Those edges stayed
as raw implementation nodes, so the default graph could show the same raw
function both inside a concept node and as a separate raw node.

Fixes:

- concept function labels now use the canonical function name, not the first
  raw implementation name.
- resolver profiles support YAML `aliases`, so corpus ids such as `mxgpu` can
  map to a real profile id such as `amd-mxgpu` without Python-only special
  cases.
- function concept normalization can infer a profile from configured aliases
  on `corpus_id`/`repo` when explicit `resolver_profile` provenance is absent.
- all committed AMD C/C++ resolver profiles now carry the same configurable
  AMD IP-versioned function normalization rule and register identity policy.
- default concept graph now normalizes callback/call edges, while
  `function_view=implementation` still returns raw path/function nodes.

Red tests added before the fix:

- `test_function_concept_infers_profile_from_corpus_for_call_edges`
- `test_function_concept_node_label_uses_canonical_name`
- `test_function_concept_infers_mxgpu_profile_from_configured_alias`

Live DB comparison after the fix:

```text
concept:        11731 nodes, 24888 edges, 10894 function, 830 register, 7 doc
implementation: 14640 nodes, 34225 edges, 13803 function, 830 register, 7 doc
concept functions: 1516 total, 1294 merged
normalization profiles: linux-amdgpu 1267, amd-mxgpu 249
concept label != canonical: 0
raw names present in both concept and raw nodes: 0
```

Verification:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  packages.core.tests.test_resolver_profiles \
  packages.core.tests.test_storage_graph \
  packages.core.tests.test_workbench_query_schema \
  packages.core.tests.test_workbench_live -v
```

Result: PASS, `Ran 155 tests`, `OK`, with 2 optional sqlite-vec skips.

```text
pnpm --filter web exec tsc --noEmit
```

Result: PASS.

```text
PLAYWRIGHT_SKIP_WEB_SERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:3111 \
  pnpm --filter web exec playwright test tests/workbench-api.spec.ts \
  --grep "graph API can switch between concept and implementation" --reporter=list
```

Result: PASS, 1 Playwright API test.
