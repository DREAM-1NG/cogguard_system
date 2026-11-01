# Text evidence: Figure 7

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 16
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text
- **Suggested region:** [97.532, 200.667, 515.247, 421.479]

## Caption

Figure 7: Effect of sampling of different tree structures on inductive performance. We conduct more experiment to investigate this topic with Wikipedia and UCI datasets. The setup is as follows: ﬁrst, we ﬁx CAW sampling number M = 64 = 26 and length m = 2, so that we always have k1k2 = M = 26; next, we assign different values to k1, so that the shape of the tree changes accordingly; controlling other hyperparameters to be the optimal combination found by grid search, we plot the corresponding inductive AUC scores of CAW-N-mean on all testing edges in Fig. 7. It is observed that while tree-structured sampling may affect the performance to some extent, its negative impact is less prominent when the ﬁrst-step sampling number k1 is relatively large, and our model still achieves state-of-the-art performance compared to our baselines. That makes the tree-structured sampling a reasonable strategy that can further reduce time complexity.

## Text from suggested visual region

~~~text
opportunity to tradeoff between prediction performance and time complexity.


           Figure 7: Effect of sampling of different tree structures on inductive performance.
We conduct more experiment to investigate this topic with Wikipedia and UCI datasets. The setup is
as follows: ﬁrst, we ﬁx CAW sampling number M = 64 = 26 and length m = 2, so that we always
have k1k2 = M = 26; next, we assign different values to k1, so that the shape of the tree changes
accordingly; controlling other hyperparameters to be the optimal combination found by grid search,
we plot the corresponding inductive AUC scores of CAW-N-mean on all testing edges in Fig. 7. It is
observed that while tree-structured sampling may affect the performance to some extent, its negative
impact is less prominent when the ﬁrst-step sampling number k1 is relatively large, and our model
still achieves state-of-the-art performance compared to our baselines. That makes the tree-structured
sampling a reasonable strategy that can further reduce time complexity.
~~~

## Body references

- [No body reference recovered]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
