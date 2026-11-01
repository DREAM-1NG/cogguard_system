# KT2 Original-Subpath Fusion Experiment

- status: `ok`
- reproduction_level: `kt2_joint_model_small_run`
- datasets: `memetracker`
- seeds: `42`
- runs: `1`
- elapsed_s: `138.141`

Boundary: Runs KT2JointModel with upstream MINDS Module.forward, FOREST RNNModel/RRModel, and CasFT GaussianDiffusion_ST plus CombinedSpatiotemporalModel5 auxiliary subpaths. This is a repeatable original-subpath fusion experiment, not full original-paper data protocol or full-run reproduction.

## Original-Subpath Audit

- all_original_subpaths_passed: `True`
- all_alignment_losses_recorded: `True`
- rows_ok: `1` / `1`

## Metric Summary

| metric | mean | std | n |
|---|---:|---:|---:|
| msle | 1.334775 | 0.000000 | 1 |
| mae | 17.217082 | 0.000000 | 1 |
| rmse | 26.023829 | 0.000000 | 1 |
| direction_accuracy | 0.750000 | 0.000000 | 1 |
| candidate_recall_full | 0.054054 | 0.000000 | 1 |
| hits@10 | 0.000000 | 0.000000 | 1 |
| hits@50 | 0.025000 | 0.000000 | 1 |
| hits@100 | 0.025000 | 0.000000 | 1 |
| map@100 | 0.001885 | 0.000000 | 1 |
| mrr | 0.013889 | 0.000000 | 1 |
| macro_micro_consistency | 0.594936 | 0.000000 | 1 |

## Schema

- ok: `True`
