# G16 Workbench IA Theme And Visual Fidelity

Status: Current pass verified; final G11/git gate remains

## Requirement

The Web UI must match the ASIP evidence-workbench design, not just route-render successfully.

The chosen UI direction is:

- Next.js + shadcn/ui,
- native shadcn primitives/composition for tables, cards, accordions, dialogs, settings forms, badges, buttons, empty states, and scroll areas before custom UI,
- actual workbench as the first screen, not a landing page,
- top bar with corpus selector, global symbol search, model backend status, and indexing status,
- left rail for Evidence Search, Graph Explorer, Corpus, Resolver Profiles, Acceptance Tests, and Settings,
- dense evidence center panel with query composer, filters, grouped results, source locations, access type, and confidence,
- right inspector with selected evidence detail, resolved chain, register fields, related entities, source preview, and mini relationship graph,
- dark and light themes by default,
- individual 2K visual anchors per route, plus logo anchor.
- package-backed graph rendering for the global relation graph; a hand-rolled SVG graph is not accepted as the final graph UI.
- graph visual design must make the global relation graph feel like an Obsidian-style knowledge graph, including visible clusters for code functions, registers/fields, document sections, and semantic concepts when present.

## Current Evidence

- `apps/web` is Next.js and uses a shadcn-style component/config setup.
- Visual anchor prompts and images exist for `/`, `/graph`, `/corpus`, `/resolver-profiles`, `/acceptance`, `/settings`, and logo.
- Route-level visual tests check anchor geometry and graph rendering behavior.
- The app has light/dark theme support and tests for route navigation persistence.
- `docs/visual-anchors/README.md` defines canonical reference assets only; it is not a final visual QA pass.
- Current visual QA `docs/qa/visual-qa-2026-05-17/visual-qa.md` captures 2K dark and light screenshots for `/`, `/graph`, `/corpus`, `/resolver-profiles`, `/acceptance`, and `/settings` against their individual anchors. Summary: 6 routes, 6 pass, 0 fail.
- The current `/graph` browser QA records 12 visible graph nodes and 4 weighted edges in both dark and light themes, with edge labels such as `sets_field / 0.90`.
- User review on 2026-05-17 rejected the hand-written graph renderer and custom-looking UI primitives. The current implementation now uses `react-force-graph-2d` for the graph surface and shadcn/Radix primitives for standard tables, cards, accordions, inputs, selects, sliders, checkboxes, and buttons.
- 2026-05-17 continuation verification after the subagent audit: global search now runs a real query, source-type filters affect query requests, semantic generation candidate/batch controls are configurable from `/graph`, the resolver editor can load/save existing profiles, and graph layer provenance is visible in the graph header.
- Fresh verification after those changes: core unittest discovery `141` tests OK with `1` sqlite-vec skip; API/MCP unittest `41` OK with `1` optional MCP runtime skip; Web API+smoke Playwright `69` passed; visual route Playwright `15` passed; `pnpm --filter web run lint`, `pnpm --filter web exec tsc --noEmit`, `pnpm --filter web run build`, and `git diff --check` passed.

## Remaining Gap

The package graph, shadcn-native control pass, light/dark persistence, live global search, source-type filters, semantic generation controls, resolver edit flow, and graph layer provenance are now covered by automated route tests. G16 is no longer blocked on a missing graph package or purely decorative UI controls.

The remaining G16 work is part of the final G11 review: ensure the final staged diff and screenshots match the documented visual-anchor workflow, and recapture visual QA if any further UI-affecting changes land before commit.

The visual anchors must be used as reference artifacts page by page. A combined multi-panel image is not acceptable as the QA baseline.

The `/graph` anchor and browser QA must be updated for the richer graph semantics. A route screenshot that only shows register-to-register labels is not accepted as the visual target once function operation edges and document section nodes exist.

## Acceptance Criteria

- Every route has one canonical visual anchor prompt and one canonical image in `docs/visual-anchors`.
- Every live route is captured at the 2K desktop target after final functional changes.
- Light and dark themes are both checked for route navigation persistence and no theme reset.
- shadcn-native components are used for standard UI surfaces unless a route-specific custom component is justified in the gap or architecture docs.
- `/graph` uses a maintained React/npm graph visualization package and remains visually aligned with the graph anchor.
- `/graph` visual QA confirms the package graph can display mixed node kinds: functions, registers, fields, source files, document sections, and semantic concepts.
- Graph controls and summaries make it obvious whether the user is viewing the global graph, a query neighborhood, or a semantic-edge generation result.
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
| Standard UI primitives | Uses shadcn components before custom table/card/accordion/button/badge/input implementations. | G16, G17 |
| Global graph renderer | Uses a React/npm graph package instead of a hand-written SVG layout. | G03, G16, G17 |

## Required Tests

- Playwright route/visual suite for `/`, `/graph`, `/corpus`, `/resolver-profiles`, `/acceptance`, and `/settings`.
- Component/route tests should not lock private hand-written SVG class names for the graph. They should verify package-backed graph data, accessibility summaries, relationship panels, and nonblank rendering.
- Browser QA screenshots at 2048 x 1280 for each route after final functional changes.
- Theme E2E: switch to light, navigate routes, reload, and verify it stays light.
- Theme E2E: dark theme remains usable and does not hide graph/evidence/status affordances.
- Manual visual QA doc comparing each live page to its own anchor.

## Not Closed Until

The final visual QA doc proves every page matches its own anchor well enough for MVP-1, supports light/dark defaults, and does not hide broken product behavior behind visual polish.
