# Web Browser E2E QA

Date: `2026-05-16`

Target: `http://127.0.0.1:3100`

## Tooling Note

Computer Use rejected direct control of the Codex app, so the local in-app browser was exercised through the Browser plugin. The tested surface is the same localhost web app.

## Route Results

| Route | Query Used | Action Verified | Theme Verified | Screenshot |
| --- | --- | --- | --- | --- |
| `/settings` | `Validate provider settings` | `Run provider smoke queued` | light | `/tmp/asip-settings.png` |
| `/` | `enable evidence smoke` | `Open resolver profile queued` | light | `/tmp/asip-final-evidence.png` |
| `/graph` | `enable graph qa` | `Inspect edge provenance queued` | light | `/tmp/asip-final-graph.png` |
| `/corpus` | `enable corpus qa` | `Run index queued` | light | `/tmp/asip-final-corpus.png` |
| `/resolver-profiles` | `enable resolver qa` | `Validate profile queued` | light | `/tmp/asip-final-resolver.png` |
| `/acceptance` | `enable acceptance qa` | `Open QA JSON queued` | light | `/tmp/asip-final-acceptance.png` |

## Graph-Specific Checks

- Verified the global weighted graph is visible on `/graph`.
- Verified weighted edge labels:
  - `writes / 0.94`
  - `has_field / 0.91`
- Verified the graph route also supports the shared query composer, result table, details panel action, and light theme.

## Settings-Specific Checks

- Verified provider/API/model settings can be configured from UI.
- Verified extra headers JSON is accepted and reflected in the runtime config preview.
- Verified empty fallback is saved as an empty string after trimming.

## Browser Health

- Page title after final route: `ASIP Evidence Workbench`.
- Final URL: `http://127.0.0.1:3100/acceptance`.
- Relevant `127.0.0.1:3100` browser warnings/errors: none observed.

## Automated UI Verification

- `pnpm --filter web test:ui`
  - Result: `14` tests passed.
  - Coverage includes route readiness against visual anchors, settings persistence, action feedback, weighted global graph, desktop/mobile styling, canonical anchor chrome, and light/dark graph visibility.
- `pnpm --filter web build`
  - Result: passed; all six app routes were prerendered as static content.

## Anchor References

The canonical visual anchors remain in `docs/visual-anchors/images/`:

- `evidence-workbench.png`
- `graph-explorer.png`
- `corpus.png`
- `resolver-profiles.png`
- `acceptance-tests.png`
- `settings.png`
- `docs/visual-anchors/logo/asip-logo.png`
