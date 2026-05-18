# G12 ASIC And IP Metadata Filtering

Status: Current real AMD filter pass verified; heuristic inference boundary documented

## Requirement

The full ASIP technical spec lists ASIC filtering as an MVP required feature. MVP evidence schema also includes `ip_block` and `asic_or_generation`, so metadata must not only be stored; it must be usable for filtering and acceptance.

## Current Evidence

- `packages/core/src/asip/storage.py` stores `ip_block` and `asic_or_generation` on evidence rows.
- `packages/core/src/asip/workbench.py` infers IP and ASIC/generation hints from symbols and paths.
- `packages/core/tests/test_workbench_query_schema.py` asserts those fields exist in query rows.
- `query_evidence()` accepts `ip_block` and `asic_or_generation` filters and applies them before scoring.
- `apps/web/app/api/workbench/query/route.ts` passes `ipBlock`/`ip_block` and `asic`/`asic_or_generation` query params to the core CLI.
- The Web query composer exposes `IP block filter` and `ASIC or generation filter` inputs and sends them with free-form queries.
- Core and Playwright tests verify that filters change query results instead of acting as static chips.
- 2026-05-18 FastAPI and MCP parity fix: `/query` now accepts `ip_block` plus `asic` or `asic_or_generation`, and MCP `search_evidence()` accepts `ip_block`, `asic_or_generation`, and `asic`. Targeted RED/GREEN tests prove both surfaces filter identical same-symbol evidence rows down to the scoped `GC/gc_11_0` result.
- 2026-05-18 real AMD filter QA proves `CP_INT_CNTL_RING0` over the clean-final default DB changes from 20 mixed rows unfiltered to 2 `CP/gfx_v10_0` code rows with `ip_block=CP`, and to 0 rows with `ip_block=SDMA`. Browser QA at 2K shows the same filtered query with `matches: 2`, two code rows from `gfx_v10_0.c`, and graph/inspector updates. Evidence: `docs/qa/2026-05-18-g12-filter-surface-qa.md` and `docs/qa/browser/g12-filter-cp-clean-final-3100-2k.png`.
- The clean provider AQ01-AQ09 runner artifact covers the broader acceptance matrix, but it is not a dedicated ASIC/IP filter proof.

## Remaining Gap

Dedicated real AMD filter QA is now recorded. Remaining boundary: metadata inference is heuristic, not a full AMD IP/ASIC taxonomy parser.

Current metadata inference reads simple symbol/path hints. `_ip_block_for_symbol()` scans the symbol plus path for `GC`, `CP`, `SDMA`, `GMC`, `BIF`, `RLC`, or `GDS`; `_asic_for_path()` extracts path fragments such as `gfx_v10_0`, `gc_11_0`, `nbio_v7_9`, or `sdma_v5_0`. This is enough for scoped retrieval and QA, but it can miss aliases, marketing names, firmware-only names, or ASIC context that only exists outside the file path/symbol.

## Acceptance Criteria

- Query/API can filter or scope results by `ip_block` and `asic_or_generation`.
- Filtered results are visibly different from unfiltered results when the fixture contains multiple IP/ASIC hints.
- UI exposes the selected ASIC/IP scope or clearly reports that global scope is used.
- Final QA includes at least one ASIC/IP-filtered query.
- Metadata inference limits are documented if path/symbol heuristics are the MVP implementation.

## Required Tests

- Core test: fixture with two ASIC/IP hints returns only scoped evidence when filter parameters are provided. Added.
- API test: FastAPI query endpoint accepts and applies ASIC/IP filters. Added.
- MCP test: `search_evidence()` accepts and applies ASIC/IP filters. Added.
- E2E test: UI can run a scoped query and displays the active scope. Added.
- Design review maps this gap to the full spec MVP `ASIC filtering` requirement.

## Not Closed Until

ASIC/IP metadata changes retrieval behavior in dedicated final filter evidence, and metadata inference limits are documented.
