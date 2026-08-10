# Text evidence: Table 10

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 14
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [43.502, 74.184, 305.646, 248.588]

## Caption

Table 10: Performance comparison between GMIN and base- lines of rumor detection task on three datasets (Ma-Weibo, Twitter15 and Twitter16). The best results in precision, recall, F1-score and accuracy are bolded.

## Text from suggested visual region

~~~text
Table 10: Performance comparison between GMIN and base-
lines of rumor detection task on three datasets (Ma-Weibo,
Twitter15 and Twitter16). The best results in precision, recall,
F1-score and accuracy are bolded.


                     Ma-Weibo        Twitter15  Twitter16
       Model
                  F1  Rec  Pre  Acc   F1  Rec  Pre  Acc

       Rumor2vec 0.952  0.952  0.952  0.951  0.797  0.723  0.851  0.852
       dEFEND    0.913  0.915  0.913  0.914  0.654  0.738  0.631  0.702
      HB-GAT    0.955  0.954  0.954  0.955  0.919  0.920 0.951 0.951
       BiGCN     0.960 0.963  0.961  0.961  0.891  0.886  0.847  0.880
      GCAN      0.854  0.854  0.854  0.854  0.825  0.877  0.759  0.908
      GLAN      0.946  0.943  0.943  0.945  0.924  0.905  0.921  0.902
      RvNN       0.908  0.908  0.908  0.908  0.729  0.723  0.737  0.737
       PPC        0.920  0.926  0.923  0.921  0.811  0.842  0.820  0.863
      GMIN      0.959 0.963 0.957 0.961 0.931 0.921 0.920  0.938
~~~

## Body references

- [PDF p.8] The representative SOTA methods for the subtasks of misinforma- tion detection are introduced in this paragraph respectively. They briefly introduce the landmark algorithms and current performance in this task. • Rumor detection: Graph-aware Multi-feature Interacting Network (GMIN) [23] detects rumors on social media by integrating text, user interactions, and propagation. It includes a Text-based Rea- soning module that uses BERT and CNN-BiGRU for feature ex- traction, a Graph-aware Interaction module that constructs a user-text graph with GAT, a Propagation Structure module that applies GCN on diffusion graphs, and a Feature Collaboration module that fuses features via co-attention for early detection and interpretability. Table 10 presents the performance com- parison between GMIN and baseline models on three datasets (Ma-Weibo [77], Twitter15 [78] and Twitter16 [78]), measured by precision, recall, F1-score, and accuracy. • Fake news detection: Adaptive Rationale Guidance (ARG) net- work [24] employs Large and Small Language Models for fake news detection. It inputs news and rationales from an LLM, en- codes them with BERT, and uses cross-attention to integrate rationales for classification, outperforming LLM-only and SLM- only methods. Table 11 presents the performance comparison between ARG and baseline models on two datasets (Weibo21 [91] and GossipCop of FakeNewsNet [47]), measured by accuracy, F1- score and macro F1.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
