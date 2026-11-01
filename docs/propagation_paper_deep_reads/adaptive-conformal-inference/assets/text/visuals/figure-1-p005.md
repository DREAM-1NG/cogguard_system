# Text evidence: Figure 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 5
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [97.751, 60.793, 514.003, 336.62]

## Caption

Figure 1: Local coverage frequencies for adaptive conformal (blue), a non-adaptive method that holds αt = α ﬁxed (red), and an i.i.d. Bernoulli(0.1) sequence (grey) for the prediction of stock market volatility. The coloured dotted lines mark the average coverage obtained across all time points, while the black line indicates the target level of 1 −α = 0.9.

## Text from suggested visual region

~~~text
Adaptive Alpha    Fixed Alpha    Bernoulli Sequence

            Nvidia                                    AMD
        Level 0.95


          0.90
            Coverage
        Local 0.85


            BlackBerry                                                Fannie Mae
        Level 0.95


          0.90
            Coverage
        Local 0.85


              2005                    2010                    2015                    2020               2000           2005           2010           2015           2020
                                                 Time

Figure 1: Local coverage frequencies for adaptive conformal (blue), a non-adaptive method that holds
αt = α ﬁxed (red), and an i.i.d. Bernoulli(0.1) sequence (grey) for the prediction of stock market
volatility. The coloured dotted lines mark the average coverage obtained across all time points, while
the black line indicates the target level of 1 −α = 0.9.
~~~

## Body references

- [PDF p.5] Daily open prices were obtained from publicly available datasets published by The Wall Street Journal. The realized local coverage frequencies for the non-adaptive and adaptive conformal methods on four different stocks are shown in Figure 1. These stocks were selected out of a total of 12 stocks that we examined because they showed a clear failure of the non-adaptive method. Adaptive conformal inference was found to perform well in all cases (see Figure 9 in the appendix).
- [PDF p.9] An a priori reasonable alternative to this is the unnormalized score ˜St := |Vt −ˆσ2 t |. However, after a more careful examination it becomes unsurprising that normalization by ˆσ2 t is critical for obtaining an approximately stationary conformity score and thus ˜St leads to much worse coverage properties. Figure 2 shows the local coverage frequency (see (4)) of adaptive conformal inference using ˜St. In comparison to Figure 1 the coverage now undergoes much wider swings away from the target level of 0.9. This issue can be partially mitigated by choosing a larger value of γ that gives greater adaptivity to the algorithm.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
