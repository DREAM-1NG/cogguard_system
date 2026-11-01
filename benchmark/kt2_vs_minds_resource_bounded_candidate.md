# KT2 vs MINDS Comparison

- status: `ok`
- evidence_level: `resource_bounded_full_source_candidate`
- full_validation_passed: `False`
- overall_verdict: `does_not_support_kt2_improvement`
- datasets: `douban, twitter, memetracker`
- seeds: `42`

Compares trainable original MINDS public-code baseline against KT2JointModel on the same FOREST-source datasets. Handcrafted/heuristic baselines are excluded from the improvement verdict. preflight evidence proves the pipeline and a directional comparison only; full_validation_passed=true is required before claiming final KT2 improvement over MINDS.

## Model Filter

- allowed_models: `KT2JointModel, MINDS`
- ignored_non_comparison_row_count: `0`
- rule: `Only trainable MINDS and KT2JointModel rows can enter pair verdicts and metric deltas.`

## Full-Run Requirements

| check | passed |
|---|---:|
| dataset_count_at_least_3 | `True` |
| seed_count_at_least_3 | `False` |
| minds_epochs_at_least_5 | `True` |
| kt2_epochs_at_least_5 | `True` |
| minds_uses_all_available_cascades | `True` |
| kt2_uses_all_train_and_test_cascades | `True` |
| kt2_unbudgeted_training_and_eval | `False` |
| no_missing_model_pairs | `True` |
| has_completed_comparisons | `True` |

## Pair Verdicts

| dataset | seed | verdict | positive | negative | tie |
|---|---:|---|---:|---:|---:|
| douban | 42 | does_not_support_kt2_improvement | 1 | 6 | 0 |
| twitter | 42 | supports_kt2_improvement | 6 | 1 | 0 |
| memetracker | 42 | does_not_support_kt2_improvement | 3 | 4 | 0 |

## Metric Deltas

| dataset | metric | MINDS | KT2 | better-direction delta | interpretation |
|---|---|---:|---:|---:|---|
| douban | msle | 0.015878 | 0.078132 | -0.062254 | supports_minds |
| douban | hits@10 | 0.138016 | 0.122281 | -0.015736 | supports_minds |
| douban | hits@50 | 0.235657 | 0.226082 | -0.009575 | supports_minds |
| douban | hits@100 | 0.303097 | 0.293622 | -0.009475 | supports_minds |
| douban | map@10 | 0.074987 | 0.064134 | -0.010853 | supports_minds |
| douban | map@50 | 0.079293 | 0.077878 | -0.001415 | supports_minds |
| douban | map@100 | 0.080253 | 0.081430 | 0.001178 | supports_kt2 |
| twitter | msle | 0.076809 | 0.179472 | -0.102663 | supports_minds |
| twitter | hits@10 | 0.083660 | 0.214150 | 0.130490 | supports_kt2 |
| twitter | hits@50 | 0.189397 | 0.398396 | 0.208999 | supports_kt2 |
| twitter | hits@100 | 0.266521 | 0.469337 | 0.202816 | supports_kt2 |
| twitter | map@10 | 0.047067 | 0.152878 | 0.105812 | supports_kt2 |
| twitter | map@50 | 0.051719 | 0.189499 | 0.137781 | supports_kt2 |
| twitter | map@100 | 0.052770 | 0.194860 | 0.142090 | supports_kt2 |
| memetracker | msle | 0.007386 | 0.071957 | -0.064571 | supports_minds |
| memetracker | hits@10 | 0.238137 | 0.208925 | -0.029212 | supports_minds |
| memetracker | hits@50 | 0.436280 | 0.403290 | -0.032990 | supports_minds |
| memetracker | hits@100 | 0.546095 | 0.501699 | -0.044396 | supports_minds |
| memetracker | map@10 | 0.128622 | 0.139331 | 0.010709 | supports_kt2 |
| memetracker | map@50 | 0.137588 | 0.171310 | 0.033722 | supports_kt2 |
| memetracker | map@100 | 0.139162 | 0.178543 | 0.039381 | supports_kt2 |
