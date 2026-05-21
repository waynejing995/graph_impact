# Current Head Goal Audit

Generated: `2026-05-21T12:00:00Z`

Current head: `641d66ec4aca17653010c535a470f05545f40b48`

Remote: `origin/main` at `https://github.com/waynejing995/graph_impact.git`

## Status

The active goal is not complete. The current post-push aggregate is blocked by
two requirements that require external/user action:

- `hosted_openai_compatible`: `OPENAI_API_KEY` is not present, so the
  credentialed hosted OpenAI-compatible embeddings and chat checks cannot run.
- `residual_acceptance`: the G13 residual boundary rows have not been explicitly
  accepted by the user/owner.

## Current Authoritative Evidence

The current authoritative aggregate is out of tree:

`/tmp/asip-postpush-gate-641d66ec4aca-20260521T114136Z/completion-gate.json`

It reports:

- `summary.total`: `20`
- `summary.passed`: `18`
- `summary.blocked`: `2`
- `summary.failed`: `0`
- `summary.missing`: `0`

The post-push bundle exited successfully and explicitly allowed only
`hosted_openai_compatible` and `residual_acceptance` as remaining blockers.

A fresh subagent rerun also wrote:

`/tmp/asip-postpush-gate-review-641d66e/completion-gate.json`

That rerun reported the same `18/20` pass shape.

## Verified Pass Evidence

- Git closure: worktree clean, `main` tracks `origin/main`, ahead/behind `0/0`,
  commit and push proven at head `641d66ec4aca`.
- Real DB: `data/asip.db` quick-check passed with `1224` documents, `147841`
  chunks, `5299434` evidence rows, `32358` edges, and `147841` embeddings.
- Provider gate: `5/5` checks passed with local Ollama settings.
- Stage 2/runtime semantic freshness: runtime semantic freshness `7/7` checks
  passed, bound to index job `10`, graph rebuild job `50`, semantic edge job
  `51`, and doc-node job `52`.
- Semantic quality: labeled semantic eval `8/8` passed with `2`
  provider-vector cases and `1` graph-target case.
- Callback/vtable audit: `4591` callback edges, `20212` deterministic call
  edges, `0` parser-pollution candidates, `0` deterministic parser-pollution
  candidates, `0` unexplained ambiguous callback edges, `7/7` real oracles, and
  `932` version-funcs receiver-table edges.
- Browser e2e: `5/5` no-mock browser tests passed. The current DB graph probes
  returned `2557` nodes and `3000` edges.
- Concept node detail: browser e2e selected
  `function:linux-amdgpu:concept:linux-amdgpu:amd-ip-versioned-functions:gfx_hw_init`
  by canvas click and verified `Concept Generated From`, `9` listed
  implementations, and `92` raw implementation records.
- Web no-server smoke: `9/9` checks passed, including current artifact
  invariants.
- Performance smoke: deterministic counts match and all configured performance
  queries are under threshold.

## Fresh Subagent Cross-Checks

Three fresh read-only subagent reviews checked the current head
`641d66ec4aca17653010c535a470f05545f40b48`:

- Vtable/callback/parser review found no remaining code blocker. It rechecked
  the current DB and callback audit path, including `registered_ip_block`,
  `version->funcs`, and non-empty `receiver_tables` evidence.
- Web/Graph Explorer review found the concept-node detail chain is backend
  backed: the backend emits `attr.is_concept=true`, raw implementations are
  preserved through compact graph payloads, and the UI only shows
  `Concept Generated From` for function nodes with `attr.is_concept === true`.
- Gate/evidence review reran the post-push bundle and again found `18/20` pass
  with only `hosted_openai_compatible` and `residual_acceptance` blocked.

## Local Rechecks

Local read-only rechecks after the push confirmed:

- `git status --short --branch`: `## main...origin/main`
- `git log --format='%an <%ae>' | sort -u` only lists
  `waynejing995 <waynejing995@users.noreply.github.com>`.
- `apps/web/components/workbench-page.tsx` now treats a concept function node as
  concept only when `node.kind === "function"` and `attr.is_concept === true`;
  it no longer relies on a `:concept:` id substring fallback.
- Current real DB contains registered/version-funcs proof:
  - `registered_ip_block` provenance matches: `775`
  - `version->funcs` provenance matches: `1115`
  - non-empty `version->funcs` receiver-table matches: `932`

## Frontend Access Note

Manual browser checking first found a stale `3100` server from
`2026-05-20 22:47:42` that loaded the page shell but returned `500` for
Workbench API requests. That process was stopped and `3100` was restarted from
the current head.

Current verified URL:

`http://127.0.0.1:3100/graph?dbPath=%2FVolumes%2Fdata%2FUser%2Fwayne%2FCode%2Fgraph_impact%2Fdata%2Fasip.db`

After restart, the page, `/api/workbench/limits`, and
`/api/workbench/graph?limit=3000&functionView=concept` all returned HTTP `200`.
The graph API returned `2557` nodes and `3000` edges, and the browser page
rendered without Workbench API console failures.

## Completion Boundary

Do not call the active goal complete until both external blockers are resolved
or explicitly accepted:

1. Provide a hosted OpenAI-compatible credential, then rerun the hosted provider
   smoke and `pnpm gate:postpush`.
2. Explicitly accept the G13 residual rows, update the G13 status to accepted,
   rerun `asip.cli residual-gate --accepted ...`, then rerun
   `pnpm gate:postpush`.
