# Text-only visual evidence ledger

> Extracted text is not visual verification. Do not infer unreported axes, colors, curves, panels, layout, or crop completeness.

## Figure 1

- **PDF page:** 2
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-1-p002.md](text/visuals/figure-1-p002.md)
- **Caption:** Figure 1: Triadic closure and feed-forward loops: Causal anonymous walks (CAW) capture the laws.

## Figure 2

- **PDF page:** 2
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-2-p002.md](text/visuals/figure-2-p002.md)
- **Caption:** Figure 2: Causal anonymous walks (CAW): causality extraction and set-based anonymization.

## Figure 3

- **PDF page:** 3
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-3-p003.md](text/visuals/figure-3-p003.md)
- **Caption:** Figure 3: Ambiguity due to removing node identi- ties in TGAT (Xu et al., 2020) (t1 < t2 < t3).

## Algorithm 1

- **PDF page:** 4
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [algorithm-1-p004.md](text/visuals/algorithm-1-p004.md)
- **Caption:** Algorithm 1: Temporal Walk Extraction (E, α, M, m, w0, t0)

## Figure 4

- **PDF page:** 4
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-4-p004.md](text/visuals/figure-4-p004.md)
- **Caption:** Figure 4: The correlation be- tween walks needs to be captured to learn this law.

## Table 1

- **PDF page:** 6
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [table-1-p006.md](text/visuals/table-1-p006.md)
- **Caption:** Table 1: Summary of dataset statistics. Average link stream intensity is calculated by 2|E|/(|V |T), where T is the total time range of all edges in unit of seconds, |V | and |E| are number of nodes and temporal links.

## Table 2

- **PDF page:** 8
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [table-2-p008.md](text/visuals/table-2-p008.md)
- **Caption:** Table 2: Performance in AUC (mean in percentage ± 95% conﬁdence level.) † highlights the best baselines. ∗, bold font, bold font∗respectively highlights the case where our models’ performance exceeds the best baseline on average, by 70% conﬁdence, by 95% conﬁdence.

## Figure 5

- **PDF page:** 9
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-5-p009.md](text/visuals/figure-5-p009.md)
- **Caption:** Figure 5: Hyperparameter sensitivity in CAW sampling. AUC on all inductive test links are reported.

## Figure 6

- **PDF page:** 9
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-6-p009.md](text/visuals/figure-6-p009.md)
- **Caption:** Figure 6: Complexity evaluation: The accumulated runtime of (a) temporal random walk extraction (Alg.1) and (b) the entire CAW-N training, timed over one epoch on Wikipedia (using different |E| for training).

## Algorithm 2

- **PDF page:** 14
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [algorithm-2-p014.md](text/visuals/algorithm-2-p014.md)
- **Caption:** Algorithm 2: Online probability computation (G, α)

## Algorithm 3

- **PDF page:** 14
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [algorithm-3-p014.md](text/visuals/algorithm-3-p014.md)
- **Caption:** Algorithm 3: Iterative Sampling (E, α, wp, tp)

## Figure 7

- **PDF page:** 16
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [figure-7-p016.md](text/visuals/figure-7-p016.md)
- **Caption:** Figure 7: Effect of sampling of different tree structures on inductive performance. We conduct more experiment to investigate this topic with Wikipedia and UCI datasets. The setup is as follows: ﬁrst, we ﬁx CAW sampling number M = 64 = 26 and length m = 2, so that we always have k1k2 = M = 26; next, we assign different values to k1, so that the shape of the tree changes accordingly; controlling other hyperparameters to be the optimal combination found by grid search, we plot the corresponding inductive AUC scores of CAW-N-mean on all testing edges in Fig. 7. It is observed that while tree-structured sampling may affect the performance to some extent, its negative impact is less prominent when the ﬁrst-step sampling number k1 is relatively large, and our model still achieves state-of-the-art performance compared to our baselines. That makes the tree-structured sampling a reasonable strategy that can further reduce time complexity.

## Table 4

- **PDF page:** 17
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [table-4-p017.md](text/visuals/table-4-p017.md)
- **Caption:** Table 4: Hyperparameter search range of CAW sampling.

## Table 5

- **PDF page:** 18
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [table-5-p018.md](text/visuals/table-5-p018.md)
- **Caption:** Table 5: Snapshot split for evaluating snapshot-based baselines.

## Table 6

- **PDF page:** 19
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [table-6-p019.md](text/visuals/table-6-p019.md)
- **Caption:** Table 6: Performance in Average Precision (AP) (mean in percentage ± 95% conﬁdence level.) † highlights the best baselines. ∗, bold font, bold font∗respectively highlights the case where our models’ performance exceeds the best baseline on average, by 70% conﬁdence, by 95% conﬁdence.

## Figure 8

- **PDF page:** 20
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-8-p020.md](text/visuals/figure-8-p020.md)
- **Caption:** Figure 8: Visualizing most discriminatory CAWs, and their occurrence ratios with positive / negative samples.

## Figure 8

- **PDF page:** 20
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-8-p020.md](text/visuals/figure-8-p020.md)
- **Caption:** Fig. 8 lists the 3 highest-scored and the 3 lowest-scored shapes of CAW, which are extracted from the Wikipedia dataset with M = 32 and m = 3. A law of general motif closure can be observed from the highest-scored CAWs: two nodes that commonly appear in some types of motif are more inclined to have a link in between. For example, the highest-scored shape of CAW, (0, ∞) →(1, 2) →(2, 3) →(1, 2), implies that the nodes except the ﬁrst in this CAW appear in the sampled common 3-hop neighborhood around the two nodes between which the link is to be

## Figure 9

- **PDF page:** 21
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-9-p021.md](text/visuals/figure-9-p021.md)
- **Caption:** Figure 9: Visualizing all AWs, and their occurrence ratios with positive / negative samples.

## Table 7

- **PDF page:** 21
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [table-7-p021.md](text/visuals/table-7-p021.md)
- **Caption:** Table 7: TGN performance in AUC (mean in percentage ± 95% conﬁdence level). Bond font highlights the case when TGN out performs CAW-N. TGN generally outperforms other baselines.

## Table 8

- **PDF page:** 22
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [table-8-p022.md](text/visuals/table-8-p022.md)
- **Caption:** Table 8: TGN performance in AP (mean in percentage ± 95% conﬁdence level). Bond font highlights the case when TGN out performs CAW-N. TGN generally outperforms other baselines.
