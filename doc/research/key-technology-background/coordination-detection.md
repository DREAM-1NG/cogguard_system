# 关键技术一：跨平台协同发现（共同行为特征复用融合检测）

> **用途**：定义 Coordination Discover / Detect 的研究问题、当前工程落点、研究目标、实现方向和验证方式。
> **受众**：Coordination Discover / Detect 研究实现者、协同检测模块维护者。
> **维护规则**：只写关键技术背景与研究方案；产品接口和任务状态放入 `../../engineering/`。

> 方向更新（2026-06-02）：Coordination Discover / Detect 是本项目核心关键技术。最新定位为 **跨平台协同发现——利用平台无关的“共同行为特征”做复用融合检测；具体的内容检测不作为协同发现的信号**。
> 立论：现有 CIB 检测文献大多依赖特定协同信号（cotweet/retweet/cofollow/time burst）；面向抖音等多媒体平台又提出更专用的内容型信号（如视频-语义 mismatch），这类内容信号平台特定、易被生成式 AI 改写、跨平台迁移成本高。Coordination Discover / Detect 转而只用各平台共有、可迁移的行为特征作为协同判据。

> 方向更新（2026-06-26）：Coordination Discover / Detect 不再定位为纯网络科学方法，而是 **GNN + LM 增强的协同社区构建与发现方法**。网络科学指标仍用于可解释评估与社区质量审计，但核心模型应从静态加权图升级为：LM 提供共享对象/节点/社区的语义表征与高影响节点标注，GNN 在多关系、动态、有向协同图上进行消息传递、关系融合和社区表示学习。

## 1. 问题定义

在事件窗口内，识别一组在该窗口内共同推动某叙事的账号集合（协同群体），并输出可解释的协同边与证据样本。核心原则：**协同判定只看“行为是否同步”，不看“内容说了什么”**。内容理解（立场/危害/图文一致）单向下沉到下游 Propagation Analysis/Risk Review，绝不回流作为协同信号。

Coordination Discover / Detect 的研究任务采用两阶段定义：

1. **协同发现**：从平台无关的共同行为事件中构建多关系协同图，并用 GNN + LM 学习用户、共享对象和社区的表示，发现协同账号簇、关键账号对和共享对象。该阶段对应 coordinated online behavior / information operations detection 文献中的 community 或 cluster 输出。
2. **协同区分**：在有 IO/control 或 coordinated/organic 标签的数据集上，检验第一阶段得到的协同图信号是否能够区分自发行为和协同攻击。该阶段才进入排序或分类评估。

因此，Coordination Discover / Detect 不是以 bot detection、troll identification 或 misinformation classification 为主任务。相关领域的指标只作为 auxiliary characterization，用于解释协同群体的真实性、组织性、危害性或时序模式。

要补齐的能力：

- 多种共同行为信号的统一建模与融合（时间同步、共享对象、共转发级联、行为节律等）
- LM 增强的共享对象归一化、节点/社区语义表征和高影响力节点标注
- GNN 在多关系、动态、有向协同图上的消息传递、关系 attention 与社区表示学习
- 自然共振 vs 人为协同的显著性筛查（抑制热门话题误报）
- 可解释的边类型与证据样本输出
- 跨平台/跨源的信号可复用性


### 1.1 Discover / Detect 任务边界（2026-06-28 固化）

Coordination Discover / Detect 正式采用 **Discover -> Detect** 两阶段口径，二者不能混用评价指标。

| 阶段 | 任务定义 | 是否使用标签 | 主要输出 | 主评价指标 |
|---|---|---:|---|---|
| Discover | 无标签协同社区发现：从共同行为事件中发现哪些账号围绕哪些对象、通过哪些关系、在什么时间窗口内形成可解释协同社区 | 否 | `cluster_id`、`edge_score`、`community_score`、`top_objects`、`relation_breakdown`、`object_concentration`、`dynamic_edges`、`metapath_attention` | `modularity`、`conductance`、`density`、`object_concentration`、`relation_entropy`、时间窗/多尺度 `NMI/ARI/Jaccard` |
| Detect | 有标签协同区分：判断账号或社区是否属于 IO driver / coordinated attacker / organic user | 是 | `node_score`、`predicted_label`、`community_detection_score`、账号/社区级排序 | `AP/AUC/AUPRC`、`MaxF1`、`Precision@K`、`Recall@K` |

AMDN-HAGE 等文献汇报的 `AP / AUC / F1@0.5 / Precision@0.5 / Recall@0.5 / MaxF1` 是账号级检测指标，衡量“单个账号是否协调/可疑”的判断能力；这些指标属于 Detect，不用于证明 Discover 的社区划分质量。Coordination Discover / Detect 正式 Detect 主表采用 `MaxF1` 作为 F1 类主指标，固定阈值 `F1@0.5` 仅作为阈值校准诊断，不用于方法排名。

Discover 阶段使用 Leiden 的原因是：Leiden 是成熟的无监督 weighted graph 社区划分后端，比 Louvain 更能避免不连通或低质量社区；它不替代 MAGNN，而是在 MAGNN 学到 `node embedding / edge_score / metapath_attention` 后，将重加权协同图切分为可审计社区。Leiden 的结果应作为 Detect 的结构化输入特征，例如 `cluster_id`、`community_size`、`community_score`、`density`、`object_concentration`、`relation_breakdown`、`edge_score`、`discover_embedding`，但不能直接当作 Detect 的真值标签。

高水平 IO/账号检测文献不普遍使用 Leiden，主要是因为任务不同：AMDN-HAGE、Unmasking、IOHunter 等核心目标是账号级或 driver 级 detection，主问题是分类、排序或跨行动泛化；而我们的 Discover 阶段目标是 label-free coordinated community discovery，因此需要一个明确、稳定、可解释的社区划分后端。我们的创新点不在“发明 Leiden”，而在动态多关系 User-Object-User 图、MAGNN 边置信度学习、对象级证据输出，以及将 Discover 社区结构传递给 Detect。

Detect 阶段的正式主线参考 IOHunter / SocGFM，而不是继续使用 Leiden 做分类。当前实现将 `gfm_lm_gnn` 定位为论文主模型：先复用 Discover 的 MAGNN `discover_embedding`、`edge_score`、`cluster_id/community_score`、关系与元路径统计；再拼接 LM/SBERT 或 `tfidf_object_bag_fallback` 语义特征；最后在 Discover 重加权的多关系图上训练监督式 LM+GNN/GFM 检测器。`fusion_gnn`、`relation_gnn` 和 `classifier` 保留为 Detect baseline。若 IOHunter processed 数据缺少真实文本，LM 分支只能声明为 metadata/object bag semantic feature，不能夸大为完整 LLM 贡献。

## 2. 当前代码基线

当前代码落点：

- `system/backend/app/core/coordination/`（`detector.py` / `network.py` / `stats.py`）
- `system/backend/app/services/coordination_service.py`
- `system/backend/app/api/v1/coordination.py`

当前已实现（真实可运行）：

- 共享对象 + 时间窗配对（CooRTweet 重写，`detector.py`）
- 加权无向图 + 百分位阈值（`network.py`）
- 账户级 / 群体级统计、社区发现、网络序列化与前端可视化

当前未实现或仅原型实现：

- **PSL（Pair Surprisal Layer）显著性筛查**：对称超几何 + Cauchy combination + pair-level BH-FDR（`significance.py` 不存在）
- 多行为通道抽取与融合（`channels.py` 不存在）
- LM 表征层（`semantic.py` 不存在）：用于 object canonicalization、节点/社区表示、Node Selection 后的 LLM annotation；不能把“文本立场/危害分类”直接当作协同边证据
- GNN 协同社区发现层：当前 `twitter_io_experiment.py` 仅有轻量 learnable relation attention 原型，还不是完整的多关系图消息传递模型

## 3. 这一技术线要解决的核心问题

- 哪些行为特征是跨平台可复用的（不依赖单平台特有机制、不依赖读懂内容）
- 如何把不同类型的行为协同边统一投影到账号协调图，并通过 GNN 学习关系权重、节点表示和社区边界
- 如何使用 LM 进行共享对象归一化、语义上下文压缩和高影响力节点标注，而不把普通内容分类误当成协同证据
- 如何用显著性筛查区分自然共振与人为协同
- 如何输出可解释的边类型证据，而不只是一个黑盒分数

## 4. 推荐实现方向

- 协同信号只取“共同行为特征”：时间同步/共现、共享对象（URL/hashtag/媒体指纹 id）、共转发与回复级联、账号行为节律、共参与模式等
- 行为 vs 内容的边界判据：共享同一媒体对象（按 id/指纹）= 协同证据；LM 对对象描述、URL 标题、模板文本、节点历史进行表征 = 表示增强；分析视频内容/字幕 mismatch/文本立场/毒性 = 下游 Characterization，不直接作为协同边证据
- 第一版工程可以保留 pandas/numpy/networkx 轻量链路作为可解释 baseline，同时把 `twitter_io_experiment.py` 中的 learnable relation attention 发展为多关系 GNN encoder：输入 relation-specific edge features、LM node/object embeddings 和时间特征，输出 edge score、node embedding、community assignment
- 使用 Node Selection + LLM annotation：先按出度/入度/加权度/PageRank/跨簇桥接性选高影响节点，再让 LLM 标注其角色、共享对象主题和疑似组织功能；LLM 标注用于解释和弱监督，不替代行为证据
- 映射到 Mannocci 2024 综述的 Detection + Characterization 两阶段：行为同步 = Detection（Coordination Discover / Detect 核心）；内容/毒性/立场 = Characterization 或下游 Propagation Analysis/Risk Review
- 表述纪律：“跨平台”当前仅验证 mock_weibo/weibo/news（跨源，非跨平台身份解析），对外应表述为“平台无关的行为信号设计 + 跨源验证”，并坦白单平台上排除内容信号是鲁棒性 tradeoff（可能略损召回，换取可迁移性与抗 AI 改写）

## 5. 推荐验证方式

正式实验分为两类：

- **Setting A: discovery-only**。使用 X/Twitter Information Operations Archive，目标是证明方法能从正样本 IO 档案中发现结构清晰、证据可解释的协同网络。主指标包括 modularity、cluster_count、largest_cluster_size、density/conductance、object concentration、relation/channel breakdown、top-K evidence audit 和跨时间/语言/campaign 切片的稳定性。
- **Setting B: labeled detection**。使用 Guo & Vosoughi 2022 state-backed IO dataset 或 Seckin et al. 2025 labeled IO datasets，目标是证明协同发现阶段得到的边权、社区和结构表征可以区分 coordinated attack 与 organic/self-organized behavior。主指标包括 AUPRC、Precision@K、Recall@K、MaxF1、AUROC；固定阈值 F1 只作为阈值诊断，不进入主表；社区级补充 FM-score、NMI、ARI、Purity。

辅助实验可以报告 bot score、toxicity、stance、harmfulness、sentiment 等表征，但这些信号只用于 Characterization，不作为协同发现判据。

- `mock_weibo`：验证行为边拼接、统计逻辑和回归测试
- `weibo`：验证真实采集样例上的误报/漏报模式（热门话题压力测试）
- `news`：验证跨源场景下共享链接与资源复用信号

建议重点补充：

- 共同行为边构建的单元测试
- 显著性筛查的回归测试
- 响应结构变更时的最小前端兼容检查

## 6. 文献线索（注意核实，旧表中部分条目 venue/方法有误）

- Mannocci et al. *Detection and Characterization of Coordinated Online Behavior: A Survey* (arXiv 2408.01257, 2024) — Detection/Characterization 框架
- Luceri et al. *CIB on TikTok* (arXiv 2505.10867, 2025) — 行为型信号可迁移、内容型不可迁移的实证
- Schneider, Yuan, Rizoiu *Beyond Content* (arXiv 2602.02838, 2026) — platform-agnostic 行为 policy，最接近的先前工作（Coordination Discover / Detect 须明确差异，勿当原创首发）
- CooRTweet（共享对象配对，工程基线来源）
- Cinus/Minici/Luceri/Ferrara *Exposing Cross-Platform CIB* (arXiv 2410.22716, 2024)
