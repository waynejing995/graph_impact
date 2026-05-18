# G03 Cross-Repo Register Merge QA

Date: 2026-05-18

Status: pass for product graph register identity; known different
`ip_version` values still remain separate nodes.

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
register:{ip}:{ip_version}:{symbol}
```

Source records are merged into `attr.source`. Known different IP versions still
stay separate, for example:

```text
register:GC:11.0:GCVM_L2_CNTL
register:GC:12.0:GCVM_L2_CNTL
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
register:IH:unknown:IH_RB_CNTL ['linux-amdgpu', 'mxgpu'] 48
register:IH:6.0:IH_RB_CNTL ['linux-amdgpu'] 5
register:IH:6.1:IH_RB_CNTL ['linux-amdgpu'] 5
register:IH:7.0:IH_RB_CNTL ['linux-amdgpu'] 5
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

nodes 15919 edges 34225 IH_RB_CNTL nodes 4
register:IH:unknown:IH_RB_CNTL ['linux-amdgpu', 'mxgpu'] 48
register:IH:6.0:IH_RB_CNTL ['linux-amdgpu'] 5
register:IH:6.1:IH_RB_CNTL ['linux-amdgpu'] 5
register:IH:7.0:IH_RB_CNTL ['linux-amdgpu'] 5
```

## Tests

Targeted:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_register_nodes_merge_by_symbol_ip_and_ip_version_across_sources \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_global_graph_keeps_smn_prefixed_registers_without_keyword_hints \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_global_graph_returns_weighted_edges_without_seed \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_global_graph_links_code_functions_to_register_operations \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_global_graph_creates_document_section_nodes_from_indexed_chunks \
  -v

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

Ran 234 tests in 23.762s
OK (skipped=2)
```

API/MCP:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest apps.api.tests.test_app apps.mcp.tests.test_tools apps.mcp.tests.test_server -v

Ran 47 tests in 39.889s
OK (skipped=1)
```

## Remaining UI Note

The default global graph budget can still hide a particular shared register if
that register is outside the selected edge budget. That is a visibility/budget
issue, not a node-identity split: requesting the full graph or querying the
register now uses the shared register identity.
