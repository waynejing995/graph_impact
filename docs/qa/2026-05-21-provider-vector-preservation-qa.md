# Provider Vector Preservation QA

Generated: 2026-05-21

## Scope

This QA covers a hybrid-retrieval bug where provider-vector evidence could be computed but disappear from the final result set when high-confidence lexical/FTS rows filled the candidate window first.

This narrows the current ASIP semantic-rerank evidence boundary. It does not claim production semantic ranking quality across arbitrary future corpora.

## Fix

- `query_evidence()` now keeps evidence rows from provider-vector chunk matches in the candidate pool even when FTS chunks already fill the candidate limit.
- Final diverse row selection now preserves a representative `provider-vector` row when one exists, alongside source-type diversity.
- Exact symbol queries still skip provider-vector search, so register/wildcard queries are not pushed into semantic rerank when the exact path is safer.

## Verification

- `PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_query_evidence_keeps_provider_vector_row_when_lexical_chunks_fill_candidates -v`
  - Result: pass.
- `PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_workbench_query_schema -v`
  - Result: `Ran 24 tests`, OK.
- AQ05 six-surface probe:
  - Artifact: `docs/qa/2026-05-21-acceptance-aq05-provider-vector-preservation.json`
  - Gate: pass.
  - Surfaces: CLI, API, API_LIVE, Web, MCP, MCP_PROTOCOL.
  - Rows: 24.
  - Source types: code, doc, pdf, register.
  - Retrieval sources: fts5, lexical, provider-vector.
  - Provider gate details in the same artifact: `147841 / 147841` provider embeddings, zero fallback embeddings, live embedding smoke pass, semantic/doc-node provenance pass.

## Current Boundary

The fix proves provider-vector participation can survive lexical candidate pressure in unit coverage and in the real AQ05 multi-surface path. Broad production semantic-ranking quality still needs either a larger labeled semantic-quality evaluation set or explicit residual acceptance.
