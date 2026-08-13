# Text evidence: Table 6

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 8
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [44.0, 44.024, 568.019, 194.028]

## Caption

Table 6: Campaign vs. non-campaign classification for news-based engagement networks. Text + MLP refers to the non-graph based classifier. The best results are in bold.

## Text from suggested visual region

~~~text
Model       Accuracy       Precision       Recall        F1 Score
                    Text + MLP   0.585 ± 0.062   0.535 ± 0.040   0.843 ± 0.000   0.651 ± 0.031
             GCN         0.554 ± 0.031   0.551 ± 0.018   0.943 ± 0.114   0.692 ± 0.037
              GAT         0.585 ± 0.092   0.631 ± 0.185   0.914 ± 0.171   0.705 ± 0.011
               GIN          0.492 ± 0.062   0.529 ± 0.057   0.543 ± 0.057   0.535 ± 0.055
                GraphSAGE   0.769 ± 0.028   1.000 ± 0.000   0.571 ± 0.089   0.727 ± 0.032
               GINE         0.585 ± 0.092   0.635 ± 0.135   0.800 ± 0.194   0.673 ± 0.026
             VNGE        0.769 ± 0.020   0.769 ± 0.024   0.833 ± 0.049   0.769 ± 0.063
              LSD          0.769 ± 0.001   0.773 ± 0.005   0.857 ± 0.010   0.800 ± 0.006

Table 6: Campaign vs. non-campaign classification for news-based engagement networks. Text + MLP refers to the non-graph
based classifier. The best results are in bold.
~~~

## Body references

- [PDF p.9] We also investigate a finer-grained binary classification among engagement networks that are based on news. There are 24 campaign networks within which the news are am- plified by bots and trolls, and 52 non-campaign networks that are organically formed due to popular events happen- ing in real world. We conjecture that this subset is uniquely challenging for classification as they share the same theme but different formation processes. To address the imbalance, we randomly sample 24 non-campaign graphs and run the GNNs mentioned above using the same setup above. Table 6 gives the results. LSD performs the best in terms of ac- curacy and F1 score, similar to the case in binary classifica- tion over all networks (Table 4). However, the scores for all the classifiers are consistently lower for the news networks, which again suggests a challenging testbed, especially for the neural network based approaches.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
