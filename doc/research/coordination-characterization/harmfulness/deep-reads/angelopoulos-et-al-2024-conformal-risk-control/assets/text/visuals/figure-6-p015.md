# Text evidence: Figure 6

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 15
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text
- **Suggested region:** [21.42, 389.666, 590.58, 742.269]

## Caption

Figure 6 shows results.

## Text from suggested visual region

~~~text
B
                  λ↑= inf  λ : R↑n(λ) +    ≤α
                                     n + 1
also results in asymptotic risk control (to see this, plug ˜λ↑into Theorem C.1 and see that the risk
level is bounded above by α − n+1).B   Note that in the case of a monotone loss function, ˜λ↑= ˆλ.
However, the counterexample in Proposition 2 does not apply to ˜λ↑, and it is currently unknown
whether this procedure does or does not provide finite-sample risk control.

D  EXPERIMENTS ON COVARIATE SHIFT

To validate the covariate shift extension from Section 4, we perform an experiment on a synthetic
regression under covariate shift. The model is as follows:

                         Xi ∼N(0, 1)
                                Yi = 2Xi + N(0, 0.5|Xi|)
                              Xtest ∼N(0, 2)
                                  Ytest = 2Xtest + N(0, 0.5|Xtest|).

The model used for prediction was a standard linear regression pre-trained on 1000 data points
independent and identically distributed with the calibration data. We estimated the likelihood ratio
using a logistic regression model by solving a classification problem to classify between all the
available training/calibration covariates and batch of 1000 unlabeled test datapoints from the shifted
distribution. The probits from the logistic regression were then transformed to likelihood ratios via
the function h(x) = x/1 −x. We took n = 100 and α = 0.1, controlling the clipped projective
distance of y onto the set C:
                                  ℓ(y, C) = min(projC(y), B),
where B = 2. The set construction is the standard

                                        h        i                                Cλ(x) =  ˆY (x) ± λ  .

Figure 6 shows results.
~~~

## Body references

- [No body reference recovered]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
