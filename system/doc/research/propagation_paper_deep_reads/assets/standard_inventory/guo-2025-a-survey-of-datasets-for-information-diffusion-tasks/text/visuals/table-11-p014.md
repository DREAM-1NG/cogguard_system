# Text evidence: Table 11

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 14
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [43.502, 243.974, 305.654, 424.129]

## Caption

Table 11: Performance comparison between ARG and base- lines of fake news detection task on two datasets (Weibo21 and GossipCop of FakeNewsNet). The best results in accu- racy, F1-score and macro F1 are bolded.

## Text from suggested visual region

~~~text
Table 11: Performance comparison between ARG and base-
lines of fake news detection task on two datasets (Weibo21
and GossipCop of FakeNewsNet). The best results in accu-
racy, F1-score and macro F1 are bolded.


                                Weibo21                  GossipCop
        Method
                      macF1  Acc 𝐹1𝑟𝑒𝑎𝑙𝐹1𝑓𝑎𝑘𝑒macF1  Acc 𝐹1𝑟𝑒𝑎𝑙𝐹𝑙𝑓𝑎𝑘𝑒

 G1:LLM-
          GPT-3.5-turbo       0.725  0.734   0.774    0.676    0.702  0.813   0.884    0.519
  Only

           Baseline             0.753  0.754   0.769    0.737    0.765  0.862   0.916    0.615
 G2: SLM- EANNT             0.754  0.756   0.773    0.736    0.763  0.864   0.918    0.608
  Only   Publisher-Emo       0.761  0.763   0.784    0.738    0.766  0.868   0.920    0.611
        ENDEF              0.765  0.766   0.779    0.751    0.768  0.865   0.918    0.618

           Baseline+Rationale  0.767  0.769   0.787    0.748    0.777  0.870   0.921    0.633
 G3: LLM  SuperICL            0.757  0.759   0.779    0.734    0.736  0.864   0.920    0.551
 +SLM  ARG               0.784  0.786  0.804   0.764   0.790  0.878  0.926   0.653
        ARG-D              0.771  0.772   0.785    0.756    0.778  0.870   0.921    0.634

   ARG-D is the rationale-free ARG by distillation for cost-sensitive scenarios.
~~~

## Body references

- [PDF p.8] The representative SOTA methods for the subtasks of misinforma- tion detection are introduced in this paragraph respectively. They briefly introduce the landmark algorithms and current performance in this task. • Rumor detection: Graph-aware Multi-feature Interacting Network (GMIN) [23] detects rumors on social media by integrating text, user interactions, and propagation. It includes a Text-based Rea- soning module that uses BERT and CNN-BiGRU for feature ex- traction, a Graph-aware Interaction module that constructs a user-text graph with GAT, a Propagation Structure module that applies GCN on diffusion graphs, and a Feature Collaboration module that fuses features via co-attention for early detection and interpretability. Table 10 presents the performance com- parison between GMIN and baseline models on three datasets (Ma-Weibo [77], Twitter15 [78] and Twitter16 [78]), measured by precision, recall, F1-score, and accuracy. • Fake news detection: Adaptive Rationale Guidance (ARG) net- work [24] employs Large and Small Language Models for fake news detection. It inputs news and rationales from an LLM, en- codes them with BERT, and uses cross-attention to integrate rationales for classification, outperforming LLM-only and SLM- only methods. Table 11 presents the performance comparison between ARG and baseline models on two datasets (Weibo21 [91] and GossipCop of FakeNewsNet [47]), measured by accuracy, F1- score and macro F1.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
