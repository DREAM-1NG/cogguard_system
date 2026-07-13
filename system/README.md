# CogGuard 系统开发文档

> 仓库定位：
> - `system/` 是当前唯一产品代码根
> - 长期文档位于 `../doc/`
> - ARIS 工作空间位于 `../aris/`
> - 当前状态与优先级以 `../doc/engineering/development-roadmap.md` 为准

## 实际目录结构

```
system/
├── docker-compose.yml              # Docker 服务编排（MySQL + MongoDB + Redis）
├── .env.example                    # 环境变量模板（复制为 .env 使用）
├── .env                            # 实际环境变量（不提交到 Git）
│
├── backend/                        # 后端服务 (Python 3.11+ / FastAPI)
│   ├── pyproject.toml              # 项目元数据与依赖管理 (uv)
│   ├── requirements.txt            # pip 兼容依赖列表
│   ├── scripts/
│   │   └── verify_mediacrawler_env.py # 内置 social runtime 环境校验脚本
│   ├── alembic.ini                 # 数据库迁移配置
│   ├── alembic/                    # 迁移脚本目录
│   │   ├── env.py                  # 迁移环境（异步引擎 + 自动导入模型）
│   │   ├── script.py.mako          # 迁移脚本模板
│   │   └── versions/               # 自动生成的迁移文件
│   ├── app/
│   │   ├── __init__.py             # 应用根包说明
│   │   ├── main.py                 # FastAPI 入口（CORS、路由、生命周期）
│   │   ├── config.py               # Pydantic Settings 配置管理
│   │   ├── celery_app.py           # Celery 异步任务队列配置
│   │   │
│   │   ├── api/                    # API 路由层
│   │   │   ├── v1/                 # 既有业务 API（保留一个发布周期）
│   │   │   └── v2/                 # 统一分析 API（EventSnapshot / AnalysisRun / SSE）
│   │   │
│   │   ├── core/                   # 核心业务逻辑
│   │   │   ├── security.py         # JWT 认证 + bcrypt 密码哈希
│   │   │   ├── analysis/           # 统一事件快照、运行状态机、registry、SSE 恢复
│   │   │   ├── propagation.py      # 传播子图与时间线、关键角色
│   │   │   ├── account_profiler.py # 账户行为画像与自动化倾向评分
│   │   │   ├── bot_detection.py    # BotRHG 风格账号级社交机器人检测
│   │   │   ├── coordination/       # CooRTweet 算法 Python 实现（检测/网络/统计）
│   │   │   └── crawler/            # 爬虫引擎
│   │   │       ├── base.py         # 爬虫抽象基类（定义统一接口）
│   │   │       ├── mediacrawler_env.py # MediaCrawler 的 uv / node / PATH 解析
│   │   │       ├── mock.py         # 模拟数据爬虫（生成含协同模式的测试数据）
│   │   │       ├── social/         # 社交采集深 module（normalizer / runtime / metadata）
│   │   │       ├── news/           # 新闻提取深 module（normalizer / runtime）
│   │   │       ├── factory.py      # 按平台构造爬虫
│   │   │       └── types.py        # collect request / batch 类型
│   │   │
│   │   ├── models/                 # 数据库模型
│   │   │   ├── analysis.py         # EventSnapshot manifest / AnalysisRun / verdict governance
│   │   │   ├── user.py             # 用户表 (MySQL/SQLAlchemy)
│   │   │   ├── task.py             # 采集任务表 (MySQL/SQLAlchemy)
│   │   │   └── post.py             # 帖子/评论文档模型 (MongoDB/Pydantic)
│   │   │
│   │   ├── schemas/                # Pydantic 请求/响应模式
│   │   │   ├── analysis.py         # V2 分析运行请求 schema
│   │   │   ├── auth.py             # 认证相关（Login/Register/Token/UserInfo）
│   │   │   └── crawl.py            # 采集相关（CrawlRequest/JobResponse/PostResponse）
│   │   │
│   │   ├── services/               # 业务服务层
│   │   │   ├── auth_service.py     # 认证业务（注册/登录/刷新/用户信息）
│   │   │   ├── crawl_service.py    # 采集业务（任务管理/数据查询）
│   │   │   ├── coordination_service.py
│   │   │   ├── propagation_service.py
│   │   │   ├── account_service.py
│   │   │   └── bot_detection_service.py
│   │   │
│   │   ├── tasks/                  # Celery 异步任务
│   │   │   └── crawl_tasks.py      # 采集任务执行（统一 collect seam → MongoDB）
│   │   │
│   │   ├── db/                     # 数据库连接管理
│   │   │   ├── mysql.py            # SQLAlchemy 异步引擎 + Session
│   │   │   ├── mongodb.py          # Motor 异步客户端
│   │   │   └── redis.py            # Redis 异步客户端
│   │   │
│   │   └── utils/                  # 通用工具
│   │       ├── logger.py           # loguru 日志配置
│   │       ├── exceptions.py       # 自定义异常 + 全局异常处理器
│   │       └── response.py         # 统一 JSON 响应格式
│   │
│   └── tests/                      # 测试套件
│       ├── conftest.py             # 测试 fixtures（DB/Client/Auth）
│       ├── test_health.py          # 健康检查测试
│       ├── test_auth.py            # 认证模块测试（需要 MySQL）
│       ├── test_crawl.py           # 采集模块测试（含纯单元测试）
│       ├── test_analysis_registry.py # 统一分析 registry / run 事件测试
│       ├── test_analysis_v2_api.py   # V2 分析 API / SSE 恢复测试
│       └── test_mediacrawler_env.py # MediaCrawler 环境解析测试
│
├── runtimes/                       # 内置 crawler runtime
│   ├── social_runtime/             # vendored MediaCrawler core（仅 weibo / douyin / xhs）
│   └── news_runtime/               # vendored NewsCrawler core（URL detector + adapters）
├── research/                       # 系统可读取的研究制品边界
│   └── kt2/                        # KT2 缓存 benchmark / 后续 runner 与 checkpoint adapter
└── frontend/                       # 前端应用 (Vue 3 + TypeScript)
    ├── package.json                # 依赖声明与脚本
    ├── vite.config.ts              # Vite 配置（代理、别名）
    ├── tsconfig.json               # TypeScript 配置
    ├── index.html                  # HTML 入口
    └── src/
        ├── main.ts                 # Vue 应用入口（注册插件）
        ├── App.vue                 # 根组件
        ├── env.d.ts                # 类型声明
        │
        ├── api/                    # 后端 API 请求封装
        │   ├── auth.ts             # 认证 API（登录/注册/刷新/用户信息）
        │   ├── crawl.ts            # 采集 API（创建任务/任务列表/数据查询）
        │   ├── coordination.ts     # 协同检测 API
        │   ├── propagation.ts      # 传播归因 API
        │   └── accounts.ts         # 账户监测 API
        │
        ├── views/                  # 页面视图
        │   ├── login/index.vue     # 登录页面
        │   ├── dashboard/index.vue # 监测看板（占位，见 ../doc/engineering/development-roadmap.md）
        │   ├── crawl/index.vue     # 数据采集管理
        │   ├── coordination/index.vue  # 协同网络可视化
        │   ├── propagation/index.vue   # 传播时间线与关键角色
        │   └── accounts/index.vue      # 账户画像列表
        │
        ├── components/
        │   ├── layout/
        │   │   └── BasicLayout.vue # 全局布局（侧边栏 + 顶栏 + 内容区）
        │   ├── PageHeader.vue
        │   └── TableSettings.vue   # 表格密度与分页条数
        │
        ├── stores/
        │   └── auth.ts             # Pinia 认证状态（Token + 用户信息）
        │
        ├── router/
        │   └── index.ts            # 路由配置 + 导航守卫
        │
        └── utils/
            └── request.ts          # Axios 实例（Token 注入 + 401 拦截）
```

## 环境要求

| 依赖 | 版本 | 必需 | 说明 |
|------|------|------|------|
| Python | ≥3.11 | 是 | 后端运行时 |
| Node.js | ≥18 | 是 | 前端构建 |
| Docker + Docker Compose | 最新 | 是 | MySQL/MongoDB/Redis 服务 |
| uv | 最新 | 推荐 | Python 包管理（可用 pip 替代） |

> 详细安装步骤见 [doc/engineering/environment-setup.md](../doc/engineering/environment-setup.md)

## 部署与启动

### 第一步：启动基础服务

```bash
cd system
cp .env.example .env        # 首次需要，按需修改密码
docker compose up -d         # 启动 MySQL + MongoDB + Redis
docker compose ps            # 确认所有服务 healthy
```

> `docker compose` 只负责 MySQL / MongoDB / Redis。社交与新闻采集运行时已 vendored 到仓库内部，后端会直接调用 `system/runtimes/*`。

### 统一分析 V2 入口

当前系统新增 `/api/v2/analysis/*` 作为 KT1、KT2、Student、Teacher 的统一入口层：

- `POST /api/v2/analysis/snapshots`：从 MongoDB `raw_posts` / `raw_comments` 生成不可变 `EventSnapshot`，并注册 MySQL manifest。
- `POST /api/v2/analysis/runs`：为一个 snapshot 创建 `AnalysisRun`，初始状态为 `queued`。
- `GET /api/v2/analysis/runs/{run_id}`：查询 run 当前状态。
- `GET /api/v2/analysis/runs/{run_id}/events?after_id=<id>`：REST 恢复路径，返回指定 cursor 之后的事件。
- `GET /api/v2/analysis/runs/{run_id}/events/stream`：SSE backlog 输出，支持 `Last-Event-ID` 恢复。

当前 V2 已完成输入、持久化、状态机和恢复路径。KT1/KT2/KT3 模型执行仍处于后续接线阶段，不应把该入口等同于三项关键技术的研究级完成。

KT2 当前只内置了 dashboard 可读的缓存 benchmark artifact，位于 `system/research/kt2/benchmark/`。未内置的 live runner、公开数据 loader 和 event checkpoint adapter 会返回明确的 unavailable，不再从外部 research workspace 动态 import。

### 第二步（可选）：配置并验证内置 social runtime

如果要采集 `weibo` / `xhs` / `douyin`，请先在 `system/.env` 中配置：

```dotenv
MEDIACRAWLER_LOGIN_TYPE=qrcode
MEDIACRAWLER_COOKIES=
MEDIACRAWLER_NODE_DIR=D:/node
MEDIACRAWLER_PROXY=http://127.0.0.1:7897
MEDIACRAWLER_GET_SUB_COMMENTS=true
MEDIACRAWLER_MAX_COMMENTS_PER_POST=200
```

说明：

- `MEDIACRAWLER_NODE_DIR` 适用于 Node.js 已安装但没有加入系统 `PATH` 的机器；后端会在调用 MediaCrawler 时自动把该目录注入子进程 `PATH`。
- `MEDIACRAWLER_PROXY` 适用于 Clash Verge TUN / 虚拟网卡 / fake-ip 模式下浏览器进程无法直连目标站点的情况；当前本机可用端口验证为 `http://127.0.0.1:7897`。配置后，后端会把代理注入 MediaCrawler 子进程，并让 CDP Chrome 通过 `--proxy-server` 显式走代理。
- `MEDIACRAWLER_GET_SUB_COMMENTS=true` 会把内置 social runtime 的二级评论抓取打开；当前上游能力上限就是“一级评论 + 二级评论”，不是无限递归整棵评论树。
- `MEDIACRAWLER_MAX_COMMENTS_PER_POST` 会把单帖评论抓取上限提升到你配置的值；`200` 适合事件级联调，热点事件可按机器性能继续上调。
- `toutiao` 不属于社交 runtime 支持范围，在 CogGuard 中应走 `news` 采集链路。
- 内置 social runtime 原始抓取结果写入 `system/runtimes/social_runtime/data/<platform>/jsonl/`。
- 当前社交平台采集链路只读取本次 crawl 新增的 JSONL 行，不再整份回读当天文件。

当前这条 `weibo / xhs / douyin` 采集链路，入库后的保真策略是：

- 帖子保留标准字段，同时把原始 runtime JSONL 行完整落到 `raw_data`
- 评论保留 `reply_to`、`sub_comment_count`、`author_id`，可还原两层评论树
- 帖子和评论都会额外保留 `author_profile`
- 帖子 / 评论里的图片、视频、封面、音频等可解析媒体链接会归一到 `media_urls`
- 微博搜索结果会在内置 social runtime 侧对每条帖子补抓详情 raw，并把 `pics`、`thumbnail_pic`、`bmiddle_pic`、`original_pic`、`page_info`、`mix_media_info`、`media_urls`、`post_details_raw` 写入 JSONL；CogGuard 会从这些字段中提取微博图片、视频、封面链接。

如果你需要“作者主页级”的完整粉丝数 / 关注数 / 简介等资料，上游要走 `creator` 模式；当前 CogGuard 这一版先保留搜索结果里已有的用户字段，并把两层评论链路对齐好。

采集 API 还支持三个可选参数，用于把后续增强点纳入同一条任务链：

```json
{
  "recursive_comments": true,
  "enrich_author_profiles": true,
  "comment_sort": "like_count_desc"
}
```

- `recursive_comments=true` 表示请求完整递归评论树；当前内置 runtime 会降级到上游实际支持的两层评论，并在 `crawl_metadata.effective_comment_depth=2`、`recursive_comments_supported=false` 中显式记录。
- `enrich_author_profiles=true` 表示请求作者主页级画像补全；当前搜索链路先记录请求并保留搜索结果已有的 `author_profile`，真正的主页级补全需要后续串接 runtime `creator` 模式。
- `comment_sort` 支持 `none`、`like_count_desc`、`reply_count_desc`，分别表示不排序、按点赞数倒序、按被回复数倒序；排序发生在评论入库前。

准备内置 runtime 依赖并执行校验：

```bash
cd runtimes/social_runtime
uv sync
uv run playwright install chromium

cd ../news_runtime/news_extractor_core
uv sync

cd ../../backend
uv run python scripts/verify_mediacrawler_env.py
```

### 第三步：启动后端

```powershell
cd G:\CISCN\CogGuard\system\backend
$env:UV_CACHE_DIR='G:\CISCN\CogGuard\system\backend\.uv-cache'
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

启动成功后：
- API 文档：http://localhost:8000/docs（Swagger UI）
- 健康检查：http://localhost:8000/api/v1/health

### 第四步：启动前端

```powershell
cd G:\CISCN\CogGuard\system\frontend
npm.cmd install
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

启动成功后访问：http://localhost:5173

#### 前端预览入口（免登录）

如果只需要查看前端页面结构、导航和功能设计，而本机暂时没有启动 MySQL / MongoDB / Redis，可以使用预览入口绕过真实登录：

```powershell
cd G:\CISCN\CogGuard\system\backend
$env:UV_CACHE_DIR='G:\CISCN\CogGuard\system\backend\.uv-cache'
.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

cd ..\frontend
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

然后访问：

- 预览入口：http://127.0.0.1:5173/preview
- 等价入口：http://127.0.0.1:5173/?preview=1

预览入口会在浏览器本地写入临时 `Preview` 用户身份，跳过路由登录守卫并进入主界面。它只用于查看前端信息架构和页面设计；需要真实数据、注册登录、采集任务、协同/传播/账号/风险接口联调时，仍需按第一步启动 MySQL / MongoDB / Redis，并使用真实账号登录。

注意：

- 后端 `uvicorn` 和前端 `vite` 必须保持运行，关闭任一终端后预览都会中断。
- 如果你只是要快速查看页面，可以直接执行项目根目录下的 `start-preview.ps1`：

```powershell
cd G:\CISCN\CogGuard\system
powershell.exe -ExecutionPolicy Bypass -File .\start-preview.ps1
```

### 第五步（可选）：启动 Celery Worker

采集任务的异步执行需要 Celery Worker：

```bash
cd backend
celery -A app.celery_app worker --loglevel=info -Q crawl
```

> 如果不启动 Worker，采集任务会被提交但不会执行。
> 测试阶段可直接调用 MockCrawler 的单元测试验证数据生成。

## 测试

### 运行测试

```bash
cd backend

# 运行所有测试（MySQL 不可用的测试会自动跳过）
uv run pytest -v

# 仅运行不需要外部服务的单元测试
uv run pytest tests/test_crawl.py tests/test_health.py -v

# 仅验证 MediaCrawler 环境解析与脚本逻辑
uv run pytest tests/test_mediacrawler_env.py -v

# 运行认证测试（需要 MySQL 运行中）
uv run pytest tests/test_auth.py -v
```

### 测试覆盖

| 测试文件 | 内容 | 外部依赖 |
|---------|------|---------|
| `test_health.py` | 健康检查接口 | 无 |
| `test_crawl.py` | MockCrawler 数据生成、Normalizer 字段映射、平台列表、鉴权校验 | 部分需 MySQL |
| `test_mediacrawler_env.py` | 内置 social runtime 的 `uv` / `node` / 路径解析 | 无 |
| `test_auth.py` | 注册、登录、密码错误、Token 鉴权、Token 刷新 | MySQL |

### 预期测试结果

```
tests/test_health.py::test_health_check                    PASSED
tests/test_crawl.py::test_mock_crawler_generates_posts     PASSED
tests/test_crawl.py::test_mock_crawler_generates_comments  PASSED
tests/test_crawl.py::test_mock_crawler_coordinated_pattern PASSED
tests/test_crawl.py::test_normalizer_standardizes_weibo_post PASSED
tests/test_crawl.py::test_normalizer_standardizes_comment  PASSED
tests/test_crawl.py::test_list_platforms                   PASSED
tests/test_crawl.py::test_create_crawl_job_requires_auth   SKIPPED (MySQL不可用时)
tests/test_auth.py::test_register_success                  PASSED/SKIPPED
tests/test_auth.py::test_login_success                     PASSED/SKIPPED
...
```

## 使用方式

### 1. 用户注册与登录

1. 打开前端 http://localhost:5173，自动跳转到登录页
2. 首次使用需要通过 API 注册：

```bash
# 注册用户
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "email": "admin@cogguard.com", "password": "admin123"}'

# 登录获取 Token
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

3. 登录成功后系统自动保存 Token，跳转到监测看板

### 2. 数据采集（Mock 模式）

1. 进入"数据采集"页面
2. 选择平台 → "模拟微博（测试）"
3. 输入关键词（如"热点事件"），设置最大帖子数
4. 点击"开始采集" → 任务进入队列
5. 任务列表中查看状态（需要 Celery Worker 运行才能执行）
6. 数据表格中查看采集到的帖子

### 3. API 文档

启动后端后访问 http://localhost:8000/docs，可查看和测试所有接口。

## 当前限制与优化方向

### 爬虫模块
- **当前**：MockCrawler 与真实爬虫封装都已接入；真实平台仍以本地/联调验证为主
- **后续**：补充更稳定的端到端验证、失败回放与更多场景样例

### 协同检测
- **当前**：已实现基于共享对象的协同检测、加权网络、账户/群组统计与前端可视化
- **后续**：补充多行为边（时间同步、共链接、共媒体、语义近似、传播互动）与显著性筛查

### 传播监控
- **当前**：已实现传播子图、时间线、关键角色识别与高危实体排序
- **后续**：补充证据链生成、关键路径展示与更强的隐式传播边建模

### 账户监测
- **当前**：已实现账户行为画像、自动化倾向评分，以及 `POST /api/v1/accounts/bot-detection` 的 BotRHG 风格账号级社交机器人检测。该接口从已采集帖子中构造 profile/text/activity 特征，生成 KNN 支持超边，按局部可靠性选择低可靠账号做残差修正，并返回 base/final bot 概率、路由状态、support evidence 与 model card。
- **前端**：账户监测页已提供轻量 BotRHG 触发入口和结果表，展示账号数、路由数、bot 数、最终 bot 概率、局部可靠性与 support 节点。
- **后续**：补充历史参与追踪、中文 NLP 特征、跨事件画像聚合，以及前端 BotRHG 证据详情深度展示。

### 报告研判
- **当前**：未实现
- **后续**：在 `core/risk/` 中实现三维评估（真实性/操纵性/危害性）、规则引擎、DISARM 映射与结构化报告生成
- **LLM 接口**：后续仅作为桥接与解释增强，不作为第一阶段最终裁决来源

### 图数据库
- **当前**：使用 NetworkX 内存图分析
- **后续**：可扩展到 Neo4j 做持久化图存储和复杂图查询

### 前端可视化
- **当前**：采集、协同检测、传播监控、账户监测页面已具备 MVP；看板/风险/报告页仍待完善
- **后续**：补充监测看板、风险工作台、预警中心与报告中心

### 部署
- **当前**：本地开发部署（手动启动各服务）
- **后续**：Dockerfile 化后端和前端，完整 Docker Compose 一键启动全栈

## API 接口一览

### 认证模块

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/api/v1/auth/register` | 用户注册 | 否 |
| POST | `/api/v1/auth/login` | 用户登录，返回 Token | 否 |
| POST | `/api/v1/auth/refresh` | 刷新 Token | 否 |
| GET  | `/api/v1/auth/profile` | 获取当前用户信息 | 是 |

### 数据采集模块

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET  | `/api/v1/crawl/platforms` | 获取支持的平台列表 | 否 |
| POST | `/api/v1/crawl/social` | 创建社交媒体采集任务 | 是 |
| GET  | `/api/v1/crawl/jobs` | 获取采集任务列表 | 是 |
| GET  | `/api/v1/crawl/data` | 查询已采集的帖子数据 | 是 |

### 协同检测模块

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| POST | `/api/v1/coordination/detect` | 执行协同检测并返回网络/统计结果 | 是 |

### 传播监控模块

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET  | `/api/v1/propagation/analyze` | 分析传播子图、时间线和关键角色 | 是 |

### 账户监测模块

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET  | `/api/v1/accounts/profiles` | 获取账户画像列表 | 是 |
| POST | `/api/v1/accounts/bot-detection` | 执行 BotRHG 风格社交机器人检测，支持 `event_id` / `platform` / `routing_budget` / `support_k` | 是 |
| GET  | `/api/v1/accounts/detail/{id}` | 获取单账户详细画像 | 是 |

### 系统

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET  | `/api/v1/health` | 健康检查 | 否 |
