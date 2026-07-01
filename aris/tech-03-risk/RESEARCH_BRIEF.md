# RESEARCH_BRIEF

## Problem Statement

项目重新定位后，关键技术三从"Phase-Aware Hazard + DISARM + D-S Fusion（规则型）"转向 **Agent + RAG 攻击分析与报告生成**。

旧有的报告生成和风险模块通常作为分类的可解释性支撑，但在本项目中，我们意图使用 Agent + RAG，显式利用协同发现（KT1）和传播监控（KT2）所生成的结果，进行深度攻击分析并生成结构化报告。

## Background

- 当前项目是面向网络舆论对抗的跨平台协同攻击监测系统
- 当前 `core/risk/` 已有规则型 MVP（1340 行：evidence_builder, phase_detector, ds_fusion, disarm_scorer, report_builder）
- 规则型方案作为 v1 归档，v2 转向 Agent+RAG
- DISARM 知识从独立规则引擎转为 RAG 知识库的一部分
- 上游已有协同发现（KT1）和传播监控（KT2）两个可复用模块

## Constraints

- 必须基于 `release-0.2`
- 只修改本技术线允许的路径
- Agent 框架需要 LLM API 支持（通义千问/智谱/DeepSeek）
- RAG 需要向量数据库或轻量检索方案
- 优先后端实现，前端只做最小入口

## What I'm Looking For

- 设计 Agent 编排框架（消费 KT1+KT2 结构化输出）
- 构建 RAG 知识库（DISARM 战术/技术 + 历史案例 + 外部证据）
- 实现攻击分析推理链
- 实现结构化报告生成
- 实现处置建议与预警

## Differentiation from v1 (Rule-based) Approach

| 维度 | v1 规则型（已归档） | v2 Agent+RAG（当前） |
|------|-------------------|---------------------|
| 核心方法 | 规则+统计+图结构 | Agent+RAG+LLM |
| DISARM 使用 | 独立规则引擎 | RAG 知识库 |
| 上游消费 | evidence_builder 手工特征 | Agent 直接消费结构化 JSON |
| 报告生成 | 模板填充 | LLM 生成+模板约束 |
| 可扩展性 | 需手工添加规则 | 知识库可持续扩充 |

## Domain Knowledge

- Agent 是核心编排层，不是附属桥接
- RAG 提供领域知识增强（DISARM、历史案例）
- 显式消费 KT1 和 KT2 的结构化输出是核心设计原则
- 报告必须可审计、可追溯

## Non-Goals

- 不做完整的 LLM 多智能体运行时
- 不做全面的事实核查检索平台
- 不一次性补齐预警中心、报告中心和看板
- 不回头重写协同发现、传播监控核心逻辑

## Existing Results

- `core/risk/evidence_builder.py` — 概念可复用（消费上游结果模式）
- `core/risk/disarm_scorer.py` — DISARM 知识可转为 RAG 语料
- `core/risk/report_builder.py` — 报告模板可复用
- `core/risk/phase_detector.py`, `ds_fusion.py` — 归档，Agent 方案不再需要
- `services/risk_service.py` — 编排模式可参考
- `api/v1/risk.py` — API 端点可复用

---

## 表述纪律（2026-06-02，答辩对齐，覆盖本文上文一切旧表述）

> 本文上半部分（v2 转向 Agent+RAG）记录了路线转折，但以 `TASK_TRACKER.md`（2026-05-31 Agent 编排版）与 `METHOD_STANCE.md` 为最终口径。下面三条纪律覆盖本文一切与之冲突的旧表述，并删除了此处原本残留的旧 rule-based v1 重复段落。

1. **头号创新 = 已落地的白盒前瞻引擎**：Phase-Aware Hazard（5 状态生命周期 + logistic hazard 阶段转换/breakout 预警）+ DISARM Attack-Path（技术转换图路径推理 + 下一步技术预测 + 反制建议）+ Contradiction-Aware D-S Fusion（信念区间 + 冲突检测）。这三块约 1340 行已落地、CPU-only、可审计。`phase_detector.py` / `disarm_scorer.py` / `ds_fusion.py` **不是归档，是主贡献**（上文 Existing Results 称其"归档"的说法作废）。

2. **Agent / RAG 是编排基座与呈现层，不作为创新卖点**。针对评审"用 Agent 做报告研判创新性较弱"的意见：不要主打"多 Agent + RAG 生成报告"（红海，已被 arXiv 2505.17511、2508.10143、Agentic DISARM 2601.15109 占位）。`llm_bridge.py` 升级时严格限定输入为 Layer 1 已算出的结构化结果，LLM 只"翻译成人话"，严禁改分/下结论。

3. **DISARM 下一步技术预测的范式源自网络安全 ATT&CK 域**（MITRE TIE、Markov attack-chain、arXiv 2508.18230），本贡献定位为"跨域迁移到 DISARM 信息操纵域 + 阶段条件化"，**不称首创**。与 Agentic DISARM (2601.15109) 的差异锚在：对方是 flat tagging（观测→标签），KT3 是 path reasoning（预测下一步 + 反制）。

4. **内容分析（立场/危害/有害言论）按闭环分工统一归 KT3 Characterization**；KT1 排除内容信号、KT2 只做传播动力学。
