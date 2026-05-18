# G04 Corpus Management

Status: Current clean corpus flow verified; background/remote orchestration deferred

## Requirement

The Corpus page must let users add, list, select, and index corpora. Corpus entries must include id, repo/path, include globs, type, and indexing status.

PDF corpus type must be represented.

## Current Evidence

- `packages/core/src/asip/workbench.py` has `add_corpus()`, `list_indexed_corpora()`, and `index_registered_corpora()`.
- `packages/core/src/asip/cli.py` exposes `corpora`, `corpus-add`, and `index --corpus-id`.
- `apps/web/app/api/workbench/corpora/route.ts` has GET and POST backed by the CLI.
- `apps/web/components/workbench-page.tsx` posts Add corpus to the backend.
- `apps/web/tests/workbench-api.spec.ts` covers backend corpus persistence and selected user-corpus indexing.
- FastAPI exposes `GET /corpora`, `POST /corpora`, and `POST /index` over the same core functions.
- MCP exposes `corpora_list()`, `corpus_add()`, and `corpora_index()` over the same core functions.
- FastAPI and MCP tests add a temp corpus to a temp SQLite DB, index the selected corpus, and query a unique symbol from that corpus.
- Corpus UI rows now expose explicit `Index <corpus id>` checkboxes, and `Run index` sends only the selected corpus ids to `/api/workbench/index`.
- `apps/web/tests/workbench-smoke.spec.ts` verifies a two-corpus page can unselect `api-corpus-a`, index only `api-corpus-b`, send `{ corpusIds: ["api-corpus-b"] }`, and show `indexed` status for that row.
- `packages/core/tests/test_workbench_corpus_state.py` verifies a missing registered `source_root` raises `FileNotFoundError`, marks the corpus `failed`, leaves `file_count` at `0`, and records `source root not found` in metadata.
- `packages/core/tests/test_workbench_corpus_state.py` verifies an unknown selected registered corpus id fails the index job instead of reporting `indexed` with zero documents.
- `packages/core/tests/test_workbench_live.py` verifies configured raw-corpus indexing fails when the configured scan root is missing, writes a failed job, and marks that corpus `failed` instead of returning a zero-document success summary.
- `apps/web/tests/workbench-smoke.spec.ts` verifies an index API `failed` response marks the selected Corpus UI row as `failed` and shows the backend error.
- `apps/web/tests/workbench-smoke.spec.ts` now has a real UI full-loop test: create a temporary local Markdown corpus, add it through the Corpus page, select only that corpus, run index through `/api/workbench/index`, navigate to Evidence Search, and query a unique symbol from that indexed corpus.
- 2026-05-17 durable job lifecycle slice: `jobs.status` is now canonical `queued/indexing/succeeded/failed`; successful result names such as `indexed` are preserved in `jobs.metadata.result_status`; `job_events` records the durable event chain.
- Legacy job rows created before `job_events` existed now normalize at read time, so old `indexed`/`rebuilt` style rows do not leak non-lifecycle statuses into CLI/API/Web/MCP. The original result name is preserved as `metadata.result_status`, and a synthetic historical event is shown when no durable event rows exist.
- Core exposes `get_job()` and `list_jobs()`, CLI exposes `asip jobs`, Next BFF exposes `GET /api/workbench/jobs` and `GET /api/workbench/jobs/{id}`, FastAPI exposes `GET /jobs` and `GET /jobs/{job_id}`, and MCP exposes `jobs_list()` and `job_detail()`.
- Corpus UI now shows a recent Index Jobs panel with job id, terminal status, message, and event chain such as `queued -> indexing -> succeeded`.
- QA evidence for the lifecycle slice is recorded in `docs/qa/2026-05-17-g04-corpus-job-lifecycle-qa.md`.
- 2026-05-18 clean flow QA `docs/qa/2026-05-18-g04-clean-corpus-flow-qa.md` proves a clean named DB Web BFF add/index/query flow where the newly indexed corpus drives query rows and a `doc_section -> register` graph edge, and proves the real Corpus/Evidence UI full-loop shows graph and inspector evidence from the new corpus while leaving default `data/asip.db` byte-identical to the clean-final artifact at the time of that QA. Default `data/asip.db` was later intentionally rebuilt for G03 graph QA.

## Remaining Gap

The backend/API/MCP state path exists, and the Corpus UI now has explicit selection controls, selected-index status update, invalid-source failed-state proof, a clean named DB BFF add-index-query graph proof, and a browser add-index-query graph/inspector proof for a temporary local corpus.

The remaining G04 boundary is no longer the MVP corpus flow itself. The current lifecycle implementation is durable event history for synchronous local jobs; it is not a background worker, streaming progress channel, cancellation system, or remote clone orchestration layer.

Default and fallback corpora remain in the UI. They are acceptable as seed/fallback display only if product paths prefer backend state and failures are visible.

## Acceptance Criteria

- Backend route creates, lists, and indexes corpus entries.
- Added corpus persists across reloads without relying only on browser localStorage.
- UI can select which corpus entries to index. Implemented for selected index request construction, indexed status display, and the real UI add-index-query path.
- Corpus status is truthful for `not_indexed`, `indexed`, and `failed`; index job lifecycle is inspectable as durable `queued`/`indexing`/`succeeded`/`failed` events through core, CLI, Web BFF, FastAPI, MCP, and the Corpus page.
- PDF and docs corpus types can be represented in the same UI/API shape.
- Query results can include evidence from a user-added corpus after indexing.

## Required Tests

- API test: add/list corpus with include globs and type.
- API test: index selected corpus and query a unique symbol from it.
- MCP test: add/list/index corpus with a temp DB and query a unique symbol from it.
- E2E test: selected corpus rows are the only ids sent to the index endpoint, and the selected row shows returned `indexed` status. Implemented.
- E2E test: add corpus, run index, observe status transition, query new evidence, and show graph/inspector provenance. Implemented for a temporary local corpus through the Web UI using an isolated DB so the clean-final default DB is not dirtied.
- Web BFF test: add/index/query a user corpus against a clean named DB and assert graph provenance for the newly indexed corpus. Implemented.
- E2E/API/MCP tests: durable job lifecycle events are exposed after index. Implemented for core, Web BFF, FastAPI, MCP, and Corpus UI.
- Failure-state test: invalid source root returns a visible failed/error state. Implemented in core and Web UI smoke coverage.
- Failure-state test: configured missing source roots and unknown selected corpus ids cannot return `indexed` with zero documents. Implemented in core coverage.

## Not Closed Until

User-added corpora can participate in indexing, query results, graph output, and inspector detail through the UI, and clean named DB evidence proves the same BFF/core flow without relying on the dirty development DB.
