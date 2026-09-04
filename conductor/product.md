# Product

## Product

**CogGuard** 是面向分析人员的跨平台协同操纵证据发现、传播分析和风险研判原型。

## Problem

跨平台事件的内容、账户、传播关系和研判记录分散，分析人员难以从可复现证据形成可审计结论。

## Approach

产品遵循 `事件 -> 证据 -> 协同 -> 传播 -> 风险 -> 处置`：以 **Event Snapshot** 固化输入，以 **Analysis Run** 执行分析，以 **Event Review Case** 承载人工研判和最终决策。

## Users

- **Analyst**：运行分析、检查证据、请求复核建议并形成研判决策。
- **Administrator**：管理模型激活、运行配置、用户和系统治理。
- **Viewer**：查看已授权的分析与研判结果。

## Core Capabilities

- Crawler 与 Event Snapshot 数据入口。
- Coordination Discover / Coordination Detect。
- Propagation Monitoring，包括 Observed Propagation Analysis 与受治理的 Propagation Forecast。
- Preliminary Finding、Review Advisory、Canonical Verdict 审批与 Confirmed Decision。
- Event Review Case、证据标注、复核请求和活动流。

## Current Goal

`final-architecture` track 在不新增产品功能、不改变现有 V1/V2 HTTP 契约的前提下，整理发布表面、深化内部 module、统一 Student Review 主线并完成面向 `release-0.2` 的可审查 PR。
