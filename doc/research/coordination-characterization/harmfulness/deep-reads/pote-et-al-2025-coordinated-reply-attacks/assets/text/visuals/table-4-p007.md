# Text evidence: Table 4

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 7
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [309.5, 44.366, 568.015, 207.624]

## Caption

Table 4: F1 scores obtained from same-campaign (diago- nal entries, in bold) and cross-campaign evaluations of the tweet classifier. RS=Serbia, SA=Saudi Arabia, TR=Turkey, EG=Egypt. SA/EG/AE = Saudi Arabia/Egypt/Arab Emi- rates is a campaign involving three countries.

## Text from suggested visual region

~~~text
Test
 Train
           RS   SA   TR  EG   SA/EG/AE   Other
 RS          0.85   0.54   0.61   0.56      0.52      0.65
 SA          0.55   0.76   0.53   0.63      0.74      0.68
 TR          0.61   0.60   0.74   0.63      0.65      0.68
 EG          0.43   0.37   0.36   0.65      0.38      0.39
 SA/EG/AE   0.47   0.58   0.57   0.60      0.73      0.48
 Other        0.62   0.59   0.63   0.56      0.52     0 .74

Table 4: F1 scores obtained from same-campaign (diago-
nal entries, in bold) and cross-campaign evaluations of the
tweet classifier. RS=Serbia, SA=Saudi Arabia, TR=Turkey,
EG=Egypt. SA/EG/AE = Saudi Arabia/Egypt/Arab Emi-
rates is a campaign involving three countries.
~~~

## Body references

- [PDF p.7] whether tweet-level engagement features would provide suf- ficient signals to discriminate between targeted and control tweets. However, Table 3 indicates that tweet-level reply, like, and retweet counts do not provide very informative sig- nals for tweet classification. To further explore this question, let us measure the correlation between tweet-level features (reply count, retweet count, and like count) and the corresponding reply-level engagement counts. As each original tweet can have many replies, there are many more replies than original tweets. We therefore calculate the mean correlation between pairs of tweet/reply engage- ment features across 10 random samples of replies matching the number of original tweets. The correlations are all very small (around 0.001), confirming that reply engagement is not a mere reflection of tweet popularity. We previously defined targeted tweets as those that re- ceive five or more replies from IO accounts. Let us test the robustness of our classifier with respect to this definition by considering a range of threshold values between five and 20 replies from IO accounts. This filters down the set of tar- geted tweets and corresponding control tweets. We follow the same procedure described above to construct the classi- fication dataset, extract the features, and train and evaluate the classifier. Fig. 7 reports the mean precision, recall, F1, and AUC from 10-fold cross-validation. While we observe slight increases as the criterion for defining targeted tweets becomes more stringent, the results appear to be robust with respect to thi

[TRUNCATED BY EXTRACTOR]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
