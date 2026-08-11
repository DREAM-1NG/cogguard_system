# Text evidence: Algorithm 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 5
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [21.42, 211.504, 590.58, 577.311]

## Caption

Algorithm 1: Coordination-aware community de- tection. We perform the community detection iter- atively at increasing coordination levels, exposing how communities’ structure and properties change when imposing increasingly restrictive similarity thresholds.

## Text from suggested visual region

~~~text
11      initialize community detection with Ci−1
   12    Ci = perform community detection on Ge,vi
   13     append Ci to C                      // trace evolving communities
   14      i = i + 1
   15 end
   16 return C                                                                             labour                                           conservative
  Algorithm 1: Coordination-aware community de-
                                                             Figure 2: The ﬁltered user similarity network of the 2019
   tection. We perform the community detection iter-
                                     UK GE. Nodes represent users involved in the online de-
   atively at increasing coordination levels, exposing
                                                                      bate, while edges weight according to the similarity strength
  how communities’ structure and properties change
                                                        between one another, as deﬁned in Step 2. Users are colored
  when imposing increasingly restrictive similarity
                                                             according to their political leaning, inferred from the polar-
   thresholds.
                                                                            ity of the hashtags they used, computed using label propaga-
                                                                          tion.

framework to uncover and characterize possible coordinated
behaviors affecting the 2019 UK General Election. Then, we
demonstrate the beneﬁts of our new framework by compar-      puted user similarities as the cosine similarity of user vec-
ing its ﬁndings with those obtained by applying a threshold-        tors. Before studying the network, we applied the technique
based approach.                                            proposed in (Serrano, Bogun´a, and Vespignani 2009) to re-
                                                                       tain only statistically-relevant edges, thus obtaining the mul-
    Surfacing coordination in 2019 UK GE             tiscale backbone of our network, which we exploited for
                                                                 the remaining analyses. The resulting ﬁltered user similar-In the following, we describe how we implemented and ap-
                                                                            ity network contains 276,775 edges and is shown in Fig-plied the aforementioned framework to uncover coordinated
                                                               ure 2. In addition, Figure 3 shows the distribution of edgebehaviors on Twitter related to the 2019 UK GE. This sec-
                                                            weights in the ﬁltered network. The ﬁltering step preservedtion’s content roughly corresponds to steps 1 to 5 of our
                                                                 the rich, multiscale nature of the network, as opposed to ﬁl-methodology, while the next section describes step 6 (i.e.,
                                                                     tering based on a ﬁxed threshold.analysis of coordinated communities).
  User similarity network. For our analysis, we focused          Political leaning. In Figure 2, nodes are colored based
on the activity of superspreaders – coarsely deﬁned as the     on their political leaning, as inferred from the hashtags that
most inﬂuential spreaders of information, including mis-      they used. In particular, we employed a label propagation
and disinformation, in online social media (Pei et al. 2014).      algorithm for assigning a polarity score to each hashtag in
Here, we deﬁned superspreaders as the top 1% of users that      our dataset. In detail,  it is a modiﬁed version of the so-
shared more retweets. This deﬁnition resulted in the selec-       called valence score, a simple, standard, well-known method
tion of 10 782 users for our analysis Despite representing      from literature adopted in many studies before (Wang et al
~~~

## Body references

- [PDF p.4] more nuanced approach for surfacing coordinated be- haviors. As such, we base our approach on an iterative process that examines increasing coordination levels, as shown in Algorithm 1. We begin by performing com- munity detection on the ﬁltered network resulting from step 4, identifying the set C0 of communities. Then, we apply an increasingly restrictive similarity threshold ti to edge weights at each iteration, thus removing certain edges and disconnected nodes. We repeat community de- tection on the obtained subnetwork Ge,v i . At each itera- tion, the community detection algorithm is initialized with the set of communities Ci−1 found at the previous itera- tion. This process guarantees that the starting communi- ties are kept, to a certain extent5, throughout all the pro- cess. As a result of the “moving” threshold, we are able to study how the structure and the properties of coordi- nated communities change across the whole spectrum of coordination. Moreover, the moving threshold implicitly deﬁnes a measure for the extent of coordination observed at each iteration, that is for each obtained subnetwork.
- [PDF p.6] analyze the communities’ characteristics at different levels of coordination, as opposed to cutting at a predetermined, ﬁxed threshold, which would exclude almost the entire net- work from the subsequent analysis. In detail, we carried out the analysis by applying community detection and the well- known Louvain algorithm (Blondel et al. 2008). This step in our analysis corresponds to line 1 of Algorithm 1. Detected communities (resolution = 1.5, minimum size at t0 = 20) are outlined in Figure 4 and are brieﬂy described in the following. Users exhibiting higher coordination with other users are assigned darker shades of color. For each commu- nity, we also computed its TF-IDF weighted hashtag cloud, as shown in Figure 5, to highlight the debated topics.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
