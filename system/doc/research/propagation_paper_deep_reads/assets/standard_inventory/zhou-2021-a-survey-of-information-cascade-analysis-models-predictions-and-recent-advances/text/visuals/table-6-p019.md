# Text evidence: Table 6

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 19
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [35.683, 72.007, 450.236, 416.72]

## Caption

Table 6. Machine Learning Methods

## Text from suggested visual region

~~~text
Table 6. Machine Learning Methods

Method                         Abbr.                      Reference
Autoregressive (âmoving-average)  AR (MA)   [48, 73, 74, 123, 137, 223, 237]
Decision Tree              DT         [12, 39, 49, 50, 60, 61, 63, 73, 84, 97, 100, 101, 103, 105, 106,
                                             134–136, 138, 194, 200, 218, 230]
k-nearest Neighbors Algorithm    k-NN      [12, 48, 61, 63, 73, 84, 97, 98, 123, 134, 135, 218]
Linear Regression              LR          [1, 3, 12, 14, 24, 31, 39, 48, 50, 63, 72, 73, 77, 90, 98, 100, 101,
                                                 123, 132, 136, 156, 160, 168, 181, 184, 186, 192, 208, 212, 218,
                                                 229, 233, 234, 238, 246]
Logistic Regression Classifier     LRC        [39, 46, 49, 50, 61, 81, 85, 86, 97, 103, 135, 138, 149, 151, 158,
                                                 165, 175, 200, 215, 227, 241]
Multilayer Perceptron         MLP       [49, 63, 100, 101, 200]
naïve Bayes classifier             Bayes      [39, 49, 50, 61, 63, 73, 85, 134, 135, 172, 173, 229, 230]
Random Forests                RF          [4, 23, 39, 49, 50, 63, 71, 72, 86, 97, 103, 136, 142, 161, 175,
                                                 187, 189, 191, 200, 207, 208, 215, 230, 241]
Support Vector Machine        SVM       [12, 36, 39, 49, 50, 61, 64, 72, 73, 84, 86, 91, 96, 97, 100, 101,
                                                 103, 108, 128, 131, 132, 134, 135, 138, 158, 166, 175, 188, 192,
                                                 200, 218, 225, 227, 232, 241]


addition of content features, which is also confirmed in Reference [106]. Authors of Reference [136]
argued that content features explain the variance of popularity poorly. Content-based methods
suffer from issues that hinder their performance—e.g., despite the recent success of deep learning,
natural language processing and computer vision, it is still challenging to effectively and efficiently
identify, retrieve, and model the content of items, and the results are far from satisfactory. In ad-
dition, previous works found that even for items with identical content, their popularity varies
greatly [24, 39, 65, 109], raising questions about whether, if one relies only on content features, the
popularity of items/cascades is inherently unpredictable or cannot be predicted a priori.
~~~

## Body references

- [PDF p.19] Since the main challenge of feature-based models lies in the feature engineering, improving the capability of prediction models is not the focus in related literature. For example, Reference [39] demonstrated that most of the machine learning methods have similar performance, despite time/space complexity. For completeness, we summarize common machine learning methods, or what are adopted as their main building blocks, as the prediction methods in Table 6. In addition to the methods listed in Table 6, a few learning paradigms such as inductive/transductive learn- ing, early feature fusion, and multi-view learning approaches have been investigated to predict the popularity of information items/cascades [36, 78, 132, 210]. We suggest researchers to experi- ment different prediction methods on their specific datasets, and techniques such as automatically selecting machine learning models and hyper-parameters [102], would greatly boost the training and optimizing processes.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
