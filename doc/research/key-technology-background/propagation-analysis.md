# 关键技术二：传播监控

> **用途**：定义 KT2 的研究问题、当前工程落点、研究目标、实现方向和验证方式。  
> **受众**：KT2 研究实现者、传播监控模块维护者、答辩材料编写者。  
> **维护规则**：只写关键技术背景与研究方案；产品接口和任务状态放入工程文档。

> 方向更新（2026-06-23）：KT2 主功能收敛为 **规模预测 + 角色定位 + 下一跳预测**。传播时间线、证据链、范围估计、立场/危害/情感线索、影响力指数和前端可视化均为 auxiliary。方法层不绑定 CascadeSwitch、HyperIDP 或任何单一模型，允许根据数据条件选择轻量启发式、传统模型、图模型、多尺度扩散模型或组合方案。

## 1. 问题定义

KT2 要回答的核心问题是：**一个传播事件接下来会扩散到多大，关键协同用户在传播中扮演什么角色，下一步可能传播到哪里。**

- **规模预测**：给定早期观测窗口 `[0, t_obs]`，预测未来 `t_pred` 或最终时刻的传播规模、方向和可选置信度。
- **角色定位**：对已经参与传播且已被 KT1 判定为协同的用户，识别起爆、桥接、扩散、放大等角色，并给出图结构或证据链依据。
- **下一跳预测**：在不使用未来真实节点或真实边的条件下，预测未来窗口内最可能被激活的用户或传播边。
- **辅助能力**：传播子图、时间线、源头追溯、证据链、范围估计、内容线索和前端可视化，为三项主功能提供解释和展示支撑。

严格区分两类路径能力：

- **路径回溯 / 证据追溯**：在已观测传播图上解释过去发生了什么，当前已有实现基础。
- **下一跳 / 路径预测**：在观测窗口结束时预测未来会发生什么，当前仍需补齐无泄漏候选生成和排序协议。

## 2. 当前代码基线

当前代码落点：

- `new-system/backend/app/core/propagation_legacy.py`：传播子图、关键角色、证据链、关键路径回溯。
- `new-system/backend/app/core/propagation/`：时序特征、事件上下文、体制模型、趋势预测等规模预测基础实现。
- `new-system/backend/app/services/propagation_service.py`
- `new-system/backend/app/api/v1/propagation.py`

当前已实现或已有基础：

- 传播图构建、时间线、关键角色、证据链、关键路径回溯。
- 规模/趋势预测相关特征和轻量预测流程。
- 前端传播监控页的部分展示能力。

当前需要补齐：

- 规模预测在公开数据集上的基准验证和与 baseline 的对比。
- 角色定位与 KT1 协同用户集合的显式联动。
- 下一跳预测的候选集构造、排序模型和无未来泄漏评估协议。
- 辅助能力与主功能的边界说明，避免把内容分析或前端展示写成主功能本体。

## 3. 方法空间

KT2 不预设唯一技术路线。可选方法包括：

- **规模预测**：随机森林、统计外推、Hawkes/点过程、CascadeSwitch、CasFlow、CasFT、ConCat、CasDO、HyperIDP、MINDS、FOREST 等。
- **角色定位**：degree、betweenness、PageRank、结构洞、社区桥接、传播路径证据、协同组条件化角色规则或学习模型。
- **下一跳预测**：逻辑回归排序、Topo-LSTM、DeepInf、FOREST、MINDS、HyperIDP、TGAT、TGN、CAW、DyGFormer、TGSL 等。

工程落地可以分阶段推进：先保证启发式和传统 baseline 可跑，再逐步接入更强模型。方法创新空间包括但不限于协同用户条件化预测、多尺度联合建模、证据链可解释角色定位、低资源数据下的下一跳候选生成。

## 4. 推荐验证方式

- 用 `mock_weibo` 验证接口、前端和证据链展示不回归。
- 用公开传播树或级联数据验证规模预测和下一跳预测。
- 用 KT1 输出的协同群组验证角色定位能否按协同用户过滤和解释。
- 每项预测任务都报告观测窗口、预测窗口、数据划分方式和是否存在未来泄漏。

## 5. 参考文献线索

- `HyperIDP: Customizing Temporal Hypergraph Neural Networks for Multi-Scale Information Diffusion Prediction` (COLING 2025)
- `Enhancing Multi-Scale Diffusion Prediction via Sequential Hypergraphs and Adversarial Learning` (AAAI 2024)
- `FOREST: Multi-scale Information Diffusion Prediction with Reinforced Recurrent Networks` (IJCAI 2019)
- `DeepCas: An End-to-end Predictor of Information Cascades` (WWW 2017)
- `DeepHawkes: Bridging the Gap between Prediction and Understanding of Information Cascades` (CIKM 2017)
- `Topological Recurrent Neural Network for Diffusion Prediction` (ICDM 2017)
- `Temporal Graph Networks for Deep Learning on Dynamic Graphs` (2020)
- `Provenance for Online Information Diffusion` (2018)
- `Rumor Detection on Social Media with Bi-Directional Graph Convolutional Networks` (AAAI 2020)
