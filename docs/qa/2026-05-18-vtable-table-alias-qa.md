# 2026-05-18 Vtable Table Alias QA

## Scope

This QA covers two concrete Stage 1 callback/type-flow gaps raised by the user after the clangd/vtable challenge.

The full clangd/libclang vtable parser is still not implemented. This slice makes the existing conservative callback overlay more precise when a function body proves that a generic receiver points at one specific callback table.

## Problem

Before this fix, code like this could over-connect:

```c
const struct amd_ip_funcs *funcs = &gfx_v11_0_ip_funcs;
return funcs->hw_init(0);
```

If another `amd_ip_funcs` table also had `.hw_init = sdma_v5_0_hw_init`, Stage 1 linked `exact_table_hw_init -> sdma_v5_0_hw_init` even though the local alias points at `gfx_v11_0_ip_funcs`.

The first implementation of this fix also exposed a second bug: a field-path assignment like `adev->gfx.rlc.funcs = &gfx_rlc_funcs` was accidentally reduced to a leaf alias named `funcs`. That polluted unrelated receivers such as `block->version->funcs` and could route IP-level common callbacks to RLC callback tables.

## Product Fix

- `CodeGraphSlotCall` now carries `receiver_tables`.
- The extractor records simple function-local callback table aliases such as `funcs = &gfx_v11_0_ip_funcs`.
- Field-path aliases such as `adev->gfx.rlc.funcs = &gfx_rlc_funcs` are stored under the full receiver path, not the leaf `funcs`.
- Callback resolution checks those exact table aliases before falling back to receiver name, receiver type, or generic slot dispatch.
- Provenance marks these edges with `call_kind=vtable_table_alias` and records `receiver_tables`.
- The Web/API/MCP graph surfaces inherit the improved SQLite graph because the persisted Stage 1 edge is narrower.

## RED / GREEN

RED:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_table_alias_limits_generic_slot_dispatch_to_assigned_table \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_uses_table_alias_to_avoid_same_slot_overlink -v
```

Failure before the fix:

```text
('exact_table_hw_init', 'calls', 'sdma_v5_0_hw_init') unexpectedly found
```

The field-path RED failed with duplicate RLC edges because `block->version->funcs` inherited the unrelated `adev->gfx.rlc.funcs` assignment:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_field_path_table_alias_does_not_pollute_other_funcs_receivers -v
```

Failure before the fix:

```text
AssertionError: 2 != 1
```

The receiver-path type RED failed because `adev->gfx.rlc.funcs` fell back to `amd_ip_funcs` when no local assignment was present:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_field_path_type_hint_maps_rlc_funcs_without_local_assignment -v
```

Failure before the fix:

```text
('resume_rlc_only', 'calls', 'gfx_rlc_resume') not found
```

The no-fallback RED failed because a known field receiver with no matching slot fell back to unrelated IP callbacks:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_known_field_path_does_not_fallback_to_unrelated_slot_when_type_has_no_match -v
```

Failure before the fix:

```text
('read_df_clockgating', 'calls', 'gfx_ip_get_clockgating_state') unexpectedly found
```

GREEN:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_links_vtable_slot_calls_to_callbacks_and_common_helpers \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_generic_slot_call_links_common_dispatch_to_callbacks \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_table_alias_limits_generic_slot_dispatch_to_assigned_table \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_field_path_table_alias_does_not_pollute_other_funcs_receivers \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_field_path_type_hint_maps_rlc_funcs_without_local_assignment \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_known_field_path_does_not_fallback_to_unrelated_slot_when_type_has_no_match \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_uses_receiver_declared_type_to_filter_generic_ops_callbacks \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_links_mxgpu_init_func_dispatch_to_callback \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_cross_file_vtable_callbacks_to_registers \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_uses_table_alias_to_avoid_same_slot_overlink \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_field_path_alias_does_not_pollute_ip_funcs \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_maps_rlc_funcs_field_path_without_local_assignment \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_generic_common_dispatch_to_multiple_callbacks \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_filters_generic_ops_dispatch_by_declared_receiver_type \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_stage1_specific_vtable_call_does_not_connect_every_same_named_slot -v
```

Result:

```text
Ran 15 tests in 0.779s
OK
```

Full core regression:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v
Ran 183 tests in 5.062s
OK (skipped=2)
```

## Real DB Rebuild

After rebuilding the local live database:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src python3 -m asip.cli graph-rebuild --db data/asip.db
job_id: 75
files: 1225
deterministic edges: 24237
```

Real SQLite checks:

```text
rlc.funcs -> *_ip_funcs mislinks: 0
calls by kind:
direct             9666
vtable_dispatch    4563
vtable_callback       8
vtable_table_alias    3
```

Browser QA at `http://127.0.0.1:3100/graph` after the rebuild:

```text
Screenshot: docs/qa/browser/graph-after-field-path-callback-fix-2k.png
Snapshot: docs/qa/browser/graph-after-field-path-callback-fix-2k-snapshot.md
graph edges: 3000
layers deterministic: 2987 semantic: 13
Loaded edge budget: 3000 / 20000
Visible nodes: 1000 / 2737
Visible edges: 3000 / 3000
visible graph summary: nodes 1000, edges 1273, doc_box 6, doc_section 1, function 787, register 206
```

Diff hygiene:

```text
git diff --check
OK
```

## Residual

This fix does not solve alias propagation through arrays, loops, interprocedural assignments, Linux compile-command-specific includes, or true clangd/libclang cursor type-flow. It prevents proven local variable/table aliases and same-function field-path aliases from falling back to broad generic dispatch.
