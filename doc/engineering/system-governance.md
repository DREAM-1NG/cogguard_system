# CogGuard System Governance

> Normative source of truth for repository naming, package boundaries, and code layout.
> If this document conflicts with older docs, this document wins.

## Scope

This governance applies to:
- `system/` product code
- `doc/` long-lived engineering documentation
- `UBIQUITOUS_LANGUAGE.md` canonical domain glossary

It does not apply to archive material except for read-only reference.

## Canonical Layers

| Layer | Canonical paths | Rule |
| --- | --- | --- |
| Product shell | `system/backend`, `system/frontend` | Code reachable from product APIs, UI, tasks, or demo flows. |
| Product runtimes | `system/runtimes/social_runtime`, `system/runtimes/news_runtime`, `system/runtimes/review_student` | Vendored executable engines used by product code. |
| System-readable research | `system/research/coordination_discover`, `system/research/coordination_detect`, `system/research/propagation_analysis`, `system/research/review_student`, `system/research/review_teacher`, `system/research/social_bot_detection` | Research code that is importable by product adapters but not a separate runtime dependency. |
| Documentation | `doc/engineering`, `doc/research` | Normative engineering docs and research notes. |
| Reference boundaries | `MediaCrawler-main`, `NewsCrawler-main`, `CooRTweet-master` | Provenance only; never runtime dependencies. |

Semantic research packages and deployable review runtimes are canonical
product boundaries. Compatibility aliases are limited to legacy application
paths such as `app.core.coordination` and `app.core.risk`.

## Code Structure

```text
system/
  backend/
    app/
      api/v1/           legacy thin compatibility layer
      api/v2/           current product API surface
      core/
        analysis/       Analysis Run lifecycle, SSE, artifacts, and uniform stage adapters
        coordination_baseline/ focused fallback implementation modules plus compatibility facade
        coordination/   legacy compatibility aliases for coordination_baseline
        crawler/        social/news/mock acquisition adapters
        propagation/    observed propagation projection and compatibility helpers
        propagation_monitoring/ shared HTTP/Celery monitoring interface
        review/         Event Review Case orchestration, Review/Teacher/Student helpers, advisory routing, and governance
        risk/           legacy compatibility aliases for review
        semantic/       internal semantic enrichment runtime
        security.py     auth and crypto utilities
      models/           SQLAlchemy and persisted domain records
      schemas/          Pydantic request/response schemas
      services/         application services
      tasks/            Celery tasks
      db/               database clients and session factories
      utils/            cross-cutting helpers
  research/
    coordination_discover/ platform-generic Coordination Discover pipeline
    coordination_detect/   public-label Coordination Detect validation boundary
    propagation_analysis/  deployed sequence inference, checkpoint, and benchmark boundary
    review_student/        offline training, Hardcase selection, losses, and artifact export
    review_teacher/        multi-agent Teacher DAG
    social_bot_detection/  trainable BotRHG Weibo transfer
  runtimes/
    social_runtime/    vendored social crawler runtime
    news_runtime/      vendored news extractor runtime
    review_student/    deployable Student runtime
  frontend/
    src/
      api/             HTTP client wrappers
      views/           route-level pages
      components/      reusable UI components
      stores/          client state
      router/          navigation and guards
```

## Naming Rules

### Files and modules

- Use `snake_case.py` for Python modules.
- Use lowercase hyphenated names for docs: `system-governance.md`.
- Use `kebab-case` for top-level narrative docs and `snake_case` for code assets.
- One concept per file; split files that mix unrelated responsibilities.

### Packages

- Package names must be nouns or stable subdomain names.
- Add a subpackage only for a real subdomain, not for a single helper.
- Every public package boundary must define `__all__`.

### Classes and dataclasses

- Use `PascalCase`.
- Prefer domain nouns: `AnalysisRun`, `EventSnapshot`, `ReviewVerdict`.
- Use `...Request`, `...Response`, `...Options`, `...Config`, `...Manifest`, `...Record`, `...Runtime`, `...Port`, `...Engine`, `...Service`, `...Adapter`, `...Decision`.

### Functions

- Use verbs for behavior: `build_*`, `run_*`, `load_*`, `export_*`, `validate_*`, `approve_*`, `select_*`.
- Async functions keep the same verb form; the coroutine nature is implied by signature.

### Constants

- Use `UPPER_SNAKE_CASE`.
- Reserve constants for policy strings, allowlists, filenames, and hard boundaries.

### Tests

- Use `test_<module>_<behavior>.py`.
- Test names should state one behavior, not one implementation detail.

## Canonical Vocabulary

Use the glossary in `UBIQUITOUS_LANGUAGE.md` for domain terms. The system-level anchors are:

- `Event Review Case`
- `Preliminary Finding`
- `Review Advisory`
- `Confirmed Decision`
- `Evidence Sufficiency`
- `Evidence Annotation`
- `Case Activity`
- `Coordination Discover`
- `Coordination Detect`
- `Propagation Analysis`
- `Review`
- `EventSnapshot`
- `AnalysisRun`
- `Analysis Stage`
- `Coordination Signal`
- `Evidence Object`
- `Evidence Graph`
- `Coordination Community`
- `Propagation Forecast`
- `ReviewVerdict`
- `Canonical Verdict`
- `Artifact Manifest`
- `Strict Leiden Artifact`

## Boundary Rules

- Backend runtime code may not depend on `MediaCrawler-main`, `NewsCrawler-main`, or `CooRTweet-master`.
- Research packages may be imported only through explicit adapters or path loaders, never by `sys.path.insert`.
- `system/backend` wheel exports only `app`.
- `system/runtimes/*` are product code and may contain executable vendor logic, but not upstream docs, tests, or notebooks.
- `system/research/*` may contain training, evaluation, and export code, but should remain system-readable and small enough to load through explicit adapters.
- Legacy compatibility code must be thin mapping only; business logic lives in the current canonical module.
- `app.core.risk` and `app.core.coordination` are legacy application aliases.
- `system/backend/app/services/review_case_service.py` and `system/backend/app/api/v2/review_cases.py` are the product case boundary.
- `system/research/coordination_discover`, `system/research/coordination_detect`, `system/research/propagation_analysis`, `system/research/review_student`, `system/research/review_teacher`, and `system/runtimes/review_student` are canonical semantic boundaries.
- `system/research/social_bot_detection` is the canonical internal boundary for trainable BotRHG transfer. It must record dataset fingerprint, model checkpoint hash, missing property/social graph coverage, and comparison against a shallow reference baseline.
- `system/research/propagation_analysis` owns the deployed propagation sequence model and checkpoint. Public event prediction must use a timezone-aware observation cutoff, must not import `subsystems/`, and must abstain rather than invoke the legacy speed/acceleration runtime when the model is unavailable.
- `system/runtimes/review_student` owns checkpoint-gated XLM-R inference. It must return `shadow_untrained` and abstain when no compatible active checkpoint is available.
- `system/research/review_student` owns masked losses, staged training, external Hardcase routing, and artifact export; the model has no defer head.
- `app.core.analysis.stages` is the canonical Analysis Stage registry. New stages implement `AnalysisStagePort.execute(AnalysisStageContext)` instead of adding role-specific executor interfaces.

### Prototype Boundary

- The LAN/local prototype uses the existing login dependency for the event-review workspace; it does not introduce a second preview-only permission model.
- Internal activation remains a single accountable operator action. Do not add multi-approver activation payloads to the prototype surface.

### Durable Review And Model Governance

- The primary frontend is a business-facing Event Review Case workspace. It may show case state, Evidence Sufficiency, evidence references, the Preliminary Finding, Review Advisory differences, analyst activity, and the Confirmed Decision.
- Model versions, artifact paths and hashes, agent graphs, queue internals, active pointers, and rollback controls belong to the authenticated backend control plane. Do not add a technical governance page to the primary frontend.
- `ANALYSIS_TEACHER_DISPATCH_MODE=auto` permits `local_inline_fallback` only for local deployments. Production resolves to `queue_required`; a broker failure is persisted as a retryable failed Teacher advisory and is never silently completed in API process memory.
- `ANALYSIS_MODEL_ACTIVATION_APPROVAL_MODE=auto` permits one accountable operator locally. Production requires two distinct active administrator records in `analysis_model_activation_approvals`, created through authenticated approval actions; activation requests must not accept caller-supplied approver identities.
- Artifact hash verification and capability quality gates apply before both approval and activation. Rollback is an audited recovery action against a previously approved artifact.
- Teacher Review remains advisory and Canonical Verdict creation remains an analyst-owned action. Queue completion or model activation cannot create a Canonical Verdict.

### Security And Deployment Contract

- `BACKEND_ENV=production` requires explicit `JWT_SECRET_KEY`,
  `DEFAULT_ADMIN_PASSWORD`, `MYSQL_PASSWORD`, `MONGO_PASSWORD`, and
  `REDIS_PASSWORD`; no public placeholder is accepted.
- Production also requires the effective policies `queue_required` for Teacher
  dispatch and `dual_operator` for model activation. Leave both settings at
  `auto` unless a deployment profile explicitly sets a stricter mode.
- All authenticated API surfaces use the shared JWT bearer dependency. Local
  walkthroughs must log in as a real user or use an explicit test dependency
  override; static bearer-token bypasses are not part of the deployment
  contract.
- `ensure_default_admin` does not create an account when the seed password is
  empty. Production bootstrap must provide the password intentionally.

### Analysis Artifact Contract

- Every executed `AnalysisRun` produces an `artifact_manifest` keyed by stage.
  Each stage records technology, model version, artifact/checkpoint reference,
  status, fallback reason, and claimability.
- `claimable` is allowed only when the runtime explicitly reports that state,
  provides an artifact or checkpoint reference, and is not a fallback or
  missing-checkpoint path. Test doubles and generic `status=ok` responses are
  non-claimable by default.
- The manifest is persisted in `analysis_runs.artifact_manifest_json` when the
  SQL store is active and is included in the terminal run payload for local
  stores and API consumers.
- Model activation is fail-closed: registered artifact hashes must be standard
  SHA-256 values, local artifacts must match the digest, and remote URIs remain
  non-activatable until a deployment-specific resolver verifies their bytes.
- Feedback attached to a verdict must reference a verdict version belonging to
  the same Analysis Run. Repeated verdict versions do not weaken this ownership
  check.

### Terminology Gate

- Do not introduce numbered capability labels in code, file names, API fields, tests, or current documentation.
- Use `Event Review Case`, `Preliminary Finding`, `Review Advisory`, `Confirmed Decision`, `Evidence Sufficiency`, `Evidence Annotation`, `Case Activity`, `Coordination Discover`, `Coordination Detect`, `Propagation Analysis`, and `Review`.
- Use `AnalysisRun`, `Analysis Stage`, `Teacher Job`, and `Celery Task` only for internal diagnostic or runtime lifecycle concepts; do not use them interchangeably.
- `Student Review` and `Teacher Review` are runtime/research terms only and must not appear in product copy.
- Use `Reference Boundary` for upstream source trees and `Vendored Runtime` for code executed from `system/runtimes/`.

## Structural Rules

- Prefer shallow packages with clear subdomains.
- Keep UI, API, runtime, research, and docs separate.
- Keep product API models in `schemas/`, persistent records in `models/`, and orchestration in `services/` or `core/`.
- Keep analysis lifecycle logic in `app/core/analysis/`.
- Keep analysis capability-specific research logic in semantic research packages: `coordination_discover`, `coordination_detect`, `propagation_analysis`, `review_student`, and `review_teacher`.
- Keep Event Review Case orchestration, review advisory routing, and decision confirmation in `app/services/review_case_service.py` and `app/api/v2/review_cases.py`.
- Keep deployable ML/runtime code in `system/runtimes/*`.

## Governance Change Checklist

When introducing a new module, package, or term:

1. Add or update the relevant doc entry in this file.
2. Add or update the glossary in `UBIQUITOUS_LANGUAGE.md`.
3. Export the new public surface with `__all__`.
4. Add tests for the new public behavior.
5. Keep compatibility layers thin and reversible.

## Documentation Sync Contract

Every completed code task must perform a documentation sync before final reply:

1. If domain terms changed, update `UBIQUITOUS_LANGUAGE.md`.
2. If package structure or ownership changed, update this file and `doc/engineering/project-map.md`.
3. If the change affects status or priorities, update `doc/engineering/development-roadmap.md`.
4. If the change is a completed deliverable, add an entry to `doc/engineering/development-log.md`.
5. If the change records a lasting decision, add or update an ADR under `doc/adr/`.
6. If APIs, setup, or runtime behavior changed, update `README.md` or `system/README.md`.
7. If future agents need a new rule, update `AGENTS.md` and, when relevant, `CLAUDE.md`.

## Examples

- `coordination_discover_adapter.py` is an adapter, not a service.
- `review_student/runtime.py` is a runtime, not a research package.
- `analysis_runs` is a persisted record name, not a UI term.
- `model_activation` is a governance decision, not a training loop.
