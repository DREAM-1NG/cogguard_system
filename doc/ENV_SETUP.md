# CogGuard 环境搭建指南

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

# （推荐）先创建项目专属数据目录，便于管理和清理
mkdir -p docker-data/mysql docker-data/mongo docker-data/redis

# 启动 MySQL + MongoDB + Redis
docker compose up -d

# 查看服务状态
docker compose ps

# 查看日志（如有问题）
docker compose logs -f
```

默认数据目录：

| 路径 | 说明 |
|------|------|
| `new-system/docker-data/mysql` | MySQL 数据文件 |
| `new-system/docker-data/mongo` | MongoDB 数据文件 |
| `new-system/docker-data/redis` | Redis 数据文件 |

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

## 8. 停止服务

```bash
cd new-system
docker compose down          # 停止容器（保留项目目录中的数据）
rm -rf docker-data           # 如需彻底清理本项目数据库数据，再手动删除项目数据目录
```

## 9. 在其他电脑部署

1. 安装 Docker Desktop、Python ≥3.11、Node.js ≥18
2. 克隆项目代码
3. `cd new-system && cp .env.example .env`
4. 按需修改 `.env` 中的密码等配置
5. `docker compose up -d`
6. 按第 5、6 节启动后端和前端

## 10. 常见问题

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
