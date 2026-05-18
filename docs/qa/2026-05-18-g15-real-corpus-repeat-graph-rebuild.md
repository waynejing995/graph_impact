# G15 Real Corpus Repeat Graph Rebuild QA

Date: 2026-05-18

Status: Pass for repeat deterministic graph rebuild timing/counts on the live workbench AMD DB snapshot; full provider embedding coverage remains a boundary.

JSON artifact: `docs/qa/2026-05-18-g15-real-corpus-repeat-graph-rebuild.json`

## Command

Two temporary SQLite copies were created with `sqlite3.Connection.backup()` from the live workbench DB:

```text
python3 -m asip.cli graph-rebuild --db <tmp-copy> --corpus-id linux-amdgpu --corpus-id mxgpu
```

The source DB was not mutated.

## Preflight Corpora

Both temp DBs contained the same indexed corpora before rebuild:

```text
amd-amdgpu-docs  indexed  docs/fixtures/amd-amdgpu-docs
linux-amdgpu     indexed  /tmp/asip-linux-amdgpu
mxgpu            indexed  /tmp/asip-mxgpu
```

## Results

| Run | Exit | Elapsed | Files | Deterministic rebuild edges | Final edge rows | Jobs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0 | 131.639s | 1225 | 41923 | 41936 | 7 |
| 2 | 0 | 126.034s | 1225 | 41923 | 41936 | 7 |

Stable counts:

```text
corpora=3
documents=124
chunks=21884
evidence=860516
edges=41936
embeddings=32
jobs=7
```

Stable edge source counts:

```text
clang_callback=6127
clang_text_spans=34987
ollama=25
query_expected_terms=22
text_fallback=775
```

`clang_callback` includes conservative source-span/alias dispatch edges plus selective clang AST JSON receiver-type hints. This artifact checks rebuild stability and count repeatability; it does not claim full clangd/libclang callback/type-flow correctness.

Stable relation counts:

```text
calls=27706
contains_box=6
is_responsible_for=5
maps_base=2387
mentions=1
reads=3533
sets_field=1563
writes=6735
```

`deterministic_counts_match=true`.

## Failed Copy Attempt Preserved

The JSON keeps an earlier failed attempt using direct filesystem copy of the clean artifact. That attempt produced `ValueError: no registered corpora found` at CLI startup and is preserved as evidence that SQLite backup is the correct snapshot method for repeat benchmarking.

## Residuals

- This closes repeat deterministic graph rebuild timing/counts for the current live AMD workbench DB snapshot.
- It does not close full raw corpus re-index timing from deleted DB.
- It does not close full provider embedding coverage across all `21884` chunks.
