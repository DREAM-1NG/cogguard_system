# Claim Response Integrity and Responsive Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Accept only exact original-post evidence for claim responses and keep propagation charts error-free during viewport changes.

**Architecture:** Candidate paths must carry the primary `claim_id` and contain the canonical evidence reference of the non-empty `CaseClaim.source_url`. Allowlisted account membership only populates the official-publication lane. The frontend resizes only live ECharts instances whose containers are visible and connected.

**Tech Stack:** FastAPI, SQLAlchemy, MongoDB projection data, Vue 3, ECharts, Node contract tests, pytest.

## Global Constraints

- Work only in `G:\CISCN\CogGuard\.worktrees\refactor-system`.
- Do not change Coordination, Propagation, or Review risk scores.
- Do not infer a claim-response path from graph adjacency, shared topic, account name, or a post from the same account.
- Missing evidence remains an explicit unavailable state, never a synthetic response.
- Preserve user-owned dirty changes and stage only task-owned files.

---

### Task 1: Enforce Exact Primary-Claim Evidence

**Files:**
- Modify: `system/backend/app/services/claim_response_landscape_service.py`
- Modify: `system/backend/app/services/case_workbench_service.py`
- Modify: `system/backend/app/schemas/case_workbench.py`
- Modify: `system/backend/tests/test_claim_response_landscape_service.py`
- Modify: `system/backend/tests/test_case_workbench_mvp_service.py`

**Interfaces:**
- Consumes: `CaseClaim.claim_id`, a non-empty `CaseClaim.source_url`, raw post URLs, and candidate `key_paths`.
- Produces: only paths whose claim ID equals the primary claim and whose refs contain the canonical original-post ref.

- [ ] Write failing tests for a missing path claim ID, a secondary post from the same allowlisted account, and a blank source URL.
- [ ] Run `pytest tests/test_claim_response_landscape_service.py tests/test_case_workbench_mvp_service.py -q` and confirm the new cases fail.
- [ ] Canonicalize real raw URLs to evidence refs, require exact primary claim IDs, use the primary claim original-post ref instead of all authority-account posts, and reject blank URLs at schema and service boundaries.
- [ ] Re-run the focused tests and commit only these task files with `fix(propagation): require exact claim path evidence`.

### Task 2: Make Propagation Chart Resize Visibility-Safe

**Files:**
- Modify: `system/frontend/src/views/propagation/index.vue`
- Modify: `system/frontend/tests/propagation-path-graph-contract.spec.mjs` or a focused propagation lifecycle test

**Interfaces:**
- Consumes: current tab, ECharts instances, and visible chart-container refs.
- Produces: no resize request for a hidden, detached, or zero-sized ECharts container.

- [ ] Write a failing test that requires the resize handler to guard chart DOM connection and dimensions.
- [ ] Run `node --test tests/propagation-path-graph-contract.spec.mjs` and confirm it fails.
- [ ] Add the smallest shared chart-resize guard while preserving active-tab rendering.
- [ ] Re-run the focused test and `npx vue-tsc -b`, then commit only task files with `fix(propagation): guard hidden chart resize`.

### Task 3: Live Acceptance and Review

- [ ] Run the focused backend and frontend regressions plus `npm run build`.
- [ ] Verify `/propagation` for `trump_visit_2026_05_21`: primary source and exact-bound official publications are visible, while absent exact paths produce a clear empty response lane.
- [ ] Resize to `390x844`; require `document.documentElement.scrollWidth <= window.innerWidth` and no console errors.
- [ ] Request an independent review and resolve every Critical or Important finding.

### Task 4: Repair Claim-Response Mobile Chart Lifecycle

**Files:**
- Modify: `system/frontend/src/views/propagation/index.vue`
- Modify: `system/frontend/tests/propagation-mobile-resize.spec.mjs`

**Observed failure:** On the real authenticated `/propagation` page for
`trump_visit_2026_05_21`, switching to **主张回应图谱** and resizing to
`390x844` keeps the document width within the viewport but emits an ECharts
canvas-renderer `TypeError` from a stale propagation chart resize.

- [ ] Write a failing lifecycle regression that distinguishes a mounted DOM
  from a chart that is still unsafe to redraw after its tab became inactive.
- [ ] Fix the actual chart lifecycle cause. Do not catch and suppress ECharts
  exceptions, and do not alter propagation facts, ranking, risk scores, or
  the claim-response projection.
- [ ] Re-run the focused test, TypeScript build, and authenticated browser
  check at `390x844`; require `scrollWidth <= clientWidth` and no ECharts
  resize console error.

### Task 5: Type the Claim-Response Projection Contract

**Files:**
- Modify: `system/backend/app/schemas/propagation.py`
- Modify: `system/backend/tests/test_propagation_viewpoint_api.py`

- [ ] Write a failing API contract test for a malformed `ready` claim-response
  payload that lacks required anchor and evidence-lane fields.
- [ ] Replace the shallow projection `dict` and `list[dict]` response fields
  with minimal nested Pydantic models that represent the existing projection.
- [ ] Preserve the authenticated route and valid payload shape; do not change
  facts, rankings, scores, or add a fallback.

### Task 6: Complete Claim-Response Evidence Reading

**Files:**
- Modify: `system/frontend/src/views/propagation/index.vue`
- Modify: `system/frontend/src/api/propagation.ts` only if needed for the
  already returned projection fields
- Modify: `system/frontend/tests/claim-response-landscape.spec.mjs`

- [ ] A ready projection with an anchor but no official publication or
  response must still show the anchor and explicit empty lanes.
- [ ] The existing path drawer must show the exact `evidence_refs`, observed
  node sequence, source-account context already returned by the projection,
  and observed path contribution. Do not synthesize a supporting post.
- [ ] Write failing contract tests before production changes and retain the
  existing node and semantic overlay drawers.
