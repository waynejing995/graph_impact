# G14 Static And Limit Cleanup QA

Date: 2026-05-18

Status: pass for the latest static graph fallback and hidden-limit cleanup slice.

## Scope

This QA records the cleanup requested after the user called out static-looking graph/query behavior and hidden hardcoded limits.

Implemented changes:

- Query semantic-edge generation now uses `semantic.queryLimit` from `configs/workbench-limits.json` instead of reusing the batch candidate limit.
- The Web query path no longer creates a synthetic row-derived graph when the API omits `graph`; it renders an explicit `No graph data returned.` state.
- Query metrics no longer fabricate `graph edges` from row count when the API omits graph data.
- The Web graph BFF clamps normal requested graph limits to the configured `graph.maxEdgeBudget`; explicit full/all graph requests remain separate.
- Function-node graph queries now use persisted graph edges when evidence rows are absent instead of reporting an empty graph for real function nodes.

## Tests

Targeted Web tests:

```text
pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts \
  -g "query graph reports omitted graph payload|graph page sends user configured semantic generation limits|graph page runs semantic edge generation through the workbench API" \
  --reporter=list

3 passed
```

Full Web API + smoke:

```text
pnpm --filter web exec playwright test tests/workbench-api.spec.ts tests/workbench-smoke.spec.ts --reporter=list

75 passed
```

Final combined Web API + smoke + visual route rerun:

```text
pnpm --filter web exec playwright test tests/workbench-api.spec.ts tests/workbench-smoke.spec.ts tests/visual-anchor-routes.spec.ts --reporter=list

90 passed
```

Lint:

```text
pnpm --filter web run lint

passed
```

TypeScript:

```text
pnpm --filter web exec tsc --noEmit

passed
```

Core regression for function-node graph fallback:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_query_evidence_expands_graph_when_query_matches_function_node_without_evidence_rows \
  -v

OK
```

## Browser Evidence

The default `/graph` page now shows live graph counts from the API:

```text
graph edges: 3000
layers deterministic: 2989 semantic: 11
visible nodes: 1000 / 2805
```

Screenshot:

```text
docs/qa/browser/graph-after-full-backfill-and-query-fallback-2k.png
```

The function query `gfx_v11_0_hw_init` shows `matches: 0` but still renders `36` graph edges from the live persisted graph:

```text
docs/qa/browser/graph-function-query-fallback-2k.png
```

## Residual

This does not close every future UI truthfulness risk. G14 remains tied to the final route-by-route audit and G11 git gate, but this slice removes the current hidden static graph fallback and hardcoded semantic query limit.
