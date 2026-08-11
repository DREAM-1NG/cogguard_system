# Text evidence: Figure 3

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 8
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [303.795, 41.024, 570.981, 247.055]

## Caption

Figure 3: Mean (Blue) and error range (blue shade 95% conﬁdence) for the classiﬁer accuracy on target classes according to the number of samples seen from the target class

## Text from suggested visual region

~~~text
100


       80

   (%) 60
         Accuracy 40


       20


        0
          0      2      4      8     16     32     64    128    256
                               Samples
Figure 3: Mean (Blue) and error range (blue shade 95% conﬁdence)
for the classiﬁer accuracy on target classes according to the number
of samples seen from the target class
~~~

## Body references

- [PDF p.8] choose X Bursty bots from the test data, and move them to the training data. And so on. The test ﬁnishes at the 9th step when both the test data and the training data contain about 250 Bursty bots. The step sizes are ﬁxed at 0, 2, 4, 8, 16, 32, 64, 128, and 256 (basically it is a 2x scale but we traded the ﬁrst step for zero bots which matches LOBO test II).Note that, this being a single C500 dataset, the difference in accuracy between the 0 bot case and LOBO test II is expected. We also use the full 500 instances of each of the classes except the target, instead of limiting to 70%. We repeat the above process 50 iterations, and then calculate the average prediction accuracy at each step for the target class. Repetition is needed because each of the times different bots from the target class are being sent into the training set, and it affects the overall accuracy differently. Finally, we run the learning rate test for each bot class in Table 6 as a target class. Detailed results are shown in Table 7. Figure 3 shows the average accuracy after X samples for all bot classes that have been tested, with the shaded area repre- senting the 95% conﬁdence interval. The overall trend would suggest that the classiﬁer has learned to identify most target classes of bots after a few examples. In contrast, Figure 4 shows that the performance for different classes varies signiﬁ- cantly. It contains the same shaded area as Figure 3 to show the stark differences between the average and the widely varying

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
