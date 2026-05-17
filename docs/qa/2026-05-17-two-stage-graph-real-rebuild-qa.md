# Two-Stage Graph Real Rebuild QA

Date: 2026-05-17
Status: Fresh real-data verification for the graph correction slice; not a full G01-G17 closure.

Update after latest graph-shape review: the real-data rebuild evidence below is still useful for proving Stage 1 and Stage 2 are real, but the visible graph node contract has changed. A passing product graph must now hide macro/wrapper/field/source-path noise as nodes and expose only function, register, document section, PDF section, and document box nodes with BoxMatrix-style `in`, `out`, and `attr` payloads.

## Scope

This run verifies the corrected graph architecture:

1. Stage 1 deterministic code graph: source-code extraction writes `edges.stage = deterministic` from clang AST/preprocess/text-fallback paths.
2. Stage 2 semantic overlay: Ollama `gemma4:e4b` writes `edges.stage = semantic` after Stage 1 has indexed candidates.

Evidence/query-term overlays are not counted as Stage 1.

## Real Rebuild

Command:

```bash
PYTHONPATH=packages/core/src:. python3 -m asip.cli index \
  --config configs/edge_cases/full-corpus-qwen35.json \
  --db data/asip.db \
  --corpus-id mxgpu \
  --corpus-id linux-amdgpu
```

Result, job `22`:

- files: `1340`
- documents: `1340`
- chunks: `31353`
- evidence: `1300559`
- deterministic edges: `37921`
- duration: `7:00.02`

Index-time embedding backfill was intentionally disabled for this graph rebuild, then provider settings were restored afterward. The UI/provider config now shows edge `Ollama / gemma4:e4b` and embedding `Ollama / nomic-embed-text:latest`.

## Edge Provenance

Final edge counts in `data/asip.db`:

- `deterministic | clang_ast`: `37526`
- `deterministic | clang_preprocess`: `356`
- `deterministic | text_fallback`: `39`
- `semantic | ollama`: `3`

Real Stage 2 command:

```bash
PYTHONPATH=packages/core/src:. python3 -m asip.cli semantic-edges-batch \
  --db data/asip.db \
  --limit 1 \
  --batch-size 1
```

Result, job `23`: `Generated 3 semantic edges from 1 candidates`.

Semantic edges persisted:

- `gpu_buddy_block_state reads GPU_BUDDY_HEADER_STATE`
- `gpu_buddy_block_is_allocated reads GPU_BUDDY_ALLOCATED`
- `kunit_fail_current_test calls kunit_fail_current_test()`

The earlier `limit=5` real run failed because `gemma4:e4b` returned malformed nested/truncated JSON. Batch semantic-edge persistence is now atomic: partial edges are rolled back if a later batch/provider call fails.

## Real Queries

Seven real queries were run after the rebuild:

| Query | Rows | Graph nodes | Graph edges | Notes |
| --- | ---: | ---: | ---: | --- |
| `GCVM_L2_CNTL` | 24 | 26 | 96 | Top hits in `gfxhub_v11_5_0.c` and `gfxhub_v12_0.c`. |
| `ENABLE_L2_CACHE` | 24 | 54 | 52 | Top hits in gfxhub cache setup code. |
| `BIF_DOORBELL_INT_CNTL DOORBELL_INTERRUPT_DISABLE` | 24 | 21 | 22 | Top hits in MxGPU NBIO source. |
| `SOFT_RESET_CP` | 24 | 14 | 31 | Top hits in Linux amdgpu gfx reset code. |
| `INVALIDATE_CACHE` | 24 | 28 | 26 | Includes flush/invalidate cache variants. |
| `VMID CACHE_POLICY EXE_DISABLE` | 24 | 18 | 19 | Query still ranks `ATC_VMID0` highly; multi-term ranking remains a follow-up. |
| `gpu_buddy_block_state GPU_BUDDY_HEADER_STATE` | 24 | 5 | 2 | Shows the generated semantic edge path. |

## Browser QA

In-app browser at `http://127.0.0.1:3100/graph`, viewport `2048x1280`:

- Provider text includes `Edge: Ollama / gemma4:e4b`.
- Provider text does not include `qwen`.
- Force graph present: `true`.
- Canvas present: `true`.
- Canvas size: `1172x727`.
- Painted pixel probe: `3001`.
- UI graph counts after raising the default global graph payload to `3000` edges: `1000 / 1299` visible nodes, `3000 / 3000` visible edges, with `2719` links rendered after the visible-node cap.
- Node mix shown in UI: `code 624`, `field 118`, `register 258`.
- Screenshot: `docs/qa/visual-qa-2026-05-17-graph-semantic/asip-graph-two-stage-2k-final.png`.

This node mix is now explicitly stale for product closure. The presence of `field` and generic `code` node buckets proves the graph still needs the latest BoxMatrix-style normalization pass. Future browser QA must assert that the product graph node kinds are limited to `function`, `register`, `doc_section`, `pdf_section`, and `doc_box`, and that fields/macros/source paths appear only in node `attr` or edge provenance.

Post-fix QA after shared graph-budget and resolver mega-node cleanup:

- `asip.cli graph --db data/asip.db --limit 3000`: `1389` nodes, `3000` edges, wrapper nodes `[]`.
- `asip.cli graph --db data/asip.db --all`: `12285` nodes, `22639` edges. Full graph output is now explicit instead of a hidden CLI default.
- In-app browser `/graph` at `2048x1280`: `data-ready=true`, `nodeCount=1000`, `edgeCount=2629`, `nodeTotal=1389`, `edgeTotal=3000`.
- Browser text includes `Edge: Ollama / gemma4:e4b`, includes the `Loaded edge budget` slider, and contains none of `WREG32`, `REG_SET_FIELD`, `SOC15_REG_OFFSET`, `amdgv_wreg32`, or `gpu_register` as visible graph nodes.

Post-fix QA after resolver-operator seed/evidence/UI hardening:

- Core targeted tests prove `REG_SET_FIELD` is rejected as a graph seed, resolver operators are skipped from query `expected_terms`, stale `REG_SET_FIELD` evidence rows are filtered out of query output, and project-local macros expanded through `compile_commands.json` produce `clang_preprocess` register edges with the original source line.
- Web API targeted test proves `/api/workbench/graph?seed=REG_SET_FIELD` returns an empty graph with a resolver-operator empty state.
- Web smoke targeted tests prove Resolver Profiles rows show profile ids and operator counts, not wrapper names as symbol identities.

Post-fix QA after Acceptance provider-check detail hardening:

- Web API targeted test proves `/api/workbench/acceptance` preserves AQ09 artifact provider checks for embedding and semantic-edge provider/model/status.
- Web smoke targeted test proves the Acceptance detail accordion renders provider check status/provider/model/message inside expanded fail/partial query detail.

Post-fix QA after config-driven resolver-operator storage hardening:

- Core targeted test proves every committed resolver YAML wrapper/extractor, including `AMDGV_WRITE_REG`, `AMDGV_READ_REG`, `AMDGV_WAIT_REG`, and `gpu_register`, is classified as a resolver operator rather than a graph entity.
- Core targeted tests prove `AsipStore.add_edge()` rejects resolver-operator endpoints, legacy `expand_graph()` omits persisted dirty wrapper endpoints, and generated artifact import counts only persisted graph-entity edges.
- Core targeted test proves a provider-returned Markdown section endpoint is preserved as `kind=doc_section` in the default global graph.

Post-fix QA after BoxMatrix-style LLM document node extraction:

- GitHub reference checked: `waynejing995/BoxMatrix` describes Box as a self-contained unit and Matrix as the relationship network.
- Core targeted tests prove PDF section nodes preserve `source_type`, `path`, `page`, `anchor`, and label metadata in graph payloads.
- Core targeted tests prove `generate_doc_nodes_batch()` calls a provider prompt containing the BoxMatrix abstraction and `Do not use a skill`, then persists a `doc_box` node plus semantic edges.
- Web API targeted test proves `/api/workbench/semantic-edges` with `mode: "doc-nodes"` runs the CLI-backed LLM doc-node path and returns a `doc_box` node.
- Web smoke targeted test proves `/graph` exposes `Extract document nodes`, sends `mode: "doc-nodes"`, and refreshes the graph with the returned document box label.

## Tests

Fresh verification after code changes:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests python3 -m unittest discover packages/core/tests -v`: `120` tests, `OK`, `1` sqlite-vec skip.
- `pnpm --filter web exec playwright test tests/workbench-api.spec.ts tests/workbench-smoke.spec.ts --reporter=list`: `64 passed`.
- `pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts --reporter=list`: `15 passed`.
- `pnpm --filter web lint`: passed.
- `git diff --check`: passed.

## Remaining Limits

- Stage 1 is a pragmatic clang command plus resolver-profile/source-span pipeline. It is not yet a full kernel `compile_commands.json` or libclang-grade macro expansion with complete include context.
- Stage 2 is proven with a successful `gemma4:e4b` batch of one candidate. Larger batches still need prompt/JSON robustness work for this local model.
- Default global graph is weighted and real, but it still needs product-shape normalization: macro/wrapper/field/source-file endpoints must be removed from the rendered node set and folded into BoxMatrix-style `in`/`out`/`attr` payloads on function/register/doc nodes.
- The configured edge budget can still hide low-weight semantic/doc edges. The UI exposes loaded edge budget, visible node/edge, and minimum-weight controls, but ranking policy still needs product tuning.
- Document/PDF section nodes exist through explicit evidence overlay paths; default Stage 1/Stage 2 graph closure still needs stronger doc/PDF semantic-edge coverage.
- Provider embeddings are configured but were not backfilled during this graph rebuild.

## Superseding Current Run

The earlier counts in this document came from a larger dirty rebuild before the final entity-schema normalization. The current product-shape run on `data/asip.db` is:

```text
PYTHONPATH=packages/core/src python3 -m asip.cli graph-rebuild --db data/asip.db
source=deterministic_graph_rebuild
job_id=42
files=1225
edges=10108
```

Current Stage 1 edge table:

```text
deterministic|clang_ast|reads|2536
deterministic|clang_ast|writes|4955
deterministic|clang_ast|sets_field|995
deterministic|clang_ast|maps_base|1616
deterministic|clang_ast|field_shift|6
```

Current Stage 2 LLM overlay:

```text
semantic-edges job 43: provider=ollama model=gemma4:e4b evidence_rows=8 edge_count=6
semantic-edges job 44: provider=ollama model=gemma4:e4b evidence_rows=8 edge_count=5
doc-nodes-batch job 45: provider=ollama model=gemma4:e4b candidate_count=2 box_count=6 edge_count=11
```

Current product graph:

```text
global_graph(limit=1500)
nodes=1123
edges=1500
node kinds: function=523, register=593, doc_box=6, doc_section=1
visible semantic edges=15
```

Important nuance: raw provider rows from jobs 43/44 still include noisy local-variable endpoints such as `ih_ring_entry` and generic names such as `register`. The product graph filters invalid node kinds/endpoints, so these raw rows do not become field/macro/local-variable visual nodes. The visible graph evidence above is therefore the product-contract evidence, not merely the raw LLM output.

Fresh verification for this current run:

```text
core unittest discovery: 138 OK, 1 sqlite-vec skip
FastAPI/MCP unittest: 41 OK, 1 optional MCP runtime skip
TypeScript: passed
ESLint: passed
Web API + smoke Playwright: 65 passed
Visual anchor route Playwright: 15 passed
git diff --check: passed
```
