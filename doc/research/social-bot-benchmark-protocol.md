# Social-Bot Benchmark Protocol

## Purpose

This protocol defines the only datasets that may support CogGuard social-bot
detector comparisons, model selection, or deployment claims. A benchmark result
is always scoped to its dataset, split, input coverage, and inference setting.
It is not evidence that an English Twitter detector can classify an arbitrary
Chinese account.

## Formal Benchmark Set

| Role | Dataset | Protocol | Allowed claim |
| --- | --- | --- | --- |
| Primary graph benchmark | TwiBot-20 | Official fixed graph and split; use the verified transductive runtime until the full graph-preparation inputs are available locally. | Reproduction on the deployed TwiBot-20 nodes only. |
| Large-scale follow-up | TwiBot-22 | Add after its complete licensed corpus and official split are locally registered. | Separate graph benchmark report only. |
| Cross-corpus adaptation | Cresci-2015 | Train and evaluate independently with its official subcorpus labels and archive provenance. | Dataset-specific adaptation result. |
| Cross-corpus adaptation | Cresci-2017 | Train and evaluate independently with its official subcorpus labels and archive provenance. | Dataset-specific adaptation result. |
| Temporal generalization complement | Midterm-2018 | Train and evaluate independently with its official human/bot labels. | Dataset-specific adaptation result. |

`system/artifacts/social_bot_detection/nlpcc_twibot20_seed3` is the current
TwiBot-20 reference runtime. It is hash-verified, fixed-graph, and
transductive. It may query only its 11,826 registered nodes and can never be
used as the online Chinese account-model pointer.

## Excluded Source

The local Botection corpus is a historical Weibo transfer experiment with text
and labels but no complete profile or social-relation coverage. It is retained
only for provenance and regression of its explicit legacy loader. It must not
be selected by the public dataset dispatcher or CLI, used for model selection,
compared as a formal benchmark, or used to justify online deployment.

## Reporting Rules

1. Train, validation, and test results are reported separately for every
   dataset. Do not pool datasets or account identities.
2. Report macro-F1, AUPRC, calibration, and the exact split/provenance hash.
   For graph datasets, report graph availability and relation coverage.
3. Compare BotRHG with a character TF-IDF baseline and an appropriate
   graph-aware baseline where graph inputs exist. Never claim superiority from
   a single result or from a result below the matched TF-IDF baseline.
4. Chinese online deployment requires a separately governed Chinese bundle,
   approved Chinese labels, leakage-safe evaluation, and an Active Pointer. No
   public English benchmark directly satisfies that condition.

## Sources

- Feng et al., *TwiBot-20: A Comprehensive Twitter Bot Detection Benchmark*,
  CIKM 2021. https://doi.org/10.1145/3459637.3482019
- Feng et al., *TwiBot-22: Towards Graph-Based Twitter Bot Detection*, NeurIPS
  Datasets and Benchmarks 2022. https://twibot22.github.io/
- Cresci et al., *The Paradigm-Shift of Social Spambots*, WWW Companion 2017.
  https://doi.org/10.1145/3041021.3055135
- Cresci et al., *Fame for Sale: Efficient Detection of Fake Twitter
  Followers*, Decision Support Systems 2015.
- Yang et al., *Scalable and Generalizable Social Bot Detection through Data
  Selection*, AAAI 2020. https://doi.org/10.1609/aaai.v34i01.5460
