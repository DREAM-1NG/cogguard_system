# KT2 vs MINDS Comparison

- status: `partial`
- evidence_level: `full_run_candidate`
- full_validation_passed: `False`
- overall_verdict: `insufficient_evidence`
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
| minds_uses_all_available_cascades | `True` |
| kt2_uses_all_train_and_test_cascades | `True` |
| kt2_unbudgeted_training_and_eval | `True` |
| no_missing_model_pairs | `False` |
| has_completed_comparisons | `False` |

## Pair Verdicts

| dataset | seed | verdict | positive | negative | tie |
|---|---:|---|---:|---:|---:|

## Metric Deltas

| dataset | metric | MINDS | KT2 | better-direction delta | interpretation |
|---|---|---:|---:|---:|---|

## Missing / Failed Pairs

- `{'dataset': 'douban', 'seed': 42, 'minds_status': 'failed', 'kt2_status': None}`
- `{'dataset': 'douban', 'seed': 43, 'minds_status': None, 'kt2_status': None}`
- `{'dataset': 'douban', 'seed': 44, 'minds_status': None, 'kt2_status': None}`
- `{'dataset': 'twitter', 'seed': 42, 'minds_status': None, 'kt2_status': None}`
- `{'dataset': 'twitter', 'seed': 43, 'minds_status': None, 'kt2_status': None}`
- `{'dataset': 'twitter', 'seed': 44, 'minds_status': None, 'kt2_status': None}`
- `{'dataset': 'memetracker', 'seed': 42, 'minds_status': None, 'kt2_status': None}`
- `{'dataset': 'memetracker', 'seed': 43, 'minds_status': None, 'kt2_status': None}`
- `{'dataset': 'memetracker', 'seed': 44, 'minds_status': None, 'kt2_status': None}`
