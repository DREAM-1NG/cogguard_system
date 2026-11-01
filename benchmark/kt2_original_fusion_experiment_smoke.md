# KT2 Original-Subpath Fusion Experiment

- status: `ok`
- reproduction_level: `kt2_joint_model_small_run`
- datasets: `douban`
- seeds: `42`
- runs: `1`
- elapsed_s: `20.239`

Boundary: Runs KT2JointModel with upstream MINDS Module.forward, FOREST RNNModel/RRModel, and CasFT GaussianDiffusion_ST plus CombinedSpatiotemporalModel5 auxiliary subpaths. This is a repeatable original-subpath fusion experiment, not full original-paper data protocol or full-run reproduction.

## Metric Summary

| metric | mean | std | n |
|---|---:|---:|---:|
| msle | 1.465898 | 0.000000 | 1 |
| mae | 16.564649 | 0.000000 | 1 |
| rmse | 22.225945 | 0.000000 | 1 |
| direction_accuracy | 0.750000 | 0.000000 | 1 |
| candidate_recall_full | 0.097561 | 0.000000 | 1 |
| hits@10 | 0.012500 | 0.000000 | 1 |
| hits@50 | 0.162500 | 0.000000 | 1 |
| hits@100 | 0.162500 | 0.000000 | 1 |
| map@100 | 0.016493 | 0.000000 | 1 |
| mrr | 0.046875 | 0.000000 | 1 |
| macro_micro_consistency | 0.653634 | 0.000000 | 1 |

## Schema

- ok: `True`
