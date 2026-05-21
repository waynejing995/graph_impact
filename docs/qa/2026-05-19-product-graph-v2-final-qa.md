# Product Graph V2 Final QA Gate

Date: 2026-05-20
Status: Gate not complete. Current code has targeted backend, DB, and
CLI/API/MCP acceptance evidence, but fresh browser/e2e and live semantic-edge
provider proof are blocked in this environment.

## Scope

This record is the current final-gate landing page for Product Graph V2. It
summarizes the latest state after the 2026-05-20 continuation and points to the
full evidence logs rather than restating every older artifact.

Primary evidence:

- `docs/qa/2026-05-19-product-graph-schema-dbpath-e2e.md`
- `docs/qa/2026-05-20-acceptance-data-asip-expanded.json`
- `docs/qa/2026-05-20-acceptance-data-asip-expanded.md`
- `docs/qa/2026-05-20-acceptance-data-asip-expanded-web-blocked.json`
- `docs/qa/2026-05-20-acceptance-data-asip-expanded-web-blocked.md`
- `docs/qa/2026-05-20-current-goal-completion-gate.json`
- `docs/qa/2026-05-20-current-goal-completion-gate.md`
- `docs/qa/2026-05-20-ui-no-server-smoke.json`
- `docs/qa/2026-05-20-residual-acceptance-gate.json`
- `docs/qa/2026-05-20-git-gate.json`
- `docs/qa/2026-05-20-current-goal-completion-audit.md`
- `docs/gaps/2026-05-16-g11-completion-gate.md`

## Current Passing Evidence

- Stage 1 parser hardening has red/green coverage for direct calls, slot calls,
  whole disabled function spans, disabled callback initializers, disabled
  global receiver aliases, comments, string/char literals, `#if 0`,
  `#if (0)`, `#ifdef` / `#ifndef` with undefined config symbols,
  `defined(CONFIG_*)`, `IS_ENABLED(CONFIG_*)`, simple `!` / `&&` / `||`,
  numeric/equality `CONFIG_*` preprocessor expressions, compile-argument-defined
  `CONFIG_*` branches including `-DCONFIG_FOO=0`,
  active/disabled `#else` branches, inactive `#elif` branches after a taken
  `#if`, compile-command preprocessed strings, and generic non-callback
  receivers named `ops`.
- Follow-up subagent review found that workbench cross-file pre-collection
  still read raw source text for known function locations and receiver aliases.
  This is now covered by live-index regressions and fixed by using the same
  masked scan text in the collector path.
- Follow-up parser/vtable review also found the workbench two-phase callback
  join still used the old generic `ops/funcs` fanout. A live-index RED test
  reproduced `struct holder *ops; ops->start()` linking to an unrelated
  `amdgpu_ring_funcs.start` callback; the join now uses the same callback-ish
  receiver guard as Stage 1 parser extraction.
- A second parser/vtable subagent audit found that nested non-callback receivers
  such as `holder->ops->start()` could still overlink to unrelated
  `amdgpu_ring_funcs.start` callbacks. Stage 1 and the workbench two-phase join
  now require actual table/type/known-receiver evidence instead of treating
  every `->`/`.` receiver as callback-like. RED/GREEN coverage exists in both
  `test_code_graph` and `test_workbench_live`.
- A later parser/vtable audit found three parser-only proof points that needed
  persisted live coverage. Workbench live tests now prove address-of callback
  initializers, direct indexed MxGPU init-function receivers, and
  `_ip_block_version` suffix registration flow through `index_registered_corpora`,
  SQLite `edges`, and `global_graph`. The direct indexed MxGPU fixture now
  includes a decoy `amdgv_init_func` candidate and exact `receiver_tables`
  assertion, so it cannot pass through type-wide same-slot fanout. A follow-up
  leak regression also proves `adapt->init_funcs[0]` wiring in one function
  does not become a global alias for unrelated direct indexed callers.
- A latest parser/vtable read-only review added two more red/green proofs:
  `CONFIG_*`-defined slot calls inside function bodies keep their callback
  edges, and direct `*_ip_block_version` assignment resolves nested
  `version->funcs` dispatch without overlinking decoy blocks. Both are covered
  at Stage 1 and through persisted workbench live indexing.
- A later parser/vtable read-only review found that numeric/equality config
  expressions could be treated as active. Stage 1 now preserves simple `-D`
  values and masks false `#if CONFIG_FOO == 1`, `#if CONFIG_FOO != 0`, and
  `#if CONFIG_FOO` with `-DCONFIG_FOO=0` branches before scanning direct calls,
  callback initializers, and slot calls.
- Stage 2 semantic-edge persistence now preserves lowercase C function
  endpoints when the indexed evidence type says `function`, and semantic edge
  provenance records the prompt case plus source refs. RED/GREEN tests cover
  both query-time semantic edges and batch semantic edges for
  `program_cache -> GCVM_L2_CNTL`. A follow-up RED/GREEN test now also proves
  provider/evidence claims cannot promote local callback/provenance tokens such
  as `init_func`, `init_funcs`, `ops`, `callbacks`, `tmp_value`, or `GC` into
  Stage 2 product graph endpoints.
- Current default `data/asip.db` is a live/default expanded DB with
  `pragma integrity_check=ok`, `1224` documents, `147841` chunks, `5299434`
  evidence rows, `39399` edges, and `125989` embeddings. Its expanded
  `linux-amdgpu` slice has `1101` documents and `125962` chunks; the earlier
  Linux-slice inventory records `4438962` evidence rows, `625` code documents,
  and `476` Linux `include/asic_reg` register-header documents.
- The stale interrupted index job `9` is now `superseded`; job `10` is the
  successful expanded index job.
- Post-fix Stage 1 deterministic graph rebuild job `12` succeeded after index
  job `10`, scanning `1122` code files and emitting `39362` deterministic
  edges.
- Acceptance query records now include explicit `schema_status` and
  `schema_failure_reasons`; missing node `kind` or edge `relation` now fails
  the product graph schema gate instead of passing as an empty/unknown value.
- AQ09 provider checks now distinguish persisted semantic-edge provenance,
  freshness, and live provider reachability. The expanded DB has `14`
  persisted `ollama/gemma4:e4b` semantic-edge extraction edges from succeeded
  job `4`, but latest successful expanded index job `10` and graph rebuild job
  `12` are newer, so those
  edges now count as `stale` and semantic-edge provenance is `partial`, not a
  pass. `11` same-provider doc-node edges are reported as ignored for AQ09
  provenance rather than counted as semantic-edge extraction. Edges without a
  matching succeeded semantic job no longer count as persisted provider
  provenance. The live provider smoke remains a separate failing check in this
  environment.
- Provider-gate JSON artifact truthfulness now has a regression proving stale
  semantic-edge provenance is written as `partial` with `gate_status=blocked`
  instead of regressing to a pass-looking artifact.
- Full acceptance JSON artifact truthfulness has a matching regression proving
  stale semantic-edge provenance makes AQ09 `fail` and top-level
  `gate_status=blocked` in the saved acceptance artifact.
- AQ09 embedding checks now separate DB provenance, corpus coverage, and live
  provider reachability. Current expanded DB has `27` provider embeddings but
  `125962` deterministic fallback embeddings plus `21852` chunks with no
  embedding row at all, so embedding coverage is `partial`; the live embedding
  smoke is a separate `embedding_live` check and currently fails with
  `Operation not permitted`.
- Acceptance artifacts now include top-level `gate_status`; the current
  expanded DB rerun records `gate_status: blocked`.
- Acceptance provider smoke timeout is capped at the runner layer so QA cannot
  hang on a persisted `timeout_seconds=900` provider setting when the local
  provider is unreachable. Invalid persisted or environment timeout values now
  fall back to the configured/default cap instead of raising during AQ09.
- Current expanded default DB acceptance has database health `pass`, product
  graph schema `pass` for AQ01-AQ09, and AQ05 source diversity across `code`,
  `doc`, `pdf`, and `register`.
- A Web-included expanded acceptance run now explicitly requests
  CLI/API/Web/MCP. It records CLI/API/MCP query probes with rows and schema
  `pass`, while every Web probe is `not_configured` because `ASIP_WEB_BASE_URL`
  is absent in this blocked local browser environment. This artifact makes the
  Web gap explicit instead of leaving the surface absent from the current run.
- The Web code path has targeted static/listed coverage for preserving URL
  `dbPath` through non-query global search and corpus job-history fetches.
- The Web request path now rejects explicitly blank `dbPath` values for all
  DB-backed Workbench APIs instead of silently falling back to the default DB.
  The UI preserves an explicitly blank URL `dbPath` through graph/query,
  provider settings, and acceptance runner payloads so that this failure path
  can be exercised rather than trimmed away.
- The Web test definitions now include HTTP/API coverage for explicitly blank
  `dbPath` returning `400` across DB-backed Workbench routes, and the
  `/graph?dbPath=...` no-mock e2e now asserts function-view data changes plus
  free-query graph data changes instead of only asserting request URLs. After a
  Web subagent audit, the same e2e definition also asserts the rendered
  `force-graph` totals and accessibility summary change after implementation
  view and free-query transitions, closing the gap between changed API payloads
  and changed visible graph state.
- `apps/web` now exposes `test:ui:no-server`, and
  `docs/qa/2026-05-20-ui-no-server-smoke.json` records the no-listen Web helper
  gate passing `8/8` checks for request-path normalization, explicit blank
  `dbPath` no-fallback checks, Playwright config behavior, no-mock hygiene,
  acceptance route wiring, current artifact invariants, Playwright discovery,
  and browser preflight shape. This is useful in the current `EPERM`
  environment but is not counted as browser/e2e runtime proof.
- The repo root now exposes `test:ui:no-server` and `test:ui:preflight` so the
  final package can reproduce the Web helper gate and browser preflight without
  cd-ing into `apps/web`.
- `docs/qa/2026-05-20-current-goal-completion-audit.md` now records the
  requirement-by-requirement completion decision for the active goal. It marks
  backend/parser/index/performance evidence as current, and keeps browser/e2e,
  live provider checks, stale semantic-edge refresh, G13 residual acceptance,
  and git closure as blocking.
- `python3 -m asip.cli completion-gate` now aggregates the real `data/asip.db`,
  artifact DB/job binding, current acceptance, Web-included acceptance,
  provider-gate, browser-gate, Web no-server smoke, performance smoke,
  residual-acceptance, and git-gate artifacts into
  `docs/qa/2026-05-20-current-goal-completion-gate.json` and `.md`. The
  current aggregate is `gate_status: blocked` with `7/14` requirements passing:
  expanded real DB, artifact binding, Stage 1 graph, product graph schema,
  CLI/API/MCP probes, Web no-server smoke, and performance smoke. The gate also
  rejects AQ subsets, tiny non-expanded DBs, mismatched DB artifacts, stale
  provider semantic-provenance graph job bindings, missing provider checks,
  stale Stage 1 graph rebuilds older than the latest index,
  preflight artifacts masquerading as browser e2e proof, unaccepted residual
  boundaries, dirty worktrees, missing upstreams, and unpushed closure.
  Artifact binding now checks all `8/8` required artifact sources and
  separately records the `3/3` DB/job-bound artifact checks.

## Current Blocking Evidence

- Current acceptance summary is `0 passed / 8 partial / 1 failed` with
  `gate_status: blocked` because Web was not executable in this environment,
  AQ09 live embedding and semantic-edge provider smokes failed, semantic-edge
  provenance is stale/partial (`14` stale edges from job `4`, latest index job
  `10`, latest graph rebuild job `12`), and embedding coverage remains partial
  (`27` provider embeddings / `125962` deterministic fallbacks / `21852` chunks
  with no embedding row).
- The explicit Web-included acceptance artifact
  `docs/qa/2026-05-20-acceptance-data-asip-expanded-web-blocked.json` records
  `0 passed / 0 partial / 9 failed`: CLI/API/MCP probes return rows, but Web is
  `not_configured` for every AQ query because there is no reachable
  `ASIP_WEB_BASE_URL`/browser server in this environment.
- The aggregate completion-gate artifact
  `docs/qa/2026-05-20-current-goal-completion-gate.json` records
  `7 passed / 7 blocked / 0 failed / 0 missing`. It blocks on Web surface,
  final AQ01-AQ09 acceptance, provider live checks, Stage 2 semantic freshness
  and live generation, browser e2e proof, G13 residual acceptance, and git
  closure.
- The residual acceptance artifact
  `docs/qa/2026-05-20-residual-acceptance-gate.json` records
  `gate_status: blocked`: G13 remains `Partial`, and explicit user acceptance
  for the residual boundaries has not been recorded.
- The git closure artifact `docs/qa/2026-05-20-git-gate.json` records
  `gate_status: blocked`: `git diff --check` passes, but the worktree is dirty
  and the branch has no upstream tracking branch.
- The fast provider gate artifact
  `docs/qa/2026-05-20-provider-gate-preflight.json` records the same current
  provider blocker without re-running all AQ01-AQ09 surfaces: database health
  `pass`, provider checks `0 passed / 2 partial / 2 failed`,
  `gate_status: blocked`, `embedding_live` blocked by `Operation not
  permitted`, and semantic-edge live generation blocked by the same provider
  network restriction.
- Playwright could list the new Web tests, but execution could not start a
  fresh Next dev server: `listen EPERM: operation not permitted
  127.0.0.1:3118`.
- `apps/web/playwright.config.ts` now starts a fresh server by default and only
  reuses an existing server when `PLAYWRIGHT_REUSE_EXISTING_SERVER=1` is set.
  `PLAYWRIGHT_WEB_SERVER_COMMAND` can override the launch command for
  controlled port/debug runs. This prevents stale 3100 instances from being
  counted as current browser evidence once local binding is available again.
- In-app Browser navigation to
  `http://127.0.0.1:3100/graph?dbPath=data/asip.db` and
  `http://localhost:3100/graph?dbPath=data/asip.db` now returns
  `ERR_BLOCKED_BY_CLIENT`; `docs/qa/2026-05-20-in-app-browser-probe.json`
  records this as a separate browser-surface blocker, not a pass.
- Manual Next startup on `0.0.0.0:3120` failed with the same `listen EPERM`
  class of error.
- A minimal Python socket listen probe on `127.0.0.1:3121` also returned
  `[Errno 1] Operation not permitted`, confirming the current sandbox blocks
  local server binding before browser assertions can run.
- `apps/web/scripts/browser-gate-preflight.mjs` now records the same blocker as
  structured gate evidence. By default it exits nonzero when local listen is
  blocked; the artifact run used `--allow-blocked` only to write
  `docs/qa/2026-05-20-browser-gate-preflight.json`, which records
  `gate_status: blocked` with `EPERM` for both listen capability and target
  port `3100`.
- AQ09 provider smokes failed against Ollama with `Operation not permitted`:
  `embedding_live` for `nomic-embed-text:latest` and semantic-edge generation
  for `gemma4:e4b`. Embedding provenance exists, but coverage is partial;
  persisted semantic-edge extraction provenance is now `partial` because the
  matching edges bind to older semantic job `4` while the latest successful
  index job is `10`.
- No new 2K light/dark in-app browser screenshots were captured after the
  latest UI/dbPath fixes.

## Verification Commands

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest packages.core.tests.test_completion_gate -v
```

Result: `Ran 8 tests`, `OK`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
python3 -m asip.cli completion-gate \
  --db data/asip.db \
  --acceptance-json docs/qa/2026-05-20-acceptance-data-asip-expanded.json \
  --web-acceptance-json docs/qa/2026-05-20-acceptance-data-asip-expanded-web-blocked.json \
  --provider-json docs/qa/2026-05-20-provider-gate-preflight.json \
  --browser-json docs/qa/2026-05-20-browser-gate-preflight.json \
  --no-server-json docs/qa/2026-05-20-ui-no-server-smoke.json \
  --performance-json docs/qa/2026-05-20-performance-smoke-fixture-current.json \
  --residual-acceptance-json docs/qa/2026-05-20-residual-acceptance-gate.json \
  --git-gate-json docs/qa/2026-05-20-git-gate.json \
  --output-json docs/qa/2026-05-20-current-goal-completion-gate.json \
  --output-md docs/qa/2026-05-20-current-goal-completion-gate.md \
  --full
```

Result: `gate_status: blocked`, `7/14` requirements passing.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
python3 -m asip.cli residual-gate \
  --residual-doc docs/gaps/2026-05-16-g13-mvp-boundary-deferrals.md \
  --output-json docs/qa/2026-05-20-residual-acceptance-gate.json \
  --full
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
python3 -m asip.cli git-gate \
  --repo-root . \
  --output-json docs/qa/2026-05-20-git-gate.json \
  --full
```

Result: both gates are blocked. Residual acceptance is not explicitly recorded;
`git diff --check` passes, but the worktree is dirty and the branch has no
upstream tracking branch.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests \
python3 -m unittest packages.core.tests.test_code_graph -v
```

Result: `Ran 49 tests`, `OK`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_ignores_disabled_cross_file_receiver_aliases \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_ignores_disabled_cross_file_function_locations \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_cross_file_vtable_callbacks_to_registers \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_does_not_generic_dispatch_non_callback_receiver \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_filters_generic_ops_dispatch_by_declared_receiver_type \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_semantic_edge_query_job_persists_lowercase_function_endpoints_from_evidence_type \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_semantic_edge_batch_job_persists_lowercase_function_endpoints_from_typed_terms \
  -v
```

RED before the collector fix: both tests failed because disabled `#if 0`
receiver aliases and disabled function locations leaked into cross-file
indexing. RED before the workbench generic receiver fix:
`holder_start -> gfx_ring_start` leaked through the two-phase callback join.
RED before the nested receiver fix: `holder->ops->start()` leaked to
`gfx_ring_start` even though `holder_methods` is not a callback table. GREEN
after the collector, generic receiver, nested receiver, compile-defined config,
ambiguous cross-file function-location, and semantic endpoint fixes: targeted
workbench live suite `Ran 11 tests`, `OK`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m pytest -p no:cacheprovider -q packages/core/tests/test_code_graph.py
```

Result: `49 passed`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m pytest -p no:cacheprovider -q \
  packages/core/tests/test_storage_graph.py packages/core/tests/test_workbench_live.py
```

Result: `125 passed, 3 skipped`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest \
  packages.core.tests.test_acceptance_runner \
  packages.core.tests.test_graph_schema \
  -v
```

Result after the provider missing-embedding-chunk regression: acceptance runner
plus graph schema `Ran 23 tests`, `OK`.

This suite includes red/green coverage for:

- explicit `schema_status` / `schema_failure_reasons`, including missing
  graph node kind and missing graph relation failures;
- persisted semantic-edge provenance for Ollama and OpenAI-compatible provider
  settings, gated by succeeded semantic jobs;
- embedding provenance versus coverage, including deterministic fallback rows
  and chunks with no embedding rows producing `partial` coverage;
- acceptance runner smoke timeout capping without rewriting provider settings;
- invalid persisted/environment provider timeout fallback;
- top-level `gate_status` staying blocked when any query is partial or failed;
- shared product graph schema validation.

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

Result after the nested receiver, missing chunk embedding, live embedding
smoke, semantic local endpoint, undefined/compile-defined config preprocessor,
stale semantic provenance, fast provider-gate CLI, provider-gate stale artifact,
acceptance stale artifact, address-of callback initializer, direct indexed
MxGPU receiver, direct indexed MxGPU alias-leak guard, compile-defined
slot-call masking, and direct/helper `_ip_block_version` registration flow
fixes plus numeric config equality true-side coverage, mixed stale/fresh
semantic provenance blocking, completion-gate stale semantic count blocking,
and closure-gate aggregation plus provider index/graph job binding:
`Ran 102 tests`, `OK`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_address_of_callback_initializer_to_registers \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_resolves_ip_block_version_suffix_common_loop_across_files \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_direct_indexed_mxgpu_init_funcs_receiver_to_register_callback \
  -v
```

Result after adding persisted live coverage for the three parser/vtable
follow-ups: `Ran 3 tests`, `OK`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest packages.core.tests.test_workbench_live -v
```

Result after the direct indexed MxGPU decoy-candidate hardening,
direct indexed alias-leak live regression, compile-defined slot-call live
coverage, direct/helper `_ip_block_version` global-graph assertions, and
product-valid semantic batch fixture fix: `Ran 78 tests`, `OK`, `skipped=1`
for the opt-in real Ollama doc-node smoke.

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
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest \
  packages.core.tests.test_performance_smoke \
  packages.core.tests.test_workbench_cli.WorkbenchCliTests.test_performance_smoke_command_rebuilds_fixture_and_times_queries \
  -v
```

Result: `docs/qa/2026-05-20-performance-smoke-fixture-current.json` and `.md`
record matching two-run fixture rebuild counts (`documents=2`, `chunks=2`,
`evidence=19`, `edges=4`), all five fixture queries under the `1.0s`
threshold, and focused performance smoke tests `Ran 2 tests`, `OK`.

```text
node apps/web/scripts/no-server-smoke.mjs \
  --output-json docs/qa/2026-05-20-ui-no-server-smoke.json
pnpm run test:ui:preflight -- --timeout-ms 500 --allow-blocked
node apps/web/scripts/browser-gate-preflight.mjs --timeout-ms 500
node apps/web/scripts/browser-gate-preflight.mjs \
  --timeout-ms 500 \
  --allow-blocked \
  --output-json docs/qa/2026-05-20-browser-gate-preflight.json
pnpm --dir apps/web exec eslint \
  components/workbench-page.tsx \
  app/api/workbench/index/route.ts \
  app/api/workbench/query/route.ts \
  app/api/workbench/graph/route.ts \
  app/api/workbench/acceptance/run/route.ts \
  app/api/workbench/corpora/route.ts \
  app/api/workbench/resolver-profiles/route.ts \
  app/api/workbench/jobs/route.ts \
  'app/api/workbench/jobs/[id]/route.ts' \
  'app/api/workbench/evidence/[id]/route.ts' \
  'app/api/workbench/entities/[symbol]/route.ts' \
  app/api/workbench/semantic-edges/route.ts \
  app/api/workbench/providers/settings/route.ts \
  lib/request-paths.ts \
  playwright.config.ts \
  scripts/request-paths-smoke.mjs \
  scripts/dbpath-no-fallback-smoke.mjs \
  scripts/playwright-config-smoke.mjs \
  scripts/browser-gate-preflight.mjs \
  scripts/no-server-smoke.mjs
pnpm --dir apps/web exec tsc --noEmit
pnpm --dir apps/web exec playwright test tests/workbench-smoke.spec.ts \
  -g "global search preserves URL dbPath|corpus page fetches index jobs|acceptance page runs configurable acceptance queries" --list
PLAYWRIGHT_SKIP_WEB_SERVER=1 pnpm --dir apps/web exec playwright test \
  tests/workbench-api.spec.ts tests/workbench-smoke.spec.ts \
  -g "blank dbPath|graph page uses URL dbPath" --list
PLAYWRIGHT_SKIP_WEB_SERVER=1 pnpm --dir apps/web exec playwright test \
  tests/workbench-smoke.spec.ts \
  -g "graph page uses URL dbPath" --list
git diff --check
```

Result: `docs/qa/2026-05-20-ui-no-server-smoke.json` records the no-server
gate as `pass` with `8/8` checks; dbPath no-fallback smoke passed;
request-path helper smoke passed; Playwright config smoke passed; the same
no-server gate verified Playwright discovery still reports `106` tests and
includes the acceptance configurable runner smoke; the existing-target browser
preflight shape smoke now asserts both listen probes are `skipped` and rejects
fresh-server listen failure text; root `test:ui:preflight` works and records
local listen, target-port listen, and target-connect probes; browser gate
preflight exited `2` by default with `gate_status: blocked`, then wrote
`docs/qa/2026-05-20-browser-gate-preflight.json` with `--allow-blocked`;
eslint exit `0`; TypeScript exit `0`; Playwright discovery lists `106` tests
across `3` files, including the URL/dbPath, stricter
blank-dbPath/graph-data-change tests, and acceptance UI CLI/API/Web/MCP surface
checkbox wiring; the strengthened no-mock `/graph?dbPath=...` test definition
was listed after adding rendered graph summary assertions. The config smoke
proves default
`reuseExistingServer=false`, `PLAYWRIGHT_SKIP_WEB_SERVER=1` removes the
webServer config, custom `PLAYWRIGHT_BASE_URL` derives the server command, and
reuse flips to `true` only with `PLAYWRIGHT_REUSE_EXISTING_SERVER=1`.
`git diff --check` passed. The no-server script is a local helper gate only;
the actual browser run is not counted as a pass because server listen failed
before assertions.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
python3 -m asip.cli acceptance \
  --db data/asip.db \
  --output-json docs/qa/2026-05-20-acceptance-data-asip-expanded.json \
  --output-md docs/qa/2026-05-20-acceptance-data-asip-expanded.md \
  --surface CLI --surface API --surface MCP --full
```

Result: database health `pass`; AQ01-AQ09 schema `pass`; summary
`0 passed / 8 partial / 1 failed`; `gate_status: blocked`. AQ09 has embedding
provenance but only partial coverage (`27` provider embeddings / `125962`
fallback embeddings / `21852` chunks with no embeddings; `125989/147841`
chunks embedded), live embedding provider smoke `fail`
(`embedding_live`, `Operation not permitted`), semantic-edge extraction
provenance `partial` because the `14` matching persisted edges from semantic
job `4` are stale relative to latest successful index job `10` and graph
rebuild job `12` (`ignored_edge_count=11` doc-node edges), and live semantic
provider smoke `fail` because the environment rejects the local Ollama network
call.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
python3 -m asip.cli provider-gate \
  --db data/asip.db \
  --output-json docs/qa/2026-05-20-provider-gate-preflight.json \
  --full
```

Result: database health `pass`; provider summary `0 passed / 2 partial / 2
failed`; `gate_status: blocked`. The fast gate independently reports the same
AQ09 blockers without running the full surface matrix: embedding coverage is
partial (`27` provider embeddings / `125962` fallback embeddings / `21852`
chunks with no embeddings), `embedding_live` fails with `Operation not
permitted`, semantic-edge provenance is stale relative to index job `10` and
graph rebuild job `12`, and live semantic-edge generation fails with
`Operation not permitted`.

## Not Closed Until

- A fresh browser/e2e path runs against the latest code and records no-mock Web
  surface evidence for `/graph`, `/acceptance`, and the new dbPath paths.
- AQ09 live embedding and semantic-edge provider smokes either pass with a
  reachable provider or are explicitly accepted as environment residuals.
- Final artifact hygiene review is recorded after the current performance-smoke
  pass, without treating fixture-scale performance as one of the seven current
  aggregate blockers.
- Final browser/provider verification results for these latest fixes are
  recorded or explicitly accepted as residuals.
- `git status --short`, `git diff --check`, final tests, commit, and push are
  completed only after the above evidence is reconciled.
