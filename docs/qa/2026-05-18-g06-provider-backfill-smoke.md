# G06 Provider Embedding Backfill Smoke

Date: 2026-05-18

Status: Pass for bounded local Ollama provider backfill; full provider-vector coverage remains a boundary.

JSON artifact: `docs/qa/2026-05-18-g06-provider-backfill-smoke.json`

## Preflight

Local Ollama `/api/tags` was reachable and included:

```text
gemma4:e4b
nomic-embed-text:latest
qwen3.5:4b
qwen3-embedding:4b
```

The live workbench DB provider settings were:

```text
edge: ollama / gemma4:e4b / http://localhost:11434/api/chat
embedding: ollama / nomic-embed-text:latest / http://localhost:11434/api/embeddings
```

Before the smoke, `data/asip.db` had `21884` chunks and `32` provider embeddings. This is partial coverage by design.

## Command

A temporary SQLite copy was created with `sqlite3.Connection.backup()` and then backfilled:

```text
python3 -m asip.cli provider-embeddings --db <tmp-copy> --limit 128 --batch-size 8
```

## Result

```text
exit_code=0
elapsed_seconds=17.703
provider=ollama
model=nomic-embed-text:latest
embedded_chunks=128
batch_size=8
limit=128
```

The temp DB then had:

```text
ollama / nomic-embed-text:latest / metadata.source=provider / count=160
```

Recent job status:

```text
embedding_backfill succeeded Embedded 128 chunks
```

## Residuals

- This proves the product CLI can run a bounded provider backfill through local Ollama.
- This does not claim full provider-vector coverage for all `21884` chunks.
- Credentialed live OpenAI-compatible provider QA and query-time provider reranking remain open boundaries.
