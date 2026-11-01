# Text evidence: Figure 8

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 10
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [296.0, 228.616, 514.005, 358.521]

## Caption

Figure 8: PINT: AP (mean and std) as a function of the dimensionality of the positional features.

## Text from suggested visual region

~~~text
.       97            UCI                  95              Enron
-
         96                                      90
f           (test) 95                                      85
 .   AP 94                                      80                             transductive
                                                                                          inductive
 .       93  4          10        15        20   75  4          10        15        20
 -                        Dims. (d)                                Dims. (d)
   Figure 8: PINT: AP (mean and std) as a function of the
    dimensionality of the positional features.
 ,
~~~

## Body references

- [PDF p.10] Dimensionality of relative positional features. We assess the performance of PINT as a func- tion of the dimension d of the relative positional features. Figure 8 shows the performance of PINT for d 2 {4, 10, 15, 20} on UCI and Enron. We report mean and standard deviation of AP on test set obtained from ﬁve independent runs. In all experiments, we re-use the optimal hyper- parameters found with d = 4. Increasing the dimensionality of the positional features leads to performance gains on both datasets. Notably, we obtain a signiﬁcant boost for Enron with d = 10: 92.69 ± 0.09 AP in the transductive setting and 88.34 ± 0.29 in the inductive case. Thus, PINT becomes the best-performing model on Enron (transductive). On UCI, for d = 20, we obtain 96.36 ± 0.07 and 94.77 ± 0.12 (inductive).

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
