# Text evidence: Figure 2

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 2
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [94.375, 165.249, 518.419, 368.962]

## Caption

Figure 2: Causal anonymous walks (CAW): causality extraction and set-based anonymization.

## Text from suggested visual region

~~~text
A temporal graph with timestamped links and a             Example: three 3-step walks (𝑡𝑥, 𝑋are the default timestamp
 queried link at certain time:                               and the default node when no historical links can be found)
                       d                                                                                      8                                                                                            7                                                                                                  6                                                          6                                                                3                                                                      1                                                                                   v                                                                                                    e                                                                                               u           b                                                       u                                                             b                                                                           a                                                                                  c                                    3,9                                                                                                     b✓                    2                                         ✓                                            g                  3,6    0,3,8                                         9                                                                                                                        𝑡𝑥                                                                                      3                                                                                            2                                                          5                                                                3                                                                                   v                                                                      0                                                                                         d                                                                                               u                                                                 x                                                       u                                                                     c                                                       𝑆𝑢:                                                                                  a     𝑆𝑣:                                                     0,3,7                              ?   𝒗              𝑡= 10            𝒖                                                                   b✓            3 a
                                                                0                                                                                                     v      1                   4, 5      7,9                                  8    4,8  h           u  3  b                                                                           a                                                                                     𝑡𝑥 x         v  9  g  7  h  4                                         ✓           c                                e
Backtrack m-step random walks over time before t=10:    Count number of 𝑏’s in different positions:
                                                                         0,     2,     1,    0 𝑇           0,     0,     0,    1 𝑇
  u  6  b  3   a  1   c     𝑀walks starting at 𝒖                                                  𝐼𝐶𝐴𝑊𝑏; 𝑆𝑢, 𝑆𝑣= 𝑔𝑏; 𝑆𝑢, 𝑔𝑏; 𝑆𝑣   (Relative node identity)
 …
                                              Anonymize  u  6  b  3  a  1   c    :
  v  8  e  7  u  6  b     𝑀walks starting at 𝒗                       6         3                                                 𝐼𝐶𝐴𝑊𝑢    𝐼𝐶𝐴𝑊𝑏   𝐼𝐶𝐴𝑊𝑎1 𝐼𝐶𝐴𝑊𝑐 …
         Causality Extraction                     Set-based Anonymization

  Figure 2: Causal anonymous walks (CAW): causality extraction and set-based anonymization.
~~~

## Body references

- [PDF p.2] Our CAW model has two important properties (Fig. 2): (1) Causality extraction — a CAW starts from a link of interest and backtracks several adjacent links over time to encode the underlying causality of network dynamics. Each walk essentially gives a temporal network motif; (2) Set-based anonymization — CAWs remove the node identities over the walks to guarantee inductive learning while encoding relative node identities based on the counts that they appear at a certain position according to a set of sampled walks. Relative node identities guarantee that the structures of motifs and their correlations are still kept after removing node identities. To predict temporal links between two nodes of interest, we propose a model CAW-Network (CAW-N) that samples a few CAWs related to the two nodes of interest, encodes and aggregates these CAWs via RNNs (Rumelhart et al., 1986) and set-pooling respectively to make the prediction.
- [PDF p.5] 4.2 CAUSAL ANONYMOUS WALK We propose CAW that shares the high-level concept with AW to remove the original node identities. However, CAW has a different causal sampling strategy and a novel set-based approach for node anonymization, which are speciﬁcally designed to encode temporal network dynamics (Fig. 2).
- [PDF p.20] First, we deﬁne the shapes of walks based on ICAW . Recall from Eq. 3 that g(w, Su) encodes the number of times node w that appears in different walk positions w.r.t source node u. This encoding induces a temporal shortest-path distance duw between node w and u: duw ≜min{i|g(w, Su)[i] > 0}. Note that in temporal networks, there is not a canonical way to deﬁne shortest-path distance between two nodes as there is no static structures. So our deﬁnition duw can be viewed the shortest- path distance between u and w over the subgraph that consists of walks in Su. Based on the way to deﬁne (duw, dvw), we introduce the mapping from ICAW of the node w to a coordinate of this node in the subgraph that consists of walks in Su ∩Sv: (g(w, Su), g(w, Sv)) −→coor(w; u, v) = (duw, dvw). This cooredinate can be viewed as a relative coordinate of node w w.r.t. the source nodes u, v. Each walk W ∈Su ∪Sv can then represented as a sequence of such coordinates by mapping each node’s ICAW to a coordinate. The obtained sequence can be viewed as a shape of W and we denote the obtained shape as sCAW (W). For instance, in the toy example shown by Fig. 2 right, the ﬁrst CAW in Su, u −→b −→a −→c is mapped to a new coordinate sequence (0, 2) −→(1, 2) −→(2, ∞) −→(3, ∞). The ∞marks the setting that node a, c do not appear in Sv.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
