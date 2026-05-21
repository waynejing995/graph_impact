# ASIP Stage2 Provider Hardening QA

Date: 2026-05-20

Status: implemented and verified for local gates. This is not a completion
pass because live provider calls and browser e2e remain blocked in the current
environment.

## Changes

- `completion-gate` now accepts `--in-app-browser-json` and includes the
  Codex in-app Browser blocker in the `browser_e2e` requirement.
- Browser preflight and in-app Browser blocker artifacts remain blockers, not
  substitutes for `source: asip.web.browser_e2e` proof.
- `apps/web/scripts/browser-e2e-artifact.mjs` can generate a real
  `asip.web.browser_e2e` artifact from Playwright JSON output in an
  environment where local Web/browser execution is available.
- Provider semantic-edge live smoke now requires at least one
  product-schema-persistable edge, instead of passing on any returned edge.
- Semantic provenance checks now normalize legacy successful job result words
  such as `generated` and `indexed`.
- Provider-gate and completion-gate now require `doc_node_provenance` in
  addition to `semantic_edge_provenance`, so stale LLM document-node semantic
  rows cannot hide behind a fresh or unrelated semantic-edge check.
- Runtime graph reads now fail closed for `extractor=semantic_edges` rows that
  lack a valid semantic job provenance chain.
- Runtime graph reads now bind extractor to job kind: `semantic_edges` rows
  require `semantic_edges`/`semantic_edges_batch` provenance, while `doc_nodes`
  rows require `doc_nodes_batch` provenance.
- `current-artifact-invariants-smoke` now asserts the aggregate completion gate
  has loaded the in-app Browser artifact, preserves the current local-target
  blocker (`ERR_BLOCKED_BY_CLIENT` or `ERR_CONNECTION_REFUSED`) in
  `browser_e2e`, and keeps the future `test:ui:artifact` browser e2e artifact
  producer wired in `apps/web/package.json`.
- `current-artifact-invariants-smoke` also asserts that the provider gate and
  both current AQ09 acceptance artifacts include all five provider checks:
  embedding provenance, embedding live smoke, semantic-edge provenance,
  doc-node provenance, and semantic-edge live smoke.
- `browser-e2e-artifact` now blocks Playwright JSON reports with zero passed
  tests, so an all-skipped run cannot become `source=asip.web.browser_e2e`
  pass evidence.
- `browser-e2e-artifact` and `completion-gate` now require the four no-mock
  Playwright tests that prove real AQ01 acceptance through the Workbench API,
  `/graph` URL `dbPath`, graph layer provenance, and evidence-page URL
  `dbPath`; a forged or partial `asip.web.browser_e2e` artifact stays blocked.
- `completion-gate` now requires the runtime semantic freshness artifact, so
  stale semantic/doc-node runtime filtering and extractor/job-kind binding are
  part of the machine completion aggregate.
- Provider artifact binding now checks both `semantic_edge_provenance` and
  `doc_node_provenance` index/graph job IDs against the current database.
- Stage 1 preprocessor masking now follows Linux helper semantics:
  `IS_ENABLED(CONFIG_FOO)` accepts builtin or module configs,
  `IS_REACHABLE(CONFIG_FOO)` accepts builtin configs or module configs only
  when the current compile unit defines `MODULE`, and `IS_BUILTIN(CONFIG_FOO)`
  remains false for module-only configs.
- Stage 1 preprocessor masking now also reads simple `#define`/`#undef` macros
  from `-include`/`-imacros` forced headers, so `autoconf.h`-style
  `CONFIG_*_MODULE` values can enable vtable/callback scans.
- The completion gate now keeps core AQ01-AQ09 acceptance separate from the
  Web surface artifact: Web `not_configured` remains a Web blocker, but it no
  longer rewrites core CLI/API/MCP acceptance into `0/9 failed`.
- Supplemental preflight or in-app Browser blockers no longer override a real
  passing `source=asip.web.browser_e2e` artifact; without real e2e proof, their
  blocker details still appear in `browser_e2e`.
- Acceptance and completion gates now share a single provider-check ID list and
  the completion gate requires AQ09 acceptance detail to carry all five checks.
  Missing or non-pass AQ09 provider detail blocks `acceptance_gate` instead of
  being hidden behind the separate provider-gate artifact.
- Malformed provider-gate artifacts where `provider_checks` is not an object now
  fail closed in artifact binding, provider live gate, and Stage 2 semantic-edge
  requirements instead of crashing or passing by omission.
- Acceptance surface probes now fail closed on malformed payload shapes such as
  non-object `rows` entries instead of crashing or silently passing.
- Completion-gate DB health now blocks on failed or unfinished jobs in the
  current DB, so stale pass artifacts cannot hide a newer local failure.
- Browser e2e artifacts must now bind to the raw Playwright JSON report path and
  matching SHA-256 hash before they can satisfy `browser_e2e`.
- Completion-gate browser proof now requires the command to be a live
  `pnpm exec playwright test` run; offline `playwright-json-report` artifacts
  can remain diagnostics but cannot satisfy final browser e2e proof.
- `browser-e2e-artifact` now mirrors that contract at the source: report replay
  artifacts stay blocked, and a pass artifact must come from a live Playwright
  run with DB/job/target URL binding.
- Completion-gate browser proof now also binds a passing browser e2e artifact
  to the current `db_path`, target URL `dbPath`, latest index job, and latest
  graph rebuild job.
- Acceptance Web surface probes and completion Web surface checks now require a
  Next BFF transport, matching `db_path`, positive row counts, and positive
  graph node counts before Web can pass. The completion gate also requires a
  positive Web graph edge count, so node-only payloads cannot pass as graph
  evidence.
- Runtime semantic freshness artifacts now bind to the current
  `latest_index_job_id`, `latest_graph_rebuild_job_id`,
  `latest_semantic_edges_job_id`, and `latest_doc_nodes_job_id`.
- Completion-gate DB health now treats both query-mode `semantic_edges` jobs
  and batch `semantic_edges_batch` jobs as the semantic-edge freshness binding
  source, and it uses normalized job statuses so legacy `generated` semantic
  jobs cannot be missed.
- Provider semantic/doc-node provenance now blocks mixed fresh+invalid evidence:
  a fresh valid edge can no longer hide another same-extractor row with missing,
  invalid, or wrong-kind job provenance.
- Completion Stage 2 checks now reject pass-looking provider artifacts that
  still report `missing_or_invalid_job_edge_count > 0`.
- Runtime graph reads now also fail closed for `extractor=doc_nodes` rows that
  lack valid doc-node job provenance.
- Stage 1 callback initializer detection now recognizes table/type names such
  as `amdgv_init_func`, so macro-wrapped MxGPU init callback tables are not
  skipped merely because the identifier uses singular `_func`.
- Completion-gate browser proof now recomputes the raw Playwright JSON summary
  from the bound report and blocks artifacts whose raw report has unexpected
  or flaky tests, report errors, or summary counts that disagree with the
  artifact summary.
- Completion-gate browser proof now also binds each required no-mock browser
  test to `workbench-smoke.spec.ts` in both the browser e2e artifact and the
  raw Playwright report, so same-title tests from another file cannot satisfy
  final e2e proof.
- Completion-gate provider artifact binding now verifies that semantic-edge
  and doc-node provenance `job_ids` exist in the current DB, have succeeded
  status after normalization, and use the expected job kinds.
- Residual acceptance now fails closed when only some residual ledger rows that
  explicitly need acceptance are listed in `accepted_residuals`.
- Stage 1 deterministic graph rebuilds now fail the graph rebuild job when a
  file-level deterministic graph parse raises, instead of silently skipping the
  file and returning a smaller successful graph.

## Verification

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest \
  packages.core.tests.test_acceptance_runner \
  packages.core.tests.test_completion_gate \
  -v
```

Result after malformed surface, browser report binding, and current-DB job
health hardening: `Ran 56 tests`, `OK`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest \
  packages.core.tests.test_closure_gates \
  -v
```

Result: `Ran 4 tests`, `OK`.

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

Result after the no-server input-hash and browser required-test source binding
hardening: `Ran 213 tests`, `OK`, `skipped=2` optional sqlite-vec runtime
tests.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest packages.core.tests.test_workbench_live -v
```

Result after Linux `IS_REACHABLE` semantics, forced-include CONFIG coverage,
and Stage 1 file-parse failure hardening: `Ran 80 tests`, `OK`, `skipped=1`
opt-in real Ollama doc-node smoke.

```text
PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest packages.core.tests.test_workbench_live -v
```

Result after macro-wrapped `amdgv_init_func`, doc-node no-job provenance, and
Stage 1 file-parse failure hardening: `Ran 80 tests`, `OK`, `skipped=1`
opt-in real Ollama doc-node smoke.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest packages.core.tests.test_storage_graph -v
```

Result after runtime extractor/job-kind and doc-node no-job hardening:
covered by the combined `199 OK` suite above; targeted no-job doc-node,
semantic no-job, and relation-normalization fixtures ran `3 OK`.

```text
node apps/web/scripts/current-artifact-invariants-smoke.mjs
node apps/web/scripts/browser-e2e-artifact-smoke.mjs
node apps/web/scripts/no-server-smoke.mjs \
  --output-json docs/qa/2026-05-20-ui-no-server-smoke.json
```

Result: current artifact invariants passed, browser e2e artifact smoke passed,
no-mock hygiene passed with `4` tests checked, and no-server smoke passed `9/9`
checks while refreshing `docs/qa/2026-05-20-ui-no-server-smoke.json`. Playwright
discovery now lists `107` tests. The invariant accepts either
`ERR_BLOCKED_BY_CLIENT` or `ERR_CONNECTION_REFUSED` as the current in-app
browser local-target blocker and verifies runtime semantic freshness job
binding across the current index, graph rebuild, semantic-edge, and doc-node
job IDs. `current-artifact-invariants-smoke` and `no-server-smoke` now accept
explicit artifact paths, and the refreshed no-server artifact records those
paths with byte counts and SHA-256 hashes so future date-stamped artifacts
cannot accidentally validate an older JSON set. The completion gate also
recomputes and validates the required no-server input hashes for browser,
in-app Browser, provider, runtime-semantic, acceptance, and Web-acceptance
artifacts. The browser e2e artifact producer smoke now also verifies that an
offline Playwright JSON replay with all required tests remains blocked until it
is paired with a live Playwright command and current DB/job/target URL binding,
and that same-title required tests from `tests/other-smoke.spec.ts` are marked
`wrong_source` instead of passing.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
python3 -m asip.cli provider-gate \
  --db data/asip.db \
  --output-json docs/qa/2026-05-20-provider-gate-preflight.json \
  --full
```

Result: blocked, provider checks `0 passed / 3 partial / 2 failed`. The local
DB health passed, but live Ollama embedding and semantic-edge calls still fail
with `Operation not permitted`; semantic-edge provenance from job `4` and
doc-node provenance from job `5` remain stale relative to index job `10` and
graph rebuild job `13`.

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

Result at `2026-05-20T10:39:11+00:00`: blocked, `8/15` passed, `7`
blocked, `0` failed, `0` missing.

Focused verification after the no-server input-hash hardening:

```text
PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest packages.core.tests.test_completion_gate -q
```

Result after raw Playwright summary and provider job-id binding hardening:
`Ran 41 tests`, `OK`.
