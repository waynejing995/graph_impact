# G02 Live Retrieval And Evidence Schema

Status: Partial; evidence schema, FTS, vector fallback retrieval, and clean AQ runner evidence exist; rerank and final UI/visual closure remain blocking

## Requirement

Free-form query must run hybrid retrieval over exact symbols, resolver output, graph expansion, FTS5, vector search, and reranking.

Each evidence item must include at least:

```text
id
source_type
repo
path
line_start
line_end or page
symbol
entity_type
ip_block
asic_or_generation
access_type
confidence
snippet
resolved_chain
```

## Current Evidence

- `packages/core/src/asip/workbench.py` has `query_evidence(db_path, query)` backed by SQLite evidence rows and FTS5 chunk matches.
- `packages/core/src/asip/storage.py` defines the minimum MVP evidence schema.
- `packages/core/tests/test_workbench_query_schema.py` asserts schema fields and no-match empty state.
- `apps/web/app/api/workbench/query/route.ts`, FastAPI `/query`, and MCP `search_evidence()` call the SQLite-backed service.
- `apps/web/tests/workbench-api.spec.ts` runs more than five real ASIP query strings against the live API.
- `apps/web/tests/workbench-smoke.spec.ts` verifies a no-match query renders an explicit UI empty state instead of falling back to seed rows.
- `apps/web/tests/workbench-smoke.spec.ts` verifies live API evidence rows drive the table, query graph, and right inspector from the same payload, including `snippet` and `resolved_chain`.
- `apps/web/tests/workbench-smoke.spec.ts` verifies clicking a different live evidence row changes the inspector to that row's snippet/resolved chain instead of keeping a static detail panel.
- Vector storage, deterministic embedding fallback, and vector-backed retrieval now participate in query ranking through the storage vector adapter.
- `packages/core/tests/test_workbench_query_schema.py` verifies low-lexical-overlap evidence can be returned through a matching chunk embedding and includes `vector_score` or vector retrieval source metadata.
- Registered doc/PDF corpus text can now be indexed as document-anchor evidence even when a chunk has no symbol-like code identifier.
- Historical artifact `docs/qa/2026-05-17-acceptance-clean-qwen35-provider-rerun.json` and `.md` recorded AQ01-AQ09 passing under the older acceptance gate against `/tmp/asip-acceptance-clean-2026-05-17.db`, including row counts, graph counts, provider settings, and local Ollama provider checks. Current source-gated artifact `docs/qa/2026-05-17-acceptance-clean-qwen35-source-gated-current.json` correctly fails the same DB because database health is bad and AQ05 lacks PDF.
- Synthetic multi-source fixture artifact `docs/qa/2026-05-17-acceptance-multisource-fixture.json` proves fixture-level source diversity: AQ05 returns 24 rows with `code`, `doc`, `pdf`, and `register`; AQ06 returns 16 rows with `code` and `register`; both expose graph counts from the NetworkX runtime. Retrieval sources in that fixture are `fts5` and `lexical`, so it does not close rerank, provider-rerank, or native vector runtime boundaries.
- Clean AMD acceptance artifact `docs/qa/2026-05-17-acceptance-clean-amd-qwen35-provider-current.json` records AQ01-AQ09 as `9/9` passed against `/tmp/asip-clean-amd-qwen35-provider-2026-05-17.db`; source types include code/register for AQ01 and AQ06, code/doc/pdf/register for AQ02-AQ05, doc/pdf/register for AQ08, and pdf/register for AQ09.
- Free-query QA artifact `docs/qa/2026-05-17-clean-amd-free-query-and-edge-qa.json` records six non-empty free-form queries, all with NetworkX query graphs, aggregate source types `code`, `doc`, `pdf`, and `register`, and global graph runtime `networkx`.
- `packages/core/tests/test_workbench_query_schema.py` now covers multiple injected source types during diverse selection so a doc/PDF insertion cannot evict a required register row; this fixed the AQ06 clean-DB failure.
- Verification: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v` ran 63 tests, OK, 1 native sqlite-vec skip.

## Remaining Gap

Retrieval is still an MVP live slice: SQLite evidence rows plus FTS-assisted lexical scoring plus vector-backed evidence merge. The clean AMD DB now proves source-diverse AQ01-AQ09 and more than five real free-form query records, but mature provider rerank/query-vector behavior, native vector-runtime boundary review, final browser visual QA, and route/tool design review remain open. Read-route mutation policy is covered for the key Web BFF/FastAPI/MCP read paths in G14/G07, while the final route/tool matrix review remains part of G07/G17.

The React UI still has seed data available for page bootstrapping and route fallback. Verified API empty results no longer mask as seed rows, and live evidence rows now drive the inspector when retrieval succeeds. Network/API failure paths still need final UX review so fallback data cannot masquerade as live retrieval.

## Acceptance Criteria

- At least all nine MVP acceptance queries run against the real index and produce verified results or explicit failures. Runner evidence exists; final completion still needs G10/G11/G16 review linkage.
- A no-match query returns an explicit empty state in both API and UI.
- Results include code, register, doc, and PDF evidence when available.
- Selecting an evidence row shows snippet, source location, resolved chain, and related entities.
- Query output includes graph seed entities and relation edges from the same retrieval result.
- Retrieval combines FTS and vector-backed results, with remaining rerank/acceptance gaps explicitly tracked.

## Required Tests

- API test: query endpoint uses indexed fixture data, not fixed JSON artifact selection.
- API/test artifact: all nine MVP acceptance queries and one no-match query. AQ01-AQ09 runner artifact exists; final route/UI review remains in G10/G11/G16.
- Core test: doc/PDF plain text evidence appears in query results from registered corpora.
- UI E2E test: rows, inspector, and graph change together for a user-entered query. Implemented for mocked live API rows, including row selection changes in the inspector.
- Schema test asserting the minimum evidence fields.
- Hybrid retrieval test: vector-only or low-lexical-overlap evidence can be returned through the configured vector adapter. Implemented for fallback vector adapter; native sqlite-vec remains optional/skipped in this runtime.

## Not Closed Until

The query path can answer a query that is not one of the pre-baked QA artifact cases, UI fallback data cannot mask query failures, and rerank/vector/native-runtime boundaries plus final visual/design review are verified or explicitly deferred.
