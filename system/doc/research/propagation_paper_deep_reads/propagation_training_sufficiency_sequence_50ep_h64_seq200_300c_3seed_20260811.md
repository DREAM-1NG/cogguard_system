# Propagation Training Adequacy 2026-08-10

- status: `partial`
- protocol_id: `propagation_training_adequacy_forestsplit_v1`
- datasets: `douban, twitter, memetracker`
- seeds: `42, 43, 44`
- models: `Ours, MINDS`
- epoch_grid: `50`
- train/eval cascades: `300/100`

This experiment diagnoses whether the 5-epoch sequence model is undertrained. It must be reported before any SOTA comparison and cannot by itself prove original-paper-level performance.

## Protocol Audit

| item | value |
|---|---:|
| passed | `False` |
| row_count | `8` |
| fair_ok_count | `8` |
| requested_count | `18` |
| missing_or_nonfair_count | `10` |

## Learning Curve Summary

| Dataset | Model | Epochs | Hidden | MSLE | MAE | Trend MAE | Hits@100 | MRR | NDCG@100 | Final Loss |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| douban | MINDS | 50 | 64 | 0.0679 | 3.0348 | 260.5751 | 0.0489 | 0.0045 | 0.0108 | 0.0185 |
| douban | Ours | 50 | 64 | 0.0810 | 5.3340 | 197.5513 | 0.0556 | 0.0075 | 0.0146 | 0.1152 |
| twitter | MINDS | 50 | 64 | 0.1141 | 2.5733 | 226.4761 | 0.0367 | 0.0052 | 0.0102 | 0.0194 |
| twitter | Ours | 50 | 64 | 0.1290 | 5.0665 | 184.2815 | 0.0333 | 0.0038 | 0.0083 | 0.1344 |

## Adequacy Verdicts

| Dataset | Model | Epoch Range | Verdict | Interpretation |
|---|---|---|---|---|

## Reporting Rule

- If `undertraining_likely` appears, the corresponding 5-epoch result must be treated as premature.
- If `plateau_or_mixed` appears, inspect candidate coverage, loss conflict, model capacity, and protocol mismatch before increasing epochs further.
- SOTA comparison should only resume after this report has at least one stable multi-seed epoch setting.
