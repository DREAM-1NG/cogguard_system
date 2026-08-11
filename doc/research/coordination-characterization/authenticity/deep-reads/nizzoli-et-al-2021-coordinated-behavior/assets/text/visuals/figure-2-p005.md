# Text evidence: Figure 2

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 5
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [298.344, 10.528, 568.005, 365.969]

## Caption

Figure 2: The ﬁltered user similarity network of the 2019 UK GE. Nodes represent users involved in the online de- bate, while edges weight according to the similarity strength between one another, as deﬁned in Step 2. Users are colored according to their political leaning, inferred from the polar- ity of the hashtags they used, computed using label propaga- tion.

## Text from suggested visual region

~~~text
labour                                           conservative

Figure 2: The ﬁltered user similarity network of the 2019
UK GE. Nodes represent users involved in the online de-
bate, while edges weight according to the similarity strength
between one another, as deﬁned in Step 2. Users are colored
according to their political leaning, inferred from the polar-
ity of the hashtags they used, computed using label propaga-
tion.
~~~

## Body references

- [PDF p.5] puted user similarities as the cosine similarity of user vec- tors. Before studying the network, we applied the technique proposed in (Serrano, Bogun´a, and Vespignani 2009) to re- tain only statistically-relevant edges, thus obtaining the mul- tiscale backbone of our network, which we exploited for the remaining analyses. The resulting ﬁltered user similar- ity network contains 276,775 edges and is shown in Fig- ure 2. In addition, Figure 3 shows the distribution of edge weights in the ﬁltered network. The ﬁltering step preserved the rich, multiscale nature of the network, as opposed to ﬁl- tering based on a ﬁxed threshold. Political leaning. In Figure 2, nodes are colored based on their political leaning, as inferred from the hashtags that they used. In particular, we employed a label propagation algorithm for assigning a polarity score to each hashtag in our dataset. In detail, it is a modiﬁed version of the so- called valence score, a simple, standard, well-known method from literature adopted in many studies before (Wang et al. 2011). The score for a given hashtag is inferred from its co- occurrences with seeds of known polarity. We used the 13 hashtags in Table 1 as the seeds for the label propagation. Finally, a user’s polarity is computed as the term-frequency weighted average of the polarities of the hashtags used by that user. Network interpretation. As shown in Figure 2, the user similarity network presents a visible structure character- ized by several large communities and a few smaller ones. Concerning political polarization, all users can be grouped into thre

[TRUNCATED BY EXTRACTOR]
- [PDF p.6] 1. CON: The community of Conservative users that was clearly visible in Figure 2 was also detected by our com- munity detection algorithm. It includes all major Con- servative users (e.g., @BorisJohnson and @Conservatives), and it is characterized by a majority of hashtags supporting the Conservative Party (voteconservative), its leader (backboris) and Brexit (getbrexitdone).
- [PDF p.6] 2. LAB: Similarly, also the dense group of Labour users that we highlighted in Figure 2 has been identiﬁed as a distinct community of Labours. These users are charac- terized by hashtags supporting the party (votelabour), their leader (jc4pm), and traditional Labour ﬂags like healthcare (saveournhs) and climate change (climatedebate). Notably, the absence of Brexit-related keywords seems to conﬁrm the alleged ambiguity of Jeremy Corbyn’s campaign on this topic7.
- [PDF p.6] 3. TVT: The largest group of neutral users in Figure 2, tightly related to LAB users, was assigned to this com- munity. These users debated topics related to liberal democrats (votelibdem), anti-Tory (liarjohnson), anti-Brexit (stopbrexit) and to the campaigns promoting tactical voting (votetactically, tacticalvote).

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
