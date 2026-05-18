# 2026-05-18 G04 Clean Corpus Flow QA

## Scope

This QA closes the G04 final-clean corpus-management slice:

- add a user corpus;
- index only that selected corpus;
- query a unique symbol from the newly indexed corpus;
- prove the query graph and inspector/source detail are driven by the new corpus;
- avoid dirtying the default clean-final `data/asip.db`.

## Clean Named DB API Flow

Web BFF test:

```text
pnpm --filter web exec playwright test tests/workbench-api.spec.ts -g "clean named DB" --reporter=list

1 passed
```

The test creates a fresh named DB:

```text
/tmp/asip-api-clean-corpus-*/clean-g04.db
```

Then it calls the real Web BFF routes:

```text
POST /api/workbench/corpora
POST /api/workbench/index
GET  /api/workbench/query?q=G04_CLEAN_FLOW_REGISTER&dbPath=<clean-g04.db>
```

Verified payload:

```text
indexed.status=indexed
indexed.jobStatus=succeeded
indexed.corpusIds=["g04-clean-docs"]
rows include:
  symbol=G04_CLEAN_FLOW_REGISTER
  corpus_id=g04-clean-docs
  source_type=doc
  path=note.md
graph nodes include:
  note.md#lines-1 kind=doc_section source.corpus_id=g04-clean-docs
  G04_CLEAN_FLOW_REGISTER kind=register source.corpus_id=g04-clean-docs
graph edges include:
  note.md#lines-1 documents G04_CLEAN_FLOW_REGISTER
  source=query_matched_section
```

## UI Flow

Web UI test:

```text
pnpm --filter web exec playwright test tests/workbench-smoke.spec.ts -g "corpus page adds indexes and queries" --reporter=list

1 passed
```

The test still uses the real Corpus page, Evidence Search page, Next BFF, and
core SQLite path. It rewrites only the `dbPath` parameter/body to an isolated
temporary DB so the default clean-final workbench database is not dirtied.

Verified UI behavior:

```text
Corpus page:
  add corpus ui-full-loop-*
  select only that corpus
  Run index
  action feedback: Index built for ui-full-loop-*
  row status: indexed

Evidence Search:
  query unique UI_FULL_LOOP_REGISTER_*
  results include docs/note.md
  page metrics include graph edges: 1
  graph data-testid=force-graph:
    data-node-count=3
    data-edge-count=1
    summary includes doc_section 1
    summary includes the unique symbol
  inspector:
    Resolved Evidence: UI_FULL_LOOP_REGISTER_*
    Source Location visible
    Source Preview visible
    source location body: doc function docs/note.md line 1
```

## Clean-Default Guard

After the UI test, the default DB was compared against the clean-final artifact:

```text
cmp -s data/asip.db /tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db
pre_cmp_exit=0
```

This confirms the G04 UI test now proves the user flow without mutating the
default clean-final evidence DB.

## Residual

This closes the local synchronous Corpus MVP flow. It does not add background
workers, streaming progress, cancellation, remote clone orchestration, or a UI
selector for arbitrary DB paths. The UI test uses an isolated DB through BFF
request rewriting only for test hygiene; the product UI continues to use the
default workbench DB.
