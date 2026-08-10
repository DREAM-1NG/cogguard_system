# Text evidence: Table 2a

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 8
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [97.641, 445.981, 515.747, 762.295]

## Caption

Table 2a shows the performance of TG methods for dynamic link property prediction on the tgbl-wiki dataset. tgbl-wiki is an existing dataset where many methods achieve over-optimistic performance in the literature [35, 46, 9]. With TGB’s evaluation protocol, there is now a clear distinction in model performance and NAT achieves the best result on this dataset. As tgbl-wiki is the smallest dataset in this task, it is computationally feasible to sample all possible destinations of a given source node. Thus, we compare the true destination with all possible negative destinations in this dataset. In Table 2b, we report the results on tgbl-review where we sample 100 negative edges per positive edge. Here, we observe that many of the best performing methods on tgbl-wiki has a significant drop in performance including NAT, CAWN and Edgebank. More notably, the method rankings also changed significantly with GraphMixer and TGAT being the top two methods. This observation emphasizes the importance of dataset diversity when benchmarking TG methods. In Appendix H, we conduct an ablation study on the effect of number of negative samples on the performance of dynamic link property prediction.

## Text from suggested visual region

~~~text
Table 2a shows the performance of TG methods for dynamic link property prediction on the
tgbl-wiki dataset. tgbl-wiki is an existing dataset where many methods achieve over-optimistic
performance in the literature [35, 46, 9]. With TGB’s evaluation protocol, there is now a clear
distinction in model performance and NAT achieves the best result on this dataset. As tgbl-wiki is
the smallest dataset in this task, it is computationally feasible to sample all possible destinations of
a given source node. Thus, we compare the true destination with all possible negative destinations
in this dataset. In Table 2b, we report the results on tgbl-review where we sample 100 negative
edges per positive edge. Here, we observe that many of the best performing methods on tgbl-wiki
has a significant drop in performance including NAT, CAWN and Edgebank. More notably, the
method rankings also changed significantly with GraphMixer and TGAT being the top two methods.
This observation emphasizes the importance of dataset diversity when benchmarking TG methods.
In Appendix H, we conduct an ablation study on the effect of number of negative samples on the
performance of dynamic link property prediction.

One explanation for the significant performance reduction of some methods on tgbl-review is that
it has a higher surprise index compared to tgbl-wiki (see Table 1). The surprise index reflects the
ratio of edges in the test set that have not been seen during training. Therefore, a dataset with a high
surprise index requires more inductive reasoning, as most of the test edges are unobserved during
training. As a heuristic that memorizes past edges, EdgeBank performance is inversely correlated
with the surprise index and it achieves higher performance when the suprise index of the dataset is low.
An interesting future direction is the investigation of the performance of certain category of methods
with the surprise index. For example, the top two methods NAT and CAWN on wikipedia both
utilizes features from the joint neighborhood of nodes in the queried edge [25]. On the tgbl-review
dataset, the best performing TGAT is designed for inductive representation learning on temporal
graph [48] which fits the inductive nature of tgbl-review which has high surprise index.


                                       8
~~~

## Body references

- [PDF p.18] tgbl-review across five trials, respectively. When contrasting these findings with those presented in Table 2a and 2b, which involve a higher quantity of negative samples, the insights outlined in Section 5 are reaffirmed. For example, there is a significant drop in performance for the top performing method, i.e. CAWN, from tgbl-wiki to tgbl-review. In addition, Edgebank performance has a significant drop when the surprise index is high (which is the case in tgbl-review). However, we can also clearly see that with lower number of negatives (particularly on tgbl-wiki), the MRR scores are significantly higher for most methods. Therefore, if computationally feasible, it is best to use more negative samples. In our case, more negative samples are used for small TGB datasets.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
