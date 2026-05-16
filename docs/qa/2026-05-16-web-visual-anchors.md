# ASIP Web Visual Anchors And QA Plan

Date: 2026-05-16
Status: required before Web UI completion

## Purpose

The Web UI must be QA'd against generated visual anchors, not only against DOM assertions. Each first-class page has its own imagegen prompt, raw reference image, canonical normalized anchor, actual screenshot paths, and pass criteria.

Generated raw anchors are design references. Canonical anchors in `docs/visual-anchors/images/` are captured from the live app at 2048 x 1280 after the prompt is logged, so topbar, left rail, center workspace, and right inspector share the same baseline. All anchors must support both light and dark themes without changing page role or information hierarchy.

## Page Prompts

### evidence-workbench

- Route: `/`
- Anchor path: `docs/visual-anchors/images/evidence-workbench.png`
- Actual screenshot paths:
  - `docs/qa/web-evidence-workbench-desktop.png`
  - `docs/qa/web-evidence-workbench-mobile.png`

```text
Create a high-fidelity product UI visual anchor for an engineering evidence workbench named ASIP Evidence Workbench. Unified ASIP operational interface with default light and dark theme support, not a marketing landing page. Target a 2K-class 16:10 desktop screenshot. Top status bar with corpus selector, global symbol search, Ollama/index status. Left sidebar with Evidence Search active. Center pane has a dense query composer, compact source filters, and evidence rows for code, register, doc, and PDF sources. Right inspector shows Resolved Chain, register fields, related entities, and a relationship summary that links into the global graph. Use small color accents only: code cyan, register amber, doc violet, pdf rose, graph blue, primary green. No gradient blobs, no hero section. Text must be readable and not overlap.
```

### graph-explorer

- Route: `/graph`
- Anchor path: `docs/visual-anchors/images/graph-explorer.png`

```text
Create a high-fidelity product UI visual anchor for ASIP Graph Explorer at `/graph`, the global weighted relationship graph for the corpus. Unified ASIP operational interface with default light and dark theme support. Target a 2K-class 16:10 desktop screenshot. Left sidebar with Graph Explorer active. Top bar same as ASIP. Center area shows the global weighted graph with entity nodes, weighted relation edges, confidence/weight encoding, and an edge list or path table for selected relationships. Include controls for hops, relation type, confidence threshold, weighting mode, and selected entity GCVM_L2_CNTL. Right inspector shows shortest paths, source-backed evidence, and edge provenance. Use restrained colors: graph blue edges, code cyan, register amber, primary green. Dense operational SaaS layout, no hero, no background art, no oversized cards.
```

### corpus

- Route: `/corpus`
- Anchor path: `docs/visual-anchors/images/corpus.png`

```text
Create a high-fidelity product UI visual anchor for ASIP Corpus Management. Unified ASIP engineering dashboard with default light and dark theme support. Target a 2K-class 16:10 desktop screenshot. Left sidebar with Corpus active. Main table lists Linux amdgpu, AMD MxGPU, register headers, repo docs, and PDF sources with clone path, commit, file count, indexing status, and last run. Right inspector shows selected corpus metadata, include patterns, PDF conversion status, and FTS/vector counts. Use small source-type badges and status dots. Quiet dense layout for repeated use, no marketing content, no decorative imagery.
```

### resolver-profiles

- Route: `/resolver-profiles`
- Anchor path: `docs/visual-anchors/images/resolver-profiles.png`

```text
Create a high-fidelity product UI visual anchor for ASIP Resolver Profiles. Unified ASIP developer tool with default light and dark theme support. Target a 2K-class 16:10 desktop screenshot. Left sidebar with Resolver Profiles active. Center pane shows profile list for linux-amdgpu, amd-mxgpu, and toy-python. Include editable tables for wrapper names, macro expansion rules, symbol prefixes, device context variables, and non-macro Python extraction rules. Right inspector shows resolved chain preview for WREG32_SOC15 and adapt->reg_offset. Use monospaced code blocks, compact controls, shadcn-style tabs and badges. No hero, no decorative gradients.
```

### acceptance-tests

- Route: `/acceptance`
- Anchor path: `docs/visual-anchors/images/acceptance-tests.png`

```text
Create a high-fidelity product UI visual anchor for ASIP Acceptance Tests. Unified ASIP QA workbench with default light and dark theme support. Target a 2K-class 16:10 desktop screenshot. Left sidebar with Acceptance Tests active. Main pane lists nine MVP queries with pass/fail status, required symbols, model/provider, corpus, duration, and evidence count. Include a selected qwen3.5 full-corpus semantic-edge run showing 9 queries, 7 pass, 2 fail, 1328 files scanned. Right inspector shows failed query details, missing terms, source snippets, and rerun controls. Use compact tables, status badges, and readable code evidence. No marketing hero or decorative background.
```

### settings

- Route: `/settings`
- Anchor path: `docs/visual-anchors/images/settings.png`

```text
Create a high-fidelity product UI visual anchor for ASIP Settings. Unified ASIP configuration page with default light and dark theme support. Target a 2K-class 16:10 desktop screenshot. Left sidebar with Settings active. Main pane has provider profiles for Ollama local and OpenAI-compatible APIs, embedding model, semantic edge model, timeout, num_ctx, num_predict, think toggle, and vector backend sqlite-vec. Include storage settings for SQLite FTS5 and NetworkX graph runtime. Right pane shows validation status and recent provider smoke result. Dense shadcn-style form controls with restrained green primary actions. No landing-page style, no gradients, no decorative blobs.
```

## QA Rules

- Compare each actual page screenshot with the matching page-level anchor before marking visual QA as passing.
- The screenshot must match the anchor's page role, active navigation item, first-screen pane structure, information density, and primary controls.
- The screenshot must match the canonical baseline geometry in `docs/visual-anchors/README.md`; raw imagegen outputs are not used for pixel/layout pass-fail.
- Source colors must remain small indicators: code cyan, register amber, doc violet, pdf rose, graph blue. Primary actions use green.
- The default desktop visual target is a 2K-class viewport; also verify that light and dark themes preserve hierarchy, contrast, and readable source indicators.
- Fail visual QA if the page shows a marketing hero, decorative graph background, gradient/blob background, nested card layout, clipped text, overlapping controls, or unreadable code. The Graph Explorer route must show `/graph` as the global weighted relationship graph with weighted edges, relation controls, evidence-backed provenance, and path inspection.
- Record viewport, screenshot path, anchor path, pass/fail, and deviations in the Web QA report.
