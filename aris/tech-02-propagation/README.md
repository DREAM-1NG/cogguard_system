# 技术线 02：传播监控

## 功能定位

**所属功能**：传播监控（三大功能之二）  
**主功能**：规模预测、角色定位、下一跳预测  
**辅助能力**：传播时间线、证据链、范围估计、事件/内容/风险线索、前端可视化、Risk Review 结构化输出

传播监控模块不再绑定为某一个固定算法或单一路线。当前定位是：围绕传播事件的早期观测数据和 Coordination Discover 协同结果，判断事件会扩散到多大、关键用户在传播中扮演什么角色、下一步可能传播到哪里；其它能力作为解释、展示或下游联动的 auxiliary。

## 目标

- **规模预测**：基于早期观测窗口预测后续传播规模、方向和可能的不确定性。
- **角色定位**：在已观测传播图中识别起爆、桥接、扩散、放大等关键角色，并能追溯证据。
- **下一跳预测**：在不使用未来信息的条件下，预测下一批可能被激活的用户或传播边。
- **辅助支撑**：保留传播子图、时间线、证据链和范围估计，并为 Risk Review 报告研判提供结构化输入。

## 必读文档

- [`request.md`](request.md) — 当前主定位与研究开发请求
- [`REQUIREMENTS.md`](REQUIREMENTS.md) — 功能级需求与工程边界
- [`ACCEPTANCE.md`](ACCEPTANCE.md) — 验收标准
- [`FEATURE_STATUS_MATRIX.md`](FEATURE_STATUS_MATRIX.md) — 功能清单与完成度
- [`../../doc/research/key-technology-background/propagation-analysis.md`](../../doc/research/key-technology-background/propagation-analysis.md) — 对外研究背景口径

## 方法空间

可选技术包括但不限于：

- 传统特征回归、统计时序、点过程、CascadeSwitch 等轻量规模预测方法。
- HyperIDP、MINDS、FOREST 等多尺度扩散预测模型。
- Topo-LSTM、TGN、TGAT、CAW、DyGFormer、TGSL 等下一跳或 temporal graph 方法。
- 中心性、结构洞、社区桥接、传播路径证据等角色定位方法。

选择具体方法时，应优先保证任务定义清楚、无未来泄漏、能和现有 baseline 对比，而不是追求一次性实现最复杂模型。

## 当前已有资产

- `propagation_legacy.py`：传播图构建、关键角色、证据链、关键路径回溯。
- `core/propagation/ts_features.py`、`regime_model.py`、`trend_predictor.py`：规模/趋势预测相关基础实现。
- `propagation_service.py`、`api/v1/propagation.py`：服务层和接口雏形。
- 前端传播监控页面：已可展示部分已落地分析结果。

## 本轮预期交付

- 三项主功能的任务定义、数据协议和 baseline 对齐。
- 规模预测、角色定位、下一跳预测的最小可运行实验或工程闭环。
- 当前实现与前沿方法的差距说明。
- 可供前端和 Risk Review 消费的稳定结构化输出，但不要求一次性固定最终 API 形态。

## 成功标准

- 不把路径回溯误写成下一跳预测。
- 不把辅助能力写成主功能完成条件。
- 不把某个论文模型写成唯一实现路线。
- 每项主功能都有清楚输入、输出、评估方式和当前完成度。
