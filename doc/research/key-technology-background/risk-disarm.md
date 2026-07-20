# 关键技术三：协同攻击的报告研判（Phase-Aware Hazard + DISARM 路径预判 + 多 Agent 编排）

> **用途**：定义 KT3 的研究问题、当前工程落点、研究目标、实现方向和验证方式。  
> **受众**：KT3 研究实现者、报告研判/DISARM 模块维护者。  
> **维护规则**：只写关键技术背景与研究方案；产品接口和任务状态放入 `../../engineering/`。

> 方向更新（2026-06-02）：KT3 定位为闭环末端的“报告研判”，分三段：**(a) 基于 Agent 的证据编排（含用户言论/行为检测）→ (b) 基于 RAG 的报告生成 → (c) Agent 对协同攻击的解释总结**。
> 重要表述纪律：针对评审“用 Agent 做报告研判创新性较弱”的意见，**头号创新必须是已落地的白盒前瞻引擎**（Phase-Aware Hazard 阶段预警 + DISARM 攻击路径预判与反制 + 阶段调制 D-S 融合），Agent / RAG 仅作为编排基座与呈现层，**不作为创新卖点**。核心叙事：从 detection 升级到 anticipation + countermeasure（预测下一步攻击技术 + 给出反制）。

## 1. 问题定义

报告研判把上游协同发现（KT1）与传播监控（KT2）的结果组织成统一证据链，对事件 / claim / thread 层级输出可审计的研判与处置建议，回答三个问题：

- **当前风险多高**（信念区间 + 冲突检测，非点估计）
- **接下来会发生什么**（阶段转换/breakout 预测 + DISARM 下一步技术预测）
- **应该如何应对**（基于预测攻击路径的反制建议）

内容层分析（立场检测、危害/有害言论评估）按闭环分工统一归 KT3 的 Characterization 层。

## 2. 当前代码基线

`core/review/` 已落地（约 1340 行，CPU 白盒，已由 `risk_service.py` 跑通）：

- `system/backend/app/core/review/evidence_builder.py`：多源证据包构建
- `system/backend/app/core/review/phase_detector.py`：5 状态战役生命周期 + logistic hazard 阶段转换/breakout 预测
- `system/backend/app/core/review/disarm_scorer.py`：DISARM 技术转换图 + 攻击路径评分 + 下一步技术预测 + 反制建议
- `system/backend/app/core/review/ds_fusion.py`：Dempster-Shafer 融合 + phase-conditioned 质量调制 + 冲突检测
- `system/backend/app/core/review/report_builder.py`：结构化报告生成
- `system/backend/app/core/review/llm_bridge.py`：**仅约 30 行占位**（待升级为 DeepSeek Agent 编排器）
- `system/backend/app/services/risk_service.py`、`api/v1/risk.py`、前端 `views/risk/index.vue`

未落地（设计稿）：Layer 2 RAG 报告生成、Layer 3 恶意言论/立场/反制叙事 Agent，以及 Agent 编排器本体（`agent`/`rag`/`retriever` 等文件不存在）。

## 3. 三层架构（Agent 编排版）

- **Layer 1 检测研判（已落地，作为 Agent 的 tools）**：Phase Agent（phase_detector）+ Evidence Agent（ds_fusion）+ DISARM Agent（disarm_scorer）
- **Layer 2 RAG + Agent 报告生成（设计稿）**：检索历史报告库 + DISARM 知识库 + 事件证据 → DeepSeek 生成结构化报告
- **Layer 3 反馈与扩展检测（设计稿）**：恶意言论 / 立场 / 反制叙事 Agent
- LLM 后端：DeepSeek API；Agent 不做最终裁决，核心检测走已落地的统计/规则/图路线

## 4. 这一技术线要解决的核心问题

- 如何把协同、传播、账户结果收束到统一证据包并做阶段感知研判
- 如何把 DISARM 从“标签映射”提升为“攻击路径推理 + 下一步预测 + 反制”
- 如何让 LLM/Agent 只把白盒结构化结论“翻译成人话”，严禁改分/下结论，保证可审计
- 如何输出能被看板、报告、预警复用的 JSON 结构

## 5. 推荐实现方向与表述纪律

- 头号创新讲 Layer 1 已落地的白盒算法（hazard 预警 + DISARM 路径预判 + 反制 + 阶段调制 D-S），CPU-only、可审计
- DISARM“预测下一步技术”范式源自网络安全 ATT&CK 域（MITRE TIE 等），本贡献定位为**跨域迁移到 DISARM 信息操纵域 + 阶段条件化**，不宜称首创
- Agent / RAG 是编排与呈现层，避免主打“多 Agent + RAG 报告生成”（红海，已被 arXiv 2505.17511、2601.15109 等占位）
- `llm_bridge.py` 升级时严格限定输入为 Layer 1 已算出的结构化结果

## 6. 推荐验证方式

- 针对纯后端服务补单元测试与响应结构测试
- 选取 `mock_weibo` / `weibo` / `news` 小样例验证 JSON 报告稳定性
- 验证重点是“预测有用性”（breakout 前能否预警、下一步技术预测是否优于启发式、反制是否可操作），而非分类完美性

## 7. 参考文献线索

- `Phase-Aware / campaign lifecycle` 与 early-warning（hazard / breakout 预测）
- MITRE ATT&CK 攻击链/技术转换预测（TIE、Markov attack-chain，迁移来源）
- Agentic DISARM for FIMI (arXiv 2601.15109, 2026) — flat tagging 对照，KT3 差异在 path reasoning + 预测 + 反制
- Multi-agent Misinformation Lifecycle (arXiv 2505.17511, 2025) — 多 agent 全生命周期对照
- `DISARM Red Framework`
