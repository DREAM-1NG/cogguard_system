# Text evidence: Table 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 5
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [309.5, 156.9, 568.015, 538.227]

## Caption

Table 1: Statistics of the three datasets.

## Text from suggested visual region

~~~text
Table 1: Statistics of the three datasets.

where P and ˆP is the ground-truth and the predicted popu-
larity, respectively. For the generative part, we minimize the
following negative log-likelihood:

             M
            L2 = − X log pθ(Y k0 |ck).            (24)
                    k=1
To sum up, the final loss is defined as:

             L = L1 + γL2,                 (25)

where γ is a hyperparameter used to adjust the trade-off be-
tween two losses.

               Experiments
In this section, we  first present our benchmark datasets
and then evaluate our model CasFT1 against state-of-the-art
baselines in information cascade popularity prediction task
to answer the following questions:
  RQ1: Compared to state-of-the-art baselines, can our ap-
proach achieve a more accurate prediction of cascade popu-
larity?
  RQ2: What are the benefits of employing neural ODEs
to model the growth rate? How much does it contribute to
performance improvement?
  RQ3: Why do we need diffusion models for enhancing
the modeling of future trend dynamics? In contrast, how
does the utilization of simpler models capture this charac-
teristic?
  RQ4: What is the impact of the hyperparameters, includ-
ing the number of segmented periods, the choice of ODES-
olver, the hidden dimension, and the diffusion steps?
~~~

## Body references

- [PDF p.6] Following previous works (Xu et al. 2021; Lu et al. 2023), we set observation time as 1 day and 2 days for the Twitter dataset, and 3 years and 5 years for the APS dataset, for Weibo, the observation times are set to 0.5 hours and 1 hour. Furthermore, prediction time is set to 15 days for Twitter, 20 years for APS, and 24 hours for Weibo. In addition, we filter out cascades with fewer than 10 participants during the ob- servation periods. For all datasets, 70% of the data is used for training, 15 % for validation, and 15% for testing. Detailed information about the three datasets is provided in Table 1.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
