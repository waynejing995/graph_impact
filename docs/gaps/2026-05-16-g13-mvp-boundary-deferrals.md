# G13 MVP Boundary And Full-Spec Deferrals

Status: Partial; deferral ledger exists, final user acceptance of residual boundaries remains blocking

## Requirement

ASIP has both an MVP-1 design doc and a long-range full technical spec. Long-range items must be explicitly deferred so they do not become hidden, ambiguous completion failures.

## Current Evidence

- The MVP-1 design excludes full root-cause analysis, firmware deep modeling, runtime log reasoning, scanned-PDF OCR, and hidden hardware dependency inference.
- The full technical spec includes broader future areas such as graph databases, logs/traces, LLM causal reasoning, incremental indexing, security/ACL/project isolation, and richer deployment concerns.
- The current implementation is SQLite-first and Web/API/MCP oriented, matching MVP-1 more closely than the long-range architecture.
- The final-candidate QA package records residual boundaries for native sqlite-vec, credentialed OpenAI-compatible live QA, partial provider embeddings, optional live MCP runtime, OCR, and full all-code indexing.

## Remaining Gap

The repo now has a deferral ledger and a final-candidate residual-boundary list. The remaining gap is explicit user acceptance of the residual boundaries if they are to be treated as out of scope for this active goal.

## Deferral Ledger

| Spec area | MVP status | Current closest capability | User acceptance status | Completion rule |
| --- | --- | --- | --- | --- |
| Real AMD code/docs/register/PDF ingestion | MVP-1 | G01 and G08 track raw corpus plus text-based PDF ingestion. | Required by user. | Must close for MVP-1. |
| Hybrid retrieval over exact, resolver, FTS5, vector, graph, rerank | MVP-1 / partial | G02 and G09 track current FTS-first retrieval, provider embeddings, vector fallback, and graph expansion. | Required by user; rerank maturity not separately accepted. | Current evidence closes live retrieval; provider-vector rerank maturity remains a residual boundary needing acceptance. |
| Configurable resolver profiles for Linux amdgpu, MxGPU, and toy Python | MVP-1 | G05 tracks config-driven resolver profiles and UI workflow. | Required by user. | Must close for MVP-1. |
| Embedding provider and optional semantic-edge provider via Ollama/OpenAI-compatible APIs | MVP-1 / partial | G06 tracks split provider settings, embedding calls/backfill, semantic-edge jobs, and live qwen3.5/nomic model QA. | Required by user for embeddings; semantic-edge model support requested. | Local Ollama path is proven; credentialed OpenAI-compatible live QA remains a residual boundary needing acceptance or credentials. |
| Web workbench and MCP as first-class surfaces | MVP-1 | G07, G16, and G17 track API/MCP/Web product surfaces. | Required by user. | Must close for MVP-1. |
| Global Obsidian-style weighted graph | Active branch requirement | G03 tracks global graph after user explicitly requested it. | Required by later user request. | Must close for this active goal. |
| Scanned PDF OCR/layout reconstruction | Deferred | G08 supports text-based PDF conversion only. | Not requested for MVP; MVP design excludes scanned-PDF OCR. | Out of MVP-1 unless user later supplies OCR requirement. |
| Full root-cause analysis / LLM causal reasoning | Out of MVP-1 | Retrieval returns evidence and relationship explanations only. | Out of MVP per design. | Must not be claimed complete. |
| Firmware deep modeling | Out of MVP-1 | Firmware references may be indexed as source evidence if present, but no deep firmware model is required. | Out of MVP per design. | Deferred. |
| Runtime log reasoning / trace correlation | Out of MVP-1 | No runtime log ingestion requirement for MVP-1. | Out of MVP per design. | Deferred. |
| Hidden hardware dependency inference beyond evidence-supported relationships | Out of MVP-1 | Graph relations must be evidence-backed. | Out of MVP per design. | Deferred. |
| Graph database backend beyond SQLite | Deferred | SQLite persists graph edges; NetworkX is runtime only. | MVP design chose SQLite-first. | Deferred unless SQLite cannot satisfy MVP tests. |
| Incremental indexing and large-scale cache invalidation | Deferred / partial | Current jobs can index and rebuild; deterministic rebuild/performance smoke is G15. | Not requested as full MVP capability. | Full incremental semantics deferred. |
| Security, ACL, multi-project isolation, deployment hardening | Deferred | Local-first dev workbench only. | Not requested for local MVP. | Deferred unless required before sharing/deploying. |
| IP-XACT/SystemRDL/XML/YAML/Excel specialized ingestion | Deferred | Text/code/docs/PDF/register-header ingestion only. | Not requested for MVP. | Deferred; future adapters can reuse ingestion interfaces. |

## Acceptance Criteria

- A deferral table lists each relevant full-spec item, whether it is MVP-1, partial, deferred, or explicitly out of scope.
- Deferred items include rationale and the current closest implemented capability.
- The deferral table references the exact design/spec lines or sections used for the decision.
- User acceptance is recorded for any deferred item that might otherwise be interpreted as part of the active goal.

## Required Tests And Checks

- Documentation review checks the deferral table against `docs/specs/2026-05-16-asip-full-technical-spec.md`.
- Documentation review checks the active implementation against `docs/specs/2026-05-16-asip-mvp1-design.md`.
- Final QA includes a section named `MVP Boundary And Deferred Full-Spec Items`.

## Not Closed Until

The final review makes it obvious which full-spec features are implemented now, which are partial, and which are intentionally deferred.
