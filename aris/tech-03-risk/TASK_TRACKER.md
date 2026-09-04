# TASK_TRACKER

## 当前状态

- 工作空间已建立：是
- 技术路线已确定：是（2026-05-31，Agent 编排版）
- 代码实现已开始：是（Layer 1 已完成，Layer 2-3 待实现）
- 当前关注点：WP-A1（升级 llm_bridge 为 DeepSeek Agent 编排器）

## 技术路线（Agent 编排版）

### 核心定位
> 基于多 Agent 编排的协同操纵事件检测、研判与反馈系统

### 三层架构
```
Layer 1: Agent-based Detection & Assessment（已完成）
  ├── Phase Agent: 战役阶段感知（tool: phase_detector.py）
  ├── Evidence Agent: 多源证据融合（tool: ds_fusion.py）
  └── DISARM Agent: 攻击路径推理（tool: disarm_scorer.py）

Layer 2: RAG + Agent Report Generation（待实现）
  ├── 检索：历史报告库 + DISARM 知识库 + 事件证据库
  └── 生成：DeepSeek Agent 基于检索结果生成结构化风险报告

Layer 3: Agent-based Feedback & Detection Extension（待实现）
  ├── Harmful Content Agent: 恶意言论/仇恨言论检测
  ├── Stance Detection Agent: 立场检测与演化追踪
  └── Counter-narrative Agent: 反制叙事建议生成
```

### 架构决策
- LLM 后端：**DeepSeek API**
- 现有 core/risk/ 模块作为 Agent tools 复用
- Agent 不做最终裁决，只做辅助检测和报告生成
- 核心检测仍走统计/规则路线，LLM 调用走 API
- MySQL 持久化报告

## 待办（优先级同等）

### 已完成（Layer 1 基础设施）
- [x] WP1：Schemas + 数据库模型 + 配置
- [x] WP2：证据构建器（evidence_builder.py）
- [x] WP3：阶段检测器（phase_detector.py）
- [x] WP4：D-S 融合（ds_fusion.py）
- [x] WP5：DISARM 攻击路径评分器（disarm_scorer.py）
- [x] WP6：报告构建器 + LLM 桥接占位
- [x] WP7：风险服务层（risk_service.py）
- [x] WP8：API 端点（risk.py）
- [x] WP9：测试（test_risk.py）
- [x] WP10：最小前端

### 待实现（Agent 编排 + 扩展检测）
- [ ] WP-A1：升级 `llm_bridge.py` 为 DeepSeek Agent 编排器
- [ ] WP-A2：实现 Harmful Content Detection Agent
- [ ] WP-A3：实现 Stance Detection Agent
- [ ] WP-A4：实现 RAG + Agent Report Generation
- [ ] WP-A5：实现 Counter-narrative Agent
- [ ] WP-A6：更新 `risk_service.py` 支持 Agent 编排
- [ ] WP-A7：更新 API 端点支持新 Agent 功能
- [ ] WP-A8：补充测试
- [ ] WP-A9：更新前端展示 Agent 检测结果

## 高水平文献支撑

| 论文 | 来源 | 与 Risk Review 的关系 |
|------|------|--------------|
| Multi-agent Systems for Misinformation Lifecycle | arXiv 2505.17511, 2025 | 最直接对标：多 Agent 全生命周期 |
| MCP-Orchestrated Multi-Agent System for Disinformation Detection | arXiv 2508.10143, 2025 | Agent 编排检测先例 |
| Retrieval-Augmented Multi-Agent Framework for Multimodal Fact-Checking | arXiv 2507.09174, 2025 | 支撑 RAG+Agent 报告生成 |
| Multi-Agent Debate for Visual Misinformation Detection | arXiv 2410.20140, 2024 | 支持 Agent 辩论/反馈 |
| LLM-based Semantic Augmentation for Harmful Content Detection | arXiv 2504.15548, 2025 | 支撑恶意言论检测 |
| Agentic DISARM for FIMI Investigation | arXiv 2601.15109, 2026 | DISARM Agent 化先例 |
| Exposing Cross-Platform CIB | WWW 2025 | 上游协同检测学术基础 |
| Evidence-Aware Fake News Detection (TKDE 2024) | IEEE TKDE | evidence-aware 叙事 |
| Multi-Modal Rumor Detection with Evolving Stances (IPM 2025) | IPM | 立场演化 + 动态叙事 |
| End-to-End Multimodal Fact-Checking (SIGIR 2023) | SIGIR | 解释性输出 |

## 会话记录

- 2026-04-08 早期：建立技术线 03 独立 ARIS 工作空间
- 2026-04-08 中期：完成初版 idea-discovery，技术路线收敛（novelty 5/10）
- 2026-04-09 上午：执行 novelty-check，redesign 为高创新版（~8/10）
- 2026-04-09 下午：方法论主张明确化，贡献层级收束
- 2026-04-14：Harness 重构，WP1-WP6 确认完成
- 2026-05-31：技术路线升级为 Agent 编排版
  - 用户确认新定位：基于多 Agent 编排的检测、研判与反馈系统
  - LLM 后端选择：DeepSeek API
  - 扩展功能：恶意言论检测、立场检测、RAG 报告生成、反制叙事
  - 各部分优先级同等
  - 高水平文献支撑已添加
