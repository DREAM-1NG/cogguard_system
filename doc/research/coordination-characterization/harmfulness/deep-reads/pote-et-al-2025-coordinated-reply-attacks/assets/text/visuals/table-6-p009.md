# Text evidence: Table 6

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 9
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [44.0, 230.792, 302.514, 393.48]

## Caption

Table 6: Contributions of different profile features and reply- level feature sets to the Random Forest replier classifier. The last row corresponds to the results in Table 5 (top).

## Text from suggested visual region

~~~text
Features set          Prec.   Rec.   F1  AUC
    activity rate     0.60    0.63   0.61   0.65
    following rate    0.54    0.52   0.53   0.56
    follower rate     0.55    0.51   0.53   0.56
    age                  0.58    0.66   0.61   0.66
     Delay                 0.57    0.60   0.58   0.62
     Engagement           0.57    0.57   0.53   0.63
       Entities               0.63    0.50   0.53   0.63
       Similarity             0.85    0.84   0.84   0.92
      All features           0.93    0.92   0.92   0.97

Table 6: Contributions of different profile features and reply-
level feature sets to the Random Forest replier classifier. The
last row corresponds to the results in Table 5 (top).
~~~

## Body references

- [PDF p.8] balance leads to poor classification, which can be addressed in two ways. First, we downsampled the normal repliers by creating 10 different balanced datasets. Each includes all the IO repliers and an equal number (7,670) of normal repliers, sampled without replacement. We train and test the model on each balanced dataset using 10-fold cross-validation and re- port the average performance score. As a second approach, we over sampled the IO repliers by splitting the data into train and test sets, then replicating the minority class. Repli- cation occurs only in the training data, to avoid data leakage. We run 10-fold cross-validation on the resulting dataset. The first approach might eliminate some potential false positives — normal repliers with similar reply behavior — potentially making the task easier. In the second approach, the model is tested on data that still maintains the class imbalance, po- tentially overfitting the training data. This approach is also more expensive due to the large dataset. Given these comple- mentary disadvantages, below we report on both methods. We standardize the features with z-scores and report the mean performance metrics obtained by different machine learning models: Logistic Regression, Random Forest, Ad- aBoost, Decision Tree, and Naive Bayes. As in the tweet classifier, we tune the threshold to maximize the mean F1 across folds. Table 5 shows that all classifiers perform better with downsampling, and Random Forest (with 100 estimator trees) performs the best with both downsampling and over- sampling. Therefore, let us focus on this m

[TRUNCATED BY EXTRACTOR]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
