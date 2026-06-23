# 开发变更日志

**用途**：按时间记录与本仓库相关的变更（代码、配置、文档），便于追溯。  
**写法**：每次合并或完成一批可交付改动时追加一条；只写**做了什么、动了哪些路径**，与 [TODO_LIST.md](TODO_LIST.md) 勾选同步。

**条目格式**（复制使用）：

```text
## YYYY-MM-DD

- 变更摘要（一句话）
- `路径/文件`：具体改动说明
```

---

## 2026-06-14

- 新增模块三风险研判 MVP：打通 harmful / stance / evidence / phase / DISARM / report / countermeasure 后端闭环。
- `new-system/backend/app/core/risk/`：新增启发式有害内容检测、立场检测、证据包构建、阶段评估、DISARM 映射、结构化报告与反制建议生成。
- `new-system/backend/app/services/risk_service.py`、`new-system/backend/app/api/v1/risk.py`、`new-system/backend/app/schemas/risk.py`、`new-system/backend/app/api/v1/router.py`：新增风险研判 API 与服务编排并接入路由。
- `new-system/backend/tests/test_risk.py`：新增并扩展模块三核心测试，覆盖真实数据分析、话题清洗与 `mock_weibo` 自动回退；已在项目本地 `.venv` 中执行 `python -m pytest tests/test_risk.py -q` 通过。
- `new-system/frontend/src/views/risk/index.vue`：补齐前端研判工作台收口，增加数据来源标识，区分已采集数据与 Mock 回退数据。
- `new-system/backend/app/services/risk_service.py`、`new-system/backend/app/core/risk/stance_detector.py`、`new-system/backend/app/core/risk/evidence_builder.py`：补充关键词/标签清洗、时间戳容错、`mock_weibo` 无数据时的自动回退能力，同时保持真实 `weibo` 仍严格依赖已采集微博数据。
- `doc/TODO_LIST.md`：同步风险研判模块状态、前端工作台与测试通过情况。
- `new-system/docker-compose.yml`、`new-system/.gitignore`、`doc/ENV_SETUP.md`、`new-system/README.md`：将基础服务持久化改为项目目录 `new-system/docker-data/` 挂载，便于隔离管理，降低对其他项目的影响。
- `new-system/backend/app/core/risk/llm_bridge.py`、`app/config.py`、`app/core/risk/__init__.py`、`app/services/risk_service.py`、`app/core/risk/report_builder.py`：补齐模块三 LLM 预留接口，统一返回配置状态、上下文和建议 Prompt，并接入结构化报告。
- Docker 本地联调：已接入 `docker.m.daocloud.io` 代理镜像并成功启动 MySQL / MongoDB / Redis；完成数据库迁移、后端 / Celery 启动、mock 采集、mock 风险研判、历史报告接口与页面登录联调。
- 真实微博链路：已补齐 `MediaCrawler` 本地运行回退（无全局 `uv` 时可回退到项目本地 Python），已为 `MediaCrawler-main` 补齐 Python 3.11 本地环境并成功采集真实微博数据（任务 4：`posts_count=5`，`comments_count=112`）。
- `new-system/backend/app/services/risk_service.py`：补充 `source_keyword` / `raw_data.source_keyword` 关键词匹配兼容，用于真实微博数据接入风险研判；当前真实微博采集、入库、查询、风险研判 API、历史报告列表与详情接口均已打通。
- `new-system/backend/app/core/crawler/social.py`、`new-system/.env`：补齐 `MediaCrawler` 本地运行回退和真实爬虫配置；已安装 `python@3.11`，为 `MediaCrawler-main` 创建本地 `.venv` 并完成依赖安装。
- 真实微博采集任务 `id=4`：已成功完成，结果为 `posts_count=5`、`comments_count=112`；`MediaCrawler-main/data/weibo/jsonl/` 已生成真实微博 JSONL 输出。
- 前端页面联调：已验证登录、主布局、风险研判页面可访问；`/risk` 页面可正常加载真实接口能力。
- 阶段1-4 研究复现 baseline：新增 `new-system/backend/app/core/risk/research/` 统一数据集 schema / 评估基线、harmful baseline、stance baseline 与推理入口；`RiskAssessRequest.analysis_mode` + `risk_service` 已支持 `rule/model` 双模式切换，模型不可用时自动回退为规则版。
- `new-system/backend/tests/test_risk_research.py`、`test_harmful_baseline.py`、`test_stance_baseline.py`、`test_risk_model_mode.py`：补齐研究复现最小闭环测试；当前阶段新增研究测试共 11 项通过。
- `new-system/backend/app/core/risk/research/trainers.py`、`tests/test_research_trainers.py`：补齐训练/评估流水线与模型工件生成测试，形成研究复现正式实验骨架；阶段 5 新增 2 项测试通过。
- `new-system/frontend/src/views/risk/index.vue`：完善研判工作台，支持历史报告详情加载、当前报告 JSON 导出、LLM 预留信息展示。
- `new-system/backend/tests/test_risk.py`：补充话题清洗、LLM 预留禁用态等 mock 驱动测试；已再次执行 `python -m pytest tests/test_risk.py -q`，共 6 项通过。
- `new-system/frontend`：已再次执行 `npm run build`，风险研判页面构建通过。
- Docker / 数据库 / 真实微博采集相关联调与验证按当前要求延后，待本机 Docker 环境就绪后再执行真实链路测试。
- 本地 Docker Desktop 已接入，基础服务通过 `docker.m.daocloud.io` 代理镜像成功启动；已完成数据库迁移、后端 / Celery 启动、mock 采集任务执行、采集数据查询、风险研判 API、历史报告列表与详情接口联调。
- `new-system/backend/app/services/risk_service.py`、`new-system/backend/tests/test_risk.py`：修复风险报告插入 Mongo 后 `_id/ObjectId` 污染响应对象的问题，并补充回归测试；当前 `tests/test_risk.py` 共 7 项通过。

---

## 2026-04-03（续）

- 规划发布分支 `release-0.2`；仓库内项目名称从 `new_workspace` 调整为 `cogguard_system`。
- `README.md`：项目结构根目录名改为 `cogguard_system/`。

---

## 2026-04-03（续）

- 新增 Cursor 项目规则，固化文档阅读顺序、变更同步要求与协作约束。
- `.cursor/rules/cogguard-project-context.mdc`：项目上下文与必读文档规则。
- `.cursor/rules/cogguard-change-sync.mdc`：代码变更后的文档同步规则。
- `.cursor/rules/cogguard-collaboration.mdc`：中文回复、方案确认、验证表述等协作规则。

---

## 2026-04-03（续）

- 接入真实爬虫：MediaCrawler 子进程 + News 提取 HTTP/本地 import；Celery 任务路由与失败落库；采集页支持文章链接。
- `new-system/backend/app/core/crawler/social.py`、`news.py`、`factory.py`：新增。
- `new-system/backend/app/tasks/crawl_tasks.py`、`app/config.py`、`app/services/crawl_service.py`、`app/api/v1/crawl.py`、`app/schemas/crawl.py`：路由与配置。
- `new-system/backend/pyproject.toml`、`requirements.txt`：补充 pandas/networkx/numpy（协同模块已有引用）。
- `new-system/backend/tests/test_crawler_real.py`、`test_auth.py`：新增/调整断言。
- `new-system/.env.example`：爬虫相关环境变量模板。
- `new-system/frontend/src/views/crawl/index.vue`：链接（post_ids）输入。
- `doc/TODO_LIST.md`：2.0 真实爬虫接入勾选。

---

## 2026-04-03

- 建立开发变更日志机制；同步文档与 `new-system` 说明。
- `doc/DEVELOPMENT_LOG.md`：新增本文件。
- `doc/TODO_LIST.md`：参考资料增加指向本文件的链接。
- `doc/ENV_SETUP.md`：常见问题章节增补条目。
- `new-system/README.md`：目录树与模块说明与当前后端（coordination / propagation / accounts 等）及前端页面对齐。

---
