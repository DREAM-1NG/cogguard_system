# Text evidence: Table 2

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 10
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [97.253, 67.405, 515.741, 408.267]

## Caption

Table 2: Average precision results for TGN-Att + relative positional features.

## Text from suggested visual region

~~~text
Table 2: Average precision results for TGN-Att + relative positional features.
                                       Transductive                                Inductive
                        UCI         Enron       LastFM       UCI         Enron       LastFM

                           80.40        TGN-Att
                           95.64 ± 1.40.1    79.9185.04 ± 1.32.5    80.6989.41 ± 0.20.9    74.7092.82 ± 0.90.4    78.9676.27 ± 0.53.4    84.6691.63 ± 0.10.3        TGN-Att + RPF
                   ± 0.1    88.71 ± 1.3    88.06 ± 0.7    93.97 ± 0.1    81.05 ± 2.4    91.76 ± 0.7        PINT             96.01                   ±       ±       ±       ±       ±       ±

Incorporating relative positional features into MP-TGNs. We can use our relative positional
features (RPF) to boost MP-TGNs. Table 2 shows the performance of TGN-Att with relative positional
features on UCI, Enron, and LastFM. Notably, TGN-Att receives a signiﬁcant boost from our RPF.
However, PINT still beats TGN-Att+RPF on 5 out of 6 cases. The values for TGN-Att+RPF reﬂect
outcomes from 5 repetitions. We have used the same model selection procedure as TGN-Att in Table
1, and incorporated d = 4-dimensional positional features

Dimensionality of relative positional features.       97            UCI                  95              Enron
We assess the performance of PINT as a func-
tion of the dimension d of the relative positional        96                                      90
features. Figure 8 shows the performance of           (test) 95                                      85
                                                                   AP
                 10, 15,PINT       for d                       UCI and Enron.       2 {4,                    20} onWe    report        mean              and                    standard                              deviation                                       of AP        94                                      80                             transductiveinductive
on test set obtained from ﬁve independent runs.       93  4          10        15        20   75  4          10        15        20
In all experiments, we re-use the optimal hyper-                        Dims. (d)                                Dims. (d)
parameters found with d = 4. Increasing the   Figure 8: PINT: AP (mean and std) as a function of the
dimensionality of the positional features leads   dimensionality of the positional features.
to performance gains on both datasets. Notably,
we obtain a signiﬁcant boost for Enron with d = 10: 92.69 ± 0.09 AP in the transductive setting
and 88.34 ± 0.29 in the inductive case. Thus, PINT becomes the best-performing model on Enron
(transductive). On UCI, for d = 20, we obtain 96.36 ± 0.07 and 94.77 ± 0.12 (inductive).
6  Conclusion
~~~

## Body references

- [PDF p.10] Incorporating relative positional features into MP-TGNs. We can use our relative positional features (RPF) to boost MP-TGNs. Table 2 shows the performance of TGN-Att with relative positional features on UCI, Enron, and LastFM. Notably, TGN-Att receives a signiﬁcant boost from our RPF. However, PINT still beats TGN-Att+RPF on 5 out of 6 cases. The values for TGN-Att+RPF reﬂect outcomes from 5 repetitions. We have used the same model selection procedure as TGN-Att in Table 1, and incorporated d = 4-dimensional positional features

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
