# CogGuard Performance Operations

> Scope: delivery, database-operation, server-side projection-cache, and
> propagation-view presentation optimizations that preserve the public product
> response contracts.
>
> Owner: maintainers operating the `system/` product root.

## Purpose

The current prototype still has cold analytical costs: pages request current
data on mount and graph-heavy pages initialize ECharts or Three.js. The review
workspace now retains its route state and retrieves a bounded evidence page,
but propagation graphs and dashboard aggregation remain cold-path work.

This document records optimizations that preserve the existing product
contracts:

1. serve the built frontend instead of the Vite development server for a
   delivery or demonstration deployment;
2. compress static payloads and cache only content-addressed build assets;
3. create explicit MongoDB indexes for the existing event, platform, time,
   crawl-job, and ingestion-generation query shapes;
4. generate a route-aware browser preload plan from Vite's production manifest;
5. make the static delivery and index preparation path the default startup;
6. cache immutable, versioned query projections behind existing API endpoints;
7. return the selected review evidence group as a cursor-paginated projection
   instead of serializing the complete case snapshot;
8. measure the remaining product-level work before changing business code.

## Delivery Profile

`system/docker-compose.yml` provides the `production-ui` profile. The default
`system/start-system.ps1` uses this profile; it builds `system/frontend/` once
and serves `dist/` with Nginx after the backend health endpoint is ready.

| Request class | Policy | Reason |
| --- | --- | --- |
| `/assets/*` | gzip plus one-year immutable cache | Vite emits content-hashed filenames. |
| HTML and SPA route fallbacks | no-cache, must-revalidate | A deployment receives a new entry document immediately. |
| `/api/*` | reverse proxy, no cache | Authentication, case data, and mutations remain current. |
| Review event stream | reverse proxy, buffering disabled, no cache | Event delivery must not be delayed by a proxy buffer. |

The profile does not change API routing: browsers continue calling `/api/*`.
Nginx forwards those requests to `BACKEND_ORIGIN`, which defaults to the
host-process backend at `http://host.docker.internal:8000`.

The default startup binds the backend to 0.0.0.0 on port 8000 so the static
frontend container can reach it through the Docker host gateway. Readiness
checks and browser access remain on 127.0.0.1; Docker is not required to
expose a separate backend container.

### Default Delivery Startup

The canonical local/LAN delivery command is:

```powershell
cd G:\CISCN\CogGuard\.worktrees\refactor-system\system
powershell.exe -ExecutionPolicy Bypass -File .\start-system.ps1
```

The helper starts only MySQL, MongoDB, and Redis from Compose; previews and
then applies named MongoDB indexes; applies Alembic migrations; starts one host backend without
`--reload`; waits for `/api/v2/health`; starts the dedicated hidden account-model
Celery worker for `account_training,account_evaluation` with concurrency 1; then
starts Celery Beat and builds the static frontend profile. It logs host backend,
account-model worker, and scheduler output under
`system/logs/`. Use
`-DevelopmentFrontend` only while changing `system/frontend/src/`.

### Start A Separately Operated Delivery Deployment

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

## Browser Asset Preparation

`npm run build` is the optimized build command. In addition to typechecking and
Vite output, it emits `dist/.vite/manifest.json`, derives
`dist/delivery-preload-manifest.json`, injects a content-addressed delivery
preload module into the built HTML, and verifies the result.

The browser reads only that generated plan. It has two policies:

| Trigger | Prepared assets | Excluded work |
| --- | --- | --- |
| Authentication or an existing session | shared layout and dashboard shell, including the local map payload and its rendering dependency | API requests, account inference, full case evidence, propagation computation, Three.js graph assets |
| Menu hover or keyboard focus | the selected non-dashboard route chunk and its static dependencies, using the menu route key or its library event-key wrapper | route API requests and analytical execution |

The plan is build-manifest-derived rather than hash-name-derived, so it stays
correct after Vite changes content hashes. Tests fail the build if a heavy graph
chunk leaks into the idle preload set. This is resource preparation only: it
does not pre-run a route, make authenticated API calls, or mutate a case.

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
| raw_posts | event_id, crawl_job_id, _id | event-scoped ingestion generation marker |
| raw_comments | event_id, crawl_job_id, _id | event-scoped ingestion generation marker |
| `raw_posts` | `event_id, platform, timestamp` | event/platform acquisition, dashboard, analysis |
| `raw_posts` | `event_id, timestamp` | event-scoped ordering |
| `raw_posts` | `platform, timestamp` | platform-scoped ordering |
| `raw_posts` | `timestamp` | unfiltered acquisition ordering |
| `raw_posts` | `crawl_job_id` | crawl-job cleanup |
| `raw_posts` | `event_id, author_id` | event-scoped display-name lookup for key accounts |
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
| `/propagation` | full observed graph calculation and ECharts redraw | compact projection and rendering contract |
| `/accounts` | full-corpus model inference on a cold fingerprint | scope selection and asynchronous precomputation |
| `/risk` | full evidence payload and large reactive list | server pagination and virtual list |

Use browser performance tools against the static delivery profile. Do not claim
that the listed product-level costs are solved until a dedicated source change
has a before/after trace and regression coverage.

## Actual Runtime Verification (2026-08-05)

This section records a real local delivery run from
`G:\CISCN\CogGuard\.worktrees\refactor-system\system`, rather than a preview
build or mocked API server.

### Runtime and Data State

| Check | Result |
| --- | --- |
| Docker engine / Compose | Docker 28.3.3 / Compose v2.39.2 |
| Backend | `http://127.0.0.1:8000/api/v2/health` returned HTTP 200 |
| Static frontend | `http://127.0.0.1:5173/healthz` returned HTTP 204 |
| Frontend container | `cogguard-frontend` healthy on port 5173 |
| MongoDB data | 467 posts and 25,812 comments across 8 event identifiers |
| Authentication | Login and authenticated route access succeeded with a local analyst test account |
| MongoDB indexes | Historical 2026-08-05 baseline used 8 indexes; current 2026-08-07 set contains 11 |

This workstation can contain a complete existing MySQL, MongoDB, and Redis
set under the fixed `cogguard-*` names but owned by another Compose project.
The normal startup helper recognizes that complete, image-compatible set,
reuses its data volumes, and runs the MongoDB index operation through
`docker exec cogguard-mongodb` rather than the current Compose project's
service lookup. Both the dry-run and apply paths remain idempotent. A partial
or image-mismatched set still fails before any container is created.
On Windows, the static frontend port check also recognizes the `wslrelay.exe`
listener paired with the Docker backend; an unrelated listener is still
rejected before Compose is invoked.

### Measured API Costs

Measurements below are authenticated requests against the real event
`trump_visit_2026_05_21`. Direct backend samples used three requests per
endpoint; browser values are first-page loads through the static Nginx proxy.

| Capability | Response size | Median | P95 / observed max | Interpretation |
| --- | ---: | ---: | ---: | --- |
| Dashboard overview | 4.6 KB | 1,127 ms (10 samples) | 2,034 ms | Loads the full event post/comment corpus to calculate small summary cards |
| Coordination graph | 46.1 KB | 1,282 ms | 2,137 ms | Dataset detail, latest result, and graph requests overlap on page load |
| Account profiles | 72.7 KB | 889 ms | 969 ms | Full profile response is generated on demand |
| Observed propagation | 1.64 MB | 10,345 ms | 13,538 ms | Full observed graph and timeline are serialized even with `node_limit=300` |
| Review evidence | 4.93 MB | 8,248 ms | 8,714 ms | All post/comment evidence is returned before the first evidence tab is needed |
| Review case list | 2.6 KB | 56 ms (10 samples) | 67 ms | Not a database or authentication bottleneck |

The browser resource traces show the same shape: propagation took 8,229 ms
for a 1.64 MB decoded response, and review evidence took 9,533 ms for a
4.93 MB decoded response. The HTML navigation itself remained below 325 ms on
all measured routes; the perceived delay is asynchronous data loading and
post-load graph/list rendering, not Nginx entry-document delivery.

### Static Delivery Checks

The optimized build and Nginx policy behaved as intended:

| Resource | Observed policy |
| --- | --- |
| HTML entry | `Cache-Control: no-cache, must-revalidate` |
| Hashed JavaScript | `public, max-age=31536000, immutable` plus gzip when requested |
| API responses | `Cache-Control: no-store` |
| `/healthz` | HTTP 204 and `no-store` |

The dashboard cold browser trace reported 98 ms document navigation and a
2,145 ms dashboard API request. The coordination, propagation, accounts, and
risk document navigations were 162 ms, 216 ms, 135 ms, and 325 ms respectively.
These document numbers must not be reported as complete page readiness because
they exclude asynchronous API and graph completion.

### Findings and Next Gates

The delivery optimization is working, but it does not solve product-level
payload and computation costs. The next implementation work should be ordered
as follows:

1. Add a server-side evidence summary plus cursor pagination for review cases;
   return the active evidence group first instead of serializing all 15,016
   unresolved items in the initial response.
2. Cache or precompute observed propagation results and expose a compact graph
   summary/viewport contract; keep full timeline and edge detail behind an
   explicit drill-down request.
3. Replace dashboard full-corpus reads with indexed counts, platform
   aggregates, and a bounded recent-post query.
4. Move account-profile construction to collection-time or a background
   materialization job and make the page consume a bounded event scope.
5. Handle expired access tokens in the raw event-stream client. During the
   long browser run, the 60-minute token expired and the review page issued a
   new unauthenticated stream request every 10 seconds, producing repeated 401
   responses. The stream must stop and route through the shared refresh/logout
   path rather than retrying indefinitely.
6. Narrow the route-aware preload plan for non-dashboard pages; Chromium warned
   that the map payload and shared CSS were preloaded but unused on analytical
   routes.

The source locations explaining the baseline measurements are
`system/backend/app/services/event_data.py` (unbounded event reads),
`system/backend/app/services/dashboard_service.py` (full-corpus dashboard
aggregation), `system/backend/app/services/propagation_observation_service.py`
and `system/backend/app/core/propagation_analysis/` (graph construction), and
`system/backend/app/services/review_case_service.py` (full snapshot evidence
materialization). The measurements predate the versioned result projection
cache described below; they remain the cold-request baseline and must not be
reported as the post-cache result.

Browser traces are retained under `system/output/playwright/` as
`*-performance.json`; authentication state files must not be retained or
committed.

### Authenticated Demo Warmup

Static asset preloading and business-data warmup are different operations.
The production build can prepare content-addressed JavaScript, CSS, and map
assets before a browser opens. It cannot request authenticated API data before
the backend and databases exist. When local demo credentials are configured,
the default startup therefore starts the infrastructure and backend, warms the
authenticated queries, and exposes the static frontend only after warmup:

```powershell
cd G:\CISCN\CogGuard\.worktrees\refactor-system\system
$env:COGGUARD_DEMO_USERNAME = 'demo_analyst'
$env:COGGUARD_DEMO_PASSWORD = '<local-demo-password>'
$env:COGGUARD_DEMO_EVENT_ID = 'trump_visit_2026_05_21'
powershell.exe -ExecutionPolicy Bypass -File .\start-system.ps1
```

`-DemoWarmup` explicitly requires this behavior; the ordinary command also
enables it automatically when both `COGGUARD_DEMO_USERNAME` and
`COGGUARD_DEMO_PASSWORD` are present in the process environment or local
`.env`. Add `-DemoWarmupStrict` to fail startup on an optional warmup route, or
use `-SkipDemoWarmup` to bypass precompute. The warmup calls the health and login endpoints, then consumes the same
dashboard, coordination, account, propagation, and review-case endpoints used
by the current frontend. It writes a redacted timing report below
`system/output/demo-warmup/`; access and refresh tokens are never persisted.
The event, case, and coordination dataset can be pinned with
`-DemoEventId`, `-DemoCaseId`, and `-DemoCoordinationDatasetId` when a stable
walkthrough is required.

The first warmup is intentionally expensive because it performs the actual
computations and fills the server-side result projection cache. A current
real-data run completed all 14 requests successfully in about 73 seconds
before the cache cutover. This is appropriate before recording a video, but
should remain opt-in for ordinary development startup.

A repeat run immediately afterward still took about 69.5 seconds; coordination
result reads remained about 18.3 seconds, graph materialization about 16.2
seconds, propagation about 15.3 seconds, and review evidence about 4.6 seconds.
This was the pre-cutover behavior: the warmup report itself only records
status and timings, while the API recomputed every projection. After the
cutover, the same process and Redis-backed cache can reuse the generated
projection; a new source fingerprint, run, snapshot revision, or artifact
version creates a different cache key.

For an already-running Docker stack, use `-SkipDocker`; automatic warmup still
uses the configured credentials. The frontend should be opened only after the command prints
`CogGuard is ready.`

### Versioned Result Projections

The API now caches immutable query projections below the HTTP layer in
`system/backend/app/core/analysis/query_result_cache.py`. The process-local
LRU is the fast path and Redis is the shared path. Cache entries are not
invalidated by a fixed TTL; their keys include the source identity:

| Projection | Version identity |
| --- | --- |
| Observed propagation | event/platform, ingestion fingerprint, node limit |
| Coordination result/graph/community | dataset, completed run or archive file markers, query options |
| Event evidence | case, snapshot revision, annotation version |
| Account detector assessment | normalized post corpus fingerprint, active model version/hash/pointer revision |

The cache stores only analysis projections, never credentials, access tokens,
or model secrets. `Invoke-DemoWarmup.ps1` still writes only its redacted
endpoint report. It now has the correct operational role: the first run
materializes the selected demo projections, and the frontend is exposed only
after that work completes. Redis is an acceleration layer rather than the
source of truth; disabling it leaves the process-local cache and preserves
correctness. Configure the behavior with `ANALYSIS_RESULT_CACHE_*` in
`system/.env`.

### Propagation Demonstration Projection (2026-08-14)

The propagation page requests a bounded hierarchy projection with
`node_limit=160`, `first_layer_limit=40`, and `second_layer_limit=80`. The demo
warmup uses the same dimensions so its cached projection is reused on the first
page load; changing any of these query values intentionally creates a new cache
identity. The page renders the root and layer nodes on concentric rings without
relationship lines in the primary overview. Propagation edge and evidence data
remain available to detail views and the API, but are not used to create a
visually dense overview graph.

This is a presentation and cache-key alignment measure, not a claim that the
underlying propagation computation is cheap. A cold snapshot still computes the
bounded projection; repeat requests should read the versioned process/Redis
projection cache.

### Propagation Forecast Cache Closure (2026-08-14)

The authenticated demo warmup also runs `POST /api/v1/propagation/model-event-predict`
for the default event with `observation_ratio=0.5` and `top_k=10`. This stores a
MongoDB entry in `propagation_prediction_cache_v1`, keyed by event, platform,
observation cutoff, observation ratio, and Top-K. The propagation page reads
that cache on initial load and does not issue the slower prediction request
until the analyst selects **刷新趋势预测**.

Observed propagation and cached forecast reads begin concurrently. Initial
load and route scope changes preserve a valid cached forecast when the observed
projection completes later; analyst-triggered resynchronization intentionally
continues to clear the prior forecast. A strict real-data warmup completed the
forecast generation in about 1.0 s, and an authenticated browser check then
opened the trend tab with cached observed size, predicted final size, direction,
and Top-10 candidates without a manual refresh.

### Cache Cutover Verification (2026-08-06)

The live Trump-event reports below were produced against the real local
services. Every report contains only endpoint paths, statuses, and elapsed
time; it does not contain credentials or tokens.

| Run | Total | Account profiles | Coordination result / graph | Propagation | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: |
| First process after the initial cache cutover | 58.48 s | 38.47 s | 5.17 s / 4.44 s | 4.88 s | 3.03 s |
| Immediate repeat in the same process | 4.26 s | 0.44 s | 24 ms / 20 ms | 0.53 s | 1.46 s |
| Default startup after a Redis-backed restart | 7.89 s | 0.77 s | 101 ms / 37 ms | 0.96 s | 2.53 s |

The final row comes from `demo-warmup-20260806-184057.json`, generated by the
ordinary `start-system.ps1` automatic warmup path. It confirms that shared
Redis entries avoid rebuilding the account detector projection, Coordination
Discover artifacts, and observed propagation graph after a backend restart.
An account-model activation deliberately changes the account cache identity and
therefore incurs one new model evaluation for the new model version.

This change removes repeat computation. The review follow-up now also uses a
summary-first evidence projection: every response includes counts for all
assessment groups and only the selected group page (default: unresolved,
cursor `0`, limit `40`). Cache identity includes the snapshot revision,
annotation revision, assessment group, cursor, and limit. A cold request still
scans the immutable snapshot to calculate accurate group counts; it no longer
serializes or makes reactive every evidence item. Propagation still needs a
compact viewport contract before its full graph is serialized. Account
materialization remains a future improvement for a newly ingested corpus or
newly activated model, not for repeated reads of an unchanged corpus.

### Post-Index Dashboard Verification (2026-08-07)

The refactor backend was started independently on http://127.0.0.1:8001
against the existing real Trump-event data. Two event-scoped generation-marker
indexes were applied:

- raw_posts(event_id, crawl_job_id, _id)
- raw_comments(event_id, crawl_job_id, _id)

explain("queryPlanner") confirmed an IXSCAN and covered projection for both
event-data fingerprint lookups. The dashboard now caches its immutable Mongo
projection using that ingestion fingerprint, while the MySQL risk-report count
and response timestamp remain live on every request. This preserves the
existing response contract and avoids stale decision metadata.

| Path | Cache state | Measured time |
| --- | --- | ---: |
| Dashboard overview | cache cleared, backend restarted | 1.04 s |
| Dashboard overview | same event/data generation | 30 ms |
| Coordination result / graph | same completed run | 35 ms / 25 ms |
| Observed propagation | same event/data generation | 488 ms |
| Review evidence page | same snapshot revision | 20 ms |

The cold dashboard still reads the current corpus once to materialize its
projection. The pre-recording warmup is therefore required for a deterministic
demonstration, and a future high-volume deployment should replace that cold
materialization with Mongo aggregations and bounded recent-post queries.

### Delivery and Session-Recovery Verification (2026-08-07)

The production static frontend was rebuilt from the optimized source and
served through the default host backend origin on port 8000. Both the direct
backend health endpoint and the Nginx-proxied health endpoint returned HTTP
200. Two authenticated warmup passes against the real Trump event completed
without failed requests. The second pass measured the following route-facing
API costs:

| Capability | Warm repeat time |
| --- | ---: |
| Dashboard overview | 104 ms |
| Coordination result / graph | 39 ms / 24 ms |
| Account profiles | 568 ms |
| Observed propagation | 681 ms |
| Review evidence page | 24 ms |
| Review activities | 261 ms |

The review activity stream now treats HTTP 401 as an expired session rather
than a recoverable stream failure. A browser verification loaded the event
review with a valid session, then replaced its access token with an invalid
value. The next stream read produced one 401, cleared the session, navigated
to the login route, and produced no additional requests after a second
15-second observation interval. This prevents stale browser tabs from adding
repeated unauthorized polling load. No access tokens or passwords were stored
in the verification reports.

### Next Optimization Gates

The remaining measured order is:

1. Replace the dashboard cold-path full-corpus materialization with indexed
   counts, platform aggregates, and bounded recent records when collection
   volume grows beyond the current demonstration corpus.
2. Materialize account profiles at collection time or in a background job for
   newly ingested corpora, then make the product query event-scoped data.
3. Replace the cold propagation full-graph payload with a compact viewport
   projection and load timeline or edge detail only after an explicit drill-down.
4. Configure bounded Redis retention or an eviction policy before treating
   versioned projections as a continuously ingesting deployment cache.

The warmup script is an operational bridge for demonstrations. It must not be
used to claim that these product-level gates are complete.

## Rollback

To temporarily use the Vite development path, stop `frontend_static` and use:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\start-system.ps1 -DevelopmentFrontend
```

This is a development fallback, not the normal demonstration or LAN startup.

To stop only the static delivery service:

```powershell
cd G:\CISCN\CogGuard\.worktrees\refactor-system\system
docker compose --profile production-ui stop frontend_static
docker compose --profile production-ui rm -f frontend_static
```

MongoDB indexes are intentionally not removed by the apply script. Remove an
index only after reviewing active query plans and a maintenance rollback plan.

## Browser Route-Switch Baseline (2026-08-06)

This verification used the static delivery service, an authenticated analyst
session, and the real `trump_visit_2026_05_21` data. It followed the normal
left-menu workflow from Dashboard through Crawl, Coordination Discover,
Propagation Analysis, Account Profiles, and Event Review, then returned to
Dashboard. No browser console errors occurred during the flow.

These values predate the review evidence pagination follow-up and are retained
only as a before/after baseline. Do not report the Event Review rows as the
current route behavior.

`First visible` is the elapsed time from the menu click until the route's
first business landmark is visible. `Settled` is the elapsed time until the
route has no Ant Design loading indicator and remains stable for 400 ms. It
includes the route component, its API response, and the first render; it does
not represent a full-page document navigation.

| Route | First visible | Settled | Slowest current API work | Assessment |
| --- | ---: | ---: | --- | --- |
| Dashboard | 353 ms | 1.30 s | overview: 762 ms | Smooth for the current event. |
| Crawl | 149 ms | 719 ms | data query: 35 ms | Smooth. |
| Coordination Discover, first dataset-8 read | 128 ms | 3.11 s | result: 2.03 s; graph: 2.01 s | Acceptable first load; cache was not yet populated for this selected dataset. |
| Coordination Discover, repeated dataset-8 read | 55 ms | 889 ms | result and graph: 60 ms each | Smooth after the versioned projection cache is populated. |
| Propagation Analysis | 113 ms | 1.04 s | observed analysis: 510 ms, 1.64 MB | Smooth in the prepared demo state. |
| Account Profiles | 891 ms | 1.47 s | profiles: 683 ms, 72.4 KB | Smooth enough for the current event. |
| Event Review, first observed visit | 85 ms | 5.25 s | evidence: 3.08 s, 4.93 MB | Noticeably slow. Browser processing of the complete evidence payload accounts for the remaining delay. |
| Event Review, repeated visit | 53 ms | 2.78 s | evidence: 1.29 s, 4.93 MB | Improved by cache, but still not fluid enough to call complete. |

The system-management route is role-gated and is not part of the analyst
demonstration navigation; it was intentionally excluded from this run.

### Review Findings

1. The cache works for a repeated Coordination Discover read: the same
   dataset's settled time dropped from 3.11 s to 889 ms. The historical
   warmup report selected dataset 6 while the page selected dataset 8; the
   warmup selector now uses the same preferred-real-dataset rule as the route
   and a real post-change run selected dataset 8. An explicit
   `-DemoCoordinationDatasetId` still takes precedence for a pinned walkthrough.
2. Event Review was the remaining severe page in this baseline. The follow-up
   now returns group counts plus one bounded evidence page and loads the case
   selector asynchronously after the latest case is applied. A cold snapshot
   scan still remains, so a post-change browser trace is required before
   claiming a settled-time improvement.
3. Propagation Analysis is smooth only after its versioned projection exists.
   A new ingestion fingerprint, event, or query option correctly causes a
   cache miss and rebuild. Keep the prewarm phase before a recorded demo, and
   move toward a compact viewport projection for cold starts.
4. The dashboard row above is a historical browser baseline. As of 2026-08-07,
   its immutable Mongo projection is cached by ingestion generation and the
   fingerprint lookup is covered by event-scoped indexes. Its cold path still
   scales with the corpus and requires aggregate queries before material growth.
5. Redis currently contains 10 analysis projection keys using 8.57 MB, but
   has `maxmemory=0` and `noeviction`; versioned cache keys also have no
   expiry. This is safe for the short-lived demonstration and preserves
   restart warmup, but a continuously ingesting deployment needs an explicit
   retention policy or a bounded Redis eviction configuration before it can be
   treated as a long-running operational cache.
