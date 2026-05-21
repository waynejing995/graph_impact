# G11 Completion Gate And Documentation Review

Status: 2026-05-20 aggregate completion gate remains blocked; expanded DB,
artifact binding, Stage 1 graph, product graph schema, CLI/API/MCP probes, Web
no-server smoke, and performance smoke pass, but Web, final acceptance,
provider live checks, Stage 2 semantic freshness/live generation, browser e2e,
residual acceptance, and latest audit git gate remain open

## Requirement

The active goal must not be marked complete until the implementation has been reviewed against the design docs and every blocking gap is closed or explicitly accepted by the user.

Commit and push happen only after verification.

## Current Evidence

- The active goal explicitly requires full implementation, E2E tests, design-doc review, visual QA, then commit/push.
- Prior progress docs contain mixed old and new status, so this `docs/gaps/` ledger is the current source of truth.
- The current branch has already pushed implementation commits through `eed0115 Preserve shared register bridges in default graph`; this documentation/visual-audit pass still needs its own artifact hygiene, verification, commit, and push before it can be counted in the gate.
- 2026-05-19 update: the current final graph/workbench gate is now defined by
  `docs/specs/2026-05-19-asip-graph-integration-plan.md` and
  `docs/specs/2026-05-19-current-graph-finalization-plan.md`. The default
  product graph must expose only `function`, `register`, and `doc` nodes;
  historical `doc_section`/`pdf_section`/`doc_box` shapes must project to
  `kind=doc` with `attr.doc_kind`; macro/resolver/source/provider/tmp names
  must stay provenance/attributes; and no-mock browser/e2e proof must use a
  real SQLite DB path.
- 2026-05-19 Product Graph V2 implementation plan is recorded at
  `docs/superpowers/plans/2026-05-19-product-graph-v2-implementation.md`.
  It is the current execution checklist for schema centralization, configurable
  register inventory, typed callback truthfulness, function/register
  normalization, LLM doc/semantic projection, real acceptance surface probes,
  explicit graph filters/budgets, and profile-first full graph optimization.
- 2026-05-19 historical QA is recorded in
  `docs/qa/2026-05-19-product-graph-schema-dbpath-e2e.md`: at that point,
  current-code clean DB audit showed product graph nodes limited to
  `doc/function/register`, clean acceptance rerun was AQ01-AQ09 `9/9` with
  `gemma4:e4b`, core schema unittests ran `87 OK` with `2` optional
  sqlite-vec skips, TypeScript passed, Web API/smoke Playwright ran
  `82 passed`, visual route Playwright ran `15 passed`, and in-app browser
  captured `/graph` and `/acceptance` screenshots at 2048 x 1280. This is
  retained as historical evidence only; it is superseded by the 2026-05-20
  expanded-DB status below and must not be quoted as the current final gate.
- 2026-05-19 historical default DB correction: two empty placeholder corpora
  (`amd-docs`, `local-amd-docs`) with `status=not_indexed`, `file_count=0`, and
  no document/chunk/evidence rows were removed from `data/asip.db` after backing
	  it up to `/tmp/asip-db-before-empty-corpus-clean-2026-05-19.db`. The
	  default DB at that time had three indexed corpora and passed AQ01-AQ09 `9/9`
  across CLI, FastAPI, Web BFF (`ASIP_WEB_BASE_URL=http://127.0.0.1:3111`),
  and MCP. These artifacts are historical after the 2026-05-20 expanded DB
  refresh:
  `docs/qa/2026-05-19-acceptance-data-asip-current.json` and
  `docs/qa/2026-05-19-acceptance-data-asip-current.md`.
- 2026-05-19 natural language graph-query correction: current `/graph?q=who
  will write/read CP_HQD_* regs` now runs a live query on load, returns
  graph-derived function-to-register answer rows, and shows `matches: 24` /
  `graph edges: 552` against `data/asip.db`. Fresh backend, Web API,
  Playwright smoke, TypeScript, and in-app browser evidence is recorded in
  `docs/qa/2026-05-19-product-graph-schema-dbpath-e2e.md`.
- 2026-05-19 subagent audit follow-up: independent read-only audits covered
  backend graph/vtable/callback behavior, Web/UI/e2e DB-path behavior, and
  real DB/QA artifact consistency. They confirmed MVP/product graph evidence
  for deterministic register access, conservative callback/vtable joins,
  cross-repo shared-register bridges, `data/asip.db` current acceptance, and
  Web graph/query surfaces. They also kept completion open for residuals:
  no full clangd/libclang cross-TU points-to extractor, live DB versus clean
  artifact distinction, stale raw semantic rows filtered only by product
  projection, expanded `include/asic_reg` production refresh, artifact hygiene,
  commit, and push.
- 2026-05-19 resolver-scope correction: a new RED/GREEN backend regression
  found that multi-profile indexing could attribute MxGPU `WREG32` evidence to
  `linux-amdgpu` when both profiles were enabled. The index/rebuild path now
  orders resolver profiles per corpus so matching `corpus_id`/repo/alias
  profiles run before fallback profiles. Targeted verification:
  `test_index_registered_corpora_prefers_matching_resolver_profile_per_corpus`,
  the relevant vtable/callback/subfolder live tests, resolver profile backend
  tests, CLI profile selection test, committed resolver profile tests, storage
  graph tests, and query-schema tests.
- 2026-05-19 default-DB audit correction: current live `data/asip.db` is not
  the complete expanded Linux register-header DB. It has real `mxgpu`, docs,
  Stage 1, and `gemma4:e4b` Stage 2 data, but `linux-amdgpu` documents include
  only one code file and no `include/asic_reg` documents. Final completion must
  either rebuild and verify a replacement default DB from the expanded config
  or explicitly keep that production-scale refresh as an accepted residual.
- 2026-05-20 continuation: the expanded `linux-amdgpu` registered corpus was
  re-indexed into live `data/asip.db` and job `10` succeeded with `1101`
  documents, including all `476` `include/asic_reg` register-header documents.
  Job hygiene now marks the old interrupted job `9` as `superseded`, and the
  current acceptance artifact is
  `docs/qa/2026-05-20-acceptance-data-asip-expanded.json` / `.md`: database
  health `pass`, schema `pass` for AQ01-AQ09, AQ05 source diversity restored
  (`code`, `doc`, `pdf`, `register`), summary `0 passed / 8 partial / 1
  failed`, and `gate_status: blocked`. AQ09 now explicitly separates provider
  embedding provenance from coverage (`27` provider embeddings and `125962`
  deterministic fallback embeddings; later rerun also reports `21852` chunks
  with no embedding rows), persisted semantic-edge extraction provenance
  freshness (`14` `ollama/gemma4:e4b` edges from succeeded job `4`, now
  `partial/stale` because latest successful index job is `10` and latest
  graph rebuild job is `12`) and doc-node provenance freshness (`11`
  `ollama/gemma4:e4b` doc-node semantic rows from succeeded job `5`, also
  `partial/stale`) from live provider
  reachability (fail). The gate is still open because Web/browser
  execution is blocked by local `listen EPERM`, AQ09 live semantic-edge
  provider smoke fails with `Operation not permitted`, and
  `docs/qa/2026-05-19-product-graph-v2-final-qa.md` records this as a
  not-complete final gate rather than a pass.
- 2026-05-20 parser/vtable subagent follow-up: independent read-only review
  found that workbench cross-file pre-collection still read raw source for
  function locations and receiver aliases. New live-index regressions first
  reproduced disabled `#if 0` receiver alias/function-location leakage, then
  passed after the collector path was changed to use the same masked source
  scan as `build_deterministic_code_graph`.
- 2026-05-20 final audit follow-up: three more independent reviews checked
  parser/vtable behavior, Web/e2e DB-path behavior, and acceptance/provider
  evidence. New RED/GREEN fixes cover inactive `#elif` callback/direct-call
  leakage, compile-command preprocessed string resolver leakage, generic
  non-callback `ops->slot()` overlinking in both parser and workbench two-phase
  joins, lowercase function endpoints in Stage 2 semantic-edge allowlists,
  explicit blank `dbPath` fallback in Web routes/UI request helpers, strict
  missing-kind/relation schema failure, semantic-edge provenance binding to a
  succeeded semantic job, provider embedding coverage reporting, and invalid
  AQ09 provider timeout values. Follow-up Web tests now include HTTP-level
  blank `dbPath` 400 coverage and stricter `/graph?dbPath=...` e2e data-change
  assertions for function view and free query, but those remain listed/compiled
  rather than browser-executed in this local environment.
  Current local verification for this follow-up: `test_code_graph` `42 OK`,
  targeted live callback/disabled-source tests `3 OK`, acceptance/schema tests
  `19 OK`, combined code-graph/acceptance/schema suite `64 OK`, request-path
  helper smoke pass, Web eslint pass, TypeScript pass, Playwright discovery for
  the stricter blank-dbPath/graph-data-change tests, Playwright config smoke
  proof that default server reuse is false, browser-gate preflight proof that
  the current environment returns `EPERM` before local Web server startup, and
  `git diff --check` pass. This is still not a completion claim because
  browser e2e and live semantic-edge provider smoke remain blocked by the
  current environment.
- 2026-05-20 subagent audit follow-up 2: Web review found the no-mock
  `/graph?dbPath=...` e2e definition needed visible rendered-graph assertions,
  not just API payload assertions; parser review found nested
  `holder->ops->start()` could still generic-dispatch to unrelated callback
  tables; provider review found embedding coverage ignored chunks with no
  embedding rows. Fixes now cover rendered `force-graph` totals/summary after
  function-view and query transitions, nested non-callback receiver guards in
  both Stage 1 and workbench two-phase joins, and AQ09
  `total_chunks`/`embedded_chunks`/`missing_embedding_chunks` reporting. Current
  verification after these fixes: combined `test_code_graph` +
  `test_acceptance_runner` + `test_graph_schema` `66 OK`, targeted workbench
  live callback/semantic endpoint suite `6 OK`, acceptance full rerun keeps
  `gate_status: blocked` and now reports `21852` chunks with no embeddings.
- 2026-05-20 subagent audit follow-up 3: Stage 2 semantic endpoint filtering
  now uses the shared product graph endpoint classifier before trusting
  `entity_type`, so local callback/provenance names such as `init_func`,
  `init_funcs`, `ops`, `callbacks`, `tmp_value`, and `GC` cannot enter product
  semantic edges even when mislabeled as `function`/`register`. Focused
  verification preserves real MxGPU `init_func->hw_init` Stage 1 callback
  dispatch and keeps lowercase function semantic endpoints working.
- 2026-05-20 preprocessor branch follow-up: Stage 1 masking now treats
  undefined `CONFIG_*` branches conservatively across `#ifdef`, `#ifndef`,
  `defined(CONFIG_*)`, `IS_ENABLED(CONFIG_*)`, and simple `!` / `&&` / `||`
  expressions. New RED/GREEN tests cover both disabled direct-call function
  spans and disabled callback initializers so config-gated code cannot leak
  false product graph edges when no compile-time definition proves it active.
  Verification after this follow-up: `test_code_graph` `45 OK`,
  `test_code_graph.py` under pytest `45 passed`, and combined
  `test_code_graph` + `test_acceptance_runner` + `test_graph_schema` `68 OK`.
- 2026-05-20 subagent audit follow-up 4: independent parser/provider/Web
  reviews found no old-level vtable overlink regression, but did expose two
  proof-strength issues: compile-defined `CONFIG_*` branches could be masked
  out as false negatives, and old semantic edges could still count as
  persisted provider provenance after a newer index or graph rebuild job.
  Stage 1 now feeds compile-command/clang `-D` symbols into source masking and
  collector paths;
  live-index tests prove config-gated callback initializers/direct calls are
  preserved when compile args define the config. The provider gate now marks
  semantic-edge provenance `partial` when matching semantic edges are older
  than the latest successful index or graph rebuild job. Current expanded
  acceptance records `14` stale semantic edges from job `4`, latest index job
  `10`, latest graph rebuild job `12`, and
  `semantic_edge_provenance=partial`; AQ09 remains `fail`, and overall
  `gate_status` remains `blocked`. Verification at that point: `test_code_graph`
  `46 OK`, `test_code_graph.py` under pytest `46 passed`, combined
  `test_code_graph` + `test_acceptance_runner` + `test_graph_schema` `70 OK`,
  targeted workbench live callback/config/semantic endpoint suite `11 OK`,
  Web TypeScript and targeted eslint exit `0`, Playwright discovery lists
  `106` tests, and browser preflight still records local `listen EPERM`.
- 2026-05-20 provider gate follow-up: AQ09 now includes a live embedding
  provider smoke (`embedding_live`) in addition to embedding provenance,
  embedding coverage, semantic-edge provenance freshness, and live
  semantic-edge generation. Fake Ollama/OpenAI-compatible tests prove the
  live embedding smoke can pass via configured transports, and a failing
  transport regression proves provider unreachability becomes an AQ09 failure
  rather than hidden behind persisted embedding rows. Current expanded
  acceptance records `embedding_live=fail` with `Operation not permitted`;
  AQ09 remains `fail`, and overall `gate_status` remains `blocked`.
  Follow-up provider-gate CLI work adds `asip provider-gate` as a fast
  preflight that writes
  `docs/qa/2026-05-20-provider-gate-preflight.json`; the real `data/asip.db`
  run now reports database health `pass`, provider checks `0 passed / 3
  partial / 2 failed`, and the same `Operation not permitted` blocker for live
  Ollama embedding/semantic calls. The additional partial check is
  `doc_node_provenance`, which blocks stale doc-node semantic rows from job `5`
  after latest index job `10` and graph rebuild job `12`. Current verification
  after this follow-up:
  acceptance runner `24 OK`, CLI provider-gate artifact test `1 OK`, combined
  `test_code_graph` + `test_acceptance_runner` + `test_graph_schema` `73 OK`,
  and the then-current two-test workbench live callback/config smoke passed.
  Later parser/UI proof refresh expanded the persisted workbench-live coverage
  to the three
  address-of callback initializer, direct indexed MxGPU receiver, and
  `_ip_block_version` registration paths; see the 2026-05-20 parser/UI proof
  refresh entry below for the current direct indexed alias-leak hardening and
  full `test_workbench_live` `77 OK` result.
- 2026-05-20 Playwright gate hardening: `apps/web/playwright.config.ts` now
  starts a fresh Web server by default; stale server reuse requires the
  explicit `PLAYWRIGHT_REUSE_EXISTING_SERVER=1` opt-in, and
  `PLAYWRIGHT_WEB_SERVER_COMMAND` can name a controlled launch command. This
  closes the stale-3100 false-positive path for the next no-mock browser run,
  but it does not replace the still-missing browser execution evidence.
- 2026-05-20 current performance smoke refresh: `asip performance-smoke`
  reran against `docs/fixtures/performance-smoke` from two empty DBs and wrote
  `docs/qa/2026-05-20-performance-smoke-fixture-current.md` / `.json`.
  Counts matched (`documents=2`, `chunks=2`, `evidence=19`, `edges=4`), five
  queries returned rows under the `1.0s` threshold, and the focused
  performance smoke unittest/CLI test ran `2 OK`. This refreshes the
  fixture-scale performance gate for the current tree, but it does not replace
  browser/e2e or live provider evidence.
- 2026-05-20 current goal completion audit is recorded in
  `docs/qa/2026-05-20-current-goal-completion-audit.md`. It preserves the full
  active objective and marks each requirement as proven, blocked, residual, or
  missing. The audit keeps the goal open because fresh browser/e2e, live
  provider checks, stale semantic-edge refresh, G13 residual acceptance, and
  final git gate are still not complete.
- 2026-05-20 parser/UI proof refresh: a final subagent review added red/green
  coverage for address-of callback initializers, direct indexed MxGPU receiver
  dispatch, and `_ip_block_version` registration flow. The acceptance UI smoke
  now verifies that the Web surface checkbox is included with CLI/API/MCP in the
  run request. A follow-up live-index review added persisted-edge coverage for
  those same three parser paths through `index_registered_corpora`, SQLite
  `edges`, and `global_graph`; the direct indexed MxGPU receiver fixture now
  includes a decoy `amdgv_init_func` candidate and exact `receiver_tables`
  assertion, and a follow-up leak regression proves `adapt->init_funcs[0]`
  wiring in one function does not become a global alias for unrelated direct
  indexed callers. The `_ip_block_version` suffix test now checks `global_graph`
  output too. Provider-gate artifact truthfulness now has a regression proving
  stale semantic-edge provenance stays `partial` and `gate_status=blocked` in
  written JSON, and full acceptance artifact truthfulness now has a matching
  regression proving AQ09 fails with top-level `gate_status=blocked` when
  semantic-edge provenance is stale. Verification at that point: targeted
  parser/provider/root-script hardening tests pass; combined `test_code_graph`
  + `test_acceptance_runner` + `test_graph_schema` `79 OK`; full
  `test_workbench_live` `77 OK` with `1` real-Ollama skip; `pnpm run
  test:ui:no-server` passes with request helper, explicit blank `dbPath`,
  Playwright config, and Playwright discovery checks; discovery lists `106`
  tests and verifies the acceptance configurable runner smoke is still
  registered. `pnpm run test:ui:preflight -- --timeout-ms 500 --allow-blocked`
  now works from the repo root and records local listen, target-port listen,
  and target-connect probes, all blocked by `EPERM` in this environment.
- 2026-05-20 final subagent triage refresh: three current read-only subagents
  reviewed parser/vtable, Web/e2e, and provider/acceptance gates. Parser review
  found two narrow proof gaps: slot calls inside compile-defined `CONFIG_*`
  function bodies and direct `*_ip_block_version` assignments. Stage 1 and
  workbench-live tests now cover both; `_slot_calls_for_function` keeps the
  known compile symbols during its internal mask pass, and direct version
  aliases resolve nested `version->funcs` dispatch without overlinking decoy
  blocks. Web review added no-listen smokes for no-mock test hygiene,
  acceptance route command wiring, and current blocked-artifact invariants.
  Provider review confirmed the current blockers are truthful and clarified
  the count boundary: whole `data/asip.db` is `1224 docs / 147841 chunks /
  5299434 evidence / 39399 edges / 125989 embeddings`, while the expanded
  `linux-amdgpu` slice is `1101 docs / 125962 chunks`. Current verification:
  combined `test_code_graph` + `test_acceptance_runner` + `test_graph_schema`
  + `test_completion_gate` + `test_closure_gates` `102 OK`; full
  `test_workbench_live` `78 OK` with
  `1` real-Ollama skip;
  `docs/qa/2026-05-20-ui-no-server-smoke.json` records no-server Web smoke
  `9/9` passing including the new hygiene/invariant/artifact-producer smokes and the
  existing-target browser preflight assertion that listen probes are skipped;
  targeted Web
  script eslint passes; refreshed browser and provider preflights remain
  blocked by `EPERM` / provider reachability and stale semantic provenance,
  respectively.
- 2026-05-20 in-app browser blocker refresh: Codex in-app Browser was used
  directly against `http://127.0.0.1:3100/graph?dbPath=data/asip.db`,
  `http://localhost:3100/graph?dbPath=data/asip.db`,
  `http://127.0.0.1:3101/graph?dbPath=data/asip.db`, and
  `http://localhost:3101/graph?dbPath=data/asip.db`; all attempts returned
  `ERR_BLOCKED_BY_CLIENT`. The blocker is recorded in
  `docs/qa/2026-05-20-in-app-browser-probe.json` and is now checked by
  `apps/web/scripts/current-artifact-invariants-smoke.mjs`. It remains
  distinct from the shell preflight artifact, so it cannot be counted as
  browser/e2e proof.
- 2026-05-20 browser/completion hardening refresh: `completion-gate` now
  accepts `--in-app-browser-json` and records the Codex in-app Browser blocker
  in the `browser_e2e` requirement. `apps/web/scripts/browser-e2e-artifact.mjs`
  now provides the future real Playwright artifact producer for
  `source=asip.web.browser_e2e`; shell preflight and in-app Browser probes
  remain blockers only, not no-mock e2e proof. The current artifact invariant
  smoke now fails if the aggregate gate stops loading the in-app Browser
  artifact, drops the `ERR_BLOCKED_BY_CLIENT` blocker from `browser_e2e`, or
  loses the `test:ui:artifact` script entry for the real e2e artifact producer.
  The e2e artifact producer also now rejects all-skipped Playwright JSON reports
  by requiring at least one passed test before it can write `gate_status=pass`.
- 2026-05-20 Web-included acceptance refresh:
  `docs/qa/2026-05-20-acceptance-data-asip-expanded-web-blocked.md` now runs the
  current expanded `data/asip.db` acceptance with CLI/API/Web/MCP explicitly
  requested. CLI/API/MCP probes return rows and schema `pass`, but all Web
  probes are `not_configured` without `ASIP_WEB_BASE_URL`; AQ09 also keeps the
  provider/semantic-edge failures. The run is `0 passed / 0 partial / 9 failed`
  and keeps G10/G11 blocked until a real browser/Web BFF run is available.
- 2026-05-20 completion-gate aggregator: `python3 -m asip.cli completion-gate`
  now writes `docs/qa/2026-05-20-current-goal-completion-gate.json` and `.md`
  by reading the real `data/asip.db`, CLI/API/MCP acceptance, Web-included
  acceptance, provider gate, runtime semantic freshness, browser gate, in-app
  Browser blocker, Web no-server smoke, performance smoke, residual
  acceptance, and git gate artifacts. The current aggregate is
  `gate_status=blocked` with `8/15` requirements passing and no missing
  requirements: expanded real DB, artifact DB/job binding, deterministic Stage
  1 graph, product graph schema, CLI/API/MCP probes, runtime semantic
  freshness, Web no-server smoke, and performance smoke pass; Web surface,
  final acceptance, provider live gate, Stage 2 semantic freshness/live
  generation, browser e2e, G13 residual acceptance, and final git closure
  remain blocked. The gate now rejects AQ subsets, tiny non-expanded DBs, stale
  Stage 1 graph rebuilds older than the latest index, mismatched DB artifacts,
  stale provider semantic/doc-node provenance index/graph job bindings,
  pass-looking semantic provenance artifacts that still report stale edges,
  missing provider checks, malformed provider-check payloads, missing or
  non-pass AQ09 provider-check details in acceptance artifacts, runtime
  semantic freshness failures, browser e2e artifacts missing required no-mock
  Playwright tests, preflight and in-app Browser artifacts masquerading as
  browser e2e proof, unaccepted residual
  boundaries, dirty worktrees, missing upstreams, and unpushed closure. The
  current residual and git closure artifacts are
  `docs/qa/2026-05-20-residual-acceptance-gate.json` and
  `docs/qa/2026-05-20-git-gate.json`; both are loaded by the aggregate gate
  and correctly blocked. Focused completion-gate tests now run `21 OK`, and the
  new closure-gate tests added `4 OK`.
- 2026-05-20 Stage2/provider hardening refresh:
  `docs/qa/2026-05-20-stage2-provider-hardening-qa.md` records the latest
  gate hardening. Provider semantic-edge live smoke now requires at least one
  product-schema-persistable edge, legacy successful job status words such as
  `generated` and `indexed` are normalized by the provenance gate, and runtime
  graph reads now filter `extractor=semantic_edges` rows that lack valid job
  provenance. Provider and completion gates now also require
  `doc_node_provenance`, so stale LLM document-node semantic rows cannot be
  treated as harmless ignored semantic-edge rows. Runtime product graph reads
  now also bind extractor to job kind: `doc_nodes` rows require
  `doc_nodes_batch` jobs and `semantic_edges` rows require
  `semantic_edges`/`semantic_edges_batch` jobs. The acceptance runner and
  completion gate now share the provider-check ID list, and the completion gate
  blocks if AQ09 acceptance detail omits any of the five provider checks or
  reports a non-pass provider detail; malformed provider-gate `provider_checks`
  payloads now fail closed instead of crashing or passing by omission. Latest
  targeted verification ran `test_acceptance_runner + test_completion_gate` as `53 OK`,
  `test_closure_gates` as `4 OK`, `test_storage_graph` as `68 OK` with `2`
  optional sqlite-vec skips, and current artifact/browser-e2e/no-server Node
  smokes with no-server `9/9` passing. The real provider artifact remains
  blocked with `0 passed / 3 partial / 2 failed`; semantic-edge job `4` and
  doc-node job `5` are both stale relative to index job `10` and graph rebuild
  job `12`. Final combined storage/parser/acceptance/schema/completion/closure
  verification after the AQ09 provider-detail schema hardening ran `184 OK`
  with `2` optional sqlite-vec skips.
- 2026-05-20 mixed semantic provenance hardening: Stage 2 provenance now blocks
  mixed fresh+stale semantic-edge rows instead of passing as soon as one fresh
  row exists. Completion gate also rejects pass-looking provider artifacts that
  still report `stale_edge_count > 0`, and provider artifact binding now has
  explicit index-job and graph-job mismatch regressions.
- 2026-05-20 runtime semantic freshness hardening: the product graph runtime now
  filters semantic rows whose persisted job provenance is older than the latest
  succeeded index or graph rebuild job, and also filters semantic rows generated
  under previous provider settings when the current provider/model differs.
  This closes the stale semantic runtime leak risk without disabling fresh
  semantic graph output: fresh matching-provider semantic jobs still appear in
  `global_graph`. Real `data/asip.db` probing is recorded in
  `docs/qa/2026-05-20-runtime-semantic-freshness-qa.json`: all-edge runtime
  graph returned `23026` deterministic edges and `0` visible semantic edges;
  the focused query probe returned `8` rows and `0` semantic query-graph edges.
  Verification after this follow-up: `test_storage_graph` `68 OK` with `2`
  optional sqlite-vec skips, targeted workbench fresh semantic-job tests `2 OK`,
  and combined storage/parser/acceptance/schema/completion/closure suite
  now has a latest refresh of `184 OK` with `2` optional sqlite-vec skips. This is not a completion pass
  because live Stage 2 provider generation, Web/browser e2e, residual
  acceptance, and git closure remain blocked.
- 2026-05-20 browser artifact and module CONFIG hardening: the future
  `source=asip.web.browser_e2e` artifact must now include the four required
  no-mock Playwright tests for real AQ01 acceptance through the Workbench API,
  `/graph` URL `dbPath`, graph layer provenance, and evidence-page URL
  `dbPath`; partial or forged reports stay blocked in both the artifact
  producer and completion gate. Stage 1 preprocessor masking now follows Linux
  helper semantics: `IS_ENABLED(CONFIG_FOO)` accepts builtin or module configs,
  `IS_REACHABLE(CONFIG_FOO)` accepts module configs only when the compile unit
  also defines `MODULE`, and `IS_BUILTIN(CONFIG_FOO)` stays false for
  module-only configs. It also reads simple `#define`/`#undef` CONFIG macros
  from `-include`/`-imacros` forced headers, covering autoconf-style module
  configs in both parser and workbench indexing paths. The completion gate now
  keeps core AQ01-AQ09 acceptance separate from Web `not_configured`, and
  supplemental in-app/preflight blockers no longer override a real passing
  browser e2e artifact. Browser e2e artifacts must also carry a raw Playwright
  report path and matching SHA-256 hash. `test_code_graph` now runs `57 OK`;
  `test_workbench_live` now runs `79 OK` with `1` opt-in real Ollama skip.
- 2026-05-20 numeric CONFIG and post-index Stage 1 refresh: read-only parser
  review found false-pass risk for `#if CONFIG_FOO == 1`,
  `#if CONFIG_FOO != 0`, and `-DCONFIG_FOO=0`. Stage 1 masking now preserves
  simple `-D` macro values and evaluates numeric/equality config expressions
  before scanning direct calls, callback initializers, and slot calls. The real
  `data/asip.db` deterministic graph was rebuilt after the fix as
  graph_rebuild job `12`, after latest index job `10`, with `1122` code files
  and `39362` emitted deterministic edges; the current DB edge count is
  `39399`.
- 2026-05-20 final local gate refresh: the real `data/asip.db` deterministic
  graph was rebuilt again after the Linux `IS_REACHABLE` correction as
  graph_rebuild job `13`, after latest index job `10`, with `1122` code files
  and `39362` emitted deterministic edges; the current DB edge count remains
  `39399`. Acceptance surface probes now fail closed on malformed row/graph
  payloads, the completion gate blocks on failed or unfinished jobs in the
  current DB even when old artifacts look green, and browser e2e proof now
  requires raw Playwright report hash binding. The acceptance Playwright set
  includes the new no-mock AQ01 real Workbench API test, and discovery now lists
  `107` tests. Current verification after this refresh: `test_acceptance_runner
  + test_completion_gate` `56 OK`, combined
  storage/parser/acceptance/schema/completion/closure suite `188 OK` with `2`
  optional sqlite-vec skips, full `test_workbench_live` `79 OK` with `1`
  opt-in real Ollama skip, no-mock hygiene `4` tests checked, browser e2e
  artifact smoke pass, no-server smoke `9/9` pass, and completion gate
  `8/15` pass with `7` blockers and `0` missing. Provider semantic-edge job
  `4` and doc-node job `5` are now stale relative to graph rebuild job `13`;
  browser/e2e, live provider reachability, Stage 2 refresh, residual
  acceptance, and git closure remain blockers.
- 2026-05-20 gate hardening refresh: completion evidence now rejects offline
  `playwright-json-report` artifacts as final browser proof, requires raw
  Playwright report SHA binding plus current DB, target URL `dbPath`,
  latest index/graph rebuild job IDs, and a live `pnpm exec playwright test`
  command, and the browser artifact producer now keeps offline report replays
  blocked as diagnostics instead of marking them final proof. The gate requires
  Web pass artifacts to prove Next BFF transport, matching
  `db_path`, rows, graph nodes, and graph edges, requires runtime freshness
  artifacts to match current index/graph/semantic/doc-node job IDs, and
  requires Stage 2 pass artifacts to
  report positive edge counts plus job IDs and zero invalid semantic job
  provenance. Runtime graph reads now fail closed
  for both `semantic_edges` and `doc_nodes` extractor rows without valid job
  provenance, and completion DB health now tracks both query-mode
  `semantic_edges` and batch `semantic_edges_batch` jobs with normalized
  legacy success statuses such as `generated`. Macro-wrapped singular
  `amdgv_init_func` initializer tables are covered by parser and
  workbench-live regressions. Verification after this
  refresh: combined storage/parser/acceptance/schema/completion/closure suite
  `212 OK` with `2` optional sqlite-vec skips, full `test_workbench_live`
  `80 OK` with `1` opt-in real Ollama skip, no-server smoke `9/9` pass,
  current artifact invariants pass, `git diff --check` pass, and completion
  gate remains truthfully blocked at `8/15` pass with `7` blockers and `0`
  missing. The current artifact invariant and no-server smoke scripts now
  accept explicit artifact paths and the refreshed no-server artifact records
  those paths with byte counts and SHA-256 hashes, avoiding stale date-stamped
  JSON checks during the final gate. The completion gate now recomputes the
  required no-server input hashes for browser, in-app Browser, provider,
  runtime-semantic, acceptance, and Web-acceptance artifacts; a stale recorded
  input hash blocks `web_no_server_smoke` instead of letting an old no-server
  artifact stay green.
- 2026-05-20 final gate hardening refresh 2: current read-only subagent
  reviews found no new parser/vtable overlink regression, but did expose
  four proof-strength gaps. Fixes now make residual acceptance fail closed
  when only some ledger rows that explicitly need acceptance are listed,
  make browser e2e completion proof recompute raw Playwright summary/errors
  from the bound report instead of trusting artifact summary alone, make
  provider provenance `job_ids` bind to real succeeded current-DB jobs of the
  expected semantic/doc-node kind, and make Stage 1 deterministic graph
  rebuild fail the job when a file-level parse raises instead of silently
  skipping the file. A follow-up browser proof hardening now also binds each
  required no-mock browser e2e test to `workbench-smoke.spec.ts` in both the
  artifact and raw Playwright report, so same-title tests from another spec
  are `wrong_source` instead of final proof. The refreshed completion gate was
  generated at `2026-05-20T10:39:11+00:00` and remains truthfully blocked at
  `8/15` pass with `7` blockers and `0` missing. Latest verification after
  that source-binding hardening: `test_completion_gate` `41 OK`, combined
  storage/parser/acceptance/schema/completion/closure suite `213 OK` with `2`
  optional sqlite-vec skips, current artifact invariants pass, browser e2e
  artifact smoke pass, and no-server smoke `9/9` pass with Playwright
  discovery still at `107` tests.
- 2026-05-21 semantic-quality completion-gate binding: the completion gate now
  accepts `--semantic-quality-json` and requires the labeled
  `source=asip.semantic_quality_eval` artifact in real final mode. The new
  `semantic_quality` requirement checks gate status, per-case pass status,
  non-empty result rows, summary totals, zero failures, and at least one
  provider-vector case, while fixture-style completion-gate runs can still omit
  the artifact. This binds the labeled semantic rerank evaluation to the final
  completion gate instead of leaving it as a detached QA artifact.
- Historical final-candidate evidence package exists at
  `docs/qa/2026-05-17-final-clean-evidence-package.md`, linking the clean AMD
  DB, AQ01-AQ09 9/9 artifact, six free queries, semantic-edge jobs, visual QA,
  automated verification, and architecture review. This is background evidence,
  not the current 2026-05-20 expanded-DB completion proof.
- Historical clean-final artifact is
  `/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db`, with
  `graph_rebuild`, `semantic_edges_batch`, and `doc_nodes_batch` jobs all
  succeeded, AQ01-AQ09 `9/9`, and macro/wrapper endpoint checks recorded in
  `docs/qa/2026-05-18-clean-final-stage2-and-macro-qa.md`; it must not be
  cited as current final-gate pass evidence.
- Current clean provider gate is `gemma4:e4b`. Older qwen artifacts remain
  historical comparison evidence and must not be cited as the current clean
  pass.
- Historical automated rerun after the 2026-05-18 implementation pass was green: core unittest 239 OK with 2 optional sqlite-vec skips; API/MCP unittest 47 OK with 1 optional MCP runtime skip under system Python; bundled-Python real MCP suite 29 OK with 0 skips from the previous G07 runtime pass; lint passed; TypeScript check passed; visual route Playwright 15 passed. This remains background evidence, not the current final-gate proof after the 2026-05-20 expanded DB and parser/provider follow-ups. Clean-final/default browser QA is recorded in the browser screenshots under `docs/qa/browser/`, the six-route dark/light pack under `docs/qa/visual-qa-2026-05-18-final-web-pack/`, and the register/performance follow-up in `docs/qa/2026-05-18-g03-register-ip-version-merge-and-profile-qa.md`.
- 2026-05-18 continuation after the user asked to continue added current QA for full local provider embedding coverage, function-node graph fallback, real 10-query graph checks, in-app browser 2K graph screenshots, hidden static graph fallback cleanup, and semantic-edge dedupe. Artifacts: `docs/qa/2026-05-18-g06-full-provider-backfill-tempdb-qa.md`, `docs/qa/2026-05-18-g03-real-query-graph-function-fallback-qa.md`, and `docs/qa/2026-05-18-g14-static-limit-cleanup-qa.md`.
- 2026-05-18 design/visual audit continuation added `docs/qa/2026-05-18-design-review-closure-matrix.md` and `docs/qa/visual-qa-2026-05-18-final-web-pack/`, explicitly mapping MVP G1-G6 and AQ01-AQ09 to current evidence and capturing all six routes in dark/light at 2048 x 1280.
- `git diff --check` passed after the current changes, and generated `apps/web/tsconfig.tsbuildinfo` plus the temporary root screenshot were removed from the worktree.
- 2026-05-17 user review reopened the completion gate for UI: package-backed graph rendering, shadcn-native UI composition, static-data cleanup, and expandable acceptance detail QA. Those blockers now have implementation and test evidence in `docs/qa/2026-05-17-graph-function-section-batch-qa.md`.
- Bundled Python 3.12 MCP runtime smoke is recorded in `docs/qa/2026-05-18-g07-real-mcp-runtime-smoke.md`; `apps.mcp.tests.test_tools` and `apps.mcp.tests.test_server` ran 29 tests with zero skips.

## Remaining Gap

Completion evidence is now separated in the final-candidate QA package and the
2026-05-18 graph/UI/acceptance-detail/design-review blocker pass is documented.
The branch is not complete until the 2026-05-19/2026-05-20 current graph final
gate is executed for the latest audit changes: artifact hygiene, final diff
review, commit, push, and explicit acceptance or implementation of residual
boundaries such as full clangd/libclang cross-TU type-flow, credentialed
OpenAI-compatible live QA, live semantic-edge provider smoke, final Stage 2
refresh if required, and browser/e2e evidence. Current product schema
validation, document subtype projection, default-DB indexing, stale-job
hygiene, and CLI/API/MCP acceptance evidence now exist for the current tree,
but they must not be overstated as proof of the full final gate until
browser/provider evidence is verified against the selected final DB candidate
or explicitly accepted as residuals. The fixture-scale performance smoke is
currently recorded as passing and is not one of the seven aggregate blockers.

The final gate must also distinguish design completion from implementation
completion. The V2 plan can be complete as a document, but the active goal is
not complete until those V2 tasks either pass current tests/QA or are explicitly
accepted as residuals. In particular, acceptance surface labels, visual-mock
route tests, and older clean qwen/gemma artifacts cannot substitute for current
real transport probes and no-mock graph e2e.

The final branch must avoid staging generated local artifacts such as `data/asip.db`, `apps/web/tsconfig.tsbuildinfo`, Python `__pycache__`, and transient browser screenshots outside `docs/qa`.

Completion must follow this order:

1. Reconcile final docs against `docs/gaps/README.md`, the gap register, the AQ matrix, and [Final Clean Evidence Package Gate](2026-05-17-final-clean-evidence-package.md).
2. Reconcile
   `docs/specs/2026-05-19-asip-graph-integration-plan.md` and
   `docs/specs/2026-05-19-current-graph-finalization-plan.md` against the gap
   ledger so older five-kind document-node wording is clearly historical.
3. Confirm the currently implemented G03/G10/G14/G16/G17 blockers remain green:
   package-backed graph, shadcn/Radix UI pass, expandable acceptance details,
   static-data cleanup, and visible graph filters/budgets.
4. Add or preserve current schema/no-mock evidence: only
   `function/register/doc` product nodes, enum edge relations, real SQLite DB
   path through `/graph`/acceptance, API/MCP/Web parity, and no mock payloads.
5. Preserve the full automated core/API/MCP/Web/build/lint/diff verification suite results after those changes.
6. Preserve fresh browser visual QA after the final functional change, including light and dark themes.
7. Review `git status --short` and generated/local artifact hygiene.
8. Commit and push only after the previous steps are recorded in the final QA doc.

## Acceptance Criteria

- `docs/gaps/README.md` shows every gap as closed or user-accepted deferred.
- `docs/gaps/2026-05-17-gap-inventory-before-code.md` is updated or superseded with the final gap inventory.
- `docs/specs/2026-05-16-asip-workbench-gap-review.md` points to the current gap index and no longer implies stale completion.
- [Final Clean Evidence Package Gate](2026-05-17-final-clean-evidence-package.md) is complete or each missing field is explicitly user-accepted as out of scope.
- Final QA doc lists exact verification commands and results.
- Final QA doc distinguishes 2026-05-18 candidate pass evidence from 2026-05-19
  current final-gate evidence.
- Final QA doc records the current clean semantic provider as `gemma4:e4b`; any
  qwen evidence is explicitly historical.
- Design review explicitly maps ASIP MVP-1 G1-G6 and all nine acceptance queries to implemented evidence.
- Worktree excludes cache/build artifacts from staging.
- Commit and push occur only after all verification passes.

## Required Tests And Checks

- `git status --short` reviewed before staging.
- Full automated test/build/lint/diff suite passes.
- Browser visual QA completed after the final build.
- `git diff --check` passes.
- Commit message references closed gap IDs.

## Not Closed Until

The user can inspect the docs and see exactly why the repo is complete, or exactly what remains.
