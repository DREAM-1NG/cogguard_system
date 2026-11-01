# Text evidence: Table 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 9
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [97.532, 67.405, 514.173, 556.861]

## Caption

Table 1: Average Precision (AP) results for link prediction. We denote the best-performing model (highest mean AP) in blue. In 5 out of 6 datasets, PINT achieves the highest AP in the transductive setting. For the inductive case, PINT outperforms previous MP-TGNs and competes with CAW. We also evaluate PINT w/ and w/o relative positional features. Adopting positional features leads to signiﬁcant performance gains.

## Text from suggested visual region

~~~text
Table 1: Average Precision (AP) results for link prediction. We denote the best-performing model (highest
mean AP) in blue. In 5 out of 6 datasets, PINT achieves the highest AP in the transductive setting. For the
inductive case, PINT outperforms previous MP-TGNs and competes with CAW. We also evaluate PINT w/ and
w/o relative positional features. Adopting positional features leads to signiﬁcant performance gains.
     Model              Reddit      Wikipedia      Twitter      UCI        Enron      LastFM
    GAT              97.33 ± 0.2    94.73 ± 0.2            -                  -                  -                  -
     GraphSAGE       97.65 ± 0.2    93.56 ± 0.3            -                  -                  -                  -
      Jodie              97.11 ± 0.3    94.62 ± 0.5    98.23 ± 0.1    86.73 ± 1.0    77.31 ± 4.2    69.32 ± 1.0
     DyRep            97.98 ± 0.1    94.59 ± 0.2    98.48 ± 0.1    54.60 ± 3.1    77.68 ± 1.6    69.24 ± 1.4
    TGAT             98.12 ± 0.2    95.34 ± 0.1    98.70 ± 0.1    77.51 ± 0.7    68.02 ± 0.1    54.77 ± 0.4
     TGN-Att          98.70 ± 0.1    98.46 ± 0.1    98.00 ± 0.1    80.40 ± 1.4    79.91 ± 1.3    80.69 ± 0.2      Transductive
    CAW             98.39 ± 0.1    98.63 ± 0.1    98.72 ± 0.1    92.16 ± 0.1   92.09 ± 0.7   81.29 ± 0.1
    PINT (w/o pos. feat.)   98.62 ± .04    98.43 ± .04    98.53 ± 0.1    92.68 ± 0.5    83.06 ± 2.1    81.35 ± 1.6
    PINT           99.03 ± .01  98.78 ± 0.1  99.35 ± .01  96.01 ± 0.1   88.71 ± 1.3   88.06 ± 0.7
    GAT              95.37 ± 0.3    91.27 ± 0.4            -                  -                  -                  -
     GraphSAGE       96.27 ± 0.2    91.09 ± 0.3            -                  -                  -                  -
      Jodie              94.36 ± 1.1    93.11 ± 0.4    96.06 ± 0.1    75.26 ± 1.7    76.48 ± 3.5    80.32 ± 1.4
     DyRep            95.68 ± 0.2    92.05 ± 0.3    96.33 ± 0.2    50.96 ± 1.9    66.97 ± 3.8    82.03 ± 0.6                        96.62                                      93.99                                                    96.33                                                                   70.54                                                                                 63.70                                                                                               56.76    TGAT                 ± 0.3                          ± 0.3                                  ± 0.1                                          ± 0.5                                                  ± 0.2                                                           ± 0.9    Inductive                        97.55                                  0.1                                      97.81                                                 0.1                                                    95.76                                                                0.1                                                                   74.70                                                                               0.9                                                                                 78.96                                                                                              0.5                                                                                               84.66     TGN-Att                 ±       ±       ±       ±       ±       ± 0.1
    CAW             97.81 ± 0.1   98.52 ± 0.1  98.54 ± 0.4   92.56 ± 0.1   91.74 ± 1.7   85.67 ± 0.5
    PINT (w/o pos. feat.)   97.22 ± 0.2    97.81 ± 0.1    96.10 ± 0.1    90.25 ± 0.3    75.99 ± 2.3    88.44 ± 1.1
    PINT           98.25 ± .04   98.38 ± .04    98.20 ± .03   93.97 ± 0.1   81.05 ± 2.4   91.76 ± 0.7

novel nodes (inductive). We report mean and standard deviation of the AP over ten runs. For further
details, see Appendix D. We provide additional results in the supplementary material.

Results.  Table 1 shows that PINT is the best-performing method on ﬁve out of six datasets for
the transductive setting. Notably, the performance gap between PINT and TGN-Att amounts to
over 15% AP on UCI. The gap is also relatively high compared to CAW on LastFM, Enron, and
UCI; with CAW being the best model only on Enron. We also observe that many models achieve
relatively high AP on the attributed networks (Reddit, Wikipedia, and Twitter). This aligns well with
ﬁndings from [38], where TGN-Att was shown to have competitive performance against CAW on
Wikipedia and Reddit. The performance of GAT and TGAT (static GNNs) on Reddit and Wikipedia
reinforces the hypothesis that the edge features add signiﬁcantly to the discriminative power. On the
other hand, PINT and CAW, which leverage relative identities, show superior performance relative
to other methods when only time and degree information is available, i.e., on unattributed networks
(UCI, Enron, and LastFM). Table 1 also shows the effect of using relative positional features. While
including these features boosts PINT’s performance systematically, our ablation study shows that
PINT w/o positional features still outperforms other MP-TGNs on unattributed networks. In the
inductive case, we observe a similar behavior: PINT is consistently the best MP-TGN, and is better
than CAW on 3/6 datasets. Overall, PINT (w/ positional features) also yields the lowest standard
deviations. This suggests that positional encodings might be a useful inductive bias for TGNs.
~~~

## Body references

- [PDF p.9] Results. Table 1 shows that PINT is the best-performing method on ﬁve out of six datasets for the transductive setting. Notably, the performance gap between PINT and TGN-Att amounts to over 15% AP on UCI. The gap is also relatively high compared to CAW on LastFM, Enron, and UCI; with CAW being the best model only on Enron. We also observe that many models achieve relatively high AP on the attributed networks (Reddit, Wikipedia, and Twitter). This aligns well with ﬁndings from [38], where TGN-Att was shown to have competitive performance against CAW on Wikipedia and Reddit. The performance of GAT and TGAT (static GNNs) on Reddit and Wikipedia reinforces the hypothesis that the edge features add signiﬁcantly to the discriminative power. On the other hand, PINT and CAW, which leverage relative identities, show superior performance relative to other methods when only time and degree information is available, i.e., on unattributed networks (UCI, Enron, and LastFM). Table 1 also shows the effect of using relative positional features. While including these features boosts PINT’s performance systematically, our ablation study shows that PINT w/o positional features still outperforms other MP-TGNs on unattributed networks. In the inductive case, we observe a similar behavior: PINT is consistently the best MP-TGN, and is better than CAW on 3/6 datasets. Overall, PINT (w/ positional features) also yields the lowest standard deviations. This suggests that positional encodings might be a useful inductive bias for TGNs.
- [PDF p.9] Time comparison. Figure 7 compares the training times of PINT against other TGNs. For fairness, we use the same architecture (number of layers & neighbors) for all MP- TGNs: i.e., the best-performing PINT. For CAW, we use the one that yielded results in Table 1. As expected, TGAT is the fastest model. Note that the average time/epoch of PINT gets amortized since positional fea- tures are pre-computed. Without these fea- tures, PINT’s runtime closely matches TGN- Att. When trained for over 25 epochs, PINT runs considerably faster than CAW. We pro- vide additional details and results in the sup- plementary material.
- [PDF p.10] Incorporating relative positional features into MP-TGNs. We can use our relative positional features (RPF) to boost MP-TGNs. Table 2 shows the performance of TGN-Att with relative positional features on UCI, Enron, and LastFM. Notably, TGN-Att receives a signiﬁcant boost from our RPF. However, PINT still beats TGN-Att+RPF on 5 out of 6 cases. The values for TGN-Att+RPF reﬂect outcomes from 5 repetitions. We have used the same model selection procedure as TGN-Att in Table 1, and incorporated d = 4-dimensional positional features

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
