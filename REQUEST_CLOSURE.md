# KT2 request.md 阶段状态说明

> 更新时间：2026-06-28
> 文档状态：ARCHIVE / STAGE SNAPSHOT。本文只保留历史 request 的阶段落实记录，不再作为活动需求源或完成状态真值。
> 口径：本文件记录 `request.md` 的当前落实状态，不把 baseline、proxy 或协议搭建写成前沿模型复现完成。
> 统一入口：KT2 当前需求、状态标签与验收标准以 `KT2_REQUIREMENTS.md` 为准；本文仅保留 request.md 阶段闭环说明。
> 说明：历史 `request.md` 已被 `KT2_REQUIREMENTS.md` 吸收为统一需求入口；当前目录不再把独立 `request.md` 作为状态真值源。
> 当前覆盖：本文中关于前沿复现的早期阶段表述已由 `benchmark/KT2_EXPERIMENT_AUDIT.json/.md` 更新；当前最高审计状态是 CasFT、DyGFormer/DyGLib 与 TGN 均为 `frontier_reproduction_small_run`，KT2 全量验证仍为 `incomplete`，关键开放项为角色证据人工抽查。

## 当前结论

`request.md` 要求的任务定义、baseline 验证、无泄漏协议和前沿仓库数据适配入口已经部分落地；**CasFT 规模预测 small-run 已完成但不是 full-run，KT1 协同用户跨事件稳定性与人工验收、产品化规模预测/下一跳 API 尚未完成**。下一跳方向已有 DyGFormer/DyGLib 与 TGN 上游 small-run 证据，但仍不是 full-run 或产品级最终模型。

当前仓库已经具备：

| 验收项 | 当前状态 | 证据 |
|---|---|---|
| 明确三项主功能边界 | 已完成 | `FEATURE_STATUS_MATRIX.md`、`KT2_COMPLETE_PLAN.md` |
| 不预设唯一主复现模型 | 已修正口径 | HyperIDP 改为多尺度参考；CasFT、MINDS/FOREST、DyGFormer/DyGLib、Topo-LSTM/TGN 作为候选路线 |
| 标准级联协议导出 | 已落地最小接口 | `propagation.protocol.export_standard_cascades`、CLI `--export-protocol` |
| 协同用户角色过滤 | 已落地最小接口 | CLI `--coordination-file`、`role_evidence.csv` |
| 规模预测 baseline | 已落地 baseline | RF、TemporalSizeBaseline、MINDS、HyperIDP proxy |
| 下一跳无泄漏 baseline | 已落地 baseline | ProspectiveHeuristic、ProspectiveRanker；旧 LR 标注为 offline edge classifier |
| 多尺度公开代码 adapter | 部分完成 | MINDS Christianity、FOREST douban sequence-only |
| 前沿复现目标 | 阶段快照已被当前审计更新 | CasFT、DyGFormer/DyGLib 与 TGN 均已完成 small-run；不得写成多随机种子 full-run 或产品级完成 |
| 前端展示口径 | 已修正 | dashboard 增加“实验预测”面板和协同角色证据表，不把预测写成确定事实 |

## 已有实验结果应如何解释

| 模型 | 类型 | 当前解释 |
|---|---|---|
| RF_Baseline / TemporalSizeBaseline | local baseline | 规模预测下限与 sanity check |
| ProspectiveHeuristic / ProspectiveRanker | local baseline | 下一跳候选覆盖与排序 sanity check |
| MINDS / FOREST | public-code adapter | 可运行公开代码 baseline；数据和配置仍未完全覆盖 |
| HyperIDPProtocolProxy / HyperIDPAdversarialProxy | protocol proxy | 只验证 macro/micro 协议和代理训练链路，不是 HyperIDP 原论文架构 |
| CasFT / DyGFormer-DyGLib / TGN | mixed frontier status | CasFT、DyGFormer/DyGLib 与 TGN 均可写为 `frontier_reproduction_small_run`；其中 CasFT 是 500 cascades / 1 epoch / seed=0 / CPU Windows shim，DyGLib/TGN 的 `num_runs=3` 是重复 small-run 证据，不是多随机种子 full-run，也不能写成产品级最终模型 |

## 仍需落实

- 规模预测主线：将 CasFT small-run 扩展为公开数据集、多观测窗口、多随机种子的正式实验，并保留同级 fallback 对照。
- 下一跳预测主线：将已跑通的 DyGFormer/DyGLib 与 TGN small-run 扩展到更多数据集、观测窗口和资源成本比较，确定最终主模型。
- 复现准备主线：已 clone 外部仓库到 `G:\CISCN\CogGuard\subsystems\kt2_repos`，已 clone Twitter15/16 与 Rumor_RvNN 到 `G:\CISCN\dataset`；PHEME 已下载并可被审计脚本解析样例事件。
- 协同角色闭环：真实 KT1 本地样例已接入并生成 `role_evidence.csv`，已生成待填写人工抽查模板，仍需扩展到跨事件协同组、PHEME 时间线验证和真实人工抽查。
- 产品化 API：在模型选择完成前，只保留实验输出和 dashboard 标注，不提供“确定性预测”接口。

## 后续工程化入口

进入产品集成阶段前，只展示已观测图分析、协同角色证据和带实验标识的预测结果。所有 next-user / size prediction 输出必须标注模型名、观测窗口、候选覆盖或误差指标，并说明是否为 baseline、public-code adapter、proxy 或 frontier reproduction。
