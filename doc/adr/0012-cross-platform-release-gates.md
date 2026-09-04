---
status: accepted
date: 2026-09-04
---

# ADR 0012: Cross-Platform Release Gates

## Context

The source-checkout prototype combines FastAPI, Celery, browser-facing
frontend behavior, migrations, and vendored runtimes. A single host check can
miss platform-specific process, path, event-loop, or integration failures.
The release branch also needs evidence that the migration chain and the
authenticated case workflow work together, rather than only passing isolated
unit tests.

## Decision

Windows and Ubuntu CI are binding acceptance gates for release-0.2. The
required GitHub checks for those workflows are binding on PR #1 and must pass
before branch integration.

The release gate set includes a real migration round-trip and a real authenticated integration workflow against the canonical source checkout.
Focused governance tests, the applicable backend suite, frontend tests and
production build checks, `git diff --check`, and release-surface checks remain
part of the evidence set when their areas are affected.

The gate records must distinguish a skipped check caused by an explicit
environment limitation from a passing check. A green local unit run cannot
substitute for a required cross-platform or integration check.

## Consequences

- Platform-specific regressions are visible before release integration.
- Migration and authentication failures are tested at the workflow seam where
  users encounter them.
- PR status is governed by required GitHub checks rather than informal local
  sign-off.
- Larger architecture deepenings remain a planned post-release track and are
  not smuggled into the release gate work.

## Rejected Alternatives

- Validate only on the developer's host | Rejected because Windows and Ubuntu
  exercise different runtime assumptions.
- Use migration compilation or mocked authentication as release evidence |
  Rejected because neither validates a real migration or integration path.
- Make the required checks advisory | Rejected because a release gate must be
  enforceable and auditable.
