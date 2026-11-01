# Text evidence: Table 6

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 9
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [131.867, 227.255, 480.117, 379.189]

## Caption

Table 6: Ablation study on Android and Memetracker datasets.

## Text from suggested visual region

~~~text
Android                     Memetracker
  Models
            Hits@100  MAP@100  MSLE   Hits@100  MAP@100  MSLE

w/o AdvDiff    0.2696       0.0711      0.467     0.5609       0.1605      0.895
w/o Diff        0.2758       0.0716      0.265     0.5747       0.1614      0.853
w/o Adv        0.2712       0.0718      0.369     0.5771       0.1634      0.844
w/o HGNN      0.5871       0.2013      1.074     0.3692       0.1178      0.581

w/o Macro      0.5580       0.1874      9.255     0.3665       0.1191      4.669
w/o Micro       0.5871       0.1937      0.865     0.3591       0.1174      0.711

MINDS         0.2766       0.0727      0.151     0.5790       0.1638      0.506

         Table 6: Ablation study on Android and Memetracker datasets.
~~~

## Body references

- [PDF p.9] We observe that the ablation study across two datasets in Ta- ble 5 may be insufficient. For example, w/o AdvDiff shows the best, worst, and average performance on three metrics compared to w/o Adv and w/o Diff respectively. To ad- dress this concern, we conducted ablation experiments on the other two datasets. The result is shown in Table 6. The suboptimal results on the Christianity and Douban datasets could be due to their unique characteristics, such as sparse network connections leading to minimal feature overlap.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
