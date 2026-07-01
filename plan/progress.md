# 进度记录

## 当前阶段

- Stage: S1 Evidence + S4 Drafting
- 当前交付：`KT3_LAYERED_REQUIREMENTS.md` 研究导向重写

## 已完成

- 读取当前 KT3 文档与 METHOD / EXPERIMENT 文档
- 核对帖子级、用户级、社区级相关代码边界
- 收集并核实一批高水平参考文献入口
- 本轮扩展 `KT3_LAYERED_REQUIREMENTS.md`：弱化手工特征/字段清单，改为文献驱动的帖子级、用户级、社区级方法论设计
- 扩展 `plan/evidence-map.md` 至 63 条 evidence-claim 映射，覆盖 harmfulness、stance、fact verification、用户级 harmfulness、社区级 coordinated harm、图表示、证据图和 Agent/RAG
- 更新章节蓝图与证据覆盖审查，明确哪些主张由哪些文献支撑，并标注 2025/2026 前沿文献的使用风险
- 接入 KT3 分层 harmfulness：`risk_service.assess_risk -> assess_layered_harmfulness -> build_report`
- 新增 `kt3_harmfulness` 报告字段，包含 `post_level / user_level / community_level / global_summary / audit / review_queue`
- 新增 `system/backend/app/core/risk/kt3_reviewer.py`，实现 KT3 Agent/RAG 复核任务队列脚手架
- `review_queue` 将 low-confidence/abstain posts、unlinked claims、高风险账户、高风险社区转为 planned-only 的 review items、retrieval tasks、agent tasks 和 counter-narrative inputs
- 新增 `system/backend/app/core/risk/kt3_review_executor.py`，实现 KT3 本地确定性复核执行器
- `review_execution` 基于报告内 evidence corpus 执行 local retrieval、review verdict、agent summary 和 counter-narrative draft，明确不调用外部 LLM/RAG
- 补充服务级测试，确认 `assess_risk` 直接输出 KT3 三层 harmfulness
- 前端风险研判页新增 KT3 分层 harmfulness 展示区，展示 KT3 风险等级、有害账户、有害社区、语义帖子、用户级/社区级表格、top harmful claims、Agent/RAG planned-only 复核队列和本地复核执行结果
- 风险 API 前端参数和后端 schema 同步支持 `event_id`、`post_semantics`、`kt3_harmfulness`
- 增加风险 API 函数级测试，验证 `/risk/assess` 参数传递和 `kt3_harmfulness` 响应保留
- 重新调用独立只读 reviewer 子智能体并采纳建议：任务级 planned-only 边界、`needs_review` 触发规则、前端复核队列展示和测试触发规则断言
- 本轮继续调用两个只读子智能体审查下一步路线；结论一致建议优先实现离线可测的 RAG/review executor，并补验收矩阵
- 本轮继续调用文献研究与图导出验收子智能体，采纳其建议：补充 PromptHate、动态用户表示、GCAN、CompareNet、GET、CACL、RAG-Fusion、ClaimCheck、MIND 等方法迁移文献；修复 `community_targets` schema 契约漂移
- 增强 `kt3_graph_exporter.py`：导出 `target / media` 节点、`post_targets / account_targets / community_targets / post_uses_media / account_shares_object / co_shares_object` 边，支持对象介导协同关系，并记录 `dropped_dangling_edges`
- 增强 `kt3_graph_exporter.py`：新增 `write_kt3_graph_artifact` / `read_kt3_graph_artifact`，支持 JSON artifact 落盘、manifest、consumer 回读和负向 dangling edge 校验
- 增强 `post_semantics.py`：在帖子级聚合输出中保留 `hashtags / media_urls`，为图导出提供真实 shared-object 输入
- 增强 `TestKT3GraphExport`：验证 target/media/shared-object、community_targets、无悬挂边和对象 relation/object_id 保真
- 增强 `kt3_review_executor.py`：新增可选 `evidence_retriever / review_provider` 插拔接口，默认保持本地 deterministic executor；provider 返回结果会被规范化和审计，provider 抛错时回退到本地结果
- 增强 `TestKT3ReviewExecution`：验证默认离线确定性、offline mock provider 成功路径、provider 失败回退路径和 `provider_audit` 边界
- 新增 `system/backend/app/core/risk/kt3_post_gate.py`：实现 KT3 Post Gate evaluation harness，对固定 gold 样例报告 claim linking、stance、harm label、harm type、evidence presence 和 abstain 指标
- 增强 `TestKT3PostGate`：验证 Post Gate 是 evaluation-only、非训练模型，指标分母来自 `aggregation_posts`，失败样本进入 planned-only 复核队列且不执行 live LLM/RAG
- 新增 `system/backend/app/core/risk/kt3_user_gate.py`：实现 KT3 User Gate evaluation harness，对固定账户 gold 样例报告 harmful flag、persistence label、trajectory、role micro-F1、representative evidence 和 runtime needs-review 指标
- 增强 `TestKT3UserGate`：验证 User Gate 是 evaluation-only、非 MIL/Transformer/user encoder，失败账户进入 planned-only 复核队列且不执行 live LLM/RAG
- 新增 `system/backend/app/core/risk/kt3_community_gate.py`：实现 KT3 Community Gate evaluation harness，对固定社区 gold 样例报告 collective harm、amplification label、harm type micro-F1、role micro-F1、claim coverage、key account evidence 和 graph export readiness 指标
- 增强 `TestKT3CommunityGate`：验证 Community Gate 是 evaluation-only、非 HGT/Graph Transformer/TGN，失败社区进入 `CommunityJudge` planned-only 复核队列且不执行 live LLM/RAG
- 更新 `KT3_LAYERED_REQUIREMENTS.md`：新增“从文献到功能闭环的设计映射”，把 HateXplain、Hateful Memes、MOCHEG、FACTIFY3M、FakeSV、用户级 hateful user 研究、coordinated harassment / IO / CIB、MARO/RAMA/DEFAME 等文献映射到 Post/User/Graph/Community/Agent Gate
- 新增 `system/backend/app/core/risk/kt3_gate_suite.py`：实现 KT3 Gate Suite，统一汇总 Post/User/Community Gate 的 executed/skipped 状态、metrics、failed thresholds 与 review items
- 将 `kt3_harmfulness.gate_suite` 接入 `risk_service.assess_risk` 默认报告；默认没有固定 gold 时输出 `executed_gates = 0 / skipped_gates = 3`，明确三层 Gate 未执行而非伪造评测结果
- 增强 `TestKT3GateSuite` 与服务/API 集成测试：验证 suite 是 evaluation-only、非训练模型，缺 gold 时安全 skipped，API 响应保留 gate suite 边界
- 前端风险研判页新增 KT3 Gate Suite 验收汇总区，展示 executed/skipped、overall pass、跳过原因和 evaluation-only 边界
- 本轮调用两个只读子智能体进行独立核查：代码核查结论确认 P0 缺口是 Gate Suite 未接入主链路；文档核查结论建议补“方法选择与替代方案”和能力边界。已采纳并更新 `KT3_LAYERED_REQUIREMENTS.md` 与实现记录。
- 本轮继续调用只读研究子智能体审查“文档过于特征工程”的问题；采纳其建议，将规则、阈值、OCR/ASR、账户统计等表述改写为 weak supervision signal、calibration policy、multimodal evidence source、post-to-user representation 和 graph-native evaluation contract。
- 新增 `system/backend/app/core/risk/kt3_gate_dataset.py`：实现 KT3 Gate Dataset 契约，规范化 `metadata / post_cases / user_gold / community_gold / thresholds / prefer_embeddings`，记录 dataset id、version、source、label policy、control notes、layer coverage、gold counts 与 warning。
- 增强 `kt3_gate_suite.py`：新增 `gate_dataset` 参数和 `evaluate_kt3_gate_suite_from_dataset` wrapper；无 gold/control set 时继续 skipped，显式提供数据集时执行有标注层的 Gate，并在报告中输出 `dataset_contract`。
- 增强 `risk_service.assess_risk`：新增可选 `kt3_gate_dataset` 参数，供后端显式标注数据驱动 Gate Suite 执行；API 默认查询参数不变，避免把复杂 gold/control set 暴露为普通线上请求参数。
- 增强 `TestKT3GateSuite` 与 `TestRiskServiceKT3Integration`：验证 dataset contract 能驱动 Suite 三层执行，服务主链路有 gold 时 `executed_gates = 3 / skipped_gates = 0`，无 gold 时仍安全 skipped；同时验证 boundary 仍是 evaluation harness，不训练模型、不启用在线 LLM/RAG。
- 新增 `KT3GateSuiteRequest` 与 `/risk/kt3/gate-suite` 离线评估 API：从 request body 接收 `kt3_gate_dataset`，内部调用 `assess_risk(..., db=None, kt3_gate_dataset=...)`，返回 `gate_suite`、`dataset_contract`、`kt3_harmfulness` 与 `persistence.persisted = false`，避免 gold/control 评估结果污染默认历史报告。
- 新增 `TestKT3GateDataset`：验证 dataset contract 正常 metadata/counts/thresholds 输出，以及非法输入 warning 行为，确保不从 runtime 或坏输入中伪造 gold。
- 新增 `TestRiskAPIKT3Integration.test_assess_kt3_gate_suite_api_accepts_dataset_body_without_persistence`：验证 `/risk/kt3/gate-suite` 透传 dataset、强制不持久化、保留 Gate Suite 评估响应。
- 新增 `GET /risk/kt3/gate-dataset/contract`：返回 `kt3-gate-dataset-v1` 机器可读契约，包括 required metadata、Post/User/Community layer contracts、默认指标阈值、example skeleton、usage policy 和 leakage policy，供外部评测脚本稳定发现字段与边界。
- 新增 `POST /risk/kt3/gate-dataset/validate`：只校验 `kt3_gate_dataset` 的契约、layer coverage、counts、threshold layers、missing metadata 与 warnings，不运行风险评估、不持久化、不使用 gold 训练或校准模型。
- 新增 KT3 Gate Dataset manifest：`build_kt3_gate_dataset_manifest()` 为离线 Gate Suite 输出 report-safe 可复现审计元数据，包含 dataset/layer/threshold fingerprints、metadata、counts、coverage、threshold layers 和 warning count；明确 `contains_gold_payload = false`，不复制 `post_cases / user_gold / community_gold` 原始标签内容。
- 前端风险研判页新增 KT3 Gate Dataset 契约与离线验收入口：支持加载 contract、填入 example skeleton、粘贴 JSON、调用 validate、调用离线 Gate Suite，并展示 required metadata、layer coverage、counts、warnings、missing metadata、manifest fingerprint 和 `persistence.persisted`。
- 前端 API client 新增 `getKT3GateDatasetContract`、`validateKT3GateDataset`、`assessKT3GateSuite`，使后端 contract/validate/gate-suite 能力在系统 UI 中可见。
- 修正风险页对统一响应包装的读取层级：`assessRisk` 与 `listRiskReports` 直接读取拦截器返回的 `res.data`，避免页面运行评估或历史报告读取时取到错误层级。
- 更新 `KT3_LAYERED_REQUIREMENTS.md`：新增 `weak-supervision-aware`、`evaluation-contract-first` 原则，补充 Gate Dataset 契约章节，并扩充自动事实核查、解释性 fact-checking、RATSD、用户/社区上下文建模、GCN、Snorkel、RAG/ReAct/Multi-Agent Debate 等参考文献。
- 更新 `KT3_IMPLEMENTATION_RECORD.md`：记录 Gate Dataset 契约、服务级 `kt3_gate_dataset` 接入、dataset contract 报告字段和新增验证。
- 更新 `KT3_LAYERED_REQUIREMENTS.md`：新增 current implemented / gold-control evaluation only / future model 三分法，以及无 gold 默认风险研判、有 gold 离线验收两条端到端路径。
- 增强 KT3 Gate Dataset readiness 审计：区分 `valid_for_execution` 与 `formal_acceptance_ready`；只有三层 gold/control 覆盖且声明 control notes、split、leakage policy、threshold policy 时才可作为正式验收 ready；前端同步展示 formal ready/not-ready 与 readiness warnings。

## 待完成

- 后续可进一步补充逐篇 PDF 级精读、中文领域文献、项目域内标注策略和实验设计
- 代码侧仍需继续实现帖子级 teacher-student 蒸馏/微调、训练式用户级 encoder、社区级异构图模型、真实在线 Agent/RAG 复核执行、真实项目 gold/control set 接入和真实数据端到端实验

### Next Gate

- `Post Gate`：已实现固定样例 evaluation harness，可验证 claim linking、stance、harm label、harm type、evidence presence 与 abstain，并将失败样本路由到 planned-only 复核队列；下一步是接入公开/项目标注集和 teacher-student 蒸馏流程。
- `User Gate`：已实现固定账户样例 evaluation harness，可验证 harmful flag、persistence、role、trajectory、代表性证据和 needs-review，并将失败账户路由到 planned-only 复核队列；下一步是接入真实账户级弱/强标注样本集。
- `Graph Export Gate`：已导出 account-post-claim-community-target-media 异构图样例，验证 target/media/shared-object、community_targets、对象介导关系、无悬挂边和 `dropped_dangling_edges` 审计；已补 artifact 落盘、consumer smoke test 和坏 artifact 负向校验。该 Gate 只证明导出契约可读可审计，不代表图模型已实现。
- `Community Gate`：已实现固定社区样例 evaluation harness，可验证 collective harm、coordinated amplification、harm type、subgroup role、claim coverage、key account evidence 和 graph export readiness，并将失败社区路由到 `CommunityJudge` planned-only 复核队列；下一步是接入真实社区级 gold/control set。
- `Gate Suite`：已实现三层 Gate 统一汇总并接入默认风险报告；无 gold 时明确 skipped，不冒充已完成真实评测；已新增 `kt3_gate_dataset` 契约和 `/risk/kt3/gate-suite` 离线评估 API，显式提供 gold/control set 时可执行三层 Gate 且默认不持久化。下一步是接入真实项目 gold/control set，让 suite 在真实事件上执行可复现验收。
- `Community Model Gate`：在 Graph Export Gate 之后训练或评估 HGT / Graph Transformer / TGN，并能生成社区级 explanation。
- `Agent/RAG Gate`：在保留本地 deterministic executor 的同时，已预留可插拔 retriever / review provider future hook，并验证 offline mock provider 与失败回退；当前不能声称真实在线 provider 已接入。后续若接入在线 provider，其失败仍不能中断主报告。
- `Evidence Gate`：每个新增能力都必须在 `KT3_IMPLEMENTATION_RECORD.md` 中记录“改了什么 / 验证了什么 / 还差什么”。

## 当前增量：帖子级多模态 -> 用户级 MIL -> 本地多智能体

- 帖子级：`post_semantics.py` 新增 `multimodal_detection`，把 text、OCR、ASR、caption/media、emoji/hashtag 作为证据通道做 modality-aware late fusion；输出 channel results、evidence modalities、claim grounding、cross-modal conflict 和 capability boundary。参考 RGCL、MOCHEG、FACTIFY3M、FakeSV 的方法思想，但当前仍不是已训练图像/视频多模态模型。
- 用户级：新增 `kt3_user_mil.py`，把账户建模为 post bag，按 Attention-MIL 思路输出 `mil_harm_score`、`attention_posts`、harm type distribution、stance distribution 和 context；已接入 `risk_service` 的 `kt3_harmfulness.user_mil`。当前是 deterministic inference scaffold，不是训练式 MIL/temporal Transformer/user encoder。
- 多智能体：新增 `kt3_multi_agent.py`，执行 `HarmReviewAgent`、`StanceClaimAgent`、`EvidenceRetrievalAgent`、`UserMILAgent`、`CommunityJudgeAgent`、`CounterNarrativeAgent` 六个本地 agent，共享 blackboard，输出 `agent_results` 和 `final_decision`；已接入 `kt3_harmfulness.multi_agent_review`。当前是真实本地多智能体执行，不只是 planned queue；但默认仍不调用在线 LLM、外部搜索或向量库 RAG。
- 服务链路：`risk_service.assess_risk()` 当前顺序为 post semantics -> layered harmfulness -> user MIL -> graph export -> review queue -> local review execution -> multi-agent review -> gate suite，报告字段保持向后兼容。
- 文档：`KT3_LAYERED_REQUIREMENTS.md` 新增本轮方法闭环章节，`KT3_IMPLEMENTATION_RECORD.md` 新增实现记录，明确每一层的高水平文献、方法迁移、当前实现和目标差距。
- 验证：新增快速测试通过，命令为 `python -m pytest tests/test_risk.py::TestPostSemantics::test_assess_post_semantics tests/test_risk.py::TestKT3UserMIL tests/test_risk.py::TestKT3MultiAgentRuntime tests/test_risk.py::TestRiskServiceKT3Integration::test_assess_risk_includes_kt3_harmfulness -q`，结果 `5 passed`。

## 当前增量：推进到可训练方法与数据集缺口

- 新增 `aris/tech-03-risk/KT3_TRAINABLE_METHOD_AND_DATASETS.md`，把 KT3 从当前 runtime scaffold 推进到可训练方法的路线拆成帖子级 teacher-student 多模态模型、用户级 trainable MIL / temporal encoder、社区级异构图模型和多智能体 teacher/reviewer/retriever/verifier 闭环。
- 明确帖子级训练任务需要 harm label/type、target、claim link、stance、evidence/rationale、abstain/calibration；用户级训练任务需要 user harmfulness、persistence、harm mixture、role、representative posts；社区级训练任务需要 collective harm、amplification、subgroup role、target/claim concentration 和 evidence subgraph。
- 汇总数据集支撑矩阵：HateXplain、Jigsaw Toxicity、Hateful Memes、MMHS150K、MAMI、MultiOFF、RumourEval/PHEME、FEVER/HoVer/AVeriTeC、MOCHEG、FACTIFY/FACTIFY3M、FakeSV、Fakeddit、MuMiN、MCFEND、IOHunter、Russian Troll Tweets、Twitter IO、CooRTweet、MediaCrawler 和项目域 KT3 gold/control set。
- 本地数据审计结论：`G:\CISCN\dataset\PHEME`、`Twitter15_16_dataset`、`mcfend`、`iohunter`、`russian-troll-tweets`、`twitter_io`，以及仓库内 `CooRTweet-master`、`MediaCrawler-main\data`、`MediaCrawler-main\data_runs` 已存在；这些可支撑传播/协同/项目域适配和弱监督构建，但不足以直接训练完整 KT3 harmfulness。
- 本地主要缺口：HateXplain、Jigsaw Toxicity、Hateful Memes、MMHS150K、MAMI、MultiOFF、MOCHEG、FACTIFY/FACTIFY3M、FakeSV、MuMiN、完整 RumourEval/FEVER/AVeriTeC、用户级 harmfulness gold、项目域三层 `kt3_project_gold/control set`、媒体二进制/OCR/ASR 对齐文件和 RAG 证据库。
- 更新 `KT3_LAYERED_REQUIREMENTS.md`：新增可训练方法与数据集缺口入口，明确当前不能声称已完成训练式帖子级多模态 harmfulness、用户级 MIL 或社区级 collective harm 模型。

## 当前增量：帖子级统一模型与验证 gate

- 新增 `aris/tech-03-risk/KT3_POST_UNIFIED_MODEL_AND_VALIDATION.md`，将帖子级目标模型命名为 `MV-PostGuard`，形式化为 `tweet / meme / img / video` 四类视图检测器、claim/evidence 条件模块和多数投票/加权 late fusion 裁决层。
- 帖子级输出契约固定为 `final_harmfulness`、`harm_score`、`harm_types`、`primary_claim`、`stance`、`view_results`、`fusion_policy`、`conflict` 和 `review_reason`，用于后续训练、评测和复核。
- 新增只读脚本 `system/backend/scripts/audit_kt3_post_datasets.py`，审计本地帖子级 benchmark 是否具备 split、label、媒体对齐和最小验证条件；默认输出到 `G:\CISCN\.tmp\kt3_post_dataset_audit.json`。
- 已运行数据审计：15 个 benchmark 中 `PHEME`、`Twitter15_16_dataset`、`mcfend` 为 ready，`MultiOFF` 为 partial，11 个关键 benchmark 缺失。`MultiOFF` 当前有 743 条 split 样本，但 split CSV 中有 3 条图片引用未在 `Labelled Images` 中找到，代表性缺失文件为 `80NRcEf.png`。
- 重要边界：当前只完成帖子级统一模型设计、验证协议和本地数据 readiness gate；尚未完成 `kt3_post_case` 统一转换脚本、模型训练、跨 benchmark 全量评测和 ablation，因此不能声称“全量验证完成”。

## 当前增量：kt3-post-case 统一转换

- 新增 `system/backend/scripts/build_kt3_post_cases.py`，将本地帖子级数据转换为统一 `kt3-post-case-v1` JSONL，字段包括 `case_id / dataset / split / source_id / text / labels / views / claim_context / metadata`。
- 已完成 smoke 转换：`--max-per-dataset 5` 输出 20 条样例到 `G:\CISCN\.tmp\kt3_post_cases_smoke`，4 个数据集均可进入统一 schema；`Twitter15_16_dataset` 因本地缺 `source_tweets.txt` 被标为 partial。
- 已完成当前本地全量转换，输出到 `G:\CISCN\.tmp\kt3_post_cases_full`，总计 `33450` 条 case：`MultiOFF` 743 条、`PHEME` 6425 条、`mcfend` 28770 条、`Twitter15_16_dataset` 3512 条。
- 转换 manifest 显示：`PHEME` 与 `mcfend` 为 converted；`MultiOFF` 为 partial，因为 3 条图片引用缺失；`Twitter15_16_dataset` 为 partial，因为只有 label/tree，没有 source tweet 正文，不能直接用于内容检测训练。
- 修复转换器对 PHEME macOS `._*.json` 资源叉文件的误读问题；重跑后 `PHEME` 的 `tweet` view 可用计数为 6425/6425。
- 重要边界：统一转换已经完成当前本地可用数据的 schema normalization，但尚未训练 `MV-PostGuard`，也尚未输出跨 benchmark 模型指标。

## 当前增量：text-only baseline 评测管线

- 新增 `system/backend/scripts/run_kt3_post_text_baseline.py`，在 `kt3-post-case-v1` 上训练并评测 `TF-IDF(char n-gram) + Logistic Regression` text-only baseline。
- 已运行 baseline：输入 `G:\CISCN\.tmp\kt3_post_cases_full`，输出 `G:\CISCN\.tmp\kt3_post_text_baseline\report.json` 和每个数据集的 predictions JSONL。
- 当前结果：`MultiOFF` official train+validation -> test，Accuracy 0.644295，Macro-F1 0.619550；`PHEME` event holdout，Accuracy 0.751303，Macro-F1 0.591633；`mcfend` stratified random 80/20，Accuracy 0.864442，Macro-F1 0.820079；三者 mean macro-F1 0.677087。
- 结果解释：这是 `D_tweet` / text-only 对照实验，证明统一 schema 上的训练和评测管线可跑通；它不使用 image/video encoder、claim retrieval 或多视图 fusion，不能声明为完整 `MV-PostGuard` 全量验证。
- 下一步应接入冻结 CLIP/BLIP-2 图像编码器，先在 MultiOFF 上跑 `text-only / image-only / weighted fusion` ablation，再补 Hateful Memes/MAMI/MOCHEG/FakeSV 等缺失 benchmark。

## 当前增量：帖子级四视图 detect 与投票/融合形式化

- 新增根目录 `CONTEXT.md`，统一 KT3 术语：Post View、View Detector、View Abstention、Majority Vote、View Fusion、Harmfulness Judgment。
- 增强 `system/backend/app/core/risk/post_semantics.py`：在每条帖子输出中新增 `post_view_detection`，固定包含 `tweet / meme / img / video` 四类视图的 `view_results`，以及 `majority_vote`、`weighted_fusion`、`fusion_policy`、`final_harmfulness`、`conflict` 和 `review_reason`。
- 形式化实现口径：`D_tweet / D_meme / D_img / D_video` 分别 detect，缺少可解码图像/视频证据时视图必须 `abstain`，多数投票只统计 confident non-abstained views；加权融合按 view prior weight 与 confidence 组合 score。
- 本轮收紧边界：`img/video` 的 `available=true` 必须来自 OCR/ASR/caption 等可解码证据，单独的图片/视频 URL 不再被视为已理解内容；`weighted_fusion` 现在与多数投票一致，排除 `abstain=true` 的视图，避免把 tweet 正文重复计入 video/img 判断。
- 更新 `aris/tech-03-risk/KT3_POST_UNIFIED_MODEL_AND_VALIDATION.md`：新增“当前形式化：四视图 detect -> vote/fusion -> post judgment”，明确输入输出、投票公式、融合公式、当前代码映射和能力边界。
- 重要边界：该增量完成的是运行时四视图 scaffold 和输出契约，不代表 `D_img / D_video` 已接入真实图像/视频 encoder，也不代表训练式 `MV-PostGuard` 已完成。

## 当前增量：MultiOFF 多视图 ablation 验证

- 新增 `system/backend/scripts/run_kt3_multioff_multiview_ablation.py`，在 `kt3-post-case-v1` 的 MultiOFF official split 上运行 `text_only / image_only / late_fusion` ablation。
- 方法：`text_only` 使用 TF-IDF char n-gram + Logistic Regression；`image_only` 使用冻结 `openai/clip-vit-base-patch32` 图像 encoder + Logistic Regression；`late_fusion` 在 validation split 上网格搜索 text/image harmful probability 权重，并在 test split 上评估。
- 复现命令：`python scripts/run_kt3_multioff_multiview_ablation.py --output-dir G:\CISCN\.tmp\kt3_multioff_multiview_ablation_hf_safe --batch-size 16 --hf-endpoint https://huggingface.co`。
- 当前结果：`text_only` Test Accuracy 0.597315 / Macro-F1 0.573799；`image_only` Test Accuracy 0.621622 / Macro-F1 0.617147；`late_fusion` Test Accuracy 0.628378 / Macro-F1 0.620743，最优权重 text 0.2 / image 0.8。
- 输出：`G:\CISCN\.tmp\kt3_multioff_multiview_ablation_hf_safe\report.json`，并生成 text/image/fusion predictions 与 `clip_image_embeddings_24a2abc8bb876cdc.npz`。
- 修正脚本加载 CLIP 时强制 `use_safetensors=True`，避免本地 `torch<2.6` 对 PyTorch `.bin` 权重的安全限制；模型缓存放在 `G:\CISCN\.cache\huggingface`，未在 C 盘创建临时目录。
- 文档更新：`KT3_POST_UNIFIED_MODEL_AND_VALIDATION.md` 新增 MultiOFF 多视图验证结果和 MultiOFF/Hateful Memes/MAMI/CLIP 文献链接；`KT3_TRAINABLE_METHOD_AND_DATASETS.md` 新增当前可训练验证入口。
- 重要边界：这是第一个公开图文 benchmark 上的多视图验证，不是全量验证；仍缺 Hateful Memes、MAMI、MMHS150K、MOCHEG、FACTIFY3M、FakeSV 等 P0 数据集和 video / claim-conditioned 视图验证。

## 当前增量：跨本地数据集 Post Multiview Suite

- 新增 `system/backend/scripts/run_kt3_post_multiview_ablation.py`，将本地 `kt3-post-case-v1` 数据统一评测为一个 suite，当前覆盖 `MultiOFF / PHEME / mcfend`。
- 运行命令：`python scripts/run_kt3_post_multiview_ablation.py --datasets MultiOFF PHEME mcfend --output-dir G:\CISCN\.tmp\kt3_post_multiview_ablation_full --batch-size 16 --hf-endpoint https://huggingface.co`。
- 输出报告：`G:\CISCN\.tmp\kt3_post_multiview_ablation_full\report.json`。
- 当前 suite 结果：MultiOFF 最优 `late_fusion` Macro-F1 0.620743；PHEME event-holdout `text_only` Macro-F1 0.591510；mcfend stratified 70/10/20 `text_only` Macro-F1 0.817638。
- 数据边界：MultiOFF 有 740/743 条 aligned local image，可运行 CLIP image-only 和 late fusion；PHEME 当前只有 text/claim；mcfend 本地转换当前来自 `news.csv`，没有 aligned image/video，虽有 `social_context.csv` 但尚未转入 post-case，因此 image/fusion/video 在 suite 中明确 skipped。
- 文档更新：`KT3_POST_UNIFIED_MODEL_AND_VALIDATION.md` 新增跨本地数据集 suite 章节；`KT3_TRAINABLE_METHOD_AND_DATASETS.md` 新增 suite 入口和 mcfend 本地能力边界。
- 重要边界：suite 是全量验证 runner 的雏形，不等于完整全量验证；仍需补齐 P0 benchmark、video 视图、claim-evidence 视图和 mcfend social/media 转换。

## 当前增量：HateXplain 纳入本地 suite 与文献闭环

- 已获取 HateXplain 官方仓库到 `G:\CISCN\dataset\kt3_public\HateXplain`，并在 `audit_kt3_post_datasets.py` 中加入 HateXplain 审计逻辑。
- 已将 HateXplain 转换为 `G:\CISCN\.tmp\kt3_post_cases_full\HateXplain.jsonl`，共 20148 条 case；完整 manifest 当前总计 53598 条 case。
- 已运行 4 数据集 suite：`G:\CISCN\.tmp\kt3_post_multiview_ablation_with_hatexplain\report.json`。当前结果为 MultiOFF late-fusion Macro-F1 0.620743，HateXplain text-only Macro-F1 0.766130，PHEME text-only Macro-F1 0.591510，mcfend text-only Macro-F1 0.817638。
- 修正 `audit_kt3_post_datasets.py` 的 `ready_for_full_post_validation` 汇总，使 HateXplain 出现在 ready 可验证集合中。
- 更新 `KT3_POST_UNIFIED_MODEL_AND_VALIDATION.md` 和 `KT3_TRAINABLE_METHOD_AND_DATASETS.md`：补充 HateXplain 当前状态、4 数据集 suite 结果、MARO/CLIP/BLIP-2/MultiOFF/MAMI 等高水平方法映射，以及 Agent 只做 reviewer/rule optimizer、不替代底层 view detector 的定位。
- 重要边界：HateXplain 当前只完成 text harmfulness 评测，target/rationale head 尚未训练；suite 仍缺 Hateful Memes、MAMI、MMHS150K、MOCHEG、FACTIFY3M、FakeSV、RumourEval 2019、Jigsaw 等 P0 数据集，不能声明全量验证完成。

## 当前增量：RumourEval 2019 与 MOCHEG 访问边界核验

- 已 clone RumourEval 2019 baseline repo 到 `G:\CISCN\dataset\kt3_public\RumourEval2019`。README 显示原始数据需从 CodaLab task 下载；仓库内 `answer.json` / `stance_answer_dev.json` 是 baseline/submission 结果，不是可用于训练的原始帖子文本与 gold。
- 已 clone MOCHEG official implementation 到 `G:\CISCN\dataset\kt3_public\Mocheg`。README 显示 MOCHEG v1 数据需通过 Google Form 获取；当前仓库包含 official code、dataset builder 和少量 example，不包含完整 `Corpus2.csv / train / dev / test`。
- 更新 `kt3_post_benchmarks.json`：将 RumourEval 2019 从 `public_github` 改为 `codalab_terms_required`，将 MOCHEG 从 `public_github` 改为 `google_form_required`，并补充 required files 与 license/access note。
- 重跑 `audit_kt3_post_datasets.py` 后，状态变为 ready 4 个、partial 1 个、present_unverified 2 个（RumourEval 2019、MOCHEG）、missing 8 个；这比之前“public clone 即可”的口径更准确。
- 重要边界：本轮没有把 baseline prediction 文件伪装为训练数据，也没有把 MOCHEG implementation 仓库当作完整数据集；这两个 P0 仍需获取原始数据后才能进入 converter 和 suite。

## 当前增量：FakeSV 短视频 metadata/text proxy 接入

- 已 clone FakeSV official repo 到 `G:\CISCN\dataset\kt3_public\FakeSV`。公开仓库包含 `dataset\data.json`、official temporal/event split 和 video id/keywords/label；README 说明 raw videos 需签署协议，预提取 VGG19/C3D/VGGish features 在 HuggingFace 外部资源。
- 新增 `build_kt3_post_cases.py::convert_fakesv`，将 FakeSV 转为 `kt3-post-case-v1`。主 manifest 更新为 6 个数据集、59093 条 case，其中 FakeSV 5495 条，official temporal split 为 train 4002 / validation 773 / test 720。
- 新增 `audit_kt3_post_datasets.py::audit_fakesv`，审计 FakeSV 的公开 metadata、split 与媒体边界；当前状态为 partial，不把它标为完整 raw-video ready。
- 更新 `run_kt3_post_multiview_ablation.py`，支持 FakeSV official temporal split，并在 report 能力边界中声明 FakeSV 当前只是 short-video metadata/text proxy，不是 raw video encoder。
- 已运行 5 数据集 suite：`G:\CISCN\.tmp\kt3_post_multiview_ablation_with_fakesv\report.json`。当前结果为 MultiOFF late-fusion Macro-F1 0.620743，HateXplain text-only 0.766130，PHEME text-only 0.591510，mcfend text-only 0.817638，FakeSV metadata/text proxy 0.772814。
- 重要边界：FakeSV 已补入短视频数据集的公开代理验证，但还未完成 keyframe/OCR/ASR/audio/social-context 多模态 video view；仍需 raw videos 或预提取视听特征后才能声明真正 `D_video` 验证完成。

## 当前增量：MMHS150K 获取链路核验

- 尝试 clone registry 中原 `https://github.com/Hironsan/MMHS150K`，GitHub 返回 repository not found，且未在 `G:\CISCN\dataset\kt3_public\MMHS150K` 留下可用目录。
- 本机没有 Kaggle 凭据：`%USERPROFILE%\.kaggle\kaggle.json` 不存在，因此无法自动下载 Kaggle 镜像。
- 更新 `kt3_post_benchmarks.json`：将 MMHS150K 的 dataset URL 改为 [Kaggle mirror](https://www.kaggle.com/datasets/victorcallejasf/multimodal-hate-speech)，repository/project URL 改为 [作者项目页](https://gombru.github.io/2019/10/09/MMHS/)，access 改为 `kaggle_terms_required`。
- 重跑审计后，MMHS150K 仍为 missing，但 acquisition action 已正确归入 `accept_terms_then_download`，不再误导为 public GitHub clone。
- 重要边界：MMHS150K 仍是图文 hate speech 的 P0/P1 关键数据，但需要 Kaggle token 与数据条款后才能进入 converter/suite。

## 当前增量：FACTIFY3M 获取链路核验

- 尝试 clone registry 中原 `https://github.com/ankuranii/acl2023-factify3m`，GitHub 返回 repository not found，未在 `G:\CISCN\dataset\kt3_public\FACTIFY3M` 留下可用目录。
- 已 clone older Factify baseline repo 到 `G:\CISCN\dataset\kt3_public\Factify`，但 README/文件结构显示该仓库只含 baseline notebook、代码和数据说明，不包含 FACTIFY/FACTIFY3M 的 train/validation/test 数据文件。
- 更新 `kt3_post_benchmarks.json`：将 FACTIFY3M 的 dataset URL 改为 EMNLP paper，repository 清空，access 改为 `manual_contact_required`，并说明原 GitHub 不可访问、需通过论文/作者或官方 release 获取数据。
- 更新 `audit_kt3_post_datasets.py`：支持 `manual_contact_required` acquisition action。重跑审计后，FACTIFY3M 仍为 missing，但获取动作从 public clone 改为 manual contact。
- 重要边界：FACTIFY3M 是 claim-evidence/5W QA 的关键高水平数据集，但当前没有可用官方数据包，不能进入 converter/suite。

## 当前增量：P0 benchmark registry 与 readiness/acquisition 审计

- 新增 `system/backend/app/core/risk/config/kt3_post_benchmarks.json`，将 KT3 帖子级 benchmark 机器可读化：记录 priority、task、views、paper URL、dataset URL、repository URL、access policy、local aliases、required files、media requirement 和 validation role；当前覆盖 15 个 benchmark，包括 Twitter15/16。
- 增强 `system/backend/scripts/audit_kt3_post_datasets.py`：新增 `--registry` 参数，输出 schema 升级为 `kt3-post-dataset-audit-v2`，并把本地 readiness 与 registry 中的官方链接/获取方式合并。
- 已运行 v2 审计：`python scripts/audit_kt3_post_datasets.py --dataset-root G:\CISCN\dataset --output G:\CISCN\.tmp\kt3_post_dataset_audit_v2.json`。
- 当前审计结论：15 个 benchmark 中 ready 3 个（PHEME、Twitter15_16_dataset、mcfend）、partial 1 个（MultiOFF）、missing 11 个；P0 ready/partial 为 MultiOFF、PHEME、mcfend。
- P0 缺口：FACTIFY3M、FakeSV、HateXplain、Hateful Memes、Jigsaw Toxicity、MAMI、MMHS150K、MOCHEG、RumourEval 2019。
- 获取动作分类：HateXplain/MMHS150K/RumourEval2019/MOCHEG/FACTIFY3M/FakeSV 可 public clone/download；Jigsaw Toxicity/MAMI 需要接受 Kaggle/CodaLab 条款；Hateful Memes 需要申请或接受 Meta/DrivenData 访问条款。
- 文档更新：`KT3_POST_UNIFIED_MODEL_AND_VALIDATION.md` 第 7 节升级为 registry-driven readiness 审计；`KT3_TRAINABLE_METHOD_AND_DATASETS.md` 标注 registry/audit 是当前权威入口。
- 重要边界：审计只证明文件是否存在和结构是否可用，不代表模型已训练或 benchmark 已完成评测。

### Capability-use audit

- Required skills: `using-research-writing`, `paper-orchestration`, `literature-review`, `evidence-driven-writing`, `writing-core`, `verification`
- Skills actually used: `using-research-writing`, `paper-orchestration`, `literature-review`, `evidence-driven-writing`, `writing-core`, `verification`
- Inputs consumed: KT3 现有文档、相关代码、Mannocci 综述、ACL/ACM/AAAI/arXiv 论文入口
- Inputs not used and why: 暂未逐篇下载全部 PDF；当前修订以标题、摘要、摘要级结论与已核验元数据为主
- Artifacts produced: `plan/` 基础工件、证据图、任务包、段落蓝图
- Verification run: `python -m pytest tests/test_risk.py -q` 通过，54 passed；`python -m compileall app/core/risk app/services/risk_service.py app/schemas/risk.py app/api/v1/risk.py tests/test_risk.py` 通过；`npx vue-tsc -b --pretty false` 通过；`npm run build` 通过，仅有 Vite 大 chunk 警告；构建产物 `system/frontend/dist` 已清理
- Remaining risk: 个别 2025-2026 前沿论文仍以摘要级信息为主，文中已将其定位为前沿参考或方法启发，未把其写成已被本项目完整复现的既成事实；当前主干仍未完成训练式帖子级 teacher-student / 用户级 / 社区级 harmfulness 模型，也未接入真实在线 LLM、外部搜索或向量数据库 RAG 执行；Post/User/Community Gate、Gate Dataset 与 Gate Suite 只证明显式 gold/control set 可驱动离线评测、统一汇总和失败样本回流，不代表帖子级多模态模型、用户级 encoder 或社区级图模型已训练完成；默认 `gate_suite` 无 gold 时只输出 skipped report，不代表真实事件评测已完成；当前 provider hook 只证明接口可插拔、mock 可测和失败可回退，不代表在线多智能体/RAG 闭环已完成

## 当前增量：帖子级四视角 detect 与多数投票/融合形式化收紧

- 新增 `aris/tech-03-risk/KT3_POST_VIEW_FORMALIZATION.md`，把单条 post 形式化为 `tweet / meme / img / video` 四个 Post View，定义 `D_tweet / D_meme / D_img / D_video` 的输入、输出、available、abstain、Effective View、多数投票、加权 late fusion、最终裁决与复核触发条件。
- 同步收紧 `KT3_POST_UNIFIED_MODEL_AND_VALIDATION.md` 第 3.4 节：多数投票和训练式 late fusion 都显式使用 `I_v = 1[available and not abstain]`，避免旧公式被误读为会融合缺失媒体视图。
- 收紧 `system/backend/app/core/risk/post_semantics.py` 的媒体视角边界：`meme / img / video` 必须有 OCR、ASR、caption、alt/frame/context 等可解码媒体证据才可参与投票/融合；单独的图片或视频 URL 不再允许复用 tweet 文本形成额外媒体票。
- `majority_vote`、`weighted_fusion`、`harm type aggregation` 和跨视角冲突检测均以 Effective View 为准，避免 unavailable/abstained view 对最终 judgment 产生影子贡献。
- 新增/扩展回归测试，验证 `meme/img` URL-only 时输出 `media_without_decodable_content` 并被排除出 weighted contributors，同时直接校验 `majority_vote`、`weighted_fusion` 和最终 `fusion_policy` 均只消费 Effective View。
- 能力边界保持不变：当前完成的是可审计 runtime scaffold 与形式化接口，不代表真实图像/视频 encoder、训练式 view detector 或完整 `MV-PostGuard` 已完成。

## 当前增量：full-registry suite 视图覆盖 gate

- 增强 `system/backend/scripts/run_kt3_post_multiview_ablation.py`：新增 `EXPECTED_DATASET_VIEWS` 与 `validation_coverage`，每个 dataset 报告期望视图、text/image/video/claim-evidence 是否验证、majority/weighted/learned fusion 是否执行，以及 `missing_requirements`。
- 增强 `system/backend/scripts/summarize_kt3_full_validation.py`：full-validation gate 不再只看 ready/converted/evaluated/macro-F1，还要求 `full_expected_view_coverage=true`；text-only-for-multimodal、metadata-proxy-only、claim-proxy-only 都不能通过 gate。
- 新增 `TestKT3PostValidationScripts`，验证 suite coverage matrix 与 strict gate 的行为，防止未来把 FakeSV metadata/text proxy 或 Hateful Memes text-only 指标误判为完整多视图验证。
- 重跑 full-registry suite 到 `G:\CISCN\.tmp\kt3_post_multiview_ablation_full_registry\report.json`：evaluated datasets 为 MultiOFF、HateXplain、PHEME、FakeSV、mcfend；full view covered datasets 为 MultiOFF、HateXplain、mcfend。
- 重跑 strict full-validation gate 到 `G:\CISCN\.tmp\kt3_full_validation_gate_report.json`：`overall_pass=false`，P0 passed 只有 HateXplain 与 mcfend；MultiOFF 因 partial 不通过，PHEME 缺 claim/evidence view，FakeSV 缺 true video view，其余 P0 多为 missing/present_unverified。
- 历史状态说明：该段记录的是 C3D baseline 接入前的 gate 结果；最新 FakeSV 状态见后文“FakeSV C3D 预提取视频特征 baseline”。

## 当前增量：PHEME claim-context view baseline

- 增强 `run_kt3_post_multiview_ablation.py`：新增 `claim_context_text`、`run_claim_context_experiment` 与 `claim_context_late_fusion`，把 PHEME annotation 中的 claim category 与 evidence link metadata 作为独立 claim-context view baseline 评测。
- 收紧 coverage 语义：`claim` 与 `evidence` 分开判定；PHEME 只要求 `tweet + claim`，因此 claim-context metadata baseline 可满足 PHEME view coverage；MOCHEG/FACTIFY3M 仍要求 evidence view，不能被 claim metadata 替代。
- 重跑 full-registry suite 后，PHEME 的 full expected view coverage 变为 true；FakeSV 仍因 `true_video_view_not_evaluated` 失败。
- 重跑 strict full-validation gate 后，P0 passed 从 2 个增加到 3 个：HateXplain、PHEME、mcfend；`overall_pass=false`，因为 MultiOFF partial、FakeSV true video 缺失、Hateful Memes/MAMI/MMHS150K/MOCHEG/FACTIFY3M/RumourEval/Jigsaw 等数据仍未可评估。
- 历史状态说明：该段记录的是 C3D baseline 接入前的 gate 结果；最新 FakeSV 状态见后文“FakeSV C3D 预提取视频特征 baseline”。

## 当前增量：FakeSV C3D 预提取视频特征 baseline

- 增强 `system/backend/scripts/run_kt3_post_multiview_ablation.py`：新增 `--fakesv-c3d-zip`，在 FakeSV 上读取 `G:\CISCN\dataset\kt3_public\FakeSV\features\c3d.zip`，对 `c3d/<video_id>.hdf5` 中的 `c3d_features` 做 temporal mean pooling + L2 normalization，并训练 Logistic Regression `video_feature_only`。
- 新增 FakeSV `video_text_majority_vote` 与 `video_text_late_fusion`：只在 C3D 特征覆盖 official temporal train/validation/test 时执行；coverage 中区分 `video_metadata_proxy_only=false` 与 `preextracted_video_feature_baseline=true`，明确这不是 raw-video 端到端 encoder。
- 增强 `system/backend/scripts/audit_kt3_post_datasets.py`：审计 `features/c3d.zip`，统计 C3D feature file count、split coverage 和 missing_by_split；当前 C3D 覆盖 train 4002、validation 773、test 720，缺失为 0，因此 FakeSV audit status 变为 `ready`。
- 重跑 full-registry suite 到 `G:\CISCN\.tmp\kt3_post_multiview_ablation_full_registry\report.json`：FakeSV `video_feature_only` Test Macro-F1 = 0.604837，`text + C3D late_fusion` Test Macro-F1 = 0.783923，full expected view coverage = true。
- 重跑 strict full-validation gate 到 `G:\CISCN\.tmp\kt3_full_validation_gate_report.json`：P0 passed 变为 FakeSV、HateXplain、PHEME、mcfend；`overall_pass=false`，剩余失败为 FACTIFY3M、Hateful Memes、Jigsaw Toxicity、MAMI、MMHS150K、MOCHEG、MultiOFF、RumourEval 2019。
- 验证：`python -m py_compile scripts\run_kt3_post_multiview_ablation.py scripts\audit_kt3_post_datasets.py` 通过；`python -m pytest tests/test_risk.py -q` 通过，65 passed。能力边界：C3D 是 public pre-extracted video feature baseline，不是 raw video、ASR/OCR/audio/social-context 完整模型。

## 当前增量：全量验证数据获取与 readiness 阻断清单

- 新增 `aris/tech-03-risk/KT3_FULL_VALIDATION_DATA_ACQUISITION.md`，系统记录 KT3 帖子级 full validation 所需 P0/P1 数据集、论文链接、数据/仓库链接、本地状态、required files 和下一步 acquisition action。
- 更新 `system/backend/app/core/risk/config/kt3_post_benchmarks.json` 中 MAMI 的状态口径：官方 GitHub 已 clone 到 `G:\CISCN\dataset\kt3_public\MAMI`，但 README 明确数据需表单申请；registry 现记录 data request form、official GitHub、required files（`TRAINING`, `train.csv`, `test.csv`, `ref`）和“本地代码 clone 不等于 full validation ready”的 license note。
- 增强 `system/backend/scripts/audit_kt3_post_datasets.py`：`present_unverified` 时会根据 access policy 输出更准确 acquisition action；summary 新增 `p0_ready`、`p0_partial`、`p0_present_unverified`、`p0_not_ready_for_full_validation` 和 `p0_acquisition_blockers`。
- 重跑审计输出 `G:\CISCN\.tmp\kt3_post_dataset_audit_v2.json`：P0 ready 只有 HateXplain、PHEME、mcfend；P0 partial 为 FakeSV、MultiOFF；P0 present_unverified 为 MAMI、MOCHEG、RumourEval 2019；P0 missing 为 FACTIFY3M、Hateful Memes、Jigsaw Toxicity、MMHS150K。
- 当前结论进一步收紧：full validation runner 已有雏形，但 full validation 尚未完成，主要阻断来自 gated datasets、缺失媒体/视频特征、claim-evidence 数据未到位，以及多个 benchmark 尚未转为 `kt3-post-case-v1`。

## 当前增量：full-registry converter 与 suite 覆盖

- 扩展 `system/backend/scripts/build_kt3_post_cases.py` 默认数据集列表到完整 15 个 benchmark registry，不再只转换已可用的 6 个数据集。
- 新增 schema-ready converters：`Jigsaw Toxicity`、`Hateful Memes`、`MAMI`、`MMHS150K`、`Fakeddit` 在数据到位时可读取常见 CSV/TSV/JSONL schema；数据未到位时输出明确 missing required files，不生成伪样本。
- 新增 gated/complex dataset gates：`RumourEval 2019`、`MOCHEG`、`FACTIFY3M`、`MuMiN` 当前先严格报告 required files / acquisition note，避免把 baseline repo 或 example 文件误转为训练数据。
- 扩展 `system/backend/scripts/run_kt3_post_multiview_ablation.py` 默认覆盖完整 15 个 benchmark；缺少 case JSONL 的数据集会进入 report 的 skipped_datasets，而不是从验证报告中静默消失。
- 重建 `G:\CISCN\.tmp\kt3_post_cases_full\manifest.json`：覆盖 15 个 benchmark、59093 条 case；FakeSV、HateXplain、PHEME、mcfend converted，MultiOFF、Twitter15/16 partial，其余 9 个 gated/missing 数据集被明确标记 missing。
- 运行 full-registry suite 输出 `G:\CISCN\.tmp\kt3_post_multiview_ablation_full_registry\report.json`：15 个 benchmark 均进入报告，当前 evaluated datasets 为 MultiOFF、HateXplain、PHEME、FakeSV、mcfend；其余数据集显式 skipped 并记录原因。

## 当前增量：MultiOFF learned fusion head

- 增强 `system/backend/scripts/run_kt3_multioff_multiview_ablation.py`：在 text-only、image-only、validation-grid weighted late fusion 之外，新增 `learned_fusion`，用 validation split 训练 Logistic Regression fusion head，并在 test split 上评估。
- learned fusion 输入为 text/image harmful probabilities、概率均值、绝对差和乘积，保留 view detector 不变；这比固定权重融合更接近可训练融合层，但仍不是端到端多模态 Transformer。
- `system/backend/scripts/run_kt3_post_multiview_ablation.py` 已接入 `learned_fusion`，只有 aligned image split 完整时执行；缺图像或类别不足的数据集显式 skipped。
- 重跑 `G:\CISCN\.tmp\kt3_post_multiview_ablation_full_registry\report.json` 后，MultiOFF 最佳实验变为 `learned_fusion`，Test Macro-F1 = 0.655878；对照为 text-only 0.573799、image-only 0.617147、weighted late-fusion 0.620743。
- 能力边界：该结果只证明 MultiOFF 上的 text/image 概率融合头可训练且有效，不代表 Hateful Memes/MAMI/MMHS150K 等 gated meme/image benchmark 已完成，也不代表 video view 或 claim-evidence view 已完成。

## 当前增量：full-validation gate 自动验收

- 新增 `system/backend/scripts/summarize_kt3_full_validation.py`，汇总 dataset audit、`kt3-post-case-v1` manifest 和 full-registry suite report，输出 `kt3-full-validation-gate-v1`。
- Gate 判定规则严格要求每个 P0 数据集同时满足：audit status 为 `ready`、conversion status 为 `converted`、case_count > 0、suite status 为 `evaluated`，且存在 test Macro-F1 指标。
- 已生成 `G:\CISCN\.tmp\kt3_full_validation_gate_report.json`：`overall_pass=false`，`claim=full_validation_not_complete`；P0 passed 为 HateXplain、PHEME、mcfend；P0 failed 为 FACTIFY3M、FakeSV、Hateful Memes、Jigsaw Toxicity、MAMI、MMHS150K、MOCHEG、MultiOFF、RumourEval 2019。
- 该 gate 防止把局部验证、partial 数据集、present_unverified 仓库或 metadata proxy 误写成 full validation 完成；后续只有当所有 P0 blockers 清零后才允许改写为 full-validation complete。
- 历史状态说明：该段记录的是 C3D baseline 接入前的 gate 结果；最新 FakeSV 状态见后文“FakeSV C3D 预提取视频特征 baseline”。
