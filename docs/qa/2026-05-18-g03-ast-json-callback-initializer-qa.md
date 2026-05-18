# G03 AST JSON Callback Initializer QA

Date: 2026-05-18

## Scope

This QA covers a bounded Stage 1 extractor improvement for macro-wrapped C callback table initializers. It does not claim full clangd/libclang cursor traversal or cross-translation-unit type-flow.

## RED

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_clang_ast_json_resolves_macro_wrapped_callback_initializer -v
```

Initial failure:

```text
AssertionError: ('amdgpu_common_hw_init', 'calls', 'gfx_v11_0_hw_init') not found
```

The fixture used `.hw_init = ASIP_CB(gfx_v11_0_hw_init)`. The old text initializer regex saw `ASIP_CB` as the candidate callback and dropped it because it was not a real function.

## GREEN

Implementation:

- Stage 1 now runs one narrow clang AST JSON pass for files that look like they contain callback slot calls or callback initializers.
- The AST JSON pass extracts real `DeclRefExpr -> FunctionDecl` callback references from table initializers.
- When the callback function is defined in a different file and clang reports the macro argument as an undeclared/recovery expression, Stage 1 uses the AST spelling offset plus the corpus-level unique function-location index to resolve the source identifier.
- The callback slot provenance records `callback_initializer_flow=clang_ast_json`.
- Macro names and callback slot names remain provenance only; they are not graph nodes.

Passing command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_clang_ast_json_resolves_macro_wrapped_callback_initializer -v
```

Result:

```text
Ran 1 test in 0.044s
OK
```

Regression command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_code_graph -v
```

Result:

```text
Ran 24 tests in 1.030s
OK
```

Persisted-index command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_cross_file_callback_initializer_to_registers -v
```

Result:

```text
Ran 1 test in 0.083s
OK
```

## Provenance Contract

The callback edge remains `source=clang_callback`. AST JSON is recorded only as bounded evidence:

- `type_flow=clang_ast_json` when clang exposes receiver type.
- `callback_initializer_flow=clang_ast_json` when clang resolves a macro-wrapped initializer to the real function.

Full clangd/libclang callback/type-flow remains a G03 residual.

## Real Corpus Rebuild

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m asip.cli graph-rebuild --db data/asip.db --corpus-id linux-amdgpu --corpus-id mxgpu
```

Result:

```json
{
  "source": "deterministic_graph_rebuild",
  "db_path": "data/asip.db",
  "corpus_ids": ["linux-amdgpu", "mxgpu"],
  "files": 1225,
  "edges": 41929,
  "job_id": 7
}
```

SQLite checks after rebuild:

```text
total edges: 41942
clang_text_spans: 34987
clang_callback: 6133
text_fallback: 775
ollama: 25
query_expected_terms: 22
type_flow=clang_ast_json: 2248
callback_initializer_flow=clang_ast_json: 6
```

Sample persisted callback-initializer edges:

```text
amdgpu_hdp_invalidate calls cik_invalidate_hdp via cik_asic_funcs
amdgpu_hdp_invalidate calls si_invalidate_hdp via si_asic_funcs
amdgpu_hdp_invalidate calls vi_invalidate_hdp via vi_asic_funcs
amdgpu_hdp_flush calls cik_flush_hdp via cik_asic_funcs
amdgpu_hdp_flush calls si_flush_hdp via si_asic_funcs
```

## Browser Smoke

In-app browser at `http://127.0.0.1:3100/graph`, 2048x1280 viewport:

```text
Edge provider badge: Ollama / gemma4:e4b
query: GCVM_L2_CNTL
matches: 24
graph edges: 231
layers deterministic: 231
visible nodes: 95 / 95
visible edges: 231 / 231
node kinds shown: function 35, register 60
```

The visible graph remains API-backed after the live rebuild; macro names and callback slot names are not exposed as graph node kinds.
