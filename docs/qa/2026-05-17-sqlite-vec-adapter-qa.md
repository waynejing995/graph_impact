# SQLite Vec Adapter QA

Date: 2026-05-17
Scope: G09 native sqlite-vec retrieval adapter and fallback vector runtime.

## What Changed

`AsipStore.search_vector()` now keeps `embeddings.vector_json` as durable
source of truth, then:

- tries a temporary sqlite-vec `vec0` table when the Python/SQLite runtime can
  load `sqlite_vec`,
- returns `retrieval_runtime=sqlite-vec` and native `distance` for that path,
- falls back to JSON + Python cosine with `retrieval_runtime=python-cosine`
  when sqlite-vec is unavailable,
- lets `query_evidence()` surface `vector_runtime` on vector-backed rows.

This is a product adapter path, not only an isolated extension smoke. A
persistent sqlite-vec sidecar remains future performance work.

## RED/GREEN

Native adapter RED in bundled Python before implementation:

```bash
PYTHONPATH=packages/core/src:packages/core/tests:. \
  /Users/chenjingwen/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m unittest \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_search_vector_uses_sqlite_vec_when_runtime_supports_extensions -v
```

Failure:

```text
KeyError: 'retrieval_runtime'
```

GREEN after implementation:

```text
test_search_vector_uses_sqlite_vec_when_runtime_supports_extensions ... ok
```

Fallback/product query runtime RED before implementation:

```bash
PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_query_evidence_merges_vector_backed_evidence_without_lexical_overlap -v
```

Failure:

```text
AssertionError: None not found in {'sqlite-vec', 'python-cosine'}
```

GREEN after implementation:

```text
test_query_evidence_merges_vector_backed_evidence_without_lexical_overlap ... ok
```

## Verification

Targeted checks:

```bash
PYTHONPATH=packages/core/src:packages/core/tests:. \
  /Users/chenjingwen/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m unittest \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_search_vector_uses_sqlite_vec_when_runtime_supports_extensions \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_embedding_vectors_are_queryable_with_sqlite_backed_fallback -v
```

Result: 2 passed.

System Python fallback/product query checks:

```bash
PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_embedding_vectors_are_queryable_with_sqlite_backed_fallback \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_query_evidence_merges_vector_backed_evidence_without_lexical_overlap -v
```

Result: 2 passed.

Full core regression:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v
```

Result: 166 passed, 1 sqlite-vec extension skip in system Python.

## Remaining Risk

The native adapter builds a temporary vec table per query from JSON vectors.
That proves product-path sqlite-vec usage without making the extension a hard
DB dependency. A persistent table-per-dimension sidecar can be added later for
large-scale speed, with reset/delete cleanup tests.

Query embeddings still use the deterministic fallback vector unless provider
query-embedding/rerank work is enabled. Full provider-vector semantic quality
remains a separate G06/G09 boundary.
