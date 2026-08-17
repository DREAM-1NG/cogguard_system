# Task 4 Semantic Overlay TDD Evidence

## RED

- Added `system/frontend/tests/propagation-semantic.spec.mjs` before production changes.
- Ran `npm test -- propagation-semantic.spec.mjs` from `system/frontend`.
- Result: 5 expected failures for the missing semantic projection loader, scope reset,
  path-id/evidence-reference matching, unavailable state, and drawer fields.

## GREEN

- Added an additive semantic projection loader to the propagation view with stale-response guards.
- Clears the projection for both route and direct event/platform scope changes.
- Adds a path drawer overlay that prefers `path_id`, then exact evidence-reference matching.
- Ready, structurally valid overlays render sentiment, keywords, topics, entities, stance,
  platform range, time range, and evidence references. Blocked, absent, empty, and malformed
  projections leave the observed propagation path unchanged and show `暂无语义叠加`.
- Updated only affected propagation prediction test doubles in
  `system/backend/tests/test_event_scoped_analysis.py` for the current parameter and response contract.

## Verification

- `npm test -- propagation-semantic.spec.mjs`: passed, 47 tests.
- `npm test`: passed, 47 tests.
- `npx vue-tsc -b`: passed.
- `npm run build`: passed, including delivery preload and budget checks.
- `python -m pytest tests/test_event_scoped_analysis.py -q`: passed, 21 passed and 1 skipped.

The focused backend invocation emitted existing local-environment warnings for the unavailable
pytest async plugin/configuration and a Transformers cache deprecation warning.

## Review Fix: Robust, Fail-Closed Propagation Overlay Matching

### RED

- Replaced source-regex-only regression coverage with executable tests that evaluate the extracted
  propagation matcher and validator.
- `node --test tests/propagation-semantic.spec.mjs` failed as expected before the repair:
  numeric `path_id` caused `path.path_id?.trim is not a function`, and the nested-overlay test
  demonstrated that the original validator accepted malformed required fields.

### GREEN

- Path identifiers now normalize finite numeric and string values before matching. Matching still
  prefers `path_id`, then falls back to exact evidence-reference equality.
- Required nested overlay fields now fail closed: non-empty numeric sentiment/stance distributions;
  non-empty, runtime-shaped keyword/topic/entity records; non-empty platforms and evidence refs;
  and complete non-empty time ranges are required before the existing empty state is bypassed.

### Verification

- `node --test tests/propagation-semantic.spec.mjs`: passed, 6 tests.
- `npm test`: passed, 48 tests.
- `npx vue-tsc -b`: passed.
- `npm run build`: passed, including delivery preload and budget checks.
- `git diff --check -- system/frontend/src/views/propagation/index.vue system/frontend/tests/propagation-semantic.spec.mjs`: passed.
