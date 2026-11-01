# KT2 Original-Subpath Fusion Experiment

- status: `ok`
- reproduction_level: `kt2_joint_model_small_run`
- datasets: `douban, twitter, memetracker`
- seeds: `42, 43, 44`
- obs_ratios: `0.1, 0.3, 0.5`
- config_id: `default-small`
- runs: `27`
- elapsed_s: `0.074`

Boundary: Runs KT2JointModel with upstream MINDS Module.forward, FOREST RNNModel/RRModel, and CasFT GaussianDiffusion_ST plus CombinedSpatiotemporalModel5 auxiliary subpaths. This is a repeatable original-subpath fusion experiment, not full original-paper data protocol or full-run reproduction.

## Original-Subpath Audit

- all_original_subpaths_passed: `True`
- all_alignment_losses_recorded: `True`
- rows_ok: `27` / `27`
- matrix_coverage: `27` / `27`
- pending_keys: `[]`

## Metric Summary

| metric | mean | std | n |
|---|---:|---:|---:|
| msle | 3.393766 | 6.255048 | 27 |
| mae | 106.203344 | 404.143639 | 27 |
| rmse | 202.067233 | 805.062674 | 27 |
| direction_accuracy | 0.777778 | 0.157135 | 27 |
| candidate_recall_full | 0.097146 | 0.041512 | 27 |
| hits@10 | 0.045370 | 0.054342 | 27 |
| hits@50 | 0.147222 | 0.092191 | 27 |
| hits@100 | 0.147222 | 0.092191 | 27 |
| map@100 | 0.018308 | 0.014272 | 27 |
| mrr | 0.066077 | 0.043018 | 27 |
| macro_micro_consistency | 0.658331 | 0.096610 | 27 |

## Schema

- ok: `True`
