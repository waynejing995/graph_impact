# ASIP Fixture Performance Smoke Current Run

Date: 2026-05-20

Status: pass for the fixture-scale performance gate; this does not close the
real-browser or live-provider blockers.

## Command

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
python3 -m asip.cli performance-smoke \
  --db /tmp/asip-performance-smoke-2026-05-20-current.db \
  --source-root docs/fixtures/performance-smoke \
  --query GCVM_L2_CNTL \
  --query IH_RB_CNTL \
  --query SDMA0_QUEUE0_RB_CNTL \
  --query program_gcvm_l2 \
  --query "interrupt ring buffer" \
  --limit 8 \
  --max-query-seconds 1.0 \
  --output-json docs/qa/2026-05-20-performance-smoke-fixture-current.json
```

## Result

- Artifact: `docs/qa/2026-05-20-performance-smoke-fixture-current.json`
- Source root: `docs/fixtures/performance-smoke`
- Primary DB: `/tmp/asip-performance-smoke-2026-05-20-current.db`
- Repeat DB: `/tmp/asip-performance-smoke-2026-05-20-current-repeat.db`
- Deterministic counts match: `true`
- All queries under threshold: `true`
- Threshold: `1.0s`

## Rebuild Counts

| Run | Elapsed seconds | Documents | Chunks | Evidence | Edges | Files |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| primary | 0.087929 | 2 | 2 | 19 | 4 | 2 |
| repeat | 0.053608 | 2 | 2 | 19 | 4 | 2 |

## Query Timings

| Query | Elapsed seconds | Rows | Graph nodes | Graph edges | Runtime |
| --- | ---: | ---: | ---: | ---: | --- |
| `GCVM_L2_CNTL` | 0.141931 | 8 | 8 | 6 | networkx |
| `IH_RB_CNTL` | 0.003118 | 8 | 8 | 6 | networkx |
| `SDMA0_QUEUE0_RB_CNTL` | 0.002944 | 8 | 10 | 8 | networkx |
| `program_gcvm_l2` | 0.002214 | 8 | 4 | 2 | networkx |
| `interrupt ring buffer` | 0.002795 | 8 | 7 | 5 | networkx |

## Regression Tests

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest \
  packages.core.tests.test_performance_smoke \
  packages.core.tests.test_workbench_cli.WorkbenchCliTests.test_performance_smoke_command_rebuilds_fixture_and_times_queries \
  -v
```

Result: `Ran 2 tests`, `OK`.
