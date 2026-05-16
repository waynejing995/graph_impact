# G11 Completion Gate And Documentation Review

Status: Blocking

## Requirement

The active goal must not be marked complete until the implementation has been reviewed against the design docs and every blocking gap is closed or explicitly accepted by the user.

Commit and push happen only after verification.

## Current Evidence

- The active goal explicitly requires full implementation, E2E tests, design-doc review, visual QA, then commit/push.
- Prior progress docs contain mixed old and new status, so this `docs/gaps/` ledger is the current source of truth.
- The worktree currently contains many uncommitted implementation files plus generated caches.
- Final-candidate evidence package now exists at `docs/qa/2026-05-17-final-clean-evidence-package.md`, linking the clean AMD DB, AQ01-AQ09 9/9 artifact, six free queries, semantic-edge jobs, visual QA, automated verification, and architecture review.
- `git diff --check` passed after the current changes, and generated `apps/web/tsconfig.tsbuildinfo` plus the temporary root screenshot were removed from the worktree.

## Remaining Gap

Completion evidence is now separated in the final-candidate QA package, but the branch is not complete until the final git gate, commit, and push are done.

The final branch must avoid staging generated local artifacts such as `data/asip.db`, `apps/web/tsconfig.tsbuildinfo`, Python `__pycache__`, and transient browser screenshots outside `docs/qa`.

Completion must follow this order:

1. Reconcile final docs against `docs/gaps/README.md`, the gap register, the AQ matrix, and [Final Clean Evidence Package Gate](2026-05-17-final-clean-evidence-package.md).
2. Run the full automated core/API/MCP/Web/build/lint/diff verification suite. Done in `docs/qa/2026-05-17-final-clean-evidence-package.md`.
3. Run fresh browser visual QA after the final functional change, including light and dark themes. Done in `docs/qa/visual-qa-2026-05-17/visual-qa.md`.
4. Review `git status --short` and generated/local artifact hygiene.
5. Commit and push only after the previous steps are recorded in the final QA doc.

## Acceptance Criteria

- `docs/gaps/README.md` shows every gap as closed or user-accepted deferred.
- `docs/gaps/2026-05-17-gap-inventory-before-code.md` is updated or superseded with the final gap inventory.
- `docs/specs/2026-05-16-asip-workbench-gap-review.md` points to the current gap index and no longer implies stale completion.
- [Final Clean Evidence Package Gate](2026-05-17-final-clean-evidence-package.md) is complete or each missing field is explicitly user-accepted as out of scope.
- Final QA doc lists exact verification commands and results.
- Design review explicitly maps ASIP MVP-1 G1-G6 and all nine acceptance queries to implemented evidence.
- Worktree excludes cache/build artifacts from staging.
- Commit and push occur only after all verification passes.

## Required Tests And Checks

- `git status --short` reviewed before staging.
- Full automated test/build/lint/diff suite passes.
- Browser visual QA completed after the final build.
- `git diff --check` passes.
- Commit message references closed gap IDs.

## Not Closed Until

The user can inspect the docs and see exactly why the repo is complete, or exactly what remains.
