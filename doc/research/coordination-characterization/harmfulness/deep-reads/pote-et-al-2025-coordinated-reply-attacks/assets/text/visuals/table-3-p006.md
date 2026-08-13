# Text evidence: Table 3

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 6
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [44.0, 308.585, 302.514, 472.27]

## Caption

Table 3: Contributions of different tweet-level features and reply-level feature sets to the Random Forest tweet classifier. The last row (using all features) corresponds to the results in Table 2.

## Text from suggested visual region

~~~text
Features set         Prec.   Rec.   F1  AUC
     reply count       0.5    0.99   0.67   0.59
     retweet count    0.49    1     0.66   0.54
     like count        0.49    1     0.66   0.52
      Engagement         0.69    0.86   0.77   0.84
        Entities              0.52    0.95   0.67   0.65
      Delay               0.51    0.96   0.67   0.66
       Similarity            0.54    0.96   0.69   0.68
       All features          0.73    0.87   0.80   0.88

Table 3: Contributions of different tweet-level features and
reply-level feature sets to the Random Forest tweet classifier.
The last row (using all features) corresponds to the results in
Table 2.
~~~

## Body references

- [PDF p.6] Forest on individual tweet-level features and reply-level fea- ture sets. The results using 10-fold cross-validation are given in Table 3. Second, we performed a permutation feature im- portance test, which measures the importance of features by computing the loss in accuracy when the values of those fea- tures are shuffled (permuted). To simplify the analysis, for each reply-level attribute we shuffled all the corresponding features rather than each feature individually. For example, for the like count engagement attribute, we shuffled all 12 summary statistics features at once. We repeated this test 10 times and recorded the drop in mean F1 score from 10- fold cross-validation for each iteration. The distribution of these drop values is given in Fig. 6. Both approaches consistently show that reply-level en- gagement features are important. A classifier using only those features achieves F1=0.77 and AUC=0.84 (Table 3), and removing those features causes significant drops in F1 (Fig. 6). In our classification dataset, the majority of targets are from the Serbia campaign. IO accounts in this campaign were not intended to generate engagement with other Twit-
- [PDF p.7] whether tweet-level engagement features would provide suf- ficient signals to discriminate between targeted and control tweets. However, Table 3 indicates that tweet-level reply, like, and retweet counts do not provide very informative sig- nals for tweet classification. To further explore this question, let us measure the correlation between tweet-level features (reply count, retweet count, and like count) and the corresponding reply-level engagement counts. As each original tweet can have many replies, there are many more replies than original tweets. We therefore calculate the mean correlation between pairs of tweet/reply engage- ment features across 10 random samples of replies matching the number of original tweets. The correlations are all very small (around 0.001), confirming that reply engagement is not a mere reflection of tweet popularity. We previously defined targeted tweets as those that re- ceive five or more replies from IO accounts. Let us test the robustness of our classifier with respect to this definition by considering a range of threshold values between five and 20 replies from IO accounts. This filters down the set of tar- geted tweets and corresponding control tweets. We follow the same procedure described above to construct the classi- fication dataset, extract the features, and train and evaluate the classifier. Fig. 7 reports the mean precision, recall, F1, and AUC from 10-fold cross-validation. While we observe slight increases as the criterion for defining targeted tweets becomes more stringent, the results appear to be robust with respect to thi

[TRUNCATED BY EXTRACTOR]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
