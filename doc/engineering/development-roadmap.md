# CogGuard 设计方案与开发进度

> **用途**：记录当前工程状态、模块优先级、剩余开发任务和已通过验证。  
> **受众**：开发者、项目维护者、后续执行任务的 AI agent。  
> **维护规则**：只维护可执行工程路线和状态；研究定位、文献依据和关键技术背景放入 `../research/`。

> 最后更新：2026-07-19

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
| BotRHG 社交机器人检测 | 轻量系统适配器 | 对接 NLPCC 2026 BotRHG 方法契约，输出可靠性路由、KNN 支持超边与选择性残差修正结果 |
| LLM 支持 | 暂不集成，预留接口 | 当前用规则引擎 + NLP 模型，后续可接入 LLM |
| 任务队列 | Celery + Redis | 爬虫、分析等耗时操作异步执行 |
| 统一分析入口 | EventSnapshot + AnalysisRun + V2 API | KT1/KT2/KT3 共享不可变输入、状态机、REST/SSE 恢复路径 |
| 包管理 | uv (后端) / npm (前端) | 高效依赖管理 |

---

## ARIS 仓库治理与三技术工作空间

- [x] 新增根 `CLAUDE.md`、`aris/README.md` 与 `doc/research/key-technology-background/`，明确仓库分层
- [x] 新增 `aris/shared/`，统一维护 runner、GPU 模板、产物策略与评审清单
- [x] 新增 `aris/tech-01-coordination/`，为关键技术一提供独立 brief / plan / tracker / acceptance
- [x] 新增 `aris/tech-02-propagation/`，为关键技术二提供独立 brief / plan / tracker / acceptance
- [x] 新增 `aris/tech-03-risk/`，为关键技术三提供独立 brief / plan / tracker / acceptance
- [x] 2026-05-10 `aris/tech-01-coordination/systemDesign.md` 单文件落盘（系统设计 × MVP × CCF-B+ 综述），含错位矩阵 M1–M5 + ADR-001 + T1–T6 时序原则 + M0–M6 里程碑
- [ ] 使用 `aris/tech-01-coordination/` 完成关键技术一代码落地（PSL 新方向；旧方向 CooRTweet 共享对象 MVP 已在 `system/`）
- [~] 使用 `aris/tech-02-propagation/` 完成关键技术二代码落地（Hybrid TS + LLM 路线：WP1-3 已完成，WP4-5 未启动）
- [x] 使用 `aris/tech-03-risk/` 完成关键技术三代码落地（`core/review/` 1,340 行 MVP + `risk_service` 编排层）

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
| 数据采集模块（真实爬虫） | ✅ 已完成 | P1 | Mock 模块完成 |
| 统一分析运行底座 | ✅ 关键技术端口已贯通 | P1 | 真实数据采集 |
| 协同检测模块（KT1 evidence runtime） | ✅ 已接入统一分析 | P1 | 数据采集 |
| 协同检测模块（公开检测评测） | 🔲 待实现 | P1 | KT1 evidence runtime |
| 传播监控模块（KT2 hindcast protocol） | ✅ 已接入统一分析 | P1 | 数据采集、协同检测 |
| 传播监控模块（KT2 WP4-5 立场/危害） | 🔲 待开发 | P1 | WP1-3 |
| 账户监测模块 | ✅ 已完成（含 BotRHG API） | P1 | 数据采集 |
| 前端 - 协同检测页（网络可视化） | ✅ 已完成 | P1 | 后端协同检测 |
| 前端 - 传播监控页（时间线+角色） | ✅ 已完成 | P1 | 后端传播监控 |
| 前端 - 账户监测页（画像+评分） | ✅ 已完成 | P1 | 后端账户监测 |
| 前端 - 报告研判页 | ✅ 已完成 | P1 | 后端报告研判 |
| 前端 - UX 增强（密度/分页/引导） | ✅ 已完成 | P1 | 各前端页面 |
| KT3 Teacher-Student 审查 | ✅ runtime seam 已接入 | P1 | EventSnapshot、KT1、KT2 |
| 报告研判模块 | ✅ MVP 已完成 | P2 | 协同检测、传播监控、账户监测 |
| 前端 - 分析工作台 | ✅ 已接入 V2 关键技术输出 | P1 | 统一分析运行底座 |
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

#### 2.0 真实爬虫接入 ✅

- [x] 内置 social runtime（`system/runtimes/social_runtime`）
  - [x] `MediaSocialCrawler.collect()` 通过仓库内 subprocess adapter 执行 runtime，并按 JSONL 增量批次入库
  - [x] 支持 `weibo` / `douyin` / `xhs`；未迁入平台不出现在生产平台清单
  - [x] 登录、Cookie、Node.js、代理、评论开关和单帖评论上限由保留的 `MEDIACRAWLER_*` 配置控制
- [x] 内置 news runtime（`system/runtimes/news_runtime`）
  - [x] `NewsExtractCrawler.collect()` 直接调用内部 `ExtractorService`，不依赖 HTTP 后端或外部根路径
  - [x] detector 识别 URL 平台，并保留当前注册 adapter 的完整提取能力
- [x] `crawl_tasks.py` 只依赖 `BaseCrawler.collect() -> CrawlBatch`，统一写入帖子、评论和 `crawl_metadata`

#### 2.0.1 统一分析运行底座 🔧

- [x] `EventSnapshot` 契约：事件、平台、核心/上下文时间窗、规范化内容、观测关系、质量报告、provenance、数据指纹
- [x] `AnalysisRegistry`：从 MongoDB `raw_posts` / `raw_comments` 构建快照，幂等写入 `analysis_event_snapshots`，并注册 MySQL manifest
- [x] `AnalysisRun` 状态机：`queued/running/needs_evidence/awaiting_review/completed/failed/cancelled`
- [x] V2 初始接口：`/api/v2/analysis/snapshots`、`/runs`、`/runs/{run_id}`、`/runs/{run_id}/execute`、`/runs/{run_id}/events`、`/runs/{run_id}/events/stream`
- [x] SSE 恢复：使用 `Last-Event-ID` 或 REST `after_id` 返回追加事件
- [x] 判决版本表支持同一 `verdict_id` 多版本，唯一性落在 `(verdict_id, version)`
- [x] `AnalysisExecutor`：以 `EventSnapshot` 为输入，顺序调用 `CoordinationEngine.analyze`、`PropagationEngine.hindcast`、`StudentRuntime.predict`、`TeacherJobPort.submit` 端口并写入 run events
- [x] 将 KT1 evidence runtime 接到 `CoordinationEngine.analyze(snapshot, options)`，替换旧默认 baseline 输出
- [x] 将 KT2 事件 bundle / checkpoint adapter / hindcast protocol 接到 `PropagationEngine.hindcast(snapshot, options)`，不再依赖外部 research workspace
- [x] 将 KT2 public fixture loader、split-conformal interval 和 baseline registry 内化到 `system/research/propagation_analysis`
- [x] 将 Student 同步 runtime 接到 `StudentRuntime.predict(case)`，没有 approved checkpoint 时显式 `shadow_untrained` 并强制 review
- [x] 将 Teacher 异步 Celery job port 接到 `system/research/review_teacher` 的 5+1+1 advisory DAG
- [x] 新增 canonical verdict、模型激活、回滚和主动学习治理 helper；数据库模型已具备 verdict/version/feedback/activation 表
- [~] 前端分析员工作流迁移到 V2 运行与 SSE 恢复：`/analysis` 已展示 KT1/KT2/Student/Teacher 输出；完整 adjudication、verdict 审批与模型激活 UI 仍待实现

#### 2.1 协同检测模块 ✅

- [x] CooRTweet 核心算法 Python 重写（`core/coordination_baseline/`）
  - [x] `detect_groups()` 重写：时间窗口内共享行为配对（pandas + numpy 向量化）
  - [x] `generate_coordinated_network()` 重写：加权无向图 + 分位数阈值（networkx）
  - [x] `flag_speed_share()` 重写：更窄时间窗打标
  - [x] `account_stats()` / `group_stats()` 重写：账户级/对象级统计
- [x] 图引擎接口（NetworkX 实现，`graph_to_dict` 序列化）
- [x] 协同检测 API 接口（`POST /api/v1/coordination/detect`）
- [x] 前端协同网络 Canvas 力导向可视化 + 统计表格
- [x] 多行为 evidence edge 构建：URL、媒体、话题、实体、目标、原生转评赞/回复、近重复内容
- [x] 1h/6h/24h 50% 重叠窗口、社区谱系、证据覆盖、零模型显著性和扰动鲁棒性
- [x] `CoordinationEngine.analyze(snapshot, options) -> CoordinationResult` 作为统一分析入口
- [ ] 数据清洗后按事件顺序进行更完整的分平台复核，再做跨平台聚合
- [ ] 公开数据 Detect 评测：campaign/platform/time 留出、AUPRC、MaxF1、校准和 5-seed 置信区间
- [ ] 分层人工复核工作台：每平台社区支持/反证/无法判断记录，不直接形成训练集

#### 2.2 传播监控模块 ✅

- [x] 传播子图构建（基于共享对象时序关系，`core/propagation.py`）
- [x] 传播时间线重建
- [x] 关键角色识别算法（起爆/桥接/扩散节点，介数中心性）
- [x] 高危 claim/thread 定位与排序
- [x] 传播监控 API 接口（`GET /api/v1/propagation/analyze`）
- [x] 前端传播时间线 + 关键角色卡片 + Claim 表格
- [x] KT2 缓存证据内置到 `system/research/propagation_analysis/benchmark/`，系统服务不再读取 `subsystems/cogguard_dev`
- [x] `kt2_prediction_service.py` 删除外部 `sys.path.insert`，事件 bundle / checkpoint adapter 内置到 `system/research/propagation_analysis/benchmark/adapters/`
- [x] KT2 current-event live runtime 已接通，并由 `kt2-hindcast-protocol-v1` 包装为统一预测协议
- [x] 公开 fixture loader、EventSnapshot bundle adapter、80/95 split-conformal 区间、下一跳 ranking 和平台 hindcast 已内置
- [x] EdgeBank、Hawkes-recency、persistence、historical-mean baseline registry 已内置；TGN/DyGFormer/CasFlow/CasFT checkpoint slot 显式返回缺 checkpoint/不可用
- [ ] 页面命名由“传播归因”调整为“传播监控”
- [ ] 相关发帖用户检测与高影响力节点识别的研究级评估
- [ ] 可部署 TGN/DyGFormer/CasFlow/CasFT checkpoint runtime 与公开 benchmark 训练/评测 runner

#### 2.3 账户监测模块 ✅

- [x] 账户行为画像构建（`core/account_profiler.py`）
  - [x] 发文频率、间隔统计、作息节律（24h 直方图）
  - [x] 互动模式（点赞/转发/评论汇总）
  - [x] 内容多样性（标签/URL 统计）
- [x] 自动化倾向评估算法（0-100 分，多维度综合评分）
- [x] 账户监测 API 接口（`GET /api/v1/accounts/profiles`、`GET /api/v1/accounts/detail/{id}`）
- [x] BotRHG 风格社交机器人检测 API（`POST /api/v1/accounts/bot-detection`）：从已采集帖子构造 profile/text/activity 特征、KNN 支持超边和局部可靠性路由，对低可靠账号执行选择性残差修正并返回 base/final bot 概率与解释证据
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

#### 3.0 KT3 Teacher-Student 审查 ✅ runtime seam 已完成

- [x] `system/runtimes/review_student/`：同步 `StudentRuntime.predict(case)`，输出 preliminary verdict、XLM-R-base / frozen multimodal / gating / MIL / community GNN 架构契约、主动学习信号和蒸馏计划
- [x] `system/research/review_teacher/`：5+1+1 Teacher DAG（claim planning、trusted retrieval、text verification、multimodal verification、harm/stance/KT context、Gold aggregator、disagreement-only Critic/Judge）
- [x] `app.core.analysis.governance`：canonical approval、model activation、rollback、active-learning batch helper
- [x] Teacher 只生成 `teacher_advisory`，Student 只生成 `preliminary`；canonical 只能来自分析员审批
- [ ] 真实多模型族在线 Teacher provider、可信检索 provider 和多模态核验 provider
- [ ] approved feedback / Teacher traces 蒸馏训练 runner 与 Student approved checkpoint
- [ ] adjudication UI、模型版本差异 UI、active pointer 激活/回滚 UI

#### 3.1 报告研判模块 ✅ MVP 已完成

- [x] 三维评估引擎（真实性/操纵性/危害性）— `core/review/ds_fusion.py` (234 行)
- [x] DISARM 战术映射 + 攻击路径评分 — `core/review/disarm_scorer.py` (381 行)
- [x] 传播阶段检测 — `core/review/phase_detector.py` (169 行)
- [x] 多源证据汇聚与证据链 — `core/review/evidence_builder.py` (244 行)
- [x] 结构化研判报告生成 — `core/review/report_builder.py` (278 行)
- [x] 报告研判服务层 — `services/risk_service.py` (153 行)
- [x] 报告研判 API — `api/v1/risk.py` (68 行)
- [x] 前端研判工作台 — `frontend/src/views/risk/index.vue`
- [ ] 数据库迁移补齐（`models/risk_assessment.py` 50 行已建模型，缺 alembic 迁移）⚠️ 部署阻塞
- [ ] LLM 桥接 `core/review/llm_bridge.py`（当前 30 行 stub，需补 LLM 客户端依赖）

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
| `test_analysis_kt1_runtime` | KT1 evidence runtime：多行为边、窗口、谱系、零模型、扰动鲁棒性 | ✅ 通过 |
| `test_kt2_prediction_service` | KT2 内置 loader、hindcast protocol、conformal、baseline registry | ✅ 通过 |
| `test_analysis_kt3_runtime` | KT3 Student/Teacher/governance seam | ✅ 通过 |
| 后端全量测试 | `python -m pytest -q` | ✅ 361 passed, 27 skipped |
| `test_register_success` | 用户注册 | ✅ 通过（需 MySQL） |
| `test_register_duplicate_username` | 重复用户名注册 | ✅ 通过（需 MySQL） |
| `test_login_success` | 用户登录 | ✅ 通过（需 MySQL） |
| `test_login_wrong_password` | 错误密码登录 | ✅ 通过（需 MySQL） |
| `test_profile_with_token` | Token 鉴权访问 | ✅ 通过（需 MySQL） |
| `test_profile_without_token` | 无 Token 拒绝访问 | ✅ 通过 |
| `test_refresh_token` | Token 刷新 | ✅ 通过（需 MySQL） |
| 前端构建 | `npm run build`（`vue-tsc -b && vite build`） | ✅ 通过 |

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
