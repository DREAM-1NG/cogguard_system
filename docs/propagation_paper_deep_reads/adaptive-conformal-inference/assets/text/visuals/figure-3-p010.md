# Text evidence: Figure 3

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 10
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [98.0, 63.401, 515.747, 330.855]

## Caption

Figure 3: Local coverage frequencies of adaptive conformal (blue), a non-adaptive method that holds αt = α ﬁxed (red), and an i.i.d. Bernoulli(0.1) sequence (grey) for county-level election predictions. Coloured dotted lines show the average coverage across all time points, while the black line indicates the target coverage level of 1 −α = 0.9.

## Text from suggested visual region

~~~text
Adaptive Alpha  Fixed Alpha   Bernoulli Sequence

     Level 0.900


          0.875
       Coverage

          0.850
     Local


          0.825

                               500                      1000                      1500                      2000
                                   Time

Figure 3: Local coverage frequencies of adaptive conformal (blue), a non-adaptive method that holds
αt = α ﬁxed (red), and an i.i.d. Bernoulli(0.1) sequence (grey) for county-level election predictions.
Coloured dotted lines show the average coverage across all time points, while the black line indicates
the target coverage level of 1 −α = 0.9.
~~~

## Body references

- [PDF p.10] We apply CQR to predict the county-level vote totals (see Section A.6.2 for details). To replicate the east to west coast bias observed on election night we order the counties by their time zone with eastern time counties appearing ﬁrst and Hawaiian counties appearing last. Within each time zone counties are ordered uniformly at random. Figure 3 shows the realized local coverage frequency over the most recent 300 counties (see (4)) for the non-adaptive and adaptive conformal methods. We ﬁnd that the non-adaptive method fails to maintain the desired 90% coverage level, incurring large troughs in its coverage frequency during time zone changes. On the other hand, the adaptive method maintains approximate 90% coverage across all time points with deviations in its local coverage level comparable to what is observed in Bernoulli sequences.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
