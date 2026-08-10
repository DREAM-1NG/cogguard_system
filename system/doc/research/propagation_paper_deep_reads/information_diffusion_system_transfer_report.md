# 信息扩散论文精读综合与传播监测系统迁移报告

> **实际使用来源**：`H:\Zotero\attenger\Projects\CISCN\Propagation` 下 10 篇 PDF、本目录 `assets/paper_text_summary.json`、`assets/evidence_snippets.json` 和逐论文 text-only inventory。  
> **页码约定**：全文使用 1-based `PDF p.N`。  
> **读者画像**：`domain: computer-science-ai`，`audience: cross-disciplinary`，`goal: transfer/reproduce`，`depth: deep`，`language: zh-CN`。  
> **视觉能力说明**：本报告未直接核验 PDF 图像像素内容；图表解释只基于 PDF 文字层、图表标题、正文引用、可抽取文本和已有 evidence snippets。凡涉及图像颜色、坐标、曲线细节、版式关系，均不作像素级断言。  
> **系统定位说明**：本文中的系统功能统一称为“传播监测”。传播监测包含两条链路：观测传播分析解释已采集事实，传播预测基于观测截止前缀输出趋势曲线和下一跳研判。

## 1. 核心结论

信息扩散研究从“解释级联如何发生”逐步走向“在严格时间边界下预测未来规模和下一跳，并报告不确定性”。对当前系统最关键的迁移是：观测传播分析要升级为带证据类型和置信度的 provenance 图，传播预测要从当前可用的已知用户再激活研判继续补齐归纳式新用户候选、严格负采样评测和自适应区间校准。

当前系统已经具备两个基础闭环：

| 系统链路 | 当前实现 | 论文支撑 | 严谨边界 |
|---|---|---|---|
| 观测传播分析 | 从 `raw_posts/raw_comments` 读取当前事件，构建用户传播图，输出传播路径、层级、共享对象、角色、证据链、时间线和摘要布局 | Zhou 2021 的级联图和传播结构分析，Guo 2025 的 5W 数据属性框架 | 只能解释已采集事实；相同对象/时间邻近边应标注为推断关系，不应当作平台确认转发 |
| 传播预测 | 通过 `observed_until` 或 `observation_ratio` 构造观测前缀，加载 Twitter checkpoint，输出 macro 趋势点和 micro 下一跳 Top-K | MINDS 2024 的 macro/micro 共享主干，CasFT 2025 的连续趋势思想，TGN/CAW/DyGFormer/TGB 的动态图预测与评测协议 | 当前主要是已知用户再激活研判；开放世界新用户激活、校准区间和完整多 seed 严格验证仍未完成 |

最重要的工程判断是：观测分析和预测模型必须继续保持分离。观测分析页面可以对齐“知微式传播分析”，但不能混入未来预测结论；趋势预测页面可以展示模型输出，但不能用速度/加速度或活动度排序回退结果替代模型推理。

## 2. 论文清单与迁移角色

| 论文 | 类型 | 研究问题 | 方法核心 | 对传播监测的迁移角色 |
|---|---|---|---|---|
| Gibbs and Candès, 2021, Adaptive Conformal Inference under Distribution Shift | 理论/方法 | 在线预测在分布漂移下如何给出长期覆盖率有保证的预测集合 | 将 conformal miscoverage 作为在线学习信号，更新单个校准参数 `alpha_t` | 用于预测区间校准；当前系统 `calibration_status=unavailable` 应以此方向补齐 |
| Guo et al., 2025, A Survey of Datasets and Tasks for Information Diffusion | 综述/数据任务 | 信息扩散任务和数据集缺少统一分类 | 用 5W 框架划分传播预测、社交机器人检测、虚假信息检测，并按用户/内容/网络属性比较数据集 | 用于系统领域词汇、数据字典和功能边界设计 |
| Huang et al., 2023, Temporal Graph Benchmark | 数据集/基准 | 动态图学习评测不真实、不可复现、负采样过易 | 建立 TGB 数据、loader、evaluator、leaderboard，并强调 historical negatives 和 inductive settings | 用于下一跳评测协议、候选覆盖审计和时间切分规范 |
| Jiao et al., 2024, MINDS | 方法/模型 | macro 规模预测和 micro 下一用户预测常被割裂，跨级联动态被忽略 | sequential hypergraph、social homophily、shared-private 表示、adversarial 和 orthogonality 约束 | 作为当前正式预测模型的主要方法论依据 |
| Jing et al., 2025, CasFT | 方法/模型 | 静态观测特征难以刻画未来流行趋势不确定性 | Neural ODE 提取动态线索，diffusion model 生成未来 popularity trend | 支撑趋势曲线建模；当前系统迁移的是连续单调趋势头，不是完整 diffusion generator |
| Rossi et al., 2020, TGN | 方法/模型 | 静态 GNN 难以处理连续时间交互流 | memory、message、aggregator、updater、embedding 模块处理 timed events | 支撑未来把传播边流建成连续时间事件模型 |
| Souza et al., 2022, Provably Expressive Temporal Graph Networks | 理论/方法 | TGN 类模型表达能力边界不清 | 比较 MP-TGN、WA-TGN，提出 injective temporal message passing 和 PINT | 用于审查模型 backbone 是否具备区分传播结构的能力 |
| Wang et al., 2022, CAW | 方法/模型 | 归纳式 temporal link prediction 不能依赖节点身份 | causal anonymous walks 抽取时间因果 motif，并匿名化节点身份 | 用于开放世界下一跳候选和跨事件迁移 |
| Yu et al., 2023, DyGFormer/DyGLib | 方法/库 | 动态图模型难以捕捉长历史，评测管线不统一 | historical first-hop interaction、neighbor co-occurrence encoding、patching Transformer、统一库 | 用于更强 micro head 和规范化实验管线 |
| Zhou et al., 2021, Cascade Analysis Survey | 综述 | 信息级联分析需要统一问题定义、指标、数据集和方法谱系 | 按 feature/stochastic process/graph/deep learning 梳理 popularity prediction 和 cascade graph | 用于传播分析/规模预测的总体问题框架 |

## 3. 信息扩散领域的问题意识地图

### 3.1 观测传播分析：不是预测，而是重建、解释和证据追溯

Zhou 2021 将 information cascade 视为由传播轨迹、结构和参与者组成的研究对象，并给出 cascade graph 这类图结构定义，节点是参与者，边是交互或传播关系 `[Zhou, PDF p.12]`。这直接对应系统中的传播路径图、层级摘要、源头节点、关键路径和角色分析。

Guo 2025 的 5W 框架把信息扩散拆为 `Who`、`Says What`、`In Which Channel`、`To Whom`、`With What Effect`，并进一步比较数据是否包含 user information、social network、bot label、propagation content、diffusion network、veracity label `[Guo, PDF p.1; Table 1/Table 2]`。这给当前系统一个清晰数据字典：

| 5W 维度 | 系统对象 | 当前可用字段 | 需要补齐 |
|---|---|---|---|
| Who | 用户、账号、协同群组 | `author_id`、`author_name`、平台、角色分数 | 用户质量、账号类型、协同检测输出的正式接入 |
| Says What | 帖子、评论、URL、标签、claim | `content/text/url/hashtag` 等抽取字段 | 对象归一化、实体/话题/claim 聚合 |
| Channel | 平台和传播媒介 | `platform`、事件范围 | 跨平台同源内容对齐 |
| To Whom | 回复、转发、评论链、隐式影响对象 | 显式回复边和部分推断边 | confirmed/reconstructed/inferred 分层证据 |
| Effect | 规模、层级、路径、趋势、下一跳 | 观测规模、层级、路径、模型趋势点 | 区间校准、反事实解释、干预模拟 |

当前系统的观测分析链路可以总结为：

```text
raw_posts/raw_comments
  -> event_id/platform 过滤
  -> 用户节点与传播边构建
  -> 共享对象、时间线、关键路径、层级、角色、证据链
  -> diffusion_summary 摘要布局
  -> 前端传播路径、传播对象、角色分析、时间线展示
```

这个链路的研究风险在于：相同 URL/标签的时间邻近关系只能说明“可能存在传播联系”，不能证明平台真实转发。高水平研究通常会区分观测事实、重建关系和模型推断；因此系统需要把边写成带 provenance 的证据对象，而不是只有 `source -> target`。

### 3.2 宏观预测：规模、增长量和未来趋势不是一个简单回归数

Zhou 2021 指出 popularity prediction 可以是分类或回归问题，并综述特征工程、随机过程、图表示和深度学习方法 `[Zhou, PDF p.1; PDF p.3; Fig.2]`。CasFT 2025 进一步强调，传统方法只用观测期信息，无法直接看到观测期后的真实未来趋势，因此需要建模未来 popularity-increasing trend 的不确定性 `[CasFT, PDF p.1-p.2]`。

对系统而言，macro 预测不应只输出 `predicted_size`，而应至少输出：

```text
observed_size
predicted_size
trend_points = [(step_1, predicted_size_1), ..., (step_H, predicted_size_H)]
direction = rising | stable | declining
intervals = calibrated lower/upper bands
calibration_status
```

当前 `PropagationSequenceJointModel` 已采用非负最终增长头和 Euler-style 单调趋势解码器。形式上可以写为：

```math
z = f_{\theta}(C_{\le t_{obs}}, G_{rel}, H_{cas})
```

```math
\hat y_{final} = y_{obs} + \operatorname{softplus}(g_{\theta}(z_{macro}))
```

```math
h_{k+1} = h_k + \Delta t \cdot F_{\theta}(h_k, k/H, r_{obs}), \quad
\hat y_{k+1} = \hat y_k + \operatorname{softplus}(q_{\theta}(h_{k+1})) \Delta t
```

这里 `C_{\le t_obs}` 是观测截止前传播前缀，`G_rel` 是关系邻居统计，`H_cas` 是阶段超边，`r_obs` 是观测比例。这个实现吸收了 CasFT 的“连续未来趋势”思想，但没有复现 CasFT 的 diffusion model，因此不能宣称已经完成 CasFT 级别复现。

### 3.3 微观预测：下一跳可以是已知用户再激活，也可以是开放世界新用户激活

MINDS 将 microscopic prediction 定义为识别下一个被影响用户，macroscopic prediction 则估计整体影响 `[MINDS, PDF p.1]`。DyGFormer 和 TGN 将问题放到 temporal graph 事件流中，预测给定历史交互前缀后未来边或节点行为 `[TGN, PDF p.1-p.3; DyGFormer, PDF p.3]`。CAW 更强调归纳式场景：不依赖训练时节点身份，而是用匿名时间游走捕捉社会网络演化规律 `[CAW, PDF p.1-p.2]`。

当前系统的下一跳输出更准确地称为“已知用户再激活研判”，原因是公开结果只映射当前事件中可唯一识别的 `author_id/author_name`。模型内部可以对训练 bucket、观测 bucket 和关系邻居 bucket 评分，但匿名 bucket 不能直接展示成真实用户。因此现在的 micro 任务是：

```math
\Pr(u_{next}=u \mid C_{\le t_{obs}}, u \in \mathcal U_{mapped})
```

还不是完整的开放世界任务：

```math
\Pr(u_{new} \in \mathcal U_{future} \setminus \mathcal U_{\le t_{obs}} \mid C_{\le t_{obs}}, \mathcal G_{history})
```

要补齐开放世界下一跳，需要三件事同时成立：

| 能力 | 论文依据 | 系统实现方向 |
|---|---|---|
| 候选检索 | TGN/DyGFormer 的历史交互建模，CAW 的归纳式 motif | 建立跨事件历史互动图和训练用户目录，生成合法候选而不是从未来真实节点注入 |
| 身份映射 | CAW 不依赖身份，DyGFormer/TGN 能处理时间边 | 为 bucket 建立可追溯 `bucket -> user_id` 映射，并报告冲突/覆盖率 |
| 评测协议 | TGB 的 random/historical/inductive negative sampling | 分别报告 Hits@K、MRR、NDCG、candidate recall、historical negative 下的性能 |

### 3.4 多尺度联合：macro 和 micro 必须共享传播状态，但不能硬相互等同

MINDS 的关键问题意识是 macro 和 micro 有互补信息，又有任务特有信息；如果共享/私有表示混乱，会产生污染和冗余 `[MINDS, PDF p.1-p.2]`。论文采用 sequential hypergraph 捕捉跨级联动态，用 social homophily 学用户关系，再用 adversarial learning 和 orthogonality constraints 区分 shared features 与 task-specific features `[MINDS, PDF p.1-p.3; Fig.2]`。

这对当前系统的迁移结论是：macro/micro 可以共享 backbone，但一致性约束必须是软约束，不应把候选用户概率和最终规模硬等同。正确的耦合应当是：

```math
L = L_{final} + \lambda_t L_{trend} + \lambda_u L_{next-user}
    + \lambda_c L_{soft-coupling}
    + \lambda_a L_{adv}
    + \lambda_o L_{orth}
```

其中 `L_soft-coupling` 只约束短期增长方向或 rollout 新增期望，不直接要求：

```math
\sum_{u \in \mathcal U_{candidate}} \sigma(s_u) = y_{final} - y_{obs}
```

因为候选集通常覆盖不完整，且已知用户再激活不等价于最终新增规模。

### 3.5 评测与不确定性：没有严格时间切分和校准，就不能把预测称为可靠

TGB 的核心贡献不是某个模型，而是把动态图评测做成可复现 pipeline，并指出历史负样本比随机负样本更难，inductive setting 需要处理测试中训练未见边 `[TGB, PDF p.1-p.3; PDF p.8]`。DyGFormer/DyGLib 也强调统一训练管线、评测协议和不同负采样策略，否则 baseline 结果会不一致 `[DyGFormer, PDF p.2; PDF p.6]`。

Gibbs and Candès 2021 则提醒，在线预测在分布漂移下需要报告覆盖率，而不是只报告点预测。其核心更新可概括为：

```math
\alpha_{t+1} = \alpha_t + \gamma(\alpha - err_t)
```

其中 `err_t` 是当前预测集合是否 miscover 的观测误差，`gamma` 控制适应速度与稳定性的权衡 `[ACI, PDF p.3]`。迁移到传播趋势预测，就是在验证集或在线回放上根据实际误差持续更新区间宽度，使系统能够报告“区间覆盖是否达标”，而不是展示未校准的置信度。

## 4. 关键图表、表格和算法的 text-only 证据卡

| 论文 | 关键 Figure/Table/Algorithm | 作者意图与可恢复内容 | 对系统的迁移 |
|---|---|---|---|
| Zhou 2021 | Fig.2 taxonomy；Table 1 metrics；Fig.3 growth trends；Fig.7 cascade structures | 图表标题和正文显示该综述按方法谱系组织 popularity prediction，并讨论增长趋势、级联图结构和常用指标 `[Zhou, PDF p.1-p.13]` | 传播分析页面应同时展示结构、时间线、规模指标；规模预测报告 MAE/RMSE/MSLE 等 |
| Guo 2025 | Fig.1 5W task categorization；Table 1 concepts；Table 2 dataset attributes；Table 12 dataset URLs | 论文把信息扩散任务映射到 5W，并按六类属性比较数据集 `[Guo, PDF p.1-p.2]` | 建立系统数据字典，检查每个事件是否具备用户、内容、社交网络、扩散网络、真假/标签属性 |
| MINDS 2024 | Fig.1 macro/micro task illustration；Fig.2 architecture；Fig.3 hypergraph convolution；Tables 2-6 results/ablation | 文字层显示模型包含全局交互、社会同质性、共享私有表示和预测模块 `[MINDS, PDF p.1-p.3]` | 当前预测模型应继续以 sequence hypergraph + shared-private 表示作为主干，而不是候选特征工程 |
| CasFT 2025 | Fig.1 toy popularity prediction；Fig.2 architecture；Figs.3-5 sensitivity | 可恢复标题说明 CasFT 用动态线索和 diffusion model 预测 future trend，关注 growth rate 和 trend uncertainty `[CasFT, PDF p.1-p.3]` | 趋势预测页应展示曲线，不只展示最终规模；但系统需标明未复现完整 diffusion generator |
| TGN 2020 | Fig.1 batch computations；Fig.2 memory update flow；Fig.4 schematic architecture | 图表标题和正文说明 timed events 经过 message、memory、embedding、loss 和 memory update `[TGN, PDF p.1-p.3]` | 后续把观测传播边流做成 continuous-time event stream，支持在线更新与实时推理 |
| CAW 2022 | Fig.1 triadic closure/feed-forward loops；Fig.2 CAW extraction/anonymization；Algorithms 1-3 | 图表和算法标题说明 CAW 从 temporal random walks 抽取 causality，并匿名化节点身份 `[CAW, PDF p.1-p.2]` | 用于新用户开放世界候选检索和跨事件归纳泛化，不依赖固定用户 ID |
| DyGFormer 2023 | Fig.1 framework；Table 1 negative sampling AP；Table 3-5 change analysis | 摘要和正文说明 historical first-hop interactions、neighbor co-occurrence、patching Transformer 与统一评测 `[DyGFormer, PDF p.1-p.6]` | 作为下一跳 micro head 或对照实验；引入 random/historical/inductive 三类负采样 |
| TGB 2023 | Fig.2 benchmark pipeline；Table 1 dataset stats；Tables 2-4 results；Table 7 inductive comparison | 论文强调真实、可复现、鲁棒的 temporal graph benchmark，包含 loader/evaluator/leaderboard `[TGB, PDF p.1-p.3]` | 建立系统预测模型的正式 benchmark 输出 schema 和时间切分协议 |
| ACI 2021 | Figs.1-3 local coverage；Figs.5-8 alpha trajectories；Algorithm 1 CQR | 文字层说明 adaptive conformal 在分布漂移下动态更新 coverage 参数 `[ACI, PDF p.1-p.4]` | 对趋势预测区间做校准，报告 coverage，不展示未校准置信度 |
| Expressive TGN 2022 | Fig.1 theorem overview；Fig.2 limitations；Fig.5 PINT；Table 1 AP | 论文建立 MP-TGN/WA-TGN 表达能力边界，并提出 PINT `[ExpressiveTGN, PDF p.1-p.2]` | 用于审查我们的动态图 backbone 是否能区分关键传播结构，指导后续 backbone 级优化 |

## 5. 当前系统实现与论文方法的对应

### 5.1 观测传播分析的当前实现

当前代码边界已经比较清楚：

| 位置 | 作用 | 论文迁移关系 |
|---|---|---|
| `backend/app/services/propagation_observation_service.py` | 从 MongoDB 读取事件数据，调用观测传播图构建，不调用预测代码 | 对齐 Zhou 的 cascade graph 和 Guo 的数据属性分类 |
| `backend/app/core/propagation_legacy.py` | 构建用户图、路径、层级、共享对象、角色、证据链、diffusion_summary | 目前是系统投影图，后续应升级为 provenance graph |
| `backend/app/api/v1/propagation.py` | `/observed-analysis` 与 `/model-event-predict` 分离 | 符合“解释已发生”和“预测未来”分离原则 |
| `frontend/src/views/propagation/index.vue` | 页面页签为传播路径、传播对象、角色分析、时间线、趋势预测 | 对齐产品端传播监测组织方式 |

观测分析的理想数据对象应从简单用户图扩展为异构 provenance 图：

```text
User --authored--> Post
User --commented--> Comment
Post/Comment --mentions--> URL/Hashtag/Claim
Comment --replies_to--> Comment/Post
User --observed_before--> User
User --inferred_shared_object_edge--> User
```

边类型建议固定为：

| 边类型 | 含义 | 前端呈现 | 置信度来源 |
|---|---|---|---|
| `explicit` | 平台明确回复、转发、引用、父评论 | 实线，作为确认传播关系 | 平台字段和帖子/评论 ID |
| `reconstructed` | 可由时间顺序和父对象重建但非平台直接边 | 半实线或标注重建 | 时间差、父对象、上下游内容 |
| `inferred` | 共享 URL/标签/claim 且时间邻近 | 虚线，必须说明推断 | 共享对象相似度、时间差、稳定性 |
| `layout` | 仅用于摘要布局或视觉分组 | 不进入传播事实边 | 不作为证据边输出 |

### 5.2 传播预测的当前实现

当前预测链路是：

```text
POST /api/v1/propagation/model-event-predict
  -> validate observed_until / observation_ratio
  -> load_event_posts/load_event_comments
  -> filter rows after observed_until
  -> event_adapter.build_event_inference_bundle
  -> checkpoint_runtime.predict_event_with_checkpoint
  -> PropagationSequenceJointModel.forward
  -> prediction_contract.map_bucket_probabilities_to_unique_users
  -> macro trend_points + micro top_users
```

`PropagationSequenceJointModel` 与论文方法的对应如下：

| 模型组件 | 当前实现 | 对应论文思想 | 严谨说明 |
|---|---|---|---|
| User embedding | hash bucket embedding | 动态图/序列模型的用户表示 | 匿名 bucket 映射仍是主要限制 |
| RelationGNN | 聚合 relation neighbor embedding | TGN/DyGFormer 的历史邻居信息，MINDS 的社会同质性 | 当前 relation 来自 checkpoint 统计，不是完整实时社交图 |
| DynamicCasHGNN | 按传播阶段构造 hyperedges 并做 attention 聚合 | MINDS sequential hypergraph | 属于 MINDS-inspired，不等于论文完整复现 |
| SharedLSTM | 编码用户激活顺序和相对时间 | FOREST/RNN 类微观序列思想，MINDS 扩散序列 | 作为共享传播状态 |
| Shared/private projection | shared、macro private、micro private | MINDS shared-private representation | 需要更完整训练和消融证明 |
| EulerTrendDecoder | 单调累计趋势点 | CasFT 连续趋势思想 | 未复现 CasFT diffusion model |
| User decoder | 对候选 bucket 做 softmax 排序 | temporal link / next-user prediction | 当前只对可映射用户展示 Top-K |
| Contract abstain | checkpoint/依赖/数据不足时拒答 | TGB/ACI 的严谨评测与不确定性意识 | 已避免启发式 fallback 冒充模型 |

当前 API 输出应继续维持：

```text
macro.observed_size
macro.predicted_size
macro.trend_points
macro.intervals
macro.direction
macro.calibration_status
micro.top_users
micro.candidate_count
micro.coverage
micro.reactivation_count
micro.new_activation_count
```

在当前版本，`new_activation_count=0` 和 `coverage.new_activation_status=abstain_no_identity_mapping` 是正确而严谨的做法，因为没有合法身份映射时不能把匿名 bucket 展示为“某个真实新用户”。

## 6. 功能迁移：系统还应该补充什么

### 6.1 观测传播分析补充

| 补充功能 | 研究依据 | 为什么需要 | 最小实现 |
|---|---|---|---|
| Provenance 异构图 | Guo 5W，Zhou cascade graph | 用户图投影会丢失帖子、对象和证据来源 | 新增 `nodes: user/post/comment/object/event` 和 typed edges |
| 边证据分级 | 观测研究的证据边界要求 | 避免把推断边误解为确认传播 | 每条边输出 `edge_type/source_ref/confidence` |
| 源头稳定性 | Zhou 对结构 virality 和 root 结构的讨论 | 单一源头可能由截断和推断边决定 | 删边、删节点、滑动窗口下计算 source stability |
| 角色稳定性 | 图中心性容易受边噪声影响 | 起爆/扩散/桥接角色不能只看一次中心性 | 输出 top role 在多窗口下的 rank variance |
| 共享对象归一化 | Guo 的 content 和 diffusion network 属性 | URL、hashtag、claim 是传播证据关键对象 | 对 URL canonicalize，hashtag/keyword/claim 合并 |
| 证据联动抽屉 | 系统工程需求 | 用户需要从路径图回到帖子和时间线 | 统一 `user_id/post_id/object_id/edge_id` 联动 |
| 推断关系可解释 | TGN/CAW 只支撑预测，不支撑事实溯源 | 推断边必须说明为什么存在 | 显示共享对象、时间差、共同前驱和置信度 |

### 6.2 传播预测补充

| 补充功能 | 研究依据 | 当前缺口 | 最小实现 |
|---|---|---|---|
| 严格时间切分 | TGB、DyGLib | 当前系统推理有 `observed_until`，但正式评测还需多事件回放 | 构建 rolling backtest：每个事件按 0.1/0.3/0.5 前缀评估 |
| historical/inductive negatives | TGB、DyGFormer | 随机负样本过易，无法证明下一跳能力 | 输出 random/historical/inductive 三组 Hits@K/MRR |
| 候选覆盖率仪表 | TGB 评测意识，当前 contract 已有 coverage | 用户不知道 Top-K 覆盖了多少合法候选 | 前端展示 mapped bucket、unmapped bucket、mapped probability mass |
| 开放世界新用户候选 | CAW、TGN、DyGFormer | 当前只做已知用户再激活 | 建立历史互动图和用户目录，候选来自历史邻居/同对象参与者/CAW motif 检索 |
| 趋势区间校准 | ACI | `intervals=None`，不能展示置信区间 | 在验证集上记录残差，使用 conformal wrapper 生成区间 |
| macro/micro 一致性审计 | MINDS | 共享 backbone 需要证明两任务没有互相拖累 | 报告 `macro_micro_consistency`、loss 权重消融、任务梯度冲突 |
| backbone 表达能力审查 | Expressive TGN | 当前模型能否区分不同传播形态缺少理论/实证证明 | 加入结构合成测试和 PINT/CAW/DyGFormer 对照 |
| 方法卡 | Guo/TGB 的可复现意识 | 前端不能暴露“黑箱预测” | 返回 `methodology`, `training_source`, `calibration_status`, `candidate_protocol` |

## 7. 对当前系统的差距判断

### 7.1 已经完成且可以对外说明

1. 传播监测已拆成观测传播分析和传播预测两条链路。
2. 观测传播分析已能基于当前事件数据生成传播路径、传播对象、角色分析、时间线和证据链。
3. 传播预测公开链路已使用 checkpoint runtime，不再把速度/加速度 fallback 当作预测结果。
4. 预测输出包含趋势点和下一跳用户表，且下一跳用户有真实 `author_id/author_name` 和 `evidence_refs`。
5. 模型缺失、数据不足、平台或观测比例不支持时返回 abstain/unavailable，而不是伪造结果。

### 7.2 不能夸大的部分

1. 当前系统不能宣称完整复现 MINDS、CasFT、TGN、DyGFormer 或 CAW。
2. 当前 CasFT 迁移是连续趋势头，不是 diffusion generator。
3. 当前下一跳预测主要是已知用户再激活，不是开放世界新用户激活。
4. 当前预测区间尚未校准，不能把 `score_concentration` 说成预测置信度。
5. 当前采样实验不能替代严格时间切分、多 seed、完整候选覆盖和强 baseline 对比。
6. 当前观测传播图仍是用户图投影，不是完整异构 provenance graph。

## 8. 建议的系统技术路线

### 8.1 第一阶段：把观测分析做严谨

```text
目标：任何传播路径、源头、角色和证据都能追溯到帖子/评论/对象/时间。
```

| 开发项 | 验收标准 |
|---|---|
| 异构 provenance graph | API 返回 user/post/comment/object/event 节点和 typed edges |
| 边类型和证据卡 | 每条边有 `edge_type`, `confidence`, `source_refs`, `inference_reason` |
| 源头和角色稳定性 | 输出 sliding-window 和删边扰动下的稳定性分数 |
| 统一联动 ID | 前端路径、对象、角色、时间线可互相定位 |
| 推断边视觉分层 | 确认关系优先显示，推断关系补充显示，layout 边不作为事实边 |

### 8.2 第二阶段：把当前预测做可评测

```text
目标：趋势曲线和下一跳研判都能通过严格 backtest 说明有效性与边界。
```

| 开发项 | 验收标准 |
|---|---|
| rolling backtest | 每个事件按 `observed_until` 回放，禁止未来数据进入输入 |
| macro 指标 | `MAE/RMSE/MSLE/sMAPE/Direction Accuracy/trend_mae/trend_rmse` |
| micro 指标 | `Hits@K/MRR/NDCG@K/MAP@K/candidate_recall` |
| TGB-style negatives | random、historical、inductive 三类负样本分别报告 |
| loss 和任务消融 | 报告 macro-only、micro-only、shared-only、no-hypergraph、no-trend 的变化 |

### 8.3 第三阶段：补齐开放世界下一跳和校准区间

```text
目标：下一跳从“已知用户再激活”扩展到“可解释的新用户候选”，趋势从点曲线扩展到校准区间。
```

| 开发项 | 论文依据 | 验收标准 |
|---|---|---|
| 历史互动图库 | TGN、DyGFormer | 候选来自训练/历史图，而不是测试未来节点 |
| CAW motif 候选 | CAW | 对训练未见用户可给出 motif-based 候选解释 |
| bucket identity registry | CAW/TGB | bucket 冲突率、映射覆盖率和 excluded ambiguous users 可报告 |
| adaptive conformal interval | ACI | 验证集 coverage 接近目标水平，漂移时能自适应更新 |
| inductive benchmark | TGB/DyGLib | 明确区分 transductive reactivation 与 inductive new activation |

## 9. 对传播监测页面的功能补充建议

| 页面 | 当前核心内容 | 建议补充 | 论文支撑 |
|---|---|---|---|
| 传播路径 | 簇状路径图、关键传播路径、层级分析 | 边类型图例、确认/重建/推断切换、节点/边证据卡 | Zhou 2021, Guo 2025 |
| 传播对象 | 高频共享对象和详情 | URL/hashtag/claim 归一化、对象到路径和时间线的双向跳转 | Guo 2025 |
| 角色分析 | 起爆和扩散节点 | 稳定性分数、角色来源证据、协同群组过滤 | Zhou 2021 |
| 时间线 | 观测传播事件流 | 关键增长拐点、对象出现时间、边证据时间差 | Zhou 2021, TGN 2020 |
| 趋势预测 | 趋势曲线和下一跳 Top-K | 候选覆盖率、校准状态、已知再激活/新激活分组、回测指标卡 | MINDS 2024, CasFT 2025, TGB 2023, ACI 2021 |

## 10. 复现与验证清单

### 10.1 观测传播分析复核

| 检查项 | 通过条件 |
|---|---|
| 数据范围 | `event_id/platform` 与页面选择一致，posts/comments 数量可追溯 |
| 显式边 | 每条确认边都有平台字段、父 ID 或回复关系证据 |
| 推断边 | 每条推断边都有共享对象、时间差和置信度 |
| 源头 | 源头节点必须有帖子或路径证据，不只由布局算法选出 |
| 层级 | 层级统计口径和路径图口径一致，或明确说明差异 |
| 角色 | 起爆/扩散/桥接等角色有指标、路径和帖子证据 |
| 前端联动 | 点击节点、对象、下一跳用户能回到对应证据 |

### 10.2 传播预测复核

| 检查项 | 通过条件 |
|---|---|
| 观测截止 | `observed_until` 后的数据不会进入模型输入、候选或证据 |
| checkpoint | 真实加载本地 checkpoint，缺失时返回 unavailable |
| 无 fallback | 不再生成速度/加速度或活动度排序替代预测 |
| macro | `trend_points` 单调且与 `observed_size` 关系合理 |
| micro | `top_users` 都能映射真实用户，匿名 bucket 不直接展示 |
| 覆盖率 | 报告 mapped/unmapped candidate buckets 和 probability mass |
| 指标 | 回测输出 macro/micro 指标和负采样协议 |
| 校准 | 区间未校准时明确 `calibration_status=unavailable` |

## 11. 最终判断

当前传播监测的系统功能定位是成立的：观测传播分析作为产品功能，解释已采集事件的路径、对象、角色和证据；传播预测作为模型功能，基于观测前缀输出趋势曲线和下一跳研判。它与信息扩散研究的主线是对齐的，但研究严谨性仍取决于三个尚未完全完成的部分：异构 provenance 图、开放世界归纳式下一跳候选、预测区间校准与严格 TGB-style 评测。

如果下一阶段只做一个高价值优化，应优先把观测传播边改为 `explicit/reconstructed/inferred` 并补齐证据卡。原因是这会直接提升系统可信度，也会为后续 TGN/CAW/DyGFormer 式预测模型提供更干净的事件流输入。

如果下一阶段只做一个模型优化，应优先做 TGB-style rolling backtest 和 candidate coverage dashboard。原因是它能把“模型是否真的有效”从页面展示问题转化为可审计的实验协议，避免再出现“能跑但不能支撑结论”的风险。
