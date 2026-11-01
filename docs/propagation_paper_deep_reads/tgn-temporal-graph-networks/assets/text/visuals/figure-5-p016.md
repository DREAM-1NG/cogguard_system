# Text evidence: Figure 5

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 16
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [98.0, 322.635, 515.745, 523.43]

## Caption

Figure 5: Comparison of two TGN-attn models using different neighbor sampling strategies (when sampling 10 neighbors). Sampling the most recent edges clearly outperforms uniform sampling. Means and standard deviations (visualized as ellipses) were computed over 10 runs.

## Text from suggested visual region

~~~text
most_recent

                                            98.4


                                            98.2                                                                                                                         Precision

                                            98.0                                                                                              Average
                                                      Test 97.8

                                                                                                              uniform
                                            97.6


                                                 23           24           25           26           27
                                                                 Time (per epoch) in seconds

Figure 5: Comparison of two TGN-attn models using different neighbor sampling strategies (when
sampling 10 neighbors). Sampling the most recent edges clearly outperforms uniform sampling.
Means and standard deviations (visualized as ellipses) were computed over 10 runs.
~~~

## Body references

- [PDF p.15] Hyperparameters For the all datasets, we use the Adam optimizer with a learning rate of 0.0001, a batch size of 200 for both training, validation and testing, and early stopping with a patience of 5. We sample an equal amount of negatives to the positive interactions, and use average precision as reference metric. Additional hyperparameters used for both future edge prediction and dynamic node classiﬁcation are reported in table 5. For all the graph embedding modules we use neighbors sampling (Hamilton et al., 2017b) (i.e. only aggregate from k neighbors) since it improves the efﬁciency of the model without losing in accuracy. In particular, the sampled edges are the k most recent ones, rather than the traditional approach of sampling them uniformly, since we found it to perform much better (see Figure 5). All experiments and timings are conducted on an AWS p3.16xlarge machine and the results are averaged over 10 runs. The code will be made available for all our experiments to be reproduced.
- [PDF p.16] When performing neighborhood sampling (Hamilton et al., 2017a) in static graphs, nodes are usually sampled uniformly. While this strategy is also possible for dynamic graphs, it turns out that the most recent edges are often the most informative. In Figure 5 we compare two TGN-attn models (see Table 1) with either uniform or most recent neighbor sampling, which shows that a model which samples the most recent edges obtains higher performances.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
