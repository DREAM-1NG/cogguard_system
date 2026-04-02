# CogGuard 设计方案与开发进度

> 最后更新：2026-04-02

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
| LLM 支持 | 暂不集成，预留接口 | 当前用规则引擎 + NLP 模型，后续可接入 LLM |
| 任务队列 | Celery + Redis | 爬虫、分析等耗时操作异步执行 |
| 包管理 | uv (后端) / npm (前端) | 高效依赖管理 |

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
| 数据采集模块（真实爬虫） | 🔲 待开发 | P1 | Mock 模块完成 |
| 协同检测模块 | 🔲 待开发 | P1 | 数据采集 |
| 传播归因模块 | 🔲 待开发 | P1 | 数据采集、协同检测 |
| 账户监测模块 | 🔲 待开发 | P1 | 数据采集 |
| 风险研判模块 | 🔲 待开发 | P2 | 协同检测、传播归因、账户监测 |
| 前端 - 监测看板 | 🔲 待开发 | P1 | 后端各模块 |
| 前端 - 可视化组件 | 🔲 待开发 | P1 | 后端协同检测、传播归因 |
| 系统联调与测试 | 🔲 待开发 | P2 | 所有模块 |

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

#### 2.0 真实爬虫接入 🔲

- [ ] MediaCrawler 封装层 (`core/crawler/social.py`)
  - [ ] 将 MediaCrawler 作为本地 Python 依赖接入
  - [ ] 封装统一 `SocialCrawler` 接口（搜索、帖子采集、评论采集）
  - [ ] 支持平台：微博（优先）、其他平台逐步接入
- [ ] NewsCrawler 封装层 (`core/crawler/news.py`)
  - [ ] 通过 HTTP 调用 NewsCrawler API 或模块导入
  - [ ] 封装统一 `NewsCrawler` 接口
- [ ] `crawl_tasks.py` 中按平台名路由到对应爬虫（mock / social / news）

#### 2.1 协同检测模块 🔲

- [ ] CooRTweet 核心算法 Python 重写
  - [ ] `detect_groups()` 重写：时间窗口内共享行为配对
  - [ ] `generate_coordinated_network()` 重写：协同网络构建
  - [ ] `flag_speed_share()` 重写：快速分享标记
  - [ ] `account_stats()` / `group_stats()` 重写：统计功能
- [ ] 多行为协同边构建（时间同步、共链接、共媒体、语义近似）
- [ ] 自然共振 vs 人为协同显著性筛查
- [ ] 图引擎接口（NetworkX 实现，预留 Neo4j 适配层）
- [ ] 协同检测相关 API 接口
- [ ] 前端协同网络可视化（vis-network / D3.js）

#### 2.2 传播归因模块 🔲

- [ ] 传播子图构建（基于时序关系：回复、转发、引用）
- [ ] 传播时间线重建
- [ ] 关键角色识别算法（起爆/桥接/扩散/伪装KOL）
- [ ] 高危 claim/thread 定位
- [ ] 归因证据链生成
- [ ] 传播归因相关 API 接口
- [ ] 前端传播路径可视化

#### 2.3 账户监测模块 🔲

- [ ] 账户行为画像构建（发文频率、作息节律、互动模式）
- [ ] 自动化倾向评估算法
- [ ] 历史参与追踪
- [ ] NLP 能力建设（中文文本向量化、语义相似度、情感分析）
- [ ] 账户监测相关 API 接口
- [ ] 前端账户画像页面

---

### 第三阶段：研判与集成

#### 3.1 风险研判模块 🔲

- [ ] 三维评估引擎（真实性/操纵性/危害性）
- [ ] 规则引擎（可配置判定规则）
- [ ] 多源证据汇聚
- [ ] 结构化研判报告生成
- [ ] LLM 接口预留 (`core/risk/llm_bridge.py`)
- [ ] 风险研判相关 API 接口
- [ ] 前端研判工作台

#### 3.2 预警管理 🔲

- [ ] 预警规则配置
- [ ] 事件级 / 群体级 / claim 级告警
- [ ] 告警状态管理
- [ ] 前端预警中心页面

#### 3.3 监测看板 🔲

- [ ] 系统概览数据（接入后端统计 API）
- [ ] 热点事件排行
- [ ] 平台数据统计
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
| T-02 | LLM 接入 | 风险研判模块预留了接口，可接入通义千问/智谱/DeepSeek | 📋 待定 |
| T-03 | DISARM 战术映射 | 将操纵行为映射为 DISARM tactics/techniques | 📋 待定 |
| T-04 | 线上部署 | 当前本地部署，后续可云服务器部署 | 📋 待定 |
| T-05 | 更多平台支持 | 当前仅 Mock 微博，逐步接入真实平台 | 📋 待定 |
| T-06 | 模型训练与微调 | 使用公开数据集微调 NLP 模型 | 📋 待定 |
| T-07 | GPU 环境适配 | NLP 模型推理加速 | 📋 待定 |

---

## 参考资料

- [环境搭建指南](ENV_SETUP.md) - Docker、Python、Node.js 安装与配置
- [系统开发文档](../new-system/README.md) - 目录结构、API、部署、测试、使用方式
- [开题报告](开题报告.doc) - 项目背景、创新性分析、功能说明、技术路线
- [MediaCrawler](../MediaCrawler-main/README.md) - 社交媒体爬虫参考
- [NewsCrawler](../NewsCrawler-main/README.md) - 新闻爬虫参考
- [CooRTweet](../CooRTweet-master/README.md) - 协调行为检测算法参考
