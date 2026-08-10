# Text evidence: Table 4

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 15
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [97.253, 267.645, 515.739, 662.548]

## Caption

Table 4: Statistics of the datasets used in the experiments.

## Text from suggested visual region

~~~text
Table 4: Statistics of the datasets used in the experiments.

                                   Wikipedia       Reddit           Twitter

      # Nodes                     9,227           11,000          8,861
      # Edges                     157,474         672,447         119,872
      # Edge features             172            172            768
      # Edge features type       LIWC        LIWC        BERT
      Timespan                  30 days         30 days         7 days
       Chronological Split         70%-15%-15%  70%-15%-15%  70%-15%-15%
      # Nodes with dynamic labels  217            366            –


Twitter Dataset Generation  To generate the Twitter dataset we started with the snapshot of the
Recsys Challenge training data on 2020/09/06. We ﬁltered the data to include only retweet edges
(discarding other types of interactions) where the timestamp was present. This left approximately
10% of the edges in the original dataset. We then ﬁltered the retweet multi-graph (users can be
connected by multiple retweets) to only include the largest connected component. Finally, we ﬁltered
the graph to only the top 5,000 nodes in-degree and the top 5,000 by out-degree, ending up with 8,861
nodes since some nodes were in both sets.


A.4  ADDITIONAL EXPERIMENTAL SETTINGS AND RESULTS

Hyperparameters  For the all datasets, we use the Adam optimizer with a learning rate of 0.0001,
a batch size of 200 for both training, validation and testing, and early stopping with a patience of 5.
We sample an equal amount of negatives to the positive interactions, and use average precision as
reference metric. Additional hyperparameters used for both future edge prediction and dynamic node
classiﬁcation are reported in table 5. For all the graph embedding modules we use neighbors sampling
(Hamilton et al., 2017b) (i.e. only aggregate from k neighbors) since it improves the efﬁciency of
the model without losing in accuracy. In particular, the sampled edges are the k most recent ones,
rather than the traditional approach of sampling them uniformly, since we found it to perform much
better (see Figure 5). All experiments and timings are conducted on an AWS p3.16xlarge machine
and the results are averaged over 10 runs. The code will be made available for all our experiments to
be reproduced.
~~~

## Body references

- [PDF p.15] The statistics of the three datasets are reported in table 4.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
