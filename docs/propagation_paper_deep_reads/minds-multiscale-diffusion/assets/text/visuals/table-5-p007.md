# Text evidence: Table 5

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 7
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [44.0, 169.648, 568.019, 474.283]

## Caption

Table 5: Ablation study on Christianity and Douban datasets. We design six variants to demonstrate the rationale behind our model: w/o AdvDiff removes Ladv and Ldiff. w/o Diff removes Ldiff. w/o Adv removes Ladv. w/o HGNN replaces sequential hypergraphs with sequential digraphs and HGNN with GAT. w/o Macro removes Lmacro. w/o Micro removes Lmicro.

## Text from suggested visual region

~~~text
Table 5: Ablation study on Christianity and Douban datasets. We design six variants to demonstrate the rationale behind our
model: w/o AdvDiff removes Ladv and Ldiff. w/o Diff removes Ldiff. w/o Adv removes Ladv. w/o HGNN replaces sequential
hypergraphs with sequential digraphs and HGNN with GAT. w/o Macro removes Lmacro. w/o Micro removes Lmicro.


         MAP@100      MAP@10         Hits@50       MSLE           MAP@100      MAP@10         Hits@50       MSLE
         MAP@50         Hits@100        Hits@10                     MAP@50         Hits@100        Hits@10
     0.122                                                                   0.0                                                                                0.0
                                                                                0.072
                                                                              0.2                                                                                0.2
     0.120
                                                                                0.070
                                                                              0.4                                                                                0.4
     0.118
                                                                              0.6      0.068                                                                   0.6
     0.116
                                                                              0.8      0.066                                                                   0.8
     0.114
                                                                              1.0      0.064                                                                   1.0
               0.25    0.50    0.75         2   4   6   8   10  12                    0.25    0.50    0.75         2   4   6   8   10  12
                                                             Intervals                                                                             Intervals
     0.375                                                                   0.0                                                                                0.0                                                                                0.275
                                                                              0.2      0.235                                                                   0.2     0.325
                                                                              0.4      0.195                                                                   0.4
     0.275
                                                                              0.6      0.155                                                                   0.6
     0.225
                                                                              0.8      0.115                                                                   0.8

     0.175                                                                   1.0      0.075                                                                   1.0
              0.025   0.050   0.075        8   16  32  64  128 256                  0.025   0.050   0.075        8   16  32  64  128 256
                                            Embedding…size                                                     Embedding…size

                                 (a) Douban                                                          (b) Android
~~~

## Body references

- [PDF p.6] Ablation Study We conduct ablation studies on the Christianity and Douban datasets to evaluate the individual contributions of different submodules in MINDS. As shown in Table 5, MINDS achieves the best results compared to other variants, indicating the effectiveness of its design. Specifically, the observations are as follows: 1) Model performance declines after removing Ladv, Ldiff, or both, validating the importance of introducing ad- versarial training and orthogonality constraints to address feature redundancy. 2) Introducing a series of interactive hypergraphs effec- tively captures cascade interactions from a global perspec- tive, as demonstrated by the results of w/o HGNN. 3) Macroscopic prediction improves microscopic predic- tion by accurately predicting the propagation behavior of in- dividual users. Conversely, microscopic prediction enhances the understanding and interpretation of overall propagation trends by macroscopic prediction. Significant differences between w/o Macro, w/o Micro, and MINDS in macro and micro indicators reveal the mutual reinforcement between the two tasks, leading to improved performance.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
