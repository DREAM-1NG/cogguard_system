# CogGuard 设计方案与开发进度

> **用途**：记录当前工程状态、模块优先级、剩余开发任务和已通过验证。  
> **受众**：开发者、项目维护者、后续执行任务的 AI agent。  
> **维护规则**：只维护可执行工程路线和状态；研究定位、文献依据和关键技术背景放入 `../research/`。

> 最后更新：2026-08-11

## 2026-08-11 Case Workbench 原型闭环

- [x] 新增 `/api/v2/cases` 读模型 MVP，面向特朗普访华归档案例聚合 Event Snapshot、Analysis Run、权威主张、语义辅助、处置项、反馈入口和报告版本占位。
- [x] 新增显式 `semantic_enrichment` Analysis Stage；默认 Analysis Run 四阶段保持不变，Case 编排才显式请求语义阶段。
- [x] 语义辅助已覆盖情感、关键词、主题、实体、近重复、社区差异和立场；当前使用轻量确定性覆盖层和固定候选模型标识，状态保持 `candidate_unvalidated`，不改变 Coordination Discover、Propagation Analysis 或 Risk Review 分数。
- [x] 前端新增“案例闭环”入口和 C 型密集五标签工作台：概览 / 证据矩阵 / 图谱 / 处置 / 报告。
- [x] 新增进程内 demo mutation：处置项完成/豁免、反馈提交、结案复核提交，可支撑演示从静态展示进入实际操作闭环。
- [ ] 完整 SQLAlchemy Case/Authority/Claim/Action/Report/Audit 持久化模型、Alembic 迁移、真实报告 HTML/PDF 文件服务、权限细分和端到端结案仍待后续迭代；当前原型先满足演示闭环。

## 2026-08-01 状态收口

- [x] 安全与部署阻塞收口：生产秘密强制配置、Preview 旁路默认关闭、Compose 凭据必填。
- [x] Analysis Run、SSE `Last-Event-ID` 恢复、阶段 Artifact Manifest 和 active model pointer 已通过后端回归测试。
- [x] Canonical Verdict、反馈持久化、双人模型激活、回滚决策和本地 SHA-256 artifact 校验已接通。
- [x] 本地原型验收脚本已贯通 EventSnapshot、Coordination Discover、Propagation Analysis、Student Review 和 Teacher Review，并明确输出 fallback/shadow/advisory/non-claimable 状态。
- [ ] 研究级 Coordination Discover、Propagation Analysis 和 Student/Teacher checkpoint 尚未因缺少批准 artifact 而声明为可研究主张结果；Social Bot Detection 的 BotRHG Weibo transfer 已有真实 checkpoint，但当前指标低于同切分 TF-IDF 参考，研究 claim 仍 blocked。
- [x] 前端 `npm run build`（包含 `vue-tsc -b`）已通过；本轮不修改前端展示页面。
- [ ] 真实 MySQL/Mongo/Redis/Celery 部署 smoke 和 GPU 长实验仍需在具备对应环境时执行。

## 技术决策记录

### 已确定的技术选型

| 决策项 | 方案 | 理由 |
|--------|------|------|
| 后端框架 | FastAPI (Python 3.11+) | 异步高性能，与参考项目技术栈一致 |
| 前端框架 | Vue 3 + TypeScript + Vite 6 | 与 NewsCrawler 前端一致，生态成熟 |
| UI 组件库 | Ant Design Vue 4 | 中后台管理系统组件丰富，适合数据分析场景 |
| 结构化存储 | MySQL 8.0+ | 用户、任务、告警、案例等结构化数据 |
| 非结构化存储 | MongoDB 7.0+ | 帖子、评论、爬取原始数据等 |
| 缓存/队列 | Redis 7.0+ | 缓存、会话管理、Celery 消息队列 |
| 图分析 | NetworkX + igraph (内存) | 当前阶段使用内存图分析，预留 Neo4j 扩展接口 |
| CooRTweet 集成 | Python 重写核心算法 | 避免 R 依赖，使用 pandas + networkx 实现 |
| BotRHG 社交机器人检测 | 内部 trainable transfer + 明确 fallback | 使用本地中文 Transformer、低阶检测器、支持超边、可靠性路由和选择性残差修正；缺少 checkpoint 时才使用 non-claimable proxy |
| LLM 支持 | 暂不集成，预留接口 | 当前用规则引擎 + NLP 模型，后续可接入 LLM |
| 任务队列 | Celery + Redis | 爬虫、分析等耗时操作异步执行 |
| 包管理 | uv (后端) / npm (前端) | 高效依赖管理 |

---

## ARIS 仓库治理与三技术工作空间

- [x] 新增根 `CLAUDE.md`、`aris/README.md` 与 `doc/research/key-technology-background/`，明确仓库分层
- [x] 新增 `aris/shared/`，统一维护 runner、GPU 模板、产物策略与评审清单
- [x] 新增 `aris/tech-01-coordination/`，为关键技术一提供独立 brief / plan / tracker / acceptance
- [x] 新增 `aris/tech-02-propagation/`，为关键技术二提供独立 brief / plan / tracker / acceptance
- [x] 新增 `aris/tech-03-risk/`，为关键技术三提供独立 brief / plan / tracker / acceptance
- [x] 2026-05-10 `aris/tech-01-coordination/systemDesign.md` 单文件落盘（系统设计 × MVP × CCF-B+ 综述），含错位矩阵 M1–M5 + ADR-001 + T1–T6 时序原则 + M0–M6 里程碑
- [~] `system/research/coordination_discover/` 与 `system/research/coordination_detect/` 已接入 artifact-first 适配器；批准 checkpoint 和公开标签验证仍需补齐
- [~] `system/research/propagation_analysis/` 已接入 hindcast、baseline 和区间输出；公开数据训练与批准 checkpoint 仍需补齐
- [~] `system/research/review_teacher/` 与 `system/runtimes/review_student/` 已接入 Review ports；多智能体 Teacher、蒸馏训练和批准模型仍需补齐

---

## 模块开发进度

### 总览

| 模块 | 状态 | 优先级 | 依赖 |
|------|------|--------|------|
| 项目骨架与基础设施 | ✅ 已完成 | P0 | - |
| 身份认证模块 | ✅ 已完成 | P0 | 项目骨架 |
| 数据采集模块（Mock） | ✅ 已完成 | P0 | 项目骨架 |
| 前端 - 布局与认证 | ✅ 已完成 | P0 | 后端认证模块 |
| 前端 - 采集管理页 | ✅ 已完成 | P0 | 后端采集模块 |
| 数据采集模块（内置 Social/News Runtime） | ✅ 已完成 | P1 | Mock 模块完成 |
| Coordination Discover / Detect | 🔧 可运行原型，研究 claim blocked | P1 | 标签数据、批准 checkpoint |
| Propagation Analysis | ✅ 观测分析与 Twitter checkpoint 推理已部署；研究 claim blocked | P1 | 严格时间切分、多 seed、覆盖率与校准验证 |
| Risk Review | 🔧 Student/Teacher 原型，canonical 需审批 | P1 | 蒸馏 checkpoint、真实 provider、分析员工作流 |
| 账户监测模块 | ✅ 已完成（含 BotRHG API） | P1 | 数据采集 |
| 前端 - 协同检测页（网络可视化） | ✅ 已完成 | P1 | 后端协同检测 |
| 前端 - 传播监控页（时间线+角色） | ✅ 已完成 | P1 | 后端传播监控 |
| 前端 - 账户监测页（画像+评分） | ✅ 已完成 | P1 | 后端账户监测 |
| 前端 - 报告研判页 | ✅ 已完成 | P1 | 后端报告研判 |
| 前端 - UX 增强（密度/分页/引导） | ✅ 已完成 | P1 | 各前端页面 |
| 案例闭环工作台 | 🔧 读模型 MVP 已接通 | P0 | EventSnapshot、AnalysisRun、特朗普访华归档证据 |
| NLP 语义辅助 | 🔧 轻量原型已接入；模型验证 blocked | P0 | EventSnapshot、权威主张 |
| 报告研判模块 | ✅ MVP 已完成 | P2 | 协同检测、传播监控、账户监测 |
| 前端 - 监测看板 | 🔧 开发中（真实数据 + 地图） | P1 | Dashboard API、Mongo 事件数据 |
| 系统联调与测试 | 🔧 部分（新增 BotRHG 后端回归测试） | P2 | 所有模块 |

状态说明：🔲 待开发 | 🔧 开发中 | ✅ 已完成 | ⏸️ 暂停 | ❌ 取消

---

### 第一阶段：基础搭建 ✅ 已完成

#### 1.1 项目骨架搭建 ✅

- [x] 后端 FastAPI 项目初始化（目录结构、配置管理、日志）
- [x] 前端 Vue 3 项目初始化（Vite + TypeScript + Ant Design Vue）
- [x] Docker Compose 编排（MySQL + MongoDB + Redis）
- [x] `.env` 配置模板与环境变量管理
- [x] 数据库连接封装（MySQL SQLAlchemy, MongoDB Motor, Redis）
- [x] Alembic 数据库迁移配置
- [x] Celery 异步任务基础配置
- [x] 统一响应格式、异常处理、中间件

#### 1.2 身份认证模块 ✅

- [x] 用户表设计与模型创建
- [x] JWT Token 认证实现（登录、注册、刷新、个人信息）
- [x] 角色权限控制（admin / analyst / viewer）
- [x] 前端登录页面
- [x] 前端路由守卫与 Token 管理
- [x] 测试：注册/登录/密码错误/Token鉴权/Token刷新

#### 1.3 数据采集模块（Mock 模式） ✅

- [x] 爬虫抽象基类 `BaseCrawler`
- [x] MockCrawler：生成含协同行为模式的模拟微博数据
- [x] DataNormalizer：跨平台字段标准化
- [x] MongoDB 存储层（raw_posts, raw_comments 集合）
- [x] Celery 异步任务执行采集
- [x] 采集相关 API 接口（创建任务/任务列表/数据查询/平台列表）
- [x] 前端采集管理页面（平台选择、参数配置、任务列表、数据查询）
- [x] 测试：Mock数据生成/协同模式验证/Normalizer/API鉴权

---

### 第二阶段：核心功能开发

#### 2.0 内置 Crawler Runtime 接入 ✅

- [x] Social Runtime 适配层 (`core/crawler/social/`)
  - [x] 从 `system/runtimes/social_runtime/` 启动内置运行时，解析 JSONL 增量批次
  - [x] 支持平台：weibo / douyin / xhs；登录、代理、Node.js 和评论抓取参数由内置配置控制
- [x] News Runtime 适配层 (`core/crawler/news/`)
  - [x] 从 `system/runtimes/news_runtime/` 直接调用内部 extractor，不读取外部 HTTP 或根目录配置
  - [x] `NewsExtractCrawler`：按文章 URL 列表提取并返回标准化 Crawl Batch
- [x] `crawl_tasks.py` 中按平台名路由（`factory.build_crawler`：mock / 社交 / news）

#### 2.1 协同检测模块 ✅

- [x] Coordination baseline Python 实现（`core/coordination_baseline/`，由 `core/coordination/` 提供兼容别名）
  - [x] `detect_groups()` 重写：时间窗口内共享行为配对（pandas + numpy 向量化）
  - [x] `generate_coordinated_network()` 重写：加权无向图 + 分位数阈值（networkx）
  - [x] `flag_speed_share()` 重写：更窄时间窗打标
  - [x] `account_stats()` / `group_stats()` 重写：账户级/对象级统计
- [x] 图引擎接口（NetworkX 实现，`graph_to_dict` 序列化）
- [x] 协同检测 API 接口（`POST /api/v1/coordination/detect`）
- [x] 前端协同网络 Canvas 力导向可视化 + 统计表格
- [ ] 多行为协同边构建（时间同步、共链接、共媒体、语义近似）
- [ ] 数据清洗后按事件顺序进行分平台聚合，再做跨平台聚合
- [ ] 用户聚类与聚类解释（平台内聚类 + 跨平台聚类）
- [ ] 自然共振 vs 人为协同显著性筛查

#### 2.2 传播监控模块 ✅

- [x] 传播子图构建（基于共享对象时序关系，`core/propagation.py`）
- [x] 传播时间线重建
- [x] 关键角色识别算法（起爆/桥接/扩散节点，介数中心性）
- [x] 高危 claim/thread 定位与排序
- [x] 传播监控 API 接口（`GET /api/v1/propagation/analyze`）
- [x] 前端传播时间线 + 关键角色卡片 + Claim 表格
- [x] 页面统一命名为“传播监测”，并拆分传播路径、对象、角色、时间线和模型预测页签
- [x] 显式、重建、推断传播证据分类及异构 provenance 图
- [x] 源头、关键路径、角色证据与时间/删边/删节点稳定性摘要
- [x] Twitter `PropagationSequenceJointModel` checkpoint 当前事件推理
- [x] 严格 `observed_until` 截断、实名再激活 Top-K 和不可用时 abstain
- [ ] 独立校准集上的规模区间与下一跳概率校准
- [ ] 严格时间切分、多 seed、完整 MINDS/FOREST/动态图基线对比

#### 2.3 账户监测模块 ✅

- [x] 账户行为画像构建（`core/account_profiler.py`）
  - [x] 发文频率、间隔统计、作息节律（24h 直方图）
  - [x] 互动模式（点赞/转发/评论汇总）
  - [x] 内容多样性（标签/URL 统计）
- [x] 自动化倾向评估算法（0-100 分，多维度综合评分）
- [x] 账户监测 API 接口（`GET /api/v1/accounts/profiles`、`GET /api/v1/accounts/detail/{id}`）
- [x] BotRHG 社交机器人检测 API（`POST /api/v1/accounts/bot-detection`）：优先加载内部 verified checkpoint，执行中文 Transformer 账号表示、低阶检测器、排除自身的 KNN 支持超边、可靠性路由和选择性残差修正；无 checkpoint 时显式回退 non-claimable proxy
- [x] 前端账户画像列表页（评分排序、进度条着色）
- [ ] 单个用户主页采集：支持主页链接/用户 ID，收集主页元数据与全部发文
- [ ] 账户详情页：查看用户主页、全部内容、内容风险/立场/模板化检测结果
- [ ] 历史参与追踪
- [ ] NLP 能力建设（中文文本向量化、语义相似度、情感分析）

#### 2.4 前端 UX 增强 ✅

- [x] 侧边栏启用协同检测、传播监控、账户监测
- [x] 登录页增加注册表单切换
- [x] 采集任务列表增加删除/取消操作
- [x] 侧边栏模块悬浮描述提示
- [x] 各模块初始引导说明与统计概览
- [x] 数据表格密度切换（紧凑/中等/宽松）+ 每页条数可选（10/30/50/100）

---

### 第三阶段：研判与集成

#### 3.1 报告研判模块 ✅ MVP 已完成

- [x] 三维评估引擎（真实性/操纵性/危害性）— `core/risk/ds_fusion.py` (234 行)
- [x] DISARM 战术映射 + 攻击路径评分 — `core/risk/disarm_scorer.py` (381 行)
- [x] 传播阶段检测 — `core/risk/phase_detector.py` (169 行)
- [x] 多源证据汇聚与证据链 — `core/risk/evidence_builder.py` (244 行)
- [x] 结构化研判报告生成 — `core/risk/report_builder.py` (278 行)
- [x] 报告研判服务层 — `services/risk_service.py` (153 行)
- [x] 报告研判 API — `api/v1/risk.py` (68 行)
- [x] 前端研判工作台 — `frontend/src/views/risk/index.vue`
- [ ] 数据库迁移补齐（`models/risk_assessment.py` 50 行已建模型，缺 alembic 迁移）⚠️ 部署阻塞
- [ ] LLM 桥接 `core/risk/llm_bridge.py`（当前 30 行 stub，需补 LLM 客户端依赖）

#### 3.1bis 案例闭环工作台 🔧 读模型 MVP 已接通

- [x] 后端 `/api/v2/cases` 返回特朗普访华主案例投影，展示事件、证据、Coordination、Propagation、Review、处置和反馈闭环。
- [x] CCTV News 作为主主张，新华社作为辅助主张；非完整平台来源以 Platform Gap blocker 显示，不伪造证据。
- [x] `semantic_enrichment` 明确作为 Case 编排 opt-in 阶段；输出只作为证据叠加。
- [x] 前端“案例闭环”五标签工作台完成构建验证。
- [x] 处置/反馈标签页可标记处置完成或豁免、提交反馈和结案复核说明；当前记录保存在后端进程内 demo state。
- [ ] 持久化 Case 聚合、权威来源审批、一主多辅增量补跑、正式处置台账、结案门槛和冻结报告文件服务仍待完成。
- [ ] 后续需要接入真实归档第二平台证据或保留明确平台缺口说明。

#### 3.2 预警管理 🔲

- [ ] 预警规则配置
- [ ] 事件级 / 群体级 / claim 级告警
- [ ] 告警状态管理
- [ ] 前端预警中心页面

#### 3.3 监测看板 🔧

- [x] 新增 Dashboard API 聚合 MongoDB 事件数据（默认 `trump_visit_2026_05_21`）
- [x] 前端统计卡片接入真实 posts/comments/platform/risk report 数据
- [x] ECharts 世界地图展示事件位置，按第一发帖者 IP 属地定位
- [x] 平台数据统计与事件定位明细表
- [ ] 热点事件排行
- [ ] 风险趋势图表（ECharts）

#### 3.4 报告中心 🔲

- [ ] 报告列表与详情
- [ ] 报告导出（PDF / JSON）
- [ ] 案例归档

---

### 第四阶段：测试与优化

#### 4.1 功能测试 🔲

- [ ] 后端 API 全模块集成测试
- [ ] 爬虫封装集成测试
- [ ] 协同检测算法正确性验证（对照 CooRTweet R 包结果）
- [ ] 前端组件测试
- [ ] 端到端测试

#### 4.2 性能优化 🔲

- [ ] 数据库查询优化
- [ ] 大规模数据处理性能
- [ ] 前端加载性能
- [ ] Celery 任务并发优化

#### 4.3 部署与文档 🔲

- [ ] 后端 Dockerfile
- [ ] 前端 Dockerfile
- [ ] 全栈 Docker Compose 一键部署
- [ ] 用户操作手册

---

## 已通过的测试

| 测试 | 说明 | 状态 |
|------|------|------|
| `test_health_check` | 后端健康检查接口 | ✅ 通过 |
| `test_mock_crawler_generates_posts` | MockCrawler 生成帖子数据 | ✅ 通过 |
| `test_mock_crawler_generates_comments` | MockCrawler 生成评论数据 | ✅ 通过 |
| `test_mock_crawler_coordinated_pattern` | Mock 数据包含协同行为模式 | ✅ 通过 |
| `test_normalizer_standardizes_weibo_post` | 微博帖子字段标准化 | ✅ 通过 |
| `test_normalizer_standardizes_comment` | 评论字段标准化 | ✅ 通过 |
| `test_list_platforms` | 平台列表接口 | ✅ 通过 |
| `test_mediacrawler_env` | MediaCrawler 的 `.env` / `uv` / `node` 解析 | ✅ 通过 |
| `test_register_success` | 用户注册 | ✅ 通过（需 MySQL） |
| `test_register_duplicate_username` | 重复用户名注册 | ✅ 通过（需 MySQL） |
| `test_login_success` | 用户登录 | ✅ 通过（需 MySQL） |
| `test_login_wrong_password` | 错误密码登录 | ✅ 通过（需 MySQL） |
| `test_profile_with_token` | Token 鉴权访问 | ✅ 通过（需 MySQL） |
| `test_profile_without_token` | 无 Token 拒绝访问 | ✅ 通过 |
| `test_refresh_token` | Token 刷新 | ✅ 通过（需 MySQL） |
| 前端构建 | `vite build` 编译成功 | ✅ 通过 |

---

## 待决议事项（后续）

| 编号 | 事项 | 说明 | 状态 |
|------|------|------|------|
| T-01 | Neo4j 接入 | 当前用 NetworkX 内存图分析，后续可切换到 Neo4j | 📋 待定 |
| T-02 | LLM 接入 | 报告研判模块预留了接口，可接入通义千问/智谱/DeepSeek | 📋 待定 |
| T-03 | DISARM 战术映射 | 将操纵行为映射为 DISARM tactics/techniques | 📋 待定 |
| T-04 | 线上部署 | 当前本地部署，后续可云服务器部署 | 📋 待定 |
| T-05 | 更多平台支持 | 当前仅 Mock 微博，逐步接入真实平台 | 📋 待定 |
| T-06 | 模型训练与微调 | 使用公开数据集微调 NLP 模型 | 📋 待定 |
| T-07 | GPU 环境适配 | NLP 模型推理加速 | 📋 待定 |

---

## 参考资料

- [环境搭建指南](environment-setup.md) - Docker、Python、Node.js 安装与配置
- [开发变更日志](development-log.md) - 开发过程变更记录，与本文档同步维护
- [ARIS 工作空间入口](../aris/README.md) - 三条关键技术的独立执行入口
- [技术背景总览](research/key-technology-background/overview.md) - 从开题报告与现有代码提炼的长期背景文档
- [系统开发文档](../../system/README.md) - 目录结构、API、部署、测试、使用方式
- [BotRHG 社交机器人检测接入计划](botrhg-social-bot-detection-plan.md) - 后端 API、方法契约与研究边界
- [开题报告](../../materials/开题报告.doc) - 项目背景、创新性分析、功能说明、技术路线
- [MediaCrawler](../MediaCrawler-main/README.md) - 社交媒体爬虫参考
- [NewsCrawler](../NewsCrawler-main/README.md) - 新闻爬虫参考
- [CooRTweet](../CooRTweet-master/README.md) - 协调行为检测算法参考
