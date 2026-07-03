# 技术线 03：报告研判（Phase-Aware Hazard + DISARM 路径预判 + 多 Agent 编排）

## 目标

把上游协同发现（KT1）与传播监控（KT2）的结果组织成统一证据链，对事件 / claim / thread 输出可审计的研判报告与处置建议。

> 方向更新（2026-06-02，以 `TASK_TRACKER.md` 2026-05-31 Agent 编排版为最终口径）：
> - **头号创新 = 已落地的白盒前瞻引擎**：Phase-Aware Hazard（阶段预警）+ DISARM Attack-Path（攻击路径预判 + 反制）+ Contradiction-Aware D-S Fusion。约 1340 行已落地、CPU-only、可审计。
> - 报告研判分三段：**(a) 基于 Agent 的证据编排（含用户言论/行为检测）→ (b) 基于 RAG 的报告生成 → (c) Agent 解释总结协同攻击**。
> - **Agent / RAG 是编排基座与呈现层，不作为创新卖点**（避开"用 Agent 做报告研判创新性弱"的评审意见，详见 `RESEARCH_BRIEF.md` 表述纪律与 `METHOD_STANCE.md`）。
> - 内容分析（立场/危害）按闭环分工统一归 KT3。

## 必读文档

- [`../../AGENTS.md`](../../AGENTS.md)
- [`../../doc/engineering/development-roadmap.md`](../../doc/engineering/development-roadmap.md)
- [`../../doc/research/key-technology-background/risk-disarm.md`](../../doc/research/key-technology-background/risk-disarm.md)
- [`../../new-system/README.md`](../../new-system/README.md)
- [`ACCEPTANCE.md`](ACCEPTANCE.md)
- [`KT3_LAYERED_REQUIREMENTS.md`](./KT3_LAYERED_REQUIREMENTS.md)
- [`KT3_POST_VIEW_FORMALIZATION.md`](./KT3_POST_VIEW_FORMALIZATION.md)
- [`KT3_AGENTIC_MARO_REFERENCE.md`](./KT3_AGENTIC_MARO_REFERENCE.md)
- [`Multiagents.md`](./Multiagents.md)
- [`KT3_FULL_VALIDATION_DATA_ACQUISITION.md`](./KT3_FULL_VALIDATION_DATA_ACQUISITION.md)

## 建议分支

- `aris/t3-risk-mvp`
- `aris/t3-disarm-report`

都必须从 `release-0.2` 起分支。

## 允许修改路径

- `../../new-system/backend/app/core/risk/`
- `../../new-system/backend/app/services/risk_service.py`
- `../../new-system/backend/app/api/v1/risk.py`
- `../../new-system/backend/app/api/v1/router.py`
- `../../new-system/backend/app/schemas/risk.py`
- `../../new-system/backend/tests/`
- `../../new-system/frontend/src/api/risk.ts`
- `../../new-system/frontend/src/views/risk/index.vue`
- `../../new-system/frontend/src/router/index.ts`
- `../../new-system/frontend/src/components/layout/BasicLayout.vue`
- 本目录下的稳定 Markdown

说明：

- 当前技术线以后端为主，前端只做最小可用入口
- 报告研判尽量消费既有上游结果，不回头重写协同、传播、账户模块

## 禁止修改路径

- `../../MediaCrawler-main/`
- `../../NewsCrawler-main/`
- `../../CooRTweet-master/`
- `../../new-system/backend/app/core/coordination/`
- `../../new-system/backend/app/core/propagation.py`
- `../../new-system/backend/app/core/account_profiler.py`
- 与看板、报告中心、预警中心相关的更大范围前端改造

## 已落地（Layer 1，约 1340 行，CPU 白盒，已由 risk_service 跑通）

- `core/risk/evidence_builder.py` — 多源证据包构建
- `core/risk/phase_detector.py` — 5 状态生命周期 + logistic hazard 阶段/breakout 预测
- `core/risk/disarm_scorer.py` — DISARM 技术转换图 + 攻击路径评分 + 下一步技术预测 + 反制建议
- `core/risk/ds_fusion.py` — D-S 融合 + phase-conditioned 质量调制 + 冲突检测
- `core/risk/report_builder.py` — 结构化报告生成
- `risk_service.py` / `api/v1/risk.py` / 前端 `views/risk/index.vue` 已接入

## 本轮预期交付（Layer 2/3，设计稿待落地）

- 升级 `llm_bridge.py`（当前约 30 行占位）为 DeepSeek Agent 编排器；输入严格限定为 Layer 1 已算出的结构化结果，LLM 只"翻译成人话"，不改分/不下结论
- (a) 基于 Agent 的证据编排（用户言论/行为检测）
- (b) 基于 RAG 的报告生成（历史报告库 + DISARM 知识库 + 事件证据）
- (c) Agent 解释总结协同攻击
- 报告 JSON 至少含：`event_id` / `claims` / `evidence` / `phase`(阶段预警) / `disarm_analysis`(路径预判 + 反制) / `fusion`(信念区间 + 冲突) / `recommendations`
- 对应测试与必要文档同步

## 目标测试

- 新增 `new-system/backend/tests/` 中的报告研判相关测试
- 路由挂载和结构化返回测试
- 如有前端改动，至少完成最小路由/页面可访问检查

## 成功标准

- Layer 1 白盒前瞻引擎（阶段预警 + DISARM 路径预判 + D-S 融合）可经 API 调用并结构化输出（已达成）
- Agent 编排可调用 DeepSeek 完成证据编排/报告/解释，且不承担最终裁决
- 头号创新讲已落地白盒算法，Agent/RAG 仅作编排与呈现层，不作创新卖点
- 不修改禁止路径
