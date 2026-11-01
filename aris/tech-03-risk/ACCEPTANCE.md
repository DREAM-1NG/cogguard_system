# ACCEPTANCE

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

## 禁止修改路径

- `../../MediaCrawler-main/`
- `../../NewsCrawler-main/`
- `../../CooRTweet-master/`
- `../../new-system/backend/app/core/coordination/`
- `../../new-system/backend/app/core/propagation.py`
- `../../new-system/backend/app/core/account_profiler.py`

## 功能验收

- 后端存在可调用的报告研判 API
- 返回结构至少包含：
  - `event_id`
  - `claims`
  - `evidence`
  - `scores`
  - `disarm_mappings`
  - `recommendations`
- 报告字段能够解释真实性、操纵性、危害性三维结果
- `llm_bridge.py` 已占位，但不负责第一阶段最终裁决

## 测试验收

- 有覆盖风险报告结构和评分逻辑的后端测试
- 新路由已正确挂载
- 如有前端改动，页面与路由完成最小兼容检查

## 非目标

- 不做完整多智能体运行时
- 不在本轮补齐预警中心、报告中心和监测看板
- 不回头重写协同、传播、账户模块
