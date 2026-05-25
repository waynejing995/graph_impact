# LLM Blackbox Graph Overlay Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Stage 2.5 blackbox overlay that uses local `gemma4:e4b` to generate auditable input-output behavior profiles for AST-derived ASIP graph endpoints.

**Architecture:** Stage 1 deterministic graph remains the grounded endpoint source. Storage exposes an unbudgeted product endpoint inventory; Workbench schedules a bounded large LLM loop with a deterministic selection manifest, batch/attempt ledger, content grounding validators, and a canonical `blackbox_profiles` table; product graph projection enriches existing `function/register/doc` nodes with `attr.blackbox`; CLI/API/Web/browser QA proves the current DB path and layer counts.

**Tech Stack:** Python core, SQLite, ASIP storage graph projection, existing Ollama/OpenAI-compatible provider adapters, local `gemma4:e4b`, Next.js Workbench UI, Playwright/browser QA.

---

## 2026-05-22 Four-Path Grill Closure

Four parallel grill analyses completed (architecture, LLM loop, UI/semantic, evidence chain) using real-DB runs. Key findings:

### Job 67/68 Real-DB Data
| Job | Candidates | batch_size | Profiles | Edges | Gate |
|---|---|---|---|---|---|
| 67 | 2 | 1 (hardcoded) | 0 | 0 | 1 failed (parse), 1 rejected (1/3 accepted) |
| 68 | 1 | 1 | 1 | 3 | 16/16 ledger pass, 0.036% coverage |

Root cause of job 67 failures: `num_predict=1024` truncation + `temperature=0` sample identity + single compact retry insufficient.

### Task 0 Critical Fixes (from grill findings)
- **P0 fix: Un-hardcode `batch_size=1`** (workbench.py:2131). Current code ignores `requested_batch_size` and always uses `batch_size=1`, wasting manifest/batch overhead on single-candidate jobs.
- **P0 fix: Increase retry ladder** from 1 compact retry to 3 escalating prompt formats (standard → compact → pure-JSON list).
- **P0 fix: Raise `num_predict`** from 1024 to 1536-2048 to reduce truncation.
- **P0 fix: Set `temperature=0.1-0.3`** instead of 0 for genuine sample independence.
- **P0 fix: Coverage gate configurable** — `--min-blackbox-coverage` flag instead of hardcoded 1.0.

### Deferred to P1 (no longer blocks Task 0)
- Force-graph blackbox node visual differentiation (node color/size). Inspector already works.
- Concept/implementation cross-view consistency check.
- LLM-as-judge relationship semantic validation.

## 2026-05-22 Subagent Grill Reset

The next slice supersedes the older "finish the first batch loop" framing.
The product definition is now:

> AST-derived product endpoints become blackbox semantic nodes when local
> `gemma4:e4b` generates, critiques, reconciles, validates, and persists their
> input-output behavior profiles.

Endpoint ids still come from deterministic AST/product projection. The LLM
generates the blackbox method profile and candidate relationship intent; the
system validates and projects only grounded facts.

### P0 Slice

- [x] **Step 1: Entity ledger migration**

  Add additive tables for `blackbox_manifests`,
  `blackbox_manifest_candidates`, `llm_provider_responses`,
  `blackbox_validation_failures`, and `blackbox_io_facts`. Keep existing
  `llm_batches`, `llm_attempts`, `blackbox_profiles`, and
  `edges.provenance_json.extractor="blackbox_profiles"` semantics intact.

- [x] **Step 2: Profile-first gemma4 runner**

  Change the P0 scheduler to `batch_size=1`, profile-only prompts, three
  samples per selected candidate, strict parse recording, validator-backed
  sample checks, and simple `2/3` reconcile. Do not persist relationships
  directly from LLM free text. A separate LLM critic remains deferred until the
  current provider-response ledger is proven against real `gemma4:e4b`.

- [x] **Step 3: Grounded relationship projection**

  Derive blackbox relationship edges from accepted profile refs,
  deterministic neighbors, and the candidate allowlist. Record rejected
  relationships with validation failure reasons.

- [x] **Step 4: Required blackbox evidence mode**

  Add a completion gate mode such as `--require-blackbox-ledger`. In that mode,
  missing or stale blackbox QA is red, and the artifact must match current
  `db_path`, `db_sha256`, `repo_head`, latest blackbox job id, provider/model,
  prompt hashes, response hashes, manifest group, and terminal attempt counts.

- [x] **Step 5: UI semantic grammar**

  Expose explicit `meta.layers`, `edge.layer`, `edge.provenance_type`, and
  blackbox generated-by/rounds metadata. Reframe the graph UI as `System
  Boundary`, `Opened Blackbox`, and `Evidence Trail`; put
  Inputs/Behavior/Outputs/Evidence before raw graph metadata in the node
  inspector.

### P0 Red Tests

- [x] Missing `--blackbox-ledger-json` fails when blackbox evidence is required.
- [x] Stale `db_path`, `db_sha256`, `repo_head`, or latest blackbox job id fails.
- [x] Non-terminal attempts or incomplete manifest group shard coverage fails.
- [x] Accepted profiles missing prompt/response/provider/model/job/batch/attempt/candidate provenance fail.
- [x] No-mock browser QA must see blackbox layers and inspector behavior against the same explicit DB path.

### Deferred

- [ ] `blackbox_component_links` table for recursive parent-to-child decomposition.
- [ ] Full all-corpus self-consistency/golden-label scoring.
- [ ] Complex nested graph navigation; P0 uses inspector drilldown.
- [ ] Hosted OpenAI-compatible proof if local Ollama/gemma remains the accepted boundary.

### Coverage Audit

- [x] Add `blackbox-coverage-qa` to measure usable profile coverage against the
  full AST-derived product endpoint inventory.
- [x] Generate current real-DB coverage evidence:
  `docs/qa/2026-05-22-blackbox-coverage-qa-real.{json,md}`.
- [ ] Scale the gemma4 loop beyond pilot coverage. Current real DB coverage is
  `5/19429` endpoints, so the original "each node has blackbox I/O behavior"
  objective is explicitly not complete yet.
- [ ] Add sharded/resumable scale-run scheduling and acceptance thresholds for
  concept and implementation views separately.

---

## File Structure

- Modify: `packages/core/src/asip/storage.py`
  - Add endpoint inventory.
  - Add ledger tables.
  - Add canonical `blackbox_profiles` table.
  - Include `blackbox_profiles` in runtime semantic freshness policy.
  - Project canonical profiles or legacy self-edge `provenance.blackbox` into node attrs.
  - Keep blackbox self-edges out of visible graph relationships.
- Modify: `packages/core/src/asip/workbench.py`
  - Replace sample-based or raw-prefix candidate selection with manifest-backed scheduling.
  - Add batch/attempt loop, content grounding validator, persistence, and QA summary helpers.
- Modify: `packages/core/src/asip/semantic_edges.py`
  - Keep provider specialization for blackbox JSON messages.
- Modify: `packages/core/src/asip/cli.py`
  - Add `blackbox-profiles-batch`.
- Modify: `packages/core/src/asip/runtime_semantic_freshness.py`
  - Add blackbox freshness probes.
- Modify: `packages/core/src/asip/completion_gate.py`
  - Add optional/then-required blackbox ledger artifact binding.
- Modify: `apps/web/app/api/workbench/semantic-edges/route.ts`
  - Add `mode: "blackbox-profiles"`.
- Modify: `apps/web/components/workbench-page.tsx`
  - Add UI action, layer counts/filters, and `Blackbox Profile` inspector section.
- Test: `packages/core/tests/test_storage_graph.py`
- Test: `packages/core/tests/test_workbench_live.py`
- Test: `packages/core/tests/test_runtime_semantic_freshness.py`
- Test: `apps/web/tests/workbench-api.spec.ts`
- Test: `apps/web/tests/workbench-smoke.spec.ts`
- Create: `docs/qa/2026-05-21-blackbox-ledger-qa.md`

### Task 0: Remove Or Rewrite Prototype Drift

**Files:**
- Modify: `packages/core/src/asip/workbench.py`
- Modify: `packages/core/src/asip/storage.py`
- Modify: `packages/core/tests/test_workbench_live.py`

**P0 priority fixes from grill findings:**

- [ ] **Step 1: Un-hardcode `batch_size=1`** (workbench.py:2131)

  Current code reads `requested_batch_size` from config/CLI but then sets
  `batch_size = 1` unconditionally, wasting manifest overhead. Change to:
  ```python
  batch_size = requested_batch_size  # remove the override
  ```

- [ ] **Step 2: Increase retry ladder from 1 to 3 rounds**

  Current retry: one compact retry per sample → if both fail → terminal.
  Change to three escalating formats:
  1. Standard evidence prompt (existing).
  2. Compact JSON-only (existing `_blackbox_compact_retry_prompt`).
  3. Pure JSON list format (no markdown, no explanation, no preamble).
  Record every retry in `llm_provider_responses` with `attempt_index` and
  `retry=N` metadata. Add `--retry-count` config knob (default 3).

- [ ] **Step 3: Raise `num_predict` to 1536-2048**

  Job 67 failures were caused by gemma4 truncation at 1024 tokens.
  Change `num_predict` default from 1024 to 1536 (conservative) or 2048
  (aggressive). Monitor per-candidate token usage.

- [ ] **Step 4: Set `temperature=0.1` instead of 0**

  Temperature 0 makes all 3 samples produce identical outputs (or fail the
  same way). A small temperature ensures genuine sample independence for
  reconciliation. Add temperature to provider settings in `workbench-limits.json`.

- [ ] **Step 5: Make coverage gate configurable**

  Add `--min-blackbox-coverage` to `completion_gate.py` (default 1.0 for
  full-goal, but P0 scale slices can pass with e.g. 0.5 or manifest-scope
  only). Change `blackbox_coverage_qa.py` `min_coverage` to accept the
  command-line value.

- [ ] **Step 6: Inspect current dirty diff**

Run:

```bash
git diff -- packages/core/src/asip/workbench.py packages/core/src/asip/storage.py packages/core/tests/test_workbench_live.py
```

Expected: identify any sample-based `_blackbox_profile_candidates()` logic.

- [ ] **Step 7: Remove sample-based candidate source**

Delete candidate enumeration that calls `global_graph_networkx(limit=max(...))`
for the blackbox universe. The replacement must come from Task 1 inventory.

- [ ] **Step 8: Keep reusable pieces only**

Keep only provider message helpers and field names that still match the spec:
`inputs`, `outputs`, `observed_behavior`, `explanation_layer`, `evidence`,
provider/model/job provenance.

### Task 1: Product Endpoint Inventory

**Files:**
- Modify: `packages/core/src/asip/storage.py`
- Test: `packages/core/tests/test_storage_graph.py`

- [ ] **Step 1: Write RED inventory test**

Add a test that creates more deterministic edges than a small display budget,
then asserts `product_endpoint_inventory(function_view="both")` returns all
projected `function/register/doc` endpoints and records concept/implementation
view membership.

- [ ] **Step 2: Run RED**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest packages.core.tests.test_storage_graph.StorageGraphTests.test_product_endpoint_inventory_ignores_graph_budget -v
```

- [ ] **Step 3: Implement inventory helper**

Scan `_runtime_graph_edge_rows()` without edge selection. For each endpoint,
reuse `_product_graph_node()` under concept and implementation views, record
source, raw implementations, neighbors, and coverage bucket.

- [ ] **Step 4: Run GREEN**

Run the command from Step 2. Expected: pass.

### Task 2: LLM Batch And Attempt Ledger

**Files:**
- Modify: `packages/core/src/asip/storage.py`
- Test: `packages/core/tests/test_storage_graph.py`

- [ ] **Step 1: Write RED migration test**

Assert `migrate()` creates `llm_batches` and `llm_attempts`, and that ledger
rows can be inserted/read with `job_id`, `batch_id`, `attempt_id`,
`candidate_id`, status, prompt hash, response hash, validator status, and
reason code.

- [ ] **Step 2: Implement ledger schema and helpers**

Add compact helper methods for starting/finishing a batch and recording an
attempt. Keep successful graph output in `edges.provenance_json`.

- [ ] **Step 3: Run GREEN**

Run the focused storage test.

### Task 3: Canonical Blackbox Profile Storage

**Files:**
- Modify: `packages/core/src/asip/storage.py`
- Modify: `packages/core/src/asip/workbench.py`
- Test: `packages/core/tests/test_storage_graph.py`
- Test: `packages/core/tests/test_workbench_live.py`

- [ ] **Step 1: Add canonical profile table test**

Assert `migrate()` creates `blackbox_profiles`, accepted profiles are written
there with job/batch/attempt/prompt/response/provider/model provenance, and
graph projection still exposes `attr.blackbox`.

- [ ] **Step 2: Implement canonical table and helpers**

Add insert/list helpers. `_persist_blackbox_profiles()` must write the
canonical table first, then optionally write the existing self-edge as a
compatibility projection.

- [ ] **Step 3: Filter visible self-edge relationships**

All default graph paths must suppress `src == dst &&
extractor=blackbox_profiles` as relationships while still projecting profile
metadata onto the node.

### Task 4: Blackbox Scheduler And Content Validator

**Files:**
- Modify: `packages/core/src/asip/workbench.py`
- Test: `packages/core/tests/test_workbench_live.py`

- [ ] **Step 1: Write RED scheduler/validator test**

Use a fake provider that returns one valid profile, one hallucinated endpoint,
one invalid schema object, and one profile that only repeats the AST name.
Assert:

- inventory count is greater than attempted limit;
- ledger records persisted, rejected, and failed counts;
- hallucinated endpoints do not persist;
- AST-name parroting does not persist;
- accepted profile fields resolve prompt evidence refs;
- persisted profile provenance includes `batch_id`, `attempt_id`,
  `candidate_id`, prompt hash, response hash, provider, model, manifest hash,
  validator status, and reason codes.

- [ ] **Step 2: Implement scheduler**

Use `product_endpoint_inventory()` as the universe source, then build a
deterministic selection manifest. `limit` selects attempted candidates from the
manifest. Batch size controls provider batch size only.

- [ ] **Step 3: Implement content grounding validator**

Enforce schema, endpoint allowlist, product kind, relation enum, evidence refs,
neighbor/source/snippet grounding, anti-parrot checks, and provenance before
persistence. Empty I/O repaired from deterministic neighbors must be counted as
`repaired_empty_io_from_neighbors`.

- [ ] **Step 4: Run GREEN**

Run the focused workbench test.

### Task 5: Runtime Freshness

**Files:**
- Modify: `packages/core/src/asip/storage.py`
- Modify: `packages/core/src/asip/runtime_semantic_freshness.py`
- Test: `packages/core/tests/test_runtime_semantic_freshness.py`

- [ ] **Step 1: Write RED freshness tests**

Assert fresh `blackbox_profiles_batch` rows remain visible, while stale,
provider-mismatched, or jobless blackbox rows are filtered.

- [ ] **Step 2: Update semantic policy**

Map `blackbox_profiles` extractor to `blackbox_profiles_batch` jobs and include
latest blackbox job ids in runtime status.

- [ ] **Step 3: Run GREEN**

Run the focused freshness tests.

### Task 6: CLI And Web API Surface

**Files:**
- Modify: `packages/core/src/asip/cli.py`
- Modify: `apps/web/app/api/workbench/semantic-edges/route.ts`
- Test: `apps/web/tests/workbench-api.spec.ts`

- [ ] **Step 1: Add CLI command**

Expose `blackbox-profiles-batch --db --limit --batch-size`, plus manifest
options: `--phase`, `--selection-seed`, `--manifest-out`,
`--dry-run-selection`, `--shard-count`, and `--shard-index`.

- [ ] **Step 2: Add route mode and graph meta**

Add `mode: "blackbox-profiles"` to `/api/workbench/semantic-edges`.
Add graph layer meta/counts for `deterministic_ast`, `concept_merge`,
`blackbox_profile`, and `blackbox_relationship`.

- [ ] **Step 3: Run focused API checks**

```bash
pnpm --filter web exec playwright test tests/workbench-api.spec.ts -g "blackbox" --reporter=line
```

### Task 7: Web Inspector

**Files:**
- Modify: `apps/web/components/workbench-page.tsx`
- Test: `apps/web/tests/workbench-smoke.spec.ts`

- [ ] **Step 1: Add inspector rendering test**

Seed graph payload with `attr.blackbox`, click a node, and assert the inspector
shows `Blackbox Profile`, `Inputs`, `Observed Behavior`, `Outputs`, `Explains`,
`Evidence`, `Generated By`, validator status, evidence refs, and layer counts.

- [ ] **Step 2: Implement UI section**

Render blackbox as behavior explanation, not raw metadata.

- [ ] **Step 3: Add UI trigger**

Add `Generate blackbox profiles`, calling the new route mode.

### Task 8: Blackbox Ledger QA Artifact

**Files:**
- Modify: `packages/core/src/asip/completion_gate.py`
- Create: `docs/qa/2026-05-21-blackbox-ledger-qa.md`

- [ ] **Step 1: Generate focused fake-provider artifact**

Record inventory count, manifest hash, selected bucket counts, attempted count,
batch/attempt counts, persisted/repaired/rejected counts, content validator
summary, and graph projection proof.

- [ ] **Step 2: Run real local gemma smoke if available**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
  python3 -m asip.cli blackbox-profiles-batch --db data/asip.db --limit 20 --batch-size 2
```

If `data/asip.db` or Ollama/gemma is unavailable, record the blocker plainly.

- [ ] **Step 3: Run browser DB-path proof**

Use the in-app browser or Playwright no-mock path to prove `/graph?dbPath=...`
shows a node inspector `Blackbox Profile` from the same DB.

## Self-Review

- This plan no longer uses a budgeted display graph as the blackbox universe.
- It requires AST-derived product endpoint inventory before LLM generation.
- It treats large LLM loop accuracy as ledger + validator + coverage, not edge
  count.
- It keeps visible product graph nodes limited to `function/register/doc`.
- It keeps completion blocked until current DB, CLI/API/Web/browser evidence
  proves the overlay.

## 2026-05-22 P0 Brainstorm Closure And Next Slice

Subagent loop decision: P0 proves a trustworthy blackbox boundary profile, not
full recursive hierarchy. `blackbox_component_links` moves to P1 unless the
delivery scope changes to require clickable parent-child opened boxes.

Current P0 additions:

- [x] Default `blackbox-profiles-batch` selection skips endpoints that already
  have usable blackbox profiles.
- [x] Full inventory ordering/shard grouping stays stable while missing-only
  selection skips covered keys.
- [x] Provider response ledger records `evidence_view` for each sample.
- [x] Reconcile rejects samples that pass validation but do not independently
  agree on grounding refs.
- [x] Completion gate supports required blackbox coverage artifacts and blocks
  full-goal completion when missing coverage remains.

Next implementation slice:

- [x] Split prompt content by evidence view instead of only tagging the sample.
- [x] Add explicit `abstained_insufficient_evidence` and
  `abstained_insufficient_agreement` terminal statuses.
- [x] Extend coverage QA with accepted/repaired/abstained/rejected/failed
  distributions and scoped manifest coverage.
- [ ] Run a real missing-only gemma4 sanity slice before the 100-endpoint scale
  slice.

Implementation notes:

- Each sample prompt now declares `PRIMARY_EVIDENCE_VIEW` and gives different
  instructions for neighbor-heavy, source-span-heavy, and
  snippet-minimal-allowlist views.
- Reconcile can return `abstained` when parseable profiles pass local
  validation but fail independent grounding-ref or behavior-family agreement.
- All-abstained batches keep their ledger/manifest terminal statuses instead
  of rolling back due to zero persisted profiles.
- Coverage QA reports terminal status counts and profile status counts so a
  slice cannot hide abstained/rejected/failed candidates behind a single
  covered/total ratio.
- Coverage QA reports `latest_manifest_scope` separately from full coverage:
  selected candidate count, selected covered/missing, terminal count, shard
  completeness, candidate-id hash, and `explicit_not_full_goal=true`.
- `blackbox-profiles-batch` supports `--omit-graph`, `--summary-only`, and
  `--output-json` so scale runs can keep stdout compact while preserving a
  full machine-readable artifact.
- P0 prompts are profile-first: direct LLM relationship generation is removed
  from the prompt. Relationships still may appear from defensive/fake providers
  and remain rejected/deferred unless derived from accepted profiles.
- Real gemma4 profile-only sanity run `job_id=68` accepted 1/1 selected
  candidate, produced 1 profile and 3 overlay edges, refreshed ledger QA to
  16/16 pass, and moved full coverage to 7/19429 while keeping full status
  blocked.
