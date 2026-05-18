# 2026-05-18 Clang AST JSON Vtable Type Hints QA

## Scope

This QA answers the user challenge that a real clangd/libclang vtable parse should connect common AMD callback logic rather than leaving only scattered point clusters.

The current implementation still does not run clangd or libclang cursor traversal. This slice adds a narrower, truthful typed path: when `clang -Xclang -ast-dump=json -fsyntax-only` can parse a source file enough to expose a callback receiver expression, Stage 1 records the receiver table type on the callback edge as `type_flow=clang_ast_json`.

The older `source=clang_callback` rows remain a conservative overlay. They may now include `type_flow=clang_ast_json` when the receiver type came from Clang AST JSON; otherwise they remain source-span/alias/type-hint derived.

## RED / GREEN

RED test before implementation:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_records_clang_ast_json_type_flow_for_nested_vtable_receiver -v
```

Failure:

```text
AssertionError: '' != 'amd_ip_funcs'
+ amd_ip_funcs
```

GREEN targeted suite after implementation:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_records_clang_ast_json_type_flow_for_nested_vtable_receiver \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_links_vtable_slot_calls_to_callbacks_and_common_helpers \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_ip_block_add_argument_flow_resolves_registered_version_funcs \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_persists_clang_ast_json_vtable_receiver_type \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_resolves_ip_block_add_argument_flow_across_files -v

Ran 5 tests in 0.369s
OK
```

Full core regression:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v
Ran 189 tests in 6.355s
OK (skipped=2)
```

## Real DB Rebuild

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src python3 -m asip.cli graph-rebuild --db data/asip.db
job_id: 78
files: 1225
deterministic edges: 43030
```

Post-rebuild SQLite checks:

```text
callback edges with type_flow=clang_ast_json: 2220
calls with non-empty receiver_type: 2287
calls by kind:
direct              21697
vtable_dispatch      7042
vtable_callback        67
vtable_table_alias      7
```

Examples of real typed callback receiver provenance:

```text
gfx_v11_0_ring_preempt_ib -> gfx11_kiq_unmap_queues
receiver: kiq->pmf
receiver_type: kiq_pm4_funcs
type_flow: clang_ast_json

aldebaran_mode2_restore_ip -> gfxhub_v11_5_0_init
receiver: adev->gfxhub.funcs
receiver_type: amdgpu_gfxhub_funcs
type_flow: clang_ast_json
```

Full product graph sample at `limit=20000`:

```text
nodes 15239
edges 20000
components 237
largest component 10021
relations: calls=16020 writes=1746 reads=1055 sets_field=705 maps_base=463 contains=6 relates_to=5
sources: clang_text_spans=14314 clang_callback=5427 text_fallback=246 ollama=13
```

For comparison, before this slice the same sample had `15040` nodes, `20000` edges, `277` components, and largest component `9835`.

## Browser QA

In-app browser at `http://127.0.0.1:3100/graph`, 2048x1280 viewport:

```text
Screenshot: docs/qa/browser/graph-after-clang-ast-json-type-hints-2k.png
Snapshot: docs/qa/browser/graph-after-clang-ast-json-type-hints-2k-snapshot.md
graph edges: 3000
layers deterministic: 2987 semantic: 13
Loaded edge budget: 3000 / 20000
Visible nodes: 1000 / 2900
Visible edges: 3000 / 3000
visible graph summary: nodes 1000, edges 1101, doc_box 6, doc_section 1, function 834, register 159
```

## Residual

This is an improvement, not closure of full clangd/libclang vtable parsing.

Still open:

- true clangd/libclang cross-translation-unit cursor/type-flow,
- Linux kernel compile database completeness,
- runtime array-slot precision for `adev->ip_blocks[i].version->funcs`,
- interprocedural device-state propagation,
- duplicate static helper disambiguation beyond conservative unique-name linking.

The graph is more connected after adding AST JSON receiver type hints, but this evidence does not justify claiming that clangd vtable parsing is complete.
