# Text evidence: Figure 2

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 5
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [97.512, 62.647, 515.243, 215.13]

## Caption

Figure 2: Limitations of TGNs. [Left] Temporal graph with nodes u, v that TGN-Att/TGAT cannot distinguish. Colors are node features, edge features are identical, and t3 > t2 > t1. [Center] TCTs of u and v are non-isomorphic. However, the attention layers of TGAT/TGN-Att compute weighted averages over a same multiset of values, returning identical messages for u and v. [Right] MP-TGNs fail to distinguish the events (u, v, t3) and (v, z, t3) as TCTs of z and u are isomorphic. Meanwhile, CAW cannot separate (u, z, t3) and (u0, z, t3): the 3-depth TCTs of u and u0 are not isomorphic, but the temporal walks from u and u0 have length 1, keeping CAW from capturing structural differences.

## Text from suggested visual region

~~~text
Figure 2: Limitations of TGNs. [Left] Temporal graph with nodes u, v that TGN-Att/TGAT cannot
distinguish. Colors are node features, edge features are identical, and t3 > t2 > t1. [Center] TCTs
of u and v are non-isomorphic. However, the attention layers of TGAT/TGN-Att compute weighted
averages over a same multiset of values, returning identical messages for u and v. [Right] MP-TGNs
fail to distinguish the events (u, v, t3) and (v, z, t3) as TCTs of z and u are isomorphic. Meanwhile,
CAW cannot separate (u, z, t3) and (u0, z, t3): the 3-depth TCTs of u and u0 are not isomorphic, but
the temporal walks from u and u0 have length 1, keeping CAW from capturing structural differences.
~~~

## Body references

- [PDF p.5] The MP-TGN framework is rather general and subsumes many modern methods for temporal graphs [e.g., 16, 32, 42]. We now analyze the theoretical limitations of two concrete instances of MP-TGNs: TGAT [42] and TGN-Att [27]. Remarkably, these models are among the best-performing MP-TGNs. Nonetheless, we can show that there are nodes of very simple temporal graphs that TGAT and TGN-Att cannot distinguish (see Figure 2). We formalize this in Proposition 4 by establishing that there are cases in which TGNs with injective layers can succeed, but TGAT and TGN-Att cannot.
- [PDF p.5] We can extend the notion of node distinguishability to edges/events. We say that a model distinguishes two synchronous events γ = (u, v, t) and γ0 = (u0, v0, t) of a temporal graph if it assigns different edge embeddings hγ 6= hγ0 for γ and γ0. Proposition 5 asserts that CAWs are not strictly more expressive than MP-TGNs, and vice-versa. Intuitively, CAW’s advantage over MP-TGNs lies in its ability to exploit node identities and capture correlation between walks. However, CAW imposes temporal constraints on random walks, i.e., walks have timestamps in decreasing order, which can limit its ability to distinguish events. Figure 2(Right) sketches constructions for Proposition 5.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
