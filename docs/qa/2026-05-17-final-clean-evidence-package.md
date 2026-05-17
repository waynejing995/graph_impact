# Final Clean Evidence Package

Generated: 2026-05-17
Status: Current completion evidence; latest live graph verification appended below

## Clean Database

- DB: `/tmp/asip-clean-amd-gemma4-provider-2026-05-17-final.db`
- Config: `configs/edge_cases/clean-amd-gemma4-e4b.json`
- MxGPU source root: `/tmp/asip-mxgpu`, git `f603f87`
- Linux amdgpu source root: `/tmp/asip-linux-amdgpu`, git `6916d57`, relative root `drivers/gpu/drm/amd/amdgpu`
- Reduced AMD docs/PDF fixture: `docs/fixtures/amd-amdgpu-docs`

Counts from the clean provider DB:

| Table | Count |
| --- | ---: |
| documents | 124 |
| chunks | 21884 |
| evidence | 860516 |
| edges | 10019 |
| embeddings | 32 |

Document source counts: `code=7`, `doc=20`, `pdf=1`, `register=96`.

Evidence source counts: `code=126`, `doc=5664`, `pdf=5`, `register=854721`.

Provider embeddings are partial by design for this QA pass: `ollama/nomic-embed-text:latest`, `metadata.source=provider`, count `32`, fallback count `0`. Full provider-vector coverage and query-time provider rerank remain G06/G09/G15 boundaries.

## Acceptance

- Artifact: `docs/qa/2026-05-17-acceptance-clean-amd-gemma4-provider-current.json`
- Markdown: `docs/qa/2026-05-17-acceptance-clean-amd-gemma4-provider-current.md`
- Result: 9 total, 9 passed, 0 partial, 0 failed
- Surfaces labelled: CLI, API, Web, MCP
- Provider checks: embedding pass with `nomic-embed-text:latest`; semantic edge pass with `gemma4:e4b`
- Edge settings: `num_ctx=2048`, `num_predict=1024`, `think=false`, `timeout_seconds=900`

## Free Queries And Graph

- Artifact: `docs/qa/2026-05-17-clean-amd-gemma4-free-query-and-edge-qa.json`
- Markdown: `docs/qa/2026-05-17-clean-amd-gemma4-free-query-and-edge-qa.md`
- Queries: 6
- Non-empty queries: 6
- Source types seen: `code`, `doc`, `pdf`, `register`
- Global graph: NetworkX runtime, 2,822 nodes, 4,725 deterministic Stage 1 edges in full no-seed graph export
- Semantic-edge proof: clean AQ09 provider smoke passes with `ollama/gemma4:e4b`; live dev graph has persisted `gemma4:e4b` semantic/doc-node jobs below

## Visual QA

- Historical route screenshot artifact: `docs/qa/visual-qa-2026-05-17/visual-qa.json`
- Markdown: `docs/qa/visual-qa-2026-05-17/visual-qa.md`
- Viewport: 2048 x 1280
- Routes: `/`, `/graph`, `/corpus`, `/resolver-profiles`, `/acceptance`, `/settings`
- Result: 6 passed, 0 failed
- Themes: dark and light screenshots captured for every route
- Historical `/graph` screenshot in that artifact: 12 nodes and 4 weighted edges visible in both themes before the later dense graph QA
- Fresh in-app browser QA at `http://127.0.0.1:3100/graph` after this pass: top bar shows `Edge: Ollama / gemma4:e4b`; `/graph` loads the live global graph with 3,000 graph edges, 1,000 visible nodes, 1,829 visible edges, layer provenance `deterministic: 2987 semantic: 13`, and visible `function`, `register`, `doc_box`, and `doc_section` node classes. `/corpus`, `/settings`, and `/acceptance` also hydrate from live backend state and show the current gemma provider artifact.
- Fresh in-app browser snapshot after the callback-overlink fix still shows the live `/graph` page with `Loaded edge budget 3000 / 20000`, `Visible nodes 1000 / 2120`, `Visible edges 3000 / 3000`, and the accessibility summary lists `nodes 1000`, `edges 1829`, `function 561`, `register 437`, `doc_box 1`, and `doc_section 1`; the underlying full product graph sample below records `control-keyword function nodes named "if": 0`.

## Automated Verification

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v`: 162 tests OK, 1 sqlite-vec skip
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest apps.api.tests.test_app apps.api.tests.test_runtime apps.mcp.tests.test_tools apps.mcp.tests.test_server -v`: 41 tests OK, 1 optional MCP runtime skip
- `pnpm --filter web exec tsc --noEmit`: passed
- `pnpm --filter web exec playwright test tests/workbench-api.spec.ts --reporter=list`: 18 passed
- `pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts --reporter=list`: 35 passed
- `pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts --reporter=list`: 13 passed
- `git diff --check`: passed

## Latest Live Graph And E2E Verification

This section supersedes the older automated counts above for the current working tree and the dirty local `data/asip.db` used by the live Web workbench.

Current provider settings were restored after tests:

```text
edge: ollama / gemma4:e4b at http://localhost:11434/api/chat
embedding: ollama / nomic-embed-text:latest at http://localhost:11434/api/embeddings
extra headers: {}
```

Current graph jobs in `data/asip.db`:

```text
graph_rebuild job 56: 14674 deterministic edges from 1225 files
semantic_edges job 43: gemma4:e4b, 6 raw semantic edges
semantic_edges job 44: gemma4:e4b, 5 raw semantic edges
doc_nodes_batch job 45: gemma4:e4b, 6 doc boxes and 11 doc semantic edges
```

Current product graph sample:

```text
global_graph(all_edges=true)
nodes=6920
edges=9287
node kinds: function=5302, register=1611, doc_box=6, doc_section=1
visible semantic edges=13
control-keyword function nodes named "if": 0
```

Query performance regression evidence:

```text
query_evidence(data/asip.db, "doorbell interrupt disable")
before final fixes: 58.228s
after final fixes: 0.487s
rows=24
query graph nodes=32
query graph edges=37
```

Fresh automated verification:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v
Ran 162 tests in 7.511s
OK (skipped=1)

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest \
  apps.api.tests.test_app apps.api.tests.test_runtime apps.mcp.tests.test_tools apps.mcp.tests.test_server -v
Ran 41 tests in 79.614s
OK (skipped=1)

pnpm --filter web exec tsc --noEmit
passed

pnpm --filter web run lint
passed

pnpm --filter web exec playwright test tests/workbench-api.spec.ts tests/workbench-smoke.spec.ts --reporter=list
69 passed

pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts --reporter=list
15 passed

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_providers.EmbeddingProviderTests.test_extra_headers_expand_environment_placeholders_without_persisting_secret \
  packages.core.tests.test_providers.EmbeddingProviderTests.test_extra_header_env_placeholder_requires_existing_variable \
  packages.core.tests.test_providers.EmbeddingProviderTests.test_extra_headers_expand_direct_environment_reference \
  packages.core.tests.test_semantic_edges.SemanticEdgeFeatureTests.test_edge_provider_extra_headers_expand_environment_placeholders \
  packages.core.tests.test_semantic_edges.SemanticEdgeFeatureTests.test_edge_provider_extra_header_missing_environment_stops_before_transport -v
Ran 5 tests in 0.003s
OK

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  /Users/chenjingwen/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m unittest packages.core.tests.test_storage_graph.StorageGraphTests.test_sqlite_vec_extension_can_run_when_runtime_supports_extensions -v
Ran 1 test in 0.001s
OK

git diff --check
passed
```

Continuation fixes verified in the same pass:

- `graph-rebuild --corpus-id` now preserves deterministic edges from non-selected corpora instead of clearing every Stage 1 edge.
- `/resolver-profiles` can load an existing YAML-backed profile into the editor before saving, so built-in profiles are editable through the UI path instead of being add-only rows.
- Top-bar global search runs a real `/api/workbench/query` request from graph-capable pages.
- Source-type filter controls are real query controls and send `sourceTypes` to the Web BFF/core query path.
- `/graph` exposes semantic generation limit and batch-size overrides in the UI and sends them to `/api/workbench/semantic-edges`.
- The graph header now displays layer provenance such as deterministic and semantic edge counts.

Clean AQ01-AQ09 provider acceptance is now represented by the `gemma4:e4b` artifact above. Historical qwen3.5 artifacts remain comparison/provenance evidence only, not current clean-provider closure. The live `data/asip.db` graph section remains separate dev-browser evidence for persisted Stage 2 semantic/doc-node jobs after the final graph-shape fixes.

## Architecture Review

| Capability | Owner | Evidence | Boundary |
| --- | --- | --- | --- |
| Corpus registration/indexing | core, Web BFF, API, MCP | `asip.workbench`, `asip.cli index`, API/MCP/Web tests | Full all-code parser deferred; current path is query-focused code plus supplemental docs/register/PDF |
| Document/PDF conversion | core | `asip.documents`, PDF tests, clean DB PDF counts | OCR/scanned PDF remains non-goal |
| Resolver profiles | core plus UI/BFF/API/MCP | resolver profile tests and UI/API smoke | Rich edit-in-place/per-job profile selection remains future work |
| Retrieval/evidence schema | core, thin app surfaces | clean AQ 9/9, six free queries, API/MCP/Web agreement tests | Provider-vector rerank remains boundary |
| SQLite/FTS/vector | core storage | FTS/vector tests, provider embedding provenance, native sqlite-vec extension smoke in bundled Python runtime | Product retrieval still uses JSON vectors plus Python cosine until native sqlite-vec retrieval acceleration is wired |
| NetworkX graph | core storage/workbench | graph tests, free-query/global graph QA, visual `/graph` QA | Browser design polish still reviewed in G16 |
| Deterministic C graph/callgraph | core code graph plus storage/workbench | function-register operation tests, compile_commands macro test, direct helper call test, cross-file ops/vtable callback test, same-slot overlink regression | Conservative source/span parser, not full clangd/libclang callback coverage |
| Semantic-edge generation | core plus CLI/Web/API/MCP | `gemma4:e4b` clean provider acceptance plus current live `gemma4:e4b` semantic/doc-node jobs and semantic-edge parity tests | Large prompts still need adequate `num_predict` and JSON robustness |
| Provider settings | core plus Settings UI/BFF/API/MCP | AQ09, provider tests, settings UI tests | Credentialed OpenAI-compatible live QA requires credentials or accepted local-compatible boundary |
| FastAPI | `apps/api` thin over core | API tests and live Uvicorn smoke | Optional deployment packaging not in MVP |
| MCP | `apps/mcp` thin over core | tool tests and server registration test | Optional external `mcp` runtime package skipped when absent |
| React UI and visual anchors | `apps/web` React UI | Playwright smoke/API/visual tests and visual QA screenshots | Recapture required after future UI-affecting changes |

## Residual Boundaries

- Native sqlite-vec extension loading is skipped in system Python 3.9, and the bundled Python 3.12 runtime passes the native sqlite-vec extension smoke; product retrieval still uses the fallback JSON-vector/Python-cosine adapter until native sqlite-vec retrieval acceleration is wired.
- Credentialed OpenAI-compatible live provider QA is not performed without credentials; request shape, safe env-based extra-header expansion, and local-compatible paths are tested.
- Stage 1 now connects direct helper calls and conservative C ops/vtable callbacks, but it is not a full clangd/libclang callgraph implementation. Generic `funcs/ops/callbacks` receivers connect only when the same slot has a single known callback candidate; otherwise the extractor leaves the deterministic callback edge absent instead of overlinking every same-slot callback.
- Provider embeddings are partial for the final clean DB; they prove provider provenance and AQ09, not full semantic reranking.
- The optional live MCP runtime package is not installed, so runtime smoke is skipped while tool registration and tool functions are tested.
- Git commit/push evidence is reported in the final assistant response after the G11 gate runs, because the commit hash is only known after this document is staged.
