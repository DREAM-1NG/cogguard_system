# Text evidence: Table 2

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 16
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [99.874, 86.084, 548.562, 475.965]

## Caption

Table 2. Network science methods for detecting coordinated behavior based on single layer user networks. For each group of works we report the considered co-actions, similarity functions, filtering criteria, and community detection methods.

## Text from suggested visual region

~~~text
Table 2. Network science methods for detecting coordinated behavior based on single layer user networks. For each group of works
we report the considered co-actions, similarity functions, filtering criteria, and community detection methods.

           reference             action                              similarity                     filters†            community detection

             [18]                   retweet                                 cardinality                    threshold, ADJ        modularity clustering
             [47]                   retweet                                 cardinality             EDO                Louvain
              [61, 62]                retweet                                 cardinality                    threshold, ADO       Louvain
             [65]                   retweet                                 cardinality                  backbone, ADJ        Louvain
             [115]                  retweet                                 cardinality             EDO
              [19, 30, 51, 66, 100, 128]  retweet                               cosine similarity TF-IDF      backbone            Louvain
              [114, 129]              retweet                               cosine similarity TF-IDF      backbone, EDO        Leiden
             [144]                  retweet                                 cardinality                    threshold, ADJ
                                                                      kNN graph,
              [8]                     retweet                               cosine similarity                        HDBSCAN
                                                                                                              correlation
                                                                                                                          Louvain, connected
             [17]                     retweet, tweet                          cardinality                    threshold, EDO
                                                                                                             components
             [59]                     retweet, tweet                          cardinality                    threshold, EDO       Louvain
             [116]                    retweet, tweet                          cardinality                    threshold, EDO
             [13]                   tweet                                 cosine similarity              threshold, EDO
             [28]                   tweet                                   cardinality            ADO
             [64]                   tweet                                   cardinality                   threshold              cohesive campaign
             [102]                  tweet                                    text similarity                 threshold, ADO
             [98]                    parley                                  cardinality                    threshold, kNN graph  Leiden
             [140]                     text                                     cardinality                 backbone            Louvain
                                                                                                              threshold, kNN graph,
             [149]                  tweet
                                                                ADO
             [96]                     tweet, URL                              cardinality,cosine similarity   threshold, EDO       Louvain
                                                                                  text similarity, cardinality,
             [97]                     tweet, parley, URL, username                                          threshold, kNN graph  Louvain
                                                                          cosine similarity
                                                                           cosine similarity TF-IDF, text
             [70]                     retweet, tweet, URL, hashtag                                          threshold, ADO
                                                                                 similarity
                                      retweet, tweet, URL, hashtag, fast
             [104]                                                         cosine similarity TF-IDF    ADO (fast retweet)    connected components
                                   retweet
              [145, 146]               retweet, URL, hashtag, mention, reply  cardinality              ADJ                     focal structures
             [138]                    retweet, tweet, URL, hashtag, mention  cosine similarity TF-IDF     ADJ                  Leiden
                                      retweet, hashtag, image, handle        Jaccard coefficient,
             [103]                                                                                           threshold, EDO
                                   change, synchronization                 cardinality, cosine similarity
             [27]                     retweet, tweet, image, synchronization  cosine similarity TF-IDF      threshold            Louvain
                                                                   Normalized Compression
             [67]                      interaction, text, synchronization                        kNN graph
                                                                        Distance
                                            text, synchronization, hashtag, URL,
             [71]                                                          cosine similarity TF-IDF      threshold             connected components
                                       duet, stitch, reply
                                     hashtag, URL, video description,
             [148]                                                             cardinality             kNN graph           connected components
                                    music, audio
             [20]              URL                                  cosine similarity TF-IDF       threshold, EDO        connected components
             [16]              URL                                    cardinality             kNN graph           Louvain
              [14, 41, 43, 44, 49, 110,
                          URL                                    cardinality                    threshold, ADO       connected components
             112, 122]
             [150]              URL                                    cardinality
~~~

## Body references

- [PDF p.15] are single-layered. Table 2 reports the main implementation details for the works that built single layer coordination
- [PDF p.15] As shown in Table 2, the most common type of co-action is co-sharing (e.g., the co-retweet action on Twitter/X) [8, 17–

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
