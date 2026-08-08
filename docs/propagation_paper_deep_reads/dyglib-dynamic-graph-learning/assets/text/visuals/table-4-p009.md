# Text evidence: Table 4

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 9
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [97.532, 181.33, 515.741, 575.306]

## Caption

Table 4: LR and CNR of TP and TN with random negative sampling strategy.

## Text from suggested visual region

~~~text
Table 3: CLR and CNR of changes made by DyGFormer.
                   CLR (%)                  CNR (%)
     Datasets
         FN→TP FP→TN TP→FN TN→FP FN→TP FP→TN TP→FN TN→FP
    Wikipedia   68.36    72.73    1.68     1.69    18.16    0.01     0.10     2.49
     UCI     71.45    94.11    7.29     1.82    19.08    2.49     3.35    13.02
      Flights    83.66    83.83    1.73     2.11    37.09    2.28     7.06    20.28
   US Legis.   31.63    23.67    6.63     1.59    69.92    62.13    61.14    63.80
   UN Vote   44.02    36.46    28.95    30.53    78.57    81.39    80.86    77.02

We find NCoE effectively helps DyGFormer rectify wrong predictions of DyGFormer w/o NCoE
on datasets with significantly higher CNR of positive links than negative ones, which happens with
most datasets. Concretely, for Wikipedia, UCI, and Flights, their CNRs of FN→TP are much higher
than FP→TN (e.g., 37.09% vs. 2.28% on Flights) and DyGFormer revises most wrong predictions of
DyGFormer w/o NCoE (e.g., 83.66% for positive links in FN and 83.83% for negative links in FP
on Flights). Corrections made by our encoding scheme are less obvious on datasets whose CNRs
between positive and negative links are similar, which occurs in only 2 of 13 datasets. For US Legis.
and UN Vote, their CNRs between FN and FP are analogous (e.g., 69.92% vs. 62.13% on US Legis.),
weakening the advantage of our neighbor co-occurrence encoding scheme (e.g., only 31.63%/23.67%
of positive/negative links are corrected in FN/FP on US Legis.). Therefore, we conclude that the
neighbor co-occurrence encoding scheme helps DyGFormer capture common historical neighbors in
Su and Sv, and bring better results in most cases.

5.6  When Will DyGFormer Be a Good Choice?

Note that DyGFormer is superior to baselines by 1) exploring the source and destination nodes’
correlations from their historical sequences by neighbor co-occurrence encoding scheme; 2) using the
patching technique to attend longer histories. Thus, DyGFormer tends to perform better on datasets
that favor these two designs. We define Link Ratio (LR) as the ratio of links in their corresponding
positive or negative set, which can be computed by TP/(TP+FN), TN/(TN+FP), FN/(TP+FN), and
FP/(TN+FP). As a method with more TP and TN (i.e., fewer FN and FP) is better, we report the
results of LR and average CNR of links in TP and TN on five typical datasets in Table 4.


Table 4: LR and CNR of TP and TN with Table 5: LR and CNR of FP under random, historical,
random negative sampling strategy.        and inductive negative sampling strategy.
           LR (%)   CNR (%)                  LR(%)         CNR(%)
    Datasets                                 Datasets
~~~

## Body references

- [PDF p.9] Note that DyGFormer is superior to baselines by 1) exploring the source and destination nodes’ correlations from their historical sequences by neighbor co-occurrence encoding scheme; 2) using the patching technique to attend longer histories. Thus, DyGFormer tends to perform better on datasets that favor these two designs. We define Link Ratio (LR) as the ratio of links in their corresponding positive or negative set, which can be computed by TP/(TP+FN), TN/(TN+FP), FN/(TP+FN), and FP/(TN+FP). As a method with more TP and TN (i.e., fewer FN and FP) is better, we report the results of LR and average CNR of links in TP and TN on five typical datasets in Table 4.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
