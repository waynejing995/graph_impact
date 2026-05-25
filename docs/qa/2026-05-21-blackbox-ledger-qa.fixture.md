# Blackbox Ledger QA

- Status: pass
- DB: `/tmp/asip-blackbox-ledger-fixture/fixture.db`
- Checks: 7/7 passed
- Batches: 1
- Attempts: 2
- Stored blackbox edges: 2
- Runtime visible blackbox edges: 2

## Checks
- pass: blackbox_job_present - latest job id=1
- pass: inventory_non_empty - inventory_total=4
- pass: ledger_present - batch_count=1
- pass: ledger_completeness - attempted=2; terminal=2; statuses={'accepted': 1, 'rejected': 1}
- pass: profile_edges_persisted - profile_edges=1
- pass: blackbox_provenance_backrefs - checked_edges=2; failures=0
- pass: runtime_freshness_visible - visible=2; stored=2
