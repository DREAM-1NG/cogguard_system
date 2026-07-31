# CLAUDE.md

This repository separates product code from research workspaces. The active
product system is `system/`; upstream source trees and historical workspace
names are provenance unless a task explicitly targets them.

## Session Startup

Read maps before details:

1. `AGENTS.md`
2. `doc/engineering/project-map.md`
3. `doc/engineering/system-governance.md`
4. `doc/engineering/development-roadmap.md`
5. `system/README.md`
6. `UBIQUITOUS_LANGUAGE.md`

Read `research-wiki/` only for literature or claim work. Read a semantic
research package only when the task touches that capability.

## Scope Rule

- Product code lives under `system/`.
- Canonical capability names are `Coordination Discover`, `Coordination Detect`, `Propagation Analysis`, `Student Review`, and `Teacher Review`.
- Historical `aris/tech-*` directories may be read for provenance, but their numbered labels must not be copied into current code or documentation.
- Reference boundaries are `MediaCrawler-main/`, `NewsCrawler-main/`, and `CooRTweet-master/`; they are provenance only.

## Repository Rules

- Active baseline: `release-0.2`.
- Do not vendor upstream agent skills into this repository.
- Do not create a single repository-root research brief as the system source of truth.
- Stable Markdown and product code may be committed; generated outputs, logs, and local research artifacts remain local.
- Research changes should be recorded in the matching semantic package and reflected in the roadmap and development log.

## Documentation Sync

- Naming or package-boundary changes must update `doc/engineering/system-governance.md` and `UBIQUITOUS_LANGUAGE.md`.
- Runtime, setup, environment-variable, or integration changes must update `system/README.md` and `doc/engineering/environment-setup.md`.
- Status changes must update `doc/engineering/development-roadmap.md` and append a concise entry to `doc/engineering/development-log.md`.
