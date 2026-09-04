# Risk Review 实现记录：分层 Harmfulness Characterization

## 1. 本轮实现目标

本轮把 Risk Review 从“帖子级语义脚手架”推进到可在风险报告中输出三层 harmfulness 的运行时闭环：

- 帖子级：保留全量 `aggregation_posts`，用于后续用户级和社区级聚合。
- 帖子级评测层：新增固定标注样例上的 Post Gate evaluation harness，报告 claim linking、stance、harm label、harm type、evidence 与 abstain 指标，并把失败样本路由到 planned-only 复核队列。
- 用户级：基于帖子级 harm / stance / claim 结果，聚合账户级 persistence、role、trajectory 和代表性证据。
- 用户级评测层：新增固定账户 gold 样例上的 User Gate evaluation harness，报告 harmful flag、persistence label、trajectory、role、代表性证据与 needs-review 指标，并把失败账户路由到 planned-only 复核队列。
- 社区级：基于账户级结果、协调网络和传播角色，聚合 community harmfulness、coordinated amplification、subgroup role 和关键 claim。
- 图导出层：导出 account-post-claim-community 异构图 schema / artifact，用于后续 HGT / Graph Transformer 输入。
- Gate Dataset 契约层：新增显式 gold/control set 输入契约，使 Gate Suite 只在有标注数据时执行三层评测，默认仍安全 skipped。
- 复核执行层：基于 `review_queue` 构建报告内 evidence corpus，执行本地确定性检索、复核和反制叙事草案生成；同时预留可插拔 `evidence_retriever / review_provider` hook，用于离线 mock 和后续 provider 接入验证。
- 报告层：`risk_service -> build_report` 正式输出 `review_harmfulness`。
- 接口/前端层：风险研判页消费并展示 `review_harmfulness` 的帖子级、用户级、社区级摘要。

## 2. 修改文件

| 文件 | 修改内容 |
|---|---|
| `system/backend/app/core/risk/post_semantics.py` | 在帖子级结果中新增 `aggregation_posts`，保留全量语义结果，并向聚合输出保留 `hashtags / media_urls`，避免用户/社区级和图导出只看到 top evidence posts |
| `system/backend/app/core/risk/review_post_gate.py` | 新增 Risk Review Post Gate 评测 harness，对固定 gold 样例计算 claim linking、stance、harm label、harm type、evidence presence、abstain 指标；gold labels 只用于评测，不用于训练或阈值更新；失败样本进入 planned-only review queue |
| `system/backend/app/core/risk/layered_harmfulness.py` | 实现/完善 Risk Review 帖子级到用户级、社区级的运行时聚合，并增强 edge count 容错 |
| `system/backend/app/core/risk/review_user_gate.py` | 新增 Risk Review User Gate 评测 harness，对固定账户 gold 样例计算 harmful flag、persistence label、trajectory、role micro-F1、representative evidence 与 runtime needs-review 指标；gold labels 只用于评测，不用于训练用户 encoder；失败账户进入 planned-only review queue |
| `system/backend/app/core/risk/review_community_gate.py` | 新增 Risk Review Community Gate 评测 harness，对固定社区 gold 样例计算 collective harm、amplification label、harm type micro-F1、role micro-F1、claim coverage、key account evidence 与 graph export readiness；gold labels 只用于评测，不用于训练图模型；失败社区进入 `CommunityJudge` planned-only review queue |
| `system/backend/app/core/risk/review_gate_dataset.py` | 新增 Risk Review Gate Dataset 契约层，规范化 `metadata / post_cases / user_gold / community_gold / thresholds / prefer_embeddings`，记录 dataset id、version、source、label policy、control notes、layer coverage 与 warning；仅作为评测输入契约，不训练、不校准、不自动生成 gold |
| `system/backend/app/core/risk/review_gate_suite.py` | 新增 Risk Review Gate Suite，将 Post/User/Community Gate 汇总为统一 evaluation report；默认无 gold 时输出 skipped gate 状态；显式传入 `gate_dataset` 时执行有标注层的 Gate，并在报告中输出 `dataset_contract`，不用 runtime 输出冒充 gold-based evaluation |
| `system/backend/app/core/risk/review_graph_exporter.py` | 新增并增强 Risk Review 异构图导出，生成 account/post/claim/community/target/media 节点和 authored、mentions_claim、member_of、community_focuses_claim、post_targets、account_targets、community_targets、post_uses_media、account_shares_object、co_shares_object、coordinated_with 等边，并审计 dropped dangling edges；新增 `write_review_graph_artifact` / `read_review_graph_artifact`，支持 JSON artifact 落盘、回读和 consumer 校验 |
| `system/backend/app/core/risk/review_reviewer.py` | 新增 Risk Review Agent/RAG 复核任务队列脚手架，生成 review items、retrieval tasks、agent tasks 和 counter-narrative inputs |
| `system/backend/app/core/risk/review_review_executor.py` | 新增 Risk Review 本地确定性复核执行器，基于报告内证据执行 local retrieval、review verdict、agent summary 和 counter-narrative draft；新增可选 `evidence_retriever / review_provider` 注入点，默认保持本地确定性路径，provider 失败时回退到本地结果并记录 `provider_audit` |
| `system/backend/app/services/risk_service.py` | 接入 `assess_layered_harmfulness`，在风险评估主链路中生成 `review_harmfulness`；新增 `review_harmfulness.gate_suite`，默认在无 gold 时记录三层 Gate skipped 状态；新增可选 `review_gate_dataset` 参数，供后端显式标注数据驱动 Gate Suite 执行，默认 `/risk/assess` 行为不变 |
| `system/backend/app/schemas/risk.py` | 新增 `KT3GateSuiteRequest`，将离线 Gate Suite 评估请求体与默认查询式风险评估区分开，显式承载 `review_gate_dataset` |
| `system/backend/app/api/v1/risk.py` | 新增 `/risk/review/gate-suite` 离线评估入口，接收 `KT3GateSuiteRequest`，调用 `assess_risk(..., db=None, review_gate_dataset=...)`，返回 `gate_suite`、`dataset_contract`、`review_harmfulness` 与 `persistence.persisted = false`，避免 gold/control 评估报告污染默认历史报告 |
| `system/backend/app/core/risk/report_builder.py` | 报告 schema 增加顶层 `review_harmfulness` |
| `system/backend/app/schemas/risk.py` | 响应 schema 增加 `post_semantics` 与 `review_harmfulness`，请求 schema 增加 `event_id` |
| `system/backend/tests/test_risk.py` | 增加分层 harmfulness、Post/User Gate evaluation、graph export、review queue、review execution、服务级链路和 API 函数级测试 |
| `system/frontend/src/api/risk.ts` | 前端风险 API 参数增加 `event_id` |
| `system/frontend/src/views/risk/index.vue` | 增加 Risk Review 分层 harmfulness、Gate Suite 验收汇总、异构图导出、Agent/RAG planned-only 复核队列、本地复核执行结果展示区 |
| `aris/tech-03-risk/REVIEW_LAYERED_REQUIREMENTS.md` | 同步方法论文档，明确当前实现能力边界 |
| `plan/evidence-map.md` | 扩展证据-主张映射至 63 条 |
| `plan/chapter-blueprints/review-layered-requirements-blueprint.md` | 更新章节蓝图 |
| `plan/review/evidence-coverage.md` | 更新证据覆盖和风险说明 |
| `plan/progress.md` | 更新进度与验证记录 |

## 3. 当前输出结构

风险报告新增顶层字段：

```json
{
  "review_harmfulness": {
    "scope": {},
    "capability_boundary": {},
    "post_level": {},
    "user_level": {},
    "community_level": {},
    "global_summary": {},
    "audit": {},
    "graph_export": {},
    "review_queue": {},
    "review_execution": {},
    "gate_suite": {}
  }
}
```

### 3.1 `post_level`

复用 `post_semantics` 的 summary 和 analysis scope，说明帖子级 claim-conditioned harmfulness 判断结果。

### 3.1.1 `post_gate_evaluation`

Post Gate 是帖子级验收工具，不进入默认风险研判主链路。它接收固定标注样例，黑盒调用当前 `assess_post_semantics`，并在 `aggregation_posts` 全量结果上计算：

- `claim_link_accuracy`
- `stance_accuracy`
- `harm_label_accuracy`
- `harm_type_micro_precision / recall / f1`
- `evidence_presence_rate`
- `abstain_rate`

该层输出 `capability_boundary.evaluation_harness_only = true`、`trained_model = false`、`uses_gold_for_training = false`、`live_llm_or_rag = false`。失败、低置信或 abstain 样本会被组织为 `post_gate_failure_review` 类型的 planned-only 复核项，用于后续人工或 Agent/RAG 复核；这仍不代表在线复核已经执行。

### 3.2 `user_level`

按账户聚合：

- `harmful_ratio`
- `avg_harm_score`
- `persistence_score`
- `stance_distribution`
- `harm_types`
- `trajectory`
- `top_claims`
- `role_profile`
- `risk_profile_flags`
- `representative_posts`

### 3.2.1 `user_gate_evaluation`

User Gate 是用户级验收工具，不进入默认风险研判主链路。它接收固定账户 gold 样例，黑盒评测当前 `review_harmfulness.user_level.accounts`，并计算：

- `harmful_flag_accuracy`
- `persistence_label_accuracy`
- `trajectory_accuracy`
- `role_micro_precision / recall / f1`
- `representative_evidence_rate`
- `runtime_needs_review_rate`

该层输出 `capability_boundary.evaluation_harness_only = true`、`trained_user_encoder = false`、`trained_mil_or_temporal_model = false`、`uses_gold_for_training = false`、`live_llm_or_rag = false`。失败账户会被组织为 `user_gate_failure_review` 类型的 planned-only 复核项，用于后续人工或 Agent/RAG 复核；这仍不代表训练式用户 encoder 或在线 Agent 审议已经完成。

### 3.3 `community_level`

按协调网络组件或 fallback community 聚合：

- `semantic_posts`
- `harmful_posts`
- `harmful_accounts`
- `dominant_harm_types`
- `amplification_score`
- `subgroup_roles`
- `claims_coverage`
- `key_accounts`
- `risk_flags`

### 3.4 `global_summary`

提供全局 Risk Review harmfulness 摘要：

- `harm_types`
- `stance_distribution`
- `claim_rank`
- `review_harm_risk_level`

### 3.5 `graph_export`

提供社区级异构图导出，状态是 `schema_exported / artifact_exported / consumer_readable / export_verified`，不是训练式图模型。`risk_service.assess_risk()` 默认仍只返回内存中的 `review_harmfulness.graph_export`，不会自动产生文件系统副作用；artifact 落盘通过显式调用 `write_review_graph_artifact` 完成：

- `capability_boundary.status = implemented_graph_export_schema`
- `capability_boundary.trained_graph_model = false`
- `schema.node_types = account / post / claim / community / target / media`
- `schema.edge_types = authored / mentions_claim / engages_claim / member_of / community_focuses_claim / post_targets / account_targets / community_targets / post_uses_media / account_shares_object / co_shares_object / coordinated_with / propagates_to`
- `summary.node_types` 与 `summary.edge_types` 给出节点/边数量统计
- `summary.dropped_dangling_edges` 记录因端点缺失被清理的边数量
- `nodes` / `edges` 是可审计图 artifact，可供后续下游 consumer 读取
- `write_review_graph_artifact(graph, path)` 将图写为带 `schema_version = review-graph-export-v1` 的 JSON artifact，并返回 manifest
- `read_review_graph_artifact(path)` 读取 artifact 并验证 schema、summary、nodes、edges、无悬挂边和节点/边数量一致性

该层只能声称“异构图导出、artifact 落盘、consumer 回读和 schema 验证”，不能声称“已训练图编码器”。

### 3.6 `review_queue`

提供 Agent/RAG 复核闭环的任务契约，但不执行在线检索或 LLM：

- `capability_boundary.status = implemented_review_queue_scaffold`
- `capability_boundary.live_llm_or_rag = false`
- `review_items`：帖子、账户、社区复核项
- `retrieval_tasks`：claim linking、外部证据检索、campaign claim verification 任务
- `agent_tasks`：HarmReviewer、RAGEvidenceRetriever、AccountBehaviorReviewer、CommunityJudge、CounterNarrativePlanner 等 planned-only 任务
- `counter_narrative_inputs`：面向后续反制叙事生成的 claim、harm type、社区受众上下文

所有任务项均带有 `execution_status = planned_only` 和 `requires_external_execution = true`，避免把“队列生成”误写成“真实 Agent/RAG 已执行”。

### 3.7 `review_execution`

提供本地确定性复核执行结果，但默认不调用外部 LLM、搜索引擎或向量数据库：

- `capability_boundary.status = implemented_local_deterministic_review_executor`
- `capability_boundary.local_rag = true`
- `capability_boundary.live_llm_or_external_rag = false`
- `capability_boundary.pluggable_retriever = false` 与 `capability_boundary.pluggable_review_provider = false` 表示默认主链路没有启用 provider
- 显式传入离线 mock provider 时，`capability_boundary.status = implemented_pluggable_local_review_executor`
- `provider_failure_policy = fallback_to_local_result`，provider 抛错或返回空结果不会中断主报告，而是回退到本地 deterministic result
- `retrieval_results`：对 queue 中检索任务执行本地 lexical evidence retrieval
- `review_results`：对帖子、账户、社区复核项给出本地 verdict、local confidence、是否仍需外部复核
- `agent_results`：对 planned agent tasks 做本地 summary
- `counter_narrative_drafts`：基于 top harmful claim 生成反制叙事 brief
- `provider_audit`：记录 provider 是否配置、provider 结果使用数量、是否发生 live external call、失败摘要

该层把 `planned_only` 队列推进到 `executed_local`，并把未来 provider 接入点固定为可测试接口；但当前默认报告仍是离线、本地、确定性的，不能视为在线 Agent/RAG 能力已落地。

### 3.8 `gate_suite` 与 `gate_dataset`

`gate_suite` 是三层 Gate 的统一评测报告，不是训练入口。默认风险研判主链路没有 gold/control set，因此输出：

- `summary.executed_gates = 0`
- `summary.skipped_gates = 3`
- `skipped_gates.post_gate.reason = missing_post_cases`
- `skipped_gates.user_gate.reason = missing_user_gold`
- `skipped_gates.community_gate.reason = missing_community_gold`

当后端显式传入 `review_gate_dataset` 时，Suite 会从同一份契约中读取：

- `metadata.dataset_id / version / source / label_policy / control_set_notes`
- `post_cases`
- `user_gold`
- `community_gold`
- `thresholds`
- `prefer_embeddings`

并只对有 gold 的层执行 Gate。报告会输出 `dataset_contract.provided`、`dataset_contract.validation.layer_coverage`、`dataset_contract.counts` 和 `threshold_layers`。该契约只用于 offline evaluation，绝不从 runtime 输出自动生成 gold，也不使用 gold 更新阈值、训练模型或校准聚合逻辑。

后端新增 `/risk/review/gate-suite` 作为外部可调用的离线评估入口。它与默认 `/risk/assess` 的区别是：默认风险评估用于线上报告和可选持久化；Gate Suite endpoint 用于带 gold/control set 的离线验收，强制 `db=None`，响应中显式返回 `persistence.persisted = false`。该设计避免把 gold labels、失败样本和评测阈值写入普通风险报告历史。

## 4. 能力边界

当前可以正式声称：

- 已实现帖子级 harmfulness 结果向用户级和社区级的运行时聚合。
- 已实现 Risk Review Post Gate 评测 harness，能够在固定 gold 样例上报告 claim linking、stance、harm label、harm type、evidence 与 abstain 指标，并把失败样本路由到 planned-only 复核队列。
- 已实现 `review_harmfulness` 报告字段。
- 已实现用户级 harmful persistence / role / trajectory 的可解释聚合版。
- 已实现 Risk Review User Gate 评测 harness，能够在固定账户 gold 样例上报告 harmful flag、persistence、trajectory、role 与代表性证据指标，并把失败账户路由到 planned-only 复核队列。
- 已实现社区级 collective harm / amplification / subgroup role 的可解释聚合版。
- 已实现 Risk Review Community Gate 评测 harness，能够在固定社区 gold 样例上报告 collective harm、coordinated amplification、harm type、subgroup role、claim coverage、key account evidence 和 graph export readiness 指标，并把失败社区路由到 `CommunityJudge` planned-only 复核队列。
- 已实现 Risk Review Gate Suite，能够统一汇总 Post/User/Community Gate 的执行/跳过状态、指标名、失败阈值和 review item 数；默认主报告在没有固定 gold 时输出 `skipped_gates = 3`，避免把 runtime aggregation 误写成 gold-based evaluation。
- 已实现 Risk Review Gate Dataset 契约，能够在显式提供 gold/control set 时驱动 Gate Suite 执行三层评测，并记录 dataset metadata、label policy、control notes、layer coverage、gold counts 与 threshold layers。
- 已实现 `/risk/review/gate-suite` 离线评估 API，能够从请求体接收 `review_gate_dataset`，执行三层 Gate Suite，并返回不持久化的评估响应。
- 已实现 Risk Review 异构图导出能力，能够输出 account-post-claim-community-target-media 图 schema、节点、边、对象介导关系和统计，并能写出/回读 JSON artifact。
- 已实现 Risk Review Agent/RAG 复核任务队列脚手架，能够把低置信帖子、未匹配 claim、高风险账户和高风险社区组织成 planned-only 复核任务。
- 已实现 Risk Review 本地确定性复核执行器，能够在报告内 evidence corpus 上执行本地检索、复核 verdict 和 agent summary。
- 已为 Risk Review 复核执行器预留离线可测的 `evidence_retriever / review_provider` 插拔接口，并验证 mock provider 成功路径与 provider 失败回退路径。
- 已通过单元测试验证报告链路。

当前不能声称：

- 已训练端到端多模态 harmfulness 模型。
- 已完成帖子级 teacher-student 蒸馏、模型微调或权重训练。
- 已训练用户级时序 Transformer / MIL 模型。
- 已训练用户级 harmfulness encoder、MIL、hierarchical attention 或 temporal Transformer。
- 已训练社区级 HGT / Graph Transformer / temporal graph model。
- 已实现图编码器、图表示学习或子图解释实验。
- 已实现在线 LLM / 外部检索 / 向量数据库 RAG 复核执行闭环。
- 已接入真实在线 provider、多轮 Agent 审议或外部证据检索服务。
- 已完成跨平台、多模态、真实标注数据上的系统性实验。
- 真实项目 gold/control set 上已有系统性 Gate Suite 验收结果。

因此，本轮实现是 `post/user/community gate evaluation harness + gate suite + runtime aggregation + heterogeneous graph export + review queue scaffold + local deterministic review execution + offline-safe provider hook`，不是最终研究目标中的 `trained post model`、`trained user encoder`、`trained graph-native model` 或 `live Agent/RAG review system`。

## 5. 验证记录

已运行：

```powershell
cd G:\CISCN\CogGuard\system\backend
python -m pytest tests/test_risk.py
python -m compileall app/core/risk app/services/risk_service.py
```

结果：

- `tests/test_risk.py`：54 passed
- `compileall`：通过

补充服务级验证：

- 新增 `TestRiskServiceKT3Integration.test_assess_risk_includes_review_harmfulness`
- 通过 mock 上游协调检测、传播分析、账户画像和帖子加载，直接调用 `risk_service.assess_risk`
- 验证最终报告包含 `post_semantics` 与 `review_harmfulness.post_level / user_level / community_level`
- 新增 `TestKT3PostGate.test_evaluate_review_post_gate_reports_metrics_and_boundaries`
- 验证 Post Gate 输出 evaluation-only 边界、claim/stance/harm/evidence/abstain 指标，并确认分母来自 `aggregation_posts`
- 新增 `TestKT3PostGate.test_evaluate_review_post_gate_routes_failures_to_planned_review_queue`
- 验证 Post Gate 失败样本进入 `post_gate_failure_review` planned-only 队列，且不执行 live LLM/RAG
- 新增 `TestKT3UserGate.test_evaluate_review_user_gate_reports_metrics_and_boundaries`
- 验证 User Gate 输出 evaluation-only 边界、harmful flag、persistence、trajectory、role、代表性证据和 needs-review 指标
- 新增 `TestKT3UserGate.test_evaluate_review_user_gate_routes_failures_to_planned_review_queue`
- 验证 User Gate 失败账户进入 `user_gate_failure_review` planned-only 队列，且不执行 live LLM/RAG
- 新增 `TestKT3CommunityGate.test_evaluate_review_community_gate_reports_metrics_boundaries_and_graph_audit`
- 验证 Community Gate 输出 evaluation-only 边界、collective harm、amplification、harm type、role、claim coverage、key account evidence 和 graph export readiness 指标，并确认 graph audit 不表示训练图模型已实现
- 新增 `TestKT3CommunityGate.test_evaluate_review_community_gate_routes_failures_to_planned_review_queue`
- 验证 Community Gate 失败社区进入 `community_gate_failure_review` planned-only 队列，由 `CommunityJudge` 承接，且不执行 live LLM/RAG
- 新增 `TestKT3GateSuite.test_evaluate_review_gate_suite_composes_layered_gates`
- 验证 Gate Suite 能统一汇总 Post/User/Community Gate 的 boundary、metrics、failed thresholds 与 review item 数，且不训练帖子模型、用户 encoder 或图模型
- 新增 `TestKT3GateSuite.test_evaluate_review_gate_suite_marks_missing_gold_as_skipped`
- 验证缺少 post cases、user gold、community gold 时 Gate Suite 会显式标注三层 Gate skipped，`overall_pass = false`，不会把运行时输出冒充 gold-based evaluation
- 新增 `TestKT3GateSuite.test_evaluate_review_gate_suite_accepts_dataset_contract`
- 验证显式 `gate_dataset` 能驱动 Post/User/Community Gate 全部执行，报告记录 dataset id、counts、layer coverage 和 thresholds，且仍保持 evaluation-only、非训练边界
- 新增 `TestKT3GateDataset.test_normalize_review_gate_dataset_reports_contract_and_counts`
- 验证 dataset contract 可以记录 metadata、layer coverage、gold counts 和 threshold layers
- 新增 `TestKT3GateDataset.test_normalize_review_gate_dataset_warns_without_inventing_gold`
- 验证非法 metadata、post_cases、user_gold、thresholds、prefer_embeddings 会进入 warnings，不会从 runtime 输出或坏输入中伪造 gold
- 新增 `TestKT3ReviewQueue.test_build_review_review_queue`
- 验证 review queue 会产生帖子级、账户级、社区级复核项，生成检索任务，并标注 `planned_only`
- 新增 `TestKT3GraphExport.test_export_review_heterogeneous_graph`
- 验证 graph export 会生成 account/post/claim/community/target/media 节点和 authored/member_of/mentions_claim/post_uses_media/account_shares_object/account_targets/community_targets/co_shares_object 等边，验证无悬挂边，并标注 `trained_graph_model = false`
- 验证 `write_review_graph_artifact` 可将图写入临时 JSON artifact，manifest 标注 `artifact_exported / consumer_readable / export_verified`，并由 `read_review_graph_artifact` 成功回读校验
- 新增负向 consumer smoke test：构造包含 dangling edge 的坏 artifact，验证 `read_review_graph_artifact` 会拒绝并抛出 `ValueError`
- 新增 `TestKT3ReviewExecution.test_execute_review_review_queue_locally`
- 验证本地执行器会执行 review items、retrieval tasks、agent tasks，并标注 `executed_local`；同时验证默认路径不启用 provider、检索模式为 `local_lexical_retrieval`、连续两次执行结果保持确定性
- 新增 `TestKT3ReviewExecution.test_execute_review_review_queue_accepts_offline_mock_providers`
- 验证显式注入离线 mock retriever / review provider 时，执行器会使用 provider 结果，记录 `provider_results_used`，但仍标注 `live_llm_or_external_rag = false`
- 新增 `TestKT3ReviewExecution.test_execute_review_review_queue_falls_back_when_provider_fails`
- 验证 provider 抛错时，执行器不会中断报告生成，会记录 `provider_audit.failures` 并回退到本地 deterministic retrieval / review
- 新增 `TestRiskAPIKT3Integration.test_assess_risk_api_returns_review_harmfulness`
- 通过 mock `risk_api.risk_service.assess_risk`，直接调用 `/risk/assess` 路由函数
- 验证 `event_id`、`time_window`、`min_participation`、`edge_weight`、`user_id` 正确传递，响应保留 `review_harmfulness`
- 验证 `risk_service.assess_risk` 默认报告包含 `review_harmfulness.gate_suite`，在没有固定 gold 时 `executed_gates = 0 / skipped_gates = 3`
- 新增 `TestRiskServiceKT3Integration.test_assess_risk_executes_review_gate_suite_when_gold_dataset_provided`
- 验证 `risk_service.assess_risk(..., review_gate_dataset=...)` 能在服务主链路中执行三层 Gate，报告保留 dataset contract、gold counts、执行状态和非训练/非在线边界；当前 mock 输出仍会因 low-confidence stance 产生 Post Gate review items，这说明 Suite 执行不等于底层模型已达标
- 验证 API 响应保留 `review_harmfulness.gate_suite`，并保留 `evaluation_harness_only = true` 边界
- 新增 `TestRiskAPIKT3Integration.test_assess_review_gate_suite_api_accepts_dataset_body_without_persistence`
- 验证 `/risk/review/gate-suite` 可从 request body 接收 `review_gate_dataset`，调用服务时强制 `db=None`，响应返回 `gate_suite` 和 `persistence.persisted = false`
- 验证前端风险研判页可展示 Gate Suite 的 executed/skipped、overall pass、跳过原因和 evaluation-only 边界

最新结果：

- `tests/test_risk.py`：54 passed
- `compileall`：通过
- `npx vue-tsc -b --pretty false`：通过
- `npm run build`：通过；仅出现 Vite 大 chunk 警告

构建说明：

- `npm run build` 会生成 `system/frontend/dist`。
- 本轮验证后已删除该构建产物，避免把大体积构建输出混入源码变更。

### 5.1 验收对照表

| 能力项 | 本轮状态 | 已验证证据 | 仍然缺口 |
|---|---|---|---|
| 帖子级语义输出 | 已具备运行时语义骨架，并新增 Post Gate evaluation harness，可在固定样例上报告 claim/stance/harm/evidence/abstain 指标并路由失败样本 | `TestPostSemantics.test_assess_post_semantics`、`TestKT3PostGate.test_evaluate_review_post_gate_reports_metrics_and_boundaries`、`TestKT3PostGate.test_evaluate_review_post_gate_routes_failures_to_planned_review_queue` | 未训练端到端多模态模型，未接图像/视频 encoder，未完成 teacher-student 蒸馏 |
| 用户级 harmfulness | 已具备 runtime aggregation，并新增 User Gate evaluation harness，可在固定账户样例上报告 harmful/persistence/trajectory/role/evidence 指标并路由失败账户 | `TestLayeredHarmfulness.test_assess_layered_harmfulness`、`TestKT3UserGate.test_evaluate_review_user_gate_reports_metrics_and_boundaries`、`TestKT3UserGate.test_evaluate_review_user_gate_routes_failures_to_planned_review_queue` | 未训练 MIL / temporal Transformer / user encoder，未完成跨事件/跨平台监督评估 |
| 社区级 harmfulness | 已具备 runtime aggregation，并新增 Community Gate evaluation harness，可在固定社区样例上报告 collective harm/amplification/harm type/role/claim/key-account evidence/graph readiness 指标并路由失败社区 | `TestLayeredHarmfulness.test_assess_layered_harmfulness`、`TestKT3CommunityGate.test_evaluate_review_community_gate_reports_metrics_boundaries_and_graph_audit`、`TestKT3CommunityGate.test_evaluate_review_community_gate_routes_failures_to_planned_review_queue` | 未训练 HGT / Graph Transformer / TGN，未做 control-aware 真实实验 |
| Gate Suite | 已具备三层 Gate 统一汇总报告，并已接入默认 `review_harmfulness.gate_suite`；无 gold 时显式 skipped；显式 `review_gate_dataset` 可在服务主链路或 `/risk/review/gate-suite` API 中执行三层评测，不冒充真实评测 | `TestKT3GateSuite.test_evaluate_review_gate_suite_composes_layered_gates`、`TestKT3GateSuite.test_evaluate_review_gate_suite_marks_missing_gold_as_skipped`、`TestKT3GateSuite.test_evaluate_review_gate_suite_accepts_dataset_contract`、`TestKT3GateDataset.test_normalize_review_gate_dataset_reports_contract_and_counts`、`TestKT3GateDataset.test_normalize_review_gate_dataset_warns_without_inventing_gold`、`TestRiskServiceKT3Integration.test_assess_risk_includes_review_harmfulness`、`TestRiskServiceKT3Integration.test_assess_risk_executes_review_gate_suite_when_gold_dataset_provided`、`TestRiskAPIKT3Integration.test_assess_review_gate_suite_api_accepts_dataset_body_without_persistence` | 仍需接入项目真实 gold/control set 后在真实事件上执行三层评测 |
| 异构图导出 | 已具备 schema_exported / artifact_exported / consumer_readable / export_verified，覆盖 target/media/shared-object，支持 JSON artifact 落盘和回读 | `TestKT3GraphExport.test_export_review_heterogeneous_graph` | 未训练 graph encoder，未跑 HGT / Graph Transformer / TGN |
| Agent/RAG 队列 | 已生成 planned-only 任务契约 | `TestKT3ReviewQueue.test_build_review_review_queue` | 未接在线 Agent、多轮审议或外部检索 |
| 本地复核执行 | 已实现 deterministic local executor，并预留 offline-safe provider hook；mock provider 与失败回退均已验证 | `TestKT3ReviewExecution.test_execute_review_review_queue_locally`、`TestKT3ReviewExecution.test_execute_review_review_queue_accepts_offline_mock_providers`、`TestKT3ReviewExecution.test_execute_review_review_queue_falls_back_when_provider_fails` | 未接真实在线 LLM provider、外部搜索、向量数据库 RAG |
| 风险报告链路 | 已接入最终报告 | `TestRiskServiceKT3Integration.test_assess_risk_includes_review_harmfulness` | 仍需真实事件端到端样例验收 |
| 前端展示 | 已展示 Risk Review 分层、Gate Suite、队列和执行结果 | `npx vue-tsc -b --pretty false`、`npm run build` | 未做浏览器截图级 UI 验收 |

## 6. 多智能体执行记录

本轮执行中先前尝试调用两个子智能体时失败：

- 代码链路核查智能体
- 文档/记录核查智能体

两个子智能体均因本地代理返回 `401 Unauthorized` 失败：

```text
CC Switch local proxy failed ... upstream_status: HTTP 401; cause: User account is not active
```

因此本轮降级为主线直接执行。该失败不影响当前实现结果，但意味着“多智能体并行核查”没有实际完成，需要在后续代理环境恢复后重新执行更严格的独立 review。

后续在当前环境中重新调用了一个独立只读 reviewer 子智能体并成功返回建议。已采纳的建议包括：

- `review_queue` 每个任务项显式标注 `execution_status = planned_only` 与 `requires_external_execution = true`；
- 用户级/社区级 `needs_review` 不再只看 harmfulness abstain，而是纳入 stance abstain、unlinked claim 与低置信度；
- 前端新增 Risk Review Agent/RAG 复核队列摘要与复核项表格；
- 后端测试从结构存在性扩展到具体触发规则断言。

## 7. 下一步建议

1. 用真实事件数据跑一轮端到端报告，检查 `user_level` 和 `community_level` 的解释质量。
2. 用 `review_gate_dataset` 契约接入公开/项目标注集，随后再构建帖子级 teacher-student 标注和蒸馏流程。
3. 在社区级引入真实异构图模型之前，继续把 Community Gate harness 扩展到真实 gold/control set，固化 collective harm、amplification、role decomposition 与 evidence 指标，并记录 control set 设计。
4. 后续在安全策略、检索源和 provider 配置明确后，再把当前 offline-safe hook 扩展为真实在线 LLM / 外部检索 / 向量数据库 RAG；在此之前文档只应声称“接口预留与 mock 验证”。

## 8. 本轮增量：Risk Review Gate Dataset 机器可读契约

本轮在不改变默认 `/risk/assess` 在线风险评估语义的前提下，补齐了外部评测脚本所需的 Risk Review Gate Dataset 契约发布与校验能力。

| 文件 | 本轮增量 |
|---|---|
| `system/backend/app/core/risk/review_gate_dataset.py` | 新增 `Risk Review_GATE_DATASET_CONTRACT`、`get_review_gate_dataset_contract_spec()`、`validate_review_gate_dataset_contract()`；契约显式列出 required metadata、Post/User/Community layer contracts、默认指标阈值、example skeleton、usage policy、leakage policy 和 warning codes |
| `system/backend/app/api/v1/risk.py` | 新增 `GET /risk/review/gate-dataset/contract` 和 `POST /risk/review/gate-dataset/validate`；两个接口只发布/校验契约，不运行风险评估、不持久化、不训练模型 |
| `system/backend/app/schemas/risk.py` | 新增 `KT3GateDatasetValidationRequest`，用于接收待校验的 `review_gate_dataset` JSON |
| `system/backend/tests/test_risk.py` | 新增 contract spec、validation report、API contract、API validate 测试；同时更新 Gate Dataset warning 断言，使空 gold 和缺 metadata 能被显式报告 |
| `aris/tech-03-risk/REVIEW_LAYERED_REQUIREMENTS.md` | 新增 “Risk Review Gate Dataset machine-readable contract update” 章节，记录 contract / validate / gate-suite 三个入口的职责和能力边界 |

当前契约边界：

- `uses_gold_for_training = false`
- `runtime_gold_generation = false`
- `default_persistence = false`
- `no_runtime_derived_gold = true`
- `no_training_or_calibration_from_gate_gold = true`
- `control_set_required_for_formal_acceptance = true`

验证结果：

- `python -m pytest tests/test_risk.py -q`：54 passed
- `python -m compileall app\core\risk app\services\risk_service.py app\schemas\risk.py app\api\v1\risk.py tests\test_risk.py`：通过
- 首次 pytest 使用系统默认 C 盘临时目录时，图导出测试因 `No space left on device` 在 `tmp_path` 写文件失败；将 `TMP/TEMP` 指向仓库临时目录后通过，说明失败原因是环境临时目录空间不足，不是 Risk Review 逻辑失败

## 9. 本轮增量：Risk Review Gate Dataset manifest

本轮继续增强 Gate Dataset 契约层，使离线 Gate Suite 具备更强的可复现实验审计能力。

| 文件 | 本轮增量 |
|---|---|
| `system/backend/app/core/risk/review_gate_dataset.py` | 新增 `build_review_gate_dataset_manifest()`，生成 `review_gate_dataset_manifest`；包含 dataset/layer/threshold fingerprints、metadata、layer coverage、counts、threshold layers、warning count 和 persistence policy |
| `system/backend/app/core/risk/review_gate_dataset.py` | `gate_dataset_contract_view()` 与 `validate_review_gate_dataset_contract()` 均返回 `manifest`，供 Gate Suite 和 validate API 复用 |
| `system/backend/tests/test_risk.py` | 新增 manifest 稳定性与 gold-safe 测试，验证 fingerprint 稳定、gold 变化会改变 fingerprint、manifest 不包含 `post_cases / user_gold / community_gold` 原始 payload |
| `aris/tech-03-risk/REVIEW_LAYERED_REQUIREMENTS.md` | 新增 Gate Dataset manifest 说明，明确它是可复现审计元数据，不是训练能力，也不是 gold payload 持久化 |

manifest 边界：

- `contains_gold_payload = false`
- `fingerprint_algorithm = sha256-canonical-json`
- 只暴露 metadata、counts、coverage、threshold layers 和哈希
- 不复制原始 `post_cases / user_gold / community_gold`

验证结果：

- `python -m pytest tests/test_risk.py -q`：54 passed
- `python -m compileall app\core\risk app\services\risk_service.py app\schemas\risk.py app\api\v1\risk.py tests\test_risk.py`：通过

## 10. 本轮增量：前端 Risk Review 契约查看与离线验收入口

本轮把后端 Risk Review Gate Dataset contract / validate / gate-suite 能力接入前端，使评审人员不必只依赖 API 文档或测试文件查看契约。

| 文件 | 本轮增量 |
|---|---|
| `system/frontend/src/api/risk.ts` | 新增 `getKT3GateDatasetContract()`、`validateKT3GateDataset()`、`assessKT3GateSuite()` 三个 API client 方法 |
| `system/frontend/src/views/risk/index.vue` | 新增“Risk Review Gate Dataset 契约与离线验收”卡片；支持加载契约、填入 example skeleton、粘贴 JSON、校验数据集、运行离线 Gate Suite |
| `system/frontend/src/views/risk/index.vue` | 页面展示 required metadata、layer contracts、manifest algorithm、`contains_gold_payload`、layer coverage、counts、warnings、missing metadata、dataset fingerprint 和 `persistence.persisted` |
| `system/frontend/src/views/risk/index.vue` | 同步修正风险页对统一响应包装的读取层级，`assessRisk` 与 `listRiskReports` 直接读取拦截器返回的 `res.data`，与其他前端页面保持一致 |
| `aris/tech-03-risk/REVIEW_LAYERED_REQUIREMENTS.md` | 新增 frontend acceptance surface 说明，明确前端只暴露契约查看/校验与离线验收入口，不改变训练/持久化边界 |

验证结果：

- `npx vue-tsc -b --pretty false`：通过
- `npm run build`：通过，仅保留 Vite 大 chunk 警告；构建产物 `system/frontend/dist` 已删除
- `python -m pytest tests/test_risk.py -q`：54 passed
- `python -m compileall app\core\risk app\services\risk_service.py app\schemas\risk.py app\api\v1\risk.py tests\test_risk.py`：通过

## 11. 本轮增量：Gate Dataset formal readiness 审计

本轮继续增强 Risk Review Gate Dataset 契约，把“可执行某个离线 Gate”和“可作为 Risk Review 三层正式验收证据”拆成两个明确状态，防止单层 smoke dataset 或缺少 control/split/leakage 说明的数据集被误读为正式验收完成。

| 文件 | 本轮增量 |
|---|---|
| `system/backend/app/core/risk/review_gate_dataset.py` | 新增 `FORMAL_ACCEPTANCE_METADATA_FIELDS`、`REQUIRED_GATE_LAYERS` 与 `evaluation_readiness` 审计对象；`normalize_review_gate_dataset()`、`gate_dataset_contract_view()`、`validate_review_gate_dataset_contract()` 和 `build_review_gate_dataset_manifest()` 均返回 readiness 信息 |
| `system/backend/app/core/risk/review_gate_dataset.py` | 新增 readiness warning codes：缺 control set notes、split、leakage policy、threshold policy、三层 coverage 或存在契约 shape warning 时，`formal_acceptance_ready = false` |
| `system/backend/tests/test_risk.py` | 新增 formal readiness 正/负向测试；验证 metadata 完整、三层 gold 覆盖且阈值策略冻结时才返回 `formal_acceptance_ready = true`，并验证 manifest 同步携带 readiness 但不复制 gold payload |
| `system/frontend/src/views/risk/index.vue` | 前端契约卡片新增 formal ready/not-ready 标签、readiness warning 文本与 required metadata/control/split/leakage/threshold/full-layer 状态展示 |
| `aris/tech-03-risk/REVIEW_LAYERED_REQUIREMENTS.md` | 新增 Gate Dataset readiness audit 小节，说明 `valid_for_execution` 与 `formal_acceptance_ready` 的差异 |

当前语义边界：

- `valid = true` 只表示契约可用于执行至少一个有标注层级的离线 Gate。
- `formal_acceptance_ready = true` 才表示该数据集具备三层 Risk Review 离线验收的最低契约条件。
- readiness audit 仍是 evaluation contract，不是训练式帖子模型、用户 encoder、社区图模型或在线 Agent/RAG 能力。

验证结果：

- `python -m pytest tests/test_risk.py::TestKT3GateDataset -q`：6 passed

## 12. 本轮增量：帖子级多模态、用户级 MIL 与本地多智能体 runtime

本轮针对“帖子级多模态检测 -> 用户级 MIL -> 真实多智能体复核”的闭环继续推进 Risk Review。设计原则是把高水平文献的方法形状落到可运行契约，而不是把系统改写成手工特征工程；同时继续明确当前能力边界，不把推理脚手架写成已训练模型。

| 文件 | 本轮增量 |
|---|---|
| `system/backend/app/core/risk/post_semantics.py` | 在帖子级输出中新增 `multimodal_detection`，对 text、OCR、ASR、caption/media、emoji/hashtag 做 modality-aware late fusion；输出 channel results、evidence modalities、cross-modal conflict、claim grounding、method trace 和 capability boundary |
| `system/backend/app/core/risk/review_user_mil.py` | 新增用户级 attention-MIL inference scaffold；把账户建模为 post bag，输出 `mil_harm_score`、`attention_posts`、harm type distribution、stance distribution、context、method trace 与 trained-model boundary |
| `system/backend/app/core/risk/review_multi_agent.py` | 新增本地多智能体 runtime；执行 `HarmReviewAgent`、`StanceClaimAgent`、`EvidenceRetrievalAgent`、`UserMILAgent`、`CommunityJudgeAgent`、`CounterNarrativeAgent` 六个角色，并输出共享 blackboard 摘要、agent results、final decision、provider audit |
| `system/backend/app/services/risk_service.py` | 在 `review_harmfulness` 主链路中接入 `user_mil` 与 `multi_agent_review`；顺序为 layered harmfulness -> user MIL -> graph export -> review queue -> local review execution -> multi-agent review -> gate suite |
| `system/backend/tests/test_risk.py` | 新增/增强帖子级多模态、用户级 MIL、本地多智能体 runtime、离线 provider hook 和服务级集成测试，验证默认不启用在线 LLM/RAG、不训练模型、不使用 runtime gold |
| `aris/tech-03-risk/REVIEW_LAYERED_REQUIREMENTS.md` | 新增“本轮方法闭环”章节，把 RGCL、MOCHEG、FACTIFY3M、FakeSV、Attention-MIL、用户建模、MARO、ReAct 等文献映射到当前实现和未来差距 |

当前可声明能力：

- 帖子级已经能输出 `multimodal_detection`，联合文本、OCR、ASR、caption/media、emoji/hashtag 的证据通道，并明确 `true_image_encoder = false`、`true_video_encoder = false`、`trained_multimodal_model = false`。
- 用户级已经能以 MIL 任务形状输出账户 bag-level harmfulness、attention posts 和实例贡献证据，并明确 `trained_mil_model = false`、`trained_user_encoder = false`。
- Agent 层已经从 `planned_only` 队列推进到本地真实执行的多智能体 runtime，六个角色会读取共享 blackboard 并产生 `agent_results` 与 `final_decision`。
- 多智能体 provider hook 支持离线 mock 与失败回退；默认不调用在线 LLM、外部搜索或向量数据库 RAG。

仍然不能声明的能力：

- 不能声明已经训练端到端图像/视频多模态 harmfulness 模型。
- 不能声明已经完成 teacher-student 蒸馏或公开 benchmark 上的帖子级模型实验。
- 不能声明已经训练神经 MIL、temporal Transformer 或用户级 encoder。
- 不能声明已经接入真实在线多智能体 LLM/RAG provider。
- 不能声明 Gate Suite 的 smoke/gold 契约等价于真实项目三层正式验收。

验证结果：

- `python -m pytest tests/test_risk.py::TestPostSemantics::test_assess_post_semantics tests/test_risk.py::TestKT3UserMIL tests/test_risk.py::TestKT3MultiAgentRuntime tests/test_risk.py::TestRiskServiceKT3Integration::test_assess_risk_includes_review_harmfulness -q`：5 passed
