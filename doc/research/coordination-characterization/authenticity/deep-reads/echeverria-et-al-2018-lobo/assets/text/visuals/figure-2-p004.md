# Text evidence: Figure 2

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 4
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [303.795, 41.023, 570.981, 327.194]

## Caption

Figure 2: Abstract representation of the LOBO test. The classiﬁer gets trained on all bot classes BCi except the target class BCt, and then tested on the target class to assess how well the classiﬁer gener- alizes.

## Text from suggested visual region

~~~text
General dataset consisting of users and
                     several classes of bots or botnets


                  Bot Ci                 User C


                   Randomly split into train/test
                    (with or without balancing/subsampling)

             Train Bci     Test Bci     Train Uc     Test Uc


                                   First Training round

             LOBO Model                Full Model

          Train {Bci - Bct}   Train Uc      Train Bci   Train Uc

                             Classiﬁer testing on
                                    target class

           LOBO Model                       Full Model

                  Bot Ct                          Test Ct


Figure 2: Abstract representation of the LOBO test. The classiﬁer
gets trained on all bot classes BCi except the target class BCt, and
then tested on the target class to assess how well the classiﬁer gener-
alizes.
~~~

## Body references

- [PDF p.5] by training only with other bot classes, explicitly without any direct knowledge of the target class itself. It was conceived strictly in the context of a binary classiﬁcation between bots and users, to speciﬁcally address the variety of bot classes that such a classiﬁer would face. We assume the LOBO test to be a proxy for generalization. For example, let us take the Bursty bots as the target class. We train the classiﬁer with all other datasets except dataset B, then we test the classiﬁer against dataset B. If the classiﬁer performs well on the Bursty bots when it hasn’t actually trained on them, then it has “generalized” from the seen bot classes to this target class. A ﬂowchart of how the test should be applied can be seen in Fig 2.
- [PDF p.7] 6.3 LOBO Test I - C30K We run a LOBO test on our C30K bot dataset with class size ≤30k. It follows the steps in Fig. 2. The results are summarized in Tab. 5, where:

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
