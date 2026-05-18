# G15 Performance Smoke And Deterministic Rebuild

Status: Partial; fixture smoke, repeat real-corpus graph rebuild, query timing, and full local provider backfill timing exist; full raw re-index timing still open

## Requirement

MVP-1 must include basic local performance smoke checks so the workbench is not only correct on tiny mocked paths but also practical on a developer machine.

The MVP-1 design sets these initial targets:

- small fixture indexing completes in seconds,
- query over the fixture corpus returns in under one second on a developer machine,
- the SQLite database can be deleted and rebuilt deterministically.

Real-corpus performance targets should be measured after the first full AMD indexing benchmark rather than guessed.

## Current Evidence

- Unit and Playwright suites exercise indexing and query behavior on small fixtures.
- Real AMD temp indexing has produced nonzero evidence rows for selected MxGPU queries.
- A naive configured full-code evidence indexing attempt was stopped after roughly two minutes and a 192 MB temporary SQLite DB. The implementation was narrowed to full doc/PDF ingestion plus query-focused code/register snippets until a selective code parser/indexer exists.
- A clean DB provider-backed registered-corpus reindex attempt with `ollama/nomic-embed-text:latest` was manually interrupted after a long serial run. It wrote 9440 embeddings before stop, left an explicit failed job record, and showed the bottleneck is synchronous per-chunk embedding API calls rather than Ollama thinking or memory pressure. This is useful performance evidence, not a pass condition.
- Six real clean-DB queries over `/tmp/asip-acceptance-clean-2026-05-17.db` returned live rows and NetworkX graphs, but took 3.782s, 5.927s, 4.726s, 4.378s, 5.403s, and 4.822s respectively. This confirms functional retrieval on the larger DB and also confirms query latency is not yet within the initial fixture-scale performance target.
- Clean AMD raw indexing against `/tmp/asip-mxgpu`, `/tmp/asip-linux-amdgpu`, and `docs/fixtures/amd-amdgpu-docs` now produces `/tmp/asip-clean-amd-gemma4-provider-2026-05-17-final.db` with `documents=124`, `chunks=21884`, `evidence=860516`, `edges=10019`, and `files=1349`.
- The provider DB records 32 provider-sourced embeddings from `ollama/nomic-embed-text:latest`. Serial per-chunk embedding indexing was stopped after it proved too slow; batch `/api/embed` backfill is now implemented but intentionally stopped as partial provider coverage for this QA pass.
- Current free-query QA `docs/qa/2026-05-17-clean-amd-gemma4-free-query-and-edge-qa.json` records six clean AMD query latencies and one global graph latency. All six queries returned rows; source types across the set were `code/doc/pdf/register`.
- `docs/qa/2026-05-17-two-stage-graph-real-rebuild-qa.md` records a real mxgpu + linux-amdgpu Stage 1 graph rebuild after batched evidence/edge commits: `1340` files, `31353` chunks, `1300559` evidence rows, `37921` deterministic edges, and `7:00.02` elapsed. This is a first real graph rebuild benchmark, not a deterministic repeat pass.
- Seven post-rebuild real queries were timed in the same QA doc, ranging from `1.597s` to `4.120s`.
- 2026-05-17 final performance correction on the current dirty `data/asip.db`:
  - `graph_rebuild --db data/asip.db`: 1,225 files, 10,108 deterministic edges, 39.610s elapsed.
  - `query_evidence(data/asip.db, "doorbell interrupt disable")` before fix: 58.228s total, with `graph_for_rows` taking 58.717s in the diagnostic script.
  - After empty-edge graph short path: 3.835s.
  - After FTS chunk lookup, SQLite lookup indexes, and lazy deterministic graph metadata: 0.487s with 24 rows, 32 graph nodes, and 37 graph edges.
  - `global_graph(data/asip.db, limit=3000)`: 2,144 nodes and 3,000 edges in 0.771s.
- 2026-05-17 performance regressions now covered by tests:
  - `test_networkx_graph_expansion_skips_function_metadata_scan_without_edges`
  - `test_networkx_graph_expansion_skips_function_metadata_scan_for_deterministic_edges`
  - `test_global_graph_skips_function_metadata_scan_for_deterministic_edges`
  - `test_find_evidence_candidates_prefers_fts_chunk_lookup`
  - `test_migrate_adds_evidence_chunk_lookup_index`
  - `test_deleting_one_corpus_index_preserves_other_corpus_edges`
  - `test_query_evidence_uses_configured_vector_limit`
  - `test_semantic_batch_candidate_overfetch_multiplier_is_configurable`
- 2026-05-18 fixture performance smoke is now a product CLI path and core test, not just a hand-written benchmark. `asip.cli performance-smoke` rebuilds a small fixture from empty SQLite twice, compares table counts, and times live queries. `docs/qa/2026-05-18-performance-smoke-fixture.json` records two matching rebuilds over `docs/fixtures/performance-smoke`: `documents=2`, `chunks=2`, `evidence=19`, `edges=4`, with elapsed times `0.053971s` and `0.042888s`. Five fixture queries all returned rows and stayed under one second: `0.099421s`, `0.002901s`, `0.002733s`, `0.007449s`, and `0.005412s`.
- 2026-05-18 query-graph performance correction is recorded in `docs/qa/2026-05-18-query-graph-performance-qa.md`. `graph_for_rows()` now expands multiple query seeds with one NetworkX build and reuses the multi-seed empty result instead of rebuilding through `expand_query_graph()`. The no-edge multi-seed storage path now returns seed nodes instead of raising `NameError`, and callable-symbol snippet checks no longer compile a regex per evidence row.
- After that correction, six real queries over the dirty local `data/asip.db` returned rows and query graphs in `4.161s`, `3.845s`, `0.878s`, `2.135s`, `2.093s`, and `2.084s`. The two GCVM paths dropped from roughly 10 seconds to about 4 seconds. The Web Playwright acceptance route for AQ01 completed in `26.3s`, below the 30s e2e timeout.
- 2026-05-18 repeat real-corpus graph rebuild QA is recorded in `docs/qa/2026-05-18-g15-real-corpus-repeat-graph-rebuild.md` and `.json`. Two SQLite backup copies of live `data/asip.db` ran `python3 -m asip.cli graph-rebuild --corpus-id linux-amdgpu --corpus-id mxgpu`. Run 1 took `131.639s`, run 2 took `126.034s`; both processed `1225` files, rebuilt `41923` deterministic edges, and ended with stable counts (`documents=124`, `chunks=21884`, `evidence=860516`, `edges=41936`, `embeddings=32`) plus matching edge source/relation counts.
  These timing/count checks include the current conservative `clang_callback` overlay and selective `type_flow=clang_ast_json` hints, but they measure deterministic rebuild stability, not full clangd/libclang callback correctness.
- 2026-05-18 bounded provider backfill smoke is recorded in `docs/qa/2026-05-18-g06-provider-backfill-smoke.md` and `.json`. A temp DB copy ran `provider-embeddings --limit 128 --batch-size 8` through local Ollama `nomic-embed-text:latest`, embedded `128` chunks in `17.703s`, and ended with `160` provider embeddings in the temp DB. This is a bounded provider-path timing smoke, not full coverage.
- 2026-05-18 full local temp-copy provider backfill timing is recorded in `docs/qa/2026-05-18-g06-full-provider-backfill-tempdb-qa.md` and `.json`. The resumed full job embedded `12572` remaining chunks in `2388.07s` with `batch_size=16`, and the temp DB ended with `21884 / 21884` chunks covered by `ollama/nomic-embed-text:latest`, `missing=0`, and `10770` long inputs marked as truncated. This measures local Ollama full-coverage backfill on a backup DB, not credentialed OpenAI-compatible throughput.

## Remaining Gap

The repo now proves that a small fixture index can be rebuilt from scratch quickly with stable table counts across two empty-DB runs, and that five fixture queries stay below the initial one-second smoke target.

The current AMD corpus path now has practical query latency fixes, real query timing over more than five ASIP queries, a repeat deterministic graph rebuild benchmark, bounded provider embedding smoke, and a full local Ollama provider embedding backfill timing on a temp DB. This gap is still not fully closed because full raw corpus re-index timing from an empty DB remains open.

## Acceptance Criteria

- A fixture rebuild starts from a deleted temp SQLite database and produces stable counts. Implemented by `asip.cli performance-smoke`.
- Fixture indexing elapsed time is recorded and is within the MVP smoke expectation. Implemented for `docs/fixtures/performance-smoke`.
- At least five fixture/live queries record elapsed time; fixture query time is under one second on the development machine. Implemented for the fixture smoke.
- Real AMD deterministic graph rebuild records repeat elapsed time and stable counts without pretending that unmeasured full raw re-index targets have been met.
- Provider-backed runs distinguish local deterministic fallback time from live Ollama/OpenAI-compatible provider time. Implemented for bounded 128-chunk Ollama smoke and full local temp-copy Ollama backfill; credentialed hosted provider throughput remains open.

## Required Tests

- Core smoke test or QA script: rebuild fixture SQLite from scratch and assert stable document/chunk/evidence/edge counts. Implemented in `packages/core/tests/test_performance_smoke.py`.
- Core/API smoke: run at least five queries and record elapsed time plus result counts. Implemented in the CLI QA artifact through `asip.cli performance-smoke`; the CLI unit test proves the subcommand path, while Web/API route timing remains part of final G11 review if required.
- Real dirty-DB query timing over more than five ASIP queries is recorded in `docs/qa/2026-05-18-query-graph-performance-qa.md`.
- Repeat real-corpus deterministic graph rebuild timing/counts are recorded in `docs/qa/2026-05-18-g15-real-corpus-repeat-graph-rebuild.md`.
- Bounded provider backfill timing is recorded in `docs/qa/2026-05-18-g06-provider-backfill-smoke.md`.
- QA doc entry: real AMD indexing benchmark with source roots, counts, elapsed time, provider mode, and model names.

## Not Closed Until

The final QA package includes both sides of the performance story:

- repeatable fixture rebuild/query timing, now recorded in `docs/qa/2026-05-18-performance-smoke-fixture.md/json`;
- repeat real-corpus deterministic graph rebuild timing, query latency budget review, bounded provider timing, and full local temp-copy provider embedding coverage timing are recorded;
- full raw corpus re-index timing is either measured in a long-running benchmark or explicitly accepted as a residual boundary.

The fixture smoke is a real product CLI path and regression test, but it must not be promoted to full AMD-corpus performance closure.
