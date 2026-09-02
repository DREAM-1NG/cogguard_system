# CogGuard System

`system/` is the only active product system root. It contains the backend, frontend, vendored runtimes, system-readable research packages, deployment files, and tests.

Canonical capabilities:

- `Event Review Case`
- `Coordination Discover` and `Coordination Detect`
- `Propagation Analysis`
- `Review`
- `Crawler`

## Directory Layout

```text
system/
  backend/
    app/
      api/v1/                  legacy thin compatibility layer
      api/v2/                  current product API surface
      core/
        analysis/              internal snapshot and diagnostics boundary
        coordination_baseline/ reference-style fallback baseline
        coordination/          legacy compatibility alias for coordination_baseline
        crawler/               Crawler interface, social/news/mock adapters
        propagation/           observed propagation projection, services, and fallback logic
        review/                Event Review Case orchestration, Review/Teacher/Student helpers, advisory routing, governance
        risk/                  legacy compatibility alias for review
      models/                  SQLAlchemy and persisted domain records
      schemas/                 Pydantic request and response schemas
      services/                application services
      tasks/                   Celery tasks
      db/                      MySQL, MongoDB, and Redis clients
      utils/                   shared helpers
    scripts/                   explicit backend and research utility entrypoints
    tests/                     backend unit, contract, integration, and governance tests
  frontend/                    Vue 3 and TypeScript UI
  research/
    coordination_discover/     platform-generic discovery pipeline and outputs
    coordination_detect/       public-label validation boundary
    propagation_analysis/      deployed sequence model, checkpoint, loaders, hindcast, and benchmarks
    review_teacher/            asynchronous Teacher Review research DAG
    social_bot_detection/     internal trainable BotRHG social-bot transfer, including Weibo
  runtimes/
    social_runtime/            vendored social crawler runtime
    news_runtime/              vendored news extractor runtime
    review_student/            internal review runtime
```

Canonical semantic paths:

- `system/research/coordination_discover/`
- `system/research/coordination_detect/`
- `system/research/propagation_analysis/`
- `system/research/review_teacher/`
- `system/research/social_bot_detection/`
- `system/runtimes/review_student/`

These paths are runtime/research-only boundaries; do not surface them in product copy unless the path itself is the point of the discussion.

Propagation is split into two product boundaries. `GET /api/v1/propagation/analyze`
performs observed-only path, object, role, timeline, provenance, and stability
analysis. `POST /api/v1/propagation/model-event-predict` applies a strict
timezone-aware observation cutoff and runs the system-owned Twitter
`PropagationSequenceJointModel` checkpoint for monotonic size/trend prediction
and identity-mapped next-hop reactivation ranking. Missing model/data states
abstain; the public event endpoint does not use the legacy speed/acceleration
runtime. Deployment is verified, while formal multi-seed performance validation
remains a separate research requirement.

## Case Workspace

The current product workspace is `/api/v2/review-cases/*`.

- `GET /api/v2/review-cases/latest` returns the latest case.
- `GET /api/v2/review-cases/{case_id}` returns case detail.
- `GET /api/v2/review-cases/{case_id}/evidence` returns grouped evidence and annotations.
- `POST /api/v2/review-cases/{case_id}/review-requests` requests an internal review advisory.
- `PUT /api/v2/review-cases/{case_id}/decision-draft` saves a draft decision.
- `POST /api/v2/review-cases/{case_id}/decisions/confirm` confirms an immutable decision.
- `GET /api/v2/review-cases/{case_id}/activities` returns the business activity stream.
- `GET /api/v2/review-cases/{case_id}/events/stream` streams case events with `Last-Event-ID` recovery.

The application-facing ports are the `ReviewCaseService` methods that power those routes:

- `latest()`
- `search()`
- `detail(case_id)`
- `evidence(case_id)`
- `request_review(case_id, request, actor)`
- `add_annotation(case_id, request, actor)`
- `save_draft(case_id, request, actor)`
- `confirm_decision(case_id, request, actor)`
- `activities(case_id, after_id, limit)`

### Analysis Run Diagnostics

The internal Analysis Run diagnostic entrypoint remains `/api/v2/analysis/*`.

- `POST /api/v2/analysis/snapshots` builds and registers an immutable `EventSnapshot` from MongoDB content.
- `POST /api/v2/analysis/runs` creates an `AnalysisRun` for one snapshot and an ordered stage list.
- `POST /api/v2/analysis/runs/{run_id}/execute` calls the configured analysis ports.
- `GET /api/v2/analysis/runs/{run_id}` returns run state, stage outputs, and an `artifact_manifest` with data fingerprint, model/checkpoint references, fallback reason, and claimability. Fallback, shadow, advisory-only, and missing-checkpoint stages are non-claimable.
- `GET /api/v2/analysis/runs/{run_id}/events?after_id=<id>` is the REST recovery path.
- `GET /api/v2/analysis/runs/{run_id}/events/stream` streams backlog events and supports `Last-Event-ID`.

The application-facing analysis ports are:

- `CoordinationEngine.analyze(snapshot, options)`
- `PropagationEngine.hindcast(snapshot, options)`
- `StudentRuntime.predict(case)`
- `TeacherJobPort.submit(case)`

When `requested_stages` is omitted, a prototype run executes
`coordination_discover`, `propagation_analysis`, `student`, and `teacher` in
that order. A narrower list remains available for focused diagnostics.

## Internal Diagnostics

The internal diagnostic boundary remains under `/api/v2/governance/*` for authenticated reads, approvals, feedback, and governance actions.

- `/api/v2/governance` reads are diagnostic only and stay behind authenticated access.
- Model governance remains a backend control-plane concern. Candidate approvals are recorded by the authenticated administrator at `/api/v2/governance/models/{model_version_id}/approvals`; production activation requires two distinct persisted approvals, while local `auto` mode keeps one accountable operator. The main frontend does not expose these controls.
- Teacher dispatch is local-inline only in local `auto` mode. Production `auto` mode requires Celery and persists dispatch or execution failures for recovery.

## Prototype Acceptance

From `system/backend/`, run:

```powershell
python scripts/prototype_acceptance.py
```

The command uses an isolated fixture and temporary working directory. It does not create labels, activate any capability, persist database rows, or modify the frontend. Expected output explicitly reports strict Leiden, propagation fallback/abstain, and review advisory/confirmation boundaries.

## Runtime Boundary

Product code executes crawler and review runtime code from `system/runtimes/`. Reference repositories may remain in the repository for provenance, license review, and diffing, but they are not runtime roots.

Supported production crawl platforms are `weibo`, `douyin`, `xhs`, and `news`. `mock_weibo` is test-only.

Useful crawler configuration:

```dotenv
MEDIACRAWLER_LOGIN_TYPE=qrcode
MEDIACRAWLER_COOKIES=
MEDIACRAWLER_PROXY=http://127.0.0.1:7897
MEDIACRAWLER_NODE_DIR=D:/node
MEDIACRAWLER_GET_SUB_COMMENTS=true
MEDIACRAWLER_MAX_COMMENTS_PER_POST=200
MEDIA_DOWNLOAD_ROOT=./media
```

External-root settings from earlier designs are not product runtime inputs.

## Local Startup

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

Optional Celery worker for queued crawl and review jobs:

```powershell
cd system\backend
celery -A app.celery_app worker --loglevel=info -Q crawl,analysis,review
```

## Verification

```powershell
cd system\backend
python -m pytest tests -q

cd ..\frontend
npm run build
```

`npm run build` runs `vue-tsc -b` before the Vite production build.

Useful targeted gates:

```powershell
cd system\backend
python -m pytest tests/test_system_naming_governance.py -q
python -m pytest tests/test_analysis_executor.py tests/test_analysis_registry.py -q
python -m pytest tests/test_coordination_local_discover_detect_script.py -q
```

## Documentation Contract

- Update `../UBIQUITOUS_LANGUAGE.md` when domain terms change.
- Update `../doc/engineering/system-governance.md` when package boundaries or public interfaces change.
- Update `../doc/engineering/development-log.md` after meaningful code or documentation work.
- Keep generated outputs out of commits unless a specific output is explicitly promoted with a manifest.

Production deployments must set `BACKEND_ENV=production`, a random `JWT_SECRET_KEY`, `DEFAULT_ADMIN_PASSWORD`, and non-empty MySQL, MongoDB, and Redis credentials. The system has no preview authentication bypass; local and LAN deployments use the same login flow.

## Internal Transfer Boundary

The internal social bot transfer boundary lives under `system/research/social_bot_detection/`. The local and strict paths stay text-only on the current corpora, and they remain transfer results rather than superiority claims.
