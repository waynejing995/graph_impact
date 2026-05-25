# Blackbox Ledger QA

- Status: pass
- DB: `/Volumes/data/User/wayne/Code/graph_impact/data/asip.db`
- Checks: 16/16 passed
- Manifest group: `0ac696a5cf83714327f5fe54a8de066d5d27c67069e17ee97509ddec1601af8b`
- Manifest shards: 1/1
- Manifest jobs: [68]
- Batches: 1
- Attempts: 1
- Stored blackbox edges: 3
- Runtime visible blackbox edges: 3

## Checks
- pass: blackbox_job_present - latest job id=68
- pass: inventory_non_empty - inventory_total=19429
- pass: ledger_present - batch_count=1
- pass: entity_manifest_present - manifest_rows=1
- pass: entity_candidate_terminal_status - candidates=1; terminal=1; statuses={'accepted': 1}
- pass: entity_provider_response_present - provider_responses=3
- pass: entity_io_facts_present - io_facts=4; profile_table_rows=1
- pass: manifest_group_present - group=0ac696a5cf83714327f5fe54a8de066d5d27c67069e17ee97509ddec1601af8b; latest_job=68
- pass: manifest_group_shard_coverage - observed_shards=1; expected_shards=1
- pass: manifest_group_ledger_completeness - attempted=1; terminal=1
- pass: ledger_completeness - attempted=1; terminal=1; statuses={'accepted': 1}
- pass: profile_edges_persisted - profile_edges=1
- pass: profile_table_persisted - profile_table_rows=1
- pass: content_validator_present - grounded=1; profile_table_rows=1; reasons={'accepted_grounded': 1}
- pass: blackbox_provenance_backrefs - checked_edges=3; failures=0
- pass: runtime_freshness_visible - visible=3; latest_stored=3; stale_filtered=3
