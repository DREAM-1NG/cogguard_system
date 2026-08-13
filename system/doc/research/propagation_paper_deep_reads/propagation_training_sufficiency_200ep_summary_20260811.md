# Propagation Training Sufficiency 200-Epoch Summary

- generated_at: `2026-08-12T02:03:53`
- queue_status: `running`
- current_step: `sequence_joint_200ep_h64_seq200_fullsource_3seed`
- summary_status: `partial`
- training_epoch: `200` for all configured trainable tracks.
- boundary: temporal graph AP/AUC is reported separately from cascade next-hop Top-K.

## Source Completion

| Source | State | Payload Status | Rows | Expected | Last Write | Path |
| --- | --- | --- | --- | --- | --- | --- |
| queue | running | running | 0 | - | 2026-08-11T22:31:13 | G:/CISCN/CogGuard/subsystems/cogguard_dev/benchmark/propagation_training_sufficiency_200ep_full_20260811_status.json |
| sequence_sampled | complete | ok | 18 | 18 | 2026-08-11T09:48:00 | G:/CISCN/CogGuard/subsystems/cogguard_dev/benchmark/propagation_training_sufficiency_sequence_200ep_h64_seq200_300c_3seed_20260811.json |
| sequence_full | missing | - | 0 | 18 | - | G:/CISCN/CogGuard/subsystems/cogguard_dev/benchmark/propagation_training_sufficiency_sequence_200ep_h64_seq200_fullsource_3seed_20260811.json |
| public_baselines | missing | - | 0 | 27 | - | G:/CISCN/CogGuard/subsystems/cogguard_dev/benchmark/propagation_training_sufficiency_public_baselines_200ep_20260811.json |
| temporal_native | missing | - | 0 | 6 | - | G:/CISCN/CogGuard/subsystems/cogguard_dev/benchmark/propagation_training_sufficiency_temporal_graph_200ep_20260811.json |

## Same-Protocol Sampled Track: Macro

| Dataset | Method | Rows | OK | Seeds | Epochs | MSLE | MAE | Trend MAE | Direction Acc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| douban | MINDS | 3 | 3 | 42,43,44 | 200 | 0.0602 +/- 0.0110 | 2.6610 +/- 0.1454 | 240.7618 +/- 8.4873 | 1.0000 +/- 0.0000 |
| douban | Ours | 3 | 3 | 42,43,44 | 200 | 0.0813 +/- 0.0059 | 5.3475 +/- 0.2306 | 188.1981 +/- 9.6764 | 1.0000 +/- 0.0000 |
| memetracker | MINDS | 3 | 3 | 42,43,44 | 200 | 0.0914 +/- 0.0037 | 1.6211 +/- 0.1017 | 66.9913 +/- 2.7139 | 1.0000 +/- 0.0000 |
| memetracker | Ours | 3 | 3 | 42,43,44 | 200 | 0.1107 +/- 0.0113 | 2.0762 +/- 0.1231 | 55.5994 +/- 1.4837 | 1.0000 +/- 0.0000 |
| twitter | MINDS | 3 | 3 | 42,43,44 | 200 | 0.1086 +/- 0.0060 | 2.7380 +/- 0.1516 | 218.8248 +/- 3.3720 | 1.0000 +/- 0.0000 |
| twitter | Ours | 3 | 3 | 42,43,44 | 200 | 0.1510 +/- 0.0235 | 5.9517 +/- 0.5806 | 183.2486 +/- 9.7662 | 1.0000 +/- 0.0000 |

## Same-Protocol Sampled Track: Micro

| Dataset | Method | Rows | OK | Seeds | Epochs | Candidate Recall | Hits@100 | MRR | NDCG@100 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| douban | MINDS | 3 | 3 | 42,43,44 | 200 | 0.9233 +/- 0.0000 | 0.0522 +/- 0.0042 | 0.0055 +/- 0.0005 | 0.0124 +/- 0.0011 |
| douban | Ours | 3 | 3 | 42,43,44 | 200 | 0.9233 +/- 0.0000 | 0.0578 +/- 0.0057 | 0.0084 +/- 0.0020 | 0.0159 +/- 0.0025 |
| memetracker | MINDS | 3 | 3 | 42,43,44 | 200 | 0.8367 +/- 0.0000 | 0.1067 +/- 0.0072 | 0.0153 +/- 0.0074 | 0.0294 +/- 0.0073 |
| memetracker | Ours | 3 | 3 | 42,43,44 | 200 | 0.8367 +/- 0.0000 | 0.1122 +/- 0.0063 | 0.0196 +/- 0.0033 | 0.0342 +/- 0.0035 |
| twitter | MINDS | 3 | 3 | 42,43,44 | 200 | 0.9233 +/- 0.0000 | 0.0400 +/- 0.0027 | 0.0095 +/- 0.0032 | 0.0142 +/- 0.0031 |
| twitter | Ours | 3 | 3 | 42,43,44 | 200 | 0.9233 +/- 0.0000 | 0.0378 +/- 0.0063 | 0.0064 +/- 0.0021 | 0.0114 +/- 0.0031 |

## Same-Protocol Full-Split Track: Macro

| Dataset | Method | Rows | OK | Seeds | Epochs | MSLE | MAE | Trend MAE | Direction Acc |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - | - | - | - |

## Same-Protocol Full-Split Track: Micro

| Dataset | Method | Rows | OK | Seeds | Epochs | Candidate Recall | Hits@100 | MRR | NDCG@100 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - | - | - | - |

## Public-Code Baselines: Macro/Micro Fields

| Dataset | Method | Rows | OK | Seeds | Epochs | MSLE | MAE | Trend MAE | Hits@100 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - | - | - | - |

## Public-Code Baselines: Micro Fields

| Dataset | Method | Rows | OK | Seeds | Epochs | Hits@10 | Hits@50 | Hits@100 | MRR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - | - | - | - |

## Native Temporal Graph Track

| Dataset | Method | Rows | OK | Seeds | Epochs | Test AP | Test AUC | New-node Test AP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| - | - | - | - | - | - | - | - | - |

## Interpretation Guardrails

- Do not claim final SOTA comparison until `summary_status` becomes `complete` and every source is `complete`.
- Ours and MINDS are directly comparable in the same-protocol sampled/full tracks.
- FOREST/CasFT public-code rows are baseline evidence, but only metrics actually emitted by those adapters are comparable.
- TGN/DyGFormer native AP/AUC remains a separate temporal-link-prediction track unless a learned event-level scorer is wired.
