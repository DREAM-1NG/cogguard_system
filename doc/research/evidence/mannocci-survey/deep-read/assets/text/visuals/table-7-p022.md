# Text evidence: Table 7

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 22
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [99.892, 86.057, 549.55, 483.075]

## Caption

Table 7. Data mining and machine learning methods, based on unsupervised learning for detecting coordinated behavior. For each group of works we report the input types, the machine learning approach, and whether the method takes time into account.

## Text from suggested visual region

~~~text
Table 7. Data mining and machine learning methods, based on unsupervised learning for detecting coordinated behavior. For each
group of works we report the input types, the machine learning approach, and whether the method takes time into account.

        reference     input                            machine learning approach                               time

           [6, 7, 107, 124]   text streams                                  text stream clustering                    Ë
         [123]            text streams, image captions                 text stream clustering                    Ë
         [11]              text, user-content network                  clustering of text and node embeddings             Ë
         [58]             daily tweeting activity                    expectation-maximization                  Ë
         [126]          hashtags                              peak detection                       Ë
         [12]           account creation timestamps               burst detection                       Ë
         [79]            user activities                              contrast pattern mining                   Ë
         [80]            user activities                           convergent cross mapping                  Ë
          [33, 34]       URL, hashtag, image, mention            networked Markov chains                  Ë
         [118]           user activities                           temporal point processes, gaussian mixture models        Ë
         [155]           user activities                           temporal point processes, expectation-maximization        Ë
         [56]            user activities                                Petri net                         Ë
         [154]           user activities                                outlier detection                      Ë
         [55]              text, posting time                            text similarity, timings of campaign launch and posting tweets   Ë
         [120]          hashtags                               bayesan model
         [136]           user activities                                cluster interactions networks
         [63]          mention                                     cluster interactions networks


identifying groups of users exhibiting similar behaviors, while others rely on the availability of labeled data and apply
supervised techniques (see Table 8). These supervised approaches can be further distinguished by their prediction target,
namely user (individual account classification), community (groups of users), network (entire interaction graphs), target
(entities targeted by coordinated actions).

4.2.1  Unsupervised. Unsupervised methods work with unlabelled data and, therefore, do not exploit any knowledge
on the membership of users to coordinated groups. Multiple unsupervised methods [6, 7, 107, 123, 124] are based on

stream clustering algorithms, designed to group similar textual documents into micro-clusters that represent the topics

recently discussed in the stream. The detection of rapidly growing clusters of documents is used to identify inorganic or

orchestrated campaigns by coordinated users. This approach is conceptually similar to the analysis of a content network

of similar documents that includes a time-based filter. A similar approach is also used in [11], where text and node

embeddings are clustered via DBSCAN. In [120], hashtags used by different users are leveraged to perform clustering

via a Bayesian model In contrast [63 136] apply clustering on interaction networks such as the mention network [63]
~~~

## Body references

- [PDF p.21] In terms of machine learning techniques, some works leverage unsupervised approaches (see Table 7) and focus on

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
