# CogGuard

CogGuard is a research-oriented product system for evidence-driven social media analysis. The active runnable system is `system/`; upstream source trees remain reference boundaries for provenance and license review.

The current product narrative is:

```text
event -> evidence -> Coordination Discover -> Propagation Analysis -> Risk Review -> governance action -> feedback
```

## Active Capabilities

| Capability | Canonical implementation | Status |
| --- | --- | --- |
| Crawler | `system/backend/app/core/crawler/`, `system/runtimes/social_runtime/`, `system/runtimes/news_runtime/` | Internal social and news runtime boundaries are wired into product collection. |
| Analysis | `system/backend/app/core/analysis/`, `system/backend/app/api/v2/analysis.py` | `EventSnapshot`, `AnalysisRun`, REST recovery, and SSE event streaming are available. |
| Coordination Discover | `system/research/coordination_discover/` | CPU research pipeline, platform-generic evidence graph, strict Leiden, hashed artifacts, and backend fallback are runnable; no approved claimable checkpoint is active. |
| Coordination Detect | `system/research/coordination_detect/` | Public-label validation boundary exists; the current unlabeled event is correctly non-claimable and reports missing labels. |
| Propagation Analysis | `system/research/propagation_analysis/`, `system/backend/app/core/propagation/` | Hindcast protocol, baselines, intervals, and live fallback are runnable; current live/cached paths remain prototype-only without an approved checkpoint. |
| Risk Review | `system/backend/app/core/review/`, `system/research/review_teacher/`, `system/runtimes/review_student/` | Student and 5+1+1 Teacher seams run locally; Student is shadow/untrained, Teacher is advisory, and canonical verdicts require analyst approval. |
| Case Workbench | `system/backend/app/api/v2/cases.py`, `system/backend/app/services/case_workbench_service.py`, `system/frontend/src/views/cases/index.vue` | Read-model MVP shows the Trump-visit case loop from evidence through semantic overlays, Review, actions, feedback, and report placeholders; durable persistence and closeout are not complete. |
| Social Bot Detection | `system/research/social_bot_detection/`, `system/backend/app/core/trained_bot_detection.py` | Internal BotRHG transfer is runnable on Botection, and the strict NLPCC-aligned path is runnable on Cresci-2015, Cresci-2017, and Midterm-2018 with local RoBERTa-backed checkpoints; public benchmark runs remain transfer artifacts, not superiority claims. |

## Repository Map

| Path | Role |
| --- | --- |
| `system/` | Active product system: backend, frontend, vendored runtimes, research packages, deployment files, and tests. |
| `system/backend/` | FastAPI, Celery, database access, product services, and backend tests. |
| `system/frontend/` | Vue 3 and TypeScript management UI. Frontend display is not part of the current governance cleanup. |
| `system/runtimes/` | Vendored executable runtimes used by product code. |
| `system/research/` | System-readable research packages consumed through explicit adapters. |
| `doc/engineering/` | Long-lived engineering documentation, governance, maps, setup, roadmap, and log. |
| `doc/adr/` | Accepted architecture decision records. One numbered file per durable decision. |
| `doc/research/` | Research positioning and literature notes. |
| `aris/` | Historical research workspace. Its physical names are not canonical product vocabulary. |
| `MediaCrawler-main/`, `NewsCrawler-main/`, `CooRTweet-master/` | Reference boundaries only; product runtime code must not execute from these directories. |

## Naming Sources

- `UBIQUITOUS_LANGUAGE.md` is the canonical glossary.
- `doc/engineering/system-governance.md` is the normative naming and package-boundary policy.
- `doc/engineering/project-map.md` describes repository boundaries and default edit ownership.
- `doc/adr/` records the accepted decisions behind those boundaries.

New code and current documentation must use formal capability names: `Coordination Discover`, `Coordination Detect`, `Propagation Analysis`, `Risk Review`, `Student Review`, `Teacher Review`, and `Crawler`.

## Quick Start

```powershell
cd system
copy .env.example .env
docker compose up -d

cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

cd ..\frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Useful URLs after startup:

- Backend API docs: `http://127.0.0.1:8000/docs`
- Frontend: `http://127.0.0.1:5173`
- Analysis API prefix: `/api/v2/analysis`
- Case Workbench API prefix: `/api/v2/cases`

## Verification

```powershell
cd system\backend
python -m pytest tests -q

# Run the complete local prototype chain without changing the database or UI.
python scripts/prototype_acceptance.py

cd ..\frontend
npm run build
```

`npm run build` runs `vue-tsc -b` before the Vite production build.

The prototype acceptance output is intentionally non-claimable. It verifies
EventSnapshot wiring, strict Leiden artifact export, Propagation Analysis
fallback/abstain behavior, Student shadow behavior, and Teacher advisory
behavior. Research claims still require labels, temporal evaluation, approved
checkpoints, and reproducible metrics.

Runtime-specific dependency setup stays inside each vendored runtime. Do not move Playwright, news extraction, or Student Review runtime dependencies into the main backend package unless the runtime boundary itself changes.

## Runtime And Attribution

- `system/runtimes/social_runtime/` preserves the source lineage and license attribution for the social crawler runtime.
- `system/runtimes/news_runtime/` preserves the source lineage and license attribution for the news extraction runtime.
- Product code must call the vendored runtime boundaries, not upstream reference directories.
- Generated experiment outputs under `system/output/` and local research notes under `research-wiki/` are not part of product commits unless a task explicitly promotes a specific artifact.
