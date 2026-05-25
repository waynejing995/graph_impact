# Blackbox Ledger QA

- Status: pass
- DB: `/Volumes/data/User/wayne/Code/graph_impact/data/asip.db`
- Checks: 9/9 passed
- Batches: 1
- Attempts: 2
- Stored blackbox edges: 5
- Runtime visible blackbox edges: 5

## Checks
- pass: blackbox_job_present - latest job id=60
- pass: inventory_non_empty - inventory_total=19429
- pass: ledger_present - batch_count=1
- pass: ledger_completeness - attempted=2; terminal=2; statuses={'accepted': 2}
- pass: profile_edges_persisted - profile_edges=2
- pass: profile_table_persisted - profile_table_rows=2
- pass: content_validator_present - grounded=2; profile_table_rows=2; reasons={'repaired_legacy_evidence_refs': 2, 'repaired_empty_io_from_neighbors': 2}
- pass: blackbox_provenance_backrefs - checked_edges=5; failures=0
- pass: runtime_freshness_visible - visible=5; latest_stored=5; stale_filtered=3
