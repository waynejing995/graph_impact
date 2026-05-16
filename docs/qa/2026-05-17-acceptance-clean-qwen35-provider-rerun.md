# ASIP Acceptance Query Run

Generated: 2026-05-16T20:45:33+00:00
DB: `/tmp/asip-acceptance-clean-2026-05-17.db`
Surfaces checked: CLI, API, Web, MCP

## Summary

- Total: 9
- Passed: 9
- Partial: 0
- Failed: 0

## Queries

| ID | Status | Rows | Graph | Missing surfaces | Query |
| --- | --- | ---: | ---: | --- | --- |
| AQ01 | pass | 24 | 2 nodes / 2 edges | - | Who reads or writes regGCVM_L2_CNTL? |
| AQ02 | pass | 24 | 1 nodes / 0 edges | - | Which fields of GCVM_L2_CNTL are set in MxGPU gfx_v11_0.c? |
| AQ03 | pass | 24 | 2 nodes / 1 edges | - | Where is IH_RB_CNTL configured, and which fields are modified? |
| AQ04 | pass | 24 | 2 nodes / 1 edges | - | Which code paths reference SDMA0_QUEUE0_RB_CNTL or SDMA1_QUEUE0_RB_CNTL? |
| AQ05 | pass | 24 | 1 nodes / 0 edges | - | Show evidence connecting amdgpu documentation to the amdgpu driver source tree. |
| AQ06 | pass | 24 | 2 nodes / 1 edges | - | Given WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp), explain the resolved register entity and macro expansion chain. |
| AQ07 | pass | 24 | 1 nodes / 0 edges | - | Change resolver profile to add or rename one C/C++ register access wrapper, then verify the same resolver engine resolves it without code changes. |
| AQ08 | pass | 24 | 1 nodes / 0 edges | - | Add a toy Python resolver profile extracting a configured function-call or string-symbol reference, proving profiles are not macro-only. |
| AQ09 | pass | 24 | 1 nodes / 0 edges | - | Run embedding and optional semantic-edge extraction through a configured Ollama provider, then switch to an OpenAI-compatible provider without changing retrieval or resolver code. |

## Provider Checks

| Check | Status | Provider | Model | Details |
| --- | --- | --- | --- | --- |
| embedding | pass | ollama | nomic-embed-text:latest | embeddings=9058, fallback=382 |
| semantic_edge | pass | ollama | qwen3.5:4b | edges=1 |
