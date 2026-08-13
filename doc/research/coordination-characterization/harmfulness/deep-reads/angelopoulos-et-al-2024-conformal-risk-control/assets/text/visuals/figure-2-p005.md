# Text evidence: Figure 2

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 5
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [98.0, 275.493, 514.003, 481.862]

## Caption

Figure 2: FNR control on MS COCO. The top figure shows examples of our procedure with correct classes in black, false positives in blue, and false negatives in red. The bottom plots report FNR and set size over 1000 independent random data splits. The dashed gray line marks α.

## Text from suggested visual region

~~~text
fork                       person                       suitcase                   person                    person
        cake                         tennis racket                 chair                              traffic light                       tie
         dining table                                                                       umbrella
                                                                                handbag


          80                                                                 0.30
                                                                               0.25
          60
                                                                               0.20
          40                                                                 0.15                  density
                                                                               0.10
          20
                                                                               0.05
           0                                                                 0.00
                         0.09            0.10            0.11            0.12            0       2       4       6       8      10      12
                                                   risk                                                                     size
Figure 2: FNR control on MS COCO. The top figure shows examples of our procedure with correct
classes in black, false positives in blue, and false negatives in red. The bottom plots report FNR and
set size over 1000 independent random data splits. The dashed gray line marks α.
~~~

## Body references

- [PDF p.6] In the multilabel classification setting, our input Xi is an image and our label is a set of classes Yi ⊂{1, . . . , K} for some number of classes K. Using a multiclass classification model f : X → [0, 1]K, we form prediction sets and calculate the number of false positives exactly as in (7). By Theorem 1, picking ˆλ as in (4) again yields the FNR-control guarantee in (8). We evaluate on the Microsoft Common Objects in Context (MS COCO) dataset (Lin et al., 2014), a large-scale 80-class multiclass classification task commonly used in computer vision. We choose a TResNet (Ridnik et al., 2020) as our model f and used n = 4000, and evaluated risk control with 1000 validation data points. We report results with α = 0.1 in Figure 2. The mean and standard deviation of the risk over 1000 trials are 0.0996 and 0.0052, respectively. The results indicate that the risk is almost exactly controlled, the spread is not too wide, and the set sizes are reasonable, not overly inflated.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
