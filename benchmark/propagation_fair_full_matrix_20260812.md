# Propagation Fair Full Matrix

- status: `ok`
- protocol_id: `cogguard.propagation.fair_split_vocab_prefix.v2`
- epochs: `200`
- datasets: `douban, twitter, memetracker`
- seeds: `42, 43, 44`
- obs_ratios: `0.1, 0.3, 0.5`

Formal comparison uses one native split loader, one train-only real-user vocabulary, one candidate universe, one prefix-window evaluator, and one metric implementation.

## Protocol Audit

| item | value |
|---|---:|
| passed | `True` |
| requested_count | `36` |
| row_count | `36` |
| fair_ok_count | `36` |

## Macro Size / Trend

| dataset | method | msle mean+/-std | mae mean+/-std | rmse mean+/-std | mape_percent mean+/-std | smape_percent mean+/-std | direction_accuracy mean+/-std | trend_mae mean+/-std | trend_rmse mean+/-std |
|---|---|---|---|---|---|---|---|---|---|
| douban | CasFT | 0.014162+/-0.000373 | 2.118827+/-0.374298 | 13.719996+/-6.812175 | 8.739689+/-0.016610 | 8.660868+/-0.040234 | 1.000000+/-0.000000 | 1.418098+/-0.199012 | 11.055500+/-5.857680 |
| douban | MINDS | 0.016655+/-0.000973 | 3.876412+/-0.112210 | 29.975915+/-5.955865 | 10.384465+/-0.024581 | 10.281860+/-0.301910 | 1.000000+/-0.000000 | 10.398238+/-0.633578 | 39.499155+/-1.562759 |
| douban | Ours | 0.016690+/-0.000885 | 3.604173+/-0.461696 | 19.211712+/-4.972452 | 10.295961+/-0.175357 | 10.347268+/-0.218528 | 1.000000+/-0.000000 | 2.101344+/-0.284223 | 12.181639+/-3.819155 |
| memetracker | CasFT | 0.016716+/-0.002085 | 1.190445+/-0.102191 | 2.242039+/-0.655324 | 10.555563+/-0.478366 | 10.465975+/-0.453905 | 1.000000+/-0.000000 | 0.782899+/-0.056837 | 1.471664+/-0.233554 |
| memetracker | MINDS | 0.020208+/-0.000851 | 1.945256+/-0.078899 | 6.258848+/-0.997914 | 12.508297+/-0.372243 | 11.989763+/-0.256912 | 1.000000+/-0.000000 | 6.052818+/-0.405394 | 17.015620+/-2.572180 |
| memetracker | Ours | 0.019708+/-0.001747 | 1.836394+/-0.165517 | 5.182673+/-0.776498 | 11.808267+/-0.292643 | 11.941591+/-0.632547 | 1.000000+/-0.000000 | 0.963993+/-0.022282 | 2.078961+/-0.127256 |
| twitter | CasFT | 0.022753+/-0.004892 | 1.464057+/-0.107039 | 3.232379+/-0.465575 | 11.719946+/-0.937739 | 11.171739+/-0.701156 | 1.000000+/-0.000000 | 1.113301+/-0.226766 | 4.134887+/-1.711398 |
| twitter | MINDS | 0.059786+/-0.001301 | 4.049287+/-0.138284 | 10.228127+/-1.278926 | 19.690624+/-0.304263 | 18.409371+/-0.003931 | 1.000000+/-0.000000 | 11.016760+/-2.235943 | 29.125954+/-2.605901 |
| twitter | Ours | 0.055195+/-0.001648 | 4.022747+/-0.128309 | 11.167996+/-0.852576 | 19.023986+/-0.270320 | 17.913680+/-0.300204 | 1.000000+/-0.000000 | 2.241669+/-0.070568 | 6.954138+/-0.773803 |

## Micro Next-Hop

| dataset | method | candidate_recall_full mean+/-std | hits@10 mean+/-std | hits@50 mean+/-std | hits@100 mean+/-std | map@10 mean+/-std | map@50 mean+/-std | map@100 mean+/-std | mrr mean+/-std | ndcg@10 mean+/-std | ndcg@50 mean+/-std | ndcg@100 mean+/-std |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| douban | FOREST | 0.989368+/-0.000000 | 0.080489+/-0.002070 | 0.184998+/-0.000830 | 0.248946+/-0.003967 | 0.037633+/-0.000773 | 0.042420+/-0.000833 | 0.043315+/-0.000773 | 0.044371+/-0.000791 | 0.047622+/-0.000792 | 0.070468+/-0.000787 | 0.080791+/-0.000442 |
| douban | MINDS | 0.989368+/-0.000000 | 0.100927+/-0.000649 | 0.211231+/-0.003671 | 0.273915+/-0.009022 | 0.045984+/-0.001988 | 0.051049+/-0.002075 | 0.051944+/-0.002144 | 0.052896+/-0.002110 | 0.058774+/-0.001590 | 0.082914+/-0.002205 | 0.093080+/-0.002996 |
| douban | Ours | 0.989368+/-0.000000 | 0.097345+/-0.001948 | 0.209018+/-0.003760 | 0.273915+/-0.001937 | 0.044058+/-0.001726 | 0.049094+/-0.001434 | 0.050009+/-0.001483 | 0.050969+/-0.001505 | 0.056463+/-0.001718 | 0.080760+/-0.001097 | 0.091254+/-0.001367 |
| memetracker | FOREST | 1.000000+/-0.000000 | 0.165877+/-0.006664 | 0.326049+/-0.011799 | 0.422152+/-0.011620 | 0.076130+/-0.003617 | 0.083440+/-0.003904 | 0.084803+/-0.003896 | 0.086156+/-0.003886 | 0.097082+/-0.004242 | 0.132047+/-0.005438 | 0.147608+/-0.005399 |
| memetracker | MINDS | 1.000000+/-0.000000 | 0.207127+/-0.008632 | 0.382745+/-0.005665 | 0.477005+/-0.001260 | 0.095074+/-0.002841 | 0.103143+/-0.002652 | 0.104485+/-0.002584 | 0.105728+/-0.002597 | 0.121301+/-0.004216 | 0.159735+/-0.003421 | 0.175012+/-0.002617 |
| memetracker | Ours | 1.000000+/-0.000000 | 0.203177+/-0.007014 | 0.376075+/-0.010857 | 0.464631+/-0.013296 | 0.097393+/-0.003797 | 0.105438+/-0.003638 | 0.106695+/-0.003656 | 0.108007+/-0.003621 | 0.122262+/-0.004537 | 0.160247+/-0.004648 | 0.174590+/-0.004927 |
| twitter | FOREST | 0.996146+/-0.000000 | 0.109929+/-0.003191 | 0.135719+/-0.002412 | 0.155384+/-0.004349 | 0.081794+/-0.001221 | 0.083015+/-0.001050 | 0.083281+/-0.001046 | 0.083947+/-0.001014 | 0.088421+/-0.001449 | 0.094115+/-0.000554 | 0.097264+/-0.000831 |
| twitter | MINDS | 0.996146+/-0.000000 | 0.139910+/-0.004349 | 0.191812+/-0.002990 | 0.221470+/-0.005528 | 0.102777+/-0.003295 | 0.105116+/-0.003091 | 0.105540+/-0.003019 | 0.106235+/-0.003065 | 0.111552+/-0.003152 | 0.122851+/-0.002500 | 0.127663+/-0.001754 |
| twitter | Ours | 0.996146+/-0.000000 | 0.139265+/-0.001368 | 0.183108+/-0.005258 | 0.214700+/-0.006884 | 0.102697+/-0.003878 | 0.104504+/-0.003783 | 0.104966+/-0.003751 | 0.105675+/-0.003757 | 0.111458+/-0.003174 | 0.120747+/-0.002989 | 0.125897+/-0.002610 |

## Excluded / Separate Track

| model | status | reason | next step |
|---|---|---|---|
| TGN | excluded_this_round | Native task is temporal link prediction; current code does not export learned cascade-prefix user rankings. | Run in a separate Temporal Link table or add a prefix-state scorer before Micro comparison. |
| DyGFormer | excluded_this_round | Native task is temporal link prediction; previous event-level Top-K used proxy candidate ordering. | Export learned temporal scores over the shared train-user candidate universe before comparison. |
| Original MINDS public runner | not_formal_table_source | The current public runner re-splits data and builds graph structures outside the shared protocol. | Keep only as reproduction evidence until a native explicit-split adapter is completed. |
| Original CasFT public runner | not_formal_table_source | The staged exporter/preprocessor can merge or re-split cascades, so it is not yet split-preserving. | Use the same-protocol macro adapter now; build split-preserving CasFT preprocessing later. |
