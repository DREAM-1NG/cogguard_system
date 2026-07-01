# EXPERIMENT_PLAN

> ⚠️ 方向对齐说明（2026-06-26，覆盖本文与之冲突处）：KT1 最新定位为 **GNN + LM 增强的协同社区构建与发现**。协同边证据仍以共同行为特征为核心，但不再把方法限制为纯网络科学社区发现。
> - LM 可用于共享对象归一、节点/社区表征、Node Selection 后的 LLM annotation 和解释；不能把立场、毒性、危害性等内容分类直接作为协同边证据。
> - GNN 是主方法的学习组件，用于多关系、动态、有向协同图上的消息传递、关系 attention、边/节点/社区表示学习。
> - PSL（对称超几何 + Cauchy + BH-FDR）作为行为通道的显著性筛查和可解释审计组件保留，不再是唯一核心方法。

## 当前目标

在现有协调图构建流程上升级出第一版 **LM-enhanced multi-relation GNN**：保留 Pair Surprisal Layer 作为显著性审计，增加 LM 节点/对象表征、learnable relation attention / GNN 消息传递、社区发现与协同区分输出。

## 正式实验定位：协同发现 -> 协同区分

KT1 的正式实验按两类设置组织，避免把无标签协同发现和有标签分类混为一个任务。

### Setting A: discovery-only

**数据集**: X/Twitter Information Operations Archive。

**目标**: 证明方法能够从正样本 IO 档案中构建可解释的多关系协同图，并通过 LM 表征 + GNN 消息传递发现协同账号社区、关键账号对和关键共享对象。该设置不强行报告账号二分类分数，因为数据主要是已披露 IO 档案，缺少完整 organic/control 背景。

**主指标**:
- 网络结构: node_count, edge_count, weighted_degree, density, component_count
- 社区发现: modularity, cluster_count, largest_cluster_size, cluster size distribution
- 解释性: top_objects, relation/channel breakdown, top-K edge evidence audit
- 稳定性: time-window/language/month slicing 下的 cluster Jaccard、NMI 或 ARI
- 学习型解释: relation attention distribution、without LM / without GNN / static-only 消融

### Setting B: labeled detection

**数据集**: Guo & Vosoughi 2022 state-backed IO dataset 或 Seckin et al. 2025 labeled IO datasets。

**目标**: 证明 Setting A 学到的协同图、GNN 节点/社区表征和边分数能够区分自发行为与协同攻击。该设置将 IO 账号/账号对/社区视为正样本，将 control/organic 账号或跨 campaign 随机配对视为负样本。

**主指标**:
- 排序检测: AUPRC, Precision@K, Recall@K
- 分类/阈值选择检测: MaxF1, AUROC
- 调试诊断: F1@0.5（不进入论文主表）
- 社区对齐: FM-score, NMI, ARI, Purity

**辅助指标**: bot score、toxicity、stance、harmfulness 等内容或身份表征只用于 characterization，不回流为 KT1 的协同判据。

## 技术路线

### 核心方法：LM-enhanced Multi-relation GNN

KT1 主方法由四层组成：

1. **Behavior graph construction**：从 URL、hashtag、媒体指纹、转发/回复/引用/提及目标、cascade root、模板指纹中构建多关系动态有向图。
2. **LM feature layer**：对共享对象、账号历史和高影响节点生成 embedding / annotation，用于 object canonicalization、节点/社区语义表征和解释。
3. **Multi-relation GNN layer**：在多关系图上执行消息传递，学习 relation attention、edge score、node embedding 和 community embedding。
4. **Community discovery and discrimination**：Setting A 输出社区和证据，Setting B 输出排序/分类分数。

PSL 不替代 GNN 的主方法，而是作为行为边显著性、热门对象校正和 evidence audit 的统计约束层。

### 统计审计层：Pair Surprisal Layer

一个即插即用的配对显著性评估层，叠加在冻结的 CooRTweet 配对引擎之上：

1. **对称双账号超几何检验**: p_pair = max(p_u, p_v)，校正 object 热度和双方账号活跃度
2. **Cauchy combination test**: 在任意依赖结构下合并多 object、多通道 p-values（Liu & Xie, JASA 2020）
3. **Pair-level BH-FDR**: 在配对层级做多重检验控制，提供形式化假阳性率保证

### 通道架构

| 通道 | 类型 | 数据来源 | 走 detect_groups? |
|------|------|----------|-------------------|
| Object Channel (link) | plug-in | post.url | Yes [frozen] |
| Object Channel (hashtag) | plug-in | post.hashtags | Yes [frozen] |
| Object Channel (media) | plug-in | post.media_urls | Yes [frozen] |
| Object Channel (cascade) | plug-in | raw_comments.reply_to → root_post_id | Yes [frozen] |
| Template Fingerprint Channel | plug-in | post/comment near-duplicate fingerprint | Yes/Direct |
| LM Feature Layer | feature | object/user/community text context → embedding/annotation | No, feature only |

### Pipeline

```
raw_posts + raw_comments
  → Multi-Channel Extraction
    Object Channel: url/hashtag/media/root_post_id → detect_groups [frozen]
    Template Channel: MinHash/near-duplicate fingerprint → candidate edges
  → Pair Surprisal Layer
    Step 1: symmetric hypergeom per (u,v,o)
    Step 2: Cauchy combine per (u,v)
    Step 3: BH-FDR at pair level
    Step 4: evidence assembly
  → LM Feature Layer
    object canonicalization + node/community embeddings + LLM annotation for selected nodes
  → Multi-relation GNN
    relation attention + edge score + node/community embedding
  → Community Discovery / Discrimination
  → API + Frontend
```

---

## 代码基线

| 层 | 文件 | 现状 |
|---|---|---|
| 检测器 | `core/coordination/detector.py` | `detect_groups()` — 冻结，不修改 |
| 网络 | `core/coordination/network.py` | 加权无向图 — 需扩展边属性 |
| 统计 | `core/coordination/stats.py` | account_stats + group_stats |
| 服务 | `services/coordination_service.py` | MongoDB → DataFrame → detect → network → stats — 需加多通道提取 |
| API | `api/v1/coordination.py` | `POST /detect` — 需加参数 |
| 前端 | `views/coordination/index.vue` | 力导向可视化 — 最小适配 |

---

## 工作包

### WP-1: 多通道 Object 提取
- 在 `coordination_service.py` 中新增 `_extract_multi_channel_objects(posts, comments)`
- Object Channel: url, hashtag, media_url, root_post_id → 统一 DataFrame
- 输出: `[object_id, channel, subtype, account_id, content_id, timestamp]`
- 保持现有逻辑作为 fallback（enable_channels 默认 ["object"]）

### WP-2: PairSurprisalLayer 实现
- 新增 `core/coordination/significance.py`
- `PairSurprisalLayer` 类:
  - `score_pairs()`: 对称超几何 per (u,v,o)，unique event 去重
  - `combine_pairs()`: Cauchy combination per (u,v)
  - `fdr_control()`: pair-level BH-FDR
  - `assemble_evidence()`: edge_channels + top-1 evidence per channel
- 新增依赖: scipy (hypergeom, combine), statsmodels (multipletests)

### WP-3: LM Feature Layer 实现
- 新增 `core/coordination/lm_features.py` 或 `semantic.py`
- 功能:
  - object canonicalization：URL 归一、标题/描述摘要、hashtag family 聚合
  - node embedding：账号历史行为上下文 + 共享对象上下文的 embedding 聚合
  - community embedding：社区内对象和证据摘要的 embedding 聚合
  - Node Selection + LLM annotation：按 in-degree/out-degree/weighted degree/PageRank/betweenness 选择高影响节点并标注角色
- 工程要求:
  - embedding/annotation 必须缓存
  - 默认可用轻量本地 fallback（TF-IDF/SVD 或小模型 embedding）
  - LM 特征只进入 GNN 表示与解释，不作为单独协同边判据

### WP-4: Cascade 提取（Object Channel 子类型）
- 在 `coordination_service.py` 中新增 cascade 提取逻辑
- raw_comments.reply_to → 追溯到 root_post_id
- object_id = f"cascade_{root_post_id}"
- 走 detect_groups [frozen] → PairSurprisalLayer

### WP-5: network.py 改造与 API 适配
- 边属性增加: edge_channels, edge_score, adjusted_p, evidence
- `graph_to_dict()` 序列化新字段
- `POST /detect` 增加可选参数: enable_channels, alpha, sim_threshold
- 向后兼容（新参数均有默认值）

### WP-5b: 多关系 GNN Encoder
- 新增 `core/coordination/gnn_model.py`
- 第一版优先实现 PyTorch 轻量 R-GCN / HAN-like encoder，不强依赖 PyTorch Geometric
- 输入: relation-specific edge features、PSL scores、LM node/object embeddings、时间/方向特征
- 输出: edge_score、node_embedding、community_embedding、relation_attention
- 训练:
  - Setting A: edge reconstruction + negative sampling + temporal consistency + modularity regularization
  - Setting B: edge/node/community supervised classification or ranking loss

### WP-6: Mock 数据增强与测试
- MockCrawler 增加: 协同帖子共享 media_url、相似内容模板、回复链
- 新增 `tests/test_coordination_multi.py`:
  - 核心机制消融 (5 variants)
  - 多通道覆盖测试
  - 热门话题压力测试
  - 证据完整性测试
  - 向后兼容回归测试
- 目标: >= 10 个用例全部通过

### WP-7: 前端最小适配
- `coordination.ts` 更新类型定义
- `index.vue` 边渲染按 channel 着色，tooltip 显示证据
- 统计表格增加 channel 分布列

---

## 依赖与顺序

```
WP-1 (多通道提取) ────────┐
WP-2 (PairSurprisalLayer) ┼──> WP-5 (network+API) ──> WP-7 (前端)
WP-3 (LM Feature Layer) ──┼──> WP-5b (GNN Encoder)
WP-4 (Cascade 提取) ──────┘

WP-6 (mock+测试) 贯穿全程
```

WP-1/2/3 可并行。WP-4 依赖 WP-1 基础设施。WP-5 依赖 WP-1~4。WP-5b 依赖 WP-1/2/3 的特征输出。WP-7 最后。

---

## 验证策略（Claim-Driven）

### Formal Setting A: 协同发现
- Dataset: X/Twitter IO Archive
- Claim: LM-enhanced multi-relation GNN 能够从 IO 档案中发现结构清晰、证据可解释的协同社区
- Primary Metrics: modularity, cluster_count, largest_cluster_size, density/conductance, object concentration, relation/channel breakdown, top-K manual precision
- Baselines: CooRTweet-style URL sharing, hashtag_share, retweet_target, reply_target, multi_relation_static, learnable_relation_attention_v0, Leiden/static graph

### Formal Setting B: 协同区分
- Dataset: Guo & Vosoughi 2022 或 Seckin et al. 2025 labeled IO/control dataset
- Claim: 协同发现阶段得到的 GNN 节点/边/社区表征能够区分 coordinated attack 与 organic/self-organized behavior
- Primary Metrics: AUPRC, Precision@K, Recall@K, MaxF1, AUROC
- Diagnostic Metrics: F1@0.5 only; do not include fixed-threshold macro-averaged F1 in paper main tables
- Community Metrics: FM-score, NMI, ARI, Purity
- Baselines: 单关系 CooRTweet-style baselines, multi_relation_static, learnable_relation_attention_v0, CARE-GNN/PC-GNN/HAN/MAGNN/HGT/R-GCN（在有标签图设置中作为辅助强基线）

### Claim 0: GNN + LM 增益
- Variants: static multi-relation / learnable attention v0 / GNN without LM / LM features without GNN / full LM-enhanced GNN
- Setting A Metric: modularity, conductance, object concentration, cluster stability, evidence audit precision
- Setting B Metric: AUPRC, Precision@K, Recall@K, MaxF1, AUROC
- Expected: full LM-enhanced GNN 在 Setting B 上优于 static 和 attention v0；Setting A 至少提升稳定性、证据集中度或社区可解释性

### Claim 1 (核心): 机制消融
- 5 variants: popularity-unaware / one-sided / no-Cauchy / no-BH / full layer
- Metric: FDR, Recall, F1
- Expected: full layer 在 FDR 上优于所有 variants

### Claim 2: 多通道覆盖
- Object-only vs object + template fingerprint + cascade
- Expected: >= 1.5× detected pairs

### Claim 3: 自然共振抑制
- 热门话题压力测试 (organic + coordinated on same hashtag)
- Expected: FDR -50%, Recall >= 85%

### Claim 4: 证据诊断性
- 盲审 50 条标记边
- Expected: Likert mean >= 3.5/5

### 工程验证
- 向后兼容: 默认参数返回结构不变
- 性能: 1000 帖子 < 10s
- 前端: 无报错渲染

## 退出标准

- 协同结果不再只有单一信号来源
- 输出可指出"为什么被判为协同"（通道 + 证据 + adjusted_p）
- 热门话题误报率显著下降（FDR 有统计保证）
- Characterization 四维度至少有 Authenticity + Orchestration 可输出
- 不修改禁止路径，不破坏现有功能

## 关键文件清单

| 文件 | 操作 |
|---|---|
| `core/coordination/detector.py` | 冻结，不修改 |
| `core/coordination/network.py` | 边属性扩展 |
| `core/coordination/significance.py` | 新增 (PairSurprisalLayer) |
| `core/coordination/lm_features.py` 或 `semantic.py` | 新增 (LM Feature Layer) |
| `core/coordination/gnn_model.py` | 新增 (Multi-relation GNN Encoder) |
| `services/coordination_service.py` | 多通道提取 + 调用 PSL |
| `api/v1/coordination.py` | 参数扩展 |
| `core/crawler/mock.py` | 数据增强 |
| `tests/test_coordination_multi.py` | 新增 |
| `frontend/src/api/coordination.ts` | 类型更新 |
| `frontend/src/views/coordination/index.vue` | 最小适配 |

## 参考

- 完整技术提案: `refine-logs/FINAL_PROPOSAL.md`
- 评审摘要: `refine-logs/REVIEW_SUMMARY.md`
- 细化报告: `refine-logs/REFINEMENT_REPORT.md`
- 详细实验计划: `refine-logs/EXPERIMENT_PLAN_DETAILED.md`
- 文献引用: `LITERATURE_REFERENCES.md` (39 篇)
- Liu & Xie (2020). Cauchy Combination Test. JASA.
- Mannocci et al. (2024). Detection and Characterization of CIB: A Survey. arXiv 2408.01257.

---

## Part 2: Characterization 验证计划（四维度表征）

基于 Mannocci et al. (2024) 综述框架，对 Detection 输出的协同群体进行四维度表征。

### Claim 5: Authenticity — 协同群体自动化程度显著高于有机群体

**任务定义**: 评估协同群体中账号的真实性/自动化程度

**方法**:
- 基于已有 `account_profiler.py` 扩展
- 行为特征: 发文频率、间隔方差、作息节律熵、互动模式规律性
- 群体聚合: 成员级 bot_probability → 群体级 authenticity_score

**实验设计**:
- **数据**: TwiBot-22 (labeled) + Seckin IO Dataset
- **Baseline**: Botometer score, BotRGCN
- **Metric**: 群体级 AUC (coordinated vs organic)
- **Expected**: 协同群体 authenticity_score 显著低于有机群体 (p < 0.01)

**验证数据集**: TwiBot-22 (1M users, GitHub 公开), Cresci-2017 (37K users)

**关键文献**:
- RGT (AAAI 2023) — 异构图 Transformer
- BotDGT (arXiv 2404.15070) — 动态图 Transformer
- UnSBot (arXiv 2404.13595) — 无监督结构信息论
- SEBot (arXiv 2405.11225) — 结构熵对比学习
- Unmasking Bots (EPJ 2025) — 置信度校准

**工作包**: WP-8 [P1]

---

### Claim 6: Harmfulness — 协同群体内容毒性/误导性显著高于有机内容

**任务定义**: 评估协同群体共享内容的危害程度和类型

**方法**:
- 毒性检测: 冻结分类器 (Perspective API 或本地 BERT)
- 叙事框架: LLM-based framing detection
- 情感极性: 极端情感检测
- 群体聚合: 内容级 harm_indicators → 群体级 harm_score + harm_type

**实验设计**:
- **数据**: Seckin IO Dataset (26 campaigns + 13M organic)
- **Baseline**: 随机内容样本的毒性/情感分布
- **Metric**: toxicity_ratio, extreme_sentiment_ratio (Mann-Whitney U test)
- **Expected**: IO campaign toxicity_ratio >= 2× organic

**验证数据集**: Seckin IO Dataset (303K accounts, 13M posts), Twitter IRA Archive

**关键文献**:
- Coordinated Behavior → Toxicity (arXiv 2310.01283) — 因果链证据
- Toxicity with KG (AAAI 2024) — 知识图谱增强
- Propagation Tree (AAAI 2024) — 谣言传播检测
- LLM Rumor+Stance (arXiv 2502.08888) — 弱监督立场
- Emotion for Misinfo (Info Fusion 2024) — 情感信号
- Framing Theory (arXiv 2402.15525) — 框架效应检测

**工作包**: WP-9 [P2]

---

### Claim 7: Orchestration — 网络结构可区分中心化/去中心化/自发涌现

**任务定义**: 评估协同群体的组织化程度

**方法**:
- 网络结构指标 (直接从 PSL 输出计算):
  - Freeman centralization index
  - Degree assortativity coefficient
  - Core-periphery ratio (Borgatti-Everett)
  - Hub dominance (最大度节点边占比)
- 分类规则:
  - centralization > 0.5 + hub_dominance > 0.3 → centralized
  - centralization < 0.3 + assortativity > 0.2 → decentralized
  - 其余 → emergent

**实验设计**:
- **数据**: IRA (centralized) + GameStop/WSB (decentralized) + Seckin IO
- **Baseline**: 随机图结构指标分布
- **Metric**: 分类准确率, Cohen's d (IO vs organic)
- **Expected**: IRA centralization > 0.5; WSB assortativity > 0.2

**验证数据集**: IRA Dataset (Twitter IO archive), GameStop/WSB (Reddit 2021), Seckin IO

**关键文献**:
- Post-hoc Node Influence (ACM 2024) — 影响力评估
- ACCD (arXiv 2601.00400) — 因果协同检测 F1 87.3%
- State-linked Coordination (Springer 2023) — 国家行为者模式
- Influence Operations 7 Strategies (arXiv 2502.11827) — 策略分类
- Fake-Follower Campaigns (arXiv 2310.20407) — 高组织度模式

**工作包**: WP-10 [P1]

---

### Claim 8: Time-variance — 时序模式可分类为 stable/bursty/adaptive/dormant

**任务定义**: 评估协同群体行为的时间演化模式

**方法**:
- 时序特征 (多窗口):
  - activity_entropy: 活跃度时间分布熵
  - burst_frequency: 突发频率
  - lifetime: 活跃持续时间
  - inter_event_cv: 事件间隔变异系数
  - adaptation_rate: 行为模式变化速率
- Archetype 分类:
  - stable: low entropy + low burst + long lifetime
  - bursty: high burst + short lifetime + high cv
  - adaptive: high adaptation + medium lifetime
  - dormant: long inactive + sporadic bursts

**实验设计**:
- **数据**: Seckin IO Dataset (多 campaign) + 真实微博采集
- **Baseline**: Tardelli PNAS 2024 archetype 分类
- **Metric**: silhouette score, archetype 分布一致性
- **Expected**: >= 3 种 archetype 可清晰区分 (silhouette > 0.4)

**验证数据集**: Seckin IO Dataset, Tardelli PNAS 2024 (联系作者), 微博采集数据

**关键文献**:
- Tardelli et al. (PNAS 2024) — Temporal Archetypes
- Iannucci et al. (arXiv 2025) — Temporal Multiplex
- EMNLP 2025 Findings — Temporal coordination and influence
- Neural TPP (arXiv 2110.15454) — 时序点过程
- Discovering Coordinated Processes (arXiv 2506.12988) — 过程发现
- Users' Response to Toxicity (ICWSM 2024) — 时序行为变化

**工作包**: WP-11 [P2]

---

## Characterization 依赖与顺序

```
Detection (WP-1~7) 完成后:
                    │
    ┌───────────────┼───────────────┐
    ▼               ▼               ▼
WP-8 (Auth)    WP-10 (Orch)    WP-11 (Time)
  [P1]           [P1]            [P2]
    │               │               │
    └───────┬───────┘               │
            ▼                       │
       WP-9 (Harm)                  │
         [P2]                       │
            │                       │
            └───────────┬───────────┘
                        ▼
              系统集成 + 前端展示
```

WP-8/10 可并行（P1，不依赖额外模型）。WP-9 依赖毒性模型选型。WP-11 依赖多窗口数据。
