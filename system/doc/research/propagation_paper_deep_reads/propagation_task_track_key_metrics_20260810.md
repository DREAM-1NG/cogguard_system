# Propagation Task-Track Key Metrics 2026-08-10

- fair_protocol_passed: `True`
- fair_rows: `18`
- principle: only methods with the same input/output/supervision/metric are placed in the same verdict table.

## Track 1: Macro Fair Scale/Trend

Comparable methods: Ours vs MINDS under the same FOREST split, obs-ratios, caps, epochs, candidate universe and metric implementation.

| Dataset | Method | N | Seeds | MSLE | MAE | Trend MAE | Direction Acc |
| --- | --- | --- | --- | --- | --- | --- | --- |
| douban | MINDS | 3 | 42,43,44 | 0.1263+/-0.0263 | 6.6398+/-1.2421 | 323.6603+/-33.8612 | 1.0000+/-0.0000 |
| douban | Ours | 3 | 42,43,44 | 0.1023+/-0.0124 | 5.6378+/-0.9340 | 225.6769+/-28.8715 | 1.0000+/-0.0000 |
| memetracker | MINDS | 3 | 42,43,44 | 0.1500+/-0.0125 | 2.1922+/-0.1374 | 63.4163+/-1.8984 | 1.0000+/-0.0000 |
| memetracker | Ours | 3 | 42,43,44 | 0.1261+/-0.0275 | 2.3757+/-0.1212 | 53.4563+/-3.3805 | 1.0000+/-0.0000 |
| twitter | MINDS | 3 | 42,43,44 | 0.1343+/-0.0225 | 4.3740+/-0.4911 | 245.2743+/-17.0176 | 1.0000+/-0.0000 |
| twitter | Ours | 3 | 42,43,44 | 0.1241+/-0.0284 | 5.2449+/-1.3583 | 187.9085+/-25.8139 | 1.0000+/-0.0000 |

## Track 2: Micro Fair Next-Hop

Comparable methods: Ours vs MINDS under the same prefix-window next-user ranking protocol.

| Dataset | Method | N | Seeds | Candidate Recall | Hits@100 | MRR | NDCG@100 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| douban | MINDS | 3 | 42,43,44 | 0.9233+/-0.0000 | 0.0511+/-0.0057 | 0.0055+/-0.0025 | 0.0121+/-0.0032 |
| douban | Ours | 3 | 42,43,44 | 0.9233+/-0.0000 | 0.0511+/-0.0042 | 0.0049+/-0.0018 | 0.0116+/-0.0020 |
| memetracker | MINDS | 3 | 42,43,44 | 0.8367+/-0.0000 | 0.1056+/-0.0110 | 0.0124+/-0.0052 | 0.0267+/-0.0067 |
| memetracker | Ours | 3 | 42,43,44 | 0.8367+/-0.0000 | 0.1056+/-0.0110 | 0.0124+/-0.0053 | 0.0267+/-0.0068 |
| twitter | MINDS | 3 | 42,43,44 | 0.9233+/-0.0000 | 0.0289+/-0.0016 | 0.0027+/-0.0007 | 0.0064+/-0.0009 |
| twitter | Ours | 3 | 42,43,44 | 0.9233+/-0.0000 | 0.0289+/-0.0016 | 0.0023+/-0.0004 | 0.0061+/-0.0006 |

## Track 3: Macro-Only External Baseline

CasFT is reported separately because it is a scale/trend model and does not output next-hop users.

| Dataset | Method | N | Seeds | MSLE | MAE | MAPE | sMAPE |
| --- | --- | --- | --- | --- | --- | --- | --- |
| douban | CasFT | 3 | 42,43,44 | 13.6440+/-0.4036 | 3.0043+/-0.0486 | 0.4999+/-0.0051 | 0.4999+/-0.0051 |
| memetracker | CasFT | 3 | 42,43,44 | 9.6215+/-0.2857 | 2.4730+/-0.0246 | 0.4806+/-0.0024 | 0.4806+/-0.0024 |
| twitter | CasFT | 3 | 42,43,44 | 10.7558+/-0.5099 | 2.9240+/-0.0872 | 0.5089+/-0.0156 | 0.5089+/-0.0156 |

## Track 4: Native Temporal Link Prediction

TGN/DyGFormer are link-prediction methods. Their native AP is not equivalent to cascade next-hop Top-K.

| Dataset | Method | Status | Test AP | New-node Test AP | Train Loss | Note |
| --- | --- | --- | --- | --- | --- | --- |
| douban | TGN | ok | 0.8267 | 0.6390 | 1.3563 | Native temporal link prediction AP from upstream TGN result pickle; not a cascade next-hop Top-K metric. |
| twitter | TGN | ok | 0.5735 | 0.5267 | 1.3813 | Native temporal link prediction AP from upstream TGN result pickle; not a cascade next-hop Top-K metric. |
| memetracker | TGN | ok | 0.6569 | 0.6263 | 1.3744 | Native temporal link prediction AP from upstream TGN result pickle; not a cascade next-hop Top-K metric. |
| douban | DyGFormer/DyGLib | training_completed_metric_not_structured | - | - | - | The stable run logs show upstream training completed, but AP/AUC were not captured into a structured artifact. |
| memetracker | DyGFormer/DyGLib | training_completed_metric_not_structured | - | - | - | The stable run logs show upstream training completed, but AP/AUC were not captured into a structured artifact. |
| twitter | DyGFormer/DyGLib | training_completed_metric_not_structured | - | - | - | The stable run logs show upstream training completed, but AP/AUC were not captured into a structured artifact. |

## Track 5: Adapted Next-Hop From Temporal Models

This track is intentionally pending until learned edge scores are used to rank event-level candidate users.

| Dataset | Method | Status | Upstream Training | Top-K Score Source | Learned Top-K Available |
| --- | --- | --- | --- | --- | --- |
| douban | DyGFormer/DyGLib | ok | completed | transition_popularity_proxy_not_learned | False |
| douban | TGN | ok | completed | transition_popularity_proxy_not_learned | False |
| twitter | DyGFormer/DyGLib | ok | completed | transition_popularity_proxy_not_learned | False |
| twitter | TGN | ok | completed | transition_popularity_proxy_not_learned | False |
| memetracker | DyGFormer/DyGLib | ok | completed | transition_popularity_proxy_not_learned | False |
| memetracker | TGN | ok | completed | transition_popularity_proxy_not_learned | False |

## Pending / Not In Verdict

| Dataset | Seed | Status | Hits@100 | Track Status | Note |
| --- | --- | --- | --- | --- | --- |
| douban | 42 | ok | 0.0000 | pending_fair_adapter | FOREST public-code adapter ran, but macro values are missing/non-finite under the current local capped run. |
| douban | 43 | ok | 0.0000 | pending_fair_adapter | FOREST public-code adapter ran, but macro values are missing/non-finite under the current local capped run. |
| douban | 44 | ok | 0.0084 | pending_fair_adapter | FOREST public-code adapter ran, but macro values are missing/non-finite under the current local capped run. |
| twitter | 42 | ok | 0.0199 | pending_fair_adapter | FOREST public-code adapter ran, but macro values are missing/non-finite under the current local capped run. |
| twitter | 43 | ok | 0.0050 | pending_fair_adapter | FOREST public-code adapter ran, but macro values are missing/non-finite under the current local capped run. |
| twitter | 44 | ok | 0.0050 | pending_fair_adapter | FOREST public-code adapter ran, but macro values are missing/non-finite under the current local capped run. |
| memetracker | 42 | ok | 0.0217 | pending_fair_adapter | FOREST public-code adapter ran, but macro values are missing/non-finite under the current local capped run. |
| memetracker | 43 | ok | 0.0362 | pending_fair_adapter | FOREST public-code adapter ran, but macro values are missing/non-finite under the current local capped run. |
| memetracker | 44 | ok | 0.0362 | pending_fair_adapter | FOREST public-code adapter ran, but macro values are missing/non-finite under the current local capped run. |

## Key Interpretation

- Macro fair track: Ours improves MSLE and trend MAE against MINDS on all three datasets, but MAE is worse on Twitter and Memetracker.
- Micro fair track: Ours and MINDS have almost identical Hits@100; Ours is slightly lower on MRR/NDCG, so next-hop improvement is not supported yet.
- CasFT is useful for macro-only discussion but should not be mixed with macro/micro joint verdicts until its prefix-window protocol is aligned.
- TGN/DyGFormer need a learned-score adapter before they can enter the next-hop Top-K table.
