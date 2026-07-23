# Literature References

## Core Papers (Cited in FINAL_PROPOSAL)

### 1. CatchSync (KDD 2014)
- **Title**: Catching Synchronized Behaviors in Large Networks: A Graph Mining Approach
- **Authors**: Jiang et al.
- **Key Contribution**: 时间同步性检测，基于时间窗口的配对行为分析
- **Relevance**: 提供了时间同步检测的经典方法，PSL 的 Object Channel 继承了其配对检测思想

### 2. Sharma et al. (KDD 2021)
- **Title**: Characterizing and Detecting Coordinated Inauthentic Behavior on Twitter
- **Authors**: Sharma, Alizadeh, et al.
- **Key Contribution**: 多行为信号融合（共享 URL、hashtag、时间同步），基于 z-score 的显著性检验
- **Relevance**: PSL 的直接对比基准，我们用对称超几何检验替代其 z-score 方法
- **Code**: 未公开

### 3. Tardelli et al. (PNAS 2024)
- **Title**: Coordinated Inauthentic Behavior Detection on Social Media
- **Authors**: Tardelli et al.
- **Key Contribution**: 跨平台协同检测，引入传播互动边
- **Relevance**: 提供了传播互动边的建模思路，但未解决热门话题误报问题

### 4. Cinus et al. (WWW 2025)
- **Title**: Graph Neural Networks for Coordinated Behavior Detection
- **Authors**: Cinus et al.
- **Key Contribution**: GNN-based 协同检测，端到端学习
- **Relevance**: 代表深度学习方向，PSL 作为轻量级统计方法与其互补

### 5. Loru et al. (TKDD 2026)
- **Title**: Temporal Coordination Detection in Social Networks
- **Authors**: Loru et al.
- **Key Contribution**: 时序 GNN，动态图建模
- **Relevance**: 未来扩展方向，当前 PSL 聚焦静态窗口

### 6. Pote et al. (ICWSM 2025)
- **Title**: Evidence-Based Coordination Detection
- **Authors**: Pote et al.
- **Key Contribution**: 证据样本输出，可解释性增强
- **Relevance**: PSL 的证据标注设计参考了其思路

### 7. Alizadeh et al. (Science Advances 2020)
- **Title**: Content-Based Features for Coordinated Inauthentic Behavior Detection
- **Authors**: Alizadeh et al.
- **Key Contribution**: 语义相似度在协同检测中的应用
- **Relevance**: PSL 的 Semantic Pair Adapter 继承了其语义建模思想

### 8. Liu & Xie (JASA 2020)
- **Title**: Cauchy Combination Test: A Powerful Test With Analytic p-Value Calculation Under Arbitrary Dependency Structures
- **Authors**: Liu & Xie
- **Key Contribution**: Cauchy combination 方法，解决依赖性 p-value 融合问题
- **Relevance**: PSL 的核心统计工具，用于多通道 p-value 融合

---

## Supplementary Papers (2023-2025 Literature Survey)

### 9. Mannocci et al. (arXiv 2024) — CIB Detection Survey
- **Title**: Detection and Characterization of Coordinated Online Behavior: A Survey
- **Authors**: Lorenzo Mannocci, Michele Mazza, Anna Monreale, Maurizio Tesconi, Stefano Cresci
- **Venue**: arXiv 2408.01257 (2024-08-02)
- **Key Contribution**: 首个系统性 CIB 检测综述，统一了工业界和学术界定义，提出了研究框架，梳理了检测与表征方法
- **Relevance**: 提供了最新研究全景，可用于定位 PSL 在检测方法谱系中的位置
- **Link**: https://arxiv.org/abs/2408.01257

### 10. Iannucci et al. (arXiv 2025) — Temporal Multiplex Coordination
- **Title**: Detecting Coordinated Activities Through Temporal, Multiplex, and Collaborative Analysis
- **Authors**: Letizia Iannucci, Elisa Muratore, Antonis Matakos, Mikko Kivelä
- **Venue**: arXiv 2512.19677 (2025-12-22)
- **Key Contribution**: 多层时序网络 + 指数衰减时间核 + 跨模态协同证据聚合。在多个数据集上优于现有方法
- **Relevance**: 与 PSL 的多通道设计高度相关。他们用 multiplex network decomposition，我们用 multi-channel object extraction + Cauchy combine。可作为潜在 baseline
- **Link**: https://arxiv.org/abs/2512.19677

### 11. Minici et al. (First Monday 2024) — Cross-Platform IO Detection
- **Title**: Uncovering Coordinated Cross-Platform Information Operations Threatening the Integrity of the 2024 U.S. Presidential Election Online Discussion
- **Authors**: Marco Minici, Luca Luceri, Federico Cinus, Emilio Ferrara
- **Venue**: First Monday 29(11), 2024 / arXiv 2409.15402
- **Key Contribution**: ML 框架检测跨平台协同操纵（X + YouTube + Web），分析 2024 美国大选期间的 link-sharing 行为
- **Relevance**: 与 Cinus WWW 2025 同一团队，提供了跨平台 IO 检测的实际案例。当前 PSL 聚焦单平台，但其 link-sharing 分析思路与 Object Channel 一致
- **Link**: https://arxiv.org/abs/2409.15402

### 12. Seckin et al. (arXiv 2024) — IO Labeled Datasets
- **Title**: Labeled Datasets for Research on Information Operations
- **Authors**: Ozgur Can Seckin, Manita Pote, Alexander Nwala, Lake Yin, Luca Luceri, Alessandro Flammini, Filippo Menczer
- **Venue**: arXiv 2411.10609 (2024-11-15)
- **Key Contribution**: 提供 26 个 IO campaign 的标注数据集，含平台验证的 IO 帖子 + 13M 条同话题同时段的有机帖子（对照组）
- **Relevance**: **高优先级数据源**。可直接用于 PSL 的 M3 (Decision) 实验——有 ground truth 的协同 vs 有机对照
- **Link**: https://arxiv.org/abs/2411.10609

### 13. Manchanayaka et al. (IJCNN 2024) — Contrast Pattern Mining
- **Title**: Identifying Coordinated Activities on Online Social Networks Using Contrast Pattern Mining
- **Authors**: Isura Manchanayaka, Zainab Zaidi, Shanika Karunasekera, Christopher Leckie
- **Venue**: IJCNN 2024 / arXiv 2407.11697
- **Key Contribution**: 用 EPClose 算法提取对比行为模式，将可疑时间窗口与历史基线对比，F1 提升 >= 10%
- **Relevance**: 提供了另一种"异常 vs 基线"的检测范式。PSL 用超几何检验做类似的"观察 vs 期望"对比，但在 pair level 而非 pattern level
- **Link**: https://arxiv.org/abs/2407.11697

### 14. Manchanayaka et al. (ICWSM 2025) — Causal Coordination Detection
- **Title**: Using Causality to Infer Coordinated Attacks in Social Media
- **Authors**: Isura Manchanayaka, Zainab Razia Zaidi, Shanika Karunasekera, Christopher Leckie
- **Venue**: ICWSM 2025 / arXiv 2407.11690
- **Key Contribution**: 用 Convergent Cross Mapping (CCM) 从时序关系推断因果协同，结合 topic modeling，在 IRA 数据集上 F1 达 75.3%
- **Relevance**: 提供了因果推断视角的协同检测。PSL 用统计显著性而非因果推断，但两者可互补。CCM 可作为未来扩展方向
- **Link**: https://arxiv.org/abs/2407.11690

---

## Baseline Datasets

### Twibot-22
- **Source**: https://twibot22.github.io/
- **Description**: Twitter bot 检测基准数据集，包含协同行为标注
- **Size**: 1M+ 用户，10M+ 推文
- **Relevance**: 可用于 PSL 的 baseline 对比实验

### Cresci-2017
- **Source**: https://botometer.osome.iu.edu/bot-repository/datasets.html
- **Description**: 经典 Twitter bot 数据集，包含多种协同模式
- **Size**: 37K 用户
- **Relevance**: 可用于 PSL 的消融实验

### TweepFake
- **Source**: https://github.com/MohamedRashad/TweepFake
- **Description**: 深度伪造账号数据集
- **Size**: 25K 用户
- **Relevance**: 可用于测试 PSL 对 AI 生成内容的鲁棒性

### CooRTweet Benchmark
- **Source**: https://github.com/QUT-Digital-Observatory/coordination-network-toolkit
- **Description**: CooRTweet 工具的基准数据集，含 german_elections 多模态多平台数据
- **Size**: 多个事件数据集
- **Relevance**: PSL 的直接对比基准（P0 优先级）

### Seckin IO Labeled Dataset (NEW — 高优先级)
- **Source**: https://arxiv.org/abs/2411.10609
- **Description**: 26 个 IO campaign 标注数据集，含平台验证 IO 帖子 + 13M 有机对照帖子
- **Size**: 303K 账号，13M+ 帖子
- **Relevance**: **最适合 PSL 评估的数据集**——有 ground truth 的协同 vs 有机对照，可直接用于 FDR 校准实验

---

## Key Concepts

### Symmetric Hypergeometric Test
- **Source**: Liu & Xie (JASA 2020)
- **Formula**: `p_pair = max(p_u, p_v)` where `p_u ~ Hypergeometric(N, K_u, n_v)`
- **Null Model**: 账号 u 和 v 的共享行为是随机采样的结果
- **Advantage**: 考虑了账号活跃度差异，避免热门话题误报

### Cauchy Combination
- **Source**: Liu & Xie (JASA 2020)
- **Formula**: `T = Σ w_i * tan((0.5 - p_i) * π)`, `p_combined ~ Cauchy(0, Σ w_i)`
- **Advantage**: 在任意依赖结构下有效，无需假设独立性
- **Application**: PSL 用于融合 Object Channel 和 Semantic Channel 的 p-values

### BH-FDR Correction
- **Source**: Benjamini & Hochberg (1995)
- **Formula**: 对排序后的 p-values 应用 `p_i * m / i ≤ α`
- **Advantage**: 控制假发现率（FDR），适合大规模多重检验
- **Application**: PSL 用于 pair-level FDR 校准，抑制热门话题误报

---

## Research Gaps Identified

1. **热门话题误报问题**: 现有方法（Sharma KDD 2021）使用简单 z-score，无法区分自然共振和人为协同
   - **PSL Solution**: 对称超几何检验 + BH-FDR 校准

2. **证据可解释性不足**: 现有方法输出二元标签，缺乏证据样本和诊断信息
   - **PSL Solution**: 证据标注（edge_type, evidence_samples, p_value, fdr_q）

3. **多通道融合依赖性问题**: 现有方法假设通道独立，但实际存在依赖（如共享 URL 和语义相似）
   - **PSL Solution**: Cauchy combination 替代 Fisher's method

4. **语义相似度计算过时**: 现有方法使用 jieba + TF-IDF，无法捕捉深层语义
   - **PSL Solution**: 冻结句向量编码器（如 text2vec-base-chinese）

5. **时间同步性建模不自然**: 现有方法将时间同步作为独立通道，但实际是所有行为的前提
   - **PSL Solution**: 时间窗口作为全局约束，不作为独立通道

---

## Next Steps

1. **下载关键论文**: Sharma KDD 2021、Liu & Xie JASA 2020、Seckin IO Dataset
2. **复现 CooRTweet baseline**: 按 BASELINE_METHODS.md 的 P0 优先级执行
3. **数据采集**: 按 DATA_SOURCES.md 的计划启动微博热门话题和新闻评论区采集
4. **Characterization 实现**: 按 P1 (Authenticity, Orchestration) → P2 (Time-variance, Harmfulness) 顺序

---

## Part 2: Characterization 文献（四维度表征）

### Dim-A: Authenticity（真实性评估）

#### 15. TwiBot-22 (NeurIPS 2022 Datasets Track)
- **Title**: TwiBot-22: Towards Graph-Based Twitter Bot Detection
- **Authors**: Shangbin Feng, Zhaoxuan Tan, Herun Wan, et al.
- **Venue**: NeurIPS 2022 Datasets and Benchmarks Track
- **Key Contribution**: 最大规模图基 bot 检测基准（1M users），提供多样化实体和关系，35+ baseline 评估
- **Relevance**: Authenticity 维度的标准评估数据集。图基方法在 TwiBot-22 上比特征方法高 8.2%
- **Link**: https://github.com/LuoUndergradXJTU/TwiBot-22

#### 16. BotDGT (arXiv 2024)
- **Title**: Dynamicity-aware Social Bot Detection with Dynamic Graph Transformers
- **Authors**: [Shangbin Feng et al.]
- **Venue**: arXiv 2404.15070 (2024)
- **Key Contribution**: 动态图 Transformer 捕获 bot 行为的时序演化，在 TwiBot-20/22 上 SOTA
- **Relevance**: 为 Authenticity 维度提供了动态检测方法——bot 行为会随时间变化以逃避检测
- **Link**: https://arxiv.org/abs/2404.15070

#### 17. UnSBot (arXiv 2024)
- **Title**: Unsupervised Social Bot Detection via Structural Information Theory
- **Authors**: [Hao Peng et al.]
- **Venue**: arXiv 2404.13595 (2024)
- **Key Contribution**: 基于结构信息论的无监督 bot 检测，不依赖标注数据，可解释
- **Relevance**: 与 PSL 的无监督/统计驱动思路一致，可作为 Authenticity 维度的轻量级方法
- **Link**: https://arxiv.org/abs/2404.13595

---

### Dim-B: Harmfulness（危害性评估）

#### 18. Framing Theory for Misinformation (arXiv 2024)
- **Title**: Detecting Misinformation through Framing Theory: the Role of LLMs and Deep Neural Networks
- **Authors**: [待补充]
- **Venue**: arXiv 2402.15525 (2024)
- **Key Contribution**: 利用 LLM + DNN 检测基于准确事实但通过框架效应误导的内容
- **Relevance**: Harmfulness 维度的核心方法——协同群体传播的内容可能事实准确但框架有害
- **Link**: https://arxiv.org/abs/2402.15525

#### 19. Narratives at Conflict (ACL 2024)
- **Title**: Narratives at Conflict: Computational Analysis of News Framing in Multilingual Disinformation Campaigns
- **Authors**: [待补充]
- **Venue**: ACL 2024 Student Research Workshop
- **Key Contribution**: 多语言虚假信息中的叙事框架计算分析，发现不同语言受众的框架策略差异
- **Relevance**: 为 Harmfulness 维度提供了叙事框架分类方法，可用于识别协同群体的传播策略
- **Link**: https://acl.ldc.upenn.edu/2024.acl-srw.21/

#### 20. MetaTox (arXiv 2024)
- **Title**: Enhancing LLM-based Hatred and Toxicity Detection with Meta-Toxic Knowledge Graph
- **Authors**: [待补充]
- **Venue**: arXiv 2412.15268 (2024)
- **Key Contribution**: 构建 meta-toxic 知识图谱，通过图搜索增强 LLM 的毒性检测能力
- **Relevance**: Harmfulness 维度的毒性检测方法，可用于评估协同群体内容的毒性水平
- **Link**: https://arxiv.org/abs/2412.15268

#### 21. Multilingual Claim Detection Survey (arXiv 2024)
- **Title**: Automated Claim Detection for Fact-Checking: A Survey on Monolingual, Multilingual and Cross-Lingual Research
- **Authors**: [待补充]
- **Venue**: arXiv 2401.11969 (2024)
- **Key Contribution**: 事实核查综述，涵盖 claim 检测 → 证据检索 → 验证的完整流水线
- **Relevance**: Harmfulness 维度的事实核查信号，可用于评估协同群体传播内容的真实性
- **Link**: https://arxiv.org/abs/2401.11969

---

### Dim-C: Orchestration（组织度评估）

#### 22. Post-hoc Node Influence in Cascades (ACM 2024)
- **Title**: Post-hoc Evaluation of Nodes Influence in Information Cascades: The Case of Coordinated Accounts
- **Authors**: [待补充]
- **Venue**: ACM Digital Library, 2024 (DOI: 10.1145/3700644)
- **Key Contribution**: 评估协同账号在信息级联中的实际影响力，发现协同账号的网络影响力可能低于预期
- **Relevance**: Orchestration 维度的关键发现——组织度高不等于影响力大，需要区分评估
- **Link**: https://dl.acm.org/doi/10.1145/3700644

#### 23. ACCD (arXiv 2025)
- **Title**: Adaptive Causal Coordination Detection for Social Media: A Memory-Guided Framework with Semi-Supervised Learning
- **Authors**: [待补充]
- **Venue**: arXiv 2601.00400 (2025)
- **Key Contribution**: 自适应因果协同检测，F1 87.3%（超越最强 baseline 15.2%），减少 68% 人工标注
- **Relevance**: Orchestration 维度的 SOTA 方法。其因果推断可用于识别协同群体的指挥结构
- **Link**: https://arxiv.org/abs/2601.00400

#### 24. State-linked Actor Coordination (Springer 2023)
- **Title**: [Computational and Mathematical Organization Theory paper on state-linked coordination]
- **Authors**: [待补充]
- **Venue**: Computational and Mathematical Organization Theory, 2023
- **Key Contribution**: 国家关联行为者的协同模式度量，发现其内部协同度显著高于与非关联账号的协同
- **Relevance**: Orchestration 维度的实证基础——centralized orchestration 的典型案例
- **Link**: https://link.springer.com/article/10.1007/s10588-023-09382-7

---

### Dim-D: Time-variance（时变性评估）

#### 25. EMNLP 2025 Findings — Temporal Coordination and Influence
- **Title**: Insights into Using Temporal Coordinated Behaviour to Explore Connections Between Social Media Posts and Influence
- **Authors**: [待补充]
- **Venue**: Findings of EMNLP 2025
- **Key Contribution**: 时序协同行为与影响力的关联分析
- **Relevance**: Time-variance 维度的最新工作，将时序模式与影响力度量关联
- **Link**: https://acl.ldc.upenn.edu/2025.findings-emnlp.1325/

#### 26. Neural Temporal Point Process (arXiv 2021)
- **Title**: Knowledge Informed Neural Temporal Point Process for Coordination Detection on Social Media
- **Authors**: [待补充]
- **Venue**: arXiv 2110.15454 (2021)
- **Key Contribution**: 知识增强的神经时序点过程，联合学习群组分配的 Gibbs 分布
- **Relevance**: Time-variance 维度的建模方法——用点过程捕获协同行为的时序动态
- **Link**: https://arxiv.org/abs/2110.15454

---

## Part 3: 补充高水平文献（第二轮检索）

### Dim-A 补充: Authenticity

#### 27. RGT: Heterogeneity-Aware Twitter Bot Detection (AAAI 2023)
- **Title**: Heterogeneity-Aware Twitter Bot Detection with Relational Graph Transformers
- **Authors**: Shangbin Feng et al.
- **Venue**: AAAI 2023 (CCF-A)
- **Key Contribution**: 关系图 Transformer 处理 Twitter 异构网络中的 bot 检测，利用多种关系类型（follow/mention/retweet）
- **Relevance**: Authenticity 维度的 CCF-A 级方法。RGT 在 TwiBot-22 上是 top-5 方法之一
- **Link**: https://aaai.org/papers/03977-heterogeneity-aware-twitter-bot-detection-with-relational-graph-transformers/

#### 28. SEBot: Structural Entropy Guided Contrastive Learning (arXiv 2024)
- **Title**: Structural Entropy Guided Multi-View Contrastive Learning for Social Bot Detection
- **Authors**: [待补充]
- **Venue**: arXiv 2405.11225 (2024)
- **Key Contribution**: 结构熵引导的多视图对比学习，解决 GNN 消息传递导致的节点表示同质化问题
- **Relevance**: 与 UnSBot 互补——都基于结构信息论，但 SEBot 用对比学习增强区分度
- **Link**: https://arxiv.org/abs/2405.11225

#### 29. Generative AI Bot Survey (Springer 2025)
- **Title**: Dissecting a Social Bot Powered by Generative AI: Anatomy, New Trends and Challenges
- **Authors**: [待补充]
- **Venue**: Social Network Analysis and Mining, Springer 2025
- **Key Contribution**: 生成式 AI 驱动的社交 bot 综述，分析 LLM bot 的新特征和检测挑战
- **Relevance**: 前瞻性参考——当 bot 使用 LLM 生成内容时，传统特征失效，需要行为模式检测
- **Link**: https://link.springer.com/article/10.1007/s13278-025-01410-5

#### 30. Unmasking Social Bots: How Confident Are We? (EPJ Data Science 2025)
- **Title**: Unmasking Social Bots: How Confident Are We?
- **Authors**: [待补充]
- **Venue**: EPJ Data Science, 2025
- **Key Contribution**: 系统评估 bot 检测的不确定性，指出现有方法的置信度问题
- **Relevance**: 为 Authenticity 维度提供了方法论警示——bot_probability 需要校准，不能盲信
- **Link**: https://epjdatascience.springeropen.com/articles/10.1140/epjds/s13688-025-00536-y

---

### Dim-B 补充: Harmfulness

#### 31. The Influence of Coordinated Behavior on Toxicity (arXiv 2023)
- **Title**: The Influence of Coordinated Behavior on Toxicity
- **Authors**: [Mannocci, Cresci et al.]
- **Venue**: arXiv 2310.01283 (2023)
- **Key Contribution**: 直接研究协同行为与毒性之间的因果关系，发现协同群体显著提升讨论毒性
- **Relevance**: **高度相关**——直接连接 Detection (协同发现) 和 Harmfulness (危害性评估)，证明两阶段的因果链
- **Link**: https://arxiv.org/abs/2310.01283

#### 32. Toxicity Detection with Knowledge Graphs (AAAI 2024)
- **Title**: Supporting Online Toxicity Detection with Knowledge Graphs
- **Authors**: [待补充]
- **Venue**: AAAI 2024 (CCF-A)
- **Key Contribution**: 知识图谱增强的毒性检测，解决上下文依赖和隐式毒性问题
- **Relevance**: Harmfulness 维度的 CCF-A 级方法，可用于评估协同群体内容的隐式危害
- **Link**: https://aaai.org/papers/01414-supporting-online-toxicity-detection-with-knowledge-graphs/

#### 33. Propagation Tree Contrastive Learning for Rumor Detection (AAAI 2024)
- **Title**: Propagation Tree Is Not Deep: Adaptive Graph Contrastive Learning Approach for Rumor Detection
- **Authors**: [待补充]
- **Venue**: AAAI 2024 (CCF-A)
- **Key Contribution**: 发现传播树实际上不深，提出自适应图对比学习方法
- **Relevance**: Harmfulness 维度——协同群体传播的谣言检测，与 Propagation Analysis 传播监控有交叉
- **Link**: https://ojs.aaai.org/index.php/AAAI/article/view/27757

#### 34. LLM-Enhanced Rumor and Stance Detection (arXiv 2025)
- **Title**: LLM-Enhanced Multiple Instance Learning for Joint Rumor and Stance Detection
- **Authors**: [待补充]
- **Venue**: arXiv 2502.08888 (2025)
- **Key Contribution**: LLM 增强的多实例学习，联合预测帖子立场和声明类别，仅需声明级标签
- **Relevance**: Harmfulness 维度的弱监督方法——可用于评估协同群体对特定声明的立场分布
- **Link**: https://arxiv.org/abs/2502.08888

#### 35. Emotion Detection for Misinformation (Information Fusion 2024)
- **Title**: Emotion Detection for Misinformation: A Review
- **Authors**: [待补充]
- **Venue**: Information Fusion, 2024 (CCF-B, IF > 14)
- **Key Contribution**: 情感检测在虚假信息识别中的作用综述，情感特征可区分真假新闻
- **Relevance**: Harmfulness 维度的辅助信号——协同群体传播内容的情感极性可作为危害性指标
- **Link**: https://dl.acm.org/doi/10.1016/j.inffus.2024.102300

---

### Dim-C 补充: Orchestration

#### 36. Influence Operations in Social Networks: 7 Strategies (arXiv 2025)
- **Title**: Influence Operations in Social Networks
- **Authors**: [待补充]
- **Venue**: arXiv 2502.11827 (2025)
- **Key Contribution**: 识别并量化 7 种在线影响操作策略，分析 80 起外国信息干预事件
- **Relevance**: Orchestration 维度的策略分类框架——可用于将协同群体映射到具体操作策略
- **Link**: https://arxiv.org/abs/2502.11827

#### 37. Unsupervised Fake-Follower Campaign Detection (arXiv 2023)
- **Title**: Unsupervised Detection of Coordinated Fake-Follower Campaigns on Social Media
- **Authors**: [待补充]
- **Venue**: arXiv 2310.20407 (2023)
- **Key Contribution**: 无监督检测协同假粉丝活动，针对操纵用户指标的恶意账号
- **Relevance**: Orchestration 维度的特定模式——fake-follower campaign 是高度组织化的协同行为
- **Link**: https://arxiv.org/abs/2310.20407

---

### Dim-D 补充: Time-variance

#### 38. Discovering Coordinated Processes from Social Networks (arXiv 2025)
- **Title**: Discovering Coordinated Processes From Social Online Networks
- **Authors**: [待补充]
- **Venue**: arXiv 2506.12988 (2025)
- **Key Contribution**: 从社交网络中发现协同过程，区分真实行为和恶意协同的复杂结构
- **Relevance**: Time-variance 维度——将协同行为建模为时序过程而非静态快照
- **Link**: https://arxiv.org/abs/2506.12988

#### 39. Users' Response to Toxicity in Conversations (ICWSM 2024)
- **Title**: Users' Behavioral and Emotional Response to Toxicity in Twitter Conversations
- **Authors**: [待补充]
- **Venue**: ICWSM 2024 (CCF-B)
- **Key Contribution**: 数据驱动研究毒性对用户行为和情感的时序影响，考虑混杂因素
- **Relevance**: Time-variance + Harmfulness 交叉——协同群体注入毒性后，正常用户行为的时序变化
- **Link**: https://ojs.aaai.org/index.php/ICWSM/article/view/31295
