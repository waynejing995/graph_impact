# Graph Backbone Budget QA

Date: 2026-05-17
Scope: G03/G16/G17 user-review correction for the default global graph looking like disconnected point clusters.

## Complaint

The `/graph` page still looked like scattered clusters even though Stage 1 callback/common dispatch extraction had been added. The user specifically asked whether clangd/vtable parsing had really been done, because real AMD common callback paths and shared registers should connect the two corpora into a visible global network.

## Root Cause

The current Stage 1 extractor is not full clangd/libclang type-flow. It is a pragmatic clang syntax probe plus source-span, resolver, preprocessing, direct-call, and conservative ops/vtable callback overlay. That boundary remains explicit.

However, the immediate scattered-graph symptom was caused by default graph budgeting, not by absence of all callback edges:

- Full no-limit product graph from `data/asip.db`: `nodes=7692`, `edges=15404`, `components=559`, largest connected component `5131`.
- Previous default `limit=3000` product graph: `nodes=2407`, `edges=3000`, `components=443`, largest connected component `155`.
- Previous frontend-visible slice after `visibleNodeBudget=1000`: largest connected component `64`.

The callback/common dispatch edges existed in storage, but the default edge selection prioritized local high-weight register operation edges and direct calls enough that the visible graph lost the main call backbone. A separate read-only subagent audit found the same issue and observed that default output had `calls=1000` but `clang_callback_calls=0`.

## Fix

- Added a RED/GREEN storage test: `test_global_graph_budget_preserves_largest_connected_backbone`.
- Reworked `packages/core/src/asip/storage.py` global edge selection to reserve the default budget for the largest call backbone before filling the rest with high-weight edges.
- Prioritized `clang_callback` call edges inside the call backbone so common dispatch and vtable/callback structure stay visible in the default product graph.
- Increased the package-backed graph viewport height and added force-layout tuning plus initial `zoomToFit`.
- Changed the relationship panel preview to show `calls` edges first, so the inspector reflects the visible backbone instead of only the first protected/doc edges.

## Verification

Targeted RED:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest packages.core.tests.test_storage_graph.StorageGraphTests.test_global_graph_budget_preserves_largest_connected_backbone -v
```

Initial failure:

```text
AssertionError: 2 not greater than or equal to 5
```

Targeted GREEN:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest packages.core.tests.test_storage_graph.StorageGraphTests.test_global_graph_budget_preserves_largest_connected_backbone \
packages.core.tests.test_storage_graph.StorageGraphTests.test_global_graph_budget_preserves_function_call_backbone_edges \
packages.core.tests.test_storage_graph.StorageGraphTests.test_global_graph_budget_preserves_semantic_doc_box_edges -v
```

Result: `3` tests passed.

Typecheck:

```bash
pnpm --filter web exec tsc --noEmit
```

Result: passed.

Graph page Playwright subset:

```bash
pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts -g "graph page|global symbol search|free evidence query" --reporter=list
```

Result: `9` tests passed.

Full follow-up checks after the UI tuning:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest apps.api.tests.test_app apps.api.tests.test_runtime apps.mcp.tests.test_tools apps.mcp.tests.test_server -v
pnpm --filter web exec playwright test tests/workbench-api.spec.ts --reporter=list
pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts --reporter=list
pnpm --filter web run lint
git diff --check
```

Results:

- Core: `172` tests passed, `2` sqlite-vec optional skips.
- API/MCP: `42` tests passed, `1` optional MCP runtime skip.
- Web API Playwright: `25` passed.
- Web smoke Playwright: `46` passed.
- Web lint: passed.
- Diff whitespace check: passed.

## Live Default Graph After Fix

Measured through `AsipStore.global_graph_networkx(limit=3000)` against `data/asip.db`:

- `nodes=2726`
- `edges=3000`
- relation counts: `calls=2446`, `writes=257`, `reads=176`, `sets_field=84`, `maps_base=26`, `contains=6`, `relates_to=5`
- source counts: `clang_text_spans=1839`, `clang_callback=1092`, `text_fallback=56`, `ollama=13`
- components: `41`
- largest connected component: `2589`

Measured after the frontend's default visible node slice (`visibleNodeBudget=1000`):

- `nodes=1000`
- `edges=1274`
- relation counts: `calls=770`, `writes=245`, `reads=156`, `sets_field=84`, `maps_base=8`, `contains=6`, `relates_to=5`
- source counts include `clang_callback=353`
- components: `41`
- largest connected component: `877`

## Browser QA

2K viewport browser artifacts:

- Snapshot: `docs/qa/browser/graph-backbone-budget-after-fit-snapshot.md`
- Screenshot: `docs/qa/browser/graph-backbone-budget-after-fit-2k.png`

Snapshot evidence:

- Page URL: `http://127.0.0.1:3100/graph`
- Metric: `graph edges: 3000`
- Layer badge: `layers deterministic: 2987 semantic: 13`
- Relationship panel now starts with callback/common `calls` edges such as `drm_mode_config_reset calls gfx_v11_0_rlc_reset`.

## Remaining Boundary

This pass fixes the default graph selection and package-backed rendering symptom. It does not claim full clangd/libclang cursor/type-flow vtable resolution. The Stage 1 extractor remains conservative and should be treated as a product-quality interim graph builder until a full compile-database/type-flow implementation is added or explicitly deferred.
