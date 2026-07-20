# CogGuard System Refactor Roadmap

## Goal

Improve reuse, locality, and long-term maintainability across the CogGuard system without changing externally visible behavior.

This refactor lane runs in:

- Branch: `refactor-system`
- Worktree: `G:\CISCN\CogGuard\.worktrees\refactor-system`

## Installed Project Skills

The refactor workspace has a project-level `skills-lock.json` and local installed skills for this lane:

- `improve-codebase-architecture`
- `request-refactor-plan`
- `architecture-patterns`
- `python-testing-patterns`

These were installed to support architecture scanning, incremental refactor planning, and test-first execution.

## Current Friction

### Backend

- `system/backend/app/core/propagation_legacy.py` is a shallow module surface over multiple responsibilities:
  - graph construction
  - role identification
  - evidence-chain extraction
  - diffusion layout
  - user quality portrait
- `system/backend/app/core/review/kt3_agent_review.py` mixes provider setup, prompt building, batching, retry policy, and result shaping in one implementation.
- `system/backend/app/services/` contains several orchestration modules that still know too much about concrete data loading and output shaping.

### Frontend

- `system/frontend/src/views/propagation/index.vue` concentrates types, formatting helpers, chart translation, route sync, and page actions in one file.
- `system/frontend/src/views/risk/components/IntelligentReviewPane.vue` and `EvidenceReviewPane.vue` both carry page-level state shaping that should become reusable view-model logic.
- Route-level pages own too much display-only transformation work instead of importing stable helpers.

## Refactor Principles

- Keep public interfaces stable unless a clearer seam is already protected by tests.
- Prefer deeper modules over more wrappers.
- Move pure transformation logic out of page files and orchestration layers first.
- Lock behavior with existing tests before moving code.
- Favor extraction and reuse over new abstraction layers.

## Phase Plan

### Phase 1: Propagation Module Deepening

Scope:

- Split `propagation_legacy.py` into internal propagation modules while keeping `build_propagation_graph()` stable.
- Extract reusable role-analysis, evidence, diffusion, and quality-portrait logic into `app/core/propagation/`.
- Reduce the propagation page's local helper burden by moving reusable types and pure helpers out of the view file when safe.

Success criteria:

- `build_propagation_graph()` behavior remains unchanged.
- Existing propagation and event-scoped tests still pass.
- Frontend still builds cleanly.

### Phase 2: KT3 Review Module Deepening

Scope:

- Separate provider adapters, prompt construction, execution planning, retry policy, and payload normalization in `app/core/review/kt3_agent_review.py`.
- Reduce direct coupling between risk orchestration and concrete LLM/runtime decisions.

### Phase 3: Service-Layer Simplification

Scope:

- Normalize service orchestration patterns across propagation, risk, coordination, and dashboard flows.
- Move duplicated "load data -> analyze -> attach scope" patterns behind smaller interfaces.

### Phase 4: Frontend View-Model Extraction

Scope:

- Extract page-local transformation logic into `model.ts`, `helpers.ts`, or composables by feature.
- Keep route views focused on interaction flow and rendering.

## Phase 1 Commit Shape

1. Add refactor workspace hygiene and roadmap artifacts.
2. Extract propagation internals into reusable backend modules.
3. Run propagation-focused backend tests.
4. Extract safe frontend propagation helpers.
5. Run frontend build and targeted regression checks.

## Out of Scope

- Product behavior changes
- Database schema changes
- New dependencies
- Full KT3 redesign in the same commit as propagation refactor

## Verification Standard

For each phase, run fresh verification before claiming completion:

- Backend: targeted pytest first, then broader dependent tests when touched
- Frontend: `npm run build`
- If an extracted seam is not behavior-locked yet, add or extend regression coverage before larger movement
