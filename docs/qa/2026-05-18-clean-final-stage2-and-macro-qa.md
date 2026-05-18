# 2026-05-18 Clean Final Stage 2 And Macro QA

## Scope

This QA records the final clean AMD graph artifact after the user review on
macro nodes, vtable/callback backbone, real Stage 2 semantic edges, and doc
node extraction.

Final clean DB:

```text
/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db
```

Source roots:

```text
MxGPU: /tmp/asip-mxgpu
Linux amdgpu: /tmp/asip-linux-amdgpu, relative root drivers/gpu/drm/amd/amdgpu
AMD docs/PDF fixture: docs/fixtures/amd-amdgpu-docs
```

Provider settings:

```text
edge: ollama / gemma4:e4b / http://localhost:11434/api/chat
embedding: ollama / nomic-embed-text:latest / http://localhost:11434/api/embeddings
edge timeout_seconds: 900
edge num_ctx: 2048
edge num_predict: 1024
```

## RED

The first clean-current semantic batch run failed because local Ollama returned
JSON that started correctly but was truncated inside an `evidence` string:

```text
semantic_edges_batch job 4
status=failed
model=gemma4:e4b
message=Ollama returned no parseable JSON content
preview included src="tmp" and a full REG_SET_FIELD source line
```

The failure showed two product risks:

- batch prompts did not constrain evidence size tightly enough for local
  generation;
- local variable endpoints such as `tmp` could be proposed by the LLM and then
  filtered rather than discouraged at the source.

A vtable/callback subagent audit also found that the deterministic text span
parser could promote all-caps C macros such as `IP_VERSION` into function nodes.
That violates the graph contract: macros and resolver wrappers are provenance,
not graph entities.

## GREEN

Prompt hardening tests:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_semantic_batch_prompt_constrains_llm_output_size_and_endpoints \
  packages.core.tests.test_workbench_live.WorkbenchLiveTests.test_doc_node_prompt_constrains_boxmatrix_evidence_size -v

Ran 2 tests
OK
```

Macro-node regression tests:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src:packages/core/tests:. python3 -m unittest \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_text_span_parser_does_not_promote_all_caps_macros_to_functions \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_stage1_does_not_link_all_caps_macros_as_call_nodes \
  packages.core.tests.test_code_graph.DeterministicCodeGraphTests.test_text_span_parser_does_not_promote_control_keywords_to_functions -v

Ran 3 tests
OK
```

Fresh final deterministic rebuild:

```text
time PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src python3 -m asip.cli graph-rebuild \
  --db /tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db

files=1225
edges=41880
job_id=3
elapsed=2:09.51
```

Fresh final semantic-edge batch:

```text
generate_semantic_edges_batch(
  /tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db,
  limit=2,
  batch_size=1,
  provider=ollama/gemma4:e4b
)

candidate_count=2
edge_count=14
job_id=4
elapsed=1:26.58
```

Fresh final doc-node batch:

```text
generate_doc_nodes_batch(
  /tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db,
  limit=2,
  batch_size=1,
  provider=ollama/gemma4:e4b
)

candidate_count=2
box_count=6
edge_count=11
job_id=5
elapsed=2:07.81
```

Ollama resource observation during the real Stage 2 calls:

```text
ollama runner RSS: about 9.6 GB
memory share: about 38 percent of 24 GB
CPU: about 5 to 10 percent during generation
```

This indicates the slow path was local model generation latency, not a Python
timeout or fake/static data path.

## Final DB Counts

```text
documents=124
chunks=21884
evidence=860516
edges=41893
embeddings=32
jobs=5
corpora=3
```

Edge stage/source counts:

```text
deterministic / clang_text_spans: 34987
deterministic / clang_callback: 6084
deterministic / text_fallback: 775
semantic / ollama: 25
evidence / query_expected_terms: 22
```

Semantic provenance:

```text
mode=batch, model=gemma4:e4b, extractor=semantic_edges: 14
mode=doc_nodes_batch, model=gemma4:e4b, extractor=doc_nodes: 11
```

All final DB jobs are successful:

```text
1 index indexed Indexed 124 documents
2 embedding_backfill embedded Embedded 32 chunks
3 graph_rebuild succeeded Rebuilt 41880 deterministic graph edges from 1225 files
4 semantic_edges_batch succeeded Generated 14 semantic edges from 2 candidates
5 doc_nodes_batch succeeded Generated 6 doc boxes from 2 candidates
```

## Macro And Wrapper Endpoint Check

Raw edge endpoint counts are zero for rejected macro/wrapper/receiver names:

```text
IP_VERSION=0
WREG32=0
RREG32=0
REG_SET_FIELD=0
SOC15_REG_OFFSET=0
funcs=0
ops=0
hw_init=0
```

Product graph check:

```text
global_graph(limit=20000)
nodes=15154
edges=20000
node kinds: function=13662, register=1485, doc_box=6, doc_section=1
edge stages: deterministic=19989, semantic=11
relations: calls=16022, writes=1746, reads=1053, sets_field=705, maps_base=463, contains=6, relates_to=5
IP_VERSION/WREG32/REG_SET_FIELD/SOC15_REG_OFFSET/funcs/ops/hw_init visible nodes: false
```

## Acceptance

Command:

```text
time PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=packages/core/src python3 -m asip.cli acceptance \
  --db /tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db \
  --full \
  --surface CLI \
  --surface API \
  --surface Web \
  --surface MCP \
  --output-json docs/qa/2026-05-18-acceptance-clean-amd-gemma4-final-current.json \
  --output-md docs/qa/2026-05-18-acceptance-clean-amd-gemma4-final-current.md
```

Result:

```text
database_health: pass
summary: 9 total, 9 passed, 0 partial, 0 failed
surfaces_checked: CLI, API, Web, MCP
provider embedding: ollama/nomic-embed-text:latest, embedding_count=32, fallback_count=0
provider semantic_edge: ollama/gemma4:e4b, edge_count=1
elapsed=24.965s
```

Artifacts:

```text
docs/qa/2026-05-18-acceptance-clean-amd-gemma4-final-current.json
docs/qa/2026-05-18-acceptance-clean-amd-gemma4-final-current.md
```

## Default Web Graph QA

After automated tests, the clean-final DB was copied to the default workbench
path:

```text
data/asip.db
backup of prior dirty dev DB: /tmp/asip-dirty-dev-before-final-default-2026-05-18.db
```

Default `3100` API smoke:

```text
GET http://127.0.0.1:3100/api/workbench/graph?limit=20
HTTP 200 in 4.539169s
first returned node kind: doc_box
```

In-app browser QA at `http://127.0.0.1:3100/graph`:

```text
Workbench status: Provider unverified, Edge Ollama / gemma4:e4b, Index ready
graph edge budget: 3000 / 20000
layers: deterministic 2989, semantic 11
visible nodes: 1000 / 2883
visible edges: 3000 / 3000
rendered canvas edges: 1132
node kinds: doc_box=6, doc_section=1, function=836, register=157
canvas ready: true
errors: none
```

Browser artifacts:

```text
docs/qa/browser/graph-clean-final-default-3100-2k.png
docs/qa/browser/graph-clean-final-default-3100-snapshot.json
```
