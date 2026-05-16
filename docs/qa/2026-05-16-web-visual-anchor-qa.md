# ASIP Web Visual Anchor QA

Date: 2026-05-16
Status: pass after normalized 2K baseline

## Anchor Generation

Imagegen was used to generate separate page-level raw references covering:

- Evidence Search
- Graph Explorer
- Corpus
- Resolver Profiles
- Acceptance Tests
- Settings

The per-page prompts are recorded in `docs/visual-anchors/prompts/` and summarized in `docs/qa/2026-05-16-web-visual-anchors.md`. The raw imagegen outputs are preserved in `docs/visual-anchors/imagegen-raw/images/`; canonical QA anchors are normalized live-app captures in `docs/visual-anchors/images/` so all routes share the same 2048 x 1280 geometry.

## Actual Page Screenshots

| Page | Route | Screenshot | Anchor reference | Result |
| --- | --- | --- | --- | --- |
| Evidence Search | `/` | `docs/qa/web-evidence-workbench-desktop.png` | `docs/visual-anchors/images/evidence-workbench.png` | PASS |
| Evidence Search mobile | `/` | `docs/qa/web-evidence-workbench-mobile.png` | `docs/visual-anchors/images/evidence-workbench.png` | PASS |
| Graph Explorer | `/graph` | `docs/qa/web-graph-explorer-desktop.png` | `docs/visual-anchors/images/graph-explorer.png` | PASS |
| Corpus | `/corpus` | `docs/qa/web-corpus-desktop.png` | `docs/visual-anchors/images/corpus.png` | PASS |
| Resolver Profiles | `/resolver-profiles` | `docs/qa/web-resolver-profiles-desktop.png` | `docs/visual-anchors/images/resolver-profiles.png` | PASS |
| Acceptance Tests | `/acceptance` | `docs/qa/web-acceptance-tests-desktop.png` | `docs/visual-anchors/images/acceptance-tests.png` | PASS |
| Settings | `/settings` | `docs/qa/web-settings-desktop.png` | `docs/visual-anchors/images/settings.png` | PASS |

## Pass Criteria Checked

- Each route renders a real Next.js page, not a static docs preview.
- Each actual page screenshot is compared with the corresponding page-level anchor, not a combined board.
- Active sidebar state matches the route.
- First viewport is an operational workbench page, not a landing page.
- Top status bar, left rail, center work area, and bounded right inspector are present.
- `/graph` is the global weighted relationship graph, with weighted edges, relation controls, provenance, and path/evidence inspection.
- ASIP palette is applied consistently across routes: neutral surfaces, primary green, code cyan, register amber, doc violet, pdf rose, graph blue.
- Default light and dark themes are supported without losing hierarchy, contrast, or source-color semantics.
- Desktop QA targets a 2K-class viewport; mobile screenshots remain supplemental for responsive checks.
- Canonical anchor geometry is locked across routes: topbar `0,0,2048,72`, left rail `0,72,288`, center workspace starts at `288,72`, and right inspector starts at `1536,72` with width `488`.
- Browser QA confirmed CSS is loaded; `.workbench-grid` computed display is `grid`.

## Issue Found And Fixed

Initial real-browser screenshots showed unstyled default HTML. Root cause: a stale Next dev server was running while `next build` rewrote `.next`, making `/_next/static/css/app/layout.css` return 404. The dev server was restarted and screenshots were regenerated after confirming the CSS endpoint returned 200.

## Deviations To Improve

- Raw imagegen references still vary in exact shell geometry and are kept only as design-generation evidence.
- Future UI work should add data-driven graph layout and richer route-specific controls before claiming full product parity.

## Verification Commands

```bash
pnpm --filter web lint
pnpm --filter web build
pnpm --filter web test:ui
node docs/visual-anchors/capture-canonical-anchors.mjs
pnpm --filter web exec playwright screenshot --viewport-size "2048,1280" http://127.0.0.1:3100 /Volumes/data/User/wayne/Code/graph_impact/docs/qa/web-evidence-workbench-desktop.png
pnpm --filter web exec playwright screenshot --viewport-size "390,844" http://127.0.0.1:3100 /Volumes/data/User/wayne/Code/graph_impact/docs/qa/web-evidence-workbench-mobile.png
```
