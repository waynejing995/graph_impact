# G04 Corpus Management

Status: Partial; backend/API/MCP add/list/index, selected UI indexing, invalid-source failure, and UI add-index-query proof exist; final clean-DB closure remains blocking

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

## Remaining Gap

The backend/API/MCP state path exists, and the Corpus UI now has explicit selection controls, selected-index status update, invalid-source failed-state proof, and a browser add-index-query proof for a temporary local corpus.

The remaining G04 work is narrower but still blocking: final QA must repeat the flow against a clean named DB/corpus, long-running queued/indexing transitions are still not modeled as a durable job stream, and graph/inspector evidence for the newly indexed corpus remains part of the broader G02/G03/G10 closure.

Default and fallback corpora remain in the UI. They are acceptable as seed/fallback display only if product paths prefer backend state and failures are visible.

## Acceptance Criteria

- Backend route creates, lists, and indexes corpus entries.
- Added corpus persists across reloads without relying only on browser localStorage.
- UI can select which corpus entries to index. Implemented for selected index request construction, indexed status display, and the real UI add-index-query path.
- Corpus status is truthful for `not_indexed`, `indexed`, and `failed`; durable `queued`/`indexing` job-stream UX remains open.
- PDF and docs corpus types can be represented in the same UI/API shape.
- Query results can include evidence from a user-added corpus after indexing.

## Required Tests

- API test: add/list corpus with include globs and type.
- API test: index selected corpus and query a unique symbol from it.
- MCP test: add/list/index corpus with a temp DB and query a unique symbol from it.
- E2E test: selected corpus rows are the only ids sent to the index endpoint, and the selected row shows returned `indexed` status. Implemented.
- E2E test: add corpus, run index, observe status transition, query new evidence. Implemented for a temporary local corpus through the Web UI; final clean DB acceptance repetition remains open.
- Failure-state test: invalid source root returns a visible failed/error state. Implemented in core and Web UI smoke coverage.
- Failure-state test: configured missing source roots and unknown selected corpus ids cannot return `indexed` with zero documents. Implemented in core coverage.

## Not Closed Until

User-added corpora can participate in indexing and query results through the UI, and final clean acceptance evidence proves the same flow without relying on the dirty development DB.
