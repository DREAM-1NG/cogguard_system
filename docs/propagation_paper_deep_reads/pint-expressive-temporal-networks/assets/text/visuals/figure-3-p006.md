# Text evidence: Figure 3

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 6
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text
- **Suggested region:** [21.42, 0.0, 590.58, 398.939]

## Caption

Figure 3 provides a construction for Proposition 7. The temporal graphs G(t) and G0(t) differ in diameter (1 vs. 3), girth (3 vs. 6), and number of cycles (2 vs. 1). By inspecting the TCTs, one can observe that, for any node in G(t), there is a corresponding one in G0(t) whose TCTs are isomorphic, e.g., Tu1(t) ⇠= Tu0

## Text from suggested visual region

~~~text
Initialization: The colors of all nodes in G(t) are initialized using the initial node features: 8v 2
      V (G(t)), c0(v) = xv. If node features are not available, all nodes receive identical colors;  Reﬁnement: At step `, the colors of all nodes are reﬁned using a hash (injective) function: for all
       v 2 V (G(t)), we apply c`+1(v) = HASH(c`(v), {{(c`(u), euv(t0), t0) : (u, v, t0) 2 G(t)}});  Termination: The test is carried out for two temporal graphs at time t in parallel and stops when
        the multisets of corresponding colors diverge, returning non-isomorphic. If the algorithm
        runs until the number of different colors stops increasing, the test is deemed inconclusive.
We note that the temporal WL test trivially reduces to the standard 1-WL test if all timestamps and
edge features are identical. The resemblance between MP-TGNs and GNNs and their corresponding
WL tests suggests that the power of MP-TGNs is bounded by the temporal WL test. Proposition 6
conveys that MP-TGNs with injective layers are as powerful as the temporal WL test.
Proposition 6. Assume ﬁnite spaces of initial node features X, edge features E, and timestamps T .Let the number of events of any temporal graph be bounded by a ﬁxed constant. Then, there is an
MP-TGN with suitable parameters using injective aggregation/update functions that outputs different
representations for two temporal graphs if and only if the temporal-WL test outputs ‘non-isomorphic’.
A natural consequence of the limited power of MP-TGNs is that even the most powerful MP-TGNs
fail to distinguish relevant graph properties, and the same applies to CAWs (see Proposition 7).
Proposition 7. There exist non-isomorphic temporal graphs differing in properties such as diameter,
girth, and total number of cycles, which cannot be differentiated by MP-TGNs and CAWs.
Figure 3 provides a construction for Proposition 7.
The temporal graphs G(t) and G0(t) differ in diameter
(1 vs. 3), girth (3 vs. 6), and number of cycles (2vs. 1). By inspecting the TCTs, one can observe that,
for any node in G(t), there is a corresponding one                                                                      3: Examples                                                                              of temporal                                                                                    graphs                                                                                                       for whichin       whose           TCTs                     are                        isomorphic,                                             e.g., Tu1(t)                                                    ⇠=   Figure   G0(t)                                        MP-TGNs                                                                cannot distinguish                                                                                        the                                                                                           diameter,                                                                                                                    girth,             As                    a result,                              the multisets                                          of node            t > t3.Tu0   1(t) for
embeddings for these temporal graphs are identical.  and number of cycles.
~~~

## Body references

- [No body reference recovered]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
