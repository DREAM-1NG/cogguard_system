# GNN + LM 协同社区构建与发现方法

## 1. 方法定位

KT1 的第一版正式方法不应只是“网络科学社区发现”，而应定位为：

**LM-enhanced multi-relation GNN for coordinated community discovery and discrimination**。

中文表述：

**基于语言模型增强的多关系图神经网络协同社区构建、发现与区分方法**。

该方法仍保留 CooRTweet / CNT / Leiden / modularity 等网络科学方法作为可解释 baseline 和审计工具，但主模型应承担三个学习任务：

1. 从多关系行为边中学习账号间协同强度。
2. 从 LM 表征和图结构中学习用户、对象、社区的低维表示。
3. 在无标签和有标签设置下分别完成协同社区发现与协同攻击区分。

## 2. 图构建

### 2.1 节点类型

- `user`：账号节点，是最终聚类和检测对象。
- `object`：共享对象节点，包括 URL、hashtag、媒体指纹、转发目标、回复目标、引用目标。
- `content`：可选的帖子/评论节点，用于动态有向图和传播链建模。

第一版可以先实现 user-user 投影图；第二版扩展为 user-object-content 异构图。

### 2.2 边类型

当前已经支持或规划支持的关系包括：

- `url_share`
- `hashtag_share`
- `media_share`
- `retweet_target`
- `reply_target`
- `quote_target`
- `mention_target`
- `cascade_root`
- `template_fingerprint`

每条边应保留：

- `relation_type`
- `weight`
- `timestamp` 或 `time_window`
- `direction`
- `object_id`
- `evidence`

动态图中，边的方向按行为流定义：例如 `user -> object`、`user -> target_user`、`reply_user -> root_user`。

## 3. LM 的作用边界

LM 不直接回答“这个账号是否协同”，也不把毒性、立场、危害性作为协同边证据。LM 只用于增强表示和解释：

1. **Object canonicalization**：把同一 URL 的不同参数形式、相同媒体描述、相似 hashtag 归一到更稳定的 object family。
2. **Node/object embedding**：把账号历史文本、共享对象标题、URL 页面摘要、hashtag 上下文压缩为向量。
3. **Node Selection + LLM annotation**：先用入度、出度、加权度、PageRank、betweenness 选高影响节点，再用 LLM 标注节点角色、共享对象主题、社区功能和证据摘要。
4. **Weak supervision**：在 Setting B 或人工审计中，LLM 标注可作为辅助标签或 consistency regularization，但不能替代行为证据。

这与 “All against some: efficient integration of large language models for message passing in graph neural networks” 和 “Label-free node classification on graphs with large language models (LLMs)” 的迁移逻辑一致：先筛选高价值节点，再用 LLM 标注/表征补全图学习信号。

## 4. GNN 的核心结构

### 4.1 输入

对每个节点：

- 行为统计特征：发文频率、活跃窗口、对象复用数、关系类型分布。
- 结构特征：in-degree、out-degree、weighted degree、PageRank、betweenness、cluster coefficient。
- LM 表征：账号文本摘要 embedding、共享对象 embedding 聚合、LLM annotation embedding。

对每条边：

- 多关系 one-hot 或 relation embedding。
- 边权、时间差、共现次数、对象热度校正分数、PSL p-value / adjusted p-value。
- 方向和时间窗口编码。

### 4.2 消息传递

第一版推荐使用轻量 R-GCN / HAN 风格结构：

```text
h_u^(0) = concat(behavior_features, structure_features, LM_embedding)

for layer l:
  m_u^r = aggregate({ W_r h_v^(l) : v -> u under relation r })
  alpha_r = relation_attention(h_u, m_u^r, edge_stats_r)
  h_u^(l+1) = sigma(W_self h_u^(l) + sum_r alpha_r * m_u^r)
```

关系 attention 是当前 `twitter_io_experiment.py` 中 learnable relation attention 的自然升级：从“按边特征融合权重”升级为“按关系类型做消息传递权重”。

### 4.3 输出

- `edge_score(u, v)`：账号对协同强度。
- `node_embedding(u)`：用户协同表示。
- `community_assignment(u)`：社区分配。
- `community_embedding(c)`：社区表征。
- `relation_attention`：不同关系对协同判定的贡献。
- `top_evidence`：最强共享对象、时间同步证据和关系类型。

## 5. 训练目标

### Setting A: discovery-only

无完整负样本时使用自监督/弱监督目标：

- **Edge reconstruction**：重构 observed coordination edges。
- **Relation contrastive learning**：真实边与时间/对象打乱的 negative edges 对比。
- **Temporal consistency**：相邻时间窗内社区表示保持稳定，同时允许突发变化。
- **Modularity regularization**：鼓励社区内边密度高、社区间边密度低，但不把 modularity 当唯一目标。
- **Evidence consistency**：同一社区内共享对象/关系 breakdown 应更集中。

### Setting B: labeled detection

有 IO/control 标签时使用监督目标：

- Edge-level coordinated vs organic classification。
- Node-level IO account ranking / classification。
- Community-level coordinated community classification。
- Community alignment loss：当 campaign/community 标签可用时，优化 NMI / ARI / FM-score 的 surrogate。

## 6. 与网络科学方法的关系

网络科学方法仍然重要，但角色应调整：

- CooRTweet：共享对象快速配对 baseline。
- CNT / multi-relation static：静态多关系融合 baseline。
- Leiden / Louvain / modularity：社区质量审计与可解释聚类 baseline。
- PageRank / degree / betweenness：Node Selection 和解释入口。

我们的主方法不是“Leiden + 指标表”，而是：

**行为图构建 -> LM 表征/标注 -> 多关系 GNN 消息传递 -> 社区发现/区分 -> 网络科学指标审计解释**。

## 7. 第一版工程落地

### Phase 1: 复用当前实验脚本

- 保留 `multi_relation_static` 作为 baseline。
- 将现有 `learned_relation_attention` 记录为 `learnable_relation_attention_v0`。
- 输出 relation attention、edge score、cluster assignment 和 top evidence。

### Phase 2: 增加 LM 特征缓存

- 新增 `semantic.py` 或 `lm_features.py`。
- 支持本地小模型或 API 生成 object/user embedding。
- embedding 必须缓存，避免每次实验重复调用。

### Phase 3: 增加轻量 GNN encoder

- 新增 `gnn_model.py`。
- 优先实现不依赖 PyTorch Geometric 的 PyTorch R-GCN/HAN-like 模型，降低部署成本。
- 后续如实验需要，再引入 PyG/DGL。

### Phase 4: API 与前端展示

- 节点 tooltip 显示 `cluster_id`、`degree`、`weighted_degree`、`influence_score`、`llm_role_label`。
- 边 tooltip 显示 `relation_attention`、`edge_score`、`object_id`、`evidence`。
- 新增社区卡片：社区主题、关键节点、关键对象、关系构成、时间窗。

## 8. 对比基线

Setting A:

- CooRTweet URL sharing。
- Single-relation baselines：URL / hashtag / media / retweet / reply / quote / mention。
- Multi-relation static weighted fusion。
- Leiden on static weighted graph。
- Learnable relation attention v0。
- Ours: LM-enhanced multi-relation GNN。

Setting B:

- CooRTweet-style percentile baseline。
- Multi-relation static。
- CARE-GNN / PC-GNN。
- HAN / MAGNN / HGT。
- R-GCN / BotRGCN-style model。
- Ours: LM-enhanced multi-relation GNN。

## 9. 汇报指标

Setting A:

- modularity、cluster_count、largest_cluster_size、density、conductance。
- object concentration、relation breakdown、top-K evidence audit。
- time/language/campaign slicing stability：Jaccard、NMI、ARI。
- relation attention interpretability。

Setting B:

- AUPRC、Precision@K、Recall@K、MaxF1、AUROC。固定阈值 F1@0.5 仅作为阈值校准诊断，不进入主结果排名；固定阈值宏平均 F1 不进入论文主表。
- community-level FM-score、NMI、ARI、Purity。
- ablation：without LM、without GNN、without relation attention、without PSL、static-only。
