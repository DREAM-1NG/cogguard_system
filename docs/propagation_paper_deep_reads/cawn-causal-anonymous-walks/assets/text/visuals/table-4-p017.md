# Text evidence: Table 4

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 17
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text
- **Suggested region:** [97.502, 17.813, 514.351, 355.28]

## Caption

Table 4: Hyperparameter search range of CAW sampling.

## Text from suggested visual region

~~~text
Published as a conference paper at ICLR 2021


C.2  BASELINES, IMPLEMENTATION AND TRAINING DETAILS

C.2.1  CAW-N-MEAN AND CAW-N-ATTN

We ﬁrst report the general training hyperparameters of our models in addition to those mentioned in
the main text: on all datasets, we train both variants with mini-batch size 32 and set learning rate =
1.0 × 10−4; the maximum training epoch number is 50 though in practice we observe that with early
stopping we usually ﬁnd the optimal epoch in fewer than 10 epochs; our early stopping strategy is
that if the validation performance does not increase for more than 3 epoch then we stop and use the
third previous epoch for testing; dropout layers with dropout probability = 0.1 are added to the RNN
module, the MLP modules, and the self-attention pooling layer. Please refer to our code for more
details.

In terms of the three hyperparameters controlling CAW sampling, we discussed them in Sec 5.3. For
all datasets, they are systematically tuned with grid search, whose ranges are reported in Tab.4.

      Dataset     Sampling number M          Time decay α          Walk length m
       Reddit             32, 64, 128           {0.25, 0.5, 1.0, 2.0, 4.0}×10−5          1, 2, 3, 4
      Wikipedia          32, 64, 128           {0.25, 0.5, 1.0, 2.0, 4.0}×10−6           2, 3, 4
    MOOC            32, 64, 128           {0.25, 0.5, 1.0, 2.0, 4.0}×10−6          2, 3, 4, 5
       Social Evo.         32, 64, 128         {0.25, 0.5, 1.0, 2.0, 4.0, 8.0}×10−6         1, 2, 3
      Enron              32, 64, 128           {0.25, 0.5, 1.0, 2.0, 4.0}×10−7          1, 2, 3, 4
     UCI                32, 64, 128            {0.6, 0.8, 1.0, 1.2, 1.4}×10−5            1, 2, 3

                   Table 4: Hyperparameter search range of CAW sampling.
~~~

## Body references

- [No body reference recovered]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
