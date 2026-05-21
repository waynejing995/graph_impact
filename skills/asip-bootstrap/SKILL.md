---
name: asip-bootstrap
description: Use when setting up a fresh ASIP checkout, installing dependencies, starting local services, preparing the real SQLite DB, or verifying provider/workbench readiness.
---

# ASIP Bootstrap

## Core Principle

Bootstrap to a real, inspectable local workbench. A running UI is not enough; verify the DB, CLI, provider settings, and browser path.

## Install Dependencies

```bash
pnpm install
export PYTHONPATH=packages/core/src:packages/core/tests:.
```

Python code uses the standard library plus project modules for most checks. If a command fails on imports, re-check `PYTHONPATH` before changing code.

## Verify The Current DB

```bash
sqlite3 data/asip.db "pragma quick_check;"
PYTHONPATH=packages/core/src:. python3 -m asip.cli corpora --db data/asip.db
PYTHONPATH=packages/core/src:. python3 -m asip.cli jobs --db data/asip.db
```

Expected current shape is an indexed real DB with `amd-amdgpu-docs`, `linux-amdgpu`, and `mxgpu` corpora.

## Start Services

Web workbench:

```bash
cd apps/web
pnpm dev --hostname 127.0.0.1 --port 3100
```

FastAPI surface:

```bash
PORT=8000 pnpm dev:api
```

Open the UI with the in-app browser:

```text
http://127.0.0.1:3100/graph?dbPath=data%2Fasip.db
```

## Provider Readiness

Inspect saved provider settings:

```bash
PYTHONPATH=packages/core/src:. python3 -m asip.cli provider-show --db data/asip.db
```

Run local provider gate:

```bash
PYTHONPATH=packages/core/src:. python3 -m asip.cli provider-gate \
  --db data/asip.db \
  --output-json /tmp/asip-provider-gate.json
```

Hosted OpenAI-compatible smoke requires a real hosted credential:

```bash
OPENAI_API_KEY=... \
PYTHONPATH=packages/core/src:. python3 -m asip.cli openai-compatible-smoke \
  --base-url https://api.openai.com \
  --embedding-model text-embedding-3-small \
  --chat-model gpt-4.1-mini \
  --api-key-env OPENAI_API_KEY \
  --require-credentialed \
  --output-json /tmp/asip-hosted-openai-compatible.json \
  --full
```

Do not substitute a local Ollama-compatible endpoint for hosted credentialed proof.

## Final Sanity Checks

```bash
pnpm --filter web exec tsc --noEmit
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest packages.core.tests.test_completion_gate -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
  python3 -m asip.cli git-gate --repo-root . --output-json /tmp/asip-git-gate.json --full
pnpm gate:postpush
```

`pnpm gate:postpush` probes for a clean local browser port, regenerates the live no-mock browser e2e artifact against the current `data/asip.db`, records the artifact git `repo_head`, and runs the aggregate completion gate with fresh no-server input path/SHA bindings.

If the user explicitly accepts residual boundaries, update the G13 status line from `Partial` to an accepted status and regenerate the residual artifact with every acceptance-required row:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
  python3 -m asip.cli residual-gate \
  --residual-doc docs/gaps/2026-05-16-g13-mvp-boundary-deferrals.md \
  --accepted \
  --accepted-residual "Hybrid retrieval over exact, resolver, FTS5, vector, graph, rerank" \
  --accepted-residual "Embedding provider and optional semantic-edge provider via Ollama/OpenAI-compatible APIs" \
  --output-json docs/qa/2026-05-20-residual-acceptance-gate.json \
  --require-pass \
  --full
```

The aggregate completion gate may remain blocked by hosted credentials or explicit residual acceptance. That is a real project boundary, not a bootstrap failure.

## Rebuilding Or Reindexing

Treat `data/asip.db` as a shared evidence artifact. Before a rebuild:

1. Back it up outside the repo.
2. Record the exact command and corpus config.
3. Re-run provider, graph, acceptance, browser, and completion checks.
4. Update docs only with fresh evidence.
