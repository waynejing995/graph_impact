# Product Graph Normalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement resolver-configured product graph normalization so the default graph shows only `function`, `register`, and `doc` concept nodes while preserving raw implementations and access provenance for inspector expansion.

**Architecture:** Stage 1 extraction continues to persist raw deterministic facts. Resolver profiles add a `graph:` section for function/register/access normalization. `storage.py` projects raw SQLite edges into either the default concept graph or a raw implementation graph, and Web/API paths keep using the default concept graph unless a debug/inspector path requests raw expansion.

**Tech Stack:** Python 3, SQLite, NetworkX, YAML resolver profiles, unittest, Next.js BFF smoke tests where graph API payload shape changes.

---

## Execution Status

2026-05-18 initial slice is implemented and verified:

- Resolver graph-normalization config parsing is implemented.
- `linux-amdgpu` has the first AMD IP-versioned function normalization rule.
- Storage global/query graph projections default to `function_view="concept"`
  and preserve raw implementation metadata.
- `function_view="implementation"` is available through storage, workbench
  query/graph functions, CLI, Next BFF, FastAPI, MCP, and the Web graph control.
- Verification passed:
  - `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_resolver_profiles packages.core.tests.test_storage_graph packages.core.tests.test_workbench_query_schema -v`
  - `pnpm --filter web exec tsc --noEmit`
  - `pnpm --filter web exec playwright test apps/web/tests/workbench-api.spec.ts --grep "function views|data-driven weighted edges|resolver operators"`

Remaining work in the broader goal: full clangd/vtable/type-flow coverage,
real full-index rebuild/QA, LLM semantic-edge batch generation over the
normalized graph, and browser visual QA against the live page.

## Source Documents

- Integrated source of truth: `docs/specs/2026-05-19-asip-graph-integration-plan.md`
- Design: `docs/specs/2026-05-18-product-graph-normalization.md`
- Gap owner: `docs/gaps/2026-05-16-g03-dynamic-weighted-graph.md`
- Resolver owner: `docs/gaps/2026-05-16-g05-resolver-profiles.md`
- QA owner: `docs/gaps/2026-05-16-g10-testing-acceptance-visual-qa.md`

## 2026-05-19 Continuation

The initial 2026-05-18 slice landed function concept projection and
`function_view=concept|implementation`. The next slice must follow the
integrated contract in
`docs/specs/2026-05-19-asip-graph-integration-plan.md`.

The required implementation order is:

1. Product graph schema validator.
   - Default Web/API/MCP graph output exposes only `function`, `register`, and
     `doc`.
   - `doc_section`, `pdf_section`, and `doc_box` are projected to
     `kind=doc` with `attr.doc_kind`.
   - Wrapper, field, source, provider, local variable, and callback-slot
     endpoints are rejected before output.
2. Register-header inventory and low-signal token filtering.
   - `reg*`, `mm*`, and `smn*` forms are accepted.
   - Noise such as `A`, `tmp`, `adapt`, and resolver wrappers cannot become
     evidence symbols or graph endpoints.
3. Typed AST extractor adapter.
   - Add a separate `TypedAstGraphExtractor` path or adapter rather than
     relabeling the existing source-span pipeline.
   - Record `libclang_cursor`, `clangd_index`, `scip_index`,
     `clang_ast_json`, `clang_preprocess`, or `text_fallback` provenance
     truthfully.
   - Keep the current `code_graph.py` pipeline as fallback.
4. Callback/vtable precision.
   - Exact typed evidence creates higher-confidence callback `calls` edges.
   - Ambiguous conservative dispatch remains `vtable_dispatch` with lower
     confidence and ambiguity provenance.
5. Resolver YAML graph config becomes operational.
   - `register_normalization`, `access_relation_map`, and merge thresholds
     drive projection behavior, not only parsing/round-trip tests.
   - Divergent normalized functions preserve all register edges and mark
     `merge_status`.
6. Stage 2 doc/semantic hardening.
   - Markdown/PDF/BoxMatrix nodes project to `kind=doc`.
   - Semantic-edge jobs reject endpoints that cannot project to
     `function/register/doc`.
7. Web/API controls and no-mock e2e.
   - Query API accepts user-controlled result limit, hops, seed budget, and
     filters.
   - `/graph` exposes loaded versus visible totals, explicit full/all loading,
     and server-side budget controls.
   - Browser e2e opens a real DB-backed `/graph`, verifies schema/data, switches
     function view, runs a free query, and expands acceptance detail.
8. Performance profiling.
   - Run cProfile for one slow query and global graph.
   - Record curl route timing and browser canvas readiness before optimizing.

Do not mark this plan complete until the new schema validator, no-mock browser
QA, and profile evidence are recorded.

## File Structure

- Modify: `packages/core/src/asip/resolver_profiles.py`
  - Parse optional `graph.function_normalization`, `graph.register_normalization`, `graph.access_relation_map`, and `graph.graph_profiles`.
- Modify: `packages/core/src/asip/storage.py`
  - Add product projection helpers for function concept nodes and raw implementation preservation.
  - Add `function_view="concept|implementation"` to graph projection entry points where needed.
- Modify: `packages/core/src/asip/workbench.py`
  - Pass active resolver graph-normalization config to the store projection layer.
- Modify: `packages/core/src/asip/cli.py`
  - Add an optional graph/debug flag only if required by the storage API, for example `--function-view implementation`.
- Modify: `configs/resolvers/linux-amdgpu.yaml`
  - Add the first enabled `graph.function_normalization` rule for AMD versioned functions.
- Test: `packages/core/tests/test_resolver_profiles.py`
- Test: `packages/core/tests/test_storage_graph.py`
- Test: `packages/core/tests/test_workbench_query_schema.py`
- Test: `packages/core/tests/test_workbench_live.py`
- Test: `apps/web/tests/workbench-api.spec.ts` only if API shape changes.
- Docs/QA: add `docs/qa/2026-05-18-g03-function-normalization-qa.md` after implementation.

## Task 1: Parse Resolver Graph Normalization Config

**Files:**
- Modify: `packages/core/src/asip/resolver_profiles.py`
- Test: `packages/core/tests/test_resolver_profiles.py`
- Modify: `configs/resolvers/linux-amdgpu.yaml`

- [ ] **Step 1: Write the failing resolver-profile test**

```python
def test_resolver_profile_loads_graph_function_normalization_rules(self):
    config = {
        "id": "linux-amdgpu",
        "language": "cpp",
        "wrappers": [],
        "graph": {
            "function_normalization": {
                "enabled": True,
                "rules": [
                    {
                        "id": "amd-ip-versioned-functions",
                        "enabled": True,
                        "match": r"^(?P<ip_block>gfxhub)_v(?P<ip_version>\\d+_\\d+)_(?P<operation>.+)$",
                        "canonical": "{ip_block}_{operation}",
                        "merge_policy": {
                            "mode": "concept_with_implementations",
                            "warn_register_overlap_below": 0.35,
                            "split_register_overlap_below": 0.10,
                        },
                    }
                ],
            },
            "register_normalization": {"identity": "register:{ip}:{symbol}"},
        },
    }
    profile = ResolverProfile.from_mapping(config)
    rule = profile.graph.function_normalization.rules[0]
    self.assertEqual(rule.id, "amd-ip-versioned-functions")
    self.assertEqual(rule.canonical, "{ip_block}_{operation}")
    self.assertEqual(rule.merge_policy.mode, "concept_with_implementations")
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_resolver_profiles.ResolverProfileTests.test_resolver_profile_loads_graph_function_normalization_rules -v
```

Expected: FAIL because `ResolverProfile` has no `graph` config parser.

- [ ] **Step 3: Implement minimal parser types**

Add small dataclasses or typed dictionaries for graph normalization config. Keep
the fields optional so old YAML remains valid. Reject missing rule `id`,
`match`, or `canonical` when `enabled: true`.

- [ ] **Step 4: Add linux-amdgpu YAML rule**

Add this under `configs/resolvers/linux-amdgpu.yaml`:

```yaml
graph:
  function_normalization:
    enabled: true
    rules:
      - id: amd-ip-versioned-functions
        enabled: true
        match: "^(?P<ip_block>gfxhub|mmhub|gfx|sdma|gmc|nbio|df|ih)_v(?P<ip_version>\\d+_\\d+(?:_\\d+)?)_(?P<operation>.+)$"
        canonical: "{ip_block}_{operation}"
        merge_policy:
          mode: concept_with_implementations
          warn_register_overlap_below: 0.35
          split_register_overlap_below: 0.10
  register_normalization:
    identity: "register:{ip}:{symbol}"
```

- [ ] **Step 5: Run resolver tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_resolver_profiles -v
```

Expected: PASS.

## Task 2: Project Versioned Functions Into Concept Nodes

**Files:**
- Modify: `packages/core/src/asip/storage.py`
- Test: `packages/core/tests/test_storage_graph.py`

- [ ] **Step 1: Write the failing concept merge test**

Add this helper inside `StorageGraphTests`:

```python
def _add_function_register_edge(
    self,
    store,
    raw_function_name,
    register_symbol,
    *,
    path,
    ip="GC",
    ip_version="unknown",
    relation="writes",
    field=None,
):
    provenance = {
        "extractor": "code_graph",
        "function": raw_function_name,
        "corpus_id": "linux-amdgpu",
        "repo": "linux",
        "path": path,
        "line_start": 10,
        "line_end": 10,
        "ip": ip,
        "ip_version": ip_version,
    }
    if field:
        provenance["field"] = field
    store.add_edge(
        raw_function_name,
        register_symbol,
        relation,
        0.95,
        stage="deterministic",
        source="clang_text_spans",
        path=path,
        line_start=10,
        line_end=10,
        provenance=provenance,
    )
```

```python
def test_function_concept_nodes_merge_versioned_implementations(self):
    store = AsipStore.connect(":memory:")
    store.migrate()
    self._add_function_register_edge(
        store,
        raw_function_name="gfxhub_v11_5_0_gart_enable",
        register_symbol="GCVM_L2_CNTL",
        path="drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c",
        ip="GC",
        ip_version="11_5_0",
        relation="sets_field",
        field="ENABLE_L2_CACHE",
    )
    self._add_function_register_edge(
        store,
        raw_function_name="gfxhub_v12_0_gart_enable",
        register_symbol="GCVM_L2_CNTL",
        path="drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
        ip="GC",
        ip_version="12_0",
        relation="sets_field",
        field="ENABLE_L2_CACHE",
    )
    graph = store.global_graph_networkx(limit=100, function_view="concept")
    function_nodes = [n for n in graph["nodes"] if n["kind"] == "function"]
    self.assertEqual(len(function_nodes), 1)
    self.assertEqual(function_nodes[0]["attr"]["function_name"], "gfxhub_gart_enable")
    self.assertCountEqual(
        function_nodes[0]["attr"]["raw_function_names"],
        ["gfxhub_v11_5_0_gart_enable", "gfxhub_v12_0_gart_enable"],
    )
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_nodes_merge_versioned_implementations -v
```

Expected: FAIL because function IDs still use raw path/name identity.

- [ ] **Step 3: Implement concept projection helper**

Add helper behavior near `_function_graph_node()`:

```python
def _normalize_function_concept(function_name: str, profile_rules: Sequence[GraphFunctionRule]) -> FunctionConcept:
    for rule in profile_rules:
        if not rule.enabled:
            continue
        match = rule.pattern.match(function_name)
        if not match:
            continue
        values = match.groupdict()
        canonical = rule.canonical.format(**values)
        return FunctionConcept(
            id=f"function:concept:{rule.id}:{canonical}",
            function_name=canonical,
            raw_function_name=function_name,
            attrs=values,
            merge_policy=rule.merge_policy,
        )
    return FunctionConcept.raw(function_name)
```

Return raw identity when no rule matches. Return concept identity plus attrs when
a rule matches. Preserve raw implementation metadata before node merge.

- [ ] **Step 4: Run storage graph tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_storage_graph -v
```

Expected: PASS after updating any assertions that intentionally inspect raw
function IDs to use `function_view="implementation"`.

## Task 3: Preserve Divergent Register Accesses

**Files:**
- Modify: `packages/core/src/asip/storage.py`
- Test: `packages/core/tests/test_storage_graph.py`

- [ ] **Step 1: Write the failing divergence test**

```python
def test_function_concept_preserves_different_register_accesses(self):
    store = AsipStore.connect(":memory:")
    store.migrate()
    self._add_function_register_edge(
        store,
        "gfxhub_v11_5_0_gart_enable",
        "GCVM_L2_CNTL",
        path="drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c",
        ip_version="11_5_0",
    )
    self._add_function_register_edge(
        store,
        "gfxhub_v12_0_gart_enable",
        "GCVM_CONTEXT0_PAGE_TABLE_BASE",
        path="drivers/gpu/drm/amd/amdgpu/gfxhub_v12_0.c",
        ip_version="12_0",
    )
    graph = store.global_graph_networkx(limit=100, function_view="concept")
    node = next(n for n in graph["nodes"] if n["kind"] == "function")
    self.assertEqual(node["attr"]["merge_status"], "divergent")
    destinations = {edge["dst"] for edge in graph["edges"] if edge["src"] == node["id"]}
    self.assertIn("register:GC:GCVM_L2_CNTL", destinations)
    self.assertIn("register:GC:GCVM_CONTEXT0_PAGE_TABLE_BASE", destinations)
    for edge in graph["edges"]:
        if edge["src"] == node["id"]:
            self.assertIn("implementations", edge["attr"])
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_preserves_different_register_accesses -v
```

Expected: FAIL because edge-level implementation provenance is not attached to
merged concept edges.

- [ ] **Step 3: Implement edge provenance aggregation**

When product edges merge, union `attr.accesses`, `attr.fields`, `attr.source`,
and `attr.implementations`. Compute register overlap per concept and set
`merge_status` to `merged`, `divergent`, or `split` according to the resolver
policy.

- [ ] **Step 4: Run storage graph tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_storage_graph -v
```

Expected: PASS.

## Task 4: Add Inspector/Implementation View

**Files:**
- Modify: `packages/core/src/asip/storage.py`
- Modify: `packages/core/src/asip/workbench.py`
- Test: `packages/core/tests/test_workbench_query_schema.py`
- Test: `packages/core/tests/test_workbench_live.py`

- [ ] **Step 1: Write query graph test**

```python
def test_register_query_graph_uses_concept_function_with_raw_implementations(self):
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "asip.db"
        store = AsipStore.connect(str(db_path))
        store.migrate()
        store.add_edge(
            "gfxhub_v11_5_0_gart_enable",
            "GCVM_L2_CNTL",
            "writes",
            0.95,
            stage="deterministic",
            source="clang_text_spans",
            path="drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c",
            line_start=10,
            provenance={
                "extractor": "code_graph",
                "function": "gfxhub_v11_5_0_gart_enable",
                "corpus_id": "linux-amdgpu",
                "repo": "linux",
                "path": "drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c",
                "ip": "GC",
                "ip_version": "11_5_0",
            },
        )
        graph = graph_for_rows([{"symbol": "GCVM_L2_CNTL"}], db_path)
    function_nodes = [n for n in graph["nodes"] if n["kind"] == "function"]
    self.assertTrue(any("raw_implementations" in n["attr"] for n in function_nodes))
    self.assertTrue(any("gfxhub_v11_5_0_gart_enable" in n["attr"]["raw_function_names"] for n in function_nodes))
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_register_query_graph_uses_concept_function_with_raw_implementations -v
```

Expected: FAIL because query graph does not expose raw implementation attrs.

- [ ] **Step 3: Thread function-view/profile config through Workbench**

Make default query/global graph use concept projection. Add an internal
implementation-view option for debugging or inspector expansion without
changing persisted raw edges.

- [ ] **Step 4: Run workbench graph tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_workbench_query_schema packages.core.tests.test_workbench_live -v
```

Expected: PASS.

## Task 5: Web/API Contract Smoke

**Files:**
- Modify: `apps/web/tests/workbench-api.spec.ts` only if JSON shape changes
- Create: `docs/qa/2026-05-18-g03-function-normalization-qa.md`

- [ ] **Step 1: Add API assertion if needed**

If the graph API payload now includes normalized function attrs, assert that a
fixture graph response exposes `attr.raw_implementations` and does not expose
wrapper/macro nodes.

- [ ] **Step 2: Run targeted Web API test**

Run:

```bash
pnpm --filter web test:ui apps/web/tests/workbench-api.spec.ts -g "graph"
```

Expected: PASS.

- [ ] **Step 3: Run core targeted suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_resolver_profiles packages.core.tests.test_storage_graph packages.core.tests.test_workbench_query_schema packages.core.tests.test_workbench_live -v
```

Expected: PASS.

- [ ] **Step 4: Record QA**

Create `docs/qa/2026-05-18-g03-function-normalization-qa.md` with:

- tests run and results,
- fixture graph before/after counts,
- proof that raw SQLite edge provenance still contains raw function names,
- proof that product graph hides raw implementation duplicates by default,
- proof that inspector/debug expansion exposes raw implementations and accesses.

- [ ] **Step 5: Run diff check**

Run:

```bash
git diff --check
```

Expected: PASS.
