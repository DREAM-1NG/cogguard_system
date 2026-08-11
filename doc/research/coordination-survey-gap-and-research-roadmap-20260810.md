# CogGuard Coordination：Survey 差距审计与研究路线

> 日期：2026-08-10
> 范围：Coordination Discovery 与 harmful Coordination Detection；不讨论 propagation、Student/Teacher 审查链
> 决策：冻结生产 Discovery，所有新方法只做离线研究；达到晋级门禁前不激活研究模型
> 第一手框架：[Mannocci et al., ACM Computing Surveys 2026](https://doi.org/10.1145/3839225)
> 精读记录：[Mannocci Survey deep read](evidence/mannocci-survey/deep-read/report.md)
> 检索制品：`research-wiki/literature_runs/20260810T103552Z-how-should-cogguard-improve-strict-coordination-/`

## 1. 结论

CogGuard 当前主要完成 **Coordination Discovery** 的生产工程闭环，没有完成可主张的 harmful Coordination **Detection**。生产 Discovery 使用冻结的 `coordination-evidence-runtime-v2`；研究 Stage 1 和 Stage 2 虽有代码与测试，但均未生产激活。

Bot detection **已经接入 CogGuard**：API、后端服务、模型适配器、账号列表/详情和前端调用链均存在。严格表述应为“生产调用路径已接入，实际推理依赖有效治理激活指针”。Bot 输出仍是账号级 authenticity proxy，不是经验证的社区真实性标签，也不能代表 harmfulness。

Discovery 研究候选目前没有稳定超过生产 evidence prior。现有同协议比较只完成 `10/30` 个可比 pair：Russia 上生产主线四项均胜，Venezuela 上候选四项均胜，campaign 平均差为负，所有报告的置信区间跨零，且 seed 与 official fold 耦合。结论只能是 candidate offline-only，不能继续通过增加模型复杂度绕过实验可信度问题。

## 2. 术语与任务边界

### 2.1 Survey 与 CogGuard 的术语映射

| Survey 术语 | Survey 含义 | CogGuard 对应术语 | 当前状态 |
|---|---|---|---|
| Detection | 从用户活动中区分协同与非协同账号，输出标签、簇或社区 | Discovery | 生产工程闭环完成 |
| Characterization | 对已发现群体输出 authenticity、harmfulness、orchestration、time-variance 指标 | 四维表征 | 部分完成 |
| Harmfulness characterization | 判断意图、潜在危害、观测影响及目标 | harmful Coordination Detection | 未完成 |
| Attribution | 识别账号背后的组织、运动、国家或交易主体 | 黑灰产核实与归因 | 仅能作为后续独立取证链 |

项目文档必须固定使用下面的链路，避免把传播预测和多智能体审查混入 Coordination 两阶段：

```text
Observable actions
  -> Coordination Discovery
  -> DiscoveredClusterBatch
  -> Four-dimensional characterization
  -> Harmful Coordination Detection with abstention
  -> Analyst adjudication
  -> Optional black-market / transaction attribution
```

### 2.2 严格任务定义

**Discovery** 的输入是 `EventSnapshot` 中的账号、动作、对象、关系、内容和时间，目标是发现比零模型或匹配对照更异常的账号关系与群体。它不以内容是否有害、账号是否为 Bot 或是否属于已知 IO 为定义条件。

**Detection** 的输入是冻结的 `DiscoveredClusterBatch`、原始证据和四维表征，目标是给出有害协同的多标签、校准概率与拒判结果。它必须能够区分：

- 协同且有害；
- 协同但无害；
- 非协同但内容有害；
- 证据不足或分布外。

**Attribution** 不能由 Discovery 社区直接推出。交易、控制关系和幕后实体需要资金、聊天、账号控制、平台处置或其他独立取证证据。

## 3. 当前系统完成度

### 3.1 状态矩阵

| 能力 | 代码 | 系统接入 | 合格研究验证 | 生产激活 | 判断 |
|---|:---:|:---:|:---:|:---:|---|
| 冻结 evidence-first Discovery | 是 | 是，爬取成功后自动编排 | 有工程测试与案例证据；无群体 Gold | 是 | 工程完成，研究主张受限 |
| 研究 Stage 1（TSGS/MHCR/Leiden） | 是 | 仅研究 runner | compact IOHunter pilot；未稳定优于生产 | 否 | 候选，不可激活 |
| Stage 2 harmful Detection | 是 | 仅研究 runner | 无 harmful-CIB 目标实验 | 否 | 未完成 |
| Bot detection | 是 | API、服务、账号页面已接入 | 有单元、服务、API 测试 | 条件激活 | 已接入，需有效模型指针 |
| 社区 authenticity | 有账号 Bot 信号 | 未形成正式群体输出 | 无聚合校准实验 | 否 | 未完成 |
| Orchestration | 有同步、结构、核心/桥接账号证据 | 在 Discovery artifact 中输出 | 未做集中/分布/自发 Gold 验证 | 部分 | 表征证据，不是正式分类 |
| Time-variance | 多尺度窗口、lineage、稳定性、成员迁移 | 在 Discovery artifact 中输出 | 有工程行为，缺跨事件外部效度 | 部分 | 四维中最完整 |
| Harmfulness | Stage 2 分类代码、外部内容信号接口 | 无合格 active artifact | 无独立群体标签与跨域结果 | 否 | 未完成 |

### 3.2 生产 Discovery 的实际调用链

```text
crawl.execute
  -> MongoDB normalized posts/comments
  -> process_successful_crawl
  -> EventSnapshot
  -> analysis run(coordination_discover, propagation_analysis, student)
  -> AnalysisExecutor
  -> SnapshotCoordinationEngine
  -> coordination-evidence-runtime-v2
  -> checksummed artifact
  -> review-case projection
  -> /api/v2/review-cases
```

关键实现证据：

- 爬取后编排：[crawl_tasks.py](../../system/backend/app/tasks/crawl_tasks.py)
- 统一 case 编排：[review_case_orchestrator.py](../../system/backend/app/services/review_case_orchestrator.py)
- 分析执行与 artifact 回退：[executor.py](../../system/backend/app/core/analysis/executor.py)
- 冻结 Discovery 接口：[coordination_discover.py](../../system/backend/app/core/analysis/coordination_discover.py)
- 业务投影：[review_case_analysis_projection.py](../../system/backend/app/services/review_case_analysis_projection.py)
- 读取 API：[review_cases.py](../../system/backend/app/api/v2/review_cases.py)

当前主线输出社区、账号风险层级、证据边、窗口、lineage、覆盖率、null-model、扰动稳定性、domain shift 和 abstain。它已满足“可运行、可存储、可查询、可解释”的工程闭环。

### 3.3 Bot detection 已接入，但真实性聚合未完成

系统证据：

- API：[accounts.py](../../system/backend/app/api/v1/accounts.py)
- 服务：[bot_detection_service.py](../../system/backend/app/services/bot_detection_service.py)
- 严格模型适配器：[trained_bot_detection.py](../../system/backend/app/core/trained_bot_detection.py)
- 研究推理：[inference.py](../../system/research/social_bot_detection/inference.py)
- 账号列表/详情投影：[account_service.py](../../system/backend/app/services/account_service.py)
- 前端调用：[accounts.ts](../../system/frontend/src/api/accounts.ts) 与 [accounts/index.vue](../../system/frontend/src/views/accounts/index.vue)
- 测试：[test_botrhg_bot_detection.py](../../system/backend/tests/test_botrhg_bot_detection.py) 与 [test_account_security.py](../../system/backend/tests/test_account_security.py)

当前缺口不是“没有 Bot 检测”，而是从账号预测到群体 authenticity 的测量链不完整：

1. 必须先做平台条件校准，不能直接平均未经校准的分数。
2. 群体输出至少包含有效账号数、覆盖率、缺失率、均值、中位数、分位数和异质性。
3. 需要区分自报 Bot、善意自动化、部分自动化、人工 Troll、假身份和未知。
4. 当覆盖不足或平台分布外时输出 `unknown/abstain`，而不是硬判“非真实”。
5. 群体真实性与 harmfulness 分开训练、评估和审批。

建议的群体 evidence contract：

```json
{
  "dimension": "authenticity",
  "scope": "community",
  "account_count": 42,
  "evaluated_count": 34,
  "coverage": 0.81,
  "missingness": 0.19,
  "calibrated_bot_probability": {
    "mean": 0.44,
    "p50": 0.38,
    "p90": 0.79
  },
  "platform_calibration_version": "...",
  "evidence_ids": ["..."],
  "decision": "evidence_only",
  "abstain_reason": null
}
```

## 4. Discovery 与前沿研究的主要失配

### 4.1 生产主线的合理部分

当前系统与高水平研究对齐的部分包括：

- 先保存账号到 URL、hashtag、entity、target、discussion、native relation、near-duplicate 等可观测对象的证据，再投影账号关系。
- 输出有向、加权、多证据边并保存证据引用，而不是直接生成“协同标签”。
- 使用 1h/6h/24h 重叠窗口，输出逐窗社区、谱系、成员迁移和稳定性。
- 使用 null model、扰动稳定性、证据覆盖和 abstain，承认无 Gold 场景的不确定性。
- 保持 frozen production runtime，不因离线单次高分切换模型。

这些机制分别与 Pacheco 的 actor-artifact 证据网络、Coordination Network Toolkit 的有向加权标记多重图、Tardelli 的动态社区分析及 Survey 的验证要求一致。它们是合理工程选择，但已是 prior art，不能单独作为新颖性主张。

### 4.2 仍然存在的结构失配

| 优先级 | 失配 | 当前表现 | 文献依据 | 研究处理 |
|---:|---|---|---|---|
| P0 | 实验 pair 不完整 | 仅 `10/30` 可比，seed/fold 耦合 | TGB 式时间/实体隔离思想；Survey validation | 先补齐比较，不改模型 |
| P1 | 社区发现前可能过早压平证据层 | 生产有多证据边，但部分统计/社区步骤使用聚合权 | Toolkit；Iannucci et al. | 保留 directed weighted multiplex contract 到社区算法 |
| P2 | 固定阈值/手工权重缺少统计可识别性 | null model 存在但未与多种骨干公平比较 | Marcaccioli & Livan；Yassin et al. | PF/NC/ECM 与 fixed threshold 同协议消融 |
| P3 | 时间主要依赖硬窗口和后处理 lineage | 有多尺度与重叠，但没有层内连续时间核 | Iannucci et al.；Tardelli et al. | 比较 hard windows、exponential kernel、activity normalization |
| P4 | 社区算法仍以单层 Leiden 为主 | lineage 是逐窗分区后的匹配 | multislice Leiden；Flow Stability 路线 | 比较 single-layer、multislice、flow/stability |
| P5 | 学习目标与最终 Discovery 单位错位 | 旧候选重构账号-对象边或用 IO 账号 proxy | Survey；Luceri；Seckin | 最后才做 pair/community objective-aligned learner |

### 4.3 为什么旧研究候选没有稳定超过生产基线

1. **目标错位**：账号-对象边重构、账号 IO membership 与最终账号对/社区 Discovery 不是同一预测单位。
2. **证据压缩**：relation、direction、time 和 layer 若过早聚合，复杂模型看到的信息反而少于生产规则。
3. **时间建模过浅**：bucket embedding 和后置 Jaccard lineage 不能替代事件级时间核或动态消息传递。
4. **负样本不公平**：随机负例过易，可能让模型学习平台、节点度或 campaign 捷径。
5. **数据代理局限**：IOHunter 提供已知 IO 账号 membership，不提供真实协同边、社区或 harmful intent Gold。
6. **协议未闭合**：只有 Russia 与 Venezuela 完成生产可比结果，且 seed/fold 耦合，无法分离优化随机性和数据折差异。
7. **复杂度没有带来可迁移增益**：Russia 与 Venezuela 的结果方向完全反转，说明 domain sensitivity，而不是稳定优势。

现有结果详见 [coordination-production-comparison-20260810.md](coordination-production-comparison-20260810.md)。在该证据下，任何“研究模型已优于系统模型”的表述都不成立。

## 5. 来源级领域映射

| 来源 | 直接支持 | 不支持的过度主张 | 对 CogGuard 的用途 |
|---|---|---|---|
| [Mannocci et al. 2026](https://doi.org/10.1145/3839225) | Discovery/characterization 分离，四维框架，验证缺口 | 不提供新模型或统一 benchmark | 任务定义、标签契约、主张边界 |
| [Pacheco et al. 2021](https://doi.org/10.1609/icwsm.v15i1.18075) | actor-artifact 证据投影和案例 Discovery | 不提供 harmfulness Gold | 生产 evidence-first 基线依据 |
| [Graham et al. 2024](https://doi.org/10.1007/s42001-024-00260-z) | directed weighted labeled multigraph 和工具化分析 | 不证明多重图必然提高准确率 | P1 evidence contract |
| [Iannucci et al. 2026](https://doi.org/10.1609/icwsm.v20i1.42682) | 时间核、activity normalization、multiplex、multislice 社区 | precision 提升可伴随 recall 下降；IO label 仍是 proxy | P1/P3/P4 对照实现 |
| [Marcaccioli & Livan 2019](https://doi.org/10.1038/s41467-019-08667-3) | Pólya urn 统计骨干 | 不是时序协调检测器 | P2 层内边显著性基线 |
| [Yassin et al. 2025](https://doi.org/10.1371/journal.pone.0316141) | 统计骨干结构保真比较，无通用赢家 | 不提供 COB 标签 | P2 多骨干消融与结构指标 |
| [Tardelli et al. 2024](https://doi.org/10.1073/pnas.2307038121) | 动态社区、成员流、稳定性和 archetype | 不提供 harmful intent Gold | P3/P4 动态输出与案例验证 |
| [Luceri et al. 2024](https://doi.org/10.1145/3589334.3645529) | 多行为网络、六国 IO、账号检测性能 | pooled/CV IO 账号标签不等于 leave-campaign harmfulness | 强账号 baseline 与泛化审计 |
| [Seckin et al. 2025](https://doi.org/10.1609/icwsm.v19i1.35958) | 26 campaign 与同主题同时间 controls | controls 可能含未标注协调；不是 harmful-intent 数据 | 更严格 IO membership 评估 |
| [Loru et al. 2024](https://doi.org/10.1016/j.osnem.2024.100289) | 协调度与毒性并非单调关系 | 反驳“越协调越有害” | Detection 负例和主张约束 |

没有幸存的新颖性空白包括：directed multiplex graph、时间衰减、动态社区、Leiden、统计骨干本身。可主张的研究贡献只能来自严格的任务适配、目标对齐、三平台数据契约、同协议消融和稳定超过生产强基线的证据。

## 6. 研究优化路线

### 6.1 Discovery：按优先级执行的离线阶梯

#### P0：先修实验可信度

- 补齐 `30/30` candidate-production 配对或逐项记录不可恢复原因。
- 固定 official fold，在每个 fold 内独立运行多个 model seed；不得再把 seed 与 fold 绑定。
- 所有 TF-IDF、SVD、scaler、文本 encoder 校准仅在训练数据拟合。
- split 单位固定为 campaign，补充 leave-platform-out 和 forward-time。
- 统一输入 snapshot、候选账号、预算、评估单位和 metrics。
- 报告每 campaign、macro mean、bootstrap CI、paired effect、最差 campaign 和运行成本。

#### P1：保留 directed weighted multiplex evidence graph

- 节点类型：account、content、URL/domain、hashtag、entity、target、platform。
- 边类型：post/share/reply/mention/co-URL/co-hashtag/near-duplicate/native relation。
- 每条边保存 direction、timestamp、layer、raw strength、provenance 和 missingness。
- 社区阶段前不得默认 sum/mean flatten；flatten 只能作为显式 baseline。

#### P2：统计骨干比较

在每个 evidence layer 内比较：

- fixed global threshold；
- degree/activity-matched null；
- Pólya filter；
- Noise-Corrected；
- Enhanced Configuration Model，若输入假设满足。

除了 actor/group precision-recall，还必须报告节点/边保留率、连通性、reachability、weight entropy、layer coverage、运行时间和峰值内存。没有任何骨干被预设为赢家。

#### P3：连续时间与活动归一化

比较：

- 现有 1h/6h/24h、50% 重叠 hard windows；
- exponential temporal kernel；
- activity-normalized similarity；
- layer-specific decay；
- 无时间信息对照。

时间参数只能在 validation campaign 选择，不能在 test campaign 调节。指标需包含 recall 损失、首次发现时延和社区稳定性，避免只优化 precision。

#### P4：动态社区对照

比较：

- 现有逐窗 Leiden + Jaccard lineage；
- multislice Leiden；
- Flow Stability 或等价流保持方法；
- 静态聚合社区。

输出完整 window-level graph、community ID、成员进入/退出、split/merge、稳定性、transition matrix 和 lineage provenance。动态一致性是评价维度，不能作为伪标签直接训练主判定。

#### P5：目标一致的学习模型

只有 P0-P4 找出可靠机制后，才实现 pair/community learner：

- 输入保留 relation、platform、continuous time、evidence strength 和可选训练内文本表示。
- 主任务直接预测账号对协调概率或社区 ranking，不再只重构 account-object edge。
- negatives 按 platform、relation、time proximity、degree/activity 匹配。
- 辅助任务可包含 layer agreement、temporal consistency 和 community stability。
- HGT/TGN 级消息传递只有在轻量 pair model 已经超过 production prior 后才进入实验。

### 6.2 Discovery 的晋级门禁

研究候选只有同时满足以下条件，才可从 `offline-only` 进入 shadow：

1. `30/30` 同协议比较完成，或缺失 pair 有审计记录且不造成选择性报告。
2. campaign-mean paired improvement 的 95% CI 不跨 0。
3. 预注册主指标上最差 campaign 不低于 production prior；若允许容差，必须事先固定。
4. actor/group precision-recall、community stability、evidence coverage 和 abstention 同时达标。
5. 结论对 seed、fold、threshold、window 和 backbone 扰动稳定。
6. 无数据泄漏、无随机 action/account 混切、无 no-edge 异常高分捷径。
7. runtime、内存和 artifact 大小满足生产预算。
8. shadow 阶段不改变生产判定，只记录双轨差异并经分析员复核。

## 7. Harmful Coordination Detection 完成路径

### 7.1 标签不能继续借用 IO membership

最小群体标签契约应独立保存：

| 标签 | 值域 | 证据要求 |
|---|---|---|
| `coordination_status` | coordinated / organic / uncertain | Discovery 证据与分析员裁决 |
| `io_membership` | platform-verified / control / unknown | 平台或数据集 provenance |
| `authenticity` | authentic / inauthentic / mixed / unknown | 身份、Bot、平台处置及反证 |
| `harmfulness` | 多标签 harm types + none + unknown | 内容、目标、意图、影响及外部事实 |
| `orchestration` | spontaneous / decentralized / centralized / unknown | 网络、同步、组织和外部证据 |
| `time_variance` | static / episodic / adaptive / unknown | 多窗成员、结构、内容与强度变化 |
| `decision` | predict / abstain | 证据覆盖、OOD、漂移和校准 |

每个标签同时保存 `scope`、`valid_time`、`provenance`、`annotator_distribution`、`confidence`、`evidence_ids` 和 `missingness_mask`。

### 7.2 数据与评估

- IOHunter 和 Seckin 数据用于 `io_membership` 与 Discovery proxy，不得改名为 harmfulness Gold。
- 必须建立 coordinated-but-harmless 对照；当前“特朗普访华”数据可做 Discovery 案例，但无人工裁决时不进入 Detection 性能表。
- 分割按 campaign，附 leave-country、leave-platform 和 forward-time。
- 主指标为 per-harm PR-AUC、macro-F1、ECE/Brier、risk-coverage、AURC/partial AURC。
- 必须分别报告 novelty/OOD、低证据、跨平台和 temporal drift 的拒判。
- 固定贝叶斯权重和处置阈值只保留为显式 heuristic baseline；正式模型参数必须从训练/校准集学习。

### 7.3 从研究代码到生产能力

Stage 2 完成需要同时具备：

1. 版本化的 `DiscoveredClusterBatch -> DetectionCase` 适配器。
2. 独立 train/validation/test campaign 和标签审计。
3. fitted artifact、schema、hash、训练数据指纹和 calibration provenance。
4. OOD/selective prediction 与明确 abstain 原因。
5. 分析员审批、不可变 verdict 和模型激活治理。
6. shadow 对比、回滚指针、延迟和资源门禁。
7. API 与前端清楚展示 Discovery evidence、四维指标、模型版本和人工裁决，不把 proxy 显示成事实。

在这些条件完成前，`system/research/coordination_detect` 应继续保持 research-only，现有分类器代码不能被描述为 Detection 已完成。

## 8. 可主张与不可主张边界

当前可以主张：

- CogGuard 已实现可运行、可追溯的 evidence-constrained Coordination Discovery。
- 系统能输出动态窗口、社区谱系、账号证据和拒判信息。
- Bot detection 已接入账号分析链，可提供账号级 authenticity evidence。
- 研究候选、生产基线和强简单 baseline 已开始同协议比较。

当前不能主张：

- 已完成 harmful Coordination Detection。
- Bot 分数能够判定社区真实性或有害性。
- IO membership 等同于协调边、群体 Gold 或 harmful intent。
- TSGS、MHCR、E-IDGU、TemporalMAGNN、HGT/TGN 或 Leiden 本身构成新颖贡献。
- 研究候选稳定优于生产主线。
- 三平台单事件案例足以支持跨事件、跨平台或因果结论。
- 社区结构能够完成幕后组织或黑灰产交易归因。

## 9. 执行顺序与停止条件

1. 完成 P0；若配对结果仍不稳定，停止新模型开发并审计数据/标签/指标。
2. 依次运行 P1-P4，每次只改变一个机制，保留生产基线与前一最强公平 baseline。
3. 只有成熟组件的增益可重复时才进入 P5；否则复杂 GNN 不进入队列。
4. Discovery 研究通过门禁后，仅进入 shadow，不直接替换 active pointer。
5. Detection 与 Discovery 并行但数据职责隔离；没有 coordinated-harmless labels 时，Detection 保持 blocked。
6. 所有新实验、缓存、模型与报告继续写入 `G:`，不得写入 `C:`。

## 10. 证据索引

- Survey MarkItDown 转换：`doc/research/evidence/mannocci-survey/`
- Survey 深读报告：[report.md](evidence/mannocci-survey/deep-read/report.md)
- Survey source map：[source_map.json](evidence/mannocci-survey/deep-read/source_map.json)
- re-search 最终报告：`research-wiki/literature_runs/20260810T103552Z-how-should-cogguard-improve-strict-coordination-/report.md`
- 文献差距矩阵：`research-wiki/literature_runs/20260810T103552Z-how-should-cogguard-improve-strict-coordination-/difference-matrix.md`
- 来源账本：`research-wiki/literature_runs/20260810T103552Z-how-should-cogguard-improve-strict-coordination-/source-ledger.json`
- 生产同协议结果：[coordination-production-comparison-20260810.md](coordination-production-comparison-20260810.md)
- 两阶段复现实验状态：[coordination-two-stage-reproduction-results.md](coordination-two-stage-reproduction-results.md)
- 两阶段研究边界：[ADR 0014](../../docs/adr/0014-coordination-two-stage-research-boundary.md)

## 11. 最终决策

生产系统继续使用冻结 evidence-constrained Discovery。研究线不再以“替换生产基线”为默认目标，而是按 P0-P5 建立可证伪的机制比较；只有稳定、跨 campaign、同协议超过生产主线时才进入 shadow。harmful Detection 从独立标签、校准和拒判开始补齐，不能通过复用 IO membership、Bot score、协调强度或固定启发式权重宣布完成。
