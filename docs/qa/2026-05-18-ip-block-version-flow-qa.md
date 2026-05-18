# 2026-05-18 IP Block Version Flow QA

## Scope

This QA covers the next Stage 1 callback/type-flow slice after the field-path callback fixes.

It still is not full clangd/libclang cursor type-flow. The goal of this slice is narrower: make AMD `amdgpu_ip_block_version.funcs` initializer relationships usable by local and cross-file `version->funcs->slot(...)` dispatch when the source proves the version table.

## Real Code Shape

The Linux amdgpu tree uses a two-level structure:

```text
amdgpu_ip.h: struct amdgpu_ip_block_version { const struct amd_ip_funcs *funcs; }
gfx_v11_0.c: .funcs = &gfx_v11_0_ip_funcs
amdgpu_device.c: adev->ip_blocks[i].version->funcs->hw_init(...)
```

The real fully-precise path can cross functions and array slots through `amdgpu_device_ip_block_add()`, so this slice intentionally covers only the provable local/cross-file aliases implemented below.

## RED / GREEN

RED 1: local `block->version = &gfx_v11_0_ip_block` still overlinked to unrelated `sdma_v5_0_ip_funcs`.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_ip_block_version_funcs_alias_resolves_nested_dispatch -v
```

Failure before the fix:

```text
('exact_ip_block_init', 'calls', 'sdma_v5_0_hw_init') unexpectedly found
```

RED 2: real-shaped `amdgpu_device_ip_block_add(adev, &gfx_v11_0_ip_block)` argument flow still overlinked to unrelated IP callbacks.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_ip_block_add_argument_flow_resolves_registered_version_funcs -v
```

Failure before the fix:

```text
('setup_and_hw_init', 'calls', 'sdma_v5_0_hw_init') unexpectedly found
```

GREEN targeted suite:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_ip_block_version_funcs_alias_resolves_nested_dispatch \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_ip_block_add_argument_flow_resolves_registered_version_funcs \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_field_path_type_hint_maps_rlc_funcs_without_local_assignment \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_known_field_path_does_not_fallback_to_unrelated_slot_when_type_has_no_match \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_generic_slot_call_links_common_dispatch_to_callbacks \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_resolves_cross_file_ip_block_version_funcs_alias \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_resolves_ip_block_add_argument_flow_across_files \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_maps_rlc_funcs_field_path_without_local_assignment \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_generic_common_dispatch_to_multiple_callbacks \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_stage1_specific_vtable_call_does_not_connect_every_same_named_slot -v
```

Result:

```text
Ran 10 tests in 0.629s
OK
```

Full core regression:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v
Ran 187 tests in 5.576s
OK (skipped=2)
```

## Real DB Rebuild

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src python3 -m asip.cli graph-rebuild --db data/asip.db
job_id: 77
files: 1225
deterministic edges: 42451
```

Checks after rebuild:

```text
rlc.funcs -> *_ip_funcs mislinks: 0
calls by kind:
direct              21697
vtable_dispatch      6495
vtable_callback        35
vtable_table_alias      7
```

The real global `adev->ip_blocks[i].version->funcs` loop is still recorded as `vtable_dispatch`; fully narrowing that path requires interprocedural device-state/array-slot propagation beyond this slice.

## Browser QA

In-app browser at `http://127.0.0.1:3100/graph`, 2048x1280 viewport:

```text
Screenshot: docs/qa/browser/graph-after-ip-block-flow-fix-2k.png
Snapshot: docs/qa/browser/graph-after-ip-block-flow-fix-2k-snapshot.md
graph edges: 3000
layers deterministic: 2987 semantic: 13
Loaded edge budget: 3000 / 20000
Visible nodes: 1000 / 2865
Visible edges: 3000 / 3000
visible graph summary: nodes 1000, edges 1148, doc_box 6, doc_section 1, function 834, register 159
```

## Residual

This slice improves proven IP block version/function-table aliases and cross-file indexing, but it does not fully model runtime order, all `adev->ip_blocks[]` array slots, or global device-state propagation. Full clangd/libclang and type-flow remains a G03 residual.
