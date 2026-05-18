# G15 Edge Count Summary QA

Date: 2026-05-18

Status: pass for counting only persisted edges in CLI/index summaries.

## Scope

The empty-DB raw re-index artifact recorded a mismatch between the CLI summary
edge count and the final SQLite `edges` table count. The root cause was that
some indexing paths counted attempted edge inserts even when `AsipStore.add_edge()`
rejected a resolver wrapper or macro hub and returned `0`.

## RED/GREEN

Initial RED:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_code_graph_edge_persistence_counts_only_inserted_edges \
  -v

AssertionError: 1 != 0
```

GREEN targeted:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_code_graph_edge_persistence_counts_only_inserted_edges \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_query_term_edge_persistence_counts_only_inserted_edges \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_generated_semantic_edge_persistence_counts_only_inserted_edges \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_summary_counts_only_inserted_code_graph_edges \
  packages.core.tests.test_workbench_cli.WorkbenchCliTests.test_index_query_and_graph_commands_use_live_sqlite_store \
  -v

Ran 5 tests in 0.648s
OK
```

Full core:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v

Ran 234 tests in 23.762s
OK (skipped=2)
```

## Notes

The historical raw re-index artifact still records the old `39233` CLI summary
versus `39199` SQLite table count because it was generated before this fix.
The code path now counts only actual inserted edge ids for deterministic graph,
query-term evidence, and semantic-edge persistence.
