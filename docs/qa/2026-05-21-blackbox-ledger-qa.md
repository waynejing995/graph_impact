# Blackbox Ledger QA

Date: 2026-05-21
Status: partial current proof; real `data/asip.db` smoke blocked

## Scope

This QA note covers the new Stage 2.5 blackbox overlay path:

- AST-derived product endpoint inventory, independent of graph display budgets.
- LLM batch/attempt ledger.
- Persisted `blackbox_profiles` semantic overlays.
- Runtime freshness visibility.
- CLI, Web API, and browser inspector surfaces.

## Current Evidence

- Backend regression:
  - `packages.core.tests.test_storage_graph`
  - `packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_llm_blackbox_profiles_use_inventory_ledger_and_allowlist_validation`
  - `packages.core.tests.test_runtime_semantic_freshness`
  - `packages.core.tests.test_blackbox_ledger_qa`
  - Result: 79 tests passed, 2 skipped.
- Python compile:
  - `py_compile` passed for blackbox QA, CLI, completion gate, workbench, storage, and runtime freshness modules.
- Frontend typecheck:
  - `pnpm --filter web exec tsc --noEmit` passed after installing lockfile dependencies.
- Web API focused proof:
  - `PLAYWRIGHT_BASE_URL=http://127.0.0.1:3117 pnpm --filter web exec playwright test tests/workbench-api.spec.ts -g "blackbox profile generation" --reporter=line`
  - Result: 1 passed.
- Browser inspector focused proof:
  - `pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts -g "blackbox profile generation" --reporter=line`
  - Result: 1 passed.
- Fixture ledger artifact:
  - JSON: `docs/qa/2026-05-21-blackbox-ledger-qa.fixture.json`
  - Markdown: `docs/qa/2026-05-21-blackbox-ledger-qa.fixture.md`
  - DB path: `/tmp/asip-blackbox-ledger-fixture/fixture.db`
  - Source: fake provider fixture, not final real DB evidence.

## Real DB Smoke Status

The requested real smoke command is currently blocked:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
  python3 -m asip.cli blackbox-profiles-batch --db data/asip.db --limit 20 --batch-size 2
```

Current worktree evidence:

- `data/asip.db` is missing in this worktree.
- `sqlite3 data/asip.db "pragma quick_check;"` cannot run because the DB path does not exist.
- Local Ollama is reachable.
- Ollama model `gemma4:e4b` is available.

Because the current DB is absent, this QA note does not claim final real-DB
completion. The next required proof is to restore or provide the authoritative
`data/asip.db`, then run the CLI smoke, `blackbox-ledger-qa`, and browser
`/graph?dbPath=...` proof against that exact DB path.
