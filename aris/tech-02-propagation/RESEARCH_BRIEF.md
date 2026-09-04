# RESEARCH_BRIEF

> 方向对齐说明（2026-06-23）：
> - Propagation Analysis / F-PROP 的主功能收敛为 **规模预测 + 角色定位 + 下一跳预测**。
> - 传播时间线、证据链、范围估计、立场/危害/情感线索、影响力指数和前端可视化均作为 auxiliary，不作为主功能完成的前置条件。
> - CascadeSwitch、HyperIDP、MINDS、FOREST、Topo-LSTM、TGN 等是方法候选或 baseline，不是唯一指定路线。
> - 已观测图上的关键路径回溯是证据追溯，不等同于预测未来下一跳。

## Problem Statement

传播监控模块要回答三个核心问题：

1. **规模预测**：事件在未来会扩散到多大，传播方向是否上升、平稳或衰减。
2. **角色定位**：已经参与传播的协同用户分别扮演起爆、桥接、扩散、放大等什么角色，证据是什么。
3. **下一跳预测**：在当前观测窗口结束时，下一批可能被激活的用户或传播边是什么。

这三个问题可以由同一个多尺度扩散模型统一建模，也可以由多个轻量模型组合完成。当前文档不预设唯一算法，鼓励组员在任务定义清楚、评价无泄漏、工程可落地的前提下做方法创新。

## Background

- 当前项目是面向网络舆论对抗的跨平台协同攻击监测系统。
- 当前代码已有传播子图、时间线、角色识别和证据链提取能力。
- 当前规模预测已有轻量 baseline 和 CascadeSwitch 类实现基础，但公开数据集评估仍需补齐。
- 当前下一跳预测只有离线候选边分类雏形，尚未形成产品级前瞻预测。
- 当前角色定位可基于传播图中心性和证据链落地，但需要与协同用户集合更紧密联动。

## Constraints

- 默认不重写 Coordination Discover 协同检测、Risk Review 报告研判和账号画像模块。
- 不要求一次性实现完整动态图神经网络训练；可以从启发式、传统模型或开源 baseline 起步。
- 不要求把 auxiliary 能力全部做完后才推进主功能。
- 任一预测任务都必须说明观测窗口、预测窗口、候选集来源和是否存在未来泄漏。

## What We Are Looking For

- 对规模预测、角色定位、下一跳预测分别给出最小可运行方案。
- 建立三项主功能对应的 baseline 和评价指标。
- 将已有传播图、时间线、证据链能力纳入角色定位和报告解释链路。
- 为后续前端展示和 Risk Review 消费保留结构化输出，但不提前锁死 API 字段。

## Domain Knowledge

- 上游输入来自 Coordination Discover 协同发现结果和采集数据。
- 规模预测对应 macroscopic cascade / popularity prediction。
- 下一跳预测对应 microscopic diffusion prediction / temporal link prediction。
- 角色定位对应 observed propagation graph 上的 role identification / provenance。
- LLM 可以作为事件抽取、解释生成、辅助分类工具，但不应被默认为唯一预测模型。

## Non-Goals

- 不把立场检测、危害评估、情感分析作为 Propagation Analysis 主功能。
- 不把路径回溯冒充未来路径预测。
- 不把某个论文模型指定为最终系统模型。
- 不做通用 LLM 对话系统。

## Evaluation Focus

- 规模预测：MSLE、MAE、RMSE、MAPE、Direction Accuracy。
- 角色定位：角色证据完整性、协同用户覆盖、中心性/路径证据可解释性。
- 下一跳预测：Candidate Coverage、Hits@K、Recall@K、MRR、MAP、NDCG@K。
- 工程验证：接口稳定、mock 数据可回归、前端只展示已落地能力。
