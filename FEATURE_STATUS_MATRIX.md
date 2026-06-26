# KT2 / F-PROP 传播监控功能状态矩阵

> 更新时间：2026-06-26  
> 口径：只记录当前仓库真实落地状态，不把研究 baseline 写成产品功能完成。

| 功能 | 当前状态 | 已有实现 | 当前边界 | 下一步 |
|---|---|---|---|---|
| 传播分析 | 已落地 | `propagation.analysis`、`propagation.cli analyze` | 支持规模、深度、宽度、时间序列、增长率、结构指标 | 持续补真实数据集覆盖率审计 |
| 传播路径/证据链 | 已落地 | `propagation.analysis`、`propagation.reporting`、dashboard artifacts | 解释已观测传播路径，不预测未来路径 | 与协同用户集合显式联动 |
| 参与者角色判定 | 已落地 | 中心性、影响力、桥接、起爆点规则 | 工程启发式，不是监督学习角色分类器 | 增加协同用户过滤与稳定性检查 |
| 引爆点检测 | 已落地 | 增长率突变与结构指标 | 基于已观测数据的启发式检测 | 增加阈值可配置与事件级解释 |
| 规模预测 baseline | 已落地 baseline | `TemporalSizeBaseline`、`RandomForestRegressor`、MINDS、`HyperIDPProtocolProxy`、`HyperIDPAdversarialProxy`、`benchmark/adapters/rf_baseline.py` | TemporalSizeBaseline 是固定时间窗 naive 外推；RF/HyperIDP proxy 是序列比例观测窗监督 baseline，不包含 CascadeSwitch/事件体制切换；MINDS Christianity 已完成 30 epochs 验证集选 epoch 后测试评估；FOREST 不产出宏观 MSLE | 扩展 MINDS douban/android 数据，补固定时间窗强模型 |
| 下一节点/下一跳预测 baseline | 研究验证中 | `ProspectiveRanker`、`ProspectiveHeuristic`、`LR_EdgeClassifier`、`HyperIDPProtocolProxy`、`HyperIDPAdversarialProxy`、MINDS、FOREST benchmark adapter | ProspectiveRanker/HyperIDP proxy 是严格不注入未来节点的学习排序 sanity baseline；ProspectiveHeuristic 是非学习 baseline；LR 是离线候选边分类；MINDS Christianity 和 FOREST douban 均已完成 30 epochs；FOREST 为 sequence-only 且 loss 为 nan，不是产品 API | 接入更强 temporal graph/GNN 排序模型；获取 MINDS douban/android 数据后补跨数据集对齐 |
| HyperIDP 主复现 | 最小协议支架已落地 | `HyperIDPProtocolProxy`、`HyperIDPAdversarialProxy`、`benchmark/REPRODUCTION_REPORT.md` | 论文标注的 GitHub URL 当前公开访问为 404；已实现 temporal coactivation hyperedge proxy、macro/micro 双头与 gradient-reversal task adversary，但尚未实现 HyperIDP 的 temporal hypergraph NAS | 基于论文复现核心 NAS 模块，或在官方仓库可访问后替换为原始实现 |
| 前端传播监控页 | 静态报告已落地 | `propagation.visualization` 生成 `dashboard.html` | 无独立前端应用；不得展示未完成 next-hop 为已完成功能 | 展示已观测图角色/证据链，隐藏或标注预测 baseline |

## 验收口径

- “已落地”只用于可通过 CLI 或报告稳定复现的能力。
- “baseline”只表示研究或离线实验可运行，不等于 KT2 核心研究功能完成。
- 下一节点预测必须同时报告候选覆盖和排序质量；仅 AUC/AP 不能视为产品级完成。
- 当前 ProspectiveHeuristic / ProspectiveRanker 已提供无未来节点注入的候选覆盖/排序 sanity baseline，但仍不是最终产品预测模型。
- 当前 TemporalSizeBaseline 已提供简单时间外推 sanity baseline，用于满足规模预测的 naive/moving-average 类对照要求。
- 当前 MINDS Christianity 与 FOREST douban 已有 30 epochs 可复现实验结果；FOREST 因 DeepWalk 嵌入缺失为 sequence-only，训练 loss 为 nan，应谨慎解释。
- 当前 HyperIDPProtocolProxy / HyperIDPAdversarialProxy 只是协议级代理模型，不等于 HyperIDP 原论文架构复现。
