# MVP Acceptance Query Matrix

Date: 2026-05-16
Status: Blocking support matrix for G10

This matrix expands the nine MVP-1 acceptance queries from `docs/specs/2026-05-16-asip-mvp1-design.md` and `docs/brainstorming/2026-05-16-asip-decisions.md`.

It is not a substitute for G01-G17. It is the query-level checklist that prevents partial query smoke tests from being mistaken for full acceptance.

Current runner status: `packages/core/src/asip/acceptance.py` and `asip.cli acceptance` can execute this matrix against a supplied SQLite database and emit JSON/Markdown artifacts. `asip.cli acceptance --query-id ... --full` can also execute selected AQ IDs and print the full runner payload for product surfaces. First clean CLI run artifacts are `docs/qa/2026-05-17-acceptance-clean-qwen35.json` and `docs/qa/2026-05-17-acceptance-clean-qwen35.md`: 9 total, 0 pass, 8 partial, 1 fail. AQ09 fails there even when lexical doc rows exist because provider settings are required. A focused AQ09 provider smoke artifact, `docs/qa/2026-05-17-aq09-provider-smoke-ollama.json`, proves CLI-level embedding provenance and semantic-edge provider checks against local Ollama. Web BFF now also verifies AQ09 provider provenance from an isolated SQLite DB with independently configured edge and embedding settings, Settings UI wiring can trigger AQ09 through the same Web BFF acceptance endpoint, and Settings can run AQ09 against a user-supplied DB path through the real BFF/core runner. Web BFF, FastAPI, MCP, and the `/acceptance` page can list/display acceptance artifacts, including `partial` counts. Web BFF `POST /api/workbench/acceptance/run`, FastAPI `POST /acceptance/run`, and MCP `run_acceptance()` can execute a selected AQ through the same runner.

Historical clean provider rerun: `docs/qa/2026-05-17-acceptance-clean-qwen35-provider-rerun.json` and `.md` were generated from `/tmp/asip-acceptance-clean-2026-05-17.db` after saving Ollama provider settings, running real qwen3.5 semantic-edge generation, and writing provider-sourced `nomic-embed-text` embedding provenance. It used the older acceptance gate and reported 9 total, 9 pass, 0 partial, 0 failed across CLI/API/Web/MCP surface labels. Provider checks passed with `ollama/nomic-embed-text:latest` embeddings (`embedding_count=9058`, `fallback_count=382`) and `ollama/qwen3.5:4b` semantic-edge smoke (`edge_count=1`). Treat this as provider/provenance evidence only, not current acceptance closure.

Current source-gated rerun: `docs/qa/2026-05-17-acceptance-clean-qwen35-source-gated-current.json` and `.md` were generated with the current acceptance gate against the same DB. Summary: 9 total, 0 pass, 0 partial, 9 failed. The DB health gate fails because `mxgpu` is still `indexing` and index job 3 failed after the interrupted provider reindex; AQ05 additionally fails with `required source types missing: pdf`.

Fixture source-diverse run: `docs/qa/2026-05-17-acceptance-multisource-fixture.json` and `.md` were generated from `/tmp/asip-multisource-clean-2026-05-17.db`. Summary: 2 total, 2 pass, 0 partial, 0 failed. AQ05 returns 24 rows with `code`, `doc`, `pdf`, and `register`; AQ06 returns 16 rows with `code` and `register`; DB health passes. Treat this as source-diversity fixture evidence only, not real AMD final acceptance.

Clean-final candidate run: `docs/qa/2026-05-18-acceptance-clean-amd-gemma4-final-current.json` and `.md` were generated from `/tmp/asip-clean-amd-gemma4-final-current-2026-05-18.db`. Summary: 9 total, 9 pass, 0 partial, 0 failed. DB health passes. Source counts are recorded in G01/G10. AQ05 passes with `code`, `doc`, `pdf`, and `register`; AQ06 passes with `code`, `doc`, and `register`; AQ09 provider checks pass with `ollama/nomic-embed-text:latest` embeddings and `ollama/gemma4:e4b` semantic-edge smoke. The same clean-final QA records `41,880` deterministic graph edges, `25` real `gemma4:e4b` semantic edges, `6` doc boxes, and zero macro/wrapper raw endpoints for `IP_VERSION/WREG32/RREG32/REG_SET_FIELD/SOC15_REG_OFFSET/funcs/ops/hw_init`. Later default `data/asip.db` G03 graph rebuilds record `41,923` deterministic graph-rebuild edges with fresh 2K browser graph QA in `docs/qa/2026-05-18-g03-typed-callback-rebuild-qa.md`, then `41,929` deterministic graph-rebuild edges after the AST JSON callback-initializer seam in `docs/qa/2026-05-18-g03-ast-json-callback-initializer-qa.md`. This remains candidate/historical clean-final evidence, not the current expanded default-DB completion gate.

Current expanded default-DB non-Web run: `docs/qa/2026-05-20-acceptance-data-asip-expanded.json` and `.md` were generated from `data/asip.db` after the expanded `linux-amdgpu` re-index. Summary: 9 total, 0 pass, 8 partial, 1 failed, with `gate_status: blocked`. AQ01-AQ08 are partial because that run checked CLI/API/MCP but not a live Web surface. AQ09 fails because embedding coverage is partial, `embedding_live` fails with `Operation not permitted`, semantic-edge provenance is `partial/stale` (`14` stale semantic edges from job `4`, latest index job `10`), and live semantic-edge generation fails with `Operation not permitted`.

Supplemental Web-included expanded run:
`docs/qa/2026-05-20-acceptance-data-asip-expanded-web-blocked.json` and `.md`
explicitly requested CLI/API/Web/MCP for AQ01-AQ09. Summary: 9 total, 0 pass,
0 partial, 9 failed, with `gate_status: blocked`. CLI/API/MCP probes returned
rows and product schema `pass`; every Web probe was `not_configured` because
`ASIP_WEB_BASE_URL` is absent and the local browser/server gate is blocked.

Known limitation in the historical clean provider rerun: every AQ01-AQ09 row reported `source_types: ["code"]`. AQ05 asked for documentation-to-driver evidence but still returned code-only rows. That artifact is superseded by the current clean AMD run above.

| ID | Acceptance query | Gap IDs | Required surfaces | Current status | Final artifact required |
| --- | --- | --- | --- | --- | --- |
| AQ01 | Who reads or writes `regGCVM_L2_CNTL`? | G01, G02, G03, G10 | CLI, API, Web, MCP | Current expanded DB: fail in Web-included run; CLI/API/MCP pass, Web `not_configured`. Clean-final candidate: pass. | Rerun with live Web surface/browser evidence. |
| AQ02 | Which fields of `GCVM_L2_CNTL` are set in MxGPU `gfx_v11_0.c`? | G01, G02, G05, G10 | CLI, API, Web | Current expanded DB: fail in Web-included run; CLI/API/MCP pass, Web `not_configured`. Clean-final candidate: pass. | Rerun with live Web surface/browser evidence. |
| AQ03 | Where is `IH_RB_CNTL` configured, and which fields are modified? | G01, G02, G03, G10 | CLI, API, Web | Current expanded DB: fail in Web-included run; CLI/API/MCP pass, Web `not_configured`. Clean-final candidate: pass. | Rerun with live Web surface/browser evidence. |
| AQ04 | Which code paths reference `SDMA0_QUEUE0_RB_CNTL` or `SDMA1_QUEUE0_RB_CNTL`? | G01, G02, G03, G10 | CLI, API, Web | Current expanded DB: fail in Web-included run; CLI/API/MCP pass, Web `not_configured`. Clean-final candidate: pass. | Rerun with live Web surface/browser evidence. |
| AQ05 | Show evidence connecting amdgpu documentation to the amdgpu driver source tree. | G01, G02, G08, G10 | CLI, API, Web | Current expanded DB: fail in Web-included run; source diversity restored across `code/doc/pdf/register`, but Web is `not_configured`. Clean-final candidate: pass. | Rerun with live Web surface/browser evidence. |
| AQ06 | Given `WREG32_SOC15(GC, 0, regGCVM_L2_CNTL, tmp)`, explain the resolved register entity and macro expansion chain. | G02, G05, G07, G10 | CLI, API, Web, MCP | Current expanded DB: fail in Web-included run; CLI/API/MCP pass, Web `not_configured`. Clean-final candidate: pass. | Rerun with live Web surface/browser evidence. |
| AQ07 | Change resolver profile to add or rename one C/C++ register access wrapper, then verify the same resolver engine resolves it without code changes. | G05, G07, G10, G14 | CLI, API, Web | Current expanded DB: fail in Web-included run; CLI/API/MCP pass, Web `not_configured`. Clean-final candidate: pass. | Rerun with live Web surface/browser evidence. |
| AQ08 | Add a toy Python resolver profile extracting a configured function-call or string-symbol reference, proving profiles are not macro-only. | G05, G07, G10, G13 | CLI, API, Web | Current expanded DB: fail in Web-included run; CLI/API/MCP pass, Web `not_configured`. Clean-final candidate: pass. | Rerun with live Web surface/browser evidence. |
| AQ09 | Run embedding and optional semantic-edge extraction through a configured Ollama provider, then switch to an OpenAI-compatible provider without changing retrieval or resolver code. | G06, G09, G10, G17 | CLI, API, MCP; Web is proved by Settings/browser e2e | Current expanded DB: fail in Web-included run; Web `not_configured`, embedding coverage partial, `embedding_live` fail, semantic-edge provenance `partial/stale`, and live semantic-edge smoke fail. Clean-final candidate: pass for local Ollama `gemma4:e4b`/`nomic-embed-text:latest` provider checks. | Provider/live-semantic checks and browser/settings proof must pass on current DB or be explicitly accepted as residuals. |

## Matrix Closure Rules

- Every acceptance query must be run against a clean, explicitly named SQLite database.
- Each result must record input corpus roots, provider settings, command/API route, elapsed time, row count, evidence ids, source paths, graph node/edge counts, and UI route checked.
- Each result must record `database_health`, corpus/job health, source-type counts, PDF page metadata when PDF is required, provider checks/provenance when AQ09 is involved, and graph runtime.
- Each result must state which surfaces passed: CLI, API, Web, and MCP. Missing surfaces are failures unless explicitly deferred in G07/G13.
- Empty or failed results are acceptable only if documented as failures, not as passes.
- Historical QA artifacts can support comparison, but final acceptance must use current code and current configured corpora.
