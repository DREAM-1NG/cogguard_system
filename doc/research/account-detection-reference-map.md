# Account Detection Reference Map

Updated: 2026-08-04

This file is the citable reference map for the **Chinese Account Detection Active Learning Loop**. It records what each reference supports, what transfers to CogGuard, and what must not be overclaimed.

## Social Bot Detection And Chinese Transfer

| Reference | What it supports | Transfer to CogGuard |
| --- | --- | --- |
| Ferrara et al., **The Rise of Social Bots**, CACM 2016, DOI [`10.1145/2818717`](https://doi.org/10.1145/2818717) | Foundational social-bot threat model and automation framing. | Account detection is observable behavior classification, not identity or nationality attribution. |
| Davis et al., **BotOrNot: A System to Evaluate Social Bots**, WWW Companion 2016, DOI [`10.1145/2872518.2889403`](https://doi.org/10.1145/2872518.2889403) | Analyst-facing bot assessment with multiple evidence families. | Preserve evidence and model card fields instead of exposing only a scalar. |
| Chavoshi et al., **DeBot: Twitter Bot Detection via Warped Correlation**, ICDM 2016, DOI [`10.1109/ICDM.2016.0096`](https://doi.org/10.1109/ICDM.2016.0096) | Temporal correlation for automated or coordinated behavior discovery. | Temporal correlation is a reason tag or acquisition signal, not a target class. |
| Varol et al., **Online Human-Bot Interactions**, ICWSM 2017, DOI [`10.1609/icwsm.v11i1.14871`](https://doi.org/10.1609/icwsm.v11i1.14871) | Human/bot task framing, characterization, and evaluation. | Keep target labels minimal: `human`, `bot`, `insufficient_evidence`. |
| Cresci et al., **Social Fingerprinting**, IEEE TDSC 2017, DOI [`10.1109/TDSC.2017.2709181`](https://doi.org/10.1109/TDSC.2017.2709181) | Group-level behavioral similarity and spambot discovery. | Similarity/group evidence supports acquisition and review, not new supervised labels. |
| Wu et al., **A Novel Framework for Detecting Social Bots with Deep Neural Networks and Active Learning**, Knowledge-Based Systems 2021, DOI [`10.1016/j.knosys.2020.106525`](https://doi.org/10.1016/j.knosys.2020.106525) | Closest Sina Weibo-specific active-learning bot detection precedent. | Transfer the collection-labeling-active-learning loop; do not copy its hand-feature stack as the primary learning claim. |
| Feng et al., **TwiBot-20**, CIKM 2020, DOI [`10.1145/3340531.3412705`](https://doi.org/10.1145/3340531.3412705) | Benchmark construction and account-level evaluation. | Use provenance, splits, and benchmark-style reporting. |
| Feng et al., **TwiBot-22**, NeurIPS Datasets and Benchmarks 2022, [project page](https://twibot22.github.io/) | Large graph benchmark with entities, relations, and annotation-quality discussion. | Use as graph/evaluation reference only; Chinese platform claims require Chinese labels. |
| Cai et al., **Detecting Social Bots by Jointly Modeling Deep Behavior and Content Information**, CIKM 2017, DOI [`10.1145/3132847.3133050`](https://doi.org/10.1145/3132847.3133050) | Joint behavior and content modeling. | Supports learned text plus account context, with leakage controls. |
| Kudugunta and Ferrara, **Deep Neural Networks for Bot Detection**, Information Sciences 2018, DOI [`10.1016/j.ins.2018.08.019`](https://doi.org/10.1016/j.ins.2018.08.019) | Neural account/text bot detection baseline. | Use learned baselines before claiming hypergraph correction gains. |
| Feng et al., **BotRGCN: Twitter Bot Detection with Relational Graph Convolutional Networks**, 2021/2022, [arXiv](https://arxiv.org/abs/2106.13092) | Relational graph neural social-bot detection. | Supports graph/account representation baselines; not a Chinese-data validation source. |
| Feng et al., **SATAR: A Self-supervised Approach to Twitter Account Representation Learning and its Application in Bot Detection**, CIKM 2021, DOI [`10.1145/3459637.3482129`](https://doi.org/10.1145/3459637.3482129) | Self-supervised account representation for bot detection. | Supports learned account representations before hand-rule expansion; transfer requires Chinese evaluation. |

## Chinese Representation And Domain Adaptation

| Reference | What it supports | Transfer to CogGuard |
| --- | --- | --- |
| Cui et al., **Pre-Training with Whole Word Masking for Chinese BERT**, IEEE/ACM TASLP 2021, [arXiv](https://arxiv.org/abs/1906.08101) | Chinese whole-word masking pretraining for Chinese language understanding. | Use Chinese RoBERTa/WWM-style local checkpoints for Chinese text, not XLM-R by default unless cross-lingual transfer is explicitly tested. |
| Gururangan et al., **Don't Stop Pretraining**, ACL 2020, DOI [`10.18653/v1/2020.acl-main.740`](https://doi.org/10.18653/v1/2020.acl-main.740) | Domain-adaptive and task-adaptive pretraining improve downstream NLP. | Inference: Chinese social text continued pretraining is likely useful, but it is not a replacement for approved labels and needs Chinese social-text validation. |
| Margatina et al., **Active Learning for Pre-trained Language Models**, ACL 2022, DOI [`10.18653/v1/2022.acl-short.93`](https://doi.org/10.18653/v1/2022.acl-short.93) | PLM adaptation and acquisition strategy interact. | Record model state and acquisition policy per batch. |

## Active Learning

| Reference | What it supports | Transfer to CogGuard |
| --- | --- | --- |
| Lewis and Gale, **A Sequential Algorithm for Training Text Classifiers**, SIGIR 1994, DOI [`10.1007/978-1-4471-2099-5_1`](https://doi.org/10.1007/978-1-4471-2099-5_1) | Uncertainty sampling for text classifiers. | Use uncertainty only in warm-start with calibrated model output. |
| Settles, **Active Learning Literature Survey**, 2009, [technical report](https://minds.wisconsin.edu/handle/1793/60660) | Taxonomy of uncertainty, query-by-committee, density, diversity, and stream sampling. | Defines acquisition vocabulary and baselines. |
| Sener and Savarese, **Core-Set Active Learning**, ICLR 2018, [OpenReview](https://openreview.net/forum?id=H1aIuk-RW) | Coverage/diversity batch selection. | Justifies diversity and coverage fallback, especially in cold start. |
| Yuan et al., **Cold-start Active Learning through Self-supervised Language Modeling**, EMNLP 2020, DOI [`10.18653/v1/2020.emnlp-main.637`](https://doi.org/10.18653/v1/2020.emnlp-main.637) | ALPS uses masked-LM surprisal before classifier uncertainty is reliable. | `cold_start_alps_core_set`; missing local MLM input fails closed rather than falling back to classifier uncertainty. |
| Ein-Dor et al., **Active Learning for BERT: An Empirical Study**, EMNLP 2020, DOI [`10.18653/v1/2020.emnlp-main.638`](https://doi.org/10.18653/v1/2020.emnlp-main.638) | Equal-budget transformer AL comparisons. | Report random and uncertainty baselines; do not report only final model accuracy. |
| Ash et al., **BADGE**, ICLR 2020, [OpenReview](https://openreview.net/forum?id=ryghZJBKPS) | Gradient embeddings combine uncertainty and diversity. | Future warm-start gradient acquisition after the Chinese model exposes stable gradients. |
| Kirsch et al., **BatchBALD**, NeurIPS 2019, [NeurIPS](https://proceedings.neurips.cc/paper/2019/hash/95323660ed2124450caaac2c46b5ed90-Abstract.html) | Joint batch information gain and redundancy reduction. | Optional expensive committee acquisition, not a current default. |
| Margatina et al., **Active Learning by Acquiring Contrastive Examples**, EMNLP 2021, DOI [`10.18653/v1/2021.emnlp-main.51`](https://doi.org/10.18653/v1/2021.emnlp-main.51) | Near-neighbor contrastive examples. | Future similar-account acquisition using hypergraph neighbors. |
| Schroeder et al., **Revisiting Uncertainty-based Query Strategies for Active Learning with Transformers**, Findings ACL 2022, DOI [`10.18653/v1/2022.findings-acl.172`](https://doi.org/10.18653/v1/2022.findings-acl.172) | Practical uncertainty strategy comparison for transformers. | Expensive AL methods must beat simple baselines before activation. |
| Zhou et al., **Camouflaged Chinese Spam Content Detection with Semi-supervised Generative Active Learning**, ACL 2020, DOI [`10.18653/v1/2020.acl-main.279`](https://aclanthology.org/2020.acl-main.279/) | Chinese social text, active learning, and semi-supervised augmentation. | Useful Chinese active-learning analogue; task is spam/content detection, so it supports acquisition design rather than bot-label claims. |
| Lowell et al., **Practical Obstacles to Deploying Active Learning**, EMNLP-IJCNLP 2019, DOI [`10.18653/v1/D19-1104`](https://aclanthology.org/D19-1104/) | Deployment failures and evaluation traps in practical active learning. | Keep equal-budget random/simple baselines and do not claim production gain from one selected pool. |
| Beck et al., **On Dataset Transferability in Active Learning for Transformers**, Findings ACL 2023, [ACL Anthology](https://aclanthology.org/2023.findings-acl.144/) | Active-learning strategies can fail to transfer across datasets/models. | Require per-dataset Chinese validation instead of reusing one acquisition policy as universal. |
| Karamcheti et al., **On the Fragility of Active Learners for Text Classification**, EMNLP 2024, [ACL Anthology](https://aclanthology.org/2024.emnlp-main.1240/) | Text AL can be brittle under initialization, noise, and budget choices. | Keep random audit and simple baselines as regression defenses. |

## Acquisition Optimization References

| Reference | What it supports | Transfer to CogGuard |
| --- | --- | --- |
| Yoo and Kweon, **Learning Loss for Active Learning**, CVPR 2019, [CVF](https://openaccess.thecvf.com/content_CVPR_2019/html/Yoo_Learning_Loss_for_Active_Learning_CVPR_2019_paper.html) | Learned loss prediction as an acquisition signal. | Later meta-acquisition candidate only after enough Chinese approved rounds exist; not a cold-start method. |
| Gal et al., **Deep Bayesian Active Learning with Image Data**, ICML 2017, [PMLR](https://proceedings.mlr.press/v70/gal17a.html) | Bayesian uncertainty and MC-dropout acquisition. | Candidate for disagreement/uncertainty studies, but image setting means it must not become the default text/account method without validation. |
| Ducoffe and Precioso, **Adversarial Active Learning for Deep Networks**, ECML PKDD 2018, [Springer](https://link.springer.com/chapter/10.1007/978-3-030-10925-7_3) | Boundary/adversarial-distance acquisition. | Possible later stress-test baseline for near-boundary accounts; not currently needed for the main Chinese account loop. |
| Karamcheti et al., **Mind Your Outliers! Investigating the Negative Impact of Outliers on Active Learning for Visual Question Answering**, ACL 2021, [ACL Anthology](https://aclanthology.org/2021.acl-long.542/) | Outlier-prone acquisition can harm active learning. | OOD should be a capped review-priority signal, not an unconstrained top priority. |
| Zhang et al., **Deep Active Learning for Named Entity Recognition: A Contrastive Learning Approach**, ACL 2022, [ACL Anthology](https://aclanthology.org/2022.acl-long.277/) | Contrastive representations for NLP active learning. | Supports representation-learning upgrade direction, but task transfer requires account-level validation. |
| ALPS code, **forest-snow/alps**, [GitHub](https://github.com/forest-snow/alps) | Paper-linked implementation of MLM surprisal acquisition. | Reference for replacing caller-supplied surprisal with local Chinese MLM scoring. |
| BADGE code, **JordanAsh/badge**, [GitHub](https://github.com/JordanAsh/badge) | Paper-linked implementation of gradient embedding acquisition. | Reference for warm-start gradient embedding extraction and batch selection. |
| Google active-learning, **kcenter_greedy.py**, [GitHub](https://github.com/google/active-learning/blob/master/sampling_methods/kcenter_greedy.py) | Implementation reference for k-center greedy coverage. | Reference for replacing hashed fallback diversity with embedding core-set. |

## Label Quality, Bias, And Human Review

| Reference | What it supports | Transfer to CogGuard |
| --- | --- | --- |
| Artstein and Poesio, **Inter-Coder Agreement for Computational Linguistics**, Computational Linguistics 2008, DOI [`10.1162/coli.2008.34.4.555`](https://doi.org/10.1162/coli.2008.34.4.555) | Agreement metrics and limits of single labels. | Store reviewer identity and prepare double-review/adjudication reports. |
| Passonneau and Carpenter, **The Benefits of a Model of Annotation**, TACL 2014, DOI [`10.1162/tacl_a_00183`](https://doi.org/10.1162/tacl_a_00183) | Annotator variation and adjudication. | Preserve raw labels, confidence, evidence ids, and adjudicator metadata. |
| Plank, **The Problem of Human Label Variation**, COLING 2022, DOI [`10.18653/v1/2022.coling-1.387`](https://doi.org/10.18653/v1/2022.coling-1.387) | Human label variation is signal, not just noise. | Do not silently collapse disagreement into a fake gold label. |
| Wang and Plank, **ACTOR**, EMNLP 2023, [ACL Anthology](https://aclanthology.org/2023.emnlp-main.126/) | Active learning with annotator-specific variation. | Future reviewer-routing; current system records analyst id and confidence. |
| van der Meer et al., **ACAL**, EMNLP 2024, [ACL Anthology](https://aclanthology.org/2024.emnlp-main.1031/) | Joint active sample and annotator selection. | Future annotator assignment policy. |
| Suresh and Guttag, **Sources of Harm throughout the ML Life Cycle**, FAccT 2021, DOI [`10.1145/3461702.3461721`](https://doi.org/10.1145/3461702.3461721) | Bias sources across collection, labeling, modeling, and deployment. | Keep random audit, holdout isolation, and false-positive burden gates. |
| Hovy et al., **Are We Modeling the Task or the Annotator?**, EMNLP-IJCNLP 2019, DOI [`10.18653/v1/D19-1107`](https://aclanthology.org/D19-1107/) | Models can learn annotator bias instead of task signal. | Analyst id and adjudication metadata should remain part of corpus provenance. |
| Prabhakaran et al., **Data Statements for Natural Language Processing**, TACL 2018, [ACL Anthology](https://aclanthology.org/Q18-1041/) | NLP datasets need language, population, and collection-context documentation. | Chinese account corpora need platform/time/source statements before public claims. |

## Calibration, Abstention, OOD, And Governance

| Reference | What it supports | Transfer to CogGuard |
| --- | --- | --- |
| Guo et al., **On Calibration of Modern Neural Networks**, ICML 2017, [PMLR](https://proceedings.mlr.press/v70/guo17a.html) | Neural confidence can be miscalibrated; temperature scaling is practical. | ECE gate before uncertainty influences acquisition or activation. |
| Geifman and El-Yaniv, **Selective Classification for Deep Neural Networks**, NeurIPS 2017, [NeurIPS](https://papers.nips.cc/paper_files/paper/2017/hash/6c340f25839e6acdc73414517203f5f0-Abstract.html) | Risk-coverage and reject option. | `insufficient_evidence` is an abstention target, not a hidden negative class. |
| Geifman and El-Yaniv, **SelectiveNet**, ICML 2019, [PMLR](https://proceedings.mlr.press/v97/geifman19a.html) | End-to-end selective classification with an integrated reject option. | Future candidate for learned abstention; current system uses explicit label and gate semantics. |
| Hendrycks and Gimpel, **A Baseline for Detecting Misclassified and OOD Examples**, ICLR workshop 2017, [arXiv](https://arxiv.org/abs/1610.02136) | OOD and misclassification baselines. | OOD is a review-priority signal, never a label. |
| Liu et al., **Energy-based Out-of-distribution Detection**, NeurIPS 2020, [NeurIPS](https://proceedings.neurips.cc/paper/2020/hash/f5496252609c43eb8a3d147ab9b9c006-Abstract.html) | Energy scores improve OOD detection beyond plain softmax confidence. | Future OOD scoring upgrade after the Chinese model exposes logits consistently. |
| Ovadia et al., **Can You Trust Your Model's Uncertainty Under Dataset Shift?**, NeurIPS 2019, [NeurIPS](https://proceedings.neurips.cc/paper/2019/hash/8558cb408c1d76621371888657d2eb1d-Abstract.html) | Uncertainty degrades under dataset shift. | Platform/time split and calibration gates are mandatory before warm-start trust. |
| Gebru et al., **Datasheets for Datasets**, CACM 2021, [arXiv](https://arxiv.org/abs/1803.09010) | Dataset documentation and intended-use boundaries. | Corpus export writes manifest and dataset card. |
| Akhtar et al., **Automatic Generation of Model and Data Cards**, NAACL 2024, [ACL Anthology](https://aclanthology.org/2024.naacl-long.110/) | Semi-automated governance documentation. | Future automation layer for dataset/model cards; current system writes a deterministic draft card. |
| Akhtar et al., **Croissant: A Metadata Format for ML-Ready Datasets**, NeurIPS 2024 Datasets and Benchmarks, [NeurIPS](https://proceedings.neurips.cc/paper_files/paper/2024/hash/9547b09b722f2948ff3ddb5d86002bc0-Abstract-Datasets_and_Benchmarks_Track.html) | Interoperable dataset metadata. | Future metadata export format, not required for the current internal corpus manifest. |
| Mitchell et al., **Model Cards for Model Reporting**, FAccT 2019, [arXiv](https://arxiv.org/abs/1810.03993) | Model intended use, metrics, limitations, and ethical considerations. | Shadow models need cards and activation records. |
| Mosqueira-Rey et al., **Human-in-the-loop Machine Learning**, Artificial Intelligence Review 2023, DOI [`10.1007/s10462-022-10246-w`](https://doi.org/10.1007/s10462-022-10246-w) | HITL systems and governance categories. | Account detection remains analyst-governed review support. |

## Leakage-Safe Evaluation And ML System Governance

| Reference | What it supports | Transfer to CogGuard |
| --- | --- | --- |
| Hu et al., **Open Graph Benchmark**, NeurIPS 2020, [arXiv](https://arxiv.org/abs/2005.00687) | Benchmark split discipline and graph ML evaluation infrastructure. | Use explicit split manifests and avoid selected-pool evaluation. |
| Huang et al., **Temporal Graph Benchmark**, NeurIPS 2023 Datasets and Benchmarks, [project](https://tgb.complexdatalab.com/) | Temporal graph split and realistic dynamic-graph evaluation. | Supports time-forward account and propagation evaluation requirements. |
| Shchur et al., **Pitfalls of Graph Neural Network Evaluation**, Relational Representation Learning workshop 2018, [arXiv](https://arxiv.org/abs/1811.05868) | Graph evaluation can be sensitive to splits, seeds, and protocol choices. | Community-disjoint and multi-seed reports are governance gates, not optional polish. |
| Kapoor and Narayanan, **Leakage and the Reproducibility Crisis in ML-based Science**, Patterns 2023, DOI [`10.1016/j.patter.2023.100804`](https://doi.org/10.1016/j.patter.2023.100804) | Data leakage can invalidate ML claims across scientific applications. | Frozen holdout must be outside active-learning selection and training. |
| Sculley et al., **Hidden Technical Debt in Machine Learning Systems**, NeurIPS 2015, [paper](https://papers.nips.cc/paper/5656-hidden-technical-debt-in-machine-learning-systems) | ML systems require governance around data dependencies, feedback loops, and configuration. | Model activation must bind dataset fingerprint, checkpoint hash, metrics, and approval evidence. |
| Breck et al., **The ML Test Score**, 2017, [paper](https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/) | Production-readiness rubric for ML systems. | Shadow run, calibration, false-positive burden, and rollback gates are deployment controls. |

## Implementation Consequences

1. Canonical labels remain `human`, `bot`, and `insufficient_evidence`.
2. `reason_tags` are evidence descriptors, not supervised target classes.
3. Cold-start cannot use uncalibrated classifier uncertainty.
4. Warm-start uncertainty requires a calibrated model output and recorded calibration status.
5. Cold-start default acquisition must use ALPS vectors from a local Chinese masked-language model plus Core-set selection; hashed text vectors are non-claimable baseline material only.
6. Warm-start default acquisition must use BADGE classifier-gradient embeddings from the internal BotRHG runtime; plain representation vectors are not a BADGE substitute.
7. Active-learning efficiency must be evaluated against random and simple uncertainty baselines at equal budgets.
8. Exported corpora need fingerprints, manifests, dataset cards, and a clear source policy.
9. Candidate models need registered dataset fingerprints, verified checkpoint hashes, frozen holdout, time-forward/platform/community-disjoint metrics, calibration, false-positive burden review, shadow run, and active administrator approval evidence before activation.
