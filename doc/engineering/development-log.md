# 开发变更日志

> **用途**：按时间记录与本仓库相关的代码、配置、文档变更，便于追溯。  
> **受众**：开发者、评审者、后续维护 agent。  
> **维护规则**：每次完成一批可交付改动时追加条目；状态类变更同步 `development-roadmap.md`。

**用途**：按时间记录与本仓库相关的变更（代码、配置、文档），便于追溯。  
**写法**：每次合并或完成一批可交付改动时追加一条；只写**做了什么、动了哪些路径**，与 [development-roadmap.md](development-roadmap.md) 勾选同步。

**条目格式**（复制使用）：

```text
## YYYY-MM-DD

- 变更摘要（一句话）
- `路径/文件`：具体改动说明
```

---

## 2026-05-17

- 总指挥触发项目实施情况盘点（3 个 Explore 子代理并行调查代码 / 文档 / ARIS 工作空间），交叉核对后发现**代码进度大幅领先文档**，特别是 KT3 风险研判已默默实现而 README/roadmap 仍标"待开发"。本条目记录本次审计与首轮文档对齐动作。
- 代码盘点（实际验证）：
  - 后端约 5,664 行 Python，前端约 1,710 行 Vue/TS。
  - KT1 协同检测（旧方向 CooRTweet）：`core/coordination/` 452 行 MVP；KT1 新方向 PSL 设计已在 `aris/tech-01-coordination/systemDesign.md` 落盘，但 `new-system/` 尚无对应实现。
  - KT2 传播监控（Hybrid TS+LLM）：`core/propagation/` 含 4 个文件 ~673 行 → **WP1-3 完整完成**（`ts_features.py` 107 / `llm_context.py` 162 / `trend_predictor.py` 180 / `regime_model.py` 224）；**WP4 `stance_detector.py` 与 WP5 `harm_assessor.py` 完全未启动**；WP6-7 服务层与测试已存在但极薄。旧方向 `core/propagation_legacy.py` 仍在 import 路径并存。
  - KT3 风险研判：`core/risk/` 6 模块 1,340 行 + `services/risk_service.py` 153 行 + `api/v1/risk.py` 68 行 + `frontend/src/views/risk/index.vue` + `tests/test_risk.py` 348 行 — **MVP 已完成，端到端串通**，但 README/roadmap 此前仍标"待开发"。
- 文档对齐：
  - `README.md` 模块状态表：风险研判 `待开发 → MVP 已完成`；协同检测拆分新旧方向；传播监控按 WP1-3/WP4-5 分粒度；看板继续保留"待开发"（`dashboard/index.vue` 仍是占位）。
  - `doc/engineering/development-roadmap.md`：头注释日期 `2026-04-08 → 2026-05-17`；总览模块表细化到 WP 粒度；第 3.1 节风险研判模块由"🔲"翻面为"✅ MVP 已完成"，并把 8 个已完成子项打勾；保留 2 个未完成子项（alembic 迁移、LLM 桥接）。
  - ARIS 治理段：tech-03 落地条目勾选；tech-02 标 `[~]` 表示 WP1-3 已完、WP4-5 未启动。
- 仓库治理风险（本次未处理，需后续单独提交）：
  - `aris/`、`doc/engineering/`、`doc/research/`、`AGENTS.md`、`CLAUDE.md` 整体仍为 untracked，是项目最大单点风险。
  - `cogguard_system/memory/` 目录此前不存在但 `CLAUDE.md` 启动顺序引用之，本次同步新增 `memory/PLAYBOOK.md` 与 `state_kt{1,2,3}.md` 修补死链。
- 关联文件：本条目对应 `README.md`、`doc/engineering/development-roadmap.md`、`memory/PLAYBOOK.md`、`memory/state_kt{1,2,3}.md`、`aris/tech-02-propagation/TASK_TRACKER.md` 同步更新。

---

## 2026-05-10

- KT1 系统设计与 CCF-B+ 多模态检测文献综述一体化落盘（deep-interview 合并草案 v0.1）。
- `aris/tech-01-coordination/systemDesign.md`（新增）：单文件 12 节交付 —— 概述、问题陈述、系统功能 ↔ 关键技术错位矩阵（M1–M5）、系统架构、C2 搜索子系统（多模态展示承载）、C3 检测 MVP（PSL primary + ADR-001 fallback 文字契约）、跨 KT 输出契约、CCF-B+ 文献综述（24 条有效条目、9 字段强制）、工程时序原则 T1–T6、M0–M6 里程碑、验收对齐 ACCEPTANCE.md。
- 记录错位追踪：M1 多模态展示由 C2 承担（不纳入检测创新）；M2 跨平台改表述为"跨源"；M3 协同类型分类放 roadmap；M4 `detect_groups` IO 扩展 `evidence_samples[]` + `channels[]` + `q_adjusted`；M5 搜索子系统为 MVP 核心缺口。
- 关联文件：`aris/tech-01-coordination/{RESEARCH_BRIEF.md, LITERATURE_REFERENCES.md, refine-logs/FINAL_PROPOSAL.md, ACCEPTANCE.md, TASK_TRACKER.md}` 未改动，systemDesign.md 对其做引用聚合。

---

## 2026-04-08

- 完成仓库 ARIS 化重组，新增独立工作空间层与技术背景层，保证三条关键技术可分别驱动实现。
- `CLAUDE.md`、`README.md`、`AGENTS.md`、`.cursor/rules/cogguard-project-context.mdc`：补齐仓库入口、执行约束与 ARIS 阅读顺序。
- `aris/`：新增共享 runner 文档与 `tech-01-coordination`、`tech-02-propagation`、`tech-03-risk` 三个独立工作空间。
- `doc/research/key-technology-background/`、`doc/engineering/environment-setup.md`、`doc/engineering/development-roadmap.md`：补充技术背景、ARIS 开发方式与后续跟踪项。
- `.gitignore`：新增 ARIS 实验产物忽略规则。

---

## 2026-04-07

- 补充面向后续会话与 GitHub 开源协作的仓库上下文说明，明确 `release-0.2` 为当前工程基线。
- `AGENTS.md`：新增仓库级 agent context，约定必读文档、主线叙事、短期验证范围与协作约束。
- `.cursor/rules/cogguard-project-context.mdc`：同步更新为 `release-0.2` 基线与文档对齐规则。

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
- `doc/engineering/development-roadmap.md`：2.0 真实爬虫接入勾选。

---

## 2026-04-03

- 建立开发变更日志机制；同步文档与 `new-system` 说明。
- `doc/engineering/development-log.md`：新增本文件。
- `doc/engineering/development-roadmap.md`：参考资料增加指向本文件的链接。
- `doc/engineering/environment-setup.md`：常见问题章节增补条目。
- `new-system/README.md`：目录树与模块说明与当前后端（coordination / propagation / accounts 等）及前端页面对齐。

---
