# Text evidence: Table 2

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 8
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [26.0, 562.888, 586.001, 767.6]

## Caption

Table 2. ROC-AUC as well as the PR-AUC universal score.

## Text from suggested visual region

~~~text
Table 2. ROC-AUC as well as the PR-AUC universal score.

               Data set                  ROC-AUC         ROC-AUC sample          PR-AUC          PR-AUC sample

                       All                             0.85 (0.84–0.86)              0.85 (0.85–0.86)              0.77 (0.75–0.79)             0.50 (0.49–0.51)

    German politicians and German bots            0.76 (0.70–0.83)              0.76 (0.76–0.77)              0.10 (0.07–0.14)             0.27 (0.27–0.27)

       German politicians and bots                 0.77 (0.74–0.79)              0.76 (0.76–0.77)              0.81 (0.78–0.84)             0.30 (0.30–0.31)

        US politicians and bots                   0.93 (0.92–0.94)              0.93 (0.93–0.93)              0.96 (0.95–0.97)             0.79 (0.79–0.80)

                Varol et al.                         0.86 (0.84–0.88)              0.86 (0.86–0.86)              0.76 (0.73–0.79)             0.58 (0.58–0.59)

ROC-AUC as well as the PR-AUC scores for the original data sets as well as the weighted resampled data sets (sample = 100,000) for the universal score. The 95%

confidence intervals based on 10,000 stratified bootstrap replicates are shown in brackets.

https://doi.org/10.1371/journal.pone.0241045.t002


PLOS ONE | https://doi.org/10.1371/journal.pone.0241045  October 22, 2020                                                         8 / 20
~~~

## Body references

- [PDF p.7] Our analysis (see Fig 2 and Table 2) shows that the ROC-AUC is worse with our complete data (AUC = 0.85) than with the data sets used in the Botometer creators’ original papers which received an AUC of 0.94 [4]. However, their baseline model also received only an AUC of 0.85 in the original paper. The nearer the ROC curve (Fig 2) is to the upper-left corner and the more space is under the curve, the better Botometer can distinguish between bots and humans. In the lower-left corner the curve starts with a threshold of 0 for the Botometer which means the false-positive rate is 0 but at the same time 0 of the bots in the population will be identified. The curve ends with a threshold of 1 in the upper-right corner as then all bots in the popula- tion will be identified. However, such a threshold also means that all human accounts will be wrongly classified as bots (false-positive rate = 1). Each point in the curve thus represents a specific threshold for which the true positive rate as well as the false positive rate is shown. When applying this to our data sets, we see that the classifier has the highest AUC score for the US politicians and bots data set (0.93) followed by Varol et al.’s labeled data set (0.86). The score for the German politicians and German bots yields a lower score (0.76). As we only had a few German bots we also tested the German politicians and bots (with the new bots instead of the German bots) which had a slightly higher AUC (0.78). We, then, calculated the ROC-AUC for the universal CAP (complete automation probabil- ity; Fig 3 and Table 3). We could ob

[TRUNCATED BY EXTRACTOR]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
