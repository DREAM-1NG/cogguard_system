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
| `CogGuard/` | Main engineering repository for CogGuard system development. | Edit for product code, engineering docs, ARIS workspaces, and reference-boundary notes. |
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
| `docs/adr/` | Architecture decision records. | Add or update when package boundaries, method boundaries, or governance rules change. |
| `UBIQUITOUS_LANGUAGE.md` | Canonical cross-system vocabulary. | Update when a task changes terminology or resolves ambiguity. |
| `MediaCrawler-main/` | Upstream social-media crawler reference/dependency boundary. | Keep in place; do not modify by default. |
| `NewsCrawler-main/` | Upstream news extraction reference/dependency boundary. | Keep in place; do not modify by default. |
| `CooRTweet-master/` | Upstream coordination-detection method reference. | Keep in place; do not modify by default. |

## Documentation Split

| Path | Role | Typical contents |
| --- | --- | --- |
| `doc/engineering/` | Runnable-system and project-governance documentation. | Product requirements, environment setup, roadmap/status, development log, project map. |
| `doc/research/` | Research positioning and technical exploration documentation. | Project positioning, literature references, key-technology background, algorithm notes. |
| `docs/adr/` | Durable architecture decisions. | System governance, method boundaries, and long-lived design decisions. |

## Governance Sources

- `UBIQUITOUS_LANGUAGE.md` is the canonical vocabulary for code, docs, and agent sessions.
- `doc/engineering/system-governance.md` is the canonical structure and documentation sync contract.
- `docs/adr/` records durable decisions that should not be rediscovered in later sessions.

## Product vs Research Rule

Product system code belongs in `system/` only when it satisfies at least one
of these conditions:

- It is called by a backend service, API route, Celery task, or frontend page.
- It is covered by product-facing tests under `system/backend/tests/`.
- It is part of the runnable demo path described by `system/README.md`.
- It defines stable schemas, models, configuration, or integration points used by the product.

Research work belongs in `aris/` or `research-wiki/` when it is:

- An algorithm idea, experiment plan, evaluation protocol, or review artifact.
- A technical proposal for Coordination Discover, Coordination Detect, Propagation Analysis, or Risk Review before product integration.
- Literature evidence, novelty analysis, claim tracking, or gap mapping.
- Prototype code or scratch output not yet connected to product APIs, UI, tests, or demos.

## Backend Core Naming Map

| Path | Role | Boundary |
| --- | --- | --- |
| `system/backend/app/core/coordination_discover/` | Canonical Coordination Discover facade. | Use for new discovery-facing backend imports, including event-table normalization and evidence graph rerun helpers; keep it thin and free of independent business logic while `coordination/` remains the baseline implementation. |
| `system/backend/app/core/coordination_detect/` | Canonical Coordination Detect facade. | Use for new detect/validation-facing backend imports, including pretrained detect and label extraction helpers; keep it thin and free of independent business logic while `coordination/` remains the baseline implementation. |
| `system/backend/app/core/coordination/` | Current CooRTweet-style coordination baseline implementation and compatibility layer. | Keep existing imports working during the one-version semantic migration window. |
| `system/backend/app/core/propagation_analysis/` | Canonical Propagation Analysis facade. | Use for new propagation backend imports; keep it thin and free of independent business logic while `propagation/` and `propagation_legacy.py` remain the implementation surface. |
| `system/backend/app/core/propagation/`, `system/backend/app/core/propagation_legacy.py` | Current propagation implementation and compatibility layer. | Keep existing imports working during the one-version semantic migration window. |
| `system/backend/app/core/review/` | Canonical Risk Review facade. | Use for new backend imports; keep it thin and free of independent business logic while `risk/` remains the implementation package. |
| `system/backend/app/core/risk/` | Current Risk Review implementation and compatibility layer. | Keep existing imports working during the one-version semantic migration window. |

## Current Functional Map

```text
materials/
  Competition PPT, application forms, opening/proposal materials

CogGuard/
  system/
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
  MediaCrawler-main/
  NewsCrawler-main/
  CooRTweet-master/

research-wiki/
  Papers, ideas, claims, experiments, gap map, research status
```

## Reference Project Policy

The three bundled reference projects are intentionally left in their existing
locations to avoid breaking paths already used by documentation, configuration,
or local experiments. Treat them as external/reference boundaries unless a task
explicitly says to modify them.

If product code needs functionality from a reference project, add a wrapper or
integration point under `system/` and document the dependency. Do not mix
active CogGuard product code into the reference project directories.

## Migrated Root Documents

The following previously top-level markdown files now live in this directory and
can be rewritten or split in later documentation-focused tasks:

- `doc/research/project-positioning-baseline.md`
- `doc/research/literature-references.md`
- `doc/research/time-series-forecasting-notes.md`
