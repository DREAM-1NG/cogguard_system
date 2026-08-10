# Text evidence: Table 8

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 23
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [63.226, 86.013, 512.833, 496.311]

## Caption

Table 8. Data mining and machine learning methods, based on supervised learning, for detecting coordinated behavior. For each group of works we report the input types, the machine learning approach, whether the method takes time into account, and the prediction target.

## Text from suggested visual region

~~~text
Table 8. Data mining and machine learning methods, based on supervised learning, for detecting coordinated behavior. For each
group of works we report the input types, the machine learning approach, whether the method takes time into account, and the
prediction target.

  reference     input                            machine learning approach                               time    target

  [156]           user activities                             representation learning, conditional embedding, neural encoding  Ë     user
  [40]           network, temporal, semantic features       outlier detection                      Ë     network
  [113]            text                                  peak detection, multiclass classification             Ë    community
  [108]           user activities                                   classifier                         Ë      user, target
  [83]           metadata, audio transcripts, thumbnails    ensemble classification                                                         target
  [4]             user activities                       random weighted walk                                               network
  [84]            co-retweet network                     graph neural network                                             community
  [57]           retweet                                  retrieval-augmented generation                                       network
  [88]           network, text                          graph neural network                                                      user


  Other works proposed simpler methods or indicators as signals of possible coordinated behavior. Bellutta and Carley

[12] analyze account creation times under the hypothesis that accounts involved in coordinated malicious activities

tend to be created in bursts. They computed the daily histogram of account creations to which they applied a burst

detection algorithm, identifying spikes in account creations by comparing the number of accounts created in a given

day against the average number of daily accounts created in a reference time window. Another simple unsupervised

technique is proposed in [126], where coordination is measured as the extent to which users converge—spontaneously

or in an organized fashion—on the use of certain hashtags. The Gini coefficient, an indicator of inequality, is applied to

the distribution of used hashtags to create time series where saddles close to 0—indicative of low inequality—correspond

to no coordination whereas peaks close to 1—indicative of a situation where all users use the same few hashtags—

correspond to strong coordination. Two alternative techniques are proposed in [79] and [80]. The former leverages

contrast pattern mining to extract anomalous behavior, while the latter uses convergent cross mapping to discover

cause-and-effect relationship and to construct an influence network. Similarly, [33, 34] use a discrete-time stochastic

model to analyze coordinated activity, representing the user behaviors as interacting Markov chains. In [56] social

media interactions are modeled as Petri nets, while in [154] coordination is detected by identifying anomalies in account

sharing behavior. In [127] an exploratory analysis is conducted on YouTube links shared on 4chan.

4.2.2  Supervised. Supervised methods can be categorized based on their prediction target, leading to approaches that
operate at the user, community, network, and target levels.
   User Zhang et al [156] tackles a binary classification task to distinguish between coordinated and non-coordinated
~~~

## Body references

- [PDF p.22] supervised techniques (see Table 8). These supervised approaches can be further distinguished by their prediction target,

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
