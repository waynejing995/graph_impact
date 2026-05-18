# ASIP Final Web Visual QA Pack

Date: 2026-05-18

Status: pass for current browser screenshot evidence; residual product
boundaries remain tracked in G13.

## Scope

Captured with the in-app browser at `http://127.0.0.1:3100`, viewport
`2048 x 1280`, after the shared-register bridge graph fix. A follow-up
in-app browser check recorded the current `/graph` shared-register visibility
state in `docs/qa/browser/graph-shared-register-2k.png`. Each route has its own
dark and light screenshot, matching the per-page anchor workflow in
`docs/visual-anchors/README.md`.

## Screenshots

| Page | Route | Anchor | Dark screenshot | Light screenshot | Observed live metric |
| --- | --- | --- | --- | --- | --- |
| Evidence Workbench | `/` | `docs/visual-anchors/images/evidence-workbench.png` | `evidence-workbench-dark.png` | `evidence-workbench-light.png` | `matches: 0`, `graph edges: not returned`, live query state |
| Graph Explorer | `/graph` | `docs/visual-anchors/images/graph-explorer.png` | `graph-explorer-dark.png` | `graph-explorer-light.png` | `graph edges: 3000`, graph canvas `1000` nodes / `1220` visible edges, `shared registers: 149` |
| Corpus | `/corpus` | `docs/visual-anchors/images/corpus.png` | `corpus-dark.png` | `corpus-light.png` | `corpora: 5`, `files: 1349`, `status: editable` |
| Resolver Profiles | `/resolver-profiles` | `docs/visual-anchors/images/resolver-profiles.png` | `resolver-profiles-dark.png` | `resolver-profiles-light.png` | `profiles: 9`, `enabled: 9`, `strategy: config` |
| Acceptance Tests | `/acceptance` | `docs/visual-anchors/images/acceptance-tests.png` | `acceptance-tests-dark.png` | `acceptance-tests-light.png` | `passed: 9`, `partial: 0`, `failed: 0`, `queries: 9` |
| Settings | `/settings` | `docs/visual-anchors/images/settings.png` | `settings-dark.png` | `settings-light.png` | `provider: unverified`, `edge model: gemma4:e4b`, `think: off`, `timeout: 900s` |

## Geometry Check

All captured screenshots are `2048 x 1280`. The browser metrics reported the
canonical anchor chrome for each route:

```text
topbar:  x=0,   y=0,  width=2048, height=72
sidebar: x=0,   y=72, width=288
center:  x=288, y=72, width=1248
details: x=1536,y=72, width=488
```

## Notes

- The graph page uses the live API result rather than a mocked graph route in
  this browser capture.
- Corpus/resolver/acceptance screenshots were recaptured after waiting for
  their live metrics so the dark/light images do not show transient loading
  rows as final state.
- These screenshots complement, not replace, the automated
  `visual-anchor-routes.spec.ts` checks.
