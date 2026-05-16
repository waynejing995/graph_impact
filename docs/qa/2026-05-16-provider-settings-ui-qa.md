# Provider Settings UI QA

Date: `2026-05-16`

## Scope

- Settings page supports editing provider runtime values without source-code changes.
- Persisted settings match the core semantic-edge model config fields.
- Core semantic-edge runner supports Ollama and OpenAI-compatible chat-completions providers.
- Extra headers can be configured from UI and carried into the runtime config preview.

## Fields Covered

- Provider: `ollama` or `openai-compatible`.
- Chat API base URL: `api_base_url`.
- Chat API path: `api_path`.
- Edge model: `preferred`.
- Fallback model: `fallback`; blank UI input is trimmed and saved as `""`.
- Embedding model: `embedding_model`.
- Timeout seconds, context tokens, prediction tokens, temperature, and thinking toggle.
- Extra headers JSON persisted as a string map.

## Browser QA

Target: `http://127.0.0.1:3100/settings`

- Selected provider: `OpenAI compatible`.
- Set chat API base URL: `https://llm.example.test`.
- Set chat API path: `/v1/chat/completions`.
- Set edge model: `gemma4:e4b`.
- Cleared fallback model; runtime preview shows `"fallback": ""`.
- Set embedding model: `text-embedding-3-small`.
- Set timeout/context/prediction/temperature: `123`, `4096`, `777`, `0.25`.
- Enabled model thinking.
- Set extra headers JSON:
  `{"Authorization":"Bearer local-test","X-ASIP-Workspace":"amd-mvp1"}`.
- Clicked `Save provider settings`.
- Verified `Provider settings saved`.
- Verified status badge: `OpenAI-compatible: gemma4:e4b`.
- Verified runtime config preview contains `provider`, `api_base_url`, `api_path`, `preferred`, `fallback`, `embedding_model`, `extra_headers`, `num_ctx`, `num_predict`, `temperature`, `think`, and `timeout_seconds`.
- Clicked `Run provider smoke` and verified `Run provider smoke queued`.
- Switched to light theme and verified the settings page remained readable.

Screenshot evidence from the browser run: `/tmp/asip-settings.png`.

## Core Provider QA

- Config loading normalizes provider ids such as ` OpenAI-Compatible ` to `openai-compatible`.
- OpenAI-compatible provider uses chat-completions request shape with configured endpoint and extra headers.
- Empty fallback does not retry for Ollama or OpenAI-compatible providers.
- Injected non-Ollama providers do not run `ollama stop` or `ollama ps`.
- Ollama cleanup stops every attempted model, including fallback models used after preferred-model failure.
- Added example config: `configs/edge_cases/full-corpus-openai-compatible-example.json`.

## Verification Commands

Fresh verification after the provider/settings changes:

- `PYTHONPATH=packages/core/src python3 -m unittest packages/core/tests/test_semantic_edges.py -v`
  - Result: `27` tests passed.
- `pnpm --filter web lint`
  - Result: passed.
- `pnpm --filter web test:ui`
  - Result: `14` tests passed.
- `pnpm --filter web build`
  - Result: passed; static routes generated for `/`, `/graph`, `/corpus`, `/resolver-profiles`, `/acceptance`, and `/settings`.
