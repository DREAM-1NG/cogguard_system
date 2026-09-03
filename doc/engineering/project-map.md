# CogGuard Project Map

This file defines repository boundaries, default edit ownership, and the split
between product code, system-readable research, reference code, and local
research notes. If this file conflicts with older documents, this file wins.

## Main Boundaries

| Path | Role | Default edit policy |
| --- | --- | --- |
| `system/` | Active product system: backend, frontend, deployment files, vendored runtimes, system-readable research packages, and tests. | Edit for runnable system work. |
| `system/backend/` | FastAPI, Celery, MySQL/MongoDB/Redis access, services, tasks, schemas, and backend tests. | Edit for product backend behavior. |
| `system/backend/app/core/analysis/` | Analysis Run lifecycle, artifact summaries, and uniform Analysis Stage adapters. | Every stage implements `AnalysisStagePort.execute(context)`; keep role-specific engines compatibility-only. |
| `system/backend/app/core/propagation_monitoring/` | Shared Propagation Monitoring use cases for HTTP and Celery adapters. | Own observed cache/compaction, forecast validation, profiles, and alert delegation. |
| `system/backend/app/core/semantic/` | Internal semantic enrichment of Event Snapshot evidence. | No rule fallback when required local weights are unavailable. |
| `system/backend/app/services/analysis_governance_service.py` | Authenticated control plane for durable Teacher dispatch outcomes, model candidates, activation approvals, active pointers, and rollback decisions. | Keep separate from product-facing case schemas and frontend. |
| `system/backend/alembic/versions/` | Versioned MySQL schema changes, including durable review and model approval tables. | Apply migrations before enabling the corresponding production endpoint. |
| `system/frontend/` | Vue 3 and TypeScript UI. | Keep `/dashboard` as the homepage and `/risk` as the Event Review Case workspace. |
| `system/runtimes/social_runtime/` | Vendored social crawler runtime for `weibo`, `douyin`, and `xhs`. | Product runtime code; keep dependencies local to this runtime. |
| `system/runtimes/news_runtime/` | Vendored news extraction runtime for `news`. | Product runtime code; keep dependencies local to this runtime. |
| `system/runtimes/review_student/` | Deployable Student Review runtime used by `StudentRuntime.predict(case)`. | Product runtime code; keep synchronous, checkpoint-gated, and governance-aware. |
| `system/research/coordination_discover/` | Platform-generic Coordination Discover pipeline and artifact export boundary. | System-readable research; backend consumes it through analysis adapters. |
| `system/research/coordination_detect/` | Public-label Coordination Detect validation boundary. | Validation boundary; do not label unlabeled project events. |
| `system/research/propagation_analysis/` | Propagation Analysis loaders, hindcast protocol, conformal intervals, and baseline registry. | System-readable research; do not point product code at external research workspaces. |
| `system/research/review_student/` | Student Review losses, staged training, Hardcase selection, and governed artifact export. | Offline research only; export a manifest and SHA-256 before activation. |
| `system/research/review_teacher/` | Multi-agent Teacher Review advisory DAG. | System-readable research; advisory only unless an analyst approves a canonical verdict. |
| `system/research/social_bot_detection/` | Internal trainable BotRHG transfer pipeline for labeled Weibo accounts. | System-readable research and checkpoint export; text-only transfer until property/social graph coverage is available. |
| `conductor/` | Product, technology, workflow, and active-track context. | Update before implementation and keep track status synchronized with verified work. |
| `doc/engineering/` | Long-lived engineering documentation. | Keep setup, governance, roadmap, project map, and development log aligned with code. |
| `doc/adr/` | Canonical architecture decision records and status index. | Never renumber an accepted record; record supersession in `index.md`. |
| `doc/research/` | Research positioning and literature notes. | Use for method positioning, references, and research context. |
| `aris/` | Historical research workspace. | Read for provenance; do not copy numbered workspace labels into current product language. |
| `research-wiki/` | Local research knowledge base and literature notes. | Local note workspace; do not commit generated local wiki output by default. |
| `MediaCrawler-main/`, `NewsCrawler-main/`, `CooRTweet-master/` | Reference boundaries. | Provenance, license review, and diffing only; never product runtime roots. |

## Governance Sources

- [system-governance.md](system-governance.md) is the normative source for naming, package boundaries, and structure rules.
- `doc/adr/index.md` is the ADR status source.
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
      app/core/analysis/              Analysis lifecycle and uniform stage ports
      app/core/crawler/               Crawler adapters and collect seam
      app/core/coordination_baseline/ Focused baseline modules plus compatibility facade
      app/core/propagation/           Propagation Analysis app support
      app/core/propagation_monitoring/ Shared monitoring interface
      app/core/semantic/              Semantic enrichment runtime
      app/core/review/                Internal Review runtime support
      app/services/analysis_governance_service.py
                                      Authenticated model and dispatch control plane
      app/services/review_case_*      Event Review Case service and orchestration
      scripts/                        Explicit local utility entrypoints
      tests/                          Backend regression and governance tests
    frontend/                         Dashboard and Event Review Case UI
    research/
      coordination_discover/          Coordination Discover research pipeline
      coordination_detect/            Coordination Detect validation boundary
      propagation_analysis/           Propagation Analysis protocol and baselines
      review_student/                  Student training and artifact export
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
