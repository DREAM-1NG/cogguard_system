# Coordination Two-Stage Reproduction Status

Date: 2026-08-10

This report records current evidence for the offline research implementation.
It is not a production activation record. The complete IOHunter matrix has not
finished, so no proxy comparison is promoted to a supported effectiveness
claim.

## Frozen Production Comparison Update

The final same-protocol static proxy comparison is documented in
`coordination-production-comparison-20260810.md`. Its final checksummed v2 matrix contains
50 rows across five campaigns (`35 success`, `15 blocked`). Only Russia and
Venezuela completed both `tsgs_mhcr_compact` and the frozen production prior.
The candidate loses all four external-account proxy metrics on Russia and wins
all four on Venezuela; the four campaign-mean deltas are negative overall and
their intervals cross zero. Candidate activation remains blocked.

This comparison starts after evidence projection. It does not evaluate the
complete production evidence, temporal-window, null-model, domain-shift,
abstention, or risk-tier path. Cuba remains a dataset-load `MemoryError`, while
China, Iran, and UAE explicitly block the production proxy above the declared
100,000-occurrence offline runtime budget.

## Architecture Status

| Stage | Implementation | Output | Status |
| --- | --- | --- | --- |
| Discovery | Label-free TSGS candidate sparsification, MHCR representation, Leiden interpretation, and compact baselines/ablations | `DiscoveredClusterBatch` and checksummed prediction artifacts | supported as an implemented research pipeline |
| Detection | Train-only learned logistic model, validation-only calibration/thresholds/OOD, and explicit heuristic baseline | `DetectionModelArtifact` and `ClusterDetectionBatch` | supported as an implemented research pipeline |
| System activation | Frozen `coordination-evidence-runtime-v2` | Production Coordination results | unchanged; candidate activation blocked |

## Current IOHunter Evidence

The latest execution smoke is stored at:

`G:\CISCN\CogGuard\.worktrees\refactor-system\system\output\coordination_two_stage_reproduction\iohunter-matrix-artifact-smoke-v2-20260808`

It ran Russia, seed 42, for `tsgs_mhcr_compact` and `edgebank`. The first run
executed both coordinates; the second resumed both without Discovery
recomputation. Both runs emitted the same manifest fingerprint:
`sha256:7e51c86a86a01c2711c6eef2b935a921b87069092bc5447d78a9f2aff316dcb5`.

| Method | External-account AUPRC | ROC-AUC | Macro F1 | Recall@K | Interpretation |
| --- | ---: | ---: | ---: | ---: | --- |
| `edgebank` | 0.464576 | 0.465373 | 0.504641 | 0.381818 | execution smoke only |
| `tsgs_mhcr_compact` | 0.464944 | 0.472523 | 0.479142 | 0.400000 | execution smoke only |

These values use IOHunter's external-account labels. They do not measure true
coordination edges, recovered communities, harmful-CIB intent, causality, or
production value.

## Claim Decisions

| Claim | Evidence source | Status | Reason |
| --- | --- | --- | --- |
| Compact matrix executes and resumes from checksummed G-drive artifacts | Russia artifact smoke and matrix tests | supported | Two coordinates executed, then resumed with a stable manifest identity. |
| Candidate improves external-account recovery over EdgeBank | One of 30 required campaign-seed pairs | blocked | All 30 paired campaign-seed results and a positive paired 95% bootstrap CI lower bound are required. |
| Discovery recovers true coordination edges or communities | IOHunter processed data | blocked | No true coordination-edge/community labels exist. |
| Detection identifies harmful CIB | IOHunter compact matrix | blocked | Harmful-CIB Gold is absent and Stage 2 was not executed. |
| Temporal coordination is validated | IOHunter processed graphs | blocked | Required observed timestamps are absent. |
| Production Discovery should be replaced | Research artifacts | blocked | The production mainline is frozen and no activation gate has passed. |

## Detection Experiment Status

| Metric | Split policy | Seed count | Status | Why blocked |
| --- | --- | ---: | --- | --- |
| Harmful-CIB AUPRC | campaign/platform/time holdout required | 0 | blocked | No approved harmful-CIB Gold corpus was executed. |
| Harmful-CIB macro F1 | campaign/platform/time holdout required | 0 | blocked | No approved harmful-CIB Gold corpus was executed. |
| Harmful-CIB ROC-AUC | campaign/platform/time holdout required | 0 | blocked | No approved harmful-CIB Gold corpus was executed. |
| ECE/calibration | validation-only calibration plus disjoint test | 0 | blocked | No target-task probability evaluation exists. |
| Selective coverage/risk | validation-only abstain thresholds plus disjoint test | 0 | blocked | No target-task test verdicts exist. |

The Stage 2 unit tests prove split isolation and artifact behavior; they are not
dataset performance experiments and therefore do not contribute seeds or
metrics to this table.

## Verification

The prediction-spooling change was verified with:

- `32 passed` in the focused compact matrix runner suite.
- `75 passed` across compact execution, compact loading, matrix runner, and
  matrix protocol tests.
- `78 passed` across the final affected compact/matrix regression after the
  provenance and single-pass partition fixes.
- `242 passed` across the remaining 14 Coordination test files.
- A real Russia smoke followed by an all-row resume smoke.

All test temporary paths, caches, smoke artifacts, and reports used for this
work were configured below `G:\CISCN\CogGuard`.

The final verification file sets were:

```text
tests/test_coordination_compact_matrix_runner.py
tests/test_coordination_iohunter_compact.py
tests/test_coordination_compact_execution.py
tests/test_coordination_matrix_protocol.py
=> 78 passed

tests/test_coordination_compact_discovery_methods.py
tests/test_coordination_detector.py
tests/test_coordination_discover_temporal_edge_model.py
tests/test_coordination_local_discover_detect_script.py
tests/test_coordination_model_api.py
tests/test_coordination_model_service.py
tests/test_coordination_network.py
tests/test_coordination_reproduction_runner.py
tests/test_coordination_research_protocol.py
tests/test_coordination_stage1_contracts.py
tests/test_coordination_stage1_engine.py
tests/test_coordination_stage1_mhcr.py
tests/test_coordination_stage1_tsgs.py
tests/test_coordination_stage2_detection.py
=> 242 passed
```

## Remaining Work

1. Complete all six campaigns, five official seeds, and six Discovery methods
   with recoverable per-coordinate artifacts.
2. Audit the final 180-row manifest, aggregate table, paired proxy decisions,
   ablations, and scaling/spectral artifacts.
3. Run harmful-CIB Detection only on a dataset whose labels support that task.
4. Keep every incomplete metric `exploratory` or `blocked`; do not activate a
   research candidate from IOHunter proxy results.
