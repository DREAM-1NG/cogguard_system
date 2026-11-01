# KT2 vs MINDS Comparison

- status: `ok`
- evidence_level: `preflight`
- full_validation_passed: `False`
- overall_verdict: `does_not_support_kt2_improvement`
- datasets: `douban, twitter, memetracker`
- seeds: `42, 43, 44`

Compares trainable original MINDS public-code baseline against KT2SequenceJointModel on the same FOREST-source datasets. Handcrafted/heuristic baselines are excluded from the improvement verdict. preflight evidence proves the pipeline and a directional comparison only; full_validation_passed=true is required before claiming final KT2 improvement over MINDS.

## Model Filter

- allowed_models: `KT2SequenceJointModel, MINDS`
- ignored_non_comparison_row_count: `0`
- rule: `Only trainable MINDS and KT2SequenceJointModel rows can enter pair verdicts and metric deltas.`

## Full-Run Requirements

| check | passed |
|---|---:|
| dataset_count_at_least_3 | `True` |
| seed_count_at_least_3 | `True` |
| minds_epochs_at_least_5 | `True` |
| kt2_epochs_at_least_5 | `True` |
| minds_uses_all_available_cascades | `False` |
| kt2_uses_all_train_and_test_cascades | `False` |
| kt2_unbudgeted_training_and_eval | `True` |
| no_missing_model_pairs | `True` |
| has_completed_comparisons | `True` |

## Pair Verdicts

| dataset | seed | verdict | positive | negative | tie |
|---|---:|---|---:|---:|---:|
| douban | 42 | does_not_support_kt2_improvement | 0 | 7 | 0 |
| douban | 43 | does_not_support_kt2_improvement | 0 | 7 | 0 |
| douban | 44 | does_not_support_kt2_improvement | 0 | 7 | 0 |
| twitter | 42 | does_not_support_kt2_improvement | 1 | 6 | 0 |
| twitter | 43 | does_not_support_kt2_improvement | 0 | 7 | 0 |
| twitter | 44 | does_not_support_kt2_improvement | 1 | 6 | 0 |
| memetracker | 42 | does_not_support_kt2_improvement | 0 | 7 | 0 |
| memetracker | 43 | does_not_support_kt2_improvement | 0 | 7 | 0 |
| memetracker | 44 | does_not_support_kt2_improvement | 0 | 7 | 0 |

## Metric Deltas

| dataset | metric | MINDS | KT2 | better-direction delta | interpretation |
|---|---|---:|---:|---:|---|
| douban | msle | 0.074702 | 0.095646 | -0.020945 | supports_minds |
| douban | hits@10 | 0.149580 | 0.010000 | -0.139580 | supports_minds |
| douban | hits@50 | 0.218487 | 0.026667 | -0.191821 | supports_minds |
| douban | hits@100 | 0.278992 | 0.053333 | -0.225658 | supports_minds |
| douban | map@10 | 0.079825 | 0.004000 | -0.075825 | supports_minds |
| douban | map@50 | 0.082877 | 0.004572 | -0.078306 | supports_minds |
| douban | map@100 | 0.083771 | 0.004888 | -0.078882 | supports_minds |
| douban | msle | 0.037184 | 0.107834 | -0.070649 | supports_minds |
| douban | hits@10 | 0.157983 | 0.006667 | -0.151317 | supports_minds |
| douban | hits@50 | 0.221849 | 0.023333 | -0.198515 | supports_minds |
| douban | hits@100 | 0.272269 | 0.050000 | -0.222269 | supports_minds |
| douban | map@10 | 0.080831 | 0.001500 | -0.079331 | supports_minds |
| douban | map@50 | 0.083083 | 0.002089 | -0.080995 | supports_minds |
| douban | map@100 | 0.083750 | 0.002407 | -0.081343 | supports_minds |
| douban | msle | 0.077685 | 0.115476 | -0.037791 | supports_minds |
| douban | hits@10 | 0.152941 | 0.010000 | -0.142941 | supports_minds |
| douban | hits@50 | 0.201681 | 0.026667 | -0.175014 | supports_minds |
| douban | hits@100 | 0.265546 | 0.053333 | -0.212213 | supports_minds |
| douban | map@10 | 0.079981 | 0.005000 | -0.074981 | supports_minds |
| douban | map@50 | 0.082287 | 0.005572 | -0.076715 | supports_minds |
| douban | map@100 | 0.083199 | 0.005888 | -0.077311 | supports_minds |
| twitter | msle | 0.482290 | 0.118403 | 0.363887 | supports_kt2 |
| twitter | hits@10 | 0.059011 | 0.003333 | -0.055678 | supports_minds |
| twitter | hits@50 | 0.098884 | 0.010000 | -0.088884 | supports_minds |
| twitter | hits@100 | 0.140351 | 0.026667 | -0.113684 | supports_minds |
| twitter | map@10 | 0.048908 | 0.000556 | -0.048352 | supports_minds |
| twitter | map@50 | 0.050452 | 0.000774 | -0.049678 | supports_minds |
| twitter | map@100 | 0.051004 | 0.000993 | -0.050012 | supports_minds |
| twitter | msle | 0.083555 | 0.162664 | -0.079109 | supports_minds |
| twitter | hits@10 | 0.052632 | 0.006667 | -0.045965 | supports_minds |
| twitter | hits@50 | 0.106858 | 0.013333 | -0.093525 | supports_minds |
| twitter | hits@100 | 0.146730 | 0.030000 | -0.116730 | supports_minds |
| twitter | map@10 | 0.047196 | 0.001389 | -0.045807 | supports_minds |
| twitter | map@50 | 0.049353 | 0.001608 | -0.047745 | supports_minds |
| twitter | map@100 | 0.049922 | 0.001826 | -0.048096 | supports_minds |
| twitter | msle | 0.253966 | 0.105337 | 0.148629 | supports_kt2 |
| twitter | hits@10 | 0.059011 | 0.003333 | -0.055678 | supports_minds |
| twitter | hits@50 | 0.108453 | 0.010000 | -0.098453 | supports_minds |
| twitter | hits@100 | 0.137161 | 0.026667 | -0.110494 | supports_minds |
| twitter | map@10 | 0.048396 | 0.000556 | -0.047840 | supports_minds |
| twitter | map@50 | 0.050391 | 0.000774 | -0.049617 | supports_minds |
| twitter | map@100 | 0.050801 | 0.000993 | -0.049809 | supports_minds |
| memetracker | msle | 0.028376 | 0.101657 | -0.073282 | supports_minds |
| memetracker | hits@10 | 0.134956 | 0.046667 | -0.088289 | supports_minds |
| memetracker | hits@50 | 0.256637 | 0.066667 | -0.189971 | supports_minds |
| memetracker | hits@100 | 0.325221 | 0.123333 | -0.201888 | supports_minds |
| memetracker | map@10 | 0.086297 | 0.016778 | -0.069519 | supports_minds |
| memetracker | map@50 | 0.091953 | 0.017509 | -0.074443 | supports_minds |
| memetracker | map@100 | 0.092893 | 0.018254 | -0.074640 | supports_minds |
| memetracker | msle | 0.087351 | 0.150387 | -0.063037 | supports_minds |
| memetracker | hits@10 | 0.134956 | 0.023333 | -0.111622 | supports_minds |
| memetracker | hits@50 | 0.258850 | 0.043333 | -0.215516 | supports_minds |
| memetracker | hits@100 | 0.338496 | 0.100000 | -0.238496 | supports_minds |
| memetracker | map@10 | 0.086427 | 0.006944 | -0.079483 | supports_minds |
| memetracker | map@50 | 0.092150 | 0.007673 | -0.084477 | supports_minds |
| memetracker | map@100 | 0.093215 | 0.008417 | -0.084799 | supports_minds |
| memetracker | msle | 0.084526 | 0.129299 | -0.044773 | supports_minds |
| memetracker | hits@10 | 0.137168 | 0.016667 | -0.120501 | supports_minds |
| memetracker | hits@50 | 0.254425 | 0.036667 | -0.217758 | supports_minds |
| memetracker | hits@100 | 0.331858 | 0.093333 | -0.238525 | supports_minds |
| memetracker | map@10 | 0.086222 | 0.002778 | -0.083444 | supports_minds |
| memetracker | map@50 | 0.091329 | 0.003506 | -0.087823 | supports_minds |
| memetracker | map@100 | 0.092377 | 0.004248 | -0.088129 | supports_minds |
