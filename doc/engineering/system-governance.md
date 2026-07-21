# CogGuard System Governance

> This is the normative source for package boundaries, code structure, naming,
> and documentation synchronization. If this file conflicts with older docs,
> update the older docs in the same change.

## Governance Sources

| Source | Purpose |
| --- | --- |
| `UBIQUITOUS_LANGUAGE.md` | Canonical domain vocabulary and ambiguity rules. |
| `doc/engineering/project-map.md` | Repository boundaries and default edit policies. |
| `doc/engineering/system-governance.md` | Code structure, public boundaries, and development pipeline rules. |
| `docs/adr/` | Durable architecture and method decisions. |
| `doc/engineering/development-log.md` | Chronological engineering change record. |
| `doc/engineering/development-roadmap.md` | Current status, priorities, and known gaps. |

## Canonical Repository Layers

| Layer | Canonical path | Rule |
| --- | --- | --- |
| Product system | `system/` | Runnable backend, frontend, deployment config, and product tests. |
| Backend application | `system/backend/app/` | FastAPI app, services, core domain modules, tasks, models, schemas, and DB clients. |
| Frontend application | `system/frontend/` | Vue UI and browser-facing API wrappers. |
| ARIS workspace | `aris/` | Research planning, acceptance, and technical workspaces before product integration. |
| Engineering docs | `doc/engineering/` | Long-lived runnable-system docs, governance, status, and setup. |
| Research docs | `doc/research/` | Research positioning, literature, and method background. |
| ADRs | `docs/adr/` | Accepted or proposed architecture decisions. |
| Reference boundaries | `MediaCrawler-main/`, `NewsCrawler-main/`, `CooRTweet-master/` | Provenance/reference only unless a task explicitly changes them. |

## Python Structure Rules

- Keep `system/backend/app/api/` for HTTP route wiring only.
- Keep orchestration in `system/backend/app/services/` or `system/backend/app/tasks/`.
- Keep reusable domain logic in `system/backend/app/core/<domain>/`.
- Keep persistence models in `system/backend/app/models/` and request/response contracts in `system/backend/app/schemas/`.
- Add focused modules when a file starts owning a second concept; do not keep expanding monoliths.
- Every new public module should define `__all__`.
- Prefer absolute imports from `app.*` inside backend code.
- Tests live under `system/backend/tests/` and should name behavior, not implementation trivia.

## Current Domain Boundaries

| Boundary | Path | Rule |
| --- | --- | --- |
| Crawler | `system/backend/app/core/crawler/` | Acquisition and normalization only. |
| Coordination Discover / Detect | `system/backend/app/core/coordination/` | KT1 coordination baseline and research adapters; the package name remains `coordination` until a tested semantic migration is approved. |
| Propagation | `system/backend/app/core/propagation/`, `system/backend/app/core/propagation.py` | KT2 spread and trend analysis. |
| Risk Review | `system/backend/app/core/risk/` | KT3 review, harmfulness, DISARM, Teacher/Student research code, and reporting. |
| KT3 Agent Contracts | `system/backend/app/core/risk/kt3_agent_contracts.py` | Manual Agent report sections, prompt builders, output contracts, report roles, and safety flags. |
| KT3 Agent Media | `system/backend/app/core/risk/kt3_agent_media.py` | Manual Agent media input extraction, visual payload gating, data URL conversion, and provider bundle trimming; review orchestration must not own raw media transfer policy. |
| KT3 Agent Provider | `system/backend/app/core/risk/kt3_agent_provider.py` | OpenAI-compatible LLM provider config, HTTP wire adapters, retries, and settings factory; review orchestration must import this boundary instead of owning provider HTTP details. |
| KT3 Agent Runtime | `system/backend/app/core/risk/kt3_agent_runtime.py` | Agent ordering, alias normalization, simple/complex runtime selection, execution plan, post-judge countermeasure gating, candidate rule hints, and failure tags. |
| Teacher Silver | `system/backend/app/core/risk/kt3_teacher_silver.py` | Structured Teacher supervision contract. |
| Selective Student | `system/backend/app/core/risk/kt3_selective_student.py` | KT3 2+1 Student targets, model, training, prediction, and metrics. |
| PropagationTreeAgent Boundary | `system/backend/app/core/risk/kt3_propagation_agent.py` | Field-constrained PropagationTreeAgent prompt contract, evidence eligibility, and context selection rules. |
| Propagation Context | `system/backend/app/core/risk/kt3_propagation_context.py` | Compact thread evidence bundle for `PropagationTreeAgent`; claim lists or reaction counts must not masquerade as thread structure. |
| Trainable Post Features | `system/backend/app/core/risk/kt3_trainable_post.py` | Shared post feature extraction, legacy view experiments, fusion, and compatibility exports. |

## Naming Rules

- Use the terms in `UBIQUITOUS_LANGUAGE.md` for domain language.
- Use **Coordination Discover** and **Coordination Detect** for KT1 method language; reserve "coordination detection" for legacy API/page names that have not been migrated.
- Use `snake_case.py` for Python modules and `kebab-case.md` for narrative docs.
- Use `PascalCase` for classes and dataclasses.
- Use verb-first functions such as `build_*`, `load_*`, `run_*`, `train_*`, `predict_*`, `export_*`, and `validate_*`.
- Do not use the historical product-root alias in current docs or code; the product root is `system/`.
- Do not use `risk score` when the intended concept is **Risk Review** or **Harmfulness Judgment**.

## Documentation Sync Contract

Every completed code task must perform a documentation sync before final reply:

1. If domain terms changed, update `UBIQUITOUS_LANGUAGE.md`.
2. If package structure or ownership changed, update this file and `doc/engineering/project-map.md`.
3. If the change affects status or priorities, update `doc/engineering/development-roadmap.md`.
4. If the change is a completed deliverable, add an entry to `doc/engineering/development-log.md`.
5. If the change records a lasting decision, add or update an ADR under `docs/adr/`.
6. If APIs, setup, or runtime behavior changed, update `README.md` or `system/README.md`.
7. If future agents need a new rule, update `AGENTS.md` and, when relevant, `CLAUDE.md`.

## Completion Gate For Agents

Before reporting completion, Codex or Claude must check:

- Relevant tests were run, or an explicit reason is recorded.
- Documentation sync was performed for the changed scope.
- `git status --short` was inspected.
- No new code path relies on reference directories unless explicitly requested.
- Any unverified runtime, frontend, or live external dependency is named as a residual risk.

## Refactor Policy

- Lock behavior with targeted tests before cleanup.
- Delete dead code before adding new abstraction.
- Split by concept, not by arbitrary size.
- Keep compatibility layers thin and temporary.
- Do not rename broad public surfaces without an ADR.
- Prefer small, reviewable patches over one sweeping rewrite.
