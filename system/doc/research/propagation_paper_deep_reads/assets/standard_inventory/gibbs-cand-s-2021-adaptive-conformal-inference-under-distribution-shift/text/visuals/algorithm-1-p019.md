# Text evidence: Algorithm 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 19
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text
- **Suggested region:** [21.42, 13.551, 590.58, 361.682]

## Caption

Algorithm 1: CQR method for election night prediction Data: Observed sequence of county-level votes counts and covariates {(Xt, Yt)}1≤t≤T and vote counts for the democratic candidate in the previous election {Y prev t }1≤t≤T . for t = 1, 2, . . . , T do

## Text from suggested visual region

~~~text
Algorithm 1: CQR method for election night prediction
Data: Observed sequence of county-level votes counts and covariates {(Xt, Yt)}1≤t≤T and vote
      counts for the democratic candidate in the previous election {Ytprev }1≤t≤T .
for t = 1, 2, . . . , T do
   Compute the residual rt = (Yt −Ytprev )/Ytprev
for t = 501, 502, . . . , T do
   // We start making predictions once 500 counties have been observed.
   Randomly split the data {(Xl, rl)}1≤l≤t−1 into a training set Dtrain and a calibration set Dcal
     with |Dtrain| = ⌊(t −1) · 0.75⌋;
    Fit a linear quantile regression model ˆq(x; p) on Dtrain;
    for (Xl, rl) ∈Dcal do
      Compute the conformity score Sl = max{ˆq(Xl; α/2) −rl, rl −ˆq(Xl; 1 −α/2)};
                           n       1                 o   Deﬁne the quantile function ˆQt(p) = inf  x :   |Dcal| P(Xl,rl)∈Dcal 1Sl≤x ≥p  ;
    Return the prediction set

                                                               t                                                                                prev   ,                                               −ˆq(Xt; 1 −α/2)} ≤ˆQt(1 −α)};     ˆCt(α) := {y : max{ˆq(Xt; α/2) −y−YYt  prev y−Ytprev                                           Ytprev


Lemma A.1 Let f : R →R and g : R →R be bounded functions such that either

      1. f is non-increasing and g is non-decreasing,

      2. or f is non-decreasing and g is non-increasing.

Then for any random variable Y
~~~

## Body references

- [No body reference recovered]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
