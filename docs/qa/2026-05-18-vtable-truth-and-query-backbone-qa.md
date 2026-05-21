# 2026-05-18 Vtable Truth And Query Backbone QA

## User Correction

The user challenged whether Stage 1 actually does clangd vtable parsing. It does not. Current callback edges are conservative source-span callback overlays, not clangd/libclang type-flow output.

## Product Fix

- `configs/workbench-limits.json` now sets `graph.defaultHops = 2`.
- `graph_for_rows()` now reads `graph.defaultHops` from the shared limits file instead of hardcoding one hop.
- Query-scoped register graphs can now reveal `common -> callback -> register` backbones by default.
- Cross-repo register merge proof now asserts both repo function edges attach to the same normalized register node when IP/version match.

## RED / GREEN

RED:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_register_query_graph_expands_to_common_callback_backbone -v
```

Failure before the fix:

```text
('function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/amdgpu_device.c:amdgpu_device_init',
 'calls',
 'function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/gfx_v11_0.c:gfx_v11_0_hw_init')
not found in {... callback -> register only ...}
```

GREEN:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_register_query_graph_expands_to_common_callback_backbone \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_register_nodes_merge_only_when_ip_version_matches -v
```

Result:

```text
Ran 2 tests in 0.096s
OK
```

## Real DB Sanity Check

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src python3 - <<'PY'
from pathlib import Path
from asip import workbench
from collections import Counter
query_graph = workbench.graph_for_rows([{"symbol": "GCVM_L2_CNTL"}], Path("data/asip.db"))
print("query_graph", len(query_graph["nodes"]), len(query_graph["edges"]), Counter(edge["relation"] for edge in query_graph["edges"]))
for edge in query_graph["edges"]:
    if edge["relation"] == "calls" and edge.get("source") == "clang_callback":
        print("sample_callback_call", edge["src"], "->", edge["dst"], edge["source"], edge.get("confidence"))
        break
full_graph = workbench.global_graph(Path("data/asip.db"), limit=None, all_edges=True)
shared = []
for node in full_graph["nodes"]:
    if node.get("kind") != "register":
        continue
    sources = (node.get("attr") or {}).get("source") or []
    corpora = {source.get("corpus_id") for source in sources if isinstance(source, dict) and source.get("corpus_id")}
    if {"linux-amdgpu", "mxgpu"} <= corpora:
        shared.append(node)
print("shared_linux_mxgpu_register_nodes", len(shared))
for node in shared[:5]:
    print("shared_register", node["id"], node.get("label"))
PY
```

Result:

```text
query_graph 88 217 Counter({'writes': 79, 'calls': 57, 'sets_field': 42, 'reads': 36, 'maps_base': 3})
sample_callback_call function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/gfx_v11_0.c:gfx_v11_0_hw_fini -> function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/gfxhub_v11_5_0.c:gfxhub_v11_5_0_gart_disable clang_callback 0.72
shared_linux_mxgpu_register_nodes 115
shared_register register:unknown:3.0:MMVM_L2_CNTL MMVM_L2_CNTL
shared_register register:unknown:3.0:MMMC_VM_MX_L1_TLB_CNTL MMMC_VM_MX_L1_TLB_CNTL
shared_register register:unknown:3.0:MMVM_CONTEXT0_CNTL MMVM_CONTEXT0_CNTL
shared_register register:unknown:1.0:VM_L2_CNTL VM_L2_CNTL
shared_register register:unknown:1.0:MC_VM_MX_L1_TLB_CNTL MC_VM_MX_L1_TLB_CNTL
```

## Browser QA

In-app browser was opened at `http://127.0.0.1:3100/graph` with a 2048x1280 viewport after the query-backbone fix.

- Screenshot: `docs/qa/browser/graph-current-after-vtable-truth-2k.png`
- Snapshot: `docs/qa/browser/graph-current-after-vtable-truth-2k-loaded-snapshot.md`

Loaded page evidence:

```text
graph edges: 3000
layers deterministic: 2987 semantic: 13
Loaded edge budget: 3000 / 20000
Visible nodes: 1000 / 2797
Visible edges: 3000 / 3000
visible graph summary: nodes 1000, edges 1216, doc_box 6, doc_section 1, function 787, register 206
```

## Residual

This QA does not close full clangd/libclang vtable/type-flow parsing. It only fixes the product-visible query graph hiding the existing conservative callback backbone and proves cross-repo register convergence through normalized register nodes.

## 2026-05-19 Subagent Review And Current DB Smoke

A read-only subagent audit rechecked the current tree and classified the
vtable/callback evidence as strong for the MVP/product graph layer, but still
explicitly residual for full clangd/libclang cross-translation-unit vtable
correctness. The current implementation is source-span deterministic graph
extraction plus selective clang AST JSON receiver/initializer hints, not a full
clangd/libclang cursor traversal.

Focused tests were rerun by the subagent across `test_code_graph`,
`test_workbench_live`, and `test_storage_graph`; the audited vtable/alias/type
coverage passed. The remaining weak point was proving that the current
`data/asip.db` still projects callback/vtable edges into valid product graph
nodes. A current-DB smoke was run for that:

```text
PYTHONPATH=packages/core/src python3 - <<'PY'
import json
import sqlite3
from collections import Counter
from pathlib import Path
from asip.graph_filters import is_resolver_wrapper_name

db = Path("data/asip.db")
con = sqlite3.connect(db)
con.row_factory = sqlite3.Row
edge_rows = [dict(row) for row in con.execute("""
select src, dst, relation, source, provenance_json
from edges
where source = 'clang_callback'
   or provenance_json like '%vtable_dispatch%'
   or provenance_json like '%callback%'
""")]
call_kinds = Counter()
type_flows = Counter()
initializer_flows = Counter()
wrapper_endpoints = [
  endpoint
  for row in edge_rows
  for endpoint in (row["src"], row["dst"])
  if is_resolver_wrapper_name(str(endpoint))
]
for row in edge_rows:
    prov = json.loads(row.get("provenance_json") or "{}")
    if prov.get("call_kind"):
        call_kinds[str(prov.get("call_kind"))] += 1
    if prov.get("type_flow"):
        type_flows[str(prov.get("type_flow"))] += 1
    if prov.get("callback_initializer_flow"):
        initializer_flows[str(prov.get("callback_initializer_flow"))] += 1
print(len(edge_rows), dict(call_kinds), dict(type_flows), dict(initializer_flows), len(wrapper_endpoints))
PY
```

Result summary:

```text
raw_callback_like_edges=6133
call_kinds:
  vtable_dispatch=6042
  vtable_callback=70
  vtable_table_alias=21
type_flows:
  clang_ast_json=2248
callback_initializer_flows:
  text=6127
  clang_ast_json=6
wrapper_endpoint_count=0
```

A follow-up expansion smoke sampled five callback/vtable seeds from the same
DB. Each sample expanded through `AsipStore.expand_graph_networkx(...,
function_view="concept")` into product graph nodes with `node_kinds =
["function"]`; sampled edges preserved `source = clang_callback`, `relation =
calls`, source path/line provenance, and raw implementation metadata. This
strengthens the current DB evidence, but it is still not a completion claim for
full clangd/libclang vtable parsing.
