# Text evidence: Table 7

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 9
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [41.024, 274.895, 308.206, 467.953]

## Caption

Table 7: Classiﬁer accuracy (%) - trained C500 excluding all but X samples of target class.

## Text from suggested visual region

~~~text
Tgt.     Number (X) of samples of target class in training data
  Class    0     2     4     8    16    32    64   128   256
  A     59.4   71.7   89.4   96.4   98.8   99.9   100   100   100
  B     97.4   97.4   97.7   97.4   98.1   98.6   99.0   99.6   99.8
  C     86.7   86.5   86.9   87.3   87.5   88.0   88.6   90.9   92.9
  D     86.7   86.8   86.7   86.8   87.0   87.6   87.8   89.0   90.6
  E     64.9   68.6   72.2   79.8   84.9   89.4   92.8   94.7   95.9
   F      0.8    1.7   21.3   72.0   86.8   94.9   96.9   97.6   98.3
  H      1.7    2.3    4.3   10.5   25.7   49.4   66.9   76.3   81.6
  K      4.0   17.8   51.9   85.3   95.2   96.6   98.5   99.2   99.5
  M    64.2   64.8   66.3   67.3   70.1   74.2   80.8   87.5   95.3
  T     89.9   89.9   89.6   89.6   89.5   89.7   90.1   90.2   91.0
  U     33.7   34.0   34.6   36.9   38.5   43.2   50.0   59.1   69.6
  V     80.0   79.7   79.7   79.9   80.0   80.7   81.0   82.2   84.3
 W    90.9   91.0   90.9   91.1   91.2   91.5   91.7   92.2   93.0

Table 7: Classiﬁer accuracy (%) - trained C500 excluding all but X
samples of target class.
~~~

## Body references

- [PDF p.8] choose X Bursty bots from the test data, and move them to the training data. And so on. The test ﬁnishes at the 9th step when both the test data and the training data contain about 250 Bursty bots. The step sizes are ﬁxed at 0, 2, 4, 8, 16, 32, 64, 128, and 256 (basically it is a 2x scale but we traded the ﬁrst step for zero bots which matches LOBO test II).Note that, this being a single C500 dataset, the difference in accuracy between the 0 bot case and LOBO test II is expected. We also use the full 500 instances of each of the classes except the target, instead of limiting to 70%. We repeat the above process 50 iterations, and then calculate the average prediction accuracy at each step for the target class. Repetition is needed because each of the times different bots from the target class are being sent into the training set, and it affects the overall accuracy differently. Finally, we run the learning rate test for each bot class in Table 6 as a target class. Detailed results are shown in Table 7. Figure 3 shows the average accuracy after X samples for all bot classes that have been tested, with the shaded area repre- senting the 95% conﬁdence interval. The overall trend would suggest that the classiﬁer has learned to identify most target classes of bots after a few examples. In contrast, Figure 4 shows that the performance for different classes varies signiﬁ- cantly. It contains the same shaded area as Figure 3 to show the stark differences between the average and the widely varying

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
