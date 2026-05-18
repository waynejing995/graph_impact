# G03 Local Receiver Alias Type-Flow QA

Date: 2026-05-18

Status: pass for bounded source-level receiver alias flow; full clangd/libclang
cross-TU type-flow remains residual.

## Scope

This slice covers two real AMD callback shapes that were still too broad when
only receiver type was available:

- `const struct amdgpu_userq_funcs *uq_funcs = adev->userq_funcs[queue->queue_type];`
  followed by `uq_funcs->map(queue)`.
- `struct amd_ip_block *ip_block = &adev->ip_blocks[i];` followed by
  `ip_block->version->funcs->hw_init(ip_block)`.

The implementation records a local receiver alias only when the source path can
be tied to a known device-level receiver table alias. Plain local aliases such
as `funcs = &gfx_v11_0_ip_funcs` remain function-local and do not leak into
other functions.

This follow-up also covers the dynamic-index ambiguity that came out of code
review: if `adev->userq_funcs[queue->queue_type]` or
`&adev->ip_blocks[i]` can match multiple statically registered slots, Stage 1
must not collapse the selector to the first table. It keeps all known table
candidates and marks the callback as a lower-confidence `vtable_dispatch`.

## Real Source Evidence

```text
/tmp/asip-linux-amdgpu/drivers/gpu/drm/amd/amdgpu/gfx_v11_0.c:1635:
  adev->userq_funcs[AMDGPU_HW_IP_GFX] = &userq_mes_funcs;
/tmp/asip-linux-amdgpu/drivers/gpu/drm/amd/amdgpu/amdgpu_userq.c:427:
  const struct amdgpu_userq_funcs *uq_funcs = adev->userq_funcs[queue->queue_type];
/tmp/asip-linux-amdgpu/drivers/gpu/drm/amd/amdgpu/amdgpu_device.c:2037:
  ip_block = &adev->ip_blocks[i];
```

## RED/GREEN

Initial RED for the userq field-load alias:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_local_receiver_alias_from_indexed_field_load_limits_same_type_callbacks \
  -v

AssertionError: ('amdgpu_userq_post_reset', 'calls', 'userq_debug_map') unexpectedly found
```

Follow-up RED for local alias leakage:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_local_receiver_table_alias_does_not_leak_across_functions \
  -v

AssertionError: ('generic_common_hw_init', 'calls', 'sdma_v5_0_hw_init') not found
```

RED for the `ip_block = &adev->ip_blocks[i]` loop alias:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_ip_block_local_alias_resolves_registered_loop_dispatch \
  -v

AssertionError: ('amdgpu_device_hw_init', 'calls', 'sdma_v5_0_hw_init') unexpectedly found
```

RED for dynamic multi-slot alias collapse:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_dynamic_receiver_alias_keeps_multiple_array_slot_candidates \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_ip_block_local_alias_keeps_multiple_registered_candidates \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_marks_dynamic_receiver_alias_as_multi_candidate \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_marks_dynamic_ip_block_alias_as_multi_candidate \
  -v

FAILED (failures=4)
```

RED for multi-candidate receivers where only one candidate implements the
called slot:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_ambiguous_receiver_alias_keeps_dispatch_kind_with_single_slot_match \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_keeps_dispatch_kind_for_ambiguous_single_slot_match \
  -v

AssertionError: 'vtable_callback' != 'vtable_dispatch'
```

GREEN targeted:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_ip_block_local_alias_resolves_registered_loop_dispatch \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_local_receiver_table_alias_does_not_leak_across_functions \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_local_receiver_alias_from_indexed_field_load_limits_same_type_callbacks \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_resolves_device_field_loaded_receiver_alias_across_files \
  -v

Ran 4 tests in 0.242s
OK
```

GREEN targeted for dynamic multi-slot ambiguity:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_dynamic_receiver_alias_keeps_multiple_array_slot_candidates \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_ip_block_local_alias_keeps_multiple_registered_candidates \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_marks_dynamic_receiver_alias_as_multi_candidate \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_marks_dynamic_ip_block_alias_as_multi_candidate \
  -v

Ran 4 tests in 0.452s
OK
```

GREEN targeted after preserving dispatch kind for single-slot matches:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_dynamic_receiver_alias_keeps_multiple_array_slot_candidates \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_ip_block_local_alias_keeps_multiple_registered_candidates \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_ambiguous_receiver_alias_keeps_dispatch_kind_with_single_slot_match \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_marks_dynamic_receiver_alias_as_multi_candidate \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_marks_dynamic_ip_block_alias_as_multi_candidate \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_keeps_dispatch_kind_for_ambiguous_single_slot_match \
  -v

Ran 6 tests in 0.834s
OK
```

Broader graph/workbench regression:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph packages.core.tests.test_workbench_live -v

Ran 91 tests in 5.562s
OK
```

Full core:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v

Ran 234 tests in 23.762s
OK (skipped=2)
```

## Notes

New callback edge provenance uses:

- `type_flow=source_receiver_table_alias` for local pointers loaded from
  device-level callback table fields such as `adev->userq_funcs[...]`.
- `type_flow=local_receiver_path_alias` for local struct-pointer aliases that
  preserve a registered path such as `ip_block->version->funcs`.
- `type_flow=source_receiver_table_alias_ambiguous` or
  `type_flow=local_receiver_path_alias_ambiguous` when a dynamic indexed
  receiver maps to multiple registered tables. In that case the edge
  provenance uses `call_kind=vtable_dispatch`, not `vtable_table_alias`.

This narrows two concrete same-type overlink cases and improves the common
callback backbone, but it still does not claim full clangd/libclang cursor or
cross-translation-unit points-to analysis.
