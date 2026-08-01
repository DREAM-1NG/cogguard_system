# CogGuard Project Map

This file defines repository boundaries, default edit ownership, and the split
between product code, system-readable research, reference code, and local
research notes. If this file conflicts with older documents, this file wins.

## Main Boundaries

| Path | Role | Default edit policy |
| --- | --- | --- |
| `system/` | Active product system: backend, frontend, deployment files, vendored runtimes, system-readable research packages, and tests. | Edit for runnable system work. |
| `system/backend/` | FastAPI, Celery, MySQL/MongoDB/Redis access, services, tasks, schemas, and backend tests. | Edit for product backend behavior. |
| `system/frontend/` | Vue 3 and TypeScript UI. | Edit for product UI work only; current governance cleanup does not change the display pages. |
| `system/runtimes/social_runtime/` | Vendored social crawler runtime for `weibo`, `douyin`, and `xhs`. | Product runtime code; keep dependencies local to this runtime. |
| `system/runtimes/news_runtime/` | Vendored news extraction runtime for `news`. | Product runtime code; keep dependencies local to this runtime. |
| `system/runtimes/review_student/` | Deployable Student Review runtime used by `StudentRuntime.predict(case)`. | Product runtime code; keep synchronous, checkpoint-gated, and governance-aware. |
| `system/research/coordination_discover/` | Platform-generic Coordination Discover pipeline and artifact export boundary. | System-readable research; backend consumes it through analysis adapters. |
| `system/research/coordination_detect/` | Public-label Coordination Detect validation boundary. | Validation boundary; do not label unlabeled project events. |
| `system/research/propagation_analysis/` | Propagation Analysis loaders, hindcast protocol, conformal intervals, and baseline registry. | System-readable research; do not point product code at external research workspaces. |
| `system/research/review_teacher/` | Multi-agent Teacher Review advisory DAG. | System-readable research; advisory only unless an analyst approves a canonical verdict. |
| `system/research/social_bot_detection/` | Internal trainable BotRHG transfer pipeline for labeled Weibo accounts. | System-readable research and checkpoint export; text-only transfer until property/social graph coverage is available. |
| `doc/engineering/` | Long-lived engineering documentation. | Keep setup, governance, roadmap, project map, and development log aligned with code. |
| `doc/adr/` | Accepted architecture decision records. | One numbered file per durable decision; never renumber an accepted record in place. |
| `doc/research/` | Research positioning and literature notes. | Use for method positioning, references, and research context. |
| `aris/` | Historical research workspace. | Read for provenance; do not copy numbered workspace labels into current product language. |
| `research-wiki/` | Local research knowledge base and literature notes. | Local note workspace; do not commit generated local wiki output by default. |
| `MediaCrawler-main/`, `NewsCrawler-main/`, `CooRTweet-master/` | Reference boundaries. | Provenance, license review, and diffing only; never product runtime roots. |

## Governance Sources

- [system-governance.md](system-governance.md) is the normative source for naming, package boundaries, and structure rules.
- `doc/adr/` holds the accepted decision records behind those boundaries.
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
      app/core/review/                Risk Review app support
      scripts/                        Explicit local utility entrypoints
      tests/                          Backend regression and governance tests
    frontend/                         Vue 3 + TypeScript UI
    research/
      coordination_discover/          Coordination Discover research pipeline
      coordination_detect/            Coordination Detect validation boundary
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
