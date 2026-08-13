# CogGuard Harmfulness 任务级综合实现说明

## 0. 本文边界与输入输出

本文只定义 CogGuard Stage 2 Harmfulness 的任务级实现与验证路线。输入是 Discovery 已经冻结输出的 `DiscoveredClusterBatch` / `EventSnapshot` 社区、事件窗口、成员、内容、互动和上下文证据；输出是独立的 `community-level harmfulness characterization`。Stage 2 不重新做 Discovery，不重新聚类，不把 IO 归因、bot 评分、真实性判断、单条内容毒性或事实核查替代为 harmfulness。

最小接口应保持单向：

```text
Frozen DiscoveredClusterBatch / EventSnapshot
  -> Harmfulness evidence extraction
  -> community-level labels, rationales, calibrated confidence, abstain/review decision
```

任务输出必须同时保留三类相互独立的判断：

- `harmful_intent`：是否有足够证据支持该社区或活动具有有害意图。
- `potential_impact`：若继续扩散或被利用，可能造成的风险类型和严重度。
- `observed_impact`：在冻结窗口内已经观察到的影响证据。
- `abstain_or_review`：证据不足、OOD、校准风险过高或标签冲突时，输出复核而不是强制分类。

本 README 的直接依据是 canonical beast report 与三篇已审查精读：

- [canonical report](G:\CISCN\CogGuard\.worktrees\refactor-system\research-wiki\literature_runs\20260811T152231Z-how-should-cogguard-implement-and-validate-harmf\report.md)
- [canonical difference matrix](G:\CISCN\CogGuard\.worktrees\refactor-system\research-wiki\literature_runs\20260811T152231Z-how-should-cogguard-implement-and-validate-harmf\difference-matrix.md)
- [canonical papers.json](G:\CISCN\CogGuard\.worktrees\refactor-system\research-wiki\literature_runs\20260811T152231Z-how-should-cogguard-implement-and-validate-harmf\papers.json)
- [P04 Pote et al. 2025 report](G:\CISCN\CogGuard\.worktrees\refactor-system\doc\research\coordination-characterization\harmfulness\deep-reads\pote-et-al-2025-coordinated-reply-attacks\report.md) and [source map](G:\CISCN\CogGuard\.worktrees\refactor-system\doc\research\coordination-characterization\harmfulness\deep-reads\pote-et-al-2025-coordinated-reply-attacks\source_map.json)
- [P13 Gopalakrishnan et al. 2025 report](G:\CISCN\CogGuard\.worktrees\refactor-system\doc\research\coordination-characterization\harmfulness\deep-reads\gopalakrishnan-et-al-2025-large-engagement-networks\report.md) and [source map](G:\CISCN\CogGuard\.worktrees\refactor-system\doc\research\coordination-characterization\harmfulness\deep-reads\gopalakrishnan-et-al-2025-large-engagement-networks\source_map.json)
- [P10 Angelopoulos et al. 2024 report](G:\CISCN\CogGuard\.worktrees\refactor-system\doc\research\coordination-characterization\harmfulness\deep-reads\angelopoulos-et-al-2024-conformal-risk-control\report.md) and [source map](G:\CISCN\CogGuard\.worktrees\refactor-system\doc\research\coordination-characterization\harmfulness\deep-reads\angelopoulos-et-al-2024-conformal-risk-control\source_map.json)

三篇精读的 strict validator 命令、退出码、原始输出和文件哈希分别保存在 [P04 validation](G:\CISCN\CogGuard\.worktrees\refactor-system\doc\research\coordination-characterization\harmfulness\deep-reads\pote-et-al-2025-coordinated-reply-attacks\strict-validation.json)、[P13 validation](G:\CISCN\CogGuard\.worktrees\refactor-system\doc\research\coordination-characterization\harmfulness\deep-reads\gopalakrishnan-et-al-2025-large-engagement-networks\strict-validation.json) 和 [P10 validation](G:\CISCN\CogGuard\.worktrees\refactor-system\doc\research\coordination-characterization\harmfulness\deep-reads\angelopoulos-et-al-2024-conformal-risk-control\strict-validation.json)。其中 `visual_verification=complete` 表示报告采用的 selected/key 图表已经人工核验；manifest 中 `automatic_crops_are_unverified=true` 仍是有意保留的安全边界，不表示所有自动候选裁剪都经过人工确认。

## 1. Canonical Beast 20 篇证据综合

canonical beast 接受了 20 篇证据。其结论不是“公开文献完全没有相关工作”，而是：已有研究提供边界、场景、控件、方法和验证组件，但没有直接闭合 CogGuard 所需的“冻结社区输入 -> 独立 community-level harmfulness characterization -> 校准/弃权/跨场景验证”生产级任务。

| ID | 主要角色 | 对 Harmfulness 的可用证据 | 必须保留的边界 |
| --- | --- | --- | --- |
| P02 | COB survey / 边界守卫 | 定义 detection 与 characterization 的区分，约束不要把协调发现等同于 harmfulness。 | Survey 不是冻结社区 harmful-intent 分类器。 |
| P04 | reply attack 场景 | 提供 coordinated reply attacks 的 tactic-specific 检测与特征。 | P04 = tactic-specific reply attack signal，不是统一 harmfulness Gold。 |
| P05 | IO provenance / controls | 提供 IO 数据、campaign provenance、topical controls 的基础设施。 | IO membership 或 actor set 不能当作 harmful intent。 |
| P06 | multimodal COB | 支持 text-image-network/time evidence fusion 的候选实现。 | 检测/融合 coordination evidence，不等于独立 harm label。 |
| P10 | conformal risk control | 支持 calibration、selective risk、threshold、abstain protocol。 | P10 = calibration/risk-control protocol，不定义 harmfulness。 |
| P11 | temporal COB | 支持 stability、archetypes、influence 等时间特征。 | 不输出 intent/potential/observed impact 三分标签。 |
| P13 | LEN campaign-vs-organic | 支持 campaign 与 organic trend 的图级区分和 harmless/organic controls 思路。 | P13 = campaign-vs-organic characterization，不是 harmful intent。 |
| P14 | multilingual Telegram | 支持平台、语言和政治语境 holdout 压力测试。 | 仍是协调活动检测/刻画，不是 Stage 2 harmfulness。 |
| P16 | social spam campaigns | 提供 campaign-level spam/scam 历史类比。 | 2010 spam/scam 不能替代现代多模态校准验证。 |
| P17 | attention MIL | 支持 community/campaign label over instances 的 MIL 聚合。 | 通用方法，无 social harmfulness label。 |
| P20 | Set Transformer | 支持 permutation-invariant set modeling。 | 通用集合模型，不含 harm ontology 或 controls。 |
| P23 | harmful-content severity | 支持内容严重度维度和标签讨论。 | 内容严重度不等于 coordinated harmful intent。 |
| P26 | cross-domain multimodal fake news | 支持 domain shift、多模态 misinformation 评估压力。 | item/news-level fake-news 不等于 community-level harmful coordination。 |
| P29 | coordinated propaganda spread | 支持 coordinated communities 传播 propaganda 的类别证据。 | propaganda 是单一 harm slice，不是完整 ontology。 |
| P30 | Twitch hate raids | 支持 harassment/raid 与实时 observed impact 语义。 | Twitch live raid 与冻结社交社区不同。 |
| P32 | Gaza observed impact | 支持 observed impact 与 intent 分离。 | 单事件 case study，不是 intent classifier。 |
| P34 | Indian multimodal IO | 支持多模态 influence-operation characterization。 | campaign-specific，不是可部署 calibrated classifier。 |
| P36 | Capitol offline-risk | 支持 offline-risk 与时间升级语境。 | event-specific，不能泛化为全局分类器。 |
| P37 | YouTube hate attacks | 支持 source-community hate/harassment 归因证据。 | YouTube hate attribution 不覆盖 misinformation/scam/OOD/abstain。 |
| P39 | benign fandom coordination | 支持 coordinated-harmless control，反驳 coordination-as-harm shortcut。 | harmless fandom 不是 harmfulness classifier。 |

### G1-G4 narrowed gaps

canonical beast 把四个 gap 收窄为可实现、可验证的协议缺口，而不是全局 absence 或 novelty 声明：

- G1：缺口不是“没有 harmfulness taxonomy”，而是缺一个适配冻结发现社区的 Stage 2 ontology，且要把 harmful intent、potential impact、observed impact 与 IO membership、coordination strength、toxicity、attribution 分开。
- G2：缺口不是“没有 controls”，而是缺 matched coordinated-harmless controls 作为 Harmfulness benchmark 的组成部分，防止模型学习 coordination、topic、platform 或 campaign shortcut。
- G3：缺口不是“没有 group aggregation / multimodal 方法”，而是这些组件尚未在 independent frozen-community harmfulness labels 上闭环验证。
- G4：缺口不是“没有 calibration / OOD / selective-risk 方法”，而是需要把 calibrated abstention、OOD、campaign/platform/time holdouts 放进 harmful coordination 的同一套 validation gate。

因此可主张的是：accepted evidence 支持 CogGuard 的任务边界、实现候选和验证设计。不可主张的是：已有文献证明了 CogGuard 的生产级 harmfulness classifier、统一 public benchmark、跨平台 SOTA 或全局研究空白。

## 2. 三篇精读的迁移结论

### 2.1 P04 = tactic-specific reply attack signal

论文：Pote et al. 2025, `Coordinated Reply Attacks in Influence Operations: Characterization and Detection`。精读文件见 [P04 report](G:\CISCN\CogGuard\.worktrees\refactor-system\doc\research\coordination-characterization\harmfulness\deep-reads\pote-et-al-2025-coordinated-reply-attacks\report.md) 与 [P04 source map](G:\CISCN\CogGuard\.worktrees\refactor-system\doc\research\coordination-characterization\harmfulness\deep-reads\pote-et-al-2025-coordinated-reply-attacks\source_map.json)。

| 维度 | 结论 |
| --- | --- |
| 任务单位 | RQ2 是 tweet-level targeted/control；RQ3 是 replier account-level IO/normal；不是 community-level harmfulness。 |
| 标签 | `targeted tweet` 由已知 Twitter IO accounts 对非 IO tweet 的集中 direct replies 构造；`IO replier` 来自平台 IO membership。 |
| 方法 | reply-level engagement、entities、delay、LaBSE similarity 聚合特征；Random Forest 等监督分类器；10-fold CV；cross-campaign F1。 |
| 最强证据 | tweet classifier AUC 0.88 / F1 0.80；replier classifier AUC 0.97 / F1 0.92；similarity 是 replier 强信号。 |
| 最大局限 | 标签依赖已知 Twitter IO membership 与控制 tweet 构造；真实低 prevalence、跨平台、未知 IO、人工 harm intent 均未闭合。 |
| 可迁移组件 | reply-attack tactic feature、target/replier/tweet 任务拆分、reply similarity/delay/engagement 聚合、人工复核队列设计。 |

对 CogGuard 的用法：把 P04 迁移为一个 `reply_attack_signal` 或 harassment-style tactic detector，作为 community harmfulness evidence 的一个输入通道。禁止把 IO membership、集中回复、高相似回复或 tweet/replier 分类结果直接映射为 `harmful_intent=true`。

### 2.2 P13 = campaign-vs-organic characterization

论文：Gopalakrishnan et al. 2025, `Large Engagement Networks for Classifying Coordinated Campaigns and Organic Twitter Trends`。精读文件见 [P13 report](G:\CISCN\CogGuard\.worktrees\refactor-system\doc\research\coordination-characterization\harmfulness\deep-reads\gopalakrishnan-et-al-2025-large-engagement-networks\report.md) 与 [P13 source map](G:\CISCN\CogGuard\.worktrees\refactor-system\doc\research\coordination-characterization\harmfulness\deep-reads\gopalakrishnan-et-al-2025-large-engagement-networks\source_map.json)。

| 维度 | 结论 |
| --- | --- |
| 任务单位 | topic/trend-level engagement graph；不是 account、edge、tweet，也不是 frozen CogGuard community。 |
| 标签 | campaign/non-campaign 或 campaign subtype；campaign 来自 ephemeral astroturfing fake-trend proxy，organic 来自人工筛选趋势。 |
| 方法 | 构建 directed engagement network；节点/边属性含 profile、text embedding、interaction metadata；比较 Text+MLP、GNN、spectral baselines。 |
| 最强证据 | official PDF 报告 314 graphs；full LEN binary 最佳 F1 约 0.788；campaign type macro-F1 明显更弱。 |
| 最大局限 | random graph split 可能泄漏时间、事件、社群、用户模式；non-campaign 是启发式 organic proxy；305 vs 314 版本冲突需复现前解决。 |
| 可迁移组件 | campaign-vs-organic control 构造、topic/trend graph-set 表征、graph baseline、size/popularity confounder audit。 |

对 CogGuard 的用法：P13 可用于设计 matched coordinated-harmless / organic controls 和 graph-set baseline，帮助避免“协调即有害”的 shortcut。禁止把 campaign/non-campaign、graph size、trend manipulation 或 campaign subtype 当作 harmfulness label。

### 2.3 P10 = calibration/risk-control protocol

论文：Angelopoulos et al. 2024, `Conformal Risk Control`。精读文件见 [P10 report](G:\CISCN\CogGuard\.worktrees\refactor-system\doc\research\coordination-characterization\harmfulness\deep-reads\angelopoulos-et-al-2024-conformal-risk-control\report.md) 与 [P10 source map](G:\CISCN\CogGuard\.worktrees\refactor-system\doc\research\coordination-characterization\harmfulness\deep-reads\angelopoulos-et-al-2024-conformal-risk-control\source_map.json)。

| 维度 | 结论 |
| --- | --- |
| 任务单位 | 已有模型、已有标签、已有 loss 下的 post-processing calibration；不是 classifier training 或 label generation。 |
| 标签 | CRC 不提供标签；要求 calibration split 上已有可计算的 true label / loss。 |
| 方法 | 选择 `lambda` 控制 bounded monotone loss 的 expected risk；依赖 exchangeability、monotonicity、boundedness、achievability。 |
| 最强证据 | Eq. (2)-(4)、Theorem 1 给出有限样本期望风险控制；Figures 1-4 是 worked examples；Figure 6 显示 standard CRC 在 shift 下会失败。 |
| 最大局限 | 不是 high-probability 保证；不自动处理 campaign/platform/time shift；不解决 harmfulness 定义、Gold、OOD 本身。 |
| 可迁移组件 | score threshold calibration、prediction-set calibration、abstention/review policy、risk-coverage ledger、shift-aware recalibration gate。 |

对 CogGuard 的用法：P10 只放在 `calibration / risk-control / abstain` 层。必须先有 qualified Gold、固定 loss、独立 calibration split，再谈 CRC 或类似 selective-risk 机制。禁止把 CRC 描述为 harmfulness classifier、Gold 生成器或 OOD 防线。

## 3. 严格实现路线

### 3.1 Qualified Gold schema

Gold 标注单位应是冻结后的 community/event snapshot，而不是 Discovery 中的单条内容、单个账号或边。推荐 schema：

```yaml
gold_version: string
snapshot_id: string
community_id: string
event_window: {start: datetime, end: datetime}
discovery_batch_id: string
label_unit: community_snapshot

harmful_intent:
  label: harmful | not_harmful | unclear | abstain
  categories: [propaganda, harassment, hate, scam, offline_risk, manipulation, other]
  evidence_items: [content, target, tactic, coordination_context, provenance]
  rationale: string
  adjudication_status: single | double | adjudicated

potential_impact:
  severity: none | low | medium | high | critical | unclear
  affected_targets: [individual, group, institution, public_discourse, platform_integrity, offline_safety]
  mechanism: string
  rationale: string

observed_impact:
  label: observed | not_observed | insufficient_evidence
  measurements: [reach, engagement_shift, target_response, organic_user_behavior, off_platform_trace]
  evidence_window: string
  rationale: string

calibration_fields:
  model_version: string
  score_vector: object
  confidence: float
  ood_score: float
  abstain_reason: string
```

关键约束：`intent`、`potential impact`、`observed impact` 必须独立标注、独立报告、独立评估。`potential_impact=high` 不推出 `observed_impact=observed`；`observed_impact=observed` 也不自动推出 `harmful_intent=harmful`。

### 3.2 Matched coordinated-harmless controls

必须构造 matched controls，而不是只拿随机普通社区做负例。至少包含：

- coordinated-harmless：粉丝应援、公益动员、正常 campaign、危机响应、新闻事件协同传播。
- organic high-activity：同主题、同平台、同窗口、同规模但无明显组织策略的自然热点。
- topical IO/control：同主题 controls，用于防止模型只学 topic。
- platform/time matched：同平台、同采集策略、相近窗口，避免 API 或时间分布 shortcut。

匹配变量至少包括平台、语言、事件类型、窗口长度、社区规模、内容量、互动量、主题、目标实体、媒体类型。每个 positive harmful community 应有一个或多个 matched coordinated-harmless / organic controls。

### 3.3 模型候选

模型只在 Gold 和 controls 到位后进入训练。候选从可解释、可控基线开始，再进入 group/set/graph：

- community MIL：instances 是 posts、accounts、reply threads、media items；bag label 是 community harmfulness。
- Set model：Set Transformer 或 permutation-invariant pooling，适合冻结社区证据集合。
- graph-set candidate：community graph embedding + set evidence fusion，需控制 graph size / popularity confounders。
- multimodal candidate：text、image、video、network、time、target、provenance 的 late fusion 或 gated fusion。

禁止把固定 Bayesian 权重当作主模型或 trained artifact。固定 Bayesian weights 只能作为 heuristic baseline。

### 3.4 Calibration、OOD 与 abstain

必须实现四个门：

- Calibration split：独立于训练和 prompt tuning，用于阈值、risk-control、abstention policy。
- OOD detection：对平台、语言、事件类型、campaign family、时间窗口、媒体类型、社区规模做分布监测。
- Abstain policy：证据冲突、OOD 高、校准失效、Gold 不覆盖、confidence 不足时进入人工复核。
- Risk ledger：报告 ECE、Brier、NLL、risk-coverage、AURC、OOD AUROC/FPR95、abstain rate、manual review burden。

CRC 或类似 selective-risk 协议只在 loss 单调、有界、Gold 固定、calibration/test exchangeability 可辩护时使用。campaign/platform/time shift 下要重新校准、加权校准或降级为人工复核，不允许继续声称原保证有效。

### 3.5 Holdout 与人工 adjudication

验证必须包含：

- leave-campaign-out：同一 campaign family 不同时出现在训练和测试。
- leave-platform-out：至少留出一个平台或平台语境。
- forward-time holdout：用过去训练/校准，用未来窗口测试。
- event/topic holdout：避免同事件或同主题模板泄漏。
- user/source disjoint：避免同一核心账号、域名、媒体源跨 split 泄漏。
- human adjudication：双人标注、冲突仲裁、标签指南版本、样本证据包、错误类别审计。

人工复核不是可选项。Harmfulness 涉及 intent 与 impact，必须保留证据链和仲裁记录，否则模型结果不能晋级为 production artifact。

### 3.6 版本治理

每次 Gold、特征、模型、校准、评估协议变化都要版本化：

- `gold_version`：标签指南、标注员、仲裁规则、样本抽样策略。
- `feature_version`：证据抽取、模态、文本模型、图构造、时间窗口。
- `model_version`：训练数据、超参、seed、checkpoint、baseline family。
- `calibration_version`：calibration split、loss、threshold、abstain policy。
- `evaluation_version`：holdout 定义、metrics、错误审计模板。
- `promotion_decision`：research-only、shadow、human-in-loop、production-blocked。

## 4. Baseline matrix

| Baseline | 输入 | 用途 | 不允许的解释 |
| --- | --- | --- | --- |
| Majority | Gold train label prior | sanity check / class imbalance floor | 不能作为有用 harmfulness detector。 |
| Content-only | post text/media content，不含 coordination features | 检查 toxicity/veracity/content shortcut | 不能说内容 toxic 就是 harmful coordination。 |
| Coordination-only | graph/time/similarity/coordination features，不含 semantic harm | 检查 coordination-as-harm shortcut | 不能说协调强就是有害。 |
| Fixed heuristic | 人工规则、固定阈值、固定 Bayesian weights | 显式 heuristic baseline | 固定 Bayesian 权重只能在这里，不能作为主模型或 production artifact。 |
| Calibrated linear | 线性/逻辑回归 + calibration | 可解释低容量基线 | 不能跳过 campaign/platform/time holdout。 |
| MIL | instance encoder + bag/community label | 聚合社区内 posts/accounts/replies | 不能把 instance toxicity 当 community intent。 |
| Set Transformer | permutation-invariant community evidence set | 检查 set-level aggregation 能力 | 不能忽略 matched controls 和 size confounders。 |
| Multimodal | text-image-video-network-time fusion | 评估多模态证据增益 | 不能把 item-level fake-news 迁移结果当 community harmfulness。 |
| Graph-set | community graph + evidence set | 建模结构、互动、模态联合 | 不能把 P13 campaign-vs-organic label 当 harm label。 |

Baseline 报告必须包含每个模型的 matched-control 错误、holdout 性能、校准指标、abstain 指标和人工复核样本，不得只报告单一 F1。

## 5. 当前完成度与禁止主张

当前完成度：

- 已完成：任务边界、canonical evidence synthesis、三篇精读迁移结论、实现路线、baseline matrix、验证门槛。
- 未完成：qualified community-level Harmfulness Gold。
- 未完成：matched coordinated-harmless benchmark。
- 未完成：trained production artifact。
- 未完成：campaign/platform/time holdout 实验结果。
- 未完成：Weibo / Douyin / XHS 或未来目标平台的完整本地验证。
- 未完成：可主张 SOTA 的统一指标、公开 benchmark 或跨任务排名。

禁止主张：

- 暂无合格 Gold，不得声称 Harmfulness 标签已被验证。
- 暂无 trained production artifact，不得声称可部署。
- 暂无 SOTA result，不得声称优于文献或闭合领域。
- IO membership != harmful intent。
- coordination strength != harmful intent。
- toxicity/veracity != harmful coordination。
- potential impact != observed impact。
- campaign-vs-organic != harmful-vs-harmless。
- CRC/calibration != harmfulness classifier。
- source coverage pass != global absence proof。

## 6. 可操作优先级

### P0：先建立任务可验证性

- 冻结 Stage 2 IO contract：只读 `DiscoveredClusterBatch` / `EventSnapshot`，禁止回写 Discovery 或重聚类。
- 写出 Gold annotation guideline v0，包括 intent、potential impact、observed impact、abstain 的独立定义和反例。
- 构建最小人工标注集，必须包含 matched coordinated-harmless controls。
- 建立 evidence packet：每个社区的内容、目标、互动、时间、模态、provenance、Discovery metadata。
- 定义 holdout plan：campaign、platform、time、event/topic、user/source disjoint。

P0 验收指标：

- 至少一个 `gold_version` 可审计，含双人标注和 adjudication 记录。
- 每个 positive 类别至少有 matched coordinated-harmless 或 organic controls。
- 任意样本可从 label 追溯到证据包和冻结 Discovery batch。
- 训练、校准、测试 split 无同源泄漏说明。

### P1：建立可靠 baseline 与校准

- 跑 majority、content-only、coordination-only、fixed heuristic、calibrated linear。
- 固定 Bayesian 权重只作为 fixed heuristic baseline。
- 加入 MIL / Set Transformer 初版，报告 matched-control errors。
- 建立 calibration split、OOD scoring、abstain policy。
- 输出 risk ledger，而不是只输出 F1。

P1 验收指标：

- 每个 baseline 报告 macro-F1、per-class recall、ECE、Brier、NLL、risk-coverage、AURC、abstain rate。
- 至少完成 leave-campaign-out 与 forward-time holdout。
- 明确 content-only 与 coordination-only 的 shortcut failure cases。
- 人工复核队列覆盖高分错例、低分漏例、OOD、高不确定样本。

### P2：扩展多模态与图集合模型

- 加入 multimodal fusion，做 modality ablation。
- 加入 graph-set candidate，做 size-only、degree-only、metadata-only、text-only、structure-only 消融。
- 加入平台/语言扩展验证。
- 在 shadow setting 中评估 review burden 和 drift。

P2 验收指标：

- 多模态或 graph-set 的增益必须在 campaign/platform/time holdout 与 matched controls 上同时成立。
- OOD 与 abstain 不能只改善平均指标，必须降低高风险错误或明确增加复核成本。
- 每次模型晋级都附带 unresolved risk audit 和禁止主张清单更新。

## 7. 最小验收门槛

一个 Harmfulness 实现只有同时满足以下条件，才能从 research-only 进入下一阶段：

- 有 qualified Gold，并且 Gold 的 intent、potential impact、observed impact 独立。
- 有 matched coordinated-harmless controls。
- 有 campaign/platform/time holdout，而不是随机 split 单点结果。
- 有 calibration、OOD、abstain 与人工 adjudication。
- 有 baseline matrix 全量对照，且 fixed Bayesian weights 仅作为 heuristic baseline。
- 有版本治理和可追溯证据包。
- 明确报告尚未覆盖的 harm family、平台、语言、事件类型和部署风险。

在这些条件满足前，CogGuard 可以实现 research-only Harmfulness pipeline 和报告脚手架，但不得声称 production-ready、SOTA、统一 public benchmark 已闭合，或“文献已证明无人做过”。
