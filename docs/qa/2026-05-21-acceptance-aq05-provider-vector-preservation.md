# ASIP Acceptance Query Run

Generated: 2026-05-21T04:35:10+00:00
DB: `data/asip.db`
Surfaces checked: CLI, API, API_LIVE, Web, MCP, MCP_PROTOCOL

## Summary

- Total: 1
- Passed: 1
- Partial: 0
- Failed: 0

## Database Health

- Status: pass
- Failure reasons: -

## Queries

| ID | Status | Schema | Rows | Source types | Graph | Surfaces | Missing surfaces | Failure reasons | Query |
| --- | --- | --- | ---: | --- | ---: | --- | --- | --- | --- |
| AQ05 | pass | pass | 24 | code, doc, pdf, register | 3 nodes / 0 edges | CLI pass core.query_evidence rows=24 graph=3n/0e; API pass fastapi.testclient.query rows=24 graph=3n/0e; API_LIVE pass fastapi.uvicorn.http.query rows=24 graph=2n/0e; Web pass next-bff.query rows=24 graph=3n/0e; MCP pass mcp.tool-direct.search_evidence rows=24 graph=3n/0e; MCP_PROTOCOL pass mcp.stdio.protocol.search_evidence rows=24 graph=3n/0e | - | - | Show evidence connecting amdgpu documentation to the amdgpu driver source tree. |

## Provider Checks

| Check | Status | Provider | Model | Details |
| --- | --- | --- | --- | --- |
| embedding | pass | ollama | nomic-embed-text:latest | embeddings=147841, fallback=0, missing_chunk_embeddings=0, embedded_chunks=147841/147841, provider embedding provenance exists |
| embedding_live | pass | ollama | nomic-embed-text:latest | embeddings=1, vector_dim=768 |
| semantic_edge_provenance | pass | ollama | gemma4:e4b | edges=10, stale_edges=0, jobs=45, latest_index_job=10, ignored=4 |
| doc_node_provenance | pass | ollama | gemma4:e4b | edges=4, stale_edges=0, jobs=49, latest_index_job=10, ignored=10 |
| semantic_edge | pass | ollama | gemma4:e4b | edges=1 |
