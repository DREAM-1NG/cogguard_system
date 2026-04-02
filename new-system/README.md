# CogGuard 系统开发文档

## 实际目录结构

```
new-system/
├── docker-compose.yml              # Docker 服务编排（MySQL + MongoDB + Redis）
├── .env.example                    # 环境变量模板（复制为 .env 使用）
├── .env                            # 实际环境变量（不提交到 Git）
│
├── backend/                        # 后端服务 (Python 3.11+ / FastAPI)
│   ├── pyproject.toml              # 项目元数据与依赖管理 (uv)
│   ├── requirements.txt            # pip 兼容依赖列表
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
│   │   │   └── v1/
│   │   │       ├── router.py       # v1 路由聚合 + 健康检查接口
│   │   │       ├── auth.py         # 认证接口（注册/登录/刷新/个人信息）
│   │   │       └── crawl.py        # 数据采集接口（创建任务/任务列表/数据查询）
│   │   │
│   │   ├── core/                   # 核心业务逻辑
│   │   │   ├── security.py         # JWT 认证 + bcrypt 密码哈希
│   │   │   └── crawler/            # 爬虫引擎
│   │   │       ├── base.py         # 爬虫抽象基类（定义统一接口）
│   │   │       ├── mock.py         # 模拟数据爬虫（生成含协同模式的测试数据）
│   │   │       └── normalizer.py   # 跨平台数据标准化器
│   │   │
│   │   ├── models/                 # 数据库模型
│   │   │   ├── user.py             # 用户表 (MySQL/SQLAlchemy)
│   │   │   ├── task.py             # 采集任务表 (MySQL/SQLAlchemy)
│   │   │   └── post.py             # 帖子/评论文档模型 (MongoDB/Pydantic)
│   │   │
│   │   ├── schemas/                # Pydantic 请求/响应模式
│   │   │   ├── auth.py             # 认证相关（Login/Register/Token/UserInfo）
│   │   │   └── crawl.py            # 采集相关（CrawlRequest/JobResponse/PostResponse）
│   │   │
│   │   ├── services/               # 业务服务层
│   │   │   ├── auth_service.py     # 认证业务（注册/登录/刷新/用户信息）
│   │   │   └── crawl_service.py    # 采集业务（任务管理/数据查询）
│   │   │
│   │   ├── tasks/                  # Celery 异步任务
│   │   │   └── crawl_tasks.py      # 采集任务执行（调用 MockCrawler → MongoDB）
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
│       └── test_crawl.py           # 采集模块测试（含纯单元测试）
│
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
        │   └── crawl.ts            # 采集 API（创建任务/任务列表/数据查询）
        │
        ├── views/                  # 页面视图
        │   ├── login/index.vue     # 登录页面
        │   ├── dashboard/index.vue # 监测看板（占位）
        │   └── crawl/index.vue     # 数据采集管理
        │
        ├── components/
        │   └── layout/
        │       └── BasicLayout.vue # 全局布局（侧边栏 + 顶栏 + 内容区）
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

> 详细安装步骤见 [doc/ENV_SETUP.md](../doc/ENV_SETUP.md)

## 部署与启动

### 第一步：启动基础服务

```bash
cd new-system
cp .env.example .env        # 首次需要，按需修改密码
docker compose up -d         # 启动 MySQL + MongoDB + Redis
docker compose ps            # 确认所有服务 healthy
```

### 第二步：启动后端

```bash
cd backend
uv sync                      # 安装依赖（或 pip install -r requirements.txt）
alembic upgrade head          # 执行数据库迁移（创建 users/crawl_jobs 表）
uvicorn app.main:app --reload --port 8000
```

启动成功后：
- API 文档：http://localhost:8000/docs（Swagger UI）
- 健康检查：http://localhost:8000/api/v1/health

### 第三步：启动前端

```bash
cd frontend
npm install                   # 安装依赖（国内建议先 npm config set registry https://registry.npmmirror.com）
npm run dev                   # 启动开发服务器
```

启动成功后访问：http://localhost:5173

### 第四步（可选）：启动 Celery Worker

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

# 运行认证测试（需要 MySQL 运行中）
uv run pytest tests/test_auth.py -v
```

### 测试覆盖

| 测试文件 | 内容 | 外部依赖 |
|---------|------|---------|
| `test_health.py` | 健康检查接口 | 无 |
| `test_crawl.py` | MockCrawler 数据生成、Normalizer 字段映射、平台列表、鉴权校验 | 部分需 MySQL |
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
- **当前**：使用 MockCrawler 生成模拟数据，不连接真实平台
- **后续**：封装 MediaCrawler（社交媒体采集）和 NewsCrawler（新闻采集）作为真实数据源
- **接入方式**：实现 `BaseCrawler` 接口，在 `crawl_tasks.py` 中按平台名路由到对应爬虫

### 协同检测
- **当前**：未实现
- **后续**：在 `core/coordination/` 中用 Python 重写 CooRTweet 核心算法（时间窗口内共享行为检测 + 协同网络构建）

### 传播归因
- **当前**：未实现
- **后续**：在 `core/propagation/` 中实现传播子图构建、关键角色识别、传播路径分析

### 账户监测
- **当前**：未实现
- **后续**：在 `core/account/` 中实现行为画像、自动化倾向评估、历史追踪

### 风险研判
- **当前**：未实现
- **后续**：在 `core/risk/` 中实现三维评估（真实性/操纵性/危害性）、规则引擎、报告生成
- **LLM 接口**：已预留 `llm_bridge.py`，后续可接入通义千问/DeepSeek 等

### 图数据库
- **当前**：使用 NetworkX 内存图分析
- **后续**：可扩展到 Neo4j 做持久化图存储和复杂图查询

### 前端可视化
- **当前**：监测看板为占位页面，协同检测/传播归因等页面尚未开发
- **后续**：接入 ECharts 图表、vis-network/D3.js 网络可视化

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

### 系统

| 方法 | 路径 | 说明 | 鉴权 |
|------|------|------|------|
| GET  | `/api/v1/health` | 健康检查 | 否 |
