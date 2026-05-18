# 2026-05-18 IP Block Registration Flow QA

## Scope

This QA covers a Stage 1 graph precision fix for real amdgpu common dispatch:
`amdgpu_device_ip_block_add(adev, &*_ip_block)` can happen in a setup path, while
another common function later dispatches through
`adev->ip_blocks[i].version->funcs->slot(...)`.

The goal is not full clangd/libclang type-flow. The goal is narrower: when a
concrete IP block registration is provable from source, use its `.funcs` table
as a strong alias for the common loop receiver, and do not fall back to unrelated
same-slot `amd_ip_funcs` callbacks when the exact registered table lacks a slot.

## RED

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_ip_block_add_registration_flow_resolves_common_loop_dispatch \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_resolves_registered_ip_block_common_loop_across_files -v

FAILED (failures=2)
```

Both failures showed `amdgpu_device_hw_init -> sdma_v5_0_hw_init` even though
only `gfx_v11_0_ip_block` was registered.

A second RED caught the exact-alias fallback bug:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_exact_ip_block_registration_does_not_fallback_when_slot_is_absent -v

FAILED (failures=1)
```

## GREEN

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_exact_ip_block_registration_does_not_fallback_when_slot_is_absent \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_ip_block_add_registration_flow_resolves_common_loop_dispatch \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_resolves_registered_ip_block_common_loop_across_files -v

Ran 3 tests in 0.342s
OK
```

Related Stage 1 regression:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_resolves_ip_block_add_argument_flow_across_files \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_resolves_registered_ip_block_common_loop_across_files \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_resolves_cross_file_ip_block_version_funcs_alias \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_cross_file_vtable_callbacks_to_registers -v

Ran 23 tests in 1.546s
OK
```

## Real DB Rebuild

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src python3 -m asip.cli graph-rebuild --db data/asip.db

job_id: 80
files: 1225
edges: 41998
```

Post-rebuild SQLite checks:

```text
total deterministic edges: 41964
clang_callback:
  vtable_dispatch / no type_flow: 3818
  vtable_dispatch / clang_ast_json: 2178
  vtable_callback / clang_ast_json: 35
  vtable_callback / no type_flow: 32
  vtable_table_alias / no type_flow: 14
  vtable_table_alias / clang_ast_json: 7

ip_blocks version funcs table_alias: 14
ip_blocks version funcs dispatch: 13
alias fallback mismatches: 0

global_graph(limit=20000):
  nodes: 15170
  edges: 20000
  components: 261
  largest component: 9864
```

Representative exact aliases:

```text
aldebaran_mode2_restore_ip -> nv_common_late_init
amdgpu_device_ip_hw_init_phase1 -> nv_common_hw_init
amdgpu_device_ip_hw_init_phase2 -> nv_common_hw_init
amdgpu_device_ip_init -> nv_common_sw_init
amdgpu_device_ip_set_clockgating_state -> nv_common_set_clockgating_state
amdgpu_device_ip_get_clockgating_state -> nv_common_get_clockgating_state
```

## Browser QA

In-app browser QA was run at `http://127.0.0.1:3100/graph` with a 2048x1280
viewport after job 80.

Artifacts:

- `docs/qa/browser/graph-after-ip-block-registration-flow-2k.png`
- `docs/qa/browser/graph-after-ip-block-registration-flow-2k-snapshot.md`
- `docs/qa/browser/graph-after-ip-block-registration-flow-2k-snapshot-full.md`

Snapshot evidence:

```text
graph edges: 3000
layers deterministic: 2987 semantic: 13
Loaded edge budget: 3000 / 20000
Visible nodes: 1000 / 2885
Visible edges: 3000 / 3000
accessibility graph summary:
  nodes 1000
  edges 1132
  doc_box 6
  doc_section 1
  function 834
  register 159
relationship panel includes:
  aldebaran_mode2_restore_ip calls nv_common_late_init
```

## Residual

This is still not a full clangd/libclang cross-TU type-flow solution. The
remaining `ip_blocks version funcs dispatch: 13` rows are kept as lower-confidence
dispatch candidates because the extractor cannot yet prove exact device-state
array-slot flow for every real kernel path.
