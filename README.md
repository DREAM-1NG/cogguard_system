# CogGuard

CogGuard is a research-oriented product system for evidence-driven social media analysis. The active runnable system is `system/`; upstream source trees remain reference boundaries for provenance and license review.

The current product narrative is:

```text
event -> evidence -> Coordination Discover -> Propagation Analysis -> Risk Review -> governance action
```

## Active Capabilities

| Capability | Canonical implementation | Status |
| --- | --- | --- |
| Crawler | `system/backend/app/core/crawler/`, `system/runtimes/social_runtime/`, `system/runtimes/news_runtime/` | Internal social and news runtime boundaries are wired into product collection. |
| Analysis | `system/backend/app/core/analysis/`, `system/backend/app/api/v2/analysis.py` | `EventSnapshot`, `AnalysisRun`, REST recovery, and SSE event streaming are available. |
| Coordination Discover | `system/research/coordination_discover/` | Platform-generic evidence graph, temporal discovery, strict Leiden artifact support, and backend fallback integration are available. |
| Coordination Detect | `system/research/coordination_detect/` | Public-label validation boundary exists; unlabeled local events must report missing-label status. |
| Propagation Analysis | `system/research/propagation_analysis/`, `system/backend/app/core/propagation/` | Hindcast protocol, baseline registry, split-conformal interval support, and live fallback are wired. |
| Risk Review | `system/backend/app/core/review/`, `system/research/review_teacher/`, `system/runtimes/review_student/` | Student Review and Teacher Review seams are wired; approved checkpoints and analyst canonical verdict flow remain governed activation work. |

## Repository Map

| Path | Role |
| --- | --- |
| `system/` | Active product system: backend, frontend, vendored runtimes, research packages, deployment files, and tests. |
| `system/backend/` | FastAPI, Celery, database access, product services, and backend tests. |
| `system/frontend/` | Vue 3 and TypeScript management UI. Frontend display is not part of the current governance cleanup. |
| `system/runtimes/` | Vendored executable runtimes used by product code. |
| `system/research/` | System-readable research packages consumed through explicit adapters. |
| `doc/engineering/` | Long-lived engineering documentation, governance, maps, setup, roadmap, and log. |
| `doc/research/` | Research positioning and literature notes. |
| `aris/` | Historical research workspace. Its physical names are not canonical product vocabulary. |
| `MediaCrawler-main/`, `NewsCrawler-main/`, `CooRTweet-master/` | Reference boundaries only; product runtime code must not execute from these directories. |

## Naming Sources

- `UBIQUITOUS_LANGUAGE.md` is the canonical glossary.
- `doc/engineering/system-governance.md` is the normative naming and package-boundary policy.
- `doc/engineering/project-map.md` describes repository boundaries and default edit ownership.

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

## Verification

```powershell
cd system\backend
python -m pytest tests -q

cd ..\frontend
npm run type-check
npm run build
```

Runtime-specific dependency setup stays inside each vendored runtime. Do not move Playwright, news extraction, or Student Review runtime dependencies into the main backend package unless the runtime boundary itself changes.

## Runtime And Attribution

- `system/runtimes/social_runtime/` preserves the source lineage and license attribution for the social crawler runtime.
- `system/runtimes/news_runtime/` preserves the source lineage and license attribution for the news extraction runtime.
- Product code must call the vendored runtime boundaries, not upstream reference directories.
- Generated experiment outputs under `system/output/` and local research notes under `research-wiki/` are not part of product commits unless a task explicitly promotes a specific artifact.
