# G03 Typed Callback Rebuild QA

Date: 2026-05-18

Note: this QA remains valid for the typed receiver/cross-file callback slice. A later AST JSON callback-initializer follow-up rebuilt the same live `data/asip.db` and recorded `41,929` deterministic graph-rebuild edges plus `6` `callback_initializer_flow=clang_ast_json` rows in `docs/qa/2026-05-18-g03-ast-json-callback-initializer-qa.md`.
Status: pass for this slice; full clangd/libclang cross-TU type-flow remains explicit residual

## Scope

This QA verifies the follow-up G03 callback/callgraph slice after the user
challenged the previous clangd/vtable wording.

The implementation is still not clangd/libclang. It uses:

- `clang -Xclang -ast-dump=json -fsyntax-only` as a narrow typed receiver hint source.
- source-span callback table and slot-call matching for conservative callback edges.
- corpus-level known function locations so callback table initializers can refer to functions defined in another file.

## RED/GREEN Tests

New red tests failed before implementation:

```text
test_stage1_clang_ast_receiver_type_overrides_generic_funcs_leaf
  expected common_unrelated_hw_init -> unrelated_hw_init
  actual before fix: common_unrelated_hw_init -> gfx_v11_0_hw_init

test_stage1_cross_file_callback_initializer_resolves_known_external_function
  expected amdgpu_common_hw_init -> gfx_v11_0_hw_init
  actual before fix: no callback edge
```

Green verification:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest packages.core.tests.test_code_graph -v

Ran 23 tests in 0.901s
OK
```

Targeted persisted-index verification:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
python3 -m unittest \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_cross_file_vtable_callbacks_to_registers \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_persists_clang_ast_json_vtable_receiver_type \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_stage1_specific_vtable_call_does_not_connect_every_same_named_slot \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_generic_common_dispatch_to_multiple_callbacks \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_filters_generic_ops_dispatch_by_declared_receiver_type \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_mxgpu_init_func_dispatch_to_register_callback \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_cross_file_callback_initializer_to_registers \
  -v

Ran 7 tests in 0.576s
OK
```

## Real AMD Rebuild

The default workbench DB was intentionally rebuilt after first validating the
same operation on `/tmp/asip-g03-typed-callback-2026-05-18.db`.

Command:

```text
PYTHONPATH=packages/core/src:. python3 -m asip.cli graph-rebuild \
  --db data/asip.db \
  --corpus-id linux-amdgpu \
  --corpus-id mxgpu
```

Result:

```text
source: deterministic_graph_rebuild
files: 1225
edges: 41923
job_id: 6
resolver_profile_ids:
  linux-amdgpu, amd-mxgpu, amd-direct-mmio, amd-field-macros,
  amd-soc15, amdgv-mxgpu-context, initial, python-hw-symbols, toy-python
```

SQLite graph evidence after rebuild:

```text
edge_total: 41936
deterministic clang_text_spans: 34987
deterministic clang_callback: 6127
deterministic text_fallback: 775
semantic ollama: 25
evidence query_expected_terms: 22

clang_callback call_kind/type_flow:
  vtable_dispatch / empty: 3836
  vtable_dispatch / clang_ast_json: 2200
  vtable_callback / empty: 35
  vtable_callback / clang_ast_json: 35
  vtable_table_alias / empty: 14
  vtable_table_alias / clang_ast_json: 7

cross-file callback edges: 44
typed callback edges: 2242
exact table-alias callback edges: 21
```

Query graph checks:

```text
GCVM_L2_CNTL: nodes=95 edges=231
  relations: reads=38 sets_field=49 writes=88 maps_base=3 calls=53
  sources: clang_text_spans=189 clang_callback=42

CP_INT_CNTL_RING0: nodes=148 edges=227
  relations: sets_field=31 maps_base=25 writes=45 reads=19 calls=107
  sources: clang_text_spans=198 clang_callback=29

SDMA0_GFX_RB_CNTL: nodes=106 edges=211
  relations: reads=28 writes=45 sets_field=52 calls=86
  sources: clang_text_spans=189 clang_callback=22
```

Global 20k graph sample:

```text
nodes: 15163
edges: 20000
node kinds: function=13671 register=1485 doc_box=6 doc_section=1
relations: calls=16022 writes=1746 reads=1053 sets_field=705 maps_base=463 contains=6 relates_to=5
components: 258
largest component: 9864
```

## Browser QA

In-app browser at `http://127.0.0.1:3100/graph`, 2048x1280 viewport.

Default global graph:

```text
graph edges: 3000
layers: deterministic 2989, semantic 11
visible nodes: 1000 / 2883
rendered edges: 1133
visible kinds: doc_box=6, doc_section=1, function=836, register=157
relationship panel: live function calls from API graph
```

Query `GCVM_L2_CNTL`:

```text
matches: 24
graph edges: 231
layers: deterministic 231
visible nodes: 95 / 95
visible edges: 231 / 231
visible kinds: function=35, register=60
relationship panel includes function -> function calls and function/register operations
```

Screenshots:

```text
docs/qa/browser/g03-typed-callback-global-graph-3100-2k.png
docs/qa/browser/g03-typed-callback-gcvm-query-3100-2k.png
```

## Residual

This slice reduces false same-slot linkage and reconnects cross-file callback
initializer paths, but it is still not a full clangd/libclang cross-translation
unit type-flow engine. Remaining G03 residuals include alias chains, casts,
container/device-state propagation, and compile-database-specific type
resolution that require a stronger typed extractor or explicit deferral.
