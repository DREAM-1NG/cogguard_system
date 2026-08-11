# Coordination Detection Public Multi-Dataset Comparison

Date: 2026-08-11

Output root: `G:/CISCN/CogGuard/.worktrees/refactor-system/system/output/coordination_two_stage_reproduction/public-detection-local-20260811-5seed-v4`

Manifest fingerprint: `sha256:837c420056a24cbd24dc8fcaa2325f17c1da6794c201a9dc002b531f708c70e8`

Manifest: `public_detection_manifest.json`

Rows: `per_seed_rows.csv`

Aggregates: `aggregates.csv`

## Scope

This run extends the CogGuard Coordination research harness from Discovery-only proxy evaluation to Stage 2 binary Coordination Detection evaluation where public graph or feature-table labels are available.

The current executable binary Detection datasets are:

| Dataset | Local path | Local sample count | Label semantics | Claim scope |
|---|---:|---:|---|---|
| Large Engagement Networks | `G:/CISCN/dataset/LEN` | 104 graph JSON files | `campaign=1`, `noncampaign=0` | graph-level campaign/non-campaign Detection |
| Astroturf/Legitimate Classification | `G:/CISCN/dataset/ALClassification/data.arff` | 366 feature rows | `truthy=1`, `legitimate=0` | classic feature-table astroturf smoke |

IOHunter processed data, Twitter State-Backed Ops, `twitter_io`, and FiveThirtyEight Russian troll tweets remain Discovery/account-recovery or temporal proxy resources. They are not treated as harmful Coordination Detection datasets because they lack cluster/graph-level harmful-vs-benign labels. LEN and ALClassification are also not marked as harmful-CIB gold; they are binary Detection-style evaluation resources.

## Fixed Methods

Executable in this run:

| Method | Role | Paper/reference alignment | Local execution |
|---|---|---|---|
| `learned_fused_detector` | CogGuard system Stage 2 learned detector | system baseline | calibrated logistic over all standardized features |
| `coordination_only_logistic` | CogGuard Stage 2 ablation | local system ablation | calibrated logistic over Discovery/coordination features |
| `detection_features_only_classifier` | CogGuard Stage 2 ablation | local system ablation | calibrated logistic over non-Discovery detection features |
| `heuristic_baseline_v1` | explicit heuristic baseline | fixed Bayesian weights/thresholds | test-only baseline, not claimable |
| `len_graph_stat_logistic` | LEN-style graph-stat baseline | LEN 2025 graph classification setting | calibrated logistic over graph statistics |
| `vargas_coordination_activity_classifier` | coordination activity feature baseline | Vargas et al. 2020 network-statistics classifier | calibrated logistic over coordination/activity features |
| `truthy_feature_logistic` | Truthy classic feature baseline | Truthy/Astroturf 2011 feature-table classifier | calibrated logistic over ARFF features |
| `gcn_graph_classifier` | graph neural baseline | Kipf & Welling 2017 GCN | local compact LEN graph adapter with normalized message passing |
| `graphsage_graph_classifier` | graph neural baseline | Hamilton et al. 2017 GraphSAGE | local compact LEN graph adapter with mean aggregation |
| `gin_graph_classifier` | graph neural baseline | Xu et al. 2019 GIN | local compact LEN graph adapter with sum aggregation |
| `diffpool_graph_classifier` | graph neural baseline | Ying et al. 2018 DiffPool | local compact LEN graph adapter with differentiable assignment pooling |

Fixed but not yet executable as fair local baselines:

| Method | Status | Reason |
|---|---|---|
| Official GCN / GraphSAGE / GIN / DiffPool repos | adapter required | The run includes local compact graph-neural adapters, not official PyG/DGL reproduction packages. |
| TGAT / TGN / DyGFormer | blocked on current Detection datasets | LEN and ALClassification are not timestamped event-stream Detection datasets. |
| Inductive IO graph learning / IOHunter account graph learning | blocked for Stage 2 Detection | Requires account-level IO/control labels, not graph-level harmful labels. |

## Protocol

Split policy: stratified binary-label holdout.

Seeds: `11, 23, 37, 41, 53`.

LEN per seed: 104 samples, 62 train, 21 validation, 21 test, test labels `0:10`, `1:11`, 19 features.

ALClassification per seed: 366 samples, proportional train/validation/test split, static-time claim marker, 37 features.

All artifacts are written under the repository's G-drive reproduction output root.

Claim gates are intentionally non-empty. They block harmful-CIB and observed-time generalization from this run because LEN is a graph-level campaign/non-campaign dataset and ALClassification is a static Truthy feature table. The dataset capability layer now distinguishes `binary_coordination_detection` from `harmful_cib_detection`.

## Results

Mean +/- std over 5 seeds.

| Dataset | Method | Macro-F1 | AUPRC | ROC-AUC | ECE | Coverage | Abstain |
|---|---|---:|---:|---:|---:|---:|---:|
| ALClassification | `coordination_only_logistic` | 0.814 +/- 0.087 | 0.764 +/- 0.115 | 0.877 +/- 0.075 | 0.078 +/- 0.011 | 0.932 +/- 0.031 | 0.068 +/- 0.031 |
| ALClassification | `detection_features_only_classifier` | 0.862 +/- 0.062 | 0.794 +/- 0.046 | 0.898 +/- 0.058 | 0.070 +/- 0.024 | 0.699 +/- 0.060 | 0.301 +/- 0.060 |
| ALClassification | `heuristic_baseline_v1` | 0.228 +/- 0.034 | 0.329 +/- 0.154 | 0.322 +/- 0.183 | 0.518 +/- 0.021 | 0.438 +/- 0.043 | 0.562 +/- 0.043 |
| ALClassification | `learned_fused_detector` | 0.871 +/- 0.083 | 0.800 +/- 0.057 | 0.898 +/- 0.059 | 0.049 +/- 0.018 | 0.699 +/- 0.067 | 0.301 +/- 0.067 |
| ALClassification | `truthy_feature_logistic` | 0.862 +/- 0.062 | 0.794 +/- 0.046 | 0.898 +/- 0.058 | 0.070 +/- 0.024 | 0.699 +/- 0.060 | 0.301 +/- 0.060 |
| LEN | `coordination_only_logistic` | 0.823 +/- 0.084 | 0.952 +/- 0.032 | 0.936 +/- 0.043 | 0.136 +/- 0.049 | 0.495 +/- 0.199 | 0.505 +/- 0.199 |
| LEN | `detection_features_only_classifier` | 0.849 +/- 0.109 | 0.953 +/- 0.033 | 0.940 +/- 0.039 | 0.143 +/- 0.038 | 0.429 +/- 0.080 | 0.571 +/- 0.080 |
| LEN | `diffpool_graph_classifier` | 0.529 +/- 0.229 | 0.889 +/- 0.069 | 0.845 +/- 0.110 | 0.046 +/- 0.063 | 0.895 +/- 0.070 | 0.105 +/- 0.070 |
| LEN | `gcn_graph_classifier` | 0.840 +/- 0.084 | 0.940 +/- 0.018 | 0.916 +/- 0.025 | 0.132 +/- 0.019 | 0.829 +/- 0.065 | 0.171 +/- 0.065 |
| LEN | `gin_graph_classifier` | 0.826 +/- 0.051 | 0.950 +/- 0.016 | 0.925 +/- 0.030 | 0.087 +/- 0.036 | 0.914 +/- 0.092 | 0.086 +/- 0.092 |
| LEN | `graphsage_graph_classifier` | 0.895 +/- 0.056 | 0.973 +/- 0.017 | 0.969 +/- 0.019 | 0.113 +/- 0.025 | 0.914 +/- 0.056 | 0.086 +/- 0.056 |
| LEN | `heuristic_baseline_v1` | 0.344 +/- 0.000 | 0.960 +/- 0.040 | 0.940 +/- 0.061 | 0.353 +/- 0.043 | 0.248 +/- 0.047 | 0.752 +/- 0.047 |
| LEN | `learned_fused_detector` | 0.831 +/- 0.114 | 0.957 +/- 0.032 | 0.942 +/- 0.045 | 0.126 +/- 0.033 | 0.381 +/- 0.095 | 0.619 +/- 0.095 |
| LEN | `len_graph_stat_logistic` | 0.849 +/- 0.109 | 0.953 +/- 0.033 | 0.940 +/- 0.039 | 0.143 +/- 0.038 | 0.429 +/- 0.080 | 0.571 +/- 0.080 |
| LEN | `vargas_coordination_activity_classifier` | 0.823 +/- 0.084 | 0.952 +/- 0.032 | 0.936 +/- 0.043 | 0.136 +/- 0.049 | 0.495 +/- 0.199 | 0.505 +/- 0.199 |

Blocked execution rows:

| Dataset | Method | Count | Reason |
|---|---|---:|---|
| LEN | `truthy_feature_logistic` | 5 | LEN is graph JSON, not Truthy ARFF handcrafted feature table. |
| LEN | `inductive_io_graph_learning` / `iohunter_account_graph_learning` | 10 | These methods require account-level IO/control labels rather than LEN graph labels. |
| LEN | `tgat` / `tgn` / `dygformer` | 15 | LEN does not provide timestamped event-stream Detection labels. |
| ALClassification | `len_graph_stat_logistic` | 5 | ALClassification has no graph labels/weighted graph structure. |
| ALClassification | `vargas_coordination_activity_classifier` | 5 | ALClassification has no graph-label coordination activity network. |
| ALClassification | `gcn_graph_classifier` / `graphsage_graph_classifier` / `gin_graph_classifier` / `diffpool_graph_classifier` | 20 | ALClassification is a feature table, not a graph dataset. |
| ALClassification | `inductive_io_graph_learning` / `iohunter_account_graph_learning` | 10 | These methods require account-level IO/control labels. |
| ALClassification | `tgat` / `tgn` / `dygformer` | 15 | ALClassification has no observed temporal edge stream. |

## Interpretation

1. CogGuard Stage 2 is operational on two public binary Detection-style datasets. The unified runner trains, calibrates, abstains, writes artifacts, and records blocked method/data combinations instead of inventing unsupported results.

2. On LEN, the best Macro-F1 among executable methods is `graphsage_graph_classifier` at `0.895 +/- 0.056`. This is a local compact GraphSAGE-style adapter, not an official reproduction. `learned_fused_detector` reaches `0.831 +/- 0.114`, so the current system detector does not dominate graph-statistical or graph-neural baselines.

3. On ALClassification, `learned_fused_detector` has the best Macro-F1 (`0.871 +/- 0.083`) and best ECE (`0.049 +/- 0.018`). This supports the learned Stage 2 interface, but AL is a small classic feature table, not a modern graph/temporal Coordination Detection benchmark.

4. The heuristic baseline is not competitive as a classifier. It sometimes has high AUPRC on LEN, but Macro-F1 is low and abstain rate is very high. It remains a transparent heuristic baseline only.

5. Selective coverage remains uneven. The CogGuard fused detector covers only about 38% of LEN test samples under current abstain thresholds, while local graph-neural adapters cover roughly 83-91%. Detection activation still needs threshold/calibration optimization.

## Research Claim Boundary

Supported now:

- The CogGuard Detection harness can run multi-dataset, multi-method, multi-seed Stage 2 experiments with sealed labels.
- LEN and ALClassification are wired as local public Detection datasets.
- Fixed SOTA candidate methods are registered with explicit ready/blocked/adapter-required statuses.
- LEN now has local compact GCN/GraphSAGE/GIN/DiffPool-style graph-neural comparison rows.

Not supported yet:

- No claim that CogGuard beats graph-neural baselines on LEN; in this run, the compact GraphSAGE-style adapter has higher Macro-F1 than the CogGuard fused detector.
- No claim that the compact graph-neural adapters are official SOTA reproductions. They are research baselines for protocol alignment.
- No claim that CogGuard beats TGAT/TGN/DyGFormer, because current Detection datasets do not provide timestamped event-stream Detection labels.
- No claim that IOHunter or Twitter takedown datasets validate harmful Coordination Detection; they remain Discovery/account-recovery or case-study resources unless control/harmfulness labels are added.
- No harmful-CIB or observed-time generalization claim passes the emitted claim gates for this run.

## Next Work

1. Replace or supplement compact graph-neural adapters with official or library-faithful PyG/DGL reproductions for GCN, GraphSAGE, GIN, and DiffPool.

2. Add calibration/threshold sweeps for `learned_fused_detector`, reporting Macro-F1 at fixed coverage and coverage at fixed selective risk.

3. Expand LEN local data to the full public release if available. Current local LEN has 104 graphs, while the LEN paper describes a larger release.

4. Keep IOHunter/Twitter event-stream experiments separate as Discovery/account-recovery proxy until a dataset with harmful/benign cluster labels and observed timestamps is available.
