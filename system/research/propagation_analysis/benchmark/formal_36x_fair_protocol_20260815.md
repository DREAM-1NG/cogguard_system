# Propagation Analysis Formal Experiment

## Provenance

- Report date: 2026-08-15
- Protocol: 3 datasets x 3 seeds x 200 epochs; 36/36 comparison rows reported with `fair_protocol_passed=true`.
- Tasks: Macro scale/trend prediction and Micro next-hop ranking are reported separately.
- Evidence note: The tables below record the latest formal run supplied for this work. The repository's older `sequence_vs_minds_sample_300c_5ep_3seed.json` remains a preflight artifact and must not be used as the source for this result.

## Macro Scale / Trend Prediction

Values are mean +/- std. Lower is better except Direction Accuracy.

| Dataset | Method | MSLE | MAE | RMSE | MAPE | sMAPE | Dir Acc | Trend MAE | Trend RMSE |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Douban | Ours | 0.0167 +/- 0.0009 | 3.6042 +/- 0.4617 | 19.2117 +/- 4.9725 | 10.2960 +/- 0.1754 | 10.3473 +/- 0.2185 | 1.0000 +/- 0.0000 | 2.1013 +/- 0.2842 | 12.1816 +/- 3.8192 |
| Douban | MINDS | 0.0167 +/- 0.0010 | 3.8764 +/- 0.1122 | 29.9759 +/- 5.9559 | 10.3845 +/- 0.0246 | 10.2819 +/- 0.3019 | 1.0000 +/- 0.0000 | 10.3982 +/- 0.6336 | 39.4992 +/- 1.5628 |
| Douban | CasFT | 0.0142 +/- 0.0004 | 2.1188 +/- 0.3743 | 13.7200 +/- 6.8122 | 8.7397 +/- 0.0166 | 8.6609 +/- 0.0402 | 1.0000 +/- 0.0000 | 1.4181 +/- 0.1990 | 11.0555 +/- 5.8577 |
| Twitter | Ours | 0.0552 +/- 0.0016 | 4.0227 +/- 0.1283 | 11.1680 +/- 0.8526 | 19.0240 +/- 0.2703 | 17.9137 +/- 0.3002 | 1.0000 +/- 0.0000 | 2.2417 +/- 0.0706 | 6.9541 +/- 0.7738 |
| Twitter | MINDS | 0.0598 +/- 0.0013 | 4.0493 +/- 0.1383 | 10.2281 +/- 1.2789 | 19.6906 +/- 0.3043 | 18.4094 +/- 0.0039 | 1.0000 +/- 0.0000 | 11.0168 +/- 2.2359 | 29.1260 +/- 2.6059 |
| Twitter | CasFT | 0.0228 +/- 0.0049 | 1.4641 +/- 0.1070 | 3.2324 +/- 0.4656 | 11.7199 +/- 0.9377 | 11.1717 +/- 0.7012 | 1.0000 +/- 0.0000 | 1.1133 +/- 0.2268 | 4.1349 +/- 1.7114 |
| Memetracker | Ours | 0.0197 +/- 0.0017 | 1.8364 +/- 0.1655 | 5.1827 +/- 0.7765 | 11.8083 +/- 0.2926 | 11.9416 +/- 0.6325 | 1.0000 +/- 0.0000 | 0.9640 +/- 0.0223 | 2.0790 +/- 0.1273 |
| Memetracker | MINDS | 0.0202 +/- 0.0009 | 1.9453 +/- 0.0789 | 6.2588 +/- 0.9979 | 12.5083 +/- 0.3722 | 11.9898 +/- 0.2569 | 1.0000 +/- 0.0000 | 6.0528 +/- 0.4054 | 17.0156 +/- 2.5722 |
| Memetracker | CasFT | 0.0167 +/- 0.0021 | 1.1904 +/- 0.1022 | 2.2420 +/- 0.6553 | 10.5556 +/- 0.4784 | 10.4660 +/- 0.4539 | 1.0000 +/- 0.0000 | 0.7829 +/- 0.0568 | 1.4717 +/- 0.2336 |

## Micro Next-hop Ranking

Candidate Recall is a candidate coverage audit, not ranking quality. The formal ranking comparison uses Hits, MAP, MRR, and NDCG.

| Dataset | Method | Candidate Recall | Hits@10 | Hits@50 | Hits@100 | MAP@10 | MAP@100 | MRR | NDCG@100 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Douban | Ours | 0.9894 +/- 0.0000 | 0.0973 +/- 0.0019 | 0.2090 +/- 0.0038 | 0.2739 +/- 0.0019 | 0.0441 +/- 0.0017 | 0.0500 +/- 0.0015 | 0.0510 +/- 0.0015 | 0.0913 +/- 0.0014 |
| Douban | MINDS | 0.9894 +/- 0.0000 | 0.1009 +/- 0.0006 | 0.2112 +/- 0.0037 | 0.2739 +/- 0.0090 | 0.0460 +/- 0.0020 | 0.0519 +/- 0.0021 | 0.0529 +/- 0.0021 | 0.0931 +/- 0.0030 |
| Douban | FOREST | 0.9894 +/- 0.0000 | 0.0805 +/- 0.0021 | 0.1850 +/- 0.0008 | 0.2489 +/- 0.0040 | 0.0376 +/- 0.0008 | 0.0433 +/- 0.0008 | 0.0444 +/- 0.0008 | 0.0808 +/- 0.0004 |
| Twitter | Ours | 0.9961 +/- 0.0000 | 0.1393 +/- 0.0014 | 0.1831 +/- 0.0053 | 0.2147 +/- 0.0069 | 0.1027 +/- 0.0039 | 0.1050 +/- 0.0038 | 0.1057 +/- 0.0038 | 0.1259 +/- 0.0026 |
| Twitter | MINDS | 0.9961 +/- 0.0000 | 0.1399 +/- 0.0043 | 0.1918 +/- 0.0030 | 0.2215 +/- 0.0055 | 0.1028 +/- 0.0033 | 0.1055 +/- 0.0030 | 0.1062 +/- 0.0031 | 0.1277 +/- 0.0018 |
| Twitter | FOREST | 0.9961 +/- 0.0000 | 0.1099 +/- 0.0032 | 0.1357 +/- 0.0024 | 0.1554 +/- 0.0043 | 0.0818 +/- 0.0012 | 0.0833 +/- 0.0010 | 0.0839 +/- 0.0010 | 0.0973 +/- 0.0008 |
| Memetracker | Ours | 1.0000 +/- 0.0000 | 0.2032 +/- 0.0070 | 0.3761 +/- 0.0109 | 0.4646 +/- 0.0133 | 0.0974 +/- 0.0038 | 0.1067 +/- 0.0037 | 0.1080 +/- 0.0036 | 0.1746 +/- 0.0049 |
| Memetracker | MINDS | 1.0000 +/- 0.0000 | 0.2071 +/- 0.0086 | 0.3827 +/- 0.0057 | 0.4770 +/- 0.0013 | 0.0951 +/- 0.0028 | 0.1045 +/- 0.0026 | 0.1057 +/- 0.0026 | 0.1750 +/- 0.0026 |
| Memetracker | FOREST | 1.0000 +/- 0.0000 | 0.1659 +/- 0.0067 | 0.3260 +/- 0.0118 | 0.4222 +/- 0.0116 | 0.0761 +/- 0.0036 | 0.0848 +/- 0.0039 | 0.0862 +/- 0.0039 | 0.1476 +/- 0.0049 |

## Supported Claim

Under the reported fair protocol, Ours improves macro trend prediction over MINDS on all three datasets and outperforms FOREST on the reported micro ranking metrics. It is not a universal SOTA result: CasFT remains strongest on most macro metrics, and MINDS is slightly better on many Douban/Twitter micro metrics. The correct system claim is unified macro/micro modeling with substantially better trend modeling and near-MINDS next-hop ranking.

## Decision Log For Runtime Limits

### Open-world user candidates

Resolving participating users and their observed graph neighbors can improve candidate recall, but it is not by itself an open-world identity solution. The next implementation should separate:

1. Candidate generation from users observed before the cutoff and their time-aware one- or two-hop neighbors.
2. Identity resolution using platform account IDs and explicit cross-platform evidence; names alone are not sufficient.
3. An unknown/new-user bucket for candidates that cannot be mapped to a stable identity.
4. Ranking and calibration evaluated with candidate recall, known-user reactivation, and unknown-user detection reported separately.

Until that contract exists, the current endpoint remains a closed-world reactivation ranking endpoint.

### Wall-clock horizons

The current checkpoint predicts normalized trajectory steps. `prediction_horizon=24` therefore cannot be interpreted as 24 hours and is rejected by the public API. Supporting wall-clock horizons requires retraining or adapting the target representation with explicit time bins, horizon metadata, and time-based evaluation. The UI should expose normalized forecast checkpoints until then.

### `unavailable` and `abstain`

- `unavailable` means the service cannot produce a result because a required checkpoint, dependency, minimum data condition, legal candidate set, or inference execution is missing.
- `abstain` means the service intentionally makes no user-level or future-fact claim, for example when identity mapping is ambiguous or evidence is insufficient.

Both are structured outcomes, not zeros or hidden fallbacks. The response should preserve a reason code, observed cutoff, candidate counts, mapping status, and calibration status.

### Prediction intervals and posterior models

A posterior or predictive uncertainty layer can be added to the existing model, but it should not be a direct UI-only patch. The recommended order is:

1. Add a held-out temporal calibration split and post-hoc conformal residual intervals as the smallest change.
2. If needed, add a heteroscedastic likelihood, Bayesian last layer, deep ensemble, or MC-dropout posterior for macro targets.
3. For micro ranking, add score/probability calibration or a ranking posterior separately; macro intervals do not automatically calibrate user ranking.
4. Version the checkpoint contract with `posterior_artifact`, `calibration_status`, interval coverage, and horizon metadata.

Acceptance checks should include interval coverage, interval width, CRPS or NLL, calibration reliability, candidate recall, and temporal leakage audits. Without a calibration artifact, the service must continue returning `intervals=None`.
