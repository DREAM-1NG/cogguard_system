# Propagation Training Adequacy 2026-08-10

- status: `ok`
- protocol_id: `propagation_training_adequacy_forestsplit_v1`
- datasets: `douban`
- seeds: `999`
- models: `Ours`
- epoch_grid: `1`
- train/eval cascades: `1/1`

This experiment diagnoses whether 200-epoch sequence-model training is sufficient under the selected cascade caps and capacity. It must be reported before any SOTA comparison and cannot by itself prove original-paper-level performance.

## Protocol Audit

| item | value |
|---|---:|
| passed | `True` |
| row_count | `1` |
| fair_ok_count | `1` |
| requested_count | `1` |
| missing_or_nonfair_count | `0` |

## Learning Curve Summary

| Dataset | Model | Epochs | Hidden | MSLE | MAE | Trend MAE | Hits@100 | MRR | NDCG@100 | Final Loss |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| douban | Ours | 1 | 8 | 0.4606 | 2.5252 | 2.4008 | 0.0000 | 0.0000 | 0.0000 | 2.4894 |

## Adequacy Verdicts

| Dataset | Model | Epoch Range | Verdict | Interpretation |
|---|---|---|---|---|

## Reporting Rule

- If `undertraining_likely` appears, the corresponding shorter-run result must be treated as premature.
- If `plateau_or_mixed` appears, inspect candidate coverage, loss conflict, model capacity, and protocol mismatch before increasing epochs further.
- SOTA comparison should only resume after this report has at least one stable multi-seed epoch setting.
