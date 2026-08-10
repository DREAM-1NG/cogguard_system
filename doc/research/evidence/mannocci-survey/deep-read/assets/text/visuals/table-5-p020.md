# Text evidence: Table 5

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 20
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [99.829, 86.131, 550.077, 494.973]

## Caption

Table 5. Network science methods for detecting coordinated behavior based on multiplex user networks, where each layer corresponds to a different co-action. For each group of works we report the considered co-actions, similarity functions, filtering criteria, and the optional flattening step applied before the community detection method.

## Text from suggested visual region

~~~text
Table 5. Network science methods for detecting coordinated behavior based on multiplex user networks, where each layer corresponds
to a different co-action. For each group of works we report the considered co-actions, similarity functions, filtering criteria, and the
optional flattening step applied before the community detection method.

  reference   action                       similarity                     filters†            flattening           community detection

  [32]          share, message, URL, hashtag   cardinality                    threshold, ADO                             Louvain, IPVC‡
   [29, 70]       retweet, tweet, URL, hashtag   cosine similarity TF-IDF      threshold, ADO    unweighted edge union
                retweet, URL, hashtag,         temporal weighted
  [52]                                                                                                               Generalized Leiden
              mention                         cardinality
  [48]          retweet, text, URL, reply        cardinality            EDO               multigraph             connected components
  [72]        URL, hashtag                   cardinality            EDO                                       multi-view clustering
  [73]        URL, hashtag, mention          cardinality            EDO                                       multi-view clustering
   [92, 94]     URL, hashtag, mention          cardinality            EDO            sum cardinality
             URL, hashtag, mention, reply,                                                                          Generalized Louvain,
  [81]                                        cosine similarity TF-IDF      threshold, EDO
               retweet                                                                                               Generalized Infomap
  [96]        URL, tweet                       cardinality, cosine similarity  threshold, EDO     unweighted edge union  Louvain

  † EDO: evenly distributed overlapping time window, ADO: action-driven overlapping time window. ‡ IPVC: iterative probabilistic voting consensus

includes a temporal decay weighting scheme that emphasizes the contribution of recent time windows over older ones.

Instead, Tardelli et al. [129] built a multiplex temporal network where the layers are obtained from a sequence of evenly

distributed overlapping time windows. Differently from all other approaches, the multiplex temporal network is then

analyzed as a whole. A further innovation is introduced in [95], which solves an optimization task to select the best

window size 𝑍in an overlapping time windows setting. Finally, we remark that the filtering methods discussed in this
section can be, and oftentimes are, used in combination for greater efficiency and to further reduce the network size

when analyzing very large datasets.


4.1.4  Community discovery. This step aims to detect a set of coordinated communities 𝑃= {𝑃1, . . . , 𝑃𝑛} via commu-
nity discovery on the coordination network. Multiplex networks are either flattened before performing community

discovery [145, 146] or an algorithm suitable for multiplex networks is used [74, 129].


   Implementation. Most of the works dealing with single layer networks carry out community discovery with Lou-
vain [16, 17, 26, 47, 59, 61, 62, 65, 90, 91, 95–97, 99, 140, 158], or more broadly via modularity clustering [18]. Other

recent works relied on Leiden [3, 98, 114, 129, 138]. Among the advantages of these approaches is their scalability,

which makes them suitable for the analysis of large networks. In addition, modularity clustering provides a hierarchical

community structure allowing for analyses at different levels of granularity The authors of [100 128] combined
~~~

## Body references

- [PDF p.15] The few existing works that built multiplex coordination networks are instead described in Table 5.
- [PDF p.21] The works presented in Table 5 performed community discovery on a multiplex coordination network. Some authors
- [PDF p.24] However, few studies considered multiple co-actions and built multiplex networks, as summarized in Table 5. Moreover,

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
