# Propagation Fair Learned Matrix

- status: `ok`
- protocol_id: `propagation_fair_sequence_forestsplit_v1`
- datasets: `douban, twitter, memetracker`
- seeds: `42, 43, 44`
- models: `Ours, MINDS`

Rows are comparable only when they use the same FOREST train/valid/test files, the same observation ratios, the same train/eval cascade caps, the same epochs/batch/hidden/sequence configuration, the same candidate policy, and the same metric implementation.

This file is the fair learned matrix. The earlier stable SOTA matrix remains an engineering run record and must not be used as a direct learned-model improvement verdict.

## Protocol Audit

| item | value |
|---|---:|
| passed | `True` |
| row_count | `18` |
| fair_ok_count | `18` |
| requested_count | `18` |

## Macro Metrics

| dataset | model | msle mean+/-std | mae mean+/-std | rmse mean+/-std | mape_percent mean+/-std | smape_percent mean+/-std | direction_accuracy mean+/-std | trend_mae mean+/-std | trend_rmse mean+/-std | macro_micro_consistency mean+/-std |
|---|---|---|---|---|---|---|---|---|---|---|
| douban | MINDS | 0.126320+/-0.026311 | 6.639837+/-1.242121 | 20.207488+/-4.176473 | 20.484659+/-4.522214 | 18.428762+/-2.964274 | 1.000000+/-0.000000 | 323.660258+/-33.861182 | 423.721813+/-46.285724 | 0.002137+/-0.000374 |
| douban | Ours | 0.102332+/-0.012360 | 5.637823+/-0.933980 | 15.226212+/-2.528579 | 15.877647+/-0.745319 | 16.447325+/-1.860124 | 1.000000+/-0.000000 | 225.676942+/-28.871464 | 292.808882+/-41.834814 | 0.002662+/-0.000507 |
| memetracker | MINDS | 0.150005+/-0.012514 | 2.192242+/-0.137363 | 3.969897+/-0.034625 | 22.884319+/-1.766329 | 19.572417+/-1.196179 | 1.000000+/-0.000000 | 63.416261+/-1.898438 | 64.353568+/-1.896013 | 0.005686+/-0.002415 |
| memetracker | Ours | 0.126113+/-0.027498 | 2.375662+/-0.121170 | 4.515848+/-0.443574 | 19.176890+/-2.987031 | 18.140371+/-1.124778 | 1.000000+/-0.000000 | 53.456293+/-3.380490 | 54.350538+/-3.405783 | 0.007400+/-0.003878 |
| twitter | MINDS | 0.134299+/-0.022504 | 4.373990+/-0.491066 | 9.493839+/-1.426582 | 18.949329+/-2.439810 | 18.157196+/-2.656307 | 1.000000+/-0.000000 | 245.274347+/-17.017614 | 291.560432+/-18.948533 | 0.002042+/-0.000389 |
| twitter | Ours | 0.124102+/-0.028370 | 5.244932+/-1.358282 | 11.590599+/-3.714942 | 17.563860+/-1.930301 | 17.830412+/-2.393038 | 1.000000+/-0.000000 | 187.908502+/-25.813916 | 221.550273+/-30.248748 | 0.002205+/-0.000428 |

## Micro Metrics

| dataset | model | candidate_recall_full mean+/-std | hits@10 mean+/-std | hits@50 mean+/-std | hits@100 mean+/-std | map@10 mean+/-std | map@50 mean+/-std | map@100 mean+/-std | mrr mean+/-std | ndcg@10 mean+/-std | ndcg@50 mean+/-std | ndcg@100 mean+/-std |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| douban | MINDS | 0.923333+/-0.000000 | 0.007778+/-0.005666 | 0.024444+/-0.005666 | 0.051111+/-0.005666 | 0.003537+/-0.002506 | 0.004115+/-0.002497 | 0.004432+/-0.002496 | 0.005548+/-0.002487 | 0.004546+/-0.003243 | 0.007923+/-0.003229 | 0.012077+/-0.003227 |
| douban | Ours | 0.923333+/-0.000000 | 0.007778+/-0.004157 | 0.024444+/-0.004157 | 0.051111+/-0.004157 | 0.002926+/-0.001774 | 0.003504+/-0.001768 | 0.003821+/-0.001768 | 0.004939+/-0.001766 | 0.004087+/-0.001979 | 0.007464+/-0.001968 | 0.011618+/-0.001967 |
| memetracker | MINDS | 0.836667+/-0.000000 | 0.028889+/-0.010999 | 0.048889+/-0.010999 | 0.105556+/-0.010999 | 0.008926+/-0.005279 | 0.009655+/-0.005279 | 0.010398+/-0.005280 | 0.012402+/-0.005211 | 0.013580+/-0.006675 | 0.017661+/-0.006677 | 0.026685+/-0.006680 |
| memetracker | Ours | 0.836667+/-0.000000 | 0.028889+/-0.010999 | 0.048889+/-0.010999 | 0.105556+/-0.010999 | 0.008889+/-0.005362 | 0.009618+/-0.005364 | 0.010362+/-0.005365 | 0.012362+/-0.005289 | 0.013552+/-0.006751 | 0.017634+/-0.006754 | 0.026660+/-0.006757 |
| twitter | MINDS | 0.923333+/-0.000000 | 0.005556+/-0.001571 | 0.012222+/-0.001571 | 0.028889+/-0.001571 | 0.001389+/-0.000680 | 0.001608+/-0.000680 | 0.001826+/-0.000680 | 0.002670+/-0.000679 | 0.002367+/-0.000877 | 0.003706+/-0.000877 | 0.006361+/-0.000877 |
| twitter | Ours | 0.923333+/-0.000000 | 0.005556+/-0.001571 | 0.012222+/-0.001571 | 0.028889+/-0.001571 | 0.001056+/-0.000360 | 0.001274+/-0.000360 | 0.001493+/-0.000360 | 0.002337+/-0.000354 | 0.002096+/-0.000645 | 0.003435+/-0.000645 | 0.006089+/-0.000645 |

## Excluded / Separate-Track Methods

| model | status | reason | next step |
|---|---|---|---|
| Original MINDS public code | excluded_from_fair_verdict | The current adapter calls SplitData(..., train_rate=0.8, valid_rate=0.1), so its split and all-position sequence metrics do not match the FOREST split + obs-ratio window protocol. | Add a native MINDS fair adapter that consumes explicit train/valid/test cascades and evaluates prefix windows. |
| DyGFormer/DyGLib | excluded_from_fair_verdict | The current temporal-graph adapter can run upstream training, but event-level Top-K metrics are still computed by protocol_next_hop_baseline(), a shared transition/popularity proxy rather than learned scores. | Extract learned temporal-node scores at each prefix window and rank the same train-user candidate universe. |
| TGN | excluded_from_fair_verdict | The current TGN adapter exports temporal edges and launches self-supervised training, but does not feed learned TGN scores into the macro/micro event-window evaluator. | Add a TGN prefix-state scorer and use the shared Top-K metric implementation. |
| CasFT | macro_only_pending | CasFT is a macro future-trend/size model and has no next-user Top-K head in the current protocol. | Evaluate CasFT in a separate macro-only table using the same FOREST split and observed prefix windows. |
| FOREST | pending_fair_adapter | The current adapter targets public-code smoke/full-run behavior, not the shared prefix-window sampled-softmax metric implementation used here. | Wrap FOREST logits/rollouts into the shared prefix-window evaluator before including it in this verdict. |
