# Text evidence: Table 2

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 8
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text
- **Suggested region:** [97.691, 17.813, 514.001, 342.669]

## Caption

Table 2: Performance in AUC (mean in percentage ± 95% conﬁdence level.) † highlights the best baselines. ∗, bold font, bold font∗respectively highlights the case where our models’ performance exceeds the best baseline on average, by 70% conﬁdence, by 95% conﬁdence.

## Text from suggested visual region

~~~text
Published as a conference paper at ICLR 2021


  Task   Methods            Reddit        Wikipedia     MOOC        Social Evo.       Enron        UCI
       DynAERNN     57.51 ± 2.54    55.16 ± 1.15    60.85 ± 1.61    52.00 ± 0.16    51.57 ± 2.63    50.20 ± 2.78
        JODIE          72.49 ± 0.38    70.78 ± 0.75    80.04 ± 0.28†   87.66 ± 0.12†   73.99 ± 2.54†   64.77 ± 0.75
       new  DyRep          62.37 ± 1.49    67.07 ± 1.26    74.07 ± 1.88    83.92 ± 0.02    69.74 ± 0.44    63.76 ± 4.67
      VGRNN        61.93 ± 0.72    60.64 ± 0.68    63.01 ± 0.29    54.49 ± 1.21    72.01 ± 0.08    61.35 ± 1.10
          v.s.        EvolveGCN     63.31 ± 0.53    58.01 ± 0.16    52.31 ± 4.14    46.95 ± 0.85    42.53 ± 2.12    76.65 ± 0.63†
       new  TGAT          94.96 ± 0.88†   93.53 ± 0.84†   70.10 ± 0.35    53.27 ± 1.16    63.34 ± 2.95    76.36 ± 1.48
       CAW-N-mean   97.67 ± 0.08∗   99.27 ± 0.08∗   90.52 ± 0.54∗   95.55 ± 0.40∗   96.43 ± 0.39∗   93.14 ± 0.32∗
        CAW-N-attn    97.71 ± 0.08∗   99.29 ± 0.10∗   90.86 ± 0.56∗   95.20 ± 0.68∗   96.98 ± 0.41∗   93.16 ± 0.25∗
       DynAERNN     58.79 ± 3.01    57.97 ± 2.38    80.99 ± 1.35    52.31 ± 0.59    54.36 ± 1.48    52.26 ± 1.36     Inductive        JODIE          76.33 ± 0.03    74.65 ± 0.06    87.40 ± 1.71    91.80 ± 0.01†   85.24 ± 0.08    69.95 ± 0.11
       old  DyRep          66.13 ± 1.07    76.72 ± 0.19    88.23 ± 1.20†   87.98 ± 0.45    94.39 ± 0.32†   93.28 ± 0.96†
          v.s. VGRNN        54.11 ± 0.74    62.93 ± 0.69    60.10 ± 0.88    64.66 ± 0.41    76.33 ± 0.05    62.39 ± 1.08
        EvolveGCN     65.61 ± 0.37    56.29 ± 2.17    50.20 ± 1.92    50.73 ± 1.36    42.53 ± 2.13    70.78 ± 0.22
       new  TGAT          97.25 ± 0.18†   95.47 ± 0.17†   69.30 ± 0.08    54.22 ± 1.28    58.76 ± 1.18    74.19 ± 0.88
       CAW-N-mean   97.70 ± 0.17∗   98.77 ± 0.13∗   91.08 ± 0.20∗   91.52 ± 0.21    93.98 ± 0.44    91.15 ± 0.24
        CAW-N-attn    97.56 ± 0.14∗   98.21 ± 0.17∗   90.40 ± 0.13∗   91.55 ± 0.30    93.99 ± 0.62    91.17 ± 0.26
       DynAERNN     83.37 ± 1.48    71.00 ± 1.10    89.34 ± 0.24    67.78 ± 0.80    63.11 ± 1.13    83.72 ± 1.79
        JODIE          87.71 ± 0.02    88.43 ± 0.02    90.50 ± 0.01†   89.78 ± 0.04    89.36 ± 0.06    74.63 ± 0.11
        DyRep          67.36 ± 1.23    77.40 ± 0.13    90.49 ± 0.03    90.85 ± 0.01†   96.71 ± 0.04†   95.23 ± 0.25†
      VGRNN        51.89 ± 0.92    71.20 ± 0.65    90.03 ± 0.32    72.84 ± 0.73    79.08 ± 0.02    89.43 ± 0.27
        EvolveGCN     58.42 ± 0.52    60.48 ± 0.47    50.36 ± 0.85    60.36 ± 0.65    74.02 ± 0.31    78.30 ± 0.22                  Transductive   TGAT          96.65 ± 0.06†   96.36 ± 0.05†   72.09 ± 0.29    56.63 ± 0.55    60.88 ± 0.37    77.67 ± 0.27
       CAW-N-mean   98.07 ± 0.06∗   98.83 ± 0.11∗   94.28 ± 0.13∗   93.88 ± 0.72∗   91.64 ± 0.15    95.25 ± 0.30∗
        CAW-N-attn    98.05 ± 0.09∗   98.96 ± 0.10∗   94.33 ± 0.08∗   92.54 ± 0.58∗   92.06 ± 0.16    95.14 ± 0.25

Table 2: Performance in AUC (mean in percentage ± 95% conﬁdence level.) † highlights the best
baselines. ∗, bold font, bold font∗respectively highlights the case where our models’ performance
exceeds the best baseline on average, by 70% conﬁdence, by 95% conﬁdence.
~~~

## Body references

- [No body reference recovered]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
