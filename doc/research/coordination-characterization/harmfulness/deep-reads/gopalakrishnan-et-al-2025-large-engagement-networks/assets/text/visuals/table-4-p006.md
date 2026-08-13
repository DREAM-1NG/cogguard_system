# Text evidence: Table 4

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 6
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [44.556, 44.024, 567.446, 271.139]

## Caption

Table 4: Campaign vs. non-campaign classification. Text + MLP is the non-graph based classifier. The best results are in bold.

## Text from suggested visual region

~~~text
Model       Accuracy       Precision       Recall         F1-Score
                      Text + MLP   0.715 ± 0.019   0.705 ± 0.011   0.738 ± 0.038   0.721 ± 0.024
              GCN         0.832 ± 0.078   0.909 ± 0.138   0.750 ± 0.000   0.816 ± 0.064
               GAT         0.856 ± 0.048   0.871 ± 0.090   0.833 ± 0.000   0.850 ± 0.043
                GIN          0.840 ± 0.000   1.000 ± 0.000   0.667 ± 0.000   0.800 ± 0.000                                                                      LEN-small  GraphSAGE   0.900 ± 0.033   0.964 ± 0.073   0.818 ± 0.000   0.884 ± 0.033
                GINE         0.800 ± 0.160   0.896 ± 0.208   0.800 ± 0.100   0.815 ± 0.083
              VNGE        0.875 ± 0.000   0.877 ± 0.000   0.818 ± 0.000   0.857 ± 0.000
               LSD          0.833 ± 0.000   0.833 ± 0.000   0.818 ± 0.000   0.818 ± 0.000
                      Text + MLP   0.57 ± 0.018    0.581 ± 0.02    0.891 ± 0.067   0.701 ± 0.012
              GCN         0.702 ± 0.018   0.869 ± 0.030   0.570 ± 0.025   0.687 ± 0.021
                       LEN  GATGIN          0.7350.633 ±± 0.0150.065   0.7830.676 ±± 0.0320.091   0.7520.791 ±± 0.0560.157   0.7650.710 ±± 0.0180.037
                 GraphSAGE   0.729 ± 0.006   0.930 ± 0.001   0.578 ± 0.011   0.713 ± 0.008
                GINE         0.648 ± 0.091   0.673 ± 0.121   0.896 ± 0.139   0.748 ± 0.035
              VNGE        0.747 ± 0.000   0.759 ± 0.000   0.717 ± 0.000   0.767 ± 0.000
               LSD          0.734 ± 0.000   0.734 ± 0.000   0.848 ± 0.000   0.788 ± 0.000

Table 4: Campaign vs. non-campaign classification. Text + MLP is the non-graph based classifier. The best results are in bold.
~~~

## Body references

- [PDF p.7] Binary Classification We first identify campaign networks by distinguishing them from non-campaign networks. Table 4 summarizes the re- sults for LEN, 179+135 graphs, as well as LEN-small, which has 51+49 networks of smaller size. GraphSAGE and VNGE achieve the best accuracy for the small and the complete dataset, while VNGE and LSD achieve the best F1 scores. ROC curves across different training epochs are given in Appendix (Figure 4 refers to the ROC curves for the small dataset and Figure 5 refers to the ROC curves for the complete dataset). One interesting observation is that the accuracy and F1 scores are lower for LEN, which has larger networks than the LEN-small. This highlights the dif- ficulty in classifying large networks, which is expected as most datasets in the graph classification literature contain small networks, as discussed in the related work. Regarding the runtime performance, Figure 2 presents the time taken to run the graph classification models plotted along the size of the graph. We observe that GCN, GIN and GAT have minor changes in performance with graph size. However, GINE shows a linear growth with the size of the graph.
- [PDF p.8] shown in Table 2, where some campaign types have signifi- cantly fewer graphs. This is further demonstrated by the con- fusion matrices shown in Figure 3, where most graphs are classified as either Politics or Reform by the baseline mod- els. Another noteworthy observation is that accuracy and F1 scores for both datasets in multi-class campaign type clas- sification is lower than the scores for binary campaign vs. non-campaign classification (in Table 4). This suggests that
- [PDF p.9] We also investigate a finer-grained binary classification among engagement networks that are based on news. There are 24 campaign networks within which the news are am- plified by bots and trolls, and 52 non-campaign networks that are organically formed due to popular events happen- ing in real world. We conjecture that this subset is uniquely challenging for classification as they share the same theme but different formation processes. To address the imbalance, we randomly sample 24 non-campaign graphs and run the GNNs mentioned above using the same setup above. Table 6 gives the results. LSD performs the best in terms of ac- curacy and F1 score, similar to the case in binary classifica- tion over all networks (Table 4). However, the scores for all the classifiers are consistently lower for the news networks, which again suggests a challenging testbed, especially for the neural network based approaches.
- [PDF p.12] – Did you state the full set of assumptions of all theoret- ical results? No. We don’t have any theoretical results in the paper. – Did you include complete proofs of all theoretical re- sults? No. We don’t have any theoretical results in the paper. • Additionally, if you ran machine learning experiments... – Did you include the code, data, and instructions needed to reproduce the main experimental results (ei- ther in the supplemental material or as a URL)? Yes. The URL for the code and the accompanying instruc- tions are given in Graph classification on engagement networks. The data is provided in the URL in the ab- stract. – Did you specify all the training details (e.g., data splits, hyperparameters, how they were chosen)? Yes. All of them are specified in the section titled Graph classifi- cation on engagement networks under the subsection titled Experimental setup and Graph classifiers. – Did you report error bars (e.g., with respect to the ran- dom seed after running experiments multiple times)? Yes. This is observable in Table 4, 5 and 6. – Did you include the total amount of compute and the type of resources used (e.g., type of GPUs, internal cluster, or cloud provider)? Yes. This is specified in the section titled Graph classification on engagement net- works under the subsection titled Experimental setup. – Do you justify how the proposed evaluation is suffi- cient and appropriate to the claims made? Yes. We do specify that in the section titled Graph classification on engagement networks. – Do you discuss what is “the cost“ of misclassification and fault (in)tol

[TRUNCATED BY EXTRACTOR]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
