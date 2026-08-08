# Text evidence: Figure 4

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 4
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [372.708, 110.933, 512.996, 214.411]

## Caption

Figure 4: The correlation be- tween walks needs to be captured to learn this law.

## Text from suggested visual region

~~~text
interacts with this node at least twice.”
                                𝑡3             𝑡1                             a             a         u       u
                                𝑡4            𝑡2                             b       u             a         u


     𝑢takes action   𝑢NOT takes action
   Figure 4:  The correlation be-
   tween walks needs to be captured
    to learn this law.

entities to avoid the issue in Fig 3
~~~

## Body references

- [PDF p.5] Set-based Anonymization. Based on Su and Sv, we may anonymize each node identity w that appears on at least one walk in Su ∪Sv and design relative node identity ICAW (w; {Su, Sv}) for w. Our design has the following consideration. IAW (Eq.2) only depends on a single path, which results from the original assumption that any two AWs do not even share the name space (i.e., node identities) (Micali & Zhu, 2016). However, in our case, node identities are actually accessible, though an inductive model is not allowed to use them directly. Instead, correlation across different walks could be a key to reﬂect laws of network dynamics: Consider the case when the link {u, v} happens only if there is another node appearing in multiple links connected to u (Fig. 4). Therefore, we propose to use node identities to ﬁrst establish such correlation and then remove the original identities.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
