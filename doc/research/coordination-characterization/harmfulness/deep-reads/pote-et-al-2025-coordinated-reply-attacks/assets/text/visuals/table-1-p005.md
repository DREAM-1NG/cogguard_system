# Text evidence: Table 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 5
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [21.42, 148.125, 590.58, 203.358]

## Caption

Table 1: Reply-level attributes used to generate features for the tweet classifier.

## Text from suggested visual region

~~~text
Table 1: Reply-level attributes used to generate features for
the tweet classifier.
~~~

## Body references

- [PDF p.5] ing, while inauthentic activity mainly focused on manipu- lating conversations through replies. Based on these obser- vations, we use three tweet-level features: reply count, retweet count, and like count. Next, let us consider reply-level features. These are based on eight attributes, listed in Table 1. Engagement and en- tity attributes are defined for each reply. The delay is also defined, for each reply, as the difference between the times- tamps of the tweet and the reply. The similarity is designed to capture the presence of similar narratives in replies, a common characteristic of inauthentic engagement. To this end, we first generate vector embeddings for the replies us- ing the LaBSE model (Feng et al. 2020), which supports 109 languages. The cosine attribute is then computed for each pair of replies to the same tweet as the cosine similarity be- tween the corresponding vectors. Since targeted tweets can have many replies, this proce- dure yields many attribute values that must be aggregated to obtain a set of features for each tweet. In the case of en- gagement, entities, and delay attributes, we have one value per reply. For the similarity attribute, we have one value per a pair of replies. In all cases, we aggregate these val- ues to obtain a single distribution of attribute values for each tweet. From these distributions we compute the following 12 summary statistic features: range, 25/50/75 quartiles, inter- quartile range, minimum, maximum, mean, standard devia- tion, skewness, kurtosis, and entropy. Since we do this for each of eight attributes, the total nu

[TRUNCATED BY EXTRACTOR]
- [PDF p.8] attributes, which we organize into four sets, just like those listed in Table 1. The only criterion that distinguishes how these features are calculated in the tweet versus the replier classification task is the reply set — all replies to a tweet in the former case and all replies by a replier in the latter. Given a set of replies, the replier classifier features are calculated as for the tweet classifier, with two exceptions. First, the delay of each reply is computed with respect to the timestamp of the targeted tweet to which the reply was di- rected. Second, cosine similarity s for replier i is calculated for each pair (rt i, rt j) where rt i is a reply by i to a targeted tweet t and rt j is a reply by a different user j to the same targeted tweet t. We obtain a distribution of these similar- ities ∪t∈T (i) ∪j∈J(t) s(rt i, rt j) across the set J(t) of other users who reply to t and then across the set T(i) of targeted tweets that receive a reply from i. From the distribution of each attribute, we compute nine summary statistic features: range, 25/50/75 quartiles, inter- quartile range, maximum, minimum, mean, and entropy. We do not calculate standard deviation, skewness, and kurtosis because they are not defined for many repliers who are in- volved in a single reply to a single targeted tweet. We end up with four profile metadata features and 8×9 = 72 reply-level features, for a total of 76 features.

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
