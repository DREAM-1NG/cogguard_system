# Event Review Case Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate CogGuard around an event-level review case that keeps research and runtime internals behind a sanitized product API and a business-focused analyst workspace.

**Architecture:** A new `ReviewCase` aggregate references immutable `EventSnapshot` revisions and existing analysis/review records. An application service owns orchestration, decision concurrency, evidence annotations, activity history, and product-safe projections; the Vue application consumes only `/api/v2/review-cases` while `/api/v2/analysis` becomes an internal diagnostic boundary.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy async, Alembic, MongoDB, Celery, Vue 3, TypeScript, Ant Design Vue, Vite, pytest, Playwright.

---

### Task 1: Domain Contracts And Persistence

**Files:**
- Create: `system/backend/app/schemas/review_case.py`
- Create: `system/backend/app/models/review_case.py`
- Create: `system/backend/alembic/versions/e8b4c1d7a620_add_review_case_tables.py`
- Modify: `system/backend/app/models/__init__.py`
- Test: `system/backend/tests/test_review_case_contracts.py`
- Test: `system/backend/tests/test_review_case_persistence_models.py`

- [ ] Define the six locked string enums and product-safe request/response contracts, with `extra="forbid"` on write models.
- [ ] Add `ReviewCase`, `ReviewCaseSnapshotRevision`, `ReviewDecisionDraft`, `ReviewDecision`, `EvidenceAnnotation`, and `CaseActivity` records with one case per event and one confirmed decision version per case/version.
- [ ] Add indexes and uniqueness constraints for event identity, snapshot fingerprint idempotency, annotation identity, activity ordering, and decision concurrency.
- [ ] Add an Alembic upgrade/downgrade that creates only the new aggregate tables and leaves legacy report tables read-only.
- [ ] Run `python -m pytest tests/test_review_case_contracts.py tests/test_review_case_persistence_models.py -q` from `system/backend`.

### Task 2: Review Case Application Service And Sanitized API

**Files:**
- Create: `system/backend/app/services/review_case_service.py`
- Create: `system/backend/app/api/v2/review_cases.py`
- Modify: `system/backend/app/api/v2/router.py`
- Modify: `system/backend/app/api/v1/risk.py`
- Test: `system/backend/tests/test_review_case_service.py`
- Test: `system/backend/tests/test_review_case_v2_api.py`

- [ ] Implement latest/search/detail/evidence/activity queries and a single product projection that cannot emit run, job, task, model, checkpoint, artifact, Agent, raw confidence, or runtime-state fields.
- [ ] Implement evidence annotations, review requests, decision draft autosave, and immutable decision confirmation through one transaction-owned service boundary.
- [ ] Add all locked `/api/v2/review-cases` routes behind the existing login dependency, including resumable case activity SSE.
- [ ] Make V1 risk endpoints a thin deprecated mapping to the new service and include deprecation metadata.
- [ ] Add recursive response-leak tests and run `python -m pytest tests/test_review_case_service.py tests/test_review_case_v2_api.py -q`.

### Task 3: Crawl Completion And Automatic Analysis Orchestration

**Files:**
- Create: `system/backend/app/services/review_case_orchestrator.py`
- Modify: `system/backend/app/tasks/crawl_tasks.py`
- Modify: `system/backend/app/services/crawl_service.py`
- Modify: `system/backend/app/core/analysis/executor.py`
- Modify: `system/backend/app/core/analysis/registry.py`
- Test: `system/backend/tests/test_review_case_orchestrator.py`
- Test: `system/backend/tests/test_crawl_review_case_integration.py`

- [ ] Upsert exactly one case after a successful local or queued crawl carrying `event_id`.
- [ ] Derive the core window from the successful crawl batch and the context window from all event data, then register an immutable snapshot revision by fingerprint.
- [ ] Execute Coordination Discover, Propagation Analysis, and Student Review for a new revision; route Teacher Review only for policy reasons or a manual request.
- [ ] Prevent duplicate analysis for an unchanged fingerprint and mark a changed fingerprint as requiring reconfirmation without overwriting a confirmed decision.
- [ ] Ensure only one active Teacher job exists per case/revision and convert late advisory arrival into a reconfirmation activity.
- [ ] Run the local/queued orchestration tests plus existing executor and registry regressions.

### Task 4: Decision Integrity, Feedback, And Legacy Compatibility

**Files:**
- Modify: `system/backend/app/services/review_case_service.py`
- Modify: `system/backend/app/services/review_system_service.py`
- Modify: `system/backend/app/models/review_system.py`
- Test: `system/backend/tests/test_review_case_decisions.py`
- Test: `system/backend/tests/test_review_case_feedback.py`

- [ ] Lock the case row during confirmation, create an immutable numbered decision, and reject stale draft/revision confirmation attempts.
- [ ] Convert analyst confirmation and correction into deduplicated structured feedback without exposing an active-learning queue.
- [ ] Project legacy risk reports, Agent reports, and feedback into compatibility activities/advisories while keeping legacy tables read-only.
- [ ] Add race, immutability, late-advisory, deduplication, and compatibility tests.

### Task 5: Model Activation History And Artifact Boundary Hardening

**Files:**
- Modify: `system/backend/app/models/analysis.py`
- Modify: `system/backend/app/schemas/analysis.py`
- Modify: `system/backend/app/services/analysis_governance_service.py`
- Modify: `system/backend/app/api/v2/analysis.py`
- Create: `system/backend/alembic/versions/f1c9d6a4b730_add_model_governance_decisions.py`
- Test: `system/backend/tests/test_analysis_governance.py`

- [ ] Resolve artifact paths under the configured root, reject symlink escapes, verify SHA-256 and manifest capability, and calculate gates only from registered server-side metrics.
- [ ] Replace client-submitted quality booleans and multi-approver payloads with a single authenticated operator decision.
- [ ] Append immutable activation/rollback decisions and atomically move the Active Pointer to any previously approved compatible version.
- [ ] Remove public analysis execution/status mutation routes while retaining authenticated diagnostic reads required by internal tooling.
- [ ] Run governance, API, path-boundary, history, and rollback tests.

### Task 6: Event Review Workspace

**Files:**
- Create: `system/frontend/src/api/reviewCases.ts`
- Create: `system/frontend/src/types/reviewCase.ts`
- Rewrite: `system/frontend/src/views/risk/index.vue`
- Modify: `system/frontend/src/router/index.ts`
- Test: `system/frontend/src/views/risk/reviewCase.spec.ts`

- [ ] Replace technical review controls with event selection, preliminary finding, evidence sufficiency, urgency/disposition, coordination and propagation summaries, and action-required copy.
- [ ] Group evidence by supports/contradicts/irrelevant/unresolved; allow only structured annotations, links, and notes.
- [ ] Present Teacher output only as review advisory and show substantive differences from the preliminary finding.
- [ ] Autosave decision drafts and require an explicit confirmation before creating an immutable confirmed decision.
- [ ] Show only business activities and preserve deep links from dashboard events.

### Task 7: Dashboard, System Surface, Accessibility, And Asset Budget

**Files:**
- Modify: `system/frontend/src/views/dashboard/index.vue`
- Modify: `system/frontend/src/views/system/index.vue`
- Modify: `system/frontend/src/components/layout/BasicLayout.vue`
- Modify: `system/frontend/src/views/login/index.vue`
- Modify: `system/frontend/vite.config.ts`
- Delete: `system/frontend/src/views/home/`
- Delete: `system/frontend/src/views/analysis/`
- Delete: `system/frontend/src/api/analysis.ts`
- Test: `system/frontend/tests/review-case-flow.spec.ts`

- [ ] Keep dashboard as `/`, add a searchable event selector and `进入研判` link, and preserve the local map/data screen.
- [ ] Reduce the offline GeoJSON payload below 2 MB while retaining correct world-map rendering.
- [ ] Limit `/system` to provider/runtime configuration, connectivity, and task health; remove governance and evaluation panels.
- [ ] Replace clickable non-semantic containers, add labels/focus/keyboard/`aria-live`/skip-link support, remove `transition: all`, and remove hardcoded login credentials.
- [ ] Remove preview and dead route/client surfaces, define stable manual chunks, and verify no generated JS chunk exceeds 1 MB.
- [ ] Run `npm run build` and Playwright at `1280x720` and `1440x900` against the real application routes.

### Task 8: Vocabulary, ADRs, And Documentation Sync

**Files:**
- Modify: `UBIQUITOUS_LANGUAGE.md`
- Create: `docs/adr/0007-event-review-case-product-boundary.md`
- Create: `docs/adr/0008-lan-prototype-governance-boundary.md`
- Modify: `docs/adr/index.md`
- Modify: `CONTEXT.md`
- Modify: `system/README.md`
- Modify: `README.md`
- Modify: `doc/engineering/system-governance.md`
- Modify: `doc/engineering/development-roadmap.md`
- Modify: `doc/engineering/development-log.md`

- [ ] Add Event Review Case, Preliminary Finding, Review Advisory, Confirmed Decision, Evidence Sufficiency, Evidence Annotation, and Case Activity as canonical terms.
- [ ] Prohibit Student, Teacher, Analysis Run, model, checkpoint, artifact, and Agent language from product copy while retaining those terms in runtime/research contexts.
- [ ] Record automatic review routing and the LAN prototype governance boundary in new ADRs; mark conflicts in the ADR index without rewriting accepted ADR bodies.
- [ ] Align README, API documentation, engineering map, roadmap, and development log with the implemented behavior and explicitly record remaining public-production limitations.
- [ ] Run naming/governance documentation tests and a repository scan for forbidden product-copy terms.

### Task 9: Full Verification And Branch Completion

**Files:**
- Modify only files required to correct verified failures.

- [ ] Run full backend `python -m pytest tests -q`.
- [ ] Run Alembic upgrade/downgrade/upgrade against an isolated database configuration.
- [ ] Run frontend `npm run build`, verify chunk and map budgets, and inspect the generated report.
- [ ] Start the real backend/frontend dependencies and validate the Trump event review flow without `/preview`.
- [ ] Run Playwright at both required desktop viewports and capture evidence that the map, event switch, evidence annotation, advisory request, draft, confirmation, and activity flow work.
- [ ] Perform final spec-compliance and code-quality reviews, synchronize documentation, and finish the branch with Lore-format commits.
