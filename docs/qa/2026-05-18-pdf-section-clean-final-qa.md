# 2026-05-18 Clean-Final PDF Section QA

## Scope

This QA closes the narrow G08 residual for browser/API proof that the clean-final
AMD corpus can expose a real PDF-derived `pdf_section` node with page
provenance.

Clean-final DB:

```text
data/asip.db
/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db
```

The two files were byte-identical before this QA.

## RED

Before this pass, clean-final DB evidence contained the reduced AMD PDF row and
page metadata, but query-scoped graph payloads did not carry the matching PDF
section node when persisted graph edges existed. G08 therefore still relied on
fixture-only `pdf_section` proof.

Failing regression:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_query_graph_keeps_pdf_section_node_from_matching_pdf_row_when_edges_exist -v

KeyError: 'docs/manual.pdf#page-3'
```

## GREEN

Implementation:

- query-scoped graph assembly now overlays doc/PDF section nodes derived only
  from the matched query rows;
- this does not scan the whole evidence table and does not require the global
  graph evidence-derived mode;
- section nodes keep BoxMatrix-style attributes, including source path and page.

Targeted tests:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_query_graph_keeps_pdf_section_node_from_matching_pdf_row_when_edges_exist \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_documentation_queries_preserve_matching_pdf_rows_before_candidate_cap -v

Ran 2 tests in 0.238s
OK
```

Full query-schema slice:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_query_schema -v

Ran 13 tests in 0.375s
OK
```

Web BFF/API test:

```text
pnpm --filter web exec playwright test tests/workbench-api.spec.ts -g "PDF section" --reporter=list

1 passed
```

## Clean-Final API Evidence

Command:

```text
curl 'http://127.0.0.1:3100/api/workbench/query?q=amdgpu%20documentation%20driver%20source%20tree%20PDF%20QA&sourceTypes=pdf'
```

Result:

```text
HTTP 200
rows=1
row source_types=pdf
graph nodes=1
graph node id=amdgpu-driver-source-tree.pdf#page-1
graph node kind=pdf_section
graph node attr.source[0].path=amdgpu-driver-source-tree.pdf
graph node attr.source[0].page=1
empty=false
```

The clean-final PDF evidence row is from corpus `amd-amdgpu-docs`, repo
`https://instinct.docs.amd.com/projects/amdgpu-docs/en/latest/`, path
`amdgpu-driver-source-tree.pdf`, page `1`.

## Browser QA

In-app browser route:

```text
http://127.0.0.1:3100/
```

UI interaction:

```text
Evidence Search
query: amdgpu documentation driver source tree PDF QA
source filters: PDF only
Run query
```

Observed DOM:

```text
Global weighted network graph:
  nodes 1
  edges 0
  pdf_section 1
  amdgpu-driver-source-tree.pdf page 1

Evidence table:
  AMD
  pdf
  mention
  0.95
  amdgpu-driver-source-tree.pdf page 1

Inspector:
  Source Location: pdf function amdgpu-driver-source-tree.pdf line 1 page 1
  Source Preview: Reduced AMD amdgpu Documentation Fixture ...
```

2K screenshot:

```text
docs/qa/browser/pdf-section-query-clean-final-3100-2k.png
```

## Residual

The reduced PDF fixture is intentionally small and contains generic PDF terms
such as `AMD`, `ASIP`, `GPU`, `PDF`, and `QA`. Those terms remain cited
evidence rather than graph endpoints, so the clean-final query-scoped PDF graph
shows a page section node without a section-to-register edge. Synthetic and
unit fixtures still cover `pdf_section -> register` edges when the PDF page
mentions a normalized register symbol.
