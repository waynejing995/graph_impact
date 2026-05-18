# G06 Full Provider Backfill Temp DB QA

Date: 2026-05-18

Status: pass for full local Ollama provider embedding coverage on a temp DB; query-time provider rerank wiring is covered by `docs/qa/2026-05-18-g06-query-time-provider-rerank-qa.md`; credentialed OpenAI-compatible QA remains residual.

JSON artifact: `docs/qa/2026-05-18-g06-full-provider-backfill-tempdb-qa.json`

## Scope

This QA replaces the earlier bounded 128-chunk provider smoke with a full temp-copy backfill of the current ASIP SQLite corpus.

The DB was a backup copy of `data/asip.db`:

```text
/tmp/asip-provider-embed-batch-smoke-20260518-133434.db
documents: 124
chunks: 21884
evidence: 860516
edges: 41942
```

Provider settings used:

```text
edge: ollama / gemma4:e4b / http://localhost:11434/api/chat / think:false
embedding: ollama / nomic-embed-text:latest / http://localhost:11434/api/embed
```

## Debugged Failure

The first full backfill attempt used a larger batch and failed:

```text
job_id=9
status=failed
message=HTTP Error 400: Bad Request
```

Manual debug showed Ollama rejected an over-large embedding input/context. The fix now:

- uses configured `embedding.batchSize: 16`;
- truncates long provider input text to `embedding.maxTextChars: 4096`;
- records `embedding_text_truncated`, `embedding_text_chars`, and `original_text_chars`;
- recursively splits batches if a provider reports context/input too large.

## Full Backfill Command

```text
/usr/bin/time -p env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
  python3 -m asip.cli provider-embeddings \
  --db /tmp/asip-provider-embed-batch-smoke-20260518-133434.db
```

Result:

```text
source: provider_embedding_backfill
provider: ollama
model: nomic-embed-text:latest
embedded_chunks: 12572
truncated_chunks: 10770
batch_size: 16
limit: 0
job_id: 10
real: 2388.07s
```

Final temp DB coverage:

```text
ollama / nomic-embed-text:latest embeddings: 21884
missing provider embeddings: 0
truncated provider embeddings: 10770
job 10: succeeded, Embedded 12572 chunks; truncated 10770 long inputs
```

`embedded_chunks=12572` is the resumed job's newly embedded chunk count. The temp DB already had embeddings from earlier job 8 and the failed job 9 before job 10 resumed. The final coverage count is `21884 / 21884`.

## Real Stage 2 Semantic Edge Check

After the full backfill, a real query-scoped semantic-edge call was run through local Ollama `gemma4:e4b`.

Before the dedupe fix:

```text
job_id=11
query=GCVM_L2_CNTL
provider=ollama
model=gemma4:e4b
edge_count=2
observed duplicate: regGCVM_L2_CNTL reads GCVM_L2_CNTL
```

After the dedupe regression fix:

```text
/usr/bin/time -p env PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
  python3 -m asip.cli semantic-edges \
  --db /tmp/asip-provider-embed-batch-smoke-20260518-133434.db \
  --q GCVM_L2_CNTL \
  --limit 4
```

Result:

```text
job_id=12
provider=ollama
model=gemma4:e4b
evidence_rows=4
edge_count=1
elapsed=51.44s
persisted edge: regGCVM_L2_CNTL reads GCVM_L2_CNTL
```

The temp DB now has `28` semantic `ollama` edges total.

## Tests

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_backend_state.WorkbenchBackendStateTests.test_backfill_provider_embeddings_splits_context_too_large_batches \
  packages.core.tests.test_workbench_backend_state.WorkbenchBackendStateTests.test_backfill_provider_embeddings_truncates_long_inputs_with_metadata \
  -v

OK
```

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_semantic_edge_job_deduplicates_provider_edges_before_persisting \
  -v

OK
```

## Residuals

- This proves full local Ollama provider embedding coverage on a temp copy, not credentialed live OpenAI-compatible coverage.
- Query-time provider-vector rerank wiring and explicit provider query-embedding fallback metadata are now covered by `docs/qa/2026-05-18-g06-query-time-provider-rerank-qa.md` and the G15 empty-DB follow-up tests; production semantic ranking quality remains open.
- Long chunks are intentionally truncated for local embedding context and carry explicit metadata.
