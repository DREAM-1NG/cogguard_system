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
