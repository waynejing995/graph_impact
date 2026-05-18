# ASIP Design Review Closure Matrix

Date: 2026-05-18

Status: current design-review evidence matrix; not a goal-complete claim while
G13 residual-boundary acceptance remains open.

## Scope

This matrix reconciles the original MVP-1 design goals in
`docs/specs/2026-05-16-asip-mvp1-design.md` and the AQ01-AQ09 acceptance
matrix with the current implementation evidence. It exists so the final review
does not rely on scattered `PASS` notes or historical qwen artifacts.

## MVP-1 Goals

| Goal | Design requirement | Current evidence | Residual or boundary |
| --- | --- | --- | --- |
| G1 | Ingest Linux `amdgpu`, `amd/MxGPU-Virtualization`, repo docs, generated register headers, and at least one text-based AMD PDF. | Clean artifact `/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db`; `docs/qa/2026-05-18-acceptance-clean-amd-gemma4-final-current.md`; `docs/qa/2026-05-18-clean-final-stage2-and-macro-qa.md`; `docs/qa/2026-05-18-g15-empty-db-raw-corpus-reindex.md`. Counts: `documents=124`, `chunks=21884`, `evidence=860516`; source types `code/doc/pdf/register` nonzero. | Future broader all-file indexing is deferred; current selective raw path and clean artifact are measured. |
| G2 | Normalize registers, fields, wrappers, macro chains, functions, doc sections, PDF sections, IP, and ASIC hints. | `docs/gaps/2026-05-16-g03-dynamic-weighted-graph.md`; `docs/qa/2026-05-18-clean-final-stage2-and-macro-qa.md`; `docs/qa/2026-05-18-g03-cross-repo-register-merge-qa.md`; resolver profiles in `configs/resolvers/*.yaml`; core tests for resolver/profile/register canonicalization. | Full clangd/libclang cross-TU type-flow remains residual; current Stage 1 uses conservative source-span plus selective Clang AST JSON hints. |
| G3 | Provide hybrid evidence retrieval across code, docs, PDFs, and register headers. | `docs/qa/2026-05-17-clean-amd-gemma4-free-query-and-edge-qa.md` records six non-empty free queries with `code/doc/pdf/register`; `docs/qa/2026-05-18-g03-real-query-graph-function-fallback-qa.md` records ten real query/graph checks; AQ01-AQ09 artifact records source types and graph counts. | Production semantic ranking quality remains residual; provider-vector wiring is proven separately in G06/G09 QA. |
| G4 | Explain relationships, resolved macro/wrapper chains, register-field relationships, and doc/code links. | `docs/qa/2026-05-18-g07-resolved-chain-and-parity-qa.md`; AQ06 in `docs/qa/2026-05-18-acceptance-clean-amd-gemma4-final-current.md`; graph QA documents for callback/call/register/doc links under `docs/qa/2026-05-18-g03-*.md`. | Evidence-supported relationships only; no hidden hardware dependency inference or full root-cause reasoning is claimed. |
| G5 | Expose Web UI and MCP as first-class product surfaces. | Web/API/MCP tests recorded in G10/G11; `docs/qa/2026-05-18-g07-real-mcp-runtime-smoke.md`; current 2K Web visual pack in `docs/qa/visual-qa-2026-05-18-final-web-pack/`; in-app browser graph screenshots under `docs/qa/browser/`. | External MCP client interoperability beyond FastMCP construction/tool execution is future deployment QA. |
| G6 | Keep resolver and model backends configurable, including local Ollama and OpenAI-compatible providers. | `docs/gaps/2026-05-16-g05-resolver-profiles.md`; `docs/gaps/2026-05-16-g06-provider-settings-ollama.md`; `docs/qa/2026-05-18-g06-query-time-provider-rerank-qa.md`; `docs/qa/2026-05-18-g06-full-provider-backfill-tempdb-qa.md`; UI/API/MCP settings tests. | Credentialed live OpenAI-compatible endpoint QA requires credentials or explicit local-compatible acceptance. |

## Acceptance Queries

| ID | Query focus | Current evidence | Status |
| --- | --- | --- | --- |
| AQ01 | Reads/writes for `regGCVM_L2_CNTL`. | Clean artifact: 24 rows, `code/register`, graph `95 nodes / 231 edges`; browser/global graph evidence in `docs/qa/browser/graph-cross-repo-register-default-2k.png`. | Pass |
| AQ02 | Fields of `GCVM_L2_CNTL` set in MxGPU `gfx_v11_0.c`. | Clean artifact: 24 rows, `code/doc/register`, graph `163 / 344`; resolver/profile field folding covered by G03/G05 tests. | Pass |
| AQ03 | `IH_RB_CNTL` configuration and modified fields. | Clean artifact: 24 rows, `code/doc/register`, graph `168 / 480`; cross-repo shared-register bridge QA proves linux-amdgpu and mxgpu connect through merged `IH_RB_CNTL`. | Pass |
| AQ04 | `SDMA0_QUEUE0_RB_CNTL` / `SDMA1_QUEUE0_RB_CNTL` code paths. | Clean artifact: 24 rows, `code/doc/pdf/register`, graph `151 / 246`. | Pass |
| AQ05 | amdgpu documentation to driver source tree evidence. | Clean artifact: 24 rows, `code/doc/pdf/register`; `docs/qa/2026-05-18-pdf-section-clean-final-qa.md` proves `pdf_section` page citation in API/browser. | Pass |
| AQ06 | `WREG32_SOC15` resolved register entity and macro expansion chain. | Clean artifact: 24 rows, `code/doc/register`, graph `95 / 231`; resolved-chain parity QA covers Web/MCP/entity explanation. | Pass |
| AQ07 | Change/add C/C++ wrapper profile without code changes. | Clean artifact passes; UI/API/MCP resolver profile add/validate/select/re-index proof is recorded in G05 and Web tests. | Pass with richer diagnostics deferred |
| AQ08 | Toy Python/non-macro resolver profile. | Clean artifact passes; `configs/resolvers/python-hw-symbols.yaml` and `toy-python.yaml` plus resolver tests prove non-macro profile support. | Pass |
| AQ09 | Ollama embedding/semantic edge and OpenAI-compatible switch without resolver code changes. | Clean artifact passes local Ollama provider checks: embedding `nomic-embed-text:latest`, semantic edge `gemma4:e4b`; OpenAI-compatible request shape and extra-header handling are tested. | Pass for local-compatible path; credentialed live OpenAI-compatible QA deferred |

## Current Verification Snapshot

Latest command evidence after the shared-register bridge pass:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v
Ran 236 tests in 38.406s
OK (skipped=2)

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest apps.api.tests.test_app apps.mcp.tests.test_tools apps.mcp.tests.test_server -v
Ran 47 tests in 47.150s
OK (skipped=1)

pnpm --filter web exec tsc --noEmit
passed

pnpm --filter web run lint
passed

pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts --reporter=list
15 passed (31.5s)

pnpm --filter web exec playwright test tests/workbench-api.spec.ts tests/workbench-smoke.spec.ts tests/visual-anchor-routes.spec.ts --reporter=list
90 passed (1.7m)
```

Current browser visual evidence:

- `docs/qa/visual-qa-2026-05-18-final-web-pack/`: six routes, dark and light screenshots, 2048 x 1280.
- `/graph` in that pack renders `graph edges: 3000`, `1000` visible nodes, and `1220` visible canvas edges in both themes.
- `docs/qa/browser/graph-cross-repo-register-default-2k.png`: default graph with cross-repo shared register bridge proof.
- `docs/qa/browser/graph-shared-register-2k.png`: in-app browser proof that the current graph accessibility summary exposes `shared registers 149`.

## Residual Boundaries

These are not silently omitted:

- Full clangd/libclang cross-TU callback/type-flow extraction.
- Credentialed live OpenAI-compatible provider QA.
- Production-scale semantic ranking quality and hosted-provider throughput.
- Scanned-PDF OCR/layout reconstruction.
- Runtime log reasoning, firmware deep modeling, root-cause analysis, hidden dependency inference.
- Security/ACL/multi-project deployment hardening.
