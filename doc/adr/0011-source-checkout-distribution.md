---
status: accepted
date: 2026-09-04
---

# ADR 0011: Source-Checkout Distribution

## Context

CogGuard is a competition-oriented prototype whose runnable product is the
`system/` source checkout. The backend package metadata supports local
development and tooling, but a standalone backend wheel would hide the
frontend, vendored runtimes, migration files, and source-level release checks
that are part of the product contract.

## Decision

Source-checkout deployment is canonical for release-0.2 and the current LAN
prototype. Release validation runs from the checked-out repository with the
declared backend and frontend environments. CogGuard does not publish or
accept a standalone backend wheel as a release deployment artifact.
There is no standalone backend wheel release.

The backend packaging metadata may remain for local dependency resolution and
developer tooling. Its presence does not change the release distribution
decision, and it must not be used to infer that `system/backend` is a complete
standalone product.

## Consequences

- Release evidence includes source paths, migrations, frontend build output,
  vendored runtime attribution, and authenticated integration behavior.
- Windows and Ubuntu validation exercise the same source checkout contract.
- Packaging changes must not silently introduce a wheel-only deployment path.
- Future distribution changes require a new ADR and an explicit migration plan.

## Rejected Alternatives

- Treat a backend wheel as the release artifact | Rejected because it omits
  source-controlled frontend, migrations, and vendored runtime context.
- Copy runtime code into a second distribution tree | Rejected because it
  creates a competing implementation and weakens locality at the source seam.
