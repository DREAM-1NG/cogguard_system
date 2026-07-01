# EXPERIMENT_PLAN

## 功能定位

**所属功能**：传播监控  
**主功能**：规模预测、角色定位、下一跳预测  
**辅助能力**：时间线、证据链、范围估计、事件/内容线索、前端展示

## 总体思路

本阶段实验不绑定唯一模型。目标是为三项主功能分别建立可运行 baseline、评价协议和工程输出，允许后续组员在此基础上替换更强模型。

## 实验 1：规模预测

**任务**：给定早期观测窗口 `[0, t_obs]`，预测未来规模或方向。

候选方法：

- Naive / EWMA / moving average
- 当前 `RandomForestRegressor` baseline
- CascadeSwitch 或其它轻量时序方法
- DeepCas / DeepHawkes / CasFlow / MINDS / FOREST / HyperIDP 等文献参照

指标：

- MSLE / MAE / RMSE / MAPE
- Direction Accuracy
- 不同 `t_obs` 下的性能曲线

最低交付：

- 一个可运行 baseline
- 一个公开数据集或可解释 mock 数据协议
- 一张结果对比表

## 实验 2：角色定位

**任务**：在已观测传播图中识别协同用户和关键节点角色。

候选方法：

- degree / in-degree / out-degree
- betweenness / PageRank
- 社区桥接、传播深度、时间先后规则
- 可选图表示学习或角色分类模型

指标 / 检查：

- 每个角色是否有图结构证据
- 是否能按 KT1 协同组过滤
- 角色结果在不同子图采样下是否稳定
- 能否回溯到支撑帖子或路径

最低交付：

- 角色标签和证据结构
- 与现有 `propagation_legacy.py` 输出对齐
- 前端或报告可消费的角色摘要

## 实验 3：下一跳预测

**任务**：在 `t_obs` 时刻预测未来窗口内可能被激活的用户或传播边。

候选方法：

- 时间/中心性启发式排序
- 当前 `LogisticRegression` 候选边分类 baseline
- Topo-LSTM / DeepInf / FOREST / MINDS / HyperIDP
- TGAT / TGN / CAW / DyGFormer / TGSL 等 temporal graph 方法

指标：

- Candidate Coverage / Candidate Recall@K
- Hits@K / Recall@K / MRR / MAP / NDCG@K
- AUC / Average Precision 仅作为边分类辅助指标

最低交付：

- 无未来泄漏候选集构造说明
- 一个简单 baseline
- 一个 Top-K 排序输出

## 实验 4：Auxiliary 联动

**任务**：验证辅助能力如何服务三项主功能。

范围：

- 时间线是否支撑规模预测解释
- 证据链是否支撑角色定位
- 范围估计是否支撑态势展示
- 内容/事件线索是否能作为可选输入

最低交付：

- 不要求独立模型指标
- 只需说明辅助能力被哪项主功能消费

## 退出标准

- [ ] 三项主功能都有明确任务定义和输入输出。
- [ ] 规模预测有至少一个可运行 baseline 和误差指标。
- [ ] 角色定位有可追溯证据并能联动协同用户。
- [ ] 下一跳预测有无泄漏候选集和 Top-K 排序指标。
- [ ] Auxiliary 不被写成主功能完成条件。
