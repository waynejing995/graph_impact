# G03 Cross-Repo Register Merge QA

Date: 2026-05-18

Status: pass for product graph register identity and default graph visibility;
known different `ip_version` values still remain separate nodes.

## Why This Was Failing

Raw deterministic edges already showed both indexed repos touching the same
canonical register names. For example, `IH_RB_CNTL` had edge provenance from
both `linux-amdgpu` and `mxgpu`.

The product graph layer was still splitting unknown-version registers by source
scope:

```text
register:IH:unknown:linux-amdgpu:IH_RB_CNTL
register:IH:unknown:mxgpu:IH_RB_CNTL
```

That made the graph look like the two repositories were not connected by shared
hardware registers. This was wrong for the BoxMatrix node schema: `source` is a
node attribute, not part of register identity.

## Fix

Register node identity is now:

```text
register:{ip}:{symbol}
```

Source records are merged into `attr.source`. Known different IP versions still
stay separate, for example:

```text
register:GC:GCVM_L2_CNTL attr.ip_versions = ["11.0", "12.0", ...]
```

## Live DB Evidence

Raw SQLite evidence over `data/asip.db`:

```text
sqlite3 data/asip.db "
select dst, group_concat(distinct json_extract(provenance_json,'$.corpus_id')), count(*)
from edges
where dst='IH_RB_CNTL' and stage='deterministic'
group by dst;"

IH_RB_CNTL|linux-amdgpu,mxgpu|121
```

Product graph evidence through core:

```text
PYTHONPATH=packages/core/src python3 - <<'PY'
from pathlib import Path
from asip.workbench import global_graph
g = global_graph(Path('data/asip.db'), limit=None, all_edges=True)
regs = [n for n in g['nodes'] if n.get('kind') == 'register' and n.get('label') == 'IH_RB_CNTL']
print(len(regs))
for n in regs:
    print(n['id'], sorted({s.get('corpus_id') for s in n['attr']['source']}), len(n['attr']['source']))
PY

4
register:IH:IH_RB_CNTL ['linux-amdgpu', 'mxgpu'] 63
```

Product graph evidence through the live Web BFF at `http://127.0.0.1:3100`:

```text
curl -sS 'http://127.0.0.1:3100/api/workbench/graph?limit=all' -o /tmp/asip-global-graph.json
python3 - <<'PY'
import json
from pathlib import Path
g = json.loads(Path('/tmp/asip-global-graph.json').read_text())
regs = [n for n in g.get('nodes', []) if n.get('kind') == 'register' and n.get('label') == 'IH_RB_CNTL']
print('nodes', len(g.get('nodes', [])), 'edges', len(g.get('edges', [])), 'IH_RB_CNTL nodes', len(regs))
for n in regs:
    sources = n.get('attr', {}).get('source') or []
    print(n.get('id'), sorted({s.get('corpus_id') for s in sources}), len(sources))
PY

nodes 14640 edges 34225 IH_RB_CNTL nodes 1
register:IH:IH_RB_CNTL ['linux-amdgpu', 'mxgpu'] 63
```

Default-budget product graph evidence through core:

```text
PYTHONPATH=packages/core/src python3 - <<'PY'
from pathlib import Path
from asip.workbench import global_graph
for limit in (300, 1000, 3000, 8000):
    g = global_graph(Path('data/asip.db'), limit=limit)
    shared = []
    for n in g['nodes']:
        if n.get('kind') == 'register':
            srcs = {s.get('corpus_id') for s in n.get('attr', {}).get('source') or []}
            if 'linux-amdgpu' in srcs and 'mxgpu' in srcs:
                shared.append(n)
    ih = [n for n in shared if n['label'] == 'IH_RB_CNTL']
    related = [e for e in g['edges'] if 'register:IH:IH_RB_CNTL' in (str(e.get('src')), str(e.get('dst')))]
    print(f"limit={limit} nodes={len(g['nodes'])} edges={len(g['edges'])} shared_regs={len(shared)} ih={len(ih)} ih_edges={len(related)}")
    for e in related[:2]:
        print(" ", e['src'], e['relation'], e['dst'], e['weight'])
PY

limit=300 nodes=317 edges=300 shared_regs=19 ih=1 ih_edges=2
  function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/cik_ih.c:cik_ih_disable_interrupts reads register:IH:IH_RB_CNTL 0.97
  function:mxgpu:libgv/core/hw/AI/mi200/mi200_irqmgr.c:mi200_ih_get_wptr maps_base register:IH:IH_RB_CNTL 0.97
limit=1000 nodes=1015 edges=1000 shared_regs=57 ih=1 ih_edges=2
  function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/cik_ih.c:cik_ih_disable_interrupts reads register:IH:IH_RB_CNTL 0.97
  function:mxgpu:libgv/core/hw/AI/mi200/mi200_irqmgr.c:mi200_ih_get_wptr maps_base register:IH:IH_RB_CNTL 0.97
limit=3000 nodes=2813 edges=3000 shared_regs=150 ih=1 ih_edges=2
  function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/cik_ih.c:cik_ih_disable_interrupts reads register:IH:IH_RB_CNTL 0.97
  function:mxgpu:libgv/core/hw/AI/mi200/mi200_irqmgr.c:mi200_ih_get_wptr maps_base register:IH:IH_RB_CNTL 0.97
limit=8000 nodes=7030 edges=8000 shared_regs=176 ih=1 ih_edges=14
  function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/cik_ih.c:cik_ih_disable_interrupts reads register:IH:IH_RB_CNTL 0.97
  function:mxgpu:libgv/core/hw/AI/mi200/mi200_irqmgr.c:mi200_ih_get_wptr maps_base register:IH:IH_RB_CNTL 0.97
```

Default-budget product graph evidence through the live Web BFF:

```text
curl -sS 'http://127.0.0.1:3100/api/workbench/graph?limit=3000' -o /tmp/asip-graph-3100-default.json
python3 - <<'PY'
import json
g = json.load(open('/tmp/asip-graph-3100-default.json'))
shared = []
for n in g.get('nodes', []):
    if n.get('kind') == 'register':
        srcs = {s.get('corpus_id') for s in n.get('attr', {}).get('source') or []}
        if 'linux-amdgpu' in srcs and 'mxgpu' in srcs:
            shared.append(n)
ih = [n for n in shared if n.get('label') == 'IH_RB_CNTL']
related = [e for e in g.get('edges', []) if 'register:IH:IH_RB_CNTL' in (str(e.get('src')), str(e.get('dst')))]
print('nodes', len(g.get('nodes', [])), 'edges', len(g.get('edges', [])))
print('shared_regs', len(shared), 'ih', len(ih), 'ih_edges', len(related))
for e in related[:2]:
    print(e.get('src'), e.get('relation'), e.get('dst'), e.get('weight'))
PY

nodes 2687 edges 3000
shared_regs 149 ih 1 ih_edges 2
function:linux-amdgpu:drivers/gpu/drm/amd/amdgpu/cik_ih.c:cik_ih_disable_interrupts reads register:IH:IH_RB_CNTL 0.97
function:mxgpu:libgv/core/hw/AI/mi200/mi200_irqmgr.c:mi200_ih_get_wptr maps_base register:IH:IH_RB_CNTL 0.97
```

Browser QA:

- 2K `/graph` screenshot: `docs/qa/browser/graph-cross-repo-register-default-2k.png`
- Page metrics: `graph edges: 3000`, loaded budget `3000 / 20000`,
  visible `1000 / 2813` nodes and `3000 / 3000` loaded edges.
- Layer header: `deterministic: 2989 semantic: 11`.
- Follow-up UI clarity fix: the force graph now counts visible shared-register
  nodes with `data-shared-register-count` and renders shared register nodes
  with a double-ring marker. This addresses the user-visible problem where
  the two corpora were connected in data but the bridge was hard to see in the
  dense force layout.
- Red/green evidence for that UI contract:

```text
pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts -g "graph route renders API-backed weighted relation graph" --reporter=list

RED: expected data-shared-register-count="1"; received null
GREEN: 1 passed
```

## Tests

Targeted:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_register_nodes_merge_by_symbol_ip_and_ip_version_across_sources \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_global_graph_budget_preserves_cross_repo_register_bridge_edges \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_global_graph_keeps_smn_prefixed_registers_without_keyword_hints \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_global_graph_returns_weighted_edges_without_seed \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_global_graph_links_code_functions_to_register_operations \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_global_graph_creates_document_section_nodes_from_indexed_chunks \
  -v

OK
```

Focused rerun for the cross-repo bridge regression:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_global_graph_budget_preserves_cross_repo_register_bridge_edges \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_register_nodes_merge_by_symbol_ip_and_ip_version_across_sources \
  -v

Ran 2 tests in 0.011s
OK
```

Broader graph/query:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_storage_graph \
  packages.core.tests.test_workbench_live \
  packages.core.tests.test_workbench_query_schema \
  -v

Ran 107 tests in 4.036s
OK (skipped=2)
```

Full core:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v

Ran 236 tests in 38.406s
OK (skipped=2)
```

API/MCP:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest apps.api.tests.test_app apps.mcp.tests.test_tools apps.mcp.tests.test_server -v

Ran 47 tests in 47.150s
OK (skipped=1)
```

Web route/visual:

```text
pnpm --filter web exec tsc --noEmit
pnpm --filter web run lint
pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts --reporter=list

15 passed (31.5s)
```

## Visibility Note

The default global graph selector now protects representative cross-repo
register bridge edges before filling the rest of the graph budget. The UI can
still show only a visible subset of nodes for legibility, but the loaded default
graph no longer drops the key cross-repo bridge class that made the two repos
look disconnected.
