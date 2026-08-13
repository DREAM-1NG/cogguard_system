
## Table 2

models: Logistic
Classifier Features                                          Regression, Random Forest, AdaBoost, Decision Tree, and
The tweet  classifier leverages several features extracted      Naive Bayes. Prior to training, we standardize the input fea-
from tweets and from the replies they receive. Let us first       tures via z-scores. We conduct 10-fold cross-validation to
focus on tweet-level features, specifically tweet engage-       mitigate over-fitting of the training data and report on the
ment. We find a few key differences between the engage-     mean precision, recall, and F1 values across folds along with
ment metrics of IO-targeted vs. control tweets. As illus-    AUC in Table 2. Precision, recall, and F1 depend on a thresh-
trated in Fig. 5a, IO-targeted tweets receive more replies      old to transform the model score into a binary classification
(median 31 vs. 22 for control tweets). On the other hand,       label. We tune the threshold to maximize the mean F1 across
control tweets receive slightly more retweets (median 84       folds. In the following, we focus on Random Forest (with
vs. 75 for IO-targeted tweets, Fig. 5b) and more likes (me-     100 estimator trees), which yields the best scores overall.
dian 420 vs. 250, Fig. 5c). This suggests that organic en-       To study the contributions of different features, we fol-
gagement generated more positive interactions and shar-      lowed two approaches. First, we trained and tested Random


                                                   1590


===== PDF p.6 =====
Figure 5: Engagement received by targeted and control tweets. (A) Replies, (B) retweets, and (C) likes. The distributions are
significantly different in all cases according to Kolmogorov-Smirnov tests (p < 10−6).

                              Classifier               Prec.         Rec.        F1      AUC
                             

## Table 3

            Naive Bayes          0.49 ± 0.00   1.00 ± 0.00   0.66 ± 0.00   0.68 ± 0.00

Table 2: Results of different algorithms in the tweet classification task. We present standard errors rounded to the second decimal
point.


      Features set         Prec.   Rec.   F1  AUC
     reply count       0.5    0.99   0.67   0.59
     retweet count    0.49    1     0.66   0.54
     like count        0.49    1     0.66   0.52
      Engagement         0.69    0.86   0.77   0.84
        Entities              0.52    0.95   0.67   0.65
      Delay               0.51    0.96   0.67   0.66
       Similarity            0.54    0.96   0.69   0.68
       All features          0.73    0.87   0.80   0.88

Table 3: Contributions of different tweet-level features and
reply-level feature sets to the Random Forest tweet classifier.
The last row (using all features) corresponds to the results in
Table 2.


Forest on individual tweet-level features and reply-level fea-      Figure 6: Permutation feature importance for tweet classi-
ture sets. The results using 10-fold cross-validation are given         fier. We report the median (orange line), 50% confidence in-
in Table 3. Second, we performed a permutation feature im-       terval (box), and 99.3% confidence interval (whiskers) of the
portance test, which measures the importance of features by      drop in F1 score when each feature/attribute set is shuffled.
computing the loss in accuracy when the values of those fea-     Boxes with the same color indicate attributes in the same
tures are shuffled (permuted). To simplify the analysis, for       feature set. Larger values indicate higher importance.
each reply-level attribute we shuffled all the corresponding
features rather than each feature individually. For example,
for the like count engagement attribute, we shuffled all
12 summary statistics features at once. We repeated this test        

## Table 4

                              RS          0.85   0.54   0.61   0.56      0.52      0.65
                                               SA          0.55   0.76   0.53   0.63      0.74      0.68
                                               TR          0.61   0.60   0.74   0.63      0.65      0.68
                                             EG          0.43   0.37   0.36   0.65      0.38      0.39
                                                      SA/EG/AE   0.47   0.58   0.57   0.60      0.73      0.48
                                                                   Other        0.62   0.59   0.63   0.56      0.52     0 .74

                                                             Table 4: F1 scores obtained from same-campaign (diago-
                                                                 nal entries, in bold) and cross-campaign evaluations of the
                                                              tweet classifier. RS=Serbia, SA=Saudi Arabia, TR=Turkey,
                                                     EG=Egypt. SA/EG/AE = Saudi Arabia/Egypt/Arab Emi-
                                                                       rates is a campaign involving three countries.

Figure 7: Scores of tweet classifiers based on different
thresholds for the number of IO replies received by targeted                                                               values are obtained when the model trained on all data from
tweets.                                                       one campaign (optimized to maximize F1) is tested on other
                                                           campaigns. As expected, the models perform better when
                                                                   trained and tested on the same campaign. However, models
whether tweet-level engagement features would provide suf-      can generalize, with F1

## Table 5

t t and rtj is a reply by a different user j to the same      We standardize the features with z-scores and report the
targeted tweet t. We obtain a distribution of these similar-     mean performance metrics obtained by different machine
ities ∪t∈T (i) ∪j∈J(t) s(rti, rtj) across the set J(t) of other       learning models: Logistic Regression, Random Forest, Ad-
users who reply to t and then across the set T(i) of targeted      aBoost, Decision Tree, and Naive Bayes. As in the tweet
tweets that receive a reply from i.                                       classifier, we tune the threshold to maximize the mean F1
  From the distribution of each attribute, we compute nine       across folds. Table 5 shows that all classifiers perform better
summary statistic features: range, 25/50/75 quartiles, inter-      with downsampling, and Random Forest (with 100 estimator
quartile range, maximum, minimum, mean, and entropy. We       trees) performs the best with both downsampling and over-
do not calculate standard deviation, skewness, and kurtosis      sampling. Therefore, let us focus on this model — Random
because they are not defined for many repliers who are in-       Forest trained with downsampling — for further analysis.
volved in a single reply to a single targeted tweet.               To test the contribution of each feature to the replier clas-
  We end up with four profile metadata features and 8×9 =         sifier, we follow the same procedure as for the tweet clas-
72 reply-level features, for a total of 76 features.                       sifier. However, here we report the averages across the 10
                                                            balanced dataset. Table 6 reports on mean 10-fold cross-
Results                                                                   validation scores for Random Forest trained and tested on
The targeted tweet dataset is h

## Table 6

ulate standard deviation, skewness, and kurtosis      sampling. Therefore, let us focus on this model — Random
because they are not defined for many repliers who are in-       Forest trained with downsampling — for further analysis.
volved in a single reply to a single targeted tweet.               To test the contribution of each feature to the replier clas-
  We end up with four profile metadata features and 8×9 =         sifier, we follow the same procedure as for the tweet clas-
72 reply-level features, for a total of 76 features.                       sifier. However, here we report the averages across the 10
                                                            balanced dataset. Table 6 reports on mean 10-fold cross-
Results                                                                   validation scores for Random Forest trained and tested on
The targeted tweet dataset is highly imbalanced with 0.8%      each profile metadata feature and reply feature set. Fig. 9
IO repliers (7,670 vs. 874,248 normal repliers). Such an im-       reports on the results of a permutation feature importance


                                                   1593


===== PDF p.9 =====
Downsampling          Prec.         Rec.        F1      AUC
                             Logistic Regression   0.89 ± 0.00   0.88 ± 0.00   0.88 ± 0.00   0.93 ± 0.00
                     Random Forest       0.93 ± 0.00   0.92 ± 0.00   0.92 ± 0.00   0.97 ± 0.00
                        AdaBoost            0.90 ± 0.00   0.90 ± 0.00   0.90 ± 0.00   0.96 ± 0.00
                           Decision Tree        0.88 ± 0.00   0.88 ± 0.00   0.88 ± 0.00   0.88 ± 0.00
                         Naive Bayes          0.62 ± 0.02   0.86 ± 0.02   0.68 ± 0.00   0.87 ± 0.00
                        Oversampling        Precision      Recall        F1      AUC
                             Logistic Regression   0.27 ± 0.00

## Table 7

        dia, and politicians are primary targets for coordinated IO
  Next, we test the generalizability of the replier classifier       attacks. These attacks can originate either from within the
by training and testing the model across different campaigns.       targeted country or from other nation-states. Our findings
Similarly to the tweet classifier, we prepare six campaign       further suggest that influential individuals may serve as po-
datasets: five selected based on the highest number of IO        tential sensors for identifying IO campaigns.
repliers and one by aggregating the remaining campaigns.       To  detect  coordinated  reply  attacks, we  propose  a
In the diagonal of Table 7 we report F1 values when the      campaign-independent and general machine learning frame-


                                                   1594


===== PDF p.10 =====
that offer similar reply functionalities, including Facebook,
                                                             Threads, Mastodon, and Bluesky. However, the lack of IO
                                                                   datasets prevents us from evaluating our framework on these
                                                                 platforms.
                                                     Our study has potential impacts on platform integrity and
                                                                public dialogue. First, it reveals that what looks like public
                                                                  reactions may in fact be efforts to manipulate a target and
                                                                 other participants of a genuine conversation. For instance,
                                                                      politicians may be posting on social media to solicit pub-
                           

## Figure 1

tudy of coordinated reply attacks, we use 43
different state-sponsored IO datasets released by the Twit-
ter Moderation Research Consortium from October 2018 to
December 2021.2 These datasets are archives of suspended
accounts that Twitter claims to have been involved in foreign
influence operations. Along with the account metadata, the
datasets provide all the tweets generated by the accounts.
  Since according to Twitter the campaigns in these datasets
are coordinated by a single entity, they provide us with
ground truth for our study. Indeed,  if we observe mass
replies to a single target from multiple accounts labeled by
Twitter as coordinated, we can establish that the coordinated      Figure 1: Data collection for the classifiers. The dashed line
reply attack tactic has been used.                                separated the last IO reply and the first successive tweet by
                                                                 the target.
Target Dataset
First, we merge the datasets of all the IOs and keep all the      Classification Dataset
replies by IO accounts to tweets by non-IO accounts. We
                                                    To identify tweets targeted by coordinated replies (RQ2) andrefer to the latter accounts as targets and to the replies by
                                                             accounts that participate in such activity (RQ3), we considerIO accounts as IO replies. There are in total 17,873,714 IO
                                                                   targeted tweets as our positive examples. For correspondingreplies from 44,425 IO accounts targeting 15,256,547 tweets
                                                                negative examples, we collect control tweets posted by theby 1,763,084 distinct targets. From this data, we extract
                                                    same t

## Figure 5

ification
(median 31 vs. 22 for control tweets). On the other hand,       label. We tune the threshold to maximize the mean F1 across
control tweets receive slightly more retweets (median 84       folds. In the following, we focus on Random Forest (with
vs. 75 for IO-targeted tweets, Fig. 5b) and more likes (me-     100 estimator trees), which yields the best scores overall.
dian 420 vs. 250, Fig. 5c). This suggests that organic en-       To study the contributions of different features, we fol-
gagement generated more positive interactions and shar-      lowed two approaches. First, we trained and tested Random


                                                   1590


===== PDF p.6 =====
Figure 5: Engagement received by targeted and control tweets. (A) Replies, (B) retweets, and (C) likes. The distributions are
significantly different in all cases according to Kolmogorov-Smirnov tests (p < 10−6).

                              Classifier               Prec.         Rec.        F1      AUC
                             Logistic Regression   0.65 ± 0.00   0.86 ± 0.00   0.74 ± 0.00   0.80 ± 0.00
                     Random Forest       0.73 ± 0.00   0.87 ± 0.00   0.80 ± 0.00   0.88 ± 0.00
                        AdaBoost            0.64 ± 0.00   0.89 ± 0.00   0.74 ± 0.00   0.81 ± 0.00
                           Decision Tree        0.52 ± 0.01   0.95 ± 0.02   0.66 ± 0.00   0.69 ± 0.00
                         Naive Bayes          0.49 ± 0.00   1.00 ± 0.00   0.66 ± 0.00   0.68 ± 0.00

Table 2: Results of different algorithms in the tweet classification task. We present standard errors rounded to the second decimal
point.


      Features set         Prec.   Rec.   F1  AUC
     reply count       0.5    0.99   0.67   0.59
     retweet count    0.49    1     0.66   0.54
     like count        0.49    1     0.66   0.52
      Engagement         0.69    0.86   0.77   0.84
        Ent

## Figure 6

   F1  AUC
     reply count       0.5    0.99   0.67   0.59
     retweet count    0.49    1     0.66   0.54
     like count        0.49    1     0.66   0.52
      Engagement         0.69    0.86   0.77   0.84
        Entities              0.52    0.95   0.67   0.65
      Delay               0.51    0.96   0.67   0.66
       Similarity            0.54    0.96   0.69   0.68
       All features          0.73    0.87   0.80   0.88

Table 3: Contributions of different tweet-level features and
reply-level feature sets to the Random Forest tweet classifier.
The last row (using all features) corresponds to the results in
Table 2.


Forest on individual tweet-level features and reply-level fea-      Figure 6: Permutation feature importance for tweet classi-
ture sets. The results using 10-fold cross-validation are given         fier. We report the median (orange line), 50% confidence in-
in Table 3. Second, we performed a permutation feature im-       terval (box), and 99.3% confidence interval (whiskers) of the
portance test, which measures the importance of features by      drop in F1 score when each feature/attribute set is shuffled.
computing the loss in accuracy when the values of those fea-     Boxes with the same color indicate attributes in the same
tures are shuffled (permuted). To simplify the analysis, for       feature set. Larger values indicate higher importance.
each reply-level attribute we shuffled all the corresponding
features rather than each feature individually. For example,
for the like count engagement attribute, we shuffled all
12 summary statistics features at once. We repeated this test        ter users; instead, they primarily boosted retweet and reply
10 times and recorded the drop in mean F1 score from 10-      counts for other IO accounts to artificially amplify Vucic
fold cross-validation for each iteration. The distribution of      and his allies on Tw

## Figure 7

                                                          Other        0.62   0.59   0.63   0.56      0.52     0 .74

                                                             Table 4: F1 scores obtained from same-campaign (diago-
                                                                 nal entries, in bold) and cross-campaign evaluations of the
                                                              tweet classifier. RS=Serbia, SA=Saudi Arabia, TR=Turkey,
                                                     EG=Egypt. SA/EG/AE = Saudi Arabia/Egypt/Arab Emi-
                                                                       rates is a campaign involving three countries.

Figure 7: Scores of tweet classifiers based on different
thresholds for the number of IO replies received by targeted                                                               values are obtained when the model trained on all data from
tweets.                                                       one campaign (optimized to maximize F1) is tested on other
                                                           campaigns. As expected, the models perform better when
                                                                   trained and tested on the same campaign. However, models
whether tweet-level engagement features would provide suf-      can generalize, with F1 drops that depend on the specific
ficient signals to discriminate between targeted and control      campaigns. This suggests that at least some commonalities
tweets. However, Table 3 indicates that tweet-level reply,       exist across coordinated reply campaigns.
like, and retweet counts do not provide very informative sig-
nals for tweet classification. To further explore this question,           RQ3: Replier Classification
let us measure the correlation between tweet-level features
(reply count, retweet count, an

## Figure 9

asets, as in the original tweet classification setup. Finally,       Each replier may be involved in one or more replies to
we evaluate the models on test data from each dataset. In the      multiple targeted tweets. Therefore, we create a number
diagonal of Table 4 we report F1 values when the model       of features that summarize the characteristics of the set of
trained on one campaign is tested on the same campaign       replies generated by each replier, including replies to multi-
(mean across 10-fold cross-validation). The off-diagonal F1       ple targeted tweets. These features are based on eight reply


                                                   1592


===== PDF p.8 =====
Figure 9: Permutation feature importance for replier clas-
                                                                                     sifier. We report the median (orange line), 50% confidence
                                                                      interval (box), and 99.3% confidence interval (whiskers) of
                                                                 the drop in F1 score when each feature/attribute is shuffled.
                                                      Boxes with the same color indicate attributes in the same
                                                                   feature set. Larger values indicate higher importance.

Figure 8: Differences between complementary cumulative
distributions of IO and normal replier metadata: (A) age,
(B) following count, (C) follower count, and (D) activ-      balance leads to poor classification, which can be addressed
ity, as measured by the sum of the numbers of original       in two ways. First, we downsampled the normal repliers by
tweets, replies, quotes, and retweets. The distributions are       creating 10 different balanced datasets. Each includes all the
significantly different in al

## Figure 10

et          Prec.   Rec.   F1  AUC
    activity rate     0.60    0.63   0.61   0.65
    following rate    0.54    0.52   0.53   0.56
    follower rate     0.55    0.51   0.53   0.56
    age                  0.58    0.66   0.61   0.66
     Delay                 0.57    0.60   0.58   0.62
     Engagement           0.57    0.57   0.53   0.63
       Entities               0.63    0.50   0.53   0.63
       Similarity             0.85    0.84   0.84   0.92
      All features           0.93    0.92   0.92   0.97

Table 6: Contributions of different profile features and reply-
level feature sets to the Random Forest replier classifier. The                                                             Figure 10: (A) Distributions of cosine similarity attributes
last row corresponds to the results in Table 5 (top).                                                                     for replies by IO and normal repliers. (B) Similarity distri-
                                                                butions for normal repliers (blue, same as in panel (A)) and
                                                                 the 10 different samples (different colored outlines).
test. Both analyses consistently shows that the similarity
among replies is the most important attribute. To help in-
terpret this finding, Fig. 10(A) compares the distributions of                                                     model trained on one campaign is tested on the same cam-
similarity attributes for replies by IO versus normal repliers.                                                            paign (mean across 10-fold cross-validation and 10 different
Replies by IO repliers are more similar to other replies to the                                                            balanced datasets). The off-diagonal F1 values are obtained
same tweets, compared to those by normal repliers. This is    

## Figure 11

iticians may be posting on social media to solicit pub-
                                                                                lic opinions. Coordinated replies may skew their perception
                                                                of public sentiment (Stewart et al. 2019). Such replies can
                                                                     further distort genuine discourse if portrayed by the me-
                                                                 dia as reflective of public opinion. Secondly, coordinated
                                                                      replies enable malicious actors to maximize the public ex-
Figure 11: Replier classification scores for different data im-      posure of their posts by exploiting the popularity of their
balance ratios.                                                          targets, thereby amplifying their influence. This pollutes on-
                                                                       line dialogues with spam, influence campaigns, and divisive
                                 Test                          messages that harass the targeted individuals or provoke the     Train
          SA   RS   TR   EG  HN   Other             public. Such behavior may also alienate the targets and pre-
    SA      0.96   0.79   0.86   0.86   0.55    0.90            vent them from sharing their opinion on social media. For all
    RS      0.53   0.89   0.76   0.53   0.48    0.49                                                                 these reasons, platforms should protect the targets from co-
    TR      0.90   0.91   0.92   0.84   0.84    0.85
                                                               ordinated reply attacks. The research community may use    EG     0.92   0.90   0.88   0.92   0.74    0.90
                                       

## AUC

vents (Woolley and Howard 2018).
  We propose two supervised machine-learning models, one to          IOs can be state-sponsored, and originate domestically or
   classify tweets to determine whether they are targeted by a re-          in a foreign state (Bradshaw and Howard 2017). A prime
   ply attack, and one to classify accounts that reply to a targeted                                                       example of foreign-initiated campaign was the effort to in-
   tweet to determine whether they are part of a coordinated at-
                                                                       terfere in the 2016 US Presidential Election by the Rus-
   tack. The classifiers achieve AUC scores of 0.88 and 0.97,
                                                                  sian Internet Research Agency (IRA) (Senate Select Com-   respectively. These results indicate that accounts involved in
   reply attacks can be detected, and the targeted accounts them-         mittee on Intelligence 2019). Reports on IOs from differ-
   selves can serve as sensors for influence operation detection.         ent countries like China, Brazil, and Nigeria show that such
                                                        campaigns have emerged as a global threat (Bradshaw and
                                                  Howard 2017; Woolley and Howard 2018; Bush 2020).
                Introduction                                                               Here, we focus on coordinated reply attacks, where a
Social media platforms are the primary environments in      group of accounts work together to target specific individ-
which civic engagement takes place. They play an impor-       uals or entities by flooding their posts with replies. This can
tant role in the exchange of ideas, discussion of political      be done to overwhelm the target, push a particular na

## F1

ms other than Twitter.
                                         We compare different machine learning models: Logistic
Classifier Features                                          Regression, Random Forest, AdaBoost, Decision Tree, and
The tweet  classifier leverages several features extracted      Naive Bayes. Prior to training, we standardize the input fea-
from tweets and from the replies they receive. Let us first       tures via z-scores. We conduct 10-fold cross-validation to
focus on tweet-level features, specifically tweet engage-       mitigate over-fitting of the training data and report on the
ment. We find a few key differences between the engage-     mean precision, recall, and F1 values across folds along with
ment metrics of IO-targeted vs. control tweets. As illus-    AUC in Table 2. Precision, recall, and F1 depend on a thresh-
trated in Fig. 5a, IO-targeted tweets receive more replies      old to transform the model score into a binary classification
(median 31 vs. 22 for control tweets). On the other hand,       label. We tune the threshold to maximize the mean F1 across
control tweets receive slightly more retweets (median 84       folds. In the following, we focus on Random Forest (with
vs. 75 for IO-targeted tweets, Fig. 5b) and more likes (me-     100 estimator trees), which yields the best scores overall.
dian 420 vs. 250, Fig. 5c). This suggests that organic en-       To study the contributions of different features, we fol-
gagement generated more positive interactions and shar-      lowed two approaches. First, we trained and tested Random


                                                   1590


===== PDF p.6 =====
Figure 5: Engagement received by targeted and control tweets. (A) Replies, (B) retweets, and (C) likes. The distributions are
significantly different in all cases according to Kolmogorov-Smirnov tests (p < 10−6).

               

## 10-fold

t-level features, the classifier uses a total of 99 features.independent classifier for identifying IO-targeted tweets.
The same methodology could also be generalized to plat-
                                                       Resultsforms other than Twitter.
                                         We compare different machine learning models: Logistic
Classifier Features                                          Regression, Random Forest, AdaBoost, Decision Tree, and
The tweet  classifier leverages several features extracted      Naive Bayes. Prior to training, we standardize the input fea-
from tweets and from the replies they receive. Let us first       tures via z-scores. We conduct 10-fold cross-validation to
focus on tweet-level features, specifically tweet engage-       mitigate over-fitting of the training data and report on the
ment. We find a few key differences between the engage-     mean precision, recall, and F1 values across folds along with
ment metrics of IO-targeted vs. control tweets. As illus-    AUC in Table 2. Precision, recall, and F1 depend on a thresh-
trated in Fig. 5a, IO-targeted tweets receive more replies      old to transform the model score into a binary classification
(median 31 vs. 22 for control tweets). On the other hand,       label. We tune the threshold to maximize the mean F1 across
control tweets receive slightly more retweets (median 84       folds. In the following, we focus on Random Forest (with
vs. 75 for IO-targeted tweets, Fig. 5b) and more likes (me-     100 estimator trees), which yields the best scores overall.
dian 420 vs. 250, Fig. 5c). This suggests that organic en-       To study the contributions of different features, we fol-
gagement generated more positive interactions and shar-      lowed two approaches. First, we trained and tested Random


                                                   1590


===== PDF p.6

## control tweets

Dataset
replies by IO accounts to tweets by non-IO accounts. We
                                                    To identify tweets targeted by coordinated replies (RQ2) andrefer to the latter accounts as targets and to the replies by
                                                             accounts that participate in such activity (RQ3), we considerIO accounts as IO replies. There are in total 17,873,714 IO
                                                                   targeted tweets as our positive examples. For correspondingreplies from 44,425 IO accounts targeting 15,256,547 tweets
                                                                negative examples, we collect control tweets posted by theby 1,763,084 distinct targets. From this data, we extract
                                                    same targets after the last IO reply. This ensures that the15,016 targets and 96,041 tweets that received five or more
                                                               tweets in our control data did not receive any coordinateddirect replies from IO accounts. We assume these tweets
                                                                      replies by IO accounts. Fig. 1 illustrates the data collection.have been targeted by coordinated reply attacks, and we la-
                                                  As in the case of positive examples, we only retain con-bel them as targeted tweets. The threshold of five or more
                                                                             trol tweets with five or more replies. In addition, to avoidreplies is arbitrary; a robustness analysis shows that the de-
                                                                  bias due to the diverse activity of the targets, we collecttection of targeted tweets does not seem to be affected by
                                      

## five or more

                                                       accounts that participate in such activity (RQ3), we considerIO accounts as IO replies. There are in total 17,873,714 IO
                                                                   targeted tweets as our positive examples. For correspondingreplies from 44,425 IO accounts targeting 15,256,547 tweets
                                                                negative examples, we collect control tweets posted by theby 1,763,084 distinct targets. From this data, we extract
                                                    same targets after the last IO reply. This ensures that the15,016 targets and 96,041 tweets that received five or more
                                                               tweets in our control data did not receive any coordinateddirect replies from IO accounts. We assume these tweets
                                                                      replies by IO accounts. Fig. 1 illustrates the data collection.have been targeted by coordinated reply attacks, and we la-
                                                  As in the case of positive examples, we only retain con-bel them as targeted tweets. The threshold of five or more
                                                                             trol tweets with five or more replies. In addition, to avoidreplies is arbitrary; a robustness analysis shows that the de-
                                                                  bias due to the diverse activity of the targets, we collecttection of targeted tweets does not seem to be affected by
                                                       from each target as many control tweets as targeted tweets.this parameter, as discussed later (Fig. 7).
                                                                       Specifically, we select control tweets that were p

## Limitations

use    EG     0.92   0.90   0.88   0.92   0.74    0.90
                                                            our methodology to detect coordinated reply attacks and    HN     0.93   0.97   0.98   0.89   0.95    0.91
      Other   0.95   0.89   0.92   0.89   0.72    0.94            study the campaigns, perpetrators, and their potential effects
                                                     on the individuals. Our methodology may also guide the de-
Table 7: F1 scores obtained from same-campaign (diago-      velopment of countermeasures by social media platforms.
nal entries, in bold) and cross-campaign evaluations of the                                                              Limitations.  Our study has several limitations, some of
replier classifier. HN=Honduras; see Table 4 for other coun-                                                       which are mentioned below:
try codes.
                                                                             • We define control tweets as those posted by previously
                                                                      targeted authors. This might lead to some biases. Our
                                                                       collection of replies to these control tweets was limited
work consisting of a tweet classifier and a replier classifier.
                                                        by the collection time, which could in theory affect the
First, the tweet classifier identifies tweets that receive co-
                                                                         distributions of numbers and delays of replies. However,
ordinated replies, narrowing the scope for further investiga-
                                                      more than 99.8% of control tweets were posted at least
tion. This classifier is robust to variations in targeted tweet
         

## negative

p all the      Classification Dataset
replies by IO accounts to tweets by non-IO accounts. We
                                                    To identify tweets targeted by coordinated replies (RQ2) andrefer to the latter accounts as targets and to the replies by
                                                             accounts that participate in such activity (RQ3), we considerIO accounts as IO replies. There are in total 17,873,714 IO
                                                                   targeted tweets as our positive examples. For correspondingreplies from 44,425 IO accounts targeting 15,256,547 tweets
                                                                negative examples, we collect control tweets posted by theby 1,763,084 distinct targets. From this data, we extract
                                                    same targets after the last IO reply. This ensures that the15,016 targets and 96,041 tweets that received five or more
                                                               tweets in our control data did not receive any coordinateddirect replies from IO accounts. We assume these tweets
                                                                      replies by IO accounts. Fig. 1 illustrates the data collection.have been targeted by coordinated reply attacks, and we la-
                                                  As in the case of positive examples, we only retain con-bel them as targeted tweets. The threshold of five or more
                                                                             trol tweets with five or more replies. In addition, to avoidreplies is arbitrary; a robustness analysis shows that the de-
                                                                  bias due to the diverse activity of the targets, we collecttection of targeted tweets does not seem to be affected by
  