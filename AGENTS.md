# Repository Agent Guide

This file is the first stop for agents working in this repository.

## Hard Rules

- Always respond to the user in Simplified Chinese.
- For browser work, use the Codex in-app browser or the computer-use/browser tool, not a hand-waved local check.
- Treat the current worktree, current DB, current runtime behavior, and current remote state as authoritative. Memory and old QA files are hints only.
- Do not claim completion from stale artifacts. Re-run or inspect the current state when accuracy matters.
- Never replace, reset, or delete user work unless the user explicitly asks.
- Before edits, run `git status -sb` and understand any dirty files.
- Prefer `rg`; if unavailable, use `find`, `grep`, and `sed`.
- Use `apply_patch` for manual edits.

## Project Shape

- `packages/core/src/asip/`: Python core, indexing, graph rebuild, retrieval, providers, gates.
- `packages/core/tests/`: Python regression and gate tests.
- `apps/web/`: Next.js workbench UI, API route helpers, Playwright tests, UI artifact scripts.
- `apps/api/`: FastAPI product surface.
- `configs/workbench-limits.json`: central budgets for graph, query, semantic, and embedding behavior.
- `data/asip.db`: current real ASIP SQLite DB used for final evidence. Do not casually replace it.
- `docs/gaps/`: source of truth for gap status and residual boundaries.
- `docs/qa/`: generated or captured QA artifacts. Check freshness before citing.
- `skills/`: repo-local skills for recurring ASIP workflows.

## Current Product Expectations

- ASIP must prove a real evidence chain: real `data/asip.db`, CLI/API/MCP/Web probes, browser QA, e2e tests, and gate artifacts must line up.
- Product graph nodes shown by default should be meaningful product entities: `function`, `register`, and `doc`; raw parser/helper/provider names belong in attributes or provenance.
- Stage 1 deterministic graph and Stage 2 semantic/doc-node edges must remain distinguishable.
- Concept function nodes must expose their generating implementations. Clicking a concept node in the graph should show node details and a `Concept Generated From` list.
- Acceptance `surface_results` must be real surface probes with transport, explicit `dbPath`, schema checks, and pass/fail status.
- Post-push git closure proof is intentionally out of tree, usually under `/tmp`, because a committed git-gate artifact self-invalidates on the next commit.

## Common Commands

Set Python path for CLI/tests:

```bash
export PYTHONPATH=packages/core/src:packages/core/tests:.
```

Inspect current DB:

```bash
PYTHONPATH=packages/core/src:. python3 -m asip.cli corpora --db data/asip.db
PYTHONPATH=packages/core/src:. python3 -m asip.cli jobs --db data/asip.db
sqlite3 data/asip.db "pragma quick_check;"
```

Run focused backend tests:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest packages.core.tests.test_completion_gate -v
```

Run web typecheck:

```bash
pnpm --filter web exec tsc --noEmit
```

Run focused real-DB graph UI proof:

```bash
PLAYWRIGHT_SKIP_WEB_SERVER=1 \
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3100 \
ASIP_BROWSER_E2E_DB_PATH=data/asip.db \
pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts \
  -g "graph page loads current data/asip.db through browser and API" \
  --reporter=line
```

Run post-push git gate out of tree:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
  python3 -m asip.cli git-gate \
  --repo-root . \
  --output-json /tmp/asip-git-gate-postpush.json \
  --full
```

Run the standard post-push completion bundle out of tree:

```bash
pnpm gate:postpush
```

This bundle starts a clean browser port, regenerates the current live browser e2e artifact, and feeds that artifact into the aggregate completion gate. Use `ASIP_POSTPUSH_BROWSER_PORT=3130` only when you need to steer the first candidate port; the script will probe forward from there.

## Remote

At the time this guide was written, `main` tracks:

```text
origin https://github.com/waynejing995/graph_impact.git
```

If the user cannot see the repository, verify `git remote -v`, the GitHub owner, branch tracking, and account permissions before pushing again.

## Completion Boundary

Do not mark the active ASIP graph/UI/backend goal complete until every required item is proven by current evidence. Known non-local blockers may remain:

- Hosted OpenAI-compatible smoke requires a real `OPENAI_API_KEY` or equivalent credentialed hosted endpoint.
- Residual-boundary acceptance must be explicitly provided by the user or project owner.

If either remains blocked, say so plainly and keep the goal active.
