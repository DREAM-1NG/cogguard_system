# Text evidence: Table 1

> This file contains extracted text, not a visual interpretation. The image pixels, layout, axes, colors, and panels were not verified.

- **PDF page:** 4
- **Text extraction status:** partial
- **Available sources:** caption, suggested-region-text, body-references
- **Suggested region:** [26.0, 600.249, 586.001, 767.6]

## Caption

Table 1. Data sets and how we combined them for our analysis.

## Text from suggested visual region

~~~text
Table 1. Data sets and how we combined them for our analysis.

                                                dataset              In our analysis                                        Valid accounts

                                     German politicians       all/ German politicians and bots                     human = 516

                                  US politicians             all/ US politicians and bots                        human = 502

                                 New bots                   all/ US politicians and bots/ German politicians and bots     bots = 928

                                     German bots              all/ German politicians and German bots                    bots = 27

                                             Varol                        all/ Varol et al.                                             bots = 699 / human = 1462

                                                     https://doi.org/10.1371/journal.pone.0241045.t001


PLOS ONE | https://doi.org/10.1371/journal.pone.0241045  October 22, 2020                                                         4 / 20
~~~

## Body references

- [PDF p.4] To answer these research questions, we rely on five data sets. We included all official accounts of German members of parliament based on a list of personally confirmed official accounts (German politicians: n = 532) and all members of the 115th U.S. Congress with a Twitter account (US politicians: n = 516) [28] as “human” accounts. We also created a list of obvious bots (new bots: n = 935). We used all bots listed on https://botwiki.org/, a database with the goal to preserve interesting and creative Twitter bots as well as a number of other labelled bots we identified on Twitter. Most of these accounts are labelled as bots and for many even their code is available on GitHub. As most of these bots use the English language, we also collected an additional list of German language bots (German bots: n = 27). As a fifth dataset we use a manually annotated data set with human (n = 1747) and bot accounts (n = 826) that was cre- ated by the makers of Botometer [4]. We combined these data sets for our data analysis (see Table 1). For the first three research questions we need bots as well as human accounts com- bined as we are evaluating how well Botometer can distinguish automated from human accounts. We therefore combine the different datasets (see Table 1). For RQ4, however, we can use single datasets consisting only of bots or humans. Our selection of the data sets is based on one basic assumption: bot detection tools like Bot- ometer will perform better in distinguishing between bots and humans when the cases are clear-cut. As can be seen in Fig 1, clear cut bot accounts will

[TRUNCATED BY EXTRACTOR]
- [PDF p.6] automatically lead to media attention and increased scrutiny. In Germany, for example, jour- nalists have discovered a network around AfD politicians’ Twitter accounts that consisted of sockpuppets that boosted engagement numbers [29]. This is not to say that politicians might not make use of any automation but rather that this form of automation is and should not be confused with bots or social bots. Finally, we also included Varol’s list that included both bots as well as humans. While we were not always able to individually verify whether an account was a bot or a human, we trust in the initial categorization which parts of Botometer’s training is based on. As a result, we have four data sets of accounts that human coders would have no difficulty in differentiating between bots and humans and one which was used to train the Bot- ometer classifier on. Based on these criteria, we would expect the Botometer tool to perform rather well as the “real world” data from Twitter is much messier. To conduct this test, we created a Python script that ran every day at 00:00 UTC time on an Ubuntu Linux server for 3 months (3rd March– 2nd of June, 2019). The data collection went uninterrupted. For every account in our sample (n = 4,583) we requested the Twitter data via the Twitter search API and the Botometer user scores via the Botometer API giving us a total of 374,724 valid scores. For the analysis we accessed Botometer v3 [12] which was the latest ver- sion of the tool in March 2019. Besides an empty timeline (Botometer needs at least one tweet– 2,021 calls had to be excluded), mi

[TRUNCATED BY EXTRACTOR]

## Mandatory limitation

A text-only model must not claim direct observation of visual trends, layout, axes, colors, panels, qualitative examples, or crop completeness.
