# Text evidence: Table 3

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 9
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text
- **Suggested region:** [97.691, 405.689, 515.244, 591.938]

## Caption

Table 3 shows the performance of TG methods on medium and large TGB datasets. Note that some methods, including CAWN, TCL, and GraphMixer, ran out of memory on GPU for these datasets, thus their performance is not reported. Overall, TGN has the best performance on all of these three datasets. Surprisingly, the EdgeBank heuristic is highly competitive on the tgbl-coin dataset where it even significantly outperforms DyRep. Therefore, it is important to include EdgeBank as a baseline for all datasets. Another observation is that for medium and large TGB datasets, there can be a significant performance change for a single model between the validation and test set. This is because TGB datasets span over a long time (such as tgbl-comment, lasting 5 years) and one can expect that models need to deal with potential distribution shifts between the validation set and the test set. Figure 6a, 6b and 6c reports the test time for TG methods on tgbl-coin, tgbl-flight and tgbl-comment, respectively. On both tgbl-coin and tgbl-comment, Edgebank is at least one order of magnitude faster than TGN and DyRep while on the tgbl-flight, due to the large number of temporal edges, DyRep is the fastest method.

## Text from suggested visual region

~~~text
closer to baselines such as EdgeBank, which can better scale to large real world temporal graphs.

Table 3 shows the performance of TG methods on medium and large TGB datasets. Note that some
methods, including CAWN, TCL, and GraphMixer, ran out of memory on GPU for these datasets,
thus their performance is not reported. Overall, TGN has the best performance on all of these three
datasets. Surprisingly, the EdgeBank heuristic is highly competitive on the tgbl-coin dataset where
it even significantly outperforms DyRep. Therefore, it is important to include EdgeBank as a baseline
for all datasets. Another observation is that for medium and large TGB datasets, there can be a
significant performance change for a single model between the validation and test set. This is because
TGB datasets span over a long time (such as tgbl-comment, lasting 5 years) and one can expect
that models need to deal with potential distribution shifts between the validation set and the test
set. Figure 6a, 6b and 6c reports the test time for TG methods on tgbl-coin, tgbl-flight and
tgbl-comment, respectively. On both tgbl-coin and tgbl-comment, Edgebank is at least one
order of magnitude faster than TGN and DyRep while on the tgbl-flight, due to the large number
of temporal edges, DyRep is the fastest method.


5.2  Dynamic Node Property Predictioni
~~~

## Body references

- [No body reference recovered]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
