# ASIP Acceptance Query Run

Generated: 2026-05-16T17:38:40+00:00
DB: `/tmp/asip-acceptance-clean-2026-05-17.db`
Surfaces checked: CLI

## Summary

- Total: 9
- Passed: 0
- Partial: 8
- Failed: 1

## Queries

| ID | Status | Rows | Graph | Missing surfaces | Query |
| --- | --- | ---: | ---: | --- | --- |
| AQ01 | partial | 14 | 2 nodes / 1 edges | API, Web, MCP | Who reads or writes regGCVM_L2_CNTL? |
| AQ02 | partial | 24 | 3 nodes / 2 edges | API, Web | Which fields of GCVM_L2_CNTL are set in MxGPU gfx_v11_0.c? |
| AQ03 | partial | 24 | 2 nodes / 1 edges | API, Web | Where is IH_RB_CNTL configured, and which fields are modified? |
| AQ04 | partial | 24 | 2 nodes / 1 edges | API, Web | Which code paths reference SDMA0_QUEUE0_RB_CNTL or SDMA1_QUEUE0_RB_CNTL? |
| AQ05 | partial | 24 | 2 nodes / 1 edges | API, Web | Show evidence connecting amdgpu documentation to the amdgpu driver source tree. |
| AQ06 | partial | 24 | 2 nodes / 1 edges | API, Web, MCP | Given WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp), explain the resolved register entity and macro expansion chain. |
| AQ07 | partial | 24 | 1 nodes / 0 edges | API, Web | Change resolver profile to add or rename one C/C++ register access wrapper, then verify the same resolver engine resolves it without code changes. |
| AQ08 | partial | 24 | 1 nodes / 0 edges | API, Web | Add a toy Python resolver profile extracting a configured function-call or string-symbol reference, proving profiles are not macro-only. |
| AQ09 | fail | 24 | 1 nodes / 0 edges | API, Web | Run embedding and optional semantic-edge extraction through a configured Ollama provider, then switch to an OpenAI-compatible provider without changing retrieval or resolver code. |
