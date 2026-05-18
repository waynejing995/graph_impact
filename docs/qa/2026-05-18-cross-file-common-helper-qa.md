# 2026-05-18 Cross-File Common Helper QA

## Scope

User review asked whether clangd vtable parsing had really been implemented, because a fully connected AMD graph should converge through common callback logic and shared registers rather than appearing as isolated point clusters.

This slice does not claim full clangd/libclang vtable parsing. It fixes one concrete Stage 1 gap found during that review: deterministic direct calls previously only resolved callees defined in the same file, so common helper chains could break before reaching register operations.

## RED

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_cross_file_direct_common_helpers_to_registers -v
```

Failure before implementation:

```text
AssertionError: ('function:linux-amdgpu:common.c:amdgpu_common_resume', 'calls', 'function:linux-amdgpu:gfx_v11_0.c:program_gcvm_l2') not found
```

The only persisted graph edge was `program_gcvm_l2 -> GCVM_L2_CNTL`, proving the cross-file common helper call was missing.

## GREEN

Implementation:

- `packages/core/src/asip/code_graph.py` now exposes `collect_code_graph_function_locations()`.
- `packages/core/src/asip/workbench.py` builds a per-corpus function-name/location index before extracting code graph edges.
- `build_deterministic_code_graph()` accepts that index and emits direct `calls` edges to uniquely defined cross-file callees.
- Direct call provenance records `callee_path` and `callee_line`; ambiguous duplicate callees are skipped rather than over-connected.

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_cross_file_direct_common_helpers_to_registers packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_cross_file_vtable_callbacks_to_registers packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_links_generic_common_dispatch_to_multiple_callbacks packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_index_registered_corpus_filters_generic_ops_dispatch_by_declared_receiver_type -v
```

Result:

```text
Ran 4 tests in 0.277s
OK
```

Additional related check:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest packages.core.tests.test_code_graph.DeterministicCodeGraphTests -v
```

Result:

```text
Ran 10 tests in 0.289s
OK
```

## Real Rebuild

Command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src python3 -m asip.cli graph-rebuild --db data/asip.db --corpus-id linux-amdgpu --corpus-id mxgpu
```

Result:

```json
{
  "source": "deterministic_graph_rebuild",
  "db_path": "data/asip.db",
  "corpus_ids": ["linux-amdgpu", "mxgpu"],
  "files": 1225,
  "edges": 26334,
  "job_id": 69
}
```

Post-rebuild checks:

- persisted `calls` by source: `clang_text_spans/direct=9183`, `clang_callback/vtable_dispatch=6663`, `text_fallback/direct=483`, `clang_callback/vtable_callback=8`.
- cross-file direct calls with distinct `path` and `callee_path`: `5054`.
- default product graph: `2797 nodes`, `3000 edges`, `95 components`, largest component `2274`, `1284` visible `clang_callback` edges.
- full product graph: `9298 nodes`, `20490 edges`, `284 components`, largest component `8041`, `6214` `clang_callback` edges.
- shared register nodes with both `linux-amdgpu` and `mxgpu` source records: `115`, including `CP_MEC_RS64_CNTL`, `CP_HQD_PQ_DOORBELL_CONTROL`, and `BIF_DOORBELL_INT_CNTL`.

Example real cross-file direct calls now persisted:

```text
aldebaran_mode2_suspend_ip -> amdgpu_ip_block_suspend
  caller path: drivers/gpu/drm/amd/amdgpu/aldebaran.c
  callee path: drivers/gpu/drm/amd/amdgpu/amdgpu_ip.c

amdgpu_amdkfd_gpu_reset -> amdgpu_device_should_recover_gpu
  caller path: drivers/gpu/drm/amd/amdgpu/amdgpu_amdkfd.c
  callee path: drivers/gpu/drm/amd/amdgpu/amdgpu_device.c
```

Browser QA at 2K:

- `docs/qa/browser/graph-cross-file-common-after-rebuild-2k.png`
- `docs/qa/browser/graph-cross-file-common-after-rebuild-snapshot.md`

Force graph accessibility summary after rebuild: `nodes 1000`, `edges 1216`, `function 787`, `register 206`, `doc_box 6`, `doc_section 1`.

## Regression Suite

Commands:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest apps.api.tests.test_app apps.api.tests.test_runtime apps.mcp.tests.test_tools apps.mcp.tests.test_server -v
pnpm --filter web exec playwright test tests/workbench-api.spec.ts tests/workbench-smoke.spec.ts --reporter=list
pnpm --filter web exec playwright test tests/visual-anchor-routes.spec.ts --reporter=list
git diff --check
```

Results:

```text
Core: 173 tests OK, skipped=2
API/MCP: 42 tests OK, skipped=1
Web API + smoke: 71 passed
Visual anchor routes: 15 passed
git diff --check: pass
```

## Boundary

This is still a source-span deterministic graph overlay, not clangd/libclang cursor type-flow parsing. It improves real graph connectivity for common helper chains, but full typed call-graph/vtable resolution remains an explicit G03 follow-up.
