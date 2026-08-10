# Text-only visual evidence ledger

> Extracted text is not visual verification. Do not infer unreported axes, colors, curves, panels, layout, or crop completeness.

## Figure 1

- **PDF page:** 2
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-1-p002.md](text/visuals/figure-1-p002.md)
- **Caption:** Figure 1: Schematic diagram and summary of our contributions.

## Figure 2

- **PDF page:** 5
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-2-p005.md](text/visuals/figure-2-p005.md)
- **Caption:** Figure 2: Limitations of TGNs. [Left] Temporal graph with nodes u, v that TGN-Att/TGAT cannot distinguish. Colors are node features, edge features are identical, and t3 > t2 > t1. [Center] TCTs of u and v are non-isomorphic. However, the attention layers of TGAT/TGN-Att compute weighted averages over a same multiset of values, returning identical messages for u and v. [Right] MP-TGNs fail to distinguish the events (u, v, t3) and (v, z, t3) as TCTs of z and u are isomorphic. Meanwhile, CAW cannot separate (u, z, t3) and (u0, z, t3): the 3-depth TCTs of u and u0 are not isomorphic, but the temporal walks from u and u0 have length 1, keeping CAW from capturing structural differences.

## Figure 3

- **PDF page:** 6
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [figure-3-p006.md](text/visuals/figure-3-p006.md)
- **Caption:** Figure 3: Examples of temporal graphs for which MP-TGNs cannot distinguish the diameter, girth, and number of cycles.

## Figure 3

- **PDF page:** 6
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [figure-3-p006.md](text/visuals/figure-3-p006.md)
- **Caption:** Figure 3 provides a construction for Proposition 7. The temporal graphs G(t) and G0(t) differ in diameter (1 vs. 3), girth (3 vs. 6), and number of cycles (2 vs. 1). By inspecting the TCTs, one can observe that, for any node in G(t), there is a corresponding one in G0(t) whose TCTs are isomorphic, e.g., Tu1(t) ⇠= Tu0

## Figure 5

- **PDF page:** 7
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-5-p007.md](text/visuals/figure-5-p007.md)
- **Caption:** Figure 5: PINT. Following the MP-TGN protocol, PINT updates memory states as events unroll. Meanwhile, we use Eqs. (7-11) to update positional features. To extract the embedding for node v, we build its TCT, annotate nodes with memory + positional features, and run (injective) MP.

## Figure 4

- **PDF page:** 7
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-4-p007.md](text/visuals/figure-4-p007.md)
- **Caption:** Figure 4: The effect of (u, v, t) on the monotone TCT of v. Also, note how the positional features of a node i, relative to v, can be incrementally updated.

## Figure 6

- **PDF page:** 8
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-6-p008.md](text/visuals/figure-6-p008.md)
- **Caption:** Figure 6: PINT cannot distinguish the events (u, v, t3) and (v, z, t3).

## Table 1

- **PDF page:** 9
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [table-1-p009.md](text/visuals/table-1-p009.md)
- **Caption:** Table 1: Average Precision (AP) results for link prediction. We denote the best-performing model (highest mean AP) in blue. In 5 out of 6 datasets, PINT achieves the highest AP in the transductive setting. For the inductive case, PINT outperforms previous MP-TGNs and competes with CAW. We also evaluate PINT w/ and w/o relative positional features. Adopting positional features leads to signiﬁcant performance gains.

## Figure 7

- **PDF page:** 9
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-7-p009.md](text/visuals/figure-7-p009.md)
- **Caption:** Figure 7: Time comparison: PINT versus TGNs (in log- scale). The cost of pre-computing positional features is quickly diluted as the number of epochs increases.

## Table 2

- **PDF page:** 10
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [table-2-p010.md](text/visuals/table-2-p010.md)
- **Caption:** Table 2: Average precision results for TGN-Att + relative positional features.

## Figure 8

- **PDF page:** 10
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-8-p010.md](text/visuals/figure-8-p010.md)
- **Caption:** Figure 8: PINT: AP (mean and std) as a function of the dimensionality of the positional features.
