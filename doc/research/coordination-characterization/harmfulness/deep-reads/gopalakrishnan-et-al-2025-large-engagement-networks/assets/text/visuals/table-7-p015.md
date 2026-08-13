# Text evidence: Table 7

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 15
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [44.0, 252.856, 302.514, 502.287]

## Caption

Table 7: Description of connected components in the graph. Here fLCC is the fraction of the largest connected compo- nent to the whole graph.

## Text from suggested visual region

~~~text
Sub-type  # of Conn. Comp.     fLCC
            Min Max    Avg Min Max  Avg
       Politics       1 2,004   207.29 0.355     1 0.800
      Reform       1   112    13.16 0.396     1 0.826
     News       17 2,138   578.67 0.147 0.975 0.735
      Finance      6 1,486   159.71 0.257 0.973 0.691          Campaign Noise       16 8,908 1,865.22 0.065 0.976 0.469
       Cult        12   122    67.00 0.293 0.899 0.553
      Overall      1 8,908   269.47 0.065     1 0.767
     News       10   818    6,169 0.203 0.989 0.793
       Sports       54 3,114   576.00 0.180 0.981 0.655
       Festival     128 7,289 1,721.24 0.349 0.924 0.793
       Internal     164 7,605 1,096.45 0.337 0.988 0.793
     Common   103 1,851   788.13 0.298 0.940 0.945              Non-Campaign  Enter.      101   396   193.28 0.570 0.953 0.792
      Sp. cam.     68   105    76.00 0.885 0.926 0.906
      Overall     54 7,605   675.80 0.180 0.989 0.816

Table 7: Description of connected components in the graph.
Here fLCC is the fraction of the largest connected compo-
nent to the whole graph.
~~~

## Body references

- [PDF p.5] Building Networks Using the data collected in the last two sections, we build engagement networks. The nodes in the networks represent the users on Twitter and a directed edge from a node A to node B signify that A engaged with (retweeted, replied to, or quoted) B. Some users engaged with the same user re- peated times. We only consider their latest engagement. In this process, we retain around 74% of edges across all the networks. We use profile and tweet data to assign the attributes of nodes and edges respectively. We used the user descrip- tion (bio), follower count, following count, user’s total tweet count, and user’s verification status as node attributes. The edge attributes are features of the tweets that are the user engaged with: the type of engagement (retweet, reply, or quote), text, impression count, engagement count (e.g., num- ber of retweets), number of likes, the timestamp of the tweet and whether the tweet is labeled as sensitive or not. The au- thor’s description and the text of the tweet are encoded us- ing an established text encoder called LaBSE (Feng et al. 2020). The LaBSE model is an bidirectional encoder, that takes source and target translation pairs and embeds them into the same space. The text encoder is initialized with a pre-trained masked language model (MLM) and a transla- tion language model (TLM), which are then concatenated to produce a text embedding. The model is trained using trained using in-batch negative sampling. For our work, we used the pre-trained set of weights for the LaBSE encoder. LEN comprises of 314 graphs of which 179 ar

[TRUNCATED BY EXTRACTOR]
- [PDF p.12] Appendix Table 7 provides a description on the number o connected components in the graph. Figure 4 and 5 provide ROC curves for campaign vs non- campaign classification across small and complete dataset respectively.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
