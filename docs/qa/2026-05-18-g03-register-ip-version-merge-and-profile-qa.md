# G03 Register IP-Version Merge And Graph Profile QA

Date: 2026-05-18
Status: PASS with residual first-load global graph cost

## Why This Exists

User review found that linux-amdgpu and MxGPU still looked weakly connected
when the same register appears under different IP versions. The schema now
treats `ip_version` as node metadata, not register identity.

Current product register identity:

```text
register:{ip}:{symbol}
```

`ip_version` remains available as `attr.ip_version`, all observed versions are
deduped into `attr.ip_versions`, and per-source provenance keeps
`source[].ip_version`.

This keeps different IP blocks separate while allowing a register name reused
across multiple generations of the same IP block to act as one conceptual
bridge node.

## Performance Profile Before Fix

Measured against `data/asip.db` before this pass:

```text
core global_graph limit=3000: 7.295s nodes=2813 edges=3000
core global_graph limit=1000: 6.732s nodes=1015 edges=1000
core query GCVM_L2_CNTL: 3.476s rows=24 graph_nodes=95 graph_edges=231
core query CP_INT_CNTL_RING0: 1.508s rows=24 graph_nodes=148 graph_edges=227
core query IH_RB_CNTL: 1.791s rows=24 graph_nodes=159 graph_edges=477
core query interrupt ring buffer: 0.858s rows=24 graph_nodes=1 graph_edges=0
curl /api/workbench/graph?limit=3000: 8.322651s, 4874009 bytes
curl /api/workbench/query?q=GCVM_L2_CNTL: 2.123145s, 203707 bytes
browser /graph: DOM 155ms, API 5379ms, force graph ready 9498ms
```

`cProfile` showed global graph time dominated by product-node metadata merging
for all persisted edges before edge-budget selection. Query profile showed
`GCVM_L2_CNTL` spent about `1.5s` in a fallback `LIKE` scan over `860516`
evidence rows and about `2.2s` rebuilding a full NetworkX graph before slicing
the query neighborhood.

## Fixes

- Register identity changed from `register:{ip}:{ip_version}:{symbol}` to
  `register:{ip}:{symbol}`.
- Evidence source records now preserve `ip` and `ip_version`.
- BoxMatrix node attrs now aggregate `ip_versions` instead of treating
  different versions as scalar conflicts.
- Sparse exact-symbol queries use indexed symbol lookup and do not fall back to
  full-table `lower(... LIKE ...)` scans.
- Query-scoped graph expansion now uses frontier edge lookup instead of building
  a full NetworkX graph for every query.
- Global graph construction now defers node metadata merges until after edge
  budget selection.
- Dense Web graphs use a lighter force-layout profile without truncating the
  API graph payload.

## Verification After Fix

```text
core global_graph limit=3000: 5.924s nodes=2687 edges=3000
core global_graph limit=1000: 4.499s nodes=941 edges=1000
core query GCVM_L2_CNTL: 0.861s rows=24 graph_nodes=52 graph_edges=216
core query CP_INT_CNTL_RING0: 0.288s rows=24 graph_nodes=117 graph_edges=201
core query IH_RB_CNTL: 0.330s rows=24 graph_nodes=135 graph_edges=457
core query gfx_v11_0_hw_init: 1.289s rows=0 graph_nodes=29 graph_edges=28
core query interrupt ring buffer: 0.192s rows=24 graph_nodes=1 graph_edges=0
expand GCVM_L2_CNTL: 0.431s nodes=52 edges=216
expand CP_INT_CNTL_RING0: 0.022s nodes=117 edges=201
expand IH_RB_CNTL: 0.053s nodes=135 edges=457
expand gfx_v11_0_hw_init: 0.040s nodes=220 edges=363
curl /api/workbench/graph?limit=3000: 6.259847s, 3935957 bytes
curl /api/workbench/query?q=GCVM_L2_CNTL: 1.247927s, 173291 bytes
browser /graph after dense profile: DOM 153ms, API 6342ms, force graph ready 9017ms
browser graph attrs: nodeCount=1000 edgeCount=1337 nodeTotal=2687 edgeTotal=3000 shared=149 layout=dense
```

Automated verification:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v
Ran 239 tests in 23.378s
OK (skipped=2)

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest apps.api.tests.test_app apps.mcp.tests.test_tools apps.mcp.tests.test_server -v
Ran 47 tests in 43.351s
OK (skipped=1)

pnpm --filter web exec tsc --noEmit
passed

pnpm --filter web run lint
passed

pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts --reporter=list
15 passed (51.0s)
```

## Residual

The first global graph request still costs several seconds because the product
graph currently builds an edge-budgeted view from persisted SQLite edge rows at
request time and the Next BFF still spawns Python per request. Query-specific
graph expansion is now the larger improvement. A future slice should add a
profiled cache or materialized graph view keyed by DB mtime/size and graph
parameters, without hardcoding user-visible limits.
