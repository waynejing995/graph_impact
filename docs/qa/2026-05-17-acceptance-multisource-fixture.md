# ASIP Acceptance Query Run

Generated: 2026-05-16T21:20:13+00:00
DB: `/tmp/asip-multisource-clean-2026-05-17.db`
Surfaces checked: CLI, API, Web, MCP

## Summary

- Total: 2
- Passed: 2
- Partial: 0
- Failed: 0

## Database Health

- Status: pass
- Failure reasons: -

## Queries

| ID | Status | Rows | Source types | Graph | Missing surfaces | Failure reasons | Query |
| --- | --- | ---: | --- | ---: | --- | --- | --- |
| AQ05 | pass | 24 | code, doc, pdf, register | 2 nodes / 1 edges | - | - | Show evidence connecting amdgpu documentation to the amdgpu driver source tree. |
| AQ06 | pass | 16 | code, register | 2 nodes / 1 edges | - | - | Given WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp), explain the resolved register entity and macro expansion chain. |
