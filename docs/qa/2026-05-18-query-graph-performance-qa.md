# 2026-05-18 Query Graph Performance QA

## Scope

This QA covers the query-scoped graph performance regression found while running
Web Playwright acceptance tests. The failing path was not Ollama thinking time:
`query_evidence()` was rebuilding NetworkX more than once for multi-seed query
graphs and was also spending most of its time recompiling regexes while scanning
function evidence metadata for semantic subgraphs.

## RED

Multi-seed query graph expansion rebuilt NetworkX repeatedly:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_graph_for_rows_expands_multiple_query_seeds_with_single_networkx_build -v

FAILED: expected 1 to_networkx call, observed 5 before the first fix
```

Empty multi-seed graphs still rebuilt once more through the single-seed fallback:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_graph_for_rows_returns_empty_multi_seed_graph_without_second_networkx_build -v

FAILED: expected 1 to_networkx call, observed 2
```

The no-edge multi-seed storage path also had a real implementation bug:

```text
NameError: name '_multi_seed_graph' is not defined
```

That surfaced in Web e2e for user-supplied DBs and semantic-edge fixtures.

Finally, cProfile on `query_evidence(data/asip.db, "GCVM_L2_CNTL", limit=24)`
showed the largest hot path was `_known_graph_function_metadata()` calling
`_snippet_has_callable_symbol()`, which repeatedly compiled regex patterns:

```text
_known_graph_function_metadata: 13.136s cumulative
_snippet_has_callable_symbol: 11.049s cumulative
re.search / re._compile / sre_compile: dominant cost
```

## GREEN

Implemented fixes:

- `graph_for_rows()` expands all query seeds through one `expand_graph_networkx_many()` call.
- Empty multi-seed query graphs now reuse the first multi-seed result instead of falling back to `expand_query_graph()`.
- `AsipStore.expand_graph_networkx_many()` now has a real `_multi_seed_graph()` path for DBs without expandable edges.
- `_snippet_has_callable_symbol()` uses a direct C-identifier-aware scan instead of compiling a regex per symbol.

Targeted regression tests:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_callable_symbol_scan_avoids_regex_compile_hot_path \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_networkx_multi_seed_expansion_without_edges_returns_seed_nodes \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_graph_for_rows_returns_empty_multi_seed_graph_without_second_networkx_build \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_graph_for_rows_expands_multiple_query_seeds_with_single_networkx_build \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_register_query_graph_expands_to_common_callback_backbone -v

OK
```

## Real Query Timing

Command:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src python3 - <<'PY'
import time
from pathlib import Path
from asip.workbench import query_evidence
queries = [
    'Who reads or writes regGCVM_L2_CNTL?',
    'GCVM_L2_CNTL',
    'doorbell interrupt disable',
    'amdgpu_device_ip_hw_init_phase1',
    'nv_common_hw_init',
    'SDMA0_QUEUE0_RB_CNTL',
]
for q in queries:
    started = time.perf_counter()
    result = query_evidence(Path('data/asip.db'), q, limit=24)
    elapsed = time.perf_counter() - started
    graph = result.get('graph') or {}
    print(q, elapsed, len(result.get('rows') or []), len(graph.get('nodes') or []), len(graph.get('edges') or []))
PY
```

Results:

| Query | Time | Rows | Graph nodes | Graph edges |
| --- | ---: | ---: | ---: | ---: |
| Who reads or writes regGCVM_L2_CNTL? | 4.161s | 24 | 102 | 237 |
| GCVM_L2_CNTL | 3.845s | 24 | 102 | 237 |
| doorbell interrupt disable | 0.878s | 24 | 230 | 400 |
| amdgpu_device_ip_hw_init_phase1 | 2.135s | 24 | 65 | 74 |
| nv_common_hw_init | 2.093s | 24 | 211 | 498 |
| SDMA0_QUEUE0_RB_CNTL | 2.084s | 24 | 134 | 213 |

The GCVM query path dropped from roughly 10 seconds before this slice to about
4 seconds on the same dirty `data/asip.db`.

## Acceptance Timing

Command:

```text
time PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src python3 -m asip.cli acceptance \
  --db data/asip.db \
  --full \
  --query-id AQ01 \
  --surface CLI \
  --surface Web
```

Result:

```text
26.025s total
row_count: 24
graph_node_count: 102
graph_edge_count: 237
provider checks: embedding pass, semantic_edge pass
```

The dirty dev DB acceptance status is still `fail` because old failed jobs and
not-indexed doc corpora remain in `data/asip.db`; the query execution path
returned rows and graph data, and the Web e2e acceptance route stayed under the
30s Playwright timeout.

## Automated Verification

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v
Ran 198 tests in 14.579s
OK (skipped=2)

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest \
  apps.api.tests.test_app apps.mcp.tests.test_tools apps.mcp.tests.test_server -v
Ran 45 tests in 60.871s
OK (skipped=1)

pnpm --filter web exec tsc --noEmit
passed

pnpm --filter web run lint
passed

pnpm --filter web exec playwright test tests/workbench-api.spec.ts tests/workbench-smoke.spec.ts --reporter=list
73 passed
```
