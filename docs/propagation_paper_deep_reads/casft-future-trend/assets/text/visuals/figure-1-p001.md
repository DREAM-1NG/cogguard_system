# Text evidence: Figure 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 1
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [309.5, 206.003, 571.4, 525.503]

## Caption

Figure 1: A toy example of information popularity predic- tion problem (top) and the variations of average growth rates after observation time in Weibo and APS datasets, respec- tively (bottom), where t0 represents the observation time and tp represents the prediction time.

## Text from suggested visual region

~~~text
Original tweet       Observed retweet
                            prediction


     Observed Cascade Graph       Incremental Popularity

                                                                                     tptp                         ll
                                                               PiPi                  ∑∑               u1u1             u4u4    PP == ∫∫toto λ*(τ)dτλ*(τ)dτ ==                                                                                                                       ii       u0u0         u2u2
                         u3u3
                                    P1P1   P2P2   P3P3   P4P4
      {{{{                                                   Time
                      tsts == 00      t1t1       t2t2               t3t3          t4t4                toto                                                            tptp

                      Growth Rate


                               toto                                                                   tptp                                        toto                                                               tptp


Figure 1: A toy example of information popularity predic-
tion problem (top) and the variations of average growth rates
after observation time in Weibo and APS datasets, respec-
tively (bottom), where t0 represents the observation time and
tp represents the prediction time.
~~~

## Body references

- [PDF p.1] the number of retweets that may occur within a specified period in the future for a tweet. State-of-the-art approaches mainly focus on capturing spatiotemporal patterns from observed cascades by adopting various deep learning techniques, such as Recurrent Neural Networks (RNNs) (Lu et al. 2023), attention mechanism (Yu et al. 2022) or Graph Neural Networks (GNNs) (Wang et al. 2022; Chen et al. 2019). However, existing approaches pre- dominantly focus on modeling cascades before an obser- vation time, neglecting their evolution of trends between the observation time and the prediction time, which is vi- tal for popularity prediction. For instance, Figure 1 illus- trates the average popularity growth rates between obser- vation (to) and prediction (tp) times in Twitter and APS datasets, where the growth rate represents the increase of popularity per unit of time. Notably, during this period, the
- [PDF p.2] variation in growth rates fluctuates significantly across both two datasets, highlighting different cascade incremental pat- terns, which contributes to the uncertainty in depicting fu- ture diffusion trends. Subsequently, achieving robust pop- ularity prediction necessitates accommodating such uncer- tainties by accounting for cascade evolution patterns after the observation period. Nevertheless, the actual dynamic changes in cascades during this period are invisible when performing real-time popularity prediction. Against this background, we resort to generative models to simulate the cascade evolving patterns between the ob- servation and prediction times for boosting popularity pre- diction performance. However, there exist two difficulties in characterizing the unique features in the patterns: 1) the in- cremental popularity equals the integral of the growth rate, which is highly fluctuated as evidenced by Figure 1; and 2) information diffusion is a complex propagation process that is susceptible to external factors, resulting in varying pat- terns of uncertainties that need to accommodate. To address these challenges, we propose CasFT, a novel information popularity prediction technique that aims to capture the evolving patterns of information Cascades over time, in particular, the Future propagation Trend. CasFT leverages neural Ordinary Differential Equations (ODEs) (Chen et al. 2018) to model the growth rate based on corresponding graph structure and sequential event infor- mation under observation, propagate the growth rate from the observation time to the predict

[TRUNCATED BY EXTRACTOR]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
