# Text evidence: Figure 6

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 9
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [97.704, 175.355, 513.996, 299.187]

## Caption

Figure 6: Complexity evaluation: The accumulated runtime of (a) temporal random walk extraction (Alg.1) and (b) the entire CAW-N training, timed over one epoch on Wikipedia (using different |E| for training).

## Text from suggested visual region

~~~text
Figure 6: Complexity evaluation: The accumulated runtime of (a) temporal random walk extraction (Alg.1) and
(b) the entire CAW-N training, timed over one epoch on Wikipedia (using different |E| for training).
~~~

## Body references

- [PDF p.9] We examine how the runtime of CAW-N depends on the number of edges |E| used for training. We record the runtimes of CAW-N for training one epoch on the Wikipedia datasets using M = 32, m = 2 with batch-size=32. Speciﬁcs of the computing infrastructure are given in Appendix C.5. Fig. 6 (a) shows the accumulated runtime of executing the random walk extraction i.e. Alg.1 only. It well aligns with our theoretical analysis (Thm. A.2) that each step of the random walk extraction has constant complexity (i.e. accumulated runtime linear with |E|). Plot (b) shows the entire runtime for one-epoch training, which is also linear with |E|. Note that O(|E|) is the time complexity that one at least needs to pay. The study demonstrates our method is scalable to long edge streams.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
