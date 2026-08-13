# Text evidence: Figure 11

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 10
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [44.0, 43.997, 302.514, 238.096]

## Caption

Figure 11: Replier classification scores for different data im- balance ratios.

## Text from suggested visual region

~~~text
Figure 11: Replier classification scores for different data im-
balance ratios.
~~~

## Body references

- [PDF p.9] test. Both analyses consistently shows that the similarity among replies is the most important attribute. To help in- terpret this finding, Fig. 10(A) compares the distributions of similarity attributes for replies by IO versus normal repliers. Replies by IO repliers are more similar to other replies to the same tweets, compared to those by normal repliers. This is a pattern that the classifier can exploit. We also observe in Fig. 10(B) that the downsampling process does not bias the similarity distributions. So far, we have tested the replier classifier on balanced datasets. In more realistic scenarios, the data may be imbal- anced with different ratios of coordinated and organic repli- ers. To test whether the classifier can generalize to such sce- narios, we train and test with 10-fold cross-validation using different positive to negative data ratios ranging from 1:5 to 1:45. Fig. 11 shows that precision and AUC are robust to class imbalance, whereas recall (and consequently F1) drops as the class imbalance increases. While this result indicates that balancing the classes affects recall, we also found that training on the original imbalanced dataset leads to a high false-positive rate and deteriorated precision. Next, we test the generalizability of the replier classifier by training and testing the model across different campaigns. Similarly to the tweet classifier, we prepare six campaign datasets: five selected based on the highest number of IO repliers and one by aggregating the remaining campaigns. In the diagonal of Table 7 we report F1 values when the

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
