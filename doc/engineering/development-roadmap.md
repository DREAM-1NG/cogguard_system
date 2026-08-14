# CogGuard 设计方案与开发进度

> **用途**：记录当前工程状态、模块优先级、剩余开发任务和已通过验证。  
> **受众**：开发者、项目维护者、后续执行任务的 AI agent。  
> **维护规则**：只维护可执行工程路线和状态；研究定位、文献依据和关键技术背景放入 `../research/`。

> 最后更新：2026-08-14

## 2026-08-14 Real Semantic Evidence Frontend Closure

- [x] Added a fail-closed, real-local-model semantic runtime using the fixed
  BGE, sentiment, stance, and Chinese NER model revisions. Semantic evidence
  remains additive and cannot alter Coordination, Propagation, Review, or risk
  scores.
- [x] Added event-scoped semantic artifact projection APIs and connected them
  to the existing Event Review (`/risk`) and Propagation (`/propagation`)
  workspaces. The review workspace renders keywords, topics, sentiment,
  stance, entities, post/comment layers, and available time/platform/community
  slices; propagation renders path overlays only when verified evidence exists.
- [x] Added bounded, preceding-only BGE near-duplicate evidence search to
  avoid all-pairs Python cosine comparison on the three-platform snapshot.
- [x] Backend semantic regression tests (`43 passed`), frontend semantic
  contract tests (`48 passed`), and the production frontend build pass.
- [ ] The real `trump_visit_2026_05_21` artifact is intentionally not claimed
  as precomputed: the source manifest is ready (Weibo 165/2680, XHS 98/1905,
  Douyin 31/10137), but the local Docker daemon is unavailable, so MongoDB,
  MySQL, and Redis cannot be reached. The precompute script returns the
  explicit `database_blocked` state and writes no successful semantic artifact.

## 2026-08-08 TwiBot-20 Research Runtime And Dataset Identity

- [x] Deploy the selected NLPCC TwiBot-20 seed-3 checkpoint as a separate,
  hash-verified fixed-graph research bundle and CLI.
- [x] Keep the TwiBot-20 runtime permanently outside the Chinese account
  model Active Pointer and document its transductive scope.
- [x] Scope approved-corpus identities by platform, preserve source IDs, and
  reject tampered JSONL fingerprints, record counts, and class counts.
- [x] Use platform-scoped IDs in system-owned frozen-holdout inference and
  audit lookup.
- [ ] Chinese online deployment still requires the real DAPT threshold,
  approved binary labels, detector retraining, signed shadow evaluation,
  activation, latency measurement, and rollback rehearsal.

## 2026-08-07 Account Detection Module Review

- [x] Account detail is platform-scoped; ambiguous cross-platform account IDs
  fail with an explicit request error instead of merging profiles.
- [x] Account detector projection cache fingerprints include the complete
  Mongo post input used by strict BotRHG inference, including nested profile,
  interaction, and relation fields.
- [x] Account-model migration chain has one Alembic head at
  `e5c1b7d9a204`; offline upgrade SQL generation now completes through that
  head.
- [ ] A governed Chinese detector bundle, real MySQL migration round-trip to
  `e5c1b7d9a204`, shadow run, activation, and rollback exercise remain
  deployment gates. No result is claimed until these are executed with real
  data and services.

## 2026-08-05 Review Teacher-Student Integrity

- [x] MultiAgents complex path keeps expert analysis, Questioning, targeted
  responses, and Judge synthesis while bounding calls and compacting prompts.
- [x] Only human-approved active policy reaches the Judge; candidate policy is
  ignored with audit provenance.
- [x] Teacher silver no longer backfills Agent predictions from dataset gold;
  only validated structured Judge predictions are distillation-eligible.
- [x] Frozen XLM-R feature evaluation writes reloadable selective-head
  checkpoints plus encoder snapshot fingerprints.
- [x] Event Review Case asynchronous Teacher execution now prefers the shared
  MARO runtime with active provider, approved policy, and feedback memory;
  deterministic fallback is explicitly non-claimable.
- [x] Capability routing reduces the measured fake-provider call plan to `2`
  calls for simple text, `6` for a standard two-expert complex case, and `8`
  for the four-expert complex path.
- [x] The governance-after-change five-dataset frozen-XLM-R baseline completed
  with a passed strict artifact gate and `9,699` test predictions.
- [ ] End-to-end XLM-R SFT, valid teacher-probability distillation, and
  cross-domain/coverage-risk evaluation remain research delivery gates.
- [ ] The deployable Student gate remains blocked: HateXplain, MultiOFF, and
  FakeSV abstain on every test case, and four datasets have zero high-risk
  recall under the current unsupervised defer fallback.
- [ ] RL is deferred until SFT/distillation and analyst-preference datasets are
  mature; it is not part of the current deployable classifier claim.
- [x] Freeze the first MARO-aligned experiment populations: `500` balanced test
  cases, `1,000` train-only Teacher Silver candidates, and `1,000` validation
  tasks, with zero case-id overlap and gold-free manifests.
- [x] Add probability-target distillation for valid Teacher Silver confidence,
  plus train/test population guards in the Student and MultiAgent runners.
- [ ] Generate current-footer Teacher outputs for the `1,000` train candidates,
  then run the paired no-teacher versus Teacher-KD learning comparison. The
  current machine has CPU-only PyTorch, so end-to-end XLM-R SFT remains a GPU
  experiment rather than a completed local run.

## 2026-08-04 Performance Delivery And Operations

- [x] Add an opt-in static frontend delivery profile with gzip, immutable
  caching for Vite content-addressed assets, uncached HTML/API behavior, and
  unbuffered review event streaming.
- [x] Add an explicit, idempotent MongoDB index operation for the existing
  event/platform/time/crawl-job query shapes.
- [x] Record the measured route-cost map and operations runbook in
  `performance-operations.md` without changing frontend or backend product
  source.
- [x] Make the optimized static delivery path the default Windows startup:
  MongoDB index preparation, migration, health-gated single-process backend,
  optimized frontend build, and static frontend readiness are ordered by
  `system/start-system.ps1`.
- [x] Generate a Vite-manifest-driven delivery preload plan. Idle preparation
  is limited to the authenticated layout and dashboard shell; other routes are
  prepared only on navigation interaction, and graph chunks are excluded from
  the idle set.
- [ ] Source-level performance work remains separately scoped: route instance
  retention, evidence pagination/virtualization, account inference
  precomputation, analytical result caching, and deferred graph initialization.

## 2026-08-03 Durable Review And Model Governance

- [x] Teacher dispatch policy is explicit: local inline fallback is allowed
  only for local deployments; production broker or worker failures become
  durable failed advisories instead of in-process successes.
- [x] Model Candidate Approval is authenticated and persisted in
  `analysis_model_activation_approvals`; activation no longer accepts a list
  of approver IDs from the caller.
- [x] Production activation requires two distinct active administrators,
  including the activating administrator; local activation records one
  accountable operator.
- [x] Artifact SHA-256 verification and capability quality gates run before
  both candidate approval and activation; rollback remains an audited backend
  recovery action.
- [x] The dashboard-first frontend remains business-facing and unchanged; no
  model-governance page is part of the product surface.
- [x] Applied migration `a2d8e5c1b904` to the active local MySQL database.
  Apply it to each production database and run a real Celery queue smoke before
  enabling production activation.
- [x] Started the local `analysis` Celery worker and verified Redis control
  ping/worker readiness.
- [x] Backend full regression passed (`510 passed, 19 skipped`); frontend
  component tests passed (`13 passed`) and production build/typecheck passed.
- [ ] Run an authenticated Teacher Advisory submission through the product API
  with a deliberately provisioned local administrator account; no known admin
  password is present in the current environment, so this smoke is not claimed.

## 2026-08-03 Analyst-Facing Case And Account Views

- [x] The Event Review Case workspace now presents a concise Chinese business
  summary: it does not render transient review-status notices, internal
  rationale text, or a propagation-summary card.
- [x] Coordination summary account references are resolved against collected
  display names and the workspace limits the visible account list.
- [x] Account profiles now request the trained account detector as part of the
  profile projection. The analyst view shows only a concise finding and does
  not expose legacy rule scores, probabilities, runtime modes, or method
  internals.
- [x] The account profile client allows the first local detector inference to
  complete, while the backend caches the result by input fingerprint for
  subsequent profile and detail reads.

## 2026-08-02 文档同步

- [x] Event Review Case 术语、ADR 索引、系统上下文和系统 README 已同步到当前代码边界。
- [x] 产品文案已切换为 Event Review Case / Preliminary Finding / Review Advisory / Confirmed Decision / Evidence Sufficiency / Evidence Annotation / Case Activity。
- [x] 旧有待决议编号已从后续决议表中移除，改用 Coordination Discover / Coordination Detect / Propagation Analysis / Review 的正式名称。
- [ ] 生产级上线和真实数据 smoke 仍需在对应环境中验证。

## 2026-08-01 状态收口

- [x] 安全与部署阻塞收口：生产秘密强制配置、Preview 旁路默认关闭、Compose 凭据必填。
- [x] Analysis Run、SSE `Last-Event-ID` 恢复、阶段 Artifact Manifest 和 active model pointer 已通过后端回归测试。
- [x] Canonical Verdict、反馈持久化、双人模型激活、回滚决策和本地 SHA-256 artifact 校验已接通。
- [x] Teacher dispatch failure classification, authenticated persisted model
  approvals, and the backend control-plane boundary are implemented; the
  deployment migration and real queue smoke remain environment gates.
- [x] 本地原型验收脚本已贯通 EventSnapshot、Coordination Discover、Propagation Analysis、Student Review 和 Teacher Review，并明确输出 fallback/shadow/advisory/non-claimable 状态。
- [ ] 研究级 Coordination Discover、Propagation Analysis 和 Student/Teacher checkpoint 尚未因缺少批准 artifact 而声明为可研究主张结果；Social Bot Detection 的 BotRHG Weibo transfer 已有真实 checkpoint，但当前指标低于同切分 TF-IDF 参考，研究 claim 仍 blocked。
- [x] 前端 `npm run build`（包含 `vue-tsc -b`）已通过；本轮不修改前端展示页面。
- [x] 账号模型控制面已完成真实 MySQL/Mongo/Redis/Celery smoke：迁移回环、transactional outbox、训练/评估队列注册、重复投递门禁、不可变 Encoder Version、Frozen Holdout 评估、训练导出 lineage、Active Pointer 失效拒绝和受限自动回滚均有代码与回归证据。
- [ ] GPU 长实验仍未完成：backend venv 已升级为 `torch 2.11.0+cu128`，本地中文 RoBERTa 的 BF16 DAPT smoke 已完成两个真实 optimizer update，峰值显存 1,972.8 MiB；当前中文语料仍为 415,686 tokens，低于 500,000-token DAPT 门禁，且尚无 200 个批准标签，因此完整 DAPT、监督重训、签名 shadow、激活和回滚全周期仍未完成。

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
| Propagation Analysis | 🔧 可运行 fallback，研究 claim blocked | P1 | 公开数据训练、批准 checkpoint、覆盖率验证 |
| Review / Event Review Case | 🔧 案例工作台原型，确认仍需分析员审批 | P1 | 解析工作流、分析员工作流 |
| 账户监测模块 | 🔧 后端子模块可接入，生产模型待激活 | P1 | 数据采集 |
| 前端 - 协同检测页（网络可视化） | ✅ 已完成 | P1 | 后端协同检测 |
| 前端 - 传播监控页（时间线+角色） | ✅ 已完成 | P1 | 后端传播监控 |
| 前端 - 账户监测页（画像+评分） | ✅ 已完成 | P1 | 后端账户监测 |
| 前端 - 报告研判页 | ✅ 已完成 | P1 | 后端报告研判 |
| 前端 - UX 增强（密度/分页/引导） | ✅ 已完成 | P1 | 各前端页面 |
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
- [ ] 页面命名由“传播归因”调整为“传播监控”
- [ ] 相关发帖用户检测与高影响力节点识别
- [ ] 归因证据链生成

#### 2.3 账户监测模块 ✅

- [x] 账户行为画像构建（`core/account_profiler.py`）
  - [x] 发文频率、间隔统计、作息节律（24h 直方图）
  - [x] 互动模式（点赞/转发/评论汇总）
  - [x] 内容多样性（标签/URL 统计）
- [x] 自动化倾向评估算法（0-100 分，多维度综合评分）
- [x] 账户监测 API 接口（`GET /api/v1/accounts/profiles`、`GET /api/v1/accounts/detail/{id}`）
- [x] BotRHG 社交机器人检测 API（`POST /api/v1/accounts/bot-detection`）：优先加载内部 verified checkpoint，执行中文 Transformer 账号表示、低阶检测器、排除自身的 KNN 支持超边、可靠性路由和选择性残差修正；legacy checkpoint 仅允许本地兼容模式，生产默认 fail-closed
- [x] 前端账户画像列表页（评分排序、进度条着色）
- [ ] 单个用户主页采集：支持主页链接/用户 ID，收集主页元数据与全部发文
- [ ] 账户详情页：查看用户主页、全部内容、内容风险/立场/模板化检测结果
- [ ] 历史参与追踪
- [ ] NLP 能力建设（持续预训练后的中文文本向量化、语义相似度、情感分析）

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

- Coordination Discover：当前用 NetworkX 内存图分析，后续可切换到 Neo4j。
- Coordination Detect：报告研判模块预留了接口，可接入更完整的验证流程。
- Propagation Analysis：当前本地推理与 fallback 可运行，公开数据训练和更强覆盖仍需补齐。
- Review：当前案例工作台可用，仍需要更完整的生产上线、分析员工作流和内部治理验证。
- Crawler：当前仅 Mock 微博和有限真实平台通路，后续继续扩展平台支持。
- Social Bot Detection：继续推进公开数据训练与推理加速。

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

## 2026-08-10 Coordination 研究门禁

- [x] 将冻结生产 `coordination-evidence-runtime-v2` 的静态图 prior 接入 IOHunter 同源评估。
- [x] 配对强制校验 source/evaluator/fold 指纹，并按 campaign 均值执行 bootstrap。
- [x] 在 G 盘完成最终 v2 五 campaign 跑批：50 行，35 success，15 production runtime-budget blocked。
- [x] 拉通官方 InfoOpsGFM（本地历史 `SocGFM` checkout）四个同国训练入口：`run_GNN.py`、`run_GNNPlusLLM.py`、`run_MultiModalGNN.py`、`run_MultiModalGNN_CrossAttention.py` 均在 Russia IOHunter bundle 完成相同五折官方协议复现；sandbox、日志、MLflow、临时缓存与 manifest 均在 G 盘。
- [x] 官方 Cross-Attention SAGE 五 campaign 复现完成 UAE、Russia、Venezuela、Iran、China；Russia 四入口统一矩阵已落盘。该结果限外部账号成员恢复 proxy，不得作为 Coordination Discover 或 harmful-CIB Coordination Detect 主张。
- [~] 官方 InfoOpsGFM 同国全矩阵已具备资源门控的串行、断点续跑 runner：五个可执行 campaign × 四个官方入口将在 GPU/主存空闲后执行；Cuba 使用已验证的 12GiB full-graph 显存门禁写 blocked manifest，不以非等价采样替代。
- [ ] 补齐官方 InfoOpsGFM Cuba full-graph 复现：本地 8GB GPU 对 SAGE 与 GCN 均在约 9GB 单次传播分配时 OOM；不得以降采样结果替代官方 full-graph 行。
- [ ] 官方 InfoOpsGFM cross-country 与 fine-tuning 路径：本地数据为 `UAE`，官方一个脚本要求 `UAE_sample`；不得静默创建别名改变路径契约。两个脚本还加载 Cuba，因此至少需要数据路径对齐和大于当前 8GB 的可用显存。
- [ ] 研究候选替换系统模型：继续阻断。Russia 全指标落后，Venezuela 全指标领先，跨 campaign 方向不稳定。
- [ ] 完全交叉 model seed 与 official fold，消除当前 seed-fold 耦合。
- [ ] 使用可扩展但单独命名的生产社区 baseline；不得替换冻结 baseline 后沿用原方法身份。
- [ ] 使用具备真实 coordination edge/community Gold 的数据验证 Discovery，并用 harmful-CIB Gold 单独验证 Detect。
