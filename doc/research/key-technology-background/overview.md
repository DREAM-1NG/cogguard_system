# 技术背景总览

> **用途**：总览三条关键技术的研究定位、当前工程基线和推荐阅读顺序。  
> **受众**：研究实现者、系统设计维护者、后续执行 ARIS 任务的 agent。  
> **维护规则**：只写稳定研究背景和技术线入口；具体工程任务状态放入 `../../engineering/development-roadmap.md`。

## 1. 项目主线

本项目面向网络舆论对抗场景中的跨平台协同攻击。

系统围绕三大主要功能形成闭环，每个功能下包含多个子功能，技术按重要程度分为关键技术和其它技术：

```
功能一: 协同发现 ──→ 功能二: 传播监控 ──→ 功能三: 风险评判
                                                    │
        └────────────────────────────────────────────┘
```

| 功能 | 关键技术 | 说明 |
|------|---------|------|
| 协同发现 | 多任务协同检测（二分类→类型分类） | 发现并分类跨平台协同行为 |
| 传播监控 | LLM+时序预测 | 预测传播趋势，含画像/立场/危害性等子功能 |
| 风险评判 | Agent+RAG | 消费上游结果，生成攻击分析报告 |

关键技术是从功能中提炼的核心创新点，不等同于功能本身。其它技术后期动态调整。

## 2. 当前工程基线

- 工程基线：`release-0.2`
- 产品代码根：`new-system/`
- 短期验证范围：`mock_weibo`、`weibo`、`news`
- 参考边界：`MediaCrawler-main/`、`NewsCrawler-main/`、`CooRTweet-master/`

仓库分层如下：

- `doc/`：长期文档与技术背景
- `aris/`：按关键技术拆分的独立执行工作空间
- `new-system/`：唯一产品代码主线

## 3. 当前实现状态

按 `release-0.2` 当前代码和 `doc/engineering/development-roadmap.md` 口径：

- 数据采集：已完成 Mock 与真实爬虫封装接入
- 协同发现（KT1）：已完成共享对象协同检测 MVP + 基础设施，待补多任务分类框架
- 传播监控（KT2）：已完成传播子图、时间线、关键角色 MVP + 证据链，待补 LLM+时序预测
- 风险评判（KT3）：已完成规则型 MVP（1340 行），待重构为 Agent+RAG 方案
- 看板/预警/报告：轻于核心分析流水线，放在后续阶段

## 4. 工程原则

- 优先保持 `new-system/` 为唯一代码主线，不搬动产品代码根
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
3. `new-system/README.md`
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
