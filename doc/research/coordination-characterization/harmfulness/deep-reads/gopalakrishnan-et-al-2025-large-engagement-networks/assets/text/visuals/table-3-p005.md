# Text evidence: Table 3

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 5
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [44.0, 44.024, 302.514, 293.456]

## Caption

Table 3: Statistics of the engagement networks for the small dataset with 100 networks. This is simply the smallest 100 networks, out of 314, with respect to node counts.

## Text from suggested visual region

~~~text
Sub-type # G     # nodes          # edges
              Min Max  Avg Min  Max Avg
     Politics     14   100 1,908   805   203   2,000 1108
    Reform     16   131   634   297   540   2,027 1192
    News        3   581 1,671  1123   942   1,726 1410
    Finance      9   273 1,590   775   243   1,862 1024   Campaign Noise        5   454 2,520  1060   473   1,634 1074
     Cult         4   313   705   512   637   1,035  843
    Overall     51   100 2,520   661   203   2,027 1113
    News       10   818 6,169  3757   709   9,076 4578
     Sports      23   469 8,355  3357   403   9,998 3994
     Festival      2   885 5,982  3433   803   6,509 3656
     Internal      1 4,188 4,188 4,188 4,374   4,374 4374
   Common     5 1,214 4,962 2,989 1,270   6,277 3559     Non-Campaign  Enter.       5 1,477 7,739 4,391 1,712 10,608 6021
     Sp. cam.     3 2,880 4,661 3,654 4,451   7,367 5534
    Overall     49   469 8,355  3545   403 10,608 4364

Table 3: Statistics of the engagement networks for the small
dataset with 100 networks. This is simply the smallest 100
networks, out of 314, with respect to node counts.
~~~

## Body references

- [PDF p.5] Building Networks Using the data collected in the last two sections, we build engagement networks. The nodes in the networks represent the users on Twitter and a directed edge from a node A to node B signify that A engaged with (retweeted, replied to, or quoted) B. Some users engaged with the same user re- peated times. We only consider their latest engagement. In this process, we retain around 74% of edges across all the networks. We use profile and tweet data to assign the attributes of nodes and edges respectively. We used the user descrip- tion (bio), follower count, following count, user’s total tweet count, and user’s verification status as node attributes. The edge attributes are features of the tweets that are the user engaged with: the type of engagement (retweet, reply, or quote), text, impression count, engagement count (e.g., num- ber of retweets), number of likes, the timestamp of the tweet and whether the tweet is labeled as sensitive or not. The au- thor’s description and the text of the tweet are encoded us- ing an established text encoder called LaBSE (Feng et al. 2020). The LaBSE model is an bidirectional encoder, that takes source and target translation pairs and embeds them into the same space. The text encoder is initialized with a pre-trained masked language model (MLM) and a transla- tion language model (TLM), which are then concatenated to produce a text embedding. The model is trained using trained using in-batch negative sampling. For our work, we used the pre-trained set of weights for the LaBSE encoder. LEN comprises of 314 graphs of which 179 ar

[TRUNCATED BY EXTRACTOR]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
