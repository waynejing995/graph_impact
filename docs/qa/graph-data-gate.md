# Graph Data Integrity Gate

A pre-ship validation gate that verifies the structural and semantic integrity
of ASIP graph data before each deployment.

## Purpose

The graph is the core data structure of the ASIP knowledge representation. If
malformed graph data ships, it corrupts the UI, the API responses, and any
downstream consumers. This gate catches structural problems early.

## What It Checks

| # | Check | Description | Threshold |
|---|-------|-------------|-----------|
| 1 | `node-count` | Total nodes must be ≥ 100 | 100 |
| 2 | `kind-validity` | Every node's `kind` must be one of `function`, `register`, `doc` | 0 invalid |
| 3 | `node-classification` | Function nodes must not have ALL_CAPS labels (register misclassification); register nodes must not have single-word labels | 0 misclassifications |
| 4 | `edge-semantic` | `reads`/`writes`/`sets_field`/`maps_base` must be function→register; `calls` must be function→function; `contains` must be doc→doc | 0 violations |
| 5 | `doc-completeness` | `boxmatrix_box` doc nodes must have `inputs`, `outputs`, and `constraints` fields | 0 missing |
| 6 | `edge-count` | Total edges must be ≥ 10 | 10 |
| 7 | `kind-presence` | At least one node of each kind (`function`, `register`, `doc`) must exist | 1 each |

## Usage

```bash
# Default path (/tmp/asip-graph-data.json)
bash docs/qa/graph-data-gate.sh

# Explicit path
bash docs/qa/graph-data-gate.sh /tmp/asip-graph-data.json

# Pipe to a consumer
bash docs/qa/graph-data-gate.sh | jq .
```

## Exit Codes

- **0** — All checks passed. Safe to ship.
- **1** — One or more checks failed. Investigate before shipping.

## Output Format

The script writes a single JSON object to stdout:

```json
{
  "gate": "graph-data-integrity",
  "timestamp": "2026-05-22T19:00:00+08:00",
  "passed": false,
  "checks": [
    { "name": "node-count",      "passed": true,  "detail": "4209 nodes found" },
    { "name": "kind-validity",   "passed": true,  "detail": "all kinds valid" },
    { "name": "node-classification", "passed": false, "detail": "1 issues: ..." },
    { "name": "edge-semantic",   "passed": false, "detail": "6 violations: ..." },
    { "name": "doc-completeness","passed": false, "detail": "9 missing fields" },
    { "name": "edge-count",      "passed": true,  "detail": "5000 edges found" },
    { "name": "kind-presence",   "passed": true,  "detail": "all kinds present" }
  ],
  "summary": "3 check(s) failed"
}
```

## Dependencies

- **bash** 4+ (for `set -euo pipefail`)
- **python3** (for JSON parsing — no `jq` required)
- **date** (GNU or BSD, must support `-Iseconds`)

## Common Failures

### edge-semantic violations

If `reads`/`writes` edges have a `function` destination, it likely means a
register-address constant (e.g. `DF_PIE_AON0_DfGlobalClkGater`) was parsed as
a function rather than a register. Check the parser or resolver profile.

### doc-completeness violations

If `boxmatrix_box` nodes are missing `inputs`/`outputs`/`constraints`, the
box-matrix extraction pipeline did not produce the expected fields. Verify the
markdown parsing step.

### node-classification violations

A single-word register like `RESET` is suspicious — it could be a register
offset that wasn't properly classified, or it could be legitimate. Verify
with the corpus source.
