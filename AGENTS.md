# CogGuard Agent Context

This repository is a competition-oriented open source prototype for cross-platform coordinated manipulation analysis.
Future coding sessions should treat this file as the quick-start project context.

## Baseline

- Active engineering baseline: `release-0.2`
- Do not use `main` as the source of truth for implementation status until it is explicitly synced.
- Current active system lives in `system/`.

## Read Before Coding

Read these files before making substantial changes:

1. `doc/engineering/development-roadmap.md`
2. `doc/engineering/environment-setup.md`
3. `doc/engineering/development-log.md`
4. `system/README.md`
5. `UBIQUITOUS_LANGUAGE.md`
6. `doc/engineering/system-governance.md`
7. `README.md`
8. If the task is ARIS-driven or targets one of the three key technologies, also read:
   - `aris/README.md`
   - the selected `aris/tech-*/README.md`
   - the selected `aris/tech-*/ACCEPTANCE.md`
   - the matching `doc/research/key-technology-background/*.md`

If code and docs disagree, trust code first, then update docs in the same change.

## Project Scope

- Core goal: evidence-driven detection of cross-platform coordinated manipulation.
- Preferred system narrative: `事件 -> 证据 -> 协同 -> 传播 -> 风险 -> 处置`
- Avoid reverting to the older headline of `bot detection + 意图识别`.
- KT1 method language is **Coordination Discover** + **Coordination Detect**.
- Short-term validation scope: `mock_weibo`, `weibo`, `news`
- Treat `MediaCrawler-main`, `NewsCrawler-main`, and `CooRTweet-master` as reference or dependency boundaries unless the user explicitly asks to modify them.

## Expected Engineering Behavior

- Keep documentation aligned with the real implementation.
- Perform **Documentation Sync** before reporting a task complete.
- When code changes terminology, ownership, public APIs, or run flow, update
  `UBIQUITOUS_LANGUAGE.md`, `doc/engineering/system-governance.md`, and the
  relevant README/ADR in the same change.
- For major feature work, update at least:
  - `doc/engineering/development-roadmap.md`
  - `doc/engineering/development-log.md`
  - `README.md` or `system/README.md` when behavior or architecture changes
  - `docs/adr/` when the decision should remain durable
- Prefer extending `system/backend/app/` and `system/frontend/src/` rather than adding duplicate entrypoints elsewhere.
- Keep risk, coordination, and propagation outputs evidence-backed and explainable.
- Do not vendor upstream ARIS skill code into this repository; keep only local workspace docs under `aris/`.

## ARIS Workspaces

- `aris/` is the execution workspace layer for the three key technologies.
- Do not create a repository-root `RESEARCH_BRIEF.md`; use the selected `aris/tech-*` workspace instead.
- For ARIS-driven work, branch from `release-0.2` and keep one branch per technology line.

## Current Gaps

As of the `release-0.2` baseline:

- Coordination exists, but multi-behavior evidence fusion and significance filtering still need strengthening.
- Propagation exists, but evidence-chain extraction and key-path presentation are still evolving.
- Risk analysis is MVP-stage and should stay rule/evidence-driven before deeper LLM integration.
- Dashboard, alerts, reports, and end-to-end validation remain lighter than the core analysis pipeline.

## Notes For Future Sessions

- If a task touches algorithm behavior, prefer adding unit tests under `system/backend/tests/`.
- If a task changes project status or roadmap interpretation, update the docs in the same turn.
- If a future session needs a clean implementation starting point, branch from `release-0.2`, not `main`.
