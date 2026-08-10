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
        propagation/           Propagation Analysis services and fallback logic
        review/                Event Review Case orchestration, advisory routing, governance
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
    propagation_analysis/      hindcast protocol, loaders, baselines, intervals
    review_teacher/            internal review research DAG
    social_bot_detection/      internal trainable BotRHG Weibo transfer
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

## Case Workspace

The current product workspace is `/api/v2/review-cases/*`.

- `GET /api/v2/review-cases/latest` returns the latest case.
- `GET /api/v2/review-cases/{case_id}` returns case detail.
- `GET /api/v2/review-cases/{case_id}/evidence` returns assessment-group counts and one
  cursor-paginated evidence group. It accepts `assessment`, `cursor`, and `limit`; the
  default is the first 40 unresolved items.
- `POST /api/v2/review-cases/{case_id}/review-requests` requests an internal review advisory.
- `PUT /api/v2/review-cases/{case_id}/decision-draft` saves a draft decision.
- `POST /api/v2/review-cases/{case_id}/decisions/confirm` confirms an immutable decision.
- `GET /api/v2/review-cases/{case_id}/activities` returns the business activity stream.
- `GET /api/v2/review-cases/{case_id}/events/stream` streams case events with `Last-Event-ID` recovery.

The application-facing ports are the `ReviewCaseService` methods that power those routes:

- `latest()`
- `search()`
- `detail(case_id)`
- `evidence(case_id, assessment, cursor, limit)`
- `request_review(case_id, request, actor)`
- `add_annotation(case_id, request, actor)`
- `save_draft(case_id, request, actor)`
- `confirm_decision(case_id, request, actor)`
- `activities(case_id, after_id, limit)`

## Account Profile

The NLPCC TwiBot-20 checkpoint is available separately as a hash-verified
research runtime under `artifacts/social_bot_detection/nlpcc_twibot20_seed3`.
It is fixed-graph and transductive: it only queries the deployed TwiBot-20
node set and is never eligible for the Chinese online account-model Active
Pointer. See `doc/research/twibot20-nlpcc-runtime.md` for the contract and
selection evidence.

Formal detector comparison follows [the social-bot benchmark protocol](../doc/research/social-bot-benchmark-protocol.md):
TwiBot-20 is the primary graph benchmark; Cresci-2015, Cresci-2017, and
Midterm-2018 are independently reported adaptation datasets. The historical
Botection Weibo transfer corpus is legacy-only and cannot select a model or
support an online deployment claim.

`GET /api/v1/accounts/profiles` returns business-facing account profiles for
the selected corpus. Each row contains a collected nickname, platform, activity
context, and an **Account Finding** projected from the trained account detector.
The profile endpoint does not expose legacy rule-derived scores, detector
probabilities, runtime modes, or support-graph details. Results are cached by
the selected corpus fingerprint and active account-model identity, so account
details reuse the same finding until either the source corpus or model changes.

Account detection also has an analyst-in-the-loop active-learning control plane:

- `POST /api/v1/accounts/active-learning/batches` creates a stratified label batch from collected account cases.
- `GET /api/v1/accounts/label-queue` lists queued account cases for analyst review.
- `POST /api/v1/accounts/labels` records observable behavior labels only.
- `POST /api/v1/accounts/labels/{label_id}/adjudicate` promotes or rejects a submitted label.
- `POST /api/v1/accounts/training/candidates` registers a shadow model candidate trained from approved labels.
- `POST /api/v1/accounts/models/{model_version}/evaluation-jobs` runs the normal system-owned frozen-holdout evaluation path.
- `GET /api/v1/accounts/evaluation-jobs/{job_id}` returns durable evaluation state and signed result identity.
- `POST /api/v1/accounts/models/{model_version}/activate` applies frozen-holdout, leakage, calibration, shadow-run, and dual-approval gates before activation.
- `GET /api/v1/accounts/models/active` reports `available`, `missing`, or `invalid` pointer resolution without hiding artifact failures.
- `POST /api/v1/accounts/models/{model_version}/rollback` records a governed manual rollback; monitor-driven automatic rollback is limited to hard runtime failures and the previous approved model.

The active-learning loop is a label-efficiency and governance pipeline. It never treats model output as a gold label, and it keeps frozen evaluation data outside the selected labeling pool.

The normal evaluator is system-owned: it locks candidate and Frozen Holdout identity, rejects any recorded training-export overlap, releases database locks during inference, rechecks the holdout fingerprint, and writes an `ACCOUNT_MODEL_EVALUATION_HMAC_SECRET` HMAC manifest bound to candidate version, artifact SHA-256, evaluation run, protocol fingerprint, and raw audit fingerprint. The direct writeback route is compatibility/recovery only. Calibration is derived only from labeled evaluator audits; candidate-provided `ece` or `calibration` fields are discarded. Production must set `ACCOUNT_MODEL_BOOTSTRAP_MODE=disabled`, configure a distinct evaluator secret of at least 32 characters, and create a governed MySQL Active Pointer before serving detection. A non-production local setup may set `ACCOUNT_MODEL_BOOTSTRAP_MODE=local_legacy` to create a persisted `local_bootstrap_unreviewed` pointer from the legacy checkpoint; no request path infers a checkpoint directly when the pointer is absent.

Governed bundles use the canonical research-package verifier. Activation and
rollback require `deployment={"eligible": true, "status": "eligible"}`; the
runtime takes source schema from the verified manifest and checks the bundle's
encoder, feature schema, and calibration against the detector checkpoint before
loading. Checkpoint deserialization uses PyTorch's weights-only boundary, and
the process keeps at most the current Active Pointer runtime in memory.

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

The default Windows startup path is the optimized delivery path. It applies
the idempotent MongoDB indexes, starts the backend without the development
reloader, waits for API readiness, builds the frontend, and serves it through
the static `production-ui` profile:

```powershell
cd system
Copy-Item .env.example .env
powershell.exe -ExecutionPolicy Bypass -File .\start-system.ps1
```

It opens the same authenticated product on `http://127.0.0.1:5173`. The
default build command is `npm run build`; it typechecks, emits a Vite manifest,
generates the delivery preload plan, and verifies both budgets and preload
policy. After login, the delivery plan immediately prepares the dashboard shell
and map asset. Other route modules load when the operator hovers or
focuses their navigation item. This intentionally avoids preloading the
coordination graph, propagation analysis, or case evidence payload before an
operator requests them.

When the local demo credentials are configured, the default startup preloads
authenticated business data after the backend is ready and before the frontend
is exposed:

```powershell
$env:COGGUARD_DEMO_USERNAME = 'demo_analyst'
$env:COGGUARD_DEMO_PASSWORD = '<local-demo-password>'
powershell.exe -ExecutionPolicy Bypass -File .\start-system.ps1
```

The warmup uses real APIs and writes only redacted timings to
`system/output/demo-warmup/`. It activates automatically when both
`COGGUARD_DEMO_USERNAME` and `COGGUARD_DEMO_PASSWORD` are configured. Add
`-DemoWarmupStrict` to fail startup on an optional warmup route, or
`-SkipDemoWarmup` to bypass the demo precompute. The first run materializes versioned server-side
analysis projections in the process cache and Redis; repeated page requests
reuse them without rerunning graph construction, account detector inference, or
the requested evidence-page projection. It warms the default review page rather
than every evidence page. See
`../doc/engineering/performance-operations.md` for cache identity, the measured
baseline, and the remaining optimization gates.

Use the development frontend only while changing frontend source:

```powershell
cd system
powershell.exe -ExecutionPolicy Bypass -File .\start-system.ps1 -DevelopmentFrontend
```

For manual component-level development, the equivalent commands remain:

```powershell
cd system
docker compose up -d mysql mongodb redis

cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

cd ..\frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

`start-system.ps1` starts a dedicated hidden account-model Celery worker for
`account_training,account_evaluation` with `--concurrency 1 --pool solo`. Its
stdout and stderr are recorded under
`system/logs/account-training-worker-*.out.log` and `.err.log`. This worker is
required for governed DAPT, detector retraining, and Frozen Holdout evaluation;
the shared queue consumer serializes GPU work. It is intentionally
separate from the crawl, analysis, and review workers so GPU training cannot
consume their worker slots. A process-bound GPU fence also rejects concurrent
account-model work from an independently started local worker. Evaluation jobs
carry a transactional dispatch intent; the backend publisher and Celery Beat
claim pending or expired leases and token-finalize broker publication, so a
broker failure does not leave a committed evaluation permanently stranded or
replay every queued job each minute.

On the RTX 4060 deployment, set `ACCOUNT_ACQUISITION_DEVICE=cuda`. DAPT uses
BF16 when the CUDA device supports it and otherwise falls back to
FP16 with GradScaler; the resolved precision is recorded in the encoder
artifact provenance. The checked-in `.env.example` intentionally remains
`cpu` so non-GPU development environments fail predictably rather than
assuming CUDA.

Separately operated workers:

```powershell
cd system\backend
celery -A app.celery_app worker --loglevel=info -Q crawl,analysis,review
celery -A app.celery_app worker --loglevel=info -Q account_training,account_evaluation --concurrency 1 --pool solo --hostname account-training@%h
celery -A app.celery_app beat --loglevel=info --schedule ..\logs\account-training-beat.schedule
```

## Delivery Performance Profile

`start-system.ps1` is the canonical default for local and LAN delivery. It
starts the static frontend profile after the backend health endpoint is ready.
Use the explicit Compose command below only when operating the frontend
separately from the helper:

```powershell
cd system
docker compose --profile production-ui up -d --build frontend_static
```

The profile serves compressed, content-addressed assets with immutable caching,
keeps HTML and `/api/*` uncached, and proxies API calls to the existing backend
at `BACKEND_ORIGIN` (default: `http://host.docker.internal:8000`). Do not run
Vite and `frontend_static` on port `5173` at the same time.

The startup helper applies the named MongoDB query indexes by default after
MongoDB is reachable. For a separate maintenance run, preview then apply the
operation manually:

```powershell
.\ops\Apply-MongoPerformanceIndexes.ps1 -DryRun
.\ops\Apply-MongoPerformanceIndexes.ps1
```

The operation creates only missing, named indexes and never drops or rebuilds
an existing index. Server-side analysis projections are versioned below the
HTTP layer and are configured with `ANALYSIS_RESULT_CACHE_*`; they never cache
credentials or tokens. See `../doc/engineering/performance-operations.md` for
request cache policy, maintenance guidance, and remaining product-code work.
The current index definition contains 11 indexes, including event-scoped
crawl_job_id markers used to invalidate dashboard and other ingestion-aware
projections without reading the full corpus on every repeat request.

## Verification

```powershell
cd system\backend
python -m pytest tests -q

cd ..\frontend
npm run build
```

`npm run build` runs `vue-tsc -b`, the Vite production build, delivery preload
manifest generation, and static delivery verification.

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
- Use `../doc/engineering/performance-operations.md` for static-delivery,
  MongoDB index, and browser-trace operations; keep its baseline current when
  changing route loading or data-volume behavior.

Production deployments must set `BACKEND_ENV=production`, a random `JWT_SECRET_KEY`, `DEFAULT_ADMIN_PASSWORD`, and non-empty MySQL, MongoDB, and Redis credentials. The system has no preview authentication bypass; local and LAN deployments use the same login flow.

## Internal Transfer Boundary

The internal social bot transfer boundary lives under `system/research/social_bot_detection/`. The local and strict paths stay text-only on the current corpora, and they remain transfer results rather than superiority claims.
The same research package now also owns account active-learning acquisition, approved-label corpus export, and active-round evaluation gates for Chinese account detection.
