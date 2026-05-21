# ASIP Acceptance Query Run

Generated: 2026-05-20T09:58:39+00:00
DB: `data/asip.db`
Surfaces checked: CLI, API, MCP

## Summary

- Total: 9
- Passed: 0
- Partial: 8
- Failed: 1

## Database Health

- Status: pass
- Failure reasons: -

## Queries

| ID | Status | Schema | Rows | Source types | Graph | Surfaces | Missing surfaces | Failure reasons | Query |
| --- | --- | --- | ---: | --- | ---: | --- | --- | --- | --- |
| AQ01 | partial | pass | 24 | code, register | 33 nodes / 93 edges | CLI pass core.query_evidence rows=24 graph=33n/93e; API pass fastapi.testclient.query rows=24 graph=33n/93e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=33n/93e | Web | - | Who reads or writes regGCVM_L2_CNTL? |
| AQ02 | partial | pass | 24 | code, doc, register | 34 nodes / 93 edges | CLI pass core.query_evidence rows=24 graph=34n/93e; API pass fastapi.testclient.query rows=24 graph=34n/93e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=34n/93e | Web | - | Which fields of GCVM_L2_CNTL are set in MxGPU gfx_v11_0.c? |
| AQ03 | partial | pass | 24 | code, doc, register | 124 nodes / 435 edges | CLI pass core.query_evidence rows=24 graph=124n/435e; API pass fastapi.testclient.query rows=24 graph=124n/435e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=124n/435e | Web | - | Where is IH_RB_CNTL configured, and which fields are modified? |
| AQ04 | partial | pass | 24 | code, doc, pdf, register | 110 nodes / 167 edges | CLI pass core.query_evidence rows=24 graph=110n/167e; API pass fastapi.testclient.query rows=24 graph=110n/167e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=110n/167e | Web | - | Which code paths reference SDMA0_QUEUE0_RB_CNTL or SDMA1_QUEUE0_RB_CNTL? |
| AQ05 | partial | pass | 24 | code, doc, pdf, register | 2 nodes / 0 edges | CLI pass core.query_evidence rows=24 graph=2n/0e; API pass fastapi.testclient.query rows=24 graph=2n/0e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=2n/0e | Web | - | Show evidence connecting amdgpu documentation to the amdgpu driver source tree. |
| AQ06 | partial | pass | 24 | code, doc, register | 34 nodes / 93 edges | CLI pass core.query_evidence rows=24 graph=34n/93e; API pass fastapi.testclient.query rows=24 graph=34n/93e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=34n/93e | Web | - | Given WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp), explain the resolved register entity and macro expansion chain. |
| AQ07 | partial | pass | 24 | code, doc, pdf, register | 2 nodes / 0 edges | CLI pass core.query_evidence rows=24 graph=2n/0e; API pass fastapi.testclient.query rows=24 graph=2n/0e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=2n/0e | Web | - | Change resolver profile to add or rename one C/C++ register access wrapper, then verify the same resolver engine resolves it without code changes. |
| AQ08 | partial | pass | 24 | code, doc, register | 1 nodes / 0 edges | CLI pass core.query_evidence rows=24 graph=1n/0e; API pass fastapi.testclient.query rows=24 graph=1n/0e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=1n/0e | Web | - | Add a toy Python resolver profile extracting a configured function-call or string-symbol reference, proving profiles are not macro-only. |
| AQ09 | fail | pass | 24 | code, doc, pdf, register | 2 nodes / 0 edges | CLI pass core.query_evidence rows=24 graph=2n/0e; API pass fastapi.testclient.query rows=24 graph=2n/0e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=2n/0e | - | embedding provider check failed: provider embedding provenance exists but 125962 deterministic fallback embeddings remain; 27/125989 embeddings match the configured provider; 21852 chunks have no embeddings; 125989/147841 chunks have embeddings, embedding_live provider check failed: embedding provider failed: <urlopen error [Errno 1] Operation not permitted>, semantic_edge_provenance provider check failed: persisted semantic edges are older than latest succeeded index or graph rebuild job, doc_node_provenance provider check failed: persisted doc-node semantic edges are older than latest succeeded index or graph rebuild job, semantic_edge provider check failed: semantic edge provider failed: Ollama edge generation failed: gemma4:e4b: <urlopen error [Errno 1] Operation not permitted> | Run embedding and optional semantic-edge extraction through a configured Ollama provider, then switch to an OpenAI-compatible provider without changing retrieval or resolver code. |

## Provider Checks

| Check | Status | Provider | Model | Details |
| --- | --- | --- | --- | --- |
| embedding | partial | ollama | nomic-embed-text:latest | embeddings=27, fallback=125962, missing_chunk_embeddings=21852, embedded_chunks=125989/147841, provider embedding provenance exists but 125962 deterministic fallback embeddings remain; 27/125989 embeddings match the configured provider; 21852 chunks have no embeddings; 125989/147841 chunks have embeddings |
| embedding_live | fail | ollama | nomic-embed-text:latest | embedding provider failed: <urlopen error [Errno 1] Operation not permitted> |
| semantic_edge_provenance | partial | ollama | gemma4:e4b | edges=0, stale_edges=14, stale_jobs=4, latest_index_job=10, ignored=11, persisted semantic edges are older than latest succeeded index or graph rebuild job |
| doc_node_provenance | partial | ollama | gemma4:e4b | edges=0, stale_edges=11, stale_jobs=5, latest_index_job=10, ignored=14, persisted doc-node semantic edges are older than latest succeeded index or graph rebuild job |
| semantic_edge | fail | ollama | gemma4:e4b | semantic edge provider failed: Ollama edge generation failed: gemma4:e4b: <urlopen error [Errno 1] Operation not permitted> |
