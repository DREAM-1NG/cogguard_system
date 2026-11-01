# Text evidence: Figure 2

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 8
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [256.398, 83.567, 514.003, 239.341]

## Caption

Figure 2: Performance of different methods on LastFM and Can. Parl. with varying input lengths.

## Text from suggested visual region

~~~text
v.


%
%


%
    Figure 2: Performance of different methods on LastFM and
%  Can. Parl. with varying input lengths.
~~~

## Body references

- [PDF p.8] We validate the advantages of our patching technique in preserving the local temporal proximities and reducing the computational complexity, which helps DyGFormer effectively and efficiently utilize longer histories. We conduct experiments on LastFM and Can. Parl. since they can benefit from longer historical records. For baselines, we sample more neighbors or perform more causal anonymous walks (starting from 32) to make them access longer histories. The results are depicted in Figure 2, where the x-axis is represented by a logarithmic scale with base 2. We also plot the performance of baselines with the optimal length by unconnected points based on Table 9 in Section B.5. Note that the results of some baselines are incomplete since they raise the out-of-memory error when the lengths are longer. For example, TGAT is only computationally feasible when extending the input length to 32, resulting in two discrete points with lengths 20 (the optimal length) and 32.
- [PDF p.8] From Figure 2, we conclude that: (i) most of the baselines perform worse when the input lengths become longer, indicating they lack the ability to capture long-term temporal dependencies; (ii) the baselines usually encounter expensive computational costs when computing on longer histories. Although memory network-based methods (i.e., DyRep and TGN) can handle longer histories with affordable computational costs, they cannot benefit from longer histories due to the potential issues of vanishing or exploding gradients; (iii) DyGFormer consistently achieves gains from longer sequences, demonstrating the advantages of the patching technique in leveraging longer histories.
- [PDF p.10] longer histories (see Figure 2 and Table 9 in Section B.5), DyGFormer is significantly better than baselines on these two datasets. When CNRs of TP and TN are less distinguishable in the datasets, DyGFormer may perform worse (only 2 out of 13 datasets show this property). For US Legis., the CNRs between TP and TN are close (i.e., 75.18% vs. 53.98%), making DyGFormer worse than memory-based baselines (i.e., JODIE, DyRep, and TGN). For UN Vote, its CNR of TP is even lower than that of TN (i.e., 56.24% vs. 76.02%), which is opposite to our motivation, leading to poor results of DyGFormer than a few baselines. Since these two datasets cannot obviously gain from longer sequences either (see Table 9 in Section B.5), DyGFormer obtains worse results on them. Thus, we conclude that for datasets with much higher CNR of TP than CNR of TN or datasets that can benefit from longer histories, DyGFormer is a good choice. Otherwise, we may need to try other methods.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
