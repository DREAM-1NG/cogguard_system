# Text evidence: Table 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 6
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [97.691, 96.968, 514.353, 525.355]

## Caption

Table 1 shows the statistics and properties of the temporal graph datasets provided by TGB. Datasets such as tgbl-flight, tgbl-comment, tgbl-coin, and tgbn-reddit are orders of magnitude larger than existing TG benchmark datasets [35, 33, 24], while their number of nodes and edges span a wide spectrum, ranging from thousands to millions. In addition, TGB dataset domains are highly diverse, coming from five distinct domains including social networks, interaction networks, rating networks, traffic networks, and trade networks. Moreover, the duration of the datasets varies from months to years, and the number of timestamps in TGB datasets ranges from 32 to more than 30 million with diverse ranges of time granularity from UNIX timestamps to annually. The datasets can be weighted, directed, or have edge attributes. We also report the surprise index (i.e., |Etest\Etrain|

## Text from suggested visual region

~~~text
Dataset       Domain # Nodes # Edges   # Steps     Surprise Edge Properties¶
   tgbl-wiki      interact. 9,227   157,474    152,757    0.108   W: ✘, Di: ✓, A: ✓
   tgbl-review   rating   352,637 4,873,540  6,865      0.987   W: ✓, Di: ✓, A: ✘
   tgbl-coin      transact. 638,486 22,809,486 1,295,720  0.120   W: ✓, Di: ✓, A: ✘ Link   tgbl-comment social   994,790 44,314,507 30,998,030 0.823   W: ✓, Di: ✓, A: ✓
   tgbl-flight   traffic   18143   67,169,570 1,385      0.024   W: ✘, Di: ✓, A: ✓
   tgbn-trade    trade    255     468,245   32         0.023   W: ✓, Di: ✓, A: ✘
   tgbn-genre    interact. 1,505   17,858,395 133,758    0.005   W: ✓, Di: ✓, A: ✘ Node   tgbn-reddit   social   11,766  27,174,118 21,889,537 0.013   W: ✓, Di: ✓, A: ✘
   tgbn-token    transact. 61,756  72,936,998 2,036,524  0.014   W: ✓, Di: ✓, A: ✓


NDCG is commonly used in information retrieval and recommendation systems as a measure of
ranking quality [19]. In this work, we use NDCG@10 where the relative order of the top 10 ranked
items (i.e., destination nodes) are examined. Specifically in the tgbn-genre dataset, the NDCG@10
compares the ground truth to the relative order of the top-10 music genres that a model predicts.

4  Datasets

TGB offers nine temporal graph datasets, seven of which are collected and curated for this work. All
datasets are split chronologically into the training, validation, and test sets, respectively containing
70%, 15%, and 15% of all edges, in line with similar studies such as [48, 35, 45, 20, 40, 25]. The
dataset licenses and download links are presented in Appendix B, and the datasets will be permanently
maintained via Digital Research Alliance of Canada funded by the Government of Canada. We
consider datasets with more than 5 million edges as medium-size and those with more than 25 million
edges as large-size datasets.

Table 1 shows the statistics and properties of the temporal graph datasets provided by TGB. Datasets
such as tgbl-flight, tgbl-comment, tgbl-coin, and tgbn-reddit are orders of magnitude
larger than existing TG benchmark datasets [35, 33, 24], while their number of nodes and edges span
a wide spectrum, ranging from thousands to millions. In addition, TGB dataset domains are highly
diverse, coming from five distinct domains including social networks, interaction networks, rating
networks, traffic networks, and trade networks. Moreover, the duration of the datasets varies from
months to years, and the number of timestamps in TGB datasets ranges from 32 to more than 30
million with diverse ranges of time granularity from UNIX timestamps to annually. The datasets can
be weighted, directed, or have edge attributes. We also report the surprise index (i.e., |Etest\Etrain| ) as                                                                                                                                         |Etest|
defined in [33] which computes the ratio of test edges that are not seen during training. Low surprise
~~~

## Body references

- [PDF p.8] One explanation for the significant performance reduction of some methods on tgbl-review is that it has a higher surprise index compared to tgbl-wiki (see Table 1). The surprise index reflects the ratio of edges in the test set that have not been seen during training. Therefore, a dataset with a high surprise index requires more inductive reasoning, as most of the test edges are unobserved during training. As a heuristic that memorizes past edges, EdgeBank performance is inversely correlated with the surprise index and it achieves higher performance when the suprise index of the dataset is low. An interesting future direction is the investigation of the performance of certain category of methods with the surprise index. For example, the top two methods NAT and CAWN on wikipedia both utilizes features from the joint neighborhood of nodes in the queried edge [25]. On the tgbl-review dataset, the best performing TGAT is designed for inductive representation learning on temporal graph [48] which fits the inductive nature of tgbl-review which has high surprise index.
- [PDF p.17] In addition to the main dataset statistics presented in Table 1, it is insightful to examine some other dataset characteristics as indicated in Table 5. The reoccurrence index (i.e., |Etrain∩Etest|

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
