# KT2 vs MINDS Comparison

- status: `ok`
- evidence_level: `preflight`
- full_validation_passed: `False`
- overall_verdict: `does_not_support_kt2_improvement`
- datasets: `douban, twitter, memetracker`
- seeds: `42`

Compares trainable original MINDS public-code baseline against KT2SequenceJointModel on the same FOREST-source datasets. Handcrafted/heuristic baselines are excluded from the improvement verdict. preflight evidence proves the pipeline and a directional comparison only; full_validation_passed=true is required before claiming final KT2 improvement over MINDS.

## Model Filter

- allowed_models: `KT2SequenceJointModel, MINDS`
- ignored_non_comparison_row_count: `0`
- rule: `Only trainable MINDS and KT2SequenceJointModel rows can enter pair verdicts and metric deltas.`

## Full-Run Requirements

| check | passed |
|---|---:|
| dataset_count_at_least_3 | `True` |
| seed_count_at_least_3 | `False` |
| minds_epochs_at_least_5 | `False` |
| kt2_epochs_at_least_5 | `False` |
| minds_uses_all_available_cascades | `False` |
| kt2_uses_all_train_and_test_cascades | `False` |
| kt2_unbudgeted_training_and_eval | `True` |
| no_missing_model_pairs | `True` |
| has_completed_comparisons | `True` |

## Pair Verdicts

| dataset | seed | verdict | positive | negative | tie |
|---|---:|---|---:|---:|---:|
| douban | 42 | does_not_support_kt2_improvement | 1 | 6 | 0 |
| twitter | 42 | does_not_support_kt2_improvement | 1 | 6 | 0 |
| memetracker | 42 | does_not_support_kt2_improvement | 1 | 6 | 0 |

## Metric Deltas

| dataset | metric | MINDS | KT2 | better-direction delta | interpretation |
|---|---|---:|---:|---:|---|
| douban | msle | 19.347897 | 1.249664 | 18.098232 | supports_kt2 |
| douban | hits@10 | 0.022222 | 0.000000 | -0.022222 | supports_minds |
| douban | hits@50 | 0.088889 | 0.041667 | -0.047222 | supports_minds |
| douban | hits@100 | 0.333333 | 0.083333 | -0.250000 | supports_minds |
| douban | map@10 | 0.002222 | 0.000000 | -0.002222 | supports_minds |
| douban | map@50 | 0.005423 | 0.001096 | -0.004326 | supports_minds |
| douban | map@100 | 0.009089 | 0.001700 | -0.007389 | supports_minds |
| twitter | msle | 6.036691 | 0.992817 | 5.043874 | supports_kt2 |
| twitter | hits@10 | 0.111111 | 0.000000 | -0.111111 | supports_minds |
| twitter | hits@50 | 0.111111 | 0.000000 | -0.111111 | supports_minds |
| twitter | hits@100 | 0.111111 | 0.000000 | -0.111111 | supports_minds |
| twitter | map@10 | 0.011111 | 0.000000 | -0.011111 | supports_minds |
| twitter | map@50 | 0.011111 | 0.000000 | -0.011111 | supports_minds |
| twitter | map@100 | 0.011111 | 0.000000 | -0.011111 | supports_minds |
| memetracker | msle | 9.000000 | 0.838688 | 8.161312 | supports_kt2 |
| memetracker | hits@10 | 0.142857 | 0.000000 | -0.142857 | supports_minds |
| memetracker | hits@50 | 0.285714 | 0.125000 | -0.160714 | supports_minds |
| memetracker | hits@100 | 0.642857 | 0.125000 | -0.517857 | supports_minds |
| memetracker | map@10 | 0.043651 | 0.000000 | -0.043651 | supports_minds |
| memetracker | map@50 | 0.053001 | 0.007511 | -0.045491 | supports_minds |
| memetracker | map@100 | 0.057629 | 0.007511 | -0.050118 | supports_minds |
