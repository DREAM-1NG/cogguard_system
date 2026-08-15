# Structural Context Follow-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep project memory aligned with the Event Review Case product boundary and remove duplicate analysis-stage aliases without changing product behavior.

**Architecture:** `conductor/` supplies concise maintained context; `UBIQUITOUS_LANGUAGE.md` and system governance remain normative. `app.core.analysis.contracts` owns stage canonicalization behind `normalize_analysis_stage()`.

**Tech Stack:** Markdown, TOML, JSON, Python 3.11, pytest.

## Global Constraints

- Work only in `G:\CISCN\CogGuard\.worktrees\refactor-system` on `coordination/deep-detection-upgrade`.
- Do not reset, clean, amend, stage, modify, or commit existing dirty semantic, propagation, Coordination, frontend, output, or Playwright files.
- `system/` is the Product System; `MediaCrawler-main/`, `NewsCrawler-main/`, and `CooRTweet-master/` are Reference Boundaries.
- Event Review Case remains the product-facing aggregate.
- Semantic Evidence Assistance remains auxiliary evidence and must not change Coordination Discover, Propagation Analysis, Review, Preliminary Finding, Review Advisory, or Confirmed Decision.
- Preserve every normalized stage value and `DEFAULT_ANALYSIS_STAGES`.

---

### Task 1: Synchronize maintained context and executable metadata

**Files:**
- Modify: `conductor/product.md`
- Modify: `conductor/product-guidelines.md`
- Modify: `UBIQUITOUS_LANGUAGE.md`
- Modify: `system/backend/pyproject.toml`
- Modify: `system/frontend/package.json`
- Modify: `conductor/tracks.md`
- Modify: `.superpowers/sdd/progress.md`

**Interfaces:**
- Consumes: the Event Review Case product boundary in `CONTEXT.md` and ADR 0007.
- Produces: context and package descriptions that describe the local/LAN Event Review Case prototype.

- [ ] Replace the `conductor/product.md` product flow with:

```text
Event Review Case -> evidence -> Coordination Discover / Propagation Analysis / Review -> findings and advisory -> Confirmed Decision -> governance action
```

- [ ] Add this row under the Event Review Case table in `UBIQUITOUS_LANGUAGE.md`:

```markdown
| **Semantic Evidence Assistance** | Auxiliary, model-derived evidence projections such as keywords, topics, sentiment, stance, and entities that help an analyst inspect an Event Review Case without changing its conclusions. | Semantic enrichment, semantic result, model conclusion |
```

- [ ] Replace semantic-enrichment wording in `conductor/product.md` and `conductor/product-guidelines.md` with the exact canonical term **Semantic Evidence Assistance**.
- [ ] Set the backend description to `CogGuard - local/LAN evidence-driven Event Review Case prototype`.
- [ ] Set the frontend description to `CogGuard 前端 - 本地/LAN 事件研判案例工作台`.
- [ ] Run `git diff --check`, inspect only task files, then commit only task-owned files with `docs(context): align case workflow terminology`.

---

### Task 2: Deduplicate analysis-stage aliases behind the canonicalization seam

**Files:**
- Modify: `system/backend/app/core/analysis/contracts.py`
- Modify: `system/backend/tests/test_analysis_contracts.py`
- Modify: `conductor/tracks.md`
- Modify: `.superpowers/sdd/progress.md`

**Interfaces:**
- Consumes: `normalize_analysis_stage(stage: Any) -> str` and `UnknownAnalysisStage`.
- Produces: one canonical `ANALYSIS_STAGE_ALIASES` mapping with unchanged normalized values.

- [ ] Add a failing test that parses `app.core.analysis.contracts.__file__` with `ast.parse`, finds the `ANALYSIS_STAGE_ALIASES` dictionary literal, and asserts its string keys have no duplicates. Python overwrites duplicate dictionary keys during import, so this source-level assertion is the required RED evidence for a behavior-preserving cleanup. In the same test, retain the public normalization assertions:

```python
assert len(alias_keys) == len(set(alias_keys))
assert normalize_analysis_stage("review_student") == "student"
assert normalize_analysis_stage("review_teacher") == "teacher"
assert normalize_analysis_stage("semantic") == "semantic_enrichment"
```

- [ ] Verify the test fails because the mapping currently repeats the two review entries.
- [ ] Remove only the second repeated `review_student` and `review_teacher` entries in `contracts.py`.
- [ ] Run `uv run --no-sync python -m pytest tests/test_analysis_contracts.py tests/test_analysis_executor.py -q` from `system/backend`.
- [ ] Run `git diff --check`, inspect only task files, then commit only task-owned files with `refactor(analysis): deduplicate stage aliases`.

## Final Validation

Run `uv run --no-sync python -m pytest tests/test_analysis_contracts.py tests/test_analysis_review_runtime.py tests/test_analysis_executor.py -q` from `system/backend`, then `git diff --check`. Conduct a whole-branch review from `5ae88ad` through the final structural commit.
