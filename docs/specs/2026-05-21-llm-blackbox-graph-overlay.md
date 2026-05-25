# LLM Blackbox Graph Overlay

Date: 2026-05-21
Status: All 4 grill loops closed on 2026-05-22 with analyzed real-DB evidence (job 67/68); P0 scope reset on 2026-05-22

## Purpose

ASIP graph should not stop at AST/deterministic edges. It should use a large,
auditable local `gemma4:e4b` loop to explain graph entities as black boxes:
what inputs are observed at the boundary, what outputs follow, what behavior
rule is inferred, and what this layer explains about the parent system.

This is not permission for the LLM to invent a graph. The deterministic graph
defines the node universe. The LLM only annotates and relates grounded
endpoints.

## 2026-05-22 Grill Consensus

The phrase "LLM-generated blackbox node" means:

> an AST-derived product endpoint whose blackbox behavior profile is generated,
> critiqued, reconciled, validated, and persisted by the local `gemma4:e4b`
> loop.

The endpoint id is not invented by the model. Stage 1 projects raw AST/code
facts into product endpoints (`function`, `register`, `doc`). Stage 2.5 uses
the LLM to generate the blackbox method view for those endpoints: observed
inputs, observed outputs, behavior rule, explanation layer, evidence refs, and
candidate relationships that validators may promote into semantic overlay
edges.

This keeps the user requirement intact: nodes are still generated from AST
nodes, but through a product projection boundary so that local variables,
macro wrappers, parser helpers, file paths, provider names, and raw line spans
do not become product nodes.

## 2026-05-22 Grill Findings (Real-DB Evidence)

Four parallel grill analyses completed: architecture, LLM loop reliability, UI/semantic, and evidence chain. Key data from real-DB runs:

**Job 67 (scale-2, 2 candidates, batch_size=1):**
- Candidate 1 `amdgpu_virt_post_reset` (function): 3/3 parse failures → "failed"
  - gemma4 returned truncated JSON-like text that validator rejected
  - Compact retry also failed — same truncation issue
  - Root cause: gemma4 output truncated at ~1024 tokens under `num_predict=1024`
- Candidate 2 `GDC_S2A0_S2A_DOORBELL_ENTRY_5_CTRL` (register): 2/3 parse fail, 1/3 accepted → "rejected"
  - Exact: `accepted_sample_count=1 < required_agreeing_samples=2`
- Total output: 0 profiles, 0 edges

**Job 68 (profile-only, 1 candidate, batch_size=1):**
- Candidate `uvd_enc_ring_emit_reg_wait` (function): 3/3 accepted ✅
  - All 3 samples parsed and passed validator
  - Behavior consensus: "write" family (3/3)
  - Evidence consensus: ref "source:3" (2/3 samples)
  - Output: 1 profile, 3 relationship edges, 4 IO facts
  - Ledger QA: 16/16 checks pass

**Critical weakness found in LLM loop:**
- `temperature=0` makes 3 samples effectively identical; parse failure is terminal after one compact retry
- `num_predict=1024` under `num_ctx=2048` causes truncation on evidence-heavy prompts
- `batch_size=1` hardcoded despite `requested_batch_size` config; wastes manifest/batch overhead

Non-negotiable decisions:

- Stage 2.5 is a semantic overlay on `function/register/doc`, not a new
  free-form LLM graph.
- Generation is profile-first. Relationships are derived from accepted
  profile refs plus deterministic neighbors; direct LLM relationships remain
  weak candidates until validated.
- The loop must be auditable by current `db_path`, `db_sha256`, `repo_head`,
  manifest group, provider/model, prompt hash, response hash, attempts, and
  browser/API visibility.
- Validator gates run before persistence and before graph visibility.
- The UI must explain the graph as `System Boundary`, `Opened Blackbox`, and
  `Evidence Trail`, not as a raw AST or weighted graph dump.

## Decision

Blackbox generation is **Stage 2.5 semantic overlay**:

1. Stage 1 remains deterministic AST/text-span/resolver extraction.
2. Stage 2 remains semantic edges and document boxes.
3. Stage 2.5 runs a bounded large LLM loop over AST-derived product endpoints
   and writes blackbox profiles plus optional semantic relationships.

The default product graph still exposes only:

- `function`
- `register`
- `doc`

The blackbox result is node behavior metadata, not a new product node kind.
It is a first-class profile record projected onto existing product nodes.

## Candidate Universe

The candidate universe must come from Stage 1 deterministic graph facts after
product projection. It must not come from a budgeted display graph.

Required inventory API:

```python
store.product_endpoint_inventory(
    function_view="concept" | "implementation" | "both",
    stages=("deterministic",),
    include_semantic_docs=False,
)
```

Inventory rules:

- Scan all usable deterministic edge rows.
- Reuse storage product projection helpers to produce `function/register/doc`
  endpoint ids.
- Do not call view-graph edge selection or Web/API graph budgets.
- Candidate `limit` controls how many candidates a job attempts, not the size
  of the universe.
- Record `inventory_total`, `attempted_count`, `profiled_count`,
  `rejected_count`, `failed_count`, and `skipped_count`.

Concept and implementation views both matter:

- Concept profile explains the product-level behavior boundary.
- Implementation profile explains the AST implementation behavior.
- Relationships generated by the LLM must stay inside one view. Cross-view
  links are provenance, not product graph edges.

## Candidate Shape

Each candidate should include:

- `candidate_id`: stable id including view and endpoint.
- `endpoint_id`: product endpoint id.
- `view`: `concept` or `implementation`.
- `kind`: `function`, `register`, or `doc`.
- `label`: user-facing label.
- `raw_ast_sources`: raw function spans, paths, line ranges, resolver profile,
  and corpus provenance where available.
- `neighbors`: deterministic graph facts around this endpoint.
- `snippets`: short source/evidence snippets that support the observed I/O.
- `allowlist`: exact endpoint ids and allowed relations for this batch.
- `coverage_bucket`: fixed bucket such as
  `stage1_ast_projected_concept_function`,
  `stage1_ast_projected_implementation_function`,
  `stage1_ast_projected_register`, or `stage2_doc_projected_doc`.

## Selection Manifest And LLM Loop

The loop is large but bounded. The P0 runner is profile-first:

- Build endpoint inventory.
- Build a deterministic selection manifest from the inventory.
- Partition candidates by kind, corpus, IP block, path bucket, degree,
  register-I/O presence, profile state, concept/implementation view, and
  coverage bucket.
- Stable-shuffle each bucket by `selection_seed + candidate_id`, then select
  by weighted round-robin. Do not use raw `inventory[:limit]` ordering.
- Batch candidates under prompt/token budgets. P0 defaults to
  `batch_size=3-5` (not 1 — hardcoded `batch_size=1` wastes manifest overhead
  and was a prototype limitation).
- Run local `gemma4:e4b` through the existing provider settings.
- Generate profiles first; omit free-form relationships in the first retry
  ladder.
- Retry transport failures, JSON truncation, and empty persist batches with
  escalating prompt formats:
  1. Standard prompt (with evidence context).
  2. Compact JSON-only retry (existing `_blackbox_compact_retry_prompt`).
  3. Pure list/array format retry (no markdown, no explanation).
  Use at most 3 retries per sample. Do not repair truncated JSON into
  accepted evidence.
- Raise `num_predict` from 1024 to 1536-2048 to reduce truncation risk on
  evidence-heavy prompts.
- Set `temperature` to `0.1-0.3` instead of `0` to increase sample
  independence. Temperature 0 produces identical outputs across all 3 samples,
  defeating the purpose of multi-sample reconciliation.
- Attempt provider fallback if gemma4 fails consecutively: fall back to a
  smaller model (e.g. gemma3) rather than failing permanently.
- For P0 self-consistency, run three profile samples per selected candidate,
  critique parseable samples, and accept only when at least two samples agree
  on endpoint, I/O direction, and core evidence refs.
- Run validator gates before persistence.
- Optionally expand verifier/self-consistency passes for high-risk candidates
  after the P0 evidence chain is stable.

The loop must be resumable and auditable. A single successful edge count is not
evidence of accuracy.

Manifest records must include:

- `manifest_sha256`
- `selection_seed`
- `phase`: `calibration`, `pilot`, `scale`, or `full`
- `candidate_id`, `endpoint_id`, `kind`, `view`, `coverage_bucket`
- corpus/path/IP/degree/relation-signature buckets where available
- `selection_rank`, `bucket_id`, `shard_index`, and `shard_count`

QA must aggregate by `manifest_group_sha256`, not only by latest job id or one
shard-local `manifest_sha256`.

## Ledger

Reuse existing storage for successful output:

- `jobs` remains the top-level run.
- `edges.provenance_json` remains the successful profile/relationship carrier.

Existing batch/attempt ledger tables remain compatible:

- `llm_batches`: job id, batch id, candidate ids/hash, prompt hash, allowed
  endpoint hash, provider options, status, latency, counts.
- `llm_attempts`: batch id, attempt id, retry index, response hash, parse
  status, validator status, persisted/rejected counts, reason codes.

P0 adds entity tables rather than hiding the real proof inside JSON metadata:

- `blackbox_manifests`: one selected manifest/shard with `db_path`,
  `db_sha256`, `repo_head`, inventory hash, manifest hashes, shard details,
  provider/model, provider settings hash, and scheduler version.
- `blackbox_manifest_candidates`: selected candidates with endpoint, view,
  kind, coverage bucket, bucket id, ranks, allowlist hash, prompt refs hash,
  candidate JSON, and terminal status.
- `llm_provider_responses`: one row per real provider call with prompt/request
  hashes, raw response or response JSON, parse status, latency, error class,
  and truncation flag.
- `blackbox_validation_failures`: one row per rejected gate so failures can be
  traced to schema, endpoint allowlist, evidence refs, anti-parrot, relation,
  parse, or freshness causes.
- `blackbox_io_facts`: structure accepted profile `inputs` and `outputs` with
  direction, text, endpoint/ref grounding, evidence refs, confidence, and
  status.

P1 adds `blackbox_component_links` for recursive decomposition from a parent
blackbox profile to implementation functions, register ports, doc support, or
next-layer blackbox candidates. P0 may expose these as validated profile
metadata before the table is promoted.

Every persisted blackbox edge must reference:

- `job_id`
- `batch_id`
- `attempt_id`
- `candidate_id`
- `prompt_sha256`
- `response_sha256`
- `validator_version`
- `provider`
- `model`

## Validator Gates

Blocking in the first implementation slice:

- JSON schema gate.
- Endpoint allowlist gate.
- Product node kind gate.
- Relation enum gate.
- Evidence/source reference gate using numbered prompt refs:
  `neighbor:N`, `source:N`, and `snippet:N`.
- Provider/model/job provenance gate.
- Runtime freshness gate.
- Ledger completeness gate:
  `candidate_count = persisted + rejected + failed + skipped`.

Partial in the first slice, but recorded in artifacts:

- **Coverage gate must be configurable.** Current `min_coverage=1.0` (100%)
  is unrealistic for P0 — the real DB has 7/19429 = 0.036%. P0 coverage target
  should be `latest_manifest_scope.selected_coverage_ratio >= 1.0` (all
  selected candidates in the current manifest have profiles), not full inventory.
  Add `--min-blackbox-coverage` to `completion_gate.py`.
- Multi-pass self-consistency.
- Golden/labeled accuracy beyond sentinel cases.
- Human review of broad profile quality.

Accepted profiles must not be free-text model claims. Each accepted
`input`, `output`, `observed_behavior`, and `evidence` item must reference
deterministic prompt facts and pass a content validator. Empty I/O filled from
deterministic neighbors is allowed only as a repaired/system-grounded profile,
and is counted separately from pure LLM-grounded output.

## Persistence

Persist blackbox profile data as semantic overlay:

- canonical table: `blackbox_profiles`
- `stage="semantic"`
- `source=<provider>`
- `provenance.extractor="blackbox_profiles"`
- `provenance.blackbox={...}`

`blackbox_profiles` is the authoritative profile ledger. A legacy semantic
self-edge may be written as a compatibility projection while existing graph
readers and tests migrate. Self-profile records enrich the node. They must not
render as visible `node relates_to node` relationships and must not be counted
as cross-node semantic relationships.

Cross-node LLM relationships may persist only when both endpoints are in the
batch allowlist and the relation normalizes to the product relation enum.

Runtime semantic freshness policy must explicitly recognize:

- extractor: `blackbox_profiles`
- job kind: `blackbox_profiles_batch`

Otherwise current graph reads can silently filter the new overlay.

## UI

The graph canvas still renders `function/register/doc` nodes only.

The graph API and UI must expose explicit product layers:

- `deterministic_ast`
- `concept_merge`
- `blackbox_profile`
- `blackbox_relationship`

P0 API should expose these fields explicitly, rather than making the frontend
infer everything from provenance strings:

- `meta.layers`: counts for `deterministic_ast`, `concept_merge`,
  `blackbox_profile`, `blackbox_relationship`, and `semantic_doc`.
- `edge.layer`: `deterministic_ast`, `blackbox_relationship`, or
  `semantic_doc`.
- `edge.provenance_type`: `deterministic`, `llm_blackbox`, or `semantic_doc`.
- `edge.evidence_refs`: refs back to `neighbor:N`, `source:N`, or
  `snippet:N`.
- `node.attr.blackbox.generated_by`: provider, model, job id, batch id,
  attempt id, prompt hash, response hash, validator version.
- `node.attr.blackbox.rounds`: summarized generation/critic/reconcile status
  when multi-sample data exists.

Node inspector adds a `Blackbox Profile` section:

- Inputs
- Observed Behavior
- Outputs
- Explains
- Evidence
- Generated By: provider, model, job, batch, attempt, confidence
- Evidence refs and validator status

Inspector ordering should lead with the blackbox behavior for profiled nodes:
Inputs, Behavior, Outputs, Evidence, Generated By, then concept
implementations/source records/metadata. The first UI slice expresses recursive
blackbox opening as inspector drilldown: `Boundary view` for concept endpoints,
`Internal components` for implementation/register/doc children, and `Next
Blackboxes` for connected endpoints that also have blackbox profiles.

The graph API must include `meta.counts` for layers, blackbox profile nodes,
blackbox relationship edges, concept nodes, stages, sources, and budget
truncation. Browser QA must compare direct API meta with rendered DOM/canvas
state through an explicit `dbPath`.

This must be designed as a behavior explanation, not a raw metadata dump.

## Surfaces

Required surfaces:

- Core function for batch execution.
- CLI command `blackbox-profiles-batch`.
- Web API mode `blackbox-profiles`.
- Web graph reader that displays `attr.blackbox`.
- Web graph reader that exposes layer filters/counts.
- Browser QA against explicit `dbPath`.

`/api/workbench/graph` reads existing blackbox profiles. It must not generate
them as a side effect.

Completion and QA boundary:

- Blackbox ledger QA is optional for non-blackbox goals, but required when the
  active goal claims Stage 2.5 blackbox behavior.
- Required mode fails when the artifact is missing, stale, bound to a different
  `db_path`, different `db_sha256`, different `repo_head`, or different latest
  successful `blackbox_profiles_batch` job.
- Current evidence must use one canonical explicit DB path across CLI, API,
  Web, Browser, and completion gate. If the worktree lacks `data/asip.db`, the
  canonical DB may be the absolute `/Volumes/.../data/asip.db`, but artifacts
  must all bind to that same path and hash.

## QA Artifact

Create a dedicated `asip.blackbox_ledger_qa` artifact with:

- repo head, db path, db sha, limits config sha;
- provider/model/settings snapshot;
- latest index, graph rebuild, and blackbox job ids;
- inventory hash and candidate counts by kind/view/bucket;
- batch and attempt counts, retry counts, parse failures, rejected endpoints;
- ledger completeness;
- validator pass/fail counts;
- runtime freshness counts and stale count;
- persisted edge/profile ids with provenance back references;
- sentinel accuracy or self-consistency results;
- CLI/API/Web/browser `surface_results` with explicit `dbPath`.

Completion cannot be claimed from a fake provider test, a mocked browser test,
or a stale screenshot.

## 2026-05-22 Subagent Brainstorm Closure

The second grill loop resolved the P0 boundary:

- A blackbox node is an AST-derived `function/register/doc` endpoint plus an
  accepted `blackbox_profile`; the endpoint id remains the graph identity.
- P0 is profile-first. Direct LLM relationships remain rejected/deferred
  candidates. Visible blackbox connections are `grounded_profile_boundary`
  projections from an accepted profile, exact evidence refs, and deterministic
  neighbors.
- Large LLM loops must be independently comparable. Three samples must use
  different evidence views and reconcile on endpoint, I/O direction, behavior
  family, and grounding refs before persistence.
- Default batch selection is missing-only. The full inventory ordering and
  shard manifest remain stable; already profiled `(view, endpoint_id)` keys are
  skipped only at selected-candidate time.
- Full coverage remains blocked until the whole deterministic endpoint
  inventory has usable profiles or an explicit residual is accepted. Scoped
  scale slices may pass only as scoped evidence and must not redefine the
  thread goal.
- `blackbox_component_links` is P1. P0 may expose boundary neighbors and next
  candidates in metadata/inspector, but it does not claim complete recursive
  opened-blackbox hierarchy.

Implemented P0 guards in this worktree:

- `blackbox-profiles-batch` defaults to missing-only selection and exposes
  `--include-profiled` for deliberate replay.
- provider response ledger records `evidence_view` per sample.
- sample reconciliation now blocks accepted samples that lack independent
  grounding-ref agreement.
- all-abstained batches preserve manifest/attempt terminal statuses instead of
  rolling back due to zero persisted profiles.
- coverage QA reports terminal and profile status distributions, so repaired,
  rejected, failed, and abstained candidates do not disappear behind the
  covered/total ratio.
- coverage QA reports `latest_manifest_scope` with
  `explicit_not_full_goal=true`, making scoped scale evidence visible without
  redefining the full graph completion boundary.
- `blackbox-profiles-batch` can omit the post-batch graph and print only a
  summary while writing the full JSON artifact, which is required before
  running 100-endpoint scale slices.
- P0 prompts are now profile-only. Direct relationship output is no longer
  requested from the LLM; visible blackbox relationships remain derived from
  accepted profile refs plus deterministic neighbors.
- completion gate can require `asip.blackbox_coverage_qa` and blocks when full
  inventory coverage is missing.

## Current Dirty Draft Status

An earlier half implementation in this worktree is a prototype only. It used a
budgeted product graph sample as candidates and therefore does not satisfy this
spec. Before implementation resumes, that code must be either removed or
rewritten around `product_endpoint_inventory`, batch/attempt ledger, validator
gates, and runtime freshness support.
