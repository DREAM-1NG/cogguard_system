# Semantic Precompute Task 1 Report

## Status

Implemented and verified on branch `coordination/deep-detection-upgrade`.
The original Task 1 implementation is in the concurrent base commit `13039d8`
(which introduced the six task paths), with readiness/precompute hardening in
`c6d946a`; the final scoped refinements are recorded in the follow-up commit
listed below. Existing dirty worktree changes outside the task paths were
preserved.

## TDD Evidence

Original RED command (before the Task 1 implementation):

```text
$env:MYSQL_HOST='127.0.0.1'; $env:MYSQL_PORT='1'; .\\venv\\Scripts\\python.exe -m pytest tests\\test_analysis_executor.py::test_default_analysis_engine_ports_reuses_the_injected_semantic_runtime_and_engine tests\\test_semantic_runtime.py::test_missing_jieba_is_reported_as_a_model_weights_blocker tests\\test_semantic_runtime.py::test_path_overlay_requires_a_matching_propagation_artifact tests\\test_precompute_trump_visit_semantic_v6.py -q
5 failed, 1 warning in 10.94s
```

Original GREEN command:

```text
5 passed, 1 warning in 7.58s
```

Follow-up RED: the new validation-only and dependency-import regressions failed
before their corresponding behavior existed. Follow-up GREEN and final focused
verification:

```text
system/backend/.venv/Scripts/python.exe -m pytest tests/test_precompute_trump_visit_semantic_v6.py tests/test_semantic_runtime.py tests/test_analysis_executor.py tests/test_semantic_enrichment_mvp_contract.py -q
26 passed, 1 warning in 8.71s
```

The warning is the pre-existing `jieba`/`pkg_resources` deprecation warning.
Compilation and scoped `git diff --check` also passed. A fresh post-commit run
repeated the focused command at `26 passed, 1 warning in 9.32s`.

The post-amend verification repeated the same suite at `26 passed, 1 warning
in 9.64s`.

## Changes

- `default_analysis_engine_ports` accepts and preserves an injected semantic runtime/engine by identity.
- Semantic execution catches `ModelWeightsBlockedError` and persists a blocked, non-fallback result.
- Dependency import/load failures are normalized to `ModelWeightsBlockedError`.
- Cross-stage community/path overlays require a matching fingerprint and an existing locally verifiable artifact reference; phantom or remote-only references remain unavailable.
- The precompute command checks source/dependency/model/database readiness before writes, runs exactly `semantic_enrichment`, supports a prebuilt runtime, and keeps validation-only mode mutation-free.

## Real Readiness

The real local model directories under `G:\\CISCN\\hf_models` contain the fixed
model files, and all three platform source trees are present. Actual model
execution was not completed: importing `transformers` fails because the local
Torch CUDA DLL cannot load (`WinError 127`). The precompute path therefore
returns explicit `model_weights_blocked` before database/import mutation.

## Files

- `system/backend/app/core/analysis/executor.py`
- `system/backend/app/core/semantic/runtime.py`
- `system/backend/scripts/precompute_trump_visit_semantic_v6.py`
- `system/backend/tests/test_analysis_executor.py`
- `system/backend/tests/test_semantic_runtime.py`
- `system/backend/tests/test_precompute_trump_visit_semantic_v6.py`

## Commits

- `13039d8` `Backup refactored case workbench and propagation prototype` (base commit containing the Task 1 paths)
- `c6d946a` `Harden semantic precompute validation` (readiness/precompute hardening)
- Follow-up commit: `51be8d8` `Normalize semantic readiness failures and artifact provenance`
- Report commit: this report is included in the final evidence commit.

Scope-risk: narrow

Reversibility: clean; remove the follow-up commit to restore the prior committed Task 1 behavior.

Directive: Keep semantic evidence auxiliary and fail closed; never fabricate propagation or model success.

Tested: focused Task 1/semantic contract tests, py_compile, scoped diff check, and live dependency/model preflight.

Not-tested: successful real Transformer inference, live MySQL/Mongo execution, and persisted semantic artifact because the Torch CUDA DLL is unavailable.
