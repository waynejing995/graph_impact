# G04 Corpus Job Lifecycle QA

Date: 2026-05-17
Scope: G04 corpus management durable index job state.

## Requirement

Corpus/index jobs must not be a transient one-line response only. The product should persist and expose job lifecycle state, including `queued`, `indexing`, `failed`, and `succeeded`, so UI/API/MCP users can inspect what happened after an index action.

## RED

Core RED:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest packages.core.tests.test_workbench_corpus_state.WorkbenchCorpusStateTests.test_index_job_lifecycle_persists_queued_indexing_and_succeeded_events -v
```

Initial failure: `ImportError: cannot import name 'get_job' from 'asip.workbench'`.

Web BFF RED:

```bash
pnpm --filter web exec playwright test tests/workbench-api.spec.ts -g "jobs API exposes durable index job lifecycle events" --reporter=list
```

Initial failure: `jobStatus` was missing from the index response and `/api/workbench/jobs` did not expose the durable job event stream.

FastAPI/MCP RED:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
python3 -m unittest \
apps.api.tests.test_app.ApiAppTests.test_corpus_endpoints_add_list_index_and_query_user_corpus \
apps.mcp.tests.test_tools.McpToolsTests.test_job_tools_expose_index_lifecycle_events -v
```

Initial failures: FastAPI `/jobs` returned `404`; MCP had no `job_detail`/`jobs_list` tools.

Corpus UI RED:

```bash
pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts -g "corpus page shows durable index job lifecycle events" --reporter=list
```

Initial failure: `data-testid="job-runs-panel"` was not present.

## Implementation

- Added durable `job_events` storage with canonical job lifecycle statuses:
  - `queued`
  - `indexing`
  - `succeeded`
  - `failed`
- `jobs.status` now stores canonical lifecycle status. Terminal successful result names such as `indexed`, `rebuilt`, `embedded`, and `generated` are preserved in `jobs.metadata.result_status`.
- Legacy job rows written before the lifecycle migration are normalized at read time: old successful statuses such as `indexed` are returned as `succeeded`, their original status is preserved in `metadata.result_status`, and a synthetic historical event is shown when no durable `job_events` rows exist.
- Added `AsipStore.update_job_status()`, `AsipStore.list_jobs()`, and job event hydration in `AsipStore.get_job()`.
- Added `asip.workbench.list_jobs()` and `asip.workbench.get_job()`.
- Added CLI `asip jobs --db ... [--id ...]`.
- Added Next BFF routes:
  - `GET /api/workbench/jobs`
  - `GET /api/workbench/jobs/{id}`
- Added FastAPI routes:
  - `GET /jobs`
  - `GET /jobs/{job_id}`
- Added MCP tools:
  - `jobs_list`
  - `job_detail`
- Corpus page now shows a shadcn Card-backed `Index Jobs` panel with recent job id, terminal status, message, and event chain such as `queued -> indexing -> succeeded`.

## GREEN

Core targeted:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest packages.core.tests.test_workbench_corpus_state packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_indexes_raw_corpus_files_and_queries_schema_from_sqlite -v
```

Result: `6` tests passed.

Legacy read normalization targeted:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_corpus_state.WorkbenchCorpusStateTests.test_legacy_success_job_status_reads_as_canonical_lifecycle_with_result_metadata \
  packages.core.tests.test_workbench_corpus_state.WorkbenchCorpusStateTests.test_index_job_lifecycle_persists_queued_indexing_and_succeeded_events -v
```

RED before implementation: old job status read as `indexed`.

GREEN after implementation: `2` tests passed.

Live dev DB spot check:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src python3 -m asip.cli jobs --db data/asip.db --id 62
```

Result: old `indexed` job row is returned as `status=succeeded`,
`metadata.result_status=indexed`, with one synthesized `succeeded` event.

API/MCP targeted:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
python3 -m unittest \
apps.api.tests.test_app.ApiAppTests.test_corpus_endpoints_add_list_index_and_query_user_corpus \
apps.mcp.tests.test_tools.McpToolsTests.test_job_tools_expose_index_lifecycle_events \
apps.mcp.tests.test_server.McpServerTests.test_build_server_registers_all_product_tools_with_fastmcp -v
```

Result: `3` tests passed.

Web API targeted:

```bash
pnpm --filter web exec playwright test tests/workbench-api.spec.ts -g "jobs API exposes durable index job lifecycle events|index API can target user-added corpora" --reporter=list
```

Result: `2` tests passed.

Corpus UI targeted:

```bash
pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts -g "corpus page" --reporter=list
```

Result: `8` tests passed.

Typecheck:

```bash
pnpm --filter web exec tsc --noEmit
```

Result: passed.

## Fresh Wider Verification

Run after the 2026-05-18 receiver type-hint graph correction and job
lifecycle implementation:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest apps.api.tests.test_app apps.api.tests.test_runtime apps.mcp.tests.test_tools apps.mcp.tests.test_server -v
pnpm --filter web exec tsc --noEmit
pnpm --filter web run lint
pnpm --filter web exec playwright test tests/workbench-api.spec.ts --reporter=list
pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts --reporter=list
git diff --check
```

Results:

- Core: `172` tests OK, `2` optional sqlite-vec skips.
- API/MCP: `42` tests OK, `1` optional MCP runtime skip.
- Typecheck: passed.
- Web lint: passed.
- Web API Playwright: `25` passed.
- Workbench smoke Playwright: `46` passed.
- Diff whitespace check: passed.

## Remaining Boundary

This closes the durable job lifecycle visibility slice for synchronous local index jobs. It does not create a background worker, streaming progress channel, or cancellation system. Clean-DB final acceptance still needs to prove user-added corpus evidence flows through query, inspector, and graph in the final evidence package.
