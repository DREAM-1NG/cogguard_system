# Text evidence: Figure 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 3
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [97.641, 60.524, 514.004, 324.684]

## Caption

Figure 1: Computations performed by TGN on a batch of time-stamped interactions. Top: embeddings are produced by the embedding module using the temporal graph and the node’s memory (1). The embeddings are then used to predict the batch interactions and compute the loss (2, 3). Bottom: these same interactions are used to update the memory (4, 5, 6). This is a simpliﬁed ﬂow of operations which would prevent the training of all the modules in the bottom as they would not receiving a gradient. Section 3.2 explains how to change the ﬂow of operations to solve this problem and ﬁgure 2 shows the complete diagram.

## Text from suggested visual region

~~~text
2                        3

                               1                                                                              loss


                                                                            Edge
                                         Node Embeddings
          1         2                                                                          Probabilities

          2         3

                            4
               Batch
                                                       5                           6


                                                               Aggregated                   (Updated)
                                  Messages
                                                          Messages                 Memory

Figure 1: Computations performed by TGN on a batch of time-stamped interactions. Top: embeddings
are produced by the embedding module using the temporal graph and the node’s memory (1). The
embeddings are then used to predict the batch interactions and compute the loss (2, 3). Bottom: these
same interactions are used to update the memory (4, 5, 6). This is a simpliﬁed ﬂow of operations
which would prevent the training of all the modules in the bottom as they would not receiving a
gradient. Section 3.2 explains how to change the ﬂow of operations to solve this problem and ﬁgure 2
shows the complete diagram.
~~~

## Body references

- [PDF p.5] TGN can be trained for a variety of tasks such as edge prediction (self-supervised) or node classi- ﬁcation (semi-supervised). We use link prediction as an example: provided a list of time ordered interactions, the goal is to predict future interactions from those observed in the past. Figure 1 shows the computations performed by TGN on a batch of training data.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
