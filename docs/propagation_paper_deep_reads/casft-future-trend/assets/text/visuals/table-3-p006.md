# Text evidence: Table 3

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 6
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [44.0, 310.531, 568.019, 714.407]

## Caption

Table 3: Performance comparison between CasFT and CasFT-variants on three datasets under two observation times measured by MSLE, MAPE (lower is better).

## Text from suggested visual region

~~~text
Table 3: Performance comparison between CasFT and CasFT-variants on three datasets under two observation times measured
by MSLE, MAPE (lower is better).

 • Sina Weibo: Weibo is the largest Chinese microblogging      havior for predicting popularity. CTCP (Lu et al. 2023) pro-
   platform, where each original microblog post and subse-      poses an evolution learning module that updates the states of
   quent reposts can form a repost cascade.                      users and cascades in real time as diffusion behaviors occur.

  Following previous works (Xu et al. 2021; Lu et al. 2023),                                                    Evaluation Metrics
we set observation time as 1 day and 2 days for the Twitter
                                              Two commonly used metrics, mean squared logarithmic er-dataset, and 3 years and 5 years for the APS dataset, for
                                                                     ror (MSLE) and mean absolute percentage error (MAPE),Weibo, the observation times are set to 0.5 hours and 1 hour.
                                                                 are employed to evaluate the performance of models:Furthermore, prediction time is set to 15 days for Twitter, 20
years for APS, and 24 hours for Weibo. In addition, we filter
out cascades with fewer than 10 participants during the ob-             M                                                                 1
servation periods. For all datasets, 70% of the data is used for    MSLE = X (log2 (P + 1) −(log2 ( ˆP + 1))2,  (26)
                                 Mtraining, 15 % for validation, and 15% for testing. Detailed                   k=1
information about the three datasets is provided in Table 1.
                                             M  log2 (P + 2) −log2 ( ˆP + 2)                                                                 1
                                 MAPE = X                                              ,  (27)
Baselines                             M                                                                      k=1         log2 (P + 2)
We compare CasFT against a sizeable collection of state-of-
the-art baselines: Feature-based methods extract key fea-      where P represents the true popularity, ˆP denotes the pre-
tures (cascade size, temporal intervals, etc.) and use an       dicted popularity, and M represents the number of cascades.
MLP model for prediction. SEISMIC (Zhao et al. 2015) de-     The operations ’+ 1’ and ’+ 2’ are used for scaling to avoid
signs a statistical model based on the theory of self-excited       potential zero values in the denominator or logarithmic op-
point processes. DeepCas (Li et al. 2017) represents cas-       erations.
cades as random walk paths and uses a bi-directional GRU
with attention for effective modeling and prediction. Deep-     Performance Comparison (RQ1)
Hawkes (Cao et al. 2017) integrates the Hawkes process      Table 2 shows the overall performance of the three datasets.
and deep learning, focusing on user impact, self-excitation,    We observe that our method CasFT significantly outper-
and time decay for cascade modeling. CasCN (Chen et al.      forms all baselines on MSLE and MAPE. For example, com-
2019) adopts a novel multi-directional/dynamic GNN. Va-      pared to the best-performing baselines, our CasFT achieves
cas (Zhou et al. 2020b) devises a hierarchical graph learning      a 4.2%-19.3% improvement of MSLE, and a 2.2%-8.6% im-
method and leverages a variational autoencoder for model-      provement of MAPE, on the three datasets with two different
ing the uncertainty. CasFlow (Xu et al. 2021) mainly consid-      observation times. We see that CasFT demonstrates notable
ers the effects of local and global graphs to represent user be-      enhancement, especially on the Twitter dataset. This can be
~~~

## Body references

- [PDF p.7] Ablation Study (RQ2 & RQ3) To answer RQ2 and RQ3, we have conducted a series of experiments where we introduced different variants of our CasFT model. We conduct the ablation study to investigate the contribution of each component and develop four vari- ants: 1) CasFT-w/o FT. We remove the future trend model- ing module and only use the spatiotemporal features S for prediction; 2) CasFT-w/o ODE. We take the spatiotempo- ral features S as the condition of the later diffusion models, without parameterizing the growth rate; 3) CasFT-w/o Dif- fusion. We remove the diffusion block and directly input the condition c into an MLP; and 4) CasFT-FM. We just use an MLP to replace our future trend modules, predict both the segmented popularity and the incremental popularity during (to, tp), and also take the predicted segmented popularity se- quence as a significant cue. The results and comparison of these variants are shown in Table 3. The comparison of CasFT over CasFT-w/o FT validates the necessity of modeling the future trend of cas- cade with an improvement of up to 20.75%. Through a comparative analysis of CasFT-w/o FT, CasFT-w/o ODE, and CasFT-w/o Diffusion, it becomes evident that model- ing the growth rate and segmented popularity generation both facilitate prediction accuracy, achieving improvements of 20.75%, 13.63%, and 10.70% respectively. We also de- signed a variant CasFT-FM which outperforms CasFT-w/o FT but is worse than CasFT, showing the usefulness of our proposed future trend block.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
