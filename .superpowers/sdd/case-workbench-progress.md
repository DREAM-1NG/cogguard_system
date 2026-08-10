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
- Never commit the Twitter benchmark CSV or a full Markdown conversion of it.
- No push is authorized for Task 01.

## Task Ledger

| Task | Status | Evidence |
| --- | --- | --- |
| 01A: design and contract resolution | complete | Design specifies CaseRecord, lifecycle/blocker separation, authority/claim policy, semantic isolation, report, security, audit, and old-contract compatibility. |
| 01B: executable TDD plan | complete | Sequential fresh-implementer/reviewer tasks name exact files, failing tests, commands, rollback boundaries, and final gate. |
| 01C: research/source provenance | complete | Bounded MIT source originals/MarkItDown conversions; comparison/governance/report manifests; source exclusions are transparent. |
| 01D: task report/branch hygiene | complete pending independent review | Content validation and the staged-diff guard passed; the controller records the Lore commit after this ledger update. |

## Verification And Review Placeholders

- Documentation validation: required contract text and no-placeholder scan passed.
- JSON parse validation: source metadata, Twitter manifest, and both conversion metadata files passed.
- SHA-256 validation: two retained original-source hashes and both conversion metadata source hashes passed.
- Markdown/link validation: eight Task 01 authored Markdown files passed; generated conversion image references are intentionally upstream-only and excluded from local-link checks.
- Git diff/restricted-file validation: `git diff --cached --check` passed; protected dirty paths are absent from the staged set.
- Fresh task reviewer: pending controller assignment.
- Branch-wide reviewer: not applicable until implementation tasks begin.

## Handoff

The next implementation owner starts at Task 1 in the plan. They must keep the legacy default stage chain unchanged and use a new Task ledger/reviewer gate per plan task; this Task 01 ledger is not a substitute for implementation reviews.
