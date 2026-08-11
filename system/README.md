# CogGuard System

`system/` is the only active product system root. It contains the backend,
frontend, vendored runtimes, system-readable research packages, deployment
files, and tests.

Canonical capabilities:

- `Coordination Discover` and `Coordination Detect`
- `Propagation Analysis`
- `Risk Review`, including `Student Review` and `Teacher Review`
- `Case Workbench`
- `Crawler`

## Directory Layout

```text
system/
  backend/
    app/
      api/v1/                  legacy thin API mappings
      api/v2/                  current Analysis and Case Workbench API surface
      core/
        analysis/              EventSnapshot, AnalysisRun, semantic enrichment, ports, SSE recovery
        coordination_baseline/ reference-style fallback baseline
        coordination/          legacy compatibility alias for coordination_baseline
        crawler/               Crawler interface, social/news/mock adapters
        propagation/           observed propagation projection and compatibility helpers
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
    propagation_analysis/      deployed sequence model, checkpoint, loaders, benchmarks
    review_teacher/            asynchronous Teacher Review DAG
    social_bot_detection/       internal trainable BotRHG social-bot transfer
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
- `system/research/social_bot_detection/`
- `system/runtimes/review_student/`

The social-bot research package supports independent account-level transfer
runs on Botection, Cresci-2015, Cresci-2017, and Midterm-2018. It uses the
repository-local RoBERTa-family checkpoint configured by the experiment and
records source-label provenance, archive fingerprints, training configuration,
checkpoint hashes, predictions, and reference metrics. The public corpus
experiments are text-only transfer implementations; their outputs are not
publication claims of superiority over strong text baselines.

Propagation is split into two product boundaries. `GET /api/v1/propagation/analyze`
performs observed-only path, object, role, timeline, provenance, and stability
analysis. `POST /api/v1/propagation/model-event-predict` applies a strict
timezone-aware observation cutoff and runs the system-owned Twitter
`PropagationSequenceJointModel` checkpoint for monotonic size/trend prediction
and identity-mapped next-hop reactivation ranking. Missing model/data states
abstain; the public event endpoint does not use the legacy speed/acceleration
runtime. Deployment is verified, while formal multi-seed performance validation
remains a separate research requirement.

## Analysis API

The current product entrypoint is `/api/v2/analysis/*`.

- `POST /api/v2/analysis/snapshots` builds and registers an immutable `EventSnapshot` from MongoDB content.
- `POST /api/v2/analysis/runs` creates an `AnalysisRun` for one snapshot and an ordered stage list.
- `POST /api/v2/analysis/runs/{run_id}/execute` calls the configured analysis ports.
  - `GET /api/v2/analysis/runs/{run_id}` returns run state, stage outputs, and an `artifact_manifest` with data fingerprint, model/checkpoint references, fallback reason, and claimability. Fallback, shadow, advisory-only, and missing-checkpoint stages are non-claimable.
- `GET /api/v2/analysis/runs/{run_id}/events?after_id=<id>` is the REST recovery path.
- `GET /api/v2/analysis/runs/{run_id}/events/stream` streams backlog events and supports `Last-Event-ID`.

The application-facing ports are:

- `CoordinationEngine.analyze(snapshot, options)`
- `PropagationEngine.hindcast(snapshot, options)`
- `StudentRuntime.predict(case)`
- `TeacherJobPort.submit(case)`

When `requested_stages` is omitted, a prototype run executes
`coordination_discover`, `propagation_analysis`, `student`, and `teacher` in
that order. A narrower list remains available for focused diagnostics.
`semantic_enrichment` is an explicit opt-in stage used by the Case Workbench and
does not alter Coordination, Propagation, Student, Teacher, or risk scores.

## Case Workbench API

The fast prototype Case Workbench entrypoint is `/api/v2/cases`.

- `GET /api/v2/cases?event_id=trump_visit_2026_05_21` lists the demo case.
- `GET /api/v2/cases/case_trump_visit_2026_05_21` returns the dense case
  projection used by the frontend page.

The MVP is a read projection over the archived Trump-visit demonstration event.
It binds CCTV News as the Primary Claim, Xinhua as a Supplementary Claim,
includes `semantic_enrichment` artifacts with `candidate_unvalidated` model
status, and represents missing same-event platform evidence as a Platform Gap
blocker instead of inventing data. Persistent Case records, approval workflows,
formal report file serving, and strict closeout gates remain future work.

## Prototype Acceptance

From `system/backend/`, run:

```powershell
python scripts/prototype_acceptance.py
```

The command uses an isolated fixture and temporary artifact directory. It
does not create labels, activate models, persist database rows, or modify the
frontend. Expected output explicitly reports strict Leiden, propagation
fallback/abstain, Student `shadow_untrained`, and Teacher advisory status.

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
npm run build
```

`npm run build` runs `vue-tsc -b` before the Vite production build.

Useful targeted gates:

```powershell
cd system\backend
python -m pytest tests/test_system_naming_governance.py -q
python -m pytest tests/test_analysis_executor.py tests/test_analysis_registry.py -q
python -m pytest tests/test_semantic_enrichment.py tests/test_case_workbench_mvp.py tests/test_case_frontend_mvp_contract.py -q
python -m pytest tests/test_coordination_local_discover_detect_script.py -q
```

## Documentation Contract

- Update `../UBIQUITOUS_LANGUAGE.md` when domain terms change.
- Update `../doc/engineering/system-governance.md` when package boundaries or public interfaces change.
- Update `../doc/engineering/development-log.md` after meaningful code or documentation work.
- Keep generated outputs out of commits unless an artifact is explicitly promoted with a manifest.

Production deployments must set `BACKEND_ENV=production`, a random
`JWT_SECRET_KEY`, `DEFAULT_ADMIN_PASSWORD`, and non-empty MySQL, MongoDB, and
Redis credentials. Preview authentication is disabled by default and is only
allowed for an explicitly configured local token.

Model governance is fail-closed: a model version needs a valid SHA-256 digest
and a locally readable artifact, or an explicitly implemented deployment
resolver, before activation. Remote `http(s)`, `s3`, and `gs` URIs are recorded
as candidates but are not treated as verified by the current backend.

## Weibo Bot Detection Transfer

The NLPCC BotRHG transfer implementation is internalized under
`system/research/social_bot_detection/`. The legacy transfer proxy remains
available for Botection, and the strict NLPCC-aligned path can be selected
for Cresci-2015, Cresci-2017, and Midterm-2018 with `--strict-method`. Both
paths use a local Chinese Transformer, a trainable low-order detector,
target-centered KNN support hyperedges, label-free reliability routing, and
selective residual correction. The Botection corpus currently provides account
labels and text only; property fields and an explicit social graph are
recorded as unavailable, so this remains a text-only Weibo transfer path and
not an exact reproduction of the paper benchmark.

Train with the local model cache:

```powershell
cd system
$env:PYTHONPATH='.'
python -m research.social_bot_detection.cli `
  --strict-method `
  --dataset-name cresci_2015 `
  --dataset-root G:\CISCN\_tmp\Botection `
  --output-dir .\output\botrhg_strict `
  --text-model-path G:\CISCN\hf_models\models--hfl--chinese-roberta-wwm-ext\snapshots\5c58d0b8ec1d9014354d691c538661bf00bfdb44 `
  --device cpu --base-epochs 3 --correction-epochs 3
```

The backend only uses `checkpoint.pt` when it is present and its manifest
fingerprint matches `BOTRHG_DATA_FINGERPRINT`; otherwise the account API
returns the explicitly non-claimable deterministic fallback.
