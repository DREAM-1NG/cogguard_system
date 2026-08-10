# Text evidence: Table 7

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 13
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [307.659, 273.428, 569.805, 536.575]

## Caption

Table 7: Performance comparison between FedInf and base- lines of social influence prediction task across three datasets (OAG-DeepInf, Digg-DeepInf, Higgs Twitter). The best results in AUC, precision, recall and F1 are bolded.

## Text from suggested visual region

~~~text
@10  @50 @100 @10  @50 @100 @10  @50 @100 @10  @50 @100

 DeepDiffuse   5.79  10.80  18.39   9.02  14.93  19.13   4.13  10.58  17.21  10.27  21.83  30.74
 Topo-LSTM   8.45  15.80  25.42   8.57  16.53  21.47   4.56  12.63  16.53  12.28  22.63  31.52
 NDM         15.21  28.23  32.30  10.00  21.13  30.14   4.85  14.24  18.97  15.41  31.36  45.86
 SNIDSA      25.37  36.64  42.89  16.23  27.24  35.59   5.63  15.22  20.93  17.74  34.58  48.76
 FOREST      28.67  42.07  49.75  19.50  32.03  39.08   9.68  17.73  24.08  24.85  42.01  51.28
 Inf-VAE      14.85  32.72  45.72   8.94  22.02  35.72   5.98  14.70  20.91  18.38  38.50  51.05
 DyHGCN     31.88  45.05  52.19  18.71  32.33  39.71   9.10  16.38  23.09  26.62  42.80  52.47
 MS-HGAT    33.50  49.59  58.91  21.33  35.25  42.75  10.41  20.31  27.55  28.80  47.14  55.62
 Topic-HGAT  35.12  51.41  61.15  23.50  37.58  45.66  11.76  21.72  29.39  30.02  48.73  57.80
 RotDiff      35.90  52.46  61.21  22.16  38.23  46.37  11.44  23.04  31.30  32.37  56.25  66.74
 MCDAN     38.45 55.78 64.25 49.39 58.58 62.81 11.89 25.10 32.79 35.49 56.92 67.41

                         Map@K

           Twitter-MSHGAT Douban-ComSoc     Android        Christianity
 Model
           @10  @50 @100 @10  @50 @100 @10  @50 @100 @10  @50 @100

 DeepDiffuse   5.87   6.80   6.39   6.02   6.93   7.13   2.30   2.53   2.56   7.27   7.83   7.84
 Topo-LSTM   8.51  12.68  13.68   6.57   7.53   7.78   3.60   4.05   4.06   7.93   8.67   9.86
 NDM         12.41  13.23  14.30   8.24   8.73   9.14   2.01   2.22   2.93   7.41   7.68   7.86
 SNIDSA      15.34  16.64  16.89  10.02  11.24  11.59   2.98   3.24   3.97   8.69   8.94   9.72
 FOREST      19.60  20.21  21.75  11.26  11.84  11.94   5.83   6.17   6.26  14.64  15.45  15.58
 Inf-VAE      19.80  20.66  21.32  11.02  11.28  12.28   4.82   4.86   5.27   9.25  11.96  12.45
 DyHGCN     20.87  21.48  21.58  10.61  11.26  11.36   6.09   6.40   6.50  15.64  16.30  16.44
 MS-HGAT    22.49  23.17  23.30  11.72  12.52  12.60   6.39   6.87   6.96  17.44  18.27  18.40
 Topic-HGAT  23.71  24.53  24.66  12.70  13.61  13.72   6.80   7.53   7.68  18.98  19.85  19.99
 RotDiff      24.06  24.82  24.95  11.70  12.54  12.66   6.96   7.45   7.56  19.81  20.91  21.05
 MCDAN     25.89 26.69 26.81 40.70 41.13 41.19  7.47  8.04  8.15  22.88 23.78 23.94

Table 7: Performance comparison between FedInf and base-
lines of social influence prediction task across three datasets
(OAG-DeepInf, Digg-DeepInf, Higgs Twitter). The best results
in AUC, precision, recall and F1 are bolded.
~~~

## Body references

- [PDF p.6] It integrates global relationships from social networks and his- torical cascades, capturing user preferences with a multi-scale sequential hypergraph attention module. Next, a contextual atten- tion enhancement module strengthens user interaction within cascades, while susceptibility labels are constructed based on user analysis. Table 6 presents the performance comparison be- tween MCDAN and baseline models on four datasets (Twitter- MSHGAT [62], Douban-ComSoc[63], Android [62], Christian- ity [62]), measured by Hits@K and Map@K for K = 10, 50, 100. • Social influence prediction: FedInf[30] introduces a federated learning framework for social influence prediction, addressing privacy concerns and enabling cross-organizational collabora- tion. It uses differential privacy during model aggregation, pro- jecting parameters into a lower-dimensional space to minimize noise. The whole framework consists of local training and global model updates. Table 7 presents the performance comparison between FedInf and baseline models across three datasets (OAG- DeepInf [29], Digg-DeepInf [29], Higgs Twitter [64]), measured by AUC, precision, recall, and F1.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
