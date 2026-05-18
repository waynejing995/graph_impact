# G03 Return Table Alias QA

Date: 2026-05-18

Status: pass for bounded return-to-vtable table alias extraction; full clangd/libclang cross-TU type-flow remains residual.

## Scope

This slice follows the vtable/callback audit suggestion to cover a concrete type-flow gap:

```c
const struct amd_ip_funcs *select_gfx_funcs(void) {
  return &gfx_v11_0_ip_funcs;
}

int common_hw_init(void) {
  const struct amd_ip_funcs *funcs = select_gfx_funcs();
  return funcs->hw_init(0);
}
```

Before this fix, `common_hw_init()` used the declared receiver type `amd_ip_funcs` and could link to every `.hw_init` callback table with that type. The new bounded flow records that `select_gfx_funcs()` returns `gfx_v11_0_ip_funcs`, then treats `funcs = select_gfx_funcs()` as an exact receiver-table alias.

Expected graph behavior:

- include `common_hw_init calls gfx_v11_0_hw_init`;
- exclude unrelated same-type `common_hw_init calls sdma_v5_0_hw_init`;
- record `call_kind=vtable_table_alias`;
- record `receiver_tables=["gfx_v11_0_ip_funcs"]`;
- record `type_flow=source_return_table_alias`.

## RED/GREEN Tests

Initial RED:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_returned_table_alias_limits_same_type_callbacks \
  -v

AssertionError: ('common_hw_init', 'calls', 'sdma_v5_0_hw_init') unexpectedly found
```

Final targeted GREEN:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_returned_table_alias_limits_same_type_callbacks \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_uses_returned_table_alias_across_files \
  -v

OK
```

Ambiguity regression GREEN:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_skips_ambiguous_returned_table_aliases \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_uses_returned_table_alias_across_files \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_returned_table_alias_limits_same_type_callbacks \
  -v

Ran 3 tests in 0.261s
OK
```

This proves duplicate selector names such as two independent `select_funcs()`
definitions returning different tables are skipped instead of overlinked.

Broader graph/live GREEN:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph \
  packages.core.tests.test_workbench_live \
  -v

Ran 75 tests in 3.541s
OK
```

Full core rerun:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v

Ran 224 tests in 23.515s
OK (skipped=2)
```

## Residual

This is still not a full clangd/libclang index. It is a bounded source
return-alias fact that feeds the existing precise `receiver_tables` path.
It now rejects duplicate selector functions when the selector maps to more than
one returned table, but it does not solve all call-argument flow, array slot
identity, dynamic device-state propagation, or complete Linux-kernel
compile-database type-flow.
