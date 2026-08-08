# Text evidence: Algorithm 2

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 14
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text
- **Suggested region:** [21.42, 143.137, 590.58, 454.29]

## Caption

Algorithm 2: Online probability computation (G, α)

## Text from suggested visual region

~~~text
such that
                              exp(αt)                     exp(αt)
                      pu,t =                             pv,t =                                        (9)
           P                       P                                   (e,t′)∈Eu,t exp(αt′),                                                                         (e,t′)∈Ev,t exp(αt′).
  These probabilities will be used later in sampling (Alg.3) and do not need to be updated any more.

  Algorithm 2: Online probability computation (G, α)
 1 Initialize V ←∅, Ω←∅;
 2 for ({u, v}, t) ∈E do
 3     for w ∈{u, v} do
 4           if w ̸∈V then
 5         V ←V ∪{w};
 6        Pw ←exp(αt);
 7         else
 8           Find Pw ∈Ω;
 9        Pw ←Pw + exp(αt);
10         pw,t ←exp(αt)Pw    ;
11     Ω←Ω∪{Pw};
12    Assign two probability scores: ({(u, pu,t), (v, pv,t)}, t, ) ←({u, v}, t) ;


  The Iterative sampling subroutine Alg.3 is an efﬁcient implementation of step 5 in Alg.1. We may
   ﬁrst show that the sampling probability of a link (e, t) in Ewp,tp is proportional to exp(α(t −tp)) in
  Prop.A.1.

  Algorithm 3: Iterative Sampling (E, α, wp, tp)
              ∅      ∅
~~~

## Body references

- [No body reference recovered]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
