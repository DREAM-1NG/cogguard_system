# CogGuard

CogGuard is a research-oriented product system for evidence-driven event review. The active runnable system is `system/`; upstream source trees remain reference boundaries for provenance and license review.

The current product narrative is:

```text
event -> evidence -> Coordination Discover -> Propagation Analysis -> Review -> Event Review Case -> governance action
```

## Active Capabilities

| Capability | Canonical implementation | Status |
| --- | --- | --- |
| Crawler | `system/backend/app/core/crawler/`, `system/runtimes/social_runtime/`, `system/runtimes/news_runtime/` | Internal social and news runtime boundaries are wired into product collection. |
| Event Review Case | `system/backend/app/services/review_case_service.py`, `system/backend/app/api/v2/review_cases.py`, `system/frontend/src/views/risk/index.vue` | Case list/detail, evidence annotations, review request, decision draft, confirmation, and activity stream are available. |
| Coordination Discover | `system/research/coordination_discover/` | CPU research pipeline, platform-generic evidence graph, strict Leiden, and backend fallback are runnable; no claimable research result is asserted here. |
| Coordination Detect | `system/research/coordination_detect/` | Public-label validation boundary exists; the current unlabeled event remains non-claimable. |
| Propagation Monitoring | `system/backend/app/core/propagation_monitoring/`, `system/research/propagation_analysis/` | Observed analysis, governed forecast, response compaction, caching, profiles, alerts, and Celery evaluation share one internal interface. |
| Review | `system/backend/app/core/review/`, `system/backend/app/services/review_case_orchestrator.py`, `system/research/review_student/`, `system/research/review_teacher/`, `system/runtimes/review_student/` | XLM-R Student inference is checkpoint-gated, Teacher output remains advisory, and confirmed decisions remain analyst-owned. |
| Social Bot Detection | `system/research/social_bot_detection/`, `system/backend/app/core/trained_bot_detection.py` | Internal transfer is runnable on Botection and the strict path is runnable on Cresci-2015, Cresci-2017, and Midterm-2018; public benchmark runs remain transfer results, not superiority claims. |

## Repository Map

| Path | Role |
| --- | --- |
| `system/` | Active product system: backend, frontend, vendored runtimes, research packages, deployment files, and tests. |
| `system/backend/` | FastAPI, Celery, database access, product services, and backend tests. |
| `system/frontend/` | Vue 3 and TypeScript case workspace. |
| `system/runtimes/` | Vendored executable runtimes used by product code. |
| `system/research/` | System-readable research packages consumed through explicit adapters. |
| `conductor/` | Product, technology, workflow, and active-track context for implementation sessions. |
| `doc/engineering/` | Long-lived engineering documentation, governance, maps, setup, roadmap, and log. |
| `doc/adr/` | Canonical ADR index and accepted durable decisions. |
| `doc/research/` | Research positioning and literature notes. |
| `aris/` | Historical research workspace. Its physical names are not canonical product vocabulary. |
| `MediaCrawler-main/`, `NewsCrawler-main/`, `CooRTweet-master/` | Reference boundaries only; product runtime code must not execute from these directories. |

## Naming Sources

- `UBIQUITOUS_LANGUAGE.md` is the canonical glossary.
- `doc/engineering/system-governance.md` is the normative naming and package-boundary policy.
- `doc/adr/index.md` records current ADR status and supersession.
- `conductor/index.md` records the active product, technology, workflow, and track context.

New code and current documentation must use formal capability names: `Coordination Discover`, `Coordination Detect`, `Propagation Analysis`, `Review`, and `Event Review Case`.

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
- Review case API prefix: `/api/v2/review-cases`

## Verification

```powershell
cd system\backend
python -m pytest tests -q

# Run the complete local prototype chain without changing the database or UI.
python scripts/prototype_acceptance.py

cd ..\frontend
npm run build
```

Backend dependencies are edited in `system/backend/pyproject.toml` and exported
from the frozen `uv.lock` into `requirements.txt`. Generated outputs, caches,
Playwright captures, local experiments, and model artifacts are not release files.

`npm run build` runs `vue-tsc -b` before the Vite production build.

The prototype acceptance output is intentionally non-claimable. It verifies EventSnapshot wiring, strict Leiden behavior, propagation fallback/abstain behavior, review advisory behavior, and confirmation boundaries. Research claims still require labels, temporal evaluation, and approved runtime evidence.

Runtime-specific dependency setup stays inside each vendored runtime. Do not move Playwright or news extraction dependencies into the main backend package unless the runtime boundary itself changes.

The analyst-facing frontend remains business-first: it shows event status,
evidence sufficiency, preliminary and advisory findings, required actions, and
confirmed decisions. Model activation, artifact verification, queue recovery,
and rollback are authenticated backend control-plane operations documented in
[ADR 0009](doc/adr/0009-durable-review-and-model-governance-boundary.md).

## Runtime And Attribution

- `system/runtimes/social_runtime/` preserves the source lineage and license attribution for the social crawler runtime.
- `system/runtimes/news_runtime/` preserves the source lineage and license attribution for the news extraction runtime.
- Product code must call the vendored runtime boundaries, not upstream reference directories.
- Generated experiment outputs under `system/output/` and local research notes under `research-wiki/` are not part of product commits unless a task explicitly promotes a specific output.
