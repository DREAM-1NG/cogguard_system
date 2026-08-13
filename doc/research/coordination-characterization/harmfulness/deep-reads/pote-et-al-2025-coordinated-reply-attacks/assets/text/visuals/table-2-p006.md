# Text evidence: Table 2

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 6
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [44.0, 195.807, 568.019, 307.288]

## Caption

Table 2: Results of different algorithms in the tweet classification task. We present standard errors rounded to the second decimal point.

## Text from suggested visual region

~~~text
Classifier               Prec.         Rec.        F1      AUC
                             Logistic Regression   0.65 ± 0.00   0.86 ± 0.00   0.74 ± 0.00   0.80 ± 0.00
                     Random Forest       0.73 ± 0.00   0.87 ± 0.00   0.80 ± 0.00   0.88 ± 0.00
                        AdaBoost            0.64 ± 0.00   0.89 ± 0.00   0.74 ± 0.00   0.81 ± 0.00
                           Decision Tree        0.52 ± 0.01   0.95 ± 0.02   0.66 ± 0.00   0.69 ± 0.00
                         Naive Bayes          0.49 ± 0.00   1.00 ± 0.00   0.66 ± 0.00   0.68 ± 0.00

Table 2: Results of different algorithms in the tweet classification task. We present standard errors rounded to the second decimal
point.
~~~

## Body references

- [PDF p.5] We compare different machine learning models: Logistic Regression, Random Forest, AdaBoost, Decision Tree, and Naive Bayes. Prior to training, we standardize the input fea- tures via z-scores. We conduct 10-fold cross-validation to mitigate over-fitting of the training data and report on the mean precision, recall, and F1 values across folds along with AUC in Table 2. Precision, recall, and F1 depend on a thresh- old to transform the model score into a binary classification label. We tune the threshold to maximize the mean F1 across folds. In the following, we focus on Random Forest (with 100 estimator trees), which yields the best scores overall. To study the contributions of different features, we fol- lowed two approaches. First, we trained and tested Random

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
