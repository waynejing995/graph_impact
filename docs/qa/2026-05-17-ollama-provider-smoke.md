# Ollama Provider Smoke

Date: 2026-05-17
Status: partial provider QA for G06/AQ09

## Local Models Detected

`http://localhost:11434/api/tags` reported:

- `gemma4:e4b`
- `qwen3.5:4b`
- `qwen3-embedding:4b`
- `nomic-embed-text:latest`
- `qwen2.5:1.5b`

## Embedding Smoke

Command path: `packages/core/src/asip/providers.py` via `EmbeddingProviderConfig(provider="ollama")`.

Input: `GCVM_L2_CNTL register field evidence`

| Model | Result |
| --- | --- |
| `nomic-embed-text:latest` | 768-dimensional vector returned |
| `qwen3-embedding:4b` | 2560-dimensional vector returned |

Combined elapsed time for both embedding calls: 5.79s.

## Chat/Semantic-Edge Smoke

Prompt: return compact JSON for `GCVM_L2_CNTL has field ENABLE_L2_CACHE`.

| Model | Settings | Result | Elapsed |
| --- | --- | --- | --- |
| `qwen3.5:4b` | default thinking behavior, `num_predict=96` | `content` empty, `thinking` present, `done_reason=length` | 26.85s |
| `qwen3.5:4b` | `think:false`, `num_predict=128`, `temperature=0` | JSON returned: `{"edge": "GCVM_L2_CNTL", "confidence": 1.0}` | 2.19s |
| `gemma4:e4b` | `think:false`, `num_predict=128`, `temperature=0` | JSON returned: `{"edge": "GCVM_L2_CNTL has field ENABLE_L2_CACHE.", "confidence": 1.0}` | 9.74s |

## Resource Note

After the gemma smoke, `/api/ps` showed `gemma4:e4b` resident at about 12.96 GB and the Ollama runner process at roughly 50.8% memory. The smoke stopped `gemma4:e4b` and `nomic-embed-text:latest`; `/api/ps` then returned an empty model list.

## Interpretation

- `qwen3.5:4b` is usable only if `think:false` is configured for this semantic-edge style smoke; otherwise it may spend the whole response budget in thinking.
- `gemma4:e4b` produced the better compact edge string in this smoke, but it is materially heavier in memory.
- AQ09 remains open: this smoke proves local Ollama provider availability, not end-to-end embedding job provenance, semantic-edge job integration, or OpenAI-compatible provider switching.
