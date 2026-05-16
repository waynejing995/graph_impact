# G12 ASIC And IP Metadata Filtering

Status: Partial; core/API/UI filtering exists, dedicated real AMD filter acceptance and inference-limit docs remain blocking

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
- The clean provider AQ01-AQ09 runner artifact covers the broader acceptance matrix, but it is not a dedicated ASIC/IP filter proof.

## Remaining Gap

Dedicated final acceptance still needs to run representative real AMD queries with and without filters, and visual QA must confirm the new filter controls do not break the 2K layout.

Current metadata inference is heuristic and not yet validated against AMD corpus examples.

## Acceptance Criteria

- Query/API can filter or scope results by `ip_block` and `asic_or_generation`.
- Filtered results are visibly different from unfiltered results when the fixture contains multiple IP/ASIC hints.
- UI exposes the selected ASIC/IP scope or clearly reports that global scope is used.
- Final QA includes at least one ASIC/IP-filtered query.
- Metadata inference limits are documented if path/symbol heuristics are the MVP implementation.

## Required Tests

- Core test: fixture with two ASIC/IP hints returns only scoped evidence when filter parameters are provided. Added.
- API test: query endpoint accepts and applies ASIC/IP filters or returns a documented unsupported response. Added.
- E2E test: UI can run a scoped query and displays the active scope. Added.
- Design review maps this gap to the full spec MVP `ASIC filtering` requirement.

## Not Closed Until

ASIC/IP metadata changes retrieval behavior in dedicated final filter evidence, and metadata inference limits are documented.
