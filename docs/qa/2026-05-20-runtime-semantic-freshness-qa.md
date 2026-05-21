# ASIP Runtime Semantic Freshness QA

- Generated: `2026-05-20T12:09:23Z`
- Database: `data/asip.db`
- Current jobs: `latest_index_job_id=10`, `latest_graph_rebuild_job_id=13`, `latest_semantic_edges_job_id=18`, `latest_doc_nodes_job_id=20`
- Status: `pass`

## Results

| Check | Status | Evidence |
| --- | --- | --- |
| storage_runtime_stale_semantic_filter | `pass` | Storage graph runtime filters semantic rows whose provider job is older than the latest succeeded index or graph rebuild job. |
| storage_runtime_fresh_semantic_keep | `pass` | Fresh semantic rows from matching provider job 18 remain visible in global product graphs. |
| storage_runtime_fresh_doc_node_keep | `pass` | Fresh doc-node rows from matching doc_nodes_batch job 20 remain visible in global product graphs. |
| storage_runtime_extractor_job_kind_binding | `pass` | Runtime semantic graph rows must use a job kind compatible with their extractor, and semantic_edges/doc_nodes extractor rows without job provenance stay hidden. |
| storage_runtime_provider_mismatch_filter | `pass` | Semantic rows generated under previous provider settings are not exposed by runtime graph when current provider settings differ. |
| real_db_global_graph_semantic_leak_probe | `pass` | global_graph(data/asip.db, all_edges=True) returned 23029 runtime edges with stage counts {'deterministic': 23010, 'mixed': 16, 'semantic': 3}. |
| real_db_query_graph_semantic_leak_probe | `pass` | query_evidence(data/asip.db, 'GCVM_L2_CNTL ENABLE_L2_CACHE', limit=8) returned 8 rows and 0 query graph edges with stage counts {}. |

## Real DB Probe

- Global graph edges: `23029`; stage counts: `{'deterministic': 23010, 'mixed': 16, 'semantic': 3}`
- Query rows: `8`; query graph edges: `0`; stage counts: `{}`

## Completion Note

This artifact is rebound to current semantic_edges_batch job 18 and doc_nodes_batch job 20 after live provider batch hardening. Historical stale job 4/5 rows remain counted but are superseded by current fresh edges.
