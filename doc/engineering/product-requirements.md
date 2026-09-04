# CogGuard 产品需求文档（PRD）

> **Historical / Non-normative**：这是早期产品提案，保留用于追溯。当前实现以 `system/README.md`、`system-governance.md`、`CONTEXT.md` 和 `UBIQUITOUS_LANGUAGE.md` 为准；本文不得作为产品 runtime 输入。

> **用途**：定义产品目标、用户场景、页面信息架构、API/数据模型与验收口径。  
> **受众**：系统开发者、产品/竞赛答辩准备者、AI 开发工具。  
> **维护规则**：只记录产品和工程契约；研究论证、文献依据和关键技术探索放入 `../research/` 并在本文中引用。

| 项目 | 内容 |
|------|------|
| **文档版本** | 1.0 |
| **日期** | 2026-04-29 |
| **代码基线** | release-0.2 |
| **受众** | 开发者 + AI 开发工具（Claude / Codex） |
| **项目全称** | 面向网络舆论对抗的跨平台协同攻击监测系统（CogGuard） |

> **AI 工具使用提示**：本文档约 2960 行，建议使用 offset/limit 分段读取。下方章节索引标注了各章节的行号范围。

## 章节索引

| 章节 | 行号范围 | 摘要 |
|------|----------|------|
| **第 1 章 产品概述** | L30-L135 | 产品定位、三大功能闭环、技术栈、ARIS 边界声明、术语表 |
| **第 2 章 用户场景与用户故事** | L136-L395 | 3 种角色定义、7 个核心场景（S1-S7）、20 条 User Story 汇总表 |
| **第 3 章 页面信息架构与交互流程** | L397-L1035 | 8 个页面详细设计、页面跳转关系图、全局交互流程 |
| **第 4 章 功能编排与优先级** | L1038-L1497 | 数据流转关系、触发条件矩阵、3 大功能子功能清单、P0-P3 分期规划 |
| **第 5 章 技术接口与数据模型** | L1500-L2727 | API 规范、26 个端点定义、MySQL/MongoDB/Redis 模型、ARIS I/O 接口 |
| **附录 A 代码文件清单** | L2729-L2795 | 65 个文件的状态清单 |
| **附录 B DISARM 映射表** | L2796-L2869 | 12 项技术、18 条路径、11 条反制措施 |
| **附录 C 风险等级与阶段** | L2870-EOF | 4 级风险、5 阶段生命周期、D-S 融合维度 |

---

## 第 1 章 产品概述

> **本章摘要**：本章定义 CogGuard 的产品定位、三大功能闭环、技术栈选型以及关键技术边界。读者可通过本章快速理解系统"做什么、怎么做、哪些算法待实现"。

### 1.1 产品定位与目标

CogGuard 面向网络舆论对抗场景，以 **跨平台协同攻击行为** 为核心监测对象，围绕"协同发现 - 传播监控 - 报告研判"形成三阶段分析闭环。

**核心问题对象**：跨平台协同操纵网络——研究对象从单账号/账号群体转为跨平台协同操纵网络，主流程从账号分类转为证据驱动的发现、归因与报告研判闭环。

**产品目标**：

1. 提供事件驱动、对象驱动、混合驱动三种监测任务模式，覆盖热点话题追踪与可疑账号监控。
2. 通过三大功能闭环，输出事件、群体、路径、claim、thread 多层风险与证据链。
3. 生成可审计的攻击分析报告，包含 DISARM 战术映射与处置建议，支撑人机复核决策。

<!-- 定位来源：project-positioning-baseline.md §1.2-1.3 -->

### 1.2 三大功能闭环

系统的三大主要功能构成闭环，每个功能独立提供价值，同时为下游功能提供输入：

```
+----------------+       +----------------+       +----------------+
| | | | | |
|   协同发现     +------>+   传播监控     +------>+   报告研判 |
|  Coordination | |  Propagation | |     Risk |
|   Discovery | |   Monitoring | |   Assessment |
| | | | | |
+-------+--------+       +----------------+       +--------+-------+
 | |
 |            反馈：案例入库 / 规则更新 |
        +<-------------------------------------------------+
```

**功能一：协同发现** — 发现跨平台协同行为，并对协同行为进行分类。

| 子功能 | 说明 |
|--------|------|
| 协同行为检测 | 判定是否存在协同（coordinated vs organic） |
| 协同类型分类 | 识别协同类型（astroturfing / brigading / amplification 等） |
| 协同群组发现 | 定位构成协同群体的账号集合 |
| 证据边提取 | 提取协同行为的证据链（五类边：时间同步、共链接、共媒体、语义近似、传播互动） |

**功能二：传播监控** — 对传播源头、范围和趋势进行监控与预测。

| 子功能 | 说明 |
|--------|------|
| 趋势预测 | 预测传播量/范围/速度的未来走势（关键技术） |
| 用户画像 | 角色识别：起爆/桥接/扩散/伪装意见领袖 |
| 立场检测 | 支持/反对/中立/讽刺 |
| 危害性评估 | 内容危害程度评分 |
| 源头追溯 | 传播起点定位 |
| 范围估计 | 传播覆盖面评估 |

**功能三：报告研判** — 针对攻击进行分析并生成报告，显式利用前两个功能所生成的结果。

| 子功能 | 说明 |
|--------|------|
| 攻击分析 | 基于多源证据的深度分析（关键技术） |
| 报告生成 | 结构化攻击分析报告（JSON + 自然语言） |
| DISARM 映射 | 战术/技术标准化表达 |
| 处置建议 | 基于分析结果的行动建议 |
| 预警 | 事件级/群体级/claim 级风险告警 |

### 1.3 技术栈概览

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| **后端框架** | FastAPI (Python 3.11+) | 异步 API 服务，SQLAlchemy 2.0 ORM |
| **前端框架** | Vue 3 + TypeScript | 组合式 API（`<script setup>`） |
| **UI 组件库** | Ant Design Vue 4 | 企业级 UI 组件 |
| **关系数据库** | MySQL 8.0 | 用户、任务、报告等结构化数据 |
| **文档数据库** | MongoDB | 采集帖子、评论等非结构化数据 |
| **缓存/消息** | Redis | 会话缓存、Celery Broker |
| **任务队列** | Celery | 异步采集任务、后台分析任务 |
| **图计算** | NetworkX + strict Leiden runtime | Evidence Graph construction, propagation analysis, and community partitioning |
| **构建工具** | Vite | 前端开发与构建 |
| **HTTP 客户端** | Axios | 前端 API 调用 |

<!-- 技术栈来源：代码基线 release-0.2 实际依赖 -->

### 1.4 Core capability boundaries

> Research packages define implementation-specific details. This product document records the stable interfaces and claimability boundaries.

本系统包含三个核心能力，每项对应一个产品闭环。当前 PRD 只定义输入/输出接口和状态，不把未激活的研究制品描述为生产模型：

| Capability | Product area | Current status | I/O interface |
|---|----------|----------|-----------|-------------|
| Coordination Discover / Detect | 协同发现 | artifact-first + fallback | 输入：EventSnapshot / Evidence Graph → 输出：communities、learned/evidence edges、validation metadata |
| Propagation Analysis | 传播分析与预测 | observed analysis + checkpoint inference + abstain | 输入：EventSnapshot → 输出：传播证据、规模趋势、实名下一跳排序和覆盖审计 |
| Risk Review | 报告研判 | Student/Teacher + governance | 输入：内容、协同和传播证据 → 输出：Review Verdict；Canonical Verdict 需人工审批 |

**边界原则**：
- 核心能力是从功能中提炼出的稳定接口，不等同于已完成的研究主张
- 其它支撑性技术（图分析、角色识别、立场分类等）后期根据实现需要动态调整
- Agent 与 DISARM 是支撑层，不是三项关键技术本体

<!-- 边界来源：project-positioning-baseline.md §4 -->

### 1.5 术语表

| 术语 | 英文 | 定义 |
|------|------|------|
| 协同发现 | Coordination Discover | Platform-generic evidence graph discovery and coordination communities |
| 传播监控 | Propagation Analysis | Source, reach, and trend analysis over event snapshots |
| 报告研判 | Risk Review | Auditable review outputs and governance actions |
| DISARM | DISARM Framework | 信息操纵对抗的标准化战术/技术框架，用于攻击行为的结构化表达与反制映射 |
| D-S 融合 | Dempster-Shafer Fusion | 基于 Dempster-Shafer 证据理论的多维风险融合方法，输出信念区间与冲突度 |
| CascadeSwitch | Legacy propagation scaffold | 历史速度/加速度体制切换脚手架；不得作为当前公开事件预测模型 |
| 协同边 | Coordination Edge | 两个账号之间的协同行为证据，包含五类：时间同步、共链接、共媒体、语义近似、传播互动 |
| 协同群组 | Coordination Group | 通过社区发现算法识别的协同行为账号集合 |
| ARIS | Algorithm Research & Implementation Stub | 标记算法核心待研究实现的模块，PRD 仅定义 I/O 接口 |
| Event | Event | 事件单元，不同平台上的同一事件聚合到同一事件簇 |
| Claim | Claim | 断言单元，同一口径/断言/素材模板聚成的 claim 簇 |
| Thread | Thread | 讨论线程，围绕同一话题的帖子-评论-转发链 |
| 起爆节点 | Originator | 传播链中最早发布内容的账号 |
| 桥接节点 | Bridge | 连接不同群体的高介数中心性账号 |
| 扩散节点 | Amplifier | 被大量跟随传播的高入度账号 |

---

## 第 2 章 用户场景与用户故事

> **本章摘要**：本章定义系统的三类用户角色及其权限边界，描述七个核心使用场景的完整操作流程，并将每个场景拆解为可验收的用户故事。所有场景基于当前代码基线（release-0.2）的页面路由和 API 接口设计。

### 2.1 用户角色定义

系统支持三种用户角色，定义于 `backend/app/models/user.py` 的 `User.role` 字段（`String(16)`，默认值 `analyst`）：

| 角色 | 英文标识 | 权限范围 | 典型用户 |
|------|----------|----------|----------|
| **管理员** | `admin` | 管理所有用户和系统配置；拥有所有 analyst 权限 | 系统管理员、项目负责人 |
| **分析人员** | `analyst` | 创建监测任务、执行数据采集、运行检测分析、查看数据、生成报告（**主要角色**） | 安全分析师、舆情研究员 |
| **只读用户** | `viewer` | 只读查看监测看板和已生成的报告 | 领导层、外部审阅者 |

<!-- 角色来源：backend/app/models/user.py 文件头注释 -->

### 2.2 场景 S1：新建监测任务与数据采集

**背景**：分析人员发现某热点事件可能存在跨平台协同操纵，需要创建采集任务获取原始数据。

**前置条件**：
- 用户已登录，角色为 analyst 或 admin
- 系统已配置至少一个可用采集平台

**操作步骤**：
1. 进入「数据采集」页面（路由 `/crawl`）
2. 在"创建采集任务"表单中选择目标平台（mock_weibo / weibo / douyin / xhs / news）
3. 输入监测关键词（逗号分隔）；新闻平台可在"链接"字段填写文章 URL
4. 设置最大帖子数（1-1000，默认 50）
5. 展开「高级设置」，可直接配置 Social Runtime 支持的采集能力（如登录方式、评论/二级评论开关、单帖评论上限、代理、时间/排序等平台支持参数）
6. 点击「开始采集」按钮，系统创建 Celery 异步任务
7. 在"采集任务列表"中查看任务状态（pending → running → done/failed）
8. 任务完成后，在"采集数据"表格中浏览已采集的帖子/评论数据
9. 如需取消运行中的任务，点击「取消」；如需删除任务及其数据，点击「删除」

**预期结果**：
- 采集任务创建成功，状态流转正常
- 帖子数据存入 MongoDB，可在采集数据表格中分页浏览
- 数据包含：平台、作者、内容、发布时间、互动指标、媒体 URL、作者画像、IP 属地等字段
- 链接输入区应适配长 URL 批量粘贴，链接框宽度优先占满表单剩余空间，并与「开始采集」按钮保持足够垂直间距

**涉及页面**：数据采集（`/crawl`）
**涉及 API**：`POST /api/v1/crawl/social`、`GET /api/v1/crawl/jobs`、`GET /api/v1/crawl/data`、`DELETE /api/v1/crawl/jobs/{job_id}`、`POST /api/v1/crawl/jobs/{job_id}/cancel`

### 2.3 场景 S2：协同行为检测与群组发现

**背景**：数据采集完成后，分析人员需要检测采集数据中是否存在协同行为，并发现协同群组。

**前置条件**：
- 用户已登录，角色为 analyst 或 admin
- MongoDB 中已有采集数据（至少执行过一次 S1）

**操作步骤**：
1. 进入「协同检测」页面（路由 `/coordination`）
2. 配置检测参数：
   - 时间窗口（1-3600 秒，默认 60）：同一共享对象下的时间同步阈值
   - 最低参与次数（默认 2）：账户最低协调参与次数
   - 边权百分位阈值（0-1，默认 0.5）：过滤偶然共振的边权分位数
   - 可选限定平台
3. 点击「运行检测」，系统先清洗事件数据，按事件时间顺序进行分平台聚合，再进行跨平台聚合
4. 系统调用 Coordination Discover / Detect，输出 Coordination Community、证据边和可审计的模型状态
5. 查看概览统计：分析帖子数、协调配对数、协调账户数、群体数量
6. 在"协同网络"可视化区域查看协同网络图（Canvas 力导向布局）
7. 在"协调账户排名"表格中查看各账户的连接数、平均边权、平均时间差、对称性等指标
8. 在"高频共享对象"表格中查看被协调分享的 URL/标签

**预期结果**：
- 系统输出协同/非协同判定结果，标识协调账户与群组
- 支持分平台聚合与跨平台聚合两种视角，并可查看用户聚类结果
- 协同网络图直观展示账户间的协调关系
- 账户排名表按连接数/边权排序，高危账户一目了然

**涉及页面**：协同检测（`/coordination`）
**涉及 API**：`POST /api/v1/coordination/detect`


**研究任务边界**：工程页面沿用“协同检测”命名，但 Coordination Discover / Detect 研究流程分为 Discover 和 Detect。Discover 是无标签协同社区发现，输出社区、协同边和证据对象；Detect 是有标签协同区分，使用 Discover 输出作为特征判断账号/社区是否属于 IO driver、coordinated attacker 或 organic user。Discover 的 Leiden 社区结果不能直接当作攻击标签，只能作为 Detect 的结构化输入。

**Coordination Discover / Detect 后端口径更新**：Discover 采用 MAGNN/Leiden 输出可审计社区；Detect 的论文主后端为 `gfm_lm_gnn`，参考 IOHunter/SocGFM 的 LM+GNN/GFM 检测范式，融合 Discover embedding、社区特征、LM/TF-IDF 语义特征和 Discover 重加权多关系图。工程接口仍可保留 `classifier`、`relation_gnn`、`fusion_gnn` 作为基线或降级路径。

### 2.4 场景 S3：传播路径分析与趋势预测

**背景**：发现协同行为后，分析人员需要追溯信息传播路径，识别关键传播角色，并预测传播趋势。

**前置条件**：
- 用户已登录，角色为 analyst 或 admin
- MongoDB 中已有采集数据

**操作步骤**：
1. 进入「传播监控」页面（路由 `/propagation`，原「传播归因」命名逐步替换）
2. 点击「运行传播分析」按钮
3. 系统基于共享对象的时序关系构建传播子图，识别三类关键角色：
   - 起爆节点（最早发布者，按出度排序）
   - 桥接节点（连接不同群体，按介数中心性排序）
   - 扩散节点（被大量跟随传播，按入度排序）
4. 查看"关键角色"三栏卡片，了解各角色的核心指标
5. 检测相关发帖用户，识别高影响力节点、桥接节点和异常放大账号
6. 在"高频共享对象"表格中查看传播最广的 URL/标签及其分享次数、涉及账户数
7. 在"传播时间线"中按时间顺序查看帖子发布序列，协调账户以红色标记
8. 在“模型预测”页签设置带时区的观测截止时间和预测范围，运行 Twitter 序列联合模型，查看未来累计规模趋势和可追溯的下一跳再激活用户

**预期结果**：
- 传播子图构建完成，关键角色识别准确
- 能识别相关发帖用户和高影响力传播节点
- 时间线清晰展示传播序列与协调账户标记
- 模型可用时输出观测规模、预测规模、单调趋势曲线和实名 Top-K；模型或数据不可用时 abstain，不生成规则替代结果

**涉及页面**：传播监控（`/propagation`）
**涉及 API**：`GET /api/v1/propagation/analyze`、`POST /api/v1/propagation/model-event-predict`

### 2.5 场景 S4：风险评估与攻击分析报告

**背景**：协同发现与传播分析完成后，分析人员需要对事件进行综合风险评估，生成可审计的攻击分析报告。

**前置条件**：
- 用户已登录，角色为 analyst 或 admin
- MongoDB 中已有采集数据（风险评估会内部调用协同检测）

**操作步骤**：
1. 进入「报告研判」页面（路由 `/risk`）
2. 配置评估参数：
   - 平台筛选（可选）
   - 时间窗口（1-3600 秒，默认 60）
   - 最低参与次数（默认 2）
   - 边权百分位阈值（0-1，默认 0.5）
3. 点击「运行评估」，系统执行三阶段评估流程：
   - 阶段感知危险模型检测
   - Dempster-Shafer 证据融合（多维风险合成）
   - DISARM 攻击路径分析
4. 查看概览卡片：综合风险分、风险等级、当前阶段、证据冲突度、攻击路径分、检测技术数
5. 查看"三维评分（D-S 信念区间）"表格，了解各维度的信念值与不确定性
6. 查看"观测到的 DISARM 技术"表格，了解已识别的攻击战术/技术
7. 查看"预测下一步 & 反制建议"，了解系统预测的攻击者下一步行动及对应反制措施
8. 查看"风险因子"与"处置建议"，获取分优先级的行动建议
9. 在"历史报告"表格中查看和检索历史评估记录

**预期结果**：
- 输出综合风险评分（0-100）与风险等级（low / medium / high / critical）
- D-S 融合输出各维度信念区间与冲突度
- DISARM 映射输出观测到的攻击技术、预测下一步、反制建议
- 报告持久化存储，可通过历史报告列表回溯查看

**涉及页面**：报告研判（`/risk`）
**涉及 API**：`POST /api/v1/risk/assess`、`GET /api/v1/risk/reports`、`GET /api/v1/risk/reports/{report_id}`

### 2.6 场景 S5：监测看板与全局态势感知

**背景**：管理员或分析人员需要快速了解系统整体运行状态和风险态势。

**前置条件**：
- 用户已登录，任意角色均可访问

**操作步骤**：
1. 登录后自动进入「监测看板」页面（路由 `/`，即 Dashboard）
2. 查看四项核心指标统计卡片：
   - 监测任务数（已创建的采集任务总数）
   - 采集数据量（已采集的帖子/评论总条数）
   - 风险预警数（触发的风险告警总数）
   - 协同群体数（已发现的协同群组总数）
3. 查看真实数据驱动的可视化区域：
   - 世界地图：按事件位置着色并标注事件点
   - 事件定位：根据事件关键词下第一条发帖者的 IP 属地定位，例如“特朗普访华”可定位到第一发帖者“新华日报”的 IP 北京
   - 平台数据分布表：展示 weibo/xhs/douyin 的 posts/comments 覆盖
   - 最近发帖样本：按时间展示最早事件帖子

**预期结果**：
- 统计卡片实时反映系统数据状态
- 地图能够显示事件位置、第一发帖者、IP 属地、平台和数据规模
- 数据加载失败时显示结构化诊断，不使用假数据冒充真实数据

**涉及页面**：监测看板（`/`）
**涉及 API**：`GET /api/v1/dashboard/overview?event_id=trump_visit_2026_05_21`

### 2.7 场景 S6：账户画像深度分析

**背景**：分析人员需要对采集数据中的账户进行行为画像分析，识别高自动化倾向的可疑账户，为协同发现和传播监控提供先验支撑。

**前置条件**：
- 用户已登录，角色为 analyst 或 admin
- MongoDB 中已有采集数据

**操作步骤**：
1. 进入「账户监测」页面（路由 `/accounts`）
2. 页面自动加载所有已采集账户的行为画像数据
3. 查看概览统计：总账户数、高危账户数（≥60 分）、可疑账户数（30-59 分）、正常账户数（<30 分）
4. 在"账户行为画像"表格中查看每个账户的详细指标：
   - 账户 ID 与昵称
   - 帖子数
   - 自动化倾向评分（0-100，进度条可视化）
   - 发文规律性
   - 活跃时段与峰值小时
   - 最短发文间隔（秒）
   - 总点赞数
5. 按自动化评分降序排列，快速定位高危账户
6. 点击「刷新」按钮可手动重新加载最新数据
7. 【待开发】点击账户 ID 进入详情页，查看 24h 活跃分布、行为模板化分析、历史参与模式
8. 【待开发】支持输入单个用户主页链接/用户 ID，调用采集器收集该用户主页内容
9. 【待开发】账户详情页不仅展示数值特征，还应展示用户主页、主页元数据和该用户发布的全部内容检测结果

**预期结果**：
- 每个账户输出 0-100 的自动化倾向评分
- 高危账户（≥60 分）以红色标记，可疑账户（30-59 分）以黄色标记
- 表格支持排序和分页，便于批量筛查
- 单用户主页采集完成后，可查看主页内容、历史发帖列表、内容风险/立场/模板化检测结果

**涉及页面**：账户监测（`/accounts`）
**涉及 API**：`GET /api/v1/accounts/profiles`、`GET /api/v1/accounts/detail/{account_id}`

### 2.8 场景 S7：预警响应与处置跟踪

**背景**：系统检测到高风险事件后触发预警，分析人员需要响应预警、查看详情并跟踪处置进度。

**前置条件**：
- 用户已登录，角色为 analyst 或 admin
- 系统已产生风险评估报告（至少执行过一次 S4）

**操作步骤**：
1. 【待开发】在监测看板或通知中心收到风险预警通知
2. 点击预警条目，跳转至对应的风险报告详情
3. 查看报告中的风险等级、攻击阶段、DISARM 技术映射
4. 查看处置建议列表（按优先级排序：high / medium / low）
5. 【待开发】对每条建议执行"确认处置"或"标记忽略"操作
6. 【待开发】填写处置备注，记录实际采取的行动
7. 【待开发】系统将处置结果回写案例库，供后续相似案例检索
8. 【待开发】在历史报告中筛选特定风险等级/阶段的报告进行复盘

**预期结果**：
- 预警通知及时送达，包含风险等级与事件摘要
- 处置建议可操作、可追踪
- 【待开发】案例入库后可被 RAG 检索，增强后续分析能力

**涉及页面**：报告研判（`/risk`）、监测看板（`/`）
**涉及 API**：`GET /api/v1/risk/reports`、`GET /api/v1/risk/reports/{report_id}`、【待开发】`POST /api/v1/risk/reports/{report_id}/dispose`

### 2.9 用户故事汇总表

以下汇总表将七个核心场景拆解为可验收的用户故事，格式为"作为 [角色]，我希望 [操作]，以便 [价值]"。

| ID | 角色 | 用户故事 | 验收标准 | 优先级 | 关联页面 |
|----|------|----------|----------|--------|----------|
| US-101 | analyst | 作为分析人员，我希望选择平台并输入关键词创建采集任务，以便获取目标事件的跨平台原始数据 | 任务创建后状态为 pending/running；完成后数据可在采集数据表中查询 | P0 | `/crawl` |
| US-102 | analyst | 作为分析人员，我希望查看采集任务列表和状态，以便掌握各任务的执行进度 | 任务列表分页展示，状态实时更新（pending/running/done/failed） | P0 | `/crawl` |
| US-103 | analyst | 作为分析人员，我希望取消或删除采集任务，以便管理无效或错误的任务 | 取消后任务状态变为 cancelled；删除后任务及关联数据被清除 | P1 | `/crawl` |
| US-104 | analyst | 作为分析人员，我希望浏览和筛选已采集的帖子数据，以便初步了解数据质量和内容分布 | 数据表支持按平台/关键词筛选，分页展示，字段完整 | P1 | `/crawl` |
| US-201 | analyst | 作为分析人员，我希望配置检测参数并运行协同检测，以便发现数据中的协同行为 | 检测完成后输出协调配对数、协调账户数、群体数量 | P0 | `/coordination` |
| US-202 | analyst | 作为分析人员，我希望查看协同网络可视化图，以便直观理解账户间的协调关系 | 网络图正确渲染节点和边，协调账户以不同颜色标记 | P0 | `/coordination` |
| US-203 | analyst | 作为分析人员，我希望查看协调账户排名和高频共享对象，以便定位核心协调者和关键传播素材 | 表格按连接数/边权排序，数据与检测结果一致 | P1 | `/coordination` |
| US-301 | analyst | 作为分析人员，我希望运行传播分析识别关键传播角色，以便追溯信息传播路径和核心节点 | 输出起爆/桥接/扩散三类角色，指标（出度/介数/入度）正确 | P0 | `/propagation` |
| US-302 | analyst | 作为分析人员，我希望查看传播时间线，以便了解信息传播的时序过程 | 时间线按时间排序，协调账户以红色标记 | P1 | `/propagation` |
| US-303 | analyst | 作为分析人员，我希望预测传播趋势，以便提前预判事件发展走向 | 【@ARIS:Propagation Analysis】输出未来 N 小时传播量/范围/速度预测值 | P0 | `/propagation` |
| US-401 | analyst | 作为分析人员，我希望运行综合风险评估，以便获取事件的多维风险评分和等级 | 输出综合风险分（0-100）、风险等级、D-S 信念区间 | P0 | `/risk` |
| US-402 | analyst | 作为分析人员，我希望查看 DISARM 攻击路径分析，以便了解攻击者使用的战术和技术 | 输出观测到的 DISARM 技术列表、预测下一步、反制建议 | P0 | `/risk` |
| US-403 | analyst | 作为分析人员，我希望查看处置建议并按优先级排序，以便快速制定响应策略 | 建议列表按 high/medium/low 排序，每条包含行动与理由 | P1 | `/risk` |
| US-404 | analyst | 作为分析人员，我希望查看和检索历史风险报告，以便复盘和对比分析 | 报告列表支持按平台/风险等级/阶段筛选，分页展示 | P1 | `/risk` |
| US-501 | viewer | 作为只读用户，我希望在监测看板查看系统核心指标，以便快速了解整体态势 | 看板展示监测任务数、采集数据量、风险预警数、协同群体数 | P0 | `/` |
| US-502 | analyst | 作为分析人员，我希望在看板查看风险趋势图表，以便掌握风险变化动态 | 【待开发】ECharts 图表展示近 7/30 天风险趋势 | P2 | `/` |
| US-601 | analyst | 作为分析人员，我希望查看所有账户的自动化倾向评分，以便批量筛查可疑水军账户 | 评分 0-100，高危（≥60）红色、可疑（30-59）黄色、正常（<30）绿色 | P0 | `/accounts` |
| US-602 | analyst | 作为分析人员，我希望查看单个账户的详细行为画像，以便深入分析其自动化特征 | 【待开发】详情页展示 24h 分布、行为模板化、历史参与模式 | P2 | `/accounts` |
| US-701 | analyst | 作为分析人员，我希望收到高风险事件的预警通知，以便及时响应 | 【待开发】预警包含风险等级、事件摘要、跳转链接 | P1 | `/`、`/risk` |
| US-702 | analyst | 作为分析人员，我希望对预警执行处置操作并记录备注，以便跟踪响应进度 | 【待开发】处置状态可更新，备注可保存，案例可入库 | P2 | `/risk` |
| US-801 | admin | 作为管理员，我希望管理系统用户（增删改查、角色分配），以便控制系统访问权限 | 【待开发】用户管理页面支持 CRUD 操作和角色变更 | P1 | 【待开发】`/admin/users` |
| US-802 | admin | 作为管理员，我希望配置系统参数（采集平台、预警阈值等），以便调整系统运行策略 | 【待开发】配置页面支持参数修改和即时生效 | P2 | 【待开发】`/admin/settings` |

**优先级说明**：
- **P0**：核心功能，release-0.2 基线已实现或必须实现
- **P1**：重要功能，当前版本部分实现，需完善
- **P2**：增强功能，待后续版本开发

---

# 第 3 章 页面信息架构与交互流程

本章定义 CogGuard 系统的前端页面信息架构、各页面功能区域划分、关联 API 以及页面间跳转关系。系统采用 Vue 3 + Ant Design Vue + Vue Router 构建单页应用，通过 BasicLayout 提供统一的侧边栏导航 + 顶部栏 + 标签页 + 内容区布局。当前已完成登录、数据采集、协同检测、传播监控、账户监测等核心页面，监测看板与报告管理为待开发模块。

---

## 3.1 全局导航结构与布局

### 3.1.1 路由结构

系统路由定义于 `frontend/src/router/index.ts`，采用两层结构：

| 路径 | 名称 | 组件 | 认证要求 | 状态 |
|------|------|------|----------|------|
| `/login` | Login | `views/login/index.vue` | 否 | 已完成 |
| `/` | Dashboard | `views/dashboard/index.vue` | 是 | 待开发 |
| `/crawl` | Crawl | `views/crawl/index.vue` | 是 | 已完成 |
| `/coordination` | Coordination | `views/coordination/index.vue` | 是 | 已完成 |
| `/propagation` | Propagation | `views/propagation/index.vue` | 是 | 已完成 |
| `/accounts` | Accounts | `views/accounts/index.vue` | 是 | 已完成 |
| `/risk` | Risk | `views/risk/index.vue` | 是 | 部分完成 |
| `/reports` | Reports | 待创建 | 是 | 新增 |

全局导航守卫逻辑：未登录用户访问受保护页面时自动跳转 `/login`；已登录用户访问 `/login` 时自动跳转首页 `/`。

> **源文件**：`G:\CISCN\cogguard_system\new-system\frontend\src\router\index.ts`

### 3.1.2 BasicLayout 布局结构

布局组件 `BasicLayout.vue` 提供全局统一的三栏 + 标签页结构：

```
+------------------+----------------------------------------------+
| |  顶部栏 (Header) |
|   侧边栏 |  [当前模块名称]              [用户头像 用户名 ▼] |
|   (Sider)        +----------------------------------------------+
| |  标签页导航 (Tab Bar) |
|   CogGuard Logo |  [监测看板] [数据采集] [协同检测] ...    [×] |
|   -------------- +----------------------------------------------+
|   监测看板 | |
|   数据采集 |  主内容区 (Content) |
|   协同检测 | |
|   传播监控 |  <router-view /> |
|   账户监测 | |
|   报告研判 | |
+------------------+----------------------------------------------+
```

**侧边栏 (Sider)**：
- 可折叠（collapsed），折叠后 Logo 显示为 "CG"
- 深色主题（theme="dark"），内联模式菜单
- 每个菜单项带 Tooltip 描述，鼠标悬停 0.4s 后显示

**菜单项定义**：

| 路径 | 标签 | 图标 | 描述 |
|------|------|------|------|
| `/` | 监测看板 | DashboardOutlined | 系统概览：任务统计、风险趋势、数据总量 |
| `/crawl` | 数据采集 | CloudDownloadOutlined | 创建采集任务，管理多平台数据抓取 |
| `/coordination` | 协同检测 | ApartmentOutlined | 检测时间窗口内的协调分享行为，构建协同网络 |
| `/propagation` | 传播监控 | ShareAltOutlined | 分析信息传播路径，识别起爆/桥接/扩散关键角色 |
| `/accounts` | 账户监测 | UserOutlined | 账户行为画像、作息节律、自动化倾向评估 |
| `/risk` | 报告研判 | AlertOutlined | 阶段感知风险评估、D-S 证据融合、DISARM 攻击路径分析 |

**顶部栏 (Header)**：
- 左侧显示当前模块名称（根据路由匹配菜单项 label）
- 右侧用户徽章：头像（取用户名首字母）+ 用户名，下拉菜单包含角色信息和退出登录

**标签页导航 (Tab Bar)**：
- 访问新页面时自动添加标签，支持点击切换和关闭
- 至少保留一个标签，最后一个标签不可关闭
- 关闭当前标签时自动跳转到相邻标签
- 水平滚动支持，标签过多时可横向滑动

**主内容区 (Content)**：
- 白色背景，圆角 6px，内边距 20px 24px
- 最小高度 360px，通过 `<router-view />` 渲染子路由组件

> **源文件**：`G:\CISCN\cogguard_system\new-system\frontend\src\components\layout\BasicLayout.vue`

---

## 3.2 登录页（/login）— 已完成

### 功能概述

独立全屏页面，不使用 BasicLayout。居中卡片式表单，支持登录与注册模式切换。深色渐变背景（#1a1a2e → #16213e → #0f3460），白色卡片宽 400px。

### 功能区域划分

| 区域 | 说明 |
|------|------|
| 品牌标识 | 标题 "CogGuard" + 副标题 "面向跨域认知操纵的智能联合防御系统" |
| 登录表单 | 用户名（必填）+ 密码（必填）+ 登录按钮（全宽，loading 状态） |
| 注册表单 | 用户名（3-64 字符）+ 邮箱（格式校验）+ 密码（≥6 位）+ 注册按钮 |
| 模式切换 | "还没有账号？立即注册" / "已有账号？返回登录" 链接 |

### 交互流程

1. 用户输入用户名和密码，点击「登录」
2. 调用 `authStore.login()` 发起认证请求，成功后保存 Token 至 localStorage
3. 登录成功提示 "登录成功"，自动跳转至首页 `/`
4. 注册成功后自动切换到登录模式，并预填用户名

### 关联 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/auth/login` | 用户登录，返回 access_token |
| POST | `/api/v1/auth/register` | 用户注册 |

> **源文件**：`G:\CISCN\cogguard_system\new-system\frontend\src\views\login\index.vue`

---

## 3.3 监测看板（/）— 开发中

### 功能概述

系统首页，提供事件级真实数据概览。当前优先接入 MongoDB 中 `event_id=trump_visit_2026_05_21` 的 posts/comments，展示统计卡片、平台分布、世界地图事件位置和最早发帖样本。事件位置按“事件关键词下第一条发帖者 IP 属地”定位，例如“特朗普访华”定位到第一发帖者“新华日报”的 IP 北京。

### 功能区域划分

| 区域 | 说明 | 状态 |
|------|------|------|
| 页面头部 | PageHeader：标题 "监测看板" + 描述文字 | 已完成 |
| 事件范围工具栏 | event_id 输入、刷新按钮、数据源状态 Tag | 开发中 |
| 统计卡片行 | 事件数、采集帖子、平台覆盖、风险报告 | 开发中，接入 API |
| 世界地图 | ECharts 本地 GeoJSON 地图，事件点按坐标标注 | 开发中 |
| 平台分布 | weibo/xhs/douyin posts/comments 表格 | 开发中 |
| 事件定位明细 | 事件、第一发帖者、IP 属地、坐标解析状态、规模 | 开发中 |
| 最近发帖样本 | 按时间展示最早帖子 | 开发中 |

### 详细设计：统计卡片

| 卡片 | 数据字段 | 后缀 | 说明 |
|------|----------|------|------|
| 事件数 | `summary.event_count` | 个 | 当前筛选范围内的事件数 |
| 采集帖子 | `summary.posts` | 条 | 当前事件 posts 数量 |
| 平台覆盖 | `summary.platform_count` | 个 | 当前事件覆盖平台数量 |
| 风险报告 | `summary.risk_reports` | 条 | 当前事件已持久化研判报告数 |

### 详细设计：世界地图与事件定位

- 地图使用 ECharts，本地注册世界地图 GeoJSON，避免运行时依赖外网。
- `event_locations[].coordinates` 非空时渲染地图散点；为空时进入“未解析位置”列表，不渲染地图点。
- Tooltip 展示事件名、第一发帖者、平台、IP 属地、posts/comments 数量。
- v1 坐标解析使用静态别名表，至少覆盖北京、上海、广东、浙江、江苏、美国、日本等常见位置。
- 默认事件为 `trump_visit_2026_05_21`，后续可扩展为事件选择器和多事件排行。

### 详细设计：平台分布与样本列表

- 平台分布表展示各平台 posts、comments、total。
- 事件定位明细表展示事件 ID、事件名称、第一发帖者、IP 属地、解析状态和规模。
- 最近发帖样本按发布时间升序展示，用于人工核对事件起点。

### 需新增 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/dashboard/overview` | 聚合看板数据：统计卡片、平台分布、世界地图事件点、最近发帖样本 |

**响应结构设计**：

```json
{
  "code": 0,
  "data": {
    "summary": {"event_count": 1, "posts": 294, "comments": 14722, "platform_count": 3, "risk_reports": 0},
    "platforms": [{"platform": "weibo", "posts": 120, "comments": 3000, "total": 3120}],
    "event_locations": [{
      "event_id": "trump_visit_2026_05_21",
      "event_name": "特朗普访华",
      "origin_author": "新华日报",
      "origin_platform": "weibo",
      "ip_location": "北京",
      "coordinates": [116.4074, 39.9042],
      "resolved": true,
      "posts": 294,
      "comments": 14722
    }],
    "recent_posts": [],
    "meta": {"event_id": "trump_visit_2026_05_21", "data_source_status": {"mongo": "ok", "mysql": "ok"}}
  }
}
```

> **源文件**：`G:\CISCN\cogguard_system\new-system\frontend\src\views\dashboard\index.vue`

---

## 3.4 数据采集（/crawl）— 已完成

### 功能概述

跨平台数据采集管理页面，支持创建采集任务、查看任务列表与状态、浏览已采集数据。支持 Mock 微博、微博（Social Runtime）、抖音、小红书、新闻链接等多平台。

### 功能区域划分

| 区域 | 说明 |
|------|------|
| 页面头部 | PageHeader：标题 "数据采集" + 功能描述 |
| 创建采集任务 | 内联表单：平台选择、关键词输入、链接输入（textarea，宽度加大）、最大帖子数、开始采集按钮 |
| 高级设置 | 折叠面板：Social Runtime 登录方式、评论/二级评论开关、单帖评论上限、代理、排序/时间等平台支持参数 |
| 采集任务列表 | 表格：ID、平台、状态（Tag 颜色编码）、进度、创建时间、操作（取消/删除） |
| 采集数据 | 表格：平台、作者、内容（ellipsis）、发布时间，支持分页 |

### 支持平台列表

| 平台 ID | 名称 | 状态 | 备注 |
|---------|------|------|------|
| `mock_weibo` | 模拟微博（测试） | active | 默认选中，用于演示 |
| `weibo` | 微博（Social Runtime） | active | 按需配置 Cookie、代理和 Node.js |
| `douyin` | 抖音（Social Runtime） | active | 按需配置代理和 Node.js |
| `xhs` | 小红书（Social Runtime） | active | 按需配置 Cookie、代理和 Node.js |
| `news` | 新闻链接（News Runtime） | active | 在「链接」中填写文章 URL |

### 交互流程

1. 页面加载时自动拉取平台列表、任务列表和采集数据
2. 用户选择平台、输入关键词/链接、设置最大帖子数，点击「开始采集」
3. 后端创建任务并通过 Celery 异步执行，前端刷新任务列表
4. 任务状态流转：pending → running → completed / failed / cancelled
5. 用户可对 pending/running 状态的任务执行「取消」，对任意任务执行「删除」（含确认弹窗）

### 关联 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/crawl/platforms` | 获取支持平台列表 |
| POST | `/api/v1/crawl/social` | 创建采集任务 |
| GET | `/api/v1/crawl/jobs` | 查询任务列表（分页） |
| DELETE | `/api/v1/crawl/jobs/{job_id}` | 删除任务及其数据 |
| POST | `/api/v1/crawl/jobs/{job_id}/cancel` | 取消任务 |
| GET | `/api/v1/crawl/data` | 查询采集数据（分页，支持 platform/keyword 筛选） |

> **源文件**：
> - 前端：`G:\CISCN\cogguard_system\new-system\frontend\src\views\crawl\index.vue`
> - 后端：`G:\CISCN\cogguard_system\new-system\backend\app\api\v1\crawl.py`

---

## 3.5 协同检测（/coordination）— 已完成

### 功能概述

Coordination Discover consumes a platform-generic Evidence Graph and learns temporal coordination structure. The coordination baseline remains an evidence-backed fallback and is not a learned research claim.

### 功能区域划分

| 区域 | 说明 |
|------|------|
| 页面头部 | PageHeader：标题 "协同检测" + 算法原理描述 |
| 参数配置 | 内联表单：时间窗口（1-3600 秒，默认 60）、最低参与次数（默认 1）、边权阈值（Slider 0-1，步长 0.05，默认 0.5）、运行检测按钮 |
| 概览统计 | 4 个 Statistic 卡片：分析帖子数、协调配对数、协调账户数（红色）、群体数量 |
| 协同网络 | Canvas 绘制的力导向网络图（420px 高），节点颜色区分协调账户（红）和普通账户（蓝），边宽度映射权重 |
| 协调账户排名 | 表格：账户 ID、连接数、平均边权、平均时间差、对称性、协调分享数，支持排序和分页 |
| 高频共享对象 | 表格：共享对象 ID、涉及账户数、协调配对数，支持排序 |

### 交互流程

1. 用户调整参数后点击「运行检测」
2. 后端 executes the configured Coordination Discover port and returns summary statistics, evidence/learned graph data, account rankings, and shared-object evidence
3. 前端渲染概览卡片、Canvas 网络图（力导向布局 50 次迭代）、两个数据表格
4. 网络图使用简易力导向算法：节点间斥力 + 边弹簧力，50 次迭代后归一化坐标

### 关联 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/coordination/detect` | 运行协同检测，参数：time_window、min_participation、edge_weight、platform、event_id；后续补事件顺序聚合、跨平台聚合和用户聚类 |

> **源文件**：
> - 前端：`G:\CISCN\cogguard_system\new-system\frontend\src\views\coordination\index.vue`
> - 后端：`G:\CISCN\cogguard_system\new-system\backend\app\api\v1\coordination.py`

---

## 3.6 传播监测（/propagation）— 观测分析与模型预测已分离

### 功能概述

页面将已发生的传播分析与未来预测分开。观测分析基于显式回复、父级 ID 重建和共享对象时间邻近关系构建可追溯传播投影；模型预测在严格观测截止时间后输出规模趋势和下一跳再激活排序。推断关系不等于平台确认转发，预测不可用时不回退到速度或加速度规则。

### 功能区域划分

| 区域 | 说明 |
|------|------|
| 页面头部 | 当前事件、平台、观测截止时间和预测范围 |
| 传播路径 | 分层簇状摘要、证据类型连线、层级统计和节点详情联动 |
| 传播对象 | URL/标签等共享对象、关联帖子及关键传播路径 |
| 角色分析 | 起爆与扩散角色、结构指标、证据引用和稳定性摘要 |
| 时间线 | 当前事件观测时间线，响应包含完整数量与截断元数据 |
| 模型预测 | 规模趋势曲线、实名下一跳再激活研判和证据回跳 |

### 交互流程

1. 用户点击「运行传播分析」
2. 后端分析已采集数据中的传播关系，返回关键角色、共享对象统计、时间线
3. 前端渲染三列角色卡片、共享对象表格、时间线组件
4. 若后端返回 `error` 字段，前端以 warning 提示（如数据不足）

### 关联 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/propagation/analyze` | 观测传播分析；可选 `platform`、`event_id`、扩散摘要 `node_limit` |
| POST | `/api/v1/propagation/model-event-predict` | 当前事件规模趋势与下一跳预测；支持 `observed_until`、`prediction_horizon`、`top_k` |

> **源文件**：
> - 前端：`G:\CISCN\cogguard_system\new-system\frontend\src\views\propagation\index.vue`
> - 后端：`G:\CISCN\cogguard_system\new-system\backend\app\api\v1\propagation.py`

---

## 3.7 账户监测（/accounts）— 已完成

### 功能概述

分析已采集帖子中每个账户的行为特征：发文频率与间隔规律性、作息节律（24h 分布）、互动指标、内容多样性。综合计算自动化倾向评分（0-100），分数越高越可能是自动化水军。页面加载时自动拉取数据。

### 功能区域划分

| 区域 | 说明 |
|------|------|
| 页面头部 | PageHeader：标题 "账户监测" + 评分机制说明 |
| 概览统计 | 4 个 Statistic 卡片：总账户数、高危账户（≥60 分，红色）、可疑账户（30-59 分，黄色）、正常账户（<30 分，绿色） |
| 账户行为画像表格 | 表格含刷新按钮，列：账户 ID（水军标红）、昵称、帖子数、自动化评分（Progress 条形图，颜色编码）、规律性、活跃时段、峰值小时、最短间隔、总点赞 |

### 自动化评分颜色编码

| 分数范围 | 颜色 | 等级 |
|----------|------|------|
| ≥ 60 | #f5222d（红） | 高危 |
| 30 - 59 | #faad14（黄） | 可疑 |
| < 30 | #52c41a（绿） | 正常 |

### 交互流程

1. 页面 `onMounted` 自动调用 `getAccountProfiles()` 加载数据
2. 表格默认按自动化评分降序排列
3. 用户可点击「刷新」按钮手动重新加载
4. 账户 ID 包含 `coord_bot` 的以红色 danger 文字标记

### 关联 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/accounts/profiles` | 获取账户行为画像列表，可选参数：platform |
| GET | `/api/v1/accounts/detail/{account_id}` | 获取单个账户详情 |

> **源文件**：
> - 前端：`G:\CISCN\cogguard_system\new-system\frontend\src\views\accounts\index.vue`
> - 后端：`G:\CISCN\cogguard_system\new-system\backend\app\api\v1\accounts.py`

---

## 3.8 报告研判（/risk）— 部分完成

### 功能概述

基于阶段感知危险模型、Dempster-Shafer 证据融合和 DISARM 攻击路径分析，对协同操纵事件进行多维风险评估。已有基础 UI 和 API，需补充详细交互设计。

### 功能区域划分

| 区域 | 说明 | 状态 |
|------|------|------|
| 页面头部 | PageHeader：标题 "报告研判" + 方法论描述 | 已完成 |
| 参数配置 | 内联表单：平台选择（Mock 微博/微博/新闻）、时间窗口（秒）、运行评估按钮 | 已完成 |
| 概览卡片 | 6 个 Statistic 卡片：综合风险分（颜色编码）、风险等级、当前阶段、证据冲突（%）、攻击路径分、检测技术数 | 已完成 |
| 三维评分表 | D-S 信念区间表格：操纵性/行为真实性/影响力 × 分数/信念/似然/区间 | 已完成 |
| DISARM 攻击路径 | 左：观测到的 DISARM 技术表格；右：预测下一步（Tag）+ 反制建议表格 | 已完成 |
| 风险因子 & 建议 | 左：风险因子分类展示（操纵性/行为真实性/影响力）；右：处置建议列表（优先级 Tag + 行动 + 原因） | 已完成 |
| 历史报告 | 历史风险报告表格，支持分页 | 已完成 |

### 阶段模型

| 阶段 Key | 中文名 | 说明 |
|-----------|--------|------|
| `seed` | 播种期 | 初始内容投放阶段 |
| `synchronize` | 同步期 | 协调账户开始同步传播 |
| `breakout` | 爆发期 | 信息大规模扩散 |
| `saturation` | 饱和期 | 传播达到峰值 |
| `regeneration` | 再生期 | 变体内容再次传播 |

### 风险等级颜色编码

| 等级 | 颜色 |
|------|------|
| critical | #f5222d（红） |
| high | #fa8c16（橙） |
| medium | #faad14（黄） |
| low | #52c41a（绿） |

### 需补充的交互设计

1. **报告详情弹窗**：点击历史报告表格行，弹出 Drawer 展示完整报告内容（当前仅有表格展示，无详情入口）
2. **报告导出**：在历史报告区域增加「导出 PDF」按钮，调用后端报告导出接口
3. **参数预设**：提供「快速检测」（宽松参数）和「精确检测」（严格参数）两个预设按钮
4. **风险趋势图**：在概览卡片下方增加 ECharts 折线图，展示历史风险分变化趋势

### 交互流程

1. 用户选择平台、设置时间窗口，点击「运行评估」
2. 后端执行阶段检测 → D-S 融合 → DISARM 分析，返回完整报告
3. 前端渲染概览卡片、三维评分表、DISARM 分析、风险因子、处置建议
4. 评估完成后自动刷新历史报告列表
5. 成功提示格式：`评估完成：{risk_level} ({score}分)`

### 关联 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/risk/assess` | 执行风险评估，参数：platform、time_window、min_participation、edge_weight |
| GET | `/api/v1/risk/reports` | 查询历史报告列表，参数：platform、risk_level、phase、page、page_size |
| GET | `/api/v1/risk/reports/{report_id}` | 获取单个报告详情 |

> **源文件**：
> - 前端：`G:\CISCN\cogguard_system\new-system\frontend\src\views\risk\index.vue`
> - 后端：`G:\CISCN\cogguard_system\new-system\backend\app\api\v1\risk.py`

---

## 3.9 报告管理（/reports）— 新增

### 功能概述

集中管理系统生成的各类分析报告，提供报告列表浏览、详情查看和导出功能。该页面为新增模块，需从零开发前后端。

### 功能区域划分

| 区域 | 说明 |
|------|------|
| 页面头部 | PageHeader：标题 "报告管理" + 描述 "查看、管理和导出系统生成的风险评估报告" |
| 筛选栏 | 内联表单：平台筛选（Select）、风险等级筛选（Select）、时间范围（RangePicker）、搜索按钮、重置按钮 |
| 报告列表 | 表格：报告 ID、平台、风险等级（Tag 颜色编码）、综合风险分、当前阶段、评估时间、操作（查看/导出/删除） |
| 报告详情 Drawer | 右侧抽屉（宽 720px），展示完整报告内容 |
| 批量操作栏 | 表格上方：全选、批量导出、批量删除 |

### 详细设计：报告列表

**表格列定义**：

| 列名 | 字段 | 宽度 | 特性 |
|------|------|------|------|
| 报告 ID | `report_id` | 160px | ellipsis |
| 平台 | `platform` | 100px | — |
| 风险等级 | `risk_level` | 100px | Tag 颜色编码（critical=红, high=橙, medium=黄, low=绿） |
| 综合风险分 | `overall_risk_score` | 100px | 可排序 |
| 当前阶段 | `current_phase` | 100px | 中文映射显示 |
| 证据冲突 | `conflict_mass` | 100px | 百分比格式 |
| 评估时间 | `assessed_at` | 180px | 可排序，默认降序 |
| 操作 | — | 200px | 查看 / 导出 PDF / 删除 |

**分页**：默认每页 20 条，支持 TableSettings 调整。

### 详细设计：报告详情 Drawer

抽屉内容分区：

| 区域 | 说明 |
|------|------|
| 报告元信息 | 报告 ID、平台、评估时间、风险等级（大号 Tag） |
| 综合评分 | 综合风险分（大号数字）+ 三维评分表（操纵性/真实性/影响力 × 分数/信念/似然） |
| 阶段信息 | 当前阶段（中文）+ 阶段置信度 + 阶段描述 |
| D-S 融合 | 证据冲突度 + 各维度信念区间可视化（Progress 条） |
| DISARM 分析 | 观测技术列表 + 预测下一步 + 反制建议 |
| 风险因子 | 分类展示操纵性/真实性/影响力因子 |
| 处置建议 | 优先级排序的建议列表 |
| 操作按钮 | 底部固定：导出 PDF、关闭 |

### 详细设计：导出功能

- **导出格式**：PDF（主要）、JSON（原始数据）
- **PDF 内容**：报告封面（系统名称 + 报告 ID + 时间）+ 评分摘要 + 详细分析 + 处置建议
- **触发方式**：
  - 列表页操作列「导出」按钮 → 单份导出
  - 详情 Drawer 底部「导出 PDF」按钮 → 单份导出
  - 批量操作栏「批量导出」→ 打包为 ZIP 下载
- **后端实现**：新增 `/api/v1/reports/{report_id}/export` 接口，返回文件流

### 交互流程

1. 页面加载时自动拉取报告列表（默认按评估时间降序）
2. 用户可通过筛选栏按平台、风险等级、时间范围过滤
3. 点击「查看」打开右侧 Drawer 展示完整报告
4. 点击「导出」触发 PDF 下载
5. 点击「删除」弹出确认弹窗，确认后删除并刷新列表
6. 支持表格行多选，启用批量导出和批量删除

### 状态流转

```
列表加载 → 筛选/翻页 → 查看详情(Drawer) → 导出/关闭
                ↓
         批量选择 → 批量导出/批量删除
```

### 需新增 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/reports` | 报告列表（复用 risk/reports 或独立接口） |
| GET | `/api/v1/reports/{report_id}` | 报告详情 |
| GET | `/api/v1/reports/{report_id}/export` | 导出报告（PDF/JSON），参数：format |
| POST | `/api/v1/reports/batch-export` | 批量导出，body：report_ids 数组 |
| DELETE | `/api/v1/reports/{report_id}` | 删除报告 |
| POST | `/api/v1/reports/batch-delete` | 批量删除，body：report_ids 数组 |

### 需新增路由

```typescript
{
  path: 'reports',
  name: 'Reports',
  component: () => import('@/views/reports/index.vue'),
  meta: { title: '报告管理' },
}
```

需在 `BasicLayout.vue` 的 `menuItems` 中新增：

```typescript
{ path: '/reports', label: '报告管理', icon: FileTextOutlined, desc: '查看、管理和导出风险评估报告', disabled: false }
```

---

## 3.10 页面间跳转关系图

```
                         ┌─────────────────────────────────────────────────────────┐
                         │                    BasicLayout                           │
                         │                                                         │
┌─────────┐   登录成功   │  ┌──────────┐    ┌──────────┐    ┌──────────────┐       │
│         │ ──────────→ │  │ 监测看板  │───→│ 数据采集  │───→│  协同检测     │       │
│  登录页  │             │  │   /      │    │  /crawl  │    │ /coordination │       │
│ /login  │ ←────────── │  └────┬─────┘    └────┬─────┘    └──────┬───────┘       │
│         │   退出登录   │       │                │                  │               │
└─────────┘             │       │                │                  │               │
                         │       ▼                ▼                  ▼               │
                         │  ┌──────────┐    ┌──────────┐    ┌──────────────┐       │
                         │  │ 报告管理  │←──│ 报告研判  │←──│  账户监测     │       │
                         │  │ /reports │    │  /risk   │    │  /accounts   │       │
                         │  └──────────┘    └────┬─────┘    └──────┬───────┘       │
                         │                       │                  │               │
                         │                       ▼                  │               │
                         │                 ┌──────────────┐         │               │
                         │                 │  传播监控     │←────────┘               │
                         │                 │ /propagation │                         │
                         │                 └──────────────┘                         │
                         └─────────────────────────────────────────────────────────┘
```

**跳转关系说明**：

| 起始页 | 目标页 | 触发条件 |
|--------|--------|----------|
| /login | / | 登录成功 |
| 任意页 | /login | 退出登录 / Token 过期 |
| / (看板) | /risk | 点击预警列表「查看详情」 |
| / (看板) | /risk | 点击风险分布饼图扇区 |
| /crawl | /coordination | 采集完成后引导用户进行协同检测 |
| /coordination | /propagation | 检测完成后可进一步分析传播路径 |
| /coordination | /accounts | 查看协调账户详细画像 |
| /risk | /reports | 评估完成后查看/管理报告 |
| /accounts | /risk | 高危账户触发风险评估 |

---

## 3.11 全局交互流程（从登录到报告的完整路径）

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          CogGuard 完整操作流程                                    │
└─────────────────────────────────────────────────────────────────────────────────┘

  ┌──────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ 登录  │────→│ 监测看板  │────→│ 数据采集  │────→│ 协同检测  │────→│ 传播监控  │
  └──────┘     └──────────┘     └──────────┘     └──────────┘     └──────────┘
                    │                                    │                │
                    │                                    ▼                ▼
                    │                              ┌──────────┐     ┌──────────┐
                    │                              │ 账户监测  │────→│ 报告研判  │
                    │                              └──────────┘     └──────────┘
                    │                                                     │
                    │                                                     ▼
                    │                                               ┌──────────┐
                    └──────────────────────────────────────────────→│ 报告管理  │
                                                                    └──────────┘
```

### 典型用户操作路径

**路径 1：完整分析流程**

```
登录 → 看板概览 → 创建采集任务 → 等待采集完成 → 运行协同检测 →
查看协同网络 → 运行传播监控 → 查看关键角色 → 查看账户画像 →
运行风险评估 → 查看评估报告 → 导出 PDF 报告
```

**路径 2：快速风险评估**

```
登录 → 报告研判 → 选择平台/参数 → 运行评估 → 查看结果 → 导出报告
```

**路径 3：日常监控**

```
登录 → 看板概览 → 查看预警列表 → 点击预警进入报告研判 → 查看详情
```

### 全局状态管理

| 状态 | 存储位置 | 说明 |
|------|----------|------|
| access_token | localStorage | JWT 认证令牌 |
| userInfo | Pinia (authStore) | 用户信息（username、role） |
| 页面标签 | BasicLayout 组件内 ref | 已打开的标签页列表 |
| 侧边栏折叠 | BasicLayout 组件内 ref | collapsed 状态 |

### 错误处理与边界情况

| 场景 | 处理方式 |
|------|----------|
| Token 过期 | 导航守卫拦截，跳转 /login |
| API 请求失败 | 各页面 catch 块处理，message.error 提示 |
| 数据为空 | 统一使用 `<a-empty>` 组件展示空状态提示 |
| 操作确认 | 删除/取消等破坏性操作使用 Popconfirm 二次确认 |
| 加载状态 | 按钮 loading + 表格 loading 属性 |

---

# 第 4 章 功能编排与优先级

CogGuard 系统围绕"数据采集 → 协同发现 → 传播监控 → 报告研判"四阶段流水线构建。本章定义三大核心功能（协同发现、传播监控、报告研判）的数据流转关系、触发条件、子功能清单及优先级分期，并以代码实现为基准标注各子功能的完成状态。所有标注为"待 ARIS"的关键技术子功能，将在 ARIS 工作空间中完成算法研发后回填至主系统。

---

## 4.1 三大功能数据流转关系

### 4.1.1 全局数据流 ASCII 图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        CogGuard 数据流水线                              │
└─────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐
  │  数据采集层   │  crawl_service
  │  (MongoDB)   │  raw_posts / raw_comments
  └──────┬───────┘
         │ posts: list[dict], comments: list[dict]
         │
    ┌────┴─────────────────────────────────────┐
    │                                          │
    ▼                                          ▼
┌──────────────────┐                ┌─────────────────────┐
│   协同发现   │                │   传播监控      │
│ coordination_svc │                │  propagation_svc    │
│                  │                │                     │
│ ┌──────────────┐ │                │ ┌─────────────────┐ │
│ │ detect_groups│ │                │ │build_propagation│ │
│ │   ↓         │ │                │ │  _graph         │ │
│ │ gen_network  │ │                │ │   ↓             │ │
│ │   ↓         │ │                │ │ predict_trend   │ │
│ │ account_stats│ │                │ │ (CascadeSwitch) │ │
│ │ group_stats  │ │                │ └─────────────────┘ │
│ └──────────────┘ │                └──────────┬──────────┘
└────────┬─────────┘                           │
         │ coord_data: dict                    │ prop_data: dict
         │   ├─ network                        │   ├─ graph
         │   ├─ account_stats                  │   ├─ key_roles
         │   ├─ group_stats                    │   ├─ claims
         │   └─ summary                        │   ├─ timeline
         │                                     │   └─ evidence_chains
         │        ┌───────────────────┐        │
         │        │  账户画像          │        │
         │        │ account_service   │        │
         │        │ → account_profiler│        │
         │        └────────┬──────────┘        │
         │                 │ acct_data:        │
         │                 │ list[dict]        │
         │                 │                   │
         ▼                 ▼                   ▼
    ┌──────────────────────────────────────────────┐
    │              报告研判                     │
    │              risk_service.assess_risk()       │
    │                                              │
    │  ┌────────────┐  ┌──────────────┐            │
    │  │ evidence   │→ │ phase        │            │
    │  │ _builder   │  │ _detector    │            │
    │  └────────────┘  └──────┬───────┘            │
    │                         ▼                    │
    │                  ┌──────────────┐             │
    │                  │  ds_fusion   │             │
    │                  │ (D-S 证据融合)│             │
    │                  └──────┬───────┘             │
    │                         ▼                    │
    │                  ┌──────────────┐             │
    │                  │disarm_scorer │             │
    │                  │(攻击路径评分) │             │
    │                  └──────┬───────┘             │
    │                         ▼                    │
    │                  ┌──────────────┐             │
    │                  │report_builder│             │
    │                  │  → MySQL     │             │
    │                  └──────────────┘             │
    └──────────────────────────────────────────────┘
```

### 4.1.2 各环节输入/输出数据格式

| 环节 | 输入 | 输出 | 数据格式 |
|------|------|------|----------|
| **数据采集** | 用户配置的平台/关键词/时间范围 | 标准化帖子与评论 | `raw_posts`: `{post_id, author_id, author_name, content, timestamp, hashtags, url, likes, reposts, comments_count, platform}` |
| **协同发现** | `posts: list[dict]` (从 MongoDB) | 协同网络 + 统计 | `coord_data: {network: {nodes, edges, component_count, components}, account_stats: [{account_id, degree, avg_weight, avg_time_delta, avg_edge_symmetry, coordinated_shares_count}], group_stats: [{object_id, num_accounts, num_pairs}], summary: {total_posts, total_pairs, coordinated_accounts, coordinated_edges, components}}` |
| **传播监控** | `posts: list[dict]`, `comments: list[dict]` | 传播图 + 角色 + 趋势 | `prop_data: {graph: {nodes, edges, node_count, edge_count}, key_roles: {originators, bridges, amplifiers}, claims, timeline, evidence_chains}` |
| **趋势预测** | `posts`, `comments` | 结构化预测 | `{volume_forecast: {1h, 6h, 24h}, confidence_interval, direction, speed, regime_posterior, detected_events, confidence, explanation}` |
| **报告研判** | `coord_data`, `prop_data`, `acct_data` | 风险报告 | `report: {report_id, event_id, platform, scores: {overall_risk_score, risk_level, manipulation, authenticity, impact}, phase, fusion, disarm_analysis, risk_factors, recommendations}` |

---

## 4.2 功能触发条件与依赖矩阵

### 4.2.1 触发条件

| 功能 | 触发方式 | 触发条件 | 说明 |
|------|----------|----------|------|
| 数据采集 | 手动触发 | 用户通过 API 提交 `CrawlRequest` | 创建 CrawlJob → Celery 异步执行 |
| 协同发现 | 手动触发 | 用户调用协同检测 API，需 MongoDB 中存在 `raw_posts` | 参数：`time_window`, `min_participation`, `edge_weight`, `platform` |
| 传播监控 | 手动触发 | 用户调用传播分析 API，需 MongoDB 中存在 `raw_posts` | 可选传入 `platform` 过滤 |
| 传播预测 | 手动触发 | 用户调用当前事件模型 API，需 MongoDB 中存在至少 3 条带时间戳观测记录 | 带时区 `observed_until` 截断，模型不可用时 abstain |
| 报告研判 | 手动触发 | 用户调用风险评估 API | 自动编排上游三个服务，无需手动前置调用 |
| 报告研判（自动） | P2 待开发 | 预警系统触发 | 基于阈值或定时任务自动执行 |

### 4.2.2 依赖矩阵

| 功能 (行依赖列) | 数据采集 | 协同发现 | 传播监控 | 趋势预测 | 账户画像 | 报告研判 |
|-----------------|:--------:|:--------:|:--------:|:--------:|:--------:|:--------:|
| **数据采集** | — | | | | | |
| **协同发现** | **必需** | — | | | | |
| **传播监控** | **必需** | | — | | | |
| **趋势预测** | **必需** |  可选(1) | 内部调用 | — | | |
| **账户画像** | **必需** | | | | — | |
| **报告研判** | **必需** | **必需** | **必需** | | **必需** | — |

> (1) 趋势预测的 `coordination_signals` 参数可接收协同检测信号作为外生事件输入，当前版本未自动串联，预留接口。

---

## 4.3 协同发现 — 子功能清单与优先级

Coordination Discover consumes a platform-generic Evidence Graph and learns temporal coordination structure. The fallback implementation lives under `app/core/coordination_baseline/`; the canonical research package is `system/research/coordination_discover/`.

### 子功能清单

#### 4.3.1 共享对象协同检测

| 属性 | 值 |
|------|-----|
| **优先级** | P0 |
| **状态** | 已完成 |
| **实现文件** | `core/coordination/detector.py` |
| **描述** | 在同一 `object_id`（URL/标签）下，检测 `time_window` 秒内发布的所有内容对。支持自环移除、最低参与次数过滤、快窗标记（`flag_speed_share`）。输入为标准化 DataFrame（`object_id, account_id, content_id, timestamp_share`），输出为协调配对表（`object_id, account_id, account_id_y, content_id, content_id_y, time_delta`）。 |
| **依赖** | 数据采集（MongoDB `raw_posts`） |

#### 4.3.2 协同网络可视化

| 属性 | 值 |
|------|-----|
| **优先级** | P0 |
| **状态** | 已完成 |
| **实现文件** | `core/coordination/network.py` |
| **描述** | 从协调配对结果构建加权无向图（networkx）。边属性含 `weight`（配对次数）、`avg_time_delta`、`edge_symmetry_score`。支持边权百分位阈值过滤（`edge_weight` 参数）、快窗子图提取（`subgraph` 模式 0-3）。通过 `graph_to_dict()` 序列化为前端可渲染的 JSON（含连通分量分析）。 |
| **依赖** | 共享对象协同检测 |

#### 4.3.3 账户统计与群组统计

| 属性 | 值 |
|------|-----|
| **优先级** | P0 |
| **状态** | 已完成 |
| **实现文件** | `core/coordination/stats.py` |
| **描述** | `account_stats`: 按账户汇总协同指标（degree, avg_weight, avg_time_delta, avg_edge_symmetry, coordinated_shares_count）。`group_stats`: 按 `object_id` 汇总涉及的协调账户数和配对数。两者均返回排序后的 DataFrame。 |
| **依赖** | 协同网络可视化 |

#### 4.3.4 多任务框架协同检测（关键技术）

| 属性 | 值 |
|------|-----|
| **优先级** | P1 |
| **状态** | 待 ARIS 工作空间实现 |
| **实现文件** | 待创建 |
| **描述** | 基于多任务学习框架的协同行为检测。在共享对象时间窗检测的基础上，引入内容语义相似度、行为序列模式等多维特征，通过多任务神经网络联合学习协同概率。该子功能为竞赛关键技术 Coordination Discover / Detect 的核心增强。 |
| **I/O 接口定义** | 输入：`DataFrame[object_id, account_id, content_id, timestamp_share, content_embedding, behavior_seq]`；输出：`DataFrame[..., coordination_prob, coordination_type]`，兼容现有 `detect_groups` 返回格式 |
| **依赖** | 共享对象协同检测、数据采集 |

#### 4.3.5 多行为边构建

| 属性 | 值 |
|------|-----|
| **优先级** | P2 |
| **状态** | 待开发 |
| **实现文件** | 待创建 |
| **描述** | 在现有单一"共享对象"边类型基础上，扩展为多行为边：共同关注、共同评论、共同转发、内容相似度边。构建多层异构网络，为多任务框架提供更丰富的图结构输入。 |
| **依赖** | 协同网络可视化、数据采集（需扩展采集评论/关注数据） |

#### 4.3.6 显著性筛查

| 属性 | 值 |
|------|-----|
| **优先级** | P2 |
| **状态** | 待开发 |
| **实现文件** | 待创建 |
| **描述** | 对协同检测结果进行统计显著性检验（置换检验 / Bootstrap），过滤偶然协同，降低误报率。输出每对协同关系的 p-value 和效应量。 |
| **依赖** | 共享对象协同检测 |

---

## 4.4 传播监控 — 子功能清单与优先级

传播模块由观测传播分析与传播预测组成。本节为当前规范，覆盖本文档后续仍可能出现的 `CascadeSwitch`、`predict-trend`、速度/加速度 fallback 历史描述。观测核心位于 `app/core/propagation_legacy.py`；当前事件预测由 `app/services/propagation_model_service.py` 和 `system/research/propagation_analysis/` 内化模型负责。

### 子功能清单

#### 4.4.1 传播子图构建

| 属性 | 值 |
|------|-----|
| **优先级** | P0 |
| **状态** | 已完成 |
| **实现文件** | `core/propagation_legacy.py` → `build_propagation_graph()` |
| **描述** | 基于帖子的共享对象（URL/标签）时序关系构建 MultiDiGraph 传播图。采用"有界时序前驱规则"：每个分享者连接到最近的不同作者前驱（而非始终连接最早分享者），更准确地还原传播路径。同时提取评论回复关系作为显式边。输出含 `graph`（节点/边列表）、`claims`（共享对象级传播统计）、`evidence_chains`（证据链路径）。 |
| **依赖** | 数据采集（MongoDB `raw_posts`, `raw_comments`） |

#### 4.4.2 时间线与角色识别

| 属性 | 值 |
|------|-----|
| **优先级** | P0 |
| **状态** | 已完成 |
| **实现文件** | `core/propagation_legacy.py` → `_identify_key_roles()`, `_build_timeline()` |
| **描述** | 基于图拓扑分析识别三类关键角色：起爆节点（originators，最早发布且有出边）、桥接节点（bridges，介数中心性 top-N）、扩散节点（amplifiers，入度 top-N）。时间线按小时聚合帖子数量，标注关键事件节点。 |
| **依赖** | 传播子图构建 |

#### 4.4.3 规模趋势与下一跳联合预测

| 属性 | 值 |
|------|-----|
| **优先级** | P1 |
| **状态** | 已完成 |
| **实现文件** | `services/propagation_model_service.py`, `research/propagation_analysis/benchmark/adapters/event_adapter.py` |
| **描述** | 系统加载 Twitter `PropagationSequenceJointModel` checkpoint。用户序列经 RelationGNN、DynamicCasHGNN 和 SharedLSTM 形成共享状态；Macro 分支预测非负最终规模并用 Euler 连续动力学生成单调趋势；Micro 分支在合法 bucket 上打分，仅返回能够映射真实身份的当前事件再激活用户。输入严格截止于带时区的 `observed_until`。 |
| **依赖** | MongoDB 当前事件快照、系统内 checkpoint、PyTorch |

#### 4.4.4 LLM 增强趋势预测（关键技术）

| 属性 | 值 |
|------|-----|
| **优先级** | P1 |
| **状态** | 待 ARIS 工作空间实现 |
| **实现文件** | `core/propagation/llm_context.py`（已有框架） |
| **描述** | 通过 LLM API（DeepSeek/通义千问）从事件文本中提取外生事件（KOL 放大、官方回应、平台干预、叙事变异、协同爆发），采用多次调用多数投票机制提升鲁棒性。当前已实现完整的 prompt 模板、API 调用框架和投票逻辑，但生产环境需配置 `LLM_API_KEY` 后启用（当前默认 `mock_llm=True`）。 |
| **I/O 接口定义** | 输入：`event_summary: str, volumes: list[int], top_posts: list[str], coordination_signals: dict`；输出：`{events: [{type, evidence, confidence}], llm_available: bool}` |
| **依赖** | 趋势预测规则引擎、LLM API 配置 |

#### 4.4.5 立场检测

| 属性 | 值 |
|------|-----|
| **优先级** | P2 |
| **状态** | 待开发 |
| **实现文件** | 待创建 |
| **描述** | 对传播网络中的帖子进行立场分类（支持/反对/中立），分析不同立场在传播路径中的分布和演变。可结合 LLM 或预训练分类模型实现。 |
| **依赖** | 传播子图构建、数据采集 |

#### 4.4.6 危害性评估

| 属性 | 值 |
|------|-----|
| **优先级** | P2 |
| **状态** | 待开发 |
| **实现文件** | 待创建 |
| **描述** | 评估传播内容的社会危害程度，综合考虑传播范围、受众敏感度、内容煽动性等维度，输出危害性评分和分级。 |
| **依赖** | 传播子图构建、立场检测 |

#### 4.4.7 源头追溯

| 属性 | 值 |
|------|-----|
| **优先级** | P2 |
| **状态** | 待开发 |
| **实现文件** | 待创建 |
| **描述** | 基于传播图的拓扑结构和时序信息，反向追溯信息的原始来源。结合起爆节点识别和证据链分析，定位最可能的首发账户和首发平台。 |
| **依赖** | 传播子图构建、时间线与角色识别 |

---

## 4.5 报告研判 — 子功能清单与优先级

报告研判模块是系统的最终决策层，编排上游三大模块的输出，通过证据构建 → 阶段检测 → D-S 融合 → DISARM 评分的流水线生成结构化风险报告。核心实现位于 `app/core/risk/`。

### 子功能清单

#### 4.5.1 证据构建

| 属性 | 值 |
|------|-----|
| **优先级** | P0 |
| **状态** | 已完成 |
| **实现文件** | `core/risk/evidence_builder.py` |
| **描述** | 从协同、传播、账户三个上游模块的输出中提取结构化特征，构建统一 `EvidencePack`。特征维度包括：协同特征（coordination_density, edge_symmetry_mean, max_component_size, coordinated_account_ratio）、传播特征（bridge_ratio, originator_concentration, burstiness, cross_cluster_spread）、账户特征（automation_entropy, high_automation_ratio, regularity_mean）。内部使用 Gini 系数衡量分布集中度、Shannon 熵衡量自动化分布、变异系数衡量突发性。 |
| **依赖** | 协同发现、传播监控、账户画像 |

#### 4.5.2 阶段检测

| 属性 | 值 |
|------|-----|
| **优先级** | P0 |
| **状态** | 已完成 |
| **实现文件** | `core/risk/phase_detector.py` |
| **描述** | 将协同操纵事件建模为 5 个生命周期阶段：seed → synchronize → breakout → saturation → regeneration。基于窗口特征的规则分类（按优先级匹配：breakout > regeneration > saturation > synchronize > seed），结合 logistic hazard 模型估计各阶段转换风险概率。输出 `PhaseResult`：当前阶段、置信度、各转换 hazard 分数、breakout 预估时间。 |
| **依赖** | 证据构建 |

#### 4.5.3 D-S 证据融合

| 属性 | 值 |
|------|-----|
| **优先级** | P0 |
| **状态** | 已完成 |
| **实现文件** | `core/risk/ds_fusion.py` |
| **描述** | Dempster-Shafer 矛盾感知多源证据融合。将协同（操纵性）、传播（影响力）、账户（真实性）三个维度的证据转换为三元质量函数 `{risk, safe, uncertain}`，通过阶段感知质量调整（phase-conditioned mass adjustment）后，逐步执行 Dempster 组合规则。输出 `FusionResult`：三维度信念区间 `[belief, plausibility]`、总体信念区间、冲突质量（conflict_mass）、是否需要升级人工复核（escalation_required）。 |
| **依赖** | 证据构建、阶段检测 |

#### 4.5.4 DISARM 攻击路径评分

| 属性 | 值 |
|------|-----|
| **优先级** | P0 |
| **状态** | 已完成 |
| **实现文件** | `core/risk/disarm_scorer.py` |
| **描述** | 基于 DISARM Red Framework 构建技术转换图（12 个技术节点、18 条有向转换边），将上游证据映射到观测技术（如 T0101 Create Fake Accounts、T0105 Coordinate Activity 等）。评分攻击路径的深度（最长路径长度）、广度（涉及战术数）、完整度（覆盖技术比例），加权计算综合攻击路径分数。基于转换概率矩阵预测下一步可能技术，并从反制措施知识库推荐应对方案（含优先级排序）。 |
| **依赖** | 证据构建、D-S 证据融合 |

#### 4.5.5 报告生成

| 属性 | 值 |
|------|-----|
| **优先级** | P0 |
| **状态** | 已完成 |
| **实现文件** | `core/risk/report_builder.py` |
| **描述** | 组装所有分析结果为最终 JSON 报告。计算三维度评分（操纵性、真实性、影响力）和综合风险评分（0-100），映射风险等级（low/medium/high/critical）。生成可解释的风险因子列表和处置建议（含 DISARM 反制措施）。报告持久化到 MySQL `risk_assessments` 表，支持分页查询和详情查看。 |
| **依赖** | 阶段检测、D-S 证据融合、DISARM 攻击路径评分 |

#### 4.5.6 LLM 桥接

| 属性 | 值 |
|------|-----|
| **优先级** | P1 |
| **状态** | 占位（接口已定义） |
| **实现文件** | `core/risk/llm_bridge.py` |
| **描述** | 为后续 LLM 集成预留的三个接口：`generate_summary()`（风险报告自然语言摘要生成）、`explain_evidence()`（证据链叙事化解释）、`assess_complex_scenario()`（复杂场景辅助判断）。当前均返回 `None`，待 LLM API 配置后启用。 |
| **依赖** | 报告生成、LLM API 配置 |

#### 4.5.7 Agent + RAG 攻击分析（关键技术）

| 属性 | 值 |
|------|-----|
| **优先级** | P1 |
| **状态** | 待 ARIS 工作空间实现 |
| **实现文件** | 待创建 |
| **描述** | 基于 LLM Agent 架构 + RAG 检索增强，对 DISARM 攻击路径进行深度分析。Agent 自主检索历史案例库和 DISARM 知识库，结合当前证据包生成攻击意图推理、战术演进预测和定制化反制方案。该子功能为竞赛关键技术 Risk Review 的核心增强。 |
| **I/O 接口定义** | 输入：`{evidence_pack: EvidencePack, disarm_result: DisarmResult, case_db: VectorStore}`；输出：`{intent_analysis: str, tactic_prediction: list[dict], countermeasures: list[dict], confidence: float}` |
| **依赖** | DISARM 攻击路径评分、报告生成、LLM 桥接、案例入库与检索 |

#### 4.5.8 预警系统

| 属性 | 值 |
|------|-----|
| **优先级** | P2 |
| **状态** | 待开发 |
| **实现文件** | 待创建 |
| **描述** | 基于风险评分阈值和阶段转换 hazard 概率的自动预警机制。支持多级预警（蓝/黄/橙/红）、预警规则配置、通知推送（WebSocket/邮件）、预警历史记录。可触发自动风险评估流水线。 |
| **依赖** | 报告研判全流水线 |

#### 4.5.9 案例入库与检索

| 属性 | 值 |
|------|-----|
| **优先级** | P3 |
| **状态** | 待开发 |
| **实现文件** | 待创建 |
| **描述** | 将已完成的风险评估报告结构化入库（向量数据库），支持基于语义相似度的历史案例检索。为 Agent + RAG 攻击分析提供知识库支撑。 |
| **依赖** | 报告生成、向量数据库基础设施 |

---

## 4.6 分期规划

### P0：核心 MVP（已完成）

P0 阶段目标是构建完整的端到端分析流水线，覆盖从数据采集到风险报告生成的全链路。

| 子功能 | 所属模块 | 状态 |
|--------|----------|------|
| 共享对象协同检测 | 协同发现 | 已完成 |
| 协同网络可视化 | 协同发现 | 已完成 |
| 账户统计与群组统计 | 协同发现 | 已完成 |
| 传播子图构建 | 传播监控 | 已完成 |
| 时间线与角色识别 | 传播监控 | 已完成 |
| 证据构建 | 报告研判 | 已完成 |
| 阶段检测 | 报告研判 | 已完成 |
| D-S 证据融合 | 报告研判 | 已完成 |
| DISARM 攻击路径评分 | 报告研判 | 已完成 |
| 报告生成 | 报告研判 | 已完成 |

**P0 交付物**：可运行的全链路系统，支持手动触发数据采集 → 协同检测 → 传播分析 → 风险评估 → 报告查看。

### P1：关键技术集成 + 增强功能

P1 阶段聚焦三项竞赛关键技术的集成，以及 LLM 能力的启用。

| 子功能 | 所属模块 | 状态 | 备注 |
|--------|----------|------|------|
| 历史趋势规则脚手架 | 传播监测 | 兼容保留，非公开主路径 | 不得作为模型预测 fallback |
| 多任务框架协同检测 | 协同发现 | **待 ARIS 工作空间实现** | 关键技术 Coordination Discover / Detect |
| 规模趋势与下一跳联合预测 | 传播监测 | **系统推理已部署；正式研究验证未完成** | Propagation Analysis |
| Agent + RAG 攻击分析 | 报告研判 | **Student/Teacher seam 已接入；治理激活待完成** | Risk Review |
| LLM 桥接 | 报告研判 | 占位 | 接口已定义，待 LLM API 启用 |

**P1 交付物**：三项关键技术的算法实现 + 集成验证，LLM 能力从 mock 切换为真实调用。

### P2：扩展功能

P2 阶段扩展系统的分析深度和自动化程度。

| 子功能 | 所属模块 | 状态 |
|--------|----------|------|
| 多行为边构建 | 协同发现 | 待开发 |
| 显著性筛查 | 协同发现 | 待开发 |
| 立场检测 | 传播监控 | 待开发 |
| 危害性评估 | 传播监控 | 待开发 |
| 源头追溯 | 传播监控 | 待开发 |
| 预警系统 | 报告研判 | 待开发 |

**P2 交付物**：更丰富的分析维度 + 自动预警能力。

### P3：远期规划

| 子功能 | 所属模块 | 状态 |
|--------|----------|------|
| 案例入库与检索 | 报告研判 | 待开发 |

**P3 交付物**：知识积累与案例复用能力，支撑 Agent + RAG 的持续优化。

---

## 4.7 模块完成状态对照表（与 release-0.2 对齐）

| 模块 | 子功能 | 优先级 | 状态 | 实现文件 | 关键技术 |
|------|--------|:------:|------|----------|:--------:|
| **协同发现** | 共享对象协同检测 | P0 | 已完成 | `core/coordination/detector.py` | |
| | 协同网络可视化 | P0 | 已完成 | `core/coordination/network.py` | |
| | 账户统计与群组统计 | P0 | 已完成 | `core/coordination/stats.py` | |
| | 多任务框架协同检测 | P1 | 待 ARIS | 待创建 | Coordination Discover / Detect |
| | 多行为边构建 | P2 | 待开发 | 待创建 | |
| | 显著性筛查 | P2 | 待开发 | 待创建 | |
| **传播监控** | 传播子图构建 | P0 | 已完成 | `core/propagation_legacy.py` | |
| | 时间线与角色识别 | P0 | 已完成 | `core/propagation_legacy.py` | |
| | 规模趋势与下一跳联合预测 | P1 | 系统推理已部署，正式研究验证未完成 | `system/research/propagation_analysis/` | 严格时间切分、多 seed、概率校准 |
| | 立场检测 | P2 | 待开发 | 待创建 | |
| | 危害性评估 | P2 | 待开发 | 待创建 | |
| | 源头追溯 | P2 | 待开发 | 待创建 | |
| **报告研判** | 证据构建 | P0 | 已完成 | `core/risk/evidence_builder.py` | |
| | 阶段检测 | P0 | 已完成 | `core/risk/phase_detector.py` | |
| | D-S 证据融合 | P0 | 已完成 | `core/risk/ds_fusion.py` | |
| | DISARM 攻击路径评分 | P0 | 已完成 | `core/risk/disarm_scorer.py` | |
| | 报告生成 | P0 | 已完成 | `core/risk/report_builder.py` | |
| | LLM 桥接 | P1 | 占位 | `core/risk/llm_bridge.py` | |
| | Agent + RAG 攻击分析 | P1 | Student/Teacher 已接入，治理激活待完成 | `system/research/review_teacher/`, `system/runtimes/review_student/` | Risk Review |
| | 预警系统 | P2 | 待开发 | 待创建 | |
| | 案例入库与检索 | P3 | 待开发 | 待创建 | |

**统计摘要**：

- P0 子功能：10 个，全部已完成
- P1 子功能：5 个，1 个已完成，1 个占位，3 个待 ARIS 工作空间实现（关键技术）
- P2 子功能：6 个，全部待开发
- P3 子功能：1 个，待开发
- **总计**：22 个子功能，11 个已完成/占位，3 个关键技术待 ARIS，8 个待开发

---

# 第 5 章 技术接口与数据模型

本章定义 CogGuard 系统的全部 API 接口规范、数据库模型、缓存策略及模块间调用关系。已有接口基于现有代码精简描述并附代码引用，新增接口（监测看板、预警系统、报告管理）提供完整的请求/响应 JSON 结构定义。同时定义三个 ARIS 关键技术 I/O 接口的 dataclass 规范，作为算法模块与业务层的契约边界。

---

## 5.1 API 设计规范

### 5.1.1 统一响应格式

所有 API 端点返回统一 JSON 结构：

```json
{
  "code": 0,
  "data": "...",
  "msg": "ok"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | int | 状态码，0 表示成功，非 0 表示错误 |
| `data` | any | 业务数据，失败时为 `null` |
| `msg` | string | 提示信息 |

> 代码引用：`app/utils/response.py` — `success()` 函数

### 5.1.2 认证方式

- 认证协议：JWT Bearer Token
- 请求头：`Authorization: Bearer <access_token>`
- Token 类型：access_token（短期，含 user_id + role）、refresh_token（长期，仅含 user_id）
- 依赖注入：所有需鉴权端点通过 `Depends(get_current_user)` 保护

> 代码引用：`app/core/security.py` — `create_access_token()`, `create_refresh_token()`, `decode_token()`, `get_current_user()`

### 5.1.3 分页约定

分页参数统一使用 Query 参数：

| 参数 | 类型 | 默认值 | 约束 | 说明 |
|------|------|--------|------|------|
| `page` | int | 1 | >= 1 | 页码 |
| `page_size` | int | 20 | 1-100 | 每页条数 |

分页响应结构：

```json
{
  "code": 0,
  "data": {
    "total": 100,
    "items": [...]
  },
  "msg": "ok"
}
```
### 5.1.4 角色权限矩阵

系统定义三种角色：`admin`（管理员）、`analyst`（分析人员）、`viewer`（只读用户）。

| API 端点 | HTTP 方法 | admin | analyst | viewer | 说明 |
|----------|-----------|:-----:|:-------:|:------:|------|
| `/api/v1/auth/register` | POST | Y | Y | Y | 公开接口，无需认证 |
| `/api/v1/auth/login` | POST | Y | Y | Y | 公开接口，无需认证 |
| `/api/v1/auth/refresh` | POST | Y | Y | Y | 公开接口，无需认证 |
| `/api/v1/auth/profile` | GET | Y | Y | Y | 获取当前用户信息 |
| `/api/v1/crawl/platforms` | GET | Y | Y | Y | 查看支持平台（公开） |
| `/api/v1/crawl/social` | POST | Y | Y | - | 创建采集任务 |
| `/api/v1/crawl/jobs` | GET | Y | Y | Y | 查看任务列表 |
| `/api/v1/crawl/jobs/{id}` | DELETE | Y | Y | - | 删除采集任务 |
| `/api/v1/crawl/jobs/{id}/cancel` | POST | Y | Y | - | 取消采集任务 |
| `/api/v1/crawl/data` | GET | Y | Y | Y | 查询采集数据 |
| `/api/v1/coordination/detect` | POST | Y | Y | - | 执行协同检测 |
| `/api/v1/propagation/analyze` | GET | Y | Y | Y | 传播监控分析 |
| `/api/v1/propagation/model-event-predict` | POST | Y | Y | - | 当前事件规模趋势与下一跳预测 |
| `/api/v1/accounts/profiles` | GET | Y | Y | Y | 账户画像列表 |
| `/api/v1/accounts/detail/{id}` | GET | Y | Y | Y | 账户详情 |
| `/api/v1/risk/assess` | POST | Y | Y | - | 执行风险评估 |
| `/api/v1/risk/reports` | GET | Y | Y | Y | 风险报告列表 |
| `/api/v1/risk/reports/{id}` | GET | Y | Y | Y | 风险报告详情 |
| `/api/v1/dashboard/overview` | GET | Y | Y | Y | 监测看板概览 |
| `/api/v1/dashboard/trends` | GET | Y | Y | Y | 趋势数据 |
| `/api/v1/alerts` | GET | Y | Y | Y | 预警列表 |
| `/api/v1/alerts/{id}` | GET | Y | Y | Y | 预警详情 |
| `/api/v1/alerts/{id}/status` | PUT | Y | Y | - | 更新预警状态 |
| `/api/v1/reports` | GET | Y | Y | Y | 报告列表 |
| `/api/v1/reports/{id}` | GET | Y | Y | Y | 报告详情 |
| `/api/v1/reports/{id}/export` | POST | Y | Y | - | 导出报告 |

> 权限说明：`Y` = 允许访问，`-` = 禁止访问。viewer 角色仅可执行只读操作（GET），不可触发写入/计算类操作（POST/PUT/DELETE）。admin 拥有全部权限。

---

## 5.2 认证模块 API（/api/v1/auth/*）

> 代码引用：`app/api/v1/auth.py`、`app/schemas/auth.py`、`app/services/auth_service.py`

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/api/v1/auth/register` | POST | 否 | 用户注册，用户名/邮箱唯一校验 |
| `/api/v1/auth/login` | POST | 否 | 用户登录，返回 access_token + refresh_token |
| `/api/v1/auth/refresh` | POST | 否 | 刷新令牌，用 refresh_token 换取新令牌对 |
| `/api/v1/auth/profile` | GET | 是 | 获取当前用户脱敏信息 |

请求/响应结构引用：

- **RegisterRequest**：`{username, email, password}` → 返回 `UserInfo`
- **LoginRequest**：`{username, password}` → 返回 `TokenResponse{access_token, refresh_token, token_type}`
- **RefreshRequest**：`{refresh_token}` → 返回 `TokenResponse`
- **UserInfo**：`{id, username, email, role, is_active}`

---

## 5.3 数据采集模块 API（/api/v1/crawl/*）

> 代码引用：`app/api/v1/crawl.py`、`app/schemas/crawl.py`、`app/services/crawl_service.py`

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/api/v1/crawl/platforms` | GET | 否 | 返回支持的采集平台列表 |
| `/api/v1/crawl/social` | POST | 是 | 创建采集任务，触发 Celery 异步执行 |
| `/api/v1/crawl/jobs` | GET | 是 | 分页查询当前用户的采集任务列表 |
| `/api/v1/crawl/jobs/{job_id}` | DELETE | 是 | 删除任务及关联 MongoDB 数据 |
| `/api/v1/crawl/jobs/{job_id}/cancel` | POST | 是 | 取消排队/执行中的任务（revoke Celery） |
| `/api/v1/crawl/data` | GET | 是 | 分页查询 MongoDB 中的标准化帖子数据 |

请求/响应结构引用：

- **CrawlRequest**：`{platform, keywords[], post_ids[], max_posts, crawl_comments}`
- **CrawlJobResponse**：`{id, job_type, platform, status, progress, result_summary, created_at, finished_at}`
- **CrawlDataQuery**：`{platform?, keyword?, start_time?, end_time?, page, page_size}`
- 支持平台：`mock_weibo`、`weibo`、`douyin`、`xhs`、`news`

---

## 5.4 协同检测模块 API（/api/v1/coordination/*）

> 代码引用：`app/api/v1/coordination.py`、`app/services/coordination_service.py`

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/api/v1/coordination/detect` | POST | 是 | 对已采集数据执行协同行为检测 |

请求参数（Query）：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `time_window` | int | 60 | 协同时间窗口（秒），1-3600 |
| `min_participation` | int | 2 | 最低参与次数，>= 1 |
| `edge_weight` | float | 0.5 | 边权百分位阈值，0-1 |
| `platform` | string? | null | 限定平台 |

响应 `data` 结构：

```json
{
  "network": {
    "nodes": [{"id": "account_id", ...}],
    "edges": [{"source": "a1", "target": "a2", "weight": 5, "avg_time_delta": 3.2, "edge_symmetry_score": 0.8}],
    "node_count": 10,
    "edge_count": 15,
    "component_count": 2,
    "components": [{"size": 6, "members": ["a1", "a2", ...]}]
  },
  "account_stats": [{"account_id": "...", ...}],
  "group_stats": [{"component_id": 0, ...}],
  "summary": {
    "total_posts": 500,
    "total_pairs": 120,
    "coordinated_accounts": 10,
    "coordinated_edges": 15,
    "components": 2
  }
}
```

---

## 5.5 传播监控与趋势预测模块 API（/api/v1/propagation/*）

> 代码引用：`app/api/v1/propagation.py`、`app/services/propagation_observation_service.py`、`app/services/propagation_model_service.py`

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/api/v1/propagation/analyze` | GET | 是 | 分析已观测传播路径、对象、角色、证据和稳定性 |
| `/api/v1/propagation/model-event-predict` | POST | 是 | 严格时间截断后的规模趋势与下一跳再激活预测 |

请求参数（Query）：`platform?`、`event_id?`；预测端另支持 `top_k`、带时区的 `observed_until` 和小时级 `prediction_horizon`。

**analyze** 响应 `data`：传播图结构（节点角色分类、边权重、桥接节点、叙事聚类等）

**model-event-predict** 的核心响应 `data` 结构：

```json
{
  "status": "ok",
  "model_status": "available",
  "macro": {
    "observed_size": 120,
    "predicted_size": 185,
    "trend_points": [{"step": 1, "at": "2026-08-05T06:00:00+00:00", "predicted_size": 138}],
    "intervals": null,
    "calibration_status": "unavailable"
  },
  "micro": {
    "top_users": [{"rank": 1, "author_id": "u1", "author_name": "用户一", "activation_type": "reactivation", "evidence_refs": []}],
    "candidate_count": 42,
    "candidate_bucket_count": 3471,
    "coverage": {"mapped_probability_mass": 0.31, "new_activation_status": "abstain_no_identity_mapping"}
  },
  "data_scope": {"observed_until": "2026-08-05T00:00:00+00:00", "prediction_horizon_hours": 24}
}
```

---

## 5.6 账户监测模块 API（/api/v1/accounts/*）

> 代码引用：`app/api/v1/accounts.py`、`app/services/account_service.py`

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/api/v1/accounts/profiles` | GET | 是 | 获取所有账户行为画像列表 |
| `/api/v1/accounts/detail/{account_id}` | GET | 是 | 获取单个账户详细画像及近期帖子 |

请求参数（Query）：`platform?`（可选，限定平台）

**profiles** 响应 `data`：账户画像数组，每项含 `account_id`、`automation_score`、`regularity`、`post_count` 等

**detail** 响应 `data`：

```json
{
  "account_id": "user_001",
  "automation_score": 72.5,
  "regularity": 0.85,
  "post_count": 45,
  "recent_posts": [
    {"post_id": "...", "content": "...", "timestamp": "...", "likes": 10}
  ]
}
```

---

## 5.7 报告研判模块 API（/api/v1/risk/*）

> 代码引用：`app/api/v1/risk.py`、`app/schemas/risk.py`、`app/services/risk_service.py`

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/api/v1/risk/assess` | POST | 是 | 执行完整风险评估流水线 |
| `/api/v1/risk/reports` | GET | 是 | 分页查询历史风险报告列表 |
| `/api/v1/risk/reports/{report_id}` | GET | 是 | 获取单个风险报告完整 JSON |

**assess** 请求参数（Query）：

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `platform` | string? | null | 限定平台 |
| `time_window` | int | 60 | 协同检测时间窗口（秒） |
| `min_participation` | int | 2 | 最低参与次数 |
| `edge_weight` | float | 0.5 | 边权百分位阈值 |

**assess** 响应 `data` 结构（`RiskReportResponse`）：

```json
{
  "report_id": "uuid",
  "event_id": "weibo",
  "platform": "weibo",
  "assessed_at": "2026-04-29T10:00:00",
  "phase": {
    "current_phase": "synchronize",
    "phase_confidence": 0.78,
    "hazard_scores": {"breakout": 0.35, "saturation": 0.12, "regeneration": 0.05},
    "time_to_breakout_estimate": 5400.0,
    "window_count": 1
  },
  "scores": {
    "overall_risk_score": 62.5,
    "risk_level": "high",
    "manipulation": {"score": 70.0, "belief": 0.65, "plausibility": 0.82},
    "authenticity": {"score": 55.0, "belief": 0.50, "plausibility": 0.70},
    "impact": {"score": 60.0, "belief": 0.55, "plausibility": 0.75}
  },
  "fusion": {
    "conflict_mass": 0.15,
    "escalation_required": false,
    "per_source_masses": {"coordination": {}, "propagation": {}, "accounts": {}, "combined": {}}
  },
  "evidence": {"coordination": {}, "propagation": {}, "accounts": {}},
  "claims": [{"content": "...", "share_count": 10}],
  "disarm_analysis": {
    "observed_techniques": [{"technique_id": "T0105", "tactic": "TA10", "name": "Coordinate Activity", "belief": 0.8, "evidence": "..."}],
    "attack_path": {"depth": 3, "breadth": 4, "completeness": 0.45, "score": 55.0},
    "predicted_next": [{"technique_id": "T0049", "name": "Flood Information Space", "probability": 0.7}],
    "countermeasures": [{"technique_id": "T0049", "action": "部署信息洪水检测机制", "priority": "critical", "probability": 0.7}]
  },
  "risk_factors": {"manipulation_factors": [], "authenticity_factors": [], "impact_factors": []},
  "recommendations": [{"priority": "high", "action": "...", "reason": "..."}]
}
```

**reports** 请求参数（Query）：`platform?`、`risk_level?`、`phase?`、`page`、`page_size`

**reports** 响应 `data` 结构（`RiskReportListResponse`）：

```json
{
  "total": 50,
  "items": [
    {
      "report_id": "uuid",
      "event_id": "weibo",
      "platform": "weibo",
      "assessed_at": "2026-04-29T10:00:00",
      "overall_risk_score": 62.5,
      "risk_level": "high",
      "current_phase": "synchronize",
      "conflict_mass": 0.15,
      "escalation_required": false,
      "attack_path_score": 55.0
    }
  ]
}
```

---

## 5.8 监测看板 API（/api/v1/dashboard/*）— 新增设计

### 5.8.1 GET /api/v1/dashboard/overview

获取系统监测概览统计数据。

**请求参数（Query）：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `platform` | string | 否 | 限定平台，为空则全量统计 |
| `time_range` | string | 否 | 时间范围：`24h`/`7d`/`30d`，默认 `24h` |

**响应 `data` 结构：**

```json
{
  "stats": {
    "total_posts": 12580,
    "total_accounts": 3420,
    "active_crawl_jobs": 3,
    "completed_assessments": 28,
    "high_risk_events": 5,
    "critical_alerts": 2
  },
  "risk_distribution": {
    "low": 12,
    "medium": 8,
    "high": 5,
    "critical": 3
  },
  "phase_distribution": {
    "seed": 10,
    "synchronize": 8,
    "breakout": 3,
    "saturation": 5,
    "regeneration": 2
  },
  "platform_stats": [
    {
      "platform": "weibo",
      "post_count": 8500,
      "account_count": 2100,
      "avg_risk_score": 45.2,
      "latest_assessment_at": "2026-04-29T09:30:00"
    }
  ],
  "recent_activities": [
    {
      "type": "assessment",
      "description": "完成微博平台风险评估",
      "risk_level": "high",
      "timestamp": "2026-04-29T09:30:00"
    }
  ],
  "generated_at": "2026-04-29T10:00:00"
}
```

### 5.8.2 GET /api/v1/dashboard/trends

获取时间维度的趋势数据，用于看板图表渲染。

**请求参数（Query）：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `platform` | string | 否 | 限定平台 |
| `metric` | string | 否 | 指标类型：`posts`/`risk_score`/`accounts`/`alerts`，默认 `posts` |
| `time_range` | string | 否 | 时间范围：`24h`/`7d`/`30d`，默认 `7d` |
| `granularity` | string | 否 | 粒度：`hour`/`day`，默认自动（24h→hour, 7d/30d→day） |

**响应 `data` 结构：**

```json
{
  "metric": "posts",
  "time_range": "7d",
  "granularity": "day",
  "data_points": [
    {"timestamp": "2026-04-23T00:00:00", "value": 1200},
    {"timestamp": "2026-04-24T00:00:00", "value": 1580},
    {"timestamp": "2026-04-25T00:00:00", "value": 980},
    {"timestamp": "2026-04-26T00:00:00", "value": 2100},
    {"timestamp": "2026-04-27T00:00:00", "value": 1750},
    {"timestamp": "2026-04-28T00:00:00", "value": 1900},
    {"timestamp": "2026-04-29T00:00:00", "value": 850}
  ],
  "summary": {
    "total": 10360,
    "average": 1480.0,
    "max": 2100,
    "min": 850,
    "trend_direction": "stable"
  }
}
```

---

## 5.9 预警系统 API（/api/v1/alerts/*）— 新增设计

### 5.9.1 GET /api/v1/alerts

分页查询预警列表。

**请求参数（Query）：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `status` | string | 否 | 预警状态：`pending`/`acknowledged`/`resolved`/`dismissed` |
| `severity` | string | 否 | 严重程度：`info`/`warning`/`critical` |
| `platform` | string | 否 | 限定平台 |
| `start_time` | datetime | 否 | 起始时间 |
| `end_time` | datetime | 否 | 结束时间 |
| `page` | int | 否 | 页码，默认 1 |
| `page_size` | int | 否 | 每页条数，默认 20 |

**响应 `data` 结构：**

```json
{
  "total": 35,
  "items": [
    {
      "id": 1,
      "alert_type": "risk_threshold",
      "severity": "critical",
      "status": "pending",
      "title": "微博平台风险评分超过阈值",
      "summary": "微博平台综合风险评分达到 82.5（critical 级别），当前处于 breakout 阶段",
      "platform": "weibo",
      "related_report_id": "uuid-xxx",
      "risk_score": 82.5,
      "risk_level": "critical",
      "phase": "breakout",
      "triggered_at": "2026-04-29T08:15:00",
      "acknowledged_at": null,
      "resolved_at": null,
      "assigned_to": null
    }
  ]
}
```

### 5.9.2 GET /api/v1/alerts/{id}

获取单条预警详情。

**路径参数：** `id` — 预警 ID（int）

**响应 `data` 结构：**

```json
{
  "id": 1,
  "alert_type": "risk_threshold",
  "severity": "critical",
  "status": "pending",
  "title": "微博平台风险评分超过阈值",
  "summary": "微博平台综合风险评分达到 82.5（critical 级别），当前处于 breakout 阶段",
  "detail": {
    "trigger_condition": "overall_risk_score > 75",
    "actual_value": 82.5,
    "threshold": 75,
    "phase": "breakout",
    "hazard_breakout": 0.72,
    "coordinated_accounts": 25,
    "attack_path_score": 68.0
  },
  "platform": "weibo",
  "related_report_id": "uuid-xxx",
  "risk_score": 82.5,
  "risk_level": "critical",
  "phase": "breakout",
  "triggered_at": "2026-04-29T08:15:00",
  "acknowledged_at": null,
  "resolved_at": null,
  "assigned_to": null,
  "history": [
    {
      "action": "created",
      "operator": "system",
      "timestamp": "2026-04-29T08:15:00",
      "note": "风险评估自动触发"
    }
  ]
}
```

### 5.9.3 PUT /api/v1/alerts/{id}/status

更新预警状态（确认、解决、驳回）。

**路径参数：** `id` — 预警 ID（int）

**请求体：**

```json
{
  "status": "acknowledged | resolved | dismissed",
  "note": "已安排分析师跟进处理"
}
```

**响应 `data` 结构：**

```json
{
  "id": 1,
  "status": "acknowledged",
  "acknowledged_at": "2026-04-29T09:00:00",
  "updated_by": "admin_user",
  "note": "已安排分析师跟进处理"
}
```

**预警类型枚举（`alert_type`）：**

| 类型 | 说明 | 触发条件 |
|------|------|----------|
| `risk_threshold` | 风险阈值预警 | `overall_risk_score` 超过配置阈值 |
| `phase_transition` | 阶段转换预警 | 检测到阶段从低危向高危转换（如 synchronize → breakout） |
| `coordination_spike` | 协同异常预警 | 协同账户数或密度突增 |
| `propagation_burst` | 传播爆发预警 | 传播量 burst_zscore 超过阈值 |
| `conflict_escalation` | 证据冲突预警 | D-S 融合冲突质量超过阈值，需人工复核 |

---

## 5.10 报告管理 API（/api/v1/reports/*）— 新增设计

### 5.10.1 GET /api/v1/reports

分页查询综合分析报告列表。与 5.7 的 risk/reports 不同，此接口面向最终用户，提供格式化的可导出报告。

**请求参数（Query）：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `platform` | string | 否 | 限定平台 |
| `report_type` | string | 否 | 报告类型：`risk_assessment`/`periodic`/`incident` |
| `risk_level` | string | 否 | 风险等级筛选 |
| `start_time` | datetime | 否 | 起始时间 |
| `end_time` | datetime | 否 | 结束时间 |
| `page` | int | 否 | 页码，默认 1 |
| `page_size` | int | 否 | 每页条数，默认 20 |

**响应 `data` 结构：**

```json
{
  "total": 28,
  "items": [
    {
      "id": 1,
      "report_id": "uuid-xxx",
      "title": "微博平台认知操纵风险评估报告",
      "report_type": "risk_assessment",
      "platform": "weibo",
      "risk_level": "high",
      "overall_risk_score": 62.5,
      "current_phase": "synchronize",
      "summary": "检测到 10 个协同账户，传播处于同步阶段，综合风险评分 62.5（高风险）",
      "created_by": "analyst_user",
      "created_at": "2026-04-29T10:00:00",
      "export_formats": ["pdf", "docx", "json"]
    }
  ]
}
```

### 5.10.2 GET /api/v1/reports/{id}

获取单个报告详情，包含完整的结构化分析数据。

**路径参数：** `id` — 报告 ID（int 或 report_id UUID）

**响应 `data` 结构：**

```json
{
  "id": 1,
  "report_id": "uuid-xxx",
  "title": "微博平台认知操纵风险评估报告",
  "report_type": "risk_assessment",
  "platform": "weibo",
  "created_by": "analyst_user",
  "created_at": "2026-04-29T10:00:00",
  "content": {
    "executive_summary": "本次评估针对微博平台近期舆情数据...",
    "risk_assessment": {
      "overall_risk_score": 62.5,
      "risk_level": "high",
      "phase": "synchronize",
      "scores": {
        "manipulation": {"score": 70.0, "belief": 0.65, "plausibility": 0.82},
        "authenticity": {"score": 55.0, "belief": 0.50, "plausibility": 0.70},
        "impact": {"score": 60.0, "belief": 0.55, "plausibility": 0.75}
      }
    },
    "coordination_analysis": {
      "coordinated_accounts": 10,
      "components": 2,
      "key_findings": ["发现两个独立协同群组", "群组间存在桥接账户"]
    },
    "propagation_analysis": {
      "direction": "rising",
      "volume_forecast": {"1h": 120, "6h": 450, "24h": 800},
      "key_findings": ["传播速度加快", "检测到 KOL 放大事件"]
    },
    "disarm_analysis": {
      "observed_techniques": ["T0105 Coordinate Activity", "T0106 Amplify Existing Narrative"],
      "predicted_next": ["T0049 Flood Information Space"],
      "attack_path_score": 55.0
    },
    "recommendations": [
      {"priority": "high", "action": "监控协同账户集群活动", "reason": "..."}
    ]
  }
}
```

### 5.10.3 POST /api/v1/reports/{id}/export

导出报告为指定格式。

**路径参数：** `id` — 报告 ID

**请求体：**

```json
{
  "format": "pdf | docx | json",
  "include_charts": true,
  "include_raw_data": false,
  "language": "zh-CN"
}
```

**响应 `data` 结构：**

```json
{
  "export_id": "export-uuid",
  "report_id": "uuid-xxx",
  "format": "pdf",
  "status": "generating | completed | failed",
  "download_url": "/api/v1/reports/exports/export-uuid/download",
  "expires_at": "2026-04-30T10:00:00",
  "file_size": null
}
```

> 说明：报告导出为异步操作，客户端可轮询 `status` 或通过 WebSocket 接收完成通知。

---

## 5.11 MySQL 数据模型

### 5.11.1 已有模型

#### users 表（User）

> 代码引用：`app/models/user.py`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | Integer | PK, 自增 | 用户 ID |
| `username` | String(64) | UNIQUE, NOT NULL, INDEX | 用户名 |
| `email` | String(128) | UNIQUE, NOT NULL, INDEX | 邮箱 |
| `hashed_password` | String(256) | NOT NULL | 密码哈希 |
| `role` | String(16) | NOT NULL, DEFAULT 'analyst' | 角色：admin/analyst/viewer |
| `is_active` | Boolean | DEFAULT true | 是否激活 |
| `created_at` | DateTime | server_default=now() | 创建时间 |
| `updated_at` | DateTime | server_default=now(), onupdate | 更新时间 |

#### crawl_jobs 表（CrawlJob）

> 代码引用：`app/models/task.py`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | Integer | PK, 自增 | 任务 ID |
| `job_type` | String(32) | NOT NULL | 任务类型：social/news |
| `platform` | String(32) | NOT NULL | 平台名称 |
| `params_json` | Text | NOT NULL, DEFAULT '{}' | 任务参数 JSON |
| `status` | String(16) | NOT NULL, DEFAULT 'pending', INDEX | 状态：pending/running/completed/failed/cancelled |
| `progress` | Integer | DEFAULT 0 | 进度 0-100 |
| `result_summary` | Text | NULLABLE | 结果摘要 |
| `celery_task_id` | String(128) | NULLABLE | Celery 任务 ID |
| `created_by` | Integer | NOT NULL | 创建者用户 ID |
| `created_at` | DateTime | server_default=now() | 创建时间 |
| `finished_at` | DateTime | NULLABLE | 完成时间 |

#### risk_assessments 表（RiskAssessment）

> 代码引用：`app/models/risk_assessment.py`

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | Integer | PK, 自增 | 自增 ID |
| `report_id` | String(36) | UNIQUE, NOT NULL, INDEX | 报告 UUID |
| `event_id` | String(128) | NOT NULL, INDEX | 事件标识 |
| `platform` | String(32) | NOT NULL, INDEX | 平台 |
| `current_phase` | String(20) | NOT NULL, INDEX | 当前阶段 |
| `phase_confidence` | Float | NOT NULL | 阶段置信度 |
| `hazard_breakout` | Float | NOT NULL, DEFAULT 0.0 | breakout 风险概率 |
| `overall_risk_score` | Float | NOT NULL | 综合风险评分 0-100 |
| `risk_level` | String(16) | NOT NULL, INDEX | 风险等级：low/medium/high/critical |
| `manipulation_belief` | Float | NOT NULL | 操纵性信念值 |
| `authenticity_belief` | Float | NOT NULL | 真实性信念值 |
| `impact_belief` | Float | NOT NULL | 影响力信念值 |
| `conflict_mass` | Float | NOT NULL | D-S 冲突质量 |
| `escalation_required` | Integer | NOT NULL, DEFAULT 0 | 是否需要升级（0/1） |
| `attack_path_score` | Float | NOT NULL, DEFAULT 0.0 | DISARM 攻击路径评分 |
| `attack_path_depth` | Integer | NOT NULL, DEFAULT 0 | 攻击路径深度 |
| `report_json` | Text | NOT NULL | 完整报告 JSON |
| `assessed_by` | Integer | NOT NULL | 评估者用户 ID |
| `assessed_at` | DateTime | server_default=now() | 评估时间 |
| `updated_at` | DateTime | server_default=now(), onupdate | 更新时间 |

### 5.11.2 新增模型

#### alerts 表（Alert）— 新增

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | Integer | PK, 自增 | 预警 ID |
| `alert_type` | String(32) | NOT NULL, INDEX | 预警类型（见 5.9 枚举） |
| `severity` | String(16) | NOT NULL, INDEX | 严重程度：info/warning/critical |
| `status` | String(16) | NOT NULL, DEFAULT 'pending', INDEX | 状态：pending/acknowledged/resolved/dismissed |
| `title` | String(256) | NOT NULL | 预警标题 |
| `summary` | Text | NOT NULL | 预警摘要 |
| `detail_json` | Text | NULLABLE | 详细信息 JSON |
| `platform` | String(32) | NULLABLE, INDEX | 关联平台 |
| `related_report_id` | String(36) | NULLABLE, INDEX | 关联风险报告 UUID |
| `risk_score` | Float | NULLABLE | 触发时的风险评分 |
| `risk_level` | String(16) | NULLABLE | 触发时的风险等级 |
| `phase` | String(20) | NULLABLE | 触发时的阶段 |
| `triggered_at` | DateTime | NOT NULL, server_default=now() | 触发时间 |
| `acknowledged_at` | DateTime | NULLABLE | 确认时间 |
| `resolved_at` | DateTime | NULLABLE | 解决时间 |
| `assigned_to` | Integer | NULLABLE | 指派处理人用户 ID |
| `updated_by` | Integer | NULLABLE | 最后更新者用户 ID |
| `note` | Text | NULLABLE | 处理备注 |
| `created_at` | DateTime | server_default=now() | 创建时间 |
| `updated_at` | DateTime | server_default=now(), onupdate | 更新时间 |

#### reports 表（Report）— 新增

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | Integer | PK, 自增 | 报告 ID |
| `report_id` | String(36) | UNIQUE, NOT NULL, INDEX | 报告 UUID |
| `title` | String(256) | NOT NULL | 报告标题 |
| `report_type` | String(32) | NOT NULL, INDEX | 类型：risk_assessment/periodic/incident |
| `platform` | String(32) | NULLABLE, INDEX | 关联平台 |
| `risk_level` | String(16) | NULLABLE, INDEX | 风险等级 |
| `overall_risk_score` | Float | NULLABLE | 综合风险评分 |
| `current_phase` | String(20) | NULLABLE | 当前阶段 |
| `summary` | Text | NULLABLE | 报告摘要 |
| `content_json` | Text | NOT NULL | 完整报告内容 JSON |
| `source_assessment_id` | Integer | NULLABLE | 来源风险评估 ID |
| `created_by` | Integer | NOT NULL | 创建者用户 ID |
| `created_at` | DateTime | server_default=now() | 创建时间 |
| `updated_at` | DateTime | server_default=now(), onupdate | 更新时间 |

---

## 5.12 MongoDB 集合结构

> 代码引用：`app/models/post.py`（Pydantic schema，非 ORM）

### 5.12.1 raw_posts 集合

存储标准化后的帖子数据，由采集模块写入。

```json
{
  "platform": "weibo",
  "post_id": "4912345678",
  "content": "帖子正文内容...",
  "author_id": "user_001",
  "author_name": "用户昵称",
  "timestamp": "2026-04-29T08:00:00Z",
  "url": "https://weibo.com/...",
  "likes": 120,
  "reposts": 45,
  "comments_count": 30,
  "media_urls": ["https://..."],
  "hashtags": ["#话题标签#"],
  "crawl_job_id": 1,
  "raw_data": {},
  "created_at": "2026-04-29T08:05:00Z"
}
```

索引建议：
- `{platform: 1, timestamp: -1}` — 按平台+时间查询
- `{author_id: 1}` — 按作者查询
- `{crawl_job_id: 1}` — 按任务关联查询
- `{content: "text"}` — 全文搜索（关键词查询）

### 5.12.2 raw_comments 集合

存储标准化后的评论数据。

```json
{
  "platform": "weibo",
  "comment_id": "c_001",
  "post_id": "4912345678",
  "content": "评论内容...",
  "author_id": "user_002",
  "author_name": "评论者昵称",
  "timestamp": "2026-04-29T08:10:00Z",
  "reply_to": null,
  "likes": 5,
  "crawl_job_id": 1,
  "created_at": "2026-04-29T08:15:00Z"
}
```

索引建议：
- `{post_id: 1, timestamp: -1}` — 按帖子+时间查询
- `{author_id: 1}` — 按作者查询
- `{crawl_job_id: 1}` — 按任务关联查询

### 5.12.3 coordination_results 集合（P2 可选）

存储协同检测的历史结果快照，用于趋势对比分析。

```json
{
  "detection_id": "uuid",
  "platform": "weibo",
  "params": {"time_window": 60, "min_participation": 2, "edge_weight": 0.5},
  "summary": {"total_posts": 500, "coordinated_accounts": 10, "components": 2},
  "network_snapshot": {},
  "detected_at": "2026-04-29T10:00:00Z"
}
```

### 5.12.4 propagation_results 集合（P2 可选）

存储传播分析与趋势预测的历史结果。

```json
{
  "analysis_id": "uuid",
  "platform": "weibo",
  "analysis_type": "propagation | trend_prediction",
  "result": {},
  "analyzed_at": "2026-04-29T10:00:00Z"
}
```

---

## 5.13 Redis 缓存策略

### 5.13.1 缓存键命名规范

采用分层命名空间，格式：`cogguard:{module}:{resource}:{identifier}`

| 键模式 | 示例 | 说明 |
|--------|------|------|
| `cogguard:auth:token:{user_id}` | `cogguard:auth:token:42` | 用户活跃 Token 记录 |
| `cogguard:crawl:job_status:{job_id}` | `cogguard:crawl:job_status:15` | 采集任务实时状态 |
| `cogguard:crawl:job_progress:{job_id}` | `cogguard:crawl:job_progress:15` | 采集任务进度（0-100） |
| `cogguard:dashboard:overview:{platform}:{range}` | `cogguard:dashboard:overview:weibo:24h` | 看板概览缓存 |
| `cogguard:dashboard:trends:{metric}:{range}` | `cogguard:dashboard:trends:posts:7d` | 趋势数据缓存 |
| `cogguard:risk:latest:{platform}` | `cogguard:risk:latest:weibo` | 最新风险评估摘要 |
| `cogguard:alerts:unread_count:{user_id}` | `cogguard:alerts:unread_count:42` | 用户未读预警数 |
| `cogguard:rate_limit:{user_id}:{endpoint}` | `cogguard:rate_limit:42:assess` | API 限流计数器 |

### 5.13.2 缓存场景与 TTL

| 场景 | 键模式 | TTL | 淘汰策略 |
|------|--------|-----|----------|
| 采集任务状态 | `crawl:job_status:*` | 300s（5 分钟） | 任务完成时主动删除 |
| 采集任务进度 | `crawl:job_progress:*` | 60s（1 分钟） | Celery 回调更新 |
| 看板概览 | `dashboard:overview:*` | 120s（2 分钟） | 新评估完成时失效 |
| 趋势数据 | `dashboard:trends:*` | 300s（5 分钟） | 定时刷新 |
| 最新风险摘要 | `risk:latest:*` | 600s（10 分钟） | 新评估写入时更新 |
| 未读预警数 | `alerts:unread_count:*` | 60s（1 分钟） | 预警状态变更时失效 |
| API 限流 | `rate_limit:*` | 60s（滑动窗口） | 自动过期 |
| 会话 Token 黑名单 | `auth:blacklist:{jti}` | 与 Token 剩余有效期一致 | 自动过期 |

> 代码引用：`app/db/redis.py` — Redis 连接管理

---

## 5.14 模块间调用关系图（服务层编排）

> 代码引用：`app/services/` 目录下所有服务文件

以下 ASCII 图展示服务层的调用关系与数据流向：

```
                              ┌─────────────────────────────────────────┐
                              │            API 路由层 (FastAPI)          │
                              │  auth  crawl  coordination  propagation │
                              │  accounts  risk  dashboard  alerts      │
                              └──────┬──────┬──────┬──────┬──────┬──────┘
                                     │      │      │      │      │
                              ┌──────▼──────▼──────▼──────▼──────▼──────┐
                              │            服务层 (Services)             │
                              └──────┬──────┬──────┬──────┬──────┬──────┘
                                     │      │      │      │      │
          ┌──────────────────────────┼──────┼──────┼──────┼──────┘
          │                          │      │      │      │
          ▼                          ▼      │      ▼      ▼
  ┌──────────────┐  ┌──────────────────┐   │  ┌────────────────┐
  │ auth_service │  │  crawl_service   │   │  │account_service │
  │              │  │                  │   │  │                │
  │ register()   │  │ create_crawl_job │   │  │ get_profiles() │
  │ login()      │  │ update_status()  │   │  │ get_detail()   │
  │ refresh()    │  │ list_jobs()      │   │  └───────┬────────┘
  │ get_profile()│  │ delete_job()     │   │          │
  └──────┬───────┘  │ cancel_job()     │   │          │
         │          │ query_posts()    │   │          │
         │          └──────┬───────────┘   │          │
         │                 │               │          │
         ▼                 ▼               │          │
  ┌────────────┐   ┌─────────────┐        │          │
  │  security  │   │ Celery Task │        │          │
  │ (JWT/Hash) │   │ crawl_tasks │        │          │
  └────────────┘   └──────┬──────┘        │          │
                          │               │          │
                          ▼               │          │
                   ┌─────────────┐        │          │
                   │   Crawler   │        │          │
                   │   Factory   │        │          │
                   │ mock/social │        │          │
                   │ /news       │        │          │
                   └──────┬──────┘        │          │
                          │               │          │
                          ▼               │          │
                   ┌─────────────┐        │          │
                   │  MongoDB    │        │          │
                   │ raw_posts   │◄───────┼──────────┘
                   │ raw_comments│        │
                   └──────┬──────┘        │
                          │               │
          ┌───────────────┼───────────────┤
          │               │               │
          ▼               ▼               ▼
  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
  │ coordination │ │ propagation  │ │   risk_service    │
  │ _service     │ │ _service     │ │                   │
  │              │ │              │ │ assess_risk()     │
  │ run_detect() │ │ analyze()    │ │  ├→ coord_service │
  └──────┬───────┘ │ predict()    │ │  ├→ prop_service  │
         │         └──────┬───────┘ │  ├→ acct_service  │
         │                │         │  │                 │
         ▼                ▼         │  ▼                 │
  ┌──────────────┐ ┌──────────────┐│ ┌─────────────────┐│
  │  core/       │ │  core/       ││ │  core/risk/     ││
  │ coordination │ │ propagation  ││ │                 ││
  │              │ │              ││ │ evidence_builder││
  │ detector     │ │ ts_features  ││ │ phase_detector  ││
  │ network      │ │ llm_context  ││ │ ds_fusion       ││
  │ stats        │ │ regime_model ││ │ disarm_scorer   ││
  └──────────────┘ │ trend_predict││ │ report_builder  ││
                   └──────────────┘│ │ llm_bridge      ││
                                   │ └─────────────────┘│
                                   │         │          │
                                   │         ▼          │
                                   │  ┌─────────────┐   │
                                   │  │   MySQL      │   │
                                   │  │ risk_assess- │   │
                                   │  │ ments        │   │
                                   │  └─────────────┘   │
                                   └────────────────────┘
```

**关键调用链路：**

1. **风险评估全链路**：`risk_service.assess_risk()` → 并行调用 `coordination_service` + `propagation_service` + `account_service` → `evidence_builder` → `phase_detector` → `ds_fusion` → `disarm_scorer` → `report_builder` → 持久化 MySQL
2. **数据采集链路**：`crawl_service.create_crawl_job()` → Celery `execute_crawl_job` → `CrawlerFactory` → 写入 MongoDB
3. **传播预测链路**：`propagation_model_service.predict_current_event_model()` → 时间截断 → `PropagationSequenceJointModel` → Macro 趋势与实名 Micro 排序

---

## 5.15 关键技术 I/O 接口定义（ARIS 边界，@version: v1）

本节定义三个 ARIS（Algorithm-Runtime Interface Specification）关键技术接口，作为算法核心模块与业务服务层的契约边界。所有接口使用 Python `dataclass` 格式定义，确保类型安全和可序列化。

> 代码引用：`app/core/coordination/detector.py`、`app/services/propagation_model_service.py`、`system/research/propagation_analysis/benchmark/adapters/event_adapter.py`、`app/core/risk/disarm_scorer.py`

### 5.15.1 协同检测接口（@version: v1）

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class CoordinationDetectionInput:
    """协同检测输入。@version: v1

    由 coordination_service 从 MongoDB 原始数据构建，
    传入 core/coordination 算法模块。
    """
    # 共享行为记录表（必须包含 object_id, account_id, content_id, timestamp_share）
    records: list[dict] = field(default_factory=list)

    # 检测参数
    time_window: int = 60               # 协同时间窗口（秒），1-3600
    min_participation: int = 2           # 最低参与次数
    edge_weight_percentile: float = 0.5  # 边权百分位阈值，0-1
    remove_loops: bool = True            # 是否移除自环

    # 可选上下文
    platform: str | None = None          # 限定平台


@dataclass
class CoordinationDetectionOutput:
    """协同检测输出。@version: v1

    由 core/coordination 算法模块产出，
    供 risk_service 的证据构建器消费。
    """
    # 网络结构
    network: dict = field(default_factory=dict)
    # 结构: {nodes: [{id, ...}], edges: [{source, target, weight, avg_time_delta, edge_symmetry_score}],
    #        node_count, edge_count, component_count, components: [{size, members}]}

    # 统计信息
    account_stats: list[dict] = field(default_factory=list)  # 每账户统计
    group_stats: list[dict] = field(default_factory=list)     # 每组件统计

    # 摘要
    total_posts: int = 0
    total_pairs: int = 0
    coordinated_accounts: int = 0
    coordinated_edges: int = 0
    component_count: int = 0

    # 错误信息（非空时表示检测失败）
    error: str | None = None
```

### 5.15.2 趋势预测接口（@version: v1）

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class TrendPredictionInput:
    """趋势预测输入。@version: v1

    由 propagation_service 从 MongoDB 原始数据构建，
    传入当前事件传播序列模型。以下 v1 结构为历史兼容契约，不是公开模型接口。
    """
    # 帖子列表（必须包含 timestamp 字段）
    posts: list[dict] = field(default_factory=list)

    # 评论列表（可选，预留接口）
    comments: list[dict] | None = None

    # Coordination Discover / Detect 协同检测信号（可选，跨模块输入）
    coordination_signals: dict[str, Any] | None = None

    # 控制参数
    mock_llm: bool = False               # 是否跳过 LLM API 调用
    forecast_horizons: list[float] = field(default_factory=lambda: [1.0, 6.0, 24.0])  # 预测时间跨度（小时）

    # 可选上下文
    platform: str | None = None


@dataclass
class TrendPredictionOutput:
    """趋势预测输出。@version: v1

    历史兼容结构；当前公开模型输出以 5.5 节的 macro/micro 契约为准，
    供前端看板和风险评估消费。
    """
    # 传播量预测
    volume_forecast: dict[str, int] = field(default_factory=dict)
    # 结构: {"1h": 120, "6h": 450, "24h": 800}

    # 置信区间
    confidence_interval: dict[str, list[int]] = field(default_factory=dict)
    # 结构: {"1h": [80, 160], "6h": [300, 600], "24h": [500, 1100]}

    # 方向判断
    direction: str = "stable"  # rising | stable | declining

    # 速度信息
    speed: dict = field(default_factory=dict)
    # 结构: {"acceleration": 2.5, "phase": "amplification"}

    # 体制后验概率
    regime_posterior: dict[str, float] = field(default_factory=dict)
    # 结构: {"seeding": 0.1, "amplification": 0.6, "peak": 0.2, "decay": 0.1}

    # 检测到的外生事件
    detected_events: list[dict] = field(default_factory=list)
    # 每项: {"type": "kol_amplification", "evidence": "...", "confidence": 0.8}

    # 预测置信度（0-1）
    confidence: float = 0.0

    # 中文趋势解释
    explanation: str = ""

    # LLM 是否可用
    llm_available: bool = False

    # 时序特征摘要
    ts_features: dict = field(default_factory=dict)
    # 结构: {current_volume, velocity, acceleration, burst_zscore, hours_since_start}
```

### 5.15.3 攻击分析接口（@version: v1）

```python
from dataclasses import dataclass, field

@dataclass
class AttackAnalysisInput:
    """DISARM 攻击路径分析输入。@version: v1

    由 risk_service 在风险评估流水线中构建，
    传入 core/risk/disarm_scorer 模块。
    """
    # 上游证据包（由 evidence_builder 构建）
    evidence_pack: "EvidencePack" = None  # type: ignore

    # 阶段检测结果（由 phase_detector 产出）
    phase_result: "PhaseResult" = None    # type: ignore

    # D-S 融合结果（由 ds_fusion 产出）
    fusion_result: "FusionResult" = None  # type: ignore

    # 可选配置覆盖
    config_overrides: dict = field(default_factory=dict)


@dataclass
class ObservedTechniqueItem:
    """观测到的 DISARM 技术。"""
    technique_id: str = ""    # 如 "T0105"
    tactic: str = ""          # 如 "TA10"
    name: str = ""            # 如 "Coordinate Activity"
    belief: float = 0.0       # 信念值 0-1
    evidence: str = ""        # 证据描述


@dataclass
class PredictedTechniqueItem:
    """预测的下一步技术。"""
    technique_id: str = ""
    name: str = ""
    probability: float = 0.0  # 转换概率 0-1


@dataclass
class CountermeasureItem:
    """反制建议。"""
    technique_id: str = ""
    action: str = ""           # 反制措施描述
    priority: str = ""         # critical/high/medium/low
    probability: float = 0.0   # 关联概率


@dataclass
class AttackPathScoreItem:
    """攻击路径评分。"""
    depth: int = 0             # 路径深度（经过的战术阶段数）
    breadth: int = 0           # 路径广度（观测到的技术数）
    completeness: float = 0.0  # 完整度（覆盖的战术比例）
    score: float = 0.0         # 综合评分 0-100


@dataclass
class AttackAnalysisOutput:
    """DISARM 攻击路径分析输出。@version: v1

    由 core/risk/disarm_scorer 产出，
    供 report_builder 组装最终报告。
    """
    # 观测到的 DISARM 技术列表
    observed_techniques: list[ObservedTechniqueItem] = field(default_factory=list)

    # 攻击路径评分
    path_score: AttackPathScoreItem = field(default_factory=AttackPathScoreItem)

    # 预测的下一步技术
    predicted_next: list[PredictedTechniqueItem] = field(default_factory=list)

    # 反制建议（按优先级排序）
    countermeasures: list[CountermeasureItem] = field(default_factory=list)
```

---

# 附录

## 附录 A：现有代码文件清单与状态

> 基于 `G:\CISCN\cogguard_system\new-system\backend\app\` 目录扫描

| 模块 | 文件路径 | 状态 | 说明 |
|------|----------|------|------|
| **入口** | `main.py` | 已实现 | FastAPI 应用入口 |
| **入口** | `config.py` | 已实现 | 配置管理（环境变量） |
| **入口** | `celery_app.py` | 已实现 | Celery 应用实例 |
| **API 路由** | `api/v1/router.py` | 已实现 | 路由注册 |
| **API 路由** | `api/v1/auth.py` | 已实现 | 认证接口 |
| **API 路由** | `api/v1/crawl.py` | 已实现 | 数据采集接口 |
| **API 路由** | `api/v1/coordination.py` | 已实现 | 协同检测接口 |
| **API 路由** | `api/v1/propagation.py` | 已实现 | 传播监控接口 |
| **API 路由** | `api/v1/accounts.py` | 已实现 | 账户监测接口 |
| **API 路由** | `api/v1/risk.py` | 已实现 | 报告研判接口 |
| **API 路由** | `api/v1/dashboard.py` | 待开发 | 监测看板接口 |
| **API 路由** | `api/v1/alerts.py` | 待开发 | 预警系统接口 |
| **API 路由** | `api/v1/reports.py` | 待开发 | 报告管理接口 |
| **数据模型** | `models/user.py` | 已实现 | 用户 ORM |
| **数据模型** | `models/task.py` | 已实现 | 采集任务 ORM |
| **数据模型** | `models/post.py` | 已实现 | MongoDB 文档 Schema |
| **数据模型** | `models/risk_assessment.py` | 已实现 | 风险评估 ORM |
| **数据模型** | `models/alert.py` | 待开发 | 预警 ORM |
| **数据模型** | `models/report.py` | 待开发 | 报告 ORM |
| **Schema** | `schemas/auth.py` | 已实现 | 认证请求/响应 |
| **Schema** | `schemas/crawl.py` | 已实现 | 采集请求/响应 |
| **Schema** | `schemas/risk.py` | 已实现 | 风险请求/响应 |
| **服务层** | `services/auth_service.py` | 已实现 | 认证业务逻辑 |
| **服务层** | `services/crawl_service.py` | 已实现 | 采集业务逻辑 |
| **服务层** | `services/coordination_service.py` | 已实现 | 协同检测编排 |
| **服务层** | `services/propagation_service.py` | 已实现 | 传播分析编排 |
| **服务层** | `services/account_service.py` | 已实现 | 账户画像编排 |
| **服务层** | `services/risk_service.py` | 已实现 | 风险评估流水线 |
| **服务层** | `services/dashboard_service.py` | 待开发 | 看板数据聚合 |
| **服务层** | `services/alert_service.py` | 待开发 | 预警管理 |
| **服务层** | `services/report_service.py` | 待开发 | 报告管理 |
| **核心算法** | `system/research/coordination_discover/` | artifact-first 已接入 | Coordination Discover；baseline 仅作 fallback |
| **核心算法** | `core/coordination/network.py` | 已实现 | 协同网络构建 |
| **核心算法** | `core/coordination/stats.py` | 已实现 | 协同统计 |
| **核心算法** | `core/propagation/ts_features.py` | 已实现 | 时序特征提取 |
| **核心算法** | `core/propagation/llm_context.py` | 已实现 | LLM 事件提取 |
| **核心算法** | `core/propagation/regime_model.py` | 已实现 | 体制切换模型 |
| **历史兼容** | `core/propagation/trend_predictor.py` | 保留 | 非公开速度/加速度脚手架，不得作为 fallback |
| **核心算法** | `core/risk/evidence_builder.py` | 已实现 | 证据构建器 |
| **核心算法** | `core/risk/phase_detector.py` | 已实现 | 阶段检测器 |
| **核心算法** | `core/risk/ds_fusion.py` | 已实现 | D-S 证据融合 |
| **核心算法** | `core/risk/disarm_scorer.py` | 已实现 | DISARM 攻击路径评分 |
| **核心算法** | `core/risk/report_builder.py` | 已实现 | 报告组装 |
| **核心算法** | `core/risk/llm_bridge.py` | 占位 | LLM 桥接（预留接口） |
| **核心算法** | `core/account_profiler.py` | 已实现 | 账户行为画像 |
| **采集器** | `core/crawler/factory.py` | 已实现 | 爬虫工厂 |
| **采集器** | `core/crawler/mock.py` | 已实现 | 模拟爬虫 |
| **采集器** | `core/crawler/social.py` | 已实现 | 社交平台爬虫 |
| **采集器** | `core/crawler/news.py` | 已实现 | 新闻爬虫 |
| **采集器** | `core/crawler/normalizer.py` | 已实现 | 数据标准化 |
| **基础设施** | `core/security.py` | 已实现 | JWT + 密码哈希 |
| **基础设施** | `db/mysql.py` | 已实现 | MySQL 连接管理 |
| **基础设施** | `db/mongodb.py` | 已实现 | MongoDB 连接管理 |
| **基础设施** | `db/redis.py` | 已实现 | Redis 连接管理 |
| **基础设施** | `tasks/crawl_tasks.py` | 已实现 | Celery 采集任务 |
| **工具** | `utils/response.py` | 已实现 | 统一响应封装 |
| **工具** | `utils/exceptions.py` | 已实现 | 自定义异常 |
| **工具** | `utils/logger.py` | 已实现 | 日志配置 |

---

## 附录 B：DISARM 技术知识库映射表

> 代码引用：`app/core/risk/disarm_scorer.py` — `TECHNIQUE_INFO`、`TRANSITIONS`、`TRANSITION_PROBS`、`COUNTERMEASURES`

### B.1 技术清单

| 技术 ID | 战术 ID | 技术名称 | 说明 |
|---------|---------|----------|------|
| T0097 | TA06 | Create Fake Experts | 创建虚假专家身份 |
| T0098 | TA06 | Establish Legitimacy | 建立合法性 |
| T0100 | TA07 | Co-opt Trusted Sources | 劫持可信来源 |
| T0101 | TA08 | Create Fake Social Media Accounts | 创建虚假社交媒体账户 |
| T0102 | TA08 | Develop Inauthentic Networks | 发展非真实网络 |
| T0103 | TA09 | Post Content | 发布内容 |
| T0104 | TA09 | Social Media Sharing | 社交媒体分享 |
| T0105 | TA10 | Coordinate Activity | 协同活动 |
| T0106 | TA10 | Amplify Existing Narrative | 放大现有叙事 |
| T0107 | TA10 | Manipulate Platform Algorithms | 操纵平台算法 |
| T0049 | TA10 | Flood Information Space | 信息洪水 |
| T0108 | TA11 | Encourage Real-World Action | 鼓励线下行动 |

### B.2 技术转换图（攻击路径推进）

```
T0097 ──→ T0100 ──→ T0103 ──→ T0104 ──→ T0105 ──→ T0106 ──→ T0049 ──→ T0108
  │          │          │          │          │          │
  └──→ T0103 └──→ T0104 └──→ T0106 └──→ T0106 └──→ T0049 └──→ T0107 ──→ T0049

T0101 ──→ T0102 ──→ T0105
  │          │
  └──→ T0103 └──→ T0103
```

### B.3 转换概率矩阵

| 源技术 | 目标技术 | 转换概率 | 说明 |
|--------|----------|----------|------|
| T0101 | T0102 | 0.80 | 虚假账户 → 非真实网络 |
| T0101 | T0103 | 0.50 | 虚假账户 → 发布内容 |
| T0102 | T0105 | 0.70 | 非真实网络 → 协同活动 |
| T0102 | T0103 | 0.60 | 非真实网络 → 发布内容 |
| T0103 | T0104 | 0.70 | 发布内容 → 社交分享 |
| T0103 | T0106 | 0.50 | 发布内容 → 放大叙事 |
| T0104 | T0105 | 0.60 | 社交分享 → 协同活动 |
| T0104 | T0106 | 0.70 | 社交分享 → 放大叙事 |
| T0105 | T0106 | 0.90 | 协同活动 → 放大叙事（最高概率） |
| T0105 | T0049 | 0.50 | 协同活动 → 信息洪水 |
| T0106 | T0049 | 0.70 | 放大叙事 → 信息洪水 |
| T0106 | T0107 | 0.40 | 放大叙事 → 操纵算法 |
| T0097 | T0100 | 0.60 | 虚假专家 → 劫持可信来源 |
| T0097 | T0103 | 0.50 | 虚假专家 → 发布内容 |
| T0100 | T0103 | 0.70 | 劫持可信来源 → 发布内容 |
| T0100 | T0104 | 0.50 | 劫持可信来源 → 社交分享 |
| T0049 | T0108 | 0.40 | 信息洪水 → 线下行动 |
| T0107 | T0049 | 0.60 | 操纵算法 → 信息洪水 |

### B.4 反制措施知识库

| 技术 ID | 反制措施 | 优先级 |
|---------|----------|--------|
| T0101 | 加强账户注册验证与异常检测 | medium |
| T0102 | 监控异常网络结构形成 | medium |
| T0103 | 内容审核与来源标注 | low |
| T0104 | 限制可疑账户的分享频率 | medium |
| T0105 | 监控协同账户集群活动 | high |
| T0106 | 限制标记账户的放大能力 | high |
| T0107 | 平台算法透明度审计 | medium |
| T0049 | 部署信息洪水检测机制 | critical |
| T0108 | 线下行动预警与快速响应 | critical |
| T0097 | 专家身份核实机制 | medium |
| T0100 | 可信来源保护与劫持检测 | high |

---

## 附录 C：风险等级与阶段定义

> 代码引用：`app/core/risk/phase_detector.py`、`app/core/risk/report_builder.py`

### C.1 风险等级定义

风险等级由综合风险评分（`overall_risk_score`，0-100）映射得出。评分公式基于 D-S 融合后的信念区间：`score = (belief × 0.7 + plausibility × 0.3) × 100`。

| 风险等级 | 评分范围 | 颜色标识 | 处置建议 |
|----------|----------|----------|----------|
| `low` | 0 - 25 | 绿色 | 常规监控，无需特别关注 |
| `medium` | 26 - 50 | 黄色 | 加强监控，关注趋势变化 |
| `high` | 51 - 75 | 橙色 | 重点关注，安排分析师跟进 |
| `critical` | 76 - 100 | 红色 | 立即启动应急响应 |

> 代码引用：`app/core/risk/report_builder.py` — `_risk_level()` 函数，阈值可通过 `risk_config.yaml` 的 `scoring.levels` 配置。

### C.2 战役生命周期阶段定义

CogGuard 将认知操纵事件建模为 5 个阶段的生命周期，基于滑动窗口特征提取 + 规则分类 + logistic hazard 估计进行阶段判定。

| 阶段 | 英文标识 | 特征描述 | 关键指标 |
|------|----------|----------|----------|
| 播种期 | `seed` | 初始阶段，少量账户开始发布内容，协同密度低，传播平缓 | coordination_density < 0.05, burstiness < 1.0 |
| 同步期 | `synchronize` | 协同行为开始显现，多账户同步发布，但尚未爆发 | coordination_density >= 0.05, burstiness < 2.0 |
| 爆发期 | `breakout` | 传播量急剧增长，跨群扩散，桥接节点活跃 | burstiness >= 2.0, bridge_ratio >= 0.1 |
| 饱和期 | `saturation` | 传播趋于饱和，增速放缓，覆盖范围广 | burstiness < 1.5, cross_cluster_spread >= 3 |
| 再生期 | `regeneration` | 新账户或新策略出现，自动化行为熵值变化显著 | automation_entropy_delta >= 0.3 |

### C.3 阶段转换风险估计

使用 logistic 模型估计各阶段转换的风险概率：

```
P(transition) = sigmoid(w_burst × burstiness + w_bridge × bridge_ratio
                       + w_auto × high_automation_ratio + w_coord × coordination_density + bias)
```

默认权重参数（可通过 `risk_config.yaml` 的 `phase.hazard_weights` 配置）：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `w_burstiness` | 1.2 | 突发性权重 |
| `w_bridge_ratio` | 2.0 | 桥接比例权重 |
| `w_high_automation_ratio` | 1.5 | 高自动化比例权重 |
| `w_coordination_density` | 1.8 | 协同密度权重 |
| `bias` | -3.0 | 偏置项 |

输出三个转换风险概率：

| 转换 | 计算方式 | 说明 |
|------|----------|------|
| `hazard_breakout` | `sigmoid(logit)` | 向爆发期转换的风险 |
| `hazard_saturation` | `sigmoid(logit × 0.6)` | 向饱和期转换的风险 |
| `hazard_regeneration` | `sigmoid(logit × 0.3)` | 向再生期转换的风险 |

### C.4 Breakout 预估时间

当处于 `seed` 或 `synchronize` 阶段且 `hazard_breakout > 0.1` 时，系统估计到达 breakout 的时间：

```
time_to_breakout = max(300, (1 - hazard_breakout) / hazard_breakout × 3600)  # 秒
```

| hazard_breakout | 预估时间 | 说明 |
|-----------------|----------|------|
| 0.1 | ~9 小时 | 低风险，充裕响应时间 |
| 0.3 | ~2.3 小时 | 中等风险，需关注 |
| 0.5 | 1 小时 | 高风险，建议立即干预 |
| 0.7 | ~25 分钟 | 极高风险，紧急响应 |
| 0.9 | ~6.7 分钟 | 临界状态，即将爆发 |

### C.5 D-S 证据融合维度

风险评估的三个核心维度及其证据来源：

| 维度 | 英文标识 | 证据来源 | 评估内容 |
|------|----------|----------|----------|
| 操纵性 | `manipulation` | 协同检测模块 | 协同密度、边对称性、协同账户比例 |
| 行为真实性 | `authenticity` | 账户监测模块 | 自动化比例、行为熵、规律性 |
| 影响力 | `impact` | 传播监控模块 | 桥接比例、突发性、跨集群传播 |

融合流程：各维度独立计算信念质量函数 → 阶段感知调制 → Dempster 组合规则逐步融合 → 冲突检测（阈值默认 0.3）→ 输出信念区间 `[belief, plausibility]`。

> 当冲突质量超过阈值时，`escalation_required = true`，系统自动生成"证据冲突预警"，提示分析师人工复核。
