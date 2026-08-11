# Text evidence: Table 4

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 6
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [303.795, 212.799, 570.98, 753.383]

## Caption

Table 4: Confusion Matrices for different classiﬁers trained on dataset C30K.

## Text from suggested visual region

~~~text
AdaBoost          30002      1503       2078     29084

Table 4:  Confusion Matrices for different classiﬁers trained on
dataset C30K.


ﬂow from the bot class identiﬁcation to our C30K and C500
datasets.

6.2  General Classiﬁers
  We utilize our user dataset against the bot training data. All
the features presented in previous Section have been calcu-
lated for every user, making each user representation a 30-
dimension vector. We use some of the most common classi-
ﬁers (mostly based on trees). The classiﬁers to test are Gra-
dient Boosted Trees (using Xgboost and LightGBM), Random
Forests, Decision Trees, and AdaBoost.
  All these algorithms are deliberately trained using their most
standard and naive python implementation. Naturally, the per-
formance evaluation is done purely on the test data which was
not “seen” during training.
Performance Evaluation - C30K Table 3 shows the results of
a binary classiﬁcation attempt using the dataset C30K. All of
the algorithms show clear signs of an easy separation task, with
accuracies over 95% in most cases. This level of accuracy in
bot classiﬁcation is not unheard of: it has been claimed before
several times (e.g., [11, 34, 25]).
  To further reiterate that this is not a ﬂuke, we also check the
area under the ROC curve and the confusion matrix for some
of the results generated (Table 4). As can be seen, almost all
bots are classiﬁed as bots, and almost all users are classiﬁed as
users, for all the algorithms tested (remember that the testing
set was 30% of the C30K dataset, i.e., ∼63k instances total).
This result was repeated several times just for consistency, all
with random 70-30 training-test splits and showed little vari-
ation. One could argue that our LGBM classiﬁer is compara-
ble to the state of the art in bot detection, having been trained
with over 200,000 data points spanning a wide variety of bot
classes, achieving accuracy of over 97%.
Performance Evaluation - C500 We need to know the per-
formance on a dataset where the bots have the same numbers,
since we cannot always count on having the beneﬁt of large
bot data corpuses like DeBot, Star Wars bots or Bursty bots.
  We evaluate performance on dataset C500 with the same
strategy, using the same standard and naive versions of several
popular classiﬁcation algorithms. The results, while still en-
~~~

## Body references

- [PDF p.6] 6.2 General Classiﬁers We utilize our user dataset against the bot training data. All the features presented in previous Section have been calcu- lated for every user, making each user representation a 30- dimension vector. We use some of the most common classi- ﬁers (mostly based on trees). The classiﬁers to test are Gra- dient Boosted Trees (using Xgboost and LightGBM), Random Forests, Decision Trees, and AdaBoost. All these algorithms are deliberately trained using their most standard and naive python implementation. Naturally, the per- formance evaluation is done purely on the test data which was not “seen” during training. Performance Evaluation - C30K Table 3 shows the results of a binary classiﬁcation attempt using the dataset C30K. All of the algorithms show clear signs of an easy separation task, with accuracies over 95% in most cases. This level of accuracy in bot classiﬁcation is not unheard of: it has been claimed before several times (e.g., [11, 34, 25]). To further reiterate that this is not a ﬂuke, we also check the area under the ROC curve and the confusion matrix for some of the results generated (Table 4). As can be seen, almost all bots are classiﬁed as bots, and almost all users are classiﬁed as users, for all the algorithms tested (remember that the testing set was 30% of the C30K dataset, i.e., ∼63k instances total). This result was repeated several times just for consistency, all with random 70-30 training-test splits and showed little vari- ation. One could argue that our LGBM classiﬁer is compara- ble to the state of the art in bot detection, having

[TRUNCATED BY EXTRACTOR]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
