# Text evidence: Table 8

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 14
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [307.659, 74.184, 568.205, 279.177]

## Caption

Table 8: Performance comparison between Contextual LSTM and baselines of user-based and content-based bot detection bot detection tasks about the Cresci-2017 dataset. The best results in precision, recall, F1-score, accuracy and AUC are bolded

## Text from suggested visual region

~~~text
Table 8: Performance comparison between Contextual LSTM
and baselines of user-based and content-based bot detection
bot detection tasks about the Cresci-2017 dataset. The best
results in precision, recall, F1-score, accuracy and AUC are
bolded


  Task Model                                         Pre Recall F1 Acc AUC

         Logistic Regression                                       0.94   0.93   0.93 0.91  0.89
      SGD Classifier                                           0.87   0.87   0.87 0.87  0.87
       Random Forest Classifier                                 0.98   0.98   0.98 0.98  0.98
        AdaBoost Classifier                                      0.98   0.98   0.98 0.98  0.98
         2-layer NN (500,200,1) RelU + Adam                      0.95   0.95   0.95 0.95  0.95
         Logistic Regression (With SMOTENN)                   0.99   0.99   0.99 0.99  0.99
      SGD Classifier (With SMOTENN)                        0.95   0.94   0.94 0.95  0.95

        AdaBoost                     Classifier                         (With                        SMOTENN)                                                                    1.00                                                                          1.00                                                                                 1.00                                                                                      1.00                                                                                            1.00          User-based  detectionbot Random Forest Classifier (With SMOTENN)              0.99   0.99   0.99 0.99  0.99         2-layer NN                      (300,200,1)                           RelU                            + Adam (With SMOTENN)                                                                    0.99                                                                          0.99                                                                                 0.99                                                                                      0.99                                                                                            0.98
         Logistic Regression (With SMOTOMEK)                 0.92   0.91   0.91 0.91  0.91
      SGD Classifier (With SMOTOMEK)                      0.90   0.90   0.90 0.90  0.90
       Random Forest Classifier (With SMOTOMEK)            0.99   0.99   0.99 0.99  0.99
        AdaBoost Classifier (With SMOTOMEK)                 0.99   0.99   0.99 0.99  0.99
         2-layer NN (300,200,1) RelU+Adam (With SMOTOMEK)  0.95   0.95   0.95 0.94  0.95

         Logistic Regression (Metadata-only)                      0.80   0.80   0.79 0.80  0.76
~~~

## Body references

- [PDF p.7] Similarly, we present a representative method for each subtask of social bot detection, respectively. They briefly introduce their landmark algorithms and current performance in this task. • User-based and content-based bot detection: [19] introduces a Con- textual LSTM network for detecting social bots using user and content data. The model converts tweet text into GloVe vectors and combines them with user metadata. It employs synthetic minority oversampling and interprets LSTM hidden layers to dif- ferentiate tweets generated from human or bot. Table 8 compares the performance of the Contextual LSTM and baseline models on account-level (user) and tweet-level bot detection tasks using the Cresci-2017 dataset [66], measured by precision, recall, F1-score, accuracy, and AUC. • Graph-based bot detection: [20] presents an adversarial attack method to bypass bot detection systems by placing a new bot near an existing one in the social graph. Utilizing a Relational Graph Convolutional Network (R-GCN), the method generates the new bot’s embedding and connects it to the target bot as second-order neighbors. An attribute recovery module conceals the new bot’s text attributes, achieving high attack success while differentiating the bot from human users. Table 9 shows per- formance results on two datasets (Cresci-2015 [71] and TwiBot- 22 [17]), measured by attack success rate and new nodes detected as bots.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
