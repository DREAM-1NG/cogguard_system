# CogGuard 系统背景综述

> **版本**：2026-08-04 ｜ **用途**：CISCN 2026 决赛答辩参考、团队内部认知对齐
> **维护规则**：本文严格区分「已落地」「设计稿」「缺口」三态，不把计划当完成。所有创新主张标注诚实边界。

---

## 1. 一页速览

| 维度 | 内容 |
|------|------|
| **项目名称** | CogGuard — 面向网络舆论对抗的跨平台协同攻击监测系统 |
| **项目定位** | 面向网络舆论对抗的**跨平台协同操纵分析**证据驱动原型系统 |
| **核心闭环** | 事件 → 证据 → **协同发现** → **传播监控** → **报告研判** → 处置 |
| **功能一** | 协同发现 (Coordination Discover / Detect) — 基于平台无关的共同行为特征的跨平台协同检测 |
| **功能二** | 传播监控 (Propagation Analysis) — 事件条件下的分层传播预测框架 (CascadeSwitch) |
| **功能三** | 报告研判 (Risk Review) — 白盒前瞻引擎 + 多 Agent 编排 |
| **后端** | Python 3.11 / FastAPI / SQLAlchemy(async) / Motor / Celery |
| **前端** | Vue 3 / TypeScript / Vite 6 / Ant Design Vue 4 / ECharts 6 / Pinia |
| **存储** | MySQL 8（结构化） / MongoDB 7（原始数据） / Redis 7（缓存+队列） |
| **验证范围** | mock_weibo、weibo、news（跨源，非跨平台身份解析） |
| **一句话现状** | 数据采集全链路、协同检测 MVP、传播趋势预测核心、报告研判白盒引擎均已落地可运行；三大关键技术的"创新增强层"多为设计稿，存在 LLM 客户端依赖缺失等共性阻塞 |

---

## 2. 问题域与研究背景

### 2.1 协同信息操纵：一个日益严峻的安全威胁

协同信息操纵（Coordinated Inauthentic Behavior, CIB）是指通过有组织的多账号协同行为，在社交媒体上操纵公众舆论、干预选举、制造恐慌或推动特定叙事的行为。与传统的单账号虚假信息传播不同，CIB 具有以下特点：

- **组织性**：幕后有统一指挥或协调机制，账号群体行为高度同步
- **跨平台性**：同一操纵战役往往横跨 Twitter/X、Facebook、YouTube、TikTok、微博等多个平台
- **隐蔽性**：操纵者持续优化策略（使用 AI 生成内容、购买真人账号），规避传统检测方法
- **规模化**：单次操纵战役涉及数千至数十万个账号、数百万条内容

根据 Mannocci 等人 2024 年的综述（arXiv 2408.01257），CIB 研究已形成 **Detection（发现协同行为）+ Characterization（刻画协同性质）** 的两阶段框架，并从四个维度进行表征：Authenticity（真实性）、Harmfulness（危害性）、Orchestration（组织化程度）、Time-variance（时序演化模式）。

### 2.2 现有方法的局限性

现有研究面临三大核心挑战：

**1. 平台依赖性**：绝大多数协同检测方法依赖平台特定信号（如 Twitter 的 co-retweet、co-follow），难以迁移到微博、TikTok 等不同平台。Schneider & Rizoiu 的 *Beyond Content*（arXiv 2602.02838）和 Luceri 等人的 *CIB on TikTok*（arXiv 2505.10867）均指出这一问题。

**2. 内容信号脆弱性**：依赖内容相似度（文本语义、图片指纹）的方法在 AI 改写/生成时代面临失效风险。生成式 AI 使操纵者能以极低成本生成高度多样化的内容，传统的基于内容特征的 bot 检测和协同检测准确率显著下降。

**3. 分析碎片化**：现有系统多聚焦单一环节（检测 or 传播分析 or 风险评估），缺乏从"事件→证据→协同→传播→风险→处置"的端到端证据链闭环。

### 2.3 CogGuard 的定位

CogGuard 试图以"**事件级证据闭环**"为核心叙事，构建一条覆盖采集→协同发现→传播监控→报告研判→处置建议的完整分析链路，其三大关键技术分别对应该链路中的三个核心环节：

1. **协同发现**：只用平台无关的"共同行为特征"做复用融合检测，刻意排除内容信号
2. **传播监控**：用 LLM 提取外生事件驱动体制后验，实现分层传播预测
3. **报告研判**：白盒前瞻引擎（阶段预警 + DISARM 攻击路径预判 + D-S 融合），从 detection 升级到 anticipation + countermeasure

设计原则：**规则/证据优先于黑盒 LLM 裁决**；LLM/Agent 作增强与呈现层，不作最终裁决；内容分析单向下沉至 Risk Review，绝不回流作为协同判据。

---

## 3. 协同发现的学术背景与技术路线

### 3.1 问题定义

协同发现的核心任务是：在给定事件窗口内，从多平台社交数据中识别出"共同推动某叙事"的协同账号群体，输出协同边、证据和协同群组。

按 Mannocci 综述（arXiv 2408.01257）的两阶段框架：
- **Detection**：发现"谁在协同"——识别具有异常协同行为模式的账号对/群体
- **Characterization**：刻画"协同群体是什么样"——从 Authenticity、Harmfulness、Orchestration、Time-variance 四维度表征

### 3.2 方法演进与代表性工作

#### 3.2.1 基于行为相似性的协同网络方法

| 工作 | Venue/年份 | 核心贡献 |
|------|-----------|---------|
| **CooRTweet / Coordination Network Toolkit** | 开源工具, 2024 | 提供 co-URL/co-tweet/co-retweet 等协同网络构建的参考实现，按时间窗配对+阈值裁剪+社区发现 |
| **Minici, Luceri, Cinus, Ferrara** — Uncovering Cross-Platform IO | First Monday 29(11) 2024 / arXiv 2409.15402 | 核心信号为 link-sharing（co-URL）相似网络，跨 X/YouTube/Web 的跨平台协同检测 |
| **Cinus, Minici, Luceri, Ferrara** — Exposing Cross-Platform CIB | arXiv 2410.22716, 2024 | 基于 similarity network（含 co-link）跨 X/Facebook/Telegram，新方向"共同行为特征复用融合"的范本 |
| **Luceri 等** — CIB on TikTok | arXiv 2505.10867, 2025 | 提出 co-caption / multimedia content reuse（共媒体指纹）/ co-hashtag 的最新定义，拓展到视频优先生态 |

#### 3.2.2 基于统计与生成模型的方法

| 工作 | Venue/年份 | 核心贡献 |
|------|-----------|---------|
| **Sharma, Zhang, Ferrara, Liu** — AMDN-HAGE | **KDD 2021 (CCF-A)** | 神经时序点过程 + 高斯混合隐组模型检测协同（注：非 z-score，文档已纠正） |
| **Somin, Cohen, Kepner, Pentland** — Echoes of the Hidden | arXiv 2504.02757, 2025 | 证明"共享突发(bursty)活动"可在链接稀疏时识别协同 |
| **Manchanayaka 等** — Contrast Pattern Mining | IJCNN 2024 / arXiv 2407.11697 | "可疑窗口 vs 历史基线"对比范式 |

#### 3.2.3 社区发现与网络分析

| 工作 | Venue/年份 | 核心贡献 |
|------|-----------|---------|
| **Traag, Waltman, van Eck** — From Louvain to Leiden | Scientific Reports 2019 | Leiden 算法原始出处，保证 well-connected communities |
| **Tardelli 等** — Temporal Dynamics of Coordinated Online Behavior | **PNAS 121(20) 2024** | 时序 archetype/稳定性论文，定义 stable/bursty/adaptive/dormant 模式 |
| **Pote, Elmas, Flammini, Menczer** — Coordinated Reply Attacks | **ICWSM 2025 (CCF-B)** | 刻画 reply 级联协同攻击的检测 |

### 3.3 SOTA 局限性

1. **平台特定性**：co-retweet/co-follow 仅适用于 Twitter/X，无法直接迁移
2. **内容信号脆弱**：基于文本/图像相似度的方法面临 AI 改写威胁
3. **缺乏统计严谨性**：热门话题的自然共振容易造成误报，多数方法仅用百分位阈值而非统计检验
4. **单平台局限**：跨平台身份解析（identity resolution）成本极高

### 3.4 CogGuard 的技术路线与定位

**核心主张**：只用平台无关的"共同行为特征"做复用融合检测，内容检测不作为协同信号。

- **行为信号**：时间同步/共现、共享对象（URL/hashtag/媒体指纹 id）、共转发与回复级联、账号行为节律
- **行为 vs 内容边界判据**：是否需要"理解内容说了什么"——共享同一媒体对象（按 id/指纹）= 行为；分析视频内容/字幕 mismatch/文本立场/毒性 = 内容（排除）
- **显著性筛查 (PSL)**：设计了对称超几何 + Cauchy combination + pair-level BH-FDR 的统计框架（**设计稿，未落地**）

**创新 delta 与诚实边界**：

| 维度 | 说明 |
|------|------|
| **借鉴源** | CooRTweet 工具（配对+阈值+社区）、Cinus/Luceri 跨平台 similarity network |
| **Delta** | PSL 统计框架（对称超几何+Cauchy+BH-FDR）替代纯阈值裁剪 |
| **撞车文献** | Schneider & Rizoiu *Beyond Content* (2602.02838)、Luceri *CIB on TikTok* (2505.10867) 已提出行为优先/平台无关方向 |
| **⚠ 诚实边界** | (1) "行为优先/平台无关"不是原创首发；(2) PSL 是 0 行代码；(3) "跨平台"仅验证 mock_weibo/weibo/news（跨源非跨平台身份）；(4) 社区发现代码实际是 greedy modularity 而非文档声称的 Leiden |

---

## 4. 传播监控的学术背景与技术路线

### 4.1 问题定义

传播监控的核心任务是：给定观测窗内的帖子序列和已感染节点序列，预测未来 1h/6h/24h 的传播量（宏观规模），以及刻画传播态势（子图结构、关键角色、源头追溯）。

**职责边界**（2026-06-03 厘清）：Propagation Analysis **只做传播动力学**（规模/形态/路径预测），**不做内容分析**。立场检测、危害性评估等内容理解任务已全部移交 Risk Review。

### 4.2 方法演进与代表性工作

#### 4.2.1 级联规模预测

| 工作 | Venue/年份 | 核心贡献 |
|------|-----------|---------|
| **DeepCas** (Li, Ma, Guo, Mei) | **WWW 2017** | 级联规模预测任务奠基工作，定义观测窗→最终规模设定 |
| **DeepHawkes** (Cao, Shen 等) | **CIKM 2017** | Hawkes 自激点过程 + 深度学习，级联早期时序/转发轨迹特征的经典刻画 |
| **CasCN** (Chen, Zhou, Zhang 等) | **ICDE 2019 (CCF-A)** | 图卷积建模级联结构的主流深度基线 |
| **CasFlow** (Xu, Zhou 等) | **IEEE TKDE 2021** | 显式建模传播不确定性（变分推断） |
| **CasFT** | arXiv 2409.16619, 2024 | 用 neural ODE 抽取动态线索引导未来增量生成 |

#### 4.2.2 LLM 与时序预测

| 工作 | Venue/年份 | 核心贡献 |
|------|-----------|---------|
| **Time-LLM** (Jin, Wang, Ma 等) | **ICLR 2024** | LLM 作为时序"上下文/语义编码器"的范式来源 |
| **LLMTime** (Gruver, Finzi 等) | **NeurIPS 2023** | LLM 零样本处理序列/数值的能力边界 |
| **AutoCas** (Zheng, Gong 等) | arXiv 2502.18040, 2025 | LLM 直接驱动级联预测的最新代表 |
| **Tan 等** — Are LLMs Useful for TS? | **NeurIPS 2024 (Spotlight)** | 论证纯 LLM 数值预测不可靠→为"轻量时序特征 + 体制模型"提供动机 |

#### 4.2.3 微观路径预测

| 工作 | Venue/年份 | 核心贡献 |
|------|-----------|---------|
| **Topo-LSTM** (Wang, Shen 等) | arXiv 2017 | 微观下一跳预测的先驱 |
| **NDM** (Yang, Tang 等) | arXiv 2018 | 用户级"谁感染谁"的微观级联预测 |
| **FOREST** (Yang, Tang 等) | **IJCAI 2019 (CCF-A)** | 微观路径 + 宏观规模联合建模 |

### 4.3 SOTA 局限性

1. **纯观测序列驱动**：现有级联模型（DeepCas/DeepHawkes/CasCN/CasFlow）仅用观测序列，无外生事件条件——在事件突变点（如官方回应、平台干预）预测失准
2. **LLM 直接做时序的问题**：Tan 等 (NeurIPS 2024) 证明 LLM 数值外推不可靠，但 LLM 在语义/上下文理解上有独特优势
3. **规模 vs 路径断裂**：宏观规模预测与微观路径预测通常由不同模型独立完成，缺乏统一条件化框架

### 4.4 CogGuard 的技术路线与定位

**核心方案 — CascadeSwitch**：用 LLM 把帖子内容抽成**外生事件**（6 类：kol_amplification / official_response / platform_intervention / narrative_mutation / coordinated_burst / none），驱动透明的**体制后验 p(z|events,history)**，并以该后验同时条件化三个尺度的传播预测。

```
LLM 事件抽取 ──→ 体制后验 p(z|events,history)   ← CascadeSwitch 核心
                      │
        ┌─────────────┼──────────────────────────┐
        ▼             ▼                           ▼
   Tier-0 宏观     Tier-1 中观                Tier-2 微观
   规模预测 ŷ      路径形态预测               下一跳预测
   (标量,已落地)   P(中心化/去中心化/          P(下一激活节点 v |
                  跨群桥接 | z,events)          序列, 条件于 p(z))
   零训练白盒      零训练白盒(设计稿)          训练式(缺口)
```

- **4 体制**：seeding（线性增长）→ amplification（指数增长）→ peak（logistic 饱和）→ decay（指数衰减）
- **后验混合**：`p(z) = softmax((W·e + b) / τ)`，混合预测 `ŷ = Σ p(z)·f_z`
- **核心设计决策**：LLM 仅做事件抽取（语义理解），不做数值外推；时序预测由零训练白盒体制模型完成

**创新 delta 与诚实边界**：

| 维度 | 说明 |
|------|------|
| **借鉴源** | DeepHawkes（特征工程）、CasFlow（不确定性）、Time-LLM（LLM 作语义编码器的范式） |
| **Delta** | 外生事件条件化 + 体制后验混合 = 现有级联模型均无外生事件条件 |
| **撞车文献** | CasFT (2409.16619) 用 neural ODE 抽取"动态线索"引导预测，思路同源；AutoCas (2502.18040) LLM 直接驱动级联预测 |
| **⚠ 诚实边界** | (1) LLM 事件抽取在线默认 `mock=True`，未在公开数据集上跑过实验；(2) Tier-1 路径形态预测为设计稿；(3) Tier-2 微观下一跳预测为缺口，依赖边级真值数据（Twitter15/16/FOREST）；(4) 后端无 LLM 客户端依赖，真实 API 尚未接入 |

---

## 5. 报告研判的学术背景与技术路线

### 5.1 问题定义

报告研判回答三个问题：
1. **当前风险多高**（信念区间）
2. **接下来会发生什么**（阶段转换 + 下一步攻击技术预测）
3. **应该如何应对**（反制建议）

核心叙事：从 detection 升级到 **anticipation + countermeasure**。

### 5.2 方法演进与代表性工作

#### 5.2.1 生命周期与阶段建模

| 工作 | Venue/年份 | 核心贡献 |
|------|-----------|---------|
| **Gautam** — Multi-agent Systems for the Misinformation Lifecycle | arXiv 2505.17511, 2025 (ICWSM) | "全生命周期"对标：分类→纠正→溯源，但无操作性阶段预测 |
| **arXiv 2508.18230** — ML Framework for ATT&CK Techniques | arXiv 2025 | phase-aware 多模型 + 阶段间有向图，是"阶段感知预测"范式的方法论原语来源 |

#### 5.2.2 攻击路径预测（源自网络安全 ATT&CK 域）

| 工作 | Venue/年份 | 核心贡献 |
|------|-----------|---------|
| **MITRE TIE** (Technique Inference Engine) | CTID 2024 | 从已观测 TTP 推荐下一步 TTP 的直接先前工作 |
| **Markov+LSTM 攻击链预测** | UMass Dartmouth thesis, 2023/2024 | Markov 攻击链下一步预测 |
| **MDP-MCTS Kill-Chain 推理** | arXiv 2512.15150, 2025 | MDP 把入侵建模为状态转移序列 |
| **Agentic DISARM** | arXiv 2601.15109, 2026 | 已有 DISARM Agent 化先例，但为 flat tagging |

#### 5.2.3 Agent + RAG 编排

| 工作 | Venue/年份 | 核心贡献 |
|------|-----------|---------|
| **MCP-Orchestrated Multi-Agent** | arXiv 2508.10143, 2025 | Agent 编排集成检测（95.3% acc） |
| **MARO** (Li 等) | **EMNLP 2025** | 多 Agent 自适应规则、question-reflection |
| **Debate-to-Detect** (Han 等) | **EMNLP 2025** | 分阶段辩论协议、shared memory |
| **RAMA** (Yang 等) | arXiv 2507.09174, 2025 | 多模态 claim-to-query、多源证据聚合 |

#### 5.2.4 证据融合

| 工作 | Venue/年份 | 核心贡献 |
|------|-----------|---------|
| **Wu 等** — Evidence-Aware Fake News Detection | IEEE TKDE 2024 | 证据感知建模 【存疑：DOI 10027720 需复核】 |
| **RumourEval** (Gorrell 等) | SemEval 2019 | support/deny/query/comment 立场分类标准 |
| **HateXplain** (Mathew 等) | **AAAI 2021** | 可解释有害内容检测基准 |

### 5.3 SOTA 局限性

1. **Agent 创新性争议**：Agent + RAG 做报告/分析是方法论红海，大量近作（2508.10143、2505.17511）已覆盖
2. **阶段标注数据缺失**：信息操纵战役的阶段演化缺乏公开标注数据集
3. **DISARM 路径预测为跨域迁移**：ATT&CK 域已有成熟先例（TIE、Markov+LSTM），DISARM 域尚无标准数据

### 5.4 CogGuard 的技术路线与定位

**头号创新 = 白盒前瞻引擎**（已落地，~1340 行）：

1. **Phase-Aware Hazard**：5 状态战役生命周期（seed → synchronize → breakout → saturation → regeneration）+ logistic hazard 预测阶段转换 / breakout 预警
2. **DISARM Attack-Path**：手工领域转换图 + 路径评分（depth × tactic breadth × completeness）+ 预测下一步技术（top-3）+ 反制建议
3. **Contradiction-Aware D-S Fusion**：信念区间 + 冲突检测 + 阶段调制质量

**Agent/RAG = 编排呈现层**（设计稿，非创新卖点）。

**创新 delta 与诚实边界**：

| 维度 | 说明 |
|------|------|
| **借鉴源** | MITRE TIE（攻击路径推理范式）、ATT&CK 阶段感知 (2508.18230)、D-S 证据理论（经典）|
| **Delta** | 跨域迁移：把网安攻击路径推理迁移到 DISARM 信息操纵域 + 阶段条件化 + 白盒可审计 + CPU-only |
| **撞车文献** | Agentic DISARM (2601.15109) 已做 DISARM Agent 化；Gautam (2505.17511) 多 agent 生命周期 |
| **⚠ 诚实边界** | (1) 不可声称"首创攻击路径预测"，应表述为"首次将网安攻击路径推理迁移到 DISARM 域"；(2) Agent/RAG 是设计稿，头号创新必须是已落地的白盒引擎；(3) Phase-Aware Hazard 缺公开标注数据，验证依赖 mock + 案例 + 专家评估；(4) 转换图与转换概率是手工 domain-informed prior |

---

## 6. 系统总体架构

### 6.1 分层架构

```
┌─────────────────────────────────────────────────────────┐
│ 前端 (Vue 3 + TS + Ant Design Vue 4 + ECharts 6 + Pinia) │
│  登录 / 监测看板 / 数据采集 / 协同检测 / 传播监控 /        │
│  账号自动化先验与角色画像 (Account Profiler) / 报告研判    │
├─────────────────────────────────────────────────────────┤
│ 后端 API (FastAPI, /api/v1 & /api/v2 ，/api/v1 为主业务路由，/api/v2 为 V2 统一分析接口) — 7+ 路由组 │
│  auth / dashboard / crawl / coordination /                │
│  accounts / propagation / risk                            │
├─────────────────────────────────────────────────────────┤
│ 服务层 services/ — 业务编排                                │
├─────────────────────────────────────────────────────────┤
│ 核心算法 core/ — coordination / propagation / risk /      │
│  account_profiler / crawler                               │
├─────────────────────────────────────────────────────────┤
│ 研究包 research/ — coordination_discover / detect /       │
│  propagation_analysis / review_teacher / social_bot       │
├─────────────────────────────────────────────────────────┤
│ 数据层  MySQL(用户/任务/研判) MongoDB(帖子/评论/原始)      │
│         Redis(缓存+Celery broker)  NetworkX(内存图)        │
├─────────────────────────────────────────────────────────┤
│ 采集层  Social Runtime / News Runtime / MockCrawler       │
└─────────────────────────────────────────────────────────┘
```

### 6.2 技术选型与理由

| 层 | 选型 | 理由 |
|----|------|------|
| 后端框架 | FastAPI (Python 3.11+) | 异步高性能，自带 OpenAPI 文档 |
| 前端框架 | Vue 3 + TypeScript + Vite 6 | 生态成熟，中后台场景适配 |
| UI 组件 | Ant Design Vue 4 | 数据分析场景组件丰富 |
| 可视化 | ECharts 6 | 力导向图、时间线、趋势图支持 |
| 结构化存储 | MySQL 8 | 用户、任务、研判报告 |
| 非结构化存储 | MongoDB 7 (Motor async) | 帖子、评论、爬取原始数据 |
| 缓存/队列 | Redis 7 | 缓存、会话、Celery broker |
| 图分析 | NetworkX（内存） | 当前阶段轻量路线 |
| 异步任务 | Celery + Redis | 采集、分析等耗时操作 |
| 鉴权 | JWT + bcrypt | 角色 admin/analyst/viewer |

### 6.3 数据流与接缝

```
crawl → MongoDB(raw_posts/comments)
  → coordination_service.detect ─┐
  → propagation_service.analyze ─┼─→ risk_service.assess_risk
  → account_service.profiles ────┘    (evidence_builder → phase_detector
                                        → ds_fusion → disarm_scorer → report_builder)
```

**事件级证据闭环的完整链路**：

1. **采集**：通过 Social Runtime（微博/抖音/小红书）和 News Runtime（新闻提取）获取原始数据，标准化入 MongoDB
2. **协同发现**：从 MongoDB 提取事件窗口内的帖子，构建共享对象配对 → 加权图 → 社区发现 → 输出协同群组与证据边
3. **传播监控**：提取时序特征 → LLM 事件抽取 → 体制后验 → 规模预测 → 传播子图 + 关键角色识别
4. **报告研判**：消费协同/传播/账户三上游证据 → 构建证据包 → 阶段检测 → D-S 融合 → DISARM 路径 → 生成结构化报告
5. **处置回流**：报告输出风险等级、预警、反制建议，回流至监测策略调整

### 6.4 API 总览

| 路由组 | 主要端点 | 说明 |
|--------|---------|------|
| auth | `/auth/register` `/login` `/refresh` `/profile` | 身份认证 |
| dashboard | `GET /dashboard/overview` | 监测看板 |
| crawl | `POST /crawl/social` `GET /crawl/jobs` `GET /crawl/data` | 数据采集 |
| coordination | `POST /coordination/detect` | 协同检测 |
| accounts | `GET /accounts/profiles` `GET /accounts/detail/{id}` | 账号自动化先验与角色画像 (Account Profiler / Social Bot Detection) |
| propagation | `GET /propagation/analyze` `POST /propagation/predict-trend` | 传播监控 |
| risk | `POST /risk/assess` `GET /risk/reports` | 报告研判 |

---

## 7. 落地状态总览

### 7.1 数据采集（闭环输入）

| 子模块 | 代码文件 | 状态 |
|--------|---------|------|
| 爬虫抽象基类 | `core/crawler/base.py` | ✅ 已落地 |
| Mock 爬虫 | `core/crawler/mock.py` | ✅ 已落地 |
| 社交平台直连 | `core/crawler/social.py` (883行) | ✅ 已落地 |
| 新闻提取 | `core/crawler/news.py` | ✅ 已落地 |
| 跨平台标准化 | `core/crawler/normalizer.py` | ✅ 已落地 |
| 异步采集任务 | `tasks/crawl_tasks.py` | ✅ 已落地 |

### 7.2 协同发现 (Coordination Discover / Detect)

| 子功能 | 代码文件 | 状态 |
|--------|---------|------|
| 时间共现 + 共享对象配对 | `core/coordination/detector.py` (184行) | ✅ 已落地 |
| 加权图 + 阈值 + 社区发现 | `core/coordination/network.py` (373行) | ✅ 已落地（⚠ 用 greedy_modularity，非 Leiden） |
| 账户/群组统计 | `core/coordination/stats.py` (142行) | ✅ 已落地 |
| PSL 显著性筛查 | `significance.py` | ❌ **设计稿（0 行代码）** |
| 多行为通道抽取 | `channels.py` | ❌ **设计稿** |
| 语义通道 | `semantic.py` | ❌ 设计稿（新方向倾向排除） |
| Authenticity 维度 | 无对应文件 | ❌ 缺口（`account_profiler.py` 仅浅层） |
| Orchestration 维度 | `network.py` 部分指标 | ⚠ 雏形（有 bridge_score 等，无分级） |
| Time-variance 维度 | `detector.py::flag_speed_share` | ❌ 缺口（多窗口打标雏形，无 archetype） |
| Harmfulness 维度 | — | ➡️ 归属 Risk Review |

**研究包 (`system/research/`)**：

| 研究包 | 路径 | 状态 |
|--------|------|------|
| Coordination Discover | `system/research/coordination_discover/` | CPU 研究 pipeline，平台通用证据图，strict Leiden，可运行 |
| Coordination Detect | `system/research/coordination_detect/` | 公开标签验证边界存在，当前未标注事件不可声称 |
| Social Bot Detection | `system/research/social_bot_detection/` | BotRHG transfer 可运行，NLPCC 对齐路径可运行 |

### 7.3 传播监控 (Propagation Analysis)

| 子功能 | 代码文件 | 状态 |
|--------|---------|------|
| 时序特征工程 | `core/propagation/ts_features.py` (107行) | ✅ 已落地 |
| LLM 事件抽取 | `core/propagation/llm_context.py` (162行) | ✅ 已落地（⚠ 默认 `mock=True`，真实 API 未接入） |
| Tier-0 体制模型+预测器 | `regime_model.py` (224行) + `trend_predictor.py` (180行) | ✅ 已落地（零训练白盒） |
| 传播子图+关键角色 | `propagation_legacy.py` (585行) | ✅ 已落地 |
| 证据链+路径回溯 | `propagation_legacy.py` | ✅ 已落地（⚠ **已观测图回溯，非预测**） |
| Tier-1 路径形态预测 | — | 🔲 设计稿（零训练，未落地） |
| Tier-2 微观下一跳预测 | — | ❌ **缺口（无设计无代码）** |

**研究包**：

| 研究包 | 路径 | 状态 |
|--------|------|------|
| Propagation Analysis | `system/research/propagation_analysis/` | hindcast protocol、基线注册、Split-Conformal Interval (分割保形区间)可运行；拟合检查点待审批 |

### 7.4 报告研判 (Risk Review)

| 子功能 | 代码文件 | 状态 |
|--------|---------|------|
| 多源证据构建 | `core/risk/evidence_builder.py` (244行) | ✅ 已落地 |
| Phase-Aware Hazard | `core/risk/phase_detector.py` (169行) | ✅ 已落地（⚠ 缺公开战役阶段标注数据集，验证依赖 mock 数据 + 专家评估 + 案例研究） |
| D-S 融合 | `core/risk/ds_fusion.py` (234行) | ✅ 已落地 |
| DISARM 攻击路径 | `core/risk/disarm_scorer.py` (381行) | ✅ 已落地（⚠ 转换概率为手工 prior，缺公开标注，验证依赖案例研究与专家评估） |
| 结构化报告生成 | `core/risk/report_builder.py` (278行) | ✅ 已落地（模板版） |
| LLM 桥接 | `core/risk/llm_bridge.py` (~30行) | ⚠ 占位（return None） |
| RAG 报告增强 | — | ❌ 设计稿 |
| Agent 证据编排 | — | ❌ 设计稿 |
| 有害内容检测 Agent | — | ❌ 设计稿 |
| 立场检测 Agent | — | ❌ 设计稿 |
| 反制叙事 Agent | — | ❌ 设计稿 |

**研究包**：

| 研究包 | 路径 | 状态 |
|--------|------|------|
| Review Teacher | `system/research/review_teacher/` | 5+1+1 advisory DAG 可运行，非 canonical |
| Review Student | `system/runtimes/review_student/` | 同步 preliminary verdict，shadow_untrained |

### 7.5 横向支撑模块

| 模块 | 状态 | 说明 |
|------|------|------|
| 账号自动化先验与角色画像 (Account Profiler) | ✅ 已落地 | `core/account_profiler.py` (163行)，行为画像+自动化倾向评分 |
| 身份认证 | ✅ 已落地 | JWT + bcrypt，角色控制 |
| 监测看板 | 🔧 开发中 | 聚合 MongoDB 事件数据 + ECharts |
| 预警中心 | ❌ 未启动 | — |
| 报告中心 | ❌ 未启动 | — |

---

## 8. 差距与风险分析

### 8.1 三条共性阻塞

| # | 阻塞 | 影响范围 | 说明 |
|---|------|---------|------|
| 1 | **LLM 客户端依赖缺失** | Propagation Analysis + Risk Review | `pyproject.toml` 无任何 LLM SDK（无 openai/dashscope/deepseek）。Propagation Analysis 真实事件抽取现走 `mock_llm=True`；Risk Review Agent 层完全依赖未来补依赖 |
| 2 | **统计/算法依赖缺失** | Coordination Discover / Detect | 无 scipy/statsmodels，PSL（超几何+BH-FDR）无法实现；无 igraph/leidenalg，Leiden 社区发现无法替代当前 greedy modularity |
| 3 | **无评估闭环** | 全模块 | 三模块均无基准数值，"超越 SOTA"类宣称暂无实证支撑 |

### 8.2 答辩风险点

#### 风险 1：创新主张的文献撞车

| 模块 | 主张 | 撞车文献 | 建议应对口径 |
|------|------|---------|------------|
| 协同发现 | "行为优先/平台无关" | Beyond Content (2602.02838)、CIB on TikTok (2505.10867) | **不能当原创首发**，delta 收窄到 PSL 统计框架（但 0 行代码） |
| 传播监控 | "LLM 事件驱动级联预测" | CasFT (2409.16619)、AutoCas (2502.18040) | 强调"LLM 仅做事件抽取不做数值外推"的分工差异，以及"零训练白盒"的可解释性优势 |
| 报告研判 | "Agent+RAG 攻击分析" | Agentic DISARM (2601.15109)、Multi-agent Lifecycle (2505.17511) | 头号创新主秀白盒引擎（已落地），Agent/RAG 降级为编排呈现层 |
| 报告研判 | "攻击路径预测" | MITRE TIE (2024)、ATT&CK ML (2508.18230) | 不称"首创"，表述为"首次跨域迁移到 DISARM 信息操纵域" |

#### 风险 2："跨平台"口径

当前仅验证 mock_weibo / weibo / news — 这是**跨源**（不同数据类型），而非**跨平台身份解析**（在不同平台上关联同一操纵者）。答辩须明确此边界，避免被质疑"你的跨平台在哪里"。

**建议口径**：系统设计面向跨平台，验证阶段覆盖微博社交数据和新闻数据的跨源分析；不做强身份统一（identity resolution），而是建立行为、内容、时间、资源层面的软连接。

#### 风险 3：设计与实现不一致

| 位置 | 设计声称 | 代码实际 | 影响 |
|------|---------|---------|------|
| 社区发现 | Leiden 算法 | `greedy_modularity_communities`（CNM） | 需如实说明或补实现 |
| LLM 事件抽取 | DeepSeek API 接入 | 默认 `mock=True`，无 API KEY | demo 中"事件条件"不生效 |
| Risk Review Agent | Agent 编排器 | `llm_bridge.py` return None | Agent 功能完全不可用 |

### 8.3 创新 delta 总结（诚实版）

| 模块 | 可守住的 delta | 不可声称 |
|------|--------------|---------|
| **协同发现** | PSL 统计框架（设计稿）；CooRTweet 重写 + 图 + 社区发现的工程集成 | "首创行为优先/平台无关"、"Leiden 社区发现"（代码不是） |
| **传播监控** | 外生事件条件化体制后验混合预测（CascadeSwitch Tier-0 已落地）| "LLM 驱动级联预测"（mock 状态）、"路径预测"（缺口）、"超越 SOTA"（无数字） |
| **报告研判** | 白盒前瞻引擎已落地（Phase + DISARM + D-S ~1340 行）；跨域迁移 ATT&CK→DISARM | "首创攻击路径预测"、"Agent 创新"（设计稿）|

### 8.4 内容分析归属的统一口径

> **答辩最致命一题："内容分析归谁？"**

- **内容分析（立场/危害/有害言论）唯一归宿 = Risk Review 的 Characterization**
- **Coordination Discover / Detect 纯行为**：刻意的鲁棒性设计，排除内容信号（承认单平台可能略损召回，换取跨平台可迁移与抗 AI 改写）
- **Propagation Analysis 只做传播动力学**：规模/体制预测，不碰内容分类
- **内容信号单向流动**：从下游消费，绝不回流作为协同判定依据

---

## 9. 参考文献列表

> 以下文献均从项目文档 `doc/SUBFUNCTION_LITERATURE_MAP.md` 和 `doc/research/` 中提取，标注核实状态。

### 协同发现领域

1. Mannocci, Mazza, Monreale, Tesconi, Cresci. *Detection and Characterization of Coordinated Online Behavior: A Survey*. arXiv 2408.01257, 2024. 【已核实】
2. Sharma, Zhang, Ferrara, Liu. *Identifying Coordinated Accounts on Social Media through Hidden Influence and Group Behaviours*. **KDD 2021 (CCF-A)**. arXiv 2008.11308. 【已核实，方法为 AMDN-HAGE】
3. Minici, Luceri, Cinus, Ferrara. *Uncovering Coordinated Cross-Platform Information Operations*. First Monday 29(11) 2024 / arXiv 2409.15402. 【已核实】
4. Cinus, Minici, Luceri, Ferrara. *Exposing Cross-Platform Coordinated Inauthentic Activity*. arXiv 2410.22716, 2024. 【已核实】
5. Luceri 等. *CIB on TikTok: Challenges and Opportunities for Detection in a Video-First Ecosystem*. arXiv 2505.10867, 2025. 【已核实】
6. Somin, Cohen, Kepner, Pentland. *Echoes of the Hidden: Uncovering Coordination beyond Network Structure*. arXiv 2504.02757, 2025. 【已核实】
7. Tardelli 等. *Temporal Dynamics of Coordinated Online Behavior: Stability, Archetypes, and Influence*. **PNAS 121(20) 2024**. DOI 10.1073/pnas.2307038121. 【已核实】
8. Pote, Elmas, Flammini, Menczer. *Coordinated Reply Attacks in Influence Operations*. **ICWSM 2025 (CCF-B)**. 【已核实】
9. Traag, Waltman, van Eck. *From Louvain to Leiden: Guaranteeing Well-Connected Communities*. Scientific Reports 2019. 【已核实】
10. Liu & Xie. *Cauchy Combination Test*. **JASA 2020**. 【已核实】
11. Benjamini & Hochberg. *Controlling the False Discovery Rate*. JRSS-B 1995. 【已核实】
12. Manchanayaka, Zaidi, Karunasekera, Leckie. *Identifying Coordinated Activities Using Contrast Pattern Mining*. IJCNN 2024 / arXiv 2407.11697, 2024. 【已核实】

### 传播监控领域

13. Li, Ma, Guo, Mei. *DeepCas: An End-to-end Predictor of Information Cascades*. **WWW 2017**. arXiv 1611.05373. 【已核实】
14. Cao, Shen, Cen, Ouyang, Cheng. *DeepHawkes: Bridging the Gap between Prediction and Understanding of Information Cascades*. **CIKM 2017**. 【已核实】
15. Chen, Zhou, Zhang 等. *Information Diffusion Prediction via Recurrent Cascades Convolution (CasCN)*. **ICDE 2019 (CCF-A)**. 【已核实】
16. Xu, Zhou 等. *CasFlow: Exploring Hierarchical Structures and Propagation Uncertainty for Cascade Prediction*. **IEEE TKDE 2021**. 【已核实】
17. Jin, Wang, Ma 等. *Time-LLM: Time Series Forecasting by Reprogramming Large Language Models*. **ICLR 2024**. arXiv 2310.01728. 【已核实】
18. Gruver, Finzi, Qiu, Wilson. *Large Language Models Are Zero-Shot Time Series Forecasters (LLMTime)*. **NeurIPS 2023**. arXiv 2310.07820. 【已核实】
19. Tan 等. *Are Language Models Actually Useful for Time Series Forecasting?* **NeurIPS 2024 (Spotlight)**. arXiv 2406.16964. 【已核实】
20. Zheng, Gong 等. *AutoCas: Autoregressive Cascade Predictor via LLMs*. arXiv 2502.18040, 2025. 【已核实】
21. CasFT. arXiv 2409.16619, 2024. 【已核实】
22. Yang, Tang 等. *FOREST: Multi-scale Information Diffusion Prediction*. **IJCAI 2019 (CCF-A)**. 【已核实】
23. Wang, Shen 等. *Topo-LSTM*. arXiv 1711.10162, 2017. 【已核实】

### 报告研判领域

24. MITRE CTID. *Technique Inference Engine (TIE)*. CTID 2024. 【已核实】
25. UMass Dartmouth Thesis. *Attack Chain Contraction and Prediction using Markov Model and LSTM on MITRE ATT&CK*. 2023/2024. 【已核实】
26. Policy-Value Guided MDP-MCTS Framework for Cyber Kill-Chain Inference. arXiv 2512.15150, 2025. 【已核实】
27. arXiv 2508.18230. *ML Framework for Predicting and Mapping ATT&CK Techniques*. 2025. 【已核实】
28. arXiv 2601.15109. *An Agentic Operationalization of DISARM for FIMI Investigation*. 2026. 【已核实】
29. Gautam. *Multi-agent Systems for the Misinformation Lifecycle*. arXiv 2505.17511, 2025. 【已核实】
30. arXiv 2508.10143. *MCP-Orchestrated Multi-Agent System for Automated Disinformation Detection*. 2025. 【已核实】
31. Li 等 (MARO). *A Multi-Agent Framework with Automated Decision Rule Optimization*. **EMNLP 2025**. 【已核实】
32. Han 等. *Debate-to-Detect*. **EMNLP 2025**. 【已核实】
33. Yang 等 (RAMA). *Retrieval-Augmented Multi-Agent Framework*. arXiv 2507.09174, 2025. 【已核实】
34. Wu et al. *Adversarial Contrastive Learning for Evidence-Aware Fake News Detection*. IEEE TKDE 2024. 【存疑：DOI 10027720 需复核】
35. DISARM Foundation. *DISARM Red Framework*. https://www.disarm.foundation/framework 【已核实】
36. Mathew 等. *HateXplain*. **AAAI 2021**. 【已核实】
37. Gorrell 等. *RumourEval 2019*. SemEval 2019. 【已核实】
38. Fanton / Chung 等. *Generating Counter Narratives (CONAN)*. **ACL 2021**. 【已核实】

### 撞车风险文献

39. Schneider & Rizoiu. *Beyond Content*. arXiv 2602.02838. — 行为优先/平台无关方向
40. CasFT. arXiv 2409.16619. — 动态线索驱动级联预测
41. AutoCas. arXiv 2502.18040. — LLM 驱动级联预测
42. Agentic DISARM. arXiv 2601.15109. — DISARM Agent 化
43. Multi-agent Misinformation Lifecycle. arXiv 2505.17511. — 多 Agent 全生命周期

---

> **文档结束**。本综述从 `doc/PROJECT_OVERVIEW.md`、`doc/SUBFUNCTION_LITERATURE_MAP.md`、`doc/research/`、`CONTEXT.md`、`UBIQUITOUS_LANGUAGE.md` 等项目文档交叉核实编制，力求准确反映系统现状与学术定位。所有落地状态描述基于代码实际情况而非设计文档。
