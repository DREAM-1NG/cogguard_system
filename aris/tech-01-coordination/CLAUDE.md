# CLAUDE.md

你当前处于关键技术一工作空间。

## 先读

1. `README.md`
2. `RESEARCH_BRIEF.md`
3. `ACCEPTANCE.md`
4. `../../doc/research/key-technology-background/coordination-detection.md`
5. `../../AGENTS.md`

## 作用域

- 当前目标：基于多任务框架的跨平台协同行为发现与分类（二分类 + 类型分类）
- 产品代码根：`../../new-system/`
- 推荐分支：`aris/t1-*`

## 默认允许修改

- `../../new-system/backend/app/core/coordination/`
- `../../new-system/backend/app/services/coordination_service.py`
- `../../new-system/backend/app/api/v1/coordination.py`
- `../../new-system/backend/tests/`
- 与返回结构直接相关的最小前端路径
- 当前工作空间文档

## 默认禁止修改

- `../../MediaCrawler-main/`
- `../../NewsCrawler-main/`
- `../../CooRTweet-master/`
- 报告研判与传播监控的无关模块

## 产物规则

- 稳定结论回写到 `EXPERIMENT_PLAN.md` 和 `TASK_TRACKER.md`
- 原始实验日志留在本地 `outputs/` 或 `logs/`，不提交
