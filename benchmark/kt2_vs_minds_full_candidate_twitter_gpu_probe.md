# KT2 vs MINDS Comparison

- status: `partial`
- evidence_level: `preflight`
- full_validation_passed: `False`
- overall_verdict: `insufficient_evidence`
- datasets: `twitter`
- seeds: `42`

Compares trainable original MINDS public-code baseline against KT2JointModel on the same FOREST-source datasets. Handcrafted/heuristic baselines are excluded from the improvement verdict. preflight evidence proves the pipeline and a directional comparison only; full_validation_passed=true is required before claiming final KT2 improvement over MINDS.

## Full-Run Requirements

| check | passed |
|---|---:|
| dataset_count_at_least_3 | `False` |
| seed_count_at_least_3 | `False` |
| minds_epochs_at_least_5 | `True` |
| kt2_epochs_at_least_5 | `True` |
| minds_uses_all_available_cascades | `True` |
| kt2_uses_all_train_and_test_cascades | `True` |
| no_missing_model_pairs | `False` |
| has_completed_comparisons | `False` |

## Pair Verdicts

| dataset | seed | verdict | positive | negative | tie |
|---|---:|---|---:|---:|---:|

## Metric Deltas

| dataset | metric | MINDS | KT2 | better-direction delta | interpretation |
|---|---|---:|---:|---:|---|

## Missing / Failed Pairs

- `{'dataset': 'twitter', 'seed': 42, 'minds_status': 'ok', 'kt2_status': None}`
