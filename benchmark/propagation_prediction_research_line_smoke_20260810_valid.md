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
| kt2_unbudgeted_training_and_eval | `False` |
| no_missing_model_pairs | `True` |
| has_completed_comparisons | `True` |

## Pair Verdicts

| dataset | seed | verdict | positive | negative | tie |
|---|---:|---|---:|---:|---:|
| douban | 42 | does_not_support_kt2_improvement | 1 | 4 | 2 |
| twitter | 42 | supports_kt2_improvement | 4 | 1 | 2 |
| memetracker | 42 | does_not_support_kt2_improvement | 2 | 3 | 2 |

## Metric Deltas

| dataset | metric | MINDS | KT2 | better-direction delta | interpretation |
|---|---|---:|---:|---:|---|
| douban | msle | 18.441401 | 0.219169 | 18.222232 | supports_kt2 |
| douban | hits@10 | 0.000000 | 0.000000 | 0.000000 | tie |
| douban | hits@50 | 0.046729 | 0.033333 | -0.013396 | supports_minds |
| douban | hits@100 | 0.093458 | 0.066667 | -0.026791 | supports_minds |
| douban | map@10 | 0.000000 | 0.000000 | 0.000000 | tie |
| douban | map@50 | 0.001817 | 0.000813 | -0.001004 | supports_minds |
| douban | map@100 | 0.002634 | 0.001157 | -0.001478 | supports_minds |
| twitter | msle | 7.399744 | 0.225240 | 7.174504 | supports_kt2 |
| twitter | hits@10 | 0.000000 | 0.000000 | 0.000000 | tie |
| twitter | hits@50 | 0.000000 | 0.033333 | 0.033333 | supports_kt2 |
| twitter | hits@100 | 0.034483 | 0.033333 | -0.001149 | supports_minds |
| twitter | map@10 | 0.000000 | 0.000000 | 0.000000 | tie |
| twitter | map@50 | 0.000000 | 0.001449 | 0.001449 | supports_kt2 |
| twitter | map@100 | 0.000493 | 0.001449 | 0.000957 | supports_kt2 |
| memetracker | msle | 11.639974 | 0.134506 | 11.505467 | supports_kt2 |
| memetracker | hits@10 | 0.000000 | 0.000000 | 0.000000 | tie |
| memetracker | hits@50 | 0.122449 | 0.066667 | -0.055782 | supports_minds |
| memetracker | hits@100 | 0.224490 | 0.233333 | 0.008844 | supports_kt2 |
| memetracker | map@10 | 0.000000 | 0.000000 | 0.000000 | tie |
| memetracker | map@50 | 0.004572 | 0.002627 | -0.001944 | supports_minds |
| memetracker | map@100 | 0.006033 | 0.004802 | -0.001231 | supports_minds |
