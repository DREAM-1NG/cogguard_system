# Risk Review 分层需求文档：帖子级、用户级、社区级 Harmfulness Characterization

## 1. 文档目标

本文档用于把 Risk Review 从“报告研判中的一个内容分析子模块”收敛为一套可以直接指导研发、实验、验收和论文叙事的正式需求基线。它回答四类问题：

1. Risk Review 在整个系统中的职责到底是什么，和 Coordination Discover、Propagation Analysis 如何分工。
2. 帖子级、用户级、社区级分别要解决什么研究问题，而不只是“做哪些规则”和“算哪些特征”。
3. 每一层更合理的方法路线是什么，哪些高水平文献最值得作为主锚点。
4. 当前 `system/backend` 已实现到哪里、还差什么、不能声称什么。

本文档是对 [METHOD_STANCE.md](./METHOD_STANCE.md) 与 [EXPERIMENT_PLAN.md](./EXPERIMENT_PLAN.md) 的进一步细化，但与那两份文档相比，这里更强调三点：

- 问题定义优先于功能罗列。
- 文献驱动的方法设计优先于手工特征枚举。
- 当前能力边界必须明确区分 `已实现 / 部分实现 / 未实现`。

## 2. Risk Review 的问题边界

### 2.1 Risk Review 在 `Detect -> Characterize` 中的位置

Mannocci 等在 *Detection and Characterization of Coordinated Online Behavior: A Survey* 中明确把协同在线行为分析划分为 `detection` 与 `characterization` 两阶段，并指出 characterization 至少可从四个正交维度展开：

- `authenticity`
- `harmfulness`
- `orchestration`
- `time-variance`

对本项目而言：

- Coordination Discover 主要负责 `detect` 与一部分 `orchestration` 的结构发现。
- Propagation Analysis 主要负责传播链、claim、thread、桥接节点等传播结构分析。
- Risk Review 负责 `characterization` 中的 `harmfulness` 维度，也就是回答“这些协同行为到底在制造什么 harm，以什么粒度、通过什么主体、以什么路径被放大”。

因此，Risk Review 的职责不是重新做一次协同检测，也不是把上游结果重新打一个总分，而是为协同群体分析补上 harmfulness characterization 这一块最难也最容易被简化错位的维度。

### 2.2 Harmfulness 的正式含义

按 Mannocci 等的框架，harmfulness 不是简单的“负面情绪强度”，而是协调行动可能造成的线上或线下负面后果。它同时依赖：

- 行动内容本身；
- 参与主体的共同意图与组织方式；
- 观察者所处的治理视角。

对本项目的网络舆论安全视角而言，Risk Review 至少要覆盖下列 harm 类型：

- `misinformation / disinformation`
- `hate / harassment`
- `targeted smear`
- `incitement / mobilization`
- `manipulative amplification`

这意味着 Risk Review 不是“敏感词检测”模块，而是一个从单帖到账户再到社区的多层 harmfulness 建模问题。

### 2.3 Risk Review 的三层结构

Risk Review 至少应拆成三个层级，每层回答的问题不同：

| 层级 | 分析对象 | 必须回答的问题 |
|---|---|---|
| 帖子级 | 单条帖子、评论、图文、短视频 | 这条内容是否 harmful，属于哪类 harmful，关联哪个 claim，对该 claim 持何立场，证据在哪里 |
| 用户级 | 单个账户 | 该账户是否持续传播 harmful 内容，harm 模式是否稳定，扮演什么 harmful 角色 |
| 社区级 | 协同群体、campaign 子群、跨平台子网络 | 该群体整体是否 harmful，harm 如何被协同放大，哪些子群体分别承担起源、桥接、放大、骚扰、动员等功能 |

三层关系不是并列功能表，而是严格的语义聚合：

- 帖子级是最小语义单元。
- 用户级是帖子级输出沿时间、claim 和关系位置的聚合。
- 社区级是用户级与传播/协调结构在图上的再次聚合。

## 3. 设计原则：为什么 Risk Review 不能走“特征工程主导”路线

### 3.1 帖子级问题天然不是关键词或词典匹配

高水平研究在这一点上已经给出非常一致的结论：

- HateXplain 说明 harmful detection 需要解释和证据，而不是只输出一个标签。
- Hateful Memes 说明图文 harmfulness 不能被单模态文本捷径解决。
- Fakeddit、FACTIFY3M、FakeSV 和 3MFact 说明 misinformation / fact-checking / harmfulness 在多模态场景中都依赖文本、图像、视频、OCR、ASR 与外部证据的联合判断。

因此，帖子级不能建模为：

- 一套 harmful 关键词规则；
- 再叠一个 stance 分类器；
- 再把 OCR/ASR 当作“辅助字段”。

更合理的对象是：多模态、claim-conditioned、evidence-aware 的联合推断。

### 3.2 用户级问题天然不是账户统计阈值问题

用户级 harmfulness 的核心难点不是“某账号发了多少条坏内容”，而是：

- 账户是一个帖子序列，而不是一个样本点。
- harm 在账户层往往体现为持续性、角色性和轨迹性。
- 同一账户在不同阶段可能从 `amplifier` 变成 `mobilizer`，或从 `commentator` 变成 `harasser`。

因此，用户级不能被压缩为：

- 发帖频率阈值；
- automation score 阈值；
- harmful 帖子占比阈值。

这些量可以作为辅助信号，但不应成为主任务本身。

### 3.3 社区级问题天然不是成员分数平均

群体 harm 常常来自：

- 分工协作；
- reply / repost / mention / shared object 的结构耦合；
- 围绕同一 target 或同一 claim 的共同指向；
- 协同行动引发的毒性升级、骚扰放大、动员扩散。

因此，社区级不能被简化成：

- 成员 harmful 分数平均；
- toxic 帖子数量累计；
- 单一平台的局部统计图表。

更合理的对象是：异构图或超图上的 collective harm 建模。

### 3.4 Agent / RAG 的正确位置不是底层分类器

MARO、RAMA、多 Agent misinformation lifecycle 等工作说明，Agent 与 RAG 在 misinformation / fact-checking 场景中有价值，但它们更适合承担：

- `teacher`
- `reviewer`
- `verifier`
- `reporter`
- `counter-narrative generator`

如果直接把 Agent 当成帖子级、用户级、社区级的底层唯一分类器，会出现三个问题：

1. 在线代价高且结果不稳定。
2. 很难形成统一的训练、评测和回归测试基线。
3. 不利于把 Risk Review 叙述为“可部署的多层 harmfulness characterization 模块”，而更像“LLM 临时裁决器”。

对 Risk Review 而言，更合理的路线是：表示模型负责底层判断，Agent/RAG 负责上层复核、解释与报告编排。

### 3.5 总体方法论原则

Risk Review 的设计原则应统一为：

| 原则 | 含义 |
|---|---|
| `representation-first` | 以预训练表示、检索和图表征为主，而不是手工特征堆叠 |
| `claim-conditioned` | stance 与 misinformation 必须围绕 claim 建模 |
| `retrieval-aware` | 对外部证据、claim 候选、历史线程的检索是核心能力，不是可选附件 |
| `graph-native` | 用户级与社区级从一开始就应面向图聚合，而非表格特征拼装 |
| `evidence-aware` | 输出不仅有标签，还要有可复核证据 |
| `agent-as-orchestrator` | Agent 用于 teacher / reviewer / report，而非替代底层模型 |
| `uncertainty-aware` | 低置信样本允许 `abstain` 与复核，而不是强行二值化 |
| `weak-supervision-aware` | 规则、词表和阈值只能作为 bootstrapping signal、labeling function 或 calibration policy，而不是最终主方法 |
| `evaluation-contract-first` | 在训练复杂模型前先固定 gold/control set、评测指标、失败回流和能力边界，避免把 runtime 输出冒充真实验收 |

## 4. 分层总览

| 层级 | 研究问题 | 推荐范式 | 主锚点文献 | 当前状态 |
|---|---|---|---|---|
| 帖子级 | 多模态 harmfulness + claim-conditioned stance | 多模态编码、claim retrieval / reranking、联合多任务头、evidence output | HateXplain、Hateful Memes、RumourEval、EMNLP 2019 rumor-stance、FACTIFY3M、FakeSV、3MFact、MuMiN | `语义骨架与评测 harness 已实现 / 训练式模型未实现` |
| 用户级 | harmful persistence + harmful role + harmful trajectory | post-to-user 聚合、多实例学习、时序 Transformer、relation-aware aggregation、图上角色建模 | ICWSM hateful users、Findings EMNLP hateful users、TWEB cyberaggression、MuMiN、IOHunter | `运行时聚合与评测 harness 已实现 / 训练式模型未实现` |
| 社区级 | collective harm + coordinated harm amplification + subgroup role decomposition | 异构图 / 超图建模、community representation learning、temporal graph reasoning、subgraph explanation | WWW toxic conversations、IMC harassment incitement、CSCW coordinated hate targeting、OSNM coordination-to-toxicity、WWW cross-platform CIB | `运行时聚合、图导出与评测 harness 已实现 / 训练式模型未实现` |

状态标签定义：

- `已实现`：主干代码中已有稳定模块、服务入口与输出字段支撑。
- `部分实现`：已有可运行骨架，但与目标任务定义仍有明显差距。
- `未实现`：主干代码中没有对应的 harmfulness 核心模块，最多只有前置结构。

### 4.0 当前态、评测态与未来模型态的三分法

为了避免把“评测 harness”误读为“已训练模型”，Risk Review 文档统一采用三分法：

| 类别 | 当前含义 | 可声称内容 | 不可声称内容 |
|---|---|---|---|
| `current implemented` | 已进入主干代码、可被服务调用、可被测试验证的运行时能力 | post/user/community runtime aggregation、graph export、review queue、local review executor、Gate Suite 和 `/risk/review/gate-suite` 离线评估入口 | 不能把这些运行时聚合写成已训练模型 |
| `gold-control evaluation only` | 仅在显式提供 `review_gate_dataset` 时执行的离线评测能力 | Post/User/Community Gate 指标、dataset contract、layer coverage、failed thresholds、review item 回流 | 不能从 runtime 输出反推 gold，不能用 gold 自动训练、校准或更新阈值 |
| `future model` | 设计目标和后续研究路线 | teacher-student、多模态 encoder、用户级 MIL/temporal model、社区级 HGT/Graph Transformer/TGN、在线 Agent/RAG provider | 当前报告不能宣称这些模型能力已经落地 |

这个三分法是后续文档、答辩和实现记录的硬边界：当前已经实现的是“分层 harmfulness characterization 的契约化评测和运行时聚合框架”，未来仍需用真实 gold/control set 与训练式模型把能力推进到研究目标形态。

### 4.1 从文献到功能闭环的设计映射

Risk Review 的三层结构并不是把帖子、账户、社区分别做成三个孤立分类器，而是把高水平文献中的共识压缩成一条可实现的证据链。HateXplain、Hateful Memes、MOCHEG、FACTIFY3M、FakeSV 和 3MFact 共同说明，帖子级 harmfulness 的难点不在关键词，而在隐式语义、图文/音视频组合、目标对象、claim 条件化和证据解释。因此帖子级的目标输出必须是 `claim + stance + harm label + harm type + evidence + uncertainty`，而不是单个 toxic score。当前 `post_semantics.py` 和 `review_post_gate.py` 只完成了这一输出结构和固定样例评测，尚未完成端到端多模态编码器或 teacher-student 蒸馏。

用户级文献给出的核心结论是：harmful actor 的稳定性通常要从账户历史、关系图和事件条件下的行为轨迹中识别，而不是从单条内容或 profile 阈值中识别。ICWSM 的 hateful users 研究、ACM HT 的 *You too Brutus!*、WOAH 2022 的 Parler hate speech 分析和 Findings EMNLP 2021 的 anti-Asian hateful users 研究都把用户从“发帖者 id”提升为独立建模对象。它们对 Risk Review 的迁移方式是 post-to-user representation learning：把帖子级语义节点按账户组织为 bag、sequence 或 ego-graph，再学习 persistence、role 和 trajectory。当前 `layered_harmfulness.py` 与 `review_user_gate.py` 只实现了可解释运行时聚合和固定账户样例评测，还没有训练 MIL、temporal Transformer 或用户级图 encoder。

社区级文献进一步把 harmfulness 从 individual harm 推到 collective harm。WWW toxic conversations 说明 toxic interaction 有对话结构；CSCW/IMC 的 coordinated hate attack 和 harassment incitement 研究说明 target-oriented harm 是群体攻击的关键入口；ICWSM 2025 的 Coordinated Reply Attacks 说明可以从被攻击对象反推 coordinated harmful subgroup；Mannocci 等的多模态 coordinated online behavior 研究说明单一 co-action 会丢失协同结构；ICWSM 2025 的 IO labeled datasets 强调同主题、同时间 control data 对评估是必要条件。这些结论对应 Risk Review 的社区级目标：构建 account-post-claim-target-media-community 异构图，评估 collective harm、coordinated amplification、subgroup role 和 evidence chain。当前 `review_graph_exporter.py` 和 `review_community_gate.py` 已把“图导出契约”和“社区级评测 harness”落地，但仍没有训练 HGT、Graph Transformer、TGN，也没有完成 control-aware 真实实验。

Agent/RAG 相关文献的合理迁移边界也需要明确。MARO 证明多 Agent 与自动规则优化可用于跨域 misinformation detection，但它解决的是 target-domain news 的多视角分析与规则泛化，不等同于 Risk Review 三层 harmfulness 的底层表示模型。RAMA、DEFAME、RAG-Fusion 和 ClaimCheck 更适合作为低置信样本的 reviewer、verifier 和 evidence retriever。当前 `review_reviewer.py` 与 `review_review_executor.py` 因此被设计为 planned-only 队列、本地 deterministic executor 和 offline-safe provider hook，而不是默认在线多智能体系统。

| 功能闭环 | 文献支撑的任务认识 | Risk Review 迁移方法 | 当前代码边界 |
|---|---|---|---|
| Post Gate | harmfulness 必须是 claim-conditioned、multimodal、evidence-aware | 固定样例评测 claim linking、stance、harm label/type、evidence、abstain | `review_post_gate.py`；不训练帖子模型 |
| User Gate | harmful user 需要从账户历史、图关系和事件轨迹中识别 | 固定账户样例评测 harmful flag、persistence、trajectory、role、representative evidence | `review_user_gate.py`；不训练 MIL/Transformer |
| Graph Export Gate | 社区级 harm 是异构图和多 co-action 问题 | 导出 account/post/claim/community/target/media 图和对象介导边 | `review_graph_exporter.py`；不训练 graph encoder |
| Community Gate | collective harm 需要同时看 harm type、协同放大、claim 覆盖和关键账户 | 固定社区样例评测 collective harm、amplification、harm type、role、claim/key-account evidence，并审计 graph export 可读性 | `review_community_gate.py`；不训练 HGT/TGN |
| Agent/RAG Gate | Agent 适合复核、解释、检索和报告编排 | planned-only 任务队列、本地确定性执行、offline mock provider 与失败回退 | `review_reviewer.py`、`review_review_executor.py`；默认无在线调用 |
| Gate Suite | 系统需要把三层 Gate 作为同一份验收报告管理，而不是散落在测试脚本中 | 统一汇总 Post/User/Community Gate 的 executed/skipped 状态、metrics、failed thresholds 与 review items | `review_gate_suite.py` 已接入 `risk_service`；默认无 gold 时只输出 skipped report |
| Gate Dataset Contract | 真实验收必须来自显式 gold/control set，而不是从系统预测反推标签 | 规范化 `post_cases / user_gold / community_gold / thresholds / metadata`，记录 dataset id、version、source、label policy 与 control notes | `review_gate_dataset.py`；只提供评测输入契约，不训练、不校准、不自动生成 gold |

### 4.2 方法选择与替代方案

当前实现顺序选择 `runtime aggregation -> gate harness -> graph export -> local review executor -> future model/provider`，不是因为训练式模型不重要，而是因为 Risk Review 的研究对象跨越帖子、账户和社区三层。如果先训练单层分类器，很容易得到局部可用但无法向上聚合的标签；如果先做在线 Agent/RAG，又会把可回归评测、成本和复现性问题后置。先把三层输出契约、失败回流和 evidence boundary 固定下来，可以让后续训练式模型替换底层 scorer 时仍然保持相同验收口径。

被拒绝的第一类替代路线是“直接全用 MultiAgent”。MARO、RAMA 和 DEFAME 的价值在于多视角分析、证据检索、解释生成和复核编排，但它们不适合作为每条帖子、每个账户、每个社区的唯一在线判定器。Risk Review 保留 Agent/RAG 作为 reviewer/verifier/orchestrator，是为了让高不确定样本有复核路径，同时避免把主链路建立在不可控在线调用上。

被拒绝的第二类替代路线是“只做结构特征或分数平均”。Mannocci 的 COB characterization 框架、toxic conversation、coordinated harassment、cross-platform IO 和 TikTok CIB 等研究都说明，harmfulness 不是协调密度、发帖频率或成员平均 toxic score 能解释的。Risk Review 因此先导出 account-post-claim-community-target-media 图，再用 Community Gate 检查 collective harm、amplification、role decomposition 和 evidence coverage。

被拒绝的第三类替代路线是“先训练 HGT/Graph Transformer/TGN 再补验收”。社区级图模型需要稳定的帖子级语义节点、账户级角色和 control-aware 标注集；如果没有 Post/User/Community Gate，模型训练即使跑通，也难以证明它学到的是 coordinated harmfulness，而不是事件热度、平台偏差或样本构成。因此当前主干先完成 graph export contract、consumer smoke test 和 Gate Suite，训练式图模型仍放在后续 Model Gate。

### 4.3 Gold/control set 与 Gate Dataset 契约

Gate Suite 的核心不是“多传几个 gold 字段”，而是把 Risk Review 的验收方式从临时测试脚本提升为可审计的数据契约。Mannocci 等关于 COB characterization 的综述提醒我们，harmfulness 依赖观察视角和治理定义；ICWSM 2025 的 *Labeled Datasets for Research on Information Operations* 进一步强调，IO / coordinated harm 的评估必须有同主题、同时间窗口、同平台或可比平台的 control data，否则模型很容易把事件热度、普通参与和真实协同伤害混在一起。Snorkel 一类弱监督工作也给出方法论启示：人工规则和阈值应被视为 labeling functions 或 calibration signals，而不是最终模型特征。

因此，Risk Review 当前新增 `review_gate_dataset.py`，将项目标注集约束为显式契约：

- `metadata`：记录 `dataset_id / version / source / label_policy / control_set_notes`，用于说明标注来源、版本和 control set 设计。
- `post_cases`：固定帖子级样例，包含原始 posts、propagation 上下文和帖子级 gold，用于 Post Gate 评测 claim linking、stance、harm label/type、evidence 和 abstain。
- `user_gold`：账户级 gold，用于 User Gate 评测 harmful flag、persistence、trajectory、role 和 representative evidence。
- `community_gold`：社区级 gold/control，用于 Community Gate 评测 collective harm、amplification、harm type、role、claim coverage、key account evidence 和 graph readiness。
- `thresholds`：显式评测阈值，用于验收报告；它是 calibration policy，不是模型训练参数。
- `prefer_embeddings`：仅控制评测时底层 scorer 是否尝试 embedding backend，不改变 gold，也不训练模型。

该契约的边界必须写清楚：`gate_dataset` 只让 Gate Suite 在有明确标注输入时执行三层评测；如果缺少任一层 gold，对应 Gate 必须 skipped。系统不得从 `post_semantics`、`user_level` 或 `community_level` 的 runtime 输出自动生成 gold；否则会把预测结果当成答案，形成自证循环。

当前后端已提供独立离线评估入口 `/risk/review/gate-suite`。该入口接收 `KT3GateSuiteRequest`，其中包含普通风险评估范围参数和 `review_gate_dataset`，内部调用 `risk_service.assess_risk(..., db=None, review_gate_dataset=...)`，并返回 `gate_suite`、`dataset_contract`、`review_harmfulness` 与 `persistence.persisted = false`。这样做的原因是：Gate Suite 结果可能包含 gold labels、失败样本和复核证据，默认不应写入历史风险报告数据库；如果后续需要持久化，应单独设计评估作业表、脱敏策略和版本化审计字段。

### 4.4 端到端验收故事

Risk Review 的端到端路径分为无 gold 与有 gold 两种：

1. 默认线上风险研判路径  
   用户调用 `/risk/assess`，系统读取 Coordination Discover 协同检测、Propagation Analysis 传播分析、账户画像和事件帖子，生成 `post_semantics`、`review_harmfulness.user_level`、`review_harmfulness.community_level`、`graph_export`、`review_queue` 和 `review_execution`。由于没有显式 gold/control set，`gate_suite.summary.executed_gates = 0`，三层 Gate 全部 skipped。该路径证明 Risk Review runtime aggregation 可以进入报告，但不证明三层模型在标注集上达标。

2. 离线 gold/control 验收路径  
   分析师或评测脚本调用 `/risk/review/gate-suite`，请求体中提供 `review_gate_dataset`。系统在同一风险上下文中执行 Post/User/Community Gate：帖子级检查 claim、stance、harm、evidence 和 abstain；用户级检查 harmful flag、persistence、trajectory、role 和代表性证据；社区级检查 collective harm、amplification、harm type、role、claim coverage、key account evidence 和 graph export readiness。结果返回 `dataset_contract`、metrics、failed thresholds 和 review items，但不持久化到默认报告库。该路径证明“给定明确 gold/control set，Risk Review 可以被可复现验收”，仍不代表 future model 已训练完成。

## 5. 帖子级需求

### 5.1 帖子级的正式任务定义

帖子级 Risk Review 不是“文本 harmful 分类”与“文本 stance 分类”两个独立工具，而是单条内容上的联合任务，至少回答四个问题：

1. 这条内容是否 harmful。
2. 它属于哪类 harmful。
3. 它链接到哪个或哪些 claim；若无法关联，则输出 `NIL`。
4. 它对该 claim 持何立场。

从任务形态上看，帖子级是：

- `multimodal`
- `claim-conditioned`
- `multi-task`
- `evidence-aware`

### 5.2 文献驱动的问题分析

#### 5.2.1 harmfulness 的关键难点是隐式语义、目标对象和上下文

[HateXplain](https://ojs.aaai.org/index.php/AAAI/article/view/17745) 的价值不只在于提供仇恨/攻击文本标签，而在于把 evidence span 和 rationale 引入 harmful detection，这说明 harmfulness 任务从一开始就不应被当成“只出最终标签”的封闭分类问题。对 Risk Review 的启示是，帖子级输出必须带有可复核证据接口，否则后续用户级、社区级聚合会失去可解释性。

[The Hateful Memes Challenge](https://proceedings.neurips.cc/paper/2020/hash/1b84c4cee2b8b3d823b30e2d604b1878-Abstract.html) 则说明，图文 harmfulness 最大的问题不是模态数量，而是“跨模态捷径”。很多样本只有把图像与文字放在一起才能判断是否 hateful 或 insulting。对 Risk Review 的意义是，图像、视频和表情不能继续被视作正文之外的附属字段。

[Fakeddit](https://aclanthology.org/2020.lrec-1.755/) 与 [FACTIFY3M](https://aclanthology.org/2023.emnlp-main.945/) 把多模态 misinformation / fact verification 推到更细的层面。它们提醒我们，帖子级 misinformation 判断不仅依赖帖子本体，还依赖 claim、图像证据与解释性问答结构。FACTIFY3M 特别重要，因为它把 explainability 通过 5W 问答形式引入多模态事实核查，这为 Risk Review 未来的 evidence 输出提供了直接参考。

更贴近 harmful meme 的研究进一步说明，harmfulness 往往还要求识别攻击目标与政治/事件语境。[Detecting Harmful Memes and Their Targets](https://aclanthology.org/2021.findings-acl.246/) 与 [MOMENTA](https://aclanthology.org/2021.findings-emnlp.379/) 都把 meme harmfulness 和 target identification 结合起来，说明“是否 harmful”与“伤害谁”不能拆开看。[Improving Hateful Meme Detection through Retrieval-Guided Contrastive Learning](https://aclanthology.org/2024.acl-long.291/) 则把检索引导的对比学习用于 hateful meme embedding，说明当网络语境、新梗和攻击对象不断变化时，检索式表示空间比固定词典更适合持续更新。

结论是：帖子级 harmfulness 的核心难点不是词，而是隐式攻击、模态冲突、目标对象、外部事实与上下文组合。

#### 5.2.2 stance 的关键难点不是标签集，而是 target / claim awareness

[RumourEval 2019](https://aclanthology.org/S19-2147/) 为 `support / deny / query / comment` 提供了最经典的 claim-conditioned stance 任务设定。更关键的是，[Modeling Conversation Structure and Temporal Dynamics for Jointly Predicting Rumor Stance and Veracity](https://aclanthology.org/D19-1485/) 表明 stance 与 rumor/veracity 最适合联合建模，而不是先独立做 stance 再把结果机械送给下游。

[Stance Classification of Context-Dependent Claims](https://aclanthology.org/E17-1024/) 和 [Integrating Stance Detection and Fact Checking in a Unified Corpus](https://aclanthology.org/N18-2004/) 提供了更直接的任务桥梁：前者强调 stance 需要明确 claim / context，后者把 stance 作为 fact checking 流水线中连接证据与真实性判断的中间层。对 Risk Review 来说，这意味着 stance 不是报告里的一个附属字段，而是从帖子语义走向 misinformation harm 判断的中间推理步骤。

[Can We Identify Stance without Target Arguments?](https://aclanthology.org/2024.lrec-main.253/) 进一步揭示，许多 stance 模型的高分来自对数据集偏差和上下文模板的利用，而不是对目标 claim 的真正理解。对 Risk Review 来说，这意味着如果不先做 claim linking，那么 stance 就很容易退化成表面情感或态度分类。

因此，帖子级设计中最不可省略的一步是：先决定 post 面向哪个 claim，再决定 stance。

#### 5.2.3 视频、多模态事实核查与证据输出应当进入帖子级主线

[FakeSV](https://ojs.aaai.org/index.php/AAAI/article/view/26689) 是当前最贴近短视频 misinformation 场景的数据与方法锚点之一。它的重要性不只在于“有视频数据”，而在于它把视频、文本和社交上下文联合起来做判断。对 Risk Review 来说，这意味着视频帖子不能只提取标题或 ASR 文本，而要至少采用“关键帧 + OCR + ASR + 社交上下文”的最低可用路线。

[Pioneering Explainable Video Fact-Checking with a New Dataset and Multi-role Multimodal Model Approach](https://ojs.aaai.org/index.php/AAAI/article/view/35048) 则进一步表明，视频 fact-checking 最合理的输出不是单一真假标签，而是 `veracity + rationale + supported evidence`。这与 Risk Review 需要的 `harmful label + harm type + claim + stance + evidence` 结构高度兼容。

[How to Train Your Fact Verifier: Knowledge Transfer with Multimodal Pretraining to Verify Online Claims](https://aclanthology.org/2024.findings-emnlp.764/) 为 teacher-student / knowledge transfer 路线提供了更直接的参照：大模型或多模态模型可用于 teacher 侧扩标、蒸馏和检索增强，而在线部署应尽量落到小型稳定学生模型上。

开放域事实核查研究也给 Risk Review 一个重要提醒：证据不是默认可得的。[Complex Claim Verification with Evidence Retrieved in the Wild](https://aclanthology.org/2024.naacl-long.196/) 和 [AVeriTeC](https://aclanthology.org/2024.fever-1.1/) 将检索、证据质量和判定结果一起评估，比只在封闭证据库上做分类更接近社交媒体场景。[AmbiFC](https://aclanthology.org/2024.tacl-1.1/) 进一步提醒，很多 claim 本身具有歧义或上下文依赖，系统不应强迫所有样本进入单一真值标签。

这组文献共同说明，帖子级不仅要做多模态输入融合，更要把 evidence-aware verification 作为主线能力，而不是只把 OCR / ASR 结果拼到输入里。

面向低标注与新事件场景，PromptHate、Towards Low-Resource Harmful Meme Detection with LMM Agents 和 MIND 又补充了另一条路线：当 harmful meme 或图文舆情样本快速演化、人工标注不足时，prompting、相似样本检索、insight derivation 和 multi-agent debate 可以作为 teacher / reviewer 机制，为 student model 提供弱标注、难例解释和复核证据。这里需要特别注意边界：这类方法不应替代 Risk Review 的可部署底层模型，而应服务于 `扩标 -> 蒸馏 -> 复核 -> 失败样本回流` 的闭环。

RAG-Fusion 与 ClaimCheck 则把 fact-checking 的在线复核过程拆得更细：先把 claim 转换成可检索问题，再进行 Web evidence retrieval、answer extraction 和 verdict synthesis。迁移到 Risk Review 时，Agent/RAG 层不应只接收“请判断是否有害”的模糊请求，而应接收结构化输入：待核查 claim、候选 target、冲突模态、当前 stance/harm verdict、需要检索的问题列表和证据质量约束。这样才能让复核结果可审计、可回归，而不是临时聊天式判断。

#### 5.2.4 帖子不是孤立样本，而是图中的节点

[MuMiN](https://arxiv.org/abs/2202.11684) 的核心价值不是“多语言数据很多”，而是它把 claim、user、post、reply、image 和 article 放进同一异构图中。这对 Risk Review 有两个直接启示：

1. 帖子级输出应天然兼容向用户级和社区级图聚合扩展。
2. claim 本身应被当成图中的显式节点，而不是临时字符串。

[Rumor Detection on Social Media with Graph Adversarial Contrastive Learning](https://dl.acm.org/doi/10.1145/3485447.3511999) 与 [A Knowledge-Guided Dual-Consistency Network for Multi-Modal Rumor Detection](https://dl.acm.org/doi/10.1109/TKDE.2023.3275586) 进一步说明，conversation graph、内容-知识一致性和跨模态一致性都会显著影响 misinformation 判断。对 Risk Review 来说，帖子级不应被设计成孤立分类器，而应被设计成可挂接 claim 图谱、thread 图和社区图的语义节点编码器。

### 5.3 帖子级方法论：从“字段拼接”转向“claim-conditioned multimodal reasoning”

帖子级实现不应被定义为“读取哪些字段、计算哪些相似度、触发哪些词典”。这些工程字段只是在当前系统中可获得的信息载体，真正的研究对象应当是三个互相耦合的推断问题：

1. `content-to-claim`：帖子表达的可核查 claim 是什么，它是否能链接到上游传播链或外部事实库中的 claim。
2. `claim-to-stance`：帖子相对于该 claim 是支持、否认、质疑、补充、讽刺还是无关。
3. `claim-and-context-to-harm`：该表达是否构成 misinformation、hate / harassment、targeted smear、incitement / mobilization 或 manipulative amplification。

这个拆法来自三条文献线索。第一，HateXplain 与 Hateful Memes 说明 harmfulness 不是关键词匹配，而是与 target community、rationale 和跨模态组合相关。第二，RumourEval、SemEval stance detection 与 EMNLP 2019 rumor-stance 联合建模说明 stance 不能脱离 target / claim。第三，FEVER、HoVer、MOCHEG、FACTIFY3M、FakeSV、3MFact、DEFAME 与 RAMA 说明事实核查类任务的核心不是“模型记住事实”，而是 claim extraction、evidence retrieval、multimodal evidence fusion 与 explanation generation 的闭环。

因此，帖子级 Risk Review 的最低目标不是“多加 OCR / ASR 字段”，而是把帖子变成一个带 claim、stance、harm、evidence、uncertainty 的语义节点。这个语义节点既能被风险报告消费，也能进入后续用户级和社区级图建模。

### 5.4 帖子级推荐实现路线

#### 5.4.1 Claim extraction / linking 层

方法上应先把帖子级任务变成 claim-conditioned，而不是直接分类 harmful。对于文本、图片、视频和表情混合内容，系统需要先抽取或链接 claim：

- 对已有传播链中的 claim，采用 dense retrieval + cross-encoder reranking，输出 top-k linked claims 与 `NIL`。
- 对没有显式 claim 的图文或视频，参考 MOCHEG、FACTIFY3M 和 2026 年 multimodal claim extraction 方向，把 caption、OCR、ASR、关键帧描述和正文一起输入 claim extractor。
- 对低置信 claim，进入 Agent/RAG reviewer，而不是强行给 stance。

这一层的核心不是手工规则，而是检索和重排。FEVER 与 HoVer 的启示是：claim verification 成败高度依赖证据检索质量；HoVer 进一步说明多跳证据会显著拉低浅层语义匹配的可靠性。因此，Risk Review 的 claim linking 也必须保留候选、分数和 evidence provenance，不能只保留最终字符串。

#### 5.4.2 Multimodal post encoder 层

帖子编码器应面向多模态统一表示，而不是“文本主干 + OCR/ASR 附件”。可分三步落地：

1. 第一阶段使用可部署的轻量文本/图文编码器，把正文、caption、OCR、ASR、hashtag、emoji 归一化到统一 post representation。
2. 第二阶段引入 CLIP / BLIP 系列图文表示、视频关键帧表示和 ASR/OCR 表示的 late fusion 或 cross-attention fusion。
3. 第三阶段面向任务蒸馏，把 MLLM teacher 的判定、rationale 与 evidence span 蒸馏到 student encoder，减少线上直接调用大模型的成本。

Hateful Memes 的关键启示是，数据集通过 benign confounders 专门打击单模态捷径；因此 Risk Review 不能把图片、视频、表情仅当作“补充文本”。FakeSV 与 3MFact 的启示是，短视频帖子至少需要关键帧、OCR、ASR、标题/正文、评论或传播上下文共同建模。

#### 5.4.3 Joint harm-stance head 层

帖子级不建议把 harmfulness、stance、claim verification 切成三个孤立分类器。推荐采用共享表示 + 多任务输出：

- `claim relevance`：该帖子是否真的指向候选 claim；
- `stance`：support / deny / query / neutral-comment，可扩展 sarcasm / quote / ambiguous；
- `harm label`：harmful / non-harmful / uncertain；
- `harm type`：misinformation、hate_harassment、targeted_smear、incitement_mobilization、manipulative_amplification；
- `evidence alignment`：哪些文本片段、OCR/ASR 片段、图像区域或关键帧支撑该判断。

EMNLP 2019 rumor stance-veracity 联合建模说明 stance 与 veracity 具有结构和时间上的耦合；HateXplain 说明 rationale supervision 有助于把 harmful label 与证据片段绑定；MOCHEG 和 FACTIFY3M 说明多模态 verification 可以与 explanation generation 一起训练。迁移到 Risk Review 时，最合理的训练形式是 multi-task learning，而不是多套规则后处理。

#### 5.4.4 Evidence-aware abstention 层

帖子级必须允许 `uncertain` 与 `abstain`。原因不是保守，而是文献中多模态 misinformation 与 hate detection 的错误来源高度集中在隐喻、反讽、上下文缺失、claim 不明确、图文冲突和证据不足。Risk Review 应把这些样本显式送入复核队列：

- claim linking 分数低；
- stance 与 harm head 冲突；
- 图像/视频与文本表达不一致；
- 外部证据无法支持或反驳；
- 涉及高风险目标群体、线下动员或人身攻击。

这个设计可直接对齐 DEFAME、RAMA 和 MARO：大模型或多 Agent 不作为所有样本的底层分类器，而是在低置信、跨模态冲突、证据不足和高风险样本上做检索、复核、解释和报告生成。

### 5.5 帖子级高水平参考文献与迁移方式

| 文献 / 数据集 | 来源 | 方法思想 | 对 Risk Review 的迁移启示 |
|---|---|---|---|
| [HateXplain](https://ojs.aaai.org/index.php/AAAI/article/view/17745) | AAAI 2021 | hate / offensive / normal 标签、target community 与 human rationale 联合标注 | 将 harmfulness 输出与 evidence span、target 对象绑定，避免黑盒标签 |
| [The Hateful Memes Challenge](https://proceedings.neurips.cc/paper/2020/hash/1b84c4cee2b8b3d823b30e2d604b1878-Abstract.html) | NeurIPS 2020 | 通过 benign confounders 迫使模型进行真正图文联合推理 | 图像/表情/视频不能作为文本附件，必须进入跨模态推理 |
| [MMHS150K](https://ojs.aaai.org/index.php/ICWSM/article/view/7347) | ICWSM 2020 | 大规模 multimodal hate speech 数据集，覆盖文本与图像 | 可作为图文 harmfulness 预训练或弱监督迁移源 |
| [MAMI](https://aclanthology.org/2022.semeval-1.74/) | SemEval 2022 | 多模态 misogyny detection，强调图文组合中的性别攻击 | 补充 hate_harassment / targeted_smear 的图文迁移样本 |
| [PromptHate](https://aclanthology.org/2022.emnlp-main.22/) | EMNLP 2022 | 用 prompt 与 few-shot examples 激发预训练语言模型的隐含知识 | 低标注阶段可先把 harm/target/claim 写成 teacher prompt，再蒸馏到 student |
| [RumourEval 2019](https://aclanthology.org/S19-2147/) | SemEval 2019 | rumor stance 与 veracity 任务基准 | 支撑 support / deny / query / comment 的 claim-conditioned 标签体系 |
| [SemEval-2016 Task 6](https://aclanthology.org/S16-1003/) | SemEval 2016 | 面向 target 的 stance detection | 证明 stance 判断必须给定 target，不能退化为情感分类 |
| [Modeling Conversation Structure and Temporal Dynamics for Jointly Predicting Rumor Stance and Veracity](https://aclanthology.org/D19-1485/) | EMNLP-IJCNLP 2019 | 对话结构、时间动态、stance 与 veracity 联合建模 | 帖子级输出应兼容 thread / timeline，不应孤立分类 |
| [Can We Identify Stance without Target Arguments?](https://aclanthology.org/2024.lrec-main.253/) | LREC-COLING 2024 | 分析无目标论元 stance 的可靠性问题 | Risk Review 必须先做 claim linking，再做 stance |
| [FEVER](https://aclanthology.org/N18-1074/) | NAACL 2018 | claim retrieval + evidence sentence + supported/refuted/NEI | Risk Review 的 misinformation 判断需要 evidence provenance |
| [HoVer](https://aclanthology.org/2020.findings-emnlp.309/) | Findings EMNLP 2020 | 多跳事实抽取与 claim verification | 对复杂 claim，浅层相似度不足，应保留多跳证据路径 |
| [MOCHEG](https://dl.acm.org/doi/10.1145/3539618.3591879) | SIGIR 2023 | 端到端多模态 fact-checking 与 explanation generation | 帖子级可把 claim verification 与 explanation 统一训练 |
| [FACTIFY3M](https://aclanthology.org/2023.emnlp-main.945/) | EMNLP 2023 | 多模态 fact verification 与 5W explainability | evidence 输出可设计为结构化问答式解释 |
| [Fakeddit](https://aclanthology.org/2020.lrec-1.755/) | LREC 2020 | 多模态假新闻数据与多粒度标签 | 可用于图文 misinformation warm-start |
| [FakeSV](https://ojs.aaai.org/index.php/AAAI/article/view/26689) | AAAI 2023 | 短视频假新闻，结合内容与社交上下文 | 视频帖子需关键帧、OCR、ASR 与社交上下文联合 |
| [3MFact / TRUE](https://ojs.aaai.org/index.php/AAAI/article/view/35048) | AAAI 2025 | explainable video fact-checking 与 multi-role multimodal model | 视频 harmfulness 输出应包含 label、rationale、supporting evidence |
| [How to Train Your Fact Verifier](https://aclanthology.org/2024.findings-emnlp.764/) | Findings EMNLP 2024 | 多模态预训练知识迁移到 fact verifier | 支撑 teacher-student、蒸馏和离线增强路线 |
| [MuMiN](https://arxiv.org/abs/2202.11684) | SIGIR 2022 dataset | claim-user-post-reply-image 多语言异构图 | 帖子级输出应天然可接入用户级和社区级图 |
| [DEFAME](https://proceedings.mlr.press/v267/braun25b.html) | MLC 2025 / arXiv 2024 | 动态证据检索、多模态专家、结构化报告 | 可迁移为低置信样本的 RAG reviewer 流程 |
| [RAG-Fusion Based Information Retrieval for Fact-Checking](https://aclanthology.org/2024.fever-1.4/) | FEVER 2024 | 由 claim 生成问题并融合多路检索结果 | Risk Review 复核应先做 claim decomposition / question generation 再检索 |
| [ClaimCheck](https://aclanthology.org/2025.knowledgenlp-1.26/) | KnowledgeNLP 2025 | 将 web evidence fact-checking 拆为问题生成、证据检索、答案抽取和 verdict synthesis | 后续若接入在线 RAG provider，应输出可审计子任务，而不是只返回最终判断 |
| [RAMA](https://arxiv.org/abs/2507.09174) | arXiv 2025 | retrieval-augmented multi-agent multimodal fact-checking | 多 Agent 更适合证据聚合和复核，不适合作为全部样本底层分类器 |
| [MARO](https://aclanthology.org/2025.emnlp-main.291/) | EMNLP 2025 | 多 Agent 分析与自动决策规则优化 | 可迁移为 reviewer/orchestrator，而不是替代帖子级 student model |
| [Towards Low-Resource Harmful Meme Detection with LMM Agents](https://aclanthology.org/2024.emnlp-main.136/) | EMNLP 2024 | LMM agent 在少标注场景下生成分析视角和推理证据 | 可作为 Risk Review teacher/reviewer 的低资源扩标机制 |
| [MIND](https://aclanthology.org/2025.acl-long.46/) | ACL 2025 | 相似样本检索、双向 insight derivation 与多 Agent debate | 新梗和高不确定样本可走 retrieve -> reason -> debate -> judge 复核链 |

### 5.6 帖子级数据使用策略

公开数据集与项目运行数据应形成三级迁移链，而不是简单混合：

| 阶段 | 数据来源 | 训练/评估目的 | 输出能力 |
|---|---|---|---|
| 公开基准 warm-start | HateXplain、Hateful Memes、MMHS150K、MAMI、Fakeddit、RumourEval、FEVER、HoVer、MOCHEG、FACTIFY3M、FakeSV、3MFact | 学习通用 harmfulness、stance、claim verification 与多模态 evidence 表示 | 初始 encoder、claim linker、stance/harm head |
| 领域适配 distillation | 项目采集帖子、上游 claim、传播链、专家标注、LLM/MLLM teacher rationale | 把通用能力迁移到中文/多语、舆情安全、跨平台传播场景 | 可部署 student model 与校准阈值 |
| 复核 calibration | 低置信样本、人工复核样本、Agent/RAG 检索证据、事后案例回放 | 发现概念漂移、隐喻新梗、事件新 claim 和跨模态冲突 | uncertainty policy、active learning 队列、报告证据质量 |

这一路线的核心边界是：公开数据负责“学会怎么看”，项目数据负责“学会看本领域”，Agent/RAG 负责“遇到疑难样本时怎么查证和解释”。

### 5.7 帖子级当前能力边界

#### 当前已实现

当前主干中与帖子级最相关的代码位于：

- [`system/backend/app/core/risk/post_semantics.py`](../../system/backend/app/core/risk/post_semantics.py)
- [`system/backend/app/core/risk/review_post_gate.py`](../../system/backend/app/core/risk/review_post_gate.py)
- [`system/backend/app/services/risk_service.py`](../../system/backend/app/services/risk_service.py)
- [`system/backend/app/core/risk/report_builder.py`](../../system/backend/app/core/risk/report_builder.py)
- [`system/backend/tests/test_risk.py`](../../system/backend/tests/test_risk.py)

已实现能力包括：

- 基于 `text + emoji + OCR + ASR + media URL metadata` 的统一归一化；
- 从传播输出 `claims / evidence_chains` 中构建 claim candidate；
- 基于 `sentence-transformers` 的 embedding-first 相似度计算；
- claim-conditioned stance 原型打分；
- harmful type 原型打分与 `harmful / uncertain / non_harmful` 联合输出；
- 帖子级结果进入风险报告结构；
- 新增 `aggregation_posts`，向用户级和社区级聚合提供全量帖子语义输入；
- Post Gate evaluation harness，能够在固定 gold 样例上报告 `claim_link_accuracy / stance_accuracy / harm_label_accuracy / harm_type_micro_f1 / evidence_presence_rate / abstain_rate`，并把失败或 abstain 样本路由到 planned-only 复核队列。

#### 当前部分实现

当前帖子级是可运行的语义脚手架，而不是正式训练好的多模态分类器。更具体地说：

- 多模态输入字段已经打通，但视觉部分仍依赖上游 OCR / ASR / caption，不是端到端图像或视频编码。
- 当前判别逻辑主要是 prototype / similarity 方式，不是任务专用监督模型。
- evidence 字段已经存在，但尚未通过 rationale supervision 或 retrieval verification 形成稳定闭环。
- Post Gate 评测 harness 只做黑盒评测和失败样本回流，不训练模型、不更新阈值、不代表 teacher-student 蒸馏闭环已经完成。

#### 当前未实现

- 图像编码器、视频编码器与真正的音视频联合分类器；
- claim retriever + reranker 的正式双阶段架构；
- teacher-student 蒸馏闭环；
- 帖子级 retrieval-augmented fact verification；
- 真实在线低置信样本 Agent 复核流程。

因此，当前系统可以声称“已有帖子级 harmfulness characterization 的第一版语义骨架和固定样例评测 harness”，但不能声称“帖子级多模态 harmfulness 已正式完成”。

## 6. 用户级需求

### 6.1 用户级的正式任务定义

用户级 Risk Review 要回答的不是“这个账号像不像机器人”，而是：

1. 它是否持续传播 harmful 内容。
2. 它的 harmful 模式是偶发的还是稳定的。
3. 它在 harmful campaign 中扮演什么角色。
4. 它的 harmful 轨迹是否随事件和时间窗口发生升级、衰减或转向。

因此，用户级的基本对象不是单帖，而是：

- 帖子序列；
- claim / stance 轨迹；
- 与其他账户和 thread 的关系位置；
- 事件驱动下的时间演化。

### 6.2 文献驱动的问题分析

#### 6.2.1 用户比帖子更能稳定暴露 harmful 模式

[Characterizing and Detecting Hateful Users on Twitter](https://ojs.aaai.org/index.php/ICWSM/article/view/15057) 的关键贡献在于把检测对象从 tweet 转到 user。它说明，单条文本可能有很强偶然性，但账户层会暴露更稳定的语言模式、互动结构和网络位置。这对 Risk Review 的启示是：用户级不应只是帖子级标签的简单多数投票，而应当形成独立表示。

[You too Brutus! Trapping Hateful Users in Social Media](https://doi.org/10.1145/3465336.3475106) 与 [Free speech or Free Hate Speech?](https://aclanthology.org/2022.woah-1.11/) 从另一个角度强化了这一点：在标注稀缺和平台迁移场景下，图结构、邻域传播和弱监督往往比纯文本规则更稳。前者比较文本、图方法和半监督 GNN，后者在 alt-tech 平台上先做帖子级检测，再通过 social graph label propagation 扩展到账户层。对 Risk Review 的迁移启示是，用户级 harmfulness 应以“帖子语义 + 关系图 + 弱监督传播”建立账户表示，而不是手工阈值。

[Predicting Anti-Asian Hateful Users on Twitter during COVID-19](https://aclanthology.org/2021.findings-emnlp.398/) 进一步显示，用户 harmfulness 与事件密切相关。某些账户不是“永远有害”，而是在特定事件窗口里转化为稳定的 hateful / smear / mobilization actor。对 Risk Review 来说，这意味着用户级应当建模 `event-conditioned trajectory`，而不是只输出全局账户标签。

[You Shall Know a User by the Company It Keeps: Dynamic Representations for Social Media Users in NLP](https://aclanthology.org/D19-1477/) 更直接地说明，用户表示可以由时间变化的社交图和邻域上下文学习得到，并且能服务于 stance 与 hate detection。它对 Risk Review 的意义很清楚：账户级 harmfulness 不应由静态 profile 决定，而应由“该账户在当前事件窗口里和谁互动、共同传播哪些 claim、在何时进入哪个 harmful 子图”共同决定。

#### 6.2.2 persistence 与 prolonged abuse 是用户级核心维度

[Detecting Cyberbullying and Cyberaggression in Social Media](https://dl.acm.org/doi/fullHtml/10.1145/3343484) 把普通攻击、持续骚扰、协同骚扰区分开来。它的重要启示是：同样的 harmful 内容，在帖子级只能看到瞬时表达，但在用户级才看得出“反复攻击”“持续动员”“重复骚扰”的行为模式。

[Improving Cyberbullying Detection with User Interaction](https://doi.org/10.1145/3442381.3449828)、[Modeling Temporal Patterns of Cyberbullying Detection with Hierarchical Attention Networks](https://doi.org/10.1145/3441141) 和 [Learning like human annotators](https://www.zubiaga.org/publications/learning-like-human-annotators-cyberbullying-detection-in-lengthy-social-media-sessions/) 共同说明，长期骚扰不能被压缩成单帖标签或总量统计。更有效的对象是 session、reply chain、temporal interaction graph 或 windowed aggregation。对 Risk Review 来说，账户级 persistence 应当从“一个账户在多个 claim/thread 中是否反复参与 harmful interaction”来建模，而不是只看 harmful post ratio。

因此，用户级 harmfulness 必须显式覆盖：

- `persistence`
- `role`
- `trajectory`

而不是只统计 harmful post 比例。

#### 6.2.3 用户级本质上是 post-to-user 聚合与图上角色识别问题

[MuMiN](https://arxiv.org/abs/2202.11684) 提供了 user-post-claim-reply 的天然异构图视角。[IOHunter](https://ojs.aaai.org/index.php/AAAI/article/view/35046) 则表明，信息行动中的驱动者、桥接者和关键操纵者更适合通过图 foundation model 或图表示学习去识别，而不是靠若干局部统计量阈值。

[On the Detection of Disinformation Campaign Activity with Network Analysis](https://dl.acm.org/doi/10.1145/3411495.3421363) 的意义在于，它提醒我们用户 harmfulness 与 campaign 角色是耦合的。单个账户的 harmful 程度，并不只由它发布了什么决定，也由它在协同网络中的位置决定。

因此，用户级最合理的对象是：帖子级语义输出在时间和图结构上的账户级聚合。

[Enriching Abusive Language Detection with Community Context](https://aclanthology.org/2022.woah-1.13/) 还提醒我们，社区语境会影响有害内容判断：同一句话在不同社区中可能是互助、反讽、引用或攻击。迁移到 Risk Review 时，用户级与帖子级都应读取社区上下文，特别是在容易误判的讽刺、反驳、引用攻击和受害者自述场景中，用 community prototype 或邻域语境降低 false positive。

### 6.3 用户级方法论：从 profile heuristics 转向 post-to-user representation learning

用户级的核心输入是一个账户在事件窗口内的帖子、互动、claim、stance、target 与协同关系序列。它可以用工程字段近似，但不能被工程字段定义。推荐把用户级 harmfulness 设计成三个耦合子任务：

1. `persistence modeling`：账户是否在多个时间窗口、多个 thread 或多个 claim 中持续参与 harmful 传播。
2. `role inference`：账户在 campaign 中更像 originator、amplifier、bridge、harasser、mobilizer 还是 opportunistic participant。
3. `trajectory modeling`：账户的 harmfulness 是否随事件发展升级、衰减、转向或跨平台迁移。

实现上，最适合的路线是 post-to-user representation learning。每条帖子先通过帖子级 encoder 得到 claim、stance、harm、evidence 和 embedding，再按账户组织成 bag / sequence / ego-graph。随后用多实例学习、hierarchical attention、temporal Transformer、dynamic graph neural network 或 relation-aware aggregation 生成用户表示。这里的关键点是：帖子级标签不是直接投票，而是作为可学习的序列元素；账户的网络位置不是手工加分项，而是图上消息传递的一部分。

### 6.4 用户级推荐实现闭环

| 环节 | 推荐方法 | 参考文献启示 | Risk Review 目标输出 |
|---|---|---|---|
| 帖子到用户聚合 | MIL、attention pooling、hierarchical Transformer | cyberbullying session 与 lengthy session 研究说明长上下文需要层次聚合 | account harmfulness representation |
| 事件/时间建模 | temporal encoding、sliding window、trajectory encoder | COVID-19 hateful users 与 temporal cyberbullying 说明 harmfulness 是事件条件化轨迹 | escalating / stable / decaying / opportunistic |
| 关系图建模 | ego-network GNN、label propagation、heterogeneous user-post-claim graph | ICWSM hateful users、HT 2021、WOAH 2022 说明图结构有助于稀疏标注和跨平台迁移 | role inference 与低标注扩展 |
| campaign 角色建模 | graph representation + campaign context | IOHunter 与 disinformation campaign network analysis 说明 driver/bridge 角色需结合网络位置 | originator / amplifier / bridge / harasser / mobilizer |
| 可解释输出 | representative posts、claim trajectory、target concentration、neighbor evidence | HateXplain 与用户级研究共同要求可追溯证据 | 用户级 evidence bundle |

在当前系统中，`automation_score`、发帖频率、URL/hashtag 多样性等已有字段只能作为辅助上下文，而不能作为用户级 harmfulness 的主方法。主方法应是“帖子级语义表示 + 时间序列 + 图关系”的联合学习。

### 6.5 用户级高水平参考文献

#### 主锚点文献

| 文献 | 来源 | 对 Risk Review 的直接启示 |
|---|---|---|
| [Characterizing and Detecting Hateful Users on Twitter](https://ojs.aaai.org/index.php/ICWSM/article/view/15057) | ICWSM 2018 | 用户层比帖子层更稳定暴露 harmful 模式 |
| [You too Brutus! Trapping Hateful Users in Social Media](https://doi.org/10.1145/3465336.3475106) | HT 2021 | 稀疏标注下可用文本 + 图 + 半监督 GNN 识别 hateful users |
| [Free speech or Free Hate Speech?](https://aclanthology.org/2022.woah-1.11/) | WOAH 2022 | 可用帖子级弱标签通过社交图传播到账户层 |
| [Predicting Anti-Asian Hateful Users on Twitter during COVID-19](https://aclanthology.org/2021.findings-emnlp.398/) | Findings EMNLP 2021 | 用户 harmfulness 具有事件依赖的时序轨迹 |
| [You Shall Know a User by the Company It Keeps](https://aclanthology.org/D19-1477/) | EMNLP-IJCNLP 2019 | 动态社交图用户表示可服务 stance 与 hate detection |
| [Detecting Cyberbullying and Cyberaggression in Social Media](https://dl.acm.org/doi/fullHtml/10.1145/3343484) | ACM TWEB 2019 | persistence 与 prolonged abuse 是账户级问题 |
| [Improving Cyberbullying Detection with User Interaction](https://doi.org/10.1145/3442381.3449828) | WWW 2021 | session temporal graph 比孤立评论更适合建模长期伤害 |
| [Modeling Temporal Patterns of Cyberbullying Detection with Hierarchical Attention Networks](https://doi.org/10.1145/3441141) | ACM TDS 2021 | 层次注意力和 temporal encoding 适合 session-level harmfulness |
| [Learning like human annotators](https://www.zubiaga.org/publications/learning-like-human-annotators-cyberbullying-detection-in-lengthy-social-media-sessions/) | WWW 2023 | 长会话可用 windowed Transformer + aggregation 保留上下文 |
| [MuMiN](https://arxiv.org/abs/2202.11684) | SIGIR 2022 / 数据集 | user-post-claim 图谱是自然建模对象 |
| [IOHunter](https://ojs.aaai.org/index.php/AAAI/article/view/35046) | AAAI 2025 | harmful role 适合通过图表示学习建模 |
| [On the Detection of Disinformation Campaign Activity with Network Analysis](https://dl.acm.org/doi/10.1145/3411495.3421363) | CCSW 2020 | 用户 harmfulness 应与 campaign 角色联动 |
| [Enriching Abusive Language Detection with Community Context](https://aclanthology.org/2022.woah-1.13/) | WOAH 2022 | 社区上下文可降低 abusive language 判断误报 |

#### 补充参考

| 文献 | 作用 |
|---|---|
| PAN 2021 `Profiling Hate Speech Spreaders on Twitter` | 提供“传播者 profiling”任务形式参考 |
| [M3FEND / Memory-Guided Multi-View Multi-Domain Fake News Detection](https://dl.acm.org/doi/10.1109/TKDE.2022.3185151) | 虽非用户级专用，但其 domain-aware / multi-view 思路可借鉴到账户级鲁棒表示 |

### 6.6 用户级当前能力边界

当前主干中与用户级最相关的实现主要位于：

- [`system/backend/app/core/account_profiler.py`](../../system/backend/app/core/account_profiler.py)
- [`system/backend/app/services/account_service.py`](../../system/backend/app/services/account_service.py)
- [`system/backend/app/core/risk/layered_harmfulness.py`](../../system/backend/app/core/risk/layered_harmfulness.py)
- [`system/backend/app/core/risk/review_user_gate.py`](../../system/backend/app/core/risk/review_user_gate.py)
- [`system/backend/app/services/risk_service.py`](../../system/backend/app/services/risk_service.py)
- [`system/backend/app/core/risk/report_builder.py`](../../system/backend/app/core/risk/report_builder.py)

#### 当前已实现

当前已实现两类能力。第一类是账户行为画像层，包括：

- 发文频率与间隔；
- 时段分布与活跃时间；
- URL / hashtag 多样性；
- automation score。

第二类是 Risk Review 运行时用户级 harmfulness 聚合，包括：

- 从 `post_semantics.aggregation_posts` 聚合账户级 harmful 帖子、harm type、stance distribution；
- 计算账户级 `harmful_ratio`、`avg_harm_score`、`persistence_score`；
- 结合传播角色输出 `originator / bridge / amplifier / harasser / mobilizer / attention_shaper` 等 harmful role；
- 基于传播时间戳输出 `escalating / decaying / stable / insufficient_temporal_evidence` trajectory；
- 在最终风险报告中输出 `review_harmfulness.user_level`。
- User Gate evaluation harness，能够在固定账户 gold 样例上报告 `harmful_flag_accuracy / persistence_label_accuracy / trajectory_accuracy / role_micro_f1 / representative_evidence_rate / runtime_needs_review_rate`，并把失败账户路由到 planned-only 复核队列。

#### 当前部分实现

- 当前用户级 harmfulness 是可解释的运行时聚合，不是训练好的 MIL、时序 Transformer 或图神经网络模型。
- 账户画像、帖子语义、传播角色已经接入同一报告链路，但尚未形成监督学习闭环。
- User Gate 评测 harness 只做黑盒评测和失败账户回流，不训练用户 encoder，不更新聚合权重，不代表 MIL / temporal Transformer 已完成。

#### 当前未实现

- 训练式用户级 harmfulness encoder；
- MIL / hierarchical attention / temporal Transformer 模型；
- 跨事件、跨平台的用户 harmfulness 泛化评估；
- 基于人工标注或 teacher-student 的用户级监督数据闭环。

因此，当前主干已经具备 `user-level harmfulness runtime aggregation` 与固定样例评测 harness，但还不是文献目标中的 `trained user-level harmfulness characterization model`。

## 7. 社区级需求

### 7.1 社区级的正式任务定义

社区级 Risk Review 需要回答：

1. 这个协同群体整体是否 harmful。
2. 这种 harm 主要体现为 misinformation、仇恨、骚扰、抹黑、动员还是混合类型。
3. 群体内部如何分工，哪些子群体负责起源、桥接、放大、骚扰、动员。
4. harm 是否因为协同行动而被升级、扩散或跨平台迁移。

社区级要面对的是 collective harm，不是成员 harmful 分数的简单汇总。

### 7.2 文献驱动的问题分析

#### 7.2.1 群体 harm 具有明显的对话结构、目标结构和组织结构

[The Structure of Toxic Conversations on Twitter](https://dl.acm.org/doi/10.1145/3442381.3449861) 说明 toxic interaction 本身有结构。它不仅关乎哪些词被用了，还关乎回复树如何展开、对话如何聚焦和极化。因此，社区级 harmfulness 不能只看“社区里出现多少 toxic 帖子”，还要看 toxic content 在 thread 上如何被组织。

[A large-scale characterization of online incitements to harassment across platforms](https://dl.acm.org/doi/10.1145/3487552.3487852) 与 [“You Know What to Do”: Proactive Detection of YouTube Videos Targeted by Coordinated Hate Attacks](https://dl.acm.org/doi/10.1145/3359309) 则说明，大规模骚扰与仇恨攻击通常具有清晰的目标对象和动员路径。这意味着社区级模型必须对 `target-oriented harm` 有显式建模能力。

[Coordinated Reply Attacks in Influence Operations](https://ojs.aaai.org/index.php/ICWSM/article/view/35889) 把这种 target-centric 视角推进到信息行动场景：先识别被定向攻击的 tweet，再识别参与协调攻击的账户。对 Risk Review 的迁移启示是，社区级 harmfulness 不一定要从全网社区划分开始，也可以从“被攻击对象 / 被攻击 claim / 被攻击帖子”作为 sensor 反推 coordinated harmful subgroup。

#### 7.2.2 群体 harm 具有升级和放大过程

[Stoking the Flames: Understanding Escalation in an Online Harassment Community](https://dl.acm.org/doi/10.1145/3641015) 直接指出，骚扰社区的 harm 是逐步升级的，而不是静态分布在所有帖子里。[The influence of coordinated behavior on toxicity](https://arxiv.org/abs/2310.01283) 则从 coordination 与 toxicity 的关系入手，强调二者需要被联合建模而不是彼此假定。

[Toxicity in State Sponsored Information Operations](https://dl.acm.org/doi/10.1145/3720553.3746680) 进一步说明，在 state-sponsored 信息行动中，toxic language 的部署具有组织性。这对 Risk Review 非常关键，因为它说明 misinformation、manipulation 与 toxic / harassment 并不是互斥任务，而常常是同一 campaign 的不同侧面。

[Coordinated Behavior on Social Media in 2019 UK General Election](https://ojs.aaai.org/index.php/ICWSM/article/view/18074) 还提醒我们，“协同”本身不应被二值化。协调度更像一个连续谱，社区级需要刻画协调信号如何与 harmfulness 一起变化，而不是先把 community 打成 coordinated / uncoordinated，再机械套 harmful 平均分。[Labeled Datasets for Research on Information Operations](https://ojs.aaai.org/index.php/ICWSM/article/view/35958) 则给出另一个关键实验启示：需要同主题、同时间窗口的 control accounts/posts，否则很容易把事件热度、普通用户参与和真实 IO harm 混为一谈。

结论是：社区级输出不能只有一个静态 `harm score`，还要回答 harm 是否被协同结构主动放大。

#### 7.2.3 社区级本质上是异构图、超图和跨平台问题

[Decoding The Playbook: Multi-Modal Characterization of Coordinated Influence Operations on Indian Social Media](https://dl.acm.org/doi/full/10.1145/3675760) 与 [Understanding Influence Operations via Images](https://dl.acm.org/doi/10.1145/3630744.3663612) 说明，真实 influence operations 中，图像和视频并不是附属内容，而是操纵叙事与协调传播的一部分。

[Exposing Cross-Platform Coordinated Inauthentic Activity in the Run-Up to the 2024 U.S. Election](https://dl.acm.org/doi/10.1145/3696410.3714698) 进一步表明，真实 campaign 往往跨平台展开。某个平台上表现为 co-hashtag，另一个平台上可能表现为集中评论、导流链接或视频二创。

[Cross-platform Information Operations](https://doi.org/10.1145/3476086) 从信息生态视角说明，big tech 与 alt-tech 的叙事动员不是孤立发生的，社区级 harmfulness 需要识别跨平台叙事链、导流链和实体链接。[Coordinated Inauthentic Behavior on TikTok](https://ojs.aaai.org/index.php/ICWSM/article/view/42711) 进一步说明，视频优先平台上的协调信号可能来自同步发布、语音片段相似、媒体复用和用户相似网络，而不是传统文本关键词。对 Risk Review 来说，跨平台和视频平台场景要求社区图保留 shared media、audio/video reuse 与 platform relay 边。

Mannocci 等的后续工作 *Multimodal Coordinated Online Behavior: Trade-offs and Strategies* 也强调，协调行为天然是多模态、多 co-action 的，仅看单一 action 会损失结构信息。对 Risk Review 的启示是：社区级 harmfulness 最终必须兼容多种 co-action，而不仅是现有 co-retweet 或 shared URL 模式。

从图方法角度看，GCAN、CompareNet 和 GET 给出了三种很适合迁移到 Risk Review 的社区级建模思想。GCAN 将源 tweet、转发用户和词语一起建图，并输出可疑转发者与词语作为解释，说明社区级判断应当能回指“哪些账户和哪些表达触发了判断”。CompareNet 把句子、主题和实体构成有向异构文档图，再与外部知识库实体做一致性比较，说明社区级叙事 harm 不应只看传播形状，还要看 claim/entity 与外部知识是否冲突。GET 则把 claim 与 evidence 建成图并做结构学习，说明 RAG 检索到的证据不能无差别堆叠，而应进行图结构筛选和去冗余。

社区感知异构图对比学习（CACL）进一步补上了“协同账号如何学习表示”的方法参照。它不是为 harmfulness 专门设计，但其 community-aware hard positive / hard negative mining 对 Risk Review 很重要：真实协同群体往往由相似账号、共享对象、共同 target 和相近时序构成，单纯二分类容易学到事件热度或平台偏差；对比学习更适合把“真正同一 campaign 的节点”与“同主题但非协同的 control 节点”拉开。

### 7.3 社区级方法论：从 community average 转向 collective harm graph

社区级 Risk Review 的主对象不是“社区成员分数平均”，而是一个带时间、模态、claim、target 和协同行为的 collective harm graph。这个图至少包含四类语义：

1. `content semantics`：帖子级 claim、stance、harm type、evidence。
2. `actor semantics`：用户级 persistence、role、trajectory。
3. `coordination semantics`：同步行为、共享媒体、相似文本/音频/视频、共同 target、共同 link、共同 hashtag、共同 reply target。
4. `campaign semantics`：跨平台导流、叙事演化、阶段转换、control group 对照。

这样建模后，社区级输出才可以回答三个更像研究问题的问题：该群体是否整体 harmful；harm 是由哪些 coordination pattern 放大的；哪些子群承担 originator、bridge、amplifier、harassment front、mobilization front 等角色。

### 7.4 社区级推荐实现闭环

| 环节 | 推荐方法 | 参考文献启示 | Risk Review 目标输出 |
|---|---|---|---|
| 图构建 | heterogeneous graph / temporal graph / hypergraph | MuMiN、HGT、TikTok CIB、cross-platform IO 说明节点和边天然异构 | account-post-claim-target-media-platform 图 |
| 协同强度建模 | continuous coordination score、dense subgraph、co-action motif | ICWSM 2021 UK election 说明 coordination 是连续谱 | coordinated harm amplification score |
| target-centric 子图 | 从 target claim / attacked post / attacked account 反推攻击子网 | You Know What to Do、Coordinated Reply Attacks 说明目标可作为 sensor | target-oriented harassment / smear detection |
| 群体表示学习 | Heterogeneous GNN、Graph Transformer、Temporal Graph Network、graph contrastive learning | HGT、Graphormer、TGN、CACL、GNNExplainer 说明图表示、对比学习与解释可结合 | community harmfulness representation |
| 证据图学习 | claim-evidence graph、knowledge graph comparison、redundancy pruning | GCAN、CompareNet、GET 说明传播图、知识图和证据图能提供可解释证据 | evidence-aware community verdict |
| control-aware 评估 | 同主题、同时间、同平台 control posts/accounts | IO labeled datasets 强调 control set 防止把事件热度误判为 IO harm | robust evaluation and calibration |
| 解释与报告 | subgraph explanation、evidence chain、role decomposition | GNNExplainer 与 fact-checking evidence 研究支撑可解释图输出 | representative subgraphs / top harmful paths |

实现时不应先把所有成员的 harmful score 平均，而应先构造社区图，在图上学习或推断 collective representation，再输出 community harmfulness、harm type mixture、coordination-to-harm amplification、subgroup roles 和 evidence chains。

### 7.5 社区级高水平参考文献

#### 主锚点文献

| 文献 | 来源 | 对 Risk Review 的直接启示 |
|---|---|---|
| [The Structure of Toxic Conversations on Twitter](https://dl.acm.org/doi/10.1145/3442381.3449861) | WWW 2021 | 社区 harmfulness 需要 thread-aware 建模 |
| [A large-scale characterization of online incitements to harassment across platforms](https://dl.acm.org/doi/10.1145/3487552.3487852) | IMC 2021 | 群体 harm 应覆盖跨平台动员与骚扰 |
| [“You Know What to Do”: Proactive Detection of YouTube Videos Targeted by Coordinated Hate Attacks](https://dl.acm.org/doi/10.1145/3359309) | CSCW 2019 | target-oriented coordinated harm 是核心场景 |
| [Coordinated Reply Attacks in Influence Operations](https://ojs.aaai.org/index.php/ICWSM/article/view/35889) | ICWSM 2025 | 可从被攻击目标反推协调攻击账户 |
| [Stoking the Flames](https://dl.acm.org/doi/10.1145/3641015) | CSCW / PACM HCI 2024 | 社区 harm 具有升级过程 |
| [The influence of coordinated behavior on toxicity](https://arxiv.org/abs/2310.01283) | OSNM 2024 | coordination 与 toxicity 需要联合评估 |
| [Toxicity in State Sponsored Information Operations](https://dl.acm.org/doi/10.1145/3720553.3746680) | HT 2025 | misinformation 与 toxicity 往往在同一 campaign 中共现 |
| [Coordinated Behavior on Social Media in 2019 UK General Election](https://ojs.aaai.org/index.php/ICWSM/article/view/18074) | ICWSM 2021 | coordination 应建模为连续谱而不是二值标签 |
| [Labeled Datasets for Research on Information Operations](https://ojs.aaai.org/index.php/ICWSM/article/view/35958) | ICWSM 2025 | IO harmfulness 评估需要同主题同时间 control set |
| [Decoding The Playbook](https://dl.acm.org/doi/full/10.1145/3675760) | 2024 | 社区级 characterization 应是多模态的 |
| [Understanding Influence Operations via Images](https://dl.acm.org/doi/10.1145/3630744.3663612) | WebSci 2024 | 图像 coordination 不应被忽略 |
| [Exposing Cross-Platform Coordinated Inauthentic Activity](https://dl.acm.org/doi/10.1145/3696410.3714698) | WWW 2025 | 社区级长期应支持跨平台 campaign 建模 |
| [Cross-platform Information Operations](https://doi.org/10.1145/3476086) | PACM HCI / CSCW 2021 | big tech 与 alt-tech 间存在跨平台叙事动员链 |
| [Coordinated Inauthentic Behavior on TikTok](https://ojs.aaai.org/index.php/ICWSM/article/view/42711) | ICWSM 2026 | 视频优先平台需建模媒体复用、语音相似和同步发布 |
| [GCAN: Graph-aware Co-Attention Networks for Explainable Fake News Detection](https://aclanthology.org/2020.acl-main.48/) | ACL 2020 | 社区/传播级判断应能回指可疑账户和触发词 |
| [Compare to The Knowledge](https://aclanthology.org/2021.acl-long.62/) | ACL 2021 | claim/entity 判断需要接入外部知识一致性 |
| [Evidence-aware Fake News Detection with Graph Neural Networks](https://dl.acm.org/doi/10.1145/3485447.3512122) | WWW 2022 | claim-evidence graph 需要结构学习和去冗余 |

#### 补充方法文献

| 文献 | 作用 |
|---|---|
| [IOHunter](https://ojs.aaai.org/index.php/AAAI/article/view/35046) | 图 foundation model 视角，可迁移到群体 harmful role |
| [Heterogeneous Graph Transformer](https://dl.acm.org/doi/10.1145/3366423.3380027) | 异构节点/边类型下的图表示学习主干 |
| [Graphormer](https://proceedings.neurips.cc/paper/2021/hash/f1c1592588411002af340cbaedd6fc33-Abstract.html) | Graph Transformer 可作为社区图编码器参考 |
| [Temporal Graph Networks](https://arxiv.org/abs/2006.10637) | 动态图适合事件窗口和传播演化 |
| [GNNExplainer](https://proceedings.neurips.cc/paper/2019/hash/d80b7040b773199015de6d3b4293c8ff-Abstract.html) | 社区级需要输出关键子图解释 |
| [Community-Aware Heterogeneous Graph Contrastive Learning for Social Media Bot Detection](https://aclanthology.org/2024.findings-acl.617/) | 社区感知 hard positive / hard negative mining 可迁移到协同 harmful subgroup 表示学习 |
| *Multimodal Coordinated Online Behavior: Trade-offs and Strategies* | 说明 co-action 多模态集成与结构保真之间存在 trade-off |

### 7.6 社区级当前能力边界

当前主干中与社区级最相关的实现主要位于：

- [`system/backend/app/core/propagation_legacy.py`](../../system/backend/app/core/propagation_legacy.py)
- [`system/backend/app/services/coordination_service.py`](../../system/backend/app/services/coordination_service.py)
- [`system/backend/app/services/propagation_service.py`](../../system/backend/app/services/propagation_service.py)
- [`system/backend/app/core/risk/layered_harmfulness.py`](../../system/backend/app/core/risk/layered_harmfulness.py)
- [`system/backend/app/core/risk/review_community_gate.py`](../../system/backend/app/core/risk/review_community_gate.py)
- [`system/backend/app/core/risk/review_graph_exporter.py`](../../system/backend/app/core/risk/review_graph_exporter.py)
- [`system/backend/app/services/risk_service.py`](../../system/backend/app/services/risk_service.py)
- [`system/backend/app/core/risk/report_builder.py`](../../system/backend/app/core/risk/report_builder.py)

#### 当前已实现

当前已具备：

- 传播图构建；
- 协调网络构建；
- `originators / bridges / amplifiers` 结构角色抽取；
- claim 级传播链与 supporting posts；
- shared object、content preview、cluster 等结构信息；
- 基于帖子级和用户级语义的社区级 runtime aggregation；
- 输出 community harmfulness、dominant harm types、amplification score、subgroup roles、claims coverage、key accounts；
- 导出 `account / post / claim / community / target / media` 异构图节点，以及 `post_targets / account_targets / community_targets / post_uses_media / account_shares_object / co_shares_object` 等对象介导关系；
- 图导出在 summary 中记录节点/边类型统计和 `dropped_dangling_edges`，用于下游 consumer 审计；
- Community Gate evaluation harness，能够在固定社区 gold 样例上报告 `collective_harm_accuracy / amplification_label_accuracy / harm_type_micro_f1 / role_micro_f1 / claim_coverage_rate / key_account_evidence_rate`，并可对 graph export 做 consumer-readiness 审计；
- Community Gate 失败样本会进入 `community_gate_failure_review` planned-only 队列，由 `CommunityJudge` 复核，但该队列不执行在线 LLM/RAG；
- 在最终风险报告中输出 `review_harmfulness.community_level` 和 `review_harmfulness.global_summary`。

#### 当前部分实现

- 当前社区级 harmfulness 是结构与语义的可解释聚合，不是训练式 heterogeneous graph / temporal graph 模型。
- 当前输出具备 graph-native schema 形态，但还没有真正的图编码器、子图解释器或 control-aware 实验闭环。
- Community Gate 只证明当前 runtime aggregation 可以被固定样例验收、失败样本可以回流复核；它不使用 gold labels 更新阈值、训练模型或校准图表示。

#### 当前未实现

- 训练式 community-level heterogeneous graph encoder；
- Graph Transformer / HGT / Temporal Graph Network 模型；
- GNNExplainer 式关键子图解释；
- 同主题、同时间、同平台 control set 评估；
- 跨平台 community harmfulness 实证实验。

因此，当前系统已经具备 `community-level harmfulness runtime aggregation + graph export + evaluation harness`，但还不是最终目标中的 `trained graph-native collective harm model`。

## 8. Agent / RAG 层的定位

### 8.1 为什么不直接“全用 MultiAgent”

MARO 这类工作回答的是“多 Agent 是否能在跨域 misinformation 检测中提供更灵活的判断与规则优化”。这对 Risk Review 很有启发，但不能直接替代 Risk Review 的底层架构，原因有三：

1. Risk Review 不是只做帖子级真假判断，而是要把帖子级、用户级、社区级串成统一语义链条。
2. Risk Review 需要稳定、可回归、可批量运行的底层表示模型，才能支撑账户级和社区级聚合。
3. 如果底层完全交给 MultiAgent，成本、时延、复现和测试都会明显变差。

因此，更合理的分工是：底层由表示模型完成，Agent/RAG 负责高层复核与报告编排。

### 8.2 推荐分工

Agent / RAG 适合承担：

- `teacher`：生成弱标注、rationale、claim 解释；
- `reviewer`：复核低置信和冲突样本；
- `verifier`：对需要外部证据的帖子做检索核查；
- `reporter`：将帖子级、用户级、社区级证据组织成风险报告；
- `counter-narrative agent`：结合社区 harm 类型与受众给出反制叙事建议。

当前主干已经实现了两层 Agent/RAG 支撑能力。第一层是 `review_queue` 脚手架：系统会把帖子级的 `abstain / uncertain / unlinked claim`、用户级的 `needs_review / high_harmful / coordinated harmful evidence`、社区级的 `high_collective_harm / coordinated_harm_amplification` 组织成复核项、检索任务、Agent 任务和反制叙事输入。该层只生成 `planned_only` 任务契约，不执行检索、不调用 LLM，也不代表多智能体已经完成审议。第二层是 `review_execution` 本地确定性执行器：系统会基于报告内帖子、claim、账户和社区证据构造本地 evidence corpus，执行本地检索、复核和反制叙事草案生成。该层已经预留 `evidence_retriever / review_provider` 插拔接口，并用离线 mock provider 与失败回退测试验证接口形状；默认主链路仍不启用在线 provider，输出中明确标注 `live_llm_or_external_rag = false`。因此，它仍然不是在线 LLM / 外部搜索 / 向量数据库 RAG。

### 8.3 参考文献

| 文献 | 作用 |
|---|---|
| [MARO](https://aclanthology.org/2025.emnlp-main.291/) | 多 Agent 反思、决策规则优化，适合借鉴 reviewer/orchestrator 设计 |
| [RAMA](https://arxiv.org/abs/2507.09174) | 多模态 fact-checking 的 retrieval-augmented multi-agent 路线 |
| [Multi-agent Systems for the Misinformation Lifecycle](https://arxiv.org/abs/2505.17511) | misinformation 生命周期中的模块化 Agent 分工 |
| [3MFact](https://ojs.aaai.org/index.php/AAAI/article/view/35048) | multi-role multimodal 设计，适合作为 video verification 层参考 |

## 9. 实施顺序建议

Risk Review 的合理落地顺序应为：

1. 先做帖子级正式化  
   把当前 prototype / similarity 脚手架提升为可训练、可评测、可蒸馏、可复核的帖子级统一输出模块。

2. 再做用户级聚合  
   用帖子级输出构建账户级 persistence / role / trajectory。

3. 再完成社区级 harmfulness  
   在已有协调和传播结构之上，加入帖子级与用户级语义，形成异构图 harmfulness。

这个顺序不是偏好问题，而是依赖关系决定的：

- 帖子级是语义底座；
- 用户级是从单帖到群体的必要中间层；
- 社区级需要稳定的帖子级和用户级语义输入，才能避免重新退化为结构统计学。

## 10. 当前主干的正式能力边界

截至当前 `system/backend` 主干，Risk Review 可以正式声称的能力只有：

- 已具备白盒风险研判主链路：`evidence -> phase -> fusion -> DISARM -> report`；
- 已具备帖子级 harmfulness characterization 的第一版语义脚手架；
- 已具备 `post_semantics.aggregation_posts` 作为用户级/社区级聚合输入；
- 已具备用户级 harmfulness runtime aggregation；
- 已具备社区级 harmfulness runtime aggregation；
- 已具备 `review_harmfulness.graph_export` 异构图导出能力，状态为 `schema_exported / artifact_exported / consumer_readable / export_verified`，覆盖 `account / post / claim / community / target / media` 节点及对象介导关系；导出产物已可落盘并被下游 consumer 回读校验，但该能力仅表示图导出契约成立，不表示已实现训练式图模型；
- 已具备 `review_harmfulness.review_queue` 复核任务队列脚手架，用于承接未来 Agent / RAG 复核；
- 已具备 `review_harmfulness.review_execution` 本地确定性复核执行器，用于在报告内 evidence corpus 上执行可测的本地复核，并已预留离线可测的 retriever / reviewer provider hook；
- 已具备 `review_harmfulness.gate_suite` 统一验收报告；默认无 gold/control set 时三层 Gate 显式 skipped，显式传入 `review_gate_dataset` 时可执行 Post/User/Community Gate；
- 已具备 `review_gate_dataset.py` 标注数据契约层，能够记录 dataset metadata、layer coverage、gold counts、threshold layers 和 warning，不使用 gold 训练或校准模型；
- 已在最终风险报告中输出 `review_harmfulness`，包含 `post_level / user_level / community_level / global_summary / audit / graph_export / review_queue / review_execution / gate_suite`。

当前不能正式声称的能力包括：

- 已完成端到端多模态帖子分类模型；
- 已完成训练式用户级 harmfulness encoder；
- 已完成训练式社区级 HGT / Graph Transformer / temporal graph model；
- 已完成 teacher-student 蒸馏闭环；
- 已完成在线 LLM / 外部检索 / 向量数据库 RAG 复核执行闭环；
- 已完成真实 provider 接入、多轮 Agent 审议或在线证据检索服务；
- 真实项目 gold/control set 上已有系统性 Gate Suite 验收结果；
- 已完成跨平台 community harmfulness 建模。

### 10.1 当前能力边界与验收矩阵

| 层级 | 当前可声称能力 | 当前不可声称能力 | 下一步验收标准 | 证据来源 | 阻塞依赖 |
|---|---|---|---|---|---|
| 帖子级 | 多模态字段归一、claim-conditioned stance/harm 语义骨架、`aggregation_posts`、固定样例 Post Gate evaluation harness | 训练式端到端多模态模型、teacher-student 蒸馏模型 | 将 Post Gate harness 扩展到公开或项目标注集，完成 harm/stance/claim 联合评估；输出 rationale/evidence 与失败样本回流 | `post_semantics.py`、`review_post_gate.py`、`tests/test_risk.py`、后续实验报告 | 标注数据、teacher 标注流程、图像/视频编码器 |
| 用户级 | runtime aggregation 版 persistence / role / trajectory；固定账户样例 User Gate evaluation harness | MIL、时序 Transformer、训练式用户 encoder | 将 User Gate harness 扩展到账户级弱/强标注样本集，验证 persistence、role、trajectory 与代表性证据 | `layered_harmfulness.py`、`review_user_gate.py`、`tests/test_risk.py`、风险报告样例 | 稳定帖子级输出、账户级标签 |
| 社区级 | runtime aggregation 版 collective harm / amplification / subgroup role；固定社区样例 Community Gate evaluation harness；`heterogeneous graph export`，含 target/media/shared-object 关系、artifact 落盘与 consumer 回读校验 | HGT / Graph Transformer / temporal graph model | 将 Community Gate harness 扩展到社区级标注/control set，验证 collective harm、amplification、role decomposition、claim/key-account evidence 与 graph export readiness；随后再训练图模型或做子图解释实验 | `layered_harmfulness.py`、`review_community_gate.py`、`review_graph_exporter.py`、`tests/test_risk.py` | 社区级标注/control set、图模型训练与解释方案 |
| Gate Suite | 默认报告包含 `review_harmfulness.gate_suite`，可统一展示三层 Gate 的 executed/skipped 状态；无固定 gold 时显式标注 skipped；显式 `review_gate_dataset` 可驱动三层 Gate 执行 | 自动用 runtime 输出冒充 gold-based evaluation；把 skipped report 写成真实评测已完成；把 gold 当作训练或阈值更新输入 | 接入项目 gold/control set 后，让 suite 在同一报告内执行 Post/User/Community Gate，并记录 dataset id、version、source、label policy、control notes、layer coverage 和 warning | `review_gate_suite.py`、`review_gate_dataset.py`、`risk_service.py`、`tests/test_risk.py` | 固定 gold/control set 或项目标注集 |
| Agent/RAG | `review_queue` planned-only 队列；`review_execution` 本地确定性执行器；offline-safe retriever / reviewer hook 与 mock/fallback 测试 | 在线 LLM、外部搜索、向量数据库 RAG、多 Agent 自主执行闭环 | 在不破坏默认离线主链路的前提下，继续验证 provider 配置、安全策略、外部检索源和审计字段 | `review_reviewer.py`、`review_review_executor.py`、`tests/test_risk.py` | 可用检索源、LLM/retriever provider、安全策略 |

### 10.2 下一步验收标准

- 帖子级 Gate：已实现固定样例 evaluation harness，能够报告 harm label、harm type、stance、claim linking、evidence presence 与 abstain 指标，并将失败样本进入 planned-only 复核队列；下一步是接入公开/项目标注集和 teacher-student 蒸馏流程。
- 用户级 Gate：已实现固定账户样例 evaluation harness，能够报告 harmful flag、persistence、role、trajectory、代表性证据和 needs-review 指标，并将失败账户进入 planned-only 复核队列；下一步是接入真实账户级弱/强标注样本集。
- Graph Export Gate：已导出异构图样例，包含 account、post、claim、community、target、media 节点与 authored、mentions_claim、member_of、community_focuses_claim、post_targets、account_targets、community_targets、post_uses_media、account_shares_object、co_shares_object、coordinated_with 等边；已完成 schema、节点/边数量、对象介导关系、无悬挂边、`dropped_dangling_edges` 审计、artifact 落盘和 consumer smoke test。这里的 `export_verified` 只表示导出结构可读可审计，不代表图编码器、HGT、Graph Transformer 或 TGN 能力已经落地。
- Community Gate：已实现固定社区样例 evaluation harness，能够报告 collective harm、coordinated amplification、harm type、subgroup role、claim coverage、key account evidence 与 graph export readiness，并将失败社区进入 `CommunityJudge` planned-only 复核队列；下一步是接入真实社区级 gold/control set。
- Gate Suite：已实现并接入默认风险报告；无 gold 时输出 `executed_gates = 0 / skipped_gates = 3`，明确说明 Post/User/Community Gate 因缺少固定标注样例而跳过；显式传入 `review_gate_dataset` 时可在服务主链路中执行三层评测并记录 dataset contract。下一步是接入真实项目 gold/control set，使 suite 在真实事件报告中形成可复现实验验收表。
- 社区级 Model Gate：在 Graph Export Gate 与 Community Gate 之后，再实现 HGT / Graph Transformer / temporal graph model 或子图解释实验。
- Agent/RAG Gate：保留本地确定性 executor，并把 retriever / review provider 作为 future hook 固化为可测试接口；当前只要求离线 mock provider 和失败回退稳定通过，不能把它表述为真实在线 provider 已接入。后续如果接入在线 provider，其失败也不能中断主风险报告。

## 11. 与现有文档的关系

- [METHOD_STANCE.md](./METHOD_STANCE.md)：给出 Risk Review 的总体方法论定位与创新叙事。
- [EXPERIMENT_PLAN.md](./EXPERIMENT_PLAN.md)：给出帖子级优先的技术路线与工作包。
- [TASK_TRACKER.md](./TASK_TRACKER.md)：给出任务拆分与进度状态。
- `REVIEW_LAYERED_REQUIREMENTS.md`：给出 Risk Review 在帖子级、用户级、社区级的正式问题定义、主参考文献、推荐方法闭环与当前能力边界。

## 12. 主参考文献清单

以下文献建议作为 Risk Review 的主参考池。原则上，优先以 AAAI、ACL/EMNLP、NAACL、WWW、CSCW、IMC、ICWSM、SIGIR、NeurIPS、TKDE、TOIS 等高水平来源作为主锚点；arXiv 与 2025/2026 前沿工作主要作为方法迁移启发。

### 12.1 问题定位与综述

- Mannocci et al., *Detection and Characterization of Coordinated Online Behavior: A Survey*
- [A Survey on Multimodal Disinformation Detection](https://aclanthology.org/2022.coling-1.576/)
- [A Survey on Automated Fact-Checking](https://aclanthology.org/2022.tacl-1.11/)
- [Explainable Automated Fact-Checking: A Survey](https://aclanthology.org/2020.coling-main.474/)
- *Multimodal Coordinated Online Behavior: Trade-offs and Strategies*

### 12.2 帖子级 harmfulness / multimodality

- [HateXplain](https://ojs.aaai.org/index.php/AAAI/article/view/17745)
- [The Hateful Memes Challenge](https://proceedings.neurips.cc/paper/2020/hash/1b84c4cee2b8b3d823b30e2d604b1878-Abstract.html)
- [MMHS150K](https://ojs.aaai.org/index.php/ICWSM/article/view/7347)
- [Detecting Harmful Memes and Their Targets](https://aclanthology.org/2021.findings-acl.246/)
- [MOMENTA](https://aclanthology.org/2021.findings-emnlp.379/)
- [MAMI](https://aclanthology.org/2022.semeval-1.74/)
- [Improving Hateful Meme Detection through Retrieval-Guided Contrastive Learning](https://aclanthology.org/2024.acl-long.291/)
- [Towards Low-Resource Harmful Meme Detection with LMM Agents](https://aclanthology.org/2024.emnlp-main.136/)
- [Towards Explainable Harmful Meme Detection through Multimodal Debate between Large Language Models](https://dl.acm.org/doi/10.1145/3589334.3645381)

### 12.3 帖子级 stance / claim verification

- [RumourEval 2019](https://aclanthology.org/S19-2147/)
- [Stance Classification of Context-Dependent Claims](https://aclanthology.org/E17-1024/)
- [Integrating Stance Detection and Fact Checking in a Unified Corpus](https://aclanthology.org/N18-2004/)
- [Modeling Conversation Structure and Temporal Dynamics for Jointly Predicting Rumor Stance and Veracity](https://aclanthology.org/D19-1485/)
- [Can We Identify Stance without Target Arguments?](https://aclanthology.org/2024.lrec-main.253/)
- [RATSD: Retrieval Augmented Truthfulness Stance Detection from Social Media Posts Toward Factual Claims](https://aclanthology.org/2025.findings-naacl.187/)
- [FEVER](https://aclanthology.org/N18-1074/)
- [HoVer](https://aclanthology.org/2020.findings-emnlp.309/)
- [MOCHEG](https://dl.acm.org/doi/10.1145/3539618.3591879)
- [FACTIFY3M](https://aclanthology.org/2023.emnlp-main.945/)
- [Complex Claim Verification with Evidence Retrieved in the Wild](https://aclanthology.org/2024.naacl-long.196/)
- [AVeriTeC](https://aclanthology.org/2024.fever-1.1/)
- [AmbiFC](https://aclanthology.org/2024.tacl-1.1/)

### 12.4 帖子级视频、多模态与数据资源

- [Fakeddit](https://aclanthology.org/2020.lrec-1.755/)
- [MuMiN](https://arxiv.org/abs/2202.11684)
- [FakeSV](https://ojs.aaai.org/index.php/AAAI/article/view/26689)
- [3MFact / TRUE](https://ojs.aaai.org/index.php/AAAI/article/view/35048)
- [How to Train Your Fact Verifier](https://aclanthology.org/2024.findings-emnlp.764/)
- [A Knowledge-Guided Dual-Consistency Network for Multi-Modal Rumor Detection](https://dl.acm.org/doi/10.1109/TKDE.2023.3275586)

### 12.5 用户级 harmfulness

- [Characterizing and Detecting Hateful Users on Twitter](https://ojs.aaai.org/index.php/ICWSM/article/view/15057)
- [You too Brutus! Trapping Hateful Users in Social Media](https://doi.org/10.1145/3465336.3475106)
- [Free speech or Free Hate Speech?](https://aclanthology.org/2022.woah-1.11/)
- [Predicting Anti-Asian Hateful Users on Twitter during COVID-19](https://aclanthology.org/2021.findings-emnlp.398/)
- [Detecting Cyberbullying and Cyberaggression in Social Media](https://dl.acm.org/doi/fullHtml/10.1145/3343484)
- [Improving Cyberbullying Detection with User Interaction](https://doi.org/10.1145/3442381.3449828)
- [Modeling Temporal Patterns of Cyberbullying Detection with Hierarchical Attention Networks](https://doi.org/10.1145/3441141)
- [Learning like human annotators](https://www.zubiaga.org/publications/learning-like-human-annotators-cyberbullying-detection-in-lengthy-social-media-sessions/)
- [Modeling Users and Online Communities for Abuse Detection](https://aclanthology.org/2021.findings-emnlp.287/)

### 12.6 社区级 coordinated harmfulness / IO / CIB

- [The Structure of Toxic Conversations on Twitter](https://dl.acm.org/doi/10.1145/3442381.3449861)
- [A large-scale characterization of online incitements to harassment across platforms](https://dl.acm.org/doi/10.1145/3487552.3487852)
- [“You Know What to Do”: Proactive Detection of YouTube Videos Targeted by Coordinated Hate Attacks](https://dl.acm.org/doi/10.1145/3359309)
- [Coordinated Reply Attacks in Influence Operations](https://ojs.aaai.org/index.php/ICWSM/article/view/35889)
- [Stoking the Flames](https://dl.acm.org/doi/10.1145/3641015)
- [The influence of coordinated behavior on toxicity](https://arxiv.org/abs/2310.01283)
- [Toxicity in State Sponsored Information Operations](https://dl.acm.org/doi/10.1145/3720553.3746680)
- [Coordinated Behavior on Social Media in 2019 UK General Election](https://ojs.aaai.org/index.php/ICWSM/article/view/18074)
- [Labeled Datasets for Research on Information Operations](https://ojs.aaai.org/index.php/ICWSM/article/view/35958)
- [Decoding The Playbook](https://dl.acm.org/doi/full/10.1145/3675760)
- [Understanding Influence Operations via Images](https://dl.acm.org/doi/10.1145/3630744.3663612)
- [Exposing Cross-Platform Coordinated Inauthentic Activity](https://dl.acm.org/doi/10.1145/3696410.3714698)
- [Cross-platform Information Operations](https://doi.org/10.1145/3476086)
- [Coordinated Inauthentic Behavior on TikTok](https://ojs.aaai.org/index.php/ICWSM/article/view/42711)

### 12.7 图表示与解释方法

- [IOHunter](https://ojs.aaai.org/index.php/AAAI/article/view/35046)
- [On the Detection of Disinformation Campaign Activity with Network Analysis](https://dl.acm.org/doi/10.1145/3411495.3421363)
- [Heterogeneous Graph Transformer](https://dl.acm.org/doi/10.1145/3366423.3380027)
- [Graphormer](https://proceedings.neurips.cc/paper/2021/hash/f1c1592588411002af340cbaedd6fc33-Abstract.html)
- [Temporal Graph Networks](https://arxiv.org/abs/2006.10637)
- [GNNExplainer](https://proceedings.neurips.cc/paper/2019/hash/d80b7040b773199015de6d3b4293c8ff-Abstract.html)
- [M3FEND](https://dl.acm.org/doi/10.1109/TKDE.2022.3185151)
- [Abusive Language Detection with Graph Convolutional Networks](https://aclanthology.org/N19-1221/)
- [Snorkel: Rapid Training Data Creation with Weak Supervision](https://arxiv.org/abs/1711.10160)

### 12.8 Agent / RAG 参考

- [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401)
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- [Towards Faithful Explainable Fact-Checking via Multi-Agent Debate](https://arxiv.org/abs/2402.07401)
- [DEFAME](https://proceedings.mlr.press/v267/braun25b.html)
- [MARO](https://aclanthology.org/2025.emnlp-main.291/)
- [RAMA](https://arxiv.org/abs/2507.09174)
- [Multi-agent Systems for the Misinformation Lifecycle](https://arxiv.org/abs/2505.17511)

## 13. Risk Review Gate Dataset machine-readable contract update

本轮新增的契约能力把 Gate Dataset 从“代码内部约定”提升为外部评测脚本可消费的机器可读接口。该设计服务于前文的 `evaluation-contract-first` 原则：在训练复杂 post / user / community model 之前，必须先固定 gold/control set 的字段、来源、阈值、泄漏边界和非持久化策略。

新增接口如下：

| Endpoint | 作用 | 能力边界 |
|---|---|---|
| `GET /api/v1/risk/review/gate-dataset/contract` | 返回 `review-gate-dataset-v1` 契约，包括 top-level fields、required metadata、Post/User/Community layer contracts、默认指标阈值、example skeleton、usage policy、leakage policy | 只发布契约，不执行风险评估，不读取或写入 gold |
| `POST /api/v1/risk/review/gate-dataset/validate` | 对提交的 `review_gate_dataset` 返回 layer coverage、counts、threshold layers、warnings、missing metadata 和 normalized contract view | 只做字段与契约校验，不运行 `assess_risk`，不持久化，不训练/校准模型 |
| `POST /api/v1/risk/review/gate-suite` | 在同一风险上下文中使用显式 `review_gate_dataset` 执行可用 Gate，并返回 `persistence.persisted = false` | 只用于离线验收，不污染默认历史风险报告 |

正式 `metadata` 至少应包含 `dataset_id / version / source / label_policy / control_set_notes`。这些字段不是形式主义：Mannocci 等关于 COB characterization 的综述、IO labeled datasets 相关研究和弱监督/数据编程路线共同说明，harmfulness 标签高度依赖观察视角、治理定义、事件时间窗和 control set 构造。如果没有 source、label policy 和 control notes，Gate Suite 即使能计算指标，也不能被论文或答辩写成正式验收。

契约明确禁止三类泄漏：第一，不能从当前 runtime prediction 反推 gold；第二，不能用 Gate gold 自动训练、校准或更新阈值；第三，不能把含 gold/失败样本/复核证据的 Gate Suite 结果默认写入普通风险报告库。当前实现仍只证明“外部显式 gold/control set 可以驱动离线评测与失败回流”，不代表 post-level 多模态模型、user-level encoder 或 community-level graph model 已训练完成。

### 13.1 Gate Dataset manifest

为了让真实 gold/control set 接入后具备可复现实验审计能力，契约层还需要输出 report-safe manifest。manifest 的目标不是保存样本，而是回答“这次 Gate Suite 到底用的是哪一个数据集版本和阈值版本”。当前实现采用 `sha256-canonical-json`，对完整输入、Post Gate 输入、User Gate 输入、Community Gate 输入和 thresholds 分别生成稳定 fingerprint，并同步记录 metadata、layer coverage、counts、threshold layers、warning count 和 persistence policy。

manifest 必须满足两个边界：

- 可以进入 `dataset_contract.manifest` 和 `validate.manifest`，用于复现、比对版本和审计评测配置。
- 不能包含 `post_cases / user_gold / community_gold` 原始 payload，不能让普通风险报告复制 gold labels。

这一步仍然是 evaluation contract 能力，而不是训练能力。它的价值在于为后续真实项目 gold/control set、teacher-student 蒸馏实验和社区级图模型实验提供稳定的数据版本锚点。

### 13.2 Gate Dataset readiness audit

为了避免把“可以执行某一层离线 Gate”误写成“Risk Review 三层正式验收已经完成”，契约层新增 `evaluation_readiness` 审计对象。该对象把两个层次明确拆开：

- `valid / valid_for_execution`：数据集中至少有一个层级具备可用标注输入，并且必填 metadata 不缺失时，可以驱动对应 Gate 运行。
- `formal_acceptance_ready`：只有当 Post/User/Community 三层均有 gold/control 覆盖，并且 metadata 明确声明 `control_set_notes / split / leakage_policy / threshold_policy` 时，才可作为 Risk Review 三层正式离线验收证据。

新增 readiness 字段包括 `has_required_metadata`、`has_control_notes`、`has_split`、`has_leakage_policy`、`has_threshold_policy`、`has_full_layer_coverage`、`covered_layers`、`missing_layers`、`readiness_warnings` 与 `acceptance_note`。其中 `readiness_warnings` 会显式指出缺少 control set 说明、split、泄漏隔离策略、阈值冻结策略或三层覆盖。这样设计的原因是：真实 harmfulness characterization 的误差来源不仅来自模型，还来自样本切分、同事件泄漏、阈值后验调参和 control set 构造。如果这些信息没有进入契约，即使 Gate Suite 可以计算指标，也只能称为 smoke test 或单层离线检查，不能称为正式验收结果。

readiness audit 仍然不复制原始 gold payload，也不训练或校准模型。它进入 `validate` 响应、`dataset_contract` 视图和 report-safe manifest，用于让评审人员、前端页面和后续实验脚本统一识别当前数据集处于哪一级验收状态。

### 13.3 Frontend acceptance surface

为了让验收链路不仅停留在后端 API，前端风险研判页也需要暴露最小的 Risk Review Gate Dataset 操作面。当前前端已经在 `src/api/risk.ts` 中接入三个接口：`getKT3GateDatasetContract()`、`validateKT3GateDataset()` 和 `assessKT3GateSuite()`；风险研判页新增“Risk Review Gate Dataset 契约与离线验收”卡片，可加载契约、填入 example skeleton、粘贴数据集 JSON、执行 validate，并在需要时触发离线 Gate Suite。

该前端能力仍遵守同一边界：

- `validate` 只校验契约，不运行风险评估。
- `gate-suite` 返回 `persistence.persisted = false`，不把 gold/control 结果写入普通历史报告。
- 页面只展示 metadata、coverage、counts、warnings、readiness audit 和 manifest fingerprint，不展示完整 gold payload。

## 14. 本轮方法闭环：帖子级多模态检测、用户级 MIL 与真实多智能体

本轮新增实现遵循“文献方法思想迁移，而不是手工特征堆叠”的边界。Risk Review 当前不声称已经训练端到端多模态模型、用户级神经 MIL 模型或在线 RAG/LLM provider；但已经把三类前沿方法的任务形状落成了可运行、可测试、可审计的系统契约。

| 层级 | 高水平文献依据 | 方法思想 | 当前实现 | 能力边界 |
|---|---|---|---|---|
| 帖子级多模态 harmfulness | [RGCL, ACL 2024](https://aclanthology.org/2024.acl-long.291/)、[MOCHEG, SIGIR 2023](https://dl.acm.org/doi/10.1145/3539618.3591879)、[FACTIFY3M, EMNLP 2023](https://aclanthology.org/2023.emnlp-main.945/)、[FakeSV, AAAI 2023](https://ojs.aaai.org/index.php/AAAI/article/view/26689) | harmfulness 不能只看文本表面；应把图文、OCR、ASR、caption、claim、证据解释和短视频社交上下文联合判断。RGCL 强调检索引导的多模态表示，MOCHEG/FACTIFY3M 强调 claim-conditioned evidence 和解释，FakeSV 强调短视频场景下内容、评论和发布者上下文。 | `post_semantics.py` 新增 `multimodal_detection`，对 text、OCR、ASR、caption/media、emoji/hashtag 做 modality-aware late fusion，并在每个帖子输出 evidence modalities、channel results、claim grounding、method trace 和 capability boundary。 | 已实现多模态归一化与推理脚手架；未实现真实图像 encoder、视频 encoder、CLIP/LMM 训练或 teacher-student 蒸馏。 |
| 用户级 MIL harmfulness | [Attention-based Deep MIL, ICML 2018](https://proceedings.mlr.press/v80/ilse18a.html)、[Characterizing and Detecting Hateful Users, ICWSM](https://ojs.aaai.org/index.php/ICWSM/article/view/15057)、[Modeling Users and Online Communities for Abuse Detection, Findings EMNLP 2021](https://aclanthology.org/2021.findings-emnlp.287/)、[You too Brutus, ACM HT 2021](https://dl.acm.org/doi/10.1145/3465336.3475106) | 账户不是一个静态 profile，而是帖子实例 bag / sequence / ego-network。MIL 的价值在于从弱实例证据聚合到账户级 label，同时保留关键实例贡献；用户建模文献说明需要把发帖历史、互动网络、社区和伦理边界一起考虑。 | 新增 `review_user_mil.py`，把账户表示为 `bag of posts`，对每条帖子构造 instance score，用 softmax attention 聚合为 `mil_harm_score`，输出 `attention_posts`、harm type distribution、stance distribution、context、method trace 和 boundary，并在 `risk_service.py` 接入 `review_harmfulness.user_mil`。 | 已实现 attention-MIL 推理契约和可解释实例贡献；未训练神经 MIL、temporal Transformer、用户 encoder 或跨平台图模型。 |
| 多智能体复核闭环 | [MARO, EMNLP 2025](https://aclanthology.org/2025.emnlp-main.291/)、[ReAct, ICLR 2023](https://openreview.net/forum?id=WE_vluYUL-X)、DEFAME / multimodal expert fact-checking、multi-agent fact-checking debate | Agent 不应替代底层分类器，而应承担 reviewer、retriever、verifier、judge、counter-narrative planner 等角色。MARO 提供多专家分析与规则优化思路，ReAct 强调 reasoning/action trace 与外部证据交互，fact-checking agent 工作强调证据与裁决分离。 | 新增 `review_multi_agent.py`，执行 `HarmReviewAgent`、`StanceClaimAgent`、`EvidenceRetrievalAgent`、`UserMILAgent`、`CommunityJudgeAgent`、`CounterNarrativeAgent` 六个本地 agent。所有 agent 读取共享 blackboard，输出 `agent_results` 和 `final_decision`，并支持 offline provider hook 与失败回退。`risk_service.py` 接入 `review_harmfulness.multi_agent_review`。 | 已实现真实本地多智能体执行，而不只是 planned queue；默认仍不调用在线 LLM、外部搜索或向量库 RAG，provider hook 只证明接口可插拔和失败可回退。 |

### 14.1 帖子级任务定义更新

帖子级输入定义为单条 social post 的多模态上下文：正文、hashtags、emoji、media URL、OCR、ASR、caption/alt/summary、传播侧 claim candidates 和上游事件上下文。输出不再是单一 toxic score，而是：

- `harmfulness`: harmful / non_harmful / uncertain、harm type、score、abstain。
- `stance`: support / deny / query / neutral / uncertain / unlinked，以及相对 primary claim 的 confidence。
- `multimodal_detection`: 各模态 channel result、融合分数、跨模态冲突、证据模态、claim grounding 与能力边界。
- `evidence`: text / OCR / ASR / media text 摘要，用于用户级 MIL、多智能体复核和图导出。

帖子级形式化口径进一步见 [REVIEW_TRAINABLE_METHOD_AND_DATASETS.md](./REVIEW_TRAINABLE_METHOD_AND_DATASETS.md)：单条帖子 `p` 被拆成 `tweet / meme / img / video` 四类可选视图，分别由 `D_tweet / D_meme / D_img / D_video` 输出局部 harmfulness、置信度和证据，再由多数投票、加权投票或可训练 late fusion 得到最终 `final_harmfulness`。若视图缺失、置信度不足或跨视图冲突，则输出 `uncertain` 并进入复核队列。

帖子级统一检测模型和 benchmark 全量验证协议进一步固化在 [REVIEW_POST_UNIFIED_MODEL_AND_VALIDATION.md](./REVIEW_POST_UNIFIED_MODEL_AND_VALIDATION.md)，其中将目标模型命名为 `MV-PostGuard`，并明确当前本地 readiness 只支持 PHEME、Twitter15/16、MCFEND 的结构化验证，MultiOFF 因缺少 3 个图片引用暂为 partial。

这对应 RGCL 的 retrieval-aware multimodal representation、MOCHEG/FACTIFY3M 的 evidence/explanation 输出和 FakeSV 的短视频最低可用路线。当前实现只把多模态证据变成可运行 inference scaffold；下一阶段才应接入真实图像/视频 encoder、hard-negative retrieval、teacher-student 蒸馏和公开数据集实验。

### 14.2 用户级任务定义更新

用户级输入定义为同一账户在事件窗口内的帖子 bag，以及账户画像、传播角色、协同关系和已有用户级聚合。输出应回答“该账户是否持续参与 harmful 传播、关键证据帖是什么、harm 类型是否稳定、是否需要复核”。本轮 `review_user_mil.py` 把该任务落成以下输出：

- `mil_harm_score`: bag-level harmfulness score。
- `attention_posts`: 对账户级判断贡献最大的帖子实例。
- `harm_type_distribution` 与 `stance_distribution`: 账户层 harm/stance 结构。
- `context`: coordinated、propagation roles、automation score、existing persistence。
- `capability_boundary`: 明确 `trained_mil_model = false` 与 `trained_user_encoder = false`。

这不是手工统计阈值替代品，而是把 Attention-MIL 的“bag label + instance contribution”思想迁移成当前工程可运行契约。后续训练式版本应把 instance encoder、attention pooling、temporal order、claim-conditioned supervision 和 user/community ethics audit 纳入统一实验。

### 14.3 多智能体任务定义更新

多智能体层输入为帖子级语义、用户级聚合、用户级 MIL、社区级聚合、图导出和本地 review execution。输出为每个 agent 的局部结论、证据、建议动作和全局 `final_decision`。本轮已实现六类 agent：

- `HarmReviewAgent`: 汇总 harmful / uncertain posts 和 harm types。
- `StanceClaimAgent`: 检查 claim grounding、stance distribution、unlinked 或低置信帖子。
- `EvidenceRetrievalAgent`: 消费本地 retrieval results，判断是否需要外部证据。
- `UserMILAgent`: 消费 `user_mil`，判断账户级持续 harmfulness。
- `CommunityJudgeAgent`: 判断 collective harm 与 coordinated amplification。
- `CounterNarrativeAgent`: 基于 counter-narrative drafts 和 harmful claims 给出人工审核前的反制叙事准备状态。

该层已经从“planned-only queue”推进到“executed local multi-agent runtime”。但默认仍是离线 deterministic runtime，不应写成在线 LLM 多智能体已经接入。真正上线 provider 时，仍必须保留审计字段、失败回退、人工审核和不自动发布反制叙事的安全边界。

## 15. 可训练方法与数据集缺口

Risk Review 当前实现已经把帖子级、用户级、社区级和多智能体复核的接口跑通，但这些能力仍属于 runtime scaffold、evaluation harness 和 local review runtime。下一步若要推进为可训练方法，应以 [REVIEW_TRAINABLE_METHOD_AND_DATASETS.md](./REVIEW_TRAINABLE_METHOD_AND_DATASETS.md) 为准：该文档把帖子级 teacher-student 多模态模型、用户级 trainable MIL / temporal encoder、社区级 HGT / Graph Transformer / TGN、多智能体 teacher/reviewer/retriever/verifier 闭环分别定义为训练任务，并列出所需公开数据集、本地已有数据和当前缺口。

最重要的边界是：本地已有 PHEME、Twitter15/16、MCFEND、IOHunter、Russian Troll Tweets、Twitter IO、CooRTweet 和 MediaCrawler 数据，可支撑传播/协同/项目域适配与弱监督构建；但仍缺少 HateXplain、Jigsaw Toxicity、Hateful Memes、MMHS150K、MAMI、MultiOFF、MOCHEG、FACTIFY/FACTIFY3M、FakeSV、MuMiN、完整 RumourEval/FEVER/AVeriTeC、用户级 harmfulness gold，以及项目域三层 `review_project_gold`。因此当前不能声称 Risk Review 已具备训练完成的帖子级多模态 harmfulness、用户级 MIL 或社区级 collective harm 模型。
