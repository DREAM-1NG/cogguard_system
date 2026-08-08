# Text evidence: Figure 2

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 9
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [97.751, 60.755, 514.003, 343.793]

## Caption

Figure 2: Local coverage frequencies for adaptive conformal (blue), a non-adaptive method that holds αt = α ﬁxed (red), and an i.i.d. Bernoulli(0.1) sequence (grey) for the prediction of stock market volatility with conformity score ˜St. The coloured dotted lines mark the average coverage obtained across all time points, while the black line indicates the target level of 1 −α = 0.9.

## Text from suggested visual region

~~~text
Adaptive Alpha    Fixed Alpha    Bernoulli Sequence

       1.0    Nvidia                                     AMD
    Level
      Coverage 0.80.6
    Local
       0.4


       1.0    BlackBerry                                                 Fannie Mae
    Level
      Coverage 0.80.6
    Local 0.4


           2005                     2010                     2015                     2020               2000           2005           2010           2015           2020
                                                Time

Figure 2: Local coverage frequencies for adaptive conformal (blue), a non-adaptive method that holds
αt = α ﬁxed (red), and an i.i.d. Bernoulli(0.1) sequence (grey) for the prediction of stock market
volatility with conformity score ˜St. The coloured dotted lines mark the average coverage obtained
across all time points, while the black line indicates the target level of 1 −α = 0.9.
~~~

## Body references

- [PDF p.9] An a priori reasonable alternative to this is the unnormalized score ˜St := |Vt −ˆσ2 t |. However, after a more careful examination it becomes unsurprising that normalization by ˆσ2 t is critical for obtaining an approximately stationary conformity score and thus ˜St leads to much worse coverage properties. Figure 2 shows the local coverage frequency (see (4)) of adaptive conformal inference using ˜St. In comparison to Figure 1 the coverage now undergoes much wider swings away from the target level of 0.9. This issue can be partially mitigated by choosing a larger value of γ that gives greater adaptivity to the algorithm.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
