# KT2 vs MINDS Comparison

- status: `ok`
- evidence_level: `preflight`
- full_validation_passed: `False`
- overall_verdict: `does_not_support_kt2_improvement`
- datasets: `douban`
- seeds: `42`

Compares trainable original MINDS public-code baseline against KT2SequenceJointModel on the same FOREST-source datasets. Handcrafted/heuristic baselines are excluded from the improvement verdict. preflight evidence proves the pipeline and a directional comparison only; full_validation_passed=true is required before claiming final KT2 improvement over MINDS.

## Model Filter

- allowed_models: `KT2SequenceJointModel, MINDS`
- ignored_non_comparison_row_count: `0`
- rule: `Only trainable MINDS and KT2SequenceJointModel rows can enter pair verdicts and metric deltas.`

## Full-Run Requirements

| check | passed |
|---|---:|
| dataset_count_at_least_3 | `False` |
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

## Metric Deltas

| dataset | metric | MINDS | KT2 | better-direction delta | interpretation |
|---|---|---:|---:|---:|---|
| douban | msle | 23.592028 | 0.967610 | 22.624418 | supports_kt2 |
| douban | hits@10 | 0.018692 | 0.000000 | -0.018692 | supports_minds |
| douban | hits@50 | 0.056075 | 0.000000 | -0.056075 | supports_minds |
| douban | hits@100 | 0.112150 | 0.016667 | -0.095483 | supports_minds |
| douban | map@10 | 0.003115 | 0.000000 | -0.003115 | supports_minds |
| douban | map@50 | 0.004056 | 0.000000 | -0.004056 | supports_minds |
| douban | map@100 | 0.004845 | 0.000168 | -0.004677 | supports_minds |
