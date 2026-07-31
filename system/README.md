# CogGuard System

`system/` is the only active product system root. It contains the backend,
frontend, vendored runtimes, system-readable research packages, deployment
files, and tests.

Canonical capabilities:

- `Coordination Discover` and `Coordination Detect`
- `Propagation Analysis`
- `Risk Review`, including `Student Review` and `Teacher Review`
- `Crawler`

## Directory Layout

```text
system/
  backend/
    app/
      api/v1/                  legacy thin API mappings
      api/v2/                  current Analysis API surface
      core/
        analysis/              EventSnapshot, AnalysisRun, ports, SSE recovery
        coordination_baseline/ reference-style fallback baseline
        coordination/          legacy compatibility alias for coordination_baseline
        crawler/               Crawler interface, social/news/mock adapters
        propagation/           Propagation Analysis services and fallback logic
        review/                Risk Review, Student Review, Teacher Review, governance
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
    coordination_discover/     platform-generic discovery pipeline and artifacts
    coordination_detect/       public-label validation boundary
    propagation_analysis/      hindcast protocol, loaders, baselines, intervals
    review_teacher/            asynchronous Teacher Review DAG
  runtimes/
    social_runtime/            vendored social crawler runtime
    news_runtime/              vendored news extractor runtime
    review_student/            deployable Student Review runtime
```

Canonical semantic paths:

- `system/research/coordination_discover/`
- `system/research/coordination_detect/`
- `system/research/propagation_analysis/`
- `system/research/review_teacher/`
- `system/runtimes/review_student/`

## Analysis API

The current product entrypoint is `/api/v2/analysis/*`.

- `POST /api/v2/analysis/snapshots` builds and registers an immutable `EventSnapshot` from MongoDB content.
- `POST /api/v2/analysis/runs` creates an `AnalysisRun` for one snapshot and an ordered stage list.
- `POST /api/v2/analysis/runs/{run_id}/execute` calls the configured analysis ports.
- `GET /api/v2/analysis/runs/{run_id}` returns run state and stage outputs.
- `GET /api/v2/analysis/runs/{run_id}/events?after_id=<id>` is the REST recovery path.
- `GET /api/v2/analysis/runs/{run_id}/events/stream` streams backlog events and supports `Last-Event-ID`.

The application-facing ports are:

- `CoordinationEngine.analyze(snapshot, options)`
- `PropagationEngine.hindcast(snapshot, options)`
- `StudentRuntime.predict(case)`
- `TeacherJobPort.submit(case)`

## Runtime Boundary

Product code executes crawler and review runtime code from `system/runtimes/`.
Reference repositories may remain in the repository for provenance, license
review, and diffing, but they are not runtime roots.

Supported production crawl platforms are `weibo`, `douyin`, `xhs`, and `news`.
`mock_weibo` is test-only.

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
npm run type-check
npm run build
```

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
- Keep generated outputs out of commits unless an artifact is explicitly promoted with a manifest.
