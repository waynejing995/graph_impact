# Graph Function Section Batch QA

Date: 2026-05-17
Status: Full pass for the current graph/function/section/batch gap slice

## Scope

This QA slice verifies the user-requested global graph gaps:

- global graph includes code function nodes and function-to-register/field operation edges,
- converted document chunks create document section graph nodes,
- batch semantic-edge generation can call the configured provider and persist generated edges,
- Web `/graph` can show the package-backed global graph and expose a batch semantic-edge action.

## Real Provider Settings

`python3 -m asip.cli provider-show --db data/asip.db` returned:

```text
edge: ollama / gemma4:e4b at http://localhost:11434/api/chat
embedding: ollama / nomic-embed-text:latest at http://localhost:11434/api/embeddings
```

The Web top bar also showed:

```text
Edge: Ollama / gemma4:e4b
```

## Real Global Graph Probe

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src python3 - <<'PY'
from pathlib import Path
from collections import Counter
from asip.workbench import global_graph, query_evidence

db = Path("data/asip.db")
g = global_graph(db, limit=400)
print("graph_runtime", g.get("graph_runtime"))
print("nodes", len(g["nodes"]), "edges", len(g["edges"]))
print("kind_counts", dict(Counter(node.get("kind", "unknown") for node in g["nodes"])))
print("top_relations", Counter(edge.get("relation", "") for edge in g["edges"]).most_common(10))
print("sample_function_nodes", [node["id"] for node in g["nodes"] if node.get("kind") == "code" and any(part in node["id"] for part in ["gfx_", "mi200", "navi32"])][:8])
print("sample_doc_sections", [node["id"] for node in g["nodes"] if node.get("kind") in {"doc_section", "pdf_section"}][:8])
PY
```

Observed summary:

```text
graph_runtime networkx
nodes 212 edges 400
kind_counts {'code': 32, 'register': 65, 'field': 111, 'doc_section': 1, 'doc': 3}
top_relations [('co_occurs', 277), ('read_modify_write', 76), ('field_set', 23), ('sets_field', 11), ('write', 6), ('section_mentions', 5), ('maps_base', 2)]
sample_function_nodes ['navi32_reset_grbm_soft_reset_stage_1', 'mi200_ih_iv_ring_hw_init', 'gfx_v10_0_kiq_reset_hw_queue', 'gfx_v11_init_cache_regs', 'navi32_enable_sdma', 'navi32_enable_sdma1', 'gfx_v10_0_enable_gui_idle_interrupt', 'gfx_v10_0_rlc_backdoor_autoload_config_me_cache']
sample_doc_sections ['docs/note.md#lines-1']
```

Function edge sample after batch run:

```text
gfx_v11_init_cache_regs -> ENABLE_L2_CACHE relation field_set weight 0.931
gfx_v11_init_cache_regs -> GCVM_L2_CNTL relation read_modify_write weight 0.931
```

## Real Batch Semantic-Edge Run

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src python3 -m asip.cli semantic-edges-batch --db data/asip.db --limit 2 --batch-size 1
```

Observed summary:

```text
source semantic_edge_batch_job
provider ollama
model gemma4:e4b
candidate_count 2
batch_size 1
edge_count 11
job_id 10
```

Ollama diagnostic notes:

```text
gemma4:e4b loaded through Metal
model memory about 9.7 GiB
observed Ollama RSS about 9.6 GiB
observed CPU during generation: low single digits to about 14 percent
```

This confirms the batch path is real, but `gemma4:e4b` is heavy and slow on the local machine. For routine automated tests, fake-provider tests remain the deterministic path.

## Browser Evidence

Browser target:

```text
http://127.0.0.1:3100/graph
viewport: 2048 x 1280 requested; browser snapshot reported wide 2K-class viewport
```

Observed:

```text
graph edges: 400
Edge: Ollama / gemma4:e4b
buttons: Generate semantic edges; Generate batch semantic edges
package-backed graph role: img "Global weighted network graph"
```

Screenshot:

```text
docs/qa/visual-qa-2026-05-17-graph-semantic/graph-global-2048-after-function-section-batch.png
```

## Targeted Tests

Passed:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_global_graph_creates_document_section_nodes_from_indexed_chunks \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_batch_semantic_edge_job_generates_edges_from_indexed_candidates \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_global_graph_links_code_functions_to_register_operations -v
```

Passed:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest \
  apps.api.tests.test_app.ApiAppTests.test_semantic_edges_endpoint_runs_batch_generation \
  apps.mcp.tests.test_tools.McpToolsTests.test_semantic_edges_batch_tool_generates_edges_from_indexed_candidates \
  apps.mcp.tests.test_server.McpServerTests.test_build_server_registers_all_product_tools_with_fastmcp -v
```

Passed:

```bash
pnpm --filter web exec playwright test tests/workbench-api.spec.ts -g "graph API global view derives" --reporter=list
pnpm --filter web exec playwright test tests/workbench-api.spec.ts -g "semantic edges API supports batch" --reporter=list
pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts -g "batch semantic" --reporter=list
pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts -g "shadcn Radix controls" --reporter=list
pnpm --filter web exec tsc --noEmit --incremental false --pretty false
```

## Full Regression Pass

Passed:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover packages/core/tests -v
```

Observed:

```text
Ran 90 tests
OK (skipped=1)
```

Passed:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest apps.api.tests.test_app apps.api.tests.test_runtime apps.mcp.tests.test_tools apps.mcp.tests.test_server -v
```

Observed:

```text
Ran 41 tests
OK (skipped=1)
```

Passed:

```bash
pnpm --filter web exec playwright test tests/workbench-api.spec.ts --reporter=list
```

Observed:

```text
21 passed
```

Passed:

```bash
pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts --reporter=list
```

Observed:

```text
39 passed
```

Passed:

```bash
pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts --reporter=list
```

Observed:

```text
14 passed
```

Passed:

```bash
pnpm --filter web run lint
pnpm --filter web run build
pnpm --filter web exec tsc --noEmit --incremental false --pretty false
git diff --check
```

Observed:

```text
lint passed
next build passed
tsc passed
git diff --check passed
```

## Notes And Remaining Risk

The Playwright suites mutate shared workbench state and should run sequentially. A parallel run of `workbench-api.spec.ts` and `visual-anchor-routes.spec.ts` produced a transient empty graph in one visual readiness check, while the same visual suite passed when run alone and `/api/workbench/graph` returned the expected real graph.

The deterministic test suite uses fake providers for generated semantic edges. The real local Ollama batch run above confirms the product path works with `gemma4:e4b`, but that path remains slow and hardware-dependent.

Subagent review after the pass found no P0 UI/package blocker. It flagged three concrete cleanup items that were fixed before final checks: remove unused graph types, replace the hardcoded top-bar `Index: ready` label with status derived from live corpora state, and delete unused static artifact query/graph helper functions from `apps/web/lib/workbench-data.ts` so they cannot be accidentally reconnected to product query paths.

After that cleanup, the shadcn wrappers were switched from the `radix-ui` barrel package to direct Radix primitive packages (`@radix-ui/react-select`, `@radix-ui/react-accordion`, `@radix-ui/react-checkbox`, `@radix-ui/react-label`, `@radix-ui/react-scroll-area`, `@radix-ui/react-separator`, and `@radix-ui/react-slot`). The Settings Select regression was reproduced, fixed, and rerun. Final sequential reruns passed: Web API 21, Web smoke 39, visual routes 14, lint, build, tsc, and `git diff --check`.
