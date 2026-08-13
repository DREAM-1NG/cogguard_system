# Text evidence: Table 5

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 7
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [44.0, 44.024, 568.019, 282.098]

## Caption

Table 5: Campaign type classification for 7 labels: politics, reform, news, finance, cult, entertainment, and common, see Table 2 for details. Text + MLP refers to the non-graph based classifier. The best results are in bold.

## Text from suggested visual region

~~~text
Model       Accuracy       Precision       Recall        Micro F1     Macro F1
              Text + MLP   0.367 ± 0.041   0.209 ± 0.135   0.367 ± 0.041   0.367 ± 0.041   0.133 ± 0.041
         GCN         0.533 ± 0.041   0.371 ± 0.042   0.533 ± 0.041   0.533 ± 0.041   0.251 ± 0.022
          GAT         0.567 ± 0.033   0.387 ± 0.031   0.567 ± 0.033   0.567 ± 0.033   0.264 ± 0.014
           GIN          0.633 ± 0.067   0.484 ± 0.105   0.633 ± 0.067   0.633 ± 0.067   0.351 ± 0.091
           GraphSAGE   0.583 ± 0.053   0.470 ± 0.082   0.583 ± 0.053   0.583 ± 0.053   0.320 ± 0.061                                       LEN-small          GINE         0.650 ± 0.033   0.569 ± 0.040   0.650 ± 0.033   0.650 ± 0.033   0.361 ± 0.042
         VNGE        0.833 ± 0.000   0.771 ± 0.000   0.833 ± 0.000   0.833 ± 0.000   0.671 ± 0.000
          LSD          0.667 ± 0.000   0.594 ± 0.000   0.667 ± 0.000   0.667 ± 0.000   0.414 ± 0.000
              Text + MLP   0.645 ± 0.011   0.462 ± 0.017   0.645 ± 0.011   0.645 ± 0.011   0.218 ± 0.006
         GCN         0.641 ± 0.009   0.457 ± 0.008   0.641 ± 0.009   0.641 ± 0.009   0.252 ± 0.004
          GAT         0.636 ± 0.000   0.467 ± 0.006   0.636 ± 0.000   0.636 ± 0.000   0.257 ± 0.001
           GIN          0.659 ± 0.000   0.495 ± 0.010   0.659 ± 0.000   0.659 ± 0.000   0.269 ± 0.002             LEN
           GraphSAGE   0.641 ± 0.017   0.453 ± 0.010   0.641 ± 0.017   0.641 ± 0.017   0.252 ± 0.006
          GINE         0.677 ± 0.009   0.478 ± 0.013   0.677 ± 0.009   0.677 ± 0.009   0.233 ± 0.004
         VNGE        0.659 ± 0.000   0.640 ± 0.000   0.659 ± 0.000   0.659 ± 0.000   0.383 ± 0.000
          LSD          0.545 ± 0.000   0.512 ± 0.000   0.545 ± 0.000   0.545 ± 0.000   0.252 ± 0.000

Table 5: Campaign type classification for 7 labels: politics, reform, news, finance, cult, entertainment, and common, see Table
2 for details. Text + MLP refers to the non-graph based classifier. The best results are in bold.
~~~

## Body references

- [PDF p.7] Campaign Type Classification We next classify campaign graphs into seven specific types: politics, reform, news, finance, cult, entertainment, and com- mon, as detailed in Table 2. Identifying the campaigns with potentially negative social impacts (e.g., false political cam- paigns) by only using the graph structure can be an im- portant problem to understand misinformation. Similar to the binary classification setup above, we use the established GNNs for multi-class classification. Table 5 presents the re- sults. VGNE achieves the highest accuracy in LEN-small and GINE achieves the highest accuracy on LEN. While VGNE and GINE provide high micro F1 scores, we notice that the macro F1 scores are lower. This applies to all the other mod- els. We suspect this is due to imbalanced labels in the data, as

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
