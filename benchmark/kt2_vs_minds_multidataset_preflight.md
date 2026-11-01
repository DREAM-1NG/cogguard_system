# KT2 vs MINDS Comparison

- status: `ok`
- evidence_level: `preflight`
- full_validation_passed: `False`
- overall_verdict: `partially_supports_kt2_improvement`
- datasets: `douban, twitter, memetracker`
- seeds: `42`

Compares trainable original MINDS public-code baseline against KT2JointModel on the same FOREST-source datasets. Handcrafted/heuristic baselines are excluded from the improvement verdict. preflight evidence proves the pipeline and a directional comparison only; full_validation_passed=true is required before claiming final KT2 improvement over MINDS.

## Full-Run Requirements

| check | passed |
|---|---:|
| dataset_count_at_least_3 | `True` |
| seed_count_at_least_3 | `False` |
| minds_epochs_at_least_5 | `False` |
| kt2_epochs_at_least_5 | `False` |
| minds_uses_all_available_cascades | `False` |
| kt2_uses_all_train_and_test_cascades | `False` |
| no_missing_model_pairs | `True` |
| has_completed_comparisons | `True` |

## Pair Verdicts

| dataset | seed | verdict | positive | negative | tie |
|---|---:|---|---:|---:|---:|
| douban | 42 | does_not_support_kt2_improvement | 2 | 5 | 0 |
| twitter | 42 | supports_kt2_improvement | 7 | 0 | 0 |
| memetracker | 42 | supports_kt2_improvement | 5 | 2 | 0 |

## Metric Deltas

| dataset | metric | MINDS | KT2 | better-direction delta | interpretation |
|---|---|---:|---:|---:|---|
| douban | msle | 20.399446 | 1.459348 | 18.940099 | supports_kt2 |
| douban | hits@10 | 0.019231 | 0.000000 | -0.019231 | supports_minds |
| douban | hits@50 | 0.067308 | 0.133333 | 0.066026 | supports_kt2 |
| douban | hits@100 | 0.153846 | 0.133333 | -0.020513 | supports_minds |
| douban | map@10 | 0.012821 | 0.000000 | -0.012821 | supports_minds |
| douban | map@50 | 0.015299 | 0.008968 | -0.006331 | supports_minds |
| douban | map@100 | 0.016734 | 0.008968 | -0.007766 | supports_minds |
| twitter | msle | 6.036691 | 2.029794 | 4.006896 | supports_kt2 |
| twitter | hits@10 | 0.000000 | 0.116667 | 0.116667 | supports_kt2 |
| twitter | hits@50 | 0.000000 | 0.183333 | 0.183333 | supports_kt2 |
| twitter | hits@100 | 0.000000 | 0.183333 | 0.183333 | supports_kt2 |
| twitter | map@10 | 0.000000 | 0.031944 | 0.031944 | supports_kt2 |
| twitter | map@50 | 0.000000 | 0.034118 | 0.034118 | supports_kt2 |
| twitter | map@100 | 0.000000 | 0.034118 | 0.034118 | supports_kt2 |
| memetracker | msle | 12.299967 | 0.691676 | 11.608290 | supports_kt2 |
| memetracker | hits@10 | 0.000000 | 0.033333 | 0.033333 | supports_kt2 |
| memetracker | hits@50 | 0.119048 | 0.033333 | -0.085714 | supports_minds |
| memetracker | hits@100 | 0.261905 | 0.033333 | -0.228571 | supports_minds |
| memetracker | map@10 | 0.000000 | 0.005556 | 0.005556 | supports_kt2 |
| memetracker | map@50 | 0.003545 | 0.005556 | 0.002010 | supports_kt2 |
| memetracker | map@100 | 0.005168 | 0.005556 | 0.000388 | supports_kt2 |
