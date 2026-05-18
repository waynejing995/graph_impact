# 2026-05-18 Performance Smoke Fixture QA

## Scope

This QA closes the fixture-side G15 smoke that was missing from the final evidence package: start from an empty SQLite database, index the same small fixture twice, compare stable counts, and time at least five live queries.

This is not a real AMD full-corpus benchmark. It is a repeatable fixture smoke for stable-count rebuild and sub-second query behavior.

## Command

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src python3 -m asip.cli performance-smoke \
  --db /tmp/asip-performance-smoke-2026-05-18.db \
  --source-root docs/fixtures/performance-smoke \
  --query GCVM_L2_CNTL \
  --query IH_RB_CNTL \
  --query SDMA0_QUEUE0_RB_CNTL \
  --query CP_INT_CNTL_RING0 \
  --query 'interrupt ring buffer' \
  --max-query-seconds 1.0 \
  --output-json docs/qa/2026-05-18-performance-smoke-fixture.json
```

## Result

```text
source: fixture_performance_smoke
primary DB: /tmp/asip-performance-smoke-2026-05-18.db
repeat DB: /tmp/asip-performance-smoke-2026-05-18-repeat.db
source root: docs/fixtures/performance-smoke
deterministic_counts_match: true
```

Index runs:

| Run | Elapsed seconds | documents | chunks | evidence | edges | files |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| primary | 0.053971 | 2 | 2 | 19 | 4 | 2 |
| repeat | 0.042888 | 2 | 2 | 19 | 4 | 2 |

Query timings:

| Query | Seconds | Rows | Graph nodes | Graph edges | Runtime | Under 1s |
| --- | ---: | ---: | ---: | ---: | --- | --- |
| `GCVM_L2_CNTL` | 0.099421 | 8 | 4 | 2 | networkx | true |
| `IH_RB_CNTL` | 0.002901 | 8 | 4 | 2 | networkx | true |
| `SDMA0_QUEUE0_RB_CNTL` | 0.002733 | 8 | 6 | 3 | networkx | true |
| `CP_INT_CNTL_RING0` | 0.007449 | 8 | 4 | 2 | networkx | true |
| `interrupt ring buffer` | 0.005412 | 8 | 4 | 2 | networkx | true |

## Automated Tests

RED:

```text
ModuleNotFoundError: No module named 'asip.performance_smoke'
```

GREEN:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_performance_smoke \
  packages.core.tests.test_workbench_cli.WorkbenchCliTests.test_performance_smoke_command_rebuilds_fixture_and_times_queries -v

Ran 2 tests in 0.502s
OK
```

Full current core regression after this slice:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v

Ran 194 tests in 8.075s
OK (skipped=2)
```

## Residual

This fixture smoke does not close the real AMD full-corpus timing boundary. G15 still needs repeat real-corpus indexing/rebuild timing and provider embedding backfill timing before the whole goal can be complete.
