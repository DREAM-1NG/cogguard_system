# Coordination Detection Runtime And Research Boundary

This package implements the `Coordination Discover -> Coordination Detect`
boundary. The deployed v1 Detection path projects account-level IO membership
probabilities into cluster-level proxy verdict hints. It does not discover
clusters, does not prove group-level harmful-CIB F1, does not replace analyst
confirmation, and is not the multi-agent Review pipeline.

## One-Way Contract

Stage 2 accepts only a serialized `DiscoveredClusterBatch` plus explicitly
detection-only features. Stage 1 labels, evaluator objects, account-risk
labels, and harmfulness features are forbidden inputs to Discovery.

```text
label-free events
  -> evidence-constrained Coordination Discover
  -> DiscoveredClusterBatch
  -> detection-only feature join
  -> active Coordination Detect artifact
  -> ClusterDetectionBatch
```

The current system primary artifact type is `socgfm_cross_attention`.
`SocGFMCrossAttentionArtifact` stores account-level IO/coordination
probabilities, a fixed group aggregation head, validation-selected threshold
metadata, calibration parameters, provenance, and a hashable artifact identity.
`SocGFMCrossAttentionDetector` aggregates each discovered cluster with
`cluster_size`, mean/max member probability, evidence coverage, relation
diversity, and the Stage-1 coordination score, then emits binary
`harmful_coordination` or `benign_coordination` verdict hints.

The online v1 runtime uses
`inference_mode=precomputed_member_probability_cluster_aggregation`,
`claim_scope=account_level_io_membership_to_cluster_proxy`, and
`online_neural_forward=false`. It does not execute the Torch/PyG
Cross-Attention network during request handling. Offline Cross-Attention
experiments may report account-level IO membership F1, but manifests must not
claim `group_level_harmful_coordination_f1`.

For local uploaded unlabeled data, the system now provides a China checkpoint
precompute bridge in
`backend/app/core/analysis/coordination_runtime/socgfm_local_precompute.py`
and `backend/scripts/precompute_socgfm_china_local_detection.py`. The bridge
loads the official China SocGFM CrossAttention/SAGE `model0.pth` through
`model4.pth`, requires 768-dimensional SBERT account text features, builds
128-dimensional positional-degree structural features, executes Torch/PyG
forward offline, and writes `predictions.csv`, `node_mapping.csv`,
`feature_audit.json`, `checkpoint_hashes.json`, and
`prediction_manifest.json` under G-drive output. The generated predictions can
then be converted by `build_socgfm_detection_artifact.py` into the deployed v1
artifact format. The internal `china_fusion_gnn_sbert.pt` checkpoint remains
legacy/archive audit material and must not be described as the SocGFM primary
Detection path.

The older `LearnedCoordinationDetector` remains available as a shadow classifier
and research baseline. It fits feature standardization and coefficients on
training cases, uses validation cases for Platt calibration and OOD bounds, and
never fits on test rows. Predictions are forced binary decisions at probability
0.5 so public Detection comparisons use standard metrics instead of selective
abstention metrics.

The backend runtime requires an explicitly registered, hash-verified active
artifact. If the active `coordination_detection` pointer is absent,
incompatible, hash-mismatched, or rooted on the forbidden C drive, the system
returns `model_unavailable`; there is no implicit heuristic fallback.

`HeuristicBayesianBaseline` is isolated as `heuristic_baseline_v1`. Its fixed
weights and thresholds are comparison constants only. It cannot be selected as
the primary detector or used to claim learned harmful-CIB performance.

## Public Research Interfaces

- `DetectionFeatureSchema` fixes ordered, versioned detection inputs.
- `DetectionTrainingCase` binds one cluster, split, label, feature schema, and
  provenance.
- `LearnedCoordinationDetector.fit(train_cases, validation_cases)` produces a
  checksummed shadow/baseline `DetectionModelArtifact`.
- `SocGFMCrossAttentionArtifact.from_json(...)` loads the current primary
  system artifact type.
- `SocGFMCrossAttentionDetector.predict(...)` projects account-level SocGFM
  probabilities into cluster-level proxy `ClusterDetectionBatch` verdict hints.
- `CoordinationDetectionEngine.predict(batch, detection_features)` produces a
  learned/shadow `ClusterDetectionBatch` with benign or harmful verdicts.
- `HeuristicBayesianBaseline.predict(...)` produces baseline-only verdicts with
  a mandatory warning.
- `backend/scripts/build_socgfm_detection_artifact.py` converts offline
  `predictions.csv` runs into deployable `checkpoint.json`, `manifest.json`,
  `account_probabilities.csv`, and `provenance.json`.
- `backend/scripts/precompute_socgfm_china_local_detection.py` runs the
  official China checkpoint ensemble on local event tables, EventSnapshot JSON,
  or registered CoordinationDataset uploads before artifact building.
- `backend/scripts/register_socgfm_detection_artifact.py` verifies and registers
  a G-drive artifact, optionally activating the governed active pointer.

The SocGFM artifact builder follows the IOHunter official-split convention used
by the local reproduction outputs: when a prediction file contains train/test
rows plus labeled `unassigned` rows, `unassigned` is treated as the validation
partition. Thresholds are selected on validation rows, metrics are evaluated on
the corresponding held-out test rows, and multi-dataset results are
macro-averaged per prediction run. Pooled-row metrics across countries are not
used for deployment quality because score scales differ by campaign. ECE remains
a recorded calibration diagnostic; it is not a group-level Detection claim and
does not imply calibrated harmful-CIB probability.

## Claim Status

| Claim | Evidence source | Status | Notes |
| --- | --- | --- | --- |
| Train-only scaler and coefficient fitting | `test_coordination_stage2_detection.py` | supported | Validation and test case IDs are excluded from model fitting. |
| Validation-only calibration, thresholds, and OOD bounds | `test_coordination_stage2_detection.py` | supported | Artifact fingerprints record each fit partition. |
| Fixed Bayesian weights are not the primary model | Engine type checks and Stage 2 tests | supported | The heuristic remains an explicit baseline. |
| IOHunter proves harmful-CIB Detection | IOHunter capability manifest | blocked | IOHunter labels external account membership, not harmful-CIB Gold; Stage 2 was not run in the compact matrix. |
| Official InfoOpsGFM account classifier runs locally | `iohunter_socgfm.py` manifests and `iohunter-socgfm-official-reproduction-20260812.md` | partially supported | The canonical upstream is `mminici/InfoOpsGFM`; the local checkout retains the historical `SocGFM` directory name. Four official SAGE entry points completed on the Russia bundle, and Cross-Attention completed on five campaigns. Cuba remains blocked by the local 8GB GPU. This is account-level IO membership classification only. |
| Trump three-platform data proves Detect accuracy | Local event inventory | blocked | No approved harmful-CIB labels exist for that event. |
| SocGFM Cross-Attention is the system primary Detection artifact type | Runtime dispatch, artifact-builder, governance, and frontend tests | supported as product decision | Online v1 consumes precomputed member probabilities and cluster features. This is an activation decision, not a claim that it beats every classifier baseline. |
| SocGFM online runtime executes Cross-Attention neural forward | Runtime diagnostics and artifact manifest | blocked for v1 | The current deployed mode sets `online_neural_forward=false`; true online neural forward is a later `v2_online_neural_forward` bridge. |
| SocGFM deployment proves group-level harmful coordination F1 | Governance forbidden-claim checks | blocked | The allowed claim scope is account-level IO membership to cluster proxy, not real group-level harmful-CIB validation. |
| China checkpoint can score local uploaded accounts offline | Local precompute module, CLI, and checkpoint-forward smoke | supported as deployment bridge | The output is account-level IO membership transfer probability plus group aggregation proxy, not an online neural forward or group-level harmful-CIB metric. |
| Learned classifier remains available for rollback and audit | Runtime separation and frontend primary filtering | supported | It must not be displayed as the primary frontend verdict. |
| Learned detector is production-ready as the primary model | Model activation gate | superseded | The learned/logistic artifact is now shadow/baseline unless explicitly reactivated by a later governance decision. |

## Dataset Capability

| Dataset | Harmful-CIB labels | Observed-time claims | Permitted role |
| --- | --- | --- | --- |
| IOHunter processed campaigns | no | no | External account-recovery proxy and implementation evaluation only. |
| Cresci-2017 | no | dataset dependent | Auxiliary bot-transfer/scaling benchmark only. |
| Trump three-platform snapshot | no | partially available | Discovery case study and system demonstration only. |
| Future approved harmful-CIB corpus | required | recorded by protocol | Stage 2 training, calibration, and holdout evaluation. |

## Activation Gate

The backend `coordination-evidence-runtime-v2` remains the frozen production
Discovery mainline. For Detection, `socgfm_cross_attention` is the current
primary artifact type and the classifier is retained as a shadow baseline. This
activation does not promote a research superiority claim: a paper-level claim
still requires leakage-safe multi-seed evaluation over fair baselines on the
target harmful-CIB task, with calibration, campaign/platform/time holdouts,
signed manifests, and independent review. A proxy improvement alone cannot
claim harmful-CIB Detection superiority.

All experiment outputs, caches, reports, and temporary files must be written
under an explicit G-drive path. C-drive temporary directories are not valid
research artifact roots.

## Official IOHunter Baseline

`research.coordination_experiments.iohunter_socgfm` runs the official
InfoOpsGFM entry points from the local historical `SocGFM` checkout in an
isolated G-drive sandbox. It supports `run_GNN.py`, `run_GNNPlusLLM.py`,
`run_MultiModalGNN.py`, and `run_MultiModalGNN_CrossAttention.py`; each output
records the executed-source hashes, command, dataset fingerprint, and G-drive
artifact locations. This remains an account-level IO membership baseline
outside this package's harmful-CIB Detection activation path. The wrapper
preserves the official dataset-provided split protocol; those five splits must
not be described as five independent model seeds.
