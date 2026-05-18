# 关键技术一：多行为协同网络构建与群体发现

> **用途**：定义 KT1 的研究问题、当前工程落点、研究目标、实现方向和验证方式。  
> **受众**：KT1 研究实现者、协同检测模块维护者。  
> **维护规则**：只写关键技术背景与研究方案；产品接口和任务状态放入 `../../engineering/`。

## 1. 问题定义

当前系统已经具备“基于共享对象的协同检测”能力，但还没有真正落到开题报告中的多行为异构协同图。要补的是：

- 时间同步
- 共链接
- 共媒体
- 语义近似
- 传播互动

目标不是再做一套独立的机器人检测，而是在事件窗口内构建证据驱动的协同网络，并通过显著性筛查区分自然共振与人为协同。

## 2. 当前代码基线

当前代码落点：

- `new-system/backend/app/core/coordination/`
- `new-system/backend/app/services/coordination_service.py`
- `new-system/backend/app/api/v1/coordination.py`

当前已实现：

- 时间窗口内共享行为配对
- 加权无向图生成
- 账户级 / 群体级统计
- 网络序列化与前端可视化

当前未实现：

- 五类多行为边统一构建
- 边类型融合与权重设计
- 显著性筛查
- 更强的证据样本输出

## 3. 这一技术线要解决的核心问题

- 如何把不同类型的协同行为边统一投影到账号协调图
- 如何避免热点事件下的正常同步被误报
- 如何输出可解释的边类型证据，而不只是一个黑盒分数

## 4. 推荐实现方向

- 保持 pandas / numpy / networkx 的轻量路线，优先完成可解释 MVP
- 先做规则与统计驱动的多行为边，不直接引入重型图神经网络训练
- 语义近似可以先用句向量或相似度阈值，后续再考虑更复杂模型
- 显著性筛查优先采用基线、模板降权、关系稀有度等统计策略

## 5. 推荐验证方式

- `mock_weibo`：验证边类型拼接、统计逻辑和回归测试
- `weibo`：验证真实采集样例上的误报/漏报模式
- `news`：验证跨来源场景下共享链接与资源复用信号

建议重点补充：

- 多行为边构建的单元测试
- 显著性筛查的回归测试
- 响应结构变更时的最小前端兼容检查

## 6. 参考文献线索

- `CatchSync` / `TKDD 2016`
- `Identifying Coordinated Accounts on Social Media through Hidden Influence and Group Behaviours` (KDD 2021)
- `Temporal Dynamics of Coordinated Online Behavior` (PNAS 2024)
- `Exposing Cross-Platform Coordinated Inauthentic Activity in the Run-Up to the 2024 U.S. Election` (WWW 2025)
