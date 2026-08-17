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

## Task 1 Follow-Up Review Fix (2026-08-14)

### RED Evidence

Before the production changes, the executor-time command regression failed as
expected because `main_async()` printed the blocked summary but returned zero:

```text
tests/test_precompute_trump_visit_semantic_v6.py::test_precompute_returns_nonzero_when_executor_blocks_the_semantic_stage
assert 0 != 0
```

The provenance regressions also failed before the runtime change. A valid
written Coordination Discover artifact was ignored in favor of caller data;
an empty artifact directory and a tampered artifact both produced caller-made
community slices; and a fabricated propagation dictionary produced a path
overlay. The focused RED command reported `4 failed, 1 warning`:

```text
system/backend/.venv/Scripts/python.exe -m pytest \
  tests/test_semantic_runtime.py::test_real_runtime_contract_stratifies_layers_and_reuses_embeddings \
  tests/test_semantic_runtime.py::test_empty_coordination_directory_does_not_trust_caller_network_or_manifest \
  tests/test_semantic_runtime.py::test_tampered_coordination_artifact_does_not_become_a_community_slice \
  tests/test_semantic_runtime.py::test_fabricated_propagation_dictionary_does_not_produce_path_overlays -q
4 failed, 1 warning in 8.61s
```

### GREEN Evidence

The runtime now loads Coordination Discover through the existing verified
artifact loader, which validates manifest file hashes and the snapshot
fingerprint before using the persisted result. Propagation overlays are
explicitly unavailable until a comparable verified loader exists. The
precompute command returns `4` when the run or semantic stage is not
completed/ready, after printing the full summary.

Focused regression checks after the implementation:

```text
tests/test_precompute_trump_visit_semantic_v6.py::test_precompute_returns_nonzero_when_executor_blocks_the_semantic_stage
1 passed in 0.09s

tests/test_semantic_runtime.py selected provenance regressions
4 passed, 1 warning in 8.04s
```

Final focused verification:

```text
system/backend/.venv/Scripts/python.exe -m pytest \
  tests/test_precompute_trump_visit_semantic_v6.py \
  tests/test_semantic_runtime.py \
  tests/test_analysis_executor.py \
  tests/test_semantic_enrichment_mvp_contract.py -q
29 passed, 1 warning in 9.13s

system/backend/.venv/Scripts/python.exe -m py_compile \
  app/core/semantic/runtime.py \
  scripts/precompute_trump_visit_semantic_v6.py
exit 0

git diff --check -- <four task-owned backend files>
exit 0
```

The warning is the pre-existing `jieba`/`pkg_resources` deprecation warning.
A fresh post-commit rerun repeated the focused suite at `29 passed, 1 warning
in 9.49s`.

### Commit And Concerns

- Commit: `174abbf` `fix(semantic): fail closed on blocked artifacts`
- Scope: only the four task-owned backend files were committed. This report is
  intentionally left unstaged because the follow-up brief limits the commit to
  those backend files.
- Concern: successful real Transformer inference and live MySQL/Mongo
  persistence remain unverified because the local Torch CUDA DLL cannot load.
- Concern: propagation path overlays remain unavailable by design until the
  repository gains a verified propagation artifact loader with equivalent
  integrity and snapshot-fingerprint checks.

## Task 1 Empty-Hash Integrity Fix (2026-08-14)

### TDD Evidence

RED, before the runtime change:

```text
system/backend/.venv/Scripts/python.exe -m pytest tests/test_semantic_runtime.py -q -k without_hashes
1 failed, 10 deselected, 1 warning in 8.29s
```

The valid-format artifact had a matching snapshot fingerprint but an empty
`artifact_hashes` mapping and incorrectly produced `persisted-community`.

GREEN, after the runtime-boundary validation:

```text
system/backend/.venv/Scripts/python.exe -m pytest tests/test_semantic_runtime.py -q -k without_hashes
1 passed, 10 deselected, 1 warning in 8.18s
```

### Final Validation

```text
tests/test_semantic_runtime.py: 11 passed, 1 warning in 9.63s
tests/test_precompute_trump_visit_semantic_v6.py: 4 passed in 9.71s
tests/test_analysis_executor.py: 11 passed in 10.43s
tests/test_semantic_enrichment_mvp_contract.py: 4 passed in 10.48s
system/backend/.venv/Scripts/python.exe -m py_compile app/core/semantic/runtime.py: exit 0
git diff --check: exit 0
```

The warning is the existing `jieba`/`pkg_resources` deprecation warning.
Only the task-owned runtime and regression test will be committed; this report
remains unstaged because the brief restricts the commit to those two files.

## Task 5 Bounded BGE Encoding Fix (2026-08-14)

### RED Evidence

Before batching was implemented, the focused regression failed because all 34
texts were sent to the injected real-style encoder in one call:

```text
system/backend/.venv/Scripts/python.exe -m pytest tests/test_semantic_runtime.py::test_bge_encoding_batches_each_text_once_in_original_order -q
AssertionError: assert 1 == 2
1 failed, 1 warning in 0.35s
```

### GREEN Evidence

`BGE_ENCODING_BATCH_SIZE = 32` now bounds actual BGE encoder calls. Each
batch's normalized vectors are concatenated in source order, so each text is
encoded once and the existing shared embedding matrix remains unchanged for
downstream consumers.

```text
Focused regression: 1 passed, 1 warning in 0.08s

system/backend/.venv/Scripts/python.exe -m pytest tests/test_semantic_runtime.py tests/test_precompute_trump_visit_semantic_v6.py tests/test_analysis_executor.py tests/test_semantic_enrichment_mvp_contract.py -q
31 passed, 2 warnings in 8.92s

system/backend/.venv/Scripts/python.exe -m py_compile app/core/semantic/runtime.py
exit 0

git diff --check
exit 0
```

The warnings are existing Transformers cache and `jieba`/`pkg_resources`
deprecations. Only `runtime.py` and `test_semantic_runtime.py` are committed;
this report remains unstaged. Concern: successful full-volume BGE inference is
not exercised in this environment, but the live encoder path is now bounded
at 32 texts per CPU call without fallback or sampling.

## Task 5 Batch-Size Contract Review Fix (2026-08-14)

### TDD Evidence

The regression was temporarily given an incorrect batch-size expectation to
confirm the new contract assertion is active. The focused test failed for the
expected reason:

```text
system/backend/.venv/Scripts/python.exe -m pytest tests/test_semantic_runtime.py::test_bge_encoding_batches_each_text_once_in_original_order -q
AssertionError: assert 32 == 31
1 failed, 1 warning in 0.28s
```

After setting the required contract to `BGE_ENCODING_BATCH_SIZE == 32`, the
focused regression passed:

```text
1 passed, 1 warning in 0.11s
```

### Required Task 5 Suite

```text
system/backend/.venv/Scripts/python.exe -m pytest tests/test_semantic_runtime.py tests/test_precompute_trump_visit_semantic_v6.py tests/test_analysis_executor.py tests/test_semantic_enrichment_mvp_contract.py -q
31 passed, 2 warnings in 8.05s
```

`git diff --check -- system/backend/tests/test_semantic_runtime.py` passed.
The warnings are the existing Transformers cache and `jieba`/`pkg_resources`
deprecations.

### Commit And Concern

- Commit: `0925e7b` `test(semantic): pin BGE encoding batch size`
- Scope: the commit contains only `system/backend/tests/test_semantic_runtime.py`.
  This report is intentionally unstaged.
- Concern: real full-volume Transformer/BGE inference remains unexercised in
  this environment; the focused real-style encoder regression verifies the
  fixed-size contract, bounded calls, source ordering, and single coverage.

## Task 5 Candidate Batching Supplement (2026-08-14)

### RED Evidence

Added `test_keyword_candidates_are_encoded_in_bounded_batches_without_recomputing_documents`.
It prepares two document embeddings, then supplies 40 unique keyword candidates
to keyword MMR. Before the production change, candidate terms bypassed the
bounded path and the focused regression failed because all candidates reached
the encoder in one request:

```text
system/backend/.venv/Scripts/python.exe -m pytest system/backend/tests/test_semantic_runtime.py::test_keyword_candidates_are_encoded_in_bounded_batches_without_recomputing_documents -q
FAILED ... AssertionError: assert [['candidate-0', ..., 'candidate-39']] == [['candidate-0', ..., 'candidate-31'], ['candidate-32', ..., 'candidate-39']]
1 failed, 2 warnings in 0.42s
```

### GREEN Evidence

Keyword candidate vectors now use the existing `_encode_texts` bounded real-BGE
path. The regression proves 32/8 ordered candidate batches, exactly-once
candidate encoding, and that the document batch is not recomputed.

```text
system/backend/.venv/Scripts/python.exe -m pytest system/backend/tests/test_semantic_runtime.py::test_keyword_candidates_are_encoded_in_bounded_batches_without_recomputing_documents -q
1 passed, 2 warnings in 0.21s

system/backend/.venv/Scripts/python.exe -m pytest system/backend/tests/test_semantic_runtime.py system/backend/tests/test_precompute_trump_visit_semantic_v6.py system/backend/tests/test_analysis_executor.py system/backend/tests/test_semantic_enrichment_mvp_contract.py -q
32 passed, 2 warnings in 9.14s

system/backend/.venv/Scripts/python.exe -m py_compile system/backend/app/core/semantic/runtime.py
exit 0

git diff --check -- system/backend/app/core/semantic/runtime.py system/backend/tests/test_semantic_runtime.py
exit 0
```

The warnings are the existing Transformers cache and `jieba`/`pkg_resources`
deprecations. Only `runtime.py` and `test_semantic_runtime.py` are staged for
the supplement commit; this report remains unstaged. Concern: the tests use a
recording real-style encoder rather than running full-volume local BGE weights,
but production continues to use only the local BGE path with no fallback,
sampling, or synthetic vectors.
