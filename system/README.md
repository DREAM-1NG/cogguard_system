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
    coordination_discover/     evidence-constrained system Discovery plus research candidates
    coordination_detect/       SocGFM primary runtime artifact and shadow public-label baselines
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

## Coordination Boundary

The current product Coordination path is the AnalysisExecutor runtime:
conservative cross-platform resolution, evidence-constrained Coordination
Discover, and group-level Coordination Detect. Discovery stays on
`coordination-evidence-runtime-v2`; MAGNN/GFM variants are not the product
Discovery decision path.

Coordination Detect uses `socgfm_cross_attention` as the primary artifact type.
If the active `coordination_detection` pointer is absent or not SocGFM, the
runtime returns `model_unavailable` and does not fall back to the older
learned/logistic classifier or a heuristic rule. The learned classifier remains
shadow/baseline-only for audit, rollback comparison, and public dataset tables.

`system/backend/app/services/coordination_model_service.py` is a legacy
dataset registry and Coordination Archive Replay surface for historical
MAGNN/Leiden/SBERT results. Its outputs are useful for comparison and
visualization, but they are not the current system mainline. Legacy account
Detection scores from this surface are exposed only as `archive_detection_*`
audit fields; frontend key-node ranking and score filtering use Discovery
evidence scores. `magnn_leiden_hybrid_discovery` is registered only in offline
research runners until it beats the evidence-constrained Discovery mainline and
retained baselines under the same protocol.

Some historical runs have persisted real member predictions but no materialized
group-level `coordination_detection` block. The service can reconstruct a
traceable group evidence projection from those predictions and the stored
community membership. If predictions are missing, it returns
`model_unavailable` instead of making up a verdict. The result cache is keyed
with `coordination-latest-result-v3` to prevent an older empty projection from
being served after this compatibility repair. High-risk groups are analyst
prompts, never Confirmed Decisions.

## Case Workspace

The current product workspace is `/api/v2/review-cases/*`.

- `GET /api/v2/review-cases/latest` returns the latest case.
- `GET /api/v2/review-cases/{case_id}` returns case detail.
- `GET /api/v2/review-cases/{case_id}/teacher-audit` returns the bounded,
  read-only review audit projection: execution state, role stages, traceable
  source excerpts, retrieval queries, and short rationale capsules when
  persisted. It never returns raw prompts, full chain-of-thought, provider
  credentials, or model confidence targets.
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
- `teacher_audit(case_id)`
- `evidence(case_id, assessment, cursor, limit)`
- `request_review(case_id, request, actor)`
- `add_annotation(case_id, request, actor)`
- `save_draft(case_id, request, actor)`
- `confirm_decision(case_id, request, actor)`
- `activities(case_id, after_id, limit)`

## Claim Response Landscape

The **主张回应图谱** tab in `/propagation` is a read-only propagation
projection. It aligns an allowlisted authority-source account and bound primary
claim with observed official publications and comment-thread responses. A
path's semantic readout is shown only when every exact post/comment evidence
reference maps to the same ready, non-fallback semantic artifact. The drawer
does not infer paths from text similarity, account names, or graph adjacency,
and semantic evidence does not alter Coordination, Propagation, Review, or
risk scores.

When a direct comment thread lacks a calculated network downstream-reach
metric, the page explicitly shows that it is unavailable instead of displaying
zero. The available semantic fields are sentiment, raw NLI stance, keywords,
topics, entities, platform/time scope, and the exact evidence references.

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

For the default demonstration event, warmup also materializes the propagation
forecast cache at the page's `50%` observation ratio and `Top-10` budget. The
**趋势预测** tab then reads that persisted result on first visit and does not
wait for model inference. Use **刷新趋势预测** only when an analyst needs an
explicit recomputation for the current event scope.

The same tab loads a separate, evidence-only timeline from
`GET /api/v1/propagation/model-event-timeline`. It opens at the event's
deterministic densest six-hour active period with minute-level aggregation.
Operators can switch to **24小时**, **7天**, or **全部** and use the chart's
slider or in-chart zoom. Date-backed observed and retrospective evidence are
kept separate from the model chart: model points remain labelled as relative
steps because the checkpoint does not provide a calibrated wall-clock horizon.

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

## Review Student and MARO Teacher boundary

The Review runtime has two separate delivery lines:

```text
Review Student: synchronous XLM-R text analysis -> preliminary Review output
Review Teacher: analyst Review API -> MARO-compatible advisory audit
```

The Teacher chain is task-scoped. Interpersonal harm uses the harm expert and
active policy context; claim deception uses claim eligibility, EvidenceRAG,
and source-bound evidence. Complex cases add QuestionReflection and at most
two targeted expert responses before the Judge. Simple cases run necessary
experts and one Judge only. Countermeasure is an explicit post-Judge option.

For claim deception, the ClaimEvidenceAgent assesses claim applicability before
any factual query is built. `not_assessed`, `no_verifiable_claim`, provider
failure, and no relevant retrieval evidence are audit states, not
`insufficient`. The Judge exposes `misinfo_claim_risk` only when a completed,
traceable evidence relation is available; otherwise it emits `unavailable`.

Student input is text-only in this stage. Raw image/video, OCR/ASR/caption
fusion, and multimodal consistency are deferred candidate capabilities. The
Student does not consume Teacher confidence or full free-form traces as
training targets. Quality-gated Rationale Capsules may provide auxiliary
alignment supervision, while the natural-language Teacher report remains an
audit artifact.

Production Student output may create an internal Hard-Case Candidate. Only an
analyst-triggered Review API request activates Teacher; offline data-production
scripts are the only future path allowed to batch-call Teacher. Neither line
overwrites the analyst-owned Confirmed Decision or changes Coordination and
Propagation responsibilities.

The paper-aligned local Weibo21 MARO/INS experiment is isolated in
`system/backend/scripts/run_maro_weibo21_ins_experiment.py`. It caches the
multi-dimensional analysis stage, optimizes decision rules only on source-domain
validation tasks, and evaluates top-3-rule majority voting on a held-out local
domain. It requires process-scoped DeepSeek and traceable retrieval credentials;
`--dry-run` validates the local protocol without external calls. Its results
must not be presented as official MARO reproduction or as Student performance.

The HateCoT harm adaptation is isolated in
`system/backend/scripts/run_maro_hatecot_harm_experiment.py`. It uses the
three-way `non_harmful/offensive/hate` label space, source-train/source-dev
rule separation, and held-out target sampling for `cad`, `dynahate`, and
`toraman`. Policy-off is the primary arm; `local_advisory` is a local context
ablation only. The runner's dry-run performs no DeepSeek, Exa, or external
retrieval call. It does not alter Student training, LRKD, product Review
routing, or multimodal capabilities.
