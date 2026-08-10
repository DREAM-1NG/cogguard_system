# Text evidence: Figure 7

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 9
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [280.163, 552.988, 515.49, 716.367]

## Caption

Figure 7: Time comparison: PINT versus TGNs (in log- scale). The cost of pre-computing positional features is quickly diluted as the number of epochs increases.

## Text from suggested visual region

~~~text
Wikipedia                   UCI
  .           log(s)
         7                               5
 -       epoch
 r     per 6                               4
         time 5                               3
 t         Avg. 4                               2 f        0  25 50    100    150    200    0  25 50    100    150    200
 -                   Epochs                          Epochs
 -          PINT         PINT (w/o pos.)        TGAT      CAW         TGN-Att
 -
T  Figure 7: Time comparison: PINT versus TGNs (in log-
     scale). The cost of pre-computing positional features is -    quickly diluted as the number of epochs increases. -
~~~

## Body references

- [PDF p.9] Time comparison. Figure 7 compares the training times of PINT against other TGNs. For fairness, we use the same architecture (number of layers & neighbors) for all MP- TGNs: i.e., the best-performing PINT. For CAW, we use the one that yielded results in Table 1. As expected, TGAT is the fastest model. Note that the average time/epoch of PINT gets amortized since positional fea- tures are pre-computed. Without these fea- tures, PINT’s runtime closely matches TGN- Att. When trained for over 25 epochs, PINT runs considerably faster than CAW. We pro- vide additional details and results in the sup- plementary material.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
