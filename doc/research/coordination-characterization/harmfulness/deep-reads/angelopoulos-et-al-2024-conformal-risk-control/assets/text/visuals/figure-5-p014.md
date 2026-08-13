# Text evidence: Figure 5

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 14
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [114.692, 87.068, 497.31, 238.623]

## Caption

Figure 5: Comparison of RCPS/LTT with conformal risk control on the polyp dataset.

## Text from suggested visual region

~~~text
35
                                                                                                      Integrate Tail Bound (Hoeffding)
   0.10                                                                         30        Conformal Risk Control
                                                                               RCPS ( = 0.5)
   0.08                                                                   25

   0.06                                                                   20
FNR                                                                                                     time
                                                                         15
   0.04
                                                                         10
   0.02                                  Integrate Tail Bound (Hoeffding)               5                                     Conformal Risk Control
   0.00                          RCPS ( = 0.5)                             0
             50      100      150      200      250      300                       50      100      150      200      250      300
                                 n                                                                    n

  Figure 5: Comparison of RCPS/LTT with conformal risk control on the polyp dataset.
~~~

## Body references

- [PDF p.13] To underscore these points, we perform a careful evaluation against these procedures on the polyp segmentation dataset in Figure 5. We compare against two versions of LTT/RCPS: Baseline 1 has δ = 0.5, Baseline 2 integrates the tail bound of LTT/RCPS to achieve a bound in expectation. The former strategy is not statistically valid for the goal of expectation control, and the latter strategy is essentially only possible using fixed-width bounds such as Hoeffding’s inequality, and is described in the below Appendix B.1. We use the same risk level α = 0.1 for all procedures and make plots with n = {25, 50, 100, 200, 300}.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
