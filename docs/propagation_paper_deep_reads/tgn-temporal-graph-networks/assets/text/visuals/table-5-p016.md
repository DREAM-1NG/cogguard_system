# Text evidence: Table 5

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 16
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [97.253, 71.977, 514.346, 356.445]

## Caption

Table 5: Model Hyperparameters.

## Text from suggested visual region

~~~text
Table 5: Model Hyperparameters.

                                                       Value

                      Memory Dimension          172
                       Node Embedding Dimension  100
                        Time Embedding Dimension   100
                         # Attention Heads           2
                          Dropout                       0.1


time embedding module, while for DyRep we augment the messages with the result of a temporal
graph attention performed on the destination’s neighborhood. For both we use a vanilla RNN as the
memory updater module.

A.4.1  NEIGHBOR SAMPLING: UNIFORM VS MOST RECENT

When performing neighborhood sampling (Hamilton et al., 2017a) in static graphs, nodes are usually
sampled uniformly. While this strategy is also possible for dynamic graphs, it turns out that the most
recent edges are often the most informative. In Figure 5 we compare two TGN-attn models (see Table
1) with either uniform or most recent neighbor sampling, which shows that a model which samples
the most recent edges obtains higher performances.


                                                               most_recent

                                       98 4
~~~

## Body references

- [PDF p.15] Hyperparameters For the all datasets, we use the Adam optimizer with a learning rate of 0.0001, a batch size of 200 for both training, validation and testing, and early stopping with a patience of 5. We sample an equal amount of negatives to the positive interactions, and use average precision as reference metric. Additional hyperparameters used for both future edge prediction and dynamic node classiﬁcation are reported in table 5. For all the graph embedding modules we use neighbors sampling (Hamilton et al., 2017b) (i.e. only aggregate from k neighbors) since it improves the efﬁciency of the model without losing in accuracy. In particular, the sampled edges are the k most recent ones, rather than the traditional approach of sampling them uniformly, since we found it to perform much better (see Figure 5). All experiments and timings are conducted on an AWS p3.16xlarge machine and the results are averaged over 10 runs. The code will be made available for all our experiments to be reproduced.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
