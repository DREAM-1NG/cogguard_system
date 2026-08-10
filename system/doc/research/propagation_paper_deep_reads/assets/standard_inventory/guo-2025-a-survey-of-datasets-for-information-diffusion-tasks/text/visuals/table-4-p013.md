# Text evidence: Table 4

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 13
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [43.502, 324.06, 304.047, 498.577]

## Caption

Table 4: Performance comparison between RAGTrans and baselines of popularity prediction task on three datasets (SMPD, ICIP, and WeChat). The best results in MSE, MAE and SRC are bolded.

## Text from suggested visual region

~~~text
Twitter-casflow               Sina Weibo                APS
  Model
                   1 Day        2 Days        0.5 Hour      1 Hour       3 Years       5 Years

            MSLE MAPE MSLE MAPE MSLE MAPE MSLE MAPE MSLE MAPE MSLE MAPE

  Feature-SH     14.792  0.960  13.515  0.983   4.455   0.390   4.001   0.398   2.382   0.316   2.348   0.350
  TimeSeries      8.214   0.547   6.023   0.445   3.119   0.277   2.693   0.268   1.867   0.271   1.735   0.291
   Feature-Linear  9.326   0.520   6.758   0.459   2.959   0.258   2.640   0.271   1.852   0.272   1.728   0.291
  Feature-Deep   7.438   0.485   6.357   0.500   2.715   0.228   2.546   0.272   1.844   0.270   1.666   0.282
  DeepHawkes    7.216   0.587   5.788   0.536   2.891   0.268   2.796   0.282   1.573   0.271  1.324   0.335
  CasCN          7.183   0.547   5.561   0.525   2.804   0.254   2.732   0.273   1.562   0.268   1.421   0.265
  DMT-LIC       7.152   0.467   5.427   0.481   2.752   0.249   2.689   0.270   1.539   0.264   1.398   0.258
  CasFlow*      6.954  0.455  5.143  0.361  2.402  0.210  2.279  0.238  1.361  0.222  1.354*  0.248

  A paired t-test is performed and * indicates a statistical significance 𝑝< 0.001 as compared to the best baselines.


Table 4: Performance comparison between RAGTrans and
baselines of popularity prediction task on three datasets
(SMPD, ICIP, and WeChat). The best results in MSE, MAE
and SRC are bolded.
~~~

## Body references

- [PDF p.5] and propagation uncertainty. The model first analyzes both local and global diffusion patterns, then captures user interactions over time with Bi-GRUs. Following this, the model encodes un- certainty in propagation using Variational Autoencoders (VAEs) and refines predictions with Normalizing Flows. Table 3 presents its performance comparison between CasFlow and baseline mod- els across three datasets (Twitter-casflow [26], APS [26], and Sina Weibo [55]) with different observation times, measured by MSLE and MAPE. • Popularity prediction: RAGTrans[35] introduces a retrieval-augmented model for predicting the popularity of multimodal social media content. It retrieves relevant instances from a user-generated con- tent (UGC) memory bank, builds a multimodal hypergraph, and applies a bootstrapping transformer for neighborhood aggrega- tion. After that, a user-aware fusion module combines multimodal data with user characteristics. Table 4 presents its performance comparison between RAGTrans and baseline models on three datasets (SMPD [32], ICIP [60], and WeChat [35]), measured by MSE, MAE and SRC. • User attitudes prediction: Neutral state model[31] introduces a neutral state model to represent the crowd attitudes during rumor propagation by segmenting individuals into Ignorants, Spreaders, Skeptics, and Stifflers with varying beliefs. The model uses dynamic equations to simulate the flow of individuals and incorporates parameters for rumor spread rate and the influence of neutral discussions. Table 5 shows its simulated results of neutral state model and XYWZ1Z2 model compared

[TRUNCATED BY EXTRACTOR]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
