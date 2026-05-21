# G08 PDF And Document Ingestion

Status: Current pass verified for indexed PDF evidence, page provenance, and historical browser/API raw `pdf_section` proof; 2026-05-19 product output projects document subtypes to `kind=doc` with `attr.doc_kind`

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
- Current clean-final default-corpus QA proves indexed PDF evidence in the Web query path.
- The historical clean provider AQ01-AQ09 artifact passed the older runner matrix, but every query reported `source_types: ["code"]`; it does not prove PDF or documentation evidence appears in retrieval.
- Source-gated acceptance rerun `docs/qa/2026-05-17-acceptance-clean-qwen35-source-gated-current.json` and `.md` now correctly fails AQ05 with `required source types missing: pdf` against the old clean DB.
- Synthetic multi-source fixture acceptance `docs/qa/2026-05-17-acceptance-multisource-fixture.*` proves PDF evidence can enter the same acceptance query path as code/doc/register. AQ05 source types include `pdf`, and the fixture DB has PDF evidence with `page=1` symbols `AMDGPU`, `ENABLE_L2_CACHE`, `GCVM_L2_CNTL`, and `PDF`.
- A targeted Web smoke test asserts evidence rows can expose source type and PDF page citation in the table/inspector, and the clean-final browser QA now proves the same path against the default workbench corpus.
- Reduced AMD amdgpu documentation fixture `docs/fixtures/amd-amdgpu-docs/amdgpu-driver-source-tree.md` and `.pdf` is included in `configs/edge_cases/clean-amd-gemma4-e4b.json`.
- `packages/core/tests/test_documents.py` now verifies that the reduced AMD PDF fixture is extractable and that ReportLab `/ASCII85Decode` + `/FlateDecode` PDF streams can be decoded by the fallback extractor when `pypdf`/MarkItDown are unavailable.
- Clean AMD DB `/tmp/asip-clean-amd-gemma4-provider-2026-05-17-final.db` contains `documents` source count `pdf=1` and `evidence` source count `pdf=5`; AQ05 passes with `code`, `doc`, `pdf`, and `register` in `docs/qa/2026-05-17-acceptance-clean-amd-gemma4-provider-current.json`.
- 2026-05-17 continuation fix: documentation/PDF queries now preserve at least one matching source row per source type before the candidate cap, so the AMD PDF row is not starved by higher-scoring code/register rows.
- 2026-05-17 targeted graph tests proved Markdown/document chunks can create historical raw `doc_section` graph facts and `section_mentions` edges. The 2026-05-19 product graph contract now projects those document subtypes to `kind=doc` with `attr.doc_kind`, and batch semantic-edge QA proves document candidates can feed the LLM edge job.
- 2026-05-17 semantic endpoint hardening proved a Stage 2 provider can return a document-section endpoint such as `docs/guide.md#programming-local-registers`. That older raw/debug evidence used `kind=doc_section`; the current 2026-05-19 product graph contract projects it to `kind=doc` with `attr.doc_kind=markdown_section`.
- 2026-05-17 PDF section provenance hardening now proves a PDF-derived graph node such as `docs/manual.pdf#page-3` carries `source_type=pdf`, `path`, `page`, `anchor`, and a user-facing label through the core graph payload.
- 2026-05-17 BoxMatrix-style doc-node extraction now uses the configured LLM provider call to turn document chunks into self-contained `doc_box` nodes and relationships. This intentionally does not use a BoxMatrix skill; the provider prompt carries the box/matrix abstraction and stores provider/model/job provenance.
- 2026-05-18 clean-final PDF section QA proves the real default Web/API path can expose `amdgpu-driver-source-tree.pdf#page-1` with `attr.source[0].path=amdgpu-driver-source-tree.pdf` and `attr.source[0].page=1`. That artifact predates the 2026-05-19 projection and recorded the historical raw shape `kind=pdf_section`; current product output must expose the same endpoint as `kind=doc` with `attr.doc_kind=pdf_section`. Evidence is recorded in `docs/qa/2026-05-18-pdf-section-clean-final-qa.md`, with browser screenshot `docs/qa/browser/pdf-section-query-clean-final-3100-2k.png`.

## Remaining Gap

PDF support is functional for deterministic fixtures, a source-diverse synthetic fixture, a real converter-level AMD PDF smoke, and an indexed reduced AMD amdgpu PDF in the clean AMD DB. The current clean-final API and browser QA show the PDF page/source metadata to the user. Older artifacts show the raw `pdf_section` shape; current product graph output must show the same evidence as `kind=doc` with `attr.doc_kind=pdf_section`.

MarkItDown remains optional; `pypdf` is the declared page-preserving converter for MVP smoke coverage, with a stdlib fallback for simple and ReportLab-compressed text streams. The final acceptance path now has API and browser proof for PDF page/source citations through the product UI.

Document graph extraction is implemented for converted document chunks, heading/line/page section ids, PDF section provenance, and LLM-extracted BoxMatrix-style doc boxes. The remaining boundary is content depth: the reduced clean-final PDF is intentionally small and generic, so it proves page-aware ingestion and section rendering, while richer real AMD PDF coverage stays outside this slice unless a larger PDF corpus is added.

## Acceptance Criteria

- MarkItDown or the chosen converter is declared and installable, or the fallback is explicitly accepted as the MVP implementation. Current chosen declared converter is `pypdf`.
- At least one text-based AMD PDF fixture/candidate is converted with page metadata.
- PDF chunks enter SQLite documents/chunks/evidence.
- Query results can return PDF evidence with page citation.
- Web inspector displays PDF page/source metadata.
- Converted Markdown/PDF sections create product `doc` graph nodes with stable ids, `attr.doc_kind`, heading/page/source metadata, and section-to-symbol edges.
- LLM doc-node extraction can create self-contained document concept boxes and relationships from indexed chunks without using a skill.
- Batch semantic-edge generation can include document/PDF sections as candidates and persist section semantic edges with provider/model provenance.
- The final QA doc records whether PDF evidence came from a real AMD PDF, a reduced fixture generated from one, or an explicitly accepted local fallback.

## Required Tests

- Core test: indexing a PDF fixture creates PDF chunks with page metadata.
- Core test: pypdf multi-page extraction preserves page numbers.
- Integration test: PDF evidence appears in a query result.
- Core graph test: Markdown/PDF headings or page sections become graph nodes with provenance and connect to mentioned symbols.
- Semantic-edge test: a fake provider can generate an edge from a document section candidate and that edge appears in the global graph.
- Semantic-edge test: a provider-returned Markdown/PDF section endpoint remains a product `doc` node in the default global graph, with subtype stored in `attr.doc_kind`.
- Real AMD PDF smoke: text extraction succeeds on a small known AMD PDF or documented reduced fixture.
- UI/E2E test: PDF evidence row and page metadata are visible.

## Not Closed Until

PDF content can be queried through the same workbench query path as code/register/doc evidence, and the page citation is visible in the UI.
