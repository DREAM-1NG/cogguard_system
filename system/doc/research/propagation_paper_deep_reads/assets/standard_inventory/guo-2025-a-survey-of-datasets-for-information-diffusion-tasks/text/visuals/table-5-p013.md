# Text evidence: Table 5

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 13
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [307.659, 74.184, 569.81, 188.862]

## Caption

Table 5: Performance comparison between neutral state model and XYWZ1Z2 baseline model of user attitudes pre- diction task compared with the actual data on the COVID-19- rumor dataset. The best results in MAE and MSE are bolded.

## Text from suggested visual region

~~~text
Table 5: Performance comparison between neutral state
model and XYWZ1Z2 baseline model of user attitudes pre-
diction task compared with the actual data on the COVID-19-
rumor dataset. The best results in MAE and MSE are bolded.


                    RMSE                 MAE
      Model
                  𝑧0     𝑧1    𝑧2   𝑠𝑢𝑚     𝑧0     𝑧1    𝑧2   𝑠𝑢𝑚

     XYWZ1Z2 15504.88 279.15 133.07 15507.96 10130.19 193.52 96.43 10420.14
        Neutral    1284.82  387.77  253.01 1365.71  917.77  266.27 171.54 1355.58
~~~

## Body references

- [PDF p.5] and propagation uncertainty. The model first analyzes both local and global diffusion patterns, then captures user interactions over time with Bi-GRUs. Following this, the model encodes un- certainty in propagation using Variational Autoencoders (VAEs) and refines predictions with Normalizing Flows. Table 3 presents its performance comparison between CasFlow and baseline mod- els across three datasets (Twitter-casflow [26], APS [26], and Sina Weibo [55]) with different observation times, measured by MSLE and MAPE. • Popularity prediction: RAGTrans[35] introduces a retrieval-augmented model for predicting the popularity of multimodal social media content. It retrieves relevant instances from a user-generated con- tent (UGC) memory bank, builds a multimodal hypergraph, and applies a bootstrapping transformer for neighborhood aggrega- tion. After that, a user-aware fusion module combines multimodal data with user characteristics. Table 4 presents its performance comparison between RAGTrans and baseline models on three datasets (SMPD [32], ICIP [60], and WeChat [35]), measured by MSE, MAE and SRC. • User attitudes prediction: Neutral state model[31] introduces a neutral state model to represent the crowd attitudes during rumor propagation by segmenting individuals into Ignorants, Spreaders, Skeptics, and Stifflers with varying beliefs. The model uses dynamic equations to simulate the flow of individuals and incorporates parameters for rumor spread rate and the influence of neutral discussions. Table 5 shows its simulated results of neutral state model and XYWZ1Z2 model compared

[TRUNCATED BY EXTRACTOR]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
