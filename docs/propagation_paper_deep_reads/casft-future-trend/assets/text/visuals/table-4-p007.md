# Text evidence: Table 4

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 7
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [309.5, 217.011, 568.015, 630.542]

## Caption

Table 4: Impact of different types of ODE Solver on the per- formance of CasFT across the three datasets.

## Text from suggested visual region

~~~text
Table 4: Impact of different types of ODE Solver on the per-
formance of CasFT across the three datasets.


CasFT using varying steps, ranging from 500 to 1500. The
results are shown in Figure 3 and we find that the number
of diffusion steps has an impact on the Twitter dataset while
the MAPE in APS and Weibo datasets tend to be stable. Ad-
ditionally, among the ODESolver options shown in Table 4,
euler yields the worst performance because the error of eu-
ler’s method usually decreases as the step size decreases,
while dopri5 demonstrates relatively superior predictive ca-
pabilities and is used across all of our experiments.
  Moreover, the prognostication of CasFT relies on the dy-
namic hidden state ht and the generated segmented popular-
ity sequence Y 0, prompting an investigation into the influ-
ence of the dimensionality of ht and the interval number l
of Y 0 on the performance, shown in Figure 4 and Figure 5.
It is observed that both the dimension of the hidden state
and the number of intervals affect the ultimate forecasting
outcomes.

                Conclusion

In this work, we propose CasFT, which leverages observed
information Cascades and dynamic cues modeled via neu-
ral ODEs as conditions to guide the generation of Future
popularity-increasing Trends through a diffusion model. The
generated trends are integrated with the spatiotemporal pat-
terns present in the observed information cascades to en-
hance the accuracy of popularity predictions. Experiments
on three real-world information cascade datasets demon-
strate the superior performance of CasFT compared to a
sizeable collection of state-of-the-art baselines. CasFT sig-
nificantly outperforms all the baselines, with 2.2%-19.3%
improvement over the best-performing baseline methods
across various datasets.
~~~

## Body references

- [PDF p.7] CasFT using varying steps, ranging from 500 to 1500. The results are shown in Figure 3 and we find that the number of diffusion steps has an impact on the Twitter dataset while the MAPE in APS and Weibo datasets tend to be stable. Ad- ditionally, among the ODESolver options shown in Table 4, euler yields the worst performance because the error of eu- ler’s method usually decreases as the step size decreases, while dopri5 demonstrates relatively superior predictive ca- pabilities and is used across all of our experiments. Moreover, the prognostication of CasFT relies on the dy- namic hidden state ht and the generated segmented popular- ity sequence Y 0, prompting an investigation into the influ- ence of the dimensionality of ht and the interval number l of Y 0 on the performance, shown in Figure 4 and Figure 5. It is observed that both the dimension of the hidden state and the number of intervals affect the ultimate forecasting outcomes.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
