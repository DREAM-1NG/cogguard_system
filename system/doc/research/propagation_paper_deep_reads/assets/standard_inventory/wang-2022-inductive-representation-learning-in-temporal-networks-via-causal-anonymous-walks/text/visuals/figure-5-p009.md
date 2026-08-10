# Text evidence: Figure 5

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 9
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [112.708, 60.525, 499.293, 184.355]

## Caption

Figure 5: Hyperparameter sensitivity in CAW sampling. AUC on all inductive test links are reported.

## Text from suggested visual region

~~~text
Figure 5: Hyperparameter sensitivity in CAW sampling. AUC on all inductive test links are reported.
~~~

## Body references

- [PDF p.9] set the rest two to an optimal value found by grid search, and report the mean AUC performance on all inductive test links (i.e. old vs. new, new vs. new) and their 95% conﬁdence intervals. The results are summarized in Fig.5. From (a), we observe that only a small number of sampled CAWs are needed to achieve a competitive performance. Meanwhile, the performance gain is saturated as the sampling number increases. We analyze the temporal decay α in (b): α usually has an optimal interval, whose values and length also vary with different datasets to capture the different levels of temporal dynamics; a small α suggests an almost uniform sampling of interaction history, which hurts the performance; an overly large α also damages the model, since it makes the model only sample the most recent few interactions for computation and blind to the rest. Based on our efﬁcient sampling strategy (Sec.4.4), we may combine the optimal α with the average link intensity τ (Tab.1), and concludes that CAW-N only needs to online record and sample from about a constant times about 5 (≈τ

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
