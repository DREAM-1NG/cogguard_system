# Text evidence: Figure 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 3
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [41.024, 41.024, 571.306, 186.127]

## Caption

Figure 1: Data collection strategy.

## Text from suggested visual region

~~~text
Previous research
     datasets

 DeBot (from API)              Twitter                   User          Proﬁle                                   Full        Sub-Sampling
                         User IDs                   Proﬁles       Features                          Dataset
 Public Research
                                                                                   General user    Datasets
                                                                                               features
 Journalist attack                                                                                  (30)
    Datasets                                       User          Tweet
Real User Dataset                                  Tweets        Features                               Dataset         Dataset
  (Through BFS)                                                                         C30K          C500
                                         Twitter API

                                            Figure 1: Data collection strategy.
~~~

## Body references

- [PDF p.2] Two datasets were compiled for this paper. First, a botnet dataset that contains the aggregated content generated from a variety of bot datasets (some previously used in research as ground truth [11, 12, 21]) and, second, a real-user dataset. Each dataset includes the information available from the user’s proﬁle, and all the retrievable tweets at collection time in accordance to Twitter’s API limitations. This means that each account in our dataset contains a maximum of 3,200 tweets authored or retweeted by that account. The way these datasets were ﬁnally constructed is illustrated in Fig. 1.
- [PDF p.5] This section describes the features to be used in our classiﬁer. Most of these features have been used in research before and are relatively common place. We placed speciﬁc importance on not including graph information. Twitter imposes strong rate limits on graph information, making it very time consum- ing to collect the followers of a popular user (e.g., a celebrity or politician) from Twitter’s API. Additionally, any real time implementation of this classiﬁer would need to depend on a few API calls, which does not bode well with the inclusion of graph information. Table 2 shows all the features that are used in the classiﬁers analysed in this paper. Also, the way the datasets at hand were ﬁnally prepared for feature extraction is illustrated in Fig. 1. Next, we deﬁne some of the features that might not be straight forward.
- [PDF p.6] Dataset with class size = 500 Dataset C30K is still quite im- balanced, having classes with 30,000 bots and classes with 26 bots. To measure the effect of bot classes without being biased by their size, we create another bot dataset. This balanced sub-sampled bot dataset contains 500 random instances from each of the bot classes that have over 500 accounts in them. This means a few of the bot datasets have been excluded, but choosing 500 as the size still allows us to have 14 bot datasets to evaluate on. This bot dataset is made of 7,000 bot instances. To contrast against this bot dataset, we add an equivalent number of users from our user dataset. The aggregation of both of these datasets will be referred to as the dataset with class size = 500, or C500. Please note that this dataset is created on the ﬂy every time it is needed. Fig. 1 shows the data collection

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
