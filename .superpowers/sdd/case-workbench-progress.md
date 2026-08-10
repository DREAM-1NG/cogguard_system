# Case Workbench SDD Progress

Plan: `docs/superpowers/plans/2026-08-10-case-workbench.md`

Spec: `docs/superpowers/specs/2026-08-10-case-workbench-design.md`

Workspace: `G:\CISCN\CogGuard\.worktrees\refactor-system`

Baseline/rollback: `425a8f2 Preserve the current refactor system before case workflow work`

## Scope Guard

- Task 01 is documentation/research foundation only. It makes no production-code, migration, API, frontend, model-download, or collection change.
- Preserve and do not stage or edit these user-owned dirty files:
  - `system/doc/research/propagation_paper_deep_reads/README.md`
  - `system/doc/research/propagation_paper_deep_reads/propagation_sota_stable_matrix_report_20260810.md`
  - `system/doc/research/propagation_paper_deep_reads/propagation_fair_learned_matrix_20260810.md`
- Never commit the Twitter benchmark CSV or a full Markdown conversion of it.
- No push is authorized for Task 01.

## Task Ledger

| Task | Status | Evidence |
| --- | --- | --- |
| 01A: design and contract resolution | amended; fresh re-review required | Separates the three organizational AuthorityTier values from AuthorityReviewStatus and ClaimRole; adds immutable CaseVerdictVersion proposal/approval/supersession/pointer/audit/closure behavior; records the dynamic migration-head boundary; defines CaseClosureReview plus its canonical hash and the one-transaction public close path as the only closure-report creator. |
| 01B: executable TDD plan | amended; fresh re-review required | Tasks now cover taxonomy independence, execution-time one-head Alembic preflight with `<generated_revision>`, CaseVerdictVersion persistence/backfill, service/API flows, ordinary-versus-closure report ownership, public close response identity/version, close rollback injection, UI close readiness, report provenance, and no legacy dual writes. |
| 01C: research/source provenance | amended; fresh re-review required | Removes uncaptured vendor capability assertions, marks five vendor rows as non-evidentiary hypotheses, preserves source statuses, and converts retained-source metadata paths to repository-relative values. |
| 01D: task report/branch hygiene | amended; ready for fresh re-review | The review identified 5 Important and 1 Minor findings. The closure-report sequencing correction records a new CaseClosureReview/closure-report transaction, uses only the public close path in acceptance, and passed terminology, JSON, retained-source hash, one-head Alembic, and scoped whitespace checks; protected dirty paths remain excluded. |

## Verification And Review Placeholders

- Independent review: `case-workbench-task-01-review.md` found 5 Important and 1 Minor issue in `425a8f2..cc4dde6`; implementation must not start until a fresh review accepts the correction.
- Amendment evidence: authority class/review state/claim role are independent; Task 2 plans a dynamic one-head migration; CaseVerdictVersion is immutable and case-owned; vendor rows are unverified hypotheses; conversion paths are repository-relative; the ignored progress index is included.
- Amendment validation: commands/results will be appended to `case-workbench-task-01-report.md` before the Lore fix commit.
- Second re-review closure-fix evidence: ordinary `/reports` rejects server-owned closure fields; `close_case`/`POST /close` alone creates and returns one closure report with immutable CaseClosureReview provenance; note/render/hash/audit failures roll back all effects; Task 11 has no retired combined-close helper. Exact commands/results are appended to `case-workbench-task-01-report.md` and the agent handoff is `case-workbench-task-01-fix2-agent-report.md`.
- Fresh task reviewer: required after this correction commit.
- Branch-wide reviewer: not applicable until implementation tasks begin.

## Handoff

Do not begin Task 1 until a fresh documentation reviewer accepts this amendment. The next implementation owner must keep the legacy default stage chain unchanged, use the Task 2 execution-time Alembic one-head preflight rather than a fixed parent revision, use ordinary `/reports` only for ordinary frozen versions, and let `close_case`/`POST /close` own the full closure-review/report/lifecycle/audit transaction; this Task 01 ledger is not a substitute for implementation reviews.
