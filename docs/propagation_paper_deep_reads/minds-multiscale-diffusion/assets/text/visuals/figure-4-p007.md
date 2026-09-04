# Text evidence: Figure 4

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 7
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [44.0, 214.365, 568.013, 531.608]

## Caption

Figure 4: Parameter sensitivity on Douban and Android dataset. For balance parameter λ ∈(0, 1) and the number of time intervals ∈[2, 12], we evaluate all map and MSLE scores. For hyper parameter γ ∈(0, 0.1) and embedding size ∈{8, 16, 32, 64, 128, 256}, we evaluate all hits scores and MSLE score. In this figure, the macro indicator (MSLE) is pre- sented with an inverted Y-axis to align with the increasing trend of the micro indicator (MAP and Hits).

## Text from suggested visual region

~~~text
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

Figure 4: Parameter sensitivity on Douban and Android dataset. For balance parameter λ ∈(0, 1) and the number of
time intervals ∈[2, 12], we evaluate all map and MSLE scores. For hyper parameter γ ∈(0, 0.1) and embedding size
∈{8, 16, 32, 64, 128, 256}, we evaluate all hits scores and MSLE score. In this figure, the macro indicator (MSLE) is pre-
sented with an inverted Y-axis to align with the increasing trend of the micro indicator (MAP and Hits).
~~~

## Body references

- [PDF p.7] γ, embedding size, and the number of time intervals, test- ing each parameter while keeping others fixed. Fig. 4 illus- trates the model’s performance on multi-scale prediction un- der various hyperparameter configurations.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
