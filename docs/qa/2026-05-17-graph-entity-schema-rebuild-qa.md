# Graph Entity Schema Rebuild QA

Date: 2026-05-17

## Scope

Validated the revised product graph contract:

- Nodes are limited to `function`, `register`, `doc_section`, `pdf_section`, and `doc_box`.
- Macro wrappers, field symbols, and source paths are not graph nodes.
- Field operations remain traceable as `function -> register` edges with fields stored in `edge.attr.fields` and register/node attrs.
- Edge relations are normalized to the enum: `reads`, `writes`, `sets_field`, `maps_base`, `calls`, `contains`, `documents`, `relates_to`, `depends_on`, `configures`, `resets`.

## Commands

```bash
PYTHONPATH=packages/core/src python3 -m asip.cli graph-rebuild \
  --db data/asip.db \
  --corpus-id mxgpu \
  --corpus-id linux-amdgpu
```

Result:

```text
files=1225
edges=10108
```

Schema validation command:

```bash
PYTHONPATH=packages/core/src python3 - <<'PY'
from pathlib import Path
from collections import Counter
from asip.workbench import global_graph
allowed_nodes = {'function','register','doc_section','pdf_section','doc_box'}
allowed_edges = {'reads','writes','sets_field','maps_base','calls','contains','documents','relates_to','depends_on','configures','resets'}
graph = global_graph(Path('data/asip.db'), all_edges=True)
node_kinds = Counter(node.get('kind') for node in graph['nodes'])
edge_relations = Counter(edge.get('relation') for edge in graph['edges'])
print(len(graph['nodes']), dict(node_kinds))
print(len(graph['edges']), dict(edge_relations))
print(sum(node.get('kind') not in allowed_nodes for node in graph['nodes']))
print(sum(edge.get('relation') not in allowed_edges for edge in graph['edges']))
PY
```

Result:

```text
nodes=3078 {'register': 1597, 'function': 1481}
edges=4999 {'writes': 2217, 'reads': 1354, 'sets_field': 749, 'maps_base': 679}
invalid_nodes=0
invalid_edges=0
field_nodes_named_ENABLE_L2_CACHE=0
wrapper_nodes=0
sets_field_edges_with_fields=749
```

Regression spot check:

```text
mmhub_v9_4_set_fault_enable_default is a function node, not a register node.
out includes sets_field VML2PF0_VM_L2_PROTECTION_FAULT_CNTL.RANGE_PROTECTION_FAULT_ENABLE_DEFAULT.
```

## Real Query Checks

All checks used `data/asip.db` after rebuild.

| Query | Seed | Evidence rows | Graph nodes | Graph edges | Relations |
| --- | --- | ---: | ---: | ---: | --- |
| `IH_RB_CNTL` | `IH_RB_CNTL` | 8 | 40 | 82 | reads, writes, sets_field, maps_base |
| `BIF_DOORBELL_INT_CNTL doorbell` | `BIF_DOORBELL_INT_CNTL` | 8 | 14 | 22 | reads, writes, sets_field |
| `VML2PF0_VM_L2_PROTECTION_FAULT_CNTL fault enable` | `VML2PF0_VM_L2_PROTECTION_FAULT_CNTL` | 8 | 3 | 4 | maps_base, reads, sets_field, writes |
| `CP_INT_CNTL_RING0 interrupt` | `CP_INT_CNTL_RING0` | 8 | 5 | 9 | maps_base, reads, writes, sets_field |
| `GCVM_L2_CNTL cache` | `GCVM_L2_CNTL` | 8 | 22 | 34 | writes, reads, sets_field, maps_base |
| `SDMA0_QUEUE0_RB_CNTL queue` | `SDMA0_QUEUE0_RB_CNTL` | 8 | 9 | 10 | sets_field, reads, writes |

## Browser QA

Opened `http://127.0.0.1:3100/graph` in the in-app browser after the real rebuild.

Result:

```text
provider=Edge: Ollama / gemma4:e4b
graph_ready=true
visible_nodes=1000
visible_edges=1792
node_total=2147
edge_total=3000
strongest_weight=0.97
summary_kinds=function 635, register 365
field_kind_text=false
wrapper_label_text=false
Graph API returned 500=false
```

Note: The Web BFF needed an explicit `spawnSync` `maxBuffer` because the real graph payload exceeded Node's default stdout buffer. After setting `maxBuffer: 128 * 1024 * 1024`, `/api/workbench/graph?limit=3000` returned `200 OK` and the canvas rendered.

## Stage 2 Semantic Edge QA

Ran a real local Ollama semantic-edge job against `data/asip.db` using `gemma4:e4b`.

```bash
PYTHONPATH=packages/core/src python3 -m asip.cli semantic-edges \
  --db data/asip.db \
  --q 'IH_RB_CNTL RB_ENABLE interrupt ring buffer' \
  --limit 8
```

Result:

```text
source=semantic_edge_job
provider=ollama
model=gemma4:e4b
evidence_rows=8
edge_count=6
job_id=38
```

SQLite verification:

```text
deterministic / clang_ast = 10108
semantic / ollama = 6
semantic relations = reads 3, calls 2, writes 1
```

Product graph verification after the semantic run:

```text
nodes=3082
edges=5002
stage counts: deterministic=4999, semantic=3
semantic visible edges:
- amdgpu_amdkfd_interrupt -> kgd2kfd_interrupt writes
- amdgpu_amdkfd_device_probe -> amdgpu_amdkfd_interrupt calls
- amdgpu_amdkfd_resume_process -> amdgpu_amdkfd_interrupt calls
```

One generated edge to `kfd.dev` and the duplicated `ih_ring_entry` parameter edges remain stored as semantic raw rows, but are filtered from the product graph because temporary variables and member expressions are not allowed graph nodes.

## Additional Regression QA

New red/green checks added in this pass:

```text
packages.core.tests.test_storage_graph.StorageGraphTests.test_semantic_code_edges_do_not_promote_local_variables_to_function_nodes
packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_expand_query_graph_canonicalizes_register_seed_aliases
```

Results:

```text
2 tests OK
```

The first test prevents LLM semantic edges from promoting local variables such as `ih_ring_entry` into function nodes. The second test verifies common AMD register aliases `regGCVM_L2_CNTL`, `mmGCVM_L2_CNTL`, and `smnGCVM_L2_CNTL` all expand to the canonical register graph seed `GCVM_L2_CNTL`.

Real DB alias spot check:

```text
query=regGCVM_L2_CNTL
rows=8
graph_nodes=22
graph_edges=34
relations=writes, reads, sets_field
```

## API, MCP, And Acceptance UI QA

FastAPI and MCP regression:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest \
  apps.api.tests.test_app \
  apps.api.tests.test_runtime \
  apps.mcp.tests.test_tools \
  apps.mcp.tests.test_server -v
```

Result:

```text
Ran 41 tests in 209.814s
OK (skipped=1)
```

The skipped test is the optional live MCP runtime package check.

Acceptance page browser verification used a clean dev server on `http://127.0.0.1:3102/acceptance` after ports `3100` and `3101` became stale dev servers that accepted connections but returned zero bytes. The page was exercised through the in-app Browser at 2048 x 1280 with a mocked `/api/workbench/acceptance/run` response.

Browser result:

```json
{
  "dbPath": "/tmp/asip-ui-acceptance.db",
  "queryIds": ["AQ01", "AQ09"],
  "surfaces": ["CLI", "API", "Web", "MCP"],
  "outputJson": "docs/qa/ui-acceptance.json",
  "outputMd": "docs/qa/ui-acceptance.md",
  "feedback": "Acceptance run passed: 2/2"
}
```

Playwright config was updated so `PLAYWRIGHT_BASE_URL` and `PLAYWRIGHT_SKIP_WEB_SERVER=1` can target a known-good running server instead of hanging on a stale port.

The same `3102` dev server was used for `/graph` browser QA. The first immediate DOM snapshot showed the loading/empty state while the real graph API was still running. After waiting for the API response, the package-backed canvas rendered:

```text
has_canvas=true
canvas_css_size=1669x920
page_metrics=graph edges: 3000
visible_nodes=1000 / 2148
visible_edges=1790 / 3000
summary_kinds=function 636, register 364
No graph data returned=false
```

## Test Suites

```text
PYTHONPATH=packages/core/src:packages/core/tests python3 -m unittest discover -s packages/core/tests
129 tests passed, 1 skipped

pnpm --filter web exec tsc --noEmit
passed

pnpm --filter web exec playwright test tests/workbench-api.spec.ts tests/workbench-smoke.spec.ts --reporter=list
64 passed

pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts --reporter=list
15 passed
```

## Superseding Verification After Query/Graph Performance Fix

This section supersedes the older permission-policy note above. The session now has `danger-full-access`, and a fresh full headless Playwright run completed.

Backend fixes in this final pass:

- `expand_graph_networkx()` no longer scans all function evidence when the DB has no edges or when the selected neighborhood contains only deterministic edges.
- `global_graph_networkx()` lazily loads function metadata only when semantic edges require it.
- `find_evidence_candidates()` now prefers FTS chunk candidates instead of combining `chunk_id` with `%like%` scans over the 1.3M-row evidence table.
- SQLite migration now creates `idx_evidence_chunk_confidence` and edge endpoint/stage indexes.
- Reindexing one corpus no longer clears unrelated corpus graph edges.
- Semantic batch overfetch and retrieval vector limits are config-backed.

Real timing before/after on `data/asip.db` for `doorbell interrupt disable`:

```text
before: query_evidence total 58.228s, graph_for_rows 58.717s
after empty-edge short path: 3.835s
after FTS chunk lookup + deterministic graph lazy metadata: 0.487s
```

Current live DB graph rebuild and semantic/doc-node jobs:

```text
graph_rebuild job 42: 10108 deterministic edges from 1225 files
semantic_edges job 43: gemma4:e4b, 8 evidence rows, 6 raw semantic edges
semantic_edges job 44: gemma4:e4b, 8 evidence rows, 5 raw semantic edges
doc_nodes_batch job 45: gemma4:e4b, 2 candidates, 6 doc boxes, 11 edges
```

Current SQLite edge counts:

```text
deterministic | clang_ast | reads      | 2536
deterministic | clang_ast | writes     | 4955
deterministic | clang_ast | sets_field | 995
deterministic | clang_ast | maps_base  | 1616
deterministic | clang_ast | field_shift| 6
semantic      | ollama    | reads      | 4
semantic      | ollama    | writes     | 7
```

Current product graph sample:

```text
global_graph(limit=1500)
nodes=1123
edges=1500
node kinds: function=523, register=593, doc_box=6, doc_section=1
visible semantic edges=15
```

Fresh final test results:

```text
PYTHONPATH=packages/core/src:packages/core/tests python3 -m unittest discover -s packages/core/tests
Ran 139 tests in 3.024s
OK (skipped=1)

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest \
  apps.api.tests.test_app apps.api.tests.test_runtime apps.mcp.tests.test_tools apps.mcp.tests.test_server -v
Ran 41 tests in 72.934s
OK (skipped=1)

pnpm --filter web exec tsc --noEmit
passed

pnpm --filter web run lint
passed

pnpm --filter web exec playwright test tests/workbench-api.spec.ts tests/workbench-smoke.spec.ts --reporter=list
65 passed

pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts --reporter=list
15 passed

git diff --check
passed
```
