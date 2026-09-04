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

## Infrastructure

Docker Compose runs MySQL, MongoDB, and Redis. Backend, Celery, and frontend processes run from the checked-out source tree.

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

## One-Command Windows Startup

After dependencies and `system/.env` are prepared:

```powershell
cd system
powershell.exe -ExecutionPolicy Bypass -File .\start-system.ps1
```

Use `-SyncHistoricalData` only when local runtime JSONL needs to be imported into MongoDB. The import is idempotent.

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

## Verification

Backend:

```powershell
cd system\backend
uv run python -m pytest tests -q
uv run python -m alembic current
```

默认测试模式允许在本机未启动 MySQL 时对数据库集成用例做明确原因的
`skip`。GitHub CI 和发布验证必须设置：

```powershell
$env:COGGUARD_REQUIRE_EXTERNAL_SERVICES = "1"
uv run python -m pytest tests -q
```

严格模式下，所请求的 MySQL、MongoDB 或 Redis 集成依赖不可达会直接失败，
不会被静默计入绿色结果。纯内存单元测试不要求这些服务。Ubuntu CI 使用
workflow service containers；Windows 本地验证使用 `docker compose up -d`。

真实迁移往返只允许使用独立测试库 `MYSQL_DATABASE_TEST`：

```powershell
$env:COGGUARD_RUN_MIGRATION_ROUNDTRIP = "1"
python scripts/verify_migration_roundtrip.py
python scripts/verify_migration_roundtrip.py --check-services
```

Frontend:

```powershell
cd system\frontend
npm test
npm run build
```

The frontend build enforces a local map payload below 2 MB and every generated JavaScript chunk below 1 MB.

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
- If a social platform resolves to a Clash fake-IP address and Chromium reports network denial, set `MEDIACRAWLER_PROXY` to the local HTTP proxy.
