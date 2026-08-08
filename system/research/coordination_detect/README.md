# Coordination Detection Research Boundary

This package implements Stage 2 of the research-only
`Coordination Discovery -> harmful Coordination Detection` pipeline. It
classifies a previously discovered coordination cluster as benign/organic or
harmful. It does not discover clusters and it is not the multi-agent review
pipeline.

## One-Way Contract

Stage 2 accepts only a serialized `DiscoveredClusterBatch` plus explicitly
detection-only features. Stage 1 labels, evaluator objects, account-risk
labels, and harmfulness features are forbidden inputs to Discovery.

```text
label-free events
  -> TSGS/MHCR Discovery
  -> DiscoveredClusterBatch
  -> detection-only feature join
  -> learned detector
  -> ClusterDetectionBatch
```

The primary implementation is `LearnedCoordinationDetector`. It fits feature
standardization and coefficients on training cases, uses validation cases for
Platt calibration, decision thresholds, abstention, and OOD bounds, and never
fits on test rows. `CoordinationDetectionEngine` requires an explicitly fitted
learned artifact; there is no implicit production fallback.

`HeuristicBayesianBaseline` is isolated as `heuristic_baseline_v1`. Its fixed
weights and thresholds are comparison constants only. It cannot be selected as
the primary detector or used to claim learned harmful-CIB performance.

## Public Research Interfaces

- `DetectionFeatureSchema` fixes ordered, versioned detection inputs.
- `DetectionTrainingCase` binds one cluster, split, label, feature schema, and
  provenance.
- `LearnedCoordinationDetector.fit(train_cases, validation_cases)` produces a
  checksummed `DetectionModelArtifact`.
- `CoordinationDetectionEngine.predict(batch, detection_features)` produces a
  `ClusterDetectionBatch` with benign, harmful, or abstain verdicts.
- `HeuristicBayesianBaseline.predict(...)` produces baseline-only verdicts with
  a mandatory warning.

## Claim Status

| Claim | Evidence source | Status | Notes |
| --- | --- | --- | --- |
| Train-only scaler and coefficient fitting | `test_coordination_stage2_detection.py` | supported | Validation and test case IDs are excluded from model fitting. |
| Validation-only calibration, thresholds, and OOD bounds | `test_coordination_stage2_detection.py` | supported | Artifact fingerprints record each fit partition. |
| Fixed Bayesian weights are not the primary model | Engine type checks and Stage 2 tests | supported | The heuristic remains an explicit baseline. |
| IOHunter proves harmful-CIB Detection | IOHunter capability manifest | blocked | IOHunter labels external account membership, not harmful-CIB Gold; Stage 2 was not run in the compact matrix. |
| Trump three-platform data proves Detect accuracy | Local event inventory | blocked | No approved harmful-CIB labels exist for that event. |
| Learned detector is production-ready | Model activation gate | blocked | No full labeled multi-dataset/cross-event result has passed the activation gate. |

## Dataset Capability

| Dataset | Harmful-CIB labels | Observed-time claims | Permitted role |
| --- | --- | --- | --- |
| IOHunter processed campaigns | no | no | External account-recovery proxy and implementation evaluation only. |
| Cresci-2017 | no | dataset dependent | Auxiliary bot-transfer/scaling benchmark only. |
| Trump three-platform snapshot | no | partially available | Discovery case study and system demonstration only. |
| Future approved harmful-CIB corpus | required | recorded by protocol | Stage 2 training, calibration, and holdout evaluation. |

## Activation Gate

The backend `coordination-evidence-runtime-v2` remains the frozen production
Discovery mainline. This package has no production activation path. A candidate
can be proposed only after a leakage-safe multi-seed evaluation demonstrates
improvement over fair baselines on the target harmful-CIB task, with calibration,
coverage, abstention, campaign/platform/time holdouts, signed manifests, and
independent review. A proxy improvement alone cannot activate either stage.

All experiment outputs, caches, reports, and temporary files must be written
under an explicit G-drive path. C-drive temporary directories are not valid
research artifact roots.
