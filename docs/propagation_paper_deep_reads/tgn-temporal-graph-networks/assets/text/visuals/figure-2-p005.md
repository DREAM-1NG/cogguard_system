# Text evidence: Figure 2

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 5
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [97.641, 55.63, 515.742, 351.585]

## Caption

Figure 2: Flow of operations of TGN used to train the memory-related modules. Raw Message Store stores the necessary raw information to compute messages, i.e. the input to the message functions, which we call raw messages, for interactions which have been processed by the model in the past. This allows the model to delay the memory update brought by an interaction to later batches. At ﬁrst, the memory is updated using messages computed from raw messages stored in previous batches (1, 2, 3). The embeddings can then be computed using the just updated memory (grey link) (4). By doing this, the computation of the memory-related modules directly inﬂuences the loss (5, 6), and they receive a gradient. Finally, the raw messages for this batch interactions are stored in the raw message store (6) to be used in future batches.

## Text from suggested visual region

~~~text
Memory
                               1                           2                               3


          Raw Message                                            Aggregated                    Updated
                                             (Old) Messages
                  Store                                            Messages                   Memory


                7


                                  4                                             5                   6
            1         2
                                                                                                                      loss
            2         3

                 Batch                                                          Edge
                                           Node Embebbings
                                                                                                         Probabilities

Figure 2: Flow of operations of TGN used to train the memory-related modules. Raw Message Store
stores the necessary raw information to compute messages, i.e. the input to the message functions,
which we call raw messages, for interactions which have been processed by the model in the past.
This allows the model to delay the memory update brought by an interaction to later batches. At
ﬁrst, the memory is updated using messages computed from raw messages stored in previous batches
(1, 2, 3). The embeddings can then be computed using the just updated memory (grey link) (4). By
doing this, the computation of the memory-related modules directly inﬂuences the loss (5, 6), and
they receive a gradient. Finally, the raw messages for this batch interactions are stored in the raw
message store (6) to be used in future batches.
~~~

## Body references

- [PDF p.5] The complexity in our training strategy relates to the memory-related modules (Message function, Message aggregator, and Memory updater) because they do not directly inﬂuence the loss and therefore do not receive a gradient. To solve this problem, the memory must be updated before predicting the batch interactions. However, updating the memory with an interaction eij(t) before using the model to predict that same interaction, causes information leakage. To avoid the issue, when processing a batch, we update the memory with messages coming from previous batches (which are stored in the Raw Message Store), and then predict the interactions. Figure 2 shows the training ﬂow for the memory-related modules. Pseudocode for the training procedure is presented in Appendix A.2.
- [PDF p.5] More formally, at any time t, the Raw Message Store contains (at most) one raw message rmi for each node i1, generated from the last interaction involving i before time t. When the model processes the next interactions involving i, its memory is updated using rmi (arrows 1, 2, 3 in Figure 2), then the updated memory is used to compute the node’s embedding and the batch loss (arrows 4, 5, 6). Finally, the raw messages for the new interaction are stored in the raw message store (arrows 7). It is also worth noticing that all predictions in a given batch have access to the same state of the memory. While from the perspective of the ﬁrst interaction in the batch the memory is up-to-date (since it contains information about all previous interactions in the graph), from the perspective of the last interaction in the batch the same memory is out-of-date, since it lacks information about previous interactions in the same batch. This disincentives the use of a big batch size (in the extreme case where the batch size is a big as the dataset, all predictions would be made using the initial zero memory). We found a batch size of 200 to be a good trade-off between speed and update granularity.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
