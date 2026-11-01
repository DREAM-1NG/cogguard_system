# ACCEPTANCE

## 允许修改路径

- `../../new-system/backend/app/core/coordination/`
- `../../new-system/backend/app/services/coordination_service.py`
- `../../new-system/backend/app/api/v1/coordination.py`
- `../../new-system/backend/tests/`
- `../../new-system/frontend/src/api/coordination.ts`
- `../../new-system/frontend/src/views/coordination/index.vue`
- 本目录下的稳定 Markdown

## 禁止修改路径

- `../../MediaCrawler-main/`
- `../../NewsCrawler-main/`
- `../../CooRTweet-master/`
- `../../new-system/backend/app/core/propagation.py`
- `../../new-system/backend/app/core/account_profiler.py`
- `../../new-system/backend/app/core/risk/`

## 功能验收

- 系统能基于多种行为关系构建协调图
- 输出包含边类型或证据样本，而不只是汇总分数
- 存在显著性筛查或等价的自然共振抑制机制

## 测试验收

- 有覆盖新增逻辑的后端测试
- 现有协调检测基本流程不回归
- 如有前端返回结构变化，页面至少完成最小兼容检查

## 非目标

- 不做通用社交机器人检测器
- 不扩展到更多平台
- 不在本轮落地报告研判逻辑
