# CogGuard Environment Setup

This guide describes the reproducible local and LAN prototype environment. The active system lives under `system/`; the reference source trees at the repository root are not runtime dependencies.

## Prerequisites

| Tool | Version |
| --- | --- |
| Docker Desktop | Current stable release |
| Python | 3.11 or newer |
| Node.js | 18 or newer |
| uv | Current stable release |

## Configuration

Create the local configuration from the tracked template:

```powershell
cd system
Copy-Item .env.example .env
```

Set at least these values before a shared LAN deployment:

```dotenv
JWT_SECRET_KEY=<random secret>
DEFAULT_ADMIN_PASSWORD=<initial administrator password>
MYSQL_PASSWORD=<database password>
MYSQL_ROOT_PASSWORD=<database root password>
MONGO_PASSWORD=<database password>
REDIS_PASSWORD=<database password>
```

Do not commit `system/.env`, crawler cookies, API keys, or provider credentials.

## Default Startup

The normal local or LAN launch uses the production-like static delivery path.
It starts infrastructure, applies idempotent MongoDB indexes, migrates MySQL,
starts the backend without a reload watcher, waits for `/api/v2/health`, builds
the frontend, and starts the `production-ui` static profile:

```powershell
cd system
powershell.exe -ExecutionPolicy Bypass -File .\start-system.ps1
```

Open `http://127.0.0.1:5173/login` after the command reports readiness.
Use `-SkipIndexPreparation` only for a known maintenance conflict. Use
`-DevelopmentFrontend` only while editing frontend source; it starts Vite in
place of the static profile.

## Infrastructure

Docker Compose runs MySQL, MongoDB, and Redis. The default helper runs the
backend from the checked-out source tree and serves the built frontend from the
Compose static-delivery profile.

```powershell
cd system
docker compose up -d
docker compose ps
```

Expected ports:

| Service | Port |
| --- | --- |
| MySQL | `3306` |
| MongoDB | `27017` |
| Redis | `6379` |
| Backend | `8000` |
| Frontend | `5173` |

## Backend

```powershell
cd system\backend
uv sync --extra dev
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Health check and API documentation:

- `http://127.0.0.1:8000/api/v1/health`
- `http://127.0.0.1:8000/docs`

## Celery Worker

Run the worker in a separate terminal when queued collection or asynchronous review advisories are required:

```powershell
cd system\backend
uv run celery -A app.celery_app worker --pool=solo --loglevel=INFO
```

Redis is both the broker and result backend. The Windows prototype uses the `solo` pool.

## Frontend

```powershell
cd system\frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Use the real login flow, then open:

- Login: `http://127.0.0.1:5173/login`
- Dashboard: `http://127.0.0.1:5173/dashboard`
- Event review: `http://127.0.0.1:5173/risk`

There is no `/preview` route or static preview token. Local and LAN prototypes use the same authenticated application path.

### Delivery Performance Profile

`start-system.ps1` uses this profile by default. Use Vite only while editing
frontend source. For a separately operated delivery run with compressed and
cacheable static assets, leave the backend on port `8000` and start the static
frontend service instead:

```powershell
cd system
docker compose --profile production-ui up -d --build frontend_static
```

It serves the frontend on `FRONTEND_PORT` (default `5173`) and proxies `/api/*`
to `BACKEND_ORIGIN` (default `http://host.docker.internal:8000`). Do not run
the Vite development server on the same port. HTML and APIs are never cached;
only Vite content-hashed assets receive long-lived cache headers.

### MongoDB Query Indexes

The default helper applies this idempotent operation before the backend starts.
For a separate maintenance run, preview the index operation and then apply it
in a quiet maintenance window:

```powershell
cd system
.\ops\Apply-MongoPerformanceIndexes.ps1 -DryRun
.\ops\Apply-MongoPerformanceIndexes.ps1
```

The operation is idempotent and never drops an index. It covers the existing
event/platform/time/crawl-job query shapes for `raw_posts` and `raw_comments`.
See `performance-operations.md` for the complete index list and rollback
boundary.

### Demo Data Warmup

The optimized static build only preloads browser assets. To make a video
walkthrough start with real analytical pages already warmed, set temporary
demo credentials and run:

```powershell
$env:COGGUARD_DEMO_USERNAME = 'demo_analyst'
$env:COGGUARD_DEMO_PASSWORD = '<local-demo-password>'
powershell.exe -ExecutionPolicy Bypass -File .\start-system.ps1 -DemoWarmup -DemoWarmupStrict
```

Use `-SkipDocker` when the infrastructure is already owned by another Compose
project. Do not put the password in a committed script or command history.
The warmup report is redacted and stored under `system/output/demo-warmup/`.

Use `-SyncHistoricalData` with the default startup command only when local
runtime JSONL needs to be imported into MongoDB. The import is idempotent.

## Built-In Crawler Runtimes

The social and news runtimes are repository-local:

```powershell
cd system\runtimes\social_runtime
uv sync --frozen
uv run playwright install chromium

cd ..\news_runtime
uv sync --frozen
```

Supported product platforms are `weibo`, `douyin`, `xhs`, and `news`; `mock_weibo` is test-only. Configure social collection with `MEDIACRAWLER_LOGIN_TYPE`, `MEDIACRAWLER_COOKIES`, `MEDIACRAWLER_NODE_DIR`, `MEDIACRAWLER_PROXY`, `MEDIACRAWLER_GET_SUB_COMMENTS`, and `MEDIACRAWLER_MAX_COMMENTS_PER_POST`.

Do not configure or execute `MediaCrawler-main`, `NewsCrawler-main`, or `CooRTweet-master` as runtime roots.

## Existing Runtime Data

Import vendored social runtime JSONL with:

```powershell
cd system
.\sync-real-data.ps1
```

New successful collection jobs carrying an `event_id` automatically create or revise an Event Review Case and run the internal analysis pipeline. Re-importing an unchanged data fingerprint does not create a duplicate revision.

## Chinese Account Training Runtime

The control plane can run on CPU, but DAPT and deployment latency acceptance
require a CUDA-enabled PyTorch environment. Verify the exact interpreter used
by the dedicated worker:

```powershell
cd system\backend
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.version.cuda)"
nvidia-smi
```

Do not treat the presence of an NVIDIA driver as proof that training uses the
GPU. As measured on 2026-08-07, the host RTX 4060 was visible while the backend
venv reported `torch 2.12.1+cpu`, `cuda.is_available() == False`. The first DAPT
run also remains quantity-blocked until the registered Chinese corpus reaches
500,000 qualified tokens; the current measured corpus contains 415,686.

An empty Active Pointer is a valid fail-closed state. `/api/v1/accounts/bot-detection`
must return `unavailable_without_active_pointer` instead of using a legacy or
heuristic detector.

## Verification

Backend:

```powershell
cd system\backend
uv run python -m pytest tests -q
uv run python -m alembic current
```

Frontend:

```powershell
cd system\frontend
npm test
npm run build
```

The frontend build enforces a local map payload below 2 MB, every generated
JavaScript chunk below 1 MB, and the generated delivery preload policy. It
prepares only the authenticated layout and dashboard shell after login;
other routes are prepared on navigation interaction.

## Stopping Services

```powershell
cd system
docker compose down
```

Do not use `docker compose down -v` unless deleting all local MySQL, MongoDB, and Redis data is explicitly intended.

## Troubleshooting

- If Docker interpolation reports a missing password, create `system/.env` from the template.
- If MySQL is not ready, wait for `docker compose ps` to report `healthy` before running Alembic.
- If PowerShell blocks `npm.ps1`, invoke `npm.cmd` directly.
- If the frontend cannot reach the backend, verify port `8000` and the Vite `/api` proxy in `system/frontend/vite.config.ts`.
- If the static delivery profile cannot reach the backend, verify
  `BACKEND_ORIGIN` from inside `cogguard-frontend` and do not use a `localhost`
  backend origin from inside the container.
- If a social platform resolves to a Clash fake-IP address and Chromium reports network denial, set `MEDIACRAWLER_PROXY` to the local HTTP proxy.
