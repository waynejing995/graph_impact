# ASIP Web Visual Anchors

Date: 2026-05-16
Status: canonical repo reference

This directory stores the visual reference set for the ASIP web UI. Every page has its own imagegen prompt, raw generated reference, and canonical normalized anchor image. Do not replace this with a combined multi-panel board.

The canonical anchors target 2K desktop review, 2048 x 1280, with a unified ASIP workbench style:

- Operational engineering UI, not a marketing page.
- Shadcn/Next.js product surface with compact controls, tables, badges, and inspectors.
- Dark theme is the default visual anchor; every page still needs light/dark theme support in implementation.
- Palette: neutral surfaces, primary green, code cyan, register amber, doc violet, PDF rose, graph blue.
- No gradient blobs, decorative backgrounds, nested page cards, clipped text, or overlapping controls.

## Baseline Geometry

Canonical anchors are captured from the live Next.js app at `2048 x 1280` after the page-specific imagegen prompt has been logged. Raw imagegen outputs are preserved in `imagegen-raw/images/`, but QA uses `images/` so all pages share the same geometry:

- Canvas: `2048 x 1280`.
- Top bar: `x=0, y=0, w=2048, h=72`.
- Left rail: `x=0, y=72, w=288`.
- Main grid right margin: `24`.
- Center workspace: `x=288, y=72`, with `24` inner padding.
- Center content origin: `x=312, y=96`.
- Right inspector: `x=1536, y=72, w=488`, with `24` inner padding.
- The `/graph` route uses the same page chrome while its center workspace renders the global weighted graph.

## Canonical Pages

| Page | Route | Prompt | Anchor image |
| --- | --- | --- | --- |
| Evidence Workbench | `/` | `prompts/evidence-workbench.md` | `images/evidence-workbench.png` |
| Graph Explorer | `/graph` | `prompts/graph-explorer.md` | `images/graph-explorer.png` |
| Corpus | `/corpus` | `prompts/corpus.md` | `images/corpus.png` |
| Resolver Profiles | `/resolver-profiles` | `prompts/resolver-profiles.md` | `images/resolver-profiles.png` |
| Acceptance Tests | `/acceptance` | `prompts/acceptance-tests.md` | `images/acceptance-tests.png` |
| Settings | `/settings` | `prompts/settings.md` | `images/settings.png` |

## Logo

| Asset | Prompt | Repo image | Web asset |
| --- | --- | --- | --- |
| ASIP logo | `prompts/logo.md` | `logo/asip-logo.png` | `../../apps/web/public/brand/asip-logo.png` |

## QA Use

Use `images/` when reviewing browser screenshots in `docs/qa/`. Visual QA passes only when the live page matches the anchor's role, active navigation state, information density, first-screen structure, major controls, and baseline geometry. The Graph Explorer page must render a global weighted relation graph similar to an Obsidian wiki graph, with edge/node emphasis driven by relationship weight.

## Regenerate

Run a production server first so the anchors do not include development overlays:

```bash
pnpm --filter web build
pnpm --filter web start --hostname 127.0.0.1 --port 3100
ASIP_WEB_BASE_URL=http://127.0.0.1:3100 node docs/visual-anchors/capture-canonical-anchors.mjs
```
