# Text evidence: Figure 9

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 8
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [309.5, 43.996, 568.015, 297.829]

## Caption

Figure 9: Permutation feature importance for replier clas- sifier. We report the median (orange line), 50% confidence interval (box), and 99.3% confidence interval (whiskers) of the drop in F1 score when each feature/attribute is shuffled. Boxes with the same color indicate attributes in the same feature set. Larger values indicate higher importance.

## Text from suggested visual region

~~~text
Figure 9: Permutation feature importance for replier clas-
sifier. We report the median (orange line), 50% confidence
interval (box), and 99.3% confidence interval (whiskers) of
the drop in F1 score when each feature/attribute is shuffled.
Boxes with the same color indicate attributes in the same
feature set. Larger values indicate higher importance.
~~~

## Body references

- [PDF p.8] balance leads to poor classification, which can be addressed in two ways. First, we downsampled the normal repliers by creating 10 different balanced datasets. Each includes all the IO repliers and an equal number (7,670) of normal repliers, sampled without replacement. We train and test the model on each balanced dataset using 10-fold cross-validation and re- port the average performance score. As a second approach, we over sampled the IO repliers by splitting the data into train and test sets, then replicating the minority class. Repli- cation occurs only in the training data, to avoid data leakage. We run 10-fold cross-validation on the resulting dataset. The first approach might eliminate some potential false positives — normal repliers with similar reply behavior — potentially making the task easier. In the second approach, the model is tested on data that still maintains the class imbalance, po- tentially overfitting the training data. This approach is also more expensive due to the large dataset. Given these comple- mentary disadvantages, below we report on both methods. We standardize the features with z-scores and report the mean performance metrics obtained by different machine learning models: Logistic Regression, Random Forest, Ad- aBoost, Decision Tree, and Naive Bayes. As in the tweet classifier, we tune the threshold to maximize the mean F1 across folds. Table 5 shows that all classifiers perform better with downsampling, and Random Forest (with 100 estimator trees) performs the best with both downsampling and over- sampling. Therefore, let us focus on this m

[TRUNCATED BY EXTRACTOR]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
