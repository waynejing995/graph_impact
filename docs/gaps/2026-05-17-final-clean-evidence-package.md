# Final Clean Evidence Package Gate

Date: 2026-05-17
Status: Blocking support gate for G01-G17 and AQ closure

## Purpose

This document defines the evidence package that must exist before the ASIP
workbench goal can be called complete.

It exists because partial artifacts can look convincing while proving only one
slice of the product. A fixture pass, a provider pass, a visual pass, or a
historical AQ pass is not enough by itself. Final closure requires one coherent
evidence package generated from the current code and a clean named database.

## Evidence Strength Levels

| Level | Meaning | Can close final goal? |
| --- | --- | --- |
| Fixture proof | Synthetic or tiny local corpus proves a code path and regression test. | No, but it can close a narrow implementation risk. |
| Historical artifact | Previously generated QA output from older gates or older UI state. | No, comparison only. |
| Isolated provider proof | Local fake/real provider proves request shape, provenance, or semantic-edge call path. | No, unless the relevant gap explicitly accepts that boundary. |
| Final clean evidence package | Current code, clean named DB, real or explicitly accepted source roots, API/Web/MCP evidence, browser screenshots, and design review. | Yes, if every required field below is present and passing or explicitly deferred. |

## Required Package Contents

The final package must include these files or sections in `docs/qa`:

- Clean SQLite database path and creation command.
- Corpus config path and every source root used.
- Source-root provenance for Linux `amdgpu`, `amd/MxGPU-Virtualization`, repo docs, generated register headers, and PDF input.
- Source commit, tag, or local snapshot identifier for each real repo root when available.
- SQL counts by `source_type` for `documents` and `evidence`: `code`, `doc`, `register`, and `pdf` must all be nonzero unless explicitly deferred.
- Chunk/page proof for PDF content, including at least one visible page citation.
- Corpus and index job health: no corpus stuck in `indexing`, no failed job hidden in the final DB.
- AQ01-AQ09 runner artifact with CLI/API/Web/MCP surface labels, row counts, source paths, source types, retrieval sources, graph node/edge counts, provider settings, elapsed time, and failure reasons.
- More than five non-AQ free-form query records showing query text, row count, source types, graph counts, and inspector evidence.
- Global graph and query-scoped graph proof from the same clean DB, with `graph_runtime: networkx`.
- Semantic-edge generation proof with configured edge provider settings, model name, base URL, and generated edge count, or an explicit accepted deferral.
- Embedding proof with configured embedding provider settings, model name, base URL, provider-sourced embedding count, deterministic fallback count, and retrieval source metadata.
- Provider settings proof showing independent edge and embedding base URLs, models, and extra headers without leaking secrets.
- Corpus UI proof: add/select/index/query loop against the clean DB or an explicitly named clean UI DB.
- Resolver profile proof: create/edit/select/validate/re-index changes extraction without code edits, including at least one non-macro or Python-style profile if kept in MVP.
- API/MCP/Web route/tool matrix showing which surface ran each capability.
- Read-route mutation review for query, graph, status, provider, corpus, resolver, and acceptance surfaces.
- Performance smoke: fixture rebuild determinism, first real-corpus indexing time, query latency, provider timing, and graph generation timing.
- Per-route 2K visual QA screenshots in light and dark themes, compared to individual anchors in `docs/visual-anchors`.
- Design review mapping ASIP MVP-1 G1-G6 and AQ01-AQ09 to implemented evidence.
- `git diff --check`, full automated verification summary, staged-file review, commit, and push evidence.

## Current Non-Final Artifacts

The following artifacts are useful but not final closure:

- `docs/qa/2026-05-17-acceptance-clean-qwen35-provider-rerun.*`: proves provider/provenance mechanics under an older gate, but every AQ row reports `source_types: ["code"]`.
- `docs/qa/2026-05-17-acceptance-clean-qwen35-source-gated-current.*`: authoritative failure for the old DB; it correctly reports 0/9 because DB health fails and AQ05 lacks PDF.
- `docs/qa/2026-05-17-acceptance-multisource-fixture.*`: proves a healthy synthetic multi-source fixture can return AQ05 with `code`, `doc`, `pdf`, and `register`, and AQ06 with `code` and `register`. It does not prove real AMD source roots, all nine AQ queries, provider closure, browser visual QA, or final performance.
- Existing visual QA `PASS` documents created before the latest functional changes: historical only until screenshots are recaptured after the final code change.

## Current Final-Candidate Package

The current final-candidate package is `docs/qa/2026-05-17-final-clean-evidence-package.md`.
It links the clean AMD DB, source roots, counts, AQ01-AQ09 9/9 artifact,
six free-form queries, qwen3.5 semantic-edge jobs, visual QA screenshots,
automated verification, and architecture review. Commit and push evidence are
still pending until the git gate runs.

## Closure Rule

No G01-G17 or active goal completion claim is valid unless this evidence package
exists, each required field is linked from the owning gap, and every missing
field is explicitly accepted by the user as out of scope.
