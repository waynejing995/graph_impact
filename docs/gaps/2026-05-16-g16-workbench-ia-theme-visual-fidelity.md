# G16 Workbench IA Theme And Visual Fidelity

Status: Blocking

## Requirement

The Web UI must match the ASIP evidence-workbench design, not just route-render successfully.

The chosen UI direction is:

- Next.js + shadcn/ui,
- actual workbench as the first screen, not a landing page,
- top bar with corpus selector, global symbol search, model backend status, and indexing status,
- left rail for Evidence Search, Graph Explorer, Corpus, Resolver Profiles, Acceptance Tests, and Settings,
- dense evidence center panel with query composer, filters, grouped results, source locations, access type, and confidence,
- right inspector with selected evidence detail, resolved chain, register fields, related entities, source preview, and mini relationship graph,
- dark and light themes by default,
- individual 2K visual anchors per route, plus logo anchor.

## Current Evidence

- `apps/web` is Next.js and uses a shadcn-style component/config setup.
- Visual anchor prompts and images exist for `/`, `/graph`, `/corpus`, `/resolver-profiles`, `/acceptance`, `/settings`, and logo.
- Route-level visual tests check anchor geometry and graph rendering behavior.
- The app has light/dark theme support and tests for route navigation persistence.
- `docs/visual-anchors/README.md` defines canonical reference assets only; it is not a final visual QA pass.
- Current visual QA `docs/qa/visual-qa-2026-05-17/visual-qa.md` captures 2K dark and light screenshots for `/`, `/graph`, `/corpus`, `/resolver-profiles`, `/acceptance`, and `/settings` against their individual anchors. Summary: 6 routes, 6 pass, 0 fail.
- The current `/graph` browser QA records 12 visible graph nodes and 4 weighted edges in both dark and light themes, with edge labels such as `sets_field / 0.90`.

## Remaining Gap

Visual tests and the latest visual QA now prove route geometry, light/dark persistence, screenshots, and graph visibility after the latest functional changes. The remaining gap is the final design-review checklist that verifies the full ASIP workbench information architecture, theme tokens, source-type indicators, right inspector responsibilities, and text overflow constraints against the design docs before completion.

The visual anchors must be used as reference artifacts page by page. A combined multi-panel image is not acceptable as the QA baseline.

## Acceptance Criteria

- Every route has one canonical visual anchor prompt and one canonical image in `docs/visual-anchors`.
- Every live route is captured at the 2K desktop target after final functional changes.
- Light and dark themes are both checked for route navigation persistence and no theme reset.
- Source-type colors are small indicators rather than large decorative fills.
- The top bar, left rail, center panel, and right inspector match the chosen workbench information architecture.
- Text does not overflow compact panels, buttons, rows, badges, or graph labels.
- Visual QA records pass/fail deltas against each individual anchor.
- Logo anchor and runtime logo usage are reviewed together.

If more functional UI changes land after this point, visual QA must be recaptured. Older `PASS` screenshot reports remain stale unless they match the current route implementation at 2048 x 1280 against individual anchors in both light and dark themes.

## UI Control Checklist

| UI area | Required behavior | Owning gap |
| --- | --- | --- |
| Top bar corpus selector | Shows current corpus/index scope and does not imply all corpora are indexed when only a subset is selected. | G04, G14 |
| Global symbol search | Runs a real query or is explicitly labeled unavailable; it must not be a decorative input. | G02, G14 |
| Model backend status | Reflects detected/smoked provider state, including failure, rather than static ready text. | G06, G14 |
| Indexing status | Shows queued/indexing/failed/succeeded states from backend jobs. | G01, G04, G15 |
| Left rail navigation | Covers Evidence Search, Graph Explorer, Corpus, Resolver Profiles, Acceptance Tests, and Settings with persistent theme. | G16 |
| Query filters | IP/ASIC/source-type filters change query results or show truthful disabled state. | G12, G14 |
| Evidence rows | Show source type, path/page/line, access type, confidence, and retrieval source without overflow. | G02, G16 |
| Right inspector source preview | Shows selected evidence snippet and source citation from live data. | G02, G14 |
| Right inspector resolved chain | Shows macro/wrapper/entity chain when present, and an explicit absent state otherwise. | G05, G14 |
| Graph panel | Renders weighted nodes/edges from API/core graph data or a visible empty/error state. | G03, G14 |
| Acceptance page | Loads current artifacts or runner output and labels stale historical QA clearly. | G10, G14 |

## Required Tests

- Playwright route/visual suite for `/`, `/graph`, `/corpus`, `/resolver-profiles`, `/acceptance`, and `/settings`.
- Browser QA screenshots at 2048 x 1280 for each route after final functional changes.
- Theme E2E: switch to light, navigate routes, reload, and verify it stays light.
- Theme E2E: dark theme remains usable and does not hide graph/evidence/status affordances.
- Manual visual QA doc comparing each live page to its own anchor.

## Not Closed Until

The final visual QA doc proves every page matches its own anchor well enough for MVP-1, supports light/dark defaults, and does not hide broken product behavior behind visual polish.
