# OpenAI-Compatible Live Smoke

- Generated: `2026-05-21T04:04:01+00:00`
- Repo head: `593e47197e07fb24053591ccf9d0e207039dd1ff`
- Base URL: `http://localhost:11434`
- Gate: `pass`
- Credential mode: `local-compatible-no-secret`

Uses Ollama OpenAI-compatible /v1 endpoints as a live compatibility surface; this is not a hosted credentialed OpenAI endpoint.

| Check | Status | Model | Evidence |
| --- | --- | --- | --- |
| `openai_compatible_embeddings_live` | `pass` | `nomic-embed-text:latest` | vector_dimension=768 |
| `openai_compatible_chat_completions_live` | `pass` | `gemma4:e4b` | persistable_edge_count=1; sample=GCVM_L2_CNTL sets_field ENABLE_L2_CACHE |
