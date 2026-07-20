# CogGuard 项目完整设计文档：功能设计与技术选型

> 版本：2026-06-03 ｜ 基线：`release-0.2` ｜ 产品代码根：`system/`
> 用途：结题答辩 / 项目交付用的单文件总览，覆盖系统定位、闭环、三大关键技术的功能设计与技术选型、真实落地状态与差距。
> 维护规则：本文区分**已落地（代码可运行）**、**设计稿（仅文档/方案）**、**缺口（无设计无代码）**三态，不把计划当完成。

---

## 0. 一页速览

| 维度 | 内容 |
|------|------|
| 项目定位 | 面向网络舆论对抗的**跨平台协同操纵分析**证据驱动原型系统 |
| 核心闭环 | 事件 → 证据 → **协同发现(KT1)** → **传播监控(KT2)** → **报告研判(KT3)** → 处置 |
| 验证范围 | `mock_weibo`、`weibo`、`news`（跨源，非跨平台身份解析） |
| 后端 | Python 3.11 / FastAPI / SQLAlchemy(async) / Motor / Celery |
| 前端 | Vue 3 / TypeScript / Vite 6 / Ant Design Vue 4 / ECharts 6 / Pinia |
| 存储 | MySQL 8（结构化）/ MongoDB 7（原始数据）/ Redis 7（缓存+队列） |
| 关键技术 | KT1 跨平台共同行为特征复用融合检测 ｜ KT2 LLM+时序的事件规模预测 ｜ KT3 Phase-Aware Hazard + DISARM 路径预判（多 Agent 编排） |

**一句话现状**：数据采集、协同检测 MVP、传播趋势预测核心、报告研判白盒引擎均已落地可运行；三大关键技术各自的"创新增强层"（KT1 的 PSL、KT2 的真实 LLM 接入与路径预测、KT3 的 Agent/RAG 层）多为设计稿，且存在 LLM 客户端依赖缺失这一共性阻塞。

---

## 1. 系统定位与主线叙事

CogGuard 围绕"跨平台协同攻击"建立一条**可解释、可复核**的分析链路：

```
事件 ──→ 证据 ──→ 协同发现 ──→ 传播监控 ──→ 报告研判 ──→ 处置
  │                                                          │
  └──────────────────── 处置/回流 ────────────────────────────┘
```

- **功能一 · 协同发现（KT1，核心关键技术）**：用平台无关的共同行为特征发现协同群体
- **功能二 · 传播监控（KT2）**：预测事件规模与传播态势
- **功能三 · 报告研判（KT3）**：消费上游证据，做阶段预警 + 攻击路径预判 + 反制 + 结构化报告

设计原则：规则/证据优先于黑盒 LLM 裁决；LLM/Agent 作增强与呈现，不作第一阶段最终裁决；内容分析单向下沉，绝不回流作为协同判据。

---

## 2. 总体架构与技术选型

### 2.1 分层架构

```
┌─────────────────────────────────────────────────────────┐
│ 前端 (Vue 3 + TS + Ant Design Vue 4 + ECharts 6 + Pinia) │
│  登录 / 监测看板 / 数据采集 / 协同检测 / 传播监控 /        │
│  账户监测 / 报告研判                                       │
├─────────────────────────────────────────────────────────┤
│ 后端 API (FastAPI, /api/v1) — 7 路由组                    │
│  auth / dashboard / crawl / coordination /                │
│  accounts / propagation / risk                            │
├─────────────────────────────────────────────────────────┤
│ 服务层 services/ — 业务编排                                │
├─────────────────────────────────────────────────────────┤
│ 核心算法 core/ — coordination / propagation / risk /      │
│  account_profiler / crawler                               │
├─────────────────────────────────────────────────────────┤
│ 数据层  MySQL(用户/任务/研判) MongoDB(帖子/评论/原始)      │
│         Redis(缓存+Celery broker)  NetworkX(内存图)        │
├─────────────────────────────────────────────────────────┤
│ 采集层  MediaCrawler / NewsCrawler / MockCrawler          │
└─────────────────────────────────────────────────────────┘
```

### 2.2 技术选型与理由

| 层 | 选型 | 理由 |
|----|------|------|
| 后端框架 | FastAPI (Python 3.11+) | 异步高性能，与参考项目栈一致，自带 OpenAPI |
| 前端框架 | Vue 3 + TS + Vite 6 | 生态成熟，与 NewsCrawler 前端一致 |
| UI 组件 | Ant Design Vue 4 | 中后台数据分析场景组件丰富 |
| 可视化 | ECharts 6 | 协同网络力导向、传播时间线、地图、趋势图 |
| 结构化存储 | MySQL 8 | 用户、任务、研判报告等结构化数据 |
| 非结构化存储 | MongoDB 7 (Motor 异步) | 帖子、评论、爬取原始 JSONL |
| 缓存/队列 | Redis 7 | 缓存、会话、Celery broker |
| 图分析 | NetworkX（内存） | 当前阶段轻量路线，预留 Neo4j |
| 异步任务 | Celery + Redis | 采集、分析等耗时操作异步执行 |
| 鉴权 | JWT (python-jose) + bcrypt (passlib) | 标准方案，角色 admin/analyst/viewer |
| 包管理 | uv（后端）/ npm（前端） | 高效依赖管理 |

### 2.3 关键依赖现状（已核实 `pyproject.toml`）

后端**实际仅含**：fastapi / uvicorn / sqlalchemy / aiomysql / motor / redis / celery / pydantic / python-jose / passlib / alembic / loguru / **httpx** / pandas / networkx / numpy。

> ⚠️ **共性阻塞（影响三大关键技术的增强层）**：
> - **无任何 LLM 客户端库**（无 openai / dashscope / deepseek SDK）——KT2 真实事件提取、KT3 Agent 全靠未来补依赖 + httpx 直连
> - **无 scipy / statsmodels** —— KT1 的 PSL（超几何、BH-FDR）无法实现
> - **无 sentence-transformers / text2vec** —— KT1 语义通道无支撑（但新方向已决定排除内容信号，影响弱化）
> - **无 igraph / leidenalg** —— 若要 Leiden 社区发现需新增（当前用 NetworkX greedy modularity）

---

## 3. 数据采集（闭环输入）

跨平台数据接入与标准化，是整条闭环的输入。

| 子模块 | 文件 | 状态 | 说明 |
|--------|------|------|------|
| 爬虫抽象基类 | `core/crawler/base.py` | ✅ 已落地 | 统一接口 |
| Mock 爬虫 | `core/crawler/mock.py` | ✅ 已落地 | 生成含协同模式的测试数据 |
| MediaCrawler 直连 | `core/crawler/social.py` (883行) | ✅ 已落地 | 微博等社交，子进程执行 + JSONL 增量入库 |
| News 提取 | `core/crawler/news.py` | ✅ 已落地 | HTTP 或本地 ExtractorService |
| 跨平台标准化 | `core/crawler/normalizer.py` | ✅ 已落地 | media_urls/hashtags/external_links 统一 |
| 异步采集任务 | `tasks/crawl_tasks.py` | ✅ 已落地 | Celery 执行 |

API：`GET /crawl/platforms`、`POST /crawl/social`、`GET /crawl/jobs`、`GET /crawl/data`。

---

## 4. 功能一 · 协同发现（KT1）— 核心关键技术

### 4.1 功能设计

在事件窗口内识别"共同推动某叙事"的协同账号群体，输出协同边 + 证据 + 协同群组。**两阶段框架**（Mannocci 2024 综述）：

- **Detection（发现"谁在协同"）** —— KT1 核心创新所在
- **Characterization（刻画"协同群体是什么样"）** —— 四维表征：Authenticity / Orchestration / Time-variance（行为/结构型，KT1）+ Harmfulness（内容型，归 KT3）

### 4.2 关键技术与创新定位（2026-06-02 最新方向）

**跨平台协同发现：只用平台无关的"共同行为特征"做复用融合检测；内容检测不作为协同信号。**

- 立论：现有 CIB 文献依赖平台特定信号（cotweet/retweet/cofollow/time burst），多媒体平台又提专用内容信号（视频-语义 mismatch）——内容信号平台特定、易被 AI 改写、迁移成本高
- 共同行为信号：时间同步/共现、共享对象（URL/hashtag/媒体指纹 id）、共转发与回复级联、账号行为节律
- 行为 vs 内容边界判据：**是否需要"理解内容说了什么"**。共享同一媒体对象（按 id/指纹）= 行为；分析视频内容/字幕 mismatch/文本立场/毒性 = 内容（排除）
- 显著性筛查（PSL）：对称超几何 + Cauchy combination + pair-level BH-FDR，抑制热门话题"自然共振"误报

### 4.3 落地状态

| 部分 | 文件 | 状态 |
|------|------|------|
| 共享对象+时间窗配对（CooRTweet 重写） | `core/coordination_baseline/detector.py` (184行) | ✅ 已落地 |
| 加权图 + 百分位阈值 + 社区发现 | `core/coordination_baseline/network.py` (373行) | ✅ 已落地 |
| 账户/群组统计 | `core/coordination_baseline/stats.py` (142行) | ✅ 已落地 |
| PSL 显著性（超几何+Cauchy+BH-FDR） | `significance.py` | ❌ **设计稿，0 行** |
| 多行为通道抽取 | `channels.py` | ❌ **设计稿，0 行** |
| 语义通道 | `semantic.py` | ❌ 设计稿（且新方向倾向排除） |

API：`POST /coordination/detect`。

### 4.4 答辩风险（须知）

- 创新主张"行为优先/平台无关"已被 Schneider/Rizoiu *Beyond Content*(arXiv 2602.02838)、Luceri *CIB on TikTok*(2505.10867) 做出 → **不能当原创首发**，唯一可辩护 delta 是 PSL 统计框架，但 0 行代码
- "跨平台"仅验证 mock_weibo/weibo/news（跨源非跨平台身份），须改口径
- 排除内容信号在单平台上是 tradeoff（可能略损召回），不是纯增益

---

## 5. 功能二 · 传播监控（KT2）

### 5.1 功能设计

预测事件规模与传播态势，功能层借鉴"知微"(Zhiwei) 传播分析产品的**呈现形态**（可视化/功能形态，非创新来源）。

> **职责边界（2026-06-03 厘清）**：KT2 **只做传播动力学**（规模/形态/路径预测），**不做内容分析**。立场检测、危害性评估等内容理解任务**已全部移交 KT3 的 Characterization 层**，KT2 不再承载，以消除与 KT3 的职责重叠。

子功能：

- **分层传播预测**（关键技术）：宏观规模 + 中观路径形态 + 微观下一跳，三层共用同一事件/体制后验
- 传播态势刻画：子图、时间线、起爆/桥接/扩散关键角色（子功能，已落地）
- 源头追溯与证据链、关键路径**回溯**（子功能，已落地；注意是事后回溯，非预测）
- ~~立场检测 / 危害性评估~~ → **移交 KT3**（见 §6.1）

### 5.2 关键技术：事件条件下的分层传播预测框架

核心主线：用 LLM 把帖子内容抽成**外生事件**，驱动透明的**体制后验 p(z|events,history)**，并以该后验**同时条件化**三个尺度的传播预测。区别于知微（仅事后分析、无预测）与现有级联模型（仅用观测序列、无外生事件条件）。

```
LLM 事件抽取 ──→ 体制后验 p(z|events,history)   ← CascadeSwitch 核心，已落地
                      │
        ┌─────────────┼──────────────────────────┐
        ▼             ▼                           ▼
   Tier-0 宏观     Tier-1 中观                Tier-2 微观
   规模预测 ŷ      路径形态预测               下一跳预测
   (标量,已落地)   P(中心化/去中心化/          P(下一激活节点 v |
                  跨群桥接 | z,events)          序列, 条件于 p(z))
   零训练白盒      零训练白盒(新增)            训练式(新增)
```

- **Tier-0 规模预测（CascadeSwitch，已落地）**：4 体制（seeding/amplification/peak/decay）softmax 后验混合预测，零训练、可解释、带置信区间
- **Tier-1 路径形态预测（新增，零训练）**：每个体制配结构先验（seeding→去中心化散播 / amplification→中心化枢纽 / coordinated_burst→跨群桥接），复用 W 矩阵后验，与规模预测同源
- **Tier-2 微观下一跳预测（新增，训练式）**：将体制后验 p(z) 作为条件输入喂给下一跳预测器 = **event/regime-conditioned next-node prediction**。真 delta：现有微观扩散模型（Topo-LSTM/NDM/FOREST）**均无外生事件条件**，本框架在体制转换点更准（用"有/无事件条件"消融证明）

### 5.3 落地状态

| 部分 | 文件 | 状态 |
|------|------|------|
| 时序特征 (WP1) | `core/propagation/ts_features.py` (107) | ✅ 已落地 |
| LLM 事件上下文 (WP2) | `core/propagation/llm_context.py` (162) | ✅ 已落地 |
| Tier-0 体制模型+预测器 (WP3) | `regime_model.py`(224)+`trend_predictor.py`(180) | ✅ 已落地 |
| 源头追溯/证据链/路径回溯 | `core/propagation_legacy.py` (585) | ✅ 已落地（子功能） |
| Tier-1 路径形态预测 | `structure_predictor.py` | 🔲 新增（零训练，推荐先做） |
| Tier-2 微观下一跳预测 | （待定） | 🔲 新增（训练式，需边级真值数据） |
| ~~立场检测 / 危害性评估~~ | — | ➡️ **移交 KT3** |

API：`GET /propagation/analyze`、`POST /propagation/predict-trend`。

### 5.4 关键技术陈述（答辩口径）

> KT2 提出**事件条件下的分层传播预测框架**：用 LLM 把帖子内容抽成外生事件，驱动透明的体制后验 p(z)，并以该后验同时条件化宏观规模、中观形态、微观下一跳预测。区别于商业产品（知微，仅事后分析无预测）与现有级联模型（仅用观测序列、无外生事件条件）。

### 5.5 落地路径与风险（诚实）

| 层 | 状态 | 需要做 | 数据 | 难度 |
|----|------|--------|------|------|
| Tier-0 规模 | ✅ 已落地 | 接通真实 LLM（关掉 mock_llm） | DeepHawkes/CasFlow | 低 |
| Tier-1 形态 | 🔲 新增 | 体制→结构先验映射 + 形态分类 | 复用现有图特征 | 中，零训练，**推荐先做** |
| Tier-2 微观 | 🔲 新增 | regime-conditioned 下一跳模型 + 训练 | Twitter15/16/FOREST 边级真值 | 高，需 GPU+消融 |

- **前置阻塞**：`propagation_service.py` 现 `mock_llm=True`，需接通真实 LLM，否则"事件条件"在 demo 不生效；后端无 LLM 客户端依赖、Tier-2 还需深度学习框架，须先补 `pyproject.toml`
- **Tier-2 最大不确定性**：依赖边级真值数据，真实采集为部分观测，数据条件可能不足；必须跑出"有/无事件条件"消融数字，否则沦为纸面创新
- **推进顺序**：先补依赖+接通 LLM → 先落 Tier-1（低风险实物）→ 再上 Tier-2（留足消融实验时间）

---

## 6. 功能三 · 报告研判（KT3）

### 6.1 功能设计（三段）

针对"用 Agent 做报告研判创新性弱"的评审意见，报告研判设计为：
**(a) 基于 Agent 的证据编排（用户言论/行为检测）→ (b) 基于 RAG 的报告生成 → (c) Agent 解释总结协同攻击**。

回答三个问题：当前风险多高（信念区间）/ 接下来会发生什么（阶段+下一步技术预测）/ 应该如何应对（反制建议）。

### 6.2 关键技术：白盒前瞻引擎（头号创新）+ 多 Agent 编排（呈现层）

> **表述纪律**：头号创新必须是已落地的白盒算法，Agent/RAG 仅作编排基座与呈现层，**不作创新卖点**。核心叙事：从 detection 升级到 anticipation + countermeasure。

- **Phase-Aware Hazard**：5 状态战役生命周期 + logistic hazard 预测阶段转换/breakout 预警
- **DISARM Attack-Path**：技术转换图路径推理 + 预测下一步技术 + 反制建议（非 flat tagging）
- **Contradiction-Aware D-S Fusion**：信念区间 + 冲突检测 + 阶段调制质量

### 6.3 落地状态

| 层 | 文件 | 状态 |
|----|------|------|
| Layer 1 证据构建 | `core/review/evidence_builder.py` (244) | ✅ 已落地 |
| Layer 1 阶段检测 | `core/review/phase_detector.py` (169) | ✅ 已落地 |
| Layer 1 D-S 融合 | `core/review/ds_fusion.py` (234) | ✅ 已落地 |
| Layer 1 DISARM 路径 | `core/review/disarm_scorer.py` (381) | ✅ 已落地 |
| Layer 1 报告生成 | `core/review/report_builder.py` (278) | ✅ 已落地 |
| LLM 桥接 | `core/review/llm_bridge.py` (~30) | ⚠️ 占位，return None |
| Layer 2 RAG 报告 | — | ❌ 设计稿 |
| Layer 3 恶意言论/立场/反制叙事 Agent | — | ❌ 设计稿 |

API：`POST /risk/assess`、`GET /risk/reports`、`GET /risk/reports/{report_id}`。

### 6.4 答辩风险

- 把研判扩成"更多 Agent+RAG"**没解决反而加重**"Agent 创新性弱"批评，且撞 Agentic DISARM(arXiv 2601.15109)、Gautam 多 agent 生命周期(2505.17511)
- 翻盘成本低（几乎只动表述）：主秀已落地的白盒引擎，Agent/RAG 降级
- DISARM"预测下一步技术"范式源自 ATT&CK 域（MITRE TIE），delta 须收窄为"跨域迁移+阶段条件化"，不称首创

---

## 7. 横向支撑模块

| 模块 | 文件 | 状态 | 说明 |
|------|------|------|------|
| 账户监测 | `core/account_profiler.py` (163) | ✅ 已落地 | 行为画像 + 自动化倾向评分（0-100），供 KT1/KT3 取证 |
| 身份认证 | `core/security.py` + `services/auth_service.py` | ✅ 已落地 | JWT + bcrypt，角色 admin/analyst/viewer |
| 监测看板 | `services/dashboard_service.py` + `api/v1/dashboard.py` | 🔧 开发中 | 聚合 MongoDB 事件数据 + ECharts 地图，热点排行/趋势图待补 |
| 预警中心 | — | ❌ 未启动 | 规则配置、事件/群体/claim 级告警 |
| 报告中心 | — | ❌ 未启动 | 报告列表/导出/案例归档 |

API：`GET /accounts/profiles`、`GET /accounts/detail/{id}`、`GET /dashboard/overview`、`/auth/*`。

---

## 8. API 总览（实际挂载的 7 路由组）

| 路由组 | 端点 | 鉴权 |
|--------|------|------|
| auth | `/auth/register` `/login` `/refresh` `/profile` | 部分 |
| dashboard | `GET /dashboard/overview` | 是 |
| crawl | `GET /crawl/platforms` `POST /crawl/social` `GET /crawl/jobs` `GET /crawl/data` | 部分 |
| coordination | `POST /coordination/detect` | 是 |
| accounts | `GET /accounts/profiles` `GET /accounts/detail/{id}` | 是 |
| propagation | `GET /propagation/analyze` `POST /propagation/predict-trend` | 是 |
| risk | `POST /risk/assess` `GET /risk/reports` `GET /risk/reports/{id}` | 是 |
| system | `GET /health` | 否 |

> 注：路由 tag 显示名称（如"传播归因""风险研判"）为代码内字符串，文档命名已统一为"传播监控""报告研判"，代码 tag 同步属代码改动，未在文档统一范围内。

---

## 9. 整体落地差距与跨模块分工

### 9.1 三态总结

**已落地可运行**：数据采集全链路、协同检测 MVP（CooRTweet 重写+图+社区发现）、传播趋势预测核心（CascadeSwitch WP1-3）、报告研判白盒引擎（Layer 1 约 1340 行）、账户画像、认证、看板雏形。

**设计稿（有方案无代码）**：KT1 的 PSL/多通道、KT3 的 Agent 编排/RAG 报告/Layer 3 Agent、KT2 的立场/危害子功能。

**缺口（无设计无代码）**：KT2 传播路径预测（未来结构）、预警中心、报告中心、评估脚本与公开数据集基准。

### 9.2 三条共性阻塞

1. **LLM 客户端依赖缺失** —— `pyproject.toml` 无任何 LLM SDK。阻塞 KT2 真实事件提取（现 `mock_llm=True`）+ KT3 Agent 层。需先定 DeepSeek 接入并补依赖。
2. **统计/算法依赖缺失** —— 无 scipy/statsmodels，阻塞 KT1 PSL 落地。
3. **无评估闭环** —— 三模块均无基准数值，"超越 SOTA"类宣称暂无实证。

### 9.3 跨模块分工（内容分析归属，闭环最大裂缝的统一口径）

> 答辩最致命一题是"内容分析归谁"。统一口径如下，三模块表述必须一致：

- **内容分析（立场/危害/有害言论）唯一归宿 = KT3 的 Characterization**
- **KT1 纯行为**：刻意的鲁棒性设计，排除内容信号（承认单平台可能略损召回，换取跨平台可迁移与抗 AI 改写）
- **KT2 只做传播动力学**：规模/体制预测，不碰内容分类
- **内容信号单向流动**：从下游消费，绝不回流作为协同判定依据
- 加分项：KT2 预测"传播会涨多大"、KT3 预测"攻击者下一步用什么手法"，两套预测互补不冲突

### 9.4 闭环数据流（服务层接缝）

```
crawl → MongoDB(raw_posts/comments)
  → coordination_service.detect ─┐
  → propagation_service.analyze ─┼─→ risk_service.assess_risk
  → account_service.profiles ────┘    (evidence_builder → phase_detector
                                        → ds_fusion → disarm_scorer → report_builder)
```
真实接缝见 `services/risk_service.py` 的 `assess_risk()`：依次调协同/传播/账户三 service，汇聚证据包后串起阶段检测→融合→DISARM→报告。

---

## 10. 参考与延伸

- 各技术线方向背景：`doc/research/key-technology-background/{coordination-detection,propagation-analysis,risk-disarm,overview}.md`
- 工程进度：`doc/engineering/development-roadmap.md`、`development-log.md`
- 答辩风险与文献核验：`tmp/defense-review/{kt1,kt2,kt3}-findings.md`、`examiner-review.md`、`novelty-validation.md`
- 关键撞车文献：Beyond Content(2602.02838)、CIB on TikTok(2505.10867)、CasFT(2409.16619)、AutoCas(2502.18040)、Agentic DISARM(2601.15109)、Multi-agent Misinformation Lifecycle(2505.17511)
