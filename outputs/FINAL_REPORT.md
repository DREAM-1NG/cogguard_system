# 知微传播分析复现验收报告

## 任务覆盖

| 功能项 | 当前实现 | 验收产物 |
|---|---|---|
| 传播分析 | 规模、边数、参与者、深度、宽度、持续时间、事件矩阵 | `analysis_summary.json`, `dashboard.html` |
| 传播路径 | 重建父子传播边，导出关键路径和路径星图 | `paths.json`, `event_report.md`, `dashboard.html` |
| 参与者信息 | 用户参与次数、出度贡献、PageRank/结构影响、角色分类 | `participants.csv`, dashboard TOP 参与者 |
| 引爆点 | 时间窗口增长异常 + 结构影响力候选节点 | `ignition_points.csv`, dashboard 引爆点清单 |
| 具体事件总结 | 自动选择最大/代表事件，输出文本总结 | `event_report.md` |
| 数据集验证 | Weibo 全量、PHEME、Rumor_RvNN 验证 | 本报告下方数据集表 |

## 数据集结果

| 数据集 | 事件 | 节点 | 边 | 参与者 | 引爆点 | 路径 AUC | 规模 RMSE | 聚焦事件 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Weibo Rumor / Ma-Weibo | 4,664 | 3,805,656 | 3,800,992 | 2,856,741 | 15,789 | 0.935 | 316.32 | `3501712684038955` |
| PHEME | 6,425 | 104,582 | 98,157 | 50,593 | 23,364 | 0.931 | 1.75 | `552806610490646528` |
| Rumor_RvNN Twitter15/16 | 3,098 | 161,038 | 157,940 | 814 | 44,519 | 0.977 | 1.24 | `716451800581279744` |

## 产物索引

### Weibo Rumor / Ma-Weibo
- `dashboard.html`: `outputs/weibo_rumor_full/dashboard.html`
- `event_report.md`: `outputs/weibo_rumor_full/event_report.md`
- `analysis_summary.json`: `outputs/weibo_rumor_full/analysis_summary.json`
- `participants.csv`: `outputs/weibo_rumor_full/participants.csv`
- `ignition_points.csv`: `outputs/weibo_rumor_full/ignition_points.csv`
- `paths.json`: `outputs/weibo_rumor_full/paths.json`
- `prediction_report.json`: `outputs/weibo_rumor_full/prediction_report.json`

说明：
- Weibo Rumor 已全量运行 4664 个事件；路径预测候选边采用 reservoir sampling。
- Full event set traversed; candidate edges were reservoir-sampled for bounded memory.

### PHEME
- `dashboard.html`: `outputs/pheme_full/dashboard.html`
- `event_report.md`: `outputs/pheme_full/event_report.md`
- `analysis_summary.json`: `outputs/pheme_full/analysis_summary.json`
- `participants.csv`: `outputs/pheme_full/participants.csv`
- `ignition_points.csv`: `outputs/pheme_full/ignition_points.csv`
- `paths.json`: `outputs/pheme_full/paths.json`
- `prediction_report.json`: `outputs/pheme_full/prediction_report.json`

说明：
- PHEME loader 跳过 annotation/structure 伪节点，只使用 source-tweets 与 reactions 构建传播树。

### Rumor_RvNN Twitter15/16
- `dashboard.html`: `outputs/rumor_rvnn_full/dashboard.html`
- `event_report.md`: `outputs/rumor_rvnn_full/event_report.md`
- `analysis_summary.json`: `outputs/rumor_rvnn_full/analysis_summary.json`
- `participants.csv`: `outputs/rumor_rvnn_full/participants.csv`
- `ignition_points.csv`: `outputs/rumor_rvnn_full/ignition_points.csv`
- `paths.json`: `outputs/rumor_rvnn_full/paths.json`
- `prediction_report.json`: `outputs/rumor_rvnn_full/prediction_report.json`

说明：
- Rumor_RvNN processed 文件中 959 个 root 无 Twitter15/16 label/nfold 匹配，报告中已保留该警告。
- 959 parsed events have no matching Twitter15/16 label entry.

## 验收结论

当前实现已经覆盖题目要求的传播分析、传播路径、参与者信息、引爆点和具体事件总结，并在 Weibo Rumor、PHEME、Rumor_RvNN 数据上完成验证。
三个数据集均已生成 dashboard、事件报告、参与者表、引爆点表、路径文件和预测报告；Weibo Rumor 采用流式全量命令运行。

## 限制说明

- 当前实现复现的是知微传播分析的核心功能模块，不是知微商业网站的像素级 UI/交互复刻。
- Rumor_RvNN 公开仓库是 Twitter15/16 processed 结构数据，缺少真实用户画像和真实时间戳，因此参与者画像为结构占位。
- ScienceDB Weibo Rumor 有用户 ID 和时间戳，但缺少完整微博账号画像，因此不能还原真实账号粉丝画像。
- 大规模路径预测对候选边使用采样，避免生成不可控的大型训练矩阵；传播分析和引爆点统计本身按事件全量覆盖。
