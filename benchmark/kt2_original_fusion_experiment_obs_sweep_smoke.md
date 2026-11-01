# KT2 Original-Subpath Fusion Experiment

- status: `ok`
- reproduction_level: `kt2_joint_model_small_run`
- datasets: `douban`
- seeds: `42`
- obs_ratios: `0.3, 0.5`
- config_id: `obs-sweep-smoke`
- runs: `2`
- elapsed_s: `171.654`

Boundary: Runs KT2JointModel with upstream MINDS Module.forward, FOREST RNNModel/RRModel, and CasFT GaussianDiffusion_ST plus CombinedSpatiotemporalModel5 auxiliary subpaths. This is a repeatable original-subpath fusion experiment, not full original-paper data protocol or full-run reproduction.

## Original-Subpath Audit

- all_original_subpaths_passed: `True`
- all_alignment_losses_recorded: `True`
- rows_ok: `2` / `2`
- matrix_coverage: `2` / `2`
- pending_keys: `[]`

## Metric Summary

| metric | mean | std | n |
|---|---:|---:|---:|
| msle | 1.211540 | 0.261712 | 2 |
| mae | 15.077971 | 1.535153 | 2 |
| rmse | 19.442770 | 2.801256 | 2 |
| direction_accuracy | 0.750000 | 0.000000 | 2 |
| candidate_recall_full | 0.134495 | 0.036934 | 2 |
| hits@10 | 0.006250 | 0.006250 | 2 |
| hits@50 | 0.187500 | 0.025000 | 2 |
| hits@100 | 0.187500 | 0.025000 | 2 |
| map@100 | 0.016705 | 0.000212 | 2 |
| mrr | 0.046354 | 0.000521 | 2 |
| macro_micro_consistency | 0.641962 | 0.012276 | 2 |

## Schema

- ok: `True`
