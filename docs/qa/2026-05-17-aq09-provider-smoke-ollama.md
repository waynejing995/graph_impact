# ASIP Acceptance Query Run

Generated: 2026-05-16T17:51:35+00:00
DB: `/tmp/asip-aq09-provider.db`
Surfaces checked: CLI

## Summary

- Total: 1
- Passed: 0
- Partial: 1
- Failed: 0

## Queries

| ID | Status | Rows | Graph | Missing surfaces | Query |
| --- | --- | ---: | ---: | --- | --- |
| AQ09 | partial | 2 | 1 nodes / 0 edges | API, Web | Run embedding and optional semantic-edge extraction through a configured Ollama provider, then switch to an OpenAI-compatible provider without changing retrieval or resolver code. |

## Provider Checks

| Check | Status | Provider | Model | Details |
| --- | --- | --- | --- | --- |
| embedding | pass | ollama | nomic-embed-text:latest | embeddings=1, fallback=0 |
| semantic_edge | pass | ollama | gemma4:e4b | edges=1 |
