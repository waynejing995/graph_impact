# Final-Candidate Evidence Package

Generated: 2026-05-17
Status: Current final-candidate evidence with explicit residuals; this document is not a goal-complete claim

2026-05-20 supersession note: the latest current-default gate is
`docs/qa/2026-05-20-current-goal-completion-audit.md` plus
`docs/qa/2026-05-20-browser-gate-preflight.json`,
`docs/qa/2026-05-20-provider-gate-preflight.json`, and
`docs/qa/2026-05-20-acceptance-data-asip-expanded.md`. The browser/provider
results below remain final-candidate or historical evidence; they do not close
the current expanded `data/asip.db` gate while browser listen and live provider
calls are blocked.

## Evidence Classes

This package intentionally separates three evidence classes:

- Clean AMD DB evidence: `/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db` is the current final clean artifact. It proves clean source-diverse indexing, current deterministic graph rebuild, real `gemma4:e4b` batch semantic edges, real `gemma4:e4b` doc-node extraction, AQ01-AQ09 acceptance, and provider smoke. `/tmp/asip-clean-amd-gemma4-provider-2026-05-17-final.db` remains the previous clean base artifact.
- Default Web DB evidence: local `data/asip.db` was reset to the clean-final DB for the G01/G10 gate, then intentionally rebuilt for the latest G03 typed-callback graph QA. It is now the live workbench graph DB, not the byte-identity acceptance artifact. The named clean artifact `/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db` remains the stable clean acceptance reference.
- Historical dirty dev DB evidence: earlier local `data/asip.db` snapshots proved live `/graph`, query performance, browser QA, semantic/doc-node jobs, and UI paths while the graph-shape fixes were still landing. Those records are retained below as development history and must not be read as the current default DB state.
- Fixture evidence: small fixture rebuilds and isolated DB tests prove regression behavior, performance smoke, provider/API/MCP/UI slices, and error paths. They cannot close real AMD corpus requirements alone.

## Current Clean AMD Database

- DB: `/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db`
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
| edges | 41893 |
| embeddings | 32 |

Document source counts: `code=7`, `doc=20`, `pdf=1`, `register=96`.

Evidence source counts: `code=126`, `doc=5664`, `pdf=5`, `register=854721`.

Provider embeddings are partial by design for this QA pass: `ollama/nomic-embed-text:latest`, `metadata.source=provider`, count `32`, fallback count `0`. Later G06 QA proves query-time provider-vector rerank wiring and a full local temp-copy provider backfill artifact; current clean/default DB coverage and semantic ranking quality remain G06/G09/G15 boundaries.

Bounded provider backfill smoke is recorded in
`docs/qa/2026-05-18-g06-provider-backfill-smoke.md` and `.json`: a SQLite
backup copy of live `data/asip.db` ran
`provider-embeddings --limit 128 --batch-size 8` through local Ollama
`nomic-embed-text:latest`, embedded `128` chunks in `17.703s`, and increased
provider embeddings from `32` to `160` in the temp DB. This proves the product
path and timing for a bounded batch, not full provider-vector coverage.

Full local temp-copy provider backfill is recorded in
`docs/qa/2026-05-18-g06-full-provider-backfill-tempdb-qa.md` and `.json`.
A backup copy of current `data/asip.db` ended with `21884 / 21884` chunks
covered by `ollama/nomic-embed-text:latest`, `missing_provider_embeddings=0`,
and `10770` long chunks carrying truncation metadata. The resumed full job
embedded `12572` remaining chunks in `2388.07s` after the previous failed job
exposed Ollama context-limit handling. This proves the product path can achieve
full local provider-vector coverage on a named temp DB. Later
`docs/qa/2026-05-18-g06-query-time-provider-rerank-qa.md` proves query-time
provider-vector wiring; credentialed OpenAI-compatible live QA and broad
semantic ranking quality remain residuals.

Clean-final artifact edge-table source counts after the 2026-05-18 clean-final rebuild and Stage 2 jobs:

```text
deterministic / clang_text_spans: 34987
deterministic / clang_callback: 6084
deterministic / text_fallback: 775
semantic / ollama: 25
evidence / query_expected_terms: 22
```

Clean-final artifact job ledger is clean. The `graph_rebuild` row reports the deterministic rebuild stdout count; the edge table also contains retained semantic/evidence rows from Stage 2 and QA overlays, so the table total is larger than this one job count:

```text
index indexed
embedding_backfill embedded
graph_rebuild succeeded, 41880 deterministic edges from 1225 files
semantic_edges_batch succeeded, 14 semantic edges from 2 candidates
doc_nodes_batch succeeded, 6 doc boxes and 11 semantic doc edges from 2 candidates
```

Macro/wrapper endpoint audit on the current clean DB:

```text
IP_VERSION=0
WREG32=0
RREG32=0
REG_SET_FIELD=0
SOC15_REG_OFFSET=0
funcs=0
ops=0
hw_init=0
```

Current product graph sample with the 2026-05-19 projection layer:

```text
global_graph(limit=20000)
nodes=14578
edges=20000
node kinds: doc=7, function=13878, register=693
doc kinds: boxmatrix_box=6, markdown_section=1
edge stages: deterministic=19989, semantic=11
visible bad node kinds: 0
visible macro/wrapper/provider/tmp nodes: 0
concept functions without resolver profile: 0
```

Stage 2 and macro QA: `docs/qa/2026-05-18-clean-final-stage2-and-macro-qa.md`.

Cross-repo shared-register graph QA:
`docs/qa/2026-05-18-g03-cross-repo-register-merge-qa.md` proves the default
`limit=3000` global graph includes `150` shared linux-amdgpu/mxgpu register
nodes and bridge edges from both repos into the merged
`register:IH:IH_RB_CNTL` node. The follow-up register identity pass also
records `ip_version` as attr/provenance instead of splitting register identity;
see `docs/qa/2026-05-18-g03-register-ip-version-merge-and-profile-qa.md`.

Semantic endpoint hygiene note: older raw `stage=semantic` rows from job 4 in
`data/asip.db` and the clean-final temp artifact still contain historical
provider endpoints such as `tmp`, `adapt`, and `GC`. The current product graph
export filters those endpoints out (`bad_nodes=0`, `bad_edges=0` in an
all-edge product graph check), and the empty-DB raw re-index QA proves new
Stage 2 generation no longer persists those endpoints. Do not cite the old raw
job 4 rows as clean semantic-edge proof.

Clean-final PDF section QA: `docs/qa/2026-05-18-pdf-section-clean-final-qa.md`
proves the default Web/API query path can expose
`amdgpu-driver-source-tree.pdf#page-1` with page provenance. That artifact
predates the 2026-05-19 product projection; current product graph output must
project the node as `kind=doc` with `attr.doc_kind=pdf_section`. Screenshot:
`docs/qa/browser/pdf-section-query-clean-final-3100-2k.png`.

## Acceptance

- Current artifact: `docs/qa/2026-05-19-acceptance-clean-amd-current.json`
- Current Markdown: `docs/qa/2026-05-19-acceptance-clean-amd-current.md`
- Previous clean-final artifact: `docs/qa/2026-05-18-acceptance-clean-amd-gemma4-final-current.json`
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

Latest real query graph QA is recorded in
`docs/qa/2026-05-18-g03-real-query-graph-function-fallback-qa.md` and `.json`.
It ran 10 CLI/core queries over
`/tmp/asip-provider-embed-batch-smoke-20260518-133434.db`; eight register/doc
queries returned rows plus graph neighborhoods, and two exact function-node
queries returned zero evidence rows but live graph neighborhoods from persisted
Stage 1 graph edges. The same artifact records a 3,000-edge global graph with
2,805 nodes in the pre-projection graph view. Current product graph output
must expose the document nodes as `kind=doc` with `attr.doc_kind` values such
as `boxmatrix_box` and `markdown_section`.

## Visual QA

- Historical route screenshot artifact: `docs/qa/visual-qa-2026-05-17/visual-qa.json`
- Markdown: `docs/qa/visual-qa-2026-05-17/visual-qa.md`
- Viewport: 2048 x 1280
- Routes: `/`, `/graph`, `/corpus`, `/resolver-profiles`, `/acceptance`, `/settings`
- Result: 6 passed, 0 failed
- Themes: dark and light screenshots captured for every route
- Historical `/graph` screenshot in that artifact: 12 nodes and 4 weighted edges visible in both themes before the later dense graph QA
- Fresh in-app browser QA at `http://127.0.0.1:3100/graph` after the clean-final DB was copied to `data/asip.db` and before later G03 typed-callback rebuilds: top bar shows `Edge: Ollama / gemma4:e4b`; `/graph` loads the live global graph with `3,000` graph edges, `1,000 / 2,883` visible nodes, `3,000 / 3,000` visible edges, rendered canvas edge count `1,132`, and layer provenance `deterministic: 2989 semantic: 11`. Browser artifacts: `docs/qa/browser/graph-clean-final-default-3100-2k.png` and `docs/qa/browser/graph-clean-final-default-3100-snapshot.json`. Document subtype labels in that snapshot are historical pre-projection labels.
- Fresh in-app browser snapshot after the cross-file common-helper fix shows the live `/graph` page with `Loaded edge budget 3000 / 20000`, `Visible nodes 1000 / 2797`, `Visible edges 3000 / 3000`, and the underlying full product graph sample below records `control-keyword function nodes named "if": 0`. Document subtype labels in that snapshot are historical pre-projection labels.
- Fresh in-app browser QA at `http://127.0.0.1:3100/` with source filter `pdf` and query `amdgpu documentation driver source tree PDF QA` shows one clean-final PDF result and inspector source `amdgpu-driver-source-tree.pdf page 1`. Browser artifact: `docs/qa/browser/pdf-section-query-clean-final-3100-2k.png`. Current product graph output projects the PDF endpoint as `kind=doc` with `attr.doc_kind=pdf_section`.
- Latest in-app browser QA after the full provider/static-cleanup/function-query slice shows `/graph` with `graph edges: 3000`, `layers deterministic: 2989 semantic: 11`, and `visible nodes: 1000 / 2805`; querying `gfx_v11_0_hw_init` shows `matches: 0` but `graph edges: 36` and live function-call relationships. Browser artifacts: `docs/qa/browser/graph-after-full-backfill-and-query-fallback-2k.png`, `docs/qa/browser/graph-after-full-backfill-and-query-fallback-deep-snapshot.md`, `docs/qa/browser/graph-function-query-fallback-2k.png`, and `docs/qa/browser/graph-function-query-fallback-2k-snapshot.md`.
- Latest in-app browser QA after the shared-register visibility fix shows
  `/graph` with `graph edges: 3000`, `nodes 1000`, `edges 1220`, and
  `shared registers 149` in the force-graph accessibility summary. Browser
  artifact: `docs/qa/browser/graph-shared-register-2k.png`.
- Latest six-route visual QA pack after the shared-register bridge pass is
  `docs/qa/visual-qa-2026-05-18-final-web-pack/visual-qa.md`, with dark and
  light screenshots for `/`, `/graph`, `/corpus`, `/resolver-profiles`,
  `/acceptance`, and `/settings` at `2048 x 1280`.

## Automated Verification

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v`: 239 tests OK, 2 sqlite-vec optional skips
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest apps.api.tests.test_app apps.mcp.tests.test_tools apps.mcp.tests.test_server -v`: 47 tests OK, 1 optional MCP runtime skip under system Python 3.9
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. /Users/chenjingwen/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest apps.mcp.tests.test_tools apps.mcp.tests.test_server -v`: 29 tests OK, 0 skips with real `mcp 1.27.1` runtime
- `pnpm --filter web run lint`: passed
- `pnpm --filter web exec tsc --noEmit`: passed
- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_storage_graph packages.core.tests.test_workbench_query_schema packages.core.tests.test_workbench_backend_state -v`: 87 tests OK, 2 optional sqlite-vec extension skips
- `pnpm --filter web exec playwright test apps/web/tests/workbench-api.spec.ts --grep "acceptance API lists real qwen and gemma QA runs" --reporter=list`: 1 passed after updating the acceptance artifact listing assertion to include the 2026-05-19 clean current run.
- `pnpm --filter web exec playwright test apps/web/tests/workbench-smoke.spec.ts --grep "graph page runs (semantic edge generation|batch semantic edge generation|LLM document node extraction)" --reporter=list`: 3 passed, proving query/batch/doc-node graph actions preserve explicit URL `dbPath` in their POST body.
- `pnpm --filter web exec playwright test apps/web/tests/workbench-api.spec.ts apps/web/tests/workbench-smoke.spec.ts --reporter=list`: 82 passed
- `pnpm --filter web exec playwright test apps/web/tests/visual-anchor-routes.spec.ts --reporter=list`: 15 passed
- In-app browser current graph QA at 2048 x 1280: `docs/qa/browser/asip-graph-current-2026-05-19-2k.png` and `docs/qa/browser/asip-graph-current-2026-05-19-snapshot.md`.
- In-app browser current acceptance QA at 2048 x 1280: `docs/qa/browser/asip-acceptance-current-2026-05-19-2k.png` and `docs/qa/browser/asip-acceptance-current-2026-05-19-snapshot.md`.
- `pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts --reporter=list`: 15 passed
- `pnpm --filter web exec playwright test tests/workbench-api.spec.ts tests/workbench-smoke.spec.ts tests/visual-anchor-routes.spec.ts --reporter=list`: 90 passed
- `git diff --check`: passed
- Design review closure matrix:
  `docs/qa/2026-05-18-design-review-closure-matrix.md` maps ASIP MVP-1 G1-G6
  and AQ01-AQ09 to implemented evidence and residual boundaries.
- Latest continuation targeted slice covers semantic endpoint filtering, underscore local/macro endpoint rejection, ambiguous returned-table alias rejection, cross-file return-table alias, provider-vector query rerank, and provider fallback vector-space safety.
- Follow-up G08 PDF-section slice: `packages.core.tests.test_workbench_query_schema` 13 tests OK, and `pnpm --filter web exec playwright test tests/workbench-api.spec.ts -g "PDF section" --reporter=list` 1 passed.
- Follow-up G12 filter slice: `apps.api.tests.test_app.ApiAppTests.test_query_endpoint_applies_ip_and_asic_filters` and `apps.mcp.tests.test_tools.McpToolsTests.test_search_evidence_applies_ip_and_asic_filters` both passed after RED failures. Real clean-final QA shows `CP_INT_CNTL_RING0` changing from 20 mixed rows to 2 `CP/gfx_v10_0` rows with `ipBlock=CP`, 0 rows with `ipBlock=SDMA`, and browser evidence at 2048 x 1280. Details: `docs/qa/2026-05-18-g12-filter-surface-qa.md`; screenshot: `docs/qa/browser/g12-filter-cp-clean-final-3100-2k.png`.
- Follow-up G04 clean corpus flow slice: `pnpm --filter web exec playwright test tests/workbench-api.spec.ts -g "clean named DB" --reporter=list` and `pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts -g "corpus page adds indexes and queries" --reporter=list` both passed. The API test proves a clean named DB add/index/query graph payload for `g04-clean-docs`; the UI test proves graph and inspector evidence for a new local corpus while preserving default `data/asip.db` byte identity with `/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db` at the time of that QA. Later G03 typed-callback rebuilds intentionally changed the default live graph DB, so the named `/tmp/...final-current...db` remains the acceptance reference. Details: `docs/qa/2026-05-18-g04-clean-corpus-flow-qa.md`.

## Historical Dirty Dev DB Graph And E2E Verification

This section records pre-final development evidence from the previously dirty local `data/asip.db`. That DB was backed up to `/tmp/asip-dirty-dev-before-final-default-2026-05-18.db` before the clean-final DB was copied to the default workbench path. It is historical evidence only and must not be conflated with the current default `data/asip.db`, which is now the live graph workbench DB derived from and intentionally rebuilt after the clean-final artifact.

Provider settings at the time of the dirty-dev evidence:

```text
edge: ollama / gemma4:e4b at http://localhost:11434/api/chat
embedding: ollama / nomic-embed-text:latest at http://localhost:11434/api/embeddings
extra headers: {}
```

Historical dirty-dev graph jobs:

```text
graph_rebuild job 78: 43030 deterministic edges from 1225 files
typed callback receiver hints: 2220 edges with type_flow=clang_ast_json
graph_rebuild job 80: 41998 graph-rebuild edges after IP-block registration-flow filtering
ip_blocks version funcs table_alias edges: 14
ip_blocks version funcs dispatch candidates: 13
alias fallback mismatches: 0
semantic_edges job 43: gemma4:e4b, 6 raw semantic edges
semantic_edges job 44: gemma4:e4b, 5 raw semantic edges
doc_nodes_batch job 45: gemma4:e4b, 6 doc boxes and 11 doc semantic edges
```

Historical dirty-dev DB snapshot after later semantic/doc-node jobs:

```text
edges_total=41986
stage counts: deterministic=41964, semantic=22
source counts: clang_text_spans=35100, clang_callback=6084, text_fallback=780, ollama=22
clang_callback call_kind: vtable_dispatch=5996, vtable_callback=67, vtable_table_alias=21
clang_ast_json callback hints=2220
ip_blocks version funcs table_alias=14
ip_blocks version funcs dispatch=13
alias_fallback_mismatches=0
```

Current product graph sample:

```text
global_graph(limit=20000)
nodes=15239
edges=20000
current snapshot nodes=15170
current snapshot edges=20000
current snapshot components=261
current snapshot largest_component=9864
```

Query performance regression evidence:

```text
query_evidence(previous dirty data/asip.db, "doorbell interrupt disable")
before final fixes: 58.228s
after final fixes: 0.487s
rows=24
query graph nodes=32
query graph edges=37

2026-05-18 query-scoped graph performance fix:
  graph_for_rows expands multi-seed queries with one NetworkX build
  empty multi-seed graph fallback no longer rebuilds through expand_query_graph()
  no-edge storage path returns seed nodes instead of NameError
  callable symbol scan no longer recompiles regexes per evidence row

six dirty-DB real queries:
  Who reads or writes regGCVM_L2_CNTL?: 4.161s rows=24 nodes=102 edges=237
  GCVM_L2_CNTL: 3.845s rows=24 nodes=102 edges=237
  doorbell interrupt disable: 0.878s rows=24 nodes=230 edges=400
  amdgpu_device_ip_hw_init_phase1: 2.135s rows=24 nodes=65 edges=74
  nv_common_hw_init: 2.093s rows=24 nodes=211 edges=498
  SDMA0_QUEUE0_RB_CNTL: 2.084s rows=24 nodes=134 edges=213

AQ01 CLI/Web acceptance timing:
  CLI command total: 26.025s
  Web Playwright route: 26.3s
```

Fixture stable-count rebuild and smoke-query evidence:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src python3 -m asip.cli performance-smoke \
  --db /tmp/asip-performance-smoke-2026-05-18.db \
  --source-root docs/fixtures/performance-smoke \
  --query GCVM_L2_CNTL \
  --query IH_RB_CNTL \
  --query SDMA0_QUEUE0_RB_CNTL \
  --query CP_INT_CNTL_RING0 \
  --query 'interrupt ring buffer' \
  --max-query-seconds 1.0 \
  --output-json docs/qa/2026-05-18-performance-smoke-fixture.json

primary rebuild: documents=2 chunks=2 evidence=19 edges=4 elapsed=0.053971s
repeat rebuild:  documents=2 chunks=2 evidence=19 edges=4 elapsed=0.042888s
deterministic_counts_match=true
five live queries: all returned rows and stayed under 1s
```

Later live `data/asip.db` snapshot repeat deterministic graph rebuild QA is recorded in
`docs/qa/2026-05-18-g15-real-corpus-repeat-graph-rebuild.md` and `.json`.
Two SQLite backup copies of live `data/asip.db` ran
`graph-rebuild --corpus-id linux-amdgpu --corpus-id mxgpu`. Run 1 took
`131.639s`, run 2 took `126.034s`; both processed `1225` files, rebuilt
`41923` deterministic edges, and ended with matching counts/source/relation
summaries, including final edge rows `41936` on each temp copy. These numbers
belong to the later live graph DB snapshot, not the named clean-final acceptance
artifact edge table above. Full raw re-index timing from an empty DB remains an explicit
long-running boundary.

Earlier automated verification from that historical dirty-dev graph pass:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v
Ran 206 tests in 11.789s
OK (skipped=2)

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest \
  apps.api.tests.test_app apps.mcp.tests.test_tools apps.mcp.tests.test_server -v
Ran 47 tests in 39.921s
OK (skipped=1)

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
  /Users/chenjingwen/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 \
  -m unittest apps.mcp.tests.test_tools apps.mcp.tests.test_server -v
Ran 29 tests in 19.002s
OK

pnpm --filter web exec tsc --noEmit
passed

pnpm --filter web exec playwright test tests/workbench-api.spec.ts tests/workbench-smoke.spec.ts --reporter=list
75 passed in 1.3m

pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts --reporter=list
15 passed in 28.0s

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

- Stage 1 callback dispatch now handles local table aliases, same-function field-path aliases, receiver-path type hints for common AMD fields such as `adev->gfx.rlc.funcs`, provable IP-block `.funcs` / `version->funcs` aliases, and selective Clang AST JSON receiver-type hints. Rebuild job 78 recorded `43,030` deterministic edges after multiline function parsing and AST JSON typed receiver extraction.
- Stage 1 now also uses corpus-level IP-block registration aliases for provable `amdgpu_device_ip_block_add(adev, &*_ip_block)` flows into common `adev->ip_blocks[i].version->funcs` dispatchers. Rebuild job 80 recorded `41,998` graph-rebuild edges; SQLite checks show `14` exact `ip_blocks version funcs` table-alias edges, `13` remaining lower-confidence dispatch candidates, and `0` alias fallback mismatches.
- Stage 1 typed callback precision follow-up now makes Clang AST JSON receiver type override generic `funcs` leaf fallback and resolves callback table initializers that reference uniquely known cross-file functions. Default `data/asip.db` rebuild job 6 recorded `41,923` deterministic graph-rebuild edges from `1,225` files; evidence is recorded in `docs/qa/2026-05-18-g03-typed-callback-rebuild-qa.md`.
- Stage 1 AST JSON callback-initializer follow-up now resolves macro-wrapped initializers such as `.hw_init = ASIP_CB(callback)` without making macro or slot names graph nodes. The latest live `data/asip.db` rebuild records `41,929` deterministic graph-rebuild edges, `41,942` total edges, `6,133` `clang_callback` rows, `2,248` typed callback rows, and `6` `callback_initializer_flow=clang_ast_json` rows. Evidence is recorded in `docs/qa/2026-05-18-g03-ast-json-callback-initializer-qa.md`.
- In-app browser `/graph` QA after the typed callback rebuild recorded `3000` graph edges, `deterministic: 2989 semantic: 11`, `1000 / 2883` visible nodes, `1133` rendered edges, and query `GCVM_L2_CNTL` with `24` matches, `231` graph edges, and `95` visible nodes in `docs/qa/browser/g03-typed-callback-global-graph-3100-2k.png` and `docs/qa/browser/g03-typed-callback-gcvm-query-3100-2k.png`.
- In-app browser `/graph` QA after job 80 recorded `3000` graph edges, `deterministic: 2987 semantic: 13`, `1000 / 2885` visible nodes, `1132` rendered edges, and relationship-panel evidence for `aldebaran_mode2_restore_ip -> nv_common_late_init` in `docs/qa/browser/graph-after-ip-block-registration-flow-2k.png`.
- In-app browser `/graph` QA after job 77 recorded `3000` graph edges, `deterministic: 2987 semantic: 13`, `1000 / 2865` visible nodes, and `1148` rendered edges in `docs/qa/browser/graph-after-ip-block-flow-fix-2k.png`.
- In-app browser `/graph` QA after job 78 recorded `3000` graph edges, `deterministic: 2987 semantic: 13`, `1000 / 2900` visible nodes, and `1101` rendered edges in `docs/qa/browser/graph-after-clang-ast-json-type-hints-2k.png`.
- Job lifecycle events remain semantically clean after resolver profile metadata updates: the stored events are `queued -> indexing -> succeeded`, not `queued -> indexing -> indexing -> succeeded`.
- `graph-rebuild --corpus-id` now preserves deterministic edges from non-selected corpora instead of clearing every Stage 1 edge.
- `/resolver-profiles` can load an existing YAML-backed profile into the editor before saving, so built-in profiles are editable through the UI path instead of being add-only rows.
- Top-bar global search runs a real `/api/workbench/query` request from graph-capable pages.
- Source-type filter controls are real query controls and send `sourceTypes` to the Web BFF/core query path.
- `/graph` exposes semantic generation limit and batch-size overrides in the UI and sends them to `/api/workbench/semantic-edges`.
- The graph header now displays layer provenance such as deterministic and semantic edge counts.
- G15 fixture performance smoke is now a product CLI path and core regression test; the QA artifact records matching empty-DB rebuild counts and five sub-second live queries. Real AMD repeat deterministic graph rebuild timing is recorded with stable counts; bounded provider backfill, full local temp-copy provider backfill, two empty-DB raw re-index timings, and edge-count summary/table counting are recorded. Broader future all-file indexing scale, hosted-provider throughput, and semantic ranking quality remain explicit residuals.
- G07 resolved-chain and parity follow-up is recorded in `docs/qa/2026-05-18-g07-resolved-chain-and-parity-qa.md`: evidence detail and entity explain now return deterministic structured `resolved_chain_explanation(s)`, and Web BFF/MCP parity covers query, evidence detail, entity, entity graph counts, and direct seed graph counts.
- G07 real MCP runtime smoke is recorded in `docs/qa/2026-05-18-g07-real-mcp-runtime-smoke.md`: bundled Python 3.12 with `mcp 1.27.1` runs MCP tool/server tests with 29 OK and 0 skips.

Clean AQ01-AQ09 provider acceptance is now represented by the `gemma4:e4b` artifact above. Historical qwen3.5 artifacts remain comparison/provenance evidence only, not current clean-provider closure. The historical dirty-dev graph section remains separate development evidence for persisted Stage 2 semantic/doc-node jobs before `data/asip.db` was copied from the clean-final artifact and later intentionally rebuilt as the live graph workbench DB.

## Architecture Review

| Capability | Owner | Evidence | Boundary |
| --- | --- | --- | --- |
| Corpus registration/indexing | core, Web BFF, API, MCP | `asip.workbench`, `asip.cli index`, API/MCP/Web tests | Full all-code parser deferred; current path is query-focused code plus supplemental docs/register/PDF |
| Document/PDF conversion | core | `asip.documents`, PDF tests, clean DB PDF counts | OCR/scanned PDF remains non-goal |
| Resolver profiles | core plus UI/BFF/API/MCP | resolver profile tests and UI/API smoke | Rich edit-in-place/per-job profile selection remains future work |
| Retrieval/evidence schema | core, thin app surfaces | clean AQ 9/9, six free queries, API/MCP/Web agreement tests, deterministic structured resolved-chain explanations, query-time provider-vector wiring QA | Semantic ranking quality and LLM-generated cross-evidence explanation remain boundaries |
| SQLite/FTS/vector | core storage | FTS/vector tests, provider embedding provenance, query-time provider-vector wiring QA, native sqlite-vec extension smoke in bundled Python runtime, native `search_vector()` adapter test, fallback adapter test | JSON vectors remain the durable source of truth; current-DB full provider-vector coverage and semantic rerank quality remain open |
| NetworkX graph | core storage/workbench | graph tests, free-query/global graph QA, visual `/graph` QA | Browser design polish still reviewed in G16 |
| Deterministic C graph/callgraph | core code graph plus storage/workbench | function-register operation tests, compile_commands macro test, direct helper call test, cross-file unique direct common-helper test, cross-file ops/vtable callback test, receiver type-hint callback test, returned-table alias test, Clang AST JSON typed receiver test, typed receiver over generic `funcs` fallback test, cross-file callback initializer test, same-slot overlink regression, real rebuild job 6 on default DB | Conservative source/span parser with bounded return aliases, selective Clang AST JSON receiver hints, and cross-file unique callee/callback indexing, not full clangd/libclang callback coverage |
| Semantic-edge generation | core plus CLI/Web/API/MCP | `gemma4:e4b` clean provider acceptance plus current live `gemma4:e4b` semantic/doc-node jobs and semantic-edge parity tests | Large prompts still need adequate `num_predict` and JSON robustness |
| Provider settings | core plus Settings UI/BFF/API/MCP | AQ09, provider tests, settings UI tests, bounded 128-chunk Ollama backfill smoke, full local temp-copy provider backfill, query-time provider-vector smoke | Credentialed OpenAI-compatible live QA and production-scale ranking quality require credentials/time or accepted local-compatible boundary |
| FastAPI | `apps/api` thin over core | API tests and live Uvicorn smoke | Optional deployment packaging not in MVP |
| MCP | `apps/mcp` thin over core | tool tests, server registration test, Web/MCP query/evidence/entity/graph parity, bundled-Python real MCP runtime smoke | External client interoperability beyond FastMCP construction/tool execution remains future deployment QA |
| React UI and visual anchors | `apps/web` React UI | Playwright smoke/API/visual tests and visual QA screenshots | Recapture required after future UI-affecting changes |

## Residual Boundaries

- Native sqlite-vec extension loading is skipped in system Python 3.9, and the bundled Python 3.12 runtime passes both the native sqlite-vec extension smoke and the native `search_vector()` adapter test. The adapter keeps JSON vectors as durable source of truth and falls back to Python cosine when sqlite-vec cannot load.
- Credentialed OpenAI-compatible live provider QA is not performed without credentials; request shape, safe env-based extra-header expansion, local-compatible paths, and bounded local Ollama provider backfill are tested.
- Stage 1 now connects direct helper calls, cross-file direct common-helper calls when the callee definition is unique, and conservative C ops/vtable callbacks, but it is not a full clangd/libclang callgraph implementation. Generic `funcs/ops/callbacks` and typed receivers such as `struct <type> *ops` emit lower-confidence dispatch-candidate edges, filtered by exact table name, callback table type, bounded returned-table alias, selective Clang AST JSON receiver type, or source-span alias hints where the extractor can prove them.
- Provider embeddings are partial for the final clean/live DB; they prove provider provenance, AQ09, bounded backfill behavior, and later query-time provider-vector wiring, not broad semantic ranking quality or guaranteed current-DB full vector coverage.
- The system Python 3.9 runtime cannot install the current `mcp` package because it requires Python 3.10+, but the bundled Python 3.12 runtime has `mcp 1.27.1` and passes MCP tool/server runtime smoke with 29 OK and 0 skips.
- Git commit/push evidence is reported in the final assistant response after the G11 gate runs, because the commit hash is only known after this document is staged.
