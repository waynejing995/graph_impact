---
name: asip-set-normalization-rules
description: Use when adding, editing, reviewing, or debugging ASIP resolver profile normalization rules for concept functions, registers, access relations, Graph Explorer nodes, or Resolver Profiles UI behavior.
---

# ASIP Normalization Rules

## Core Principle

Normalization is config-owned. Put repo naming conventions in resolver profiles or inline resolver config, not in ad hoc Python or TypeScript conditionals.

## Sources Of Truth

- Human guide: `docs/guides/normalization-rules.md`
- Committed profiles: `configs/resolvers/*.yaml`
- Config parser: `packages/core/src/asip/resolver_profiles.py`
- Graph projection: `packages/core/src/asip/storage.py`
- Resolver API/UI: `apps/web/app/api/workbench/resolver-profiles/route.ts`, `apps/web/components/workbench-page.tsx`

## Workflow

1. Run `git status -sb` and preserve user edits.
2. Decide whether the change is a committed YAML rule or a UI inline resolver profile.
3. Search existing rules before adding another:

```bash
grep -R "function_normalization\\|register_normalization\\|access_relation_map" -n configs/resolvers packages/core/tests apps/web/tests
```

4. For YAML rules, edit `configs/resolvers/<profile>.yaml`.
5. For UI inline rules, verify the Resolver Profiles page posts `functionNormalization`.
6. Add or update tests that prove config drives the graph.

## Function Concept Rule Template

```yaml
graph:
  function_normalization:
    enabled: true
    rules:
      - id: amd-ip-versioned-functions
        enabled: true
        match: "^(?P<ip_block>gfxhub|gfx|gmc|sdma)_v(?P<ip_version>\\d+(?:_\\d+){0,2})_(?P<operation>.+)$"
        canonical: "{ip_block}_{operation}"
        merge_policy:
          mode: concept_with_implementations
          warn_register_overlap_below: 0.35
          split_register_overlap_below: 0.10
```

Concept nodes must preserve implementations. Browser proof should click the canvas node and show `Concept Generated From`.

## Register And Access Rules

```yaml
graph:
  register_normalization:
    identity: "register:{ip}:{symbol}"
    merge_across_repos_when_ip_and_symbol_match: true
    merge_across_ip_versions: true
    merge_across_ip_blocks: false
  access_relation_map:
    field_write: writes
    field_read: reads
    field_set: sets_field
```

Keep `{ip}` or `{ip_version}` in `identity` when the matching merge flag is false.

## Required Checks

Resolver/profile parser:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest packages.core.tests.test_resolver_profiles -v
```

Graph behavior:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest packages.core.tests.test_storage_graph -v
```

Inline UI/API behavior:

```bash
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3102 \
pnpm --filter web exec playwright test tests/workbench-api.spec.ts \
  -g "resolver profiles API accepts inline concept normalization config" \
  --reporter=line

PLAYWRIGHT_SKIP_WEB_SERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:3102 \
pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts \
  -g "resolver page sends configurable concept normalization rules" \
  --reporter=line
```

## Do Not

- Hardcode function-name prefixes in graph/storage/UI code.
- Claim correctness from a `:concept:` node id alone.
- Broaden regexes without checking raw implementations and register overlap.
- Treat a reachable page as browser proof; inspect the graph detail pane.
