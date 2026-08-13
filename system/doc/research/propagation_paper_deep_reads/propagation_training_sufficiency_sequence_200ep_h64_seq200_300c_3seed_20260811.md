# Propagation Training Adequacy 2026-08-10

- status: `ok`
- protocol_id: `propagation_training_adequacy_forestsplit_v1`
- datasets: `douban, twitter, memetracker`
- seeds: `42, 43, 44`
- models: `Ours, MINDS`
- epoch_grid: `200`
- train/eval cascades: `300/100`

This experiment diagnoses whether the 5-epoch sequence model is undertrained. It must be reported before any SOTA comparison and cannot by itself prove original-paper-level performance.

## Protocol Audit

| item | value |
|---|---:|
| passed | `True` |
| row_count | `18` |
| fair_ok_count | `18` |
| requested_count | `18` |
| missing_or_nonfair_count | `0` |

## Learning Curve Summary

| Dataset | Model | Epochs | Hidden | MSLE | MAE | Trend MAE | Hits@100 | MRR | NDCG@100 | Final Loss |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| douban | MINDS | 200 | 64 | 0.0602 | 2.6610 | 240.7618 | 0.0522 | 0.0055 | 0.0124 | 0.0142 |
| douban | Ours | 200 | 64 | 0.0813 | 5.3475 | 188.1981 | 0.0578 | 0.0084 | 0.0159 | 0.0798 |
| memetracker | MINDS | 200 | 64 | 0.0914 | 1.6211 | 66.9913 | 0.1067 | 0.0153 | 0.0294 | 0.0165 |
| memetracker | Ours | 200 | 64 | 0.1107 | 2.0762 | 55.5994 | 0.1122 | 0.0196 | 0.0342 | 0.0534 |
| twitter | MINDS | 200 | 64 | 0.1086 | 2.7380 | 218.8248 | 0.0400 | 0.0095 | 0.0142 | 0.0153 |
| twitter | Ours | 200 | 64 | 0.1510 | 5.9517 | 183.2486 | 0.0378 | 0.0064 | 0.0114 | 0.1018 |

## Adequacy Verdicts

| Dataset | Model | Epoch Range | Verdict | Interpretation |
|---|---|---|---|---|

## Reporting Rule

- If `undertraining_likely` appears, the corresponding 5-epoch result must be treated as premature.
- If `plateau_or_mixed` appears, inspect candidate coverage, loss conflict, model capacity, and protocol mismatch before increasing epochs further.
- SOTA comparison should only resume after this report has at least one stable multi-seed epoch setting.
