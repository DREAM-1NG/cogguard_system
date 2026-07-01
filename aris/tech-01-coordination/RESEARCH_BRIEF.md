# RESEARCH_BRIEF

## Problem Statement

当前 CogGuard 协同检测停留在单信号驱动的网络构建阶段（CooRTweet percentile threshold），存在三个结构性缺陷：信号单一、无显著性筛查、无证据输出。

根据 Mannocci et al. (2024) 的综述框架，协同行为研究分为两个任务：
- **Detection** f(U,H) → 发现协同群体
- **Characterization** g(Y,H) → 评估协同群体的属性

**系统功能层面**：CogGuard 需要同时覆盖 Detection（协同发现）和 Characterization（协同评估/类型分类）。

**关键技术层面**：KT1 的核心创新聚焦于 Detection 内部的方法突破——如何在 Network Science 的 co-action 检测范式内，将 edge filtering 从启发式阈值升级为 pair-level 统计假设检验，并通过 dependence-robust p-value combination 实现多行为类型的理论化融合。

## 系统功能 vs 关键技术的区分

| 层面 | 内容 | 性质 |
|------|------|------|
| 系统功能 | Detection + Characterization 两阶段 | 工程架构设计 |
| 关键技术 | Pair Surprisal Layer (PSL) | 方法论创新 |
| 验证 | 消融实验 + FDR 校准 | 科学声明证据 |

## Background

- 当前项目是面向跨平台协同操纵的证据驱动监测系统
- 当前代码已有共享对象协同检测、加权网络、群组统计与可视化
- 综述（Mannocci 2024）将现有检测方法分为 Network Science 和 ML 两大类
- PSL 属于 Network Science → Backbone Extraction (统计显著性) 子类
- 综述明确指出该方向的核心挑战：Heterogeneity (#3)、Scalability (#6)、热门话题误报
- 这些挑战正是 PSL 的创新切入点

## 关键技术一的创新定位

### 在方法谱系中的位置

```
Network Science Methods
├── Co-action + Threshold filtering (CooRTweet) ← 我们的 baseline
├── Backbone extraction (统计显著性)
│   └── Pair Surprisal Layer ← 我们的创新
├── Multiplex network (多层融合)
│   └── Iannucci 2025 ← 潜在 baseline
└── Community discovery (Louvain/Leiden)

ML Methods
├── Unsupervised clustering (Sharma KDD 2021) ← differentiation
└── Supervised classification ← 不适合我们的约束
```

### 创新点精确表述

> 提出 Pair Surprisal Layer，一种面向协同检测的 pair-level 统计显著性评估方法。在不修改底层配对引擎的前提下，通过对称超几何检验校正 object 热度和账号活跃度，使用 Cauchy combination 在任意依赖结构下融合多行为通道证据，并在 pair level 提供 BH-FDR 形式化假阳性率保证。

### 解决的综述 Open Challenges

| Challenge | PSL 的回应 |
|-----------|-----------|
| #3 Heterogeneity (多行为类型) | 多通道 Object 提取 + Cauchy combine 统一融合 |
| #6 Scalability | 纯统计方法，无需训练，O(n·k) 复杂度 |
| Threshold filtering 误报 | 对称超几何 + BH-FDR 替代 percentile |
| 检测结果不可审计 | edge-level evidence + adjusted_p 输出 |

## Constraints

- 必须基于 `release-0.2`
- 只修改本技术线允许的路径
- 优先使用 pandas / numpy / networkx 的轻量路线
- 不把参考子仓纳入修改范围
- 不引入仓库级单一 brief 或大体量实验产物

## What I'm Looking For

### Detection 层（关键技术核心）
- Pair Surprisal Layer 实现：对称超几何 + Cauchy combine + pair-level BH-FDR
- 多通道 Object 提取：shared_asset (link/hashtag/media) + cascade (reply_to)
- Semantic Pair Adapter：冻结句向量编码器 + mutual-kNN + 经验零分布
- 证据输出：edge_channels + adjusted_p + evidence_samples

### Characterization 层（系统功能扩展）
- 基于 Detection 输出的协同群体，沿综述四个**正交维度**进行表征
- 概念锚点见 `SURVEY_DIMENSIONS.md`（Mannocci et al. 2024 原文摘录）
- 为下游 KT2（传播监控）和 KT3（报告研判）提供结构化输入

> **正交性原则（综述核心）**: Authenticity 与 Harmfulness 是两个独立维度，不能合并为单一"可疑度"。系统输出应支持 4 象限定位：
> - authentic + harmless（良性社区协同，如应急互助）
> - authentic + harmful（真人但有害，如真人水军围攻）
> - inauthentic + harmless（假号但无害，如营销刷量）
> - inauthentic + harmful（假号且有害，典型 CIB）
>
> Intent 是贯穿 Harmfulness 和 Orchestration 的隐变量，通常未知/隐藏，只能由 actions 间接推断。

#### Dim-A: Authenticity（真实性评估）
- **综述定义**: actors 在行为和整体在线存在中表现出的"真实性与透明度"程度
- **任务定义**: 评估协同群体中账号的真实性（genuine actors vs fake accounts: bots/trolls/fake personas）
- **输入**: 协同群体成员列表 + 账号行为特征（发文频率、间隔方差、作息节律熵、互动规律性）
- **输出**: 群体级 `authenticity_score` (0-1) + 成员级 `inauthenticity_signals`（automation / template / persona 倾向）
- **方法**: 行为特征 + 时序模式 → 自动化/模板化倾向评分（已有 `account_profiler.py` 基础）
- **注意**: 输出"真实性"而非"bot/human 二元标签"——综述强调本项目不做最终 bot 裁决
- **验证数据集**: TwiBot-22 (NeurIPS 2022), Cresci-2017
- **关键文献**: TwiBot-22, BotDGT (arXiv 2404.15070), UnSBot (arXiv 2404.13595), RGT (AAAI 2023)

#### Dim-B: Harmfulness（危害性评估）
- **综述定义**: 协同行为产生的负面影响/后果（线上线下），取决于 shared intent + actions + **观察者视角**
- **任务定义**: 评估协同群体传播内容的危害程度和类型
- **视角声明**: 本项目采用"网络舆论安全"观察者视角（综述指出 harmfulness 依赖视角，需显式声明）
- **输入**: 协同群体共享的内容集合 (posts, claims, shared URLs)
- **输出**: 群体级 `harm_score` + 危害类型标签 (disinformation / hate_speech / harassment / amplification)
- **方法**: 内容分析 → 毒性检测 + 叙事框架识别 + 事实核查信号
- **正交检验**: 需验证 authentic+harmful 和 inauthentic+harmless 两个非平凡象限存在（综述强调的边界案例）
- **验证数据集**: Seckin IO Labeled Dataset (26 campaigns + organic control)
- **关键文献**: Coordinated Behavior→Toxicity (arXiv 2310.01283), Framing Theory (arXiv 2402.15525), Toxicity+KG (AAAI 2024), MetaTox (arXiv 2412.15268)

#### Dim-C: Orchestration（组织度评估）
- **综述定义**: 协同 actors 之间"计划与组织"的程度，与 intent 强关联
- **任务定义**: 评估协同群体的组织化程度，分为三档（综述明确三档，非两档）
  - **centralized**: 单一 actor/entity 控制所有成员，dictating timing/content/strategy（典型: botnet + botmaster）
  - **decentralized**: 控制分布于多 actor，self-organize/autonomous，由 shared goals/ideologies 引导（典型: Reddit GameStop）
  - **non-orchestrated (emergent)**: 行为自发围绕话题/叙事汇聚，无组织（典型: 病毒式 hashtag 趋势）
- **输入**: PSL 输出的协同网络结构 + 时序互动模式
- **输出**: `orchestration_type` (centralized / decentralized / emergent) + 结构指标 (centralization, assortativity, core-periphery ratio, hub_dominance)
- **方法**: 网络结构分析 → Freeman centralization + degree assortativity + core-periphery 检测
- **理论依据**: centralized 对应 tight synchronization（高 centralization + 高 hub_dominance）；decentralized 对应自组织（低 centralization + 正 assortativity）
- **验证数据集**: IRA Dataset (centralized, state-linked), GameStop/WSB (decentralized), Seckin IO
- **关键文献**: Post-hoc Node Influence (ACM 2024), ACCD (arXiv 2601.00400), State-linked Coordination (Springer 2023), Influence Operations 7 Strategies (arXiv 2502.11827)

#### Dim-D: Time-variance（时变性评估）
- **综述定义**: 协同行为的时间特征与动态性，捕获 actions 的 types/timing/frequency/intensity 变化
- **任务定义**: 评估协同群体行为的时间演化模式，沿**两个轴**刻画（综述: 模式轴 + 时长轴）
  - **模式轴**: static（固定模式重复，如 spammer/bot）vs dynamic（不同时间点呈现不同特征，如 IO 切换 actor 类型/话题）
  - **时长轴**: long-term（state-sponsored 运营数年，渐进演化 tactics/narratives/targets）vs short-lived（一次性/可丢弃账号，短命快节奏）
- **输入**: 协同群体的时序行为序列（多窗口）
- **输出**: `temporal_archetype` (stable / bursty / adaptive / dormant) + 演化指标 (activity_entropy, burst_frequency, lifetime, adaptation_rate)
- **archetype 与综述映射**:
  - stable = static + 任意时长（固定模式）
  - bursty = dynamic + short-lived（一次性账号快节奏爆发）
  - adaptive = dynamic + long-term（长期渐进适应 tactics/narratives/targets）
  - dormant = 间歇性（长期潜伏 + 偶发爆发）
- **方法**: 时序分析 → 动态社区检测 + archetype 分类 + 活跃度变化检测
- **验证数据集**: Tardelli PNAS 2024 数据, Seckin IO Dataset
- **关键文献**: Tardelli PNAS 2024, Iannucci (arXiv 2025), EMNLP 2025 Findings, Neural TPP (arXiv 2110.15454)

### 优先级
- **P0**: PSL Detection 核心实现 + 消融验证（关键技术）
- **P1**: 多通道覆盖验证 + FDR 校准（关键技术验证）
- **P1**: Authenticity + Orchestration（已有代码基础 + 直接利用 PSL 输出）
- **P2**: Time-variance + Harmfulness（依赖数据采集和 NLP 模型选型）

## Domain Knowledge

- 事件窗口组织证据池是当前项目的默认前提
- 短期验证范围只考虑 `mock_weibo`、`weibo`、`news`
- 报告研判当前尚未实现，因此本技术线不依赖 risk 模块
- 协同检测的输出应当保持证据驱动和可解释
- Characterization 依赖 Detection 的输出类型——PSL 的 edge-level 输出使后续分析更丰富

## Non-Goals

- 不做全新 GNN 训练流水线
- 不做跨平台身份解析系统
- 不扩展更多平台
- 不重构无关前端页面
- 不在 Detection 阶段引入 LLM（统计问题不需要生成式推理）

## Existing Results

- `new-system/backend/app/core/coordination/` 已有核心算法骨架
- `new-system/backend/app/services/coordination_service.py` 已可返回网络和统计结果
- `POST /api/v1/coordination/detect` 已存在
- `coordination` 前端页已能消费当前返回结构
- PSL 方案经过 5 轮 GPT-5.4 评审收敛（8.6/10）
- 完整技术提案：`refine-logs/FINAL_PROPOSAL.md`
- 实验计划：`refine-logs/EXPERIMENT_PLAN_DETAILED.md`
- 39 篇参考文献：`LITERATURE_REFERENCES.md`
- 四维度综述原文锚点：`SURVEY_DIMENSIONS.md`

## Key References

- Mannocci et al. (2024) — CIB Detection Survey, 定位 PSL 在方法谱系中的位置
- Liu & Xie (JASA 2020) — Cauchy Combination Test, PSL 核心方法论依赖
- Seckin et al. (2024) — IO Labeled Datasets, 高优先级评估数据源
- Iannucci et al. (2025) — Temporal Multiplex, 潜在 baseline
