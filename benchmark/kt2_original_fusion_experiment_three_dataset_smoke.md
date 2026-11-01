# KT2 Original-Subpath Fusion Experiment

- status: `ok`
- reproduction_level: `kt2_joint_model_small_run`
- datasets: `douban, twitter, memetracker`
- seeds: `42`
- runs: `3`
- elapsed_s: `78.149`

Boundary: Runs KT2JointModel with upstream MINDS Module.forward, FOREST RNNModel/RRModel, and CasFT GaussianDiffusion_ST plus CombinedSpatiotemporalModel5 auxiliary subpaths. This is a repeatable original-subpath fusion experiment, not full original-paper data protocol or full-run reproduction.

## Original-Subpath Audit

- all_original_subpaths_passed: `True`
- all_alignment_losses_recorded: `True`
- rows_ok: `3` / `3`

## Metric Summary

| metric | mean | std | n |
|---|---:|---:|---:|
| msle | 1.706303 | 0.431223 | 3 |
| mae | 15.751209 | 1.664359 | 3 |
| rmse | 21.945941 | 3.457705 | 3 |
| direction_accuracy | 0.666667 | 0.117851 | 3 |
| candidate_recall_full | 0.094983 | 0.032417 | 3 |
| hits@10 | 0.050000 | 0.062082 | 3 |
| hits@50 | 0.141667 | 0.087995 | 3 |
| hits@100 | 0.141667 | 0.087995 | 3 |
| map@100 | 0.018765 | 0.014797 | 3 |
| mrr | 0.061227 | 0.045653 | 3 |
| macro_micro_consistency | 0.646705 | 0.039554 | 3 |

## Schema

- ok: `True`
