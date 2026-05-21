# G13 MVP Boundary And Full-Spec Deferrals

Status: Partial; deferral ledger exists, final user acceptance of residual boundaries remains blocking

## Requirement

ASIP has both an MVP-1 design doc and a long-range full technical spec. Long-range items must be explicitly deferred so they do not become hidden, ambiguous completion failures.

## Current Evidence

- The MVP-1 design excludes full root-cause analysis, firmware deep modeling, runtime log reasoning, scanned-PDF OCR, and hidden hardware dependency inference.
- The full technical spec includes broader future areas such as graph databases, logs/traces, LLM causal reasoning, incremental indexing, security/ACL/project isolation, and richer deployment concerns.
- The current implementation is SQLite-first and Web/API/MCP oriented, matching MVP-1 more closely than the long-range architecture.
- The final-candidate QA package records residual boundaries for system-Python sqlite-vec fallback, credentialed OpenAI-compatible live QA, partial provider embeddings, OCR, and full all-code indexing.
- 2026-05-18 follow-up narrowed several previous residuals: G07 now has deterministic structured resolved-chain explanations, Web/MCP graph parity, and bundled-Python real MCP runtime smoke; G15 now has repeat deterministic graph rebuild timing over live AMD DB backups plus empty-DB raw timing for the current selective path; G06 now has full local temp-copy Ollama provider embedding coverage timing plus query-time provider rerank wiring. These do not close full clangd/libclang cross-TU vtable/type-flow, credentialed OpenAI-compatible live QA, production-scale semantic rerank quality, scanned-PDF OCR, or future full all-file code indexing beyond the current selective path.
- 2026-05-20 gate hardening: `asip residual-gate` now parses ledger rows that
  explicitly need acceptance and blocks partial acceptance where only some of
  those rows are listed in `accepted_residuals`. The current artifact
  `docs/qa/2026-05-20-residual-acceptance-gate.json` records
  `acceptance_required_rows` for hybrid retrieval semantic quality and
  provider/OpenAI-compatible live QA boundaries, and still blocks because
  explicit user acceptance has not been recorded.
- 2026-05-21 OpenAI-compatible live smoke narrows the provider residual:
  `docs/qa/2026-05-21-openai-compatible-live-smoke.json` proves the local
  Ollama OpenAI-compatible `/v1/embeddings` and `/v1/chat/completions`
  protocol paths with real live calls. This closes protocol compatibility
  evidence, but it does not prove a hosted credentialed OpenAI-compatible
  endpoint because no credentials have been supplied.
- 2026-05-21 semantic rerank quality evaluation narrows the hybrid-retrieval
  residual: `docs/qa/2026-05-21-semantic-rerank-quality-eval.json` confirms
  full current-DB provider embedding coverage (`147841 / 147841` chunks),
  AQ01-AQ09 live acceptance consistency across product surfaces, and explicit
  `provider-vector` participation in AQ05. The artifact is intentionally
  `partial` because it does not claim production semantic ranking quality
  across arbitrary future corpora.

## Remaining Gap

The repo now has a deferral ledger and a final-candidate residual-boundary list. The remaining gap is explicit user acceptance of the residual boundaries if they are to be treated as out of scope for this active goal.

## Deferral Ledger

| Spec area | MVP status | Current closest capability | User acceptance status | Completion rule |
| --- | --- | --- | --- | --- |
| Real AMD code/docs/register/PDF ingestion | MVP-1 | G01 and G08 track raw corpus plus text-based PDF ingestion. | Required by user. | Must close for MVP-1. |
| Hybrid retrieval over exact, resolver, FTS5, vector, graph, rerank | MVP-1 / partial | G02 and G09 track FTS retrieval, provider embeddings, provider query-time vector rerank wiring, vector fallback, graph expansion, and the 2026-05-21 AQ semantic quality proxy. | Required by user; rerank maturity not separately accepted. | Current evidence closes provider-vector wiring, full current-DB provider embedding coverage, and the AQ01-AQ09 quality proxy; production-scale semantic rerank quality across arbitrary future corpora remains a residual boundary needing acceptance or broader evaluation. |
| Configurable resolver profiles for Linux amdgpu, MxGPU, and toy Python | MVP-1 | G05 tracks config-driven resolver profiles and UI workflow. | Required by user. | Must close for MVP-1. |
| Embedding provider and optional semantic-edge provider via Ollama/OpenAI-compatible APIs | MVP-1 / partial | G06 tracks split provider settings, safe env-based extra headers, embedding calls/backfill, query-time provider rerank wiring, semantic-edge jobs, full default-DB provider embedding coverage, and live `gemma4:e4b`/`nomic-embed-text:latest` model QA. The 2026-05-21 OpenAI-compatible live smoke proves the local `/v1` compatible protocol path. | Required by user for embeddings; semantic-edge model support requested. | Local Ollama path, safe header expansion, full current-DB provider-vector coverage, query-time provider-vector wiring, semantic/doc-node provenance, and local OpenAI-compatible `/v1` live smoke are proven; hosted credentialed OpenAI-compatible live QA and broad production semantic quality remain residual boundaries needing acceptance, credentials, or implementation. |
| Web workbench and MCP as first-class surfaces | MVP-1 | G07, G16, and G17 track API/MCP/Web product surfaces. G07 now includes deterministic structured resolved-chain explanations, Web/MCP graph parity, and bundled-Python real MCP runtime smoke. | Required by user. | Product surface parity and real local MCP runtime smoke are implemented; external client interoperability beyond FastMCP construction/tool execution remains future deployment QA. |
| Global Obsidian-style weighted graph | Active branch requirement | G03 tracks global graph after user explicitly requested it. | Required by later user request. | Must close for this active goal. |
| Scanned PDF OCR/layout reconstruction | Deferred | G08 supports text-based PDF conversion only. | Not requested for MVP; MVP design excludes scanned-PDF OCR. | Out of MVP-1 unless user later supplies OCR requirement. |
| Full root-cause analysis / LLM causal reasoning | Out of MVP-1 | Retrieval returns evidence and relationship explanations only. | Out of MVP per design. | Must not be claimed complete. |
| Firmware deep modeling | Out of MVP-1 | Firmware references may be indexed as source evidence if present, but no deep firmware model is required. | Out of MVP per design. | Deferred. |
| Runtime log reasoning / trace correlation | Out of MVP-1 | No runtime log ingestion requirement for MVP-1. | Out of MVP per design. | Deferred. |
| Hidden hardware dependency inference beyond evidence-supported relationships | Out of MVP-1 | Graph relations must be evidence-backed. | Out of MVP per design. | Deferred. |
| Graph database backend beyond SQLite | Deferred | SQLite persists graph edges; NetworkX is runtime only. | MVP design chose SQLite-first. | Deferred unless SQLite cannot satisfy MVP tests. |
| Incremental indexing and large-scale cache invalidation | Deferred / partial | Current jobs can index and rebuild; deterministic rebuild/performance smoke is G15. | Not requested as full MVP capability. | Full incremental semantics deferred. |
| Full raw AMD re-index timing | Current selective path measured / broader scale deferred | G15 now has fixture rebuild, repeat deterministic graph rebuild timing, more than five query timings, full local temp-copy provider embedding backfill timing, and two empty-DB raw re-index timings for the current selective raw path. | User asked for real graph generation and tests; the current selective raw path is measured. Future full all-file code indexing would be a larger parser/indexer scope. | Broader all-file indexing scale remains deferred; the current path is no longer an unmeasured residual. |
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
