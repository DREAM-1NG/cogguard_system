# Analysis Review Runtime Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove obsolete deterministic Review builders and make the active `app.core.analysis.runtime` module interface explicit without changing Event Review Case, Analysis Run, worker, or product behavior.

**Architecture:** `app.core.analysis.runtime` is the internal runtime module behind the existing Student and Teacher ports. The active runtime loader, asynchronous Teacher dispatch, persistence, and fallback classification remain in that module. The two `_legacy_build_*` functions are unused historical implementations and are deleted rather than moved. An explicit `__all__` documents the stable import surface and keeps later adapter extraction from depending on retired implementation details.

**Tech Stack:** Python 3.11, pytest, FastAPI application modules.

## Global Constraints

- Work only in `G:\CISCN\CogGuard\.worktrees\refactor-system` on branch `coordination/deep-detection-upgrade`.
- Do not reset, clean, stage, modify, or commit pre-existing dirty files outside this task.
- Do not change Review verdict contents, Teacher dispatch policy, persistence, runtime loading, queue behavior, model identity, API routes, database records, or frontend behavior.
- Preserve the `AnalysisEnginePorts` seam and do not modify `app/core/analysis/executor.py`, which contains unrelated in-progress Coordination work.
- `Event Review Case` remains the product boundary; runtime-only terms stay out of product-facing copy.
- Every new behavior test must be written and observed failing before production code is changed.
- Commit only this task's files with the repository Lore commit protocol.

---

### Task 1: Retire inactive Review builders and declare the runtime interface

**Files:**
- Modify: `system/backend/app/core/analysis/runtime.py:1-378`
- Modify: `system/backend/tests/test_analysis_review_runtime.py:1-18`
- Modify: `doc/engineering/system-governance.md`
- Modify: `conductor/tracks.md`
- Modify: `.superpowers/sdd/progress.md`

**Interfaces:**
- Consumes: existing direct imports from `app.core.analysis.runtime` and the current Student/Teacher runtime adapters.
- Produces: `runtime.__all__` containing exactly `ANALYSIS_STUDENT_MODEL_VERSION`, `ANALYSIS_TEACHER_MODEL_VERSION`, `ANALYSIS_TEACHER_SOURCE`, `InternalStudentRuntime`, `InternalTeacherJobPort`, `build_student_verdict`, `build_teacher_advisory_verdict`, `build_teacher_advisory_verdict_async`, `submit_teacher_review_job`, `finalize_teacher_review_job`, and `mark_teacher_review_failed`.
- Invariant: `_legacy_build_student_verdict` and `_legacy_build_teacher_advisory_verdict` are absent after the change; every active public function retains its existing name and behavior.

- [ ] **Step 1: Write the failing contract test**

Add this test immediately after the existing `from app.core.analysis.runtime import ...` imports in `system/backend/tests/test_analysis_review_runtime.py`:

```python
def test_runtime_exposes_only_active_review_entry_points():
    assert set(runtime.__all__) == {
        "ANALYSIS_STUDENT_MODEL_VERSION",
        "ANALYSIS_TEACHER_MODEL_VERSION",
        "ANALYSIS_TEACHER_SOURCE",
        "InternalStudentRuntime",
        "InternalTeacherJobPort",
        "build_student_verdict",
        "build_teacher_advisory_verdict",
        "build_teacher_advisory_verdict_async",
        "submit_teacher_review_job",
        "finalize_teacher_review_job",
        "mark_teacher_review_failed",
    }
    assert not hasattr(runtime, "_legacy_build_student_verdict")
    assert not hasattr(runtime, "_legacy_build_teacher_advisory_verdict")
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
cd system\backend
uv run python -m pytest tests/test_analysis_review_runtime.py::test_runtime_exposes_only_active_review_entry_points -q
```

Expected: failure because one or both `_legacy_build_*` attributes still exist (or because `runtime.__all__` does not yet exist). Record the relevant failure in the task report.

- [ ] **Step 3: Apply the minimum behavior-preserving cleanup**

In `system/backend/app/core/analysis/runtime.py`, immediately after `TEACHER_JOB_CACHE`, add the following exact module interface:

```python
__all__ = [
    "ANALYSIS_STUDENT_MODEL_VERSION",
    "ANALYSIS_TEACHER_MODEL_VERSION",
    "ANALYSIS_TEACHER_SOURCE",
    "InternalStudentRuntime",
    "InternalTeacherJobPort",
    "build_student_verdict",
    "build_teacher_advisory_verdict",
    "build_teacher_advisory_verdict_async",
    "submit_teacher_review_job",
    "finalize_teacher_review_job",
    "mark_teacher_review_failed",
]
```

Delete only the complete definitions named `_legacy_build_student_verdict` and `_legacy_build_teacher_advisory_verdict`, including their function bodies. Do not delete shared helpers, imports, constants, the active runtime loader, active Teacher advisory builder, queue dispatch, persistence, or fallback behavior.

- [ ] **Step 4: Run focused regression tests and verify GREEN**

Run:

```powershell
cd system\backend
uv run python -m pytest tests/test_analysis_review_runtime.py tests/test_analysis_executor.py -q
```

Expected: all selected tests pass with no new warnings or collection errors.

- [ ] **Step 5: Synchronize structure records**

Add one sentence to the `Code Structure` section of `doc/engineering/system-governance.md` stating that `app.core.analysis.runtime` has an explicit `__all__` and retired deterministic builder implementations must not be restored or imported by new product code.

In `conductor/tracks.md`, replace the `Structural deepening` row status `Discovery` with `In progress` and state that the first completed subtask explicitly narrowed the Review runtime interface and removed retired builders.

Append one line to `.superpowers/sdd/progress.md` in this form after clean task review:

```text
- Runtime cleanup Task 1: complete (commits `<base7>..<head7>`, review clean; review runtime and executor tests passed).
```

- [ ] **Step 6: Commit only task-owned files**

Run:

```powershell
git add system/backend/app/core/analysis/runtime.py system/backend/tests/test_analysis_review_runtime.py doc/engineering/system-governance.md conductor/tracks.md .superpowers/sdd/progress.md docs/superpowers/plans/2026-08-15-analysis-review-runtime-cleanup.md
git commit -m "refactor(analysis): retire legacy review builders"
```

Expected: one commit containing only the listed files. Do not stage the existing semantic, propagation, Coordination, output, or Playwright changes.

## Plan Self-Review

- **Scope coverage:** The task removes the two confirmed unused builders, establishes the public module interface, retains the existing runtime seam, records the structural decision, and adds a regression test.
- **No behavior expansion:** No model, queue, database, API, frontend, or product-copy change is planned.
- **TDD evidence:** The new assertion necessarily fails before deletion because both legacy attributes exist; the focused regression suite then proves the active Student/Teacher runtime and Analysis Executor behavior still work.
- **Type consistency:** The `__all__` names are defined active names in `runtime.py`; no new runtime type or alternate adapter is introduced.

## Execution Handoff

Execute with Subagent-Driven Development: one fresh implementation subagent, then a separate specification-and-quality reviewer. Repair every Critical or Important finding with a fresh fixer and re-review before marking the task complete.
