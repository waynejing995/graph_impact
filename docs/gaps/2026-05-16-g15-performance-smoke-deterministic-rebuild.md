# G15 Performance Smoke And Deterministic Rebuild

Status: Blocking

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
- Clean AMD raw indexing against `/tmp/asip-mxgpu`, `/tmp/asip-linux-amdgpu`, and `docs/fixtures/amd-amdgpu-docs` produced `/tmp/asip-clean-amd-qwen35-2026-05-17.db` with `documents=124`, `chunks=21884`, `evidence=860543`, `edges=23`, and `files=1349`.
- The provider DB `/tmp/asip-clean-amd-qwen35-provider-2026-05-17.db` reuses that clean index and records 961 provider-sourced embeddings. Serial per-chunk embedding indexing was stopped after it proved too slow; batch `/api/embed` backfill is now implemented but intentionally stopped as partial provider coverage for this QA pass.
- Current free-query QA `docs/qa/2026-05-17-clean-amd-free-query-and-edge-qa.json` records six clean AMD query latencies and one global graph latency. All six queries returned rows; source types across the set were `code/doc/pdf/register`.
- There is no dedicated performance smoke command, timing record, or deterministic rebuild report yet.

## Remaining Gap

The repo does not yet prove that the fixture index can be rebuilt from scratch quickly and deterministically, nor that query latency stays below the initial MVP smoke target.

The real AMD corpus path also needs a first benchmark that records source roots, file counts, document/chunk/evidence/edge counts, elapsed time, and whether provider calls were live or deterministic fallback.

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

The final QA doc includes deterministic rebuild evidence and timing summaries for fixture query/index plus first real-corpus indexing measurements.
