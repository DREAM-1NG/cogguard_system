# Text evidence: Figure 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 4
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [98.0, 61.998, 514.003, 234.094]

## Caption

Figure 1: Framework of the proposed model.

## Text from suggested visual region

~~~text
Figure 1: Framework of the proposed model.
~~~

## Body references

- [PDF p.3] The framework of our DyGFormer is shown in Figure 1, which employs Transformer [56] as the backbone. Given an interaction (u, v, t), we first extract historical first-hop interactions of source node u and destination node v before timestamp t and obtain two interaction sequences St u and St v. Next, in addition to computing the encodings of neighbors, links, and time intervals for each sequence, we also encode the frequencies of every neighbor’s appearances in both St u and St v to exploit the correlations between u and v, resulting in four encoding sequences for u/v in total. Then, we divide each encoding sequence into multiple patches and feed all the patches into a Transformer for capturing long-term temporal dependencies. Finally, the outputs of the Transformer are averaged to derive time-aware representations of u and v at timestamp t (i.e., ht u and ht v), which can be applied in various downstream tasks like dynamic link prediction and dynamic node classification.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
