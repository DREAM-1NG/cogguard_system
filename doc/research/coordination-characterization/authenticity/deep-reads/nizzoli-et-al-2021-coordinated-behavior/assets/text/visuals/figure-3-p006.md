# Text evidence: Figure 3

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 6
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [44.0, 43.999, 302.505, 295.123]

## Caption

Figure 3: Edge weight distribution of the unﬁltered (blue- colored) and ﬁltered (red-colored) user similarity networks. The network ﬁltered using a multiscale ﬁltering method al- lows us to retain statistically-meaningful network structures independently on their scale (i.e., edge weight), as opposed to cutting at a predetermined, ﬁxed threshold (dotted-black line), which would exclude almost the entire network from the subsequent analysis.

## Text from suggested visual region

~~~text
Figure 3: Edge weight distribution of the unﬁltered (blue-
colored) and ﬁltered (red-colored) user similarity networks.
The network ﬁltered using a multiscale ﬁltering method al-
lows us to retain statistically-meaningful network structures
independently on their scale (i.e., edge weight), as opposed
to cutting at a predetermined, ﬁxed threshold (dotted-black
line), which would exclude almost the entire network from
the subsequent analysis.
~~~

## Body references

- [PDF p.5] puted user similarities as the cosine similarity of user vec- tors. Before studying the network, we applied the technique proposed in (Serrano, Bogun´a, and Vespignani 2009) to re- tain only statistically-relevant edges, thus obtaining the mul- tiscale backbone of our network, which we exploited for the remaining analyses. The resulting ﬁltered user similar- ity network contains 276,775 edges and is shown in Fig- ure 2. In addition, Figure 3 shows the distribution of edge weights in the ﬁltered network. The ﬁltering step preserved the rich, multiscale nature of the network, as opposed to ﬁl- tering based on a ﬁxed threshold. Political leaning. In Figure 2, nodes are colored based on their political leaning, as inferred from the hashtags that they used. In particular, we employed a label propagation algorithm for assigning a polarity score to each hashtag in our dataset. In detail, it is a modiﬁed version of the so- called valence score, a simple, standard, well-known method from literature adopted in many studies before (Wang et al. 2011). The score for a given hashtag is inferred from its co- occurrences with seeds of known polarity. We used the 13 hashtags in Table 1 as the seeds for the label propagation. Finally, a user’s polarity is computed as the term-frequency weighted average of the polarities of the hashtags used by that user. Network interpretation. As shown in Figure 2, the user similarity network presents a visible structure character- ized by several large communities and a few smaller ones. Concerning political polarization, all users can be grouped into thre

[TRUNCATED BY EXTRACTOR]
- [PDF p.6] (blue-colored), and Neutral users (yellow-colored). We per- formed a ﬁrst sanity check by comparing the structural prop- erties of the network with political ones. In particular, col- ors in the network appear to be clearly separated. In other words, communities derived from network structure appear to be extremely politically homogeneous, and we do not have any cluster that contains users with markedly differ- ent colors. Moving forward, the Conservative cluster ap- pears to be sharply separated from the rest of the network, while the Labour and Neutral clusters are more intertwined with one another. This interesting property of our network closely resembles the political landscape in the UK ahead of the 2019 GE. Indeed, one of the debate’s main topics was Brexit, which led to a strong polarization between Conserva- tives and all other parties. (Schumacher 2019). In addition, the ﬁrst-past-the-post UK voting system also motivated anti- Tory electors to converge on the candidate of the party hav- ing the highest chances to defeat the Conservative’s one in each constituency – a strategy dubbed tactical voting6. Our rich and informative network embeds and conveys these nu- ances. Coordinated communities. Building on these promis- ing preliminary results, we are now interested in a ﬁne- grained analysis of the user similarity network communities. As mentioned before, previous works focused on threshold- based approaches and enforced restrictive edge weight ﬁlters to retain only edges with very large weights. Instead, in our study, the ﬁltered user similarity network features d

[TRUNCATED BY EXTRACTOR]
- [PDF p.10] Comparative evaluation The analysis carried out so far demonstrated how our frame- work embeds – and therefore allows investigating – the in- trinsic properties of coordinated behavior. In fact, by avoid- ing to enforce a binary separation between coordinated vs. uncoordinated behaviors, we were able to study this phe- nomenon across its entire spectrum, thus measuring the in- trinsic coordination of each emerging community and char- acterizing it under multiple dimensions of analysis. To high- light the theoretical and practical contribution of our novel framework, in this section we compare our ﬁndings with those obtainable with previous, threshold-based approaches. First, we consider the unﬁltered user similarity network, that is what we obtained after carrying out step 3 of our framework, as outlined in Figure 1. This is where our method departs from previous approaches. Then, we set an arbitrary, very strict threshold, and we cut all those edges whose weight is below the threshold, and the resulting dis- connected nodes. Finally, we visualize the obtained ﬁltered networks. By comparing the results obtained in this way with those of our framework, we can comparatively evalu- ate the contributions of steps 4-6, which constitute the main novelty of our work. We set the ﬁltering threshold to 0.9, following the value proposed in (Pacheco et al. 2020) for a similar, co-retweet- based analysis. We recall that here we are directly consid- ering edge weights, following previous approaches, whereas in our framework the coordination was measured as a per- centile rank. We refer t

[TRUNCATED BY EXTRACTOR]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
