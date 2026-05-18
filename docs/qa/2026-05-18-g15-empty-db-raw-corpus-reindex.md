# G15 Empty DB Raw Corpus Re-index QA

Date: 2026-05-18

Status: pass with explicit residuals.

JSON artifact: `docs/qa/2026-05-18-g15-empty-db-raw-corpus-reindex.json`

## Scope

This run rebuilt the AMD workbench from raw source roots into fresh `/tmp` SQLite DBs. It did not reuse `data/asip.db`.

Source roots:

```text
mxgpu: /tmp/asip-mxgpu @ f603f87
linux-amdgpu: /tmp/asip-linux-amdgpu @ 6916d57, relative root drivers/gpu/drm/amd/amdgpu
amd-amdgpu-docs: docs/fixtures/amd-amdgpu-docs
config: configs/edge_cases/clean-amd-gemma4-e4b.json
```

## Empty DB Rebuilds

Two independent empty DB rebuilds completed with stable counts.

| DB | real | user | sys | documents | chunks | evidence | SQLite edges | files |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/tmp/asip-raw-reindex-20260518-161425/asip-1.db` | 506.75s | 405.94s | 59.93s | 124 | 21,884 | 860,516 | 39,199 | 1,349 |
| `/tmp/asip-raw-reindex-20260518-161425/asip-2.db` | 507.07s | 408.49s | 56.55s | 124 | 21,884 | 860,516 | 39,199 | 1,349 |

Source-type document counts:

```text
register 96
doc      20
code      7
pdf       1
```

The CLI index summary reported `edges=39233`, while the final SQLite `edges` table contained `39199`. The stable table count is used for graph verification; the summary/table reporting delta remains a small follow-up.

## Stage 2 Semantic Edge Debug

Provider settings saved into the temp DB:

```text
edge: ollama / gemma4:e4b / http://localhost:11434/api/chat / think:false
embedding: ollama / nomic-embed-text:latest / http://localhost:11434/api/embed
```

The first real Stage 2 batch exposed a schema bug: local/IP tokens such as `tmp`, `adapt`, and `GC` could be persisted as semantic endpoints. That violated the graph contract that entity nodes are function/register/doc-section/doc-box, while source/macro/local values belong in `attr`/provenance.

TDD fixes added:

```text
test_batch_semantic_edge_job_filters_provider_local_variable_endpoints
RED 1: summary edge_count was 3 instead of 1 because tmp/GC persisted.
RED 2: summary edge_count was 2 instead of 1 when GC appeared in candidate TERMS.
GREEN: provider prompt no longer includes GC as a TERMS endpoint, persisted semantic edges filter tmp/adapt/GC.

test_index_registered_corpus_skips_ambiguous_returned_table_aliases
RED: duplicate select_funcs() definitions overlinked common_hw_init to both gfx and sdma callbacks.
GREEN: returned-table aliases are only used when the callee maps to one table.

test_query_evidence_reports_provider_query_embedding_fallback_metadata
RED: provider query embedding fallback metadata was not exposed for lexical-only rows.
GREEN: query responses include top-level query_embedding metadata without the vector payload.

test_query_evidence_does_not_compare_fallback_query_vector_to_provider_vectors
RED: provider query embedding failure could still compare the deterministic query vector to stored provider vectors.
GREEN: fallback query vectors only use deterministic/deterministic-fallback stored vectors.
```

## Fixed Stage 2 Re-run

The fixed rerun used `/tmp/asip-raw-reindex-20260518-161425/asip-2-filtered-rerun.db`, copied from the second raw rebuild with previous semantic rows cleared.

| Operation | Provider | Result | real |
| --- | --- | --- | ---: |
| `semantic-edges --q GCVM_L2_CNTL --limit 4` | `ollama/gemma4:e4b` | `edge_count=1`, job 2 | 49.43s |
| `doc-nodes-batch --limit 1 --batch-size 1` | `ollama/gemma4:e4b` | `box_count=6`, `edge_count=11`, job 4 | 57.36s |
| `semantic-edges-batch --limit 2 --batch-size 1` before prompt TERM filtering | `ollama/gemma4:e4b` | failed, no persistable edges | 78.13s |
| `semantic-edges-batch --limit 2 --batch-size 1` after prompt TERM filtering | `ollama/gemma4:e4b` | `edge_count=1`, job 5 | 110.11s |

Final semantic rows include:

```text
regGCVM_L2_CNTL reads  GCVM_L2_CNTL  mode=query
regGCVM_L2_CNTL writes GCVM_L2_CNTL  mode=batch
README.md#gim contains_box README.md#box-*
README.md#box-gim is_responsible_for README.md#box-*
```

Endpoint audit:

```text
bad semantic endpoints tmp/adapt/GC: 0
invalid macro/local endpoints tmp/adapt/GC/WREG32/RREG32/REG_SET_FIELD/SOC15_REG_OFFSET: 0
```

The endpoint-filter regression tests additionally cover underscore local/macro
tokens such as `IP_VERSION`, `tmp_value`, and `init_func`.

Fixed full graph export:

```text
nodes=14404
edges=31512
node kinds: function=12255, register=2142, doc_box=6, doc_section=1
visible stages: deterministic=31497, semantic=11, evidence=4
bad graph nodes tmp/adapt/GC/WREG32/RREG32/REG_SET_FIELD/SOC15_REG_OFFSET: 0
graph --all real=6.34s
```

The persisted SQLite table has 13 semantic rows; the graph export shows 11 semantic edges because the product graph normalizes/deduplicates query/batch read/write edges against deterministic graph structure.

## Real Queries

All queries ran against the fixed temp DB with `--limit 24`.

| ID | Query | Rows | Top hit | Time | Note |
| --- | --- | ---: | --- | ---: | --- |
| Q1 | Who reads or writes `regGCVM_L2_CNTL`? | 24 | `regGCVM_L2_CNTL`, `gfx_v11_0.c:322` | 2.66s | strong |
| Q2 | Which fields of `GCVM_L2_CNTL` enable L2 cache? | 24 | `ENABLE_L2_CACHE`, `gfx_v11_0.c:322` | 0.79s | strong |
| Q3 | Where is `IH_RB_CNTL` configured and which fields are modified? | 24 | `IH_RB_CNTL`, `mi200_irqmgr.c:323` | 5.10s | strong |
| Q4 | Which code paths reference `SDMA0_QUEUE0_RB_CNTL` or `SDMA1_QUEUE0_RB_CNTL`? | 24 | `SDMA0_QUEUE0_RB_CNTL`, `navi32_sdma.c:146` | 0.61s | strong |
| Q5 | Show evidence connecting amdgpu documentation to the amdgpu driver source tree. | 24 | `AMDGPU_NUM_VMID`, `gfx_v10_0.c:5225` | 0.56s | weak ranking |
| Q6 | Explain `WREG32_SOC15 regGCVM_L2_CNTL` macro expansion chain. | 24 | `AFID`, docs row | 0.57s | weak ranking |
| Q7 | Which callbacks or common helpers reach registers through amdgpu IP function tables? | 24 | `AMDGPU_RING_TYPE_GFX`, `gfx_v10_0.c:3845` | 0.56s | weak ranking |
| Q8 | Which `RLC_FED_DRVR_STATUS` field is set and waited on? | 24 | `regRLC_FED_DRVR_STATUS`, `navi32_reset.c:1322` | 0.65s | strong despite queryId heuristic mismatch |
| Q9 | Which register offset table maps `GC_HWIP` to `GC_BASE`? | 24 | `GC_BASE`, `mi200_reg_init.c:37` | 0.70s | strong |
| Q10 | Which `GRBM_SOFT_RESET` field is written when resetting RLC? | 24 | `GRBM_SOFT_RESET__SOFT_RESET_RLC_MASK` | 0.61s | strong |
| Q11 | Which `CP_INT_CNTL_RING0` interrupt enable fields are set? | 24 | `CMP_BUSY_INT_ENABLE`, `gfx_v10_0.c:5433` | 0.70s | strong |

This satisfies the "more than five real query" verification requirement, while also recording the weak ranking cases instead of calling them pass.

## Residuals

- Full clangd/libclang cross-TU vtable/type-flow extraction is still not implemented.
- Credentialed hosted OpenAI-compatible live QA is still not run.
- Semantic ranking quality remains a product-quality boundary; Q5-Q7 show weak ranking even though live rows return.
- The CLI index summary/table edge-count delta should be cleaned up.
- OCR for scanned PDFs remains outside this artifact.
