# API/MCP Doc Node And Callback Contract QA

Date: 2026-05-19
Status: Targeted pass for backend graph surfaces; not a full completion claim.

## Scope

This QA record covers two gaps found during the 2026-05-19 continuation audit:

- Stage 1 callback graph tests must reflect the current product projection:
  default graph view uses resolver-configured concept functions, while
  implementation view still exposes raw callback function nodes.
- FastAPI and MCP must expose the same LLM document-node generation feature as
  the Web BFF/CLI path, and their raw graph payloads must preserve the current
  product node contract: only `function`, `register`, and `doc`, with document
  subtypes in `attr.doc_kind`.

## Implementation Evidence

- `packages/core/tests/test_workbench_live.py` now checks both:
  `amdgpu_device_init -> concept:gfx_hw_init -> GCVM_L2_CNTL` in default
  concept view, and
  `amdgpu_device_init -> gfx_v11_0_hw_init -> GCVM_L2_CNTL` in implementation
  view.
- `apps/api/main.py` supports `POST /semantic-edges` with
  `mode = doc-nodes`.
- `apps/mcp/tools.py` exposes `semantic_doc_nodes_generate_batch()`.
- `apps/mcp/server.py` registers `semantic_doc_nodes_generate_batch` as a
  product MCP tool.
- API and MCP tests use a fake Ollama-compatible server that returns
  BoxMatrix-style `documents/boxes/relationships` JSON and assert:
  graph nodes are limited to `function/register/doc`, doc boxes are
  `kind = doc`, and `attr.doc_kind = boxmatrix_box`. The fake server now also
  rejects requests that do not include the configured `gemma4:e4b` model, the
  target document/chunk text, `GCVM_L2_CNTL`, and the BoxMatrix
  `documents/boxes/relationships` schema instruction.
- FastAPI validates `functionView` before calling core graph/query code, so
  invalid values return HTTP 400 instead of leaking a core `ValueError`.
- FastAPI validates `semantic-edges.mode` before provider dispatch, so unknown
  modes return a semantic-mode error instead of falling through to query mode.
- PDF-derived document nodes now preserve `attr.page` when the source metadata
  or anchor includes a page number.
- Function concept merge status now follows the resolver YAML overlap policy:
  disjoint register neighborhoods are `split_recommended`; partial overlap
  below the warning threshold is `divergent`; identical access remains merged.
- Function normalization is now scoped by resolver profile provenance in the
  product graph projection: edges without `resolver_profile` metadata do not
  consume global committed rules; DB resolver profile configs and YAML path
  fallback can provide rules; committed defaults remain available when an edge
  explicitly names a default profile such as `linux-amdgpu`; concept node ids
  include `resolver_profile_id`, so duplicate local rule ids in different
  profiles do not merge; duplicate rule ids use the current profile's merge
  policy.
- Disabled DB resolver profile aliases now disable both the row id and the
  loaded YAML profile id in graph projection and indexing profile selection.
- Product register projection now consumes `graph.register_normalization.identity`
  from DB/YAML resolver profiles; the default remains `register:{ip}:{symbol}`.
- Stage 1 callback/call edges now carry active `resolver_profile_ids` from the
  deterministic indexing run, so vtable/callback paths can still project to
  resolver-configured concept functions without falling back to unscoped global
  rules.

## Test Evidence

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_cross_file_vtable_callbacks_to_registers \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_global_graph_budget_preserves_callback_operation_edges \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_global_graph_budget_preserves_cross_repo_register_bridge_edges \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_clang_ast_receiver_type_overrides_generic_funcs_leaf \
  -v
```

Result: `Ran 4 tests`, `OK`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
  python3 -m unittest \
  apps.api.tests.test_app.ApiAppTests.test_semantic_edges_endpoint_generates_edges_from_live_db \
  apps.api.tests.test_app.ApiAppTests.test_semantic_edges_endpoint_runs_batch_generation \
  apps.api.tests.test_app.ApiAppTests.test_semantic_edges_endpoint_runs_doc_node_generation \
  apps.mcp.tests.test_tools.McpToolsTests.test_semantic_edges_tool_generates_edges_from_live_db \
  apps.mcp.tests.test_tools.McpToolsTests.test_semantic_edges_batch_tool_generates_edges_from_indexed_candidates \
  apps.mcp.tests.test_tools.McpToolsTests.test_semantic_doc_nodes_tool_generates_doc_boxes_from_indexed_documents \
  apps.mcp.tests.test_server.McpServerTests.test_build_server_registers_all_product_tools_with_fastmcp \
  -v
```

Result: `Ran 7 tests`, `OK`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_llm_doc_node_job_extracts_boxmatrix_style_doc_boxes \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_batch_semantic_edge_job_promotes_doc_section_nodes_into_default_global_graph \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_cross_file_vtable_callbacks_to_registers \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_global_graph_budget_preserves_callback_operation_edges \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_global_graph_budget_preserves_cross_repo_register_bridge_edges \
  -v
```

Result: `Ran 5 tests`, `OK`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
  python3 -m unittest \
  apps.api.tests.test_app.ApiAppTests.test_graph_endpoint_rejects_invalid_function_view \
  apps.api.tests.test_app.ApiAppTests.test_query_endpoint_rejects_invalid_function_view \
  apps.api.tests.test_app.ApiAppTests.test_semantic_edges_endpoint_rejects_unknown_mode \
  apps.api.tests.test_app.ApiAppTests.test_semantic_edges_endpoint_runs_doc_node_generation \
  apps.mcp.tests.test_tools.McpToolsTests.test_semantic_doc_nodes_tool_generates_doc_boxes_from_indexed_documents \
  -v
```

Result: `Ran 5 tests`, `OK`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
  python3 -m unittest \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_marks_disjoint_register_accesses_split_recommended \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_marks_low_overlap_register_accesses_divergent \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_nodes_merge_versioned_implementations \
  -v
```

Result: `Ran 3 tests`, `OK`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  apps.api.tests.test_app.ApiAppTests.test_semantic_edges_endpoint_generates_edges_from_live_db \
  apps.api.tests.test_app.ApiAppTests.test_semantic_edges_endpoint_runs_batch_generation \
  apps.api.tests.test_app.ApiAppTests.test_semantic_edges_endpoint_runs_doc_node_generation \
  apps.api.tests.test_app.ApiAppTests.test_graph_endpoint_rejects_invalid_function_view \
  apps.api.tests.test_app.ApiAppTests.test_query_endpoint_rejects_invalid_function_view \
  apps.api.tests.test_app.ApiAppTests.test_semantic_edges_endpoint_rejects_unknown_mode \
  apps.mcp.tests.test_tools.McpToolsTests.test_semantic_edges_tool_generates_edges_from_live_db \
  apps.mcp.tests.test_tools.McpToolsTests.test_semantic_edges_batch_tool_generates_edges_from_indexed_candidates \
  apps.mcp.tests.test_tools.McpToolsTests.test_semantic_doc_nodes_tool_generates_doc_boxes_from_indexed_documents \
  apps.mcp.tests.test_server.McpServerTests.test_build_server_registers_all_product_tools_with_fastmcp \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_llm_doc_node_job_extracts_boxmatrix_style_doc_boxes \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_batch_semantic_edge_job_promotes_doc_section_nodes_into_default_global_graph \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_cross_file_vtable_callbacks_to_registers \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_product_graph_projects_document_subtypes_to_doc_nodes \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_unknown_function_merge_policy_uses_default_thresholds \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_keeps_high_overlap_register_accesses_merged \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_marks_disjoint_register_accesses_split_recommended \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_marks_low_overlap_register_accesses_divergent \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_nodes_merge_versioned_implementations \
  -v
```

Result: `Ran 19 tests`, `OK`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_nodes_merge_versioned_implementations \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_without_profile_metadata_does_not_use_global_rules \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_normalization_is_scoped_to_edge_resolver_profile \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_default_resolver_profile_rules_survive_db_profile_overrides \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_normalization_uses_db_resolver_profile_rule \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_normalization_loads_db_profile_path_fallback \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_merge_policy_is_scoped_when_rule_ids_overlap \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_marks_disjoint_register_accesses_split_recommended \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_marks_low_overlap_register_accesses_divergent \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_keeps_high_overlap_register_accesses_merged \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_implementation_view_keeps_versioned_function_nodes \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_query_expansion_can_request_implementation_function_view \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_unknown_function_merge_policy_uses_default_thresholds \
  packages.core.tests.test_workbench_backend_state.WorkbenchBackendStateTests.test_selected_resolver_profiles_limit_registered_index_evidence_and_graph \
  packages.core.tests.test_workbench_cli.WorkbenchCliTests.test_index_and_graph_rebuild_commands_accept_resolver_profile_id \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_cross_file_vtable_callbacks_to_registers \
  -v
```

Result: `Ran 16 tests`, `OK`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. \
  python3 -m pytest \
  packages/core/tests/test_workbench_query_schema.py \
  packages/core/tests/test_storage_graph.py \
  packages/core/tests/test_workbench_backend_state.py \
  -q
```

Result: `85 passed, 2 skipped`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  apps.api.tests.test_app.ApiAppTests.test_semantic_edges_endpoint_generates_edges_from_live_db \
  apps.api.tests.test_app.ApiAppTests.test_semantic_edges_endpoint_runs_batch_generation \
  apps.api.tests.test_app.ApiAppTests.test_semantic_edges_endpoint_runs_doc_node_generation \
  apps.api.tests.test_app.ApiAppTests.test_graph_endpoint_rejects_invalid_function_view \
  apps.api.tests.test_app.ApiAppTests.test_query_endpoint_rejects_invalid_function_view \
  apps.api.tests.test_app.ApiAppTests.test_semantic_edges_endpoint_rejects_unknown_mode \
  apps.mcp.tests.test_tools.McpToolsTests.test_semantic_edges_tool_generates_edges_from_live_db \
  apps.mcp.tests.test_tools.McpToolsTests.test_semantic_edges_batch_tool_generates_edges_from_indexed_candidates \
  apps.mcp.tests.test_tools.McpToolsTests.test_semantic_doc_nodes_tool_generates_doc_boxes_from_indexed_documents \
  apps.mcp.tests.test_server.McpServerTests.test_build_server_registers_all_product_tools_with_fastmcp \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_llm_doc_node_job_extracts_boxmatrix_style_doc_boxes \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_batch_semantic_edge_job_promotes_doc_section_nodes_into_default_global_graph \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_cross_file_vtable_callbacks_to_registers \
  packages.core.tests.test_workbench_backend_state.WorkbenchBackendStateTests.test_selected_resolver_profiles_limit_registered_index_evidence_and_graph \
  packages.core.tests.test_workbench_backend_state.WorkbenchBackendStateTests.test_disabled_db_resolver_profile_overrides_default_index_profiles \
  packages.core.tests.test_workbench_cli.WorkbenchCliTests.test_index_and_graph_rebuild_commands_accept_resolver_profile_id \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_without_profile_metadata_does_not_use_global_rules \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_disabled_db_resolver_profile_overrides_default_rules \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_disabled_db_resolver_profile_alias_overrides_loaded_default_rules \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_default_resolver_profile_rules_survive_db_profile_overrides \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_normalization_loads_db_profile_path_fallback \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_concept_node_ids_are_profile_namespaced_when_rule_ids_overlap \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_register_normalization_uses_resolver_profile_identity \
  packages.core.tests.test_workbench_backend_state.WorkbenchBackendStateTests.test_disabled_db_resolver_profile_alias_overrides_loaded_default_index_profile \
  packages.core.tests.test_storage_graph.StorageGraphTests.test_function_merge_policy_is_scoped_when_rule_ids_overlap \
  -v
```

Result after the follow-up profile-scope fix: `Ran 25 tests`, `OK`.

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest \
  packages.core.tests.test_resolver_profiles \
  packages.core.tests.test_storage_graph \
  packages.core.tests.test_workbench_backend_state \
  -v
```

Result for the full resolver/storage/backend module sweep:
`Ran 83 tests`, `OK (skipped=2)`.

```text
pnpm --filter web exec playwright test \
  apps/web/tests/workbench-api.spec.ts \
  --grep "graph API can switch|resolver operators"
```

Result: `2 passed`.

## Residual Risk

- This pass proves the API/MCP doc-node surface and current callback projection
  contract plus the first resolver-policy merge-status guard. It does not
  claim full clangd/libclang cross-translation-unit type flow.
- This pass uses a local fake Ollama-compatible server for deterministic
  API/MCP tests. Live local Ollama/gemma4 evidence remains covered by separate
  clean/current artifacts and still needs final-package reconciliation.
- Function and register normalization are now profile-scoped for deterministic
  graph projection. Remaining follow-up: evidence rows still lack structured
  resolver-profile provenance, so evidence-derived fallback projection should
  gain `resolver_profile_id` or `provenance_json` before calling that path fully
  scoped.
- The final goal remains open until full clean DB acceptance, browser QA,
  e2e, final artifact review, and git gate all pass together.
