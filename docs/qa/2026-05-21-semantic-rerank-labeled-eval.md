# Semantic Quality Evaluation

Generated: `2026-05-21T04:45:26+00:00`
Repo head: `6d127fa9fc90f17814a1e63952ef7362133c0ef7`
DB: `data/asip.db`
Eval set: `docs/qa/semantic-rerank-eval-set.jsonl`
Gate: `pass`

## Summary

- Total: 5
- Passed: 5
- Failed: 0
- Provider-vector cases: 2
- Mean reciprocal rank: 0.67

## Cases

| Case | Status | Rows | First expected rank | Sources | Retrieval | Failures |
| --- | --- | ---: | ---: | --- | --- | --- |
| SQ01_DOC_SOURCE_TREE | pass | 24 | 1 | code, doc, pdf, register | fts5, lexical, provider-vector | - |
| SQ02_MANUAL_DRIVER_IMPL | pass | 24 | 10 | code, doc, pdf, register | fts5, lexical, provider-vector | - |
| SQ03_GCVM_EXACT | pass | 24 | 1 | code, register | fts5, lexical | - |
| SQ04_SDMA_EXACT | pass | 24 | 1 | code, doc, pdf, register | fts5, lexical | - |
| SQ05_MACRO_CHAIN | pass | 24 | 4 | code, doc, register | fts5, lexical | - |

Boundary: This evaluates a labeled current-corpus semantic retrieval set. It does not claim quality across arbitrary future corpora.
