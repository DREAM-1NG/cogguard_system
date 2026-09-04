# Text evidence: Table 2

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 8
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [100.799, 62.08, 269.639, 252.541]

## Caption

Table 2: AP for TCL with NCoE.

## Text from suggested visual region

~~~text
Table 2: AP for TCL with NCoE.

 Datasets  TCL w/ NCoE Improv.
 Wikipedia 96.47   99.09   2.72%
  Reddit   97.53   99.04   1.55%
 MOOC   82.38   86.92   5.51%
 LastFM   67.27   84.02  24.90%
  Enron   79.70   90.18  13.15%
Social Evo. 93.13   94.06   1.00%
  UCI    89.57   94.69   5.72%
  Flights   91.23   97.71   7.10%
 Can. Parl.  68.67   69.34   0.98%
US Legis.  69.59   69.47   -0.17%
UN Trade  62.21   63.46   2.01%  F
 UN Vote  51.90   51.52   -0.73% C
  Contact   92.44   97.98   5.99%
~~~

## Body references

- [PDF p.8] TCL and GraphMixer and show their performance in Table 2 and Table 16 in Section C.4. We find TCL and GraphMixer usually yield better results with NCoE, achieving an average improvement of 5.36% and 1.86% over all datasets. This verifies the effectiveness and versatility of the neighbor co-occurrence encoding, and highlights the importance of capturing correlations between nodes. Also, as TCL and DyGFormer are built upon Transformer, TCL w/ NCoE can achieve similar results with DyGFormer on datasets that enjoy shorter input sequences (in which cases the patching technique in DyGFormer contributes little). However, when datasets exhibit more obvious long-term temporal dependencies (e.g., LastFM, Can. Parl.), the performance gaps become more significant.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
