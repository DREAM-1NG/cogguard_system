# CLAUDE.md

你当前处于关键技术三工作空间。

## 先读

1. `README.md`
2. `RESEARCH_BRIEF.md`
3. `ACCEPTANCE.md`
4. `../../doc/research/key-technology-background/risk-disarm.md`
5. `../../AGENTS.md`

## 作用域

- 当前目标：Agent+RAG 攻击分析与报告生成（消费 KT1+KT2 结果）
- 产品代码根：`../../new-system/`
- 推荐分支：`aris/t3-*`

## 默认允许修改

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
- 当前工作空间文档

## 默认禁止修改

- `../../MediaCrawler-main/`
- `../../NewsCrawler-main/`
- `../../CooRTweet-master/`
- `../../new-system/backend/app/core/coordination/`
- `../../new-system/backend/app/core/propagation.py`
- `../../new-system/backend/app/core/account_profiler.py`

## 产物规则

- 稳定结论回写到 `EXPERIMENT_PLAN.md` 和 `TASK_TRACKER.md`
- 原始实验日志留在本地 `outputs/` 或 `logs/`，不提交
