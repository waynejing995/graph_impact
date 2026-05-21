# G13 MVP Boundary And Full-Spec Deferrals

Status: Accepted; user accepted the remaining residual boundaries for the active goal and selected local Ollama gemma as the OpenAI-compatible provider path

## Requirement

ASIP has both an MVP-1 design doc and a long-range full technical spec. Long-range items must be explicitly deferred so they do not become hidden, ambiguous completion failures.

## Current Evidence

- The MVP-1 design excludes full root-cause analysis, firmware deep modeling, runtime log reasoning, scanned-PDF OCR, and hidden hardware dependency inference.
- The full technical spec includes broader future areas such as graph databases, logs/traces, LLM causal reasoning, incremental indexing, security/ACL/project isolation, and richer deployment concerns.
- The current implementation is SQLite-first and Web/API/MCP oriented, matching MVP-1 more closely than the long-range architecture.
- The final-candidate QA package records residual boundaries for system-Python sqlite-vec fallback, hosted OpenAI-compatible live QA, partial provider embeddings, OCR, and full all-code indexing.
- 2026-05-18 follow-up narrowed several previous residuals: G07 now has deterministic structured resolved-chain explanations, Web/MCP graph parity, and bundled-Python real MCP runtime smoke; G15 now has repeat deterministic graph rebuild timing over live AMD DB backups plus empty-DB raw timing for the current selective path; G06 now has full local temp-copy Ollama provider embedding coverage timing plus query-time provider rerank wiring. These do not close full clangd/libclang cross-TU vtable/type-flow, hosted OpenAI-compatible live QA, production-scale semantic rerank quality, scanned-PDF OCR, or future full all-file code indexing beyond the current selective path.
- 2026-05-20 gate hardening: `asip residual-gate` now parses ledger rows that
  explicitly need acceptance and blocks partial acceptance where only some of
  those rows are listed in `accepted_residuals`. The refreshed artifact
  `docs/qa/2026-05-20-residual-acceptance-gate.json` now records explicit
  acceptance for the hybrid retrieval semantic-quality boundary and the local
  Ollama OpenAI-compatible provider boundary.
- 2026-05-21 OpenAI-compatible live smoke narrows the provider residual:
  `docs/qa/2026-05-21-openai-compatible-live-smoke.json` proves the local
  Ollama OpenAI-compatible `/v1/embeddings` and `/v1/chat/completions`
  protocol paths with real live calls. This closes protocol compatibility
  evidence, but it does not prove a hosted credentialed OpenAI-compatible
  endpoint because no credentials have been supplied.
- 2026-05-21 hosted OpenAI-compatible readiness is executable through
  `python3 -m asip.cli openai-compatible-smoke --require-credentialed` when a
  hosted credential exists. In this run the user stated that no hosted
  `OPENAI_API_KEY` is available and selected local Ollama/gemma instead, so
  hosted-provider QA is deferred rather than treated as the active-goal path.
- 2026-05-21 completion-gate follow-up: the final aggregate gate now consumes
  that readiness artifact through `--hosted-openai-json` and exposes a
  first-class `hosted_openai_compatible` requirement. Credentialed hosted
  proof still passes this requirement, while local Ollama `/v1` compatible
  proof is accepted only when the residual artifact records explicit user
  acceptance of the local provider boundary.
- 2026-05-21 semantic rerank quality evaluation narrows the hybrid-retrieval
  residual: `docs/qa/2026-05-21-semantic-rerank-quality-eval.json` confirms
  full current-DB provider embedding coverage (`147841 / 147841` chunks),
  AQ01-AQ09 live acceptance consistency across product surfaces, and explicit
  `provider-vector` participation in AQ05. The artifact is intentionally
  `partial` because it does not claim production semantic ranking quality
  across arbitrary future corpora.
- 2026-05-21 provider-vector preservation QA further narrows the
  hybrid-retrieval residual: `docs/qa/2026-05-21-provider-vector-preservation-qa.md`
  records a regression fix for lexical/FTS candidate pressure and a real AQ05
  six-surface probe where `provider-vector` remains visible with code/doc/pdf/register
  source diversity.
- 2026-05-21 labeled semantic-quality eval further narrows the hybrid-retrieval
  residual: `docs/qa/2026-05-21-semantic-rerank-labeled-eval.json` passes
  `8/8` current-corpus cases over `docs/qa/semantic-rerank-eval-set.jsonl`,
  with two provider-vector cases, one graph-target case for the natural-language
  `CP_HQD_*` wildcard query, and MRR `0.7643`. The artifact still does not
  claim quality across arbitrary future corpora.
- 2026-05-21 user acceptance update: the user explicitly stated that no hosted
  `OPENAI_API_KEY` is available and instructed the project to use the local
  Ollama `gemma` model path instead. For this active goal, that accepts the
  local Ollama OpenAI-compatible `/v1` proof and defers hosted credentialed
  OpenAI-compatible QA. The current-corpus semantic quality boundary is also
  accepted against the `8/8` labeled eval, with broader arbitrary-future-corpus
  semantic ranking quality remaining a future evaluation boundary.

## Remaining Gap

The repo now has a deferral ledger and explicit user acceptance for the remaining residual boundaries in this active goal. Future hosted-provider QA and broader arbitrary-corpus semantic ranking quality remain future work, not current completion blockers.

## Deferral Ledger

| Spec area | MVP status | Current closest capability | User acceptance status | Completion rule |
| --- | --- | --- | --- | --- |
| Real AMD code/docs/register/PDF ingestion | MVP-1 | G01 and G08 track raw corpus plus text-based PDF ingestion. | Required by user. | Must close for MVP-1. |
| Hybrid retrieval over exact, resolver, FTS5, vector, graph, rerank | MVP-1 / accepted residual | G02 and G09 track FTS retrieval, provider embeddings, provider query-time vector rerank wiring, vector fallback, graph expansion, provider-vector preservation under lexical candidate pressure, the 2026-05-21 AQ semantic quality proxy, and a labeled current-corpus semantic eval. | Accepted by user for this active goal after current-corpus `8/8` labeled eval. | Current evidence closes provider-vector wiring, visible provider-vector preservation for AQ05, full current-DB provider embedding coverage, AQ01-AQ09 quality proxy, and an `8/8` labeled current-corpus semantic eval including natural-language `CP_HQD_*` graph expansion; production-scale semantic rerank quality across arbitrary future corpora remains future evaluation work. |
| Configurable resolver profiles for Linux amdgpu, MxGPU, and toy Python | MVP-1 | G05 tracks config-driven resolver profiles and UI workflow. | Required by user. | Must close for MVP-1. |
| Embedding provider and optional semantic-edge provider via Ollama/OpenAI-compatible APIs | MVP-1 / accepted residual | G06 tracks split provider settings, safe env-based extra headers, embedding calls/backfill, query-time provider rerank wiring, semantic-edge jobs, full default-DB provider embedding coverage, and live `gemma4:e4b`/`nomic-embed-text:latest` model QA. The 2026-05-21 OpenAI-compatible live smoke proves the local `/v1` compatible protocol path. | Accepted by user with explicit instruction to use local Ollama gemma instead of a hosted key. | Local Ollama path, safe header expansion, full current-DB provider-vector coverage, query-time provider-vector wiring, semantic/doc-node provenance, and local OpenAI-compatible `/v1` live smoke are proven; hosted credentialed OpenAI-compatible live QA is deferred because no key is available and the user selected Ollama gemma for this active goal. |
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
