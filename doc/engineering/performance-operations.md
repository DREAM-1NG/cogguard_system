# CogGuard Performance Operations

> Scope: deployment and database-operation optimizations that do not change
> `system/frontend/src/` or `system/backend/app/` behavior.
>
> Owner: maintainers operating the `system/` product root.

## Purpose

The current prototype has several intentionally visible page-transition costs:
route components are recreated, analytical pages request current data on mount,
and graph-heavy pages initialize ECharts or Three.js. Those product behaviors
are not changed by this operations pass.

This document records the optimizations that are safe outside product source:

1. serve the built frontend instead of the Vite development server for a
   delivery or demonstration deployment;
2. compress static payloads and cache only content-addressed build assets;
3. create explicit MongoDB indexes for the existing event, platform, time, and
   crawl-job query shapes;
4. measure the remaining product-level work before changing business code.

## Delivery Profile

`system/docker-compose.yml` provides an opt-in `production-ui` profile. It
builds `system/frontend/` once and serves `dist/` with Nginx.

| Request class | Policy | Reason |
| --- | --- | --- |
| `/assets/*` | gzip plus one-year immutable cache | Vite emits content-hashed filenames. |
| HTML and SPA route fallbacks | no-cache, must-revalidate | A deployment receives a new entry document immediately. |
| `/api/*` | reverse proxy, no cache | Authentication, case data, and mutations remain current. |
| Review event stream | reverse proxy, buffering disabled, no cache | Event delivery must not be delayed by a proxy buffer. |

The profile does not change API routing: browsers continue calling `/api/*`.
Nginx forwards those requests to `BACKEND_ORIGIN`, which defaults to the
host-process backend at `http://host.docker.internal:8000`.

### Start A Delivery Deployment

Start the backend using the existing process or service on port `8000`, then
run the static frontend profile instead of `npm run dev`:

```powershell
cd G:\CISCN\CogGuard\.worktrees\refactor-system\system
docker compose --profile production-ui up -d --build frontend_static
docker compose --profile production-ui ps
```

The default port is `5173`; set `FRONTEND_PORT` before startup when that port
is already occupied. Set `BACKEND_ORIGIN` only when the backend is not on the
Docker host at port `8000`.

Do not start Vite and `frontend_static` on the same port. The Vite server stays
the correct workflow for frontend development and hot reload; the static
profile is the correct workflow for a measured local or LAN delivery run.

### Verify Static Delivery

```powershell
curl.exe -I http://127.0.0.1:5173/
curl.exe -I http://127.0.0.1:5173/assets/<hash>.js
curl.exe -I http://127.0.0.1:5173/api/v1/health
```

Expected headers are `Cache-Control: no-cache, must-revalidate` for the HTML
entry, `public, max-age=31536000, immutable` for hashed assets, and `no-store`
for API responses. The exact asset filename changes on every production build.

## MongoDB Index Operations

The current product queries `raw_posts` and `raw_comments` by event, platform,
timestamp, and crawl-job ownership. Index creation is intentionally an explicit
operation, rather than an application-start side effect.

| Collection | Index | Existing query shape |
| --- | --- | --- |
| `raw_posts` | `event_id, platform, timestamp` | event/platform acquisition, dashboard, analysis |
| `raw_posts` | `event_id, timestamp` | event-scoped ordering |
| `raw_posts` | `platform, timestamp` | platform-scoped ordering |
| `raw_posts` | `timestamp` | unfiltered acquisition ordering |
| `raw_posts` | `crawl_job_id` | crawl-job cleanup |
| `raw_comments` | `event_id, platform, timestamp` | event/platform comment loading |
| `raw_comments` | `platform, timestamp` | platform-scoped comment loading |
| `raw_comments` | `crawl_job_id` | crawl-job cleanup |

Preview the exact operation first:

```powershell
cd G:\CISCN\CogGuard\.worktrees\refactor-system\system
.\ops\Apply-MongoPerformanceIndexes.ps1 -DryRun
```

Apply it after reviewing the plan:

```powershell
.\ops\Apply-MongoPerformanceIndexes.ps1
```

The operation is idempotent: an identically named index with the expected key
is retained, a missing index is created, and a same-name/different-key conflict
fails without dropping anything. Run it during a quiet maintenance window for
large collections because index builds consume disk and CPU.

## Measurement Baseline

Measure one cold visit and one repeat visit per route after logging in. Record
network response sizes, request duration, and browser long tasks separately.

| Route | Primary remaining cost | Outside this pass |
| --- | --- | --- |
| `/dashboard` | map payload and repeated map initialization | component lifecycle and map render triggers |
| `/coordination` | Three.js force graph initialization | deferred graph loading and graph lifecycle |
| `/propagation` | full observed graph calculation and ECharts redraw | result caching and rendering contract |
| `/accounts` | full-corpus model inference on a cold fingerprint | scope selection and asynchronous precomputation |
| `/risk` | full evidence payload and large reactive list | server pagination and virtual list |

Use browser performance tools against the static delivery profile. Do not claim
that the listed product-level costs are solved until a dedicated source change
has a before/after trace and regression coverage.

## Rollback

To stop only the static delivery service:

```powershell
cd G:\CISCN\CogGuard\.worktrees\refactor-system\system
docker compose --profile production-ui stop frontend_static
docker compose --profile production-ui rm -f frontend_static
```

MongoDB indexes are intentionally not removed by the apply script. Remove an
index only after reviewing active query plans and a maintenance rollback plan.
