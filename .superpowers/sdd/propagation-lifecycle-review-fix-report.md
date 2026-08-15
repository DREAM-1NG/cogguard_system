# Propagation Lifecycle Review Fix Report

## Summary

Fixed the propagation page race conditions and narrow-viewport control overflow:

- `loadAnalysis()` now snapshots request params and current event/platform/node-limit/full-view scope, increments an analysis request generation, and rejects stale responses before mutating analysis state or rendering charts.
- `loadPropagationAlerts()` now snapshots event/platform scope, increments an alert request generation, and rejects stale success or error responses before replacing current alert rows.
- `.path-node-control` now stacks inside the existing mobile breakpoint so the 160px slider minimum cannot force a four-column overflow at a 390px viewport.

The existing chart resize lifecycle behavior from `6a5ba41` was preserved and rechecked with the focused lifecycle tests.

## Files Changed

- `system/frontend/src/views/propagation/index.vue`
- `system/frontend/tests/propagation-scope-race.spec.mjs`
- `.superpowers/sdd/propagation-lifecycle-review-fix-report.md`

## RED/GREEN Evidence

1. RED - analysis race guard:
   - Command: `node --test tests/propagation-scope-race.spec.mjs`
   - Result: failed as expected.
   - Key failure: `Expected samePropagationAnalysisScope to exist`

2. GREEN - analysis race guard:
   - Command: `node --test tests/propagation-scope-race.spec.mjs`
   - Result: `pass 1`, `fail 0`

3. RED - alert race guard:
   - Command: `node --test tests/propagation-scope-race.spec.mjs`
   - Result: failed as expected with the first analysis test still passing.
   - Key failure: `Expected samePropagationAlertsScope to exist`

4. GREEN - alert race guard:
   - Command: `node --test tests/propagation-scope-race.spec.mjs`
   - Result: `pass 2`, `fail 0`

5. RED - mobile path-node control:
   - Command: `node --test tests/propagation-scope-race.spec.mjs`
   - Result: failed as expected with the race tests still passing.
   - Key failure: missing mobile `@media (max-width: 768px)` override for `.path-node-control`

6. GREEN - mobile path-node control:
   - Command: `node --test tests/propagation-scope-race.spec.mjs`
   - Result: `pass 3`, `fail 0`

## Validation Results

- Focused propagation/lifecycle tests:
  - Command: `node --test tests/propagation-scope-race.spec.mjs tests/propagation-mobile-resize.spec.mjs tests/kept-alive-route-lifecycle.spec.mjs`
  - Result: `pass 16`, `fail 0`

- Type check:
  - Command: `npx vue-tsc -b`
  - Result: passed

- Frontend suite:
  - Command: `npm test`
  - Result: `pass 91`, `fail 0`

## Self-Review

- Stale analysis responses are rejected before `analysisResult.value = res.data`, before sync-time updates, and before path chart rendering.
- The analysis guard includes event ID, platform, requested node limit, and full-view mode.
- Analysis requests pass a snapshot of `requestParams.value` to avoid mixing a current computed object with an older in-flight request.
- Stale alert successes and stale alert errors are both ignored, preventing old rows or old error cleanup from replacing the current scope.
- Loading flags are only cleared by the latest generation, while a latest request whose scope changed without a replacement request can still stop loading.
- The resize lifecycle code and active-tab ownership checks were not changed.
- Mobile CSS uses a one-column grid for `.path-node-control` inside the existing `max-width: 768px` breakpoint and allows the label/count to wrap.

## Concerns

The mobile overflow check is covered by a focused CSS contract test rather than a live browser screenshot at 390px, because the existing frontend test suite for this area is Node-based source/behavior checks.
