# Visual inventory

> Text-only mode: inspect the generated text evidence; visual pixels remain unverified.

| ID | Label | PDF page | Caption | Candidate crop | Review |
|---|---|---:|---|---|---|
| figure-1-p002 | Figure 1 | 2 | Schematic diagram and summary of our contributions. | `not generated` | TEXT REVIEW REQUIRED |
| figure-2-p005 | Figure 2 | 5 | Limitations of TGNs. [Left] Temporal graph with nodes u, v that TGN-Att/TGAT cannot distinguish. Colors are node features, edge features are identical, and t3 > t2 > t1. [Center] TCTs of u and v are non-isomorphic. However, the attention layers of TGAT/TGN-Att compute weighted averages over a same multiset of values, returning identical messages for u and v. [Right] MP-TGNs fail to distinguish the events (u, v, t3) and (v, z, t3) as TCTs of z and u are isomorphic. Meanwhile, CAW cannot separate (u, z, t3) and (u0, z, t3): the 3-depth TCTs of u and u0 are not isomorphic, but the temporal walks from u and u0 have length 1, keeping CAW from capturing structural differences. | `not generated` | TEXT REVIEW REQUIRED |
| figure-3-p006 | Figure 3 | 6 | Examples of temporal graphs for which MP-TGNs cannot distinguish the diameter, girth, and number of cycles. | `not generated` | TEXT REVIEW REQUIRED |
| figure-3-p006 | Figure 3 | 6 | provides a construction for Proposition 7. The temporal graphs G(t) and G0(t) differ in diameter (1 vs. 3), girth (3 vs. 6), and number of cycles (2 vs. 1). By inspecting the TCTs, one can observe that, for any node in G(t), there is a corresponding one in G0(t) whose TCTs are isomorphic, e.g., Tu1(t) ⇠= Tu0 | `not generated` | TEXT REVIEW REQUIRED |
| figure-5-p007 | Figure 5 | 7 | PINT. Following the MP-TGN protocol, PINT updates memory states as events unroll. Meanwhile, we use Eqs. (7-11) to update positional features. To extract the embedding for node v, we build its TCT, annotate nodes with memory + positional features, and run (injective) MP. | `not generated` | TEXT REVIEW REQUIRED |
| figure-4-p007 | Figure 4 | 7 | The effect of (u, v, t) on the monotone TCT of v. Also, note how the positional features of a node i, relative to v, can be incrementally updated. | `not generated` | TEXT REVIEW REQUIRED |
| figure-6-p008 | Figure 6 | 8 | PINT cannot distinguish the events (u, v, t3) and (v, z, t3). | `not generated` | TEXT REVIEW REQUIRED |
| table-1-p009 | Table 1 | 9 | Average Precision (AP) results for link prediction. We denote the best-performing model (highest mean AP) in blue. In 5 out of 6 datasets, PINT achieves the highest AP in the transductive setting. For the inductive case, PINT outperforms previous MP-TGNs and competes with CAW. We also evaluate PINT w/ and w/o relative positional features. Adopting positional features leads to signiﬁcant performance gains. | `not generated` | TEXT REVIEW REQUIRED |
| figure-7-p009 | Figure 7 | 9 | Time comparison: PINT versus TGNs (in log- scale). The cost of pre-computing positional features is quickly diluted as the number of epochs increases. | `not generated` | TEXT REVIEW REQUIRED |
| table-2-p010 | Table 2 | 10 | Average precision results for TGN-Att + relative positional features. | `not generated` | TEXT REVIEW REQUIRED |
| figure-8-p010 | Figure 8 | 10 | PINT: AP (mean and std) as a function of the dimensionality of the positional features. | `not generated` | TEXT REVIEW REQUIRED |
