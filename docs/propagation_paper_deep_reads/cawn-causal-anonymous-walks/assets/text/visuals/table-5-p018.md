# Text evidence: Table 5

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 18
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text
- **Suggested region:** [97.532, 524.052, 515.242, 772.157]

## Caption

Table 5: Snapshot split for evaluating snapshot-based baselines.

## Text from suggested visual region

~~~text
Table 5: Snapshot split for evaluating snapshot-based baselines.


We make the following decisions to evaluate snapshot-based baselines in a fair manner, so that their
performances are comparable to those derived from the stream-based evaluation procedure. The
ﬁrst step we do is to evenly split the whole dataset chronologically into a number of snapshots. We
determine the exact number of snapshots by referring the three snapshot-based baselines we use. For
Wikipedia and MOOC dataset which are not used by any snapshot-based baseline, we split them into
a total of 20 snapshots. Next, we need to determine the proportions of these snapshots assigned each
to training, validation, and testing set. In doing this, our principle is that the proportions of these three
sets should be close to 70:15:15 as much as possible, since that ratio is what we use for evaluating
stream-based baselines and our proposed method. These decisions lead to our ﬁnal splitting scheme
summarized in Tab. 5.

Extra care should also be taken when testing snapshot-based methods. For a queried link in a snapshot,
usually snapshot-based methods only make a binary prediction whether or not that link may exist
at any time in that snapshot. They do not, however, take care of the case that the link may appear
multiple times at different time points within that snapshot’s time range. This lead to a different
evaluation scheme than stream-based methods, which do consider the multiplicity of links. Therefore,


                                       18
~~~

## Body references

- [No body reference recovered]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
