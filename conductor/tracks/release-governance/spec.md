# Release Governance Context Specification

## Goal

Establish an auditable release context for release-0.2 and PR #1 while
preserving the completed final-architecture track and the existing product
contracts.

## Current Product Contract

- The current product contract is complete for the capabilities implemented in
  this source checkout.
- Both V1 capability APIs and V2 case/governance APIs are current contracts.
- Only endpoints explicitly marked deprecated are legacy. Version labels alone
  do not make an endpoint legacy.
- Current-product-contract completeness excludes future roadmap features.
- This context task does not modify product behavior or public HTTP paths.

## Release And Distribution

- Branch: `cleanup/final-architecture`.
- Target: `release-0.2`.
- Pull request: `#1`.
- Source-checkout deployment is canonical for the prototype and release
  validation.
- The backend is not distributed as a standalone wheel. The packaging
  metadata remains useful for local tooling, but release acceptance validates
  the `system/` source checkout and its declared environments.

## Binding Acceptance Gates

Windows and Ubuntu CI are required because the prototype depends on
cross-platform runtime and integration behavior. Required GitHub checks are
binding acceptance gates and must pass before release integration. The gate
set includes:

1. Focused governance tests and the applicable backend test suite.
2. A real migration round-trip against the current migration chain.
3. A real authenticated integration workflow against the source checkout.
4. Frontend tests and production build checks where the release surface is
   affected.
5. `git diff --check` and release-surface checks for generated output leakage.

## Deferred Architecture Work

The accompanying architecture report audits these candidates:

- Event Review Case/V1 adapter split - `Strong`.
- legacy Analysis Engine seam retirement - `Strong`.
- Propagation Monitoring persistence seam - `Worth exploring`.
- Crawl Execution deep module - `Strong`.
- typed Student/Teacher outcome - `Speculative`.

These candidates are planned post-release deepenings. They do not expand the
current product contract or block this context task; release gating is the top
recommendation for PR #1.
