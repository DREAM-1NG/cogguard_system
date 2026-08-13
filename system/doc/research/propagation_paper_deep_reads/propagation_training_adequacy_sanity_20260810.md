# Propagation Training Adequacy 2026-08-10

- status: `ok`
- protocol_id: `propagation_training_adequacy_forestsplit_v1`
- datasets: `twitter`
- seeds: `42`
- models: `Ours`
- epoch_grid: `1`
- train/eval cascades: `20/10`

This experiment diagnoses whether the 5-epoch sequence model is undertrained. It must be reported before any SOTA comparison and cannot by itself prove original-paper-level performance.

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
| twitter | Ours | 1 | 16 | 0.9351 | 9.5982 | 36.9855 | 0.0667 | 0.0017 | 0.0117 | 2.2311 |

## Adequacy Verdicts

| Dataset | Model | Epoch Range | Verdict | Interpretation |
|---|---|---|---|---|

## Reporting Rule

- If `undertraining_likely` appears, the corresponding 5-epoch result must be treated as premature.
- If `plateau_or_mixed` appears, inspect candidate coverage, loss conflict, model capacity, and protocol mismatch before increasing epochs further.
- SOTA comparison should only resume after this report has at least one stable multi-seed epoch setting.
