Detection and Characterization of Coordinated Online Behavior: A Survey

LORENZO MANNOCCI, University of Pisa, Italy and Institute for Informatics and Telematics, National Research
Council (IIT-CNR), Italy

MICHELE MAZZA, Institute for Informatics and Telematics, National Research Council (IIT-CNR), Italy
ANNA MONREALE, University of Pisa, Italy
MAURIZIO TESCONI, Institute for Informatics and Telematics, National Research Council (IIT-CNR), Italy
STEFANO CRESCI, Institute for Informatics and Telematics, National Research Council (IIT-CNR), Italy

Coordination is a fundamental aspect of life. The advent of social media has made it integral also to online human interactions,

such as those that characterize thriving online communities and social movements. At the same time, coordination is also core to

effective disinformation, manipulation, and hate campaigns. This survey collects, categorizes, and critically discusses the body of

work produced as a result of the growing interest on coordinated online behavior. We reconcile industry and academic definitions,

propose a comprehensive framework to study coordinated online behavior, and review and critically discuss the existing detection and

characterization methods. Our analysis identifies open challenges and promising directions of research, serving as a guide for scholars,

practitioners, and policymakers in understanding and addressing the complexities inherent to online coordination.

ACM Reference Format:
Lorenzo Mannocci, Michele Mazza, Anna Monreale, Maurizio Tesconi, and Stefano Cresci. 2026. Detection and Characterization of

Coordinated Online Behavior: A Survey. 1, 1 (April 2026), 39 pages. https://doi.org/10.1145/nnnnnnn.nnnnnnn

1 INTRODUCTION

Coordination, the process in which multiple connected actors are involved to pursue goals [78], is a fundamental aspect

in the existence of various life forms, including human beings. From flocks of birds engaging in synchronized flight to

insects working together in colonies, coordination enhances efficiency, safety, and resource utilization [77]. The ability

to coordinate actions boosts the chances to overcome environmental challenges, fostering not only individual survival

but also the resilience and success of entire communities. For these reasons, human coordination has been extensively

scrutinized in multiple scientific disciplines interested in the dynamics of our offline interactions [119, 133].

With the advent of social media platforms, coordination has also become a fundamental component of online interac-
tions. Social media users are now provided with a broad array of tools to coordinate with each other, such as hashtags

that enable them to collectively discuss specific topics [129]. Online platforms have become a suitable environment for

organizing social and political movements, giving rise to phenomena such as online activism [94, 100], boycotts [68],

protests [73, 126], and coordinated crisis communication by democratic institutions during emergencies [151]. The 2011

Arab Springs are a notable example, being largely organized through social media [126]. At the same time however,

scholars found evidence of online coordination being exploited by nefarious actors for all sorts of malicious purposes.

For instance, disinformation campaigns often leverage actors that coordinate their actions to maximize the outreach of

Authors’ addresses: Lorenzo Mannocci, University of Pisa, Italy and Institute for Informatics and Telematics, National Research Council (IIT-CNR), Italy,
lorenzo.mannocci@di.unipi.it; Michele Mazza, Institute for Informatics and Telematics, National Research Council (IIT-CNR), Italy, michele.mazza@iit.
cnr.it; Anna Monreale, University of Pisa, Italy, anna.monreale@unipi.it; Maurizio Tesconi, Institute for Informatics and Telematics, National Research
Council (IIT-CNR), Italy, maurizio.tesconi@iit.cnr.it; Stefano Cresci, Institute for Informatics and Telematics, National Research Council (IIT-CNR), Italy,
stefano.cresci@iit.cnr.it.

2026. Manuscript submitted to ACM

Manuscript submitted to ACM

1

6
2
0
2

r
p
A
0
1

]
I
S
.
s
c
[

2
v
7
5
2
1
0
.
8
0
4
2
:
v
i
X
r
a

2

Mannocci et al.

Fig. 1. Coordination is a fundamental aspect of online human interactions
and the study of coordinated online behavior can complement the analyses
of many other online phenomena.

Fig. 2. Number of articles published yearly on co-
ordinated online behavior.

their false narratives [59, 125, 138]. Similarly, coordination is employed within information operations [18, 99, 138],

coordinated social media manipulation [87, 130], and astroturfing, which involves creating the false appearance of

grassroots support for a target cause, product, or person [59]. Also, social bots (automated accounts [23, 93]) and trolls

(human-driven accounts engaging in collective disruptive or deceptive behavior [153]) exploit coordination to amplify

messages, manipulate trends, or spread disinformation [69, 82, 153]. Coordination both results from and contributes

to echo chambers and online polarization [139]. Figure 1 illustrates its multifaceted nature, underlying diverse and

interconnected phenomena in online social media.

Recognizing the profound impact of online coordination on social media as well as its consequences on the offline

world, both researchers [100, 102, 138, 146] and industry stakeholders [35] devoted a great deal of efforts to study its

dynamics and to develop effective strategies to detect and mitigate its malicious instances. Research sped up significantly
after 2018, when Facebook introduced the concept of coordinated inauthentic behavior (CIB) [35], marking a milestone
in the development of the field. As shown in Figure 2, subsequent years saw a surge of interest on the subject, testified

by the steadily growing number of published papers, with only a minor fluctuation in 2023. This survey is motivated by

this thriving interest on online coordination, which resulted in the availability of a large body of work. However, while

Facebook’s interest towards online coordination was constrained to inauthentic behaviors as a response to the threat of

orchestrated campaigns [35], here we embrace a more holistic and unbiased view by focusing on the broader concept of
coordinated behavior. This inclusive approach allows for the analysis of a broader spectrum of works, including those
focused on legitimate collective actions, offering a more comprehensive understanding of the coordination dynamics

that shape digital spaces and fostering nuanced perspectives that go beyond mere threat detection. In spite of the many

efforts, the existing literature still reflects the complexities and ambiguities surrounding this phenomenon. Among them

is the limited agreement on a shared definition, which also hinders operationalization. Complexity also emerges from the

diversity of methods proposed for detecting and characterizing coordinated online behavior, which impairs comparisons

between different works and limits the generalizability of findings. Finally, the use of the same coordination technique

by actors with disparate motivations poses challenges to estimating the impact and effects of online coordination.

This survey offers an extensive overview and critical analysis on coordinated behavior, starting from reconciling

existing definitions from industry and academia, and proposing a general and comprehensive conceptual framework.

We systematically analyze and categorize existing approaches for detecting and characterizing online coordination,

elucidating open challenges and delineating promising directions for future research. Our work provides a roadmap for

scholars, practitioners, and policymakers navigating the evolving complexities of coordinated online behavior.

Significance. Comprehensively modeling coordinated online behavior has far-reaching implications. On a theoretical
level, it reconciles diverse definitions and provides a foundational framework for future research. On a technical level,

Manuscript submitted to ACM

Detection and Characterization of Coordinated Online Behavior: A Survey

3

Identification of studies
via databases and registers

Records identified from:
Scopus (𝑛 = 353)
Google Scholar (𝑛 = 1000)

Identification of studies
via other methods

Additional studies identified through
backward reference searching

(𝑛 = 38)

Records removed before screening:

Duplicate records removed (𝑛 = 147)

Records screened (𝑛 = 1206)

Full-text articles excluded (𝑛 = 1123):

Not in English (𝑛 = 4)
Out of scope (𝑛 = 1118)

Studies included in review (𝑛 = 122)

n
o
i
t
a
c
fi
i
t
n
e
d
I

g
n
i
n
e
e
r
c
S

d
e
d
u
l
c
n
I

Fig. 3. PRISMA diagram summarizing the stages used to construct the
final corpus of studies considered in this survey.

Fig. 4. Distribution of papers in the dataset according
to the disciplinary area of the publication venue, high-
lighting the predominance of Computer Science venues
alongside contributions from Social Sciences and inter-
disciplinary outlets.

it critically evaluates and categorizes existing detection and characterization methods, informing the development

of the next generation of robust and adaptive tools for studying both malicious and neutral instances of coordinated

behavior. By shedding light on online coordination—a fundamental dynamic of computer-mediated human behavior—

this survey contributes to safeguarding online integrity and to fostering positive interactions in digital spaces. It offers

valuable insights for shaping future methodologies, platforms, and policies, and it also contributes to enriching the

interdisciplinary research occurring at the intersection between computer science and social dynamics.

Scope. Coordinated online behavior is orthogonal to many of the research topics tackled in fields such as Web and
social media analysis, online social networks security, as well as social computing and computational social science,

as shown in Figure 1. Therefore, a large number of works from these scientific communities implicitly or explicitly

deal with online coordination. While coordinated behavior can manifest across a wide range of online environments

(e.g., e-commerce platforms, review systems, or online marketplaces [105]), this survey focuses primarily on online

social media platforms, where coordination has been most extensively studied and where interactions are more readily

observable at scale. Accordingly, this survey is constrained to those papers that address online coordination explicitly

within this context and that provide relevant contributions to its detection, characterization, or understanding.

Literature search and selection. A systematic literature search was conducted to identify studies addressing coordinated
behavior on social media platforms using two databases: Scopus and Google Scholar. The Scopus query targeted papers

containing the following search strings:

(“coordinated behavior” OR “coordinated behaviour” OR “coordinated activity” OR “coordinated campaign” OR “coor-

dinated inauthentic behavior” OR “coordinated inauthentic behaviour” OR “inauthentic behavior” OR “inauthentic

behaviour” OR “information operation*”) AND (“social media” OR online OR twitter OR facebook OR instagram OR

reddit OR telegram OR tiktok OR youtube)

The search was restricted to publications between 2014 and 2026, written in English, and within relevant subject

areas (Computer Science, Social Sciences, Decision Sciences, Engineering, and Multidisciplinary). This query returned

353 records. To broaden coverage, a complementary search was performed on Google Scholar using similar search

strings, collecting the first 1000 results returned by the platform. This choice aims to maximize coverage while reducing

potential bias introduced by the platform’s ranking mechanism. After merging the two sources, 147 duplicate records

were removed, leaving 1206 records for screening. Titles and abstracts were manually reviewed, leading to the exclusion

Manuscript submitted to ACM

4

Mannocci et al.

of 4 non-English papers and 1118 records that were out of scope (e.g., biological coordination, general sociological

coordination, or studies on bot detection or information operations not explicitly addressing coordinated behavior).

Most of these discarded records derived from the search on Google Scholar, likely due to the choice of selecting the

first 1000 results to maximize the coverage. After the screening phase, 83 papers were retained. A backward reference

search of these studies identified an additional 38 relevant papers, resulting in a final corpus of 122 papers included in

this survey. The full selection workflow is illustrated in the PRISMA diagram in Figure 3.

Subject area distribution. To analyze the disciplinary distribution of the collected studies, each paper was assigned a
subject area based on the official classification associated with the publication outlet. For journal articles, the subject
area was determined using the Scimago Journal Rank classification system1. For conference papers, the classification
provided by the CORE conference ranking portal was used2. For preprints available on arXiv, the category assigned by
arXiv itself was adopted. The resulting distribution of papers across subject areas is shown in Figure 4.

Organization. This survey is structured as follows. Section 2 presents the theoretical foundations of coordinated
online behavior, proposing a new general definition and laying out a comprehensive conceptual framework. Section 3

bridges the theoretical and methodological parts by defining the detection and characterization tasks. Section 4 discusses

the existing literature on the detection task, while Section 5 focuses on the characterization task. Section 6 summarizes

the main outstanding challenges and suggests promising directions of research. Finally, Section 7 concludes the survey.

2 CONCEPTUAL FRAMEWORK

The study of online coordination has its roots in the earlier studies of offline coordination. Recently, this study was

advanced both by commercial platforms and academia, with a large array of different proposals. This section examines

previously proposed definitions of coordination and discusses their advantages and limitations. Based on the results of

this analysis, we then propose a general definition and a comprehensive conceptual framework.

2.1 Offline coordination

Coordination has already been extensively studied well before the emergence of social media across disciplines such

as computer science, organization theory, management science, economics, and psychology [78, 119, 133]. Although

the meaning of coordination is intuitive, researchers suggested many definitions to frame the concept. A concise and

precise definition was given in [76]:

Definition 2.1. Coordination (1988): The additional information processing performed when multiple, connected actors pursue
goals that a single actor pursuing the same goals would not perform [76].

Definition 2.1 denotes coordination as the organizational overhead that multiple actors incur into when pursuing goals

together. We note that this and similar definitions [9, 10, 75, 78] implicitly leverage the fundamental components of

coordination, which we explicitly define as follows:

Definition 2.2. Coordination components: A set of two or more actors who perform activities in order to achieve goals.

Definition 2.2 introduces the fundamental components of coordination: actors, activities, and goals. Being coordination
a nuanced concept, the theoretical modeling of these components can have major implications on downstream analyses

and results. For example, in the case of communities or groups of users, each user in the group can be treated as a

standalone actor, or alternatively the entire group may be considered as a single actor. Similar choices must be made

1https://www.scimagojr.com
2https://portal.core.edu.au/conf-ranks/

Manuscript submitted to ACM

Detection and Characterization of Coordinated Online Behavior: A Survey

5

when modeling the activities that allow actors to coordinate. Each actor typically performs multiple activities during

any given time frame, and each of these activities might contribute differently to the overall coordination. Therefore,

the choice of activities to model during an analysis directly impacts the resulting observed coordination [77]. Finally,

the analyst is often interested in knowing the goal that the actors pursue when performing the activities. However, the

actors may not all have the same goal, or even have any explicit goal at all [76]. These reflections on the components of

coordination surface some of the challenges that early scholars faced since the 80s when studying offline coordination.

Interestingly, many of these challenges carry over to the study of online coordination, informing the development of a

new comprehensive definition and conceptual framework.

2.2 Concepts and definitions by online platforms

Beginning around 2016, mounting societal pressure impelled major social media platforms to confront pervasive

challenges such as the organized dissemination of mis- and disinformation [143]. In consequence of this pressure,

each platform adopted disclosure practices to communicate their results at exposing orchestrated deceptive activities

perpetrated by organized actors. Given the importance of coordination for the success of large-scale disinformation

campaigns [100, 103], within these public disclosure initiatives each platform addressed some instances of malicious

online coordination. This section explores the concepts and definitions introduced by major social media platforms that

are related to online coordination, discussing both their merits and limitations.

2.2.1 Meta (Facebook, Instagram, Threads). After the public disclosure that the Internet Research Agency (IRA) had
strategically exploited the platform to influence the 2016 US presidential election [118, 146, 155], Facebook began

publishing reports detailing how their services were abused and the actions taken in response. In unveiling further
actions against the IRA, in July 2018 Facebook introduced the concept of coordinated inauthentic behavior (CIB) [35].
A few months later, they supplied it with a first definition, and in October 2019 with a second one. These definitions,

originally introduced by Facebook, also applied to Instagram due to their shared ownership. Then they have been

extended across Meta’s platforms, including Facebook, Instagram, and Threads.

Definition 2.3. Coordinated inauthentic behavior (2018): Groups of pages or people working together to mislead others on
who they are or what they are doing [35].

Definition 2.4. Coordinated inauthentic behavior (2019): The use of multiple Facebook or Instagram assets (accounts, pages,
groups, or events), working in concert to engage in inauthentic behavior, i.e., to mislead people or Facebook, where the use of fake

accounts is central to the operation [37].

Definition 2.3 underscores the collaborative nature of disinformation campaigns [125], emphasizing the objective

of misleading others about the purported identity of the involved actors. To this end, it introduces the concept of
inauthenticity of the actors, which is ever since often used in conjunction with the notion of coordination. Definition 2.4
explicitly articulates the concept of inauthenticity and elucidates that the act of deceiving others involves the extensive

use of fake accounts [36]. A widespread critique of these initial definitions is that they exclusively address CIB,

overlooking other types of malicious and possibly harmful coordination, let alone the neutral or benign ones [19, 44, 49,

100]. In September 2021, Facebook provided additional definitions focusing on harmfulness rather than inauthenticity.

Definition 2.5. Coordinated social harm (2021): Networks of primarily authentic users who organize to systematically violate
policies to cause harm on or off the platform [39].

Manuscript submitted to ACM

6

Mannocci et al.

Definition 2.6. Coordinated mass harassment (2021): Coordinated efforts of mass harassment that target individuals at
heightened risk of offline harm [38].

Definitions 2.5 and 2.6 adopt the concept of harmfulness in place of inauthenticity, thereby broadening the scope to also

encompass authentic yet coordinated actors. These, in fact, hold the potential to cause negative consequences both on

and off the platforms, as underscored in Definition 2.5.

2.2.2 Twitter/X. In October 2018, the platform released a public archive containing data about identified information
operations (IOs) [117]. Although not explicitly stated in Twitter’s definition at the time, a certain degree of coordination
is necessary for the success of an IO [18, 138]. However, it was not until January 2021 that Twitter adopted a similar

approach to Facebook and released a definition that explicitly addresses instances where coordination is leveraged to

cause harm both online and offline.

Definition 2.7. Information operation (2018): People directly involved in manipulation that can be reliably attributed to a
government or state-linked actor [134].

Definition 2.8. Coordinated harmful activity (2021): Groups, movements, or campaigns that are engaged in coordinated
activity resulting in harm on and off of Twitter [135].

2.2.3 YouTube/Google. In its reports, primarily concerning abuses that occurred on YouTube, Google makes reference
to coordinated influence operations (CIO) [46]. Even though Google did not provide a definition for CIOs, they nonetheless
highlighted the importance of coordination in these online manipulations.

2.2.4 Reddit. In contrast to other platforms, Reddit embraced the broad concept of content manipulation to characterize
the campaigns that violate its rules [109]. The platform shared only a small number of such campaigns, leaving it

unclear whether these represent the entirety of the identified cases, or only a selection of them. Despite the absence of

an explicit reference to coordination, large-scale content manipulations gain advantage from coordinated activities,

similarly to what we discussed earlier about IOs.

Definition 2.9. Content manipulation (2022): Things like spam, community interference, vote manipulation, and other attempts
to artificially promote content [109].

2.2.5 Tiktok. In 2023, TikTok revisited Facebook’s definition of CIB, explicitly linking coordination with inauthenticity.
In doing so, it emphasizes coordinated activity aimed at misleading users or influencing public discourse. Among the

cited examples, TikTok highlights coordination in the context of information operations, such as accounts covertly

promoting political candidates or issues, or posting content on behalf of foreign entities without proper disclosure.

Definition 2.10. Covert Influence Operations (2023): Coordinated, inauthentic behaviors where networks of accounts work
together to mislead people or our systems and try to strategically influence public discussion. This may include attempting to

undermine the results of an election, influencing parts of an armed conflict, or shaping public discussion of social issues. [131].

2.2.6 Ambiguities and limitations. This brief survey of the main concepts and definitions proposed by social media
shows that online platforms are at the forefront in the analysis of coordinated online behavior. However, their con-

ceptualizations are driven primarily by pressing practical regulation needs and by immediate contingencies, rather

than by methodological rigor and theoretical soundness [35]. Faced with specific instances of malicious coordination,

online platforms adopt different and at times contrasting definitions, adding confusion and ambiguity to the already

challenging task of defining an inherently nuanced and complex phenomenon [89].

Manuscript submitted to ACM

Detection and Characterization of Coordinated Online Behavior: A Survey

7

Table 1. Examples of operational definitions used in recent academic literature. No definition is general enough to comprehensively
describe coordinated online behavior. However, each definition grasps one or more relevant properties (highlighted in bold) that we
leverage in our framework.

reference

Nizzoli et al. [100]
Cinelli et al. [19]
Giglietto et al. [44]
Magelinski and Carley [72]
Weber and Neumann [145]
Magelinski et al. [73]
Zhang et al. [155]
Pacheco et al. [103]
Hristakieva et al. [51]
Keller et al. [59]

definition
Unexpected, suspicious, or exceptional similarity between a number of users
The number of times two accounts behaved similarly, such as when they repeatedly retweet the same post
The act of making people and/or things be involved in an organized cooperation
Many instances of a tweet-behavior, i.e. tweeted hashtag [...] within a small predetermined time window
Anomalous levels of coincidental behavior
Users [that] take the same actions within minutes of one another
Accounts that co-appear, or are synchronized in time
[Users exhibiting a] surprising lack of independence
Coordination between users implies a shared intent
A group of people who want to convey specific information to an audience

The current tangled landscape of platform definitions means that certain coordinated efforts may be categorized

as such by some platforms but not by others, contingent upon the concepts they adhere to. What may be identified

as coordinated behavior on one platform could be overlooked or dismissed on another, leading to inconsistencies in

detection and mitigation. As a notable example, in June 2020 many teenagers organized on TikTok to reserve tickets for

a Donald Trump rally to be held in Tulsa, OK (US). By mass-reserving and later cancelling their participation, they

prevented others from making reservations and artificially inflated expected attendance numbers, ultimately causing an

embarrassing number of empty seats at the rally [31]. Facebook’s head of security commented that, while tactical and

sophisticated, they would have not acted upon this campaign as an instance of CIB (as per Definition 2.4), since it did

not make use of fake accounts nor aimed to mislead Facebook users [31]. A similar case is the Chinese Spamouflage
campaign, a cross-platform propaganda effort against the Hong Kong pro-democracy movement.3 Various platforms
reported takedowns of Spamouflage instances, with Google and Twitter labeling it as CIO and IO (as per Definition 2.7),

respectively. However, Reddit interpreted Spamouflage differently, recognizing its low-quality and one-sided content,
but refraining from considering these activities as rule violations.4

Evidently, platforms address instances of coordinated online behavior disparately, and the criteria to establish the

legitimacy of user behaviors lack objectivity. These discrepancies underscore the need for a unified understanding

and standardized approach to defining and addressing online coordination, one that transcends platform-specific

idiosyncrasies and fosters a more cohesive response to this challenge.

2.3 Concepts and definitions in academic literature

As shown in Figure 2, scientific interest in coordinated online behavior has drastically risen in the last few years. However,

akin to social media platforms, scholars have generally refrained from proposing theoretically-grounded and general

definitions. The majority of the existing studies adopt Facebook’s Definition 2.3 of CIB [85, 86]. Instead, those who
propose their own conceptualization mainly provide operational definitions useful for the development of coordination
detection methods [73, 100, 103]. Table 1 reports some examples of operational definitions proposed recently. As shown,

no definition is comprehensive and general enough to adequately describe the multifaceted phenomenon of coordinated

online behavior. The existing conceptualizations of the phenomenon appear to be influenced by the specific technique

employed for its detection. Consequently, the criteria used to define coordination vary, encompassing aspects ranging

3https://graphika.com/reports/spamouflage-breakout (accessed: 31/07/2024)
4https://www.reddit.com/r/redditsecurity/comments/dp9nbg/reddit_security_report_october_30_2019/ (accessed: 31/07/2024)

Manuscript submitted to ACM

8

Mannocci et al.

from similar behavior [19, 72, 73, 100, 103, 145] to synchronicity [72, 73, 155] and common intent [51, 59]. As practical

examples of the above, some definitions and the resulting detection methods revolve around the anomalous use of

hashtags or URLs by multiple users [44, 73], or repeated screen name swapping [103].

More fundamentally, the field still lacks a formal and statistically grounded definition of coordination, including

well-defined null models against which coordinated behavior can be rigorously assessed. As a consequence, many

approaches rely on platform- and task-specific heuristics, which complicates cross-domain comparisons, reproducibility,

and the estimation of effect sizes. This limitation echoes challenges observed in related areas such as bot detection,

where simplistic data collection and labeling practices have been shown to hinder generalization even across datasets

from the same platform [50]. While no single definition fully captures the complexity of coordinated online behavior,

existing works collectively highlight key properties of the phenomenon. These properties can serve as building blocks

toward a more general and theoretically grounded definition of coordination.

2.4 General definition and fundamental components of coordinated online behavior

We propose a new general definition of coordinated online behavior that overcomes the ambiguities and limitations of

the existing definitions. The new definition leverages the components of offline coordination introduced in Section 2.1

and is informed by the various operational definitions proposed by social media platforms and by the academic literature,

respectively discussed in Sections 2.2 and 2.3.

Definition 2.11. Coordinated online behavior: A group of users
(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)
(cid:125)

(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)

(cid:124)

(cid:123)(cid:122)
actors

(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)

who perform synergic actions
(cid:123)(cid:122)
(cid:125)
(cid:124)
actions

(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)

(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)

.
in pursuit of an intent
(cid:123)(cid:122)
(cid:125)
(cid:124)
intent

(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)(cid:32)

Definition 2.11 delineates coordinated online behavior based on three fundamental components—actors, actions, and
intent—that are similar to the components of offline coordination outlined in Definition 2.2. Definition 2.11 and its three
fundamental components enable the comprehensive mapping of all instances of online coordination, as discussed in the

following.

2.4.1 Actors. Actors refer to the individuals or entities that are engaged in coordinated behavior. The attributes of
the actors contribute to characterizing instances of coordination. For example, the way in which the actors represent

themselves to those not involved in the coordinated behavior determines whether the coordination is authentic or

otherwise. All instances of online coordination where the actors misrepresent themselves, as in the case of social

bots [47, 51, 100, 103] and state-backed trolls [91], are cases of inauthentic coordination. Conversely, coordination

among actors who accurately self-portray is deemed authentic [47]. In addition, the relationships between the actors

determine whether the coordination is spontaneous, grassroots, or emergent (i.e., bottom-up) [100] or whether it is

structured and well-organized (i.e., top-down) [138]. Finally, the number of the involved actors determines the scale of

the coordination.

2.4.2 Actions. Actions represent the practical means that allow actors to coordinate. In coordinated behavior the
actions are synergic, in that they are mutually reinforcing and potentially capable of producing a larger effect than

that obtainable by individual actions alone. While actors and intent can be misrepresented or concealed, actions

are typically visible and non-falsifiable. In other words, the actions with which the actors coordinate represent the

digital breadcrumbs of the coordination. For this reason, the actions are the component based on which the majority

of coordination detection methods are developed. Furthermore, the types and attributes of the actions also provide

information towards characterizing instances of coordination. For example, the timing and synchronization of the

Manuscript submitted to ACM

Detection and Characterization of Coordinated Online Behavior: A Survey

9

actions among actors indicates the degree of planning and organization involved [73, 155]. The consistency of the

actions and the actions performed in response to external events are further characteristics of coordinated behaviors.

Finally, the types of actions and their content provides insights into the intent and goals of the actors [19].

Intent. The intent is the objective that the actors pursue when they coordinate. When studying coordinated
2.4.3
online behavior, the intent of the actors is typically unknown, if not deliberately concealed. For example, actors involved

in malicious or harmful coordination conceal their intent to avoid being stopped in their endeavor [51]. However, also

actors involved in neutral or benign forms of coordination might not openly state their goals and intent. For this reason,

the observer often tries to infer the intent based on the visible actions performed by the actors. Furthermore, intent can

be either shared and explicit among the actors, or implicit. For instance, the perpetrators of a disinformation campaign

share the explicit goal of disseminating certain pieces of false information [59]. Conversely, fans of a sports team or

public character may spontaneously engage in coordinated actions to support their idol, without having agreed on

a specific objective or course of action [100]. The previous examples highlight that the characteristics of the intent

are related to the degree of organization of the actors. Importantly, the intent also contributes to determining the

harmfulness of the coordinated behavior. However, while there are cases in which it is relatively straightforward to

categorize a coordinated behavior as harmful or otherwise—think for example of coordinated hate attacks [83] or

state-backed disinformation campaigns [18]—there also exist situations where the harmfulness of the intent is inherently

subjective. Coordinated efforts to promote a controversial political ideology may be perceived as harmful by some,

while others may view them as legitimate expressions of free speech [102]. Similarly, coordinated campaigns to boycott

a company or criticize a public figure may be seen as harmful by those targeted, but supporters may genuinely view

them as justified forms of activism [97].

2.5 Defining dimensions of coordinated online behavior

As discussed in the preceding sections, coordinated online behavior constitutes a complex and multifaceted phenomenon

whose instances are contingent upon the actions and intent of the involved actors. Here we leverage our discussion

about the fundamental components of online coordination to introduce four defining dimensions of this phenomenon:

authenticity, harmfulness, orchestration, and time-variance.

2.5.1 Authenticity. Authenticity refers to the degree of genuineness and transparency that the actors exhibit in their
actions and overall online presence. Coordinated authentic behavior is executed by genuine actors and typically emerges

organically within a community of users who share common interests or beliefs. Examples of authentic coordination

are activists, social movements, and mutual support groups, which are driven by motivations such as a desire for social

or political change or the cultivation of a sense of community and belonging [100, 126]. While authentic forms of

coordination are also harmless in the majority of cases, as in the previous examples, there also exist less frequent cases

of authentic yet harmful behaviors. For instance, certain coordinated hate groups openly encourage racist, xenophobic,

or supremacist ideologies [95, 97, 146]. Conversely, coordinated inauthentic behavior entails the use of fake accounts,

such as social bots, trolls, and fake personas [25, 115]. These are typically employed for purposes such as spreading

disinformation, sowing confusion, or eroding trust in democratic institutions. As such, inauthentic coordination is

often characterized by its deceptive nature and aim to manipulate unaware users [125]. Nonetheless, there exist cases

of inauthentic yet harmless coordination. For example, online participants in the Arab Spring movements concealed

their identities to avoid government surveillance and potential reprisals [126]. While their coordinated efforts were

inauthentic in terms of individual identity disclosure, they remained largely harmless in intent, aiming to promote

Manuscript submitted to ACM

10

Mannocci et al.

democratic ideals, social justice, and human rights. These examples highlight the difference between authenticity and

harmfulness, which represent two orthogonal dimensions of coordinated online behavior.

2.5.2 Harmfulness. Harmfulness refers to the negative impact, consequences, or outcomes—both online and offline—
resulting from the coordinated actions of the actors. As discussed in Section 2.4.3, harmfulness depends both on the

shared intent and actions of the actors engaged in coordination, and on the viewpoint of the observer, constituting a

much more conceptually intricate dimension of online coordination than authenticity. However, in spite of the inherent

subjectivity, there exist many clear cut cases of harmful and harmless coordination. For example, coordinated actors

involved in the spread of disinformation, hate speech, and online harassment, represent straightforward cases of harmful

coordination [18, 99]. In contrast, users who coordinate to collect and share information and other resources, such as in

the aftermath of mass emergencies, represent cases of harmless coordination [73, 100, 102].

2.5.3 Orchestration. Orchestration represents the degree of planning and organization between the coordinated actors.
This dimension is closely linked to the intent of the actors, in that highly orchestrated campaigns typically imply

shared intent and goals between the participants. The orchestration of a coordinated campaign can be centralized or

distributed. In centralized orchestration, a single actor or entity exercises control and coordination over the actions

of all other actors involved in the coordinated behavior. This centralized authority dictates the timing, content, and

strategy of the coordinated actions, allowing for tight coordination and synchronization. An example of strong and

centralized orchestration is the coordinated behavior exhibited by social botnets, where large groups of automated

accounts quasi-simultaneously perform predefined actions depending on the command of a botmaster entity [82]. In

decentralized orchestration, coordination and control are distributed among multiple actors within a network, without

a single central authority dictating the actions of all participants. Actors may self-organize, collaborate, or communicate

autonomously, often guided by shared goals, interests, or ideologies. For instance, in January 2021, retail investors

coordinated on Reddit to target short-selling activity by hedge funds on GameStop shares, causing a surge in the share

price and triggering significant losses for the funds involved [68]. Instead, non-orchestrated coordinated behavior

occurs when the actions of multiple actors spontaneously converge around a given topic, narrative, or activity. Certain

viral social media trends are an example of non-orchestrated coordination emerging from the widespread adoption of a

particular hashtag or activity that occurs organically as many users observe and emulate others’ behavior [126].

2.5.4 Time-variance. Time-variance refers to the temporal characteristics and the dynamic nature of coordinated online
behavior. It grasps possible changes in the types, timing, frequency, and intensity of the actions, which in turn may

reflect changes in the intent of the actors, as well as adaptations or responses to external stimuli. Examples of largely

static coordinated behavior are the activities of some spammers and bots, who repeatedly perform the same actions

adhering to a fixed pattern without much adaptation or variation [25, 102]. Conversely, many information operations

are dynamic and time-varying, presenting different characteristics at different points in time. Among the changing

characteristics are the types of actors involved in the coordination (e.g., whether automated or human-operated) or

the topics of discussion [125, 138]. Time-variance also strongly depends on the duration of the coordinated behavior

itself. Actors involved in certain state-sponsored disinformation campaigns operate on online platforms for extended

periods, spanning years or even decades [138]. Over such lengthy time frames, the actors adapt their tactics, narratives,

and targets in response to shifts in intent, changes in technology and platforms, or advancements in countermeasures.

This extended duration implies a relatively gradual and nuanced evolution of the coordinated behavior. Conversely,

other forms of online coordination rely on expendable or disposable accounts created for short-lived and fast-paced

Manuscript submitted to ACM

Detection and Characterization of Coordinated Online Behavior: A Survey

11

activities [12]. These actors are employed for specific tasks and then discarded or deactivated once their purpose is

fulfilled or they are detected. As a result, these ephemeral instances of coordination are rapid, intense, and short-lived.

2.6 Taxonomy and final remarks

Our conceptual framework of coordinated online behavior encompasses the three fundamental components pre-

sented in Section 2.4 and the four defining dimensions discussed in Section 2.5, providing a general and flexible

scheme for studying, categorizing, and comprehensively mapping the multiple instances of online coordination.

2.6.1 Taxonomy. Figure 5 demonstrates the generality of the concep-
tual framework by presenting a taxonomy of coordinated online be-

havior based on the dimensions of authenticity and harmfulness. This

analysis takes inspiration from the well-known conceptual frame-
work of information disorder that categorizes instances of mis-, mal-,
and disinformation based on the falseness and harmfulness of the in-

formation [143]. As shown in Figure 5, the dimensions of authenticity

and harmfulness allow distinguishing between different types of coor-

dinated online behavior, ranging from potentially nefarious to neutral

and beneficial ones. Among the most problematic instances of online

coordination are harmful and inauthentic phenomena such as infor-

mation operations and disinformation campaigns, which are often ini-

tiated by malicious social bots and state-sponsored trolls [3, 18, 138].

Fig. 5. Taxonomy of coordinated online behavior ob-
tained by considering the dimensions of harmfulness
and authenticity of our conceptual framework. The
framework conveniently allows the mapping of dis-
parate instances of online coordination.

Other problematic phenomena are those featuring harmful yet authentic behaviors, such as the activity of conspiracy

theorists and hateful extremists [83, 95, 97]. Conversely, the activity of coordinated crisis communication by democratic

institutions during emergencies [151], grassroots social movements, fandoms, and other activists represent instances

of harmless and authentic coordination [126]. Finally, harmless yet inauthentic behaviors lay outside of the partially

overlapping sets, and are exemplified by hacktivists, dissidents, and other anonymous protesters [126]. Alternative

taxonomies can be obtained by leveraging the dimensions of orchestration and time-variance, which would highlight

additional phenomena to those shown in Figure 5.

Final remarks. The previous instantiation of our conceptual framework in a taxonomy based on the dimensions of
2.6.2
harmfulness and authenticity concludes the theoretical part of the survey. The following section bridges the theoretical

and methodological parts by presenting the problem definition. Subsequently, we systematically review the proposed

methodologies for detecting and characterizing coordinated online behavior, showing how these tasks stem from the

conceptual modeling of the phenomenon presented in this section.

3 PROBLEM DEFINITION

The problem of identifying and investigating different types of coordinated online behavior involves defining two
functions 𝑓 (·) and 𝑔(·) that respectively implement the tasks of coordinated behavior detection and characterization, as
outlined in Figure 6. Given a set of users and their actions on one or more online platforms, 𝑓 (·) identifies possible
coordinated groups of users. Instead, 𝑔(·) extracts additional information for each detected group, thus contributing to
determining the nature, intent, and the overall characteristics of the involved actors (e.g., whether they are inauthentic,

harmful, etc.). The detection and characterization tasks are related to the Definition 2.11 of coordinated online behavior

Manuscript submitted to ACM

HARMFULAUTHENTICMalicious Social BotsState-backedConspiracistsExtremistsActivistsFandomsGrassrootsHacktivistsProtestersDissidentsSocialMovementsTrolls12

Mannocci et al.

input

detection task

detection output

characterization
task

characterization
output

𝑈 = {𝑢1, . . . , 𝑢𝑁 }

users (U)

ı
𝑡1

(cid:239)
𝑡2

. . .

. . .

𝑡𝑚−1

ı
𝑡𝑚

𝐻 = {𝐻1, . . . , 𝐻𝑁 }

activities (H)

𝑓 (𝑥)

communities (P)

𝑔(𝑥)

network science
data mining

machine learning

clusters (C)

labels (B)

inauthenticity

harmfullnes

orchestration

time-variance

toxicity score

⌣ (cid:192) ⌢
sentiment score

3
bot score
...

indicators (M)

Fig. 6. The analytical process of studying coordinated online behavior, involving the detection and characterization tasks. The input to
the overall process is a set of users 𝑈 and their activities 𝐻 on one or more platforms. The output of the detection task is either a set of
binary labels 𝐵, clusters 𝐶, or network communities 𝐺 that differentiate coordinated and non-coordinated users. The characterization
task receives these in input and outputs a set of indicators 𝑀.

and its components in that the function 𝑓 (·) implementing the detection task does so via the analysis of user actions,
while the function 𝑔(·) implementing the characterization task provides information about the actors and their intent.
third component, i.e., actors and intent, respectively. A comprehensive overview of the entire process is depicted in
Figure 6. The input is represented by the set of users 𝑈 to analyze and their activities 𝐻 . The detection task differentiates

coordinated users from non-coordinated ones. Depending on the detection method, the distinction between the two

can be expressed as binary labels assigned to the users, as two or more sets (e.g., clusters) of either coordinated or

non-coordinated users, or as two or more coordinated or non-coordinated communities (i.e., nodes and edges) from

a network. These are subsequently scrutinized during the characterization task, which computes a set of indicators

for each coordinated user, set, or community. The indicators are selected so as to provide information about the

characteristics of the coordinated actors and their behavior. For example, computing bot scores is a common method to

estimate the inauthenticity of coordinated users.

3.1 Detection of coordinated online behavior

1 , . . . , ℎ𝑢 𝑗

Input. Let 𝐼 = ⟨𝑈 , 𝐻 ⟩ be the problem input, where 𝑈 = {𝑢1, . . . , 𝑢𝑁 } denotes the set of users and 𝐻 =
3.1.1
[𝐻𝑢1, . . . , 𝐻𝑢𝑁 ] represents an ordered vector of activities performed by those users. We define the activity of a user 𝑢 𝑗
as 𝐻𝑢 𝑗 = [ℎ𝑢 𝑗
𝑇 ] representing the vector of chronologically ordered actions performed by 𝑢 𝑗 . An action is defined
by the quadruple ℎ = ⟨𝑡𝑦𝑝𝑒, 𝑡𝑎𝑟𝑔𝑒𝑡, 𝑐𝑜𝑛𝑡𝑒𝑛𝑡, 𝑡𝑖𝑚𝑒𝑠𝑡𝑎𝑚𝑝⟩ which describes the type of action executed by a user on a
specific target or content, at a given timestamp. Users can execute actions of different type such as posting, resharing,
befriending, and more. A target is another user of the platform who is affected by the action. For example, in the case
of a retweet action on the platform Twitter/X, the target is the author of the retweeted tweet. For some actions the
target is undefined, as in the case of the posting action. The content of an action is a post (e.g., a tweet, comment,
submission, and more, depending on the platform). Posts contain one or more elements of content, such as text, image,

URL, mention, hashtag, and more. In case the content contains multiple elements, the corresponding action is called

Manuscript submitted to ACM

Detection and Characterization of Coordinated Online Behavior: A Survey

13

compound action [73]. Similarly to the target, also the content can be undefined depending on the type of action, as

in the case of a befriending or following action. To wrap up, the type of action and its timestamp are always defined,

while one of content and target might be optional, depending on the type of action.

3.1.2 Methods and output. As presented in Section 4, most of the existing literature on coordinated behavior detection
analyzes both the set of users and their actions. Some studies only leverage the content of the actions, without

considering their type [26, 83, 141]. Furthermore, certain works do not take into consideration the timings of the

actions [16, 17, 19, 83], while some others only consider the timings [12]. The task of detecting coordinated online
behavior is modelled by the function 𝑓 (𝑈 , 𝐻 ), which can provide three different outputs depending on the adopted
method, corresponding to different levels of detail and information on the coordinated users:

𝑓 (𝑈 , 𝐻 ) =

𝑃𝑖 = (𝑉𝑖, 𝐸𝑖 ), 𝑉𝑖 ⊆ 𝑈

𝑃 = {𝑃1, . . . , 𝑃𝑖, . . . 𝑃𝑘 },


𝐶 = {𝐶1, . . . , 𝐶𝑖, . . . 𝐶𝑘 }, 𝐶𝑖 ⊆ 𝑈



𝐵 = {𝐵𝑐, 𝐵𝑢 },

𝐵𝑐 ∪ 𝐵𝑢 = 𝑈

communities

clusters

binary labels

(1)

In the most general case, the output of 𝑓 (·) is a set 𝑃 of communities of coordinated users. Coordinated communities 𝑃𝑖
are sub-networks where the nodes are users from 𝑈 , and the edges—with their weights—encode the level of coordination

among the users. Communities are typically outputted by those methods that adopt an internal network representation,

which is then analyzed with community detection algorithms. Coordinated communities are an information rich

representation, given that the presence and weight of links between the coordinated users facilitates subsequent
analyses, such as those needed for the characterization task. Another possible output consists of a set of clusters
of users. The clusters 𝐶𝑖 are produced by methods that adopt tabular representations of the users, which are then
analyzed with clustering algorithms. These methods typically ignore the relationships between the users but are able to

identify multiple groups of coordinated users. Finally, the least informative output is given by those methods based
on classification algorithms. These methods assign binary labels, partitioning the initial set of users 𝑈 in two labeled
groups of coordinated (𝐵𝑐 ) and non-coordinated (𝐵𝑢 ) users. These labelled groups do not provide information about
neither the relationships between the users nor the existence of multiple coordinated groups of users in 𝑈 .

3.2 Characterization of coordinated online behavior

Input. The characterization task is modelled by the function 𝑔(𝑌, 𝐻 ) = 𝑀 whose inputs are the groups of
3.2.1
coordinated users resulting from the detection task 𝑓 (𝑈 , 𝐻 ) = 𝑌 ∈ {𝑃, 𝐶, 𝐵}, defined in Eq. (1), with their activities 𝐻 .

3.2.2 Methods and output. As discussed in Section 5, the characterization task aims at computing a set of quantitative
indicators 𝑀 to measure distinctive properties of the detected coordinated behaviors in terms of the defining dimensions

that we presented in Section 2.5: authenticity, harmfulness, orchestration, and time-variance. The indicators that can

be used in the characterization task partly depend on the methods and outputs of the detection task. For example,

assortativity measures the extent to which nodes with a high degree in a network are connected to other nodes with

a high degree, and vice versa. This indicator was used to gain insights into the inner structure and organization of

certain coordinated communities [100]. However, assortativity can be computed only if the coordination detection

method outputs communities, rather than clusters or binary labels. On the contrary, other indicators can be computed

independently of the detection method, such as the aforementioned bot scores that are commonly used as an estimator

of the inauthenticity of the coordinated users [47, 51, 100, 103]. The utility of the characterization task is not limited to

shedding light on the nature of the detected coordinated behaviors nor to distinguishing between different instances

Manuscript submitted to ACM

14

Mannocci et al.

1: user selection

2: network construction

3: network filtering

4: community discovery

Fig. 7. Main steps of the network science methods for the detection of coordinated online behavior. 1: The selected users become
nodes in a network. 2: User similarities are computed with a similarity function and assigned to the edge weights of the network. 3:
The network is filtered so as to retain only similarities with given properties. 4: Community discovery is performed to detect groups
of strongly coordinated users.

of the phenomenon. In fact, the output of characterization task can also be leveraged to validate the output of the

detection task, as in those frequent cases when a ground-truth of coordinated users is unavailable.

4 DETECTION OF COORDINATED BEHAVIOR

Coordination detection methods can be classified into two main categories depending on their underlying approach:

network science or machine learning. The following sections discuss the existing solutions in each category.

4.1 Network science methods

Network science coordination detection methods build a network of users or posts, where the links between the nodes

in the network represent the presence, and possibly also the extent [100], of coordination. In spite of the existing
differences, all methods in this category carry out the sequence of steps shown in Figure 7, namely: (i) user selection, (ii)
coordination network construction, (iii) network filtering, and (iv) community discovery. We now discuss the objective
and the implementation options available for each step.

4.1.1 User selection. This step selects an initial subset 𝑈 ′ ⊆ 𝑈 of users according to some criteria that depend on the
purpose of the analysis. This initial selection is motivated by the observation that a small fraction of users accounts for

the majority of actions on a social network [100], especially those associated with harmful behaviors [111]. Selecting a

subset of users also has the positive consequence of reducing the computational cost of the subsequent steps, which

can easily become time- and computation-intensive for large networks [21].

Implementation. Multiple choices can be made to select a subset of relevant users. A common choice is to select
the most active users as they produce the largest share of actions and content. Most active users can be defined as
those who publish a large number of original posts (super-producers) [64, 72, 103], or as those having a large number
of re-shares (super-spreaders) [19, 30, 51, 66, 67, 90, 100, 128]. Other than activity, network centrality or influence,
suspicious behavior, location, and timings are used for user selection [70]. Furthermore, many other general criteria can

also be adopted, such as selecting all users who posted certain keywords, or all followers of a given user. Combining

multiple criteria allows for even more fine-grained user selections.

4.1.2 Coordination network construction. This step builds a coordination network between the users 𝑈 ′ ⊆ 𝑈 previously
selected.5 A coordination network is a type of network where links exist only between coordinated nodes. As per
Definition 2.11, coordination implies synergic actions between users. In network science methods, this concept is
operationalized with co-actions. A co-action represents two users performing the same action on the same target

5A few works follow the general approach of network science methods, but build networks of content rather than users. These are discussed in Section 4.1.5.
Manuscript submitted to ACM

Detection and Characterization of Coordinated Online Behavior: A Survey

15

A: social network
𝑢1

B: interaction network
𝑢1

C: coordination network
𝑢1

ı

ı

𝑢2

𝑢3

𝑢2

7

𝑢3

𝑢2

ı

𝑢3

Fig. 8. Differences between social (A), interaction (B), and coordination (C) networks. Solid black edges represent actions on the
online platform, while dashed colored edges show how actions are translated into edges in the corresponding type of network.
Coordination networks are typically undirected and link users performing similar actions at around the same time. Differently to
social and interaction networks, coordination networks allow connecting users even if they never directly interact with one another.

or content. For instance, two users who comment, like, or re-share the same post are generating a co-action. As

shown in Figure 8, the two coordinated users need not be directly connected in the social or interaction network.

This characteristic makes coordination networks particularly suitable for surfacing coordination between seemingly

unrelated users, such as those involved in inauthentic or harmful behavior, so much so that some scholars specifically
refer to latent coordination networks [146]. In the most general case, a coordination network is a multiplex network
𝐺 (𝑉 , 𝐸,𝑊 , L). In order to build 𝐺, one must define the types of co-actions 𝐶𝑎 to consider (e.g., re-shares, mentions,
follows, etc.). When multiple co-actions are used, 𝐺 is a multiplex network with 𝐿 layers, where L = {1, . . . , 𝐿} is the set
of layers, each corresponding to a co-action 𝑖 ∈ 𝐶𝑎. However, the majority of existing works leverage a single co-action.
In this case, the number of layers is 𝐿 = 1 and 𝐺 is a single layer network. Each layer in 𝐺 is an undirected weighted
graph 𝐺𝑖 (𝑉 𝑖, 𝐸𝑖,𝑊 𝑖 ), where 𝑉 𝑖 ⊆ 𝑈 ′, 𝐸𝑖 and 𝑊 𝑖 respectively denote the set of nodes, edges, and weights of layer 𝑖. We
highlight that 𝑉 = (cid:208)𝑖 ∈ L 𝑉 𝑖 , 𝐸 = (cid:208)𝑖 ∈ L 𝐸𝑖 , and 𝑊 = (cid:208)𝑖 ∈ L 𝑊 𝑖 . Given a layer 𝑖, an edge 𝑒𝑖
is created if there exists a
𝑗𝑘
co-action of type 𝑖 between two users (𝑢 𝑗, 𝑢𝑘 ). The edge weight 𝑤𝑖
𝑗𝑘 = 𝑠𝑖𝑚𝑖 (𝑢 𝑗, 𝑢𝑘 ) is obtained via a similarity function
that computes pairwise user similarities in 𝑈 ′. Different similarity functions can be used for different co-actions.

Implementation. Building the coordination network 𝐺 requires defining the types of co-actions and the corresponding
similarity functions. The vast majority of works in literature rely on a single co-action and the resulting networks

are single-layered. Table 2 reports the main implementation details for the works that built single layer coordination

networks. In table, when multiple co-actions are listed for the same author or work, this means that multiple single layer

networks were built, rather than a multiplex network resulting from the simultaneous analysis of multiple co-actions.

The few existing works that built multiplex coordination networks are instead described in Table 5.

As shown in Table 2, the most common type of co-action is co-sharing (e.g., the co-retweet action on Twitter/X) [8, 17–
19, 29, 30, 32, 47, 51, 52, 58, 61, 62, 65, 66, 70, 81, 100, 103, 104, 114–116, 128, 129, 138, 144–146]. Other frequently used
co-actions are co-reply/co-comment [60, 71, 81, 106, 145, 146] and co-like [53], which occur when two users comment
or leave a reaction to the same post. The previous co-actions are based on the type of interaction between users and
content in an online platform. Other co-actions are instead based on the content of user posts. For example, co-post
(e.g., co-tweet on Twitter/X and co-parley on Parler) [13, 17, 22, 28, 32, 48, 59, 67, 71, 104, 116, 138, 140, 141, 149],
co-image, and co-video [152] represent the publishing of posts with the same text, image, or video by multiple users.
More specific co-actions are also possible, such as co-text-image that occurs when multiple users post images that
contain the same text [121]. Similarly, co-mention [3, 52, 73, 81, 90, 92, 94, 95, 138, 145, 146], co-URL [3, 14, 16, 22,
29, 32, 41–44, 49, 52, 70–73, 81, 92, 94–97, 112, 122, 138, 145, 146, 148, 150], and co-hashtag [3, 15, 29, 32, 52, 70–
73, 81, 91, 92, 94, 95, 103, 138, 142, 145, 146, 148] represent two users publishing a post with the same user mention,
URL, or hashtag. Regarding the latter, the majority of works consider publishing a post with a single common hashtag
Manuscript submitted to ACM

16

Mannocci et al.

Table 2. Network science methods for detecting coordinated behavior based on single layer user networks. For each group of works
we report the considered co-actions, similarity functions, filtering criteria, and community detection methods.

reference

[18]
[47]
[61, 62]
[65]
[115]
[19, 30, 51, 66, 100, 128]
[114, 129]
[144]

[8]

[17]

[59]
[116]
[13]
[28]
[64]
[102]
[98]
[140]

[149]

[96]

[97]

[70]

[104]

[145, 146]
[138]

[103]

[27]

[67]

[71]

[148]

[20]
[16]
[14, 41, 43, 44, 49, 110,
112, 122]
[150]
[3]
[95]
[22]
[42, 121]
[99]
[152]
[15]
[91]
[142]
[53]

[60]

[106]
[90]
[157]
[158]

action

retweet
retweet
retweet
retweet
retweet
retweet
retweet
retweet

retweet

retweet, tweet

retweet, tweet
retweet, tweet
tweet
tweet
tweet
tweet
parley
text

tweet

tweet, URL

tweet, parley, URL, username

retweet, tweet, URL, hashtag

similarity

cardinality
cardinality
cardinality
cardinality
cardinality
cosine similarity TF-IDF
cosine similarity TF-IDF
cardinality

cosine similarity

cardinality

cardinality
cardinality
cosine similarity
cardinality
cardinality
text similarity
cardinality
cardinality

cardinality,cosine similarity
text similarity, cardinality,
cosine similarity
cosine similarity TF-IDF, text
similarity

cosine similarity TF-IDF

retweet, tweet, URL, hashtag, fast
retweet
retweet, URL, hashtag, mention, reply cardinality
retweet, tweet, URL, hashtag, mention cosine similarity TF-IDF
retweet, hashtag, image, handle
change, synchronization
retweet, tweet, image, synchronization cosine similarity TF-IDF
Normalized Compression
Distance

interaction, text, synchronization

Jaccard coefficient,
cardinality, cosine similarity

filters†
threshold, ADJ
EDO
threshold, ADO
backbone, ADJ
EDO
backbone
backbone, EDO
threshold, ADJ
kNN graph,
correlation

threshold, EDO

community detection

modularity clustering
Louvain
Louvain
Louvain

Louvain
Leiden

HDBSCAN

Louvain, connected
components
Louvain

cohesive campaign

threshold, EDO
threshold, EDO
threshold, EDO
ADO
threshold
threshold, ADO
threshold, kNN graph Leiden
backbone
threshold, kNN graph,
ADO
threshold, EDO

Louvain

Louvain

threshold, kNN graph Louvain

threshold, ADO

ADO (fast retweet)

connected components

ADJ
ADJ

threshold, EDO

threshold

kNN graph

focal structures
Leiden

Louvain

text, synchronization, hashtag, URL,
duet, stitch, reply
hashtag, URL, video description,
music, audio
URL
URL

URL

URL
URL, hashtag, mention
URL, hashtag, mention
URL, text
URL, text-image
image
image, video
hashtag
hashtag
hashtag
like

comment

comment
mention
report
follow

cosine similarity TF-IDF

threshold

connected components

cardinality

kNN graph

connected components

cosine similarity TF-IDF
cardinality

threshold, EDO
kNN graph

connected components
Louvain

cardinality

threshold, ADO

connected components

cardinality
unweighted
cardinality
cosine similarity TF-IDF
cardinality
cardinality
cardinality
cardinality
cardinality
cardinality
cardinality

cardinality

cardinality
cosine similarity TF-IDF
cardinality
cosine similarity

EDO
threshold, EDO
threshold, ADJ
threshold, ADO
threshold, kNN graph
threshold, ADO
threshold
threshold, backbone

threshold

threshold

threshold, ADO
threshold
threshold

Leiden
Louvain

connected components

connected components
connected components
Louvain

k-means, hierarchical
clustering
connected components
Louvain
connected components
Louvain

† ADJ: adjacent time window, EDO: evenly distributed overlapping time window, ADO: action-driven overlapping time window

as a valid co-action [3, 32, 72, 73, 91, 94, 95, 138, 142, 145, 146]. However, others argued that using the same set or
sequence of hashtags represents a stronger and more reliable signal of coordination [15, 29, 70, 103]. More recently,

Manuscript submitted to ACM

Detection and Characterization of Coordinated Online Behavior: A Survey

17

on platforms such as TikTok, coordinated behaviors have also been studied through co-stitch [71] and co-duet [71],

which correspond to users jointly engaging with the same source content by embedding or responding to it within

their own videos, as well as through the sharing of videos that reuse the same [148] or similar audio tracks [148].

Additional forms of coordination include co-follow [158] and co-report [157], where users collectively follow or report

the same account. When a co-action is defined in such a way that multiple atomic actions are required for two users
to be considered as coordinated, that co-action is a compound action [73]. More generally, compound actions refer
to actions that involve the simultaneous occurrence or combination of multiple individual actions or sub-events.

Therefore, a co-action requiring the posting of the same set or sequence of hashtags is a compound action composed
of multiple homogeneous elements: ⟨hashtag, hashtag, . . .⟩. However, compound co-actions can also be defined with
heterogeneous elements, such as ⟨hashtag, mention⟩ or ⟨URL, mention⟩ [73]. When building coordination networks, the
use of compound actions increases the confidence of labelling a group of users as coordinated, since compound actions

are less likely to occur by chance. However, this approach risks neglecting simpler, milder, or looser forms of coordination.
Lastly, co-handle changes refer to multiple users using the same handle or username at different points in time [103].
After selecting one or more co-actions to identify similar user behaviors, it is necessary to define the corresponding
similarity functions. A similarity function computes the weight 𝑤 𝑗𝑘 of the edges connecting two coordinated users
𝑢 𝑗 and 𝑢𝑘 based on how similar their behaviors are according to the chosen co-action. Independently of the type of
co-action, the majority of works use similarity functions based on the cardinality of the co-action between the two
users [14–18, 28, 32, 41–44, 47–49, 52, 54, 59–62, 65, 92, 94, 96–99, 106, 110, 112, 115, 116, 121, 122, 128, 140, 142, 144–
146, 148, 150, 152, 157]. For example, when using co-hashtags, the similarity function may simply count the number of
times the two users used the same hashtags. Another widely adopted function is the cosine similarity between the two
user vectors [5, 8, 13, 19, 20, 22, 29, 29, 30, 51, 66, 70, 71, 81, 90, 96, 97, 100, 103, 104, 114, 129, 138, 158]. These can be binary

vectors, frequency vectors, or TF-IDF weighted vectors. The latter allows discounting the importance of popular or viral

content, boosting instead the relevance of unpopular items [5, 19, 20, 22, 29, 30, 51, 66, 70, 71, 81, 90, 100, 104, 129, 138].

Depending on the choice of co-action, the previous similarity functions must be preceded by additional processing steps.
For example, the use of co-actions such as co-post, co-image, and co-video involve counting the number of times two
users shared the same content, which severely limits the possibility to detect certain coordinated behaviors. For this
reason, some scholars relaxed this requirement by also considering the posting of similar—as opposed to equal—content.
This solution requires defining additional similarity functions for texts, images, and videos. In literature, text similarity

was computed via correlation [64], cosine similarity of document embeddings [29, 32, 70, 96, 98], Ratcliff/Obershelp

algorithm [102], or Jaccard similarity [48]. All these works first computed similarities between the text of two users’

posts. Then, they set a threshold to select highly similar texts. Finally, they computed user similarities based on the

number of similar texts [32, 48, 96, 98], or as the average of the similarities between the highly similar texts [29, 70].
Analogously, co-image involves a pre-processing step for representing the images with their embeddings [99] or with
RGB color histograms [103]. Then, image similarity is computed via measures such as the Euclidean distance [99]. Finally,

a similarity threshold is applied and user similarity is computed as the cardinality [99] or the Jaccard coefficient [103]

of the sets of similar images.

4.1.3 Network filtering. This optional, yet crucial, step allows to filter out nodes and edges from the coordination
network so as to only retain network structures that convey meaningful and reliable coordination. Independently of the

method used to the achieve this objective, performing network filtering also has the advantage of reducing the size of

the final coordination network, which speeds-up subsequent analyses.

Manuscript submitted to ACM

18

Mannocci et al.

Table 3. Types and characteristics of the time windows and the coordination networks used by network science methods.

reference

type

time window

size

[144–146]
[138]
[18, 22, 65]
[1]
[47]
[17]
[59, 115, 116]
[95]
[3]
[72, 96]
[48, 73, 94]
[103]
[20, 71]
[13]
[81]
[129]
[62]
[28]
[102, 104]
[29, 70]
[41–44, 49, 110, 121]
[14]
[152]
[61]
[32]
[149]
[141]

adjacent
adjacent
adjacent
adjacent
evenly distributed overlapping
evenly distributed overlapping
evenly distributed overlapping
evenly distributed overlapping
evenly distributed overlapping
evenly distributed overlapping
evenly distributed overlapping
evenly distributed overlapping
evenly distributed overlapping
evenly distributed overlapping
evenly distributed overlapping
evenly distributed overlapping
action-driven overlapping
action-driven overlapping
action-driven overlapping
action-driven overlapping
action-driven overlapping
action-driven overlapping
action-driven overlapping
action-driven overlapping
action-driven overlapping
action-driven overlapping
action-driven overlapping

15 min, 1 hour, 6 hour, 1 day
1 day, 1 week
1 week
1 hour, 1 day,
1 sec
from 1 sec to 250 sec
1 min
from 1 min to 30 min
5 min
5 min
5 min
30 min
1 day
2 day
6 hour, 1 week
1 week
from 1 sec to 1 hour
from 1 sec to 11 day
10 sec
10 sec
from 10 sec to 1 min
25 sec
1 min
2 min
1 min, 1 hour, 1 day
1 hour
10 tweets

network

layer(s)

single
single
single
single
single
single
single
single
single
multiple (L=2)
multiple (L=3)
single
single
single
multiple (L=5)
single
single
single
single
single, multiple (L=4)
single
single
single
single
multiple (L=4)
single
single

type

user
user
user
content
user
content
user
user
user
user
user
user
user
user
user
user
user
user
user
user
user
user
user
user
user
user
content

Implementation. There are three main approaches for coordination network filtering: (i) fixed thresholds, (ii) statistical
validation, and (iii) the timings of the co-actions. Methods based on fixed similarity thresholds discard all edges in the
network whose weight 𝑤 < 𝑤th, and all the resulting disconnected nodes [13–15, 17, 18, 20, 22, 25, 32, 41–44, 49, 53, 59–
62, 70, 71, 81, 90–92, 94–96, 98, 99, 102, 103, 106, 116, 121, 141, 144, 149, 152, 157]. The threshold 𝑤th is chosen in such a
way to retain only strongly coordinated users, as they are implicitly considered to be more relevant. Relevant nodes can

also be identified via eigenvector centrality, by pruning those nodes that do not exceed a certain threshold [29, 70].

The similarity and centrality thresholds are typically selected arbitrarily, without a strong underlying theoretical

motivation [100]. Moreover, coordination networks resulting from the analysis of different datasets, or from the use of

different types of co-actions, inevitably result in different edge weight and node centrality distributions. This variability

makes the repeated use of “standard” thresholds unsuitable and mandates in-depth case-by-case analyses.

To alleviate this burden some works leverage 𝑘-nearest neighbors graphs (𝑘-NNG), where two users 𝑢 𝑗 and 𝑢𝑘 are
connected only if 𝑢 𝑗 is among the 𝑘-nearest neighbors of 𝑢𝑘 [8, 16, 67, 98, 99, 148, 149]. This filtering operation retains
only the 𝑘 strongest neighborhoods in the coordination network, thus reducing the emphasis on the edge weight.

However, determining the best value for 𝑘 is also challenging since 𝑘 strongly depends on the characteristics of the

different networks and their layers. Other methods for identifying relevant network structures are those that retain

statistically-meaningful edges, independently of their weight. This approach, used by several recent works [19, 30, 51,

65, 66, 91, 100, 128, 129, 140], is not biased towards fixed arbitrary levels of similarity or coordination, but instead erases

network structures that convey limited information, allowing to focus on meaningful expressions of coordination.

Filtering methods based on the timings of the co-actions use a sequence of time windows of equal size 𝑍 = 𝑡end − 𝑡start.
The filtering typically occurs when computing user similarities, by only retaining the co-actions that occur within the

Manuscript submitted to ACM

Detection and Characterization of Coordinated Online Behavior: A Survey

19

Table 4. Time window types, their parameters, and their effect on valid co-actions. To the right, a sequence of actions occurs at times
𝑡1, . . . , 𝑡6. The same sequence results in different valid co-actions, marked by the (cid:181) lock icon, depending on the time window type.

type

adjacent

evenly distributed overlapping

action driven overlapping

parameters

action sequence and valid co-actions

Z

Z

Z

𝛿

O

(cid:181)

(cid:181)

(cid:181)

(cid:181)

(cid:181)

 (cid:181)

𝑡𝑖

𝑡𝑖+1

𝑡0

𝑡1

𝑡2

𝑡3

𝑡4

𝑡5

𝑡6

time

same time window. In other words, this filter corresponds to adding a further constraint to the actions that determine

the coordination, in that such actions must be temporally close to one another. Table 3 displays the type and length of

the time windows used in literature, along with the type of coordination network built. As shown in Tables 3 and 4,
time windows can be either adjacent [1, 3, 18, 65, 138, 145, 146] or overlapping. Furthermore, overlapping time windows
can be evenly distributed in time [3, 13, 17, 20, 47, 48, 59, 71–73, 81, 94–96, 103, 115, 116, 129], or action-driven—that is,
positioned based on the timings of the actions [14, 28, 29, 32, 41, 41–44, 49, 61, 62, 70, 102, 104, 110, 121, 141, 149, 152].

As shown in Table 4, in the latter case each time window starts when a relevant action occurs. In the former case instead,

the additional parameter step 𝛿 < 𝑍 defines the temporal offset between two consecutive time windows. The amount
of overlap 𝑂 between two consecutive overlapping time windows is thus 𝑂 = 𝑍 − 𝛿. Given a sequence of actions by
two or more users, the choice of time windows and their parameters influence the number of such actions that are
valid co-actions. These are indicated with the (cid:181) lock icon in the example shown in the rightmost column of Table 4.
Let 𝑑 = 𝑡2 − 𝑡1 be the delay with which user 𝑢2 performs an action at time 𝑡2, with respect to the same action that 𝑢1
performed at time 𝑡1. Independently of the type of time window, actions whose 𝑑 > 𝑍 are never considered as co-actions.
Then, actions with 𝑑 ≤ 𝑍 are always co-actions when using action-driven overlapping time windows. Conversely,
actions with 𝑑 ≤ 𝑂 are always co-actions when using evenly distributed overlapping time windows, and can possibly
be co-actions when 𝑂 < 𝑑 ≤ 𝑍 . Instead, with adjacent time windows, also actions that are close in time (i.e., 𝑑 ≪ 𝑍 ) are
occasionally not considered valid co-actions, when they occur across the boundary between two windows, as in the
case of the actions occurred at 𝑡3 and 𝑡4 in the example of Table 4. Therefore, using overlapping rather than adjacent
time windows ensures that no actions close in time are missed. However, it increases the number of windows required

to cover the same time frame, leading to more computational demands. Another critical consideration is the length 𝑍 of

the time window. A larger 𝑍 includes more actions as co-actions, while a shorter one restricts valid co-actions to highly

synchronized events, while also increasing the number of windows and the resulting computations. The choice of 𝑍

also depends on the goal of the analysis. Literature indicates that inauthentic or harmful coordinated behaviors are

highly synchronized and can often be detected with short windows [73, 103], whereas emergent human behaviors that

are typically less orchestrated and loosely synchronized, require longer windows to capture their relaxed temporal

dynamics [100].

A few works departed from the traditional time windows filters presented above. For example, [129, 145, 146] built

a distinct coordination network for each time window. Then, [145, 146] aggregated all networks, each correspond-

ing to a different adjacent time window, by computing the pairwise sums of the network weights. The summation

Manuscript submitted to ACM

20

Mannocci et al.

Table 5. Network science methods for detecting coordinated behavior based on multiplex user networks, where each layer corresponds
to a different co-action. For each group of works we report the considered co-actions, similarity functions, filtering criteria, and the
optional flattening step applied before the community detection method.

reference

action

similarity

[32]
[29, 70]

[52]

[48]
[72]
[73]
[92, 94]

[81]

[96]

share, message, URL, hashtag
retweet, tweet, URL, hashtag
retweet, URL, hashtag,
mention
retweet, text, URL, reply
URL, hashtag
URL, hashtag, mention
URL, hashtag, mention
URL, hashtag, mention, reply,
retweet
URL, tweet

cardinality
cosine similarity TF-IDF
temporal weighted
cardinality
cardinality
cardinality
cardinality
cardinality

filters†
threshold, ADO
threshold, ADO

flattening

community detection

unweighted edge union

Louvain, IPVC‡

EDO
EDO
EDO
EDO

multigraph

sum cardinality

Generalized Leiden

connected components
multi-view clustering
multi-view clustering

Generalized Louvain,
Generalized Infomap

cosine similarity TF-IDF

threshold, EDO

cardinality, cosine similarity threshold, EDO

unweighted edge union Louvain

† EDO: evenly distributed overlapping time window, ADO: action-driven overlapping time window. ‡ IPVC: iterative probabilistic voting consensus

includes a temporal decay weighting scheme that emphasizes the contribution of recent time windows over older ones.

Instead, Tardelli et al. [129] built a multiplex temporal network where the layers are obtained from a sequence of evenly

distributed overlapping time windows. Differently from all other approaches, the multiplex temporal network is then

analyzed as a whole. A further innovation is introduced in [95], which solves an optimization task to select the best

window size 𝑍 in an overlapping time windows setting. Finally, we remark that the filtering methods discussed in this

section can be, and oftentimes are, used in combination for greater efficiency and to further reduce the network size

when analyzing very large datasets.

4.1.4 Community discovery. This step aims to detect a set of coordinated communities 𝑃 = {𝑃1, . . . , 𝑃𝑛 } via commu-
nity discovery on the coordination network. Multiplex networks are either flattened before performing community

discovery [145, 146] or an algorithm suitable for multiplex networks is used [74, 129].

Implementation. Most of the works dealing with single layer networks carry out community discovery with Lou-
vain [16, 17, 26, 47, 59, 61, 62, 65, 90, 91, 95–97, 99, 140, 158], or more broadly via modularity clustering [18]. Other

recent works relied on Leiden [3, 98, 114, 129, 138]. Among the advantages of these approaches is their scalability,

which makes them suitable for the analysis of large networks. In addition, modularity clustering provides a hierarchical

community structure, allowing for analyses at different levels of granularity. The authors of [100, 128] combined

community discovery via Louvain with the iterative application of a progressively increasing edge weight filtering

threshold on the coordination network. As a result of the moving threshold, they studied how the structure and the

properties of the coordinated communities change across the whole spectrum of coordination. Moreover, the moving

threshold implicitly defines a measure for the extent of coordination observed at each iteration, for each coordinated

community, thus providing a continuous score of coordination rather than a binary label. Others proposed a variation

of focal structures analysis to identify influential sets of nodes in a coordination network [145, 146].

An alternative to community discovery is the application of a particularly restrictive set of filters that results in

splitting the coordination network in multiple connected components [14, 15, 20, 41–44, 48, 49, 104, 106, 110, 112, 121,

122, 148, 152, 157]. Since each component is disconnected from the others, this process essentially produces an output

that is similar to that of community discovery, in that it identifies groups of connected and highly coordinated users.

However, the application of very restrictive filters also discards much of the coordination network [100].

Manuscript submitted to ACM

Detection and Characterization of Coordinated Online Behavior: A Survey

21

Table 6. Network science methods for detecting coordinated behavior based on content networks, where nodes are posted contents
and edge weights encode the similarity between the linked contents. For each group of works we report the types of content, similarity
functions, filtering criteria, and the community detection methods.

reference

nodes

similarity

filters†

community detection

[5]
[64]
[141]
[26, 146]
[24, 25]
[99]
[1]

texts
texts
texts, hashtags
hashtags
cashtags
images
comments

cosine similarity TF-DID
text similarity scores
cosine similarity, cardinality
cardinality
cardinality
Euclidean distance
message similarity

† EDO: evenly distributed overlapping time window

threshold
EDO, threshold
threshold
threshold
kNN graph
Louvain

loose strict campaign, cohesive campaign
hierarchical clustering
Louvain

Louvain

The works presented in Table 5 performed community discovery on a multiplex coordination network. Some authors

reduced the complexity of dealing with multiplex networks by flattening them into single layer networks where nodes

and edges are the union of the nodes and edges of each layer. Flattened networks can be either weighted [94] or

unweighted [29, 70, 96], with the latter resulting in the loss of some information. Alternative approaches involve

representing the multiplex network as a single-layer multigraph with labeled parallel edges [48], leveraging multi-view

clustering to combine different network layers [72, 73], or applying Louvain on each layer and an iterative probabilistic

voting consensus algorithm to achieve consensus clustering [32]. Only a couple of works exploit the multiplex version

of Leiden [52], Infomap [81], and Louvain [81], fully exploiting the multimodal structure of the coordination network.

4.1.5 Content networks. A few works built and analyzed networks of content rather than users. After selecting the
initial set of users, these methods build a fully connected network where the nodes are contents posted by the users

(e.g., posts) and edge weights are proportional to the similarity between the linked contents. The community discovery

process on a content network yields clusters of highly similar contents, regarded as proxies for coordination. User and

content networks are interchangeable because each node in a user network can be mapped to the content they published,

and each node in a content network can be mapped to its respective author, allowing for a dual representation of the

same underlying actions. The main characteristics of the works based on content networks are reported in Table 6. Some

works built and analyzed content networks where the nodes were Twitter cashtags [24, 25], or hashtags [26, 146]. Edge

weights were given by the number of co-occurrences of the cashtags and hashtags in the same tweets. The analyses

revealed suspicious clusters of contents that were later linked to online manipulations by coordinated actors. Other

works created a network of similar texts [5, 64] or comments [1] published by multiple users. Lee et al. [64] identify

clusters through connected components and maximal clique analysis. Similarly, [141] constructed two content networks:

one for copypasta tweets, clustering coordinated actors via hierarchical clustering, and another to analyze the temporal

evolution of co-occurring hashtags. [99] built an image similarity network by computing image embeddings and using

Euclidean distance for comparison, then applied Louvain to detect groups of similar images.

4.2 Data mining and machine learning methods

Methods in this category follow the typical knowledge discovery in databases (KDD) analytical process, involving data

collection and preparation, application of data mining and machine learning techniques, validation of the discovered

patterns, and extraction of insights by interpretation of the results. The types of analyzed data include texts [6, 7, 11, 107,

113, 123, 124], images [123], audio [83], interactions [56, 79, 80, 118, 126, 136, 154–156], and temporal data [12, 40, 58].

In terms of machine learning techniques, some works leverage unsupervised approaches (see Table 7) and focus on

Manuscript submitted to ACM

22

Mannocci et al.

Table 7. Data mining and machine learning methods, based on unsupervised learning for detecting coordinated behavior. For each
group of works we report the input types, the machine learning approach, and whether the method takes time into account.

reference

input

machine learning approach

time

[6, 7, 107, 124]
[123]
[11]
[58]
[126]
[12]
[79]
[80]
[33, 34]
[118]
[155]
[56]
[154]
[55]
[120]
[136]
[63]

text streams
text streams, image captions
text, user-content network
daily tweeting activity
hashtags
account creation timestamps
user activities
user activities
URL, hashtag, image, mention
user activities
user activities
user activities
user activities
text, posting time
hashtags
user activities
mention

text stream clustering
text stream clustering
clustering of text and node embeddings
expectation-maximization
peak detection
burst detection
contrast pattern mining
convergent cross mapping
networked Markov chains
temporal point processes, gaussian mixture models
temporal point processes, expectation-maximization
Petri net
outlier detection
text similarity, timings of campaign launch and posting tweets
bayesan model
cluster interactions networks
cluster interactions networks

¸
¸
¸
¸
¸
¸
¸
¸
¸
¸
¸
¸
¸
¸

identifying groups of users exhibiting similar behaviors, while others rely on the availability of labeled data and apply
supervised techniques (see Table 8). These supervised approaches can be further distinguished by their prediction target,
namely user (individual account classification), community (groups of users), network (entire interaction graphs), target
(entities targeted by coordinated actions).

4.2.1 Unsupervised. Unsupervised methods work with unlabelled data and, therefore, do not exploit any knowledge
on the membership of users to coordinated groups. Multiple unsupervised methods [6, 7, 107, 123, 124] are based on

stream clustering algorithms, designed to group similar textual documents into micro-clusters that represent the topics

recently discussed in the stream. The detection of rapidly growing clusters of documents is used to identify inorganic or

orchestrated campaigns by coordinated users. This approach is conceptually similar to the analysis of a content network

of similar documents that includes a time-based filter. A similar approach is also used in [11], where text and node

embeddings are clustered via DBSCAN. In [120], hashtags used by different users are leveraged to perform clustering

via a Bayesian model. In contrast, [63, 136] apply clustering on interaction networks, such as the mention network [63],

or more comprehensive networks incorporating mentions, replies, retweets, textual content, and hashtags [136]. Keller
et al. [58] modeled user daily tweeting activity with a binary matrix whose cells 𝑥 𝑗𝑡 = 1 represent a user 𝑢 𝑗 who
tweeted at least once on day 𝑡, while cells 𝑥 𝑗𝑡 = 0 indicate no tweeting on that day. Then, groups of users with similar
tweeting behaviors are found via expectation-maximization. Here, highly similar tweeting behaviors are considered as

a proxy for coordination. Others modeled the sequence of user activities as temporal point processes. Sharma et al.

[118] proposed the AMDN-HAGE generative model to jointly account for user activities and hidden group behaviours.

The Attentive Mixture Density Network (AMDN) component models observed activity traces as a temporal

point process, while the Hidden Account Group Estimation (HAGE) component models user groups as mixtures

of multiple distributions. The synchronized groups detected by AMDN-HAGE are deemed coordinated and assumed

to be malicious. Similarly, Zhang et al. [155] jointly learned a distribution of user-group assignments based on how

consistent each assignment is to the user embedding space and to some prior knowledge such as temporal logic. Finally,

they used expectation-maximization to cluster the users according to the different distributions.

Manuscript submitted to ACM

Detection and Characterization of Coordinated Online Behavior: A Survey

23

Table 8. Data mining and machine learning methods, based on supervised learning, for detecting coordinated behavior. For each
group of works we report the input types, the machine learning approach, whether the method takes time into account, and the
prediction target.

reference

input

machine learning approach

time

target

[156]
[40]
[113]
[108]
[83]
[4]
[84]
[57]
[88]

user activities
network, temporal, semantic features
text
user activities
metadata, audio transcripts, thumbnails
user activities
co-retweet network
retweet
network, text

representation learning, conditional embedding, neural encoding
outlier detection
peak detection, multiclass classification
classifier
ensemble classification
random weighted walk
graph neural network
retrieval-augmented generation
graph neural network

¸
¸
¸
¸

user
network
community
user, target
target
network
community
network
user

Other works proposed simpler methods or indicators as signals of possible coordinated behavior. Bellutta and Carley

[12] analyze account creation times under the hypothesis that accounts involved in coordinated malicious activities

tend to be created in bursts. They computed the daily histogram of account creations to which they applied a burst

detection algorithm, identifying spikes in account creations by comparing the number of accounts created in a given

day against the average number of daily accounts created in a reference time window. Another simple unsupervised

technique is proposed in [126], where coordination is measured as the extent to which users converge—spontaneously

or in an organized fashion—on the use of certain hashtags. The Gini coefficient, an indicator of inequality, is applied to

the distribution of used hashtags to create time series where saddles close to 0—indicative of low inequality—correspond

to no coordination whereas peaks close to 1—indicative of a situation where all users use the same few hashtags—

correspond to strong coordination. Two alternative techniques are proposed in [79] and [80]. The former leverages

contrast pattern mining to extract anomalous behavior, while the latter uses convergent cross mapping to discover

cause-and-effect relationship and to construct an influence network. Similarly, [33, 34] use a discrete-time stochastic

model to analyze coordinated activity, representing the user behaviors as interacting Markov chains. In [56] social

media interactions are modeled as Petri nets, while in [154] coordination is detected by identifying anomalies in account

sharing behavior. In [127] an exploratory analysis is conducted on YouTube links shared on 4chan.

Supervised. Supervised methods can be categorized based on their prediction target, leading to approaches that

4.2.2
operate at the user, community, network, and target levels.

User. Zhang et al. [156] tackles a binary classification task to distinguish between coordinated and non-coordinated
users that participate in cross-platform campaigns. They leverage information from an aid platform where coordinated
users are known, to detect unknown coordinated users on a target platform. Input data consists of a known coordinated
activity set on the aid platform, plus unknown user activities on the target platform. The relationship between the two

activities are modeled with neural time series encoders before being fed to a multi-layer perceptron for prediction.

In [108] traditional classifiers (e.g., Random Forest) are employed on user- and content-level engagement features to

address to detect both coordinated users and content targeted by coordination. In [88], a similarity network is built

following [70], and multimodal node embeddings—combining one-hot features and text—are fed into a GNN to classify

users as information operation drivers or legitimate accounts.

Community. Saeed et al. [113] focused on attributing coordinated hate attacks to the communities that organized
them. A peak detector identifies an abrupt rise in the comment activity of a YouTube video, a signal of a coordinated

attack. Then, it leverages a trained classifier based on linguistic features from the comments to the video and a set of

Manuscript submitted to ACM

24

Mannocci et al.

Reddit and 4chan communities, identifying the community responsible for each attack based on linguistic patterns and

similarities. In [84], a graph neural network model is exploited to recognize normal and abnormal communities.

Network. A simpler approach is proposed in [40], where a small expert-labeled ground truth of organic and inorganic
campaigns is used to characterize campaigns along network, temporal, and semantic dimensions. Unknown campaigns

are then labeled as coordinated if their indicators fall within the 95% confidence interval of inorganic campaigns and

outside that of organic ones. In [4] a graph classification method based on random weighted walks leverages the density

of local network structures to distinguish coordinated from non-coordinated networks. Kanakaris et al. [57] model

retweet networks as propagation trees, encode them into text via graph prompting, and combine them with content and

similarity-based examples in a RAG framework, enabling an LLM to classify coordinated disinformation campaigns.

Target. In [83], authors propose a system to predict YouTube videos likely to be targeted by coordinated hate attacks,
using features from metadata, transcripts, and thumbnails, and an ensemble classifier trained on previously raided
videos. As previously discussed, the approach in [108] operates at both the user and target levels.

4.3 Discussion

4.3.1 Modeling complex coordination. In Section 2 we highlighted that coordinated online behavior is complex and
multifaceted, often involving various actions across multiple platforms. Consequently, methods that analyze only a

single type of action—particularly single-layer network approaches—risk missing significant coordination activities. To
address this limitation, using multiplex networks and compound actions can offer more comprehensive insights. The
network science framework presented in Section 4.1 supports both single- and multi-layer (i.e., multiplex) networks.

However, few studies considered multiple co-actions and built multiplex networks, as summarized in Table 5. Moreover,

to fully leverage the benefits of multiplex networks, these should not be flattened before running the community

detection algorithm, which must be specifically designed for multiplex networks so as to utilize the multiple layers

effectively [74]. Unfortunately, only a few studies possess these characteristics [29, 32, 70, 72, 94], making the analysis

of coordinated behavior across multiple actions a largely unexplored area of research. Compound co-actions, combining

simpler actions (e.g., a post with both a hashtag and user mention), can enhance detection confidence because they are

less likely to occur by chance [73]. However, this approach is also almost completely unexplored. In conclusion, too

little research has been conducted so far on using multiple co-actions for detecting coordinated online behavior, leaving

the actual advantages of these methods over single-action analysis unclear. Moreover, any potential benefits must be

weighed against the increased complexity and computational costs that they introduce.

4.3.2 Network science vs. machine learning. Most methods for detecting coordinated behavior rely on network science,
offering greater generality and expressiveness than machine learning approaches. They effectively model complex

interactions and relationships, capturing varying degrees of coordination [100], tracking temporal changes [129], and

providing detailed characterizations of coordinated groups [128]. The disadvantage is the computational cost of analyzing

large networks and the requirement for human analysts to interpret results, making them less suitable for being directly

used in automatic decision making systems. A further drawback is their sensitivity to specific parameters, such as those

defining the way in which the timings of user actions are modeled [144], which can significantly impact the obtained

results and for which few guidelines currently exist [95, 129]. Instead, data mining and machine learning methods

often rely on oversimplified assumptions, such as the existence of a sharp binary distinction between coordinated

and non-coordinated actors, which overlooks the nuanced nature of online coordination. This binary approach can

undermine the theoretical and practical reliability of results. Furthermore, these methods face limitations due to the

Manuscript submitted to ACM

Detection and Characterization of Coordinated Online Behavior: A Survey

25

lack of comprehensive labeled datasets needed for training effective models. Despite these challenges, machine learning

methods excel in encoding diverse actions and characteristics of users, and offer outputs that are directly applicable

for automatic decision-making systems, unlike the more complex network science methods. In conclusion, network

science methods are particularly suitable when the goal is an in depth understanding of the studied phenomenon, while

machine learning methods can be used—with due caution—for quick decisions and when scalability is a concern.

4.4 Validation

The scarcity of labeled data limits the development of coordinated behavior detection methods. This constraint hampers

the adoption of supervised approaches, contributing to the predominance of unsupervised techniques, and complicates

both model tuning and evaluation. As a result, many methods are still assessed through post-hoc analyses rather than

standardized quantitative benchmarks. To address this challenge, existing works adopt three main validation strategies.

Characterization-based validation. A common approach consists in validating methods through qualitative or descrip-
tive analyses of the detected behaviors. In this setting, outputs are assessed a posteriori by examining account activity,

temporal patterns, content and socio-linguistic signals, and network structure, to verify their consistency with known

characteristics of coordinated behavior. While this strategy enables exploratory insights, it lacks objective ground truth

and limits reproducibility and comparability across methods. Section 5 is dedicated to the task of characterization.

Public ground-truth datasets. Publicly available datasets can act as ground truth proxies, with some studies constructing
balanced datasets from authoritative repositories6 enabling both training [70] and evaluation [18, 52, 56, 67, 79–
81, 88, 91, 99, 104, 108, 118, 120, 138, 154, 155] of detection methods. However, these datasets are often limited to specific

platforms and coordination types, restricting model generalization.

Simulation-based validation. An alternative strategy consists in evaluating detection methods in controlled simulated
environments, where coordinated behaviors can be explicitly modeled. Early approaches rely on agent-based models

grounded in empirical observations. For instance, Mehta et al. [86] develop a multi-agent simulation of Reddit to

analyze the impact of coordinated activity on recommendation systems, while Jahn et al. [54] design an agent-based

model with heterogeneous agents (e.g., authentic users and coordinated boosters) to generate synthetic data. Other

approaches generate synthetic datasets by injecting controlled anomalous patterns to enable systematic evaluation

across coordination scenarios [107, 158]. Recent work explores large language models (LLMs) to simulate more realistic

and adaptive behaviors. For instance, in [101] LLM-driven agents are used to mimic both organic users and coordinated

actors under different regimes, from implicit alignment to explicit collaboration. Overall, simulation-based validation

offers a flexible framework, though current efforts remain limited in scale and standardization.

5 CHARACTERIZATION OF COORDINATED BEHAVIOR

When the coordination detection method is not integrated into an automated decision-making system, its output may

initiate the characterization task. The aim of this task is to describe each coordinated user, group, or community along

one or more of the defining dimensions outlined in Section 2.5. Characterizing the detected instances of coordination

can also provide valuable information for validating detection results, especially in the absence of ground truth data.

Characterizing coordinated online behavior is a semi-automatic task, as it involves some degree of manual analyses

and observations by human analysts supported by automatically computed indicators that provide information on

the coordinated actors. Table 9 summarizes the main indicators used for characterizing coordinated actors, whose

6https://transparency.x.com/en/reports/moderation-research.html (accessed: 31/07/2024)

Manuscript submitted to ACM

26

Mannocci et al.

Table 9. Indicators used for characterizing coordinated behavior. For each group of indicators we report the works that used them, the
high-level concept implemented, and the defining dimensions of coordination for which the indicators provide
,
information. Table rows are grouped based on the type of information (i.e., user, content, network) leveraged by the indicator.

, or could provide

reference

concept

indicators

auth. harm. orch.

time other

defining dimensions

r
e
s
u

[7, 12, 17, 26, 28, 47, 51, 90, 92, 94–
96, 100, 102, 103, 128, 146, 158]
[28, 49, 51, 64, 65, 90, 95, 100, 115, 118, 128,
152, 155]
[95]
[13, 61, 84, 115]

[15, 25, 26, 41, 55, 58, 59, 64, 110, 115, 116,
126, 138, 140, 142, 146]
[110, 136, 140]
[5, 14, 17, 55, 61, 102, 150]
[12, 13, 15, 20, 25, 26, 29, 58, 61, 80, 90, 91,
95, 97, 100, 113, 118, 122, 136, 140, 142, 145,
146, 149, 155, 155]
[55, 91, 145, 146]
[129, 141]
[16, 44]
[12, 20, 43, 142]
[11, 12, 20, 110, 122, 128, 150]
[51, 84]
[66, 113]
[62, 66, 100, 128, 129]
[20]

t
n
e
t
n
o
c

k
r
o
w
t
e
n

automation

bot scores

moderation

suspended users

username diversity entropy
activity

account creation burstiness

activity

number of posts, retweets, . . .

engagement
timings

number of views, likes, . . .
action time interval

socio-linguistics

repetitiveness
socio-linguistics
news diversity
news reliability
news reliability
manipulation
offensiveness
political bias
fake content

attitudes, concerns, emotions, stances,
topics, words

text similarity scores
topic and hashtag evolution
entropy, Gini coefficient
suspended and blacklisted URLs
NewsGuard and MBFC† scores
propaganda scores
toxicity scores
MBFC† scores, hashtag bias
AI-generated

edge weights

centrality scores

assortativity
clustering coefficient, modularity, density
user influx and outflux, user evolution

[17, 18, 51, 62, 66, 84, 90, 91, 94, 95, 100, 128] coordination
[19, 28, 30, 44, 48, 60, 62, 63, 90, 91, 96, 102,
140]
[18, 25, 90, 100, 149]
[18, 28, 44, 48, 60, 62, 90, 91, 96, 99, 100, 122] cohesiveness
[65, 129]

stationarity

homophily

influence

†: Media Bias/Fact Check

discussion is presented in the remainder of this section. Indicators in the table are grouped based on the information
they leverage, which can be related to (i) users, (ii) content, or (iii) networks, a distinction that has also been adopted in
related analyses of bots [93]. The table also highlights the dimensions of coordination that each indicator addresses.

Full dots indicate dimensions where the indicator has already been applied, while empty dots denote dimensions where

it has potential use that has not yet been explored.

5.1 Authenticity

Authenticity refers to the extent to which users, groups, or communities correctly represent themselves to others on a

platform. As a consequence, inauthenticity is found when an actor misrepresents itself, such as to mislead others on

who they are or what they do. In other words, authenticity is a property of the actors. In literature, the most common
proxy for inauthenticity is an account’s degree of automation, obtained via a bot score [7, 12, 17, 26, 28, 47, 51, 90, 92, 94–
96, 100, 102, 103, 128, 146, 158]. By definition, social bots are accounts that make use of some or full automation [23].

Thus, accounts with a high bot score are likely to be mostly automated. Unfortunately however, while useful, the use of

bot scores as indicators of inauthenticity faces some limitations. First, computing bot scores is a challenging task per se,

and it is prone to errors [93]. Second, not all bots are inauthentic, as there exist some types of self-declared bots that

operate for neutral or benign purposes [23]. Finally and most importantly, there exist multiple types of users that are

Manuscript submitted to ACM

Detection and Characterization of Coordinated Online Behavior: A Survey

27

inauthentic but that do not make use of automation (e.g., trolls, dissidents). Therefore, using bot scores as indicators of

inauthenticity can cause both false positive and false negative errors. In addition to bot scores, some also used username

similarity [95] and bursts of account creations [13, 61, 84, 115] as proxies for inauthenticity. Table 9 also shows that the

few existing indicators of inauthenticity are all based on user information. While this is expected since authenticity

is a property of the actors rather than their actions, we also note that extremely short time intervals between user

actions [5, 14, 17, 55, 61, 102, 150] could be used as a red flag of automation and, by extension, also of inauthenticity.

5.2 Harmfulness

Harmfulness measures the extent to which the actions of the coordinated actors can potentially cause negative

consequences. Hence, the analysis of the actions can provide valuable information about the intent, or potential, for

harm of the coordinated actors. The production or re-sharing of content (e.g., text, images, links) is the most information-

rich type of action and, in fact, nearly all indicators of harmfulness in Table 9 are derived from the analysis of content.

Traditional NLP methods are used to analyze attitudes, concerns, emotions, stances, topics, hashtags, and words, as

these provide useful insights into the intent and aims of coordinated actors [12, 13, 15, 20, 25, 26, 29, 58, 80, 90, 91, 95, 97,

100, 113, 118, 122, 136, 140, 142, 145, 146, 149, 155, 155]. For instance, certain words, negative emotions, and stances can

amplify social discord and polarize public opinion. The prevalence of these indicators is largely due to the abundance of

readily available tools and their ease of application. However, these indicators are often quite generic and consequently

lack substantial power and informativeness. Text similarity scores were also used to identify harmful campaigns that aim

to create false consensus through repeated sharing of similar posts [55, 91, 145, 146]. Other straightforward indicators

of harmfulness are those based on the presence of toxic (i.e., hateful or offensive) [66, 113] or propagandistic [51, 84]

content. A different line of work measured harmfulness in terms of the unreliability of the news shared by coordinated
actors, which was measured via NewsGuard’s7 reliability ratings and Media Bias/Fact Check8 factual reporting and
credibility ratings [11, 12, 20, 110, 122, 128, 150]. Others measured unreliability in terms of suspended and blacklisted

URLs [12, 20, 43, 142]. The fraction of coordinated users that were suspended or banned by a social platform has been

extensively used as an indicator of harmfulness [28, 49, 51, 64, 65, 90, 95, 100, 115, 118, 128, 152, 155]. Finally, the use

of AI generated content may be a signal of potentially harmful activity [20]. This stands out as the only indicator of

harmfulness based on user, rather than content, information. However, we note that harmfulness indicators based on

content moderation lack predictive capabilities and can only be used retrospectively, since moderation actions typically

occur some time after the account have engaged in the harmful activities.

5.3 Orchestration

Orchestration expresses the extent to which the coordination is well-organized, rather than spontaneous and emer-

gent. Since orchestration reflects the level of organization among coordinated actors, its indicators are derived

from coordination networks (Table 9) and typically computed after network-based detection. High coordination

scores are used as proxies for orchestration, under the assumption that tightly synchronized groups are more orga-

nized [17, 18, 51, 62, 66, 84, 90, 91, 94, 95, 100, 128]. Centrality scores measure node importance within a network or

community. Highly central nodes have a greater influence on the dissemination of information, and their presence in

coordinated communities may indicate a structured hierarchy [19, 28, 30, 44, 48, 60, 62, 90, 91, 96, 102, 140]. Conversely,

assortativity is a measure of homophily in a network. Measuring assortativity can help determine whether coordinated

7https://www.newsguardtech.com/ (accessed: 31/07/2024)
8https://mediabiasfactcheck.com/ (accessed: 31/07/2024)

Manuscript submitted to ACM

28

Mannocci et al.

behavior is orchestrated or spontaneous by assessing the extent to which highly connected nodes tend to connect with

other highly connected nodes [18, 25, 90, 100, 149]. For example, high assortativity between nodes with large degree

might indicate a centralized orchestrated structure. Instead, high assortativity between nodes with low degree might

indicate decentralized orchestration, while low assortativity or disassortativity might indicate spontaneous behaviors.

Likewise, low modularity, high density, or high clustering coefficient indicates a tendency for nodes to form tightly-knit

groups, suggesting well-organized and potentially orchestrated behavior [18, 28, 44, 48, 60, 62, 90, 91, 96, 99, 100, 122].

Finally, the time intervals between the actions of coordinated actors can provide information on whether the coordinated

behavior is orchestrated or spontaneous because tightly synchronized actions suggest a higher level of premeditated

organization, whereas more irregular intervals might indicate spontaneous, less structured coordination. The study

of the internal structure and organization of coordinated communities is also relevant for investigating the diverse

strategies of online manipulation. Organized influence campaigns often unfold in distinct ways: some aim to mobilize

pre-existing organic communities, leveraging existing social ties and trust, while others seek to establish new com-

munities controlled by a central entity [125]. Additionally, organic communities can emerge from grassroots efforts,

where users are genuinely motivated by a common goal without external orchestration. These different strategies leave

“network footprints” that can be captured by orchestration indicators [18].

5.4 Time-variance

Time-variance indicators aim at quantifying temporal changes in a wide array of characteristics of the coordinated

actors. These include the number, intent, and behavior of the actors, which may result in changes in the types, timing,

frequency, and intensity of their actions. Many measures can serve as time-variance indicators, including the indicators

previously discussed for the dimensions of authenticity, harmfulness, and orchestration. Indeed, as shown in Table 9, all

indicators for authenticity, harmfulness, and orchestration can potentially be analyzed over time, even if they have

not been already studied in this way yet. However, utilizing a measure as a time-variance indicator requires repeated

and extended monitoring to detect possible changes over time. This requirement for prolonged monitoring poses

an additional challenge compared to other types of indicators, which explains the scarcity of studies that employed

time-variance indicators or that investigated the temporal dynamics of coordinated behavior [129]. The few existing

detailed temporal analyses examined user flows between coordinated communities or the variation of users between

different time windows [65, 129]. Other temporal analyses of user activity can involve examining bursts of account

creations [115], abnormal post or retweet volumes [15, 25, 26, 41, 55, 58, 59, 64, 110, 115, 116, 126, 138, 140, 142, 146], or

inflated engagement metrics, such as the number of views [110, 140]. The analysis of topics and hashtags over time can

reveal the evolution of the narratives promoted or discussed by the coordinated actors [129, 141]. The timing of the

actions, such as the intervals between pairs of actions that result in a co-action, can provide insights into the type of

coordination and strategies employed, which may evolve over time [14, 17, 102].

5.5 Other general indicators

In addition to the indicators that provide information about the four defining dimensions of coordinated behavior, other

general-purpose indicators have also been used. These come in handy to provide additional context on the coordinated

behavior and may be particularly relevant depending on the application context, as in the case of the indicators

of political polarization or bias that are used to characterize coordinated communities involved in online electoral

debates [62, 66, 100, 128, 129]. Political bias was computed based on MBFC scores or by leveraging hashtag polarity.

Analyses of the level of activity of coordinated actors on a platform [15, 25, 26, 41, 55, 58, 59, 64, 110, 115, 116, 126, 138,

Manuscript submitted to ACM

Detection and Characterization of Coordinated Online Behavior: A Survey

29

140, 142, 146], of the engagement they obtain [110, 140], or of the content they produce, can provide additional contextual

information. Regarding the latter, standard socio-linguistic analyses were used to draw insights into the narratives and

stances of coordinated actors [12, 15, 25, 26, 58, 61, 90, 91, 95, 97, 100, 113, 118, 122, 129, 140–142, 145, 146, 155, 155].

Similarly, others considered the diversity of the news shared by the coordinated actors [16, 44] or assessed the presence

of patterns in the timings of their actions [14, 17, 55, 102]. Finally, acknowledging that coordination is a nuanced

and non-binary concept, some studies computed coordination scores, for example based on the edge weights of the

coordination network [17, 18, 51, 62, 63, 66, 90, 91, 94, 95, 100, 128].Analyzing the degree of coordination helps reveal

the level of collaboration, influence, and effectiveness of collective actions within a group.

5.6 Compound indicators

While the previous discussion considered indicators individually, combining multiple indicators can provide deeper

insights by capturing complex interactions. For instance, studies [18, 51, 90, 100, 128] analyze trends and correlations

across dimensions such as coordination, propaganda, moderation, cohesiveness, and automation, showing that coordi-

nated communities can exhibit distinct behaviors. They also highlight that relying on a single indicator may lead to

unreliable assessments, emphasizing the importance of compound indicator approaches [51]. Similarly, others consid-

ered the interplay between coordination, toxicity, and political bias [66]. In [128], a comprehensive characterization

of coordinated communities is proposed using multiple indicators, including coordination, automation, suspensions,

news unreliability, and political bias, visualized via radar charts. Higher scores—and thus larger chart areas—indicate

more suspicious behavior, making the radar area a compound indicator of suspiciousness. This approach highlights the

potential of combining multiple indicators, an area that remains largely underexplored.

5.7 Discussion

Table 9 shows that many and diverse indicators are used to measure harmfulness. These include indicators of hate speech,

toxicity, and propaganda, as well as indicators based on platform moderation decisions. Conversely, inauthenticity

has only been examined through the lens of automation, despite being the focus of many works. From a practical

standpoint, understanding the authenticity of an account is inherently more challenging than assessing its harmfulness,

as authenticity pertains to the nature of the actors rather than their actions. Many online platforms afford users a

significant degree of anonymity, making it difficult to verify their true identities. In contrast, many actions performed

online leave unforgeable traces, which can be more easily analyzed to determine harmful behavior. Despite the challenges

however, future work should focus on developing additional indicators of authenticity. Among the untapped sources of

information are the completeness and credibility of the user profile, the regularity of activity patterns, the duplication or

repetitiveness of posted content, the lack of consistency in language or interests, the authenticity of posted multimedia

content, the cross-platform consistency of profile and behavior, the similarity of profile and behavior to that of previously

moderated accounts, and the verification status, which however should be evaluated differently depending on whether
such status can be purchased on the analyzed platform.9

6 OPEN CHALLENGES AND FUTURE RESEARCH DIRECTIONS

Multiplatform-ness. Some coordinated campaigns unfold simultaneously on multiple platforms, resulting in multiplatform
coordinated behavior [147]. These campaigns exhibit overall similar behaviors, such as the use of campaign-specific

9link.gale.com/apps/doc/A746844400/AONE (accessed: 31/07/2024)

Manuscript submitted to ACM

30

Mannocci et al.

Fig. 9. Distribution of works based on the combination of analyzed
platforms. The vast majority of works analyzed a single platform,
mainly Twitter/X. Only a few works performed cross-platform anal-
yses, represented by multiple connected dots.

Fig. 10. Distribution of works focused on different types
of coordinated behavior, categorized based on the defining
dimensions of authenticity, harmfulness, orchestration, and
time-variance. Vertical bars show the number of works
for each combination of dimensions, while horizontal bars
show the number of works for each individual dimension.
Only combinations covered by 2+ works are shown.

hashtags, with minor variations between platforms. In contrast, cross-platform campaigns involve different platforms
playing distinct roles, with coordinated behavior varying significantly across the involved platforms. For example,

organizers of a targeted hate attack might use private groups on a messaging platform to plan their actions before moving

to the target platform to flood it with hateful comments [55]. Detecting coordination on the planning platform might

involve analyzing group joinings, while on the target platform it could involve examining synchronized commenting.

The example highlights the challenges of multi- and cross-platform analyses, which require extensive data collection,

careful selection of actions or machine learning features for each platform, and identification of the same groups of users
across multiple platforms. While the latter can be mitigated via the analysis of content rather than user networks—as
discussed in Section 4.1.5—the remaining outstanding challenges result in a scarcity of multi- and cross-platform

analyses. Figure 9 shows that most studies analyzed coordinated behavior on Twitter/X, with only a few multiplatform

analyses [11, 32, 52, 55, 81, 97, 98, 110, 113, 156], highlighting that this area still necessitates much investigation.

Temporal variability. Most studies on coordinated behavior incorporate time to some degree, as shown in Tables 3, 7, 8,
and 9. However, the majority of such works only perform superficial temporal analyses. Figure 10 highlights that only a
few works have deeply investigated the temporal dynamics of coordinated behavior, using methods like multiplex tem-
poral networks [129] and temporal point processes [118, 155]. Thus, analyzing temporal dynamics remains a promising
yet relatively unexplored research avenue. Temporal analyses offer numerous advantages, including examining (i) the
temporal stability of coordinated groups, (ii) changes in membership, structure, and actions, and (iii) adaptation to
countermeasures or other stimuli [45]. Further, dynamic analyses seem to yield more accurate results compared to

static ones [129]. However, this approach faces several challenges, such as setting appropriate temporal parameters and

addressing the computational demands resulting from the time-intensive nature of dynamic analyses.

Heterogeneity. The great degree of heterogeneity inherent of coordinated behavior does not only manifests through
temporal variations, but also through the multitude of characteristics that the different instances of coordinated

behaviors exhibit. Figure 10 shows the distribution of studies that addressed specific types of online coordination, based
on the defining dimensions introduced in Section 2.5. As shown by the vertical bars, coordinated harmful inauthentic
and orchestrated behavior is the type of coordination that was studied the most. As discussed in Section 2, this is due

Manuscript submitted to ACM

Detection and Characterization of Coordinated Online Behavior: A Survey

31

to both practical reasons related to the urgency of contrasting online manipulations, as well as to the large body of

work that adopted Facebook’s initial Definition 2.3 of coordinated inauthentic behavior. Almost all the other remaining
combinations involve harmful behavior and static analyses. Figure 10 also shows that authentic spontaneous and harmless
coordinated behavior is completely unstudied. While harmful, inauthentic, and orchestrated behaviors are of particular

practical relevance for content moderation purposes, the study of harmless, authentic, and spontaneous coordination

should not be overlooked as it provides valuable insights into fundamental aspects of online human interactions.

Therefore, the analysis of the less problematic forms of online coordination should be increased in the near future.

Multimodality. Online coordination can involve multiple content modalities, such as text, images, and videos. This
diversity of content types adds complexity to detecting and analyzing coordinated behavior, as each modality has

unique characteristics requiring different analytical techniques. For instance, text-based coordination might involve

analyzing text similarities or hashtags use [28, 140, 142]. Image-based coordination could require image recognition

tasks or computing image similarities [42, 103, 152], while video-based coordination demands techniques like video

content analysis and transcript examination. As shown in Tables 2, 6, 7, 8 however, only a handful of works investigated

modalities other than text [42, 83, 99, 103, 121, 152]. Accounting for and integrating different modalities offers the

potential to capture a more comprehensive picture of coordinated behavior, but also poses new challenges. These

include developing features and methodologies to assess similarities based on multimedia content and addressing

the computational demands of multimodal analyses. Nonetheless, given the rising trend of online platforms centered

around multimedia content, multimodal analyses appear promising and well motivated.

Generative AI The rise of generative AI presents both challenges and opportunities. One potential challenge is the
increased difficulty in detecting coordinated actors that use such techniques to mask their activities. AI is already capable

of producing human-like text with given properties, and increasingly also images, audio, and video [20]. Moreover, it

has already been used to simulate authentic online human behaviors in such a way as to evade detection by existing

systems [93]. Progress in generative AI could thus make it harder to detect future instances of coordinated behavior or

to assess the authenticity of coordinated actors. However, it is still unknown what the effect of these techniques will

be on the landscape of online coordination. At the same time, as discussed in Section 4.4, recent work has begun to

explore LLM-driven agents to simulate coordinated behavior in controlled environments [101]. Looking ahead, these

approaches could enable more realistic and scalable simulations, supporting the development and stress-testing of

detection methods. However, the use of LLMs in this context is still in its early stages, and a systematic understanding

of their capabilities and limitations for modeling coordinated behavior is currently lacking.

Scalability. Large-scale coordinated campaigns can involve tens of thousands of users and millions of interactions,
posing significant computational challenges, especially for methods based on pairwise user similarities. As a result,

some studies analyze only a small fraction of data—sometimes as little as 1% [30, 100]—limiting reliability. Future efforts

should focus on increasing the scalability of current detection methods to handle the vast amounts of data generated
by large-scale campaigns. Possible solutions to this issue can include the use of approximation algorithms to obtain
near-accurate results with reduced computational complexity, or sampling techniques to select representative data
subsets. Additionally, online algorithms can update results incrementally as new data arrives, while graph summarization
techniques can condense large networks while preserving key structural properties.

Validation and formalization. As discussed in Section 4.4, current validation strategies only partially alleviate the lack
of labeled data. The challenge of data availability is expected to intensify as access to platform data continues to decline

in the post-API era [132]. Although some works leverage publicly available repositories to construct ground-truth

Manuscript submitted to ACM

32

Mannocci et al.

datasets [18, 70, 81], these resources remain limited in scope, typically focusing on a single platform or a specific

type of coordinated behavior. This restricts the ability of models to generalize across the diverse manifestations of

coordination, such as those illustrated in Figure 5. At the same time, simulation-based solutions are still underexplored

in the coordinated behavior literature [54, 86, 101]. As discussed in Section 2.3, the field lacks a unified and statistically

grounded definition of coordinated behavior, which limits principled validation. A key challenge is to translate existing

operational definitions into formal, testable frameworks, for instance through appropriate null models capturing baseline

behavior. Such models would enable more robust and comparable assessments across datasets and domains. In this

direction, theory-driven approaches offer a promising path, drawing from socio-psychological models of collective

action [137] and the statistical physics of complex networks [2] to develop more general and interpretable frameworks.

Subjectivity. The existence of many indicators of harmfulness—reported in Table 9—is advantageous from a practical
standpoint. However, this multitude of indicators reflects great variability in how harmfulness has been practically

defined. More broadly, the subjective nature of harmfulness—discussed in Sections 2.4.3 and 2.5.2—presents several

challenges to its assessment. The first of such challenges is the variability with which different stakeholders define

what constitutes harmful behavior, which hinder reaching a consensus on definitions and indicators [31]. Additionally,

perceptions of harmfulness are influenced by cultural and social norms, which differ across individuals, regions, and

communities. Consequently, what is seen as harmful by some might not be perceived the same way by others. Finally,

assessing harmfulness involves evaluating both the intent behind the actions and their impact. While the impact

can sometimes be measured—as with misinformation that leads to real-world violence [141] or that reduces vaccine

uptake [122]—the intent is often hidden or ambiguous, making it difficult to measure accurately. Given that a certain

degree of subjectivity in the assessment of online coordination is inevitable and bound to persist, future works must

prioritize transparency in defining and implementing it, favoring nuanced analyses based on multiple indicators.

Attribution. Detecting coordination, especially in cases where malicious actors aim to remain hidden, is already
challenging. Attributing these instances to the responsible entities is even more difficult. Attribution does not merely

involve identifying the accounts that take part in the coordination, but most importantly uncovering the entities behind

them—such as movements, organizations, or states—and understanding their goals. Several obstacles hinder this process,

including the anonymity afforded by online platforms and the sophisticated techniques used to obfuscate identities,

activities, and intentions. Potential solutions include strengthening the collaboration with platforms, which have access

to more data than what is publicly visible or available via APIs or scraping. Additionally, advanced forensic techniques

and multidisciplinary approaches that combine technical, social, and behavioral analysis are essential. Despite these

solutions, the task will remain daunting and require continuous research and experimentation.

Multidisciplinarity. The study of coordinated behavior is intrinsically multidisciplinary due to the complex interplay
of technical, social, and regulatory factors involved. This multidisciplinary nature is evident in the diversity of the

studies on the subject, which employ a wide array of methods from multiple scientific communities. For instance,

computer scientists and complex systems scholars develop computational methods to detect instances of coordinated

behavior [73, 128, 146]. Social scientists study the emergent behaviors and interactions that lead to massive online

coordination [26, 62], while political scientists analyze the impact of coordinated campaigns on real-world events, such

as elections [17, 100, 152]. The involvement of media and communication experts in understanding the dissemination

of (mis)information further highlights the multidisciplinary scope [44, 121]. In this context, multidisciplinarity is both a

challenge and an opportunity. Challenges arise from the need to coordinate efforts among various scientific communities

and to organize and keep track of the extensive body of work on the subject—a task for which this survey aims to

Manuscript submitted to ACM

Detection and Characterization of Coordinated Online Behavior: A Survey

33

provide a contribution. In spite of the challenges however, the comprehensive understanding of the phenomenon and

the effective mitigation of its nefarious instances can only be achieved through the collaboration between diverse

stakeholders, such as scholars, platform operators, policymakers, and civil society organizations.

Ethical dilemmas. Research on coordinated online behavior also faces some ethical dilemmas. The process of
collecting and analyzing online data involves monitoring user interactions and behaviors, which can raise concerns

about surveillance and consent. The inherent subjectivity of coordinated behavior leads to additional challenges, as

certain coordinated actions may be punished on some platforms while being tolerated on others [31], resulting in

imbalanced interventions and potentially unfair decisions. Characterizing coordinated actors further complicates

matters, as this requires assessing the authenticity and harmfulness of actors who might have strong motivations—such

as social and political reasons [61, 126]—for remaining anonymous, raising privacy concerns. Additionally, developing

methods to detect coordinated actors presents risks as these tools could be misused to silence certain groups or minorities,

thereby selectively threatening freedom of expression. Ultimately, these issues demand that great attention to ethical

and normative considerations should be devoted in future research.

7 CONCLUSIONS

Coordination is a fundamental dynamic of human behavior and its study holds great theoretical significance and

numerous practical implications. Theoretically, understanding coordinated online behavior contributes to shedding

light on social dynamics, group formation, and collective action. Practically, this research is pivotal in combating

online manipulations, such as disinformation campaigns and orchestrated hate attacks, and fostering more inclusive

online spaces that promote genuine cooperation and constructive discourse. However, the field faces several significant

challenges, including the complexity of multimodal and cross-platform analyses, the opportunities and perils of

generative AI, the scarcity of labeled data, the subjectivity and ethical dilemmas inherent to the evaluation of coordinated

behavior. These diverse challenges, coupled with the broad interest in the topic, highlight the need for multidisciplinary

efforts from diverse research communities. In the coming years, these efforts should aim to develop a comprehensive

array of datasets, methods, and studies to better understand and address this complex and dynamic phenomenon.

REFERENCES

[1] Md Sayeed Al-Zaman. 2025. Coordinated Computational Propaganda: Exploring Social Bot Activities During the July Revolution of Bangladesh.

Social Science Computer Review (2025).

[2] Réka Albert and Albert-László Barabási. 2002. Statistical mechanics of complex networks. Reviews of modern physics 74, 1 (2002), 47.
[3] Iuliia Alieva, Lynnette H. X. Ng, and Kathleen M. Carley. 2022. Investigating the spread of Russian disinformation about biolabs in Ukraine on

Twitter using social network analysis. In IEEE BigData. 1770–1775.

[4] Atul Anand Gopalakrishnan, Jakir Hossain, Tuğrulcan Elmas, and Ahmet Erdem Sarıyüce. 2025. Density-Aware Walks for Coordinated Campaign

Detection. In ECML-PKDD. 283–298.

[5] Despoina Antonakaki and Sotiris Ioannidis. 2026. Coordinated Information Dissemination on Telegram and Reddit During Political Turbulence: A

Case Study of Venezuela in Global News Channels. arXiv:2602.13333

[6] Dennis Assenmacher, Lena Adam, Heike Trautmann, and Christian Grimme. 2020. Towards real-time and unsupervised campaign detection in

social media. In AAAI FLAIRS. 303–307.

[7] Dennis Assenmacher, Lena Clever, Janina S. Pohl, Heike Trautmann, and Christian Grimme. 2020. A two-phase framework for detecting

manipulation campaigns in social media. In HCII. 201–214.

[8] David Axelrod and John Paolillo. 2025. Structure and Context of Retweet Coordination in the 2022 US Midterm Elections. arXiv:2501.11165
[9] Helmy H. Baligh. 1986. Decision rules and transactions, organizations and markets. Management Science 32, 11 (1986), 1480–1491.
[10] Helmy H. Baligh and Richard M. Burton. 1981. Describing and designing organizational structures and processes. International Journal of Policy

Analysis and Information Systems 5, 4 (1981), 251–266.

Manuscript submitted to ACM

34

Mannocci et al.

[11] Fabio Barbero, Sander op den Camp, et al. 2023. Multi-modal embeddings for isolating cross-platform coordinated information campaigns on social

media. In MISDOOM. 14–28.

[12] Daniele Bellutta and Kathleen M. Carley. 2023. Investigating coordinated account creation using burst detection and network analysis. Journal of

Big Data 10, 1 (2023), 1–17.

[13] Leonardo Blas, Diya Saraf, Tanishq Salkar, Nora Adadurova, Luca Luceri, and Emilio Ferrara. 2025. Large-scale detection of multilingual coordinated

activity on Telegram. npj Complexity 2, 1 (2025), 33.

[14] D. A. Broniatowski. 2021. Towards statistical foundations for detecting coordinated inauthentic behavior on Facebook. Technical Report. Institute for

Data, Democracy and Politics, The George Washington University.

[15] Keith Burghardt, Ashwin Rao, Georgios Chochlakis, Baruah Sabyasachee, Siyi Guo, Zihao He, Andrew Rojecki, Shrikanth Narayanan, and Kristina

Lerman. 2024. Socio-linguistic characteristics of coordinated inauthentic accounts. In AAAI ICWSM, Vol. 18. 164–176.

[16] Cheng Cao, James Caverlee, Kyumin Lee, Hancheng Ge, and Jin-Wook Chung. 2015. Organic or organized?: Exploring URL sharing behavior. In

ACM CIKM. 513–522.

[17] Victor Chomel, Maziyar Panahi, and David Chavalarias. 2023. Manipulation during the French presidential campaign: Coordinated inauthentic

behaviors and astroturfing analysis on text and images. In CNA. 121–134.

[18] Lorenzo Cima, Lorenzo Mannocci, Marco Avvenuti, Maurizio Tesconi, and Stefano Cresci. 2024. Coordinated behavior in information operations

on Twitter. IEEE Access 11 (2024), 61568–61585.

[19] Matteo Cinelli, Stefano Cresci, Walter Quattrociocchi, Maurizio Tesconi, and Paola Zola. 2022. Coordinated inauthentic behavior and information

spreading on Twitter. Decision Support Systems 160 (2022), 113819.

[20] Federico Cinus, Marco Minici, Luca Luceri, and Emilio Ferrara. 2025. Exposing cross-platform coordinated inauthentic activity in the run-up to the

2024 us election. In ACM WWW. 541–559.

[21] Aaron Clauset, Mark EJ Newman, and Cristopher Moore. 2004. Finding community structure in very large networks. Physical Review E 70, 6 (2004),

066111.

[22] Carlo Colizzi, Antonio Alessio Della Sala, Giuseppe Fenza, and Lukasz Gajewski. 2025.

Investigating Coordinated Inauthentic Behavior on

Alternative Platforms During the 2024 U.S. Election. In AAAI ICWSM.

[23] Stefano Cresci. 2020. A decade of social bot detection. Commun. ACM 63, 10 (2020), 72–83.
[24] Stefano Cresci, Fabrizio Lillo, Daniele Regoli, Serena Tardelli, and Maurizio Tesconi. 2018. $FAKE: Evidence of spam and bot activity in stock

microblogs on Twitter. In AAAI ICWSM. 580–583.

[25] Stefano Cresci, Fabrizio Lillo, Daniele Regoli, Serena Tardelli, and Maurizio Tesconi. 2019. Cashtag Piggybacking: Uncovering spam and bot activity

in stock microblogs on Twitter. ACM Transactions on the Web 13, 2 (2019), 11:1–11:27.

[26] Adya Danaditya, Lynnette H. X. Ng, and Kathleen M. Carley. 2022. From curious hashtags to polarized effect: Profiling coordinated actions in

Indonesian Twitter discourse. Social Network Analysis and Mining 12, 1 (2022), 105.

[27] Saloni Dash and Tanu Mitra. 2024. Decoding The Playbook: Multi-Modal Characterization of Coordinated Influence Operations on Indian Social

Media. ACM Journal on Computing and Sustainable Societies (2024).

[28] Bart De Clerck, Juan Carlos Fernandez Toledano, Filip Van Utterbeeck, and Luis EC Rocha. 2024. Detecting coordinated and bot-like behavior in

Twitter: the Jürgen Conings case. EPJ Data Science 13, 1 (2024), 40.

[29] Priyanka Dey, Luca Luceri, and Emilio Ferrara. 2024. Coordinated activity modulates the behavior and emotions of organic users: A case study on

tweets about the Gaza conflict. In ACM WWW. 682–685.

[30] Niccolò Di Marco, Sara Brunetti, Matteo Cinelli, and Walter Quattrociocchi. 2025. Post-hoc evaluation of nodes influence in information cascades:

The case of coordinated accounts. ACM Transactions on the Web 19, 2 (2025), 1–19.

[31] Evelyn Douek. 2020. What does “coordinated inauthentic behaviour” actually mean? https://slate.com/technology/2020/07/coordinated-inauthentic-

behavior-facebook-twitter.html. (accessed: 31/07/2024).

[32] Auriant Emeric and Chomel Victor. 2023. Interpretable cross-platform coordination detection on social networks. In CNA. 143–155.
[33] Keeley Erhardt and Dina Albassam. 2023. Detecting the hidden dynamics of networked actors using temporal correlations. In ACM WWW.

1214–1217.

[34] Keeley Erhardt and Alex Pentland. 2024. Hidden messages: mapping nations’ media campaigns. Computational and Mathematical Organization

Theory 30, 2 (2024), 161–172.

[35] Facebook. 2018. Coordinated inauthentic behavior explained. https://about.fb.com/news/2018/12/inside-feed-coordinated-inauthentic-behavior/.

(accessed: 31/07/2024).

[36] Facebook. 2019. How we respond to inauthentic behavior on our platforms: Policy update. https://about.fb.com/news/2019/10/inauthentic-

behavior-policy-update/. (accessed: 31/07/2024).

[37] Facebook. 2019. Inauthentic behavior. https://transparency.fb.com/policies/community-standards/inauthentic-behavior/. (accessed: 31/07/2024).
[38] Facebook. 2021. Advancing our policies on online bullying and harassment. https://about.fb.com/news/2021/10/advancing-online-bullying-

harassment-policies/. (accessed: 31/07/2024).

[39] Facebook. 2021. Removing new types of harmful networks. https://about.fb.com/news/2019/10/inauthentic-behavior-policy-update/. (accessed:

31/07/2024).

Manuscript submitted to ACM

Detection and Characterization of Coordinated Online Behavior: A Survey

35

[40] Camille Francois, Vladimir Barash, and John Kelly. 2023. Measuring coordinated versus spontaneous activity in online social movements. New

Media & Society 25, 11 (2023), 3065–3092.

[41] Piyush Ghasiya and Kazutoshi Sasahara. 2022. Rapid sharing of Islamophobic hate on Facebook: The case of the Tablighi Jamaat controversy.

Social Media + Society 8, 4 (2022).

[42] Fabio Giglietto, Giada Marino, Roberto Mincigrucci, and Anna Stanziano. 2023. A workflow to detect, monitor, and update lists of coordinated

social media accounts across time: The case of the 2022 Italian election. Social Media + Society 9, 3 (2023).

[43] Fabio Giglietto, Nicola Righetti, Luca Rossi, and Giada Marino. 2020. Coordinated link sharing behavior as a signal to surface sources of problematic

information on Facebook. In ACM SMSociety. 85–91.

[44] Fabio Giglietto, Nicola Righetti, Luca Rossi, and Giada Marino. 2020. It takes a village to manipulate the media: Coordinated link sharing behavior

during 2018 and 2019 Italian elections. Information, Communication & Society 23, 6 (2020), 867–891.

[45] Fabio Giglietto, Massimo Terenzi, Giada Marino, Nicola Righetti, and Luca Rossi. 2020. Adapting to mitigation efforts: Evolving strategies of

coordinated link sharing on Facebook. SSRN:3775469

[46] Google. 2020. Updates about government-backed hacking and disinformation. https://blog.google/threat-analysis-group/updates-about-

government-backed-hacking-and-disinformation/. (accessed: 31/07/2024).

[47] Timothy Graham, Axel Bruns, Guangnan Zhu, and Rod Campbell. 2020. Like a virus: The coordinated spread of coronavirus disinformation. Technical

Report. Centre for Responsible Technology, The Australia Institute.

[48] Timothy Graham, Sam Hames, and Elizabeth Alpert. 2024. The coordination network toolkit: A framework for detecting and analysing coordinated

behaviour on social media. Journal of Computational Social Science 7, 2 (2024), 1139–1160.

[49] Anatoliy Gruzd, Philip Mai, and Felipe B. Soares. 2022. How coordinated link sharing behavior and partisans’ narrative framing fan the spread of

COVID-19 misinformation and conspiracy theories. Social Network Analysis and Mining 12, 1 (2022), 118.

[50] Chris Hays, Zachary Schutzman, Manish Raghavan, Erin Walk, and Philipp Zimmer. 2023. Simplistic collection and labeling practices limit the

utility of benchmark datasets for twitter bot detection. In ACM WWW. 3660–3669.

[51] Kristina Hristakieva, Stefano Cresci, Giovanni Da San Martino, Mauro Conti, and Preslav Nakov. 2022. The spread of propaganda by coordinated

communities on social media. In ACM WebSci. 191–201.

[52] Letizia Iannucci, Elisa Muratore, Antonis Matakos, and Mikko Kivelä. 2025. Detecting Coordinated Activities Through Temporal, Multiplex, and

Collaborative Analysis. arXiv:2512.19677

[53] Laura Jahn and Rasmus K. Rendsvig. 2023. Towards detecting inauthentic coordination in Twitter likes data. arXiv:2305.07384
[54] Laura Jahn, Rasmus K. Rendsvig, and Jacob Stærk-Østergaard. 2023. Detecting coordinated inauthentic behavior in likes on social media: Proof of

concept. arXiv:2305.07350

[55] Maurice Jakesch, Kiran Garimella, Dean Eckles, and Mor Naaman. 2021. Trend alert: A cross-platform organization manipulated Twitter trends in

the Indian general election. In ACM CSCW. 1–19.

[56] Anna Kalenkova, Lewis Mitchell, and Ethan Johnson. 2025. Discovering Coordinated Processes From Social Online Networks. arXiv:2506.12988
[57] Nikos Kanakaris, Heng Ping, Xiongye Xiao, Nesreen K Ahmed, Luca Luceri, Emilio Ferrara, and Paul Bogdan. 2025. Network-informed Prompt

Engineering against Organized Astroturf Campaigns under Extreme Class Imbalance. In ACM WWW. 2651–2660.

[58] Franziska B. Keller, David Schoch, Sebastian Stier, and JungHwan Yang. 2017. How to manipulate social media: Analyzing political astroturfing

using ground truth data from South Korea. In AAAI ICWSM. 564–567.

[59] Franziska B. Keller, David Schoch, Sebastian Stier, and JungHwan Yang. 2020. Political astroturfing on Twitter: How to coordinate a disinformation

campaign. Political Communication 37, 2 (2020), 256–280.

[60] Baris Kirdemir, Oluwaseyi Adeliyi, and Nitin Agarwal. 2022. Towards characterizing coordinated inauthentic behaviors on YouTube. In ROMCIR.

100–116.

[61] Aytalina Kulichkina, Paul Balluff, Nicola Righetti, and Annie Waldherr. 2026. Connective action and digital repression during China’s COVID-19

protests: a computational analysis of multilingual coordinated activity on Twitter. EPJ Data Science (2026).

[62] Aytalina Kulichkina, Nicola Righetti, and Annie Waldherr. 2025. Protest and repression on social media: Pro-Navalny and pro-government

mobilization dynamics and coordination patterns on Russian Twitter. New media & Society 27, 9 (2025), 5433–5454.

[63] Daria Kuznetsova. 2025. Amplifying the regime: identifying coordinated activity of pro-government Telegram channels in Russia and Belarus.

Journal of Information Technology & Politics (2025), 1–17.

[64] Kyumin Lee, James Caverlee, Zhiyuan Cheng, and Daniel Z. Sui. 2013. Campaign extraction from social media. ACM Transactions on Intelligent

Systems and Technology 5, 1 (2013), 9:1–9:28.

[65] Renan S. Linhares, José M. Rosa, Carlos H. G. Ferreira, Fabricio Murai, Gabriel Nobre, and Jussara Almeida. 2022. Uncovering coordinated

communities on Twitter during the 2020 US election. In IEEE/ACM ASONAM. 80–87.

[66] Edoardo Loru, Matteo Cinelli, Maurizio Tesconi, and Walter Quattrociocchi. 2024. The influence of coordinated behavior on toxicity. Online Social

Networks and Media 43 (2024), 100289.

[67] Edoardo Loru, Niccolò Di Marco, Matteo Cinelli, and Walter Quattrociocchi. 2025. A Compression-Based Approach to Detecting Automated and

Coordinated Behavior on Social Media. ACM Transactions on Knowledge Discovery from Data 20, 2 (2025), 25 pages.

[68] Lorenzo Lucchini, Luca M. Aiello, Laura Alessandretti, Gianmarco De Francisci Morales, Michele Starnini, and Andrea Baronchelli. 2022. From

Reddit to Wall Street: The role of committed minorities in financial collective action. Royal Society Open Science 9, 4 (2022), 211488.

Manuscript submitted to ACM

36

Mannocci et al.

[69] Luca Luceri, Silvia Giordano, and Emilio Ferrara. 2020. Detecting troll behavior via inverse reinforcement learning: A case study of Russian trolls

in the 2016 US election. In AAAI ICWSM. 417–427.

[70] Luca Luceri, Valeria Pantè, Keith Burghardt, and Emilio Ferrara. 2024. Unmasking the Web of deceit: Uncovering coordinated activity to expose

information operations on Twitter. In ACM WWW. 2530–2541.

[71] Luca Luceri, Tanishq Vijay Salkar, Ashwin Balasubramanian, Gabriela Pinto, Chenning Sun, and Emilio Ferrara. 2025. Coordinated Inauthentic

Behavior on TikTok: Challenges and Opportunities for Detection in a Video-First Ecosystem. arXiv:2505.10867

[72] Thomas Magelinski and Kathleen M. Carley. 2020. Detecting coordinated behavior in the Twitter campaign to reopen America. Technical Report.

School of Computer Science, Carnegie Mellon University.

[73] Thomas Magelinski, Lynnette H. X. Ng, and Kathleen Carley. 2022. A synchronized action framework for detection of coordination on social

media. Journal of Online Trust and Safety 1, 2 (2022).

[74] Matteo Magnani, Obaida Hanteer, Roberto Interdonato, Luca Rossi, and Andrea Tagarelli. 2021. Community detection in multiplex networks. ACM

Computing Surveys (CSUR) 54, 3 (2021), 1–35.

[75] Thomas W. Malone. 1987. Modeling coordination in organizations and markets. Management Science 33, 10 (1987), 1317–1332.
[76] Thomas W. Malone. 1988. What is coordination theory? Technical Report 182. Massachusetts Institute of Technology (MIT), Sloan School of

Management.

[77] Thomas W. Malone and Kevin Crowston. 1990. What is coordination theory and how can it help design cooperative work systems?. In ACM CSCW.

357–370.

[78] Thomas W. Malone and Stephen A. Smith. 1988. Modeling the performance of organizational structures. Operations Research 36, 3 (1988), 421–436.
[79] Isura Manchanayaka, Zainab Zaidi, Shanika Karunasekera, and Christopher Leckie. 2024. Identifying coordinated activities on online social

networks using contrast pattern mining. In 2024 International Joint Conference on Neural Networks (IJCNN). IEEE, 1–9.

[80] Isura Manchanayaka, Zainab Razia Zaidi, Shanika Karunasekera, and Christopher Leckie. 2025. Using causality to infer coordinated attacks in

social media. In Proceedings of the International AAAI Conference on Web and Social Media, Vol. 19. 1176–1189.

[81] Lorenzo Mannocci, Stefano Cresci, Matteo Magnani, Anna Monreale, and Maurizio Tesconi. 2026. Multimodal coordinated online behavior:

Trade-offs and strategies. Information Sciences (2026), 123125.

[82] Lorenzo Mannocci, Stefano Cresci, Anna Monreale, Athina Vakali, and Maurizio Tesconi. 2022. MulBot: Unsupervised bot detection based on

multivariate time series. In IEEE BigData. 1485–1494.

[83] Enrico Mariconti, Guillermo Suarez-Tangil, Jeremy Blackburn, Emiliano De Cristofaro, Nicolas Kourtellis, Ilias Leontiadis, Jordi L. Serrano, and
Gianluca Stringhini. 2019. “You Know What to Do”: Proactive detection of YouTube videos targeted by coordinated hate attacks. In ACM CSCW.
1–21.

[84] Hodaka Matsuzaki, Isao Karube, and Junichi Hirayama. 2025. EDCOC: Early Detection of Coordinated Online Community Using Graph Neural

Networks. In IEEE/ACM ASONAM. 348–362.

[85] Michele Mazza, Guglielmo Cola, and Maurizio Tesconi. 2022. Ready-to-(ab) use: From fake account trafficking to coordinated inauthentic behavior

on Twitter. Online Social Networks and Media 31 (2022), 100224.

[86] Swapneel S. Mehta, Atilim G. Baydin, Bogdan State, Richard Bonneau, Jonathan Nagler, and Philip Torr. 2022. Estimating the impact of coordinated

inauthentic behavior on content recommendations in social networks. In AI4ABM.

[87] Miriam Milzner, Daniel Thiele, and Baoning Gong. 2025. Just the tip of the iceberg? State of the art of coordinated social media manipulation

research. Information, Communication & Society (2025), 1–20.

[88] Marco Minici, Luca Luceri, Francesco Fabbri, and Emilio Ferrara. 2025. IOHunter: Graph foundation model to uncover online information operations.

In AAAI, Vol. 39. 28258–28266.

[89] Monica Murero. 2023. Coordinated inauthentic behavior: An innovative manipulation tactic to amplify COVID-19 anti-vaccine communication

outreach via social media. Frontiers in Sociology 8 (2023), 28.

[90] Kumari Neha, Vibhu Agrawal, Saurav Chhatani, Rajesh Sharma, Arun Balaji Buduru, and Ponnurangam Kumaraguru. 2024. Understanding
coordinated communities through the lens of protest-centric narratives: A case study on #CAA protest. In AAAI ICWSM, Vol. 18. 1123–1133.
[91] Kin W. Ng and Adriana Iamnitchi. 2023. Coordinated information campaigns on social media: A multifaceted framework for detection and analysis.

In MISDOOM. 103–118.

[92] Lynnette H. X. Ng, Mihovil Bartulovic, and Kathleen Carley. 2024. Tiny-botbuster: Identifying automated political coordination in digital campaigns.

In SBP-BRiMS. 25–34.

[93] Lynnette H. X. Ng and Kathleen Carley. 2025. A global comparison of social media bot and human characteristics. Scientific Reports 15, 1 (2025),

10973.

[94] Lynnette H. X. Ng and Kathleen M. Carley. 2022. A combined synchronization index for grassroots activism on social media. arXiv:2212.13221
[95] Lynnette H. X. Ng and Kathleen M. Carley. 2022. Online coordination: Methods and comparative case studies of coordinated groups across four

events in the United States. In ACM WebSci. 12–21.

[96] Lynnette H. X. Ng and Kathleen M Carley. 2023. Do you hear the people sing? Comparison of synchronized URL and narrative themes in 2020 and

2023 French protests. Frontiers in Big Data 6 (2023), 1343108.

[97] Lynnette H. X. Ng, Iain J. Cruickshank, and Kathleen M. Carley. 2022. Cross-platform information spread during the January 6th Capitol riots.

Social Network Analysis and Mining 12, 1 (2022), 133.

Manuscript submitted to ACM

Detection and Characterization of Coordinated Online Behavior: A Survey

37

[98] Lynnette H. X. Ng, Iain J. Cruickshank, and Kathleen M. Carley. 2023. Coordinating narratives framework for cross-platform analysis in the 2021

US Capitol riots. Computational and Mathematical Organization Theory 29, 3 (2023), 470–486.

[99] Lynnette H. X. Ng, J. D. Moffitt, and Kathleen M. Carley. 2022. Coordinated through a Web of images: Analysis of image-based influence operations

from China, Iran, Russia, and Venezuela. arXiv:2206.03576

[100] Leonardo Nizzoli, Serena Tardelli, Marco Avvenuti, Stefano Cresci, and Maurizio Tesconi. 2021. Coordinated behavior on social media in 2019 UK

General Election. In AAAI ICWSM. 443–454.

[101] Gian Marco Orlando, Jinyi Ye, Valerio La Gatta, Mahdi Saeedi, Vincenzo Moscato, Emilio Ferrara, and Luca Luceri. 2025. Emergent coordinated

behaviors in networked LLM agents: Modeling the strategic dynamics of information operations. arXiv:2510.25003

[102] Diogo Pacheco, Alessandro Flammini, and Filippo Menczer. 2020. Unveiling coordinated groups behind White Helmets disinformation. In ACM

WWW. 611–616.

[103] Diogo Pacheco, Pik-Mai Hui, Christopher Torres-Lugo, Bao T. Truong, Alessandro Flammini, and Filippo Menczer. 2021. Uncovering coordinated

networks on social media: Methods and case studies. In AAAI ICWSM. 455–466.

[104] Valeria Pantè, David Axelrod, Alessandro Flammini, Filippo Menczer, Emilio Ferrara, and Luca Luceri. 2025. Beyond Interaction Patterns: Assessing

Claims of Coordinated Inter-State Information Operations on Twitter/X. In ACM WWW. 1234–1238.

[105] Himangshu Paul and Alexander Nikolaev. 2021. Fake review detection on online E-commerce platforms: a systematic literature review. Data

Mining and Knowledge Discovery 35, 5 (2021), 1830–1881.

[106] Preston Piercey, Roger Pearce, and Nate Veldt. 2023. Coordinated Botnet Detection in Social Networks via Clustering Analysis. In ICPP. 192–196.
[107] Janina Pohl, Dennis Assenmacher, Moritz V. Seiler, Heike Trautmann, and Christian Grimme. 2022. Artificial social media campaign creation for

benchmarking and challenging detection approaches. In AAAI ICWSM.

[108] Manita Pote, Tuğrulcan Elmas, Alessandro Flammini, and Filippo Menczer. 2025. Coordinated Reply Attacks in Influence Operations: Characteriza-

tion and Detection. In AAAI ICWSM, Vol. 19. 1586–1598.

[109] Reddit. 2022. 2022 Transparency report. https://www.redditinc.com/policies/2022-transparency-report/. (accessed: 31/07/2024).
[110] Nicola Righetti, Fabio Giglietto, Azade E. Kakavand, Aytalina Kulichkina, Giada Marino, and Massimo Terenzi. 2022. Political advertisement and
coordinated behavior on social media in the lead-up to the 2021 German federal elections. Dusseldorf: Media Authority of North Rhine-Westphalia
(2022).

[111] Ronald E Robertson. 2022. Uncommon yet consequential online harms. Journal of Online Trust and Safety 1, 3 (2022).
[112] Richard Rogers and Nicola Righetti. 2025. Coordinated inauthentic behaviour on Facebook? A typology of manufactured attention. Platforms &

Society 2 (2025).

[113] Mohammad H. Saeed, Kostantinos Papadamou, et al. 2024. TUBERAIDER: Attributing coordinated hate attacks on YouTube videos to their source

communities. In AAAI ICWSM, Vol. 18. 1354–1366.

[114] Elisa Sartori, Serena Tardelli, Maurizio Tesconi, Mauro Conti, Alessandro Galeazzi, Stefano Cresci, Giovanni Da San Martino, et al. 2025. Insights

into using temporal coordinated behaviour to explore connections between social media posts and influence. In EMNLP. 24392–24404.

[115] Marcel Schliebs, H. Bailey, J. Bright, and P. N. Howard. 2021. China’s inauthentic UK Twitter diplomacy: A coordinated network amplifying PRC

diplomats. Technical Report. Programme on Democracy and Technology, Oxford University.

[116] David Schoch, Franziska B. Keller, Sebastian Stier, and JungHwan Yang. 2022. Coordination patterns reveal online political astroturfing across the

world. Scientific Reports 12, 1 (2022), 4572.

[117] Ozgur Can Seckin, Manita Pote, Alexander C Nwala, Lake Yin, Luca Luceri, Alessandro Flammini, and Filippo Menczer. 2025. Labeled datasets for

research on information operations. In AAAI ICWSM, Vol. 19. 2567–2574.

[118] Karishma Sharma, Yizhou Zhang, Emilio Ferrara, and Yan Liu. 2021. Identifying coordinated accounts on social media through hidden influence

and group behaviours. In ACM SIGKDD. 1441–1451.

[119] Christophe Sibertin-Blanc, Frédéric Amblard, and Matthias Mailliard. 2005. A coordination framework based on the sociology of organized action.

In AAMAS. 3–17.

[120] D Hudson Smith, Carl Ehrett, and Patrick Warren. 2025. Unsupervised detection of coordinated information operations in the wild. EPJ Data

Science 14, 1 (2025), 26.

[121] Felipe B. Soares. 2023. From sharing misinformation to debunking it: How coordinated image text sharing behaviour is used in political campaigns

on Facebook. In MISDOOM. 45–59.

[122] Yunya Song, Yin Zhang, Sheng Zou, Xian Yang, and Qintao Huang. 2025. The spread of pro-and anti-vaccine views by coordinated communities

on facebook during COVID-19 pandemic. Journal of Computational Social Science 8, 4 (2025), 98.

[123] Lucas Stampe, Janina Pohl, and Christian Grimme. 2023. Towards multimodal campaign detection: Including image information in stream clustering

to detect social media campaigns. In MISDOOM. 144–159.

[124] Lucas Stampe, Janina L¨"utke Stockdiek, Britta Grimme, and Christian Grimme. 2024. Benchmarking Sentence Embeddings in Textual Stream

Clustering with Applications to Campaign Detection. In IEEE IJCNN. 1–8.

[125] Kate Starbird, Ahmer Arif, and Tom Wilson. 2019. Disinformation as collaborative work: Surfacing the participatory nature of strategic information

operations. In ACM CSCW. 127:1–127:26.

[126] Zachary C. Steinert-Threlkeld, Delia Mocanu, Alessandro Vespignani, and James H. Fowler. 2015. Online social networks and offline protest. EPJ

Data Science 4, 1 (2015), 19.

Manuscript submitted to ACM

38

Mannocci et al.

[127] Gianluca Stringhini and Jeremy Blackburn. 2024. Understanding the phases and themes of coordinated online aggression attacks. In Social Processes

of Online Hate. 250–272.

[128] Serena Tardelli, Leonardo Nizzoli, Marco Avvenuti, Stefano Cresci, and Maurizio Tesconi. 2024. Multifaceted online coordinated behavior in the

2020 US presidential election. EPJ Data Science 13, 1 (2024), 1–27.

[129] Serena Tardelli, Leonardo Nizzoli, Maurizio Tesconi, Mauro Conti, Preslav Nakov, Giovanni Da San Martino, and Stefano Cresci. 2024. Temporal

dynamics of coordinated online behavior: Stability, archetypes, and influence. Proceedings of the National Academy of Sciences (2024).

[130] Daniel Thiele, Miriam Milzner, Annett Heft, Baoning Gong, and Barbara Pfetsch. 2025. Attributing coordinated social media manipulation: A

theoretical model and typology. New Media & Society (2025), 14614448251350100.

[131] TikTok. 2025. Integrity and Authenticity. https://www.tiktok.com/community-guidelines/en/integrity-authenticity. (accessed: 17/03/2026).
[132] Rebekah Tromble. 2021. Where have all the data gone? A critical reflection on academic digital research in the post-API age. Social Media + Society

7, 1 (2021).

[133] Michael T. Turvey. 1990. Coordination. American Psychologist 45, 8 (1990), 938.
[134] Twitter. 2018. Enabling further research of information operations on Twitter. https://blog.twitter.com/en_us/topics/company/2018/enabling-

further-research-of-information-operations-on-twitter. (accessed: 31/07/2024).

[135] Twitter. 2021. Coordinated harmful activity. https://help.twitter.com/en/rules-and-policies/coordinated-harmful-activity. (accessed: 31/07/2024).
[136] Joshua Uyheng, Iain J Cruickshank, and Kathleen Carley. 2022. Mapping state-sponsored information operations with multi-view modularity

clustering. EPJ Data Science 11, 1 (2022), 25.

[137] Martijn Van Zomeren, Tom Postmes, and Russell Spears. 2008. Toward an integrative social identity model of collective action: A quantitative

research synthesis of three socio-psychological perspectives. Psychological bulletin 134, 4 (2008), 504.

[138] Luis Vargas, Patrick Emami, and Patrick Traynor. 2020. On the detection of disinformation campaign activity with network analysis. In ACM

CCSW. 133–146.

[139] Vítor V. Vasconcelos, Sara M. Constantino, Astrid Dannenberg, Marcel Lumkowsky, Elke Weber, and Simon Levin. 2021. Segregation and clustering

of preferences erode socially beneficial coordination. Proceedings of the National Academy of Sciences 118, 50 (2021).

[140] Otavio R. Venâncio, Carlos H. G. Ferreira, Jussara M. Almeida, and Ana P. C. da Silva. 2024. Unraveling user coordination on Telegram: A

comprehensive analysis of political mobilization during the 2022 Brazilian Presidential election. In AAAI ICWSM, Vol. 18. 1545–1556.

[141] Padinjaredath Suresh Vishnuprasad, Gianluca Nogara, Felipe Cardoso, Stefano Cresci, Silvia Giordano, and Luca Luceri. 2024. Tracking fringe and

coordinated activity on Twitter leading up to the US Capitol attack. In AAAI ICWSM, Vol. 18. 1557–1570.

[142] Xinyu Wang, Jiayi Li, Eesha Srivatsavaya, and Sarah Rajtmajer. 2023. Evidence of inter-state coordination amongst state-backed information

operations. Scientific Reports 13, 1 (2023), 7716.

[143] Claire Wardle and Hossein Derakhshan. 2017. Information Disorder: Toward an Interdisciplinary Framework for Research and Policymaking. Council

of Europe report DGI (2017)09. Council of Europe.

[144] Derek Weber and Lucia Falzon. 2021. Temporal nuances of coordination networks. arXiv:2107.02588
[145] Derek Weber and Frank Neumann. 2020. Who’s in the gang? Revealing coordinating communities in social media. In IEEE/ACM ASONAM. 89–93.
[146] Derek Weber and Frank Neumann. 2021. Amplifying influence through coordinated behaviour in social networks. Social Network Analysis and

Mining 11, 1 (2021), 111.

[147] Tom Wilson and Kate Starbird. 2020. Cross-platform disinformation campaigns: Lessons learned and next steps. HKS Misinformation Review (2020).
[148] Inga K Wohlert, Davide Vega, Matteo Magnani, and Alexandra Sergerberg. 2025. Detecting Coordination on Short-Video Platforms: The Challenge

of Multimodality and Complex Similarity on TikTok. arXiv:2506.05868

[149] Yanhong Wu and Jianqiang Yu. 2025. Unmasking Coordination: How Inauthentic Behavior Emerged and Diffusion During the Russia–Ukraine War

on Twitter. Social Science Computer Review (2025).

[150] Yunkang Yang, Ramesh Paudel, Jordan McShan, Matthew Hindman, H Howie Huang, and David Broniatowski. 2025. Coordinated link sharing on

Facebook. Scientific Reports 15, 1 (2025), 15684.

[151] Changseung Yoo, Eunae Yoo, Lu Yan, and Alfonso Pedraza-Martinez. 2024. Speak with one voice? Examining content coordination and social

media engagement during disasters. Information Systems Research 35, 2 (2024), 551–569.

[152] William E. S. Yu. 2022. A framework for studying coordinated behaviour applied to the 2019 Philippine midterm elections. In ICICT. 721–731.
[153] Savvas Zannettou, Tristan Caulfield, William Setzer, Michael Sirivianos, Gianluca Stringhini, and eremy Blackburn. 2019. Who let the trolls out?:

Towards understanding state-sponsored trolls. In ACM WebSci. 353–362.

[154] Ahmad Zareie, Mehmet E Bakir, Mark A Greenwood, Kalina Bontcheva, and Carolina Scarton. 2025. Identifying coordination in online social

networks through anomalous sharing behaviour. Online Social Networks and Media 50 (2025), 100341.

[155] Yizhou Zhang, Karishma Sharma, and Yan Liu. 2021. VigDet: Knowledge informed neural temporal point process for coordination detection on

social media. In NeurIPS. 3218–3231.

[156] Yizhou Zhang, Karishma Sharma, and Yan Liu. 2023. Capturing cross-platform interaction for identifying coordinated accounts of misinformation

campaigns. In ECIR. 694–702.

[157] Andy Zhao and Haohan Hu. 2025. Unveiling Strategic Governance and User Dynamics in Weibo’s Community-driven Content Moderation System.

Journal of Quantitative Description: Digital Media 5 (2025).

Manuscript submitted to ACM

Detection and Characterization of Coordinated Online Behavior: A Survey

39

[158] Yasser Zouzou and Onur Varol. 2024. Unsupervised detection of coordinated fake-follower campaigns on social media. EPJ Data Science 13, 1

(2024), 62.

Manuscript submitted to ACM

