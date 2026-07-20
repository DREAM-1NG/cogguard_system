# CogGuard Project Map

> **Purpose**: define project directory boundaries, default edit policies, and
> the engineering/research documentation split.  
> **Audience**: developers, research contributors, and future coding agents.  
> **Maintenance rule**: update this file whenever top-level directories,
> document locations, or default ownership boundaries change.

This document records the current lightweight project boundaries after the
workspace reorganization. The organizing rule is product-runnable first: code
that is wired into the backend, frontend, tests, or demonstration flow stays in
the product system; exploratory research and unproductized algorithm work stay
in the research workspaces.

## Top-Level Workspace

| Path | Role | Default edit policy |
| --- | --- | --- |
| `materials/` | Competition-facing materials: PPT, application forms, proposal/opening-report files, packaged submission assets. | Edit when preparing competition or application deliverables. |
| `.` | Current CogGuard engineering repository root. | Edit for product code, engineering docs, ARIS workspaces, and reference-boundary notes. |
| `research-wiki/` | Research knowledge base: papers, ideas, claims, gap maps, novelty notes, and accumulated research status. | Edit for research notes and literature/claim tracking. |
| `_archive/` | Historical snapshots and pre-reposition archive material. | Read-only by default. |
| `.omx/`, `.omc/`, `.remember/`, `.claude/` | Agent/runtime/tooling state and local automation context. | Do not reorganize as part of project structure cleanup. |
| `nul` | Existing local artifact. | Leave untouched unless a separate cleanup task explicitly handles it. |

## Main Repository Boundaries

| Path | Role | Boundary |
| --- | --- | --- |
| `system/` | Current product system root. Contains the runnable backend, frontend, deployment configuration, and tests. | Product code only: keep implementations here when they are reachable through API/UI/tests/demo flows. |
| `aris/` | Research execution workspace for the three key technologies. | Use for technical exploration, experiment plans, acceptance criteria, reviews, and algorithm work before product integration. |
| `doc/` | Long-lived engineering and project documentation. | Use for PRD, setup, development log, project map, technical background, and migrated baseline/reference documents. |
| `system/runtimes/social_runtime/` | Vendored social crawler runtime used by the product. | Product runtime code; modify when crawler cutover or maintenance requires it. |
| `system/runtimes/news_runtime/` | Vendored news extraction runtime used by the product. | Product runtime code; modify when extractor cutover or maintenance requires it. |
| `system/runtimes/review_student/` | Deployable KT3 Student runtime used by `StudentRuntime.predict(case)`. | Product runtime code; keep synchronous, checkpoint-gated, and governance-aware. |
| `system/research/coordination_discover/` | KT1 platform-generic Coordination Discover pipeline and artifact export boundary. | System-readable research boundary; backend consumes it only through analysis adapters. |
| `system/research/coordination_detect/` | KT1 public-label Coordination Detect validation boundary. | System-readable research boundary; validation only unless an approved artifact is activated. |
| `system/research/propagation_analysis/` | KT2 public loader, event bundle adapter, hindcast protocol, conformal intervals, and baseline registry. | System-readable research boundary; never point backend code at external research workspaces. |
| `system/research/review_teacher/` | KT3 multi-agent Teacher advisory DAG. | System-readable research runtime; advisory only, never canonical without analyst approval. |
| `MediaCrawler-main/` | Upstream social-media crawler reference boundary. | Reference only by default; not part of runtime execution path. |
| `NewsCrawler-main/` | Upstream news extraction reference boundary. | Reference only by default; not part of runtime execution path. |
| `CooRTweet-master/` | Upstream coordination-detection method reference. | Reference only by default; not part of runtime execution path. |

## Documentation Split

| Path | Role | Typical contents |
| --- | --- | --- |
| `doc/engineering/` | Runnable-system and project-governance documentation. | Product requirements, environment setup, roadmap/status, development log, project map. |
| `doc/research/` | Research positioning and technical exploration documentation. | Project positioning, literature references, key-technology background, algorithm notes. |

## Governance Sources

- [doc/engineering/system-governance.md](system-governance.md) is the normative source for repository naming, package boundaries, and code layout.
- [UBIQUITOUS_LANGUAGE.md](../../UBIQUITOUS_LANGUAGE.md) is the canonical glossary for domain terms, aliases to avoid, and relationship definitions.

## Product vs Research Rule

Product system code belongs in `system/` only when it satisfies at least one
of these conditions:

- It is called by a backend service, API route, Celery task, or frontend page.
- It is covered by product-facing tests under `system/backend/tests/`.
- It is part of the runnable demo path described by `system/README.md`.
- It defines stable schemas, models, configuration, or integration points used by the product.

Research work belongs in `aris/` or `research-wiki/` when it is:

- An algorithm idea, experiment plan, evaluation protocol, or review artifact.
- A technical proposal for KT1, KT2, or KT3 before product integration.
- Literature evidence, novelty analysis, claim tracking, or gap mapping.
- Prototype code or scratch output not yet connected to product APIs, UI, tests, or demos.

## Current Functional Map

```text
materials/
  Competition PPT, application forms, opening/proposal materials

CogGuard/
  system/
    backend/     FastAPI, Celery, MySQL/MongoDB/Redis access, product tests
    frontend/    Vue 3 + TypeScript management UI
    docker-compose.yml
    research/
      coordination_discover/ Platform-generic Coordination Discover pipeline
      coordination_detect/   Public-label Coordination Detect validation boundary
      propagation_analysis/  Propagation hindcast protocol and benchmark adapters
      review_teacher/        Multi-agent Teacher advisory DAG
    runtimes/
      review_student/        Synchronous deployable Student runtime
  aris/
    tech-01-coordination/   Multi-behavior coordination and significance screening
    tech-02-propagation/    Propagation evidence chains, paths, and trend prediction
    tech-03-risk/           Risk assessment, DISARM mapping, structured reports
  doc/
    engineering/  PRD, setup, roadmap, development log, project map
    research/     positioning, literature, key-technology background, notes
  system/runtimes/
    social_runtime/
    news_runtime/
    review_student/
  MediaCrawler-main/
  NewsCrawler-main/
  CooRTweet-master/

research-wiki/
  Papers, ideas, claims, experiments, gap map, research status
```

## Runtime Boundary Policy

Crawler runtime execution now happens inside `system/runtimes/`. The vendored
runtime trees are part of the product surface and should carry only the
minimum upstream core needed by the live system.

KT2 and KT3 research runtimes now have product-readable internal seams:
`system/research/propagation_analysis/runtime/protocol.py` is the KT2 hindcast protocol module,
and `system/research/review_teacher/dag.py` is the KT3 Teacher advisory module.
The deployable KT3 Student lives in `system/runtimes/review_student/`.
Backend code may call these internal seams through `EventSnapshot` / `AnalysisRun`
ports, but must not treat missing checkpoints as successful research results.

The upstream repositories remain in place only for provenance, license review,
and diffing against upstream behavior. Product execution, tests, docs, and
configuration should not depend on `MediaCrawler-main/`, `NewsCrawler-main/`,
or `CooRTweet-master/`.

## Migrated Root Documents

The following previously top-level markdown files now live in this directory and
can be rewritten or split in later documentation-focused tasks:

- `doc/research/project-positioning-baseline.md`
- `doc/research/literature-references.md`
- `doc/research/time-series-forecasting-notes.md`
