# Text evidence: Table 6

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 8
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [59.658, 41.914, 291.269, 232.941]

## Caption

Table 6: Lobo test on dataset C500

## Text from suggested visual region

~~~text
Target    1 - Class    Full Model  LOBO Model  Accuracy
 Class   Model Acc.   Accuracy     Accuracy      Gain
 A        99.80%      93.90%        62.01%    31.89%
  B        99.74%      93.92%        98.14%     -4.22%
 C        96.42%      94.22%        84.81%     9.41%
 D        92.37%      94.17%        86.65%     7.52%
  E        97.42%      94.11%        49.19%    44.92%
  F        99.47%      94.02%         0.71%    93.31%
 H        94.56%      94.92%         2.19%    92.73%
 K        99.70%      94.05%         1.97%    92.08%
 M        98.43%      94.25%        66.02%    28.23%
  T        92.79%      94.25%        88.79%     5.46%
 U        91.14%      95.16%        39.44%    55.73%
 V        92.22%      94.57%        77.86%    16.71%
 W        94.53%      94.21%        89.82%     4.39%
 Avg.      96.05%     94.29%       57.51%    36.78%

           Table 6: Lobo test on dataset C500
~~~

## Body references

- [PDF p.7] All of these steps are performed 100 times for each of the bot classes. What results is the ability to evaluate how a model trained on balanced bot classes can be expected to perform against a target bot class which is previously unseen by this model. Furthermore, it allows performance comparison for when this model has seen just 500 of the target class against not seeing any, with some surprising results. Table 6 shows
- [PDF p.8] choose X Bursty bots from the test data, and move them to the training data. And so on. The test ﬁnishes at the 9th step when both the test data and the training data contain about 250 Bursty bots. The step sizes are ﬁxed at 0, 2, 4, 8, 16, 32, 64, 128, and 256 (basically it is a 2x scale but we traded the ﬁrst step for zero bots which matches LOBO test II).Note that, this being a single C500 dataset, the difference in accuracy between the 0 bot case and LOBO test II is expected. We also use the full 500 instances of each of the classes except the target, instead of limiting to 70%. We repeat the above process 50 iterations, and then calculate the average prediction accuracy at each step for the target class. Repetition is needed because each of the times different bots from the target class are being sent into the training set, and it affects the overall accuracy differently. Finally, we run the learning rate test for each bot class in Table 6 as a target class. Detailed results are shown in Table 7. Figure 3 shows the average accuracy after X samples for all bot classes that have been tested, with the shaded area repre- senting the 95% conﬁdence interval. The overall trend would suggest that the classiﬁer has learned to identify most target classes of bots after a few examples. In contrast, Figure 4 shows that the performance for different classes varies signiﬁ- cantly. It contains the same shaded area as Figure 3 to show the stark differences between the average and the widely varying

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
