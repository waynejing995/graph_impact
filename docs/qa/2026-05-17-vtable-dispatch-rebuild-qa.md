# Vtable Dispatch Rebuild QA

Date: 2026-05-17
Scope: G03/G17 user-review correction for AMD common callback connectivity.

## User Concern

The graph was still visually fragmented. The user called out that a real
clangd-style vtable parse would connect AMD common logic and callbacks, and
that both AMD repos should also meet through shared registers.

## Boundary

This pass does not claim full clangd/libclang cursor or type-flow resolution.
It implements and tests a conservative Stage 1 dispatch overlay:

- exact table calls such as `gfx_v11_0_ip_funcs.hw_init(...)` stay constrained
  to the matching table,
- generic common dispatchers such as `funcs->hw_init(...)`,
  `ops->resume(...)`, `init_func->hw_init(...)`,
  `adapt->init_funcs[i]->hw_init(...)`, and `callbacks->...(...)` emit
  lower-confidence `vtable_dispatch` provenance edges to all known callbacks
  for that slot, filtered by table type where possible,
- callback slot/table names remain provenance only, not graph nodes.
- `clang_text_spans` is used instead of `clang_ast` when clang only acts as a
  syntax/diagnostic probe and spans still come from source-text parsing.

## RED/GREEN Evidence

Initial failing tests:

```bash
PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_generic_slot_call_links_common_dispatch_to_callbacks -v
```

Failed before implementation because `amdgpu_common_hw_init` had no edges to
the same-slot callbacks.

```bash
PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_generic_common_dispatch_to_multiple_callbacks -v
```

Failed before implementation because cross-file generic dispatch did not
persist callback edges.

Passing targeted checks after implementation:

```bash
PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_cross_file_vtable_callbacks_to_registers \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_stage1_specific_vtable_call_does_not_connect_every_same_named_slot \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_generic_common_dispatch_to_multiple_callbacks -v
```

Result: 11 passed.

Additional MxGPU and truthful-provenance RED/GREEN checks:

```bash
PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_clang_stage_extracts_function_wrapper_and_register_edges \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_links_mxgpu_init_func_dispatch_to_callback \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_mxgpu_init_func_dispatch_to_register_callback -v
```

Result: passed after implementation. Before implementation, the first test
failed because `analysis_mode` was still `clang_ast`; the MxGPU tests failed
because `init_func->hw_init` did not connect to `gfx_v11_hw_init`.

## Real Local Rebuild

Command:

```bash
time PYTHONPATH=packages/core/src python3 -m asip.cli graph-rebuild \
  --db data/asip.db \
  --corpus-id linux-amdgpu \
  --corpus-id mxgpu
```

First result:

- job id: 58
- files: 1,225
- deterministic edges: 19,732
- elapsed: 46.312s total

Deterministic edge counts after rebuild:

```text
clang_text_spans calls      4,129
clang_text_spans maps_base  1,616
clang_text_spans reads      2,492
clang_text_spans sets_field   995
clang_text_spans writes     4,894
clang_callback calls 5,138
text_fallback calls    468
```

Callback provenance counts:

```text
direct           4,597
vtable_callback     80
vtable_dispatch  5,058
```

Second result after MxGPU init-function and provenance correction:

```bash
time PYTHONPATH=packages/core/src python3 -m asip.cli graph-rebuild \
  --db data/asip.db \
  --corpus-id linux-amdgpu \
  --corpus-id mxgpu
```

```text
job id: 59
files: 1,225
deterministic edges: 21,248
elapsed: 46.915s total
```

```text
clang_text_spans calls      4,129
clang_text_spans maps_base  1,616
clang_text_spans reads      2,492
clang_text_spans sets_field   995
clang_text_spans writes     4,894
clang_callback calls 6,654
text_fallback calls    468
```

```text
direct           4,597
vtable_callback      4
vtable_dispatch  6,650
source='clang_ast'   0
source='clang_text_spans' 14,126
amdgv_init_func dispatch rows 1,315
```

Example high-fanout common dispatch rows:

```text
amdgpu_device_ip_init 176
aldebaran_mode2_restore_ip 181
soc24_common_hw_init 112
amdgpu_ip_block_resume 103
```

## Product Graph Shape

No-limit global graph after first rebuild:

```text
nodes 7,497
edges 14,345
node kinds: function 5,879, register 1,611, doc_box 6, doc_section 1
relations: calls 9,607, writes 2,037, reads 1,262, sets_field 749, maps_base 679, contains 6, relates_to 5
```

Connected component smoke:

```text
components 632
largest component 4,113 nodes
largest component kinds: function 2,842, register 1,271
```

No-limit global graph after second rebuild:

```text
nodes 7,692
edges 15,404
node kinds: function 6,074, register 1,611, doc_box 6, doc_section 1
relations: calls 10,666, writes 2,037, reads 1,262, sets_field 749, maps_base 679, contains 6, relates_to 5
components 559
largest component 5,131 nodes
largest component kinds: function 3,707, register 1,424
```

Two-hop seed smoke:

```text
GCVM_L2_CNTL nodes 87 edges 216 rels calls,maps_base,reads,sets_field,writes
SDMA0_RLC0_RB_CNTL nodes 7 edges 6 rels calls,reads
gfx_v11_0_hw_init nodes 355 edges 1319 rels calls,reads,sets_field,writes
gfx_v11_hw_init nodes 361 edges 1102 rels calls,maps_base,reads,sets_field,writes
amdgv_device_func_sw_init nodes 756 edges 1950 rels calls,maps_base,reads,sets_field,writes
amdgpu_device_ip_init nodes 656 edges 2448 rels calls,maps_base,reads,writes
```

Default Web/API budget after call-backbone selection:

```text
GET /api/workbench/graph?all=1
nodes 2,407
edges 3,000
relations: calls 1,000, writes 929, reads 542, sets_field 327, maps_base 191, contains 6, relates_to 5
```

Browser QA:

```text
viewport: 2048x1280
route: http://127.0.0.1:3100/graph
snapshot: docs/qa/browser/graph-vtable-backbone-snapshot.md
screenshot: docs/qa/browser/graph-vtable-backbone-2k.png
console: React DevTools info only
visible page metric: graph edges: 3000
```

## 2026-05-18 Receiver Type-Hint Correction

User review correctly noted that a real vtable/callback graph should connect
through common callback logic and shared registers, and that the current
implementation must not be called full clangd/libclang vtable parsing.

This follow-up still does not claim full clangd/libclang type-flow. It adds a
tested source-span type-hint filter for receiver declarations such as
`struct amdgpu_ring_funcs *ops`, so generic `ops->slot()` calls are filtered
to callback tables with matching `table_type`. It also handles wrapped
function-pointer calls such as `(*ops->start)(...)`.

New RED tests before implementation:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_uses_receiver_declared_type_to_filter_generic_ops_callbacks \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_filters_generic_ops_dispatch_by_declared_receiver_type -v
```

Initial result: both tests failed because `(*ops->start)(...)` produced no
callback edge.

GREEN after implementation: same command reported 2 tests OK.

Broader targeted graph check:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph \
  packages.core.tests.test_workbench_live -v
```

Result: 45 tests OK.

Real local rebuild:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src python3 -m asip.cli graph-rebuild \
  --db data/asip.db \
  --corpus-id linux-amdgpu \
  --corpus-id mxgpu
```

Result:

```text
job id: 66
files: 1,225
deterministic edges: 21,265
```

Post-rebuild deterministic edge counts:

```text
clang_callback calls 6,671
clang_text_spans calls 4,129
clang_text_spans maps_base 1,616
clang_text_spans reads 2,492
clang_text_spans sets_field 995
clang_text_spans writes 4,894
text_fallback calls 468
```

Callback provenance counts:

```text
direct 4,597
vtable_callback 8
vtable_dispatch 6,663
```

Receiver type-hint coverage now appears in persisted provenance:

```text
amdgv_init_func 418
drm_crtc_helper_funcs 12
amdgv_gpu_reset_funcs 4
amdgv_pp_funcs 4
amdgpu_userq_funcs 3
drm_encoder_helper_funcs 1
```

Product graph after rebuild:

```text
no limit: nodes 7,696, edges 15,421, components 558, largest component 5,128
default limit 3000: nodes 2,726, edges 3,000, components 41, largest component 2,589
default limit sources: clang_callback 1,092, clang_text_spans 1,839, text_fallback 56, ollama 13
```

Browser QA after rebuild:

```text
viewport: 2048x1280
route: http://127.0.0.1:3100/graph
snapshot: docs/qa/browser/graph-receiver-type-after-rebuild-deep-snapshot.md
screenshot: docs/qa/browser/graph-receiver-type-after-rebuild-2k.png
visible metric: graph edges: 3000
layer badge: layers deterministic: 2987 semantic: 13
visible graph metric: nodes 1000
relationship panel: starts with callback/common calls from drm_mode_config_reset to AMD reset callbacks
top bar edge provider: Ollama / gemma4:e4b
```

## Remaining Risk

The current extractor is still not a full clangd/libclang type-flow parser.
It is a tested conservative overlay that makes AMD common dispatch visible in
the graph while preserving provenance. A future clangd/libclang implementation
should replace or refine `vtable_dispatch` candidate edges with exact
type-resolved callback calls where possible.
