# CogGuard Project Map

This file defines repository boundaries, default edit ownership, and the split
between product code, system-readable research, reference code, and local
research notes. If this file conflicts with older documents, this file wins.

## Main Boundaries

| Path | Role | Default edit policy |
| --- | --- | --- |
| `system/` | Active product system: backend, frontend, deployment files, vendored runtimes, system-readable research packages, and tests. | Edit for runnable system work. |
| `system/backend/` | FastAPI, Celery, MySQL/MongoDB/Redis access, services, tasks, schemas, and backend tests. | Edit for product backend behavior. |
| `system/backend/app/services/analysis_governance_service.py` | Authenticated control plane for durable Teacher dispatch outcomes, model candidates, activation approvals, active pointers, and rollback decisions. | Keep separate from product-facing case schemas and frontend. |
| `system/backend/alembic/versions/` | Versioned MySQL schema changes, including durable review and model approval tables. | Apply migrations before enabling the corresponding production endpoint. |
| `system/frontend/` | Vue 3 and TypeScript UI plus the canonical `npm run build` delivery build. | Keep `/dashboard` as the homepage and `/risk` as the Event Review Case workspace. |
| `system/deploy/` | Default static frontend delivery profile and Nginx cache/proxy policy. | Do not add product behavior here; use it to serve built frontend assets and proxy existing APIs. |
| `system/ops/` | Explicit maintenance operations, including MongoDB performance-index application. | Keep operations idempotent, observable, and free of destructive defaults. |
| `system/runtimes/social_runtime/` | Vendored social crawler runtime for `weibo`, `douyin`, and `xhs`. | Product runtime code; keep dependencies local to this runtime. |
| `system/runtimes/news_runtime/` | Vendored news extraction runtime for `news`. | Product runtime code; keep dependencies local to this runtime. |
| `system/runtimes/review_student/` | Deployable Student Review runtime used by `StudentRuntime.predict(case)`. | Product runtime code; keep synchronous, checkpoint-gated, and governance-aware. |
| `system/research/coordination_discover/` | Label-free Coordination Discovery research pipeline, including TSGS/MHCR and the `DiscoveredClusterBatch` seam. | System-readable research; keep product activation frozen until ADR-0014 gates pass. |
| `system/research/coordination_detect/` | Learned harmful-CIB Detection validation boundary consuming only `DiscoveredClusterBatch` plus detection-only features. | Train/calibrate on approved labeled data only; the fixed Bayesian rule is heuristic baseline only. |
| `system/research/propagation_analysis/` | Propagation Analysis loaders, hindcast protocol, conformal intervals, and baseline registry. | System-readable research; do not point product code at external research workspaces. |
| `system/research/review_teacher/` | Multi-agent Teacher Review advisory DAG. | System-readable research; advisory only unless an analyst approves a canonical verdict. |
| `system/research/social_bot_detection/` | Internal trainable BotRHG transfer pipeline for labeled Weibo accounts. | System-readable research and checkpoint export; text-only transfer until property/social graph coverage is available. |
| `doc/engineering/` | Long-lived engineering documentation. | Keep setup, governance, roadmap, project map, and development log aligned with code. |
| `doc/adr/` | Historical accepted architecture decision records. | Never rewrite or renumber an accepted record in place. |
| `docs/adr/` | Current ADR index and new decisions. | Record supersession in the index and keep one numbered file per new durable decision. |
| `doc/research/` | Research positioning and literature notes. | Use for method positioning, references, and research context. |
| `aris/` | Historical research workspace. | Read for provenance; do not copy numbered workspace labels into current product language. |
| `research-wiki/` | Local research knowledge base and literature notes. | Local note workspace; do not commit generated local wiki output by default. |
| `MediaCrawler-main/`, `NewsCrawler-main/`, `CooRTweet-master/` | Reference boundaries. | Provenance, license review, and diffing only; never product runtime roots. |

## Governance Sources

- [system-governance.md](system-governance.md) is the normative source for naming, package boundaries, and structure rules.
- `docs/adr/index.md` is the ADR status source and links to historical records under `doc/adr/`.
- [UBIQUITOUS_LANGUAGE.md](../../UBIQUITOUS_LANGUAGE.md) is the canonical glossary for domain terms and aliases to avoid.
- [system/README.md](../../system/README.md) is the runnable-system guide.

## Product Vs Research Rule

Product code belongs in `system/` when it is called by a backend service, API
route, Celery task, frontend page, product test, demo path, stable schema,
model, configuration, or integration point.

System-readable research belongs in `system/research/` when product adapters
need to import it or read its artifacts. Exploratory notes, literature maps,
and unproductized ideas stay in `doc/research/`, `aris/`, or `research-wiki/`.

Offline experiment inputs should default to vendored runtime data roots or an
explicit user-provided path. They must not default to a reference boundary.

## Current Functional Map

```text
CogGuard/
  system/
    backend/
      app/core/analysis/              Analysis lifecycle and ports
      app/core/crawler/               Crawler adapters and collect seam
      app/core/coordination_baseline/ Compatibility baseline
      app/core/propagation/           Propagation Analysis app support
      app/core/review/                Internal Review runtime support
      app/services/analysis_governance_service.py
                                      Authenticated model and dispatch control plane
      app/services/review_case_*      Event Review Case service and orchestration
      scripts/                        Explicit local utility entrypoints
      tests/                          Backend regression and governance tests
    frontend/                         Dashboard and Event Review Case UI
    deploy/                           Static frontend delivery and proxy policy
    ops/                              Explicit database and runtime maintenance operations
    research/
      coordination_discover/          Label-free Discovery and DiscoveredClusterBatch seam
      coordination_detect/            Learned harmful-CIB Detection validation boundary
      propagation_analysis/           Propagation Analysis protocol and baselines
      review_teacher/                 Teacher Review advisory DAG
      social_bot_detection/           trainable BotRHG Weibo transfer
    runtimes/
      social_runtime/                 Vendored social crawler runtime
      news_runtime/                   Vendored news extractor runtime
      review_student/                 Student Review runtime
  doc/
    engineering/                      Governance, setup, roadmap, log, maps
    research/                         Positioning and literature notes
  aris/                               Historical research workspace
  MediaCrawler-main/                  Reference boundary
  NewsCrawler-main/                   Reference boundary
  CooRTweet-master/                   Reference boundary
```

## Runtime Boundary Policy

Crawler execution happens inside `system/runtimes/`. The vendored runtime trees
are product runtime code and should carry only the minimum upstream core needed
by the live system.

Propagation Analysis and Teacher Review have product-readable internal seams:
`system/research/propagation_analysis/runtime/protocol.py` and
`system/research/review_teacher/dag.py`. Backend code may call these through
`EventSnapshot` and `AnalysisRun` ports, but missing checkpoints must be
reported as unavailable rather than successful research results.

The upstream reference directories remain in place only for provenance, license
review, and diffing. Product execution, tests, documentation, and configuration
must not depend on them as runtime roots.

Model governance is persisted in MySQL. `analysis_model_versions` stores
registered Model Candidates, `analysis_model_activation_approvals` stores one
immutable authenticated approval per candidate and administrator, and
`analysis_model_activations` stores the active pointer. These records are
control-plane data and must not be copied into the business-safe frontend
contracts.

Coordination research is not a product activation shortcut. Stage 1 Discovery
may consume only observed coordination evidence and must stay label-free; Stage
2 harmful-CIB Detection may consume only the serialized `DiscoveredClusterBatch`
plus detection-only features and approved labels. IOHunter external-account
metrics are proxy-only. The frozen `coordination-evidence-runtime-v2` remains
the production mainline until the ADR-0014 activation gate passes. New research
artifacts, reports, caches, and temporary outputs must use explicit G-drive
paths.

## Performance Operations

`system/start-system.ps1` uses `system/deploy/frontend.Dockerfile` and
`system/deploy/nginx/default.conf.template` as the default static frontend
delivery path. `npm run build` creates the content-addressed asset set and a
Vite-manifest-driven `Delivery Preload Plan`: the authenticated layout and
dashboard prepare during idle time, while other routes prepare only after menu
hover or keyboard focus. The plan never prefetches API data or executes an
analysis, and it excludes Three.js graph assets from idle preparation. Static
delivery caches only content-addressed assets, keeps HTML/API/SSE uncached,
and does not alter product routes or contracts.

`system/ops/Apply-MongoPerformanceIndexes.ps1` applies the explicit
`raw_posts`/`raw_comments` index set through the running Compose MongoDB
service. It does not run on backend startup and never removes indexes. The
operational source of truth is [performance-operations.md](performance-operations.md).
