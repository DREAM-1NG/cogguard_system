# Release Governance Context

- [Specification](spec.md)
- [Implementation Plan](plan.md)
- [Metadata](metadata.json)

Current status: `complete / ready to merge`.

This track establishes the release-0.2 context for PR #1 on
`cleanup/final-architecture`. The current product contract is complete for
the capabilities already implemented in this checkout; future roadmap
features are explicitly excluded from that completeness claim.

## Release Context

- Source-checkout deployment is canonical; there is no standalone backend
  wheel release surface.
- Windows and Ubuntu CI are binding acceptance gates.
- Required GitHub checks are binding acceptance gates for the branch and PR.
- Real migration validation and a real authenticated integration workflow are
  release evidence, not optional follow-up work.

## Architecture Disposition

The architecture review report audits five candidates. The first, second, and
fourth are `Strong`; the third is `Worth exploring`; the fifth is `Speculative`.
All five code deepenings are deferred to a planned post-release track. This
release-governance track puts release gating first. PR #1 is open against
`release-0.2`; branch protection requires all seven CI checks before merge.
