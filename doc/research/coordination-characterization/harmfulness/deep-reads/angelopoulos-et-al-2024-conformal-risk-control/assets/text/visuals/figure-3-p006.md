# Text evidence: Figure 3

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 6
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [98.0, 73.043, 514.003, 343.698]

## Caption

Figure 3: Control of graph distance on hierarchical ImageNet. The top figure shows examples of our procedure with correct classes in black, false positives in blue, and false negatives in red. The bottom plots report our minimum hierarchical distance loss and set size over 1000 independent random data splits. The dashed gray line marks α.

## Text from suggested visual region

~~~text
soupsoupsoup bowlbowlbowl            LoaferLoaferLoafer             ponchoponchoponcho              candlecandlecandle
         dishdish                shoeshoe                 cloakcloak              lamplamp
        hot pot              sandal               cloak                  jack-o'-lantern


       meatmeatmeat loafloafloaf             tabletabletable lamplamplamp            spotlightspotlightspotlight            soupsoupsoup bowlbowlbowl
         dishdish               lamplamp              lamplamp                 dishdish
         burrito              candle              candle            consomme


                                                                              100

                  density                                                            10 1
          100                                                         10 2

            0
                     0.047   0.048   0.049   0.050   0.051   0.052   0.053          0     1     2     3     4     5     6     7     8
                                                    risk                                                              height
Figure 3: Control of graph distance on hierarchical ImageNet. The top figure shows examples
of our procedure with correct classes in black, false positives in blue, and false negatives in red.
The bottom plots report our minimum hierarchical distance loss and set size over 1000 independent
random data splits. The dashed gray line marks α.
~~~

## Body references

- [PDF p.7] We use the ImageNet dataset (Deng et al., 2009), which comes with an existing label hierarchy, WordNet, of maximum depth D = 14. We choose a ResNet152 (He et al., 2016) for f and n = 30000, and evaluate risk with the remaining 20000. We report results with α = 0.05 in Figure 3. The mean and standard deviation of the risk over 1000 trials are 0.0499 and 0.0011, respectively. The results indicate that the risk is almost exactly controlled, and that the adaptively chosen resolution of the prediction appropriately encodes the model uncertainty (it is almost always a leaf node).

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
