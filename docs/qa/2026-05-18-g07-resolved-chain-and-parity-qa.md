# G07 Resolved Chain And Surface Parity QA

Date: 2026-05-18

Status: Pass for the deterministic structured resolved-chain slice. The later real MCP runtime smoke is recorded in `docs/qa/2026-05-18-g07-real-mcp-runtime-smoke.md`.

## Scope

This QA closes the smallest G07 residual that did not require a new LLM explanation system:

- evidence detail returns a structured `resolved_chain_explanation`;
- entity explain returns `resolved_chain_explanations` for the same live evidence rows;
- FastAPI, MCP, and Web BFF share the same core shape;
- Web BFF and MCP agree for query, evidence detail, entity detail, and seed graph counts.

The explanation is deterministic and evidence-backed. It splits the existing `resolved_chain` into ordered steps and attaches source path, line/page fields, relation/access type, snippet, and evidence id. It does not claim natural-language causal reasoning.

## Tests

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest \
  apps.api.tests.test_app.ApiAppTests.test_evidence_and_entity_endpoints_return_live_detail_and_resolved_chain \
  apps.mcp.tests.test_tools.McpToolsTests.test_evidence_detail_and_entity_explain_use_live_sqlite_rows \
  apps.mcp.tests.test_tools.McpToolsTests.test_entity_explain_explicit_missing_db_returns_empty_without_creating_db \
  -v
```

Result: 3 tests OK.

```text
pnpm --filter web exec playwright test tests/workbench-api.spec.ts -g "Web BFF and MCP agree" --reporter=list
```

Result: 1 test passed.

```text
pnpm --filter web exec tsc --noEmit
```

Result: passed.

## Evidence Shape

The API/MCP tests now require evidence detail to include:

```json
{
  "resolved_chain_explanation": {
    "evidence_id": 1,
    "symbol": "API_DETAIL_REGISTER",
    "relation": "mention",
    "steps": [
      { "index": 1, "label": "source mention", "kind": "operation" },
      { "index": 2, "label": "API_DETAIL_REGISTER", "kind": "register" }
    ],
    "source": {
      "path": "note.md",
      "source_type": "doc"
    }
  }
}
```

The Web/MCP parity test now compares:

- query agreement: source, query id, row ids;
- evidence detail agreement: id, symbol, path, resolved chain, resolved-chain step labels;
- entity agreement: symbol, evidence rows, resolved chains, resolved-chain explanation evidence ids;
- graph agreement: query id, node count, edge count for the same seed and SQLite DB.

## Residuals

- The real external MCP runtime smoke is still optional because the local Python environment skips it when the `mcp` package is not installed.
- This does not implement an LLM-generated explanation UX. It structures existing evidence; cross-evidence natural-language synthesis remains out of this slice.
