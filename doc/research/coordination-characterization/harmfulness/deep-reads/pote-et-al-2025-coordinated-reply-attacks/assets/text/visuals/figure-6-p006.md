# Text evidence: Figure 6

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 6
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [129.051, 463.27, 568.015, 561.923]

## Caption

Figure 6: Permutation feature importance for tweet classi- fier. We report the median (orange line), 50% confidence in- terval (box), and 99.3% confidence interval (whiskers) of the drop in F1 score when each feature/attribute set is shuffled. Boxes with the same color indicate attributes in the same feature set. Larger values indicate higher importance.

## Text from suggested visual region

~~~text
al tweet-level features and reply-level fea-      Figure 6: Permutation feature importance for tweet classi-
ts using 10-fold cross-validation are given         fier. We report the median (orange line), 50% confidence in-
 , we performed a permutation feature im-       terval (box), and 99.3% confidence interval (whiskers) of the
 h measures the importance of features by      drop in F1 score when each feature/attribute set is shuffled.
 in accuracy when the values of those fea-     Boxes with the same color indicate attributes in the same
(permuted). To simplify the analysis, for       feature set. Larger values indicate higher importance.
 tribute we shuffled all the corresponding
~~~

## Body references

- [PDF p.6] Forest on individual tweet-level features and reply-level fea- ture sets. The results using 10-fold cross-validation are given in Table 3. Second, we performed a permutation feature im- portance test, which measures the importance of features by computing the loss in accuracy when the values of those fea- tures are shuffled (permuted). To simplify the analysis, for each reply-level attribute we shuffled all the corresponding features rather than each feature individually. For example, for the like count engagement attribute, we shuffled all 12 summary statistics features at once. We repeated this test 10 times and recorded the drop in mean F1 score from 10- fold cross-validation for each iteration. The distribution of these drop values is given in Fig. 6. Both approaches consistently show that reply-level en- gagement features are important. A classifier using only those features achieves F1=0.77 and AUC=0.84 (Table 3), and removing those features causes significant drops in F1 (Fig. 6). In our classification dataset, the majority of targets are from the Serbia campaign. IO accounts in this campaign were not intended to generate engagement with other Twit-

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
