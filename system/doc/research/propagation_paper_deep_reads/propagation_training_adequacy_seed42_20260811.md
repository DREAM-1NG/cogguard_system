# Propagation Training Adequacy 2026-08-10

- status: `ok`
- protocol_id: `propagation_training_adequacy_forestsplit_v1`
- datasets: `douban, twitter, memetracker`
- seeds: `42`
- models: `Ours, MINDS`
- epoch_grid: `5, 10, 20, 50`
- train/eval cascades: `300/100`

This experiment diagnoses whether the 5-epoch sequence model is undertrained. It must be reported before any SOTA comparison and cannot by itself prove original-paper-level performance.

## Protocol Audit

| item | value |
|---|---:|
| passed | `True` |
| row_count | `24` |
| fair_ok_count | `24` |
| requested_count | `24` |
| missing_or_nonfair_count | `0` |

## Learning Curve Summary

| Dataset | Model | Epochs | Hidden | MSLE | MAE | Trend MAE | Hits@100 | MRR | NDCG@100 | Final Loss |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| douban | MINDS | 5 | 32 | 0.1594 | 8.3387 | 367.7139 | 0.0567 | 0.0075 | 0.0149 | 1.8396 |
| douban | MINDS | 10 | 32 | 0.0608 | 3.7453 | 238.8936 | 0.0467 | 0.0028 | 0.0090 | 1.7954 |
| douban | MINDS | 20 | 32 | 0.0641 | 3.5668 | 266.4165 | 0.0500 | 0.0035 | 0.0102 | 0.5145 |
| douban | MINDS | 50 | 32 | 0.0444 | 2.2284 | 244.2190 | 0.0567 | 0.0112 | 0.0177 | 0.0526 |
| douban | Ours | 5 | 32 | 0.0851 | 4.3414 | 266.4444 | 0.0567 | 0.0051 | 0.0131 | 2.0724 |
| douban | Ours | 10 | 32 | 0.1207 | 6.4923 | 197.3885 | 0.0433 | 0.0020 | 0.0075 | 2.1902 |
| douban | Ours | 20 | 32 | 0.1425 | 7.1140 | 195.7222 | 0.0467 | 0.0027 | 0.0088 | 0.4854 |
| douban | Ours | 50 | 32 | 0.0762 | 4.3097 | 221.8086 | 0.0533 | 0.0098 | 0.0159 | 0.1671 |
| memetracker | MINDS | 5 | 32 | 0.1409 | 2.2499 | 60.7693 | 0.1200 | 0.0190 | 0.0353 | 1.9289 |
| memetracker | MINDS | 10 | 32 | 0.0792 | 1.5228 | 70.7130 | 0.1267 | 0.0176 | 0.0358 | 1.8924 |
| memetracker | MINDS | 20 | 32 | 0.0707 | 1.3990 | 71.5860 | 0.1233 | 0.0237 | 0.0397 | 1.2154 |
| memetracker | MINDS | 50 | 32 | 0.0695 | 1.3774 | 64.3540 | 0.1133 | 0.0187 | 0.0337 | 0.0384 |
| memetracker | Ours | 5 | 32 | 0.0948 | 2.3046 | 52.7685 | 0.1200 | 0.0192 | 0.0355 | 2.0870 |
| memetracker | Ours | 10 | 32 | 0.0765 | 1.7373 | 56.8013 | 0.1267 | 0.0205 | 0.0381 | 2.0121 |
| memetracker | Ours | 20 | 32 | 0.0902 | 1.8935 | 68.5776 | 0.1200 | 0.0182 | 0.0348 | 1.4715 |
| memetracker | Ours | 50 | 32 | 0.1327 | 2.2949 | 53.3105 | 0.1233 | 0.0238 | 0.0398 | 0.1553 |
| twitter | MINDS | 5 | 32 | 0.1645 | 5.0640 | 223.6390 | 0.0300 | 0.0035 | 0.0073 | 1.8943 |
| twitter | MINDS | 10 | 32 | 0.1051 | 3.3510 | 231.6109 | 0.0300 | 0.0027 | 0.0066 | 1.4041 |
| twitter | MINDS | 20 | 32 | 0.1073 | 3.3368 | 228.1178 | 0.0333 | 0.0052 | 0.0094 | 0.3440 |
| twitter | MINDS | 50 | 32 | 0.1107 | 2.9539 | 230.8426 | 0.0333 | 0.0052 | 0.0094 | 0.0342 |
| twitter | Ours | 5 | 32 | 0.1214 | 5.0100 | 177.1035 | 0.0300 | 0.0025 | 0.0065 | 2.3654 |
| twitter | Ours | 10 | 32 | 0.1478 | 7.2606 | 172.4265 | 0.0333 | 0.0038 | 0.0083 | 1.9065 |
| twitter | Ours | 20 | 32 | 0.1911 | 8.2956 | 167.7031 | 0.0300 | 0.0035 | 0.0073 | 0.3513 |
| twitter | Ours | 50 | 32 | 0.1126 | 5.2616 | 176.4948 | 0.0300 | 0.0052 | 0.0085 | 0.0425 |

## Adequacy Verdicts

| Dataset | Model | Epoch Range | Verdict | Interpretation |
|---|---|---|---|---|
| douban | MINDS | 5-50 | undertraining_likely | Later epochs improve multiple primary signals by more than 5%; the 5-epoch result is probably premature. |
| douban | Ours | 5-50 | undertraining_likely | Later epochs improve multiple primary signals by more than 5%; the 5-epoch result is probably premature. |
| memetracker | MINDS | 5-50 | undertraining_likely | Later epochs improve multiple primary signals by more than 5%; the 5-epoch result is probably premature. |
| memetracker | Ours | 5-50 | undertraining_likely | Later epochs improve multiple primary signals by more than 5%; the 5-epoch result is probably premature. |
| twitter | MINDS | 5-50 | undertraining_likely | Later epochs improve multiple primary signals by more than 5%; the 5-epoch result is probably premature. |
| twitter | Ours | 5-50 | undertraining_likely | Later epochs improve multiple primary signals by more than 5%; the 5-epoch result is probably premature. |

## Reporting Rule

- If `undertraining_likely` appears, the corresponding 5-epoch result must be treated as premature.
- If `plateau_or_mixed` appears, inspect candidate coverage, loss conflict, model capacity, and protocol mismatch before increasing epochs further.
- SOTA comparison should only resume after this report has at least one stable multi-seed epoch setting.
