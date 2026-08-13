# Text evidence: Table 5

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 9
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [44.0, 44.49, 568.019, 229.495]

## Caption

Table 5: Results of different algorithms in the replier classification task. Top: downsampling of the majority class (normal repliers). Bottom: oversampling of the minority class (IO repliers). We present standard errors rounded to the second decimal point.

## Text from suggested visual region

~~~text
Downsampling          Prec.         Rec.        F1      AUC
                             Logistic Regression   0.89 ± 0.00   0.88 ± 0.00   0.88 ± 0.00   0.93 ± 0.00
                     Random Forest       0.93 ± 0.00   0.92 ± 0.00   0.92 ± 0.00   0.97 ± 0.00
                        AdaBoost            0.90 ± 0.00   0.90 ± 0.00   0.90 ± 0.00   0.96 ± 0.00
                           Decision Tree        0.88 ± 0.00   0.88 ± 0.00   0.88 ± 0.00   0.88 ± 0.00
                         Naive Bayes          0.62 ± 0.02   0.86 ± 0.02   0.68 ± 0.00   0.87 ± 0.00
                        Oversampling        Precision      Recall        F1      AUC
                             Logistic Regression   0.27 ± 0.00   0.48 ± 0.01   0.35 ± 0.00   0.94 ± 0.00
                     Random Forest       0.70 ± 0.00   0.72 ± 0.01   0.71 ± 0.00   0.96 ± 0.00
                        AdaBoost            0.47 ± 0.02   0.54 ± 0.02   0.50 ± 0.01   0.96 ± 0.00
                           Decision Tree        0.55 ± 0.01   0.51 ± 0.01   0.53 ± 0.01   0.75 ± 0.01
                         Naive Bayes          0.06 ± 0.00   0.50 ± 0.03   0.10 ± 0.00   0.86 ± 0.00

Table 5: Results of different algorithms in the replier classification task. Top: downsampling of the majority class (normal
repliers). Bottom: oversampling of the minority class (IO repliers). We present standard errors rounded to the second decimal
point.
~~~

## Body references

- [PDF p.8] balance leads to poor classification, which can be addressed in two ways. First, we downsampled the normal repliers by creating 10 different balanced datasets. Each includes all the IO repliers and an equal number (7,670) of normal repliers, sampled without replacement. We train and test the model on each balanced dataset using 10-fold cross-validation and re- port the average performance score. As a second approach, we over sampled the IO repliers by splitting the data into train and test sets, then replicating the minority class. Repli- cation occurs only in the training data, to avoid data leakage. We run 10-fold cross-validation on the resulting dataset. The first approach might eliminate some potential false positives — normal repliers with similar reply behavior — potentially making the task easier. In the second approach, the model is tested on data that still maintains the class imbalance, po- tentially overfitting the training data. This approach is also more expensive due to the large dataset. Given these comple- mentary disadvantages, below we report on both methods. We standardize the features with z-scores and report the mean performance metrics obtained by different machine learning models: Logistic Regression, Random Forest, Ad- aBoost, Decision Tree, and Naive Bayes. As in the tweet classifier, we tune the threshold to maximize the mean F1 across folds. Table 5 shows that all classifiers perform better with downsampling, and Random Forest (with 100 estimator trees) performs the best with both downsampling and over- sampling. Therefore, let us focus on this m

[TRUNCATED BY EXTRACTOR]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
