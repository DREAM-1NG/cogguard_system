# Text evidence: Figure 7

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 7
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [44.0, 198.624, 302.514, 249.055]

## Caption

Figure 7: Scores of tweet classifiers based on different thresholds for the number of IO replies received by targeted tweets.

## Text from suggested visual region

~~~text
Figure 7: Scores of tweet classifiers based on different
thresholds for the number of IO replies received by targeted
tweets.
~~~

## Body references

- [PDF p.3] First, we merge the datasets of all the IOs and keep all the replies by IO accounts to tweets by non-IO accounts. We refer to the latter accounts as targets and to the replies by IO accounts as IO replies. There are in total 17,873,714 IO replies from 44,425 IO accounts targeting 15,256,547 tweets by 1,763,084 distinct targets. From this data, we extract 15,016 targets and 96,041 tweets that received five or more direct replies from IO accounts. We assume these tweets have been targeted by coordinated reply attacks, and we la- bel them as targeted tweets. The threshold of five or more replies is arbitrary; a robustness analysis shows that the de- tection of targeted tweets does not seem to be affected by this parameter, as discussed later (Fig. 7). The targeted tweets can still be publicly available at the time of our analysis, allowing us to collect all of their replies. Some of these replies may have originated from non-IO repliers, both before and after the IO accounts were taken down by Twitter. We refer to these replies as normal replies and to their authors as normal repliers. Since we only have direct replies by IO accounts, we only consider direct replies by normal repliers as well; replies to replies are discarded. In addition to the metadata about the IO replies that are present in the initial data, we query the /users/:id, /search/all, and /tweets/?ids= endpoints of the Twitter API3 to collect metadata about the targets, the tar- geted tweets, their normal replies, and the normal repliers. We collected this information in April 2023. Among the 15,016 targets, 5,0

[TRUNCATED BY EXTRACTOR]
- [PDF p.7] whether tweet-level engagement features would provide suf- ficient signals to discriminate between targeted and control tweets. However, Table 3 indicates that tweet-level reply, like, and retweet counts do not provide very informative sig- nals for tweet classification. To further explore this question, let us measure the correlation between tweet-level features (reply count, retweet count, and like count) and the corresponding reply-level engagement counts. As each original tweet can have many replies, there are many more replies than original tweets. We therefore calculate the mean correlation between pairs of tweet/reply engage- ment features across 10 random samples of replies matching the number of original tweets. The correlations are all very small (around 0.001), confirming that reply engagement is not a mere reflection of tweet popularity. We previously defined targeted tweets as those that re- ceive five or more replies from IO accounts. Let us test the robustness of our classifier with respect to this definition by considering a range of threshold values between five and 20 replies from IO accounts. This filters down the set of tar- geted tweets and corresponding control tweets. We follow the same procedure described above to construct the classi- fication dataset, extract the features, and train and evaluate the classifier. Fig. 7 reports the mean precision, recall, F1, and AUC from 10-fold cross-validation. While we observe slight increases as the criterion for defining targeted tweets becomes more stringent, the results appear to be robust with respect to thi

[TRUNCATED BY EXTRACTOR]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
