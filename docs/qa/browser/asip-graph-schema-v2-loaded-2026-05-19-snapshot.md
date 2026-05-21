# ASIP Graph Schema V2 Browser Snapshot

Date: 2026-05-19
Viewport: 2048 x 1280
URL: `http://localhost:3111/graph`

This snapshot was captured after stopping a stale 3100 Next.js server that
accepted connections but returned zero bytes, then launching a clean dev server
on port 3111.

Observed page state:

- Header: `ASIP Evidence Workbench`
- Provider status: `Provider: unverified`
- Edge provider: `Ollama / gemma4:e4b`
- Index status: `ready`
- Page metric: `graph edges: 3000`
- Graph title: `Global Relation Graph`
- Graph layer badge: `layers deterministic: 2989 semantic: 11`
- Loaded edge budget: `3000 / 20000`
- Visible nodes: `1000 / 2776`
- Visible edges: `3000 / 3000`
- Canvas accessibility label: `Global weighted network graph`
- Canvas summary: `nodes 1000`, `edges 1245`, `shared registers 149`,
  `doc 7`, `function 696`, `register 297`
- Relationship panel shows live function `calls` edges from the default graph.

Console note: the captured console log only showed React DevTools/Fast Refresh
development messages during this run; no runtime exception was observed.

Screenshot evidence:

- `docs/qa/browser/asip-graph-schema-v2-loaded-2026-05-19-2k.png`
- `docs/qa/browser/asip-graph-schema-v2-2026-05-19-2k.png`
