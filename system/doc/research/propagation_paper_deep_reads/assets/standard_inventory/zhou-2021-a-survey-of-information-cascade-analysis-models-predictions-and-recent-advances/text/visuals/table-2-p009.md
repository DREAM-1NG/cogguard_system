# Text evidence: Table 2

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 9
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [35.945, 100.238, 449.906, 474.347]

## Caption

Table 2. Frequently Used Scenarios in Popularity Prediction Literature

## Text from suggested visual region

~~~text
Metric                   Formulation                      Reference
Accuracy                         -                   [20, 34, 35, 39, 49, 50, 60, 61, 73, 81, 84, 90, 92, 124, 131, 138,
                                                 142, 165, 172, 173, 175, 187, 189, 200, 215, 225, 241]
                                          ˆPi−PiAccuracy with tolerance τ    1(|            | ≤τ )    [15, 16, 30, 48, 62, 63, 73, 174, 214, 234, 235], [247]∗                                           Pi
Area under the ROC Curve    -                   [23, 39, 49, 50, 60, 61, 84, 86, 149, 158, 194, 200, 230]
Coefficient of Determination  -                   [11, 50, 108, 109, 135, 136, 163, 177, 186, 212], [1, 12, 31]†
Coefficient of Correlation      -                   [47, 77, 84, 151, 170, 186, 188, 205, 246], [20, 64, 132, 192,
                                                 209, 210]†
F1 or Fβ Score                   -                     [4, 19, 23, 39, 46, 49, 50, 58, 60, 63, 68, 71, 72, 81, 84, 85, 88,
                                                    97, 100, 101, 103, 124, 128, 155, 158, 165, 173, 179, 189, 191,
                                                 200, 208, 217, 219, 227, 229, 230, 241], [54, 61, 96, 126, 134,
                                                 135, 220]‡
Mean Absolute Error      M1     iM  | ˆPi −Pi |   [50, 95, 151, 200, 212], [217]∗, [14, 130, 132, 160, 171, 201,
                                                 202, 209, 243]†
                                  1  M  ˆPi−Pi
Mean Abs. Percent. Error   M     i    |  Pi     |    [15, 16, 30, 41, 48, 59, 62, 63, 72, 74, 78, 87, 99, 123, 125, 129,
                                                 133, 142, 170, 174, 203, 205, 214, 219, 238, 246], [217, 247]∗,
                                                    [92]†, [250]∗†
Mean Square Error       M1     iM ( ˆPi −Pi )2  [3, 63, 72, 161], [37]∗, [36, 47, 105, 106, 132, 171, 181, 192,
                                                 201, 202, 216, 220, 221, 233, 243]†, [29, 38, 119, 120, 250]∗†
Precision                          -                     [1, 4, 7, 19, 23, 46, 49, 50, 58, 60, 63, 68, 71, 72, 81, 90, 101,
                                                 103, 158, 165, 173, 191, 207, 208, 215, 217, 219, 227, 229, 230,
                                                 232, 234, 241, 248], [61, 126, 134, 135]‡
Recall                             -                     [1, 4, 7, 19, 23, 46, 49, 50, 58, 60, 63, 68, 71, 72, 81, 88, 90,
                                                 101, 103, 158, 165, 173, 191, 207, 208, 215, 217, 219, 227, 229,
                                                 230, 241, 248], [61, 126, 134, 135]‡
Root Mean Square Error      M1     iM ( ˆPi−Pi )2    [72, 74, 114, 133, 137, 186], [14, 72, 100, 101, 151, 234, 235]†
∗Some models use incremental popularity, i.e., P →ΔP = P (tp ) −P (to).
† Some models use logarithmic popularity (error), i.e., P →log P, or other similar transformations/normalizations.
‡ Some models use macro/micro-Precision, macro/micro-Recall, or macro/micro-F1.


                 Table 2. Frequently Used Scenarios in Popularity Prediction Literature
~~~

## Body references

- [PDF p.8] In Table 2, we list widely used and publicly available datasets. The scope of information items ranges broadly, from news articles, academic papers, posted images, music and videos, and these diverse scenarios of popularity prediction cause difficulties in the design of prediction models. Whether for feature extractions, problem formulations, evaluation selections, devising of genera- tive processes, or deep learning architecture designs, it is difficult and sometimes even impossible to fully generalize one model from one specific platform to another. The datasets used throughout this survey contain two microblog datasets, Twitter1 hashtags [207] and Weibo2 tweets [29], and one scientific dataset APS3 papers [174]. The basic statistics of the three datasets are shown in Table 3.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
