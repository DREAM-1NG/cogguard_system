# CogGuard 环境搭建指南

> **用途**：说明本地/部署环境、基础服务、后端、前端、测试和可选 ARIS 开发方式。  
> **受众**：开发者、部署者、后续执行任务的 AI agent。  
> **维护规则**：只记录可复现的运行步骤；环境变量、端口、启动命令变化必须同步本文和 `../../new-system/README.md`。

## 1. 前置依赖

| 工具 | 版本要求 | 下载地址 |
|------|---------|---------|
| Docker Desktop | 最新 | https://www.docker.com/products/docker-desktop/ |
| Python | ≥3.11 | https://www.python.org/downloads/ |
| Node.js | ≥18 | https://nodejs.org/ |
| uv (可选) | 最新 | https://docs.astral.sh/uv/getting-started/installation/ |

## 2. Windows 快速启动（推荐）

按下面顺序即可直接拉起数据库、后端和前端：

```powershell
cd G:\CISCN\cogguard_system\new-system
docker compose up -d
docker compose ps

cd .\backend
$env:UV_CACHE_DIR='G:\CISCN\cogguard_system\new-system\backend\.uv-cache'
uv sync
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

cd ..\frontend
npm.cmd install
npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

常用检查命令：

```powershell
Invoke-WebRequest -Uri http://127.0.0.1:8000/api/v1/health -UseBasicParsing
npm.cmd run build
```

预览入口：

- http://127.0.0.1:5173/preview
- http://127.0.0.1:5173/?preview=1

## 3. 安装 Docker Desktop (Windows)

### 3.1 启用 WSL2

以管理员身份打开 PowerShell，执行：

```powershell
wsl --install
```

重启电脑后，WSL2 默认启用。

### 3.2 安装 Docker Desktop

1. 下载 Docker Desktop: https://www.docker.com/products/docker-desktop/
2. 运行安装程序，勾选 **Use WSL 2 instead of Hyper-V**
3. 安装完成后重启电脑
4. 启动 Docker Desktop，等待其初始化完成

### 3.3 验证安装

```powershell
docker --version
docker compose version
```

## 4. 启动基础服务

```bash
cd new-system

# 复制环境变量（首次需要）
cp .env.example .env

# 启动 MySQL + MongoDB + Redis
docker compose up -d

# 查看服务状态
docker compose ps

# 查看日志（如有问题）
docker compose logs -f
```

服务端口：

| 服务 | 端口 | 说明 |
|------|------|------|
| MySQL | 3306 | 用户名 cogguard / 密码 cogguard123 |
| MongoDB | 27017 | 用户名 cogguard / 密码 cogguard123 |
| Redis | 6379 | 密码 cogguard123 |

## 5. 真实爬虫（可选）

社交与新闻采集核心已经内置在 `system/runtimes/`，不需要配置外部仓库路径或单独启动新闻后端。`docker compose` 仍只负责 MySQL、MongoDB 和 Redis；crawler runtime 在宿主机由后端直接调用。

- **Social runtime**：支持 `weibo` / `xhs` / `douyin`，按需配置登录、Cookie、Node.js 和代理。
- **News runtime**：支持 detector 驱动的文章 URL 提取，不读取 `NEWSCRAWLER_API_BASE` 或 `NEWSCRAWLER_ROOT`。
- **Toutiao / 头条**：使用 `news` 平台和文章 URL，不进入 social runtime。

建议的本机配置示例：

```dotenv
MEDIACRAWLER_LOGIN_TYPE=qrcode
MEDIACRAWLER_COOKIES=
MEDIACRAWLER_NODE_DIR=D:/node
MEDIACRAWLER_PROXY=http://127.0.0.1:7897
MEDIACRAWLER_GET_SUB_COMMENTS=true
MEDIACRAWLER_MAX_COMMENTS_PER_POST=200
```

如果本机开启 Clash Verge 的 TUN / 虚拟网卡 / fake-ip 模式，并且目标站点解析到 `198.18.x.x` 后出现 `ERR_NETWORK_ACCESS_DENIED`，请配置 `MEDIACRAWLER_PROXY` 指向 Clash 的本地 HTTP 代理端口。CogGuard 会把该值传给 MediaCrawler 子进程，并让 CDP Chrome 通过 `--proxy-server` 显式走代理；同时也会设置 `HTTP_PROXY` / `HTTPS_PROXY`，供 MediaCrawler 内部 HTTP 客户端使用。当前本机 Clash Verge 验证可用端口为 `http://127.0.0.1:7897`。

首次准备内置运行时：

```bash
cd system/runtimes/social_runtime
uv sync --frozen
uv run playwright install chromium

cd ../news_runtime
uv sync --frozen
```

补充说明：

- `MEDIACRAWLER_GET_SUB_COMMENTS=true` 会启用上游的二级评论抓取；这已经是当前 MediaCrawler 对评论树的能力上限。
- `MEDIACRAWLER_MAX_COMMENTS_PER_POST=200` 会覆盖上游默认的单帖评论上限 `10`，更适合事件级多平台对齐采集。
- `MEDIACRAWLER_PROXY` 只在需要代理时配置；关闭 Clash 或切换为系统全局代理可留空。
- `douyin` 现已补充更稳健的登录态判断：除了 `HasUserLogin` / `LOGIN_STATUS`，还会识别持久化 `sessionid(_ss)` + `xmst` 等会话信号；如果扫码后进入“验证码中间页”，轮询期间也会继续处理滑块验证，而不是固定等待后直接判失败。
- CogGuard 当前会把帖子 / 评论的原始 JSONL 行保留在 `raw_data`，并把可解析的多模态链接归一到 `media_urls`；评论侧还会保留 `reply_to` 和 `sub_comment_count`，方便还原两层评论树。
- 采集请求可额外传 `recursive_comments`、`enrich_author_profiles`、`comment_sort`。其中 `recursive_comments` 和 `enrich_author_profiles` 目前会写入 `crawl_metadata` 并按当前 MediaCrawler 能力降级执行；`comment_sort` 已支持 `none`、`like_count_desc`、`reply_count_desc`。
- social runtime 原始抓取结果默认落在 `system/runtimes/social_runtime/data/<platform>/jsonl/`。
- CogGuard 当前社交采集任务会直接执行内置 runtime，然后只读取本次运行新增的 JSONL 行再入库；不会整份回读当天文件。
- 微博搜索链路会在 `ENABLE_WEIBO_FULL_TEXT=true` 时对每条搜索结果补抓详情页 raw，而不再只补长文本；输出行会保留 `pics` / `page_info` / `mix_media_info` 等 mblog 媒体字段、`media_urls` 和 `post_details_raw`，方便 CogGuard 后续归一化图片、视频与封面链接。

## 6. 启动后端

```bash
cd new-system/backend

# 方式一：使用 uv（推荐）
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# 方式二：使用 pip
python -m venv .venv
.venv\Scripts\activate      # Windows
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

后端启动后访问：
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/api/v1/health

如果需要验证内置 social runtime 是否就绪，可执行：

```bash
cd new-system/backend
uv run python scripts/verify_mediacrawler_env.py
```

该脚本会检查内置 runtime 入口、冻结 Python 环境、Node.js 注入、Playwright Chromium，以及 `weibo` / `xhs` / `douyin` 平台路由。新闻 runtime 可在 `system/runtimes/news_runtime` 执行 `uv run --frozen python -c "from news_extractor_core.services.extractor import ExtractorService"` 验证。

## 7. 启动前端

```bash
cd new-system/frontend

npm install
npm run dev
```

前端启动后访问: http://localhost:5173

### 7.1 前端预览入口（免登录）

当目标只是查看前端页面、导航结构和功能设计，而本机暂时没有启动 MySQL / MongoDB / Redis 时，可以使用前端预览入口：

```bash
# 启动后端 API 壳，至少保证健康检查和 Vite 代理目标存在
cd new-system/backend
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 启动前端开发服务器
cd ../frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

Windows PowerShell 如果因为执行策略无法运行 `npm.ps1`，使用 `npm.cmd`：

```powershell
D:/node/npm.cmd run dev -- --host 127.0.0.1 --port 5173
```

访问以下任一地址进入预览态：

- http://127.0.0.1:5173/preview
- http://127.0.0.1:5173/?preview=1

该入口会在浏览器本地写入临时 `Preview` 用户身份，跳过前端路由登录守卫并直接进入主界面。预览态只用于评估页面结构和交互设计；若要验证注册登录、数据采集、协同检测、传播分析、账号画像和报告研判等真实数据链路，必须先按第 3 节启动 MySQL / MongoDB / Redis，并使用真实账号登录。

补充说明：

- 预览并不是静态 HTML 截图，`uvicorn` 和 `vite` 都必须保持常驻运行；关闭任一终端窗口后，`/preview` 都会失效。
- 如果只是想快速打开前端预览，可以直接运行项目根目录下的 `start-preview.ps1`，它会自动弹出两个 PowerShell 窗口分别启动后端和前端。

```powershell
cd G:\CISCN\cogguard_system\new-system
powershell.exe -ExecutionPolicy Bypass -File .\start-preview.ps1
```

## 8. 运行测试

```bash
cd new-system/backend

# 安装含 pytest 的开发依赖后运行全部测试
uv sync --extra dev
uv run pytest -v

# 或使用 pip 环境
pytest -v
```

## 9. ARIS / Claude / Codex 可选开发方式

如果本次任务不是直接手写实现，而是要通过 ARIS 工作流驱动，请使用仓库内的本地适配层，而不是在根目录临时堆放 prompt 和日志。

### 8.1 必读入口

开始前先读：

1. `AGENTS.md`
2. `doc/engineering/development-roadmap.md`
3. `new-system/README.md`
4. `aris/README.md`
5. 目标 `aris/tech-*/README.md`
6. 对应 `doc/research/key-technology-background/*.md`

### 8.2 本地运行

1. 从 `release-0.2` 起分支：`aris/t1-*`、`aris/t2-*`、`aris/t3-*`
2. 进入目标工作空间，例如 `aris/tech-01-coordination/`
3. 仅在该工作空间允许的路径内实现
4. 按上游 ARIS 文档安装外部 skill：
   - 上游 README：<https://github.com/wanshuiyin/Auto-claude-code-research-in-sleep>
   - Codex/Claude 兼容说明：<https://raw.githubusercontent.com/wanshuiyin/Auto-claude-code-research-in-sleep/main/docs/CODEX_CLAUDE_REVIEW_GUIDE.md>
5. Claude Code 与 Codex 的本仓运行步骤见 `aris/shared/RUNNERS.md`

### 8.3 远端 GPU 运行

- 当技术线需要句向量、中文编码器或批量实验时，再切到远端 GPU
- 本仓只保留模板：`aris/shared/GPU_SETUP_TEMPLATE.md`
- 真实主机、密钥、token、路径映射请写入本地未跟踪文件或系统环境变量，不写入仓库
- 实验输出默认保留本地或远端，不提交到 Git

### 8.4 安全约束

- 不在仓库内提交任何 SSH 私钥、API Key、Cookie、GPU 主机信息
- 不把 `outputs/`、`logs/`、`refine-logs/` 等原始实验产物纳入版本控制
- 如果某轮实验有结论，只把稳定摘要回写到 `TASK_TRACKER.md`、`EXPERIMENT_PLAN.md` 或 `doc/engineering/development-log.md`

## 10. 停止服务

```bash
cd new-system
docker compose down          # 停止容器（保留数据）
docker compose down -v       # 停止并删除数据卷
```

## 11. 在其他电脑部署

1. 安装 Docker Desktop、Python ≥3.11、Node.js ≥18
2. 克隆项目代码
3. `cd new-system && cp .env.example .env`
4. 按需修改 `.env` 中的密码等配置
5. `docker compose up -d`
6. 按第 5、6 节启动后端和前端

## 12. 常见问题

**Q: Docker 启动失败？**
- 确认 WSL2 已启用：`wsl --status`
- 确认 Docker Desktop 正在运行
- Windows 需要启用虚拟化（BIOS 中开启 VT-x）

**Q: MySQL 连接被拒绝？**
- 等待 healthcheck 通过：`docker compose ps` 确认状态为 healthy
- 检查端口是否被占用：`netstat -ano | findstr 3306`

**Q: 前端无法连接后端？**
- 确认后端已启动在 8000 端口
- 检查 `vite.config.ts` 中的代理配置
