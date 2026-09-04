# CLAUDE.md

你当前处于关键技术二工作空间。

## 先读

1. `README.md`
2. `RESEARCH_BRIEF.md`
3. `ACCEPTANCE.md`
4. `../../doc/research/key-technology-background/propagation-analysis.md`
5. `../../AGENTS.md`

## 作用域

- 当前目标：传播趋势预测（LLM+时序）与传播监控子功能（画像/立场/危害性/源头/范围）
- 产品代码根：`../../new-system/`
- 推荐分支：`aris/t2-*`

## 默认允许修改

- `../../new-system/backend/app/core/propagation.py`
- `../../new-system/backend/app/services/propagation_service.py`
- `../../new-system/backend/app/api/v1/propagation.py`
- `../../new-system/backend/tests/`
- 与返回结构直接相关的最小前端路径
- 当前工作空间文档

## 默认禁止修改

- `../../MediaCrawler-main/`
- `../../NewsCrawler-main/`
- `../../CooRTweet-master/`
- 协同检测与报告研判的无关模块

## 产物规则

- 稳定结论回写到 `EXPERIMENT_PLAN.md` 和 `TASK_TRACKER.md`
- 原始实验日志留在本地 `outputs/` 或 `logs/`，不提交
