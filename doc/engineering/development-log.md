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

## 2026-08-11

- Case 报告预览补齐语义研判摘要：HTML/PDF fallback 报告现在打印 `Semantic decision support`，包含覆盖率、候选置信状态、平台切片、时间切片和“语义只作分诊提示”的操作边界；本地验收脚本同步检查该区块可见。

- Case Workbench 验收导出补充语义研判摘要：后端 `case_workbench_acceptance.py` 和前端验收 JSON 导出均包含 `semantic_decision_support`，记录覆盖率、候选状态、平台/时间切片和“只作分诊提示”的操作边界，便于演示后复查 NLP 支撑证据。

- 增强 Case Workbench 的语义研判摘要：`semantic_enrichment` 新增 `decision_support`，统一输出覆盖率、候选置信等级、模块可用性、时间切片、平台切片和研判提示；前端“语义辅助”面板新增密集摘要卡片，仍明确语义只作分诊提示，不进入风险分数。
- `system/backend/app/core/analysis/semantic_enrichment.py`、`system/backend/app/services/case_workbench_service.py`、`system/frontend/src/{types/case.ts,views/cases/index.vue}`：补齐 NLP 支撑功能的可见闭环；相关后端 Case/语义回归和前端构建通过。

- 独立注册 Twitter IO benchmark 清单：只保存 31 列字段、39,964 行、60 用户、retweet/reply/quote 统计、25.6 MB 字节数和 SHA-256，不提交 CSV 或 Markdown 转换文本，也不接入中文 Case 验收。
- `system/backend/app/schemas/twitter_benchmark.py`、`system/backend/scripts/verify_twitter_benchmark.py`、`system/backend/fixtures/case_workbench/twitter_io_manifest.json`、`system/backend/tests/test_twitter_benchmark_manifest.py`：新增 digest-only Pydantic 契约、stdlib CSV/hashlib 校验器、fixture manifest 和隔离回归测试。

- 新增 Case Workbench 研究归档契约：结构化搜索记录和 reviewed MarkItDown 归档可校验 SHA-256、NFC 规范化摘录范围、归档路径及可选原始来源字节；第二平台结果只能来自已校验归档或显式 `platform-gap.json`，不伪造 CCTV、新华社或第二平台来源。
- `system/backend/app/{schemas/case_research.py,services/case_research_archive.py}`、`system/backend/tests/test_case_research_archive.py`、`doc/research/case-workbench/README.md`：新增 Pydantic 公共契约、只读归档验证器、回归测试和 append-only 研究协议说明。

- 加固 Case Workbench 原型可信边界：demo 权威主张统一标记为 `candidate_unvalidated`，不再伪造 `source_content_hash`；结案后禁止继续修改，viewer 角色禁止处置/反馈/结案类写操作，报告预览改为通过 Axios 鉴权后打开 Blob URL。
- 新增 `system/backend/scripts/case_workbench_acceptance.py` 本地验收脚本：以 Weibo-only demo fixture 验证平台缺口确认、处置完成、反馈、结案和报告预览闭环；XHS 缺口保留可见，不伪造第二平台证据。
- 新增 Case Workbench 平台缺口确认原型：默认 fallback 仍只含微博证据，但研判员可在页面显式确认 `platform_gap` 后继续处置、反馈和结案；确认记录保存在进程内 demo state，并保留缺失平台，不伪造 XHS/抖音证据。
- `system/backend/app/{schemas/cases.py,api/v2/cases.py,services/case_workbench_service.py}` 与 `system/frontend/src/{api/cases.ts,types/case.ts,views/cases/index.vue}`：新增 blocker acknowledgement API、前端“确认平台缺口继续”按钮、确认记录展示和报告预览中的 Policy acknowledgements 区块。

- 同步 Case Workbench 快速原型状态：工作台展示 `事件 -> 证据 -> Coordination -> Propagation -> Review -> 处置 -> 反馈`；`semantic_enrichment` 保持 opt-in，默认四阶段 Analysis Run 不变，并记录情感、关键词、主题、实体、有 Primary Claim 时的立场、近重复与平台/社区对比。
- `doc/engineering/{development-log.md,development-roadmap.md}`、`system/README.md`、`README.md`：明确处置/反馈/结案变更只保存于进程内 demo state，默认 fallback 证据仅为微博且不伪造 XHS/抖音证据，报告预览/PDF 在持久 HTML/PDF 渲染落地前可使用原型 fallback。

- 继续推进 Case Workbench 原型闭环从“展示态”到“可操作态”：处置项可在页面标记完成/豁免，反馈和结案复核说明可通过 `/api/v2/cases` demo mutation API 写入并刷新页面；当前状态为进程内 demo 记录，服务重启后不保留，正式持久化仍待后续 Case 模型与迁移。
- `system/backend/app/schemas/cases.py`、`system/backend/app/api/v2/cases.py`、`system/backend/app/services/case_workbench_service.py`：新增 `complete/waive action`、`feedback`、`closeout` API 和 append-only demo audit events；完整第二平台证据存在时可从 `actioning -> ready_to_close -> closed`，默认 fixture 继续因 XHS platform gap 停留在 `evidence_ready`。
- `system/frontend/src/api/cases.ts`、`system/frontend/src/types/case.ts`、`system/frontend/src/views/cases/index.vue`：新增 Case 操作客户端、处置按钮、反馈列表、结案复核提交控件和状态刷新。
- 验证：后端选择集 `40 passed`；前端 `npm.cmd run build` 通过（仅 Vite 大 chunk warning）。

- 新增 Case Workbench 快速原型闭环：以已归档特朗普访华事件为演示对象，将事件证据、权威主张、显式语义辅助、分析运行、处置项、反馈入口和冻结报告占位聚合到一个案例视图；当前为读模型 MVP，不声称已完成完整 SQL 持久化、迁移或真实 PDF 渲染。
- `system/backend/app/core/analysis/{contracts.py,executor.py,semantic_enrichment.py}`：新增显式 `semantic_enrichment` Analysis Stage，默认四阶段仍保持 `coordination_discover / propagation_analysis / student / teacher`；语义辅助输出情感、关键词、主题、实体、近重复、社区差异和立场，模型状态统一为 `candidate_unvalidated`，缺少主主张时立场返回 `blocked_missing_primary_claim`。
- `system/backend/app/services/case_workbench_service.py`、`system/backend/app/api/v2/cases.py`、`system/backend/app/api/v2/router.py`：新增 `/api/v2/cases` 读接口，内置 CCTV 主主张、新华社辅助主张、平台缺口 blocker、Case 生命周期和报告版本占位；Mongo 不可用时显式返回 `demo_fixture` 来源并保留 XHS 平台缺口，不伪造第二平台证据。
- `system/frontend/src/{api/cases.ts,types/case.ts,views/cases/index.vue,router/index.ts,components/layout/BasicLayout.vue}`：新增“案例闭环”侧边栏入口和五标签工作台（概览 / 证据矩阵 / 图谱 / 处置 / 报告），跨标签常驻生命周期、主核心主张和阻塞项。
- `system/backend/tests/{test_semantic_enrichment.py,test_case_workbench_mvp.py,test_case_frontend_mvp_contract.py}`：新增 MVP 契约测试，覆盖默认四阶段兼容、显式语义阶段、缺主张降级、Case API 闭环投影和前端路由/标签契约。
- 验证：后端选择集 `37 passed`；前端 `npm.cmd run build` 通过（仅 Vite 大 chunk warning）；Terra 只读复审确认 4 个原型阻塞项均已修复。

## 2026-08-05

- 将传播能力拆分为观测传播分析与传播预测两个独立运行边界：观测接口不调用预测代码，预测接口只消费截止时间前的事件快照。
- `system/backend/app/core/propagation_legacy.py`：新增用户、帖子、评论、共享对象和事件 provenance 图；传播边区分 `explicit`、`reconstructed`、`inferred`，布局关系不再混入事实边；补源头、路径、角色及时间前缀稳定性，并移除 `user_quality` 返回。
- `system/research/propagation_analysis/benchmark/adapters/event_adapter.py`：系统内化 `PropagationSequenceJointModel`，真实加载 Twitter checkpoint，输出单调趋势和实名下一跳再激活排序；匿名 bucket 仅进入覆盖审计。
- `system/backend/app/services/propagation_model_service.py`、`app/api/v1/propagation.py`、`app/schemas/propagation.py`：严格校验带时区的 `observed_until`，统一成功/abstain 响应，删除公开事件预测路径中的速度、加速度和活动度替代预测。
- `system/frontend/src/views/propagation/index.vue`：消费真实趋势时间点、预测范围、证据类型和实名下一跳结果；本地时间转 UTC 后提交，不可用时保持预测区为空。
- 验证：后端全量 `458 passed, 18 skipped`；前端 `vue-tsc` 与生产构建通过；Twitter checkpoint CPU smoke 输出四个趋势点和实名 Top-K。当前样本实验仍为 `full_validation_passed=false`，不构成模型优越性结论。

---

## 2026-08-01

- 完成本轮三项关键能力的原型交付收口：新增 `system/backend/scripts/prototype_acceptance.py`，用隔离 EventSnapshot 验证 Coordination Discover 严格 Leiden artifact、Propagation Analysis fallback/abstain、Student shadow 和 Teacher advisory 运行边界；不写数据库、不生成标签、不修改前端。
- `system/backend/app/core/analysis/contracts.py`：默认 Analysis Run 现在执行完整的 Coordination Discover、Propagation Analysis、Student Review、Teacher Review 链路；窄阶段运行仍可显式指定。
- `system/backend/app/core/analysis/executor.py`：artifact manifest 增加 `run_id`、prototype 标记、`execution_mode`、`prototype_status` 和 `research_claim`，防止 fallback/live runtime/shadow/advisory 输出被误认为研究结果。
- `system/research/coordination_discover/{artifacts.py,contracts.py}`：研究 artifact 对已写入结果文件记录 SHA-256，加载时校验完整性；manifest 默认 non-claimable。
- `system/backend/scripts/smoke_crawl_backend_api.py`：移除硬编码管理员密码，smoke 登录改由 `COGGUARD_SMOKE_USERNAME` / `COGGUARD_SMOKE_PASSWORD` 显式提供。
- Re-search 预检 `research-wiki/preflight_runs/20260731T190240Z-evaluate-and-optimize-cogguard-s-three-core-capa/` 已完成 v2 校验，覆盖 MAGNN、Coordination Network Toolkit、TGN、TGB、CQR、DEFAME、ReConcile、MAGDi，并记录迁移边界和 omission handling。
- 验证：targeted `22 passed`；后端全量 `441 passed, 18 skipped`；治理 targeted `28 passed, 2 warnings`；严格 Leiden import `igraph 0.11.9`；无产品后端外部 runtime 引用；Compose 在显式测试凭据下解析通过；前端 `npm run build`（包含 `vue-tsc -b`）通过。Docker 服务、GPU 长实验和真实 checkpoint 尚未验证。

- 完成安全与治理链路的实际验证收口：后端编译、全量测试、Alembic 单一 head 和 Compose 必填凭据检查均通过；新增治理边界回归测试。
- `system/backend/app/services/analysis_governance_service.py`：模型激活前严格校验本地 artifact 的 SHA-256；远程 URI 在接入可审计 resolver 前不视为已验证；反馈 verdict 必须属于同一 Analysis Run；禁止重复激活当前模型。
- `system/backend/tests/test_analysis_governance.py`：覆盖本地制品哈希、不可信远程 URI、Canonical Verdict 审批和双人模型激活门禁。
- 验证：后端全量 `424 passed, 18 skipped`；治理 targeted `5 passed`；`compileall` 通过；Alembic head 为 `d2f7a8b9c0e1`。
- 完成最终系统收口的安全与部署阻塞修复：清除未完成合并冲突，统一 dashboard 与核心认证边界，取消公开 JWT、管理员和基础设施默认凭据，preview 旁路默认关闭。
- `system/backend/app/config.py`、`system/backend/app/core/security.py`、`system/backend/app/services/auth_service.py`：生产环境强制显式秘密；本地未配置 JWT 时使用临时进程密钥；未配置管理员种子口令时不自动创建 `admin`。
- `system/backend/app/core/analysis/executor.py`、`system/backend/app/core/analysis/registry.py`：将每个分析阶段的模型/制品、fallback、checkpoint 和 claimability 写入 `artifact_manifest` 并持久化；未绑定真实制品的结果默认不可作为研究主张。
- `system/.env.example`、`system/docker-compose.yml`、`system/README.md`、`doc/engineering/system-governance.md`：同步部署前置、制品追溯和文档治理规则。
- 验证：安全、Analysis Run、SSE、Coordination Discover runtime 与治理 targeted pytest 共 `28 passed`；完整后端测试和真实数据库/队列部署 smoke 待继续执行。

---

## 2026-07-21

- 收口仓库入口与 Risk Review 上下文命名：`README.md`、`system/README.md`、`AGENTS.md`、`CLAUDE.md`、`CONTEXT.md` 与 `plan/progress.md` 的当前-facing 术语统一为正式方法名与工作流表述。
- 收口全局系统治理：新增统一术语表、系统治理文档和 ADR，要求后续代码变更同步文档、术语和架构决策。
- `UBIQUITOUS_LANGUAGE.md`：新增跨系统术语、别名禁用、run/job/task、artifact/checkpoint/model version、Teacher Silver 与 Selective Student 定义。
- `doc/engineering/system-governance.md`、`docs/adr/0002-system-governance-and-documentation-sync.md`：新增代码结构、公共边界、文档同步与长期迭代规则。
- `AGENTS.md`、`CLAUDE.md`、`README.md`、`system/README.md`、`doc/engineering/project-map.md`：同步 Codex/Claude 读取顺序、文档更新要求和当前产品根 `system/`。
- `system/backend/app/core/review/teacher_silver.py`、`system/backend/app/core/review/selective_student.py`：从 `trainable_post.py` 拆出 Teacher Silver 和 2+1 Selective Student 职责，原文件保留懒加载兼容导出。
- 追加收口 Coordination Discover / Detect 正式方法名：`Coordination Discover` / `Coordination Detect`，同步 `UBIQUITOUS_LANGUAGE.md`、`doc/engineering/system-governance.md`、`README.md`、`system/README.md` 和研究总览。
- `doc/engineering/environment-setup.md`、`doc/engineering/data-contract-mediacrawler.md`、`doc/research/key-technology-background/*.md`：把当前-facing 路径从历史产品根别名同步到 `system/`。
- `system/backend/app/api/v1/propagation.py`、`system/backend/app/services/propagation_service.py`：补传播分析 `node_limit` / `diffusion_node_limit` 的旧调用面兼容，避免新增参数打断旧替身和旧集成测试。
- 验证：`python -m pytest system/backend/tests/test_trainable_post.py system/backend/tests/test_governance_docs.py -q`；`python -m pytest system/backend/tests -q`（319 passed, 27 skipped）。
- 收口 Risk Review PropagationTreeAgent 证据边界：新增 Thread Context / Propagation Context 术语、ADR 与工程说明，PHEME 转换保留 node-edge reply tree，离线 Agent runner 只在真实传播树上下文存在时插入 `PropagationTreeAgent`。
- `system/backend/app/core/review/propagation_agent.py`、`system/backend/app/core/review/propagation_context.py`、`system/backend/app/core/review/graph_exporter.py`：新增字段约束型 Agent 契约、传播线程压缩上下文与 post-post `replies_to` / `reposts` / `quotes` 边导出，避免 claim-only 或 reaction-count-only 样本被伪装成传播树证据。
- `system/backend/tests/test_review_propagation_context.py`、`system/backend/tests/test_review_graph_exporter.py`、`system/backend/tests/test_governance_docs.py`：补 propagation context、图导出和 ADR 编号 / `__all__` 治理回归测试。
- `system/backend/app/core/review/agent_provider.py`：从 `agent_review.py` 拆出 OpenAI-compatible provider、wire API payload、retry 与 settings factory；产品服务、Celery task 和离线实验脚本改用新 provider 边界，旧路径保留兼容导出。
- `system/backend/app/core/review/agent_contracts.py`：从 `agent_review.py` 拆出 Agent report sections、prompt builders、output contract、report role 与 safety flag，`agent_review.py` 保留薄包装兼容旧私有测试面。
- `system/backend/app/core/review/agent_runtime.py`：从 `agent_review.py` 拆出 Agent 顺序、别名归一化、simple/complex runtime 选择、execution plan、反制延后、candidate rule hints 与 failure tags。
- `system/backend/app/core/review/agent_media.py`：从 `agent_review.py` 拆出媒体输入抽取、vision gating、data URL 转换与 provider payload trimming，`agent_review.py` 仅保留旧私有 helper 兼容包装。
- `system/backend/app/core/{__init__.py,crawler/__init__.py,coordination/__init__.py,propagation/__init__.py}`：公共包入口统一改为英文 canonical boundary docstring，规避 Windows 控制台和 agent 工具中的 mojibake，并用治理测试防止回归。
- `system/backend/app/core/review/__init__.py`：新增 Risk Review Risk Review canonical facade，懒加载转发到现有 `app.core.risk` 实现包；`risk` 保留为一个版本窗口的兼容层，新代码命名优先使用 `review`。
- `system/backend/app/core/coordination_discover/__init__.py`、`system/backend/app/core/coordination_detect/__init__.py`：新增 Coordination Discover / Detect Coordination Discover / Detect canonical facade，分别转发现有 `app.core.coordination` 的发现入口与检测/统计入口；`coordination` 保留为 CooRTweet-style baseline 兼容层。
- `system/backend/app/core/propagation_analysis/__init__.py`：新增 Propagation Analysis Propagation Analysis canonical facade，转发现有 `app.core.propagation` 与 `propagation_legacy.py` 的传播图、趋势预测、时序特征、事件提取和体制模型入口；旧路径保留为兼容层。
- `system/backend/app/services/propagation_service.py`、`system/backend/app/core/coordination/characterization.py`：把当前传播图和趋势预测调用点切到 `app.core.propagation_analysis`，治理测试禁止这些调用点回退到旧实现包直连。
- `system/backend/app/services/coordination_service.py`：把当前协同检测产品服务切到 `coordination_detect` / `coordination_discover` facade；`coordination_discover` 同步公开 `graph_to_dict` 以承载网络结果序列化入口。
- `system/backend/app/services/coordination_model_service.py`：把 Coordination 数据集 registry、MAGNN+Leiden rerun 与 pretrained detect 调用切到 `coordination_discover` / `coordination_detect` facade，并扩展 facade `__all__` 作为模型服务公共入口。
- `system/backend/app/api/v1/risk.py`、`system/backend/app/services/{risk_service.py,review_system_service.py}`、`system/backend/app/tasks/review_tasks.py`：把当前 Risk Review Risk Review 产品调用面切到 `app.core.review` facade，并用治理测试禁止这些入口重新直连旧 `app.core.risk` 实现包。
- `system/backend/app/services/propagation_prediction_service.py`、`system/backend/app/api/v1/propagation.py`：把传播预测桥接服务从编号缩写文件名迁到正式 Propagation Prediction 命名，移除旧编号路由，前端仍使用 `/propagation/model-predict`。
- `system/backend/app/services/risk_review_system_service.py`、`system/backend/app/tasks/risk_review_tasks.py`：把 Risk Review 产品层服务与 Celery task 迁到正式方法命名，旧编号缩写文件名不再作为运行入口。

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

- 总指挥触发项目实施情况盘点（3 个 Explore 子代理并行调查代码 / 文档 / ARIS 工作空间），交叉核对后发现**代码进度大幅领先文档**，特别是 Risk Review 报告研判已默默实现而 README/roadmap 仍标"待开发"。本条目记录本次审计与首轮文档对齐动作。
- 代码盘点（实际验证）：
  - 后端约 5,664 行 Python，前端约 1,710 行 Vue/TS。
  - Coordination Discover / Detect 协同检测（旧方向 CooRTweet）：`core/coordination/` 452 行 MVP；Coordination Discover / Detect 新方向 PSL 设计已在 `aris/tech-01-coordination/systemDesign.md` 落盘，但 `new-system/` 尚无对应实现。
  - Propagation Analysis 传播监控（Hybrid TS+LLM）：`core/propagation/` 含 4 个文件 ~673 行 → **WP1-3 完整完成**（`ts_features.py` 107 / `llm_context.py` 162 / `trend_predictor.py` 180 / `regime_model.py` 224）；**WP4 `stance_detector.py` 与 WP5 `harm_assessor.py` 完全未启动**；WP6-7 服务层与测试已存在但极薄。旧方向 `core/propagation_legacy.py` 仍在 import 路径并存。
  - Risk Review 报告研判：`core/risk/` 6 模块 1,340 行 + `services/risk_service.py` 153 行 + `api/v1/risk.py` 68 行 + `frontend/src/views/risk/index.vue` + `tests/test_risk.py` 348 行 — **MVP 已完成，端到端串通**，但 README/roadmap 此前仍标"待开发"。
- 文档对齐：
  - `README.md` 模块状态表：风险研判 `待开发 → MVP 已完成`；协同检测拆分新旧方向；传播监控按 WP1-3/WP4-5 分粒度；看板继续保留"待开发"（`dashboard/index.vue` 仍是占位）。
  - `doc/engineering/development-roadmap.md`：头注释日期 `2026-04-08 → 2026-05-17`；总览模块表细化到 WP 粒度；第 3.1 节风险研判模块由"🔲"翻面为"✅ MVP 已完成"，并把 8 个已完成子项打勾；保留 2 个未完成子项（alembic 迁移、LLM 桥接）。
  - ARIS 治理段：tech-03 落地条目勾选；tech-02 标 `[~]` 表示 WP1-3 已完、WP4-5 未启动。
- 仓库治理风险（本次未处理，需后续单独提交）：
  - `aris/`、`doc/engineering/`、`doc/research/`、`AGENTS.md`、`CLAUDE.md` 整体仍为 untracked，是项目最大单点风险。
  - `cogguard_system/memory/` 目录此前不存在但 `CLAUDE.md` 启动顺序引用之，本次同步新增 `memory/PLAYBOOK.md` 与各关键技术线状态记录 修补死链。
- 关联文件：本条目对应 `README.md`、`doc/engineering/development-roadmap.md`、`memory/PLAYBOOK.md`、各关键技术线状态记录、`aris/tech-02-propagation/TASK_TRACKER.md` 同步更新。

---

## 2026-05-23

- 完成 F-ACCT（深度账号画像）的功能细化：从 5 个子功能扩展为 6 个，新增 **F-ACCT-6 单用户主页采集与内容巡检**。该子功能定位为"按主页链接/用户 ID 抓取主页元数据 + 全部发文 + 对全部内容做风险/立场/模板化检测"，不引入新算法，全部复用上游能力（Propagation Analysis WP4 立场 / Propagation Analysis WP5 危害 / F-COORD 通道模板）。
- 关键设计决策：
  - **复用 MediaCrawler creator 模式**，不新增爬虫。在 `core/crawler/social.py` 扩展 `mode=creator` 参数，`homepage_collector.py` 通过该入口调用。weibo / douyin / xhs 已支持。
  - **三段流水线**：homepage_collector（主页采集）→ content_checker（按帖批处理调用上游）→ account_service（详情页响应组装）。
  - **mock fallback 策略**：上游算法（Propagation Analysis WP4/5、F-COORD 通道）未完成时，content_checker 仅给规则化结果并标 `data_completeness="partial"`，前端用占位符渲染，确保 F-ACCT-6 可独立先行。
- 文档同步：
  - `doc/engineering/F-ACCT-account-profiling.md`：§ 3.5 新增 F-ACCT-6 完整技术方案（架构 + schema + 降级 + research/engineering 拆分）；§ 4.3 新增 `account_homepage` 表 SQL；§ 5.2 新增 `homepage_collector.py` / `content_checker.py` / `social.py mode=creator` 扩展 / `models/account_homepage.py` / 账户详情页等 7 项待新增；§ 6.2 新增 E11-E15 五项 P1 任务；§ 7.1 新增 2 条关键决策（决策 6 复用 MediaCrawler、决策 7 全部复用上游）；§ 8.5 新增 F-ACCT-6 → 上游算法的契约说明；§ 10 三周计划全部纳入 F-ACCT-6 工作量。
  - `doc/engineering/research-engineering-split.md`：§ 5bis.2 新增 F-ACCT-6 两行（主页采集 + 内容巡检）+ 前端详情页一行；§ 八 engineering 任务清单新增 4 条；§ 九 跨功能契约新增 3 行（Propagation Analysis WP4/5 → F-ACCT-6 / F-COORD channels.py → F-ACCT-6 / MediaCrawler creator → F-ACCT-6）。
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

- Coordination Discover / Detect 系统设计与 CCF-B+ 多模态检测文献综述一体化落盘（deep-interview 合并草案 v0.1）。
- `aris/tech-01-coordination/systemDesign.md`（新增）：单文件 12 节交付 —— 概述、问题陈述、系统功能 ↔ 关键技术错位矩阵（M1–M5）、系统架构、C2 搜索子系统（多模态展示承载）、C3 检测 MVP（PSL primary + ADR-001 fallback 文字契约）、跨关键技术输出契约、CCF-B+ 文献综述（24 条有效条目、9 字段强制）、工程时序原则 T1–T6、M0–M6 里程碑、验收对齐 ACCEPTANCE.md。
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
## 2026-08-01

- Completed independent internal BotRHG transfer runs on the official local Cresci-2015, Cresci-2017, and Midterm-2018 Twitter corpora using the repository-local `FacebookAI/xlm-roberta-base` snapshot (`e73636d4f797dec63c3081bb6ed5c7b0bb3f2089`). Added `system/research/social_bot_detection/datasets.py` with streaming nested-archive adapters, official label provenance, source-subclass preservation, bounded account-text sampling, and archive fingerprints.
- Added the generic `cogguard.botrhg.account.v2` checkpoint schema while retaining the Weibo schema loader for compatibility. Replaced the full NxN KNN allocation with chunked exact top-K retrieval so Midterm-2018 runs within an 8 GB GPU. Research package tests: `13 passed`.
- Public training artifacts are under `system/output/botrhg_public/`: Cresci-2015 usable accounts `5,175`, corrected test macro-F1 `0.9360`; Cresci-2017 `13,949`, `0.6376`; Midterm-2018 `50,538`, `0.7042`. Same-split character TF-IDF remains stronger on all three datasets (`0.9804`, `0.9304`, `0.7852`), so the real training milestone is complete but method-superiority and publication claims remain blocked.
- The Midterm-2018 archive contains account descriptions rather than a tweet corpus; this limitation is recorded in each manifest and the cross-dataset report. No external NLPCC directory is imported or executed.

- 完成内部 BotRHG Weibo transfer 训练与系统接入，不再把外部 NLPCC 研究目录作为运行时来源。
- 新增 `system/research/social_bot_detection/`：Botection 标签/文本加载、稳定 data fingerprint、中文 Transformer 的均匀多块账号表示、低阶分类器、target-centered KNN support hyperedge、相似度加权 reliability route、selective residual correction、checkpoint inference、评估和 artifact export。
- 训练制品写入 `system/output/botrhg_weibo/`：`checkpoint.pt`（另有 `checkpoint.sha256`）、`config.json`、`data_manifest.json`、`metrics.json`、`predictions.jsonl`、`training_history.json`、`model_card.md`。数据为 979 个可用账号，636/146/197 split，fingerprint 为 `50327a90e7b9fa6cb65140af3e1573d139925033b184af2ed43aa938ab42c0ae`。
- 同切分结果：BotRHG corrected test ROC-AUC `0.6473`、macro-F1 `0.4312`；字符 TF-IDF 参考 ROC-AUC `0.7843`、macro-F1 `0.7028`。因此真实训练链路和部署推理已验证，但研究有效性和论文主张仍 blocked。
- backend 只在 checkpoint 存在且 fingerprint 门禁通过时使用 `trained_checkpoint`，否则返回明确 `proxy` fallback；本轮不修改前端展示页面。
- 验证：研究包 `8 passed`，相关 backend tests `8 passed`，backend 全量 `443 passed, 18 skipped`。

---

## 2026-08-12

- Case Workbench 报告页新增可复制/下载的 Semantic Support Pack JSON；导出仅复用当前语义 artifact 和既有人工修正，包含情感、关键词、主题、实体、立场、近重复、社区对比、决策支持、provenance 与原型限制，保持 `evidence_overlay_only`、`candidate_unvalidated`、微博单平台/XHS 缺口和 excerpt-only 边界，不改变 Coordination/Propagation/Review 分数。
- `system/frontend/src/views/cases/index.vue`、`system/backend/tests/test_case_frontend_mvp_contract.py`：新增前端计算 payload、复用剪贴板/下载辅助流程以及静态契约测试；下载文件名包含 `semantic-support-pack`。

- Case Workbench 报告增加紧凑语义证据附录，直接复用现有 `semantic_artifacts[0].summary`，展示情感、关键词、主题、实体、立场、近重复和社区对比，保持 `candidate_unvalidated` / `evidence_overlay_only` 边界。
- 缺少 Primary Claim 时报告继续可渲染，明确显示 `blocked_missing_primary_claim`，同时保留非立场语义辅助，不伪造来源、归档或哈希。
- 验收脚本输出 `semantic_evidence_appendix_visible` 与附录类别统计；演示数据仍为微博单平台并记录 XHS 缺口。
- Case Workbench 前端与报告补齐语义复核链路：展示 review hints、module coverage、Semantic examples 和 action evidence refs，验收输出新增 traceability 包，仍不影响风险分、处置状态或结案门槛。
- Case Workbench 新增 `prototype_constraints` 原型限制契约，在后端 payload、报告、前端报告页和验收导出中显式记录：微博单平台 + XHS 缺口、语义样例仅为 excerpt、语义产物不改 Coordination/Propagation/Review 风险分、模型 `candidate_unvalidated`、PDF 为 HTML fallback。
- Case Workbench 增加 `SemanticCorrection` 原型闭环：分析员可对语义辅助结果追加人工修正，后端 API、报告、前端语义区与验收导出均可见，并通过审计事件 `record_semantic_correction` 记录；修正保持 `advisory_overlay`，不改变 Case 状态、处置、结案门槛或平台证据。
