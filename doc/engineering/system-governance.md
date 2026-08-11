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
| System-readable research | `system/research/coordination_discover`, `system/research/coordination_detect`, `system/research/propagation_analysis`, `system/research/review_teacher`, `system/research/social_bot_detection` | Research code that is importable by product adapters but not a separate runtime dependency. |
| Documentation | `doc/engineering`, `doc/research` | Normative engineering docs and research notes. |
| Reference boundaries | `MediaCrawler-main`, `NewsCrawler-main`, `CooRTweet-master` | Provenance only; never runtime dependencies. |

Semantic research packages and deployable review runtimes are canonical
product boundaries. Compatibility aliases are limited to legacy application
paths such as `app.core.coordination` and `app.core.risk`, plus explicitly
named `*_legacy_alias` packages.

## Code Structure

```text
system/
  backend/
    app/
      api/v1/           legacy thin compatibility layer
      api/v2/           current Analysis and Case Workbench API surface
      core/
        analysis/       EventSnapshot, AnalysisRun, semantic enrichment, SSE, Coordination Discover, Propagation Analysis, Review ports, governance
        coordination_baseline/ CooRTweet-style fallback baseline implementation
        coordination/   legacy compatibility aliases for coordination_baseline
        crawler/        social/news/mock acquisition adapters
        propagation/    observed propagation projection and compatibility helpers
        review/         Review, Teacher, Student, and governance helpers
        risk/           legacy compatibility aliases for review
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
    review_teacher/        multi-agent Teacher DAG
    social_bot_detection/  trainable BotRHG Weibo transfer
    *_legacy_alias/        one-version import-only compatibility packages
  runtimes/
    social_runtime/    vendored social crawler runtime
    news_runtime/      vendored news extractor runtime
    review_student/    deployable Student runtime
    review_student_legacy_alias/ one-version import-only compatibility package
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

- `EventSnapshot`
- `AnalysisRun`
- `Analysis Stage`
- `Coordination Signal`
- `Coordination Discover`
- `Coordination Detect`
- `Evidence Object`
- `Evidence Graph`
- `Coordination Community`
- `Propagation Forecast`
- `ReviewVerdict`
- `Canonical Verdict`
- `Case`
- `Case Workbench`
- `Authority Source`
- `Case Claim`
- `Semantic Artifact`
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
- `system/research/*_legacy_alias` and `system/runtimes/*_legacy_alias` are import-only compatibility packages.
- `system/research/coordination_discover`, `system/research/coordination_detect`, `system/research/propagation_analysis`, `system/research/review_teacher`, and `system/runtimes/review_student` are canonical semantic boundaries.
- `system/research/social_bot_detection` is the canonical internal boundary for trainable BotRHG transfer. It must record dataset fingerprint, model checkpoint hash, missing property/social graph coverage, and comparison against a shallow reference baseline.
- `system/research/propagation_analysis` owns the deployed propagation sequence model and checkpoint. Public event prediction must use a timezone-aware observation cutoff, must not import `subsystems/`, and must abstain rather than invoke the legacy speed/acceleration runtime when the model is unavailable.

### Security And Deployment Contract

- `BACKEND_ENV=production` requires explicit `JWT_SECRET_KEY`,
  `DEFAULT_ADMIN_PASSWORD`, `MYSQL_PASSWORD`, `MONGO_PASSWORD`, and
  `REDIS_PASSWORD`; no public placeholder is accepted.
- `PREVIEW_AUTH_ENABLED` defaults to `false`. A preview token is accepted only
  when `BACKEND_ENV=local`, `BACKEND_DEBUG=true`, and
  `PREVIEW_AUTH_TOKEN` is explicitly configured. Dashboard access uses the
  shared security dependency and must not define a second token.
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
- Use `Coordination Discover`, `Coordination Detect`, `Propagation Analysis`, `Student Review`, and `Teacher Review`.
- Use `Analysis Run`, `Teacher Job`, and `Celery Task` for distinct lifecycle concepts; do not use them interchangeably.
- Use `Reference Boundary` for upstream source trees and `Vendored Runtime` for code executed from `system/runtimes/`.

## Structural Rules

- Prefer shallow packages with clear subdomains.
- Keep UI, API, runtime, research, and docs separate.
- Keep product API models in `schemas/`, persistent records in `models/`, and orchestration in `services/` or `core/`.
- Keep analysis lifecycle logic in `app/core/analysis/`.
- Keep Case Workbench orchestration and read projections in focused services under `app/services/`; long-lived Case persistence belongs in `app/models/` and API contracts in `app/schemas/` when the MVP becomes durable.
- Keep analysis capability-specific research logic in semantic research packages: `coordination_discover`, `coordination_detect`, `propagation_analysis`, and `review_teacher`.
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
