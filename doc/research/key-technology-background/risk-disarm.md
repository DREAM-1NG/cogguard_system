# 关键技术三：事件 / 叙事单元的内容风险研判

> **用途**：定义 KT3 的研究问题、当前工程落点、研究目标、实现方向和验证方式。  
> **受众**：KT3 研究实现者、风险研判/DISARM 报告模块维护者。  
> **维护规则**：只写关键技术背景与研究方案；产品接口和任务状态放入 `../../engineering/`。

## 1. 问题定义

风险研判是当前代码主线中最大的空缺模块。它需要把上游协同检测、传播归因和账户监测的结果组织成统一证据链，对事件、claim、thread 三个层级进行：

- 真实性评估
- 操纵性评估
- 危害性评估

同时还要把结果表达映射到可共享的治理语言，这里对应开题报告中的 Agent 编排与 DISARM 映射。

## 2. 当前代码基线

当前尚无 `core/risk/` 代码目录。需要新建：

- `new-system/backend/app/core/risk/`
- `new-system/backend/app/services/risk_service.py`
- `new-system/backend/app/api/v1/risk.py`
- `new-system/backend/app/schemas/risk.py`

前端只需要最小可用入口：

- `new-system/frontend/src/api/risk.ts`
- `new-system/frontend/src/views/risk/index.vue`

## 3. 第一阶段目标

第一阶段不是做大而全的智能判定，而是做 rule / evidence-driven MVP：

- claim 聚类与口径归并
- 多源证据包构建
- 三维评分框架
- DISARM 映射接口
- 结构化报告输出
- `llm_bridge.py` 仅保留桥接占位

## 4. 这一技术线要解决的核心问题

- 如何把协同、传播、账户结果收束到统一证据包
- 如何给出可复核的三维评分理由
- 如何把操纵行为表达转换为标准化 DISARM 语言
- 如何输出后续能被看板、报告、预警复用的 JSON 结构

## 5. 推荐实现方向

- 先做后端优先，不先追求完整前端
- 先规则化、证据化，再保留 LLM bridge 扩展点
- 真实性维度优先支持“可信 / 存疑 / 已证伪”
- 操纵性维度优先消费协同与传播证据
- 危害性维度优先基于事件影响面、传播强度和角色结构

## 6. 推荐验证方式

- 针对纯后端服务补单元测试与响应结构测试
- 选取 `mock_weibo` / `weibo` / `news` 的小样例验证 JSON 报告稳定性
- 验证报告字段能直接被前端与后续预警模块消费

## 7. 参考文献线索

- `Detecting Breaking News Rumors of Emerging Topics in Social Media` (IPM 2020)
- `A Unified Framework for Multi-Modal Rumor Detection via Multi-Level Dynamic Interaction with Evolving Stances` (IPM 2025)
- `End-to-End Multimodal Fact-Checking and Explanation Generation` (SIGIR 2023)
- `Adversarial Contrastive Learning for Evidence-Aware Fake News Detection With Graph Neural Networks` (TKDE 2024)
- `DISARM Red Framework`
