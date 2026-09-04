# Prediction Boundary Closure Plan

## Goal

Close the highest-risk gaps in the current-event propagation prediction path without changing the observed-analysis path: make observation ratios produce real temporal prefixes, make candidate identity coverage explicit and truthful, isolate cached benchmark evidence from the product endpoint, and enforce the Twitter checkpoint scope.

## Tasks

## Task 1

Update the event adapter and its tests so observation_ratio deterministically truncates records when no explicit cutoff is supplied, and candidate metadata distinguishes observed reactivation candidates from unmapped train/relation buckets without fabricating identities.

## Task 2

Update the prediction API/service and its tests so the deployed current-event endpoint rejects unsupported platforms, while the cached benchmark route is clearly research-only and cannot be mistaken for current-event inference.

## Task 3

Clean stale prediction method metadata and frontend/API types, and add contract tests for the new scope and coverage fields.

## Task 4

Run focused backend tests, frontend type/build checks, and an HTTP smoke path; resolve failures before final review.

## Constraints

- Do not alter propagation observation analysis or its graph visualization.
- Do not use future event rows to generate candidates or identity mappings.
- Do not restore speed/acceleration fallback behavior.
- The public current-event endpoint may silently abstain with structured empty output, but must not return fabricated prediction users.
- Keep the existing checkpoint under system/research/propagation_analysis and report its dataset scope.
