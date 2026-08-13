
# abstract_intro_rqs

Abstract                                 to distort trends and attract or distract the attention of main-
                                                            stream media (Ong and Caba˜nes 2018); use of inauthentic
  Coordinated reply attacks are a tactic observed in online in-                                                       and automated accounts to create the appearance of popu-
   fluence operations and other coordinated campaigns to sup-
                                                                            larity (Elmas 2023; Woolley and Howard 2018); deletion of   port or harass targeted individuals, or influence them or their
                                                               content violating terms of service to avoid detection by plat-   followers. Despite its potential to influence the public, past
   studies have yet to analyze or provide a methodology to de-        forms (Torres-Lugo et al. 2022); troll accounts (Zannettou
   tect this tactic. In this study, we characterize coordinated re-          et al. 2019a); the spread of disinformation and propaganda
   ply attacks in the context of influence operations on Twitter.        (Woolley and Howard 2018; Hristakieva et al. 2022); politi-
  Our analysis reveals that the primary targets of these attacks          cal memes (Rowett 2018; Zannettou et al. 2020; Ng, Moffitt,
   are influential people such as journalists, news media, state        and Carley 2022); and ‘kompromat’ strategies to influence
   officials, and politicians.                                              political events (Woolley and Howard 2018).
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
tant role in the exchange of ideas, discussion of political      be done to overwhelm the target, push a particular narrative,
agendas, and development of political identities thanks to       or generate engagement. Coordinated reply attacks are ac-
the ease with which one can access and consume informa-       tively employed in influence operations (Matthews and Go-
tion and build influence. However, social media platforms      erzen 2019; Bush 2020). Such a tactic has been used for
are also exploited by coordinated groups to purposefully dis-      harassment, as observed for example in a hate-speech cam-
tribute misleading information (Weedon, Nuland, and Sta-      paign against Mehreen Faruqi, Australia’s first female Mus-
mos 2017; Starbird, Arif, and Wilson 2019), artificially am-      lim senator (Thomas, Thompson, and Wanless 2020); ampli-
plify certain content (Elmas, Overdorf, and Aberer 2022), or       fication by inauthentic accounts (Weedon, Nuland, and Sta-
interfere with elections (Ferrara et al. 2020; Office of the Di-     mos 2017; Thomas et al. 2021); and spamming, trolling, and
rector of National Intelligence 2017; Neudert, Howard, and       incitement.
Kollanyi 2019). These types of social media exploitation are         In this paper, we provide a quantitative, large-scale study
referred to as information operations or influence operations       of coordinated reply attacks in influence operations reported
(IOs).                                                 by Twitter.1 We explore the targeting patterns of IO actors
  Influence operations are organized attempts to achieve a      employing this tactic and introduce methods to detect the
specific effect, such as manipulating public opinion, usually       targets of these attacks and the actors involved. We pose the
through coordinated tactics (Pamment and Smith 2022). IO      following research questions:
tactics include public relations via advertising or paid digi-
                                                                             • RQ1: Who are the targets of coordinated replies, and
tal influencers (Ong and Caba˜nes 2018); hashtag hijacking
                                                          what specific topics characterize the tweets that attract
   *Corresponding author. Email: potem@iu.edu
Copyright © 2025, Association for the Advancement of Artificial          1Although Twitter is now called X, we use the previous name
Intelligence (www.aaai.org). All rights reserved.                       because the data analyzed here predates the name change.


                                                   1586


===== PDF p.2 =====
such coordinated responses?                                Stanford Internet Observatory (2021) produced several re-
                                                                   ports describing influence campaigns and a range of tactics • RQ2: Among a set of tweets by potential targets, how
                                                          used by IO actors, including coordinated reply attacks (Bush   can we identify those that receive coordinated replies?
                                                              2020). While that work provides a qualitative description of
 • RQ3: Given a set of targeted tweets, how can we detect                                                                 the tactic, here we focus on methods to detect it.
   the accounts that participate in coordinated replies?
                                                              Coordinated reply attacks are also carried out by auto-
  We make the following contributions:                      mated accounts; social bots have been reported to target in-
 • We find that primary targets of coordinated reply attacks       fluential users in an attempt to direct their attention toward
   are mostly influential people such as journalists, news      fake news (Shao et al. 2018). Financial rather than political
   media, state officials, and politicians. Most of the targets       incentives may be the drivers of such tactics, as in the case of
   are attacked only once. The attacks for most of the tar-      cryptocurrency manipulation (Yang and Menczer 2024). The
   gets are sporadic and tend to focus on specific contexts,      methods presented here are context-independent and there-
   such as politics. The attackers can originate from within       fore could be applied to these kinds of campaigns.
   the target’s country or from foreign states.
 • We present a classifier model to identify tweets that are     Detection of Influence Operations
   targeted by coordinated replies. This model is general-
   izable to other contexts, as it does not use any features
                                              Many supervised machine-learning models have been pro-
   specific to IOs. It can also be developed into a tool for
                                                         posed in the literature to detect IO actors, especially IRA
   monitoring and safety.
                                                                              trolls on Twitter, using deceptive linguistic cues (Addawood
 • We present a second model that performs well on the task        et al. 2019) and behavioral and linguistic features (Im et al.
   of detecting accounts that are involved in reply attacks.        2020). Luceri, Giordano, and Ferrara (2020) propose an in-
                                                                verse reinforcement learning model for this task. Alizadeh
               Related Work                               et al. (2020) build a content-based classifier to detect tweets
                                                       from troll accounts in Russia, China, and Venezuela IO cam-Given the dearth of prior research on coordinated reply at-
                                                                 paigns. Work from Sharma et al. (2021) uses a generativetacks, we review the literature on IOs in general.
                                                     model to learn hidden group behavior to identify coordi-
                                                              nated accounts. Ezzeddine et al. (2023) present an LSTM-
Characterization of Influence Operations
                                                           based approach that identifies troll accounts based on behav-
Influence operations present novel challenges to content       ioral cues. Kong et al. (2023) propose an interval-censored
moderation on social media. A crucial initial step to ad-      transformer Hawkes architecture to identify IO operators. A
dress these challenges is to characterize how IO actors op-      supervised model by Saeed et al. (2022) leverages the fea-
erate: their tactics, motivations, and engagement patterns.       tures engineered from the interaction patterns of seed Rus-
Matthews and Goerzen (2019) present different trolling       sian troll accounts on Reddit to find other troll accounts.
techniques used in social media, from dogpiling to sock                                                     Our work is similar to the above-mentioned efforts in the
puppetry, along with interventions. Zannettou et al. (2019a)                                                            use of a supervised learning approach to identify coordi-
observe that Russian trolls displayed different behavior in                                                              nated accounts. However, we design features that leverage
the use of Twitter compared to random users. The same au-                                                                 the targeting behaviors of the IO actors, specifically focus-
thors also find that Russian trolls on Twitter and Reddit were                                                               ing on reply/comment engagements. Our method does not
pro-Trump, while Iranian trolls were anti-Trump (Zannet-                                                            use any IO-specific features or sentiment cues, therefore it
tou et al. 2019b). The images shared by Russian trolls ap-                                                          can be generalized to different social media platforms that
peared in many popular social networks as well as main-                                                          have similar engagement functionalities.
stream and alternative news outlets, and focused on Russia,
                                                                   Influence operations are one kind of co

# data_collection

===== PDF p.3 =====
Data Collection

For the present study of coordinated reply attacks, we use 43
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
                                                    same targets after the last IO reply. This ensures that the15,016 targets and 96,041 tweets that received five or more
                                                               tweets in our control data did not receive any coordinateddirect replies from IO accounts. We assume these tweets
                                                                      replies by IO accounts. Fig. 1 illustrates the data collection.have been targeted by coordinated reply attacks, and we la-
                                                  As in the case of positive examples, we only retain con-bel them as targeted tweets. The threshold of five or more
                                                                             trol tweets with five or more replies. In addition, to avoidreplies is arbitrary; a robustness analysis shows that the de-
                                                                  bias due to the diverse activity of the targets, we collecttection of targeted tweets does not seem to be affected by
                                                       from each target as many control tweets as targeted tweets.this parameter, as discussed later (Fig. 7).
                                                                       Specifically, we select control tweets that were posted im-
  The targeted tweets can still be publicly available at the
                                                             mediately after the last IO reply, subject to the five-reply
time of our analysis, allowing us to collect all of their replies.
                                                   minimum. In cases where we could not obtain as many con-
Some of these replies may have originated from non-IO
                                                                             trol tweets as targeted tweets, we ensure a balanced dataset
repliers, both before and after the IO accounts were taken
                                                     by keeping the most recent targeted tweets.
down by Twitter. We refer to these replies as normal replies
                                                                  Similar to the targeted tweets, we fetch all the replies to
and to their authors as normal repliers. Since we only have
                                                                 the control tweets and all replier metadata. The resulting
direct replies by IO accounts, we only consider direct replies
                                                                       classification dataset includes 3,866 targeted tweets and the
by normal repliers as well; replies to replies are discarded.
                                                    same number of control tweets by 1,507 targets. The drop
In addition to the metadata about the IO replies that are
                                                                     in the number of tweets compared to the target dataset is
present in the initial data, we query the /users/:id,
                                                       due to the various constraints outlined above: authors with
/search/all, and /tweets/?ids= endpoints of the
                                                                 deleted or suspended accounts, or with no original tweets af-Twitter API3 to collect metadata about the targets, the tar-
                                                                            ter the IO, were removed; only original tweets with at least
geted tweets, their normal replies, and the normal repliers.
                                                                         five replies were considered; and original (targeted or con-
We collected this information in April 2023.
                                                                             trol) tweets were removed due to balancing. There are in to-
  Among the 15,016 targets, 5,041 were suspended, 3,992                                                                                tal 881,918 and 323,378 repliers in the positive and negative
could not be found (possibly deleted accounts), and 5,983                                                            examples, respectively. These include IO and normal repli-
were alive at analysis time (2,031 verified and 3,952 non-                                                                           ers. While the full classification dataset is used for RQ2, for
verified accounts). Of the  total 96,041 targeted tweets,                                        RQ3 we only use the positive examples (targeted tweets):
43,048 could not be found, which means these tweets could                                                           7,670 IO repliers and 874,248 normal repliers.
have originated from deleted or suspended accounts; 18,808
had unauthorized access; and 34,185 were accessible. For                                              RQ1: Targets and Topics
our influence operation case studies (RQ1), we consider this
target dataset of 34,185 tweets by 5,983 targets.                  In this section, we present an exploratory analysis of the tar-
                                                                  gets of coordinated reply attacks and two case studies of spe-
   2IO datasets were available at transparency.x.com/en/reports/        cific campaigns where we can analyze the targets as well as
moderation-research until summer 2024. An archival version of       the topics of their targeted tweets and other tactics employed
the site is available at web.archive.org/web/20240829231920/https:       in the campaigns.
//transparency.x.com/en/reports/moderation-research.                   Exploratory analysis of target metadata (Fig. 2a) shows
    3developer.twitter.com/en/docs/twitter-api/                           that targets tend to have more followers (median 22,540)


                                                   1588


=

# rq1

===== PDF p.4 =====
Figure 3: Characterization of the Serbia campaign. Distribu-
                                                                     tions of (A) countries and (B) professions of the targets. BiH
                                               = Bosnia and Herzegovina, NA = Not Available (C) Word-
                                                                           shift graph comparing the most frequent words in targeted
                                                       and non-targeted tweets. The top bar represents the cumula-
                                                                         tive contribution of each type of word shift.
Figure 2: Complementary cumulative distribution functions
(CCDF) of statistics describing target accounts and their
tweets. (A) Numbers of followers and following (friends) of     we report the top 10 target professions/types and countries.
targets. (B) Number of targeted tweets per target. (C) Num-    We also inspected the targeted tweets to understand the con-
ber of coordinated replies received by each targeted tweet.       text of the attacks. In preprocessing, we used Google Trans-
(D) Time delay between targeted tweets and their coordi-        late to translate the targeted tweets into English and removed
nated replies.                                                   stop words and emojis.

                                                    Case Study: Serbia.  The majority of accounts targeted by
                                                                 the Serbia campaign, approximately 648, were from Serbiathan following (median 707). This suggests that targets can
                                                                                   itself, with the remaining coming from the Balkan regionbe influential people. Reply attacks tend to be selective
                                                                      (Fig. 3a). This suggests that the campaign focused its ef-(Fig. 2b): only a few tweets by each target were targeted
                                                                         forts on influencing public opinion within Serbia. Fig. 3b(median one). The median number of coordinated replies re-
                                                                   reveals that the coordinated reply attacks primarily targetedceived by targeted tweets was eight (Fig. 2c). Coordinated
                                                                      journalists (102), state officials (99), news media organi-replies tend to occur quickly after a targeted tweet, with a
                                                                  zations (76), and politicians (43). A wordshift graph (Gal-median delay of 3 hours (Fig. 2d). However, these distri-
                                                                lagher et al. 2021) highlighting the most prominent termsbutions are broad. For example, 54 of the targeted tweets
                                                                     in the targeted tweets (Fig. 3c) shows that the campaignreceived more than 1,000 replies.
                                                            focused on President Vucic, the Serbian Progressive Party
  The above statistics are merely descriptive, as we lack a
                                                          (SNS), the 2017 election, the “1 out of 5 Millions” protest,
reference model to interpret how targeted users differ from
                                                       and the Serbia-Kosovo diplomatic crisis. These findings are
the general population of Twitter users. To better understand
                                                                   consistent with analysis by Bush (2020), who reported that
what kinds of accounts were targeted, one of the authors
                                                                 the primary objective of IO actors involved in the Serbia
annotated some target profiles with the corresponding pro-
                                                       campaign was to rally support for President Alexander Vu-
fessions or organization types and country of origin. We
                                                                     cic and his party, the SNS. This was achieved by promoting
used manual annotation by checking each Twitter profile,
                                                                 the popularity and visibility of Vucic and the SNS through
description, the profession metadata indicated by the ‘brief-
                                                               retweeting their content and replying to other accounts with
case icon,’ and by searching Google for the accounts with
                                                                supportive messages. The IO accounts also targeted oppo-
more than a million followers. We grouped profession and
                                                              nent political parties with derisive tweets and attempted to
organization types into broad categories, such as state of-
                                                                      discredit them by flooding their posts with negative com-
ficials, news media, and politicians. Accounts with insuffi-
                                                             ments. This tactic aimed to create a public perception that
cient information were labeled ‘Not Available.’
                                                                 the opposition was unpopular.
  As the annotation process was time-consuming, we fo-
cused on two cases, namely two of the five campaigns with     Case Study: Egypt.   Fig. 4a shows that the majority of
the most targets: Serbia (the top campaign with 1,175 tar-      accounts targeted by the Egypt campaign were from mul-
gets) and Egypt (the fifth campaign with 372 targets). Ap-        tiple Middle East and North Africa countries, primarily
proximately 26% of the targeted accounts in the Serbia cam-      Saudi Arabia (74 targets), Egypt (39), UAE (36), Qatar
paign and 20% in the Egypt campaign did not have sufficient       (30), and Yemen (26). This suggests a potential interstate
information available. In the next subsections, for each case,       attack. News media organization (67), journalists (52), and


                                                   1589




# rq2

[NOT FOUND]

# rq3

[NOT FOUND]

# discussion_limitations

discussion of political      be done to overwhelm the target, push a particular narrative,
agendas, and development of political identities thanks to       or generate engagement. Coordinated reply attacks are ac-
the ease with which one can access and consume informa-       tively employed in influence operations (Matthews and Go-
tion and build influence. However, social media platforms      erzen 2019; Bush 2020). Such a tactic has been used for
are also exploited by coordinated groups to purposefully dis-      harassment, as observed for example in a hate-speech cam-
tribute misleading information (Weedon, Nuland, and Sta-      paign against Mehreen Faruqi, Australia’s first female Mus-
mos 2017; Starbird, Arif, and Wilson 2019), artificially am-      lim senator (Thomas, Thompson, and Wanless 2020); ampli-
plify certain content (Elmas, Overdorf, and Aberer 2022), or       fication by inauthentic accounts (Weedon, Nuland, and Sta-
interfere with elections (Ferrara et al. 2020; Office of the Di-     mos 2017; Thomas et al. 2021); and spamming, trolling, and
rector of National Intelligence 2017; Neudert, Howard, and       incitement.
Kollanyi 2019). These types of social media exploitation are         In this paper, we provide a quantitative, large-scale study
referred to as information operations or influence operations       of coordinated reply attacks in influence operations reported
(IOs).                                                 by Twitter.1 We explore the targeting patterns of IO actors
  Influence operations are organized attempts to achieve a      employing this tactic and introduce methods to detect the
specific effect, such as manipulating public opinion, usually       targets of these attacks and the actors involved. We pose the
through coordinated tactics (Pamment and Smith 2022). IO      following research questions:
tactics include public relations via advertising or paid digi-
                                                                             • RQ1: Who are the targets of coordinated replies, and
tal influencers (Ong and Caba˜nes 2018); hashtag hijacking
                                                          what specific topics characterize the tweets that attract
   *Corresponding author. Email: potem@iu.edu
Copyright © 2025, Association for the Advancement of Artificial          1Although Twitter is now called X, we use the previous name
Intelligence (www.aaai.org). All rights reserved.                       because the data analyzed here predates the name change.


                                                   1586


===== PDF p.2 =====
such coordinated responses?                                Stanford Internet Observatory (2021) produced several re-
                                                                   ports describing influence campaigns and a range of tactics • RQ2: Among a set of tweets by potential targets, how
                                                          used by IO actors, including coordinated reply attacks (Bush   can we identify those that receive coordinated replies?
                                                              2020). While that work provides a qualitative description of
 • RQ3: Given a set of targeted tweets, how can we detect                                                                 the tactic, here we focus on methods to detect it.
   the accounts that participate in coordinated replies?
                                                              Coordinated reply attacks are also carried out by auto-
  We make the following contributions:                      mated accounts; social bots have been reported to target in-
 • We find that primary targets of coordinated reply attacks       fluential users in an attempt to direct their attention toward
   are mostly influential people such as journalists, news      fake news (Shao et al. 2018). Financial rather than political
   media, state officials, and politicians. Most of the targets       incentives may be the drivers of such tactics, as in the case of
   are attacked only once. The attacks for most of the tar-      cryptocurrency manipulation (Yang and Menczer 2024). The
   gets are sporadic and tend to focus on specific contexts,      methods presented here are context-independent and there-
   such as politics. The attackers can originate from within       fore could be applied to these kinds of campaigns.
   the target’s country or from foreign states.
 • We present a classifier model to identify tweets that are     Detection of Influence Operations
   targeted by coordinated replies. This model is general-
   izable to other contexts, as it does not use any features
                                              Many supervised machine-learning models have been pro-
   specific to IOs. It can also be developed into a tool for
                                                         posed in the literature to detect IO actors, especially IRA
   monitoring and safety.
                                                                              trolls on Twitter, using deceptive linguistic cues (Addawood
 • We present a second model that performs well on the task        et al. 2019) and behavioral and linguistic features (Im et al.
   of detecting accounts that are involved in reply attacks.        2020). Luceri, Giordano, and Ferrara (2020) propose an in-
                                                                verse reinforcement learning model for this task. Alizadeh
               Related Work                               et al. (2020) build a content-based classifier to detect tweets
                                                       from troll accounts in Russia, China, and Venezuela IO cam-Given the dearth of prior research on coordinated reply at-
                                                                 paigns. Work from Sharma et al. (2021) uses a generativetacks, we review the literature on IOs in general.
                                                     model to learn hidden group behavior to identify coordi-
                                                              nated accounts. Ezzeddine et al. (2023) present an LSTM-
Characterization of Influence Operations
                                                           based approach that identifies troll accounts based on behav-
Influence operations present novel challenges to content       ioral cues. Kong et al. (2023) propose an interval-censored
moderation on social media. A crucial initial step to ad-      transformer Hawkes architecture to identify IO operators. A
dress these challenges is to characterize how IO actors op-      supervised model by Saeed et al. (2022) leverages the fea-
erate: their tactics, motivations, and engagement patterns.       tures engineered from the interaction patterns of seed Rus-
Matthews and Goerzen (2019) present different trolling       sian troll accounts on Reddit to find other troll accounts.
techniques used in social media, from dogpiling to sock                                                     Our work is similar to the above-mentioned efforts in the
puppetry, along with interventions. Zannettou et al. (2019a)                                                            use of a supervised learning approach to identify coordi-
observe that Russian trolls displayed different behavior in                                                              nated accounts. However, we design features that leverage
the use of Twitter compared to random users. The same au-                                                                 the targeting behaviors of the IO actors, specifically focus-
thors also find that Russian trolls on Twitter and Reddit were                                                               ing on reply/comment engagements. Our method does not
pro-Trump, while Iranian trolls were anti-Trump (Zannet-                                                            use any IO-specific features or sentiment cues, therefore it
tou et al. 2019b). The images shared by Russian trolls ap-                                                          can be generalized to different social media platforms that
peared in many popular social networks as well as main-                                                          have similar engagement functionalities.
stream and alternative news outlets, and focused on Russia,
                                                                   Influence operations are one kind of coordinated cam-Ukraine, and the USA (Zannettou et al. 2020). Dutt, Deb,
                                                                 paign. A body of work has explored unsupervised methodsand Ferrara (2018) analyze the advertisements purchased by
                                                                     to detect coordinated behaviors in general. Pacheco et al.IRA accounts on Facebook and identify their changing cam-
                                                            (2021) introduced a network-based framework for coordi-paign targets over time by performing clustering and seman-
                                                                nation detection. As campaigns use more than one tactictic analysis. Stewart, Arif, and Starbird (2018) investigate
                                                                          at a time, Uyheng, Cruickshank, and Carley (2022) presentthe behavior of Russian trolls around the #BlackLivesMat-
                                                            a multi-view modularity clustering method. A Bayesianter movement and find that the trolls infiltrated both right-
                                                     model by Hudson Smith, Ehrett, and Warren (2024) lever-and left-leaning political communities to participate in both
                                                            ages similarities in narrative and account characteristics.sides of the discussion. Farkas and Bastos (2018) manu-
                                                        Nwala, Flammini, and Menczer (2023) propose a languageally annotate IRA-linked tweets into 19 different categories
                                                       framework that represents user actions and content as se-to study whether IRA operations are consistent with clas-
                                                          quences of symbols to find coordinated accounts.sic propaganda models. Merhi, Rajtmajer, and Lee (2023)
find that the accounts involved in an IO in Turkey were re-        Unlike the above methods, we do not cluster accounts
silient to large-scale shutdown. Elmas, Overdorf, and Aberer      based on similar behaviors. We classify individual posts
(2023) discover that IO actors and other adversarial accounts      based on aggregate features of their replies, and individual
often change their names and assume new identities. The      accounts based on their metadata and reply activity.


                                                   1587


===== PDF p.3 =====
Data Collection

For the present study of coordinated reply attacks, we use 43
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
reply attack tactic has been used.                       

# ethics

Ethics Checklist
stanfordio/publications. Accessed: 2025-04-08.
                                                                       1. For most authors...
Starbird, K.; Arif, A.; and Wilson, T. 2019. Disinformation
as Collaborative Work: Surfacing the Participatory Nature of         (a) Would answering this research question advance sci-
Strategic Information Operations. Proc. ACM Hum. Com-           ence without violating social contracts, such as violat-
put. Interact.                                                        ing privacy norms, perpetuating unfair profiling, exac-
                                                                       erbating the socio-economic divide, or implying disre-
Stewart, A.; Mosleh, M.; Diakonova, M.; Arechar, A.; Rand,
                                                                      spect to societies or cultures? Yes
D.; and Plotkin, J. 2019. Information gerrymandering and
undemocratic decisions. Nature, 573(7772): 117–121.              (b) Do your main claims in the abstract and introduction
                                                                      accurately reflect the paper’s contributions and scope?
Stewart, L. G.; Arif, A.; and Starbird, K. 2018. Examining
                                                            Yes
Trolls and Polarization with a Retweet Network.  In Proc.
                                                                          (c) Do you clarify how the proposed methodological ap-ACM WSDM Workshop on Misinformation and Misbehavior
                                                                proach is appropriate for the claims made? YesMining on the Web (MIS2). https://api.semanticscholar.org/
CorpusID:44033303.                                                (d) Do you clarify what are possible artifacts in the data
                                                                     used, given population-specific distributions? YesThomas, E.; Thompson, N.; and Wanless, A. 2020.  The
Challenges of Countering Influence Operations.  Techni-         (e) Did you describe the limitations of your work? Yes
cal report, Carnegie Endowment for Intl. Peace. Accessed:           (f) Did you discuss any potential negative societal im-
2025-04-08.                                                          pacts of your work? NA


                                                   1597


===== PDF p.13 =====
(g) Did you discuss any potential misuse of your work?         (a)  If your work uses existing assets, did you cite the cre-
   NA                                                               ators? Yes.
  (h) Did you describe steps taken to prevent or mitigate po-         (b) Did you mention the license of the assets? NA
      tential negative outcomes of the research, such as data         (c) Did you include any new assets in the supplemental
     and model documentation, data anonymization, re-            material or as a URL? Yes. We provide link to data
     sponsible release, access control, and the reproducibil-          and code as URL.
      ity of findings? Yes                                                                      (d) Did you discuss whether and how consent was ob-
   (i) Have you read the ethics review guidelines and en-            tained from people whose data you’re using/curating?
     sured that your paper conforms to them? Yes                    Yes; this is addressed by IRB exemption.
2. Additionally, if your study involves hypotheses testing...          (e) Did you discuss whether the data you are using/cu-
                                                                          rating contains personally identifiable information or
  (a) Did you clearly state the assumptions underlying all                                                                       offensive content? Yes. The Twitter profiles are public
      theoretical results? NA                                                                      information.
  (b) Have you provided justifications for all theoretical re-                                                                                  (f)  If you are curating or releasing new datasets, did you
      sults? NA                                                                      discuss how you intend to make your datasets FAIR?
  (c) Did you discuss competing hypotheses or theories that            Yes. The link to data is included in the paper so that
     might challenge or complement your theoretical re-          anyone can access it, including the details of the meta-
      sults? NA                                                       data in the Datasheet to make  it interoperable and
  (d) Have you considered alternative mechanisms or expla-             reusable.
     nations that might account for the same outcomes ob-         (g)  If you are curating or releasing new datasets, did you
     served in your study? NA                                         create a Datasheet for the Dataset? The Datasheet is
  (e) Did you address potential biases or limitations in your             available at doi.org/10.5281/zenodo.13896308
      theoretical framework? NA                                    6. Additionally, if you used crowdsourcing or conducted
  (f) Have you related your theoretical results to the existing          research with human subjects, without compromising
      literature in social science? NA                              anonymity...
  (g) Did you discuss the implications of your theoretical         (a) Did you include the full text of instructions given to
      results for policy, practice, or further research in the             participants and screenshots? NA
      social science domain? Answer                                                                      (b) Did you describe any potential participant risks, with
3. Additionally, if you are including theoretical proofs...              mentions of Institutional Review Board (IRB) ap-
                                                                     provals? NA
  (a) Did you state the full set of assumptions of all theoret-
                                                                          (c) Did you include the estimated hourly wage paid to      ical results? NA
                                                                          participants and the total amount spent on participant
  (b) Did you include complete proofs of all theoretical re-                                                               compensation? NA
      sults? NA
                                                                      (d) Did you discuss how data is stored, shared, and dei-
4. Additionally, if you ran machine learning experiments...             dentified? NA
  (a) Did you include  the code,  data, and  instructions
     needed to reproduce the main experimental results (ei-                     Ethical Impact
      ther in the supplemental material or as a URL)? Yes        This  study  has been  granted exemption from  Institu-
  (b) Did you specify all the training details (e.g., data splits,       tional Review Board review (Indiana University proto-
     hyperparameters, how they were chosen)? Yes              cols 12410 and 1102004860). Our  results can be  re-
                                                         produced using code available at github.com/osome-iu/io-  (c) Did you report error bars (e.g., with respect to the ran-
                                                                 coordinated-replies and data available at doi.org/10.5281/    dom seed after running experiments multiple times)?
                                                          zenodo.13896308. The collection and release of the dataset     Yes. Our experiments report averages across 10-fold
                                                     comply with the Twitter platform’s terms of service. To mit-      cross-validation as well as standard errors.
                                                                     igate the potential ethical risks of analyzing human subjects,
  (d) Did you include the total amount of computation and                                              we only rely on the data of public Twitter accounts do not
      the type of resources used (e.g., type of GPUs, internal                                                               include any raw data. We only manually inspect the profiles
      cluster, or cloud provider)? Yes                                                                of the targets of the attacks, who are public figures and con-
  (e) Do you justify how the proposed evaluation is suffi-        stitute the vulnerable group our study aims to protect. We
      cient and appropriate to the claims made? Yes              provide our annotation data about these profiles for repro-
  (f) Do you discuss what is “the cost” of misclassification       ducibility. Our classification models do not use any person-
     and fault (in)tolerance? Yes. We recommend manual       ally identifiable information. We only report aggregated re-
     inspection to complement our classifiers.                       sults.

5. Additionally, if you are using existing assets (e.g., code,
   data, models) or curating/releasing new assets, without
  compromising anonymity...


                                                   1598
