# KT2 传播监控统一需求与当前状态

> 更新时间：2026-06-28  
> 主口径：本文是 KT2 传播监控模块的统一需求入口。其他文档保留为计划、状态矩阵、复现实验报告或参考文献，不再单独承担最终状态解释。  
> 文档治理：历史 request/closure/report 类文档只作为证据或阶段快照保留；过期口径不再删除追溯记录，而是通过本文统一收敛和显式归档。

## KT2 统一研究定位与文献迁移

KT2 的定位不是“把若干论文模型堆叠到系统里”，也不是单一论文的复现工程，而是面向社交媒体平台的信息扩散监控框架。它把信息扩散研究中的三类任务统一到同一套数据协议、无泄漏实验协议、复现证据和前端展示口径下：用级联时序/流行度预测支撑宏观规模预测，用动态图未来边/下一用户排序支撑微观下一跳预测，用中心性、源头检测和信息扩散 provenance 支撑已观测传播图上的协同用户角色解释与证据追溯。

三类核心能力共享 `standard_cascades`、temporal edge stream、benchmark schema、实验审计和 completion gate。文献迁移到 KT2 时只迁移其任务定义、数据组织、模型路线和评估协议，不把任何尚未 full-run 的模型写成产品级最终能力。当前新增的统一框架口径是 **Macro/Micro 多尺度传播预测**：Macro 分支预测传播规模、增长趋势与最终影响范围；Micro 分支预测未来窗口内可能被激活的用户/节点/边；两者通过共享传播状态和 `macro_micro_consistency` 协议指标进行一致性审计。

| 文献簇 | 学术任务定位 | 迁移到 KT2 的方式 | 当前边界 |
|---|---|---|---|
| 规模预测：Can Cascades be Predicted、SEISMIC、DeepCas、DeepHawkes、CasFlow、CasDO、ConCat、CasFT | Cascade popularity prediction / temporal cascade forecasting，即给定早期观测级联，预测未来增长或最终规模 | 将 `t_obs` 前节点、边、时间戳和文本上下文转为规模预测输入；以 CasFT 为主候选，对比统计模型、深度级联模型、连续时间模型和 diffusion/ODE 模型 | 当前 CasFT 已有 small-run 与 Douban/seed=42/1 epoch same-protocol 预检证据，但仍不是论文级多数据多种子完整复现或产品级最终模型 |
| 下一跳预测：Topo-LSTM、DeepInf、TGAT、TGN、CAW、DyGFormer/DyGLib | Dynamic graph learning / temporal link prediction / next activated user ranking，即在无未来泄漏候选集上预测未来激活节点或边 | 将传播级联转为 temporal edge stream；DyGFormer/DyGLib 为主候选，TGN 为 fallback，Topo-LSTM/FOREST/MINDS/LR/ProspectiveRanker 作 baseline | 当前 DyGLib/TGN 仅为 small-run，事件级 Top-K 仍需多数据、多窗口、多随机种子验证 |
| 多尺度扩散：FOREST、MINDS、HyperIDP | Multi-scale information diffusion prediction，同时关注 macro 规模与 micro 下一用户 | 用作统一任务框架和 benchmark 参照；MINDS/FOREST 可作开源 baseline，HyperIDP 只作为论文/protocol proxy 参照 | HyperIDP proxy 不是原架构复现，不能作为唯一主线或完成证据 |
| 角色与证据：Freeman betweenness centrality、rumor source detection、online information diffusion provenance、Bi-GCN | Observed-graph role explanation / source and path provenance，即解释已观测图中的起爆、桥接、放大、二级扩散和普通参与者 | 对 KT1 已判定协同用户做角色排序、路径证据和帖子/时间追溯；非协同用户只作为路径上下文 | 当前是解释性规则服务，不是未来路径预测，也不是监督角色分类器 |
| 社交机器人检测：LGB: Language Model and Graph Neural Network-Driven Social Bot Detection | Social bot detection / node classification，即把社交账号作为图节点，结合账号文本语义与社交关系结构判断 human/bot | 作为传播监控的参与者风险辅助能力：对传播图中的账号输出 bot 概率、风险标签，并辅助解释协同角色和传播异常 | 当前新增 LGB 本地复现入口与严格复现规格；尚未完成 TwiBot-22/TwiBot-20 论文级 full-run |

因此，KT2 的最终判断标准不是“是否跑过一个模型”，而是：每个核心任务是否有明确的学术定义、无泄漏数据协议、可复现实验记录、与 baseline 的对比证据、可解释的系统输出，以及前端上不误导用户的展示边界。

### 统一 Macro/Micro 框架

KT2 的统一框架不把 FOREST、MINDS、CasFT 机械拼接成一个论文复现声明，而是把三者迁移为一套可验证的多尺度协议，并在此基础上实现 KT2 自有的正式序列式联合训练模型 `KT2SequenceJointModel`。当前方法定义固定为：**MINDS 原始公开代码实现作为可训练 baseline；KT2SequenceJointModel 在 MINDS 式动态图/超图序列主干上吸收 FOREST 的 macro/micro 软耦合，并引入 CasFT 的连续时间未来趋势建模思想**。RF、Temporal、ProspectiveHeuristic、ProspectiveRanker、LR、中心性规则等只能作为 sanity check 或解释模块，不作为证明 KT2 方法有效性的主对比对象。

硬性比较规则：KT2 方法有效性的主结论只能来自可训练模型之间的同协议比较。当前 `benchmark/kt2_minds_comparison.py` 的主 verdict 白名单固定为 `MINDS` 原始公开代码 baseline 与 `KT2SequenceJointModel`；`KT2`/`KT2Sequence` 只是 `KT2SequenceJointModel` 的命令别名。`KT2JointModel` 已降级为 legacy candidate-level / 原组件融合消融模型，不能进入 pair verdict、metric delta 或 `overall_verdict`。

| 框架层 | 研究支撑 | KT2 落点 |
|---|---|---|
| 级联内状态 `Z_intra` | FOREST 用 RNN 建模传播序列，并用结构上下文增强用户表示 | 支撑单事件传播路径、下一跳序列和规模增长之间的关系 |
| 跨级联状态 `Z_cross` | MINDS 用 sequential hypergraph 捕捉多个级联之间的全局扩散动态，并用对抗/正交约束区分共享特征和任务特有特征 | 支撑跨事件共享传播规律，避免只在单条级联上做孤立预测 |
| 未来趋势状态 `Z_future` | CasFT 用 neural ODE 提取动态线索，再用 diffusion model 生成未来 popularity trend | 支撑 Macro 规模预测从“预测一个数”升级到“预测未来趋势 + 最终规模” |
| Macro Head | CasFT、CasDO、CasFlow、DeepHawkes、RF/Temporal | 输出 `predicted_size`、增长趋势、误差指标和观测窗口表现 |
| Micro Head | DyGFormer/DyGLib、TGN、FOREST、MINDS、Topo-LSTM、ProspectiveRanker | 输出 Top-K 激活用户/边、候选覆盖、排序指标和无泄漏审计 |
| 一致性约束与审计 | FOREST 的 macro 奖励反馈与 MINDS 的 macro/micro 解耦思想 | `KT2SequenceJointModel` 用下一用户 sampled softmax 的多步 rollout 期望增长软约束 macro 短期增长趋势，并输出 `macro_micro_soft_consistency`；旧 `KT2JointModel` 的 candidate-level 一致性只作为消融证据 |

当前代码已实现三类统一框架出口：`benchmark/adapters/kt2_sequence_joint_model.py` 是 KT2 当前正式序列式联合训练模型；`benchmark/adapters/kt2_joint_model.py` 保留为 legacy candidate-level / 原组件融合消融模型；`benchmark/macro_micro.py` 是协议审计行。`KT2SequenceJointModel` 的输入是 cascade sequence 多观测窗口，而不是 prefix+candidate feature row；主干显式包含 `DynamicCasHGNN`、`RelationGNN` 和 `SharedLSTM`，Micro 分支用 next-user autoregressive sampled softmax，Macro 分支预测最终规模和未来累计趋势，趋势头使用 CasFT-style Euler latent dynamics 与正增量单调累计，FOREST 迁移为 rollout 期望增长对 macro trend 的软耦合。当前实现仍是 KT2 自有模型，不是 MINDS/FOREST/CasFT 任一原论文的完整源码复现；旧 `KT2JointModel` 的原组件融合、teacher alignment 和 `kt2_joint_model_*` 结果只用于历史追溯和 ablation，不作为正式 improvement verdict。

## 0. 本轮综合检查结论

本轮调用文档审查与验收状态复核智能体，并重新执行 `python -m pytest -q`、`python -m benchmark.role_evidence_review status`、`python -m benchmark.experiment_audit` 与 `python -m benchmark.completion_gate`。综合结论是：当前文档体系没有发现把 baseline/proxy/export-only 错写成前沿复现完成的实质性过度声明，但存在“历史阶段快照”和“当前审计结论”并列时容易误读的问题，尤其是 `small-run passed` 与 `full validation passed` 容易被混读。因此本文继续作为统一需求与状态入口，`REQUEST_CLOSURE.md`、`FEATURE_STATUS_MATRIX.md`、`KT2_COMPLETE_PLAN.md`、`benchmark/REPRODUCTION_REPORT.md` 只保留为阶段说明或证据索引。

当前真值摘要：

| 字段 | 当前值 | 唯一判定来源 |
|---|---|---|
| `frontier_small_run_passed` | `true` | `benchmark/KT2_EXPERIMENT_AUDIT.json/.md` 与 `benchmark/*_external_attempt.json` |
| `full_validation_passed` | `false` | `benchmark/KT2_COMPLETION_GATE.json/.md` |
| `completion_gate_status` | `incomplete`，唯一 open check 为 `role_evidence/manual_review_records` | `python -m benchmark.completion_gate` |
| `manual_review_status` | `role_evidence_manual_review.csv` 已初始化，8/8 样本覆盖模板，但 `review_pass` 全空，当前审核进度 `0/8`；通过前还必须补齐 `reviewer`、`evidence_match`、`confidence_1to5`，失败样本需填写 `reason_if_fail` | `python -m benchmark.role_evidence_review status` |
| `kt2_integrated_evidence_gate` | `evidence_passed`；说明 KT2 自有联合模型的原始子路径、teacher alignment、ablation、同协议预检和指标审计通过，但不等于 MINDS/FOREST/CasFT 论文原架构完整复现 | `benchmark/KT2_ORIGINAL_FUSION_GATE.json/.md` |

当前过期文档采用逻辑清理而非物理删除：保留历史文件用于追溯，但在文件开头或状态表中标注其非状态真值定位。后续判断完成度时，以本文、`benchmark/KT2_EXPERIMENT_AUDIT.json/.md` 和 `benchmark/KT2_COMPLETION_GATE.json/.md` 为准；若历史文档与当前审计不一致，当前审计优先。

需要特别避免的误读是：`benchmark/frontier_status.json` 记录的是默认/聚合安全路径，其中 CasFT、DyGFormer/DyGLib 与 TGN 可处于 export-only 或历史 attempted；而 `benchmark/casft_external_attempt.json`、`benchmark/dyglib_external_attempt.json` 与 `benchmark/tgn_external_attempt.json` 记录的是显式 `--run_external_frontier` small-run。二者不是互相冲突，而是不同命令阶段的证据。当前最高审计状态为：CasFT、DyGFormer/DyGLib 与 TGN 均为 `frontier_reproduction_small_run`；KT2 全量验证仍为 `incomplete`，唯一 critical 开放项是角色证据人工抽查。

### 0.1 唯一事实源与冲突处理规则

完成度判断采用以下优先级：

1. `benchmark/KT2_COMPLETION_GATE.json/.md`：最终闸门，只回答 KT2 full validation 是否通过。
2. `benchmark/KT2_EXPERIMENT_AUDIT.json/.md`：分模块审计，说明哪些 critical section 已通过、哪些仍 partial/missing/blocked。
3. `benchmark/REPRODUCTION_REPORT.md`：复现实验命令、数据、日志和指标证据，不单独承担完成判定。
4. `KT2_REQUIREMENTS.md`：统一需求、状态标签、边界和下一步开发入口。
5. `KT2_COMPLETE_PLAN.md`、`FEATURE_STATUS_MATRIX.md`、`REQUEST_CLOSURE.md`、`README.md`、`REFERENCE.md`：计划、矩阵、历史快照、使用说明或参考文献，不能覆盖审计与闸门结论。

若任一历史文档写法看起来与审计文件冲突，按以下规则解释：`frontier_reproduction_small_run` 只能说明 small-run 可复现；当前代码中的 `frontier_reproduction_full_run` 只能说明上游公开代码在指定 same-protocol 配置下跑通完整训练/评估路径，不能自动等价为论文级多数据、多种子、长训完整复现；`kt2_joint_model_full_run` 只能说明 KT2 自有联合模型的同协议 full-run 预检证据，不是 MINDS/FOREST/CasFT 原论文架构复现；分项 `passed` 只能说明该分项当前审计通过，不能说明 KT2 full validation 通过；只有 `benchmark.completion_gate` 返回 `passed` 且 `full_validation_complete=true` 时，才能对外写“KT2 全量验收完成”。

## 1. 当前结论

KT2 当前已经完成基础传播分析、角色证据最小闭环、baseline/proxy 实验协议、前沿仓库 clone、export-only 数据适配，以及 CasFT、DyGFormer/DyGLib、TGN 的 1 epoch 小样本上游训练尝试；三者均通过 schema 记录为 `frontier_reproduction_small_run`。尚未完成正式多数据多种子 full-run、严格产品化规模预测/下一跳预测 API，以及 KT1 协同角色证据的跨事件稳定性和人工抽查验收；PHEME 本地样例解析已通过。

当前新增的正式 MINDS 对比入口为 `benchmark/kt2_minds_comparison.py`：该入口只比较可训练模型 `MINDS` 原仓库 baseline 与 `KT2SequenceJointModel`，并过滤旧 `KT2JointModel`、RF、LR、ProspectiveRanker 等非主比较行。历史 `benchmark/kt2_vs_minds_multidataset_preflight.json/.md` 仍记录旧 `KT2JointModel` preflight，只能作为 legacy ablation 证据，不能作为当前正式模型结论。

继续推进全量验证时，统一使用以下入口，而不是再用 RF/Heuristic 或本地 proxy 证明方法有效：

该入口的报告中若出现 `comparison_model_filter.ignored_non_comparison_row_count > 0`，说明历史或外部输入中存在非主比较模型行；这些行只用于审计追溯，不参与 KT2 是否优于 MINDS 的判断。

```powershell
python -m benchmark.kt2_minds_comparison `
  --datasets douban,twitter,memetracker `
  --seeds 42,43,44 `
  --max_minds_cascades 0 `
  --minds_epochs 5 `
  --kt2_epochs 5 `
  --kt2_max_train_cascades 0 `
  --kt2_max_test_cascades 0 `
  --out benchmark\kt2_vs_minds_full_candidate.json `
  --config_id kt2-vs-minds-full-candidate `
  --device cpu
```

只有该入口产物满足 `full_validation_passed=true`，并且 `schema_report.ok=true`、`missing_pairs=[]` 时，才能对外写“KT2 对 MINDS 的改进经多数据多种子同协议验证”。

全量实验验证入口为 `benchmark/KT2_EXPERIMENT_AUDIT.json` 与 `benchmark/KT2_EXPERIMENT_AUDIT.md`。当前审计总状态为 `incomplete`：规模预测 `passed`（CasFT small-run 已完成，但不是多随机种子 full-run）、下一跳预测 `passed`（DyGLib/TGN 已完成 3 次重复 small-run 与无泄漏审计，但不是多随机种子 full-run）、角色证据 `partial`（真实 KT1 本地样例已接入，PHEME 样例解析与 observed-user 角色证据产物已通过，人工抽查模板/指南/证据包已 ready，但仍缺已审核通过记录）、前端与协议 `passed`。

当前不得把以下内容写成“KT2 已完成”：

- RF、Temporal、ProspectiveHeuristic、ProspectiveRanker、LR 只能写为 local baseline 或 sanity baseline。
- 历史 `benchmark/kt2_vs_minds_multidataset_preflight.json/.md` 是 MINDS 原仓库可训练 baseline vs 旧 `KT2JointModel` 的 legacy preflight 对比证据；当前正式模型 `KT2SequenceJointModel` 需要重新生成同协议多数据/多种子结果，历史旧结果不能写成当前正式模型结论。
- HyperIDPProtocolProxy / HyperIDPAdversarialProxy 只能写为 protocol proxy，不是 HyperIDP 原论文架构复现。
- CasFT 当前可写为 `frontier_reproduction_small_run`，并有 Douban / seed=42 / 1 epoch 的 same-protocol 预检行；即便该行使用 `frontier_reproduction_full_run` 标签，也只能解释为“公开代码完整训练/评估路径跑通”，不能写成论文级完整复现或产品级最终模型。
- DyGFormer/DyGLib 与 TGN 当前仅可写为 `frontier_reproduction_small_run`，不能写成 full-run 或产品级完成。
- Dashboard 只能展示已观测事实、角色证据和带“实验预测”标识的预测结果，不能展示未完成的功能清单或确定性未来结论。

本轮多智能体审查结论：当前文档体系未发现把 baseline/proxy/export-only 错写成前沿复现完成的实质冲突；旧文档已基本指向本文件作为统一入口。仍需明确的是：历史 `request.md` 不再作为独立状态源，其需求已被本文件吸收，`REQUEST_CLOSURE.md` 已标注为 archive/stage snapshot，仅保留阶段落实说明。

## 2. 文档体系

| 文档 | 定位 | 是否作为状态真值 |
|---|---|---|
| `KT2_REQUIREMENTS.md` | 统一需求、状态、边界与下一步验收入口 | 是，主入口 |
| `request.md` | 历史开发请求来源；当前目录不再保留独立状态文件 | 否，已由本文吸收 |
| `KT2_COMPLETE_PLAN.md` | 阶段计划与路线说明 | 辅助 |
| `FEATURE_STATUS_MATRIX.md` | 功能清单、完成度与待开发项 | 辅助 |
| `REQUEST_CLOSURE.md` | Archive / stage snapshot；对 request.md 落实程度的阶段说明 | 否，只作历史证据 |
| `benchmark/REPRODUCTION_REPORT.md` | 复现实验、数据协议、指标与命令记录 | 辅助证据 |
| `benchmark/KT2_EXPERIMENT_AUDIT.md` / `.json` | 全量实验验证审计入口，汇总每项要求的证据、缺口和阻塞原因 | 是，验证入口 |
| `REFERENCE.md` | 参考文献与模型路线 | 非状态源 |
| `README.md` | 传播分析原型使用说明 | 非 KT2 前沿复现状态源 |

当前审查结论：

- 未发现文档把 baseline/proxy/export-only 错写成前沿复现完成。
- 未发现 HyperIDP 被继续写成唯一主线；它仅作为多尺度论文参考和 protocol proxy baseline。
- `README.md`、`KT2_COMPLETE_PLAN.md`、`FEATURE_STATUS_MATRIX.md`、`REQUEST_CLOSURE.md`、`REFERENCE.md`、`benchmark/REPRODUCTION_REPORT.md` 均已声明以本文为统一入口。
- 过期文档采用“逻辑清理”策略：不删除历史文件，避免丢失决策追溯；通过 archive 标识、主入口声明和状态标签约束来阻止旧口径继续扩散。
- 后续新增或修改文档时，所有“已完成”“已落地”表述必须显式绑定状态标签，避免把 CLI/baseline 可运行误读为产品级或前沿复现完成。

## 3. 功能范围

KT2 收敛为三项核心功能和若干辅助展示/协议能力：

| 模块 | 任务定义 | 当前完成度 | 目标完成状态 |
|---|---|---|---|
| 规模预测 | 给定早期观测窗口，预测未来或最终传播规模 | 本地 baseline、CasFT export-only adapter、CasFT upstream small-run 与 Douban same-protocol 预检已接入；当前仍是短训/单种子证据 | 扩展 CasFT 或同级前沿模型到多窗口、多数据、多种子长训对比，优于本地 baseline |
| 协同角色定位与证据追溯 | 对 KT1 已判定协同用户，在已观测传播图中解释角色和证据链 | KT1 本地样例接入与最小闭环已落地；PHEME observed-user 时间线证据已通过；已生成 `role_evidence_manual_review_template.csv`，但未填写人工审核结论 | 扩展真实 KT1 跨事件输出，完成人工抽查 |
| 下一跳预测 | 给定 `t_obs` 前传播图和候选用户，预测未来窗口内可能激活用户/边 | 本地 next-hop baseline 已接入；DyGFormer/DyGLib 与 TGN 均已完成 3 次重复 / 1 epoch small-run 和无泄漏审计 | 扩展到更多数据集/观测窗口和多随机种子并比较落地性；严格无未来节点注入，指标优于 ProspectiveRanker |
| Macro/Micro 多尺度框架 | 在同一协议下联合解释规模趋势与下一跳排序，并审计二者是否一致 | 已新增 `KT2SequenceJointModel` 正式序列联合训练 small-run；旧 `KT2JointModel` 的 `kt2_joint_model_*` 结果保留为 legacy ablation；`benchmark/macro_micro.py`、`prediction_report.json` 与 dashboard 审计面板已接入 | 后续将 `KT2SequenceJointModel` 扩展到更多数据、更长训练、多窗口、多随机种子，并与 CasFT、DyGLib/TGN、FOREST/MINDS 和本地 baselines 对比；当前不是论文原架构 full-run |
| KT2 vs MINDS 可训练模型对比 | 以 MINDS 原仓库实现作为 baseline，对比 KT2SequenceJointModel 是否改进 | `benchmark/kt2_minds_comparison.py` 的正式 pair verdict 只允许 `MINDS` 与 `KT2SequenceJointModel`；旧 `KT2JointModel` 和手工/启发式基线会被过滤或拒绝 | 全量结论要求 `full_validation_passed=true`：至少 3 数据集、至少 3 seeds、MINDS/KT2 均不少于 5 epochs，且 MINDS/KT2 使用全量可用级联；当前尚未完成 |
| 多尺度实验协议 | 统一 scale 与 next-hop 的数据、切分、指标、泄漏审计 | 已有 benchmark 入口、protocol export 和 macro/micro framework summary | 所有候选模型输出统一 JSON、日志、随机种子、结果表和一致性摘要 |
| 前端/报告展示 | 展示总览、时间线、路径、角色证据、实验预测与 Macro/Micro 一致性审计 | 静态 dashboard 已落地；预测面板已字段化展示数据集、观测窗口、模型名、复现等级和误差说明 | 产品 API 需等模型选择完成 |
| 社交机器人检测 | 对传播参与账号检测 human/bot 风险，辅助解释社交机器人参与的传播/协同行为 | 已新增 LGB 论文复现入口 `benchmark/adapters/lgb_bot_detection.py`、benchmark schema `bot_detection`、smoke 测试；当前是 local reproducible adapter，不是论文 full-run | 按 LGB 论文严格复现 TwiBot-22/TwiBot-20：RoBERTa/T5 统一文本序列 SFT、GCL 图预训练、GNN concat 融合微调、5 次随机初始化，报告 Accuracy/F1/ROC-AUC |

### 3.1 核心功能数据集与报告指标

| 核心功能 | 当前已用数据集 | 后续必须扩展/可选数据集 | 必须报告指标 | 当前报告边界 |
|---|---|---|---|---|
| 规模预测 | FOREST Douban；当前 CasFT small-run 使用 FOREST Douban 转 CasFT staging 数据 | CasFT Twitter/Weibo/APS、FOREST Twitter、DeepHawkes Weibo、Twitter15/16、Rumor_RvNN/Weibo 传播树 | MSLE、MAE、RMSE、MAPE/sMAPE、Direction Accuracy、不同 `t_obs` 观测窗口表现；可补充 PCC、R2、预测区间覆盖率 | 当前 CasFT 仅为 500 cascades / 1 epoch / seed=0 small-run；RF/Temporal 是 local baseline，不能写成前沿 full-run |
| 下一跳预测 | FOREST Douban temporal edge stream；DyGLib/TGN small-run 与 ProspectiveRanker/Heuristic 对比均在该路径上验证 | FOREST Twitter、Twitter15/16、Rumor_RvNN、PHEME；必要时补充社交邻接或历史转移统计 | Candidate Recall、Hits@10/50/100、MAP@10/50/100、MRR、NDCG@10/50/100、平均候选集大小、候选集无泄漏审计；上游动态图模型可补充 AP/AUC | 当前 DyGLib/TGN 是 20 cascades / 1 epoch / seed=0 / 3 次重复 small-run；事件级 Top-K 仍以 KT2 候选协议聚合，不能写成产品级最终模型 |
| 协同角色定位与证据追溯 | KT1 本地样例协同用户输出；PHEME 5 个真实时间线样例事件；Twitter15/16/Rumor_RvNN 已作为传播树验证目标 | 真实 KT1 跨事件协同输出、完整 PHEME、Twitter15/16、Rumor_RvNN/Weibo；必要时抽样人工标注证据 | coordination_user_coverage、path_complete_rate、role_stability、人工审核通过率、evidence_match、confidence_1to5；结构证据报告 out_degree_sum、betweenness_sum、pagerank_sum、post_count、first_seen、evidence_paths | 当前是 observed-graph 解释性规则服务，不是监督角色分类器；人工审核 CSV 仍需填写后才能从 `partial` 升级为 `passed` |
| 社交机器人检测 | 当前仅有合成 smoke fixture；本地尚未发现 TwiBot-22/TwiBot-20 官方数据目录 | 必须下载/准备 TwiBot-22 与 TwiBot-20；可选补充 Cresci、MGTAB、Botometer 风格数据用于迁移验证 | Accuracy、F1-Score、ROC-AUC；按节点度数分桶报告 isolated、sparse 1-2 neighbors、dense >2 neighbors；消融报告 w/o LM SFT、w/o GNN pretraining、w/o GNN finetuning、w/o concat、average/max fusion、SFT LM only | 当前 `benchmark/adapters/lgb_bot_detection.py` 使用 HashingVectorizer 作为本地可跑语义代理；严格复现必须替换为论文中的监督 fine-tuned RoBERTa/T5 特征，并跑 5 seeds |

## 4. 当前代码证据

| 能力 | 已有代码 | 当前边界 |
|---|---|---|
| 标准协议导出 | `propagation/protocol.py::export_standard_cascades` | 可导出 `standard_cascades.json`，但不是模型训练本身 |
| KT1 协同用户接入 | `propagation/protocol.py::load_coordination_scope`；CLI `--coordination-file` | 支持 JSON/CSV/TSV；已用本地 KT1 样例输出完成解析与角色证据生成，仍需跨事件批量验收 |
| 角色证据表 | `propagation/analysis.py::role_evidence_table` | 五类规则角色，偏解释性启发式，不是监督学习分类器 |
| 角色证据质量评估 | `propagation/analysis.py::role_evidence_quality`；输出 `role_evidence_quality.json` | 已统计覆盖率、路径完整率、角色稳定性；当前 KT1 样例 coverage=1.0、path_complete_rate=1.0；PHEME 5 个样例事件已生成 observed-user 角色证据 10 行，coverage=1.0、path_complete_rate=1.0；仍需真实人工抽查 |
| Dashboard 展示 | `propagation/visualization.py::build_dashboard` | 展示候选高频共享对象、代表性事件、角色证据、实验预测；预测面板包含 `dataset`、`t_obs/observation_ratio`、`model_name`、`reproduction_level` 和误差/不确定性说明 |
| 预测报告元数据 | `propagation/prediction.py::run_prediction`；`prediction_report.json` | 输出 `cogguard.kt2.prediction_report.v1`，统一记录数据集、观测窗口、实验预测标签和 local baseline 复现等级 |
| KT2 正式序列联合模型 | `benchmark/adapters/kt2_sequence_joint_model.py`；`benchmark/kt2_minds_comparison.py`；`benchmark/schema.py`；`tests/test_smoke.py::test_kt2_sequence_joint_model_trains_sequence_macro_micro_small_run` | 读取 FOREST 级联，构造 `obs_ratio=0.1/0.3/0.5` 多窗口序列样本；输入包含 `user_sequence`、时间特征、训练转移图 RelationGNN 邻居、prefix stage hyperedges 和观测规模，不使用 prefix+candidate 手工特征作为主模型输入；主干为 `DynamicCasHGNN + RelationGNN + SharedLSTM`，micro 用下一用户 autoregressive sampled softmax，macro 用最终规模与 CasFT-style Euler latent trend decoder，FOREST 迁移为 rollout 期望增长对 macro trend 的软耦合；loss 按 cascade `event_id` 分组归一；输出 `msle/mae/rmse/mape/smape/direction_accuracy`、`trend_mae/trend_rmse`、`Candidate Recall/Hits/MAP/MRR/NDCG`、`rollout_summary`、`candidate_protocol_audit` 和 `macro_micro_soft_consistency`。当前状态为 `kt2_sequence_joint_model_small_run`，不是论文原架构 full-run |
| KT2 legacy candidate-level / 原组件融合模型 | `benchmark/adapters/kt2_joint_model.py`；`benchmark.run_benchmark --models kt2_joint`；历史 `kt2_joint_model_*` 结果 | 保留旧 prefix+candidate 特征二分类路径、原组件融合、teacher alignment 和 ablation 证据；可用于解释旧设计为何出现 micro 强、macro 弱，以及作为历史消融对照 | 不再作为 KT2 正式模型或 `MINDS vs KT2` 主 verdict 输入 |
| Macro/Micro 框架审计 | `benchmark/macro_micro.py`；`benchmark.run_benchmark`；`propagation/prediction.py`；`propagation/visualization.py` | benchmark 生成 `KT2MacroMicroFramework` 协议行与 `*_macro_micro_framework.json`；当结果中存在 `KT2JointModel` 时，汇总会把它作为同一模型的 macro/micro 配对；本地 dashboard 展示 `macro_micro_consistency`，但不宣称论文前沿 full-run |
| CasFT 适配 | `benchmark/adapters/casft_runner.py`；`benchmark.run_benchmark --models casft` | 默认 `protocol_export_only`；显式 `--run_external_frontier` 会 staging 到 `data/kt2_<dataset>_casft` 并运行官方 `gen_cas.py -> gen_emb.py -> train.py`。当前 `benchmark/casft_external_attempt.json` 已记录 `frontier_reproduction_small_run` |
| DyGLib/TGN 适配 | `benchmark/adapters/temporal_graph_runner.py`；`benchmark.run_benchmark --models dyglib tgn` | DyGLib/TGN 均可运行上游 3 次重复 / 1 epoch small-run，并记录 seed、num_runs、日志和 `candidate_protocol_audit`；`num_runs=3` 不是多随机种子 full-run；默认不加 `--run_external_frontier` 时仍保持 export-only 安全口径 |
| FOREST 公开代码适配 | `benchmark/adapters/forest_runner.py`；`benchmark.run_benchmark --models forest` | 支持从迁移后的 `G:\CISCN\dataset\forest-data` staging 到 FOREST 原始 `data/<dataset>` 结构；普通 RNN 下一用户预测和 RRModel policy-gradient macro reward fine-tune 均已接入。当前 `benchmark/forest_rl_smoke.json` 为 Douban / 1 epoch / batch-limited / rollout_len=32 / 1 RL batch CPU smoke-run，证明原 FOREST RL coupling 路径可执行，但不是原论文完整 500-step rollout full-run 或性能结论 |
| Benchmark schema 校验 | `benchmark/schema.py`；伴随输出 `<benchmark>.schema.json` | 校验任务、状态、复现等级、指标形态和下一跳候选泄漏审计；防止 export-only 被写成复现完成 |
| 全量实验审计 | `benchmark/experiment_audit.py`；输出 `benchmark/KT2_EXPERIMENT_AUDIT.json/.md` | 汇总规模预测、下一跳预测、角色证据、前端协议四类验收项；当前明确标记 full validation 未完成 |
| 防误判测试 | `tests/test_smoke.py` | 明确断言 export-only 不等于 frontier reproduction，并验证 frontier small-run 必须记录 seed/random_seed/num_runs |

## 5. 状态标签

| 标签 | 含义 | 可用于完成声明吗 |
|---|---|---|
| `local_baseline` | 本地传统/启发式 baseline 可运行 | 只能说明 baseline 完成 |
| `protocol_proxy_not_original_architecture` | 协议级代理模型可运行，不是原论文结构 | 不能说明前沿复现完成 |
| `public_code_adapter` | 公开代码适配器可运行或可调用 | 只能说明该公开代码路径可用 |
| `frontier_data_adapter_ready_not_model_run` | 前沿仓库已接入，数据可导出，但上游训练未完成 | 不能说明复现完成 |
| `frontier_reproduction_attempted` | 尝试运行上游训练，但失败/超时/不稳定 | 不能说明复现完成 |
| `frontier_reproduction_small_run` | 上游前沿模型 small-run 完成，有日志、随机种子、指标 JSON | 可说明 small-run 完成 |
| `frontier_reproduction_full_run` | 上游公开代码在指定 same-protocol 配置下跑通完整训练/评估路径，并记录命令、随机种子、日志和指标；若只有单数据/单种子/短训，只能称为 full-run preflight | 可说明公开代码路径可完整执行；只有扩展到论文级多数据、多种子、长训并完成统计对比后，才能写为正式复现完成 |
| `kt2_sequence_joint_model_small_run` | KT2SequenceJointModel 正式序列式联合模型完成 small-run，并输出 macro/trend、next-user rollout、无泄漏审计和一致性指标 | 可说明正式 KT2 序列模型链路已跑通；不能说明多数据多种子 full validation |
| `kt2_sequence_joint_model_full_run` | KT2SequenceJointModel 在指定 same-protocol 配置下跑通完整训练/评估路径，并记录数据、种子、指标、rollout 与审计信息 | 可说明 KT2 正式序列模型 full-run 预检；仍不能自动等价为论文原架构复现 |
| `kt2_joint_model_small_run` | 旧 KT2JointModel legacy candidate-level/原组件融合模型在本地数据上完成 small-run | 只能作为 ablation 或历史证据，不能进入正式 improvement verdict |
| `kt2_joint_model_full_run` | 旧 KT2JointModel legacy/原组件融合路径在指定 same-protocol 配置下跑通完整训练/评估路径 | 只能说明 legacy integrated path 预检通过，不能说明当前正式模型完成 |

## 6. 模型路线

| 任务 | 主候选 | fallback / baseline | 当前状态 |
|---|---|---|---|
| 规模预测 | CasFT | CasDO、ConCat、CasFlow、DeepHawkes、RF、Temporal | CasFT 仓库已 clone，export-only adapter 与上游 small-run 已接入；当前结果见 `benchmark/casft_external_attempt.json`，仍需多窗口、多数据、多种子 full-run |
| 下一跳预测 | DyGFormer/DyGLib | TGN、FOREST、MINDS、Topo-LSTM、ProspectiveRanker、ProspectiveHeuristic、LR | DyGFormer/DyGLib 与 TGN 均已完成 3 次重复 / 1 epoch small-run；FOREST 已补充 RRModel policy-gradient fine-tune smoke-run 作为 macro/micro coupling baseline 证据；仍需更多数据集、观测窗口和多随机种子扩展后再最终选型 |
| KT2 联合模型 | KT2SequenceJointModel | KT2JointModel legacy ablation、CasFT+DyGLib/TGN 分支组合、FOREST/MINDS、HyperIDP protocol/adversarial proxy | KT2SequenceJointModel 已作为 KT2 正式序列联合模型接入 benchmark；当前为 small-run，需要扩展到更长训练、更多数据、更多随机种子后才能定型 |
| 多尺度参考 | MINDS、FOREST、HyperIDP 论文 | HyperIDP protocol/adversarial proxy | MINDS/FOREST 有部分公开代码结果；HyperIDP proxy 不能当原架构 |
| 角色证据 | 中心性 + 路径证据 v1 | 后续可加稳定性/一致性检验 | 已落地最小闭环，不等待前沿模型 |

CasFT 环境边界：不要在当前主环境 Python 3.12 中硬装旧依赖。CasFT 官方 README 指向 Python 3.7、PyTorch 1.12/CUDA 11.3、`cogdl`、`karateclub`、`numba`、`torchdiffeq` 等旧栈，并且 `setup.py` 需要编译 `data_utils_fast.pyx`。当前已验证隔离环境 `casft_torch_clean` 中 Python 3.7.16、PyTorch 1.12.0、NumPy 1.21.5、PyTorch 1.12.0 CPU 与 `cogdl==0.6` 可支撑 small-run；Windows shim 已处理 `forkserver`、DDP CPU backend 与日志管道兼容问题。后续复跑仍应使用隔离环境，并记录命令、日志、随机种子、数据版本和指标 JSON。

## 7. 数据与本地路径

| 资源 | 路径 / 状态 | 用途 |
|---|---|---|
| 外部复现仓库 | `G:\CISCN\CogGuard\subsystems\kt2_repos` | 不放入 `cogguard_dev` Git 管理 |
| CasFT | HEAD `ebb7e8e` | 规模预测主候选 |
| DyGLib | HEAD `3aacc36` | 下一跳 temporal graph 主候选 |
| TGN | HEAD `d55bbe6` | 下一跳 fallback |
| FOREST | HEAD `637c748` | 数据与经典 baseline |
| FOREST Douban/Twitter/Memetracker 数据 | `G:\CISCN\dataset\forest-data` | 当前 benchmark 已支持将 `--forest_dir` 指向该迁移后的数据根目录，也兼容旧的 FOREST repo `data/` 布局 |
| CasFT/CasFlow 官方数据 | `G:\CISCN\dataset\casflow-data`，其中 Twitter/Weibo 可用，APS `dataset.txt` 当前为空 | 规模预测 CasFT/CasFlow 类实验数据；不再要求新增其它数据集 |
| Twitter15/16 | `G:\CISCN\dataset\Twitter15_16_dataset`，HEAD `6a33ebd` | 传播树、角色证据、下一跳验证 |
| Rumor_RvNN | `G:\CISCN\dataset\Rumor_RvNN`，HEAD `6d3bb25` | Twitter 传播树数据源 |
| PHEME | 已下载并解压到 `G:\CISCN\dataset\PHEME`；原始包位于 `G:\CISCN\dataset\PHEME\raw\PHEME_veracity.tar.bz2`；审计脚本已解析 5 个样例事件，得到 99 个节点、94 条边和 99 个时间戳；来源 [Figshare 6392078](https://figshare.com/articles/dataset/PHEME_dataset_for_Rumour_Detection_and_Veracity_Classification/6392078)，经典 RNR 版本参考 [Figshare 4010619](https://figshare.com/articles/dataset/PHEME_dataset_of_rumours_and_non-rumours/4010619) | 谣言线程、证据追溯、时间线验证 |

## 8. 实验与验收要求

规模预测验收：

- 输入只能使用 `t_obs` 前节点、边、时间戳、文本/事件上下文。
- 标签为未来窗口规模或最终规模，不能使用最终规模派生特征。
- 指标至少包括 MSLE、MAE、RMSE、MAPE、Direction Accuracy。
- 每个正式实验必须报告数据集名称、数据版本/本地路径、训练/验证/测试切分、观测窗口 `t_obs`、预测窗口 `t_pred`、随机种子、模型复现等级和命令/日志路径。
- 正式对比表至少包含 CasFT、RF、Temporal，并在可运行时补充 CasDO、ConCat、CasFlow、DeepHawkes；fallback 结果必须标注为 fallback，不能写成 CasFT 原模型复现。
- CasFT small-run 需产出命令、日志、随机种子、数据路径、指标 JSON。
- 若 CasFT 8GB GPU 不可运行，依次记录 CasDO/ConCat fallback 结果，但不能把 fallback 写成 CasFT 复现。

下一跳预测验收：

- 统一输入为 temporal edge stream：`event_id, parent_user, child_user, timestamp, edge_type`。
- 候选集只能来自训练集用户、观测前缀用户、历史转移统计、已知社交邻居，禁止注入未来真实节点或真实 parent。
- 指标至少包括 Candidate Recall、Hits@K、MAP@K、MRR、NDCG@K。
- 每个正式实验必须报告候选集构造来源、平均候选集大小、未来节点注入检查、`future_only_candidate_violations`、`observed_user_candidate_violations` 和 `leakage_check_passed`。
- 上游 DyGLib/TGN 可报告 AP/AUC，但 KT2 最终比较必须以事件级 Top-K 用户/边排序指标为主；LR 只能作为 offline edge classifier 辅助解释，不作为下一跳完成证据。
- DyGLib/TGN small-run 需产出上游训练日志和 KT2 事件级 Top-K 聚合结果。
- LR 只能写为 offline edge classifier；ProspectiveRanker 只能写为 sanity baseline。
- 当前 DyGLib/TGN export-only adapter 已输出 `candidate_protocol_audit`，用于证明候选集未注入未来节点；后续上游 small-run 也必须保留该字段。

角色证据验收：

- `--coordination-file` 接入真实 KT1 协同用户输出。
- 主榜只排序协同用户；非协同用户只能作为路径上下文。
- 输出 `role_evidence.csv`，字段至少包括用户、协同组、角色、结构指标、证据路径、关键节点、时间。
- 评估路径完整率、协同用户覆盖率、角色稳定性和人工抽查通过率。
- 每个角色证据报告必须列出支撑数据集/事件来源、协同用户来源、角色定义版本、抽样策略、审核人、`review_pass`、`evidence_match`、`confidence_1to5`；失败样本必须记录 `reason_if_fail`。
- 角色证据指标只能证明“已观测图上的解释质量”，不能证明未来传播路径预测能力。
- 当前已自动输出 `role_evidence_quality.json`，包含 `coordination_user_coverage`、`path_complete_rate`、`role_stability` 和 `manual_review_required`。

前端/报告验收：

- 页面优先展示已观测高频共享对象、传播时间线、路径图、角色证据。
- 预测区必须显示模型名、观测窗口、数据集、指标、误差/置信信息和“实验预测”标识。
- 不上传未完成的功能清单，不把实验预测展示为确定事实。
- 当前 dashboard 已做到“不展示未完成功能清单”和“实验预测标识”；预测区已字段化展示 `dataset`、`t_obs/observation_ratio`、模型名、复现等级和误差/不确定性说明。当前尚无校准置信区间，因此以 MAE/RMSE/MSLE/MAPE 或候选覆盖/排序指标作为误差证据。

## 9. 已验证命令

```powershell
python -m pytest -q
```

当前结果：`32 passed`，覆盖 `prediction_report.json` schema、dashboard 预测区字段化展示、协同角色证据过滤、PHEME loader 样例解析、PHEME observed-user 角色证据产物、frontier export-only 防误判、frontier small-run 元数据、`seed=0` 前沿复现 schema、KT1 样例接入、角色证据人工抽查模板/初始化/校验入口、KT2 completion gate 正反向夹具和 benchmark schema 校验。

```powershell
python -m benchmark.run_benchmark `
  --models casft dyglib tgn `
  --datasets douban `
  --forest_dir G:\CISCN\CogGuard\subsystems\kt2_repos\FOREST `
  --casft_dir G:\CISCN\CogGuard\subsystems\kt2_repos\CasFT `
  --dyglib_dir G:\CISCN\CogGuard\subsystems\kt2_repos\DyGLib `
  --tgn_dir G:\CISCN\CogGuard\subsystems\kt2_repos\tgn `
  --frontier_max_cascades 100 `
  --frontier_timeout 120 `
  --output benchmark\frontier_status.json
```

当前结果（默认/聚合安全状态文件；CasFT、DyGFormer/DyGLib 与 TGN 的显式 external small-run 结果见下方独立输出文件）：

| 模型 | 状态 | reproduction_level |
|---|---|---|
| CasFT | 历史默认安全快照，不作为当前最高状态 | 以 `benchmark/casft_external_attempt.json` 的 external small-run 为准 |
| DyGFormer/DyGLib | `temporal_edge_export_only` | `frontier_data_adapter_ready_not_model_run` |
| TGN | `temporal_edge_export_only` | `frontier_data_adapter_ready_not_model_run` |

解释：该聚合表不能覆盖显式 `--run_external_frontier` small-run 的结果；当前最终审计以 `benchmark/KT2_EXPERIMENT_AUDIT.json/.md` 为准。

DyGFormer/DyGLib 外部 small-run 验证：

```powershell
python -m benchmark.run_benchmark `
  --models dyglib `
  --datasets douban `
  --forest_dir G:\CISCN\CogGuard\subsystems\kt2_repos\FOREST `
  --dyglib_dir G:\CISCN\CogGuard\subsystems\kt2_repos\DyGLib `
  --frontier_max_cascades 20 `
  --frontier_epochs 1 `
  --frontier_batch_size 16 `
  --frontier_gpu -1 `
  --frontier_timeout 120 `
  --run_external_frontier `
  --output benchmark\dyglib_external_attempt.json
```

当前结果：`status=ok`，`reproduction_level=frontier_reproduction_small_run`，`seed=0`，`num_runs=3`，`dyglib_dataset_alias=wikipedia`，schema `ok=true`。该结果证明上游 DyGLib 训练链路可跑通并满足当前重复 small-run 审计门槛；这里的 `num_runs=3` 不是 3 个随机种子，也不是 full-run。事件级 Top-K 面板仍使用 KT2 候选协议指标保证与 baseline 可比，不等于产品级最终模型。

TGN 外部 small-run 验证：

```powershell
python -m benchmark.run_benchmark `
  --models tgn `
  --datasets douban `
  --forest_dir G:\CISCN\CogGuard\subsystems\kt2_repos\FOREST `
  --tgn_dir G:\CISCN\CogGuard\subsystems\kt2_repos\tgn `
  --frontier_max_cascades 20 `
  --frontier_epochs 1 `
  --frontier_batch_size 16 `
  --frontier_gpu -1 `
  --frontier_timeout 120 `
  --run_external_frontier `
  --output benchmark\tgn_external_attempt.json
```

当前结果：`status=ok`，`reproduction_level=frontier_reproduction_small_run`，`seed=0`，`num_runs=3`，schema `ok=true`。上游日志包含 test AUC/AP；这里的 `num_runs=3` 是重复 small-run 证据，不是多随机种子 full-run。事件级 Top-K 面板仍使用 KT2 候选协议指标保证与 baseline 可比。

CasFT 外部 small-run 验证：

```powershell
python -m benchmark.run_benchmark `
  --models casft `
  --datasets douban `
  --forest_dir G:\CISCN\CogGuard\subsystems\kt2_repos\FOREST `
  --casft_dir G:\CISCN\CogGuard\subsystems\kt2_repos\CasFT `
  --frontier_max_cascades 500 `
  --frontier_epochs 1 `
  --frontier_timeout 300 `
  --casft_observation_time 31536000 `
  --casft_prediction_time 157680000 `
  --run_external_frontier `
  --output benchmark\casft_external_attempt.json
```

当前结果：`status=ok`，`reproduction_level=frontier_reproduction_small_run`，schema `ok=true`。本次为 500 cascades / 1 epoch / seed=0 / CPU Windows shim small-run，指标为 `msle=10.9604`、`mae=2.7008`、`smape=0.5824`、`mape_percent=0.5824`、`pcc=-0.4065`、`r2=-0.6614`。该结果可证明 CasFT small-run 完成，但仍不得写成多数据多种子 full-run 或产品级最终模型。

伴随 schema 校验：

| 文件 | 结果 |
|---|---|
| `benchmark/frontier_status.json.schema.json` | `schema=cogguard.kt2.benchmark_result.v1`，`ok=true`，`rows=3`，`errors=[]`，`warnings=[]` |
| `benchmark/casft_external_attempt.json.schema.json` | `schema=cogguard.kt2.benchmark_result.v1`，`ok=true`，`rows=1`，`errors=[]`，`warnings=[]` |

全量实验审计：

```powershell
python -m benchmark.experiment_audit
```

当前结果：`schema=cogguard.kt2.experiment_audit.v1`，`status=incomplete`，`full_validation_complete=false`。关键开放项为 `role_evidence`；`scale_prediction`、`next_hop_prediction` 与 `frontend_and_protocol` 已通过。

PHEME 真实时间线角色证据验证：

```powershell
python -m benchmark.kt1_coordination_adapter `
  --pheme-observed-sample `
  --data-dir G:\CISCN\dataset\PHEME `
  --output benchmark\pheme_role_evidence_sample `
  --max-events 5 `
  --users-per-event 2
```

当前结果：`status=ok`，5 个 PHEME 样例事件、99 个节点、94 条边，生成 `benchmark/pheme_role_evidence_sample/analysis/role_evidence.csv` 共 10 行；`coordination_user_coverage=1.0`，`path_complete_rate=1.0`。该结果只验证 KT2 在真实 PHEME 时间线上可生成 observed-graph 角色证据，不是 KT1 真实协同预测输出。

角色证据人工抽查模板：

```powershell
python -m benchmark.role_evidence_review `
  --role-evidence benchmark\kt1_role_evidence_validation\analysis\role_evidence.csv `
  --output benchmark\kt1_role_evidence_validation\analysis\role_evidence_manual_review_template.csv `
  --sample-size 30 `
  --per-role 5 `
  --seed 0
```

当前结果：已生成 8 条待审样本，覆盖 `普通参与者`、`桥接`、`起爆/源头`。模板不会预填 `review_pass`；当前 `analysis/role_evidence_manual_review.csv` 已从模板初始化，覆盖全部 8 条样本，但 `review_pass` 仍全空，因此审核进度为 `0/8`。人工审核后需在该 CSV 中填写每行 `review_pass`、`reviewer`、`evidence_match`、`confidence_1to5` 和必要备注；若 `review_pass=false`，还必须填写 `reason_if_fail`。通过率不低于 0.8 且元数据完整时，审计才会把 `manual_review_records` 升级为 `passed`。

伴随审核指南：`benchmark/kt1_role_evidence_validation/analysis/ROLE_EVIDENCE_REVIEW_GUIDE.md`；逐条证据卡：`benchmark/kt1_role_evidence_validation/analysis/ROLE_EVIDENCE_REVIEW_PACKET.md`；本地 HTML 审核页：`benchmark/kt1_role_evidence_validation/analysis/ROLE_EVIDENCE_REVIEW.html`。当前审计中 `manual_review_packet_ready=passed`，说明审核材料已准备好；`manual_review_records=partial`，说明仍缺真实审核结论。若 `role_evidence_manual_review.csv` 丢失，可用下面命令从模板重建待填 CSV：

```powershell
python -m benchmark.role_evidence_review init `
  --template benchmark\kt1_role_evidence_validation\analysis\role_evidence_manual_review_template.csv `
  --output benchmark\kt1_role_evidence_validation\analysis\role_evidence_manual_review.csv
```

当前 `role_evidence_manual_review.csv` 已存在时，不需要重新 init；直接填写 8 条审核结果，然后运行：

```powershell
python -m benchmark.role_evidence_review status
python -m benchmark.role_evidence_review validate `
  --review-file benchmark\kt1_role_evidence_validation\analysis\role_evidence_manual_review.csv
```

`init` 只会从模板创建待填写 CSV，不会预填 `review_pass`；`status` 用于检查模板、指南、证据包、HTML 页面和最终审核 CSV 是否就绪；`validate` 是比审计更严格的预检查，会要求审核 CSV 覆盖模板全部样本，且所有抽样行都填写可识别的 `review_pass`、`reviewer`、`evidence_match`、`confidence_1to5`；失败样本还必须填写 `reason_if_fail`。模板文件或未填写的审核 CSV 返回 `ok=false` 是预期行为，不表示代码失败。

KT2 最终验收闸门：

```powershell
python -m benchmark.completion_gate
```

当前结果：`status=incomplete`，`full_validation_complete=false`，唯一 open check 为 `role_evidence/manual_review_records`；同时生成 `benchmark/KT2_COMPLETION_GATE.json` 与 `benchmark/KT2_COMPLETION_GATE.md`。该命令用于人工审核文件填完后一键判断是否达到 KT2 full validation。

测试夹具已验证：当 scale、next-hop、KT1/PHEME role evidence 与人工审核记录都满足条件时，`benchmark.completion_gate` 会返回 `passed`；当前真实运行未通过仅因为 `role_evidence_manual_review.csv` 虽已存在但 8 条样本的 `review_pass` 仍全空。

## 10. 下一步开发清单

1. 将 CasFT 从当前 500 cascades / 1 epoch / seed=0 small-run 扩展到多观测窗口、多数据集和至少 3 个随机种子；同时对比 RF、Temporal、CasDO/ConCat fallback。
2. 将 DyGFormer/DyGLib 与 TGN 从当前 20 cascades / 1 epoch / 3 次重复 small-run 扩展为更多数据集、观测窗口和多随机种子，并解析上游 AP/AUC 到统一报告。
3. 比较 DyGFormer/DyGLib、TGN 与 ProspectiveRanker 的候选覆盖、排序指标和资源成本，确定下一跳主落地模型。
4. 将 `frontier_status.json` 从 export-only 安全快照扩展为可索引 `casft_external_attempt.json`、`dyglib_external_attempt.json`、`tgn_external_attempt.json` 的复现证据汇总。
5. 将已接入的真实 KT1 样例扩展到跨事件协同组输出，验证 `role_evidence.csv` 的覆盖率、稳定性和人工抽查结果。
6. 基于已解析的 `G:\CISCN\dataset\PHEME` 扩展证据追溯与时间线测试，并补充 sampled role-evidence 人工抽查记录；只有人工抽查通过后，角色证据才能从 `partial` 升级为 `passed`。
7. 前端继续只展示已观测事实和实验预测结果，等最终模型选择后再封装产品 API。
8. 在多数据多种子实验完成后，将 dashboard 预测面板从实验 small-run 证据升级为最终候选模型结果，并同步展示对应日志、随机种子和指标 JSON 链接。

