# Text evidence: Table 5

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 9
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [97.532, 533.861, 517.137, 762.295]

## Caption

Table 5: LR and CNR of FP under random, historical, and inductive negative sampling strategy.

## Text from suggested visual region

~~~text
Table 4: LR and CNR of TP and TN with Table 5: LR and CNR of FP under random, historical,
random negative sampling strategy.        and inductive negative sampling strategy.
           LR (%)   CNR (%)                  LR(%)         CNR(%)
    Datasets                                 Datasets
           TP  TN   TP  TN                 rnd    hist   ind   rnd    hist   ind
  Wikipedia 92.74 97.19 59.09  0.01     Wikipedia  2.81  89.28 94.53  0.02  14.00 11.66
    UCI    82.70 96.77 28.03  1.45      UCI     3.23  64.93 76.42  9.98  12.22 13.81
     Flights   96.13 95.33 47.58  1.40       Flights    4.67  94.52 92.94  0.01  35.62 30.29
  US Legis.  78.95 56.83 75.18 53.98   US Legis.  43.17 17.31 21.21 79.40 87.51 75.51
  UN Vote  65.18 45.43 56.24 76.02   UN Vote  54.57 39.90 52.92 79.60 75.53 79.15

We observe when CNR of TP is significantly higher than CNR of TN in the datasets, DyGFormer
often outperforms baselines (most datasets satisfy this property). For Wikipedia, UCI, and Flights,
their CNRs of TP are much higher than those of TN (e.g., 59.09% vs. 0.01% on Wikipedia). Such
a characteristic matches the motivation of our neighbor co-occurrence encoding scheme, enabling
DyGFormer to correctly predict most links (e.g., 92.74% of positive links and 97.19% of negative
links are properly predicted on Wikipedia). Moreover, as LastFM and Can. Parl. can gain from


                                       9
~~~

## Body references

- [PDF p.10] Compared with the random (rnd) strategy, historical (hist) and inductive (ind) strategies will sample previous links as negative ones. This makes previous positive links negative, which may hurt the performance DyGFormer since the motivation of our neighbor co-occurrence encoding scheme is violated. As positive links are identical among rnd, hist, and ind, we compute LR and the average CNR of links in FP and show results in Table 5.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
