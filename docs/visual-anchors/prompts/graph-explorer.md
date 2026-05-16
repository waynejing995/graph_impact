# Graph Explorer Anchor Prompt

```text
Use case: ui-mockup
Asset type: canonical repo visual anchor for one Next.js/shadcn web page
Output: one 2048 x 1280 desktop screenshot-style image, 16:10 composition, no multi-panel board
Baseline geometry: apply `base-workbench-geometry.md` exactly. Keep top bar, left rail, center workspace, and right inspector coordinates identical to every other ASIP page.
Primary request: Create a high-fidelity product UI visual anchor for ASIP Graph Explorer.
Visual system: Unified ASIP workbench style across all pages. Dark theme default with a visible light/dark theme toggle. Neutral operational surfaces, restrained borders, compact shadcn-style controls, 8px or smaller card radius, no decorative blobs, no marketing hero.
Palette: primary green, code cyan, register amber, doc violet, PDF rose, graph blue, quiet neutral backgrounds.
Layout: Top status bar matching ASIP. Left sidebar with Graph Explorer active. Main center area is a global weighted relation graph like an Obsidian wiki graph: many nodes, visible clusters, connection thickness/opacity based on edge weight, larger nodes for higher degree or stronger evidence. Include controls for hops, relation type, confidence threshold, selected entity GCVM_L2_CNTL, and a compact weighted edge list below or beside the graph. Right inspector shows shortest paths, source-backed evidence, and edge provenance.
Content anchors: GCVM_L2_CNTL as a high-weight register node, gmc_v11_0 as a code cluster, ENABLE_L2_CACHE as a field node, AMD MxGPU and Linux amdgpu corpus nodes, PDF/doc nodes, weighted edges such as writes 0.94, has_field 0.91, documented_by 0.72, maps_base 0.68.
Quality constraints: graph is functional and inspectable, not decorative background art; readable node labels, no clipped text, no overlapping controls, dense engineering workflow.
```
