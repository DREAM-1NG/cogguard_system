# KT2 vs MINDS Comparison

- status: `ok`
- evidence_level: `preflight`
- full_validation_passed: `False`
- overall_verdict: `does_not_support_kt2_improvement`
- datasets: `douban`
- seeds: `7`

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
| douban | 7 | does_not_support_kt2_improvement | 1 | 6 | 0 |

## Metric Deltas

| dataset | metric | MINDS | KT2 | better-direction delta | interpretation |
|---|---|---:|---:|---:|---|
| douban | msle | 26.728127 | 0.980269 | 25.747857 | supports_kt2 |
| douban | hits@10 | 0.057143 | 0.000000 | -0.057143 | supports_minds |
| douban | hits@50 | 0.228571 | 0.055556 | -0.173016 | supports_minds |
| douban | hits@100 | 0.657143 | 0.055556 | -0.601587 | supports_minds |
| douban | map@10 | 0.009796 | 0.000000 | -0.009796 | supports_minds |
| douban | map@50 | 0.016291 | 0.001684 | -0.014608 | supports_minds |
| douban | map@100 | 0.022642 | 0.001684 | -0.020958 | supports_minds |
