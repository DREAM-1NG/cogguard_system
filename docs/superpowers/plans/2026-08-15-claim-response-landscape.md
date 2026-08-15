# Claim Response Landscape Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the observed relationship between an authority claim, official
account publications, influential responses, and their propagation evidence
visible in the existing Propagation Analysis page.

**Architecture:** Store reviewed authority-account bindings in MySQL. Build a
read-only event projection from bindings, Case Claims, raw event records,
semantic artifact results, and observed propagation paths. Keep ranking and
views event/platform scoped; the frontend consumes only the projection.

**Tech Stack:** FastAPI, SQLAlchemy/Alembic, MongoDB event readers, Vue 3,
TypeScript, Ant Design Vue, ECharts, pytest, node:test.

## Global Constraints

- Work only in `G:\CISCN\CogGuard\.worktrees\refactor-system`.
- Preserve unrelated dirty files and do not reset, clean, or overwrite them.
- Do not modify Coordination, Propagation, or Review risk conclusions.
- Official classification requires an allowlisted source plus exact
  `platform + author_id`; platform verification alone is insufficient.
- Stance is relative to the bound primary claim; no stance is fabricated when
  semantic evidence is unavailable.
- Use test-first development and make every displayed record evidence-backed.

---

### Task 1: Authority Account Bindings And Normalized Author Evidence

**Files:**
- Modify: `system/backend/app/models/case_workbench.py`
- Modify: `system/backend/app/models/__init__.py`
- Modify: `system/backend/app/schemas/case_workbench.py`
- Modify: `system/backend/app/services/case_workbench_service.py`
- Modify: `system/backend/app/api/v2/authority_sources.py`
- Modify: `system/backend/app/core/crawler/social/normalizers.py`
- Create: `system/backend/alembic/versions/<revision>_add_authority_source_accounts.py`
- Test: `system/backend/tests/test_case_workbench_mvp_service.py`
- Test: `system/backend/tests/test_social_crawler_normalization.py`

**Interfaces:**
- Produces `AuthoritySourceAccount(source_id, platform, author_id, display_name_snapshot, verification_snapshot, reviewed_by)`.
- Exposes authenticated source-account create/list endpoints under
  `/api/v2/authority-sources/{source_id}/accounts`.

- [ ] Write failing tests that reject a non-allowlisted source binding, preserve
  exact platform/account identity, and normalize verification/follower fields.
- [ ] Run the focused tests and confirm they fail for missing binding/normalizer behavior.
- [ ] Implement the smallest model, schema, migration, service, API, and
  normalizer changes needed for those tests.
- [ ] Re-run focused tests, then commit only Task 1 files.

### Task 2: Claim Response Landscape Projection And API

**Files:**
- Create: `system/backend/app/services/claim_response_landscape_service.py`
- Modify: `system/backend/app/api/v1/propagation.py`
- Modify: `system/backend/app/schemas/propagation.py`
- Test: `system/backend/tests/test_claim_response_landscape_service.py`
- Test: `system/backend/tests/test_propagation_viewpoint_api.py`

**Interfaces:**
- Produces `build_claim_response_landscape(event_id, platform=None)`.
- Exposes `GET /api/v1/propagation/claim-response-landscape?event_id=...&platform=...`.
- Returns `ready`, `not_found`, or `blocked`, plus claim anchor, official
  publications, influential responses, timeline, and coverage.

- [ ] Write failing tests for exact official-account matching, exclusion of
  verified-but-unbound accounts, platform-scoped ranking, missing path/semantic
  coverage, and canonical evidence references.
- [ ] Run tests and confirm failures arise because the projection/API do not exist.
- [ ] Implement the projection with observed readers and existing propagation
  graph results. Rank by downstream reach and path contribution; calculate
  engagement only as a platform-local percentile.
- [ ] Re-run focused tests and commit only Task 2 files.

### Task 3: Propagation Page Claim Response Landscape

**Files:**
- Modify: `system/frontend/src/api/propagation.ts`
- Modify: `system/frontend/src/views/propagation/index.vue`
- Test: `system/frontend/tests/claim-response-landscape.spec.mjs`
- Test: `system/frontend/tests/propagation-semantic.spec.mjs`

**Interfaces:**
- Consumes `getClaimResponseLandscape({ event_id, platform })`.
- Adds one `主张回应图谱` tab without changing existing tabs or their result semantics.

- [ ] Write a failing contract test requiring the tab, claim anchor, two-lane
  timeline, platform-local influence selector, evidence drill-down, and blocked
  state.
- [ ] Run the node test and confirm it fails because the view/API client is absent.
- [ ] Add narrow API types and the new tab. Reuse existing path/node detail
  drawers; do not duplicate propagation graph data or display unbound accounts
  as official media.
- [ ] Re-run frontend contract tests, `vue-tsc -b`, and build; commit only Task 3 files.

### Task 4: Context, Documentation, And Integrated Verification

**Files:**
- Modify: `conductor/product.md`
- Modify: `conductor/tracks.md`
- Modify: `UBIQUITOUS_LANGUAGE.md`
- Modify: `doc/engineering/development-roadmap.md`
- Modify: `doc/engineering/development-log.md`
- Test: Task 1-3 focused suites and production frontend build.

- [ ] Record the authoritative account binding and Claim Response Landscape
  terms without promoting them to a risk conclusion.
- [ ] Run migration upgrade against an available local database; if unavailable,
  record the infrastructure blocker and validate migration syntax/tests.
- [ ] Run backend focused suites, frontend node tests, TypeScript check, and
  production build.
- [ ] Run an authenticated browser check when services are available: exact
  source binding shows in the official lane, unbound verified account does not,
  and a selected response drills into its evidence.
- [ ] Commit only Task 4 files and update `.superpowers/sdd/progress.md` after
  each reviewed task.
