# ASIP Acceptance Query Run

Generated: 2026-05-16T21:10:32+00:00
DB: `/tmp/asip-acceptance-clean-2026-05-17.db`
Surfaces checked: CLI, API, Web, MCP

## Summary

- Total: 9
- Passed: 0
- Partial: 0
- Failed: 9

## Database Health

- Status: fail
- Failure reasons: corpus mxgpu status is indexing, index job 3 failed: Interrupted after long serial provider embedding reindex; 9440 embeddings written before stop

## Queries

| ID | Status | Rows | Source types | Graph | Missing surfaces | Failure reasons | Query |
| --- | --- | ---: | --- | ---: | --- | --- | --- |
| AQ01 | fail | 24 | code | 2 nodes / 2 edges | - | corpus mxgpu status is indexing, index job 3 failed: Interrupted after long serial provider embedding reindex; 9440 embeddings written before stop | Who reads or writes regGCVM_L2_CNTL? |
| AQ02 | fail | 24 | code, doc | 1 nodes / 0 edges | - | corpus mxgpu status is indexing, index job 3 failed: Interrupted after long serial provider embedding reindex; 9440 embeddings written before stop | Which fields of GCVM_L2_CNTL are set in MxGPU gfx_v11_0.c? |
| AQ03 | fail | 24 | code | 2 nodes / 1 edges | - | corpus mxgpu status is indexing, index job 3 failed: Interrupted after long serial provider embedding reindex; 9440 embeddings written before stop | Where is IH_RB_CNTL configured, and which fields are modified? |
| AQ04 | fail | 24 | code | 2 nodes / 1 edges | - | corpus mxgpu status is indexing, index job 3 failed: Interrupted after long serial provider embedding reindex; 9440 embeddings written before stop | Which code paths reference SDMA0_QUEUE0_RB_CNTL or SDMA1_QUEUE0_RB_CNTL? |
| AQ05 | fail | 24 | code, doc | 1 nodes / 0 edges | - | corpus mxgpu status is indexing, index job 3 failed: Interrupted after long serial provider embedding reindex; 9440 embeddings written before stop, required source types missing: pdf | Show evidence connecting amdgpu documentation to the amdgpu driver source tree. |
| AQ06 | fail | 24 | code | 2 nodes / 1 edges | - | corpus mxgpu status is indexing, index job 3 failed: Interrupted after long serial provider embedding reindex; 9440 embeddings written before stop | Given WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp), explain the resolved register entity and macro expansion chain. |
| AQ07 | fail | 24 | code | 1 nodes / 0 edges | - | corpus mxgpu status is indexing, index job 3 failed: Interrupted after long serial provider embedding reindex; 9440 embeddings written before stop | Change resolver profile to add or rename one C/C++ register access wrapper, then verify the same resolver engine resolves it without code changes. |
| AQ08 | fail | 24 | code, doc | 1 nodes / 0 edges | - | corpus mxgpu status is indexing, index job 3 failed: Interrupted after long serial provider embedding reindex; 9440 embeddings written before stop | Add a toy Python resolver profile extracting a configured function-call or string-symbol reference, proving profiles are not macro-only. |
| AQ09 | fail | 24 | code, doc | 1 nodes / 0 edges | - | corpus mxgpu status is indexing, index job 3 failed: Interrupted after long serial provider embedding reindex; 9440 embeddings written before stop | Run embedding and optional semantic-edge extraction through a configured Ollama provider, then switch to an OpenAI-compatible provider without changing retrieval or resolver code. |

## Provider Checks

| Check | Status | Provider | Model | Details |
| --- | --- | --- | --- | --- |
| embedding | pass | ollama | nomic-embed-text:latest | embeddings=9058, fallback=382 |
| semantic_edge | pass | ollama | qwen3.5:4b | edges=1 |
