# CogGuard Agent Context

This repository is a competition-oriented open source prototype for cross-platform coordinated manipulation analysis.
Future coding sessions should treat this file as the quick-start project context.

## Baseline

- The active product source lives in `system/`.
- Verify the current branch and worktree with Git before editing; do not infer implementation status from `main` or a historical release branch.
- Treat code plus passing verification as the implementation source of truth, then synchronize documentation in the same change.

## Read Before Coding

Read these files before making substantial changes:

1. `conductor/index.md`
2. `conductor/tracks.md` and the active track
3. `doc/engineering/development-roadmap.md`
4. `doc/engineering/environment-setup.md`
5. `doc/engineering/development-log.md`
6. `system/README.md`
7. `UBIQUITOUS_LANGUAGE.md`
8. `doc/engineering/system-governance.md`
9. `README.md`
10. If the task is ARIS-driven or targets a research capability, also read:
   - `aris/README.md`
   - the selected `aris/tech-*/README.md`
   - the selected `aris/tech-*/ACCEPTANCE.md`
   - the matching `doc/research/key-technology-background/*.md`

If code and docs disagree, trust code first, then update docs in the same change.

## Project Scope

- Core goal: evidence-driven detection of cross-platform coordinated manipulation.
- Preferred system narrative: `事件 -> 证据 -> 协同 -> 传播 -> 风险 -> 处置`
- Avoid reverting to the older headline of `bot detection + 意图识别`.
- The formal method language is **Coordination Discover** + **Coordination Detect**.
- Production crawl platforms are `weibo`, `douyin`, `xhs`, and `news`; `mock_weibo` is test-only.
- Treat `MediaCrawler-main`, `NewsCrawler-main`, and `CooRTweet-master` as reference boundaries, never product runtime roots.
- The product boundary is the **Event Review Case**. `/dashboard` is the dashboard-first home and `/risk` is the single case workspace.
- Keep Event Snapshot, Analysis Run, Student Review, Teacher Review, model versions, checkpoints, artifacts, and queue identifiers out of product copy and product API projections.
- Do not add a model-governance UI or a second core page. Governance remains an authenticated backend concern for the LAN/competition prototype.

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
  - `doc/adr/` when the decision should remain durable
- Prefer extending `system/backend/app/` and `system/frontend/src/` rather than adding duplicate entrypoints elsewhere.
- Keep Review, Coordination Discover, Coordination Detect, and Propagation Analysis outputs evidence-backed and explainable.
- Do not vendor upstream ARIS skill code into this repository; keep only local workspace docs under `aris/`.

## ARIS Workspaces

- `aris/` is the execution workspace layer for the three key technologies.
- Do not create a repository-root `RESEARCH_BRIEF.md`; use the selected `aris/tech-*` workspace instead.
- For ARIS-driven work, branch from `release-0.2` and keep one branch per technology line.

## Current Product Contract

- A successful event-scoped crawl upserts one **Event Review Case** and appends an immutable snapshot revision when its data fingerprint changes.
- New revisions run Coordination Discover, Propagation Analysis, and the synchronous preliminary review; an asynchronous review advisory is routed only by policy or analyst request.
- Analysts may annotate evidence and autosave a decision draft. A **Confirmed Decision** is immutable and later data or advice creates a reconfirmation action instead of overwriting it.
- Product responses and UI expose business conclusions, evidence sufficiency, urgency, disposition, summaries, evidence, and case activities. Internal runtime and governance details stay behind authenticated diagnostic boundaries.
- The prototype targets authenticated local or LAN deployment. It does not claim public-production authorization or tenancy controls.

## Notes For Future Sessions

- If a task touches algorithm behavior, prefer adding unit tests under `system/backend/tests/`.
- If a task changes project status or roadmap interpretation, update the docs in the same turn.
- Before branch integration, run the full backend suite, frontend tests and production build, migration round-trip, and a real authenticated desktop workflow against the current approved branch.
- Commits use the Lore commit protocol defined by the workspace orchestration contract.
