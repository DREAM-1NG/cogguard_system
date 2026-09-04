# 技术背景总览

> **用途**：总览三条关键技术的研究定位、当前工程基线和推荐阅读顺序。
> **受众**：研究实现者、系统设计维护者、后续执行 ARIS 任务的 agent。
> **维护规则**：只写稳定研究背景和技术线入口；具体工程任务状态放入 `../../engineering/development-roadmap.md`。

## 1. 项目主线

本项目面向网络舆论对抗场景中的跨平台协同攻击。

系统围绕三大主要功能形成闭环，每个功能下包含多个子功能，技术按重要程度分为关键技术和其它技术：

```
功能一: Coordination Discover ──→ 功能二: Propagation Analysis ──→ 功能三: Risk Review
                                                    │
        └────────────────────────────────────────────┘
```

| 功能 | 关键技术 | 说明 |
|------|---------|------|
| Coordination Discover | 跨平台共同行为特征复用融合检测 | 用平台无关的行为信号发现协同群体；内容检测不作协同信号 |
| Propagation Analysis | LLM+时序预测（事件规模预测） | 事件条件体制切换的级联规模前瞻预测；借鉴知微产品形态 |
| Risk Review | Phase-Aware Hazard + DISARM 路径预判（多 Agent 编排） | 阶段预警 + 攻击路径预判 + 反制；Agent/RAG 作编排与呈现层 |

关键技术是从功能中提炼的核心创新点，不等同于功能本身。其它技术后期动态调整。
方向更新见各技术线背景文档（2026-06-02）。

## 2. 当前工程基线

- 工程基线：`release-0.2`
- 产品代码根：`system/`
- 短期验证范围：`mock_weibo`、`weibo`、`news`
- 参考边界：`MediaCrawler-main/`、`NewsCrawler-main/`、`CooRTweet-master/`

仓库分层如下：

- `doc/`：长期文档与技术背景
- `aris/`：按关键技术拆分的独立执行工作空间
- `system/`：唯一产品代码主线

## 3. 当前实现状态

按 `release-0.2` 当前代码和 `doc/engineering/development-roadmap.md` 口径：

- 数据采集：已完成 Mock 与真实爬虫封装接入
- Coordination Discover：已完成共享对象协同检测 MVP（CooRTweet 重写 + 加权图 + 社区发现）；最新方向"跨平台共同行为特征复用 + 显著性筛查（PSL）"尚为设计稿、未落地
- Propagation Analysis：已完成 CascadeSwitch 趋势预测核心（WP1-3：时序特征 + LLM 事件上下文 + 体制混合预测）+ legacy 源头追溯/证据链；立场/危害子功能未启动，"传播路径预测"无设计无代码
- Risk Review：已完成 Layer 1 白盒核心（Phase-Aware Hazard + DISARM 路径 + D-S 融合，约 1340 行）；多 Agent 编排 + RAG 报告（Layer 2/3）为设计稿、未落地
- 看板/预警/报告：轻于核心分析流水线，放在后续阶段

## 4. 工程原则

- 优先保持 `system/` 为唯一代码主线，不搬动产品代码根
- 参考子仓默认只读，不在无明确任务时修改
- 规则与证据优先于黑盒 LLM 裁决
- ARIS 只作为执行工作空间和研发编排层，不进入产品运行时
- 每条关键技术单独工作空间、单独 brief、单独分支

## 5. ARIS 使用原则

本仓库不 vendoring 上游 ARIS skill 代码，只保留本地适配层：

- `aris/shared/`：统一 runner、GPU 模板、产物策略、评审清单
- `aris/tech-01-coordination/`：关键技术一执行入口
- `aris/tech-02-propagation/`：关键技术二执行入口
- `aris/tech-03-risk/`：关键技术三执行入口

执行时不要在仓库根创建单一 `RESEARCH_BRIEF.md`。每次都从目标 `aris/tech-*` 工作空间进入。

## 6. 推荐阅读顺序

1. `AGENTS.md`
2. `doc/engineering/development-roadmap.md`
3. `system/README.md`
4. `aris/README.md`
5. 目标 `aris/tech-*/README.md`
6. 目标技术的背景文档

## 7. 关键参考文献入口

- [`../literature-references.md`](../literature-references.md)
- [`../../../../materials/开题报告.doc`](../../../../materials/开题报告.doc)
- [`../../engineering/development-roadmap.md`](../../engineering/development-roadmap.md)

三条技术线的具体背景分别见：

- [coordination-detection.md](coordination-detection.md)
- [propagation-analysis.md](propagation-analysis.md)
- [risk-disarm.md](risk-disarm.md)
