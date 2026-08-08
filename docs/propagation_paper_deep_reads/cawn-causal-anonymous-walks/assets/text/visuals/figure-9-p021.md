# Text evidence: Figure 9

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 21
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [130.892, 71.861, 481.111, 223.502]

## Caption

Figure 9: Visualizing all AWs, and their occurrence ratios with positive / negative samples.

## Text from suggested visual region

~~~text
Figure 9: Visualizing all AWs, and their occurrence ratios with positive / negative samples.
~~~

## Body references

- [PDF p.21] We further apply the similar procedure to analyze the AWs introduced in Sec. 4.1 and the model Ab.5 of Tab. 3 used for ablation study. Note that AW cannot establish the correlation between walks, each single AW itself, say W = (v0, v1, ..., vm), decides its own shape sAW (W). We directly set sAW (W) = IAW (v0; W) →IAW (v2; W) →· · · →IAW (vm; W) with IAW (w; W) deﬁned in Eq. 2. As the Wikipedia dataset is a bipartite graph, there are in total four different shapes when m = 3 as listed align with the x-axis of Fig. 9. For illustration, we explain one shape of AW as an example, say 0 →1 →2 →1: The corresponding walks have the second and the fourth nodes correspond to the same node, which the ﬁrst, second and third nodes are different. As shown in Fig. 9, we can see that AW’s occurrence with positive versus negative links are highly mixed-up, compared to CAW’s. That suggests that AWs possess signiﬁcantly less discriminatory power than CAWs. The main reason is that AWs do not have set-based anonymization, so they cannot capture the correlation between walks/motifs but CAWs can do that. This observation further gives a reason on why the model Ab.5 of Tab. 3 only achieves some performance on-par with the model Ab.2 where we totally remove the anonymization procedure: the anonymization adopted by AWs loses too much information of the structure and cannot beneﬁt the prediction much. However, the original CAW-N well captures such information via the set-based anonymization.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
