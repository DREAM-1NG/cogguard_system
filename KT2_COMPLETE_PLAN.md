# KT2 / F-PROP 传播监控后续实现计划

> 更新时间：2026-06-28
> 当前阶段：baseline 与实验协议已搭建，前沿复现和系统落地继续推进。
> 统一入口：KT2 当前需求、状态标签与验收标准以 `KT2_REQUIREMENTS.md` 为准；本文仅保留阶段计划。
> 状态边界：`small_run_passed` 不等于 `full_validation_passed`。当前 full validation 仍为 `false`，以 `benchmark/KT2_COMPLETION_GATE.md` 为准。

## 当前定位

KT2 传播监控模块固定围绕三项主功能推进：

1. **规模预测**：给定早期观测窗口，预测未来或最终传播规模。
2. **协同用户角色定位与证据追溯**：对 KT1 已判定协同用户，在已观测传播图中解释其起爆、桥接、放大或二级扩散角色。
3. **下一跳预测**：在不注入未来真实节点的前提下，预测未来时间窗内可能被激活的用户或传播边。

当前实现不能写成 KT2 完成。更准确的状态是：基础传播分析、baseline、proxy 和部分公开代码 adapter 已落地；CasFT、DyGFormer/DyGLib 与 TGN 已完成 small-run 证据；跨事件协同角色验收、正式多数据多种子复现和产品 API 仍待开发。

## 模型路线

本轮不设置唯一主复现模型。各路线定位如下：

| 路线 | 作用 | 当前状态 |
|---|---|---|
| CasFT / ConCat / CasDO | 规模预测前沿候选 | CasFT 仓库已 clone，CasFT 格式导出 adapter 与上游 small-run 已接入；当前 CasFT small-run 是 500 cascades / 1 epoch / seed=0 / CPU Windows shim，仍不是多数据多种子 full-run |
| DyGFormer / DyGLib / TGN | 下一跳 temporal graph 强模型候选 | DyGFormer/DyGLib 与 TGN 均已完成 20 cascades / 1 epoch / 3 次重复 small-run；temporal edge stream 导出与无未来节点候选协议已接入；仍不是多随机种子 full-run |
| MINDS / FOREST | 多尺度公开代码 baseline | 已有 adapter 和部分结果，数据覆盖仍需补齐 |
| RF / Temporal / ProspectiveRanker | 本地 sanity baseline | 已落地，用于下限对比 |
| HyperIDP | 多尺度论文参考 | 当前只有 protocol proxy，不是原架构复现 |

## 分阶段计划

| 阶段 | 目标 | 交付物 | 完成标准 |
|---|---|---|---|
| P0 | 修正文档和协议口径 | 状态矩阵、标准级联协议、benchmark task 分组 | 不再写“request 已闭环完成”或“唯一主复现目标” |
| P1 | 协同角色证据闭环 | `role_evidence.csv`、KT1 协同用户过滤、dashboard 证据表 | 给定协同用户集合后，只优先展示相关用户角色与证据链 |
| P2 | 规模预测前沿复现 | CasFT small-run、数据适配报告、与 RF/Temporal 对比 | `small_run_passed`：CasFT 已跑通；`full_validation_not_passed`：仍需多窗口、多数据、多种子的 MSLE/MAE/RMSE/MAPE/Direction Accuracy 曲线 |
| P3 | 下一跳前沿复现 | DyGFormer/DyGLib 与 TGN 3 次重复 small-run 已完成；继续扩展更多数据集、观测窗口和多随机种子并比较落地性 | `small_run_passed`：DyGLib/TGN 已跑通；`full_validation_not_passed`：仍需 Candidate Recall、Hits@K、MAP@K、MRR、NDCG@K 与上游训练 AP/AUC 的正式对比 |
| P4 | 系统展示集成 | dashboard/前端实验预测面板 | 预测结果带模型名、观测窗口和“实验预测”标识 |

## 当前禁止项

- 不把 LR 离线边分类 AUC/AP 写成线上下一跳预测完成。
- 不把 ProspectiveHeuristic / ProspectiveRanker 写成最终模型。
- 不把 RF 或 TemporalSizeBaseline 写成规模预测主模型。
- 不把 FOREST sequence-only 30 epochs 写成完整论文复现结果。
- 不把 HyperIDPProtocolProxy / HyperIDPAdversarialProxy 写成 HyperIDP 原论文架构复现。
- 不把 CasFT、DyGFormer/DyGLib 或 TGN 写成 full-run 或产品级已完成。当前三者只能按已有日志写为 `frontier_reproduction_small_run`。

## 本地复现目录

- 外部复现仓库统一位于 `G:\CISCN\CogGuard\subsystems\kt2_repos`：CasFT `ebb7e8e`、DyGLib `3aacc36`、TGN `d55bbe6`、FOREST `637c748` 等。
- 数据仓库位于 `G:\CISCN\dataset`：Twitter15/16 `6a33ebd`、Rumor_RvNN `6d3bb25`。PHEME 已下载并解压到 `G:\CISCN\dataset\PHEME`，当前审计脚本已解析 5 个样例事件用于时间线与角色证据验证。
- 现阶段 benchmark 可运行 export-only 命令生成 CasFT `dataset.txt` 与 DyGLib/TGN temporal edge stream；CasFT、DyGLib/TGN 显式 external small-run 均已记录为 `frontier_reproduction_small_run`。
