# ADR 0003: Semantic Package Governance

## Status

Partially superseded by ADR 0007 and ADR 0010. The semantic package and
compatibility-alias rules remain current.

## Context

CogGuard now exposes one product entry point, `analysis`, while the three key
technology areas have different method semantics:

- Coordination Discover is `Coordination Discover` plus `Coordination Detect`.
- Propagation Analysis is `Propagation Analysis`.
- Review is the `Review` domain, with `Student` and `Teacher` as public roles.
- The acquisition layer remains `Crawler`.

Earlier package names mixed stage labels (`coordination_discover`, `propagation_analysis`, `review`), legacy domains
(`risk`, `coordination`), and upstream reference names. That made it too easy
for product code, research code, vendored runtimes, and provenance directories
to blur together.

## Decision

The canonical package layout is:

- `system/backend/app/core/review`
- `system/backend/app/core/coordination_baseline`
- `system/research/coordination_discover`
- `system/research/coordination_detect`
- `system/research/propagation_analysis`
- `system/research/review_teacher`
- `system/runtimes/review_student`

Legacy import paths are retained for one release window as thin compatibility
aliases only:

- `system/backend/app/core/risk`
- `system/backend/app/core/coordination`
- `system/research/coordination_discover`
- `system/research/propagation_analysis`
- `system/research/review_teacher`
- `system/runtimes/review_student`

Product code must use canonical package names. Research and runtime seams must
be reached through explicit adapters, not external repository roots or
`sys.path.insert`.

This ADR intentionally does not rename existing model-version identifiers such
as `propagation_analysis-hindcast-protocol-v1`, `review-student-runtime-v2`, or
`review-teacher-dag-v2`; those identifiers are artifact lineage, not package
structure.

This ADR also freezes frontend display pages for this governance pass. UI copy,
routes, and page structure can be migrated in a later product pass.

## Consequences

- Code review should reject new product imports from legacy packages unless the
  file itself is a compatibility wrapper.
- Public package boundaries must publish explicit `__all__` values.
- Documentation should describe current execution paths with semantic package
  names and mention legacy paths only as compatibility aliases.
- Governance tests must keep product backend code independent from
  `MediaCrawler-main`, `NewsCrawler-main`, and `CooRTweet-master`.

## Rejected Alternatives

- Rename every stage id from `coordination_discover/propagation_analysis/student/teacher` in one pass. Rejected
  because run protocols and persisted records still use those stable stage ids.
- Rename artifact model versions to semantic names. Rejected because it would
  break lineage continuity without improving runtime boundaries.
- Delete legacy packages immediately. Rejected because a one-release alias
  window keeps the migration reversible and testable.
- Update frontend display pages in this pass. Rejected because the current
  scope explicitly freezes frontend presentation.
