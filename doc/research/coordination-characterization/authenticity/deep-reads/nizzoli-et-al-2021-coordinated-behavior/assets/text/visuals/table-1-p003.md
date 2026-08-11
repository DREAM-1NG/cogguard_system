# Text evidence: Table 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 3
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [325.384, 49.147, 552.118, 249.582]

## Caption

Table 1: Statistics about data collected via hashtags.

## Text from suggested visual region

~~~text
hashtag                       leaning       users        tweets

  #GE2019              N      436,356    2,640,966
   #GeneralElection19       N      104,616     274,095
   #GeneralElection2019      N      240,712     783,805
   #VoteLabour              L      201,774     917,936
   #VoteLabour2019          L       55,703     265,899
   #ForTheMany             L       17,859      35,621
   #ForTheManyNotTheFew     L       22,966      40,116
   #ChangeIsComing          L         8,170      13,381
   #RealChange             L       78,285     274254
   #VoteConservative         C       52,642     238,647
   #VoteConservative2019     C       13,513      34,195
   #BackBoris              C       36,725     157,434
   #GetBrexitDone           C       46,429     168,911

    total                         –      668,312    4,983,499

Table 1: Statistics about data collected via hashtags.
~~~

## Body references

- [PDF p.3] Dataset By leveraging Twitter Streaming APIs, we collected a large dataset of tweets related to the 2019 UK GE. Our data col- lection covered one month before the election day, from 12 November to 12 December 2019. During that period, we col- lected all the tweets mentioning at least one hashtag from a list containing the most popular hashtags, some used by the two main parties while others more neutral. Table 1 lists all the hashtags used during this phase, their corresponding po- litical leaning (N: Neutral, L: Labour, C: Conservative), and the related data collected. The tweets column only counts quoted retweets if the quote text contains one of the hash- tags in the table. The remaining quoted retweets are still in- cluded in our dataset, but they are not counted in Table 1. In addition to the aforementioned hashtags-based collection, we collected all tweets published by the two parties’ ofﬁcial accounts and their leaders, together with all the interactions (i.e., retweets and replies) they received. Table 2 shows the accounts and the collected data. Our ﬁnal dataset for this
- [PDF p.5] puted user similarities as the cosine similarity of user vec- tors. Before studying the network, we applied the technique proposed in (Serrano, Bogun´a, and Vespignani 2009) to re- tain only statistically-relevant edges, thus obtaining the mul- tiscale backbone of our network, which we exploited for the remaining analyses. The resulting ﬁltered user similar- ity network contains 276,775 edges and is shown in Fig- ure 2. In addition, Figure 3 shows the distribution of edge weights in the ﬁltered network. The ﬁltering step preserved the rich, multiscale nature of the network, as opposed to ﬁl- tering based on a ﬁxed threshold. Political leaning. In Figure 2, nodes are colored based on their political leaning, as inferred from the hashtags that they used. In particular, we employed a label propagation algorithm for assigning a polarity score to each hashtag in our dataset. In detail, it is a modiﬁed version of the so- called valence score, a simple, standard, well-known method from literature adopted in many studies before (Wang et al. 2011). The score for a given hashtag is inferred from its co- occurrences with seeds of known polarity. We used the 13 hashtags in Table 1 as the seeds for the label propagation. Finally, a user’s polarity is computed as the term-frequency weighted average of the polarities of the hashtags used by that user. Network interpretation. As shown in Figure 2, the user similarity network presents a visible structure character- ized by several large communities and a few smaller ones. Concerning political polarization, all users can be grouped into thre

[TRUNCATED BY EXTRACTOR]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
