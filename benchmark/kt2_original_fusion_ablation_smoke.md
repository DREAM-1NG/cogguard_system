# KT2 Original-Fusion Ablation

- status: `ok`
- reproduction_level: `kt2_original_fusion_ablation_small_run`
- datasets: `douban`
- seeds: `42`
- obs_ratios: `0.3`
- variants: `minds_baseline, minds_plus_forest, minds_plus_casft, full_minds_forest_casft, local_kt2_bridge`
- matrix_coverage: `5` / `5`

Boundary: Same-protocol KT2 ablation for MINDS baseline, FOREST macro/micro constraint, and CasFT continuous trend migration. It is evidence for method design, not full original-paper reproduction.

## Original Subpaths

- full_variant_rows: `1`
- all_full_variant_original_subpaths_passed: `True`
- all_full_variant_alignment_losses_recorded: `True`

## Variant Metrics

| variant | metric | mean | std | n |
|---|---|---:|---:|---:|
| full_minds_forest_casft | msle | 1.473253 | 0.000000 | 1 |
| full_minds_forest_casft | mae | 16.613124 | 0.000000 | 1 |
| full_minds_forest_casft | rmse | 22.244026 | 0.000000 | 1 |
| full_minds_forest_casft | direction_accuracy | 0.750000 | 0.000000 | 1 |
| full_minds_forest_casft | candidate_recall_full | 0.097561 | 0.000000 | 1 |
| full_minds_forest_casft | hits@10 | 0.012500 | 0.000000 | 1 |
| full_minds_forest_casft | hits@50 | 0.162500 | 0.000000 | 1 |
| full_minds_forest_casft | hits@100 | 0.162500 | 0.000000 | 1 |
| full_minds_forest_casft | map@100 | 0.016493 | 0.000000 | 1 |
| full_minds_forest_casft | mrr | 0.046875 | 0.000000 | 1 |
| full_minds_forest_casft | macro_micro_consistency | 0.654239 | 0.000000 | 1 |
| local_kt2_bridge | msle | 1.462063 | 0.000000 | 1 |
| local_kt2_bridge | mae | 16.541697 | 0.000000 | 1 |
| local_kt2_bridge | rmse | 22.216738 | 0.000000 | 1 |
| local_kt2_bridge | direction_accuracy | 0.750000 | 0.000000 | 1 |
| local_kt2_bridge | candidate_recall_full | 0.097561 | 0.000000 | 1 |
| local_kt2_bridge | hits@10 | 0.000000 | 0.000000 | 1 |
| local_kt2_bridge | hits@50 | 0.162500 | 0.000000 | 1 |
| local_kt2_bridge | hits@100 | 0.162500 | 0.000000 | 1 |
| local_kt2_bridge | map@100 | 0.015362 | 0.000000 | 1 |
| local_kt2_bridge | mrr | 0.024246 | 0.000000 | 1 |
| local_kt2_bridge | macro_micro_consistency | 0.652542 | 0.000000 | 1 |
| minds_baseline | msle | 1.464336 | 0.000000 | 1 |
| minds_baseline | mae | 16.544019 | 0.000000 | 1 |
| minds_baseline | rmse | 22.221323 | 0.000000 | 1 |
| minds_baseline | direction_accuracy | 0.750000 | 0.000000 | 1 |
| minds_baseline | candidate_recall_full | 0.097561 | 0.000000 | 1 |
| minds_baseline | hits@10 | 0.000000 | 0.000000 | 1 |
| minds_baseline | hits@50 | 0.162500 | 0.000000 | 1 |
| minds_baseline | hits@100 | 0.162500 | 0.000000 | 1 |
| minds_baseline | map@100 | 0.015972 | 0.000000 | 1 |
| minds_baseline | mrr | 0.036458 | 0.000000 | 1 |
| minds_baseline | macro_micro_consistency | 0.653495 | 0.000000 | 1 |
| minds_plus_casft | msle | 1.466294 | 0.000000 | 1 |
| minds_plus_casft | mae | 16.561001 | 0.000000 | 1 |
| minds_plus_casft | rmse | 22.226423 | 0.000000 | 1 |
| minds_plus_casft | direction_accuracy | 0.750000 | 0.000000 | 1 |
| minds_plus_casft | candidate_recall_full | 0.097561 | 0.000000 | 1 |
| minds_plus_casft | hits@10 | 0.000000 | 0.000000 | 1 |
| minds_plus_casft | hits@50 | 0.162500 | 0.000000 | 1 |
| minds_plus_casft | hits@100 | 0.162500 | 0.000000 | 1 |
| minds_plus_casft | map@100 | 0.015972 | 0.000000 | 1 |
| minds_plus_casft | mrr | 0.036458 | 0.000000 | 1 |
| minds_plus_casft | macro_micro_consistency | 0.653816 | 0.000000 | 1 |
| minds_plus_forest | msle | 1.463354 | 0.000000 | 1 |
| minds_plus_forest | mae | 16.540220 | 0.000000 | 1 |
| minds_plus_forest | rmse | 22.219113 | 0.000000 | 1 |
| minds_plus_forest | direction_accuracy | 0.750000 | 0.000000 | 1 |
| minds_plus_forest | candidate_recall_full | 0.097561 | 0.000000 | 1 |
| minds_plus_forest | hits@10 | 0.000000 | 0.000000 | 1 |
| minds_plus_forest | hits@50 | 0.162500 | 0.000000 | 1 |
| minds_plus_forest | hits@100 | 0.162500 | 0.000000 | 1 |
| minds_plus_forest | map@100 | 0.015347 | 0.000000 | 1 |
| minds_plus_forest | mrr | 0.023958 | 0.000000 | 1 |
| minds_plus_forest | macro_micro_consistency | 0.652556 | 0.000000 | 1 |

## Full vs MINDS Baseline

| metric | baseline | full | better-direction delta | interpretation |
|---|---:|---:|---:|---|
| msle | 1.464336 | 1.473253 | -0.008917 | non_positive_or_inconclusive |
| mae | 16.544019 | 16.613124 | -0.069105 | non_positive_or_inconclusive |
| rmse | 22.221323 | 22.244026 | -0.022703 | non_positive_or_inconclusive |
| direction_accuracy | 0.750000 | 0.750000 | 0.000000 | non_positive_or_inconclusive |
| candidate_recall_full | 0.097561 | 0.097561 | 0.000000 | non_positive_or_inconclusive |
| hits@10 | 0.000000 | 0.012500 | 0.012500 | positive_supports_full_variant |
| hits@50 | 0.162500 | 0.162500 | 0.000000 | non_positive_or_inconclusive |
| hits@100 | 0.162500 | 0.162500 | 0.000000 | non_positive_or_inconclusive |
| map@100 | 0.015972 | 0.016493 | 0.000521 | positive_supports_full_variant |
| mrr | 0.036458 | 0.046875 | 0.010417 | positive_supports_full_variant |
| macro_micro_consistency | 0.653495 | 0.654239 | 0.000743 | positive_supports_full_variant |
