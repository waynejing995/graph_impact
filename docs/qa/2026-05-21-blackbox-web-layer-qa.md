# Blackbox Web Layer QA

- Status: pass
- DB: `/Volumes/data/User/wayne/Code/graph_impact/data/asip.db`
- URL: `http://127.0.0.1:3180/graph?dbPath=%2FVolumes%2Fdata%2FUser%2Fwayne%2FCode%2Fgraph_impact%2Fdata%2Fasip.db`
- Browser: Codex in-app browser
- Latest blackbox job: 60
- Provider/model: `ollama/gemma4:e4b`

## Evidence

The graph page loaded the current real DB through `/api/workbench/graph?limit=3000&dbPath=...&functionView=concept`.

Observed layer badge:

```text
layers blackbox_profile: 3 blackbox_relationship: 5 concept_merge: 1099 deterministic_ast: 2982 semantic_doc_node: 4 semantic_edge: 9
```

Observed provenance badge included:

```text
ollama/gemma4:e4b job 60
```

This proves the default Web graph budget now carries the blackbox profile layer and blackbox relationship layer, rather than hiding the latest blackbox job behind deterministic AST edge budget selection.
