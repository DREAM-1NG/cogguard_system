# 开发变更日志

## 2026-08-08: TwiBot-20 Research Deployment And Dataset Identity

- Added an internal `TwiBot20ResearchRuntime` and CLI. It verifies a compact,
  hash-managed bundle containing the NLPCC checkpoint, fixed node mapping,
  predictions, source manifest, and selection metrics before serving a lookup.
- Selected seed 3 according to the source experiment's validation-accuracy
  rule (`0.908828` validation accuracy, `0.904926` validation macro-F1). The
  five-seed test comparison remains non-significant and is not a superiority
  claim.
- Built and smoke-tested `system/artifacts/social_bot_detection/nlpcc_twibot20_seed3`.
  The bundle has 11,826 fixed nodes and is explicitly forbidden from the
  Chinese `cogguard.botrhg.account.v3` Active Pointer.
- Corrected approved-corpus identity and provenance: exported IDs are
  platform-scoped, raw IDs are retained as `source_account_id`, timestamps
  require explicit timezone information, and community fields are copied only
  from persisted payload values.
- Strict approved-corpus loading now recomputes JSONL fingerprint, record
  count, and class counts and rejects a mismatching manifest. Frozen-holdout
  inference and audits use the same platform-scoped identity.
- Verification: TwiBot-20 runtime `4 passed`; social-bot research suite
  `74 passed`; frozen-holdout evaluation suite `20 passed`; real MySQL export
  identity/metadata tests `2 passed`. Frontend was not changed.
- `luna max` was attempted three times for Task 2 and the local provider
  returned HTTP 503 each time; Task 2 was completed on the main execution
  path and independently verified.

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

## 2026-08-07 Account Detection Module Review And Deployment Closure

- `system/backend/app/services/account_service.py`: account detail now rejects
  an omitted platform when the same account id exists on multiple platforms;
  detector cache fingerprints now include the complete Mongo post projection,
  including nested profile, interaction, relation, and order inputs used by
  strict BotRHG inference.
- `system/backend/tests/test_botrhg_bot_detection.py`: added regression tests
  for cross-platform detail ambiguity and model-input-sensitive cache keys.
- `system/backend/alembic/versions/a4d8c2b1f305_add_risk_assessments_table.py`
  and `a1e9c7d4b605_make_account_evaluation_run_ids_global.py`: preserved
  online data checks while making offline SQL generation deterministic; the
  risk-table migration now rejects incompatible same-name indexes.
- Verification: focused account regression `20 passed`; account governance
  and runtime regression `82 passed`; social-bot research package `66 passed`;
  Alembic offline upgrade SQL generates successfully through
  `e5c1b7d9a204`.
- Deployment status remains bounded: no verified Chinese detector bundle is
  active, and the Docker CLI did not return from `docker info`; live database
  migration round-trip and real bundle activation remain unverified.

---

## 2026-08-07 Review Stream Recovery Completion

- `system/frontend/src/utils/request.ts` centralizes expired-session cleanup so
  Axios requests and the review event stream use the same login recovery path.
- `system/frontend/src/api/reviewCases.ts` reports typed stream failures and
  routes an HTTP 401 through that shared session handler.
- `system/frontend/src/views/risk/index.vue` stops its activity recovery timer
  after the typed unauthorized stream failure, preventing repeated requests
  from an expired tab without changing the review presentation.
- `system/frontend/tests/review-case-flow.spec.mjs` adds the regression
  contract. It was observed failing before the implementation and passes after
  the change. Full verification completed with backend `898 passed`, frontend
  `27 passed`, and the optimized production build.
- A real browser session against the static Docker delivery verified one 401,
  login redirection, and no repeat stream request after another polling
  interval. `performance-operations.md` records the redacted runtime results.

---

## 2026-08-07 Performance Projection Follow-up

- system/backend/app/services/dashboard_service.py caches the immutable
  event-scoped Mongo dashboard projection by ingestion fingerprint while
  retaining the MySQL risk-report count and response timestamp as live values.
- system/ops/mongo/apply_performance_indexes.js adds
  event_id, crawl_job_id, _id indexes for posts and comments so fingerprint
  lookups use covered event-scoped scans.
- system/start-system.ps1 binds the host backend on 0.0.0.0 and discovers
  wildcard listeners, allowing the static frontend container to proxy to the
  default backend origin instead of returning a gateway error.
- system/backend/tests/test_dashboard.py,
  system/backend/tests/test_mongo_performance_indexes.py, and
  system/backend/tests/test_trained_bot_detection.py add regression coverage
  for dashboard cache invalidation, operational index definitions, and
  disabled legacy model bootstrap.
- Real 2026-08-07 measurements against the Trump-event corpus: dashboard
  1.04 s cold / 30 ms warm; propagation 488 ms warm; review evidence
  20 ms warm. The operational procedure and cold-path limitation are
  documented in performance-operations.md.

---

## 2026-08-06 Versioned Analysis Result Projections

- Added `system/backend/app/core/analysis/query_result_cache.py`, a process-local
  LRU plus optional Redis cache with single-flight construction and versioned
  keys; it never stores credentials or tokens.
- `propagation_observation_service.py` now keys observed graph results by event
  ingestion generation; `coordination_model_service.py` keys result, graph, and
  community projections by completed run/archive version; `review_case_service.py`
  keys evidence by immutable snapshot revision and annotation version.
- `event_data.py` adds a cheap Mongo ingestion-generation fingerprint. If a
  collection cannot provide a trustworthy marker, the service bypasses the
  cache and preserves the original behavior.
- Added cache and fingerprint regression tests. The first demo warmup still
  performs the real computation; repeated warmups can reuse the projection.
- `system/start-system.ps1` now enables warmup automatically when local demo
  credentials are configured, with `-SkipDemoWarmup` as the explicit bypass;
  no credential is written to the timing report.
- Added ADR 0013 and synchronized `system/README.md` and
  `performance-operations.md` with the new result lifecycle.

## 2026-08-06 Warmup Cache Completion And Startup Repair

- `system/backend/app/services/account_service.py`: moved account detector
  conclusions from a process-only LRU into the versioned query projection
  cache. The identity combines the normalized post corpus and active model
  version/hash/pointer revision, so a data or model change creates a new entry.
- `system/start-system.ps1`: fixed warmup child-script invocation by using
  named-parameter hash splatting, and limited stale training-worker cleanup to
  the exact backend virtualenv Celery process instead of broad command-line
  text matching.
- `system/frontend/tests/delivery-startup.spec.mjs` and
  `system/backend/tests/test_botrhg_bot_detection.py`: added regression
  coverage for named warmup dispatch, safe worker identity matching, and
  one-build account detector reuse.
- Real default startup was verified through an independent PowerShell process:
  all 14 authenticated warmup requests completed with zero failures in 7.89 s
  after Redis reuse. The report is
  `system/output/demo-warmup/demo-warmup-20260806-184057.json`; it contains
  timings and statuses only.

---

## 2026-08-05 MARO-Aligned Review Experiment Protocol

- Added a deterministic, gold-free experiment protocol builder for three
  disjoint populations: `500` paired test cases, `1,000` train-only Teacher
  Silver candidates, and `1,000` validation tasks split equally by the two
  semantic risk axes.
- Added explicit population roles to the offline MultiAgent runner and
  train/test leakage guards to the Student runner.
- Added confidence-derived Teacher soft targets with configurable
  `distillation_alpha`; the current local regime remains frozen-XLM-R feature
  extraction plus multi-task head training, not end-to-end SFT.
- Materialized the protocol at
  `G:\CISCN\.tmp\review_maro_protocol_20260805`. The existing no-teacher
  Student baseline on its `500` balanced test cases reached Macro-F1 `0.522933`,
  PR-AUC `0.631870`, ECE `0.124526`, and escalation rate `0.84`; current-footer
  MultiAgent predictions are still required for a paired result.
- Revised protocol artifacts with `protocol_split` at
  `G:\CISCN\.tmp\review_maro_protocol_v2_20260805`: test `500`, train-only
  Teacher Silver candidates `1,000`, validation rule tasks `1,000`, zero
  pairwise overlap.
- Real `LabDaily` API test smoke completed `5/5` Judges across all five
  datasets at `G:\CISCN\.tmp\review_maro_agent_smoke_v2_20260805`; 33 Agent
  reports completed, 6 failed, and Judge completion was `1.0`. The run was
  gold-free after the subsequent export fix and is a runtime smoke, not a
  classification benchmark.
- Real train-only Teacher smoke completed `5/5` at
  `G:\CISCN\.tmp\review_maro_teacher_train_smoke_20260805`; `4/5` rows passed
  `distillation_eligible` and one MultiOFF row was correctly blocked for an
  invalid Judge stance footer. Student KD plumbing then completed `500` test
  predictions at `G:\CISCN\.tmp\review_student_teacher_kd_smoke_20260805`,
  with `distillation_alpha=0.75` and four datasets receiving Teacher
  supervision in this five-case smoke.

## 2026-08-04

- Made the optimized delivery path the default without changing product
  analysis or presentation behavior.
- `system/frontend/package.json`, `vite.config.ts`,
  `scripts/generate-delivery-preload.mjs`, and `scripts/verify-build.mjs`:
  `npm run build` now emits the Vite manifest, generates a content-addressed
  route preload plan, injects its delivery module into the built HTML, and
  verifies that Three.js/graph chunks are absent from idle preload.
- `system/start-system.ps1`: the default startup sequence is now infrastructure
  readiness, idempotent MongoDB indexes, migrations, a non-reload backend
  health check, and the static `production-ui` frontend. `-DevelopmentFrontend`
  is the explicit Vite exception for source editing.
- `system/ops/Apply-MongoPerformanceIndexes.ps1`: accepts the resolved Docker
  executable from the startup helper so the same Docker lookup path works for
  both operations.
- `system/frontend/tests/delivery-preload.spec.mjs` and
  `system/frontend/tests/delivery-startup.spec.mjs`: add regression coverage
  for preload policy and static-first startup behavior.
- `system/README.md`, `doc/engineering/environment-setup.md`,
  `doc/engineering/performance-operations.md`, and
  `doc/engineering/development-roadmap.md`: document the default command,
  preload boundary, operational sequence, and development fallback.

---

## 2026-08-04

- Added non-business performance delivery and query-operation support without
  modifying `system/frontend/src/` or `system/backend/app/`.
- `system/deploy/frontend.Dockerfile` and
  `system/deploy/nginx/default.conf.template`: add the opt-in
  `production-ui` Compose profile, gzip static payloads, cache only
  content-addressed frontend assets, preserve uncached HTML/API responses, and
  disable proxy buffering for the Event Review Case stream.
- `system/ops/mongo/apply_performance_indexes.js` and
  `system/ops/Apply-MongoPerformanceIndexes.ps1`: add an explicit,
  idempotent MongoDB index operation for current event/platform/time and
  crawl-job access patterns. It creates missing named indexes, retains matching
  indexes, and fails rather than replacing a conflicting same-name index.
- `system/.dockerignore`, `system/docker-compose.yml`, and
  `system/.env.example`: add the static build context, opt-in frontend service,
  mounted maintenance script, and delivery configuration variables.
- `doc/engineering/performance-operations.md`, `system/README.md`,
  `doc/engineering/environment-setup.md`, `doc/engineering/project-map.md`,
  `doc/engineering/system-governance.md`, `doc/engineering/development-roadmap.md`,
  `docs/adr/0011-static-delivery-and-query-index-operations.md`, and
  `docs/adr/index.md`: record cache policy, operations procedure, rollback
  boundary, remaining source-level bottlenecks, and the durable deployment
  decision.
- Remaining product-code work is deliberately unchanged: page-instance
  retention, evidence pagination and virtualization, full-corpus account
  inference precomputation, analytical result caching, and deferred graph
  initialization require separate implementation and before/after traces.

---

## 2026-08-04

- 建立并补强 Chinese Account Detection Active Learning Loop：账号检测从一次性 checkpoint 推理扩展为“case registry -> label batch -> analyst label -> approved corpus -> shadow model -> governed activation”的闭环。
- `system/research/social_bot_detection/active_learning.py`、`chinese_corpus.py`、`evaluate_active_round.py`：新增主动学习 acquisition、批准标签语料导出、frozen holdout leakage manifest、equal-budget active-learning efficiency comparison 和激活评估门禁。
- `system/research/social_bot_detection/datasets.py`、`cli.py`：新增 `approved_account_corpus` loader 和训练 CLI 入口，支持从 `approved_account_labels.jsonl` 进入本地 BotRHG/RoBERTa 训练；`abstain` 只作为审查/拒判标签，不进入二分类监督训练。
- `system/backend/app/core/account_labeling.py`、`account_active_learning.py`：新增账号检测 case 指纹、正式标签体系和后端到研究包的 acquisition adapter；malformed model scores 会被安全忽略而不是破坏选样。
- `system/backend/app/models/account_labeling.py`、`services/account_active_learning_service.py`、`services/account_label_service.py`、`services/account_model_governance_service.py`、`schemas/account_labeling.py`、`api/v1/accounts.py`：新增标注批次、标签提交/裁决、训练候选、模型审批与激活治理 API；标签提交校验 case、batch、fingerprint、evidence ids。
- `system/backend/app/services/account_dataset_service.py`、`system/backend/alembic/versions/b6c2e9d4a731_add_account_detection_active_learning_tables.py`、`system/backend/alembic/env.py`：新增批准标签语料导出、dataset manifest / dataset card、空语料拒绝、账号检测治理表迁移和 Alembic metadata 导入；语料导出只使用仍匹配当前 case fingerprint 的 approved/adjudicated labels。
- `system/backend/app/services/account_model_governance_service.py`、`app/api/v1/accounts.py`：训练候选必须绑定已注册数据集并校验 checkpoint SHA-256；模型审批写入 immutable active-admin approval rows；模型激活只使用持久化指标和已记录审批，不再接受请求体伪造指标/审批身份。
- `doc/research/account-detection-active-learning.md`、`doc/research/account-detection-reference-map.md`、`research-wiki/preflight_runs/20260804T005356Z-expand-and-verify-the-literature-chain-supportin/`、`research-wiki/account-active-learning/chinese-account-detection-active-learning-record.md`、`UBIQUITOUS_LANGUAGE.md`：扩展账号检测文献闭环，明确三类标签、cold-start / warm-start 分界、标注分歧、校准/OOD、leakage-safe evaluation、ML system governance 和未来升级边界；明确 DABot/TwiBot 不支撑 `insufficient_evidence`，该标签边界来自 selective classification / abstention。
- `doc/research/account-detection-acquisition-optimization-plan.md`、`research-wiki/preflight_runs/20260804T152213Z-optimize-chinese-account-detection-active-learni/`：新增主动学习 acquisition 优化预检和计划，明确当前 selector 是 baseline/fallback，后续研究升级顺序为 Chinese MLM surprisal + core-set cold-start、BADGE warm-start、再评估 BatchBALD / contrastive / OOD / meta acquisition。
- 验证：`pytest system/backend/tests/test_account_active_learning.py system/research/social_bot_detection/tests/test_active_learning.py system/research/social_bot_detection/tests/test_public_datasets.py system/backend/tests/test_system_naming_governance.py -q` 结果 `31 passed, 6 skipped, 2 warnings`；敏感标签与不正式简称扫描通过；`re-search` preflight validator 通过（`reference_count=12`，`verified_reference_count=8`，`omission_handling_count=3`）；Alembic head 为 `b6c2e9d4a731`。
- 剩余风险：账号模型审批已具备不可变记录，但仍需后续统一到 shared analysis governance 以减少重复治理面；中文批准语料的真实 active-round RoBERTa/BotRHG retraining、time-forward/platform/community-disjoint/calibration/false-positive burden/efficiency 曲线仍需签名实验制品。

---

## 2026-08-03

- 收口分析员产品展示：`system/frontend/src/views/risk/index.vue` 删除瞬时
  复核状态提示、原始内部理由与传播摘要，系统初判改为中文业务结论；重点账号
  限量展示并使用采集到的昵称。
- `system/backend/app/services/review_case_analysis_projection.py`、
  `system/backend/app/services/review_case_service.py`：新分析结果使用中文
  业务摘要，案件详情会以快照中的昵称替换不透明账号标识。
- `system/backend/app/services/account_service.py`、
  `system/frontend/src/views/accounts/index.vue`：账户列表和详情直接消费
  训练模型的业务结论；移除规则型自动化评分、概率、方法与运行状态展示。首次
  推理按数据指纹缓存，前端账户请求允许模型完成加载。
- `system/frontend/tests/review-case-flow.spec.mjs`、
  `system/backend/tests/test_botrhg_bot_detection.py`、
  `system/backend/tests/test_review_case_service.py`：补充页面边界、模型
  结论投影与昵称替换的回归覆盖。

- Closed the durable review and model-governance boundary without changing the
  dashboard-first frontend.
- `system/backend/app/core/analysis/runtime.py` and
  `system/backend/app/tasks/analysis_tasks.py`: production Teacher dispatch is
  queue-required, while local inline fallback is explicit; broker and worker
  failures remain durable and recoverable.
- `system/backend/app/models/analysis.py`,
  `system/backend/app/services/analysis_governance_service.py`, and
  `system/backend/app/api/v2/analysis.py`: model candidate approvals now use
  authenticated append-only records, distinct-admin activation policy, artifact
  hash verification, quality gates, and audited rollback.
- `system/backend/alembic/versions/a2d8e5c1b904_add_model_activation_approvals.py`:
  added the approval persistence migration and applied it to the active local
  MySQL database; real Celery smoke remains a deployment verification step.
- `UBIQUITOUS_LANGUAGE.md`, `CONTEXT.md`, `doc/engineering/project-map.md`, and
  `doc/engineering/development-roadmap.md`: synchronized formal governance
  vocabulary, control-plane ownership, and current status.
- Verification: targeted governance suite `26 passed`, including a real MySQL
  persistence test; broader backend and frontend verification continues in
  this worktree.
- Runtime verification: the local `analysis` Celery worker connected to Redis
  and returned `OK` to `inspect ping`; an authenticated Teacher Advisory API
  smoke was intentionally not run because the active database has no known
  administrator password in the environment.
- Final quality gates for this pass: backend full suite `510 passed, 19 skipped`,
  frontend component suite `13 passed`, `vue-tsc` plus production Vite build
  passed, `compileall` passed, and `/api/v1/health` plus `/api/v2/health`
  returned 200 after the backend restart.
- Corrected the documented internal control-plane prefix to
  `/api/v2/governance/*`, matching the V2 router; `/api/v2/analysis/*` is not
  a public route.

---

## 2026-08-02

- 完成 Event Review Case 文档同步：更新 `UBIQUITOUS_LANGUAGE.md`、`CONTEXT.md`、`README.md`、`system/README.md`、`doc/engineering/system-governance.md`、`doc/engineering/development-roadmap.md`、`doc/engineering/development-log.md`，并新增 `docs/adr/index.md`、`docs/adr/0007-event-review-case-product-boundary.md`、`docs/adr/0008-lan-prototype-governance-boundary.md`。
- `docs/adr/index.md`：仅在索引中标注旧 ADR 的 superseded 状态，保留既有 accepted ADR 正文不变。
- `docs/adr/0007-event-review-case-product-boundary.md`、`docs/adr/0008-lan-prototype-governance-boundary.md`：分别记录自动复核路由与 LAN prototype governance boundary。

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
## 2026-08-05

- Kept the MARO-style complex review order while making Questioning responses
  targeted, bounding per-case LLM calls, compacting prompt state, and recording
  per-stage prompt/latency telemetry.
- Reused provider HTTP clients and bounded external retrieval concurrency.
- Added a deterministic active-policy frame and rejected non-human-approved
  policies before Judge execution.
- Removed the Teacher Silver gold-label leakage path. The Judge now emits a
  validated machine footer that is stripped from the analyst report and stored
  in the audit sidecar; invalid/missing predictions cannot enter distillation.
- Added strict frozen-XLM-R full-evaluation preflight, reloadable selective-head
  checkpoints, encoder provenance hashes, and artifact manifests. This remains
  a frozen-feature baseline rather than end-to-end SFT.
- Completed the strict five-dataset frozen-XLM-R baseline at
  `G:\CISCN\.tmp\review_student_xlmr_full_v2_20260805`: test Macro-F1 is
  `0.397016 / 0.379167 / 0.464349 / 0.424922 / 0.400998` for
  HateXplain / MultiOFF / PHEME / mcfend / FakeSV. All checkpoint, prediction,
  case, and encoder hashes match and checkpoint reload is verified. The result
  proves the training-artifact loop only: defer is unsupervised, three datasets
  abstain on every test case, and the model is not approved for deployment.
- Restored the Chinese `反制` Judge recommendation trigger and added bilingual
  regression coverage so post-Judge Countermeasure planning is not silently
  skipped by mojibake.
- Hardened the Agent/Student boundary after an independent code audit: all
  expert and full-debate provider calls now share an atomic per-case budget,
  Judge footer booleans require strict JSON types, Teacher Silver confidence is
  derived only from bounded available-axis confidence, Review retrieval reads
  the canonical `review_harmfulness` context, and the offline runner passes the
  actual `max_agent_calls_per_case` parameter.
- Full Review regression: 106 passed. Literature workflow completed with
  MARO, RouteLLM, and Cascade Routing as the main verified transfer sources.
- Unified the Event Review Case asynchronous Teacher with the shared MARO
  runtime. An active LLM provider now runs expert analysis, QuestionReflection,
  targeted expert response, and policy-aware Judge; provider absence, runtime
  failure, or an incomplete chain falls back to the deterministic DAG with
  `execution_mode`, `fallback_reason`, and `non_claimable=true`.
- Added capability-aware execution planning. The reproducible fake-provider
  benchmark records `2` LLM calls for simple text, `6` for claim, multimodal,
  or propagation two-expert complex cases, and `8` for the four-expert complex
  case, instead of the old unbounded full-chain shape.
- Persisted feedback memory now has stable feedback IDs and conservative claim,
  multimodal, conflict, and propagation aliases. Rule generation can no longer
  observe held-out labels; held-out data is evaluated only after a candidate is
  fixed and cannot affect accepted-rule selection.
- Completed the governance-after-change strict baseline at
  `G:\CISCN\.tmp\review_student_xlmr_full_v3_20260805` in `5,513.587` seconds.
  It evaluated all five datasets, wrote `9,699` test predictions, passed the
  full artifact gate, and reloaded every selective-head checkpoint. Test
  Macro-F1 is `0.560184 / 0.379167 / 0.464349 / 0.424922 / 0.400998` for
  HateXplain / MultiOFF / PHEME / mcfend / FakeSV.
- The v3 result is still not deployable: Teacher Silver was not used,
  HateXplain / MultiOFF / FakeSV have `abstain_rate=1.0`, and high-risk recall
  is zero except for mcfend (`0.353937`). This remains a frozen-feature baseline,
  not end-to-end SFT, knowledge distillation, or RL.
- Verification after integration: all `test_review*.py` tests passed (`127`),
  and the Risk/Analysis/Review Case integration selection passed (`115`).
- Added the MARO-compatible horizontal comparison path for MultiAgents and
  ReviewStudent. It fixes the shared `2+1` mapping, reads gold only from source
  cases, rejects legacy or invalid Teacher Silver predictions, separates
  classification from routing coverage, and reports strict paired metrics.
  The Agent dataset runner now accepts a gold-free `--case-manifest`; a
  deterministic stratified manifest builder and standalone comparison CLI were
  added. The existing 15-case Agent smoke overlaps only three of the 9,699
  Student test cases and is not a valid horizontal performance result.

## 2026-08-05: Real Delivery Performance Verification

- Started the refactor-system delivery against the already healthy local
  MySQL, MongoDB, and Redis containers, ran migrations, and built the optimized
  static frontend.
- Verified the real Trump event corpus (467 posts and 25,812 comments), login,
  backend/frontend health endpoints, static cache headers, gzip delivery, and
  the eight MongoDB performance indexes.
- Browser and direct API measurements are recorded in
  `doc/engineering/performance-operations.md`. The remaining bottlenecks are
  full evidence serialization, observed propagation graph construction, and
  on-demand account/dashboard corpus scans; no product source was changed in
  this measurement pass.

## 2026-08-05: Authenticated Demo Warmup

- Added `system/ops/Invoke-DemoWarmup.ps1`, which logs in with credentials
  supplied through the current environment or local `.env`, discovers the
  selected coordination dataset and review case, and consumes the same real
  endpoints used by the dashboard, coordination, account, propagation, and
  review pages.
- Added `-DemoWarmup`, `-DemoWarmupStrict`, `-DemoEventId`,
  `-DemoCaseId`, and `-DemoCoordinationDatasetId` to `system/start-system.ps1`.
  Warmup runs after backend health and before static frontend delivery; it is
  intentionally opt-in so normal development startup does not incur the
  analytical cost.
- A real-data strict run completed 14/14 requests with no failures for
  `trump_visit_2026_05_21`, selecting coordination dataset `6` and review case
  `case_999ca7131fca02459fc1665c`. The cold preparation took about 73 seconds;
  the report contains only timings and statuses under
  `system/output/demo-warmup/`.
- An immediate repeat still took about 69.5 seconds, with coordination result
  reads around 18.3 seconds, graph materialization around 16.2 seconds,
  propagation around 15.3 seconds, and evidence around 4.6 seconds. The
  comparison confirms that warmup improves readiness but does not replace
  durable analytical result caching or payload reduction.
- This operation warms process, MongoDB, and operating-system state only. It
  does not constitute durable result caching, pagination, or an algorithmic
  performance improvement. Product optimization remains ordered by evidence
  payload reduction, propagation result caching, bounded dashboard queries,
  background account materialization, and expired-stream handling.

## 2026-08-07: Chinese Account Detection Deployment Integrity

- Added per-test FastAPI dependency-override isolation. The ordered regression
  that previously removed the shared test database override now passes, and
  production security tests explicitly preserve the evaluator HMAC gate.
- Completed the account-training outbox migration round trip at
  `c3a7e5d8f914`; MySQL reports `created_at` and `updated_at` as `NOT NULL`.
- Reused the research package's canonical account-model bundle verifier in the
  backend. Activation and rollback now reject non-deployable bundles, source
  schema comes from the verified manifest, and runtime encoder, feature schema,
  and calibration must match the detector checkpoint.
- Changed model deserialization to `weights_only=True`, added a locked one-model
  inference cache, and rechecks the detector hash immediately before runtime
  construction.
- Verified `156` account-detection backend tests and `57` standalone research
  package tests. The complete backend run is `805 passed, 6 failed`; the six
  remaining failures are in legacy Coordination dataset fixtures, crawl job
  visibility, and a Review test double, not the account-detection module.
- Restarted the refactor backend on port `8001` and the dedicated
  `account_training` worker. A real Trump/Weibo request with no Active Pointer
  returned `unavailable_without_active_pointer` and did not invoke a fallback
  detector.
- Deployment acceptance remained incomplete at this checkpoint: the registered
  corpus had 415,686 qualified tokens, no 200-label approved detector corpus
  existed, and the backend venv was still CPU-only. The CUDA runtime update is
  recorded in the lifecycle closure below.

## 2026-08-07: Account Model Lifecycle Closure

- Added immutable `ChineseSocialEncoderVersion` records. DAPT now exports a
  portable encoder/tokenizer plus a Torch-loadable frozen state, and every
  deployable detector binds both the encoder version and artifact hash.
- Added append-only `AccountTrainingExportMembership` lineage so the evaluator
  can prove which account cases and labels entered each detector training
  export.
- Added durable, system-owned `AccountModelEvaluationJob` execution. The worker
  binds a candidate to a Frozen Holdout fingerprint, rejects exact training
  overlap, releases database locks during inference, revalidates the data and
  candidate before finalization, and writes the existing HMAC-signed immutable
  evaluation record.
- Active Pointer resolution now distinguishes `available`, `missing`, and
  `invalid`. Corrupt or hash-mismatched active bundles produce a hard detection
  error with the bound model version and pointer revision instead of appearing
  as an absent pointer.
- Added bounded automatic rollback from persisted monitor snapshots. Immediate
  rollback is limited to bundle corruption and runtime load failure; other hard
  errors require two adjacent snapshots. The only target is the current
  pointer revision's previous model after hash, signed-evaluation, approval,
  and activation-history checks.
- Updated `start-system.ps1` so one `solo`, concurrency-one worker consumes both
  `account_training` and `account_evaluation`; Celery Beat retains heartbeat
  reconciliation and active-model monitoring cadence. Replaced naive queued-job
  replay with a transactional evaluation dispatch outbox using claim leases and
  token-fenced finalization. Training and evaluation now share a process-bound
  single-node GPU ownership fence, and stale consumers of either queue are
  removed by the standard startup path.
- Connected the existing account-profile APIs and page projection to the
  governed detector output without exposing embeddings or raw model features.
  The list/detail views show probability, prediction, model version, routing
  path, and support-hypergraph neighbor summaries; a missing or invalid Active
  Pointer is rendered as `暂无研判` rather than invoking a legacy or heuristic
  detector.
- Replaced the backend CPU-only PyTorch build with `torch 2.11.0+cu128` and
  verified the RTX 4060 runtime. DAPT now resolves BF16 on supported CUDA GPUs,
  records the resolved precision in the encoder artifact, and does not advance
  the scheduler or global step when an FP16 GradScaler update is skipped. A
  real local Chinese RoBERTa smoke completed two BF16 optimizer updates and
  peaked at 1,972.8 MiB.
- Exercised the backend `execute_account_training_artifact` adapter against the
  same local model and CUDA device. This uncovered and fixed Python 3.12 dynamic
  dataclass loading by registering the internal DAPT module in `sys.modules`
  before execution; the adapter smoke now returns `global_step=2`,
  `runtime_precision=bfloat16`, and a 64-character artifact hash.
- Verified the account backend suite (`235 passed`), social-bot research suite
  (`65 passed`), and backend regression with the known native-crash fixture
  isolated (`1092 passed, 1 deselected`). MySQL Alembic downgrade/upgrade to
  `c4f7a9d2e618` and real MySQL/MongoDB/Redis connectivity also passed. The one
  deselected legacy Coordination SentenceTransformer fixture remains an
  unrelated Windows native-crash risk.
- Remaining deployment evidence is model/data work: reach the 500,000-token
  DAPT gate, obtain 200 approved binary account labels, run the full CUDA DAPT
  and detector retraining, then complete a real signed shadow evaluation,
  activation, latency/VRAM measurement, and rollback exercise.

## 2026-08-07: Account Module Boundary Review

- Reviewed the account-detection module as a deployable subsystem. Account
  profiles, platform-scoped BotRHG inference, analyst labeling, ALPS/Core-set,
  calibrated uncertainty/BADGE, corpus export, training runs, evaluation jobs,
  Active Pointer resolution, monitoring, and rollback boundaries are present.
- Fixed Frozen Holdout membership creation so `platform` is persisted and
  account disjointness uses `(platform, account_id)`. Corpus manifest platform
  and event scopes are now applied when selecting holdout candidates; legacy
  memberships can still recover platform from `stratum_json`.
- The active-model endpoint now exposes `missing`/`invalid` pointer state and a
  diagnostic reason. Account profiles keep their existing `pending` projection
  when no model is available, avoiding a second pointer query on every profile
  request and never fabricating a detector conclusion.
- The module is not yet deployment-complete: the current database still has
  no approved binary labels or accepted governed bundle. Required evidence is
  a real 500,000-token DAPT run, 200 approved labels, detector retraining,
  leakage-safe evaluation, shadow execution, activation, and rollback rehearsal.

## 2026-08-08: Refactor-System Prototype Deployment

- Deployed the current `refactor-system` backend, account-model worker, Celery
  Beat, and optimized static frontend at `http://127.0.0.1:5173`; frontend and
  backend health checks and the authenticated account-profile API pass.
- Preserved the historical MySQL, MongoDB, and Redis data volumes. The startup
  helper now reuses a complete, image-compatible named infrastructure set and
  rejects partial or mismatched sets instead of attempting conflicting
  containers.
- Mapped this workstation's MongoDB host port to `37017` because Windows
  reserves `27006-27105`; this is an ignored local `.env` override, not a new
  repository default.
- Fixed account-monitor snapshot creation to materialize `created_at` before
  projection. The real scheduled task now completes without SQLAlchemy
  `MissingGreenlet` failures.
- Account profiles return 262 current accounts, but online bot detection remains
  intentionally unavailable. The Botection bootstrap checkpoint underperforms
  its same-split TF-IDF baseline, and the TwiBot-20 runtime is fixed-graph only;
  neither is activated as the Chinese online detector.
- Deferred by operator decision: Chinese DAPT, approved-label detector
  retraining, shadow evaluation, approval/activation, and rollback rehearsal.

## 2026-08-08: Social-Bot Benchmark Boundary

- Removed Botection from the public social-bot dataset dispatcher, training CLI
  choices, default training configuration, and default local runtime settings.
  Its files and explicit legacy loader remain only for historical provenance.
- Registered TwiBot-20 as the primary graph benchmark through the existing
  hash-verified fixed-graph runtime. Cresci-2015, Cresci-2017, and Midterm-2018
  remain independently evaluated public adaptation corpora; their local source
  archives are preserved under `G:/CISCN/dataset/social_bot_detection`.
- Added the formal benchmark protocol. No result from Botection may select a
  detector, establish a comparative claim, or justify Chinese online inference.

## 2026-08-10: Coordination Candidate vs Frozen Production Prior

- Added the executable `frozen_system_evidence_prior` IOHunter adapter around
  the canonical production graph and account-stat core. The adapter is limited
  to `post_evidence_projection_static_graph_only` and cannot stand for the
  complete EventSnapshot, temporal-window, null-model, OOD, or abstention path.
- Hardened claim generation with source/evaluator/fold provenance matching and
  campaign-level bootstrap inference. Model seed and official fold remain
  coupled and are now reported as a protocol limitation.
- Added a non-substituting 100,000 source-occurrence safety gate and per-campaign
  deterministic projection cache. Over-budget production rows block before
  fusion; successful runtime reporting uses the cold projection duration.
- Completed the final checksummed G-drive v2 run with 50 rows (`35 success`, `15 blocked`).
  Russia favors production on all four external-account proxy metrics;
  Venezuela favors the candidate on all four. Only 10/30 pairs are comparable,
  so production replacement remains blocked.
- Verified 49 targeted tests and 95 extended compact loader, execution, matrix
  protocol, production network, and adapter tests. The independent experiment
  audit returned `WARN` for incomplete proxy scope, with no fake-ground-truth,
  score-normalization, phantom-result, or checksum finding.
