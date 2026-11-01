# Text evidence: Algorithm 3

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 14
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text
- **Suggested region:** [21.42, 374.755, 590.58, 686.81]

## Caption

Algorithm 3: Iterative Sampling (E, α, wp, tp)

## Text from suggested visual region

~~~text
The Iterative sampling subroutine Alg.3 is an efﬁcient implementation of step 5 in Alg.1. We may
  ﬁrst show that the sampling probability of a link (e, t) in Ewp,tp is proportional to exp(α(t −tp)) in
  Prop.A.1.

  Algorithm 3: Iterative Sampling (E, α, wp, tp)
1 Initialize V ←∅, Ω←∅;
2 for (e, t) ∈Ewp,tp with an decreasing order of t do
3    Sample a ∼Unif[0, 1];
4     pwp,t is the score of this link related to wp obtained from Alg.2;
5       if a < pwp,t then
6        Return (e, t);

7 Return ({wp, X}, tX);

  Proposition A.1. Based on the probabilities (Eq.9) pre-computed by Alg.2, Alg.3 will sample a link
  (e, t) in Ewp,tp with probability proportional to exp(α(t −tp)).

  Proof. To show this, we ﬁrst order the timestamps of links in Ewp,tp between [t, tp) as t = t′0 < t′1 <
   t′2 < · · · < t′k < tp where there exists an link (e′, t′i) ∈Ewp,tp for t′i. Then, the probability to sample
  a link (e, t) ∈Ewp,tp satisﬁes

                               k
               p = pwp,t × Y 1 −pwp,t′i
                             i=1
                                                 k P             exp(αt′)
                           exp(αt)                     (e′,t′)∈Ewp,t′i−1           =             × Y
         P         exp (αt′)   P           exp(αt′)
~~~

## Body references

- [No body reference recovered]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
