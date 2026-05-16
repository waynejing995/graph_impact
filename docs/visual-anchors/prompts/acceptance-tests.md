# Acceptance Tests Anchor Prompt

```text
Use case: ui-mockup
Asset type: canonical repo visual anchor for one Next.js/shadcn web page
Output: one 2048 x 1280 desktop screenshot-style image, 16:10 composition, no multi-panel board
Baseline geometry: apply `base-workbench-geometry.md` exactly. Keep top bar, left rail, center workspace, and right inspector coordinates identical to every other ASIP page.
Primary request: Create a high-fidelity product UI visual anchor for ASIP Acceptance Tests.
Visual system: Unified ASIP workbench style across all pages. Dark theme default with a visible light/dark theme toggle. Neutral operational surfaces, restrained borders, compact shadcn-style controls, 8px or smaller card radius, no decorative blobs, no marketing hero.
Palette: primary green, code cyan, register amber, doc violet, PDF rose, graph blue, quiet neutral backgrounds.
Layout: Top ASIP status bar. Left sidebar with Acceptance Tests active. Main pane lists nine MVP queries with pass/fail status, required symbols, model/provider, corpus, duration, and evidence count. Include a selected qwen3.5 full-corpus semantic-edge run showing 9 queries, 7 pass, 2 fail, 1328 files scanned. Right inspector shows failed query details, missing terms, source snippets, rerun controls, and log links.
Content anchors: qwen3.5:4b, Ollama local, full-corpus edge generation, mxgpu_reg_offset_gc_base fail, linux_gds_vmid_writes fail, min_pass 6.
Quality constraints: compact QA table, status badges, readable source evidence, real engineering QA surface, no marketing hero or decorative background.
```
