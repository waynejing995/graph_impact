# G08 PDF And Document Ingestion

Status: Markdown/doc section graph nodes verified; indexed PDF evidence exists; PDF-specific section browser proof remains a narrower residual

## Requirement

MVP-1 supports text-based PDF ingestion. PDF conversion may use MarkItDown or a similar pipeline and must preserve page metadata.

Converted PDF chunks must enter the same documentation/evidence path as Markdown, RST, and repo docs.

After conversion to Markdown/text chunks, documents must also provide graph structure. Headings, page anchors, and extracted sections should become section nodes with source/page/heading provenance. LLM semantic-edge generation can then operate on those section nodes to connect documentation concepts to code functions, registers, fields, and other section concepts.

## Current Evidence

- `packages/core/src/asip/documents.py` attempts page-preserving `pypdf` extraction, then MarkItDown import, then a simple text-based PDF extractor.
- `packages/core/requirements.txt` declares `pypdf>=4,<7`.
- `packages/core/tests/test_documents.py` covers a fake two-page `pypdf` reader and verifies page metadata is preserved.
- `packages/core/src/asip/workbench.py` includes `.pdf` in source extensions and calls `convert_pdf_to_chunks()` for registered corpus indexing.
- `packages/core/tests/test_workbench_live.py` verifies fixture PDF evidence enters query results with page metadata.
- `packages/core/tests/test_workbench_corpus_state.py` verifies registered `.rst` and `.pdf` text can become queryable doc/pdf evidence.
- `packages/core/tests/test_workbench_live.py` verifies configured include globs can index non-query Markdown/PDF files as queryable evidence.
- A converter-level smoke against AMD's public MI300 CDNA3 ISA PDF extracted 561 page chunks and first-page text containing `AMD Instinct MI300`.
- Current default full-corpus runs have not proven real indexed PDF evidence in the Web query path.
- The historical clean provider AQ01-AQ09 artifact passed the older runner matrix, but every query reported `source_types: ["code"]`; it does not prove PDF or documentation evidence appears in retrieval.
- Source-gated acceptance rerun `docs/qa/2026-05-17-acceptance-clean-qwen35-source-gated-current.json` and `.md` now correctly fails AQ05 with `required source types missing: pdf` against the old clean DB.
- Synthetic multi-source fixture acceptance `docs/qa/2026-05-17-acceptance-multisource-fixture.*` proves PDF evidence can enter the same acceptance query path as code/doc/register. AQ05 source types include `pdf`, and the fixture DB has PDF evidence with `page=1` symbols `AMDGPU`, `ENABLE_L2_CACHE`, `GCVM_L2_CNTL`, and `PDF`.
- A targeted Web smoke test now asserts evidence rows can expose source type and PDF page citation in the table/inspector, but final browser QA still needs to run against the real final corpus and visual anchors.
- Reduced AMD amdgpu documentation fixture `docs/fixtures/amd-amdgpu-docs/amdgpu-driver-source-tree.md` and `.pdf` is included in `configs/edge_cases/clean-amd-gemma4-e4b.json`.
- `packages/core/tests/test_documents.py` now verifies that the reduced AMD PDF fixture is extractable and that ReportLab `/ASCII85Decode` + `/FlateDecode` PDF streams can be decoded by the fallback extractor when `pypdf`/MarkItDown are unavailable.
- Clean AMD DB `/tmp/asip-clean-amd-gemma4-provider-2026-05-17-final.db` contains `documents` source count `pdf=1` and `evidence` source count `pdf=5`; AQ05 passes with `code`, `doc`, `pdf`, and `register` in `docs/qa/2026-05-17-acceptance-clean-amd-gemma4-provider-current.json`.
- 2026-05-17 continuation fix: documentation/PDF queries now preserve at least one matching source row per source type before the candidate cap, so the AMD PDF row is not starved by higher-scoring code/register rows.
- 2026-05-17 targeted graph tests now prove Markdown/document chunks create `doc_section` graph nodes and `section_mentions` edges. The graph renderer preserves `doc_section`/`pdf_section` node kinds, and batch semantic-edge QA proves document candidates can feed the LLM edge job.
- 2026-05-17 semantic endpoint hardening now proves a Stage 2 provider can return a document-section endpoint such as `docs/guide.md#programming-local-registers`, and the default global graph preserves it as `kind=doc_section`.
- 2026-05-17 PDF section provenance hardening now proves a PDF-derived graph node such as `docs/manual.pdf#page-3` carries `source_type=pdf`, `path`, `page`, `anchor`, and a user-facing label through the core graph payload.
- 2026-05-17 BoxMatrix-style doc-node extraction now uses the configured LLM provider call to turn document chunks into self-contained `doc_box` nodes and relationships. This intentionally does not use a BoxMatrix skill; the provider prompt carries the box/matrix abstraction and stores provider/model/job provenance.

## Remaining Gap

PDF support is functional for deterministic fixtures, a source-diverse synthetic fixture, a real converter-level AMD PDF smoke, and an indexed reduced AMD amdgpu PDF in the clean AMD DB. The old clean AQ runner pass is superseded by the source-gated failure artifact; the current clean AMD artifact is the first accepted indexed PDF evidence. G08 remains open until final API/UI/browser QA shows page/source metadata to the user.

MarkItDown remains optional; `pypdf` is the declared page-preserving converter for MVP smoke coverage, with a stdlib fallback for simple and ReportLab-compressed text streams. The final acceptance path still needs browser QA proving PDF page/source citations through API/UI.

The Web inspector and E2E path still need to prove PDF page/source metadata is visible to users.

Document graph extraction is implemented for converted document chunks, heading/line/page section ids, PDF section provenance, and LLM-extracted BoxMatrix-style doc boxes. The residual G08 risk is narrower: final browser proof still needs to isolate a real PDF-derived `pdf_section` node with page provenance from the final AMD corpus rather than only fixture-level core proof.

## Acceptance Criteria

- MarkItDown or the chosen converter is declared and installable, or the fallback is explicitly accepted as the MVP implementation. Current chosen declared converter is `pypdf`.
- At least one text-based AMD PDF fixture/candidate is converted with page metadata.
- PDF chunks enter SQLite documents/chunks/evidence.
- Query results can return PDF evidence with page citation.
- Web inspector displays PDF page/source metadata.
- Converted Markdown/PDF sections create graph section nodes with stable ids, heading/page/source metadata, and section-to-symbol edges.
- LLM doc-node extraction can create self-contained document concept boxes and relationships from indexed chunks without using a skill.
- Batch semantic-edge generation can include document/PDF sections as candidates and persist section semantic edges with provider/model provenance.
- The final QA doc records whether PDF evidence came from a real AMD PDF, a reduced fixture generated from one, or an explicitly accepted local fallback.

## Required Tests

- Core test: indexing a PDF fixture creates PDF chunks with page metadata.
- Core test: pypdf multi-page extraction preserves page numbers.
- Integration test: PDF evidence appears in a query result.
- Core graph test: Markdown/PDF headings or page sections become graph nodes with provenance and connect to mentioned symbols.
- Semantic-edge test: a fake provider can generate an edge from a document section candidate and that edge appears in the global graph.
- Semantic-edge test: a provider-returned Markdown/PDF section endpoint remains a section node in the default global graph.
- Real AMD PDF smoke: text extraction succeeds on a small known AMD PDF or documented reduced fixture.
- UI/E2E test: PDF evidence row and page metadata are visible.

## Not Closed Until

PDF content can be queried through the same workbench query path as code/register/doc evidence, and the page citation is visible in the UI.
