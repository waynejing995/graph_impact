# ASIP Current Completion Gate

- Generated: `2026-05-21T06:45:42+00:00`
- Database: `data/asip.db`
- Gate status: `blocked`

## Summary

- Requirements: `17/20` passed, `3` blocked, `0` failed, `0` missing.

## Requirements

| Requirement | Status | Evidence |
| --- | --- | --- |
| `real_index_db` | `pass` | quick_check=ok; documents=1224, chunks=147841, evidence=5299434, edges=32368, linux_asic_reg_documents=476 |
| `artifact_binding` | `pass` | 9/9 required artifacts loaded; 4/4 DB/job-bound artifacts checked |
| `stage1_deterministic_graph` | `pass` | edges=32368; latest_graph_rebuild_job_id=44; latest_index_job_id=10 |
| `product_graph_schema` | `pass` | 18 acceptance query schema records checked |
| `cli_api_mcp_surfaces` | `pass` | 9 queries checked for CLI, API, MCP |
| `api_live_surface` | `pass` | 9 API_LIVE surface query records checked |
| `mcp_protocol_surface` | `pass` | 9 MCP_PROTOCOL surface query records checked |
| `web_surface` | `pass` | 9 Web surface query records checked |
| `acceptance_gate` | `pass` | gate_status=pass; passed=9/9; query_ids=AQ01,AQ02,AQ03,AQ04,AQ05,AQ06,AQ07,AQ08,AQ09 |
| `provider_live_gate` | `pass` | gate_status=pass; checks=5 |
| `stage2_semantic_edges` | `pass` | semantic_edge_provenance=pass; doc_node_provenance=pass; semantic_edge=pass |
| `runtime_semantic_freshness` | `pass` | gate_status=pass; checks=7/7 |
| `semantic_quality` | `pass` | gate_status=pass; passed=8/8; provider_vector_cases=2; graph_target_cases=1; mrr=0.7643 |
| `callback_edge_audit` | `pass` | gate_status=pass; callback_edges=4601; parser_pollution=0; unexplained_ambiguous=0; real_oracles=7/7 |
| `hosted_openai_compatible` | `blocked` | gate_status=blocked; credential_mode=hosted-missing-credential; checks=0/0 |
| `browser_e2e` | `pass` | browser gate_status=pass; e2e_status=pass; in-app gate_status=pass; e2e_status=missing |
| `web_no_server_smoke` | `pass` | gate_status=pass; checks=9/9 |
| `performance_smoke` | `pass` | deterministic_counts_match=True; all_queries_under_threshold=True; queries=5 |
| `residual_acceptance` | `blocked` | gate_status=blocked; accepted_residuals=0 |
| `git_gate` | `blocked` | diff_check=pass; worktree_status=dirty; committed=False; pushed=True; artifact_head=47eece938b77; current_head=47eece938b77; artifact_branch=main; current_branch=main; current_w... |

## Blocking Reasons

- hosted_openai_compatible: gate_status=blocked
- hosted_openai_compatible: credential env var is missing: OPENAI_API_KEY
- hosted_openai_compatible: credential_mode=hosted-missing-credential does not satisfy hosted-credentialed
- hosted_openai_compatible: summary total=0 is below required hosted check count 2
- hosted_openai_compatible: hosted OpenAI-compatible checks are missing
- hosted_openai_compatible: openai_compatible_embeddings_live: check is missing
- hosted_openai_compatible: openai_compatible_chat_completions_live: check is missing
- residual_acceptance: gate_status=blocked
- residual_acceptance: residual document status remains open: Status: Partial; deferral ledger exists, final user acceptance of residual boundaries remains blocking
- residual_acceptance: explicit user acceptance has not been recorded
- residual_acceptance: accepted is not true
- residual_acceptance: accepted_residuals is empty
- git_gate: gate_status=blocked
- git_gate: worktree has 11 changed/untracked paths
- git_gate: worktree_status=dirty
- git_gate: committed is not true
- git_gate: current worktree has 11 changed/untracked paths
