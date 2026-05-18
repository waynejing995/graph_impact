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
