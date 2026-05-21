# Product Graph Schema And DB Path E2E QA

Date: 2026-05-19
Status: Targeted pass for the current closure slice; not a full completion claim.

## Scope

This QA record covers the 2026-05-19 product graph schema slice:

- default product graph nodes are limited to `function`, `register`, and `doc`;
- legacy document subtypes are projected to `kind = doc` and preserved in
  `attr.doc_kind`;
- `/graph?dbPath=...` and `/?q=...&dbPath=...` pass the explicit SQLite DB
  path through graph and query requests instead of silently using a mock or
  stale default DB;
- semantic-edge graph actions also carry the same explicit DB path when present.
- the current clean AMD/gemma4 artifact still satisfies the product graph
  projection: Web/API product output exposes only `function`, `register`, and
  `doc` nodes, while document subtypes remain in `attr.doc_kind`.

The broader two-stage ASIP graph remains governed by
`docs/specs/2026-05-19-asip-graph-integration-plan.md`.

## Implementation Evidence

- `packages/core/src/asip/storage.py` now projects document graph nodes to
  `kind = doc` with `attr.doc_kind` values:
  `markdown_section`, `pdf_section`, or `boxmatrix_box`.
- `apps/web/components/workbench-page.tsx` gates initial graph/query work until
  URL `dbPath` has been initialized, then passes it to
  `/api/workbench/graph`, `/api/workbench/query`, and
  `/api/workbench/semantic-edges`.
- `apps/web/components/workbench-page.tsx` keeps a compatibility sanitizer for
  old document subtype payloads, but the backend tests assert the raw product
  graph contract directly.
- `apps/web/tests/workbench-smoke.spec.ts` adds a no-mock SQLite-backed e2e that
  seeds a real temporary DB, opens `/graph?dbPath=...`, verifies graph API and
  query API request URLs include that DB path, checks nonzero graph data, and
  asserts visible node kinds are only `function`, `register`, and `doc`.
- The same e2e records every graph/query request during the scenario and fails
  if any request falls back to the default DB by omitting the target `dbPath`.
- `apps/web/tests/workbench-smoke.spec.ts` also covers `/?q=...&dbPath=...` so
  the initial evidence query path cannot run before URL DB-path initialization.
- `apps/web/tests/workbench-smoke.spec.ts` now also covers all three graph-side
  semantic actions with a URL DB path: query-scoped semantic edges, batch
  semantic edges, and LLM document-node extraction. Each test fails if the
  action POST body omits or changes the explicit `dbPath`.

## Current Clean Artifact Audit

Database: `/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db`

Current-code product graph audit:

```text
global_graph(limit=20000)
nodes=14578
edges=20000
node kinds: doc=7, function=13878, register=693
doc kinds: boxmatrix_box=6, markdown_section=1
bad visible node kinds: 0
visible macro/wrapper/provider/tmp nodes: 0
concept functions without resolver profile: 0
semantic edges in sample: 11
```

Clean artifact table/job audit:

```text
documents=124
chunks=21884
evidence=860516
edges=41893
embeddings=32

edge stages:
  deterministic / clang_text_spans = 34987
  deterministic / clang_callback = 6084
  deterministic / text_fallback = 775
  semantic / ollama = 25
  evidence / query_expected_terms = 22

jobs:
  doc_nodes_batch succeeded
  embedding_backfill embedded
  graph_rebuild succeeded
  index indexed
  semantic_edges_batch succeeded
```

Acceptance rerun with current code:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m asip.cli acceptance \
  --db /tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db \
  --output-json docs/qa/2026-05-19-acceptance-clean-amd-current.json \
  --output-md docs/qa/2026-05-19-acceptance-clean-amd-current.md \
  --surface CLI --surface API --surface Web --surface MCP --full
```

Result: AQ01-AQ09 `9/9`, provider edge `Ollama/gemma4:e4b`,
embedding `Ollama/nomic-embed-text:latest`.

## Test Evidence

Natural-language register wildcard query regression:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests \
  python3 -m unittest \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_natural_language_register_wildcard_query_uses_symbol_prefix_not_regs_noise \
  -v
```

Result: `Ran 1 test`, `OK`.

This protects the user-reported query
`who will write/read CP_HQD_* regs`. The query parser now treats `CP_HQD_*` as
a symbol prefix and `write/read` as access intent. The result rows are derived
from Stage 1 graph edges, include `target_symbol`, and reject unrelated
`REGS`-like noise such as `CPM_CONTROL__REFCLK_REGS_GATE_ENABLE_MASK`.

Current `data/asip.db` live check:

```text
query="who will write/read CP_HQD_* regs"
empty=False
rows=24
graph_nodes=164
graph_edges=552
relations={'reads': 81, 'writes': 275, 'sets_field': 42, 'maps_base': 29, 'calls': 125}
first rows:
  gfx_deactivate_hqd -> CP_HQD_ACTIVE reads drivers/gpu/drm/amd/amdgpu/gfx_v8_0.c:4369
  gfx_deactivate_hqd -> CP_HQD_DEQUEUE_REQUEST writes drivers/gpu/drm/amd/amdgpu/gfx_v8_0.c:4370
  gfx_deactivate_hqd -> CP_HQD_PQ_RPTR writes drivers/gpu/drm/amd/amdgpu/gfx_v8_0.c:4380
  gfx_deactivate_hqd -> CP_HQD_PQ_WPTR writes drivers/gpu/drm/amd/amdgpu/gfx_v8_0.c:4381
```

Web/API URL-query regression:

```text
PLAYWRIGHT_SKIP_WEB_SERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:3114 \
  pnpm --dir apps/web exec playwright test \
  tests/workbench-api.spec.ts -g "natural language register wildcards"

PLAYWRIGHT_SKIP_WEB_SERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:3114 \
  pnpm --dir apps/web exec playwright test \
  tests/workbench-smoke.spec.ts -g "initial URL query"
```

Results: API `1 passed`; Web smoke `1 passed`.

In-app browser evidence at 2048 x 1280:

- `docs/qa/browser/asip-cp-hqd-nl-query-2026-05-19-3114.png`
- `docs/qa/browser/asip-cp-hqd-nl-query-2026-05-19-3114-snapshot.md`
- `docs/qa/browser/asip-cp-hqd-nl-query-table-2026-05-19-3114-snapshot.md`

The browser table shows graph-derived rows such as
`gfx_deactivate_hqd -> CP_HQD_ACTIVE`, `gfx_deactivate_hqd ->
CP_HQD_DEQUEUE_REQUEST`, and `gfx_kiq_fini_register -> CP_HQD_IB_CONTROL`.

Callback/vtable dispatch provenance regression:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests \
  python3 -m unittest \
  packages.core.tests.test_code_graph \
  packages.core.tests.test_storage_graph \
  packages.core.tests.test_workbench_query_schema \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_generic_common_dispatch_to_multiple_callbacks \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_keeps_dispatch_kind_for_ambiguous_single_slot_match \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_stage1_specific_vtable_call_does_not_connect_every_same_named_slot \
  -v
```

Result: `Ran 117 tests`, `OK (skipped=2)`; skips are optional
`sqlite-vec` extension checks on this Python runtime.

This guards the dispatch provenance added after the vtable review: generic
multi-callback dispatch edges are marked `dispatch=ambiguous`,
`call_kind=vtable_dispatch`, and carry `callback_candidate_count` in product
graph edge attributes instead of looking like exact direct calls.

Product graph schema module:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
  python3 -m unittest packages.core.tests.test_graph_schema -v
```

RED result before the fix: `ModuleNotFoundError: No module named
'asip.graph_schema'`.

GREEN result after adding `packages/core/src/asip/graph_schema.py`:
`Ran 3 tests`, `OK`.

`packages/core/src/asip/acceptance.py` now imports the shared product node kind
and relation enum from `asip.graph_schema` for surface graph contract checks.
The 2026-05-19 continuation also moved storage relation projection, semantic
edge prompts, and workbench semantic-edge persistence onto that shared relation
schema. `macro` evidence is no longer projected as a register node; field
endpoints may still appear in raw `sets_field` semantic edges so they can fold
into register attributes, but they are not product graph nodes.

Product Graph V2 schema regression:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  packages.core.tests.test_semantic_edges.SemanticEdgeFeatureTests.test_edge_prompt_uses_product_relation_enum \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_global_graph_relation_normalization_uses_shared_schema \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_evidence_macro_symbols_do_not_become_register_product_nodes \
  -v
```

RED result before the fix:

- semantic prompt still contained `checks_mask`, `assigns_doorbell`, and
  `waits_for`;
- `asip.storage` had no `normalize_product_relation` integration point;
- evidence `entity_type=macro` produced a visible `MACRO_HELPER` register node.

GREEN result after the fix: `Ran 3 tests`, `OK`.

Semantic/workbench persistence regression:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_generated_semantic_edges_persist_product_relation_enum \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_batch_semantic_edge_job_generates_edges_from_indexed_candidates \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_llm_doc_node_job_extracts_boxmatrix_style_doc_boxes \
  -v
```

Result: `Ran 3 tests`, `OK`. This proves raw LLM `checks_mask` is persisted as
`relates_to` with `original_relation=checks_mask`, `wraps` is dropped, field
terms can still support `sets_field`, and doc-node extraction does not promote
field-only `documents_field` relationships into product graph nodes.

Acceptance surface probe implementation, current tree:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  packages.core.tests.test_acceptance_runner.AcceptanceRunnerTests.test_runner_records_real_surface_probe_results \
  -v
```

RED result before the fix: `KeyError: 'surface_results'`.

GREEN result after the fix: `Ran 1 test`, `OK`.

The runner now records per-query `surface_results`:

- `CLI` / `core` uses `core.query_evidence`;
- `API` uses FastAPI `TestClient` against the real `/query` route, transport
  `fastapi.testclient.query`;
- `MCP` uses the registered MCP product tool function and records transport
  `mcp.tool-direct.search_evidence` plus `server_registered=true`; this is
  honest tool-surface coverage, not an MCP protocol-client smoke because the
  current Python runtime does not have the optional `mcp` package installed;
- `Web` uses `ASIP_WEB_BASE_URL` with the Next BFF query route when
  configured; otherwise it records `not_configured` and does not count as a
  surface pass.

Follow-up P1 regression:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  packages.core.tests.test_acceptance_runner.AcceptanceRunnerTests.test_runner_records_real_surface_probe_results \
  packages.core.tests.test_acceptance_runner.AcceptanceRunnerTests.test_runner_marks_web_surface_not_configured_without_base_url \
  -v
```

Result: `Ran 2 tests`, `OK`. The second test proves that selecting Web without
`ASIP_WEB_BASE_URL` fails truthfully with `not_configured` instead of silently
counting Web as passed. The UI default runner now selects `CLI`, `API`, and
`MCP`; Web must be selected intentionally or configured through the environment.

Broader acceptance/API/MCP regression:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest packages.core.tests.test_acceptance_runner -v
```

Result before the P1 review fix: `Ran 11 tests`, `OK`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  apps.api.tests.test_app.ApiAppTests.test_acceptance_run_endpoint_executes_single_query_for_api_and_mcp_surfaces \
  apps.mcp.tests.test_tools.McpToolsTests.test_run_acceptance_executes_single_query_for_mcp_surface \
  -v
```

Result: `Ran 2 tests`, `OK`.

Combined P1 follow-up sweep:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  packages.core.tests.test_acceptance_runner \
  apps.api.tests.test_app.ApiAppTests.test_acceptance_run_endpoint_executes_single_query_for_api_and_mcp_surfaces \
  apps.mcp.tests.test_tools.McpToolsTests.test_run_acceptance_executes_single_query_for_mcp_surface \
  -v
```

Result after the P1 review fixes: `Ran 14 tests`, `OK`.

Schema plus acceptance combined sweep:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  packages.core.tests.test_graph_schema \
  packages.core.tests.test_acceptance_runner \
  -v
```

Result: `Ran 15 tests`, `OK`.

Core graph/workbench schema sweep:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  packages.core.tests.test_graph_schema \
  packages.core.tests.test_storage_graph \
  packages.core.tests.test_semantic_edges \
  packages.core.tests.test_workbench_live \
  -v
```

Result: `Ran 155 tests`, `OK`, with `2` optional sqlite-vec extension skips.

Acceptance/API/MCP regression after the schema continuation:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  packages.core.tests.test_acceptance_runner \
  apps.api.tests.test_app.ApiAppTests.test_acceptance_run_endpoint_executes_single_query_for_api_and_mcp_surfaces \
  apps.mcp.tests.test_tools.McpToolsTests.test_run_acceptance_executes_single_query_for_mcp_surface \
  -v
```

Result: `Ran 14 tests`, `OK`.

```text
pnpm --filter web exec tsc --noEmit
```

Result: passed.

```text
git diff --check
```

Result: passed.

Web e2e/browser note for this continuation: earlier headless Playwright attempts
failed in this environment with `listen EPERM` on a fresh server port and
`bootstrap_check_in ... Permission denied` while launching Chromium. Those are
not counted as Web e2e passes. A later in-app browser run used a clean Next.js
dev server on `http://localhost:3111/graph` after detecting that the old 3100
server returned zero bytes and had a hot `next-server` process.

Default DB/API evidence at the time of the browser run:

```text
data/asip.db size=997M
corpora=5
documents=124
chunks=21884
evidence=860516
edges=41942
GET /api/workbench/graph?limit=5 returned product graph JSON with doc nodes.
```

In-app browser QA at 2048 x 1280:

- URL: `http://localhost:3111/graph`
- status header: `Edge: Ollama / gemma4:e4b`, `Index: ready`
- metrics: `graph edges: 3000`
- graph layer summary: `deterministic: 2989`, `semantic: 11`
- graph controls visible: function view, loaded edge budget, minimum edge
  weight, visible node budget, visible edge budget
- visible summary: `nodes 1000`, `edges 1245`, `shared registers 149`,
  `doc 7`, `function 696`, `register 297`
- console: React DevTools/Fast Refresh dev messages only; no runtime exception
  was observed in the captured console log.

Screenshots:

- `docs/qa/browser/asip-graph-schema-v2-2026-05-19-2k.png` captures the first
  reachable page state.
- `docs/qa/browser/asip-graph-schema-v2-loaded-2026-05-19-2k.png` captures the
  loaded graph state with real graph metrics.

This is a real browser reachability and default-DB graph smoke for the schema
continuation. It still is not the final no-mock DB-path Playwright gate because
the page was opened against the default `data/asip.db`, not an isolated
`/graph?dbPath=...` fixture.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  packages.core.tests.test_storage_graph \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_global_graph_creates_document_section_nodes_from_indexed_chunks \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_global_graph_exposes_pdf_section_node_provenance \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_batch_semantic_edge_job_promotes_doc_section_nodes_into_default_global_graph \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_llm_doc_node_job_extracts_boxmatrix_style_doc_boxes \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_query_graph_keeps_pdf_section_node_from_matching_pdf_row_when_edges_exist \
  -v
```

Result: `Ran 46 tests`, `OK`, with `2` optional sqlite-vec skips.

```text
pnpm --filter web exec tsc --noEmit
```

Result: passed.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  packages.core.tests.test_storage_graph \
  packages.core.tests.test_workbench_query_schema \
  packages.core.tests.test_workbench_backend_state \
  -v
```

Result: `Ran 87 tests`, `OK`, with `2` optional sqlite-vec extension skips.

```text
pnpm --filter web exec playwright test apps/web/tests/workbench-api.spec.ts \
  --grep "PDF section|semantic edges API supports batch generation|semantic edges API supports LLM document node extraction|corpus API indexes" \
  --reporter=list
```

Result: `4 passed`.

```text
pnpm --filter web exec playwright test apps/web/tests/workbench-smoke.spec.ts \
  --grep "corpus page adds indexes|graph page runs batch semantic|graph page runs LLM document|URL dbPath|initial query uses URL dbPath" \
  --reporter=list
```

Result: `5 passed`.

```text
pnpm --filter web exec playwright test apps/web/tests/workbench-smoke.spec.ts \
  --grep "graph page runs (semantic edge generation|batch semantic edge generation|LLM document node extraction)" \
  --reporter=list
```

Result: `3 passed`. This is the regression lock for semantic/doc-node action
`dbPath` propagation.

2026-05-19 continuation: the DB-path semantic action now has an explicit
no-mock browser gate. The test opens `/graph?dbPath=<isolated sqlite>`, clicks
`Generate batch semantic edges`, lets the real Next route call the real ASIP
CLI/core path, uses only a local fake Ollama HTTP server for the external model
call, and then queries the real graph API with `limit=all` to prove a persisted
`stage=semantic` `documents` edge appears in the graph.

```text
PLAYWRIGHT_SKIP_WEB_SERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:3111 \
  pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts \
  --grep "graph page runs no-mock batch semantic edge generation against a supplied DB" \
  --reporter=list
```

Result: `1 passed`.

The related Settings AQ09 user-supplied DB path gate also passes after aligning
AQ09 required surfaces with the runner default `CLI/API/MCP`; Web remains
covered by the browser action itself instead of being counted as a hidden
runner surface.

```text
PLAYWRIGHT_SKIP_WEB_SERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:3111 \
  pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts \
  --grep "graph page runs (batch semantic edge generation through the workbench API|no-mock batch semantic edge generation against a supplied DB)|settings page can run AQ09 against a user supplied DB" \
  --reporter=list
```

Result: `3 passed`.

```text
pnpm --filter web exec playwright test apps/web/tests/workbench-api.spec.ts \
  apps/web/tests/workbench-smoke.spec.ts --reporter=list
```

Result: `82 passed`.

```text
pnpm --filter web exec playwright test apps/web/tests/visual-anchor-routes.spec.ts \
  --reporter=list
```

Result: `15 passed`.

2026-05-19 continuation: natural-language register wildcard queries now have
both core and Web BFF regression coverage. The bug was that
`who will write/read CP_HQD_* regs` lost the wildcard intent, kept `regs` as a
ranking token, and could return unrelated `...REGS...` symbols while failing
to seed read/write graph edges. The fix preserves wildcard symbol prefixes,
filters matching rows by that prefix, keeps read/write as access intent, and
recognizes `CP_HQD_` registers as graphable register endpoints.

```text
PYTHONPATH=packages/core/src:packages/core/tests \
  python3 -m unittest \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_natural_language_register_wildcard_query_uses_symbol_prefix_not_regs_noise \
  -v
```

Result: `Ran 1 test`, `OK`.

```text
pnpm --filter web exec playwright test tests/workbench-api.spec.ts \
  -g "natural language register wildcards"
```

Result: `1 passed`. This test builds a temporary SQLite DB with one noisy
`CPM_CONTROL__REFCLK_REGS_GATE_ENABLE_MASK` row, two `CP_HQD_*` register rows,
and real persisted `reads`/`writes` graph edges. It then calls the real Next
`/api/workbench/query` route and fails unless every returned row is a
`CP_HQD_` symbol and the graph contains both `reads` and `writes` edges.

Manual current-DB and browser checks for the same query:

```text
query: who will write/read CP_HQD_* regs
data/asip.db via core: rows=8, graph nodes=164, graph edges=552
data/asip.db via Next BFF: rows=24, graph nodes=164, graph edges=552
relations: reads=81, writes=275, sets_field=42, maps_base=29, calls=125
```

In-app Browser at `http://localhost:3111/graph` after running the query showed
`matches: 24`, `graph edges: 552`, visible `CP_HQD_ACTIVE`,
`CP_HQD_PQ_DOORBELL_CONTROL`, and `reads`/`writes` edge labels in the graph
surface.

Fresh continuation regression after the NL wildcard fix:

```text
PYTHONPATH=packages/core/src:packages/core/tests \
  python3 -m unittest \
  packages.core.tests.test_workbench_query_schema \
  packages.core.tests.test_storage_graph \
  packages.core.tests.test_workbench_live \
  -v
```

Result: `Ran 142 tests`, `OK`, with `2` optional sqlite-vec skips.

```text
pnpm --filter web exec playwright test tests/workbench-api.spec.ts --reporter=list
```

Result: `33 passed`.

```text
pnpm --filter web exec tsc --noEmit
git diff --check
```

Result: both passed. The generated `apps/web/tsconfig.tsbuildinfo` file was
removed after the TypeScript run.

```text
In-app Browser: http://localhost:3100/graph
```

Result: page rendered without runtime crash at 2048 x 1280, top bar shows
`Edge: Ollama / gemma4:e4b`, and Graph Explorer exposes the graph action
buttons plus semantic controls. Screenshot:
`docs/qa/browser/asip-graph-current-2026-05-19-2k.png`. Snapshot:
`docs/qa/browser/asip-graph-current-2026-05-19-snapshot.md`.

```text
In-app Browser: http://localhost:3100/acceptance
```

Result: page rendered without runtime crash at 2048 x 1280, top bar shows
`Edge: Ollama / gemma4:e4b`, and the Acceptance test workspace exposes the
runner/results/detail surfaces. Screenshot:
`docs/qa/browser/asip-acceptance-current-2026-05-19-2k.png`. Snapshot:
`docs/qa/browser/asip-acceptance-current-2026-05-19-snapshot.md`.

## Acceptance Notes

- This pass closes the immediate doc subtype product projection and the Graph
  page explicit DB-path no-mock e2e gap that existed in this slice. It does not
  close later `/acceptance` DB-path/browser evidence requirements.
- This pass does not claim the full ASIP goal is complete. The remaining full
  gate still needs final design/spec reconciliation, generated-artifact
  hygiene, full diff review, commit/push, and explicit residual-boundary
  acceptance.
- Future graph completion claims must continue to prove both Stage 1
  deterministic graph edges and Stage 2 LLM semantic edges, with provider/model
  provenance and no visible resolver/macro helper nodes.

## Graph Filter And Provenance Follow-Up

Date: 2026-05-19

Implemented a no-mock graph control regression for the Graph Explorer. The test
creates a temporary SQLite DB with two deterministic Stage 1 edges and one
semantic Stage 2 document edge, then loads `/graph?dbPath=...` through the real
Next workbench API.

Verified behavior:

- The graph header shows real layer counts: `deterministic: 2 semantic: 1`.
- The semantic edge carries provider provenance through core graph projection:
  `ollama/gemma4:e4b` and `job 42`.
- The UI exposes shadcn/Radix checkbox filters for relation, stage, and source.
- Toggling the `documents` relation filter changes the rendered force graph
  from `3` visible edges to `2` visible edges.
- Moving the visible `Loaded edge budget` slider triggers a real graph API
  request with `limit=1`; the limit is user controlled instead of hidden in the
  component.

Commands:

```text
PYTHONPATH=packages/core/src:packages/core/tests \
  python3 -m pytest \
  packages/core/tests/test_storage_graph.py::StorageGraphTests::test_global_graph_edge_attr_preserves_semantic_provider_provenance \
  -q
```

Result: `1 passed`.

```text
pnpm --filter web exec playwright test \
  tests/workbench-smoke.spec.ts \
  -g "graph page filters no-mock graph layers" \
  --reporter=list
```

Result: `1 passed`.

Follow-up regression set:

```text
PYTHONPATH=packages/core/src:packages/core/tests \
  python3 -m unittest \
  packages.core.tests.test_storage_graph \
  packages.core.tests.test_workbench_live \
  -v
```

Result: `Ran 124 tests`, `OK`, with `3` expected skips including the opt-in
real Ollama smoke when `ASIP_REAL_OLLAMA` is not set.

```text
pnpm --filter web exec playwright test \
  tests/workbench-smoke.spec.ts \
  -g "graph page uses URL dbPath|graph page filters no-mock graph layers|graph page runs LLM document node extraction" \
  --reporter=list
```

Result: `3 passed`.

```text
pnpm --filter web exec tsc --noEmit
```

Result: passed.

In-app browser smoke at 2048 x 1280:

```text
http://localhost:3111/graph
query: who will write/read CP_HQD_* regs
```

Result: after pressing `Run query`, the page showed `matches: 24`,
`graph edges: 552`, `layers deterministic: 552`, provenance
`source clang_text_spans source clang_callback`, and visible relation/stage/source
filter groups. Screenshot:
`docs/qa/browser/asip-graph-filter-provenance-after-query-2026-05-19-2k.png`.
Snapshot:
`docs/qa/browser/asip-graph-filter-provenance-after-query-2026-05-19-snapshot.md`.

## Real Ollama Doc-Node Smoke

Added an opt-in live smoke test for local Ollama doc-node extraction. By default
it skips unless `ASIP_REAL_OLLAMA=1` is set. When enabled, it checks local
Ollama `/api/tags`, requires `gemma4:e4b`, calls
`workbench.generate_doc_nodes_batch(...)` without a fake provider, and asserts
that a `stage=semantic`, `source=ollama`, `extractor=doc_nodes` edge is
persisted and projected as a `doc_kind=boxmatrix_box` product graph node.

Subagent validation ran:

```text
ASIP_REAL_OLLAMA=1 PYTHONPATH=packages/core/src:packages/core/tests \
  python3 -m pytest \
  packages/core/tests/test_workbench_live.py::WorkbenchLiveTests::test_real_ollama_doc_node_batch_persists_boxmatrix_doc_edges_when_enabled \
  -q -rs
```

Result: `1 passed in 25.35s`.

## Resolver Access Relation Map

Date: 2026-05-19

Closed a G05 implementation gap where `graph.access_relation_map` was parsed
from resolver profiles but did not affect Stage 1 deterministic graph edges.

New RED/GREEN coverage:

```text
PYTHONPATH=packages/core/src:packages/core/tests \
  python3 -m pytest \
  packages/core/tests/test_code_graph.py::DeterministicCodeGraphTests::test_resolver_access_relation_map_controls_deterministic_graph_relation \
  -q
```

Result: `1 passed` after the implementation change. The test uses a custom
profile with wrapper `DOORBELL_WRITE`, raw access `doorbell_write`, and
`graph.access_relation_map: {doorbell_write: writes}`. Stage 1 now emits a
product `writes` edge to `CP_HQD_PQ_DOORBELL_CONTROL` and keeps
`access=doorbell_write` plus `mapped_relation=writes` in provenance.

Regression sweep:

```text
PYTHONPATH=packages/core/src:packages/core/tests \
  python3 -m unittest \
  packages.core.tests.test_code_graph \
  packages.core.tests.test_resolver_profiles \
  packages.core.tests.test_workbench_live \
  -v
```

Result: `Ran 110 tests`, `OK`, with the expected opt-in real Ollama smoke skip
when `ASIP_REAL_OLLAMA` is not set.

## Current Default DB Acceptance

Date: 2026-05-19

Subagent evidence review found that the current default `data/asip.db` still had
two empty placeholder corpora, `amd-docs` and `local-amd-docs`, with
`status=not_indexed`, `file_count=0`, and no document/chunk/evidence rows. This
made the current DB health gate fail even though the graph/query evidence was
present. I backed up the DB to
`/tmp/asip-db-before-empty-corpus-clean-2026-05-19.db`, removed those empty
placeholder corpus rows from `data/asip.db`, and reran acceptance against the
current default DB.

Post-cleanup DB health:

```text
sqlite3 -readonly data/asip.db \
  "select status, count(*) from corpora group by status; \
   select id, status, file_count from corpora order by id; \
   select stage, source, count(*) from edges group by stage, source order by stage, source;"
```

Result:

```text
indexed|3
amd-amdgpu-docs|indexed|2
linux-amdgpu|indexed|625
mxgpu|indexed|722
deterministic|clang_callback|6133
deterministic|clang_text_spans|34987
deterministic|text_fallback|775
evidence|query_expected_terms|22
semantic|ollama|25
```

Current default DB acceptance:

```text
ASIP_WEB_BASE_URL=http://127.0.0.1:3111 \
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=packages/core/src:. \
python3 -m asip.cli acceptance \
  --db data/asip.db \
  --surface CLI \
  --surface API \
  --surface Web \
  --surface MCP \
  --output-json docs/qa/2026-05-19-acceptance-data-asip-current.json \
  --output-md docs/qa/2026-05-19-acceptance-data-asip-current.md
```

Result: `9 passed / 0 partial / 0 failed`.

This new artifact proves the current `data/asip.db` passes DB health and
AQ01-AQ09 across CLI, FastAPI, Web BFF, and MCP direct tool surfaces. The older
`docs/qa/2026-05-19-acceptance-clean-amd-current.*` artifact remains useful as a
named `/tmp` clean-DB comparison, but it is no longer the only passing
acceptance evidence for the current default workbench DB.

## Natural Language Register Wildcard Query

Date: 2026-05-19

User-reported symptom: the query `who will write/read CP_HQD_* regs` did not
feel like it worked from `/graph`. The root cause was not provider inference:
the backend could find prefix-matched register evidence, but the first result
rows were register-header `mention` rows instead of graph-derived
function-to-register access answers. In addition, `/graph?q=...` did not run
the URL query on load and could be overwritten by the global graph request.

Implementation evidence:

- `packages/core/src/asip/workbench.py` now converts access-intent wildcard
  queries into graph-derived answer rows when the graph contains matching
  `reads` or `writes` edges.
- The result row schema preserves `target_symbol`, so the Web table can render
  `function -> register` instead of only the function name.
- `/graph?q=...` now executes the URL query on load and guards against stale
  global-graph responses overwriting the query graph.
- Register-header inventory extraction now uses a stricter
  source-type-specific symbol filter. It keeps real register/header symbols
  such as `CP_HQD_ACTIVE`, `CP_HQD_PQ_WPTR_LO`, and
  `CP_HQD_ACTIVE__ACTIVE_MASK`, while rejecting low-signal tokens such as `A`,
  `tmp`, and `adapt`.

Fresh verification:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests \
python3 -m unittest \
  packages.core.tests.test_workbench_query_schema \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_generated_register_headers_are_indexed_as_register_source_type \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_register_header_inventory_classifies_cp_hqd_registers_and_skips_low_signal_tokens \
  -v
```

Result: `Ran 22 tests`, `OK`.

```text
pnpm --filter web exec playwright test \
  tests/workbench-api.spec.ts \
  -g "natural language register wildcards" \
  --reporter=list
```

Result: `1 passed`.

```text
pnpm --filter web exec playwright test \
  tests/workbench-smoke.spec.ts \
  -g "settings page uses URL dbPath|corpus page uses URL dbPath|global symbol search|graph page initial URL query|graph page uses URL dbPath" \
  --reporter=list
```

Result: `5 passed`.

This adds two no-route-rewrite DB-path gates found by the Web audit:

- `/corpus?dbPath=<temp sqlite>` lists from the temp DB, adds a corpus with
  repo-relative subfolder filters, survives reload, runs index, and proves the
  temp DB contains the new corpus, documents, and
  `regURL_DBPATH_HEADER_ONLY` evidence.
- `/settings?dbPath=<temp sqlite>` saves provider settings and proves the temp
  DB's `provider_settings.settings_json` contains the saved edge and embedding
  models.

The same fix makes resolver-profile list/add/validate BFF calls carry
`dbPath` as well, so Graph/Corpus/Settings/Resolver UI state does not silently
fall back to `data/asip.db` when a user opens an isolated workbench DB.

```text
pnpm --filter web exec playwright test \
  tests/workbench-api.spec.ts \
  -g "corpora API persists user-added corpus subfolder filters|index API honors user-added corpus subfolder filters|natural language register wildcards" \
  --reporter=list
```

Result: `3 passed`. A first parallel run hit `EADDRINUSE` on port `3100` due
to overlapping Playwright web servers; the serial rerun above passed.

```text
pnpm --filter web exec tsc --noEmit
```

Result: exit code `0`.

Current `data/asip.db` live query evidence:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 - <<'PY'
from pathlib import Path
from collections import Counter
from asip.workbench import query_evidence
result = query_evidence(Path("data/asip.db"), "who will write/read CP_HQD_* regs", limit=8)
print(len(result["rows"]), len(result["graph"]["nodes"]), len(result["graph"]["edges"]))
print(Counter(edge["relation"] for edge in result["graph"]["edges"]))
for row in result["rows"]:
    print(row["symbol"], row["relation"], row.get("target_symbol"), row["path"], row.get("line_start"))
PY
```

Result: `8` rows, `164` graph nodes, `552` graph edges. The first visible
answers are code access rows:

```text
gfx_deactivate_hqd reads CP_HQD_ACTIVE drivers/gpu/drm/amd/amdgpu/gfx_v8_0.c 4369
gfx_deactivate_hqd writes CP_HQD_DEQUEUE_REQUEST drivers/gpu/drm/amd/amdgpu/gfx_v8_0.c 4370
gfx_deactivate_hqd writes CP_HQD_PQ_RPTR drivers/gpu/drm/amd/amdgpu/gfx_v8_0.c 4380
gfx_deactivate_hqd writes CP_HQD_PQ_WPTR drivers/gpu/drm/amd/amdgpu/gfx_v8_0.c 4381
```

In-app browser verification used a clean dev server on port `3112` after the
previous `3111` server became stale during hot reload. The page
`http://localhost:3112/graph?q=who%20will%20write%2Fread%20CP_HQD_*%20regs`
showed `matches: 24`, `graph edges: 552`, and table rows such as
`gfx_deactivate_hqd -> CP_HQD_ACTIVE code reads`. Snapshot and screenshot
evidence:

- `docs/qa/browser/asip-graph-cp-hqd-nl-query-2026-05-19-3112.md`
- `docs/qa/browser/asip-graph-cp-hqd-nl-query-table-2026-05-19-3112.md`
- `docs/qa/browser/asip-graph-cp-hqd-nl-query-2026-05-19-3112.png`

Residual note: the current default `data/asip.db` still contains some historical
register-header evidence rows that were indexed before this classification
fix. The live query no longer surfaces those rows ahead of access answers, and
fresh indexing uses the stricter filter. A full re-index will make the stored
header evidence classification itself clean as well.

## Subagent Audit Follow-Up

Date: 2026-05-19

Three read-only subagent audits were run against the current worktree and
runtime state:

- Backend graph/vtable audit: Stage 1 register-access extraction, function
  nodes, direct calls, conservative callback/vtable joins, and
  concept/implementation normalization have implementation and test evidence.
  Current `data/asip.db` contains `6133` `clang_callback` deterministic edges,
  including `6042` `vtable_dispatch`, `70` `vtable_callback`, and `21`
  `vtable_table_alias` provenance rows. Product graph probes found shared
  linux-amdgpu/MxGPU register bridges such as `register:IH:IH_RB_CNTL`. The
  audit explicitly does not prove full clangd/libclang cross-TU points-to
  correctness; that remains a residual boundary unless scoped into a later
  extractor.
- Web/UI audit: strong evidence exists for `/graph` live DB output,
  shadcn/Radix usage, light/dark theme, acceptance detail UI, corpus subfolder
  API support, and graph relation filters. It found a real gap where
  `/corpus?dbPath=...` and `/settings?dbPath=...` UI paths could fall back to
  `data/asip.db`; the current patch adds no-route-rewrite e2e coverage and
  fixes Corpus, Settings, and Resolver Profile DB-path propagation.
- DB/QA audit: current `data/asip.db` is a real workbench DB with `3` indexed
  corpora, `124` documents, `21884` chunks, `860516` evidence rows, `41942`
  edges, `32` embeddings, and current acceptance AQ01-AQ09 `9/9` across
  CLI/API/Web/MCP. The audit distinguishes this live DB from the clean
  reference `/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db`, notes
  that AMD docs are represented by a reduced fixture, and warns not to cite old
  qwen artifacts as current clean evidence.

Residuals carried forward from these audits:

- full clangd/libclang cross-TU vtable/points-to extraction is not implemented;
- current `data/asip.db` is a live DB and still has some raw historical
  semantic rows that product graph projection filters out;
- the expanded `linux-amdgpu` sibling `include/asic_reg` production DB refresh
  still needs a fresh full re-index/performance pass before it replaces the
  default DB shape;
- final gate still requires artifact hygiene, final diff review, commit, push,
  and explicit residual-boundary wording.

## Resolver Profile Corpus Scope

Date: 2026-05-19

Subagent and local review found a real resolver-profile gap: a multi-corpus
index job that enabled both `linux-amdgpu` and `amd-mxgpu` could attribute an
MxGPU `WREG32` access to the `linux-amdgpu` profile because profiles were
applied in global sort order. That was wrong for the user requirement that
different repos can carry different resolver macro sets.

RED test:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests \
python3 -m unittest \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpora_prefers_matching_resolver_profile_per_corpus \
  -v
```

Initial result:

```text
AssertionError: 'linux-amdgpu' != 'amd-mxgpu'
```

Implementation:

- `index_configured_corpora`, `index_registered_corpora`, and
  `rebuild_deterministic_graph` now order resolver profiles per corpus.
- Profiles matching the corpus id, repo URL text, or profile aliases run first.
- Non-matching profiles remain available as fallback, so generic or custom
  profiles still work when no corpus-specific profile matches.

GREEN verification:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests \
python3 -m unittest \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpora_prefers_matching_resolver_profile_per_corpus \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_cross_file_vtable_callbacks_to_registers \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_generic_common_dispatch_to_multiple_callbacks \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_mxgpu_init_func_dispatch_to_register_callback \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_configured_index_supports_multiple_subfolder_filters_for_one_repo \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_rebuild_deterministic_graph_honors_registered_subfolder_filters \
  -v
```

Result: `Ran 6 tests`, `OK`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests \
python3 -m unittest \
  packages.core.tests.test_workbench_backend_state.WorkbenchBackendStateTests.test_selected_resolver_profiles_limit_registered_index_evidence_and_graph \
  packages.core.tests.test_workbench_cli.WorkbenchCliTests.test_index_and_graph_rebuild_commands_accept_resolver_profile_id \
  packages.core.tests.test_resolver_profiles \
  -v
```

Result: `Ran 16 tests`, `OK`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests \
python3 -m unittest packages.core.tests.test_workbench_live -v
```

Result: `Ran 65 tests`, `OK`, `skipped=1` for the opt-in real Ollama doc-node
smoke.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests \
python3 -m unittest packages.core.tests.test_storage_graph packages.core.tests.test_workbench_query_schema -v
```

Result: `Ran 81 tests`, `OK`, `skipped=2` for optional sqlite-vec extension
checks.

The new fixture proves:

- `ih_v11_0_hw_init` from `linux-amdgpu` is resolved by `linux-amdgpu`;
- `mxgpu_irq_init` from `mxgpu` is resolved by `amd-mxgpu`;
- the Linux callback path still connects
  `amdgpu_device_init -> ih_hw_init -> IH_RB_CNTL`;
- MxGPU still writes the same `register:IH:IH_RB_CNTL`;
- the merged register node keeps source provenance from both corpora and the
  MxGPU source record keeps `resolver_profile=amd-mxgpu`.

## Default DB Audit Correction

Date: 2026-05-19

The current live `data/asip.db` should not be cited as the complete expanded
Linux register-header default DB. A read-only subagent audit found:

```text
corpora=4
documents=124
chunks=21884
evidence=860516
edges=41942
embeddings=32
```

Source distribution:

```text
amd-amdgpu-docs: 2 docs, source_type doc=1/pdf=1
linux-amdgpu:    1 doc, source_type code=1
mxgpu:           121 docs, code=6/doc=19/register=96
url-dbpath-corpus: not_indexed placeholder, 0 docs
```

Key correction: `linux-amdgpu` has zero documents under
`drivers/gpu/drm/amd/include/asic_reg` in the current live DB. The expanded
multi-subfolder config is correct, but the live default DB has not been
replaced by a fresh production-scale rebuild that includes those Linux register
headers. Stage 2 rows are `gemma4:e4b`, not qwen, but the raw semantic rows are
older than the latest deterministic rebuild and should be treated as live DB
state, not clean final proof.

Final completion must either:

- rebuild a new default candidate DB from
  `configs/edge_cases/clean-amd-gemma4-e4b.json`, verify Linux
  `include/asic_reg` document counts, Stage 1, Stage 2, acceptance, browser,
  and e2e; or
- explicitly keep the expanded default-DB replacement as an accepted residual.

## 2026-05-20 Continuation Evidence

Status: targeted parser/UI/default-DB progress; still not a final completion
claim.

Stage 1 false-positive call scanning was extended after subagent review found
that comments/strings were handled but disabled whole-function spans,
disabled vtable initializers, and disabled global receiver aliases could still
pollute deterministic graph edges. New red/green coverage in
`packages/core/tests/test_code_graph.py` now proves:

- direct and slot calls inside comments, string/char literals, and `#if 0`
  blocks are ignored;
- whole function definitions inside disabled preprocessor blocks do not emit
  call/register/callback edges;
- disabled callback initializers do not become vtable dispatch candidates;
- disabled global receiver aliases do not narrow active slot dispatch;
- `#if (0)` with `#else` and `#if 1` with disabled `#else` branches keep the
  active/disabled side straight.

Fresh verification:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests \
python3 -m unittest packages.core.tests.test_code_graph -v
```

Result: `Ran 38 tests`, `OK`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src \
python3 -m pytest packages/core/tests/test_code_graph.py \
  packages/core/tests/test_workbench_live.py \
  packages/core/tests/test_semantic_edges.py -q
```

Result: `135 passed, 1 skipped`.

A follow-up read-only parser/vtable subagent review found a remaining cross-file
collector path: the workbench pre-collected function locations and receiver
aliases from raw source text before calling `build_deterministic_code_graph`.
Two live-index regressions now cover that path:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_ignores_disabled_cross_file_receiver_aliases \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_ignores_disabled_cross_file_function_locations \
  -v
```

RED before the fix: disabled `#if 0` aliases/functions leaked into cross-file
indexing. GREEN after changing the collector path to use the same masked source
scan as the graph builder: `Ran 2 tests`, `OK`.

Fresh parser/storage/workbench regression after that fix:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m pytest -p no:cacheprovider -q packages/core/tests/test_code_graph.py
```

Result: `38 passed`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m pytest -p no:cacheprovider -q \
  packages/core/tests/test_storage_graph.py packages/core/tests/test_workbench_live.py
```

Result: `125 passed, 3 skipped`.

The live default `data/asip.db` was re-indexed for the expanded
`linux-amdgpu` subfolder corpus:

```text
PYTHONPATH=packages/core/src python3 -m asip.cli index \
  --db data/asip.db --corpus-id linux-amdgpu
```

Result summary:

```text
job_id=10
job_status=succeeded
documents=1101
chunks=125962
evidence=4438962
edges=27533
files=1101
```

Read-only DB audit after the re-index:

```text
linux-amdgpu status=indexed
linux-amdgpu file_count=1101
scan roots:
  drivers/gpu/drm/amd/amdgpu: 625 files
  drivers/gpu/drm/amd/include/asic_reg: 476 files
documents=1101
include/asic_reg documents=476
include/asic_reg evidence=4195965
document source types:
  code=625
  register=476
edge count=39981
top relations:
  calls=25761
  writes=6730
  reads=3533
  maps_base=2387
  sets_field=1558
```

The old interrupted job `9` has now been marked `superseded` by the job hygiene
CLI instead of being left as an active index failure:

```text
PYTHONPATH=packages/core/src python3 -m asip.cli jobs \
  --db data/asip.db --kind index --supersede-stale-before-id 10
```

Result: `superseded_job_ids: [9]`. The default DB health gate no longer fails
on the stale job.

The CP_HQD natural-language regression still passes:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests \
python3 -m unittest \
  packages.core.tests.test_workbench_query_schema.WorkbenchQuerySchemaTests.test_natural_language_register_wildcard_query_uses_symbol_prefix_not_regs_noise \
  -v
```

Result: `Ran 1 test`, `OK`.

Manual CLI query against the refreshed default DB returned graph-derived
function-to-register rows for `who will write/read CP_HQD_* regs`, including:

```text
gfx_deactivate_hqd -> CP_HQD_ACTIVE reads
gfx_deactivate_hqd -> CP_HQD_DEQUEUE_REQUEST writes
gfx_deactivate_hqd -> CP_HQD_PQ_RPTR writes
gfx_deactivate_hqd -> CP_HQD_PQ_WPTR writes
gfx_kiq_fini_register -> CP_HQD_ACTIVE reads
```

Web dbPath propagation was tightened after audit:

- non-query page global search now preserves URL `dbPath` when navigating to
  `/?q=...`;
- corpus-page job history now waits for URL DB-path initialization and sends
  `dbPath` to `/api/workbench/jobs`.

Fresh frontend checks:

```text
pnpm --dir apps/web exec tsc --noEmit
pnpm --dir apps/web exec eslint components/workbench-page.tsx tests/workbench-smoke.spec.ts
pnpm --dir apps/web exec playwright test tests/workbench-smoke.spec.ts \
  -g "global search preserves URL dbPath|corpus page fetches index jobs from the URL dbPath" --list
```

Results: `tsc` exit 0; eslint exit 0; Playwright listed both new tests.

Attempting to execute the two Playwright tests with a fresh local Next dev
server on `127.0.0.1:3118` failed before assertions because the sandbox
rejected the listen syscall:

```text
Error: listen EPERM: operation not permitted 127.0.0.1:3118
Error: Process from config.webServer exited early.
```

Manual server startup on `0.0.0.0:3120` failed with the same `listen EPERM`
class of error, so the current environment still cannot provide fresh browser
e2e evidence for these UI fixes.

A minimal Python socket probe on `127.0.0.1:3121` also returned
`[Errno 1] Operation not permitted`, and direct localhost reads for the prior
`3100` / `3111` graph URLs were blocked with the same permission class. This
keeps the browser evidence gap environment-bound rather than a silent test
pass.

Acceptance/schema follow-up after job hygiene:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest packages.core.tests.test_acceptance_runner -v
```

Result: `Ran 14 tests`, `OK`. The new red/green regression proves acceptance
query records include explicit `schema_status` and `schema_failure_reasons` for
product graph contract failures. The provider acceptance coverage now also
requires persisted semantic-edge provenance in addition to live provider smoke,
so AQ09 can distinguish existing real semantic edges from current provider
reachability.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest packages.core.tests.test_graph_schema -v
```

Result: `Ran 3 tests`, `OK`.

Current expanded default DB acceptance artifact:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
python3 -m asip.cli acceptance \
  --db data/asip.db \
  --output-json docs/qa/2026-05-20-acceptance-data-asip-expanded.json \
  --output-md docs/qa/2026-05-20-acceptance-data-asip-expanded.md \
  --surface CLI --surface API --surface MCP --full
```

Result: database health `pass`; AQ01-AQ09 product graph schema `pass`; summary
`0 passed / 8 partial / 1 failed`. AQ05 now includes `code`, `doc`, `pdf`, and
`register` source types. AQ01-AQ08 are partial only because the Web surface is
still missing from this run. AQ09 fails because the live Ollama
`gemma4:e4b` semantic-edge provider smoke is blocked by
`Operation not permitted`; embedding provenance exists for
`nomic-embed-text:latest`, and `14` persisted `ollama/gemma4:e4b` semantic
edges exist from job `4`, but the current 2026-05-20 acceptance gate marks
semantic-edge extraction provenance `partial/stale` because latest index job
`10` is newer. `11` same-provider doc-node edges are reported as ignored for
this AQ09 check.

Therefore browser/e2e evidence and live provider semantic-edge evidence are
still missing in this environment. The final gate still needs an executable
browser path, `/acceptance` explicit DB-path no-mock QA, 2K light/dark captures
after the final UI changes, the V2 final QA package, and an explicit residual
decision for full clangd/libclang cross-TU coverage.
