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

## 2026-07-21

- 收口全局系统治理：新增统一术语表、系统治理文档和 ADR，要求后续代码变更同步文档、术语和架构决策。
- `UBIQUITOUS_LANGUAGE.md`：新增跨系统术语、别名禁用、run/job/task、artifact/checkpoint/model version、Teacher Silver 与 Selective Student 定义。
- `doc/engineering/system-governance.md`、`docs/adr/0002-system-governance-and-documentation-sync.md`：新增代码结构、公共边界、文档同步与长期迭代规则。
- `AGENTS.md`、`CLAUDE.md`、`README.md`、`system/README.md`、`doc/engineering/project-map.md`：同步 Codex/Claude 读取顺序、文档更新要求和当前产品根 `system/`。
- `system/backend/app/core/risk/kt3_teacher_silver.py`、`system/backend/app/core/risk/kt3_selective_student.py`：从 `kt3_trainable_post.py` 拆出 Teacher Silver 和 2+1 Selective Student 职责，原文件保留懒加载兼容导出。
- 追加收口 KT1 正式方法名：`Coordination Discover` / `Coordination Detect`，同步 `UBIQUITOUS_LANGUAGE.md`、`doc/engineering/system-governance.md`、`README.md`、`system/README.md` 和研究总览。
- `doc/engineering/environment-setup.md`、`doc/engineering/data-contract-mediacrawler.md`、`doc/research/key-technology-background/*.md`：把当前-facing 路径从历史产品根别名同步到 `system/`。
- `system/backend/app/api/v1/propagation.py`、`system/backend/app/services/propagation_service.py`：补传播分析 `node_limit` / `diffusion_node_limit` 的旧调用面兼容，避免新增参数打断旧替身和旧集成测试。
- 验证：`python -m pytest system/backend/tests/test_kt3_trainable_post.py system/backend/tests/test_governance_docs.py -q`；`python -m pytest system/backend/tests -q`（319 passed, 27 skipped）。
- 收口 KT3 PropagationTreeAgent 证据边界：新增 Thread Context / Propagation Context 术语、ADR 与工程说明，PHEME 转换保留 node-edge reply tree，离线 Agent runner 只在真实传播树上下文存在时插入 `PropagationTreeAgent`。
- `system/backend/app/core/risk/kt3_propagation_agent.py`、`system/backend/app/core/risk/kt3_propagation_context.py`、`system/backend/app/core/risk/kt3_graph_exporter.py`：新增字段约束型 Agent 契约、传播线程压缩上下文与 post-post `replies_to` / `reposts` / `quotes` 边导出，避免 claim-only 或 reaction-count-only 样本被伪装成传播树证据。
- `system/backend/tests/test_kt3_propagation_context.py`、`system/backend/tests/test_kt3_graph_exporter.py`、`system/backend/tests/test_governance_docs.py`：补 propagation context、图导出和 ADR 编号 / `__all__` 治理回归测试。

---

## 2026-07-02

- 接入 BotRHG 风格社交机器人检测后端能力，将 NLPCC 2026 投稿方法的“特征编码 → KNN 支持超边 → 可靠性路由 → 选择性残差修正”落为账号级 API 契约。
- `system/backend/app/core/bot_detection.py`：新增确定性 BotRHG 系统适配器，输出 base/final bot 概率、local reliability、routed hyperedge、support evidence 与 model card。
- `system/backend/app/services/bot_detection_service.py`、`system/backend/app/api/v1/accounts.py`：新增 `POST /api/v1/accounts/bot-detection`，支持 `event_id`、`platform`、`routing_budget`、`support_k`，复用现有 Mongo 事件过滤和预览 token 认证。
- `system/backend/tests/test_botrhg_bot_detection.py`：新增回归测试，覆盖路由/残差修正、服务过滤、API 参数传递。
- `system/frontend/src/api/accounts.ts`、`system/frontend/src/views/accounts/index.vue`：账户监测页新增轻量 BotRHG 触发入口和结果表。
- `doc/engineering/botrhg-social-bot-detection-plan.md`、`README.md`、`system/README.md`、`doc/engineering/development-roadmap.md`、`AGENTS.md`：同步当前真实代码根 `system/`、新增 BotRHG API 与研究边界。
- 验证：`python -m pytest tests/test_botrhg_bot_detection.py -q`、`uv run python -m pytest tests/test_botrhg_bot_detection.py -q`、`uv run python -m pytest tests/test_event_scoped_analysis.py tests/test_health.py tests/test_coordination_detector.py tests/test_coordination_network.py -q`、`npm.cmd run build`。

## 2026-05-21

- 增强 MediaCrawler 微博搜索媒体保真：搜索结果不再只对长文本微博补抓详情，而是在 `ENABLE_WEIBO_FULL_TEXT=true` 时对每条微博详情补抓，并把 mblog 图片、视频、封面字段与 detail raw 写入输出。
- `MediaCrawler-main/media_platform/weibo/core.py`：移除 `get_note_full_text()` 的 `isLongText` 限制，使搜索页每条微博都尝试请求 `get_note_info_by_id()`。
- `MediaCrawler-main/store/weibo/__init__.py`：新增 `_extract_mblog_media_fields()`，保留 `pics`、`pic_ids`、`pic_infos`、`thumbnail_pic`、`bmiddle_pic`、`original_pic`、`page_info`、`mix_media_info`、`media_urls`、`post_details_raw`。
- `new-system/backend/app/core/crawler/social.py`：微博标准化新增对顶层媒体字段和 `post_details_raw.raw` 的显式解析，将微博图片、视频、封面 URL 归一到 `StandardPost.media_urls`。
- `MediaCrawler-main/tests/test_weibo_media_fields.py`、`new-system/backend/tests/test_social_crawler_normalization.py`：新增回归测试，覆盖微博 mblog 媒体字段保留、非长文本详情补抓、detail raw 媒体链接归一化。
- `new-system/README.md`、`doc/engineering/environment-setup.md`：同步微博详情补抓与媒体字段保真说明。

---

## 2026-05-19

- 完成 MediaCrawler 宿主机环境对齐：后端配置改为同时读取 `new-system/.env` 与 `backend/.env`，并新增 Node.js 目录注入与环境验证脚本，方便在 Windows 本机自动启动 `weibo` / `xhs` / `douyin` 的采集链路。
- `new-system/backend/app/config.py`：新增 `PROJECT_ROOT`，`SettingsConfigDict` 同时读取仓库根 `.env` 与后端局部 `.env`，并新增 `MEDIACRAWLER_NODE_DIR`。
- `new-system/backend/app/core/crawler/mediacrawler_env.py`：新增 uv / python / node / PATH 解析与子进程环境构造。
- `new-system/backend/app/core/crawler/social.py`：MediaCrawler 子进程调用改为复用环境构造逻辑，并显式指定 Python 解释器。
- `new-system/backend/scripts/verify_mediacrawler_env.py`：新增环境烟雾测试脚本，检查 `MEDIACRAWLER_ROOT`、`uv`、`python`、`node`、`main.py`、Playwright Chromium 与平台路由说明。
- `new-system/backend/tests/test_mediacrawler_env.py`：新增解析逻辑回归测试。
- `new-system/.env`、`new-system/.env.example`：补充 `MEDIACRAWLER_PYTHON_BIN`、`MEDIACRAWLER_NODE_DIR` 与本机示例值。
- `doc/engineering/environment-setup.md`、`new-system/README.md`、`doc/engineering/development-roadmap.md`：补充宿主机运行方式、验证命令与 `toutiao` 路由说明。

---

## 2026-05-17

- 总指挥触发项目实施情况盘点（3 个 Explore 子代理并行调查代码 / 文档 / ARIS 工作空间），交叉核对后发现**代码进度大幅领先文档**，特别是 KT3 报告研判已默默实现而 README/roadmap 仍标"待开发"。本条目记录本次审计与首轮文档对齐动作。
- 代码盘点（实际验证）：
  - 后端约 5,664 行 Python，前端约 1,710 行 Vue/TS。
  - KT1 协同检测（旧方向 CooRTweet）：`core/coordination/` 452 行 MVP；KT1 新方向 PSL 设计已在 `aris/tech-01-coordination/systemDesign.md` 落盘，但 `new-system/` 尚无对应实现。
  - KT2 传播监控（Hybrid TS+LLM）：`core/propagation/` 含 4 个文件 ~673 行 → **WP1-3 完整完成**（`ts_features.py` 107 / `llm_context.py` 162 / `trend_predictor.py` 180 / `regime_model.py` 224）；**WP4 `stance_detector.py` 与 WP5 `harm_assessor.py` 完全未启动**；WP6-7 服务层与测试已存在但极薄。旧方向 `core/propagation_legacy.py` 仍在 import 路径并存。
  - KT3 报告研判：`core/risk/` 6 模块 1,340 行 + `services/risk_service.py` 153 行 + `api/v1/risk.py` 68 行 + `frontend/src/views/risk/index.vue` + `tests/test_risk.py` 348 行 — **MVP 已完成，端到端串通**，但 README/roadmap 此前仍标"待开发"。
- 文档对齐：
  - `README.md` 模块状态表：风险研判 `待开发 → MVP 已完成`；协同检测拆分新旧方向；传播监控按 WP1-3/WP4-5 分粒度；看板继续保留"待开发"（`dashboard/index.vue` 仍是占位）。
  - `doc/engineering/development-roadmap.md`：头注释日期 `2026-04-08 → 2026-05-17`；总览模块表细化到 WP 粒度；第 3.1 节风险研判模块由"🔲"翻面为"✅ MVP 已完成"，并把 8 个已完成子项打勾；保留 2 个未完成子项（alembic 迁移、LLM 桥接）。
  - ARIS 治理段：tech-03 落地条目勾选；tech-02 标 `[~]` 表示 WP1-3 已完、WP4-5 未启动。
- 仓库治理风险（本次未处理，需后续单独提交）：
  - `aris/`、`doc/engineering/`、`doc/research/`、`AGENTS.md`、`CLAUDE.md` 整体仍为 untracked，是项目最大单点风险。
  - `cogguard_system/memory/` 目录此前不存在但 `CLAUDE.md` 启动顺序引用之，本次同步新增 `memory/PLAYBOOK.md` 与 `state_kt{1,2,3}.md` 修补死链。
- 关联文件：本条目对应 `README.md`、`doc/engineering/development-roadmap.md`、`memory/PLAYBOOK.md`、`memory/state_kt{1,2,3}.md`、`aris/tech-02-propagation/TASK_TRACKER.md` 同步更新。

---

## 2026-05-23

- 完成 F-ACCT（深度账号画像）的功能细化：从 5 个子功能扩展为 6 个，新增 **F-ACCT-6 单用户主页采集与内容巡检**。该子功能定位为"按主页链接/用户 ID 抓取主页元数据 + 全部发文 + 对全部内容做风险/立场/模板化检测"，不引入新算法，全部复用上游能力（KT2 WP4 立场 / KT2 WP5 危害 / F-COORD 通道模板）。
- 关键设计决策：
  - **复用 MediaCrawler creator 模式**，不新增爬虫。在 `core/crawler/social.py` 扩展 `mode=creator` 参数，`homepage_collector.py` 通过该入口调用。weibo / douyin / xhs 已支持。
  - **三段流水线**：homepage_collector（主页采集）→ content_checker（按帖批处理调用上游）→ account_service（详情页响应组装）。
  - **mock fallback 策略**：上游算法（KT2 WP4/5、F-COORD 通道）未完成时，content_checker 仅给规则化结果并标 `data_completeness="partial"`，前端用占位符渲染，确保 F-ACCT-6 可独立先行。
- 文档同步：
  - `doc/engineering/F-ACCT-account-profiling.md`：§ 3.5 新增 F-ACCT-6 完整技术方案（架构 + schema + 降级 + research/engineering 拆分）；§ 4.3 新增 `account_homepage` 表 SQL；§ 5.2 新增 `homepage_collector.py` / `content_checker.py` / `social.py mode=creator` 扩展 / `models/account_homepage.py` / 账户详情页等 7 项待新增；§ 6.2 新增 E11-E15 五项 P1 任务；§ 7.1 新增 2 条关键决策（决策 6 复用 MediaCrawler、决策 7 全部复用上游）；§ 8.5 新增 F-ACCT-6 → 上游算法的契约说明；§ 10 三周计划全部纳入 F-ACCT-6 工作量。
  - `doc/engineering/research-engineering-split.md`：§ 5bis.2 新增 F-ACCT-6 两行（主页采集 + 内容巡检）+ 前端详情页一行；§ 八 engineering 任务清单新增 4 条；§ 九 跨功能契约新增 3 行（KT2 WP4/5 → F-ACCT-6 / F-COORD channels.py → F-ACCT-6 / MediaCrawler creator → F-ACCT-6）。
- 跨功能影响：
  - F-PROP WP4/WP5 接口要求更新——除原有的 `/propagation/stance/by-account` 端点外，需保证 `harm_assessor.score(text, metadata)` / `stance_detector.detect(text)` 可作为单帖纯函数被 F-ACCT-6 import 调用。
  - F-COORD `channels.py` 需提供 `template_detector.check(post, account_corpus)` 子接口（单账号语料模板抽取，不同于群体协同模式），归入 F-ACCT-6 推进期内的小幅扩展。
- 关联文件：本条目对应 `doc/engineering/F-ACCT-account-profiling.md`、`doc/engineering/research-engineering-split.md`、`doc/engineering/development-roadmap.md`（§ 2.3 已勾选 F-ACCT-6 两个待开发项）、`doc/engineering/product-requirements.md`（§ 主页采集功能描述已存在）同步更新。

---

## 2026-05-20

- 将社交平台采集链路收敛为“直接执行 MediaCrawler -> 读取本次新增 JSONL 行 -> 直接入库”，避免同一天重复任务整份回读最新文件时把前一批关键词结果混入当前任务。
- `new-system/backend/app/core/crawler/social.py`：新增 `MediaCrawlBatch`、按当天输出文件记录偏移量、只读取本次运行新增 JSONL 行并标准化；`search()` 改为复用新的直接批次执行路径。
- `new-system/backend/app/tasks/crawl_tasks.py`：社交平台任务改为直接走 `MediaSocialCrawler.execute_search_batch()` 后入库；`mock/news` 仍保留原有分支。
- `new-system/backend/tests/test_social_crawler_normalization.py`：新增增量 JSONL 读取回归测试，防止再次退回整份最新文件回读。
- `new-system/README.md`、`doc/engineering/environment-setup.md`、`doc/engineering/development-roadmap.md`：同步更新“MediaCrawler 直连执行 + 增量入库”的运行口径。

- 修复 MediaCrawler 抖音登录验证链路，补上“验证码中间页”轮询处理与持久化 session 识别，并完成一次真实抖音搜索抓取验证。
- `MediaCrawler-main/media_platform/douyin/login.py`：新增更稳健的登录态识别逻辑，轮询时如果页面进入“验证码中间页”会继续触发滑块验证；登录成功判定不再只依赖 `HasUserLogin` / `LOGIN_STATUS`，也会识别持久化会话 cookie + token 信号。
- `MediaCrawler-main/media_platform/douyin/client.py`：`pong()` 改为复用新的登录态判定逻辑，使已保存的抖音浏览器会话可直接复用。
- `MediaCrawler-main/tests/test_douyin_login.py`：新增回归测试，覆盖持久化 session 判定、验证码中间页拒绝误判、验证码后重试成功、`DouYinClient.pong()` 复用登录态判定。
- 真实验证：`python main.py --platform dy --lt qrcode --type search --keywords 热点事件 --get_comment yes --get_sub_comment yes --max_comments_count_singlenotes 10 --max_concurrency_num 1 --save_data_option jsonl` 已在本机跑通，输出 `14` 条帖子和 `1934` 条评论到 `MediaCrawler-main/data/douyin/jsonl/`。

- 完成 CogGuard -> MediaCrawler 宿主机运行链路校准，确认 `weibo` / `xhs` / `douyin` 可在 Windows + Docker 混合环境下通过本地 `MediaCrawler-main` 运行；`toutiao` 继续明确走 `news` / NewsCrawler 链路。
- 本机环境落定：
  - `uv 0.11.13`
  - `Python 3.11.15`（`C:/Users/p/AppData/Roaming/uv/python/cpython-3.11-windows-x86_64-none/python.exe`）
  - `Node v24.15.0`（`D:/node/node.exe`）
- `new-system/.env`、`new-system/.env.example`：MediaCrawler 配置切换到 Python 3.11，并补充 `MEDIACRAWLER_UV_CACHE_DIR`。
- `new-system/backend/app/config.py`、`app/core/crawler/mediacrawler_env.py`：新增 `MEDIACRAWLER_UV_CACHE_DIR` 配置；子进程环境自动注入 Node 路径与 uv 缓存目录，并清理父级 `uv` 运行标记。
- `new-system/backend/app/core/crawler/social.py`、`scripts/verify_mediacrawler_env.py`：运行时优先直接使用 `MediaCrawler-main/.venv` 的 Python 启动 `main.py` 和 Playwright，避免后端 `uv run` 再嵌套一层 `uv run` 导致的 Windows 缓存权限问题。
- `new-system/backend/tests/test_mediacrawler_env.py`：补充 `UV_CACHE_DIR`、父级 uv 标记清理、MediaCrawler `.venv` 解释器解析的回归断言。
- 运行验证：
  - `MediaCrawler-main` 下 `uv sync --python <3.11>` 成功
  - `playwright install chromium` 成功
  - `new-system/backend/scripts/verify_mediacrawler_env.py` 返回 PASS，平台摘要为 `weibo: ready` / `xhs: ready` / `douyin: ready`
- 未完成项：
  - `tests/test_mediacrawler_env.py` 未通过 `uv run --with pytest ...` 补跑；当前环境对 PyPI 额外拉取 `pytest` 时触发 `os error 10013` 套接字访问限制，但不影响已完成的 MediaCrawler 宿主机验证。

- 新增 MediaCrawler 话题采集对齐增强：把子评论抓取与单帖评论上限暴露为环境配置，并在标准化层保留帖子 / 评论原始载荷、媒体链接、用户画像与评论父子关系，便于按事件对齐 `weibo / xhs / douyin` 的两层评论树。
- `new-system/backend/app/config.py`：新增 `MEDIACRAWLER_GET_SUB_COMMENTS`、`MEDIACRAWLER_MAX_COMMENTS_PER_POST`。
- `new-system/backend/app/models/post.py`、`app/core/crawler/normalizer.py`：为帖子 / 评论模型补充 `author_profile`、评论 `raw_data`、`media_urls`、`sub_comment_count` 等字段。
- `new-system/backend/app/core/crawler/social.py`：调用 MediaCrawler 时显式传入 `--get_sub_comment` 与 `--max_comments_count_singlenotes`，并增强对 `weibo / xhs / douyin` 的帖子 / 评论多模态、用户字段和评论树父子关系标准化。
- `new-system/backend/tests/test_social_crawler_normalization.py`：新增回归测试，覆盖命令构造、帖子媒体抽取、评论树字段保留与原始载荷保真。
- `new-system/.env`、`new-system/.env.example`、`new-system/README.md`、`doc/engineering/environment-setup.md`：同步补充二级评论开关、评论上限和“当前只支持两层评论树”的说明。
- 继续补充可选采集参数：`recursive_comments`、`enrich_author_profiles`、`comment_sort`。当前 `comment_sort` 已在评论入库前按点赞数或被回复数倒序生效；递归完整评论树和作者主页级画像补全先作为请求元数据接入，并显式记录当前 MediaCrawler 后端的降级边界，后续可在此接口上串接平台特定递归抓取 / creator 模式。

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
