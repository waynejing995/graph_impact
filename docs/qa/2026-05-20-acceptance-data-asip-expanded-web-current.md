# ASIP Acceptance Query Run

Generated: 2026-05-20T14:43:17+00:00
DB: `data/asip.db`
Surfaces checked: CLI, API, Web, MCP

## Summary

- Total: 9
- Passed: 8
- Partial: 0
- Failed: 1

## Database Health

- Status: pass
- Failure reasons: -

## Queries

| ID | Status | Schema | Rows | Source types | Graph | Surfaces | Missing surfaces | Failure reasons | Query |
| --- | --- | --- | ---: | --- | ---: | --- | --- | --- | --- |
| AQ01 | pass | pass | 24 | code, register | 33 nodes / 93 edges | CLI pass core.query_evidence rows=24 graph=33n/93e; API pass fastapi.testclient.query rows=24 graph=33n/93e; Web pass next-bff.query rows=24 graph=33n/93e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=33n/93e | - | - | Who reads or writes regGCVM_L2_CNTL? |
| AQ02 | pass | pass | 24 | code, doc, register | 34 nodes / 93 edges | CLI pass core.query_evidence rows=24 graph=34n/93e; API pass fastapi.testclient.query rows=24 graph=34n/93e; Web pass next-bff.query rows=24 graph=34n/93e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=34n/93e | - | - | Which fields of GCVM_L2_CNTL are set in MxGPU gfx_v11_0.c? |
| AQ03 | pass | pass | 24 | code, doc, register | 124 nodes / 435 edges | CLI pass core.query_evidence rows=24 graph=124n/435e; API pass fastapi.testclient.query rows=24 graph=124n/435e; Web pass next-bff.query rows=24 graph=124n/435e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=124n/435e | - | - | Where is IH_RB_CNTL configured, and which fields are modified? |
| AQ04 | pass | pass | 24 | code, doc, pdf, register | 110 nodes / 167 edges | CLI pass core.query_evidence rows=24 graph=110n/167e; API pass fastapi.testclient.query rows=24 graph=110n/167e; Web pass next-bff.query rows=24 graph=110n/167e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=110n/167e | - | - | Which code paths reference SDMA0_QUEUE0_RB_CNTL or SDMA1_QUEUE0_RB_CNTL? |
| AQ05 | pass | pass | 24 | code, doc, pdf, register | 2 nodes / 0 edges | CLI pass core.query_evidence rows=24 graph=2n/0e; API pass fastapi.testclient.query rows=24 graph=2n/0e; Web pass next-bff.query rows=24 graph=2n/0e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=2n/0e | - | - | Show evidence connecting amdgpu documentation to the amdgpu driver source tree. |
| AQ06 | pass | pass | 24 | code, doc, register | 34 nodes / 93 edges | CLI pass core.query_evidence rows=24 graph=34n/93e; API pass fastapi.testclient.query rows=24 graph=34n/93e; Web pass next-bff.query rows=24 graph=34n/93e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=34n/93e | - | - | Given WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp), explain the resolved register entity and macro expansion chain. |
| AQ07 | pass | pass | 24 | code, doc, pdf, register | 2 nodes / 0 edges | CLI pass core.query_evidence rows=24 graph=2n/0e; API pass fastapi.testclient.query rows=24 graph=2n/0e; Web pass next-bff.query rows=24 graph=2n/0e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=2n/0e | - | - | Change resolver profile to add or rename one C/C++ register access wrapper, then verify the same resolver engine resolves it without code changes. |
| AQ08 | pass | pass | 24 | code, doc, register | 1 nodes / 0 edges | CLI pass core.query_evidence rows=24 graph=1n/0e; API pass fastapi.testclient.query rows=24 graph=1n/0e; Web pass next-bff.query rows=24 graph=1n/0e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=1n/0e | - | - | Add a toy Python resolver profile extracting a configured function-call or string-symbol reference, proving profiles are not macro-only. |
| AQ09 | fail | pass | 24 | code, doc, pdf, register | 2 nodes / 0 edges | CLI pass core.query_evidence rows=24 graph=2n/0e; API pass fastapi.testclient.query rows=24 graph=2n/0e; Web pass next-bff.query rows=24 graph=2n/0e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=2n/0e | - | embedding provider check failed: provider embedding provenance exists but 125962 deterministic fallback embeddings remain; 18299/144261 embeddings match the configured provider; 3580 chunks have no embeddings; 144261/147841 chunks have embeddings | Run embedding and optional semantic-edge extraction through a configured Ollama provider, then switch to an OpenAI-compatible provider without changing retrieval or resolver code. |

## Provider Checks

| Check | Status | Provider | Model | Details |
| --- | --- | --- | --- | --- |
| embedding | partial | ollama | nomic-embed-text:latest | embeddings=18299, fallback=125962, missing_chunk_embeddings=3580, embedded_chunks=144261/147841, provider embedding provenance exists but 125962 deterministic fallback embeddings remain; 18299/144261 embeddings match the configured provider; 3580 chunks have no embeddings; 144261/147841 chunks have embeddings |
| embedding_live | pass | ollama | nomic-embed-text:latest | embeddings=1, vector_dim=768 |
| semantic_edge_provenance | pass | ollama | gemma4:e4b | edges=18, stale_edges=0, jobs=18, latest_index_job=10, ignored=3 |
| doc_node_provenance | pass | ollama | gemma4:e4b | edges=3, stale_edges=0, jobs=20, latest_index_job=10, ignored=18 |
| semantic_edge | pass | ollama | gemma4:e4b | edges=1 |
