# G03 Real Query Graph And Function Fallback QA

Date: 2026-05-18

Status: pass for real graph query coverage, function-node fallback, and in-app browser graph QA; full clangd/libclang cross-TU type-flow remains residual.

JSON artifact: `docs/qa/2026-05-18-g03-real-query-graph-function-fallback-qa.json`

## Scope

This QA verifies the latest G03/G14 graph changes after user review:

- the default `/graph` payload is live NetworkX/SQLite data, not static page rows;
- more than five real queries return rows and graph neighborhoods;
- function nodes that exist only in the persisted graph can be queried directly;
- the browser renders a visible weighted graph from the live API payload.

The verified DB is:

```text
/tmp/asip-provider-embed-batch-smoke-20260518-133434.db
```

## Real Query Verification

Command shape:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 - <<'PY'
from pathlib import Path
from asip.workbench import query_evidence, global_graph
# run query_evidence() over the query set below and collect graph counts
PY
```

Results:

| Query | Rows | Graph nodes | Graph edges | Relations |
| --- | ---: | ---: | ---: | --- |
| `GCVM_L2_CNTL` | 12 | 95 | 231 | calls=53, reads=38, sets_field=49, writes=88, maps_base=3 |
| `CP_INT_CNTL_RING0` | 12 | 148 | 227 | calls=107, maps_base=25, reads=19, sets_field=31, writes=45 |
| `SDMA0_QUEUE0_RB_CNTL` | 12 | 134 | 213 | calls=82, maps_base=23, reads=27, sets_field=36, writes=45 |
| `IH_RB_CNTL` | 12 | 164 | 477 | calls=99, maps_base=130, reads=72, sets_field=76, writes=100 |
| `doorbell interrupt disable` | 12 | 17 | 32 | calls=10, reads=8, sets_field=4, writes=10 |
| `SDMA0_RLC0_RB_CNTL` | 12 | 70 | 142 | calls=33, maps_base=23, reads=28, sets_field=14, writes=44 |
| `BIF_DOORBELL_INT_CNTL` | 12 | 16 | 32 | calls=10, reads=8, sets_field=4, writes=10 |
| `mmIH_RB_CNTL` | 12 | 164 | 477 | calls=99, maps_base=130, reads=72, sets_field=76, writes=100 |
| `gfx_v11_0_hw_init` | 0 | 29 | 36 | calls=36 |
| `gfxhub_v11_5_0_gart_enable` | 0 | 17 | 16 | calls=15, writes=1 |

The last two queries prove the new fallback: if evidence rows are absent but the query is a real graph endpoint, `query_evidence()` returns an empty evidence table plus a live graph expansion. It does not synthesize fake evidence rows.

CLI query smoke:

```text
for q in GCVM_L2_CNTL CP_INT_CNTL_RING0 SDMA0_QUEUE0_RB_CNTL IH_RB_CNTL \
  "doorbell interrupt disable" SDMA0_RLC0_RB_CNTL BIF_DOORBELL_INT_CNTL \
  mmIH_RB_CNTL gfx_v11_0_hw_init gfxhub_v11_5_0_gart_enable; do
  python3 -m asip.cli query --db /tmp/asip-provider-embed-batch-smoke-20260518-133434.db --q "$q" --limit 12 >/dev/null
done
```

Result: all 10 commands exited 0.

## Global Graph Verification

Global graph over the same DB:

```text
limit: 3000
nodes: 2805
edges: 3000
runtime: networkx
node kinds: function=2532, register=266, doc_box=6, doc_section=1
relations: calls=2392, writes=266, reads=180, maps_base=82, sets_field=69, contains=6, relates_to=5
```

The API route used by the Web graph returned the same shape:

```text
GET http://127.0.0.1:3100/api/workbench/graph
HTTP 200
bytes: 4810000
time: 5.422s
nodes: 2805
edges: 3000
runtime: networkx
```

## Browser QA

In-app browser, 2048 x 1280 viewport:

```text
http://127.0.0.1:3100/graph
```

Default global graph screenshot:

```text
docs/qa/browser/graph-after-full-backfill-and-query-fallback-2k.png
docs/qa/browser/graph-after-full-backfill-and-query-fallback-deep-snapshot.md
```

Observed on page:

```text
graph edges: 3000
layers deterministic: 2989 semantic: 11
visible nodes: 1000 / 2805
visible edges: 3000 / 3000
Edge: Ollama / gemma4:e4b
```

Function-node query fallback browser screenshot:

```text
docs/qa/browser/graph-function-query-fallback-2k.png
docs/qa/browser/graph-function-query-fallback-2k-snapshot.md
```

Observed on page after entering `gfx_v11_0_hw_init` and clicking `Run query`:

```text
matches: 0
graph edges: 36
layers deterministic: 36
visible nodes: 29 / 29
Relationship panel includes:
gfx_v11_0_hw_init calls gfx_v11_0_init_golden_registers
```

## RED/GREEN Test

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_query_evidence_expands_graph_when_query_matches_function_node_without_evidence_rows \
  -v

OK
```

## Residuals

- Full clangd/libclang cross-translation-unit vtable/type-flow remains a G03 residual.
- Function-node fallback exposes graph neighborhoods even when evidence rows are absent; it does not synthesize evidence rows.
- The default global graph is a budgeted 3000-edge product view; users can adjust frontend bars, and the API supports larger/all-edge requests.
