# ASIP Acceptance Query Run

Generated: 2026-05-19T02:20:47+00:00
DB: `data/asip.db`
Surfaces checked: CLI, API, Web, MCP

## Summary

- Total: 9
- Passed: 9
- Partial: 0
- Failed: 0

## Database Health

- Status: pass
- Failure reasons: -

## Queries

| ID | Status | Rows | Source types | Graph | Surfaces | Missing surfaces | Failure reasons | Query |
| --- | --- | ---: | --- | ---: | --- | --- | --- | --- |
| AQ01 | pass | 24 | code, register | 35 nodes / 93 edges | CLI pass core.query_evidence rows=24 graph=35n/93e; API pass fastapi.testclient.query rows=24 graph=35n/93e; Web pass next-bff.query rows=24 graph=35n/93e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=35n/93e | - | - | Who reads or writes regGCVM_L2_CNTL? |
| AQ02 | pass | 24 | code, doc, register | 82 nodes / 191 edges | CLI pass core.query_evidence rows=24 graph=82n/191e; API pass fastapi.testclient.query rows=24 graph=82n/191e; Web pass next-bff.query rows=24 graph=82n/191e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=82n/191e | - | - | Which fields of GCVM_L2_CNTL are set in MxGPU gfx_v11_0.c? |
| AQ03 | pass | 24 | code, doc, register | 123 nodes / 423 edges | CLI pass core.query_evidence rows=24 graph=123n/423e; API pass fastapi.testclient.query rows=24 graph=123n/423e; Web pass next-bff.query rows=24 graph=123n/423e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=123n/423e | - | - | Where is IH_RB_CNTL configured, and which fields are modified? |
| AQ04 | pass | 24 | code, doc, pdf, register | 110 nodes / 167 edges | CLI pass core.query_evidence rows=24 graph=110n/167e; API pass fastapi.testclient.query rows=24 graph=110n/167e; Web pass next-bff.query rows=24 graph=110n/167e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=110n/167e | - | - | Which code paths reference SDMA0_QUEUE0_RB_CNTL or SDMA1_QUEUE0_RB_CNTL? |
| AQ05 | pass | 24 | code, doc, pdf, register | 3 nodes / 0 edges | CLI pass core.query_evidence rows=24 graph=3n/0e; API pass fastapi.testclient.query rows=24 graph=3n/0e; Web pass next-bff.query rows=24 graph=3n/0e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=3n/0e | - | - | Show evidence connecting amdgpu documentation to the amdgpu driver source tree. |
| AQ06 | pass | 24 | code, doc, register | 36 nodes / 93 edges | CLI pass core.query_evidence rows=24 graph=36n/93e; API pass fastapi.testclient.query rows=24 graph=36n/93e; Web pass next-bff.query rows=24 graph=36n/93e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=36n/93e | - | - | Given WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp), explain the resolved register entity and macro expansion chain. |
| AQ07 | pass | 24 | pdf, register | 1 nodes / 0 edges | CLI pass core.query_evidence rows=24 graph=1n/0e; API pass fastapi.testclient.query rows=24 graph=1n/0e; Web pass next-bff.query rows=24 graph=1n/0e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=1n/0e | - | - | Change resolver profile to add or rename one C/C++ register access wrapper, then verify the same resolver engine resolves it without code changes. |
| AQ08 | pass | 24 | doc, register | 1 nodes / 0 edges | CLI pass core.query_evidence rows=24 graph=1n/0e; API pass fastapi.testclient.query rows=24 graph=1n/0e; Web pass next-bff.query rows=24 graph=1n/0e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=1n/0e | - | - | Add a toy Python resolver profile extracting a configured function-call or string-symbol reference, proving profiles are not macro-only. |
| AQ09 | pass | 24 | pdf, register | 1 nodes / 0 edges | CLI pass core.query_evidence rows=24 graph=1n/0e; API pass fastapi.testclient.query rows=24 graph=1n/0e; Web pass next-bff.query rows=24 graph=1n/0e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=1n/0e | - | - | Run embedding and optional semantic-edge extraction through a configured Ollama provider, then switch to an OpenAI-compatible provider without changing retrieval or resolver code. |

## Provider Checks

| Check | Status | Provider | Model | Details |
| --- | --- | --- | --- | --- |
| embedding | pass | ollama | nomic-embed-text:latest | embeddings=32, fallback=0 |
| semantic_edge | pass | ollama | gemma4:e4b | edges=1 |
