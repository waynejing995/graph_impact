# G15 Performance Smoke And Deterministic Rebuild

Status: Partial; real graph rebuild benchmark exists, deterministic repeat/embedding timing still open

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

## Remaining Gap

The repo does not yet prove that the fixture index can be rebuilt from scratch quickly and deterministically, nor that query latency stays below the initial MVP smoke target.

The current dirty AMD corpus path now has a practical query latency fix and a graph rebuild benchmark. This gap is still not fully closed because clean-from-zero deterministic repeat timing and full provider embedding backfill timing remain open.

## Acceptance Criteria

- A fixture rebuild starts from a deleted temp SQLite database and produces stable counts.
- Fixture indexing elapsed time is recorded and is within the MVP smoke expectation.
- At least five fixture/live queries record elapsed time; fixture query time is under one second on the development machine.
- Real AMD corpus indexing records elapsed time and counts without pretending that unmeasured performance targets have been met.
- Provider-backed runs distinguish local deterministic fallback time from live Ollama/OpenAI-compatible provider time.

## Required Tests

- Core smoke test or QA script: rebuild fixture SQLite from scratch and assert stable document/chunk/evidence/edge counts.
- Core/API smoke: run at least five queries and record elapsed time plus result counts.
- QA doc entry: real AMD indexing benchmark with source roots, counts, elapsed time, provider mode, and model names.

## Not Closed Until

The final QA doc includes deterministic rebuild evidence and timing summaries for fixture query/index plus first real-corpus indexing measurements. A continuation regression test now proves scoped deterministic graph rebuilds preserve other corpus edges when `--corpus-id` is used, preventing partial rebuilds from destroying unrelated graph state.
