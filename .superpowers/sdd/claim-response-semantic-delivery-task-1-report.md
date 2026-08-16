# Task 1 Report: Backend Path Semantic Contract

## Implementation

- Preserved the existing direct-comment path implementation and schema contract.
- The path-level semantic overlay is emitted only after exact canonical
  evidence-reference matching against a ready, non-fallback semantic artifact.
- Fallback artifacts, incomplete path mappings, and missing NLI labels are
  fail-closed; no partial overlay or synthetic `unknown` stance is returned.
- Direct comment-thread paths represent uncomputed network downstream reach as
  unavailable with the stable reason
  `direct_comment_thread_network_reach_not_computed`.

## TDD Evidence

The pre-existing task record documents RED before the initial implementation.
The inherited tests cover ready exact aggregation, unmatched references,
fallback artifacts, and absent NLI labels. The final GREEN verification was:

```powershell
cd system/backend
.\.venv\Scripts\python.exe -m pytest tests\test_claim_response_landscape_service.py tests\test_propagation_viewpoint_api.py -q
```

Result: `34 passed in 0.89s`.

## Owned Files

- `system/backend/app/services/claim_response_landscape_service.py`
- `system/backend/app/schemas/propagation.py`
- `system/backend/tests/test_claim_response_landscape_service.py`
- `system/backend/tests/test_propagation_viewpoint_api.py`

## Constraint Notes

- No `.env` settings, runtime model configuration, risk score, ranking, or
  inferred propagation path was changed.
- `uv run` was not used because its environment repair attempts conflict with
  a locked local Torch DLL.

## Review Fix: Snapshot Integrity And Behavioral Frontend Coverage

### Implementation

- Semantic artifacts now require a matching immutable run snapshot and matching
  `embedding_manifest.snapshot_fingerprint`; a missing, unreadable, or stale
  binding is unavailable.
- Before a ready semantic artifact can contribute to Claim Response, the live
  event/platform posts and comments are compared with the artifact snapshot.
  Any mismatch or missing source identity is fail-closed with
  `semantic_artifact_snapshot_mismatch`.
- Direct-comment overlays now require every exact canonical evidence reference
  to resolve to a complete ready semantic record. Empty/malformed
  distributions, features, platforms, timestamps, or references emit no
  overlay.
- Frontend tests execute the exported Claim Response overlay selector and the
  unavailable direct-comment reach copy instead of source-text scanning those
  decisions.

### TDD Evidence

RED commands and observed failures before the corresponding production changes:

```powershell
cd system/backend
.\.venv\Scripts\python.exe -m pytest tests\test_claim_response_landscape_service.py -k 'incomplete_ready_evidence_records or stale_snapshot_fingerprint' -q
```

Result: `2 failed`; the service returned a partial overlay and accepted the
stale fingerprint artifact as ready.

```powershell
cd system/frontend
node --test tests\claim-response-presentation.spec.mjs
```

Result: `2 failed`; `selectClaimResponseSemanticOverlay` and
`claimResponseDownstreamReachText` did not exist.

```powershell
cd system/backend
.\.venv\Scripts\python.exe -m pytest tests\test_claim_response_landscape_service.py -k current_rows_that_do_not_match -q
```

Result: `1 failed`; current response rows were not checked against the
immutable snapshot.

```powershell
cd system/backend
.\.venv\Scripts\python.exe -m pytest tests\test_claim_response_landscape_service.py -k invalid_timestamp -q
```

Result: `1 failed`; a non-ISO semantic timestamp was accepted.

GREEN validation:

```powershell
cd system/backend
.\.venv\Scripts\python.exe -m pytest tests\test_claim_response_landscape_service.py tests\test_propagation_viewpoint_api.py -q
```

Result: `38 passed in 3.34s`.

```powershell
cd system/frontend
node --test tests\claim-response-landscape.spec.mjs tests\claim-response-presentation.spec.mjs tests\propagation-semantic.spec.mjs
npx vue-tsc -b
```

Result: `28 passed`; `vue-tsc` exited 0.

```powershell
git diff --check -- system/backend/app/services/claim_response_landscape_service.py system/backend/tests/test_claim_response_landscape_service.py system/frontend/src/views/propagation/claimResponsePresentation.ts system/frontend/src/views/propagation/index.vue system/frontend/tests/claim-response-presentation.spec.mjs system/frontend/tests/propagation-semantic.spec.mjs
```

Result: exit 0.

### Commit

- `4f58575 fix(propagation): enforce claim response semantic integrity`
