# G01/G04 AMDGPU Multi-Subfolder Corpus QA

Date: 2026-05-18

Status: pass for multi-subfolder ingestion plumbing; follow-up performance and
header-symbol filtering required before using the expanded header corpus as the
default production DB.

## Problem

The prior `linux-amdgpu` corpus only checked out and scanned:

```text
drivers/gpu/drm/amd/amdgpu
```

That excluded generated AMD register headers under:

```text
drivers/gpu/drm/amd/include/asic_reg
```

The visible graph therefore under-reported register nodes. The previously
observed `830` product-graph register nodes was a connected graph count, not a
register inventory count.

## Fix

The corpus model now supports multiple repo-relative subfolder filters for one
logical corpus. This lets one `linux-amdgpu` corpus scan both source code and
the sibling generated register header tree without widening to the whole Linux
kernel checkout.

Configured `linux-amdgpu` corpora now include:

```text
drivers/gpu/drm/amd/amdgpu: **/*.c, **/*.h, **/*.md, **/*.rst, **/*.pdf
drivers/gpu/drm/amd/include/asic_reg: **/*.h
```

The Web Corpus page exposes this as a multiline `Subfolder filters` field. The
API and CLI persist structured `metadata.subfolders`, and registered-corpus
indexing plus deterministic graph rebuild both read that same metadata.

Subfolder paths are validated as repo-relative. Absolute paths, `..`, empty
path components, `~`, and `:` are rejected so a corpus cannot scan outside its
declared `source_root`.

The Python core accepts both config-style `relative_root` and UI/API-style
`relativeRoot` keys. Explicit subfolder objects without a root are rejected
instead of being silently interpreted as the whole repo.

## Real Checkout Verification

The local linux checkout was expanded from one sparse path to two:

```text
git -C /tmp/asip-linux-amdgpu sparse-checkout list

drivers/gpu/drm/amd/amdgpu
drivers/gpu/drm/amd/include/asic_reg
```

Header count:

```text
find /tmp/asip-linux-amdgpu/drivers/gpu/drm/amd/include/asic_reg -type f -name '*.h' | wc -l

476
```

Configured scanner count after the fix:

```text
drivers/gpu/drm/amd/amdgpu 625 files
drivers/gpu/drm/amd/include/asic_reg 476 files
total_unique 1101 files
```

## TDD Evidence

RED failures before implementation:

```text
test_full_corpus_rejects_subfolder_filters_outside_source_root ... FAIL
test_registered_corpus_rejects_subfolder_filters_outside_source_root ... FAIL
test_index_and_graph_rebuild_commands_accept_resolver_profile_id ... ERROR
test_index_command_requires_config_only_for_configured_corpus_indexing ... FAIL
```

GREEN after implementation and review hardening:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_semantic_edges.SemanticEdgeFeatureTests.test_full_corpus_can_scan_multiple_subfolders_in_one_repo \
  packages.core.tests.test_semantic_edges.SemanticEdgeFeatureTests.test_full_corpus_rejects_subfolder_filters_outside_source_root \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_configured_index_supports_multiple_subfolder_filters_for_one_repo \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_rebuild_deterministic_graph_honors_registered_subfolder_filters \
  packages.core.tests.test_workbench_corpus_state.WorkbenchCorpusStateTests.test_registered_corpus_indexes_multiple_subfolder_filters \
  packages.core.tests.test_workbench_corpus_state.WorkbenchCorpusStateTests.test_registered_corpus_accepts_camel_case_subfolder_filters_without_repo_wide_scan \
  packages.core.tests.test_workbench_corpus_state.WorkbenchCorpusStateTests.test_registered_corpus_rejects_subfolder_filters_outside_source_root \
  packages.core.tests.test_workbench_cli.WorkbenchCliTests.test_index_and_graph_rebuild_commands_accept_resolver_profile_id \
  packages.core.tests.test_workbench_cli.WorkbenchCliTests.test_index_command_requires_config_only_for_configured_corpus_indexing \
  -v

Ran 9 tests in 1.285s
OK
```

Web API and UI:

```text
pnpm --filter web test:ui apps/web/tests/workbench-api.spec.ts apps/web/tests/workbench-smoke.spec.ts -g \
  "corpora API persists user-added corpus subfolder filters|corpora API rejects unsafe subfolder filters outside the corpus root|index API honors user-added corpus subfolder filters|corpus page submits multiline subfolder filters as structured corpus metadata"

4 passed
```

TypeScript:

```text
pnpm --filter web exec tsc --noEmit

passed
```

## Real Temp Index

A temp DB rebuild for only `linux-amdgpu` with the new two-subfolder config ran
from:

```text
/tmp/asip-linux-amdgpu
```

Final output:

```text
db_path /var/folders/b6/q7tnsx1974gb0jhjkj023ltw0000gn/T/asip-linux-amdgpu-subfolders-bm191rno/asip.db
elapsed_sec 1758.77
summary {"chunks": 120850, "documents": 477, "edges": 27559, "evidence": 4784408, "files": 1101, "job_status": "succeeded"}
documents_by_type [('code', 1), ('register', 476)]
asic_reg_docs 476
register_evidence (4784398, 1514784)
```

Corpus metadata recorded the two scan roots:

```text
drivers/gpu/drm/amd/amdgpu file_count=625
drivers/gpu/drm/amd/include/asic_reg file_count=476
```

This proves the new header corpus is no longer a dry config change: generated
register headers are entering the evidence store at scale.

## Follow-Up Risk

The full `asic_reg` import exposed a new performance/quality risk. Register
header evidence is currently too broad: it produced `4,784,398` register
evidence rows and `1,514,784` distinct symbols, including low-signal tokens such
as `A`. The multi-subfolder feature is correct, but the production default index
should not simply ingest every identifier from generated register headers as an
evidence symbol. The next indexing pass should add register-header-specific
symbol filtering or an inventory table path before replacing the default
`data/asip.db` with the expanded header corpus.
