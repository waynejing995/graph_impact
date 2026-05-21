# ASIP Current Graph Finalization Plan

Date: 2026-05-19
Status: Docs-only current final gate; implementation and QA evidence still required

## Purpose

This is the current completion checklist for the ASIP graph/workbench closure.
It does not replace the implementation plan in
[`2026-05-19-asip-graph-integration-plan.md`](2026-05-19-asip-graph-integration-plan.md);
it turns that contract into the final gate the main thread must prove before
claiming the graph/workbench gap is closed.

The executable TDD handoff for the current architecture is
[`../superpowers/plans/2026-05-19-product-graph-v2-implementation.md`](../superpowers/plans/2026-05-19-product-graph-v2-implementation.md).
That plan was written after the 2026-05-19 subagent audit and should be used
for the next code pass. This finalization checklist remains stricter: a written
plan does not close the active goal until the implementation and QA evidence
exist.

The guiding rule is strict: no historical pass, fixture artifact, mock API, or
stale default `data/asip.db` can close the current graph contract. A 2026-05-18
artifact may be cited as candidate evidence, but the 2026-05-19 final gate must
say exactly what was rechecked against the current tree.

## Product Contract To Prove

Default product graph output across CLI, API, MCP, Web, browser QA, and
acceptance artifacts exposes exactly three node kinds:

- `function`
- `register`
- `doc`

Document subtypes are attributes:

- Markdown sections: `kind=doc`, `attr.doc_kind=markdown_section`
- PDF sections/pages: `kind=doc`, `attr.doc_kind=pdf_section`
- BoxMatrix boxes: `kind=doc`, `attr.doc_kind=boxmatrix_box`

The following are never visible product nodes: macro wrappers, resolver helper
calls, callback slot/table names, register fields, source files, provider/model
names, corpus ids, local variables, and temporary names. They remain in
`attr`, edge provenance, resolved chains, inspector expansion, and QA records.

Allowed edge relations are enum-bound:

- `reads`
- `writes`
- `sets_field`
- `maps_base`
- `calls`
- `contains`
- `documents`
- `relates_to`
- `depends_on`
- `configures`
- `resets`

Raw access names, provider wording, macro expansion facts, field facts, and
source-file relations must normalize into this enum or remain provenance-only.

## Stage Gates

Stage 1 deterministic graph proof must be separate from Stage 2 LLM proof.

Stage 1 owns deterministic function/register/doc projection and
`function -> function` / `function -> register` edges from AST/clang,
preprocessor, macro-resolver, vtable/callback, direct call, and fallback
extractors. Current source-span and selective clang AST JSON work is useful,
but it must not be described as full clangd/libclang cross-TU type flow unless
that extractor and tests actually land.

Stage 2 owns semantic edges and BoxMatrix-style document boxes after Stage 1
and document extraction. Stage 2 may enrich relationships, but it cannot invent
non-product node kinds or substitute for deterministic function/register
extraction.

Stage 1.5 product projection owns function normalization, register
normalization, document subtype projection, edge enum normalization, and
provenance folding. It must preserve raw facts for inspector/debug expansion.

## Required Current Evidence

The final package must include fresh current-tree evidence for:

- product schema validator: only `function/register/doc` nodes and allowed edge
  relations in default output;
- document projection: historical `doc_section`, `pdf_section`, and `doc_box`
  raw/debug facts appear as `kind=doc` with `attr.doc_kind`;
- same-repo multi-subfolder corpus: one logical corpus can include source and
  sibling register-header roots with separate source type/file counts and safe
  path validation;
- register inventory: accepted AMD register forms include `reg*`, `mm*`,
  `smn*`, offset/mask/default/IP namespace families; low-signal tokens such as
  `A`, `tmp`, `adapt`, wrappers, and local variables do not become endpoints;
- register merge: same `ip` and `symbol` merge across repos/IP versions,
  `ip_versions` and per-source `ip_version` remain attrs/provenance, different
  IP blocks do not merge, and unknown IP does not silently merge into known IP;
- function normalization: resolver YAML controls every concept merge,
  duplicate rule ids across profiles stay isolated, no YAML/profile metadata
  means no merge, merged concepts preserve `raw_implementations`, and low
  overlap is marked `divergent` or `split_recommended`;
- resolver YAML: committed resolver configs are loaded, UI/API/MCP only list or
  use real YAML/backend profiles, and macros/resolvers stay provenance instead
  of graph mega-nodes;
- global graph controls: default graph is global, limits come from
  `configs/workbench-limits.json`, API/URL params, and visible UI filters;
  loaded/visible/total counts and relation/stage/source/weight filters are
  visible rather than hidden constants;
- acceptance surface probes: per-query results show the real transport used,
  DB path, row/graph counts, schema status, and failure reason for CLI/core,
  FastAPI, MCP, and Web BFF when configured; otherwise Web is explicitly tied
  to the no-mock Playwright/browser DB-path gate rather than silently marked
  pass;
- UI contract: standard controls use shadcn/Radix composition and the graph
  uses a maintained package renderer;
- no-mock browser/e2e: `/graph` and `/acceptance` are verified against a real
  SQLite DB path, with no fixture shortcut, mocked graph payload, or stale DB
  assumption;
- provider gate: current clean semantic-edge gate is `gemma4:e4b`; qwen
  artifacts are historical comparison evidence only;
- visual gate: in-app browser or Computer Use captures 2K light/dark evidence
  after the final UI-affecting change;
- performance gate: current profile/timing captures browser, Next BFF, Python
  query, SQLite/NetworkX graph, and acceptance layers before any optimization
  claim.

## Historical Evidence Policy

2026-05-18 clean artifacts may be linked as candidate evidence when they still
match the current behavior, especially the clean AMD `gemma4:e4b` acceptance
and source-diversity results. They must be labeled as 2026-05-18 evidence.

2026-05-17 qwen artifacts, older PASS notes, fixture-only results, and provider
smokes are historical or comparison evidence. They cannot close the current
final gate unless the final QA package explicitly reruns or supersedes them.

Any document that says "complete" or "pass" must specify which date and gate it
belongs to. For the current goal, "complete" means the 2026-05-19 schema,
real-DB/no-mock, visual, performance, residual-boundary, commit, and push gates
are all recorded.

## Residuals To Accept Or Implement

The final review must explicitly choose implement-now or accepted-residual for:

- full clangd/libclang cross-translation-unit type flow;
- broader Linux kernel compile database coverage metrics;
- production semantic ranking quality and larger robust LLM batches;
- credentialed OpenAI-compatible live provider QA;
- background corpus workers, cancellation, and remote clone orchestration;
- arbitrary DB selection beyond the no-mock `dbPath` final gate;
- full graph progressive loading beyond the current budgeted global graph.

## Close Order

1. Reconcile docs/specs/gaps to this contract.
2. Land or verify implementation for schema projection and real-DB e2e routing.
3. Rerun current automated core/API/MCP/Web checks.
4. Rerun no-mock `/graph` and `/acceptance` browser checks with in-app browser
   or Computer Use.
5. Capture current 2K light/dark visual QA for UI-affecting pages.
6. Record performance/profile evidence or explicitly defer optimization work.
7. Update the final QA package with exact commands, DB paths, counts, and
   residuals.
8. Review `git status --short` and exclude generated/local artifacts.
9. Commit and push only after the current evidence package is internally
   consistent.
