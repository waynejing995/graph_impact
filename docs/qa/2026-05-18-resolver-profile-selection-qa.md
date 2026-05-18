# 2026-05-18 Resolver Profile Selection QA

## Scope

This QA covers per-index resolver profile selection across core, CLI, FastAPI, MCP, Web BFF, and the Corpus page.

## RED / GREEN Highlights

- Core RED: `index_registered_corpora(... resolver_profile_ids=["custom-a"])` initially raised `TypeError`.
- Web API RED: `/api/workbench/index` accepted `resolverProfileIds` in the body but did not return or pass the selected ids.
- Web UI RED: Corpus page had no resolver-profile checkbox named `Use resolver profile amd-soc15`.

## Implemented Behavior

- Core index/rebuild functions filter resolver profiles by selected ids and record active ids in job metadata.
- CLI accepts repeated `--resolver-profile-id` on `index` and `graph-rebuild`.
- FastAPI `/index` and `/graph-rebuild` accept snake/camel profile id fields.
- MCP `corpora_index` and `graph_rebuild` accept snake/camel profile id fields.
- Next `/api/workbench/index` passes selected ids to the CLI and returns `resolverProfileIds`.
- Corpus page renders enabled YAML-backed profiles as shadcn/Radix checkboxes and sends selected ids with the index request.

## Verification

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_backend_state.WorkbenchBackendStateTests.test_selected_resolver_profiles_limit_registered_index_evidence_and_graph \
  packages.core.tests.test_workbench_cli -v
```

Result:

```text
Ran 8 tests in 3.732s
OK
```

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:. python3 -m unittest \
  apps.api.tests.test_app apps.mcp.tests.test_tools apps.mcp.tests.test_server -v
```

Result:

```text
Ran 45 tests in 77.310s
OK (skipped=1)
```

```bash
pnpm --filter web exec playwright test tests/workbench-api.spec.ts -g "index API passes selected resolver profiles" --reporter=list
```

Result:

```text
1 passed
```

```bash
pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts -g "corpus page (runs the index job|indexes only the selected corpus|sends the selected resolver profiles|shows durable index job|marks selected corpus failed)" --reporter=list
```

Result:

```text
5 passed
```

Post-fix full regression also passed after tightening job event deduplication:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest discover -s packages/core/tests -p 'test_*.py' -v
Ran 176 tests in 5.154s
OK (skipped=2)

pnpm --filter web exec playwright test tests/workbench-api.spec.ts tests/workbench-smoke.spec.ts --reporter=list
73 passed
```

The full regression initially caught a duplicate `indexing` event after active resolver ids were written back into job metadata. `AsipStore.update_job_status()` now appends a lifecycle event only when the job status or display message changes, while metadata-only updates still persist.

## Browser QA

In-app browser was opened at `http://127.0.0.1:3100/corpus` with a 2048x1280 viewport.

- Screenshot: `docs/qa/browser/corpus-resolver-selector-after-g05-2k.png`
- Snapshot: `docs/qa/browser/corpus-resolver-selector-after-g05-full-depth-snapshot.md`

Snapshot evidence includes checked shadcn/Radix checkboxes for real YAML-backed profiles such as:

```text
Use resolver profile amd-direct-mmio
Use resolver profile amd-field-macros
Use resolver profile amd-mxgpu
Use resolver profile amd-soc15
Use resolver profile amdgv-mxgpu-context
Use resolver profile initial
Use resolver profile linux-amdgpu
Use resolver profile python-hw-symbols
Use resolver profile toy-python
```

## Remaining Boundary

The product can now select YAML-backed profiles per job, but it still needs richer diagnostics explaining unmatched wrappers/spans and broader non-C language strategies beyond the current configured Python call extractors.
