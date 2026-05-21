# Semantic Quality Evaluation

Generated: `2026-05-21T06:10:00+00:00`
Repo head: `7be78abf7ee65eaeb9554e09e8d5a7a8fab4c58b`
DB: `data/asip.db`
Eval set: `docs/qa/semantic-rerank-eval-set.jsonl`
Gate: `pass`

## Summary

- Total: 8
- Passed: 8
- Failed: 0
- Provider-vector cases: 2
- Graph-target cases: 1
- Mean reciprocal rank: 0.7643

## Cases

| Case | Status | Rows | First expected rank | Sources | Retrieval | Failures |
| --- | --- | ---: | ---: | --- | --- | --- |
| SQ01_DOC_SOURCE_TREE | pass | 24 | 1 | code, doc, pdf, register | fts5, lexical, provider-vector | - |
| SQ02_MANUAL_DRIVER_IMPL | pass | 24 | 10 | code, doc, pdf, register | fts5, lexical, provider-vector | - |
| SQ03_GCVM_EXACT | pass | 24 | 1 | code, register | fts5, lexical | - |
| SQ04_SDMA_EXACT | pass | 24 | 1 | code, doc, pdf, register | fts5, lexical | - |
| SQ05_MACRO_CHAIN | pass | 24 | 4 | code, doc, register | fts5, lexical | - |
| SQ06_SMN_PREFIX_EXACT | pass | 24 | 1 | code | fts5, lexical | - |
| SQ07_CP_HQD_FIELD_MASK_EXACT | pass | 24 | 1 | code, register | fts5, lexical | - |
| SQ08_CP_HQD_NL_WILDCARD_GRAPH | pass | 24 | - | code | graph-edge | - |

Boundary: This evaluates a labeled current-corpus semantic retrieval set. It does not claim quality across arbitrary future corpora.
