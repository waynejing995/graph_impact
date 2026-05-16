# Settings Anchor Prompt

```text
Use case: ui-mockup
Asset type: canonical repo visual anchor for one Next.js/shadcn web page
Output: one 2048 x 1280 desktop screenshot-style image, 16:10 composition, no multi-panel board
Baseline geometry: apply `base-workbench-geometry.md` exactly. Keep top bar, left rail, center workspace, and right inspector coordinates identical to every other ASIP page.
Primary request: Create a high-fidelity product UI visual anchor for ASIP Settings.
Visual system: Unified ASIP workbench style across all pages. Dark theme default with a visible light/dark theme toggle. Neutral operational surfaces, restrained borders, compact shadcn-style controls, 8px or smaller card radius, no decorative blobs, no marketing hero.
Palette: primary green, code cyan, register amber, doc violet, PDF rose, graph blue, quiet neutral backgrounds.
Layout: Top ASIP status bar. Left sidebar with Settings active. Main pane has provider profiles for Ollama local and OpenAI-compatible APIs, embedding model, semantic edge model, timeout, num_ctx, num_predict, think toggle, and vector backend sqlite-vec. Include storage settings for SQLite FTS5, sqlite-vec, and NetworkX graph runtime. Right pane shows validation status, recent provider smoke result, and CPU/memory/GPU debug hints.
Content anchors: qwen3.5, qwen3.6 compatible slot, OpenAI-compatible endpoint, Ollama base URL, markitdown PDF conversion, FTS5, sqlite-vec, NetworkX.
Quality constraints: dense shadcn-style form controls, restrained green primary actions, readable settings values, no landing page style, no gradients, no decorative blobs.
```
