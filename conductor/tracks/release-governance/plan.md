# Release Governance Context Plan

## Ordered Tasks

- [x] Add the release-governance track index, specification, plan, and metadata.
- [x] Pin release-0.2, branch `cleanup/final-architecture`, and PR #1.
- [x] Record source-checkout deployment as canonical and exclude future roadmap
  features from current-product-contract completeness.
- [x] Record Windows and Ubuntu CI plus required GitHub checks as binding
  acceptance gates.
- [x] Reconcile glossary, context vocabulary, and ADR statuses.
- [x] Publish the five-candidate architecture review in the Windows temp
  directory and record its absolute path in the task report.
- [x] Execute the complete release gate set on the approved branch and accept
  the release evidence.

## Verification Evidence

- Backend: `689 passed, 20 skipped`; research package tests are collected by
  the standard backend command.
- Frontend: Node governance/race tests `21 passed`; Vitest component tests `2
  passed`; production build and static preview smoke passed for 3 routes and
  33 assets.
- Migration: one head `c1d4e8f2a706`; real round-trip is CI-gated and local
  execution is explicitly skipped when disposable MySQL is unavailable.
- Product contract smoke, service readiness, release surface, dependency
  export, and CI workflow contract tests passed.
- [x] Complete final branch review with no Critical or Important findings.
- [x] Push the branch and update PR #1; do not auto-merge.

## Post-Release Track

The Event Review Case/V1 adapter split, legacy Analysis Engine seam retirement,
Propagation Monitoring persistence seam, Crawl Execution deep module, and
typed Student/Teacher outcome remain planned post-release work. No code
deepening is part of this release-governance context task.
