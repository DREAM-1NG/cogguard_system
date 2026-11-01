# Text evidence: Table 2

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 6
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [44.0, 45.49, 568.019, 230.499]

## Caption

Table 2: Performance comparison between baselines and CasFT on three datasets across different observation times measured by MSLE, MAPE (lower is better).

## Text from suggested visual region

~~~text
Twitter                      APS                          Weibo
  Method          1 day            2 days           3 years           5 years            0.5 hours          1 hour
           MSLE  MAPE  MSLE  MAPE  MSLE  MAPE  MSLE  MAPE  MSLE  MAPE  MSLE  MAPE
Feature-based   7.8268   0.7073   6.5154   0.6514   1.9881   0.3085   1.9696   0.3193   4.0788   0.4094   3.6380   0.4268
 SEISMIC     10.687   0.9689   8.1851   0.8147   2.0583   0.3013   2.3013   0.4320   5.0300   0.4819   4.0594   0.5003
  DeepCas     6.3297   0.6566   5.7146   0.6671   2.1051   0.2869   1.9260   0.3458   4.6460   0.3258   3.5532   0.3532
DeepHawkes   5.9341   0.5017   4.8489   0.5189   1.9142   0.2823   1.8145   0.3368   2.8741   0.3041   2.7434   0.3346
  CasCN      5.8742   0.4894   4.7154   0.4974   1.8930   0.2763   1.7494   0.3208   2.7931   0.2940   2.6831   0.3255
   VaCas      5.5124   0.4796   4.2147   0.4871   1.7764   0.2697   1.6945   0.3012   2.5246   0.2847   2.3451   0.2997
  CasFlow     4.7799   0.4150   3.6888   0.4222   1.4370   0.2401   1.3346   0.2624   2.3370   0.2665   2.2232   0.2949
  CTCP      5.3991   0.3757   3.6016   0.3773   1.7676   0.3054   1.3751   0.2908   2.5572   0.3056   2.2968   0.3010
  CasFT      3.8546   0.3674   3.4496   0.3605   1.2468   0.2282   1.1748   0.2561   2.1728   0.2448   2.0655   0.2695
  (Improve)    19.36%↑2.21%↑  4.22%↑  4.45%↑  13.24%↑4.96%↑  11.97%↑2.40%↑  7.02%↑  8.14%↑  10.07%↑8.61%↑

Table 2: Performance comparison between baselines and CasFT on three datasets across different observation times measured
by MSLE, MAPE (lower is better).

                                  Twitter                     APS                         Weibo
~~~

## Body references

- [PDF p.6] Performance Comparison (RQ1) Table 2 shows the overall performance of the three datasets. We observe that our method CasFT significantly outper- forms all baselines on MSLE and MAPE. For example, com- pared to the best-performing baselines, our CasFT achieves a 4.2%-19.3% improvement of MSLE, and a 2.2%-8.6% im- provement of MAPE, on the three datasets with two different observation times. We see that CasFT demonstrates notable enhancement, especially on the Twitter dataset. This can be

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
