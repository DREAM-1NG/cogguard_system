# Coordination Characterization: Authenticity

状态：文献检索与三篇重点论文精读完成；系统方法和社区级 Gold 尚未完成。

## 研究边界

本分区研究已经经过 Coordination Discovery 的社区是否具有可核查的真实性特征。它不重新发现社区，也不把以下变量合并为一个分数：

- coordination：账号是否表现出可观测的协同行为；
- automation：账号是否具有自动化迹象；
- identity authenticity：账号身份、控制者或来源披露是否可信；
- community composition：社区由真实、非真实或混合成员构成；
- harmfulness：社区的协调行为是否具有有害意图、潜在影响或已观察影响；
- attribution：行为能否归属于特定组织、行动或控制关系。

CogGuard 的研究目标限定为四状态社区输出：authentic、inauthentic、mixed、unknown。账号级 bot probability 只能作为带版本、平台、时间和覆盖率 provenance 的辅助证据，不能作为社区 Gold。

## 已完成证据

### Beast 文献工作流

完整工作流位于 research-wiki/literature_runs/20260810T114245Z-how-should-cogguard-validate-community-level-aut/。

- map/hunt/compare/report 全部完成；
- 15 篇论文通过四个 Beast lane 交叉核验；
- requested-source coverage 为 pass；
- 三个研究 gap 均为 narrowed，没有 survived gap，因此不能提出普遍新颖性或领域缺失主张；
- 接受集不存在共享社区真实性 Gold、共同协议和共同指标的直接 SOTA benchmark，禁止跨论文拼接数值排名；
- Semantic Scholar/OpenAlex 对抗查询已执行并记录，但匿名访问出现 HTTP 429，结论只覆盖接受集。

### 重点精读

| 论文 | 对 CogGuard 的直接结论 | 不可迁移内容 |
|---|---|---|
| Echeverria et al. 2018, LOBO | 使用 leave-campaign、leave-platform、forward-time 替代随机账户划分；按 campaign 做聚类 bootstrap | LOBO 的账户 bot recall 不是社区真实性准确率 |
| Rauchfleisch & Kaiser 2020 | 保存连续自动化证据、做本地校准、基率敏感 PR、重复测量和阈值稳定性审计 | Botometer v3 阈值、CAP 或 score distribution 不能作为社区 Gold/prevalence |
| Nizzoli et al. 2021 | 保留 Discovery 证据图、过滤轨迹、社区谱系和结构/文本/自动化画像，作为 Characterization dossier | 协调强度、Louvain 社区或 Botometer 画像不能自动判定真实性 |

精读制品位于 deep-reads/ 下的三个论文目录。三份报告均具有合法 source_map.json、完整视觉 manifest，并通过 Paper Deep Reader strict validator。

## 建议的任务定义

输入是冻结且带 provenance 的 DiscoveredClusterBatch。每个社区样本必须固定：

- community_id、成员集合和核心/上下文时间窗；
- Discovery 使用的证据边、关系类型、阈值或过滤轨迹；
- 平台、语言、事件/campaign 和采集覆盖；
- 账号级 bot/automation 输出的模型版本、调用时间、缺失原因和原始连续值；
- 身份披露、共同控制、平台处置和人工 forensic evidence；
- 标签来源、两名分析员判断、冲突裁决和置信度。

标签本体：

| 状态 | 最小语义 |
|---|---|
| authentic | 社区协调行为与公开身份/组织关系一致，没有充分的身份欺骗或隐藏控制证据 |
| inauthentic | 有独立证据支持身份、控制者、来源或草根外观被系统性伪装 |
| mixed | 社区同时包含可区分的真实与非真实成员/子群，单一二值标签会丢失组成信息 |
| unknown | 证据覆盖不足、证据冲突、域外或无法可靠裁决 |

平台 enforcement、IO membership、automation threshold 和 Discovery risk 都不得直接生成这些标签。

## 方法与基线

首先实现显式、可审计的基线，再训练 composition-aware 模型：

1. bot_share_threshold：成员 bot flag 比例阈值，仅作为应被超越的 heuristic baseline。
2. calibrated_mean：按平台/时间校准账号证据后做均值聚合，显式报告 coverage。
3. beta_binomial：传播成员证据不确定性和社区规模差异，但不假设标签即真实性。
4. attention_mil：以社区标签训练成员级证据聚合，输出四状态概率和成员贡献。
5. evidence_set_model：对 automation、identity、control、enforcement、coverage 和 Discovery provenance 分通道建模，禁止把缺失值当作负证据。

固定 Bayesian 权重和处置阈值只能保留为 heuristic baseline；主模型的参数、校准器和拒判策略必须只在训练/validation domain 学习。

## 固定评估协议

- 划分轴：leave-campaign-out、leave-platform-out、forward-time，另保留随机账户划分作为内插上限。
- 关键负例：coordinated-but-authentic、benign automation、human-operated deception、非协调低真实性账号集合。
- 指标：四类 Macro-F1、每类 AUPRC/recall、NLL、Brier、ECE、risk-coverage、固定 selective risk 下的 coverage。
- 统计单元：先在 campaign/domain 内聚合，再对 campaign 做 bootstrap；不得把成员账号当独立样本制造窄区间。
- 压力测试：账号证据 MNAR、community size、成员相关误差、平台/语言缺失、bot detector disagreement、时间漂移。
- 激活门禁：在所有主要 held-domain 协议下超过 transparent baselines，校准和 worst-domain 不退化，并能在覆盖不足时稳定输出 unknown。

## 当前缺口

- 没有独立、双人编码并完成 adjudication 的四状态社区 Gold；
- 没有足够的 coordinated-but-authentic、mixed 和 unknown 对照；
- 没有三平台本地自动化证据校准集；
- 没有 community-level MNAR 与误差传播实验；
- 没有可支持生产激活的 held-campaign/platform/time 结果。

因此，Authenticity 当前状态是“研究定义和验证协议已完成，模型与有效性验证未完成”。任何系统界面只能显示分通道证据和 unknown，不能把 bot 比例或 Discovery 风险包装成正式社区真实性判决。
