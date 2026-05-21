# ASIP Product Graph V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the default ASIP graph a real global weighted graph over exactly `function`, `register`, and `doc` product nodes, with deterministic Stage 1 facts, LLM Stage 2 semantic overlays, no-mock Web/API/MCP acceptance, and profiled large-graph behavior.

**Architecture:** Keep SQLite raw facts lossless, project them through a resolver-configured product graph schema, then render a budgeted/filterable view graph. Stage 1 owns deterministic code/register/callback facts; Stage 2 owns doc boxes and semantic edges; acceptance validates product output across CLI/API/MCP/Web rather than trusting surface labels.

**Tech Stack:** Python core, SQLite FTS5, NetworkX, resolver YAML, Ollama/OpenAI-compatible provider config, FastAPI, MCP tools, Next.js, shadcn/Radix primitives, `react-force-graph-2d` now with a Sigma/Graphology performance spike only after profiling.

---

## File Structure

- Create: `packages/core/src/asip/graph_schema.py`
- Create: `packages/core/tests/test_graph_schema.py`
- Modify: `packages/core/src/asip/storage.py`
- Modify: `packages/core/src/asip/workbench.py`
- Modify: `packages/core/src/asip/code_graph.py`
- Modify: `packages/core/src/asip/semantic_edges.py`
- Modify: `packages/core/src/asip/acceptance.py`
- Modify: `packages/core/src/asip/resolver_profiles.py`
- Modify: `configs/resolvers/*.yaml`
- Modify: `apps/api/main.py`
- Modify: `apps/mcp/tools.py`
- Modify: `apps/mcp/server.py`
- Modify: `apps/web/app/api/workbench/graph/route.ts`
- Modify: `apps/web/app/api/workbench/query/route.ts`
- Modify: `apps/web/app/api/workbench/acceptance/run/route.ts`
- Modify: `apps/web/components/workbench-page.tsx`
- Modify: `apps/web/components/weighted-force-graph.tsx`
- Modify: `apps/web/tests/workbench-api.spec.ts`
- Modify: `apps/web/tests/workbench-smoke.spec.ts`
- Modify: `docs/gaps/2026-05-16-g03-dynamic-weighted-graph.md`
- Modify: `docs/gaps/2026-05-16-g10-testing-acceptance-visual-qa.md`
- Modify: `docs/gaps/2026-05-16-g11-completion-gate.md`
- Modify: `docs/gaps/2026-05-16-g15-performance-smoke-deterministic-rebuild.md`
- Create or update: `docs/qa/2026-05-19-product-graph-v2-final-qa.md`

### Task 1: Central Product Graph Schema

**Files:**
- Create: `packages/core/src/asip/graph_schema.py`
- Create: `packages/core/tests/test_graph_schema.py`
- Modify: `packages/core/src/asip/storage.py`
- Modify: `packages/core/src/asip/workbench.py`

- [ ] **Step 1: Write failing schema tests**

```python
from asip.graph_schema import (
    ALLOWED_PRODUCT_NODE_KINDS,
    ALLOWED_PRODUCT_RELATIONS,
    is_product_node_kind,
    normalize_graph_relation,
    product_endpoint_kind,
)


def test_product_schema_allows_only_three_node_kinds():
    assert ALLOWED_PRODUCT_NODE_KINDS == {"function", "register", "doc"}
    for bad in ["macro", "field", "source", "provider", "doc_box", "pdf_section"]:
        assert not is_product_node_kind(bad)


def test_relation_normalization_is_enum_bound():
    assert normalize_graph_relation("field_set") == "sets_field"
    assert normalize_graph_relation("REG_SET_FIELD") == "sets_field"
    assert normalize_graph_relation("contains_box") == "contains"
    assert normalize_graph_relation("checks_mask") == "relates_to"
    assert normalize_graph_relation("wraps") is None


def test_endpoint_kind_rejects_macro_field_and_local_tokens():
    assert product_endpoint_kind("gfx_v11_0_hw_init") == "function"
    assert product_endpoint_kind("GCVM_L2_CNTL") == "register"
    assert product_endpoint_kind("docs/guide.md#programming-registers") == "doc"
    for bad in ["WREG32", "REG_SET_FIELD", "ENABLE_L2_CACHE", "tmp", "value", "ops"]:
        assert product_endpoint_kind(bad) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
  python3 -m pytest packages/core/tests/test_graph_schema.py -q
```

Expected: fail because `asip.graph_schema` does not exist or storage/workbench still own scattered schema rules.

- [ ] **Step 3: Implement `graph_schema.py`**

Add enum constants, relation map, provenance-only relation names, and endpoint helpers. The first implementation should be conservative: return `None` for uncertain endpoints instead of inventing product nodes.

- [ ] **Step 4: Wire schema into storage/workbench**

Replace local relation and endpoint checks in storage/workbench semantic persistence with the shared helpers. Keep raw relation and raw endpoint values in provenance when a fact is dropped or normalized.

- [ ] **Step 5: Run schema tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
  python3 -m pytest packages/core/tests/test_graph_schema.py -q
```

Expected: pass.

### Task 2: Register Inventory And Resolver Prefix Rules

**Files:**
- Modify: `packages/core/src/asip/code_graph.py`
- Modify: `packages/core/src/asip/resolver_profiles.py`
- Modify: `configs/resolvers/linux-amdgpu.yaml`
- Test: `packages/core/tests/test_resolver_profiles.py`
- Test: `packages/core/tests/test_storage_graph.py`

- [ ] **Step 1: Add failing tests for AMD register forms**

Add tests that prove configured inventory accepts `regGCVM_L2_CNTL`, `mmGCVM_L2_CNTL`, `smnMP1_FIRMWARE_FLAGS`, and configured lowercase-family forms when the resolver says so, while rejecting `tmp`, `adapt`, `value`, wrapper names, and helper calls without a real register token.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  packages.core.tests.test_resolver_profiles \
  packages.core.tests.test_storage_graph -v
```

Expected: at least the new prefix/lowercase-register tests fail.

- [ ] **Step 3: Add resolver YAML register inventory config**

Extend resolver graph config with an explicit inventory section:

```yaml
graph:
  register_inventory:
    prefixes:
      - prefix: reg
        case: mixed
      - prefix: mm
        case: mixed
      - prefix: smn
        case: mixed
    reject_tokens: [tmp, value, adapt, data, ops, funcs]
```

- [ ] **Step 4: Apply inventory rules during deterministic extraction and product projection**

Use configured rules to canonicalize accepted register symbols and reject helper/local tokens. Do not turn wrappers or fields into nodes.

- [ ] **Step 5: Run targeted tests**

Expected: new register inventory tests pass and existing resolver/profile tests remain green.

### Task 3: Stage 1 Typed Callback Truthfulness

**Files:**
- Modify: `packages/core/src/asip/code_graph.py`
- Test: `packages/core/tests/test_code_graph.py`
- Test: `packages/core/tests/test_workbench_live.py`

- [ ] **Step 1: Add failing callback tests**

Add fixtures where two structs share a slot name such as `hw_init`, but only one receiver type matches the call. Add a second fixture where the receiver type is unknown and the edge must be marked ambiguous instead of exact.

- [ ] **Step 2: Run tests**

Expected: current generic receiver logic overlinks or lacks ambiguity provenance.

- [ ] **Step 3: Implement typed evidence boundary**

Use available `clang_ast_json` receiver type data when present. Emit exact `calls` only when the receiver type/table can be proven. Emit lower-confidence `vtable_dispatch` provenance for ambiguous paths, but project it to product `calls` only with `attr.dispatch="ambiguous"`.

- [ ] **Step 4: Run callback suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  packages.core.tests.test_code_graph \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_cross_file_vtable_callbacks_to_registers \
  -v
```

Expected: pass, with no claim of full clangd/libclang cross-TU coverage.

### Task 4: Function/Register Product Normalization

**Files:**
- Modify: `packages/core/src/asip/storage.py`
- Modify: `configs/resolvers/linux-amdgpu.yaml`
- Test: `packages/core/tests/test_storage_graph.py`
- Test: `packages/core/tests/test_workbench_backend_state.py`

- [ ] **Step 1: Add merge-policy tests**

Assert that versioned AMD functions merge only through resolver YAML, duplicate rule ids are profile-scoped, raw implementations are preserved, different register neighborhoods create union edges, low overlap marks `divergent`, disjoint overlap marks `split_recommended`, and implementation view still exposes raw functions.

- [ ] **Step 2: Run tests**

Expected: any missing profile-scope or merge-status behavior fails.

- [ ] **Step 3: Implement or tighten projection**

Keep concept ids namespaced by resolver profile and rule id. Keep `edge.attr.implementations` and `node.attr.raw_implementations`. Do not collapse across IP block or language without an explicit YAML rule.

- [ ] **Step 4: Run normalization tests**

Expected: storage/backend state tests pass.

### Task 5: Docs, PDF, And LLM Semantic Edge Projection

**Files:**
- Modify: `packages/core/src/asip/workbench.py`
- Modify: `packages/core/src/asip/semantic_edges.py`
- Test: `packages/core/tests/test_workbench_live.py`
- Test: `packages/core/tests/test_semantic_edges.py`
- Test: `apps/api/tests/test_app.py`
- Test: `apps/mcp/tests/test_tools.py`

- [ ] **Step 1: Add failing tests for product-only semantic endpoints**

Assert Markdown/PDF sections project to `kind=doc`, LLM doc boxes include `inputs`, `outputs`, and `constraints`, and generated semantic edges reject field/helper/provider/local endpoints.

- [ ] **Step 2: Run tests**

Expected: tests fail if prompts still invite non-enum relations or if field endpoints persist.

- [ ] **Step 3: Tighten prompts and validators**

Change provider prompts to use only product relation enum values. Preserve provider wording as `attr.original_relation` only after normalization. Reject endpoints that cannot project to `function`, `register`, or `doc`.

- [ ] **Step 4: Run doc/semantic/API/MCP tests**

Expected: live fake-provider tests pass and product graph contains no visible `field`, `doc_box`, `pdf_section`, or provider nodes.

### Task 6: Real Acceptance Surface Probes

**Files:**
- Modify: `packages/core/src/asip/acceptance.py`
- Modify: `apps/web/components/workbench-page.tsx`
- Modify: `apps/web/app/api/workbench/acceptance/run/route.ts`
- Test: `packages/core/tests/test_acceptance_runner.py`
- Test: `apps/web/tests/workbench-smoke.spec.ts`

- [ ] **Step 1: Add failing acceptance runner test**

Use a real temporary DB and run one query with `surfaces_checked=["CLI", "API", "MCP"]`. Assert each query result has `surface_results` with `surface`, `transport`, `status`, `db_path`, `row_count`, `graph_node_count`, and `graph_edge_count`.

- [ ] **Step 2: Run test**

Expected: fail if the runner only records labels.

- [ ] **Step 3: Implement probes**

Map CLI to core `query_evidence`, API to FastAPI query function or HTTP route, MCP to MCP tool function, and Web to `ASIP_WEB_BASE_URL` HTTP when configured. If Web HTTP is not configured, mark Web as `not_configured` and rely on separate no-mock Playwright DB-path tests; do not call that a Web pass.

- [ ] **Step 4: Make UI defaults match the gate**

Default acceptance surfaces should include CLI/API/MCP/Web in the runner UI, but the result must make clear which transports were truly exercised.

- [ ] **Step 5: Run acceptance tests**

Expected: acceptance runner tests pass and query details can expand surface-specific failures.

### Task 7: Global Graph Controls And No-Mock Web E2E

**Files:**
- Modify: `apps/web/components/workbench-page.tsx`
- Modify: `apps/web/components/weighted-force-graph.tsx`
- Modify: `apps/web/app/api/workbench/graph/route.ts`
- Modify: `apps/web/tests/workbench-api.spec.ts`
- Modify: `apps/web/tests/workbench-smoke.spec.ts`

- [ ] **Step 1: Add failing no-mock graph tests**

Create a temp SQLite DB, seed product graph data, open `/graph?dbPath=...`, wait for `data-ready=true`, assert nonzero nodes/edges, assert node kinds are only `function/register/doc`, switch function view, change weight/relation/stage/source filters, and run a free query that changes the graph request and displayed counts.

- [ ] **Step 2: Run tests**

Expected: fail if any request omits `dbPath`, if filters are component-only constants, or if relation/stage/source controls are missing.

- [ ] **Step 3: Implement visible controls**

Use shadcn/Radix controls for loaded budget, visible nodes, visible edges, weight threshold, relation filter, stage filter, source filter, function view, and explicit `budgeted/global/full` mode. Keep `react-force-graph-2d` as the renderer until profile evidence justifies Sigma/Graphology.

- [ ] **Step 4: Run Web API and smoke suites**

Expected: API/smoke tests pass with no mocked graph payload for the final graph e2e.

### Task 8: Profile Before Graph Optimization

**Files:**
- Modify: `packages/core/src/asip/cli.py`
- Modify: `packages/core/src/asip/storage.py`
- Modify: `apps/web/app/api/workbench/graph/route.ts`
- Create or update: `docs/qa/2026-05-19-product-graph-v2-final-qa.md`

- [ ] **Step 1: Capture baseline profile**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src \
  python3 -m cProfile -o /tmp/asip-query-v2.prof \
  -m asip.cli query --db data/asip.db --q 'GCVM_L2_CNTL' --limit 24

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src \
  python3 -m cProfile -o /tmp/asip-graph-v2.prof \
  -m asip.cli graph --db data/asip.db --limit 3000
```

- [ ] **Step 2: Record top cumulative costs**

Use `pstats` to record the top 30 cumulative functions for query and graph. Also record graph API curl total time, payload size, node count, edge count, and browser canvas readiness.

- [ ] **Step 3: Choose one optimization based on profile**

Only implement cache, precomputed summaries, metadata hydration changes, streaming/paging, warm workers, or renderer reducers when the profile shows that layer is the bottleneck.

- [ ] **Step 4: Capture after profile**

Repeat the same commands and write before/after numbers into the QA doc.

### Task 9: Final Verification And Documentation Gate

**Files:**
- Modify: `docs/qa/2026-05-19-product-graph-v2-final-qa.md`
- Modify: `docs/gaps/2026-05-16-g03-dynamic-weighted-graph.md`
- Modify: `docs/gaps/2026-05-16-g10-testing-acceptance-visual-qa.md`
- Modify: `docs/gaps/2026-05-16-g11-completion-gate.md`
- Modify: `docs/gaps/2026-05-16-g15-performance-smoke-deterministic-rebuild.md`

- [ ] **Step 1: Run automated suites**

Run core, API/MCP, TypeScript, Web API/smoke, visual route, and `git diff --check`.

- [ ] **Step 2: Run no-mock browser QA**

Use the in-app browser or Computer Use. Capture 2048 x 1280 screenshots for `/graph` and `/acceptance` in light and dark themes after the final UI-affecting change.

- [ ] **Step 3: Write final QA record**

The final QA doc must list DB path, provider/model, Stage 1 counts, Stage 2 counts, schema validator result, more than five real queries, AQ01-AQ09 result, API/MCP/Web parity, browser screenshots, performance profile, and accepted residuals.

- [ ] **Step 4: Review git hygiene**

Exclude local DBs, build caches, `node_modules`, `.next`, `.pytest_cache`, and transient screenshots outside committed `docs/qa`.

- [ ] **Step 5: Commit and push only after all gates pass**

Commit message should mention G03/G10/G11/G15 and product graph V2.
