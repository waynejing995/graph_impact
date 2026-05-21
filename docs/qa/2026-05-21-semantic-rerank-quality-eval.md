# Semantic Rerank Quality Evaluation

- Generated: `2026-05-21T04:10:30+00:00`
- Repo head: `cab672d6062a5df0916c804ac6f86fc5164f1950`
- Gate: `partial`
- DB: `/Volumes/data/User/wayne/Code/graph_impact/data/asip.db`

This evaluates current default-DB provider-vector coverage and AQ quality proxy evidence. It does not claim hosted production semantic ranking quality across arbitrary future corpora.

## Checks

| Check | Status | Evidence |
| --- | --- | --- |
| `full_provider_embedding_coverage` | `pass` | total_chunks=147841; provider_embeddings=147841; missing_embedding_chunks=0 |
| `aq01_aq09_live_acceptance_quality_proxy` | `pass` | queries_passed=9; queries=9 |
| `provider_vector_participation` | `partial` | queries_with_provider_vector=['AQ05'] |

## AQ Query Coverage

| Query | Status | Sources | Rows | Graph |
| --- | --- | --- | --- | --- |
| `AQ01` | `pass` | fts5, lexical | 24 | 31n/91e |
| `AQ02` | `pass` | fts5, lexical | 24 | 32n/91e |
| `AQ03` | `pass` | fts5, lexical | 24 | 92n/314e |
| `AQ04` | `pass` | fts5, lexical | 24 | 73n/83e |
| `AQ05` | `pass` | fts5, lexical, provider-vector | 24 | 2n/0e |
| `AQ06` | `pass` | fts5, lexical | 24 | 32n/91e |
| `AQ07` | `pass` | fts5, lexical | 24 | 2n/0e |
| `AQ08` | `pass` | fts5, lexical | 24 | 1n/0e |
| `AQ09` | `pass` | fts5, lexical | 24 | 2n/0e |
