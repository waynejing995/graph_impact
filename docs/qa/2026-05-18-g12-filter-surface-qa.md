# 2026-05-18 G12 Filter Surface QA

## Scope

This QA closes the FastAPI/MCP parity slice of G12. Core and Web already passed
`ip_block` and `asic_or_generation`; this pass verifies that the other product
surfaces do not silently ignore the same filters.

## RED

FastAPI failed because `/query` did not pass filter params to MCP/core:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest \
  apps.api.tests.test_app.ApiAppTests.test_query_endpoint_applies_ip_and_asic_filters -v

FAIL: expected one FILTER_REG row, got two FILTER_REG rows
```

MCP failed because `search_evidence()` did not accept filter args:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest \
  apps.mcp.tests.test_tools.McpToolsTests.test_search_evidence_applies_ip_and_asic_filters -v

TypeError: search_evidence() got an unexpected keyword argument 'ip_block'
```

## GREEN

Implementation:

- FastAPI `/query` accepts `ip_block`, `asic`, and `asic_or_generation`;
- MCP `search_evidence()` accepts `ip_block`, `asic_or_generation`, and `asic`;
- both surfaces pass the values to existing core `query_evidence()` filtering.

Targeted tests:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest \
  apps.api.tests.test_app.ApiAppTests.test_query_endpoint_applies_ip_and_asic_filters -v

Ran 1 test in 0.021s
OK
```

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest \
  apps.mcp.tests.test_tools.McpToolsTests.test_search_evidence_applies_ip_and_asic_filters -v

Ran 1 test in 0.016s
OK
```

## Real AMD Filter QA

Clean-final DB:

```text
data/asip.db
/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db
```

Core query evidence:

```text
CP_INT_CNTL_RING0 unfiltered:
  rows=20
  counts:
    CP / gfx_v10_0 / code = 1
    GC / gc_9_0 / register = 4
    GC / gc_9_4 / register = 12
    GC / gc_11_0 / register = 3

CP_INT_CNTL_RING0 ip_block=CP:
  rows=2
  counts:
    CP / gfx_v10_0 / code = 2
  first symbols:
    CP_INT_CNTL_RING0
    cp_int_cntl_reg

CP_INT_CNTL_RING0 ip_block=SDMA:
  rows=0
  empty=true
```

Additional ASIC filter check:

```text
GCVM_L2_CNTL unfiltered:
  rows=20
  counts:
    GC / gfx_v11_0 / code = 2
    GC / gc_11_0 / register = 18

GCVM_L2_CNTL asic_or_generation=gc_11_0:
  rows=20
  counts:
    GC / gc_11_0 / register = 20

GCVM_L2_CNTL asic_or_generation=gc_9_4:
  rows=0
  empty=true
```

Web BFF evidence:

```text
GET /api/workbench/query?q=CP_INT_CNTL_RING0&ipBlock=CP
HTTP 200
rows=2
filters.ip_block=CP
rows:
  CP_INT_CNTL_RING0 / CP / gfx_v10_0 / code
  cp_int_cntl_reg / CP / gfx_v10_0 / code

GET /api/workbench/query?q=CP_INT_CNTL_RING0&ipBlock=SDMA
HTTP 200
rows=0
empty=true
filters.ip_block=SDMA
```

Browser QA:

```text
route: http://127.0.0.1:3100/
viewport: 2048 x 1280
query: CP_INT_CNTL_RING0
IP block filter: CP

observed:
  matches: 2
  graph edges: 227
  layers deterministic: 227
  result rows:
    CP_INT_CNTL_RING0 code field_set 0.95 drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c lines 5433-5441
    cp_int_cntl_reg code read_modify_write 0.95 drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c lines 5433-5441
  inspector:
    Source Location: code register drivers/gpu/drm/amd/amdgpu/gfx_v10_0.c line 5433
```

Screenshot:

```text
docs/qa/browser/g12-filter-cp-clean-final-3100-2k.png
```

## Residual

The real AMD filter behavior is proven. The remaining boundary is that
IP/ASIC metadata inference is path/symbol heuristic, not a full AMD taxonomy
parser. `_ip_block_for_symbol()` scans simple block tokens such as `GC`, `CP`,
`SDMA`, `GMC`, `BIF`, `RLC`, and `GDS`; `_asic_for_path()` extracts path
fragments like `gfx_v10_0`, `gc_11_0`, `nbio_v7_9`, or `sdma_v5_0`.
