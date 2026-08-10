# Text evidence: Figure 8

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 20
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [21.42, 334.796, 590.58, 742.293]

## Caption

Fig. 8 lists the 3 highest-scored and the 3 lowest-scored shapes of CAW, which are extracted from the Wikipedia dataset with M = 32 and m = 3. A law of general motif closure can be observed from the highest-scored CAWs: two nodes that commonly appear in some types of motif are more inclined to have a link in between. For example, the highest-scored shape of CAW, (0, ∞) →(1, 2) →(2, 3) →(1, 2), implies that the nodes except the ﬁrst in this CAW appear in the sampled common 3-hop neighborhood around the two nodes between which the link is to be

## Text from suggested visual region

~~~text
E  VISUALIZING CAWS AND AWS

Here, we introduce one way to visualize and interpret CAWs. Our interpretation can also illustrate
the importance to capture the correlation between walks to represent the dynamics of temporal
networks, where the set-based anonymization of CAWs can work while AWs will fail. The basic idea
of our intrepretation is to identify different shapes of CAWs via their patterns encoded in ICAW , and
compare their contributions to the link-prediction conﬁdence. The idea will be also used to interpret
AWs so that we can compare CAWs with AWs.

First, we deﬁne the shapes of walks based on ICAW . Recall from Eq. 3 that g(w, Su) encodes the
number of times node w that appears in different walk positions w.r.t source node u. This encoding
induces a temporal shortest-path distance duw between node w and u: duw ≜min{i|g(w, Su)[i] >
0}. Note that in temporal networks, there is not a canonical way to deﬁne shortest-path distance
between two nodes as there is no static structures. So our deﬁnition duw can be viewed the shortest-
path distance between u and w over the subgraph that consists of walks in Su. Based on the way to
deﬁne (duw, dvw), we introduce the mapping from ICAW of the node w to a coordinate of this node in
the subgraph that consists of walks in Su ∩Sv: (g(w, Su), g(w, Sv)) −→coor(w; u, v) = (duw, dvw).
This cooredinate can be viewed as a relative coordinate of node w w.r.t. the source nodes u, v. Each
walk W ∈Su ∪Sv can then represented as a sequence of such coordinates by mapping each node’s
ICAW to a coordinate. The obtained sequence can be viewed as a shape of W and we denote the
obtained shape as sCAW (W). For instance, in the toy example shown by Fig. 2 right, the ﬁrst CAW in
Su, u −→b −→a −→c is mapped to a new coordinate sequence (0, 2) −→(1, 2) −→(2, ∞) −→(3, ∞).
The ∞marks the setting that node a, c do not appear in Sv.

Next, we score the contributions of CAWs with different shapes. We use CAW-N-Mean as enc(Su ∪
Sv) is simply mean over the encodings of sampled CAWs and further use linear projrepresented as a
sequence of such coordinates by mapping each node’section βT enc(Su ∪Sv) to compute the ﬁnal
scalar logit for prediction. As the two operations mean and projection are commutative, the above
setting allows each CAW ˆWi contributing a scalar score logit(ˆWi) = βT enc(ˆWi) to the ﬁnal logit.

Fig. 8 lists the 3 highest-scored and the 3 lowest-scored shapes of CAW, which are extracted
from the Wikipedia dataset with M = 32 and m = 3. A law of general motif closure can be
observed from the highest-scored CAWs: two nodes that commonly appear in some types of motif
are more inclined to have a link in between.  For example, the highest-scored shape of CAW,
(0, ∞) →(1, 2) →(2, 3) →(1, 2), implies that the nodes except the ﬁrst in this CAW appear in
the sampled common 3-hop neighborhood around the two nodes between which the link is to be
~~~

## Body references

- [PDF p.21] predicted. Therefore, CAW-N essentially adaptively samples a temporal motif closure pattern that is very informative to predict this link. CAW-N does not explicitly enumerating or counting these motif patterns. In contrast, when CAWs do not bridge the two nodes, as shown in top-2 lowest-scored CAWs, very unlikely there will exist a link. Fig. 8 also displays each of the 6 CAW’s occurrence ratio with positive and negative links. The difference within each pair of ratios is an indicator of the corresponding CAW’s discriminatory power. We also see that the discriminatory power of CAWs is very strong: highest-scored CAWs almost never occur with negative links, and lowest-scored CAWs also seldom occur with positive links.
- [PDF p.22] It has come to our notice there exists an error in our original implementation of ICAW as well as the attention Self-Att-AGG(Su ∪Sv). Fixing the error leads to numerical changes to some of the experimental results reported in the original paper: Tables 2, 3, 6, and Fig.8. Based on the correct implementation, we have updated the artifacts above and their relevant text . The correct implementation has also been updated to the GitHub repository at the original code link. Despite the change, the vast majority of the conclusions about CAWN remain unaffected.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
