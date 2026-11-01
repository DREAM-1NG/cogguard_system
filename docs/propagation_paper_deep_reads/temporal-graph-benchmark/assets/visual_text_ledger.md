# Text-only visual evidence ledger

> Extracted text is not visual verification. Do not infer unreported axes, colors, curves, panels, layout, or crop completeness.

## Figure 1

- **PDF page:** 2
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-1-p002.md](text/visuals/figure-1-p002.md)
- **Caption:** Figure 1: TGB consists of a diverse set of datasets that are one order of magnitude larger than existing datasets in terms of number of nodes, edges, and timestamps.

## Figure 2

- **PDF page:** 3
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-2-p003.md](text/visuals/figure-2-p003.md)
- **Caption:** Figure 2: Overview of the Temporal Graph Benchmark (TGB) pipeline: (a) TGB includes large-scale and realistic datasets from five different domains with both dynamic link prediction and node property prediction tasks. (b) TGB automatically downloads datasets and processes them into numpy, PyTorch and PyG compatible TemporalData formats. (c) Novel TG models can be easily evaluated on TGB datasets via reproducible and realistic evaluation protocols. (d) TGB provides public and online leaderboards to track recent developments in temporal graph learning domain. The code is publicly available as a Python library.

## Figure 3

- **PDF page:** 5
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-3-p005.md](text/visuals/figure-3-p005.md)
- **Caption:** Figure 3: The node affinity prediction task aims to predict how the preference of a user towards items changes over time. In the tgbn-genre example, the task is to predict the frequency at which the user would listen to each genre over the next week given their listening history until today.

## Table 1

- **PDF page:** 6
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [table-1-p006.md](text/visuals/table-1-p006.md)
- **Caption:** Table 1: Dataset Statistics. Dataset names are colored based on their scale as small, medium, and large. ¶: Edges can be Weighted, Directed, or Attributed.

## Table 1

- **PDF page:** 6
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [table-1-p006.md](text/visuals/table-1-p006.md)
- **Caption:** Table 1 shows the statistics and properties of the temporal graph datasets provided by TGB. Datasets such as tgbl-flight, tgbl-comment, tgbl-coin, and tgbn-reddit are orders of magnitude larger than existing TG benchmark datasets [35, 33, 24], while their number of nodes and edges span a wide spectrum, ranging from thousands to millions. In addition, TGB dataset domains are highly diverse, coming from five distinct domains including social networks, interaction networks, rating networks, traffic networks, and trade networks. Moreover, the duration of the datasets varies from months to years, and the number of timestamps in TGB datasets ranges from 32 to more than 30 million with diverse ranges of time granularity from UNIX timestamps to annually. The datasets can be weighted, directed, or have edge attributes. We also report the surprise index (i.e., |Etest\Etrain|

## Table 2

- **PDF page:** 8
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [table-2-p008.md](text/visuals/table-2-p008.md)
- **Caption:** Table 2: Results for dynamic link property prediction on small datasets.

## Figure 4

- **PDF page:** 8
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [figure-4-p008.md](text/visuals/figure-4-p008.md)
- **Caption:** Figure 4: Test set inference time of TG methods can have up to two orders of magnitude difference.

## Table 2a

- **PDF page:** 8
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [table-2a-p008.md](text/visuals/table-2a-p008.md)
- **Caption:** Table 2a shows the performance of TG methods for dynamic link property prediction on the tgbl-wiki dataset. tgbl-wiki is an existing dataset where many methods achieve over-optimistic performance in the literature [35, 46, 9]. With TGB’s evaluation protocol, there is now a clear distinction in model performance and NAT achieves the best result on this dataset. As tgbl-wiki is the smallest dataset in this task, it is computationally feasible to sample all possible destinations of a given source node. Thus, we compare the true destination with all possible negative destinations in this dataset. In Table 2b, we report the results on tgbl-review where we sample 100 negative edges per positive edge. Here, we observe that many of the best performing methods on tgbl-wiki has a significant drop in performance including NAT, CAWN and Edgebank. More notably, the method rankings also changed significantly with GraphMixer and TGAT being the top two methods. This observation emphasizes the importance of dataset diversity when benchmarking TG methods. In Appendix H, we conduct an ablation study on the effect of number of negative samples on the performance of dynamic link property prediction.

## Figure 5

- **PDF page:** 9
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [figure-5-p009.md](text/visuals/figure-5-p009.md)
- **Caption:** Figure 5: Total train and validation time of TG methods can have two orders of magnitude difference.

## Table 3

- **PDF page:** 9
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [table-3-p009.md](text/visuals/table-3-p009.md)
- **Caption:** Table 3: Results for dynamic link property prediction task on medium and large datasets.

## Figure 4a

- **PDF page:** 9
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [figure-4a-p009.md](text/visuals/figure-4a-p009.md)
- **Caption:** Figure 4a and 4b show the inference time of different methods for the test set of tgbl-wiki and tgbl-review, respectively. Similarly, Figure 5a and 5b show the total training and validation time of TG methods for tgbl-wiki and tgbl-review. Notice that as a heuristic baseline, EdgeBank inference, train, or validation time is generally at least one order of magnitude lower than neural network based methods. We also observe an order of difference in inference time within TG methods. We believe one important future direction is to improve the computational time of these models to be closer to baselines such as EdgeBank, which can better scale to large real-world temporal graphs.

## Table 3

- **PDF page:** 9
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [table-3-p009.md](text/visuals/table-3-p009.md)
- **Caption:** Table 3 shows the performance of TG methods on medium and large TGB datasets. Note that some methods, including CAWN, TCL, and GraphMixer, ran out of memory on GPU for these datasets, thus their performance is not reported. Overall, TGN has the best performance on all of these three datasets. Surprisingly, the EdgeBank heuristic is highly competitive on the tgbl-coin dataset where it even significantly outperforms DyRep. Therefore, it is important to include EdgeBank as a baseline for all datasets. Another observation is that for medium and large TGB datasets, there can be a significant performance change for a single model between the validation and test set. This is because TGB datasets span over a long time (such as tgbl-comment, lasting 5 years) and one can expect that models need to deal with potential distribution shifts between the validation set and the test set. Figure 6a, 6b and 6c reports the test time for TG methods on tgbl-coin, tgbl-flight and tgbl-comment, respectively. On both tgbl-coin and tgbl-comment, Edgebank is at least one order of magnitude faster than TGN and DyRep while on the tgbl-flight, due to the large number of temporal edges, DyRep is the fastest method.

## Table 4

- **PDF page:** 9
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [table-4-p009.md](text/visuals/table-4-p009.md)
- **Caption:** Table 4 shows the performance of various methods on the node affinity prediction task in the dynamic node property prediction category. As node-level tasks have received less attention compared to edge-level tasks in the literature, adopting methods that are specially designed for link prediction to this task is non-trivial. As a result, these methods are omitted in this section. Considering Table 4, the key observation is that simple heuristics like persistence forecast and moving average are strong contenders to TG methods such as DyRep and TGN. Notably, persistence forecast is SOTA on tgbn-trade while moving average is the best performing on other datasets. TGN is second place on tgbn-genre dataset. Different from link prediction where the existence of a link is casted as binary classification, the node affinity prediction task compares the likelihood or weight that the model assigns to different target nodes (mostly positive links). These results highlight the need for the future development of TG methods that can acquire flexible node representations capable of learning how user preferences evolve over time.

## Figure 6

- **PDF page:** 10
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [figure-6-p010.md](text/visuals/figure-6-p010.md)
- **Caption:** Figure 6: Inference time comparison of TG methods.

## Table 4

- **PDF page:** 10
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [table-4-p010.md](text/visuals/table-4-p010.md)
- **Caption:** Table 4: Node affinity prediction results.

## Figure 7

- **PDF page:** 17
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [figure-7-p017.md](text/visuals/figure-7-p017.md)
- **Caption:** Figure 7: GPU Memory Usage for tgbl-wiki dataset.

## Table 5

- **PDF page:** 17
- **Status:** partial
- **Sources:** caption, suggested-region-text, body-references
- **Text card:** [table-5-p017.md](text/visuals/table-5-p017.md)
- **Caption:** Table 5: Additional dataset properties. Dataset names are colored based on their scale as small, medium, and large. ⋆: denotes the average number of edges per timestamp.

## Table 6

- **PDF page:** 18
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [table-6-p018.md](text/visuals/table-6-p018.md)
- **Caption:** Table 6: Results for dynamic link property prediction on small datasets with 20 negative samples.

## Table 7

- **PDF page:** 18
- **Status:** partial
- **Sources:** caption, suggested-region-text
- **Text card:** [table-7-p018.md](text/visuals/table-7-p018.md)
- **Caption:** Table 7: Transductive vs. Inductive Setting on tgbl-wiki Dataset.
