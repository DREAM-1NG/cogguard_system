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
| System-readable research | `system/research/coordination_discover`, `system/research/coordination_detect`, `system/research/propagation_analysis`, `system/research/review_teacher` | Research code that is importable by product adapters but not a separate runtime dependency. |
| Documentation | `doc/engineering`, `doc/research` | Normative engineering docs and research notes. |
| Reference boundaries | `MediaCrawler-main`, `NewsCrawler-main`, `CooRTweet-master` | Provenance only; never runtime dependencies. |

## Code Structure

```text
system/
  backend/
    app/
      api/v1/           legacy thin compatibility layer
      api/v2/           current product API surface
      core/
        analysis/       EventSnapshot, AnalysisRun, SSE, Coordination Discover, Propagation Analysis, Review ports, governance
        coordination_baseline/ CooRTweet-style fallback baseline implementation
        coordination/   legacy compatibility aliases for coordination_baseline
        crawler/        social/news/mock acquisition adapters
        propagation/    propagation heuristics and services
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
    propagation_analysis/  Propagation Analysis hindcast research pipeline
    review_teacher/        multi-agent Teacher DAG
    coordination_discover/, propagation_analysis/, review_teacher/ legacy compatibility aliases
  runtimes/
    social_runtime/    vendored social crawler runtime
    news_runtime/      vendored news extractor runtime
    review_student/    deployable Student runtime
    review_student/       legacy compatibility alias
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
- `Artifact Manifest`
- `Strict Leiden Artifact`

## Boundary Rules

- Backend runtime code may not depend on `MediaCrawler-main`, `NewsCrawler-main`, or `CooRTweet-master`.
- Research packages may be imported only through explicit adapters or path loaders, never by `sys.path.insert`.
- `system/backend` wheel exports only `app`.
- `system/runtimes/*` are product code and may contain executable vendor logic, but not upstream docs, tests, or notebooks.
- `system/research/*` may contain training, evaluation, and export code, but should remain system-readable and small enough to load through explicit adapters.
- Legacy compatibility code must be thin mapping only; business logic lives in the current canonical module.
- `app.core.risk`, `app.core.coordination`, `system/research/coordination_discover`, `system/research/propagation_analysis`, `system/research/review_teacher`, and `system/runtimes/review_student` are compatibility names only.

## Structural Rules

- Prefer shallow packages with clear subdomains.
- Keep UI, API, runtime, research, and docs separate.
- Keep product API models in `schemas/`, persistent records in `models/`, and orchestration in `services/` or `core/`.
- Keep analysis lifecycle logic in `app/core/analysis/`.
- Keep analysis capability-specific research logic in semantic research packages: `coordination_discover`, `coordination_detect`, `propagation_analysis`, and `review_teacher`.
- Keep deployable ML/runtime code in `system/runtimes/*`.

## Governance Change Checklist

When introducing a new module, package, or term:

1. Add or update the relevant doc entry in this file.
2. Add or update the glossary in `UBIQUITOUS_LANGUAGE.md`.
3. Export the new public surface with `__all__`.
4. Add tests for the new public behavior.
5. Keep compatibility layers thin and reversible.

## Examples

- `coordination_discover_adapter.py` is an adapter, not a service.
- `review_student/runtime.py` is a runtime, not a research package.
- `analysis_runs` is a persisted record name, not a UI term.
- `model_activation` is a governance decision, not a training loop.

