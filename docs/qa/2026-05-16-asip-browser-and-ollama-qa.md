# ASIP Browser And Ollama QA

Date: 2026-05-16

## Scope

This QA pass validates the design-plan artifacts, not the future production Next.js app. The implementation plan now requires a second browser-controlled QA pass against the real app after Tasks 12 and 13 are implemented.

## Local Machine

```text
CPU: Apple M4
Memory: 24GB
Ollama: /usr/local/bin/ollama
```

## Ollama Model Deployment

Models present before low-memory deployment:

```text
qwen3-embedding:4b
qwen3.5:4b
```

Low-memory models deployed for MVP-1:

```text
nomic-embed-text
qwen2.5:1.5b
```

Embedding smoke:

```text
model: nomic-embed-text
result: 768-dimensional embedding returned through Ollama HTTP API
prompt: GCVM_L2_CNTL register field evidence
```

Semantic-edge smoke:

```text
model: qwen2.5:1.5b
mode: Ollama chat, format=json, num_ctx=2048, temperature=0, keep_alive=0s
result: valid JSON with one edge from GCVM_L2_CNTL to ENABLE_L2_CACHE
```

Memory hygiene:

```text
ollama ps was empty after stop commands.
```

## Browser-Controlled QA Target

```text
docs/qa/asip-workbench-design-preview.html
```

Required checks:

- Desktop viewport: `1440x900`.
- Narrow viewport: `390x844`.
- Workbench first screen, not a landing page.
- Left rail navigation is visible.
- Global symbol search is visible.
- Evidence rows are visible.
- Right inspector and resolved chain are visible.
- Relationship panel is visible.
- Source-type indicators for code, register, and PDF are small indicators.
- No full graph canvas is present in the MVP-1 preview.

## Result

Passed for the static design-plan preview.

Browser-control method:

```text
Python local HTTP server on 127.0.0.1:8765
Playwright MCP browser navigation, snapshots, viewport resize, and screenshots
```

Evidence captured by the browser tool:

```text
Desktop snapshot: asip-desktop-snapshot-final.md
Desktop screenshot: asip-workbench-desktop-final.png
Mobile snapshot: asip-mobile-snapshot-final.md
Mobile screenshot: asip-workbench-mobile-final.png
```

Observed checks:

- Desktop viewport `1440x900` loaded the ASIP Workbench Design Preview without console errors.
- Narrow viewport `390x844` loaded the same preview without console errors.
- The page title was `ASIP Workbench Design Preview`.
- The browser snapshot exposed the ASIP sections navigation, global symbol search, evidence results, resolved chain, and relationship panel.
- The preview contains source indicators for code, register, and PDF.
- The preview intentionally does not define `data-testid="marketing-hero"` or `data-testid="graph-canvas"`.

Remaining QA:

- Run the same browser-controlled QA against the real Next.js app after the Web UI implementation tasks are complete.
