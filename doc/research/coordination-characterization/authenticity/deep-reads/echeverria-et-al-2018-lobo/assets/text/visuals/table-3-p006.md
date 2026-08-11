# Text evidence: Table 3

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 6
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [317.58, 116.484, 557.194, 225.721]

## Caption

Table 3: Classiﬁer performance on C30K and C500 datasets.

## Text from suggested visual region

~~~text
AdaBoost       94.29%    0.94   88.88%    0.89

   Table 3: Classiﬁer performance on C30K and C500 datasets.


                     True       False       False      True
                      Negatives   Positives   Negatives   Positives
   LGBM            31161       344       1010     30152
   XGBC             30767       738       1824     29338
    Random Forest      31073       432       1438     29724
     DecissionTree       30241      1264       1250     29912
     AdaBoost          30002      1503       2078     29084

Table 4:  Confusion Matrices for different classiﬁers trained on
~~~

## Body references

- [PDF p.6] 6.2 General Classiﬁers We utilize our user dataset against the bot training data. All the features presented in previous Section have been calcu- lated for every user, making each user representation a 30- dimension vector. We use some of the most common classi- ﬁers (mostly based on trees). The classiﬁers to test are Gra- dient Boosted Trees (using Xgboost and LightGBM), Random Forests, Decision Trees, and AdaBoost. All these algorithms are deliberately trained using their most standard and naive python implementation. Naturally, the per- formance evaluation is done purely on the test data which was not “seen” during training. Performance Evaluation - C30K Table 3 shows the results of a binary classiﬁcation attempt using the dataset C30K. All of the algorithms show clear signs of an easy separation task, with accuracies over 95% in most cases. This level of accuracy in bot classiﬁcation is not unheard of: it has been claimed before several times (e.g., [11, 34, 25]). To further reiterate that this is not a ﬂuke, we also check the area under the ROC curve and the confusion matrix for some of the results generated (Table 4). As can be seen, almost all bots are classiﬁed as bots, and almost all users are classiﬁed as users, for all the algorithms tested (remember that the testing set was 30% of the C30K dataset, i.e., ∼63k instances total). This result was repeated several times just for consistency, all with random 70-30 training-test splits and showed little vari- ation. One could argue that our LGBM classiﬁer is compara- ble to the state of the art in bot detection, having

[TRUNCATED BY EXTRACTOR]
- [PDF p.7] couraging, show clear deterioration in accuracy. In Table 3, we see more than 5% loss in accuracy for the best performing algorithm, and a steeper 8% loss for decision trees.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
