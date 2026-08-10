# Text evidence: Table 9

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 14
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [307.659, 409.538, 568.204, 552.061]

## Caption

Table 9: Performance of the adversarial attack method in graph-based bot detection task on two datasets (Cresci-2015 and TwiBot-22). The best results in attack success rate and new node detected as bot are bolded.

## Text from suggested visual region

~~~text
Table 9: Performance of the adversarial attack method in
graph-based bot detection task on two datasets (Cresci-2015
and TwiBot-22). The best results in attack success rate and
new node detected as bot are bolded.


                       Cresci-2015               TwiBot-22
   Model
               Attack success New node  Attack success  New node
                      rate     become bot      rate     become bot

  GCN           95.68 ± 1.44    0.00 ± 0.00    93.97 ± 5.43     2.66 ± 5.09
  HGT           94.79 ± 1.18    0.06 ± 0.12    89.37 ± 3.56    5.40 ± 10.80
   Simple-HGN   95.74 ± 1.25    0.00 ± 0.00    74.94 ± 2.16    7.39 ± 14.78
   R-GCN        95.74 ± 1.50   0.06 ± 0.12    73.73 ± 1.71   12.94 ± 19.19
~~~

## Body references

- [PDF p.7] Similarly, we present a representative method for each subtask of social bot detection, respectively. They briefly introduce their landmark algorithms and current performance in this task. • User-based and content-based bot detection: [19] introduces a Con- textual LSTM network for detecting social bots using user and content data. The model converts tweet text into GloVe vectors and combines them with user metadata. It employs synthetic minority oversampling and interprets LSTM hidden layers to dif- ferentiate tweets generated from human or bot. Table 8 compares the performance of the Contextual LSTM and baseline models on account-level (user) and tweet-level bot detection tasks using the Cresci-2017 dataset [66], measured by precision, recall, F1-score, accuracy, and AUC. • Graph-based bot detection: [20] presents an adversarial attack method to bypass bot detection systems by placing a new bot near an existing one in the social graph. Utilizing a Relational Graph Convolutional Network (R-GCN), the method generates the new bot’s embedding and connects it to the target bot as second-order neighbors. An attribute recovery module conceals the new bot’s text attributes, achieving high attack success while differentiating the bot from human users. Table 9 shows per- formance results on two datasets (Cresci-2015 [71] and TwiBot- 22 [17]), measured by attack success rate and new nodes detected as bots.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
