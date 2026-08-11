# Text evidence: Table 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 4
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [41.024, 41.988, 308.202, 321.212]

## Caption

Table 1: Different bot datasets, their identiﬁers, botometer metrics, and number of accounts collected for each of them

## Text from suggested visual region

~~~text
ID  Name              BTS(%)  BTS(Avg)      Size
 A    Star Wars Bots        —    —   357,000
  B    Bursty Bots                  2.75        0.04   500,000
  C   DeBot                       7.67        0.09   700,000
 D   Fake followers              96.79        0.90      721
  E    Social spambots #1          92.35        0.85      551
  F    Social spambots #2          99.37        0.96     3,320
 G    Social spambots #3          94.10        0.87      458
 H    Traditional spambots #1      98.28        0.93      872
   I     Traditional spambots #2    100.00        0.85        1
   J     Traditional spambots #3      66.08        0.60      283
 K    Traditional spambots #4      97.81        0.90      977
  L   ∼1k followers              20.89        0.21      387
 M  ∼100K followers           10.90        0.13      534
 N  ∼1M followers              1.32        0.02      229
 O  ∼10M followers             0.00        0.00       26
 Q   Fake followers-FSF        100.00        0.96       33
  S    Fake followers-INT        100.00        0.95       64
  T    Fake followers-TWT        95.34        0.89      624
 V   HoneyPot bots (Darpa)       27.69        0.30     2,521
 W   Attack on Ben Nimmo       59.09        0.54     1,558
 X    Attack on Brian Krebs       83.05        0.78      728

Table 1: Different bot datasets, their identiﬁers, botometer metrics,
and number of accounts collected for each of them
~~~

## Body references

- [PDF p.3] so far in the literature. While most of the datasets have high percentage of bot ac- counts associated with them, a few might have small amounts of false positives in them. This is a trade-off that needs to be made to avoid inducing bias by ﬁltering these datasets before classiﬁcation. Do note that we are only reporting the number of accounts that, at collection time, had not been suspended by Twitter or marked as private. This is because suspension or marking an account as private prevents us from collecting any of its information. Many of these datasets were obtained from past papers ei- ther from authors or directly querying each of the user IDs in them against the Twitter API. Some of them come from an API themselves, and a couple of extra ones are not related to research, but the result of botnet attacks on two journalists and their own listing of the IDs that were involved in those attacks. A summary of these datasets is presented in Table 1. Overall, what follows is how we aggregated one of the largest and most varied bot datasets in research.
- [PDF p.4] 3.4 Botometer Scores Botometer [15] (previously botornot) is a public API that provides a score based on whether an account is likely to be a bot or a user. It has been used to verify bot accounts in other research [9]. For our different bot classes, botometer does not perform well enough. This can be seen in Table 1,

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
