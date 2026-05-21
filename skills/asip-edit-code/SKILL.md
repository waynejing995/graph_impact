---
name: asip-edit-code
description: Use when modifying ASIP Python backend, graph parser, storage, completion gates, Next.js UI, Playwright tests, or QA artifact scripts.
---

# ASIP Code Editing

## Core Principle

Every edit should make the real ASIP graph/UI/backend state more truthful. Do not patch around gates or weaken evidence to make a run look green.

## First Checks

```bash
git status -sb
```

If files are dirty, identify whether they are yours. Work with user changes; do not revert them unless explicitly asked.

Find relevant code before editing:

```bash
grep -R "symbol-or-error-text" -n packages apps scripts docs | head -80
```

## Ownership Map

- Parser and deterministic graph extraction: `packages/core/src/asip/code_graph.py`
- Graph rebuild and workbench orchestration: `packages/core/src/asip/workbench.py`
- SQLite persistence and graph readback: `packages/core/src/asip/storage.py`
- Retrieval/query/provider logic: `packages/core/src/asip/query.py`, `providers.py`, `semantic_edges.py`
- Completion and closure gates: `packages/core/src/asip/completion_gate.py`, `closure_gates.py`
- Web UI and product graph rendering: `apps/web/components/`, `apps/web/app/`
- Browser and artifact checks: `apps/web/tests/`, `apps/web/scripts/`

## Edit Workflow

1. Reproduce or inspect the failing behavior.
2. Add or identify a focused failing test where practical.
3. Make the smallest code change that addresses the root cause.
4. Run the focused tests for the touched surface.
5. Run broader checks if the change touches shared graph schema, DB state, or gate behavior.
6. Update docs/QA artifacts only when they are produced by a real command or clearly documented as a manual probe.

## Evidence Rules

- Real DB proof should bind to `data/asip.db`, latest index job, and latest graph rebuild job when possible.
- Browser proof should include explicit `dbPath`, raw Playwright status, and no-mock target URL.
- Concept-node proof should include `selection_input=canvas-node-click`.
- Provider proof must distinguish local OpenAI-compatible/Ollama from hosted credentialed OpenAI-compatible.
- Post-push git proof belongs in `/tmp` or another out-of-tree artifact, not committed back into the repo as final proof.

## Useful Focused Commands

Completion gate tests:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest packages.core.tests.test_completion_gate -v
```

Callback/vtable audit:

```bash
PYTHONPATH=packages/core/src:. \
  python3 scripts/audit_callback_edges.py \
  --db data/asip.db \
  --assert-no-parser-pollution \
  --max-ambiguous-fanout 2
```

Web typecheck:

```bash
pnpm --filter web exec tsc --noEmit
```

No-server artifact hygiene:

```bash
node apps/web/scripts/no-server-smoke.mjs --output-json /tmp/asip-no-server-smoke.json
```

## Common Mistakes

- Raising limits to hide graph/query bugs instead of profiling.
- Treating count stability as semantic correctness.
- Rebuilding `data/asip.db` without backing it up or recording exact commands.
- Editing generated QA JSON by hand without saying it is manual.
- Marking completion while residual acceptance or hosted credentials remain blocked.
