# Claim Response Semantic Delivery

## Goal

Close the smallest remaining delivery gap for the existing Claim Response
Landscape. A direct comment-thread path can expose a real semantic overlay in
the Propagation drawer only when every displayed evidence reference maps to a
ready, non-fallback semantic artifact item.

This remains a read-only evidence projection. It must not change Coordination,
Propagation, Review, risk scores, rankings, or create paths from similarity,
account names, or graph adjacency.

## Task 1: Verify And Stabilize The Backend Contract

- Treat the existing uncommitted path-overlay implementation as the task
  ownership boundary: `claim_response_landscape_service.py`,
  `schemas/propagation.py`, and their focused tests.
- Use the existing test-first records as baseline, then run and repair the
  focused contract tests without weakening configuration or changing secrets.
- Verify that a direct-comment path exposes `semantic_overlay` only when every
  canonical path `evidence_ref` has a matching ready semantic layer item.
- Keep raw NLI labels in the overlay and emit no partial, fallback, synthetic,
  similarity-derived, or event-wide aggregate result.
- Keep direct comment-thread `downstream_reach` unavailable when network reach
  has not been computed, including a stable reason for the frontend.
- Commit only files owned by this task.

## Task 2: Complete Propagation Page Readout

- Extend the Claim Response path contract in `src/api/propagation.ts` with the
  optional backend `semantic_overlay` payload.
- Pass the exact Claim Response overlay into the existing propagation path
  drawer. Prefer it over the generic Propagation Analysis artifact overlay for
  the same selected Claim Response path; retain the generic overlay for normal
  propagation paths.
- In the drawer display the existing real semantic evidence fields: sentiment,
  raw NLI stance, keywords, topics, entities, platforms, time range, and exact
  evidence references.
- Show `评论链路径，未计算网络下游覆盖` whenever the backend marks direct
  comment network reach unavailable. Never render this state as numeric zero.
- Add contract tests for rendered exact overlays and unavailable reach. Clear
  stale overlay data when event or platform scope changes.
- Commit only files owned by this task.

## Task 3: Verify The Integrated Delivery And Synchronize Context

- Run the focused backend and frontend suites, TypeScript check, production
  frontend build, and the available local browser/API smoke checks.
- Do not claim live success if local services, credentials, or the test
  environment prevent it; record the exact blocker and preserve fail-closed UI
  behaviour.
- Update only relevant project memory and delivery documentation:
  `CONTEXT.md`, `UBIQUITOUS_LANGUAGE.md`, `conductor/tracks.md`,
  `doc/engineering/development-roadmap.md`, `doc/engineering/development-log.md`,
  and `system/README.md` when their current wording would otherwise misstate
  this delivery.
- Update `.superpowers/sdd/progress.md` with review-backed status and commit
  only task-owned documentation.

## Acceptance

- The API preserves path-level semantic overlays and the frontend can render
  them without requesting an unrelated generic overlay.
- Every rendered semantic value is traceable to the same exact evidence
  references shown in the selected path.
- An unavailable network-reach value has explanatory Chinese copy, not `0`.
- Any artifact that is missing, blocked, fallback, malformed, stale, or only
  partially mapped remains unavailable rather than being presented as evidence.
- Backend and frontend targeted checks pass; broader checks and runtime smoke
  outcomes are recorded truthfully.

## Final Contract Hardening (2026-08-17)

The final review identified three fail-closed gaps and they were repaired in
`1200856`:

- A Claim Response path cannot use a generic Propagation semantic overlay when
  its own exact overlay is absent or rejected.
- A string evidence reference is accepted only in its supplied canonical form:
  `platform:post|comment:id`, with no whitespace, empty segment, or extra
  colon.
- A semantic artifact is unavailable when either semantic layer contains a
  malformed entry or a duplicate canonical post/comment identity.

The repair was test-first. Focused backend validation passed (`39 passed`),
frontend contracts passed (`30 passed`), and `vue-tsc -b`, the production
frontend build, and `git diff --check` passed. Live authenticated browser/API
verification remains an environment-dependent check; it is not claimed here.
