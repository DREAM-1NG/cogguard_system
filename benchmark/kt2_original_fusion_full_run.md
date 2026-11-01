# KT2 Original-Subpath Fusion Experiment

- status: `ok`
- reproduction_level: `kt2_joint_model_full_run`
- datasets: `douban`
- seeds: `42`
- obs_ratios: `0.3`
- config_id: `full-run-preflight`
- runs: `1`
- elapsed_s: `47.631`

Boundary: Runs KT2JointModel with upstream MINDS Module.forward, FOREST RNNModel/RRModel, and CasFT GaussianDiffusion_ST plus CombinedSpatiotemporalModel5 auxiliary and main-fusion subpaths as a same-protocol KT2 joint-model full-run evidence row. This is KT2's integrated model evidence, not a frontier-paper full reproduction label; completion still requires same-protocol MINDS, FOREST, and CasFT baseline full-run comparison.

## Original-Subpath Audit

- all_original_subpaths_passed: `True`
- all_alignment_losses_recorded: `True`
- rows_ok: `1` / `1`
- matrix_coverage: `1` / `1`
- pending_keys: `[]`

## Metric Summary

| metric | mean | std | n |
|---|---:|---:|---:|
| msle | 1.234727 | 0.000000 | 1 |
| mae | 17.655910 | 0.000000 | 1 |
| rmse | 22.563375 | 0.000000 | 1 |
| direction_accuracy | 0.833333 | 0.000000 | 1 |
| candidate_recall_full | 0.111111 | 0.000000 | 1 |
| hits@10 | 0.016667 | 0.000000 | 1 |
| hits@50 | 0.133333 | 0.000000 | 1 |
| hits@100 | 0.175000 | 0.000000 | 1 |
| map@100 | 0.013337 | 0.000000 | 1 |
| mrr | 0.073647 | 0.000000 | 1 |
| macro_micro_consistency | 0.569581 | 0.000000 | 1 |

## Schema

- ok: `True`
