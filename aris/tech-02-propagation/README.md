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

当前正式预测路线收敛为 **Macro/Micro Sequence Propagation Prediction**：用同一传播序列状态同时支撑规模趋势预测和下一跳用户排序。方法论上以 MINDS 的多尺度共享表示为主干取向，吸收 FOREST 的宏微观软耦合思想，并用 CasFT 风格的连续趋势头输出未来累计趋势点。

- 规模/趋势预测：以可训练 macro head + 连续趋势 decoder 为正式实现；传统特征回归、统计时序和速度/加速度体制切换仅保留为历史对照或 ablation，不再作为系统公开预测接口。
- 多尺度扩散：MINDS、FOREST、HyperIDP 作为 macro/micro 统一建模参照。
- 下一跳预测：当前使用 next-user sampled softmax 和当前事件候选排序；Topo-LSTM、TGN、TGAT、CAW、DyGFormer、TGSL 等作为后续可替换的 temporal graph 强基线。
- 中心性、结构洞、社区桥接、传播路径证据等角色定位方法。

选择具体方法时，应优先保证任务定义清楚、无未来泄漏、能和现有 baseline 对比，而不是追求一次性实现最复杂模型。

## 当前已有资产

- `propagation_legacy.py`：传播图构建、关键角色、证据链、关键路径回溯。
- `system/backend/app/services/propagation_prediction_service.py`：正式预测方法卡、当前事件 checkpoint 推理、缓存实验结果读取。
- `system/research/propagation_analysis/benchmark/adapters/`：Macro/Micro sequence joint model 适配层，包含 DynamicCasHGNN、RelationGNN、SharedLSTM、Euler trend decoder 和 next-user sampled softmax。历史研究工作区中的同名适配器文件仅作溯源参考，不是产品运行路径。
- `core/propagation/ts_features.py`、`regime_model.py`、`trend_predictor.py`：历史速度/加速度体制切换脚手架，仅作内部对照，不再通过系统传播预测接口暴露。
- `propagation_model_service.py`、`api/v1/propagation.py`：观测分析与预测模型接口已分离，公开预测入口为当前事件 macro/micro 预测。
- 前端传播监测页面：已展示传播路径、传播对象、角色分析、时间线和趋势预测页签。

## 本轮预期交付

- 三项主功能的任务定义、数据协议和方法边界保持一致。
- 规模预测、角色定位、下一跳预测的最小工程闭环，以及 macro/micro 预测方法卡。
- 当前实现与前沿方法的差距说明。
- 可供前端和 Risk Review 消费的稳定结构化输出，但不要求一次性固定最终 API 形态。

## 成功标准

- 不把路径回溯误写成下一跳预测。
- 不把辅助能力写成主功能完成条件。
- 不把某个论文模型写成唯一实现路线。
- 每项主功能都有清楚输入、输出、评估方式和当前完成度。
