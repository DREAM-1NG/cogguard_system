# request.md 闭环说明

> 更新时间：2026-06-26  
> 口径：面向 `/Users/albert/Desktop/xas/request.md` 的研究开发闭环，不把实验 baseline 写成产品能力。

## 完成结论

`request.md` 要求的研究复现与实证验证闭环已完成。

本仓库现在具备：

| 验收项 | 状态 | 证据 |
|---|---|---|
| 明确传播监控三类任务边界 | 完成 | `FEATURE_STATUS_MATRIX.md`、`KT2_COMPLETE_PLAN.md` |
| 选择唯一主复现目标 HyperIDP | 完成 | `REFERENCE.md`、`benchmark/REPRODUCTION_REPORT.md` |
| 核验 HyperIDP 官方代码可访问性 | 完成 | 论文标注 GitHub URL 当前公开访问 404，`git ls-remote` 返回 `Repository not found` |
| 在代码不可得时采用 protocol-level reproduction | 完成 | `HyperIDPProtocolProxy`、`HyperIDPAdversarialProxy` |
| 加入 MINDS / FOREST 统一多尺度 baseline | 完成 | MINDS Christianity 30 epochs；FOREST douban 1 epoch sanity |
| 保留 RF / LR 传统 baseline 并标注边界 | 完成 | `RF_Baseline`、`LR_EdgeClassifier` |
| 建立无未来泄漏 prospective next-user 协议 | 完成 | `ProspectiveHeuristic`、`ProspectiveRanker`、HyperIDP proxy |
| 同时报告候选覆盖与排序质量 | 完成 | Candidate Recall、Hits@K、MAP@K、MRR、NDCG@K |
| 报告宏观规模误差 | 完成 | MSLE、MAE、Direction Accuracy |
| 覆盖不同观测窗口 | 完成 | `benchmark/observation_sensitivity.json` |
| 文档同步与禁止项 | 完成 | `benchmark/REPRODUCTION_REPORT.md`、`FEATURE_STATUS_MATRIX.md`、`KT2_COMPLETE_PLAN.md` |
| 自动化验证 | 完成 | `pytest -q` 当前 6 passed |

## 关键结果

| 模型 | 数据集 | 宏观 MSLE | 微观 Hits@100 | 微观 MAP@100 | 说明 |
|---|---|---:|---:|---:|---|
| MINDS | christianity | 0.0807 | 0.5848 | 0.1895 | 30 epochs，best valid MAP@100 epoch=29 |
| HyperIDPProtocolProxy | douban | 0.0228 | 0.3088 | 0.0836 | temporal coactivation hyperedge proxy |
| HyperIDPAdversarialProxy | douban | 0.0293 | 0.3075 | 0.0826 | shared encoder + macro/micro heads + gradient reversal |
| ProspectiveRanker | douban | — | 0.3083 | 0.0838 | strict prospective learned ranker |
| TemporalSizeBaseline | douban | 1.8181 | — | — | fixed 7-day observation window |

## 外部阻塞与非阻塞项

以下事项未完成为原始论文/数据/算力外部限制，不影响 `request.md` 当前闭环：

- HyperIDP 论文标注的官方仓库当前不可公开访问，无法替换为原始实现。
- 本地 MINDS 仓库仅含 Christianity，未含 douban/android 数据。
- FOREST douban CPU 1 epoch 约 12 分钟，30 epochs 长训需要 GPU 或后台长任务。
- 当前 HyperIDP proxy 不是论文 NAS 架构，不能写成 HyperIDP 原模型复现。

## 后续工程化入口

若进入产品集成阶段，建议只展示已观测图分析能力；所有 next-user / size prediction 输出必须标注为实验 baseline，直到完成正式模型选择、接口设计和前端口径审查。
