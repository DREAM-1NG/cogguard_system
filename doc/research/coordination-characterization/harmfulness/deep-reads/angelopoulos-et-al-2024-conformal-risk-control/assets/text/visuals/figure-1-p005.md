# Text evidence: Figure 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 5
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [98.0, 71.858, 514.003, 284.493]

## Caption

Figure 1: FNR control in tumor segmentation. The top figure shows examples of our procedure with correct pixels in white, false positives in blue, and false negatives in red. The bottom plots report FNR and set size over 1000 independent random data splits. The dashed gray line marks α.

## Text from suggested visual region

~~~text
30                                                                100
                  density 20                                                         10 1
          10                                                         10 2

           0
              0.06    0.07    0.08    0.09    0.10    0.11    0.12    0.13           0        5        10       15       20       25
                                                   risk                                                   set size as a fraction of polyp size
Figure 1: FNR control in tumor segmentation. The top figure shows examples of our procedure
with correct pixels in white, false positives in blue, and false negatives in red. The bottom plots
report FNR and set size over 1000 independent random data splits. The dashed gray line marks α.
~~~

## Body references

- [PDF p.5] For evaluating the proposed procedure we pool data from several online open-source gut polyp segmentation datasets: Kvasir, Hyper-Kvasir, CVC-ColonDB, CVC-ClinicDB, and ETIS-Larib. We choose a PraNet (Fan et al., 2020) as our base model f and used n = 1000, and evaluated risk control with the 781 remaining validation data points. We report results with α = 0.1 in Figure 1. The mean and standard deviation of the risk over 1000 trials are 0.0987 and 0.0114, respectively.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
