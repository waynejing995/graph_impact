# G05 Resolver Profiles

Status: Current pass verified; richer diagnostics and broader non-C strategies remain blocking

## Requirement

Resolver behavior must be configurable, not hardcoded. MVP-1 must support Linux `amdgpu`, AMD MxGPU/GIM, and at least one non-macro Python-style profile.

Configurable fields include wrapper names, argument positions, prefixes, base-index suffixes, context variables, field rules, and language-specific extraction strategies.

Every resolver shown in the UI must correspond to a real YAML config file under `configs/resolvers/` or a backend-persisted profile that points to an existing YAML file. The UI must not show profile-like static rows that cannot be loaded or validated by the resolver engine.

Resolver wrapper/extractor names are configuration and provenance, not graph entities. Profiles may define `WREG32`, `REG_SET_FIELD`, `SOC15_REG_OFFSET`, `amdgv_wreg32`, `gpu_register`, and similar operations, but those operation names must not become graph nodes.

## Current Evidence

- `configs/resolvers/linux-amdgpu.yaml`, `configs/resolvers/amd-mxgpu.yaml`, and `configs/resolvers/toy-python.yaml` exist.
- `packages/core/src/asip/resolver_profiles.py` contains resolver profile parsing/resolution helpers.
- `packages/core/src/asip/workbench.py` persists resolver profiles and validates a profile against source text.
- `apps/web/app/api/workbench/resolver-profiles/route.ts` exposes GET/POST/validate behavior through the CLI.
- `apps/web/components/workbench-page.tsx` can add resolver profiles through the backend.
- Core and Web API tests cover add/list/validate and toy Python extraction.
- `packages/core/tests/test_workbench_backend_state.py` verifies a saved resolver profile can change indexed evidence for a configured wrapper without editing code.
- `packages/core/src/asip/workbench.py` loads persisted resolver profiles during registered-corpus indexing and stores resolver-derived access/resolved-chain metadata for the matched symbol.
- FastAPI exposes `GET /resolver-profiles`, `POST /resolver-profiles`, and `POST /resolver-profiles/{profile_id}/validate` over backend resolver state.
- MCP exposes `resolver_profiles_list()`, `resolver_profile_add()`, and `resolver_profile_validate()` over backend resolver state.
- FastAPI and MCP tests add a Python resolver profile to a temp DB, list it, and validate a dynamic `@gpu_register(...)` source snippet.
- The Resolver Profiles UI now has a validation source editor and `Validate resolver profile` action backed by `/api/workbench/resolver-profiles`.
- The Resolver Profiles UI now exposes an `Enable resolver profile` checkbox when adding profiles, and disabled profiles render a visible `disabled` status in the results table.
- `apps/web/tests/workbench-smoke.spec.ts` verifies a user-created Python `gpu_register` profile can validate a dynamic source snippet from the UI.
- `apps/web/tests/workbench-smoke.spec.ts` verifies a user-created disabled profile has visible disabled status.
- 2026-05-17 user review clarified that all resolver profiles shown by the UI must be backed by real YAML config. A starter `initial.yaml` is required only if it is real and loadable, not a decorative default row.
- 2026-05-17 resolver expansion pass doubled the committed resolver profile count and AMD wrapper coverage. The committed YAML set now includes `amd-direct-mmio.yaml`, `amd-soc15.yaml`, `amd-field-macros.yaml`, `amdgv-mxgpu-context.yaml`, `linux-amdgpu.yaml`, `amd-mxgpu.yaml`, `initial.yaml`, `toy-python.yaml`, and `python-hw-symbols.yaml`.
- `linux-amdgpu.yaml` now covers W/R direct access, `_P`, SOC15, SOC15 IP, SOC15 offset, no-KIQ, RLC, RLC shadow, `SOC15_REG_OFFSET`, `SOC15_REG_ENTRY`, field read/write, `REG_FIELD_*`, `REG_SET_FIELD`, and `REG_GET_FIELD` patterns. `amd-mxgpu.yaml` now covers direct, `_P`, PCIe, NBIO, SOC15, SOC15 offset, field, `REG_FIELD_*`, and `amdgv_*` context-style wrappers.
- The split profiles represent the specific resolver situations requested during brainstorming: direct read/write wrappers, SOC15 address/read/write wrappers, field macros that produce register plus field symbols, MxGPU/GIM `adapt`/`amdgv` context wrappers, and non-macro Python-style hardware symbol references.
- `packages/core/src/asip/resolver_profiles.py` now resolves every configured wrapper call in a snippet, supports balanced nested calls, and supports `symbol_args: [...]` for macros that emit register and field symbols from one call.
- `packages/core/src/asip/workbench.py` now persists and rehydrates full YAML resolver config, including argument positions and symbol prefixes, instead of reconstructing enabled profiles from wrapper names only.
- `packages/core/src/asip/storage.py` migrates old `resolver_profiles` tables by adding `config_json`, so existing DBs can be upgraded instead of requiring a rebuild.
- 2026-05-17 graph correction filters resolver wrapper/extractor names from deterministic graph endpoints, evidence-derived symbols, semantic-edge persistence, and NetworkX traversal output. Wrapper names remain visible in provenance/resolved chains.
- 2026-05-17 UI correction: the Resolver Profiles table now treats the profile id as the row identity and summarizes wrapper/extractor count as operators, instead of presenting `WREG32`/`REG_SET_FIELD` as if they were symbol nodes.
- 2026-05-17 backend correction: wrapper/extractor names are rejected as graph seeds, skipped from query `expected_terms`, and filtered from stale persisted evidence rows before query results can build graph fallback nodes.
- 2026-05-17 API correction: committed YAML profiles are merged before backend DB rows and cannot be shadowed by stale local test state for the same profile id, so the built-in `initial`/AMD profiles stay truthful to the checked-in YAML.
- 2026-05-17 prefix correction: every committed C/C++ resolver profile now carries `symbol_prefixes: [reg, mm, smn]`, and `packages/core/tests/test_resolver_profiles.py` proves both `mmGCVM_L2_CNTL` and `smnGCVM_L2_CNTL` canonicalize to the same `GCVM_L2_CNTL` register node instead of creating prefix-specific graph nodes.
- 2026-05-17 continuation: the Resolver Profiles UI can now select an existing YAML-backed profile, load it into the editor, toggle enabled state, and save it through the same backend upsert path. Playwright covers loading `linux-amdgpu` into the editor and saving it disabled.
- 2026-05-18 per-job selection correction: core `index_configured_corpora`, `index_registered_corpora`, and `rebuild_deterministic_graph` accept selected resolver profile ids, filter against real YAML/backend profiles, record the active ids in job metadata, and reject unknown ids. CLI `index`/`graph-rebuild`, FastAPI `/index`/`/graph-rebuild`, MCP `corpora_index`/`graph_rebuild`, and the Next Web BFF all pass these ids through.
- 2026-05-18 Corpus UI correction: the Corpus page now renders a shadcn/Radix checkbox list of enabled YAML-backed resolver profiles and sends `resolverProfileIds` with the next index job. The action feedback echoes the profiles used, and Playwright verifies an unchecked profile is omitted from the request body.
- 2026-05-18 selection proof: Web API indexing with `resolverProfileIds: ["amd-soc15"]` indexes a `WREG32_SOC15` fixture while excluding `WREG32` direct-MMIO edges, proving selection changes graph output without resolver code edits.

## Remaining Gap

Resolver profiles are a real product control path for the current C/C++ and Python-call MVP. The backend preserves YAML argument positions, resolves multiple symbols per configured wrapper call, and can restrict an index/rebuild job to user-selected profiles.

The UI now supports add, validate, enabled/disabled creation state, existing-profile editing through the selector, and per-index job selection. Remaining work is richer diagnostics for why a profile did or did not match a source span, and broader language-specific non-macro strategies beyond configured Python-style call extractors; those need either implementation or explicit MVP limits.

The UI/backend path filters out resolver rows that are not backed by a real YAML config, and the starter `initial` profile is a truthful checked-in YAML file.

## Acceptance Criteria

- Profiles are parsed with structured code, not ad hoc regex in Web product paths.
- UI can add, enable/disable on creation, validate profiles through backend state, edit existing profiles through the selector, and select profiles for a specific index job.
- UI only lists resolver profiles that can be loaded from real YAML config or backend-persisted state with an existing config path.
- Resolver validation calls core resolver logic and returns structured diagnostics.
- Linux and MxGPU wrapper changes affect indexing/query without code changes.
- Toy Python/non-macro extraction is represented as a real strategy interface, not only a fixture row.
- Field macros can resolve more than one symbol from one configured call, for example register plus field from `REG_SET_FIELD`.
- Persisted profiles keep YAML-configured `symbol_arg`, `symbol_args`, prefixes, and extractor lists through add/list/validate/index flows.
- Resolver wrapper/extractor names never appear as graph endpoints; only the resolved register/field/context/document entities enter the graph.

## Required Tests

- Core test: changing a resolver profile changes extracted evidence without editing code.
- Core tests for multiline/nested wrapper calls or explicitly documented MVP limits.
- Core tests for SOC15, field macro, Linux amdgpu, and MxGPU/GIM wrappers represented in real YAML.
- Core regression test for common AMD register prefixes such as `reg*`, `mm*`, and `smn*` so prefix aliases do not fragment register nodes.
- Core integration test for persisted profile argument positions during registered-corpus indexing.
- Core migration test for old `resolver_profiles` tables without `config_json`.
- API/E2E tests for add/edit/toggle/validate/profile selection. Add, enabled/disabled creation, validate, edit-in-place, and per-job selection are implemented for the current YAML-backed profile model.
- MCP/API tests for add/list/validate profile against a temp DB.
- Integration test proving selected profile is used during indexing.
- Regression test: indexing/resolver graph output does not create mega-nodes for configured wrapper/extractor names.
- Regression test: resolver profile UI rows show profile identity and operator count, not wrapper names in the symbol column.
- Regression test: wrapper/extractor names are rejected as graph seeds and filtered out of stale evidence/query expected-term paths.

## Not Closed Until

The final G11 gate reruns the resolver profile selection path together with the full graph/query/browser suite and explicitly accepts the remaining diagnostic and broader-language boundaries.
