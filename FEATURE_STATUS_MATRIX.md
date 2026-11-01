# KT2 / F-PROP 传播监控功能状态矩阵

> 更新时间：2026-06-28
> 口径：只记录当前仓库真实落地状态，不把研究 baseline 写成产品功能完成。
> 统一入口：KT2 当前需求、状态标签与验收标准以 `KT2_REQUIREMENTS.md` 为准；本文仅保留功能完成度矩阵。
> 状态边界：`small_run_passed` 只表示上游 small-run 和证据文件存在；`full_validation_passed` 只由 `benchmark/KT2_COMPLETION_GATE.md` 判定。当前 KT2 full validation 仍未通过。

| 功能 | 当前状态 | 已有实现 | 当前边界 | 下一步 |
|---|---|---|---|---|
| 传播分析 | 已落地 | `propagation.analysis`、`propagation.cli analyze` | 支持规模、深度、宽度、时间序列、增长率、结构指标 | 持续补真实数据集覆盖率审计 |
| 传播路径/证据链 | 已落地 | `propagation.analysis`、`propagation.reporting`、dashboard artifacts | 解释已观测传播路径，不预测未来路径 | 用真实 KT1 协同组做跨事件验证 |
| 协同用户角色判定 | 最小闭环已落地 | 中心性、影响力、桥接、起爆点规则、`role_evidence.csv`、CLI `--coordination-file` | 工程启发式，不是监督学习角色分类器；当前只解释已观测图 | 增加真实协同组稳定性检查 |
| 引爆点检测 | 已落地 | 增长率突变与结构指标 | 基于已观测数据的启发式检测 | 增加阈值可配置与事件级解释 |
| 规模预测 baseline | 已落地 baseline | `TemporalSizeBaseline`、`RandomForestRegressor`、MINDS、`HyperIDPProtocolProxy`、`HyperIDPAdversarialProxy`、`benchmark/adapters/rf_baseline.py` | TemporalSizeBaseline 是固定时间窗 naive 外推；RF/HyperIDP proxy 是序列比例观测窗监督 baseline，不包含 CascadeSwitch/事件体制切换；MINDS Christianity 已完成 30 epochs 验证集选 epoch 后测试评估；FOREST 不产出宏观 MSLE | 扩展 MINDS douban/android 数据，补固定时间窗强模型 |
| 下一节点/下一跳预测 baseline | 研究验证中 | `ProspectiveRanker`、`ProspectiveHeuristic`、`LR_EdgeClassifier`、`HyperIDPProtocolProxy`、`HyperIDPAdversarialProxy`、MINDS、FOREST benchmark adapter | ProspectiveRanker/HyperIDP proxy 是严格不注入未来节点的学习排序 sanity baseline；ProspectiveHeuristic 是非学习 baseline；LR 是离线候选边分类；MINDS Christianity 和 FOREST douban 均已完成 30 epochs；FOREST 为 sequence-only 且 loss 为 nan，不是产品 API | 接入更强 temporal graph/GNN 排序模型；获取 MINDS douban/android 数据后补跨数据集对齐 |
| 前沿复现目标 | `small_run_passed`，`full_validation_not_passed` | 外部仓库已 clone 到 `G:\CISCN\CogGuard\subsystems\kt2_repos`；`benchmark/adapters/casft_runner.py`、`benchmark/adapters/temporal_graph_runner.py`；`benchmark.run_benchmark` 已接入 CasFT、DyGFormer/DyGLib、TGN | 当前可导出 CasFT `dataset.txt` 和 temporal edge stream；CasFT 已完成 `frontier_reproduction_small_run`（500 cascades, 1 epoch, seed=0, CPU Windows shim）；DyGFormer/DyGLib、TGN 已完成 `frontier_reproduction_small_run`（20 cascades, 1 epoch, seed=0, num_runs=3）。这些都不是多随机种子 full-run 或产品级最终模型 | 扩展 CasFT/DyGLib/TGN 到更多数据集、观测窗口和多随机种子；补齐最终模型选择 |
| HyperIDP 参考/proxy | 最小协议支架已落地 | `HyperIDPProtocolProxy`、`HyperIDPAdversarialProxy`、`benchmark/REPRODUCTION_REPORT.md` | 只是 protocol proxy，不是原论文架构复现 | 仅作为多尺度参考或 proxy baseline |
| 前端传播监控页 | 静态报告已落地 | `propagation.visualization` 生成 `dashboard.html` | 无独立前端应用；预测结果必须标注实验性质 | 展示已观测图角色/证据链、协同角色证据和实验预测面板 |

## 验收口径

- “已落地”只用于可通过 CLI 或报告稳定复现的能力。
- “baseline”只表示研究或离线实验可运行，不等于 KT2 核心研究功能完成。
- 下一节点预测必须同时报告候选覆盖和排序质量；仅 AUC/AP 不能视为产品级完成。
- 当前 ProspectiveHeuristic / ProspectiveRanker 已提供无未来节点注入的候选覆盖/排序 sanity baseline，但仍不是最终产品预测模型。
- 当前 TemporalSizeBaseline 已提供简单时间外推 sanity baseline，用于满足规模预测的 naive/moving-average 类对照要求。
- 当前 MINDS Christianity 与 FOREST douban 已有 30 epochs 可复现实验结果；FOREST 因 DeepWalk 嵌入缺失为 sequence-only，训练 loss 为 nan，应谨慎解释。
- 当前 HyperIDPProtocolProxy / HyperIDPAdversarialProxy 只是协议级代理模型，不等于 HyperIDP 原论文架构复现。
- 当前 CasFT、DyGFormer/DyGLib 与 TGN 已有 small-run 日志、随机种子和 schema 结果，可写为 `frontier_reproduction_small_run`；这不是多随机种子 full-run，也不能写成前沿复现正式完成或产品级最终模型。
