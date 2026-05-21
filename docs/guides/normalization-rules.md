# Normalization Rules Guide

This guide explains how people and agents should set ASIP graph normalization rules without hardcoding repo-specific behavior in Python or TypeScript.

## What Owns Normalization

Normalization is owned by resolver profiles, not by UI labels or parser heuristics.

- Committed profiles live in `configs/resolvers/*.yaml`.
- User-created UI profiles are persisted in `data/asip.db` with an inline resolver config.
- The parser for the supported config shape is `packages/core/src/asip/resolver_profiles.py`.
- Product graph projection reads those configs in `packages/core/src/asip/storage.py`.

Do not add a one-off conditional such as `if name.startswith("gfxhub_v")` in code. Add or edit a resolver profile rule, then prove the graph behavior with tests.

## Rule Types

### Function Concept Normalization

Use `graph.function_normalization` when versioned implementation functions should appear as one concept node while preserving raw implementations.

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

Supported fields:

- `enabled`: profile-level and rule-level switch.
- `id`: stable rule id. It becomes part of concept provenance and node ids.
- `match`: Python regular expression. Use named groups for any value referenced by `canonical`.
- `canonical`: format string for the concept label, for example `{ip_block}_{operation}`.
- `merge_policy.mode`: currently `concept_with_implementations`.
- `warn_register_overlap_below`: mark low-overlap concepts as divergent.
- `split_register_overlap_below`: mark very low-overlap concepts as split recommended.

The concept node id includes profile and rule identity:

```text
function:<corpus>:concept:<profile-id>:<rule-id>:<canonical-name>
```

Clicking a concept node in Graph Explorer should show `Concept Generated From`, implementation names, source paths, and raw implementation records.

### Register Normalization

Use `graph.register_normalization` when register identity should merge across files, repos, or IP versions in a controlled way.

```yaml
graph:
  register_normalization:
    identity: "register:{ip}:{symbol}"
    merge_across_repos_when_ip_and_symbol_match: true
    merge_across_ip_versions: true
    merge_across_ip_blocks: false
```

Supported identity tokens include `{symbol}`, `{ip}`, and `{ip_version}`. If a merge flag is false, keep the corresponding token in `identity` so the graph does not silently over-merge.

### Access Relation Mapping

Use `graph.access_relation_map` when resolver wrapper access names need product graph relations.

```yaml
graph:
  access_relation_map:
    field_write: writes
    field_read: reads
    field_set: sets_field
```

The relation must be a product graph relation accepted by the graph schema. Keep raw access in provenance; do not erase whether the evidence was read, write, field, mask, shift, or address-like.

## Editing A Committed YAML Profile

1. Choose the owning profile, usually `linux-amdgpu`, `amd-mxgpu`, or a narrower profile under `configs/resolvers/`.
2. Add or edit `graph.function_normalization`, `graph.register_normalization`, or `graph.access_relation_map`.
3. Use a narrow regex and keep the profile id/rule id stable.
4. Add or update tests before relying on the rule.

Focused validation:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest packages.core.tests.test_resolver_profiles -v

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. \
  python3 -m unittest packages.core.tests.test_storage_graph -v
```

If the rule changes UI-visible concept behavior, also run:

```bash
PLAYWRIGHT_SKIP_WEB_SERVER=1 \
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3102 \
pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts \
  -g "graph page loads current data/asip.db through browser and API|resolver page sends configurable concept normalization rules" \
  --reporter=line
```

## Adding An Inline UI Profile

Use the Resolver Profiles page when a user needs to try a rule without committing YAML.

1. Open `/resolver-profiles`.
2. Set `Profile id`, `Wrapper symbol`, `Language strategy`, and `Config path`.
3. Enable `Enable concept normalization`.
4. Fill `Concept rule id`, `Concept match regex`, and `Concept canonical name`.
5. Save the resolver profile.

The Web API sends this shape:

```json
{
  "id": "inline-concepts",
  "language": "cpp",
  "wrappers": ["CUSTOM_WRITE"],
  "strategy": "macro",
  "path": "inline:inline-concepts",
  "functionNormalization": {
    "enabled": true,
    "rules": [
      {
        "id": "inline-ip-versioned-functions",
        "enabled": true,
        "match": "^(?P<ip_block>gfxhub)_rev(?P<ip_version>\\d+)_(?P<operation>.+)$",
        "canonical": "inline_{operation}"
      }
    ]
  }
}
```

Inline UI profiles currently cover function concept normalization. Use committed YAML for register normalization and access relation mapping.

## Agent Checklist

- Start with `git status -sb`; do not overwrite user edits.
- Search existing profiles and tests before editing.
- Prefer config under `configs/resolvers/*.yaml` or an inline resolver profile over code conditionals.
- Add a regression that proves the config controls the graph behavior.
- Verify concept view and implementation view separately when changing function normalization.
- In browser QA, click the canvas node and verify `Concept Generated From`.
- If multiple Next dev servers are running for this repo, stop extras and clear `apps/web/.next`; shared dev cache can produce false 404s.

## Common Mistakes

- Treating a node label as proof that concept normalization is correct.
- Merging across IP blocks without preserving `ip` or `ip_version` provenance.
- Using a broad regex that collapses unrelated functions.
- Changing parser/storage code for a naming convention that belongs in resolver config.
- Updating docs or QA artifacts without a fresh command proving current behavior.
