# G01 Real Ingestion And Indexing

Status: Partial; blocking until full code/docs/register/PDF AMD corpus acceptance is verified

## Requirement

ASIP MVP-1 must ingest real AMD GPU engineering corpora:

- Linux `drivers/gpu/drm/amd/amdgpu`
- `https://github.com/amd/MxGPU-Virtualization`
- aligned repo docs
- generated register headers
- at least one text-based AMD PDF

The index path must build ASIP evidence from raw inputs, not from an already generated QA artifact.

## Current Evidence

- `packages/core/src/asip/workbench.py` has `index_configured_corpora()` for raw corpus config indexing and `index_registered_corpora()` for user-added corpora.
- `packages/core/src/asip/storage.py` persists corpora, jobs, documents, chunks, FTS rows, evidence, edges, resolver profiles, provider settings, and embeddings metadata.
- `packages/core/tests/test_workbench_live.py` covers raw fixture indexing into SQLite, including code and PDF fixture evidence.
- `apps/web/app/api/workbench/index/route.ts` calls `python3 -m asip.cli index` and supports selected `corpusIds`.
- `apps/web/tests/workbench-api.spec.ts` covers default raw index and selected user corpus indexing.
- `configs/edge_cases/full-corpus-qwen35.json` and `full-corpus-gemma4-e4b.json` now include real MxGPU IH_RB_CNTL and SDMA queue acceptance-oriented queries.
- A temp SQLite verification against local `/tmp/asip-mxgpu` and `/tmp/asip-linux-amdgpu` produced non-empty evidence rows for `IH_RB_CNTL` and `SDMA0_QUEUE0_RB_CNTL SDMA1_QUEUE0_RB_CNTL`.
- Current full-corpus configs now include `**/*.c`, `**/*.h`, `**/*.md`, `**/*.rst`, and `**/*.pdf` globs for the configured AMD corpora.
- Registered-corpus indexing can convert docs/PDFs into chunks and create document-anchor evidence when no symbol-like code evidence is present.
- Configured raw-corpus indexing now keeps query-focused code/register snippets and additionally indexes doc/PDF files from include globs as full-file chunks, including files that do not match configured acceptance query terms.
- A real AMD MI300 PDF converter smoke produced page-preserving chunks outside the main index path; this proves extraction feasibility, not final indexed acceptance.
- The historical clean provider AQ01-AQ09 artifact passed the older runner matrix, but all nine query rows reported `source_types: ["code"]`. This means it proved live query mechanics/provider plumbing, not final multi-source ingestion closure.
- Current code now classifies generated register-header-style files such as `*_offset.h`, `*_sh_mask.h`, `*_d.h`, and paths under `asic_reg`/`register*` as `source_type: "register"`, and configured indexing includes those register headers in the non-query supplemental pass.
- Source-gated acceptance rerun `docs/qa/2026-05-17-acceptance-clean-qwen35-source-gated-current.json` and `.md` correctly marks the old `/tmp/asip-acceptance-clean-2026-05-17.db` as failed: `mxgpu` is still `indexing`, index job 3 failed, and AQ05 is missing `pdf`.
- Synthetic multi-source fixture acceptance `docs/qa/2026-05-17-acceptance-multisource-fixture.json` and `.md` proves the current gate can pass when the index actually contains multiple source classes: `/tmp/asip-multisource-clean-2026-05-17.db` has `documents` counts `code=1`, `doc=1`, `pdf=1`, `register=2`, and `evidence` counts `code=23`, `doc=3`, `pdf=4`, `register=4`. AQ05 passes with `code`, `doc`, `pdf`, and `register`; AQ06 passes with `code` and `register`.
- Clean AMD verification now exists at `/tmp/asip-clean-amd-gemma4-provider-2026-05-17-final.db` with `documents=124`, `chunks=21884`, `evidence=860516`, `edges=10019`, and `embeddings=32`. Document source counts are `code=7`, `doc=20`, `pdf=1`, `register=96`; evidence source counts are `code=126`, `doc=5664`, `pdf=5`, `register=854721`.
- Final current acceptance artifact `docs/qa/2026-05-17-acceptance-clean-amd-gemma4-provider-current.json` and `.md` records AQ01-AQ09 as `9 passed, 0 partial, 0 failed` against that clean AMD DB with DB health pass and `gemma4:e4b` semantic-edge provider smoke.

## Remaining Gap

The first live slice now has real SQLite indexing for MxGPU/Linux snippets plus configured docs/PDF/register sources, and the clean AMD DB proves code, docs, generated register headers, and a reduced AMD amdgpu PDF fixture in one repeatable CLI/core path. The old clean provider AQ pass remains superseded because its recorded source diversity is code-only, while the new clean AMD provider artifact is the current acceptance evidence.

The configured raw-corpus path deliberately remains query-focused for code sources and supplemental for docs/register/PDF to avoid unbounded symbol evidence explosions; full all-file code indexing still needs a more selective parser/indexer before it can close G15. Final Web/API/browser closure still needs visual QA and product-surface review.

Final closure must link to [Final Clean Evidence Package Gate](2026-05-17-final-clean-evidence-package.md) and include real source roots, DB health, source-type counts, query evidence, graph counts, provider state, visual QA, and performance.

## Acceptance Criteria

- A corpus config can be indexed without editing code.
- Indexing scans source files, docs, register headers, and text-based PDFs directly.
- Indexing creates job status records and durable corpus/document/chunk/evidence/graph state.
- Re-running indexing is deterministic for fixtures and does not silently delete unrelated local state.
- Web `Run index`, FastAPI, and MCP use this path or truthfully report that indexing is unavailable.
- Final QA records the actual AMD source roots used for Linux `amdgpu`, `amd/MxGPU-Virtualization`, docs, generated headers, and PDF.

## Required Tests

- Core integration test: fixture corpus indexing from raw files produces documents, chunks, symbols/evidence, and graph edges.
- Core integration test: source fixture plus PDF fixture indexes without network access.
- Core integration test: registered doc and PDF corpus text becomes queryable evidence without symbol-like code identifiers.
- Core integration test: configured include globs index non-query doc/PDF files into queryable evidence.
- Core integration test: generated register headers are classified and queried as `source_type: register`. Implemented in `test_generated_register_headers_are_indexed_as_register_source_type`.
- Web API/E2E test: `Run index` creates or updates a real index job and shows resulting status.
- Real AMD smoke: default config produces nonzero code/doc/register/PDF evidence counts and records source roots.

## Not Closed Until

The product query path reads from the index generated by this ingestion pipeline, and the final QA doc shows the AMD corpus inputs and resulting counts.
