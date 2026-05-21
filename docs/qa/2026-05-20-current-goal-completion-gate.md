# ASIP Current Completion Gate

- Generated: `2026-05-20T14:44:18+00:00`
- Database: `data/asip.db`
- Gate status: `blocked`

## Summary

- Requirements: `10/15` passed, `5` blocked, `0` failed, `0` missing.

## Requirements

| Requirement | Status | Evidence |
| --- | --- | --- |
| `real_index_db` | `pass` | quick_check=ok; documents=1224, chunks=147841, evidence=5299434, edges=39395, linux_asic_reg_documents=476 |
| `artifact_binding` | `pass` | 9/9 required artifacts loaded; 4/4 DB/job-bound artifacts checked |
| `stage1_deterministic_graph` | `pass` | edges=39395; latest_graph_rebuild_job_id=13; latest_index_job_id=10 |
| `product_graph_schema` | `pass` | 18 acceptance query schema records checked |
| `cli_api_mcp_surfaces` | `pass` | 9 queries checked for CLI, API, MCP |
| `web_surface` | `blocked` | 9 Web surface query records checked |
| `acceptance_gate` | `blocked` | gate_status=blocked; passed=0/9; query_ids=AQ01,AQ02,AQ03,AQ04,AQ05,AQ06,AQ07,AQ08,AQ09 |
| `provider_live_gate` | `blocked` | gate_status=blocked; checks=5 |
| `stage2_semantic_edges` | `pass` | semantic_edge_provenance=pass; doc_node_provenance=pass; semantic_edge=pass |
| `runtime_semantic_freshness` | `pass` | gate_status=pass; checks=7/7 |
| `browser_e2e` | `pass` | browser gate_status=pass; e2e_status=pass; in-app gate_status=pass; e2e_status=missing |
| `web_no_server_smoke` | `pass` | gate_status=pass; checks=9/9 |
| `performance_smoke` | `pass` | deterministic_counts_match=True; all_queries_under_threshold=True; queries=5 |
| `residual_acceptance` | `blocked` | gate_status=blocked; accepted_residuals=0 |
| `git_gate` | `blocked` | diff_check=pass; worktree_status=dirty; committed=False; pushed=False |

## Blocking Reasons

- web_surface: web acceptance gate_status=blocked; summary passed=8/9 failed=1
- web_surface: AQ09: web acceptance query status=fail: embedding provider check failed: provider embedding provenance exists but 125962 deterministic fallback embeddings remain; 18299/144261 embeddings match the configured provider; 3580 chunks have no embeddings; 144261/147841 chunks have embeddings
- acceptance_gate: AQ09 provider check embedding=partial (provider embedding provenance exists but 125962 deterministic fallback embeddings remain; 18299/144261 embeddings match the configured provider; 3580 chunks have no embeddings; 144261/147841 chunks have embeddings)
- provider_live_gate: embedding: partial (provider embedding provenance exists but 125962 deterministic fallback embeddings remain; 18299/144261 embeddings match the configured provider; 3580 chunks have no embeddings; 144261/147841 chunks have embeddings)
- residual_acceptance: gate_status=blocked
- residual_acceptance: residual document status remains open: Status: Partial; deferral ledger exists, final user acceptance of residual boundaries remains blocking
- residual_acceptance: explicit user acceptance has not been recorded
- residual_acceptance: accepted is not true
- residual_acceptance: accepted_residuals is empty
- git_gate: gate_status=blocked
- git_gate: worktree has 144 changed/untracked paths
- git_gate: branch has no upstream tracking branch
- git_gate: worktree_status=dirty
- git_gate: committed is not true
- git_gate: pushed is not true
