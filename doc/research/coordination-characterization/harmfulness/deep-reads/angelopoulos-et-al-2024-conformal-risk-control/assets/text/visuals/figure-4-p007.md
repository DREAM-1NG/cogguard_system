# Text evidence: Figure 4

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 7
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [98.0, 71.862, 514.003, 288.217]

## Caption

Figure 4: F1-score control on Natural Questions. The top figure shows examples of our procedure with fully correct answers in green, partially correct answers in blue, and false positives in gray. Note that answers that are technically correct may still be down-graded if they do not match the reference. We treat this as part of the randomness in the task. The bottom plots report the F1 risk and average set size over 1000 independent random data splits. The dashed gray line marks α.

## Text from suggested visual region

~~~text
{1 august 1965, 1965, 11 january 2006, …}
        when were cigarette ads banned from tv uk?
                                                                                                     Answers = {1 august 1965, …}    F1 = 1.0


                                                                                                                                   {robert wilkins, jesus, david, keith green, …}
        who told the story of the prodigal son?
                                                                                                      Answers = {Jesus Christ}        F1 = 0.66


           25
                                                                     10 1
           20
           15                  density
           10
            5                                                         10 2
            0
                   0.26       0.28       0.30       0.32       0.34                  20        22        24        26        28        30
                                                   risk                                                                set size
Figure 4: F1-score control on Natural Questions. The top figure shows examples of our procedure
with fully correct answers in green, partially correct answers in blue, and false positives in gray.
Note that answers that are technically correct may still be down-graded if they do not match the
reference. We treat this as part of the randomness in the task. The bottom plots report the F1 risk
and average set size over 1000 independent random data splits. The dashed gray line marks α.
~~~

## Body references

- [PDF p.7] We use the Natural Questions (NQ) dataset (Kwiatkowski et al., 2019), a popular open-domain ques- tion answering baseline, to evaluate our method. We use the splits distributed as part of the Dense Passage Retrieval (DPR) package (Karpukhin et al., 2020). Our base model is the DPR Retriever- Reader model (Karpukhin et al., 2020), which retrieves passages from Wikipedia that might contain the answer to the given query, and then uses a reader model to extract text sub-spans from the retrieved passages that serve as candidate answers. Instead of enumerating all possible answers to a given question, we retrieve the top several hundred candidate answers, extracted from the top 100 passages. We use n = 2500 calibration points, and evaluate risk control with the remaining 1110. We use α = 0.3 (chosen empirically as the lowest F1 score which reliably results in approximately correct answers by manual validation) in Figure 4. The mean and standard deviation of the risk over 1000 trials are 0.2996 and 0.0150, respectively. The results indicate that the risk is almost exactly controlled, and that the sets are reasonably sized, scaling appropriately with question difficulty.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
