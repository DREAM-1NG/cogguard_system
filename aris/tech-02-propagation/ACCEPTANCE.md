# ACCEPTANCE

## 允许修改路径

- `../../new-system/backend/app/core/propagation.py`
- `../../new-system/backend/app/core/propagation/`
- `../../new-system/backend/app/core/propagation_legacy.py`
- `../../new-system/backend/app/services/propagation_service.py`
- `../../new-system/backend/app/api/v1/propagation.py`
- `../../new-system/backend/tests/`
- `../../new-system/frontend/src/api/propagation.ts`
- `../../new-system/frontend/src/views/propagation/index.vue`
- 本目录下的稳定 Markdown

## 禁止修改路径

- `../../MediaCrawler-main/`
- `../../NewsCrawler-main/`
- `../../CooRTweet-master/`
- `../../new-system/backend/app/core/coordination/`
- `../../new-system/backend/app/core/risk/`

## 功能验收

本阶段验收围绕三项主功能：

- **规模预测**：能在明确观测窗口和预测窗口下输出传播规模或趋势预测，并给出 baseline 对比或误差指标。
- **角色定位**：能基于已观测传播图识别关键角色，并提供图结构或证据链依据；能与 KT1 协同用户集合联动。
- **下一跳预测**：能生成无未来泄漏的候选用户/边，并输出排序结果或预测分数；至少报告候选覆盖或 Top-K 排序指标。

辅助能力验收：

- 已有传播图、时间线、证据链和关键路径回溯不回归。
- 前端只展示已落地能力，不把实验性下一跳预测或未验证模型写成已完成。
- 输出能被 KT3 或前端消费，但不要求一次性固定最终字段。

## 测试验收

- 有覆盖主功能核心路径的后端测试或实验脚本。
- 对预测类功能使用 mock / fixture 数据验证基本输出形态。
- 对角色定位和证据链保持回归测试。
- 若引入外部模型或 LLM 调用，应有 fallback 或 mock 机制，测试不依赖外部 API。

## 非目标

- 不要求一次性复现所有论文。
- 不要求固定最终系统模型。
- 不要求完整实现所有 auxiliary。
- 不要求把内容分析、立场检测、危害评估作为传播监控主功能。
