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
| `cogguard_system/` | Main engineering repository for CogGuard system development. | Edit for product code, engineering docs, ARIS workspaces, and reference-boundary notes. |
| `research-wiki/` | Research knowledge base: papers, ideas, claims, gap maps, novelty notes, and accumulated research status. | Edit for research notes and literature/claim tracking. |
| `_archive/` | Historical snapshots and pre-reposition archive material. | Read-only by default. |
| `.omx/`, `.omc/`, `.remember/`, `.claude/` | Agent/runtime/tooling state and local automation context. | Do not reorganize as part of project structure cleanup. |
| `nul` | Existing local artifact. | Leave untouched unless a separate cleanup task explicitly handles it. |

## Main Repository Boundaries

| Path | Role | Boundary |
| --- | --- | --- |
| `new-system/` | Current product system root. Contains the runnable backend, frontend, deployment configuration, and tests. | Product code only: keep implementations here when they are reachable through API/UI/tests/demo flows. |
| `aris/` | Research execution workspace for the three key technologies. | Use for technical exploration, experiment plans, acceptance criteria, reviews, and algorithm work before product integration. |
| `doc/` | Long-lived engineering and project documentation. | Use for PRD, setup, development log, project map, technical background, and migrated baseline/reference documents. |
| `system/runtimes/social_runtime/` | Vendored social crawler runtime used by the product. | Product runtime code; modify when crawler cutover or maintenance requires it. |
| `system/runtimes/news_runtime/` | Vendored news extraction runtime used by the product. | Product runtime code; modify when extractor cutover or maintenance requires it. |
| `MediaCrawler-main/` | Upstream social-media crawler reference boundary. | Reference only by default; not part of runtime execution path. |
| `NewsCrawler-main/` | Upstream news extraction reference boundary. | Reference only by default; not part of runtime execution path. |
| `CooRTweet-master/` | Upstream coordination-detection method reference. | Reference only by default; not part of runtime execution path. |

## Documentation Split

| Path | Role | Typical contents |
| --- | --- | --- |
| `doc/engineering/` | Runnable-system and project-governance documentation. | Product requirements, environment setup, roadmap/status, development log, project map. |
| `doc/research/` | Research positioning and technical exploration documentation. | Project positioning, literature references, key-technology background, algorithm notes. |

## Product vs Research Rule

Product system code belongs in `new-system/` only when it satisfies at least one
of these conditions:

- It is called by a backend service, API route, Celery task, or frontend page.
- It is covered by product-facing tests under `new-system/backend/tests/`.
- It is part of the runnable demo path described by `new-system/README.md`.
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

cogguard_system/
  new-system/
    backend/     FastAPI, Celery, MySQL/MongoDB/Redis access, product tests
    frontend/    Vue 3 + TypeScript management UI
    docker-compose.yml
  aris/
    tech-01-coordination/   Multi-behavior coordination and significance screening
    tech-02-propagation/    Propagation evidence chains, paths, and trend prediction
    tech-03-risk/           Risk assessment, DISARM mapping, structured reports
  doc/
    engineering/  PRD, setup, roadmap, development log, project map
    research/     positioning, literature, key-technology background, notes
  system/
    runtimes/
      social_runtime/
      news_runtime/
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
