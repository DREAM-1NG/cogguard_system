# Text evidence: Figure 3

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 3
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [296.0, 516.355, 515.654, 603.555]

## Caption

Figure 3: Ambiguity due to removing node identi- ties in TGAT (Xu et al., 2020) (t1 < t2 < t3).

## Text from suggested visual region

~~~text
y
-     a   t1, t2  b   History:  𝑎, 𝑏, t1  ,  𝑎′, 𝑏′, t1  , 𝑎, 𝑏, t2  ,  𝑎′, 𝑏′, t2  ;
-           𝐭𝟑?              The order of timestamps: 𝑡1 < 𝑡2 < 𝑡3.
       a’          b’   Question: Which is more likely to happen,
             t1, t2                   𝑎, 𝑏, t3  or  𝑎′, 𝑏, t3 ?
,  Figure 3: Ambiguity due to removing node identi-
,   ties in TGAT (Xu et al., 2020) (t1 < t2 < t3).
.
 b            i    d  id   titi    d j   t     di    li k
~~~

## Body references

- [PDF p.3] Most of the above models are not inductive be- cause they associate each node with an one- hot identity (or the corresponding row of the adjacency matrix, or a free-trained vector) (Li et al., 2018; Chen et al., 2019; Kumar et al., 2019; Hajiramezanali et al., 2019; Sankar et al., 2020; Manessi et al., 2020; Goyal et al., 2020). TGAT (Xu et al., 2020) claimed to be inductive by removing node identities and just encoding link timestamps and attributes. However, TGAT was only evaluated over networks with rich link attributes, where the structural dynamics is not captured essentially: If we focus on structural dynamics only, it is easy to show a case when TGAT confuses node representations and will fail: Suppose in the history, two node pairs {a, b} and {a′, b′} only interact within each pair but share the timestamps (Fig. 3). Intuitively, a proper model should predict that future links still appear within each pair. However, TGAT cannot distinguish a v.s. a′, and b v.s. b′, which leads to incorrect prediction. Note that GraphSAGE (Hamilton et al., 2017a) and GAT (Veliˇckovi´c et al., 2018) also share the similar issue when representing static networks for link prediction (Zhang et al., 2020; Srinivasan & Ribeiro, 2019). DyRep (Trivedi et al., 2019) is able to relieve such ambiguity by merging node representations with their neighbors’ via RNNs. However, when DyRep runs over a new network, it frequently encounters node representations unseen during its training and will fail to make correct prediction.
- [PDF p.4] Our CAW-N removes node identities and leverages relative node identities to avoid the issue in Fig. 3. Detailed explanations are given in Sec.4.2.
- [PDF p.5] Essentially, g(w, Su) and g(w, Sv) encode the correlation between walks within Su and Sv respec- tively and the set operation in Eq.3 establishes the correlation across Su and Sv. For the case in Fig.3, suppose Sa, Sb, Sa′, Sb′ include all historical one-step walks (before t3) starting from a, b, a′, b′ respectively. Then, it is easy to show that ICAW (a; {Sa, Sb}) ̸= ICAW (a′; {Sa′, Sb}) that allows differentiating a and a′, while TGAT (Xu et al., 2020) as discussed in Sec.2 fails. From the network- motif point of view, ICAW not only encodes each network motif that corresponds to one single walk as IAW does but also establishes the correlation among these network motifs. IAW cannot establish the correlation between motifs and will also fail to distinguish a and a′ in Fig.3. We see it as a signiﬁcant breakthrough as such correlation often gets neglected in previous works that directly count motifs or adopt AW-type anonymization IAW .
- [PDF p.8] gaps between the two settings are small, while they sometimes do not perform well in the transductive setting, as they encounter the ambiguity issue in Fig. 3. In contrast, our methods perform well in both the transductive and inductive settings. We attribute this superiority to the anonymization procedure: the set-based relative node identities well capture the correlation between walks to make good prediction while removing the original node identities to keep entirely inductive. Even when the network structures greatly change and new nodes come in as long as the network evolves according to the same law as the network used for training, CAW-N will always work. Comparing CAW-N-mean and CAW-N-attn, we see that our attention-based variant outperforms the mean-pooling variant, albeit at the cost of high computation complexity. Also note that the strongest baselines on all datasets are stream-based methods, which indicates that the aggregation of links into network snapshots may remove some useful time information (see more discussion in Appendix D.2). We further conduct ablation studies on Wikipedia (attributed), UCI (non-attributed), and Social Evolution (non-attributed), to validate effectiveness of critical components of our model. Tab. 3 shows the results. By comparing Ab.1 with Ab.2, 3 and 4 respectively, we observe that our proposed node anonymization and encoding, f1(ICAW ), contributes most to the performance, though the time encoding f2(t) also helps. Comparing performance across different datasets, we see that the impact of ablation is more prominent when informati

[TRUNCATED BY EXTRACTOR]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
