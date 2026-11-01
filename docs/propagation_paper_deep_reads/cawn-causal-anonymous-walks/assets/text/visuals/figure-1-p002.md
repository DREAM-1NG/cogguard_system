# Text evidence: Figure 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 2
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [98.0, 144.371, 513.999, 345.195]

## Caption

Figure 1: Triadic closure and feed-forward loops: Causal anonymous walks (CAW) capture the laws.

## Text from suggested visual region

~~~text
Figure 1: Triadic closure and feed-forward loops: Causal anonymous walks (CAW) capture the laws.


 A temporal graph with timestamped links and a             Example: three 3-step walks (𝑡𝑥, 𝑋are the default timestamp
  queried link at certain time:                               and the default node when no historical links can be found)
                        d                                                                                       8                                                                                            7                                                                                                   6                                                           6                                                                3                                                                      1                                                                                    v                                                                                                     e                                                                                                u            b                                                        u                                                              b                                                                            a                                                                                   c                                    3,9                                                                                                      b✓                     2                                         ✓                                            g                   3,6     0,3,8                                         9                                                                                                                         𝑡𝑥                                                                                       3                                                                                            2                                                           5                                                                3                                                                                    v                                                                      0                                                                                          d                                                                                                u                                                                  x                                                        u                                                                     c                                                        𝑆𝑢:                                                                                   a     𝑆𝑣:                                                      0,3,7                               ?   𝒗               𝑡= 10             𝒖                                                                    b✓             3  a
                                                                 0                                                                                                      v       1                    4, 5      7,9                                   8    4,8  h           u  3  b                                                                            a                                                                                      𝑡𝑥 x         v  9  g  7  h  4                                         ✓            c                                 e
 Backtrack m-step random walks over time before t=10:    Count number of 𝑏’s in different positions:
                                                                          0,     2,     1,    0 𝑇           0,     0,     0,    1 𝑇
   u  6  b  3   a  1   c     𝑀walks starting at 𝒖                                                  𝐼𝐶𝐴𝑊𝑏; 𝑆𝑢, 𝑆𝑣= 𝑔𝑏; 𝑆𝑢, 𝑔𝑏; 𝑆𝑣   (Relative node identity)
 …
                                               Anonymize  u  6  b  3  a  1   c    :
   v  8  e  7  u  6  b     𝑀walks starting at 𝒗                       6         3                                                 𝐼𝐶𝐴𝑊𝑢    𝐼𝐶𝐴𝑊𝑏   𝐼𝐶𝐴𝑊𝑎1 𝐼𝐶𝐴𝑊𝑐 …
         Causality Extraction                     Set-based Anonymization
~~~

## Body references

- [PDF p.2] Here we propose Causal Anonymous Walks (CAW) for modeling temporal networks. Our idea for inductive learning is inspired by the recent investigation on temporal network motifs that correspond to connected subgraphs with links that appear within a restricted time range (Kovanen et al., 2011; Paranjape et al., 2017). Temporal network motifs essentially reﬂect network dynamics: Both triadic closure and feed-forward control can be viewed as temporal network motifs evolving (Fig. 1); An inductive model should predict the 3rd link in both cases when it captures the correlation of these two links as they share a common node, while the model is agnostic to the node identities of these motifs.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
