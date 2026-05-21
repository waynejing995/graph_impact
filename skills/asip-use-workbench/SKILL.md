---
name: asip-use-workbench
description: Use when an agent needs to operate, inspect, or verify the ASIP Evidence Workbench UI, API, graph explorer, concept nodes, acceptance surfaces, or QA artifacts.
---

# ASIP Workbench Usage

## Core Principle

Use the workbench as a real product surface, not as a static screenshot. Verify the browser, API, DB path, graph payload, and UI detail state together.

## Before Using The UI

1. Check the service:

```bash
curl -sS -m 5 -D /tmp/asip-web-headers.txt \
  -o /tmp/asip-web-graph.html \
  'http://127.0.0.1:3100/graph?dbPath=data%2Fasip.db'
```

2. If the port is unhealthy, start a clean one:

```bash
cd apps/web
pnpm dev --hostname 127.0.0.1 --port 3100
```

3. Use the Codex in-app browser for visual/browser checks whenever possible.

## Graph Explorer Checklist

- Open `/graph?dbPath=data%2Fasip.db`.
- Confirm the page title is `ASIP Evidence Workbench`.
- Confirm the graph request includes the explicit `dbPath`.
- Confirm graph data comes from the current real DB, not fallback fixtures.
- For concept nodes, click the canvas node itself, not only a summary/sidebar item.
- Confirm the detail pane shows:
  - `Graph Node: <label>`
  - `Node Detail`
  - `Concept Generated From`
  - implementation names with source/path/line provenance
- When recording browser evidence, capture `selection_input=canvas-node-click` and the selected node id.

## Focused Real-DB UI Proof

```bash
PLAYWRIGHT_SKIP_WEB_SERVER=1 \
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3100 \
ASIP_BROWSER_E2E_DB_PATH=data/asip.db \
pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts \
  -g "graph page loads current data/asip.db through browser and API" \
  --reporter=line
```

Expected proof includes a current-DB concept probe with node and edge counts, latest index/graph rebuild job ids, selected concept id, implementation count, and `Concept Generated From`.

## Acceptance Surface Checklist

- Acceptance artifacts must include real `surface_results`.
- Each surface result should name the transport and explicit DB path.
- CLI, API, API_LIVE, Web, MCP, and MCP_PROTOCOL must be separated when present.
- Do not treat a string label like `Web` as proof that Web was probed.

## Common Mistakes

- Using an old listening port that returns stale data.
- Treating `/graph` reachability as proof of concept detail behavior.
- Citing in-repo git-gate artifacts as post-push proof.
- Accepting local Ollama OpenAI-compatible smoke as hosted credentialed OpenAI proof.
