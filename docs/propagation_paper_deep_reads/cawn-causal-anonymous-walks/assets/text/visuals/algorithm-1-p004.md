# Text evidence: Algorithm 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 4
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text
- **Suggested region:** [21.42, 29.255, 590.58, 341.149]

## Caption

Algorithm 1: Temporal Walk Extraction (E, α, M, m, w0, t0)

## Text from suggested visual region

~~~text
Published as a conference paper at ICLR 2021


  Algorithm 1: Temporal Walk Extraction (E, α, M, m, w0, t0)       The rule: “one node (e.g. u) interacts
                                                                                           with other nodes only if another node
1 Initialize M walks: Wi ←((w0, t0)), 1 ≤i ≤M ;                          interacts with this node at least twice.”
2 for j from 1 to m do                                                                                                                            𝑡3                                                                                                           𝑡1                                                                                                       a                                                                                       a         u                                                                                 u
3     for i from 1 to M do
4        (wp, tp) ←the last (node, time) pair in Wi;                       u   𝑡2  a         u  𝑡4  b
5       Sample one (e, t) ∈Ewp,tp with prob. ∝exp(α(t −tp))
         Denote e = {w′, w} and then Wi ←Wi ⊕(w′, t);            𝑢takes action   𝑢NOT takes action
                                                                Figure 4:  The correlation be-
6 Return {Wi|1 ≤i ≤M};                                        tween walks needs to be captured
                                                                                 to learn this law.

  Our CAW-N removes node identities and leverages relative node identities to avoid the issue in Fig. 3.
  Detailed explanations are given in Sec.4.2.

  Network-embedding approaches may also be applied to temporal networks (Zhou et al., 2018; Du
  et al., 2018; Mahdavi et al., 2018; Singer et al., 2019; Nguyen et al., 2018). However, they directly
  assign each node with a learnable vector. Therefore, they are not inductive and cannot digest attributes.

 3  PROBLEM FORMULATION AND NOTATIONS
  Problem Formulation. A temporal network can be represented as a sequence of links that come in
  over time, i.e. E = {(e1, t1), (e2, t2), ...} where ei is a link and ti is the timestamp showing when
  ei arrives. Each link ei corresponds to a dyadic event between two nodes {vi, ui}. For simplicity,
 we ﬁrst assume those links to be undirected and without attributes while later we discuss how to
            li  d        th d t  di    t d   tt ib  t d    t   k  Th                f li k     d       t   k
~~~

## Body references

- [No body reference recovered]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
