# KT2 Original-Subpath Fusion Experiment

- status: `ok`
- reproduction_level: `kt2_joint_model_small_run`
- datasets: `twitter`
- seeds: `43`
- obs_ratios: `0.5`
- config_id: `default-small`
- runs: `1`
- elapsed_s: `84.832`

Boundary: Runs KT2JointModel with upstream MINDS Module.forward, FOREST RNNModel/RRModel, and CasFT GaussianDiffusion_ST plus CombinedSpatiotemporalModel5 auxiliary subpaths. This is a repeatable original-subpath fusion experiment, not full original-paper data protocol or full-run reproduction.

## Original-Subpath Audit

- all_original_subpaths_passed: `True`
- all_alignment_losses_recorded: `True`
- rows_ok: `1` / `1`
- matrix_coverage: `1` / `1`
- pending_keys: `[]`

## Metric Summary

| metric | mean | std | n |
|---|---:|---:|---:|
| msle | 8.369809 | 0.000000 | 1 |
| mae | 57.346919 | 0.000000 | 1 |
| rmse | 94.498504 | 0.000000 | 1 |
| direction_accuracy | 0.750000 | 0.000000 | 1 |
| candidate_recall_full | 0.103448 | 0.000000 | 1 |
| hits@10 | 0.125000 | 0.000000 | 1 |
| hits@50 | 0.250000 | 0.000000 | 1 |
| hits@100 | 0.250000 | 0.000000 | 1 |
| map@100 | 0.035802 | 0.000000 | 1 |
| mrr | 0.069079 | 0.000000 | 1 |
| macro_micro_consistency | 0.576941 | 0.000000 | 1 |

## Schema

- ok: `True`
