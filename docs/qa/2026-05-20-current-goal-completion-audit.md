# ASIP Current Goal Completion Audit

Date: 2026-05-20

Status: not complete. This audit preserves the full active goal and records
which requirements are currently proven, blocked, residual, or still missing.

## Objective Under Audit

Complete the ASIP graph/UI/backend gaps and tests, including:

- two-stage graph construction;
- real indexing;
- real semantic edges;
- browser QA and e2e verification;
- multiple subagent reviews of vtable-like parsing and all features.

Completion requires current evidence, not historical or mock-only evidence.

## Current Decision

The goal must remain active.

The current tree has strong backend/parser/index/performance evidence, but the
full objective is not proven because:

- fresh browser/e2e cannot run in this environment: local listen probes return
  `EPERM`, and Codex in-app Browser navigation to the local target returns
  `ERR_CONNECTION_REFUSED`;
- live Ollama embedding and semantic-edge provider calls fail with
  `Operation not permitted`;
- current expanded `data/asip.db` acceptance is `gate_status: blocked`;
- residual-boundary acceptance for full clangd/libclang cross-TU type-flow,
  credentialed OpenAI-compatible live QA, and broader semantic ranking quality
  has not been provided by the user.

## Requirement Matrix

| Requirement | Current evidence | Status | Final proof still needed |
| --- | --- | --- | --- |
| Real expanded index in `data/asip.db` | `docs/qa/2026-05-20-acceptance-data-asip-expanded.json` records database health `pass`; job `10` is the current expanded index. `pragma integrity_check` is `ok`. The current default DB has `1224` documents, `147841` chunks, `5299434` evidence rows, `39399` edges, and `125989` embeddings; the expanded `linux-amdgpu` slice has `1101` documents and `125962` chunks. `docs/qa/2026-05-19-product-graph-v2-final-qa.md` records the Linux slice details including `476` Linux `include/asic_reg` register-header documents. | Proven for current DB health and expanded index presence. | Keep current artifact as candidate evidence until browser/provider gates pass or residuals are explicitly accepted. |
| Stage 1 deterministic graph and vtable/callback parsing | Current parser tests cover disabled preprocessor branches, numeric/equality `CONFIG_*` expressions including true-side equality branches, compile-defined `CONFIG_*` callback initializers and in-function slot calls, Linux helper semantics for module configs (`IS_ENABLED` accepts module configs, `IS_REACHABLE` requires builtin or `MODULE` compile unit for module configs, and `IS_BUILTIN` remains false for module-only configs), forced `-include autoconf.h` style config macros, direct calls, address-of callback initializers, direct indexed MxGPU receivers, macro-wrapped singular `amdgv_init_func` callback tables, direct and helper `_ip_block_version` registration flows, generic receiver overlink prevention, nested non-callback receivers, cross-file unique callbacks, and workbench two-phase joins. Workbench live tests now also prove address-of callback initializers, direct indexed MxGPU receivers, macro-wrapped MxGPU init callback dispatch to register callbacks, direct/helper `_ip_block_version` flows, compile-command-defined `CONFIG_*` slot calls, forced-include `CONFIG_*_MODULE` macros through `index_registered_corpora -> SQLite edges -> global_graph`, and graph rebuild failure when a Stage 1 file parse raises instead of silently skipping that file. The direct indexed MxGPU parser and live fixtures include a decoy `amdgv_init_func` candidate, exact `receiver_tables` assertion, and a leak regression proving `adapt->init_funcs[0]` wiring in one function does not become a global alias for unrelated direct indexed callers. Post-fix graph rebuild job `13` succeeded after index job `10`; full `test_workbench_live` now runs `80 OK` with `1` real-Ollama skip. | Strongly proven for implemented conservative parser slice. | Full clangd/libclang cross-TU type-flow remains a named residual unless implemented and tested. |
| Product graph schema | Acceptance runner fails missing node `kind` or edge `relation`; current expanded AQ01-AQ09 schema status is `pass`; `packages/core/src/asip/graph_schema.py` owns allowed node kinds/relations. | Proven for current acceptance payloads and tests. | Keep schema gate in final acceptance/browser artifacts. |
| Machine completion gate | `packages/core/src/asip/completion_gate.py` and `python3 -m asip.cli completion-gate` now aggregate the real DB, artifact DB/job binding, CLI/API/MCP acceptance, Web-included acceptance, provider gate, runtime semantic freshness, browser gate, Codex in-app Browser blocker, Web no-server smoke, performance smoke, residual acceptance, and git gate into one pass/blocked artifact. Current output is `docs/qa/2026-05-20-current-goal-completion-gate.json` generated at `2026-05-20T10:39:11+00:00`, with `8/15` requirements passing, `7/15` blocked, and `0` missing. The gate checks all `9/9` required artifact sources, records optional in-app Browser evidence, rejects AQ subsets, tiny non-expanded DBs, stale Stage 1 graph rebuilds older than the latest index, failed or unfinished jobs in the current DB, mismatched DB artifacts, stale provider semantic/doc-node provenance index/graph job binding, provider provenance `job_ids` that do not exist in the current DB or use the wrong job kind/status, stale runtime freshness job binding across current index, graph rebuild, query/batch semantic-edge, and doc-node jobs, pass-looking semantic provenance artifacts that still report stale edges, invalid job provenance, or no edge/job counts, missing provider checks, malformed provider-check payloads, missing or non-pass AQ09 provider-check details inside acceptance artifacts, no-server smoke artifacts whose recorded required input paths or SHA-256 hashes no longer match the current browser/in-app/provider/runtime/acceptance artifacts, runtime semantic freshness failures, Web pass artifacts without Next BFF/dbPath/positive row+graph+edge proof, browser e2e artifacts missing required no-mock tests, required browser-test source mismatches against `workbench-smoke.spec.ts` in the artifact or raw report, raw Playwright report hash binding, raw Playwright summary mismatch or unexpected/flaky/errors, current DB/target URL/job binding, or a live `pnpm exec playwright test` command, preflight or in-app Browser artifacts masquerading as browser e2e proof, partially listed residual-boundary acceptance, dirty worktrees, missing upstreams, and unpushed closure. It now keeps core AQ01-AQ09 acceptance separate from Web `not_configured`, and supplemental in-app/preflight blockers cannot override a real passing browser e2e artifact. | Proven as a truthful current-state aggregator. | The aggregate gate must become `pass`; today it correctly blocks on Web, final acceptance, provider live checks, Stage 2 semantic freshness/live generation, browser e2e, G13 residual acceptance, and git closure. |
| Stage 2 semantic-edge pipeline | Query/batch semantic-edge code and tests preserve lowercase function endpoints, reject local callback/provenance tokens, and record provider/job/source refs. Current expanded DB has persisted old semantic edges from job `4` and doc-node semantic rows from job `5`. The provenance gate now blocks mixed fresh+stale semantic-edge rows instead of passing when at least one fresh row exists, separately blocks stale `doc_node_provenance`, normalizes legacy successful job result words such as `generated` and `indexed`, and treats mixed fresh+invalid/no-job/wrong-kind rows as partial rather than pass. Completion DB health now binds runtime freshness to both query-mode `semantic_edges` and batch `semantic_edges_batch` jobs, and Stage 2 completion rejects pass-looking artifacts that still report `missing_or_invalid_job_edge_count > 0`. The live semantic-edge smoke now requires at least one product-schema-persistable edge. Runtime product graph/query reads now also filter stale/provider-mismatched semantic rows, fail closed for `extractor=semantic_edges` and `extractor=doc_nodes` rows without valid job provenance, and bind extractor to job kind so `doc_nodes` cannot borrow a fresh `semantic_edges_batch` job and `semantic_edges` cannot borrow a fresh `doc_nodes_batch` job; `docs/qa/2026-05-20-runtime-semantic-freshness-qa.json` records `latest_index_job_id=10`, `latest_graph_rebuild_job_id=13`, `latest_semantic_edges_job_id=4`, `latest_doc_nodes_job_id=5`, `0` visible semantic edges from the current real DB runtime graph, and `docs/qa/2026-05-20-stage2-provider-hardening-qa.md` records the latest hardening tests. | Implemented and partly proven; stale/runtime false-green risks closed. | Current semantic-edge provenance and doc-node provenance are still stale relative to index job `10` and graph rebuild job `13`; rerun fresh Stage 2 on the expanded DB with reachable provider, or obtain explicit residual acceptance. |
| Provider settings and AQ09 | `docs/qa/2026-05-20-provider-gate-preflight.json` and expanded acceptance split embedding provenance, embedding live smoke, semantic-edge provenance freshness, doc-node provenance freshness, and semantic-edge live smoke. The acceptance runner and completion gate share the same provider-check ID list, and the current AQ09 acceptance detail must include all five checks. The current provider gate is `0 passed / 3 partial / 2 failed`. | Gate exists and truthfully blocks. | Live embedding and semantic-edge calls must pass in an environment with provider access, and embedding coverage/stale semantic/doc-node provenance must be resolved or accepted as residual. |
| CLI/API/MCP/Web acceptance | Current expanded acceptance ran CLI/API/MCP surfaces for AQ01-AQ09; DB health and schema are `pass`; AQ05 source diversity includes `code`, `doc`, `pdf`, and `register`. A follow-up Web-included run at `docs/qa/2026-05-20-acceptance-data-asip-expanded-web-blocked.json` explicitly requested CLI/API/Web/MCP and records all non-Web probes passing for rows/schema while Web is `not_configured` without `ASIP_WEB_BASE_URL`. | Partially proven with a current Web blocker artifact. | Web BFF/browser surface must pass against a real reachable Next server, AQ09 must pass, and overall `gate_status` must become `pass`. |
| Web/UI no-mock e2e | Playwright discovery lists `107` tests; no-mock `/graph?dbPath=...` definitions assert URL DB path, graph totals, function-view changes, free-query graph changes, and layer provenance. The acceptance UI now has both the mocked surface-checkbox wiring smoke and a no-mock AQ01 test that uses a temporary SQLite DB, clicks the `/acceptance` page, and verifies the real Next acceptance API returns CLI/API/MCP transport results with Web recorded as the missing surface. `docs/qa/2026-05-20-ui-no-server-smoke.json` records the local no-listen gate passing `9/9` checks for request helpers, explicit blank `dbPath` no-fallback checks, Playwright config behavior, no-mock hygiene, acceptance route command wiring, explicit-path current blocked-artifact invariants, browser e2e artifact producer smoke, Playwright discovery, and browser preflight shape; it now also records each explicit current-artifact input path with byte count and SHA-256. The completion gate recomputes those required no-server input hashes so stale provider/browser/runtime/acceptance JSON cannot stay green after the referenced files change. The existing-target shape check now asserts listen probes are `skipped` and rejects fresh-server listen failure text. Browser gate preflight writes `docs/qa/2026-05-20-browser-gate-preflight.json` with local listen, target-port listen, and target-connect probes. `docs/qa/2026-05-20-in-app-browser-probe.json` records Codex in-app Browser attempts against `127.0.0.1:3100` and `localhost:3100`, both blocked by `ERR_CONNECTION_REFUSED`; the current artifact invariant smoke accepts `ERR_BLOCKED_BY_CLIENT` or `ERR_CONNECTION_REFUSED`, verifies the aggregate completion gate loaded the in-app Browser artifact, and verifies the future browser e2e artifact producer remains wired through `test:ui:artifact`. `current-artifact-invariants-smoke` now accepts explicit artifact paths so a later final artifact set cannot accidentally validate stale date-stamped JSON. `apps/web/scripts/browser-e2e-artifact.mjs` is now available to write the future `source=asip.web.browser_e2e` artifact from a real Playwright run, and both the artifact producer and completion gate require the four no-mock Playwright tests for real AQ01 acceptance, `/graph` URL `dbPath`, graph layer provenance, and evidence-page URL `dbPath` before browser e2e can pass. Browser e2e artifacts also require the raw Playwright JSON report path, matching SHA-256 hash, current DB path, matching target URL `dbPath`, latest index/graph rebuild job IDs, required-test file binding to `workbench-smoke.spec.ts`, and a live `pnpm exec playwright test` command; offline JSON replay artifacts remain blocked diagnostics even when all required tests are present, and same-title required tests from another spec are marked `wrong_source`. | Test definitions, no-server gate artifact, shell preflight blocker, in-app browser blocker, and artifact producer proven; runtime behavior not proven. | Run fresh Playwright/in-app browser against the current code once local listen/browser access is available; capture `/graph` and `/acceptance` evidence. |
| Static-data and truthful empty states | G14 records route truth audit and tests for API failure, empty states, blank `dbPath`, no auto-indexing, and no static fallback rows. | Mostly proven; audit residual remains. | Final route-by-route audit must be carried through G11 and no new UI changes should bypass it. |
| Performance/rebuild smoke | `docs/qa/2026-05-20-performance-smoke-fixture-current.json` records two empty-DB fixture rebuilds with matching counts and five queries under `1.0s`; focused performance tests ran `2 OK`. | Proven for fixture-scale current tree. | Real-corpus performance remains bounded by recorded residuals and future optimization profiling. |
| Multiple subagent review | Current read-only subagent reviews covered parser/vtable, Web/e2e, provider/acceptance, completion-gate logic, and artifact/docs consistency. Parser review drove new `CONFIG_*` slot-call and direct `_ip_block_version` assignment tests/fixes; Web review drove no-mock hygiene, acceptance-route, and blocked-artifact invariant smokes; provider review confirmed AQ09/provider/Web blockers are truthful and identified whole-DB versus Linux-slice count boundaries. The latest completion-gate review found false-pass risks for AQ subsets, tiny DBs, artifact DB mismatches, missing provider checks, malformed provider-check payloads, and missing AQ09 provider-check detail in acceptance artifacts; those now have regressions. | Proven as process evidence for the latest audit cycle. | Any new final-claim round must include current read-only review results or equivalent final diff review. |
| Final git gate | `git diff --check` passes in recent runs. | Hygiene partially proven. | Commit/push are not done; dirty worktree and generated artifacts require final review and staging decision. |

## Current Blocking Artifacts

- `docs/qa/2026-05-20-current-goal-completion-gate.json`: `gate_status:
  blocked`, summary `8 passed / 7 blocked / 0 failed / 0 missing`.
- `docs/qa/2026-05-20-residual-acceptance-gate.json`: `gate_status:
  blocked`; G13 remains `Partial` and explicit user acceptance is not recorded.
- `docs/qa/2026-05-20-git-gate.json`: `gate_status: blocked`;
  `git diff --check` passes but the worktree is dirty and the branch has no
  upstream tracking branch.
- `docs/qa/2026-05-20-browser-gate-preflight.json`: `gate_status: blocked`
  with local listen `EPERM`.
- `docs/qa/2026-05-20-in-app-browser-probe.json`: `gate_status: blocked`;
  Codex in-app Browser returns `ERR_CONNECTION_REFUSED` for `127.0.0.1:3100`
  and `localhost:3100`.
- `docs/qa/2026-05-20-provider-gate-preflight.json`: `gate_status: blocked`
  with provider checks `0 passed / 3 partial / 2 failed`; the third partial
  is `doc_node_provenance` from stale job `5`.
- `docs/qa/2026-05-20-acceptance-data-asip-expanded.json`: `gate_status:
  blocked`, summary `0 passed / 8 partial / 1 failed`.
- `docs/qa/2026-05-20-acceptance-data-asip-expanded-web-blocked.json`:
  `gate_status: blocked`, summary `0 passed / 0 partial / 9 failed` because
  Web was explicitly requested and every Web probe is `not_configured` in this
  environment.

## Current Passing Artifacts

- `docs/qa/2026-05-20-performance-smoke-fixture-current.json`: deterministic
  fixture rebuild counts match and all fixture queries are under threshold.
- `docs/qa/2026-05-20-runtime-semantic-freshness-qa.json`: stale semantic and
  doc-node runtime filtering, provider-setting freshness, extractor/job-kind
  binding, and real-DB leak probes pass.
- `docs/qa/2026-05-19-product-graph-v2-final-qa.md`: current landing page for
  parser, schema, DB, Web-gate, provider-gate, and performance evidence.

## Commands From Current Evidence

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest \
  packages.core.tests.test_code_graph \
  packages.core.tests.test_acceptance_runner \
  packages.core.tests.test_graph_schema \
  packages.core.tests.test_completion_gate \
  packages.core.tests.test_closure_gates \
  -v
```

Result after latest completion/browser hardening: `Ran 116 tests`, `OK`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest \
  packages.core.tests.test_storage_graph \
  packages.core.tests.test_code_graph \
  packages.core.tests.test_acceptance_runner \
  packages.core.tests.test_graph_schema \
  packages.core.tests.test_completion_gate \
  packages.core.tests.test_closure_gates \
  -v
```

Result after latest Stage 2/provider/browser/no-server hash/residual/source
binding hardening: `Ran 213 tests`, `OK`, `skipped=2` optional sqlite-vec
runtime tests.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest packages.core.tests.test_workbench_live -v
```

Result: `Ran 80 tests`, `OK`, `skipped=1` for the opt-in real Ollama
doc-node smoke.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
python3 -m asip.cli acceptance \
  --db data/asip.db \
  --surface CLI --surface API --surface Web --surface MCP \
  --output-json docs/qa/2026-05-20-acceptance-data-asip-expanded-web-blocked.json \
  --output-md docs/qa/2026-05-20-acceptance-data-asip-expanded-web-blocked.md \
  --full
```

Result: blocked, `0 passed / 0 partial / 9 failed`; CLI/API/MCP probes returned
rows and schema `pass`, while Web probes were `not_configured` because
`ASIP_WEB_BASE_URL` is absent and browser/e2e remains blocked by local listen
`EPERM`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
python3 -m asip.cli provider-gate \
  --db data/asip.db \
  --output-json docs/qa/2026-05-20-provider-gate-preflight.json \
  --full
```

Result: blocked, provider checks `0 passed / 3 partial / 2 failed`; live
provider calls are blocked by `Operation not permitted`, semantic-edge
provenance from job `4` is stale, and doc-node provenance from job `5` is stale.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
python3 -m asip.cli completion-gate \
  --db data/asip.db \
  --acceptance-json docs/qa/2026-05-20-acceptance-data-asip-expanded.json \
  --web-acceptance-json docs/qa/2026-05-20-acceptance-data-asip-expanded-web-blocked.json \
  --provider-json docs/qa/2026-05-20-provider-gate-preflight.json \
  --runtime-semantic-json docs/qa/2026-05-20-runtime-semantic-freshness-qa.json \
  --browser-json docs/qa/2026-05-20-browser-gate-preflight.json \
  --in-app-browser-json docs/qa/2026-05-20-in-app-browser-probe.json \
  --no-server-json docs/qa/2026-05-20-ui-no-server-smoke.json \
  --performance-json docs/qa/2026-05-20-performance-smoke-fixture-current.json \
  --residual-acceptance-json docs/qa/2026-05-20-residual-acceptance-gate.json \
  --git-gate-json docs/qa/2026-05-20-git-gate.json \
  --output-json docs/qa/2026-05-20-current-goal-completion-gate.json \
  --output-md docs/qa/2026-05-20-current-goal-completion-gate.md \
  --full
```

Result: blocked, `8 passed / 7 blocked / 0 failed / 0 missing`; the expanded
DB, artifact DB/job binding, Stage 1 graph, product graph schema, CLI/API/MCP
probes, runtime semantic freshness, Web no-server smoke, and performance smoke
pass, while Web, AQ01-AQ09 final acceptance, provider live checks, Stage 2
semantic edges, browser e2e, G13 residual acceptance, and git closure remain
blocked.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
python3 -m asip.cli residual-gate \
  --residual-doc docs/gaps/2026-05-16-g13-mvp-boundary-deferrals.md \
  --output-json docs/qa/2026-05-20-residual-acceptance-gate.json \
  --full
```

Result: blocked; G13 still says residual-boundary user acceptance remains
blocking.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
python3 -m asip.cli git-gate \
  --repo-root . \
  --output-json docs/qa/2026-05-20-git-gate.json \
  --full
```

Result: blocked; `git diff --check` is `pass`, but the worktree is dirty and
the branch has no upstream tracking branch.

```text
node apps/web/scripts/browser-gate-preflight.mjs \
  --timeout-ms 500 \
  --allow-blocked \
  --output-json docs/qa/2026-05-20-browser-gate-preflight.json
```

Result: blocked.

```text
node apps/web/scripts/no-server-smoke.mjs \
  --output-json docs/qa/2026-05-20-ui-no-server-smoke.json
```

Result: pass, `9/9` checks. This no-listen gate covers request helper normalization,
explicit blank `dbPath` no-fallback checks across DB-backed Workbench routes,
Playwright config behavior, no-mock Playwright hygiene, acceptance route
command wiring, current blocked-artifact invariants, browser e2e artifact
producer all-skipped/pass report handling, and Playwright discovery
(`107` tests including the no-mock AQ01 acceptance runner smoke). The refreshed
artifact records explicit input paths, byte counts, and SHA-256 hashes; the
completion gate validates the required current-artifact inputs against the
files it loads. Its existing-target browser preflight smoke also proves the
listen probes are `skipped` in existing-target mode and rejects fresh-server
listen failure text. It does not replace the blocked browser/e2e runtime gate.

```text
pnpm run test:ui:preflight -- --timeout-ms 500 --allow-blocked
```

Result: blocked. The root preflight command now records local listen,
target-port listen, and target-connect probes; all remain blocked by `EPERM` in
this environment.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
python3 -m asip.cli performance-smoke \
  --db /tmp/asip-performance-smoke-2026-05-20-current.db \
  --source-root docs/fixtures/performance-smoke \
  --query GCVM_L2_CNTL \
  --query IH_RB_CNTL \
  --query SDMA0_QUEUE0_RB_CNTL \
  --query program_gcvm_l2 \
  --query "interrupt ring buffer" \
  --limit 8 \
  --max-query-seconds 1.0 \
  --output-json docs/qa/2026-05-20-performance-smoke-fixture-current.json
```

Result: pass.

## Not Complete Until

- Fresh browser/e2e runs against the current tree and records no-mock Web
  evidence for `/graph` and `/acceptance`.
- Live provider checks pass or the user explicitly accepts the provider/network
  limitation as a residual.
- Stale semantic-edge provenance is refreshed for the expanded index or
  explicitly accepted as a residual.
- Residual boundaries in G13 are explicitly accepted or implemented.
- Final diff/artifact review, commit, and push are complete.
