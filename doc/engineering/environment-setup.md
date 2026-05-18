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

## 2. 安装 Docker Desktop (Windows)

### 2.1 启用 WSL2

以管理员身份打开 PowerShell，执行：

```powershell
wsl --install
```

重启电脑后，WSL2 默认启用。

### 2.2 安装 Docker Desktop

1. 下载 Docker Desktop: https://www.docker.com/products/docker-desktop/
2. 运行安装程序，勾选 **Use WSL 2 instead of Hyper-V**
3. 安装完成后重启电脑
4. 启动 Docker Desktop，等待其初始化完成

### 2.3 验证安装

```powershell
docker --version
docker compose version
```

## 3. 启动基础服务

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

## 4. 真实爬虫（可选）

在 `.env` 中配置（参见 `new-system/.env.example`）：

- **MediaCrawler**（微博等）：`MEDIACRAWLER_ROOT` 指向本机 MediaCrawler 仓库根目录；`MEDIACRAWLER_LOGIN_TYPE` / `MEDIACRAWLER_COOKIES` 按上游要求登录。
- **NewsCrawler**：`NEWSCRAWLER_API_BASE` 指向已启动的 `news_extractor_backend`（例如 `http://127.0.0.1:8020`），或配置 `NEWSCRAWLER_ROOT` 使用进程内提取。

## 5. 启动后端

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

## 6. 启动前端

```bash
cd new-system/frontend

npm install
npm run dev
```

前端启动后访问: http://localhost:5173

## 7. 运行测试

```bash
cd new-system/backend

# 安装含 pytest 的开发依赖后运行全部测试
uv sync --extra dev
uv run pytest -v

# 或使用 pip 环境
pytest -v
```

## 8. ARIS / Claude / Codex 可选开发方式

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

## 9. 停止服务

```bash
cd new-system
docker compose down          # 停止容器（保留数据）
docker compose down -v       # 停止并删除数据卷
```

## 10. 在其他电脑部署

1. 安装 Docker Desktop、Python ≥3.11、Node.js ≥18
2. 克隆项目代码
3. `cd new-system && cp .env.example .env`
4. 按需修改 `.env` 中的密码等配置
5. `docker compose up -d`
6. 按第 5、6 节启动后端和前端

## 11. 常见问题

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
