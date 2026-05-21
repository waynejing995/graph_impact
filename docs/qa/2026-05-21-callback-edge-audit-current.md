# Callback Edge Audit Current

- Artifact: `docs/qa/2026-05-21-callback-edge-audit-current.json`
- Source: `asip.callback_edge_audit`
- Database: `data/asip.db`
- Gate status: `pass`

## Summary

- Callback/vtable edges: `4601`
- Ambiguous callback edges: `4530`
- Explained dynamic dispatch edges: `4530`
- Unexplained ambiguous callback edges: `0`
- Parser pollution candidates: `0`

## Notes

The strict audit is run with `--assert-no-parser-pollution` and
`--max-ambiguous-fanout 2`. The previously suspicious `aca_bank_parser` and
`aca_bank_is_valid` fanout is now classified as typed `aca_bank_ops` dynamic
dispatch rather than unexplained parser overlinking.
