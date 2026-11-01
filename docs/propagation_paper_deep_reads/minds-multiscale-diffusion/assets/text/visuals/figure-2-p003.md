# Text evidence: Figure 2

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 3
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [70.032, 53.476, 541.987, 322.988]

## Caption

Figure 2: The architectural overview of our model.

## Text from suggested visual region

~~~text
User Global Interactive Learning
                                                                Shared-private
                                                           Representation Learning              Diﬀusion Prediction

                      GD1  HGNN        Fusion Layer
                                        LSTM            MLPMLP                                       ?
Diffusion hypergraph

                      GD2  HGNN        Fusion Layer                                                         Macro Prediction
                              ……                        Ldiff
                                 XD

                                               Shared
 Diffusion sequence                               LSTM             Ladv
                   HGNN                      GDT
           User Social Homophily Learning                  Ldiff                                     Micro Prediction
                                 XS                                                ?
                                                       MLP             ?                                        LSTM           MLP            ?
     Social graph           GCN

                           Figure 2: The architectural overview of our model.
~~~

## Body references

- [PDF p.2] Method In this section, we will provide a comprehensive introduc- tion to the proposed model. The architectural overview of the proposed model is depicted in Fig. 2, which comprises four primary modules: User Global Interactive Learning Module: This module is responsible for extracting user preferences at each time interval and characterizing the dynamic changes of cascades. A fusion layer at the cascade level facilitates this process. User Social Homophily Learning Module: It captures users’ social relationship at the individual user level using Graph Convolutional Networks (GCN). Shared-private Representation Learning Module: This module learns task-specific representations and shared rep- resentations to facilitate diffusion prediction. Diffusion Prediction Module: This module concatenates task-specific features with shared representation for macro- scopic and microscopic diffusion prediction, respectively.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
