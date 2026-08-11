# Coordination SOTA 数据集获取与复现路线

日期：2026-08-11  
范围：Coordination Discovery / Coordination Detection 研究复现，不切换生产系统模型  
产出规则：全部数据、缓存、结果和报告放在 `G:`；当前文件只定义 acquisition 与复现门禁，不下载大型数据

## 当前结论

`IOHunter processed` 已经完成 `6 campaigns x 5 seeds x 5 folds x 8 methods = 1200` 的全交叉 proxy 对比，但它缺少真实时间戳、协同边 Gold、社区 Gold 和 harmfulness Gold。因此它只能继续用于静态 external-account recovery proxy，不能公平复现 TGAT、TGN、DyGFormer、Temporal Multiplex/Multislice、Flow Stability，也不能支撑 Coordination Detection。

新的公开数据优先级固定为：

| 优先级 | 数据源 | 获取入口 | 用途 | 不能主张 |
|---|---|---|---|---|
| P0 | LEN: Large Engagement Networks | `G:\CISCN\dataset\LEN` | 本地已下载 campaign/noncampaign graph-level JSON，适合 Stage 2 群体级 Detection 和 campaign/organic 图分类 | 当前不是事件流；不能直接跑 TGAT/TGN/DyGFormer 或 Flow Stability |
| P0 | X/Twitter state-backed IO archive / Stanford takedown archive | `https://cyber.fsi.stanford.edu/io/news/twitter-takedown-data-archive` | 平台披露 IO 账号与原始时间信息，适合时间 Discovery 和案例研究 | 默认没有 control accounts；没有 edge/community/harmfulness Gold |
| P1 | Astroturf/Legitimate Classification | `G:\CISCN\dataset\ALClassification` | 本地已下载 Truthy meme feature table，适合 Stage 2 经典特征 baseline/smoke | 没有原始事件流、图结构和 campaign holdout |
| P1 | Seckin et al. 2024 Labeled Datasets for Research on Information Operations | `https://doi.org/10.5281/zenodo.14141549` | 26 个 IO campaign，IO/control posts，理论上适合 temporal external-account recovery 和跨 campaign holdout；但当前环境 files API 返回 `403`，已标记无法直接下载 | 目前不可执行；没有协同边 Gold、社区 Gold、harmfulness taxonomy |
| P1 | Guo & Vosoughi 2022 IO control datasets | `https://ojs.aaai.org/index.php/ICWSM/article/view/19375` | 28 个 campaign、14 个国家、历史 control 数据，适合复核 Seckin 之外的跨 campaign 泛化 | 需要 access/schema audit；仍不是 coordination edge/community Gold |
| P1 | IRA/Russia troll public archives | 平台、国会、Kaggle/Internet Archive 派生公开集 | 单 campaign 时间动态复现、orchestration case study | campaign 单一，不能证明泛化 |
| P2 | TGB / DyGLib dynamic graph benchmarks | `https://tgb.complexdatalab.com/` | 只用于 TGAT/TGN/DyGFormer 方法复现和 temporal graph sanity check | 不是 Coordination 检测数据，不含 IO labels |

## 代码侧已落地的门禁

新增 `public_benchmark_registry.py`，把公开数据集和方法复现要求写成机器可读 registry。

核心判断：

| 数据集 | TGAT/TGN/DyGFormer | Temporal Multiplex/Multislice | Pólya/Noise-Corrected/ECM | Flow Stability |
|---|---|---|---|---|
| IOHunter processed | `blocked`：无真实时间戳和 temporal edges | `blocked`：无真实时间戳 | `proxy_only`：可做静态 account-recovery proxy | `blocked`：无真实时间戳 |
| Seckin 2024 | `adapter_required` | `adapter_required` | `adapter_required` | `adapter_required` |
| X/Twitter IO archive | `adapter_required` | `adapter_required` | `adapter_required` | `adapter_required` |
| Guo/Vosoughi 2022 | `adapter_required` | `adapter_required` | `adapter_required` | `adapter_required` |
| LEN | `blocked`：当前是 graph-level JSON，不是事件流 | `blocked`：当前是 graph-level JSON | `proxy_only`：可做图骨架/统计对照 | `blocked`：当前不是 temporal event stream |
| ALClassification | `blocked`：只有特征表 | `blocked`：只有特征表 | `blocked`：无图结构 | `blocked`：无事件流 |
| TGB | `method_only` | `method_only` | `method_only` | `method_only` |

这意味着：TGB 可以帮助确认 TGAT/TGN/DyGFormer 代码复现没有跑偏，但不能写成 Coordination Detection 结果；LEN 是当前可执行的 Stage 2 群体级 Detection 主数据；Seckin 2024 仍是理论上最理想的 IO/control 数据，但当前环境无法直接下载，不能作为近期执行前提。

## 方法复现路线

### Lane 1：数据适配

目标目录固定：

| 数据源 | 本地 raw root | 本地 processed root |
|---|---|---|
| Seckin 2024 | `G:\CISCN\dataset\coordination_public\seckin_2024_labeled_io\raw` | `G:\CISCN\dataset\coordination_public\seckin_2024_labeled_io\processed`，先写 access/request manifest |
| X/Twitter IO archive | `G:\CISCN\dataset\coordination_public\twitter_state_backed_io_archive\raw` | `G:\CISCN\dataset\coordination_public\twitter_state_backed_io_archive\processed` |
| Guo/Vosoughi 2022 | `G:\CISCN\dataset\coordination_public\guo_vosoughi_2022_io_controls\raw` | `G:\CISCN\dataset\coordination_public\guo_vosoughi_2022_io_controls\processed` |
| LEN | `G:\CISCN\dataset\LEN` | `G:\CISCN\dataset\coordination_public\large_engagement_networks\processed` |
| ALClassification | `G:\CISCN\dataset\ALClassification` | `G:\CISCN\dataset\coordination_public\astroturf_legitimate_classification\processed` |
| TGB | `G:\CISCN\dataset\coordination_public\tgb\raw` | `G:\CISCN\dataset\coordination_public\tgb\processed` |

每个 adapter 必须输出统一事件流：

| 字段 | 要求 |
|---|---|
| `account_id` | 已匿名或哈希后稳定 ID |
| `event_id` | 原始 post/reply/repost/mention/URL 事件 ID 的稳定哈希 |
| `timestamp_utc` | 真实观测时间；缺失则不能进 temporal SOTA |
| `platform` | 至少包含 `twitter/x`，多平台数据保留原平台 |
| `relation_type` | `post`、`reply`、`reshare`、`mention`、`url`、`hashtag`、`near_duplicate` 等 |
| `target_id` | URL/hashtag/user/post/content cluster 等可观测对象 |
| `campaign_id` | 平台披露或论文提供的 campaign 标识 |
| `label_scope` | `io_account_membership`、`control_account`、`method_only` 等 |
| `provenance` | 源文件、下载时间、checksum、license/terms |

### Lane 2：静态/逐窗口 backbone

先复现 Pólya、Noise-Corrected、ECM backbone，因为它们对 IOHunter processed 也能跑静态 proxy，风险最低。

实验目标：

| 方法 | 作用 | 评估 |
|---|---|---|
| Pólya filter | 对 weighted evidence graph 做统计显著骨架筛选 | external-account recovery、边保留率、社区稳定性 |
| Noise-Corrected backbone | 在 noisy weighted graph 中保留超出 null expectation 的边 | 同上 |
| ECM backbone | 用 degree/strength conditioned null model 做骨架 | 同上；公式级实现需先精读锁定 |

门禁：这些方法只能主张“backbone/filter improves Discovery proxy”，不能主张 harmful Coordination Detection。

### Lane 3：TGAT / TGN / DyGFormer

复现顺序：

1. 在 TGB 上跑官方或 DyGLib/TGB-compatible runner，确认 temporal link prediction pipeline 正常。
2. 在 Seckin 2024 上构建 timestamped interaction stream，任务改成 IO/control account recovery 或 future interaction recovery。
3. 在 X/Twitter IO archive 和 Guo/Vosoughi 上复核跨 campaign 泛化。

门禁：如果只在 TGB 上跑通，只能叫方法复现；只有在 IO/control 数据上跑通并超过 frozen production proxy，才进入 CogGuard 研究候选。

### Lane 4：Temporal Multiplex/Multislice 与 Flow Stability

这条线必须等 timestamped multiplex adapter 完成后启动。输入需要按时间窗生成多层图：

| 层 | 来源 |
|---|---|
| `co-reshare` | 共同转发/转帖对象 |
| `co-url` | 同 URL 或同 domain |
| `co-hashtag` | 同 hashtag |
| `co-mention` | 同提及对象 |
| `reply-target` | 同回复目标 |
| `near-duplicate` | 近重复文本或媒体 |

Flow Stability 输出 dynamic communities；Temporal Multiplex/Multislice 输出多层协同结构。二者没有社区 Gold 时，只能报告稳定性、扰动鲁棒性、平台披露账号覆盖和人工案例复核，不能报告 community recovery accuracy。

### Lane 5：Coordination Detection

Detection 不能由固定贝叶斯权重或处置阈值主张完成。后续必须用公开 IO/control 或人工审核构建可学习任务：

| 子任务 | 可用公开数据 | 模型 |
|---|---|---|
| harmfulness 内容判别 | HateXplain、Fakeddit、FakeSV、MOCHEG、Factify、PHEME/Weibo rumor | 文本/多模态 classifier |
| IO/control 判别 | IOHunter、Guo/Vosoughi、X/Twitter archive + controls；Seckin 2024 若后续取得访问 | cluster-level classifier |
| campaign/organic 图判别 | LEN | graph-level classifier，作为 Stage 2 主基准 |
| astroturf/legitimate 经典特征判别 | ALClassification | classic feature baseline/smoke |
| community authenticity 聚合 | TwiBot/Cresci/Botometer + CogGuard bot output | calibrated aggregation |
| orchestration characterization | IO archive + timestamped multiplex graph | learned or statistical characterization head |

最终 Coordination Detection 的输入必须是 Discovery 输出的 cluster，不是单账号或单帖；输出应包含 `harmful/benign/uncertain`、校准概率、abstain、证据维度和模型版本。

## Coordination Detection 对比基线

Detection 对比基线分为四层：群体级图分类、账号级 IO 检测、统计/启发式检测和动态编码器。只有前两层进入主表；后两层用于消融和机制解释。

| 层级 | 基线 | 年份 | 链接 | 适用数据 | 实现方式 |
|---|---:|---:|---|---|---|
| 系统方法 | CogGuard learned fused detector | 当前系统 | local | LEN、IOHunter、后续 Twitter event adapter | 输入 Discovery cluster/graph features、内容危害、bot/authenticity、时间稳定性、证据覆盖，训练校准二分类或三分类 |
| 系统方法 | CogGuard heuristic Bayesian baseline | 当前系统 | local | LEN、ALClassification、IOHunter proxy | 固定权重只作为显式 heuristic baseline，不参与主张 |
| 图级主基线 | LEN graph-classification baseline | 2025 | `https://arxiv.org/abs/2503.00599` | LEN | campaign/noncampaign graph-level classification；复现论文中的 graph feature 与 GNN 对照 |
| 图级主基线 | Coordination Activity Classifier | 2020 | `https://arxiv.org/abs/2005.13466` | LEN、TwitterStateBackedOps/twitter_io adapter | 构造逐日 coordination networks，提取网络统计特征，训练 binary classifier 区分 SIO/campaign-like vs legitimate/organic |
| 图级 GNN | GCN | 2017 | `https://arxiv.org/abs/1609.02907` | LEN | 作为图/节点编码器 baseline，配 graph pooling 做 campaign/noncampaign |
| 图级 GNN | GraphSAGE | 2017 | `https://arxiv.org/abs/1706.02216` | LEN、IOHunter | inductive graph encoder，适合跨 campaign/跨图泛化 |
| 图级 GNN | GIN | 2019 | `https://arxiv.org/abs/1810.00826` | LEN | 强 graph classification baseline |
| 图级 GNN | DiffPool | 2018 | `https://arxiv.org/abs/1806.08804` | LEN | hierarchical graph pooling baseline，检验大图池化是否有收益 |
| 账号级 IO 主基线 | Inductive IO Graph Learning | 2023 | `https://doi.org/10.1038/s41598-023-49676-z` | TwitterStateBackedOps、twitter_io、IOHunter proxy | co-URL graph + graph/content indicators，LR/RF/MLP/GCN/MP-GCN 跨 operation 检测 IO 账号 |
| 账号级 IO 主基线 | Unmasking the Web of Deceit | 2024 | `https://doi.org/10.1145/3589334.3645529` | TwitterStateBackedOps、twitter_io | 多 similarity trace，node pruning，fused similarity network embedding，再做 IO driver classification |
| 账号级 IO 强基线 | IOHunter | 2025 | `https://arxiv.org/abs/2412.14663` | IOHunter | LM 表征 + 多关系相似图 + GNN，账号级 IO driver detection |
| 无监督/弱监督 | Unsupervised CIO Bayesian model | 2025 | `https://link.springer.com/article/10.1140/epjds/s13688-025-00544-y` | TwitterStateBackedOps/twitter_io case | 账号特征 + narrative targets 的 Bayesian latent-group inference，用作无监督/弱先验 baseline |
| 经典特征 | Truthy Astroturf Meme classifier | 2011 | `https://arxiv.org/abs/1011.3768` | ALClassification | ARFF 手工特征表，LogReg/SVM/RF baseline，只做 smoke 和历史对照 |
| 动态编码器 | TGAT | 2020 | `https://arxiv.org/abs/2002.07962` | TwitterStateBackedOps/twitter_io event stream | temporal account/edge encoder；在 Detection 中作为表示学习组件，不单独代表 CIB 方法 |
| 动态编码器 | TGN | 2020 | `https://arxiv.org/abs/2006.10637` | TwitterStateBackedOps/twitter_io event stream | memory-based temporal graph encoder；用于账号/cluster 表示 |
| 动态编码器 | DyGFormer | 2023 | `https://arxiv.org/abs/2303.13047` | TwitterStateBackedOps/twitter_io event stream | long-history dynamic graph transformer；用于 temporal representation |

主实验表不应堆满所有基线。推荐主表固定为：CogGuard learned fused detector、CogGuard heuristic、LEN graph baseline、Vargas 2020、GCN、GraphSAGE、GIN、Inductive IO Graph Learning、IOHunter。TGAT/TGN/DyGFormer 进入 temporal adapter 完成后的附表或消融表。

## 当前执行状态

| 项 | 状态 |
|---|---|
| IOHunter full crossed matrix | 已完成，`1200` rows，`975` success，`225` blocked |
| Public benchmark registry | 已完成初版 |
| IOHunter temporal SOTA gating | 已完成，TGAT/TGN/DyGFormer/Flow Stability 均 blocked |
| LEN local dataset | 已确认，`G:\CISCN\dataset\LEN`，可作为 Stage 2 graph classification 主数据 |
| ALClassification local dataset | 已确认，`G:\CISCN\dataset\ALClassification`，可作为 Stage 2 classic baseline/smoke |
| Seckin 2024 adapter | 当前阻塞：Zenodo files API 返回 `403`，不能作为近期执行前提 |
| TGB method-only runner | 未完成，第二优先级 |
| Backbone implementations | 未完成，先做 Pólya/Noise-Corrected，再 ECM |
| Coordination Detection learned task | 未完成，等待数据 adapter 和 Detection label schema |

## 下一步

1. 实现 LEN adapter，输出 graph-level `campaign/noncampaign` Detection partitions，作为 Stage 2 主基准。
2. 实现 ALClassification adapter，输出 classic feature baseline/smoke。
3. 接入 backbone lane：Pólya、Noise-Corrected、ECM，先跑 IOHunter proxy 和 LEN graph/statistical 对照。
4. 接入 X/Twitter IO archive / `twitter_io` timestamped event adapter，再启动 TGAT/TGN/DyGFormer、Temporal Multiplex/Multislice 和 Flow Stability。
5. 接入 TGB method-only sanity runner，复现 TGAT/TGN/DyGFormer 的基本 temporal link prediction。
6. Seckin 2024 仅保留为 blocked acquisition；除非完成访问授权，不再作为近期执行前提。

## 已核验来源

- Seckin et al. 2024, Labeled Datasets for Research on Information Operations: `https://arxiv.org/abs/2411.10609`，数据 DOI：`https://doi.org/10.5281/zenodo.14141549`
- TGB, Temporal Graph Benchmark: `https://arxiv.org/abs/2307.01026`，官网：`https://tgb.complexdatalab.com/`
- TGAT, Inductive Representation Learning on Temporal Graphs: `https://arxiv.org/abs/2002.07962`
- TGN official implementation: `https://github.com/twitter-research/tgn`
- DyGFormer / DyGLib: `https://arxiv.org/abs/2303.13047`
- Flow Stability implementation: `https://github.com/bovet-research-group/flow_stability`
- Pólya urn backbone: `https://doi.org/10.1038/s41467-019-08667-3`
- Noise-Corrected backbone reference route: `https://arxiv.org/abs/1701.07336`
- Structured backbone / ECM-related reference route: `https://doi.org/10.1038/s41467-018-08160-3`
