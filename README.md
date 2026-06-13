# 知微传播分析复现：传播分析、路径、参与者、引爆点与预测

本项目提供一个本地可运行的传播分析原型，用于复现知微传播分析中常见的四类能力：

1. **传播分析**：规模、深度、宽度、时间序列、增长率、结构指标。
2. **传播路径**：基于转发/回复树重建传播 DAG/树，导出关键路径与层级结构。
3. **参与者信息**：用户参与次数、首发时间、影响力、桥接作用、传播角色。
4. **引爆点**：检测导致传播增速突变的节点与时间窗口。
5. **预测任务**：传播路径预测（下一跳/新增边候选）与传播规模预测（最终规模回归）。

支持并已在本地验证的数据集：

- Weibo Rumor / Ma-Weibo: <https://doi.org/10.57760/sciencedb.j00133.00050>
- Rumor_RvNN Twitter15/16: <https://github.com/majingCUHK/Rumor_RvNN>
- PHEME Dataset for Rumour Detection and Veracity Classification

当前本地数据目录：

- `data/Rumor_RvNN`：majingCUHK/Rumor_RvNN 官方仓库。
- `data/PHEME/all-rnr-annotated-threads`：PHEME annotated threads。
- `data/Weibo_Rumor`：ScienceDB/Ma-Weibo 原始 Weibo Rumor 数据，已用于 loader 覆盖率验证。

若未提供数据，也可以运行内置合成样例以验证流程。

## 安装

```bash
cd propagation_analysis
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 快速运行 Demo

```bash
python scripts/run_demo.py
```

或：

```bash
python -m propagation.cli demo --output outputs/demo
```

## 读取真实数据

### Weibo Rumor / Ma-Weibo

这是中文 Sina Weibo 谣言事件数据集，ScienceDB 元数据说明其包含 4664 个带标签事件；事件索引行格式为 `event_id, label, post_ids`，帖子内容位于 `posts/{event_id}.json`。

```bash
python -m propagation.cli analyze \
  --dataset weibo_rumor \
  --data-dir /path/to/weibo-rumor \
  --output outputs/weibo
```

适配器会尝试读取常见文件，并建议先运行覆盖率审计：

```bash
python -m propagation.cli inspect \
  --dataset weibo_rumor \
  --data-dir /path/to/weibo-rumor \
  --output outputs/weibo_inspect
```

审计会输出 `dataset_inspection.json`，包含事件索引文件数量、解析事件数、帖子 JSON 覆盖情况、行级解析率和未解析样例。

如果帖子 JSON 内包含父节点字段，如 `parent_id`、`parent_mid`、`reply_to_id` 或 `retweeted_status`，系统会重建传播边；如果没有显式父节点，系统将第一个帖子视为源帖，并使用源帖星型传播结构作为保守 fallback。

### Rumor_RvNN Twitter15/16

`https://github.com/majingCUHK/Rumor_RvNN` 官方仓库公开的是 ACL 2018 RvNN 论文使用的 Twitter15/Twitter16 预处理数据，不是中文 Weibo Rumor 原始数据。当前已下载到：

```text
data/Rumor_RvNN
```

运行：

```bash
python -m propagation.cli inspect \
  --dataset rumor_rvnn_twitter \
  --data-dir data/Rumor_RvNN \
  --output outputs/rumor_rvnn_inspect

python -m propagation.cli analyze \
  --dataset rumor_rvnn_twitter \
  --data-dir data/Rumor_RvNN \
  --output outputs/rumor_rvnn_analysis
```

该适配器读取 `resource/data.TD_RvNN.vol_5000.txt` 或 `resource/data.BU_RvNN.vol_5000.txt`，行格式为 `root-id, parent-index, current-index, parent-number, text-length, bow-features...`。

注意：该 processed 文件只包含传播结构和特征，不包含真实用户画像、真实时间戳和原文内容。系统会用结构节点 ID 作为参与者占位，并用节点顺序补齐时间，仅用于验证传播路径、结构分析、引爆点和预测流程；不应把其参与者报告当作真实 KOL 画像。

### 通用传播树文本

- `Weibo/tree/*.txt` 或任意 `tree` 目录下的传播树文本；
- `label*.txt` / `Weibo.txt` 形式标签文件；
- Rumor_RvNN 常见边格式如 `parent -> child`、`parent child`、`parent: child1 child2 ...`；
- tab 分隔的 `event_id parent child ...` / `parent child time` 风格；
- JSON line 风格节点或边；
- tuple-like 的 `(parent_id,parent_user,parent_time) -> (child_id,child_user,child_time)` 风格。

如果 `dataset_inspection.json` 中 `overall_parse_line_rate` 明显低于 0.8，需要根据未解析样例补充对应格式解析器。

### PHEME

```bash
python -m propagation.cli analyze \
  --dataset pheme \
  --data-dir data/PHEME/all-rnr-annotated-threads \
  --output outputs/pheme
```

适配器按 `*/rumours|non-rumours/<thread>/source-tweets|reactions` 组织线程，跳过 `annotation.json`、`structure.json` 和 macOS `._*.json` 资源文件。系统会读取 `annotation.json` 中的 claim/veracity，并结合 `structure.json` 与 `in_reply_to_status_id_str` 构建回复树。

建议先审计覆盖率：

```bash
python -m propagation.cli inspect \
  --dataset pheme \
  --data-dir data/PHEME/all-rnr-annotated-threads \
  --output outputs/pheme_inspect
```

## 预测

```bash
python -m propagation.cli predict \
  --dataset weibo_rumor \
  --data-dir /path/to/weibo-rumor \
  --output outputs/weibo_predict \
  --observation-ratio 0.3
```

输出：

- `analysis_summary.json`：事件级传播指标与总结；
- `participants.csv`：参与者画像；
- `ignition_points.csv`：引爆点；
- `paths.json`：关键传播路径；
- `prediction_report.json`：路径预测与规模预测指标；
- `dashboard.html`：炫酷专业的本地交互式传播分析驾驶舱；
- `event_report.md`：适合写作业/报告的文字版传播分析总结。

## 专业可视化驾驶舱

生成完整分析、预测和展示页面：

```bash
python -m propagation.cli dashboard \
  --dataset weibo_rumor \
  --data-dir /path/to/weibo-rumor \
  --output outputs/weibo_dashboard \
  --observation-ratio 0.3
```

也可以在分析或预测时附加 `--dashboard`：

```bash
python -m propagation.cli analyze --dataset pheme --data-dir /path/to/pheme --output outputs/pheme --dashboard
python -m propagation.cli predict --dataset pheme --data-dir /path/to/pheme --output outputs/pheme --dashboard
```

`dashboard.html` 为静态 HTML 文件，可直接用浏览器打开。页面包含：

- 总览大屏：事件数、节点数、参与者、引爆点；
- 传播路径星图：高影响节点、根节点、引爆点高亮；
- 传播增长时间线：新增节点与累计规模；
- 深度-宽度结构图：传播层级剖面；
- 事件规模矩阵：规模、深度、宽度、持续时间；
- 参与者角色分布：KOL、桥接节点、二级传播者、普通参与者；
- TOP 参与者表；
- 引爆点清单；
- 关键传播链路表。

## 本地验证结果

全量数据覆盖率：

```bash
python -m propagation.cli inspect --dataset rumor_rvnn --data-dir data/Rumor_RvNN --output outputs/rumor_rvnn_inspect_final
python -m propagation.cli inspect --dataset pheme --data-dir data/PHEME/all-rnr-annotated-threads --output outputs/pheme_inspect
```

- Rumor_RvNN：解析 `data.TD_RvNN.vol_5000.txt`，3098 个 root、161038 行/节点；其中 2139 个 root 命中 Twitter15/16 label/nfold，959 个 root 为 processed 文件中的未标注样本。
- PHEME：6425 个线程，6425 个 source tweets，98929 个 reactions，6425 个 annotation/structure；标签分布为 non-rumour 4023、true-rumour 1067、unverified-rumour 697、false-rumour 638。
- Weibo Rumor / Ma-Weibo：4664 个事件、3805656 个帖子 ID，4664 个事件 JSON 全部存在。

全量/验证命令：

```bash
python -m propagation.cli dashboard --dataset rumor_rvnn --data-dir data/Rumor_RvNN --output outputs/rumor_rvnn_full --observation-ratio 0.3
python -m propagation.cli dashboard --dataset pheme --data-dir data/PHEME/all-rnr-annotated-threads --output outputs/pheme_full --observation-ratio 0.3
python -m propagation.cli weibo-full --data-dir data/Weibo_Rumor --output outputs/weibo_rumor_full --observation-ratio 0.3
python -m propagation.cli report --output outputs/FINAL_REPORT.md
```

- Rumor_RvNN full：3098 事件，161038 节点，路径预测 AUC 约 0.977，规模预测 RMSE 约 1.24。
- PHEME full：6425 事件，104582 节点，路径预测 AUC 约 0.931，规模预测 RMSE 约 1.75。
- Weibo Rumor full：4664 事件，3805656 节点，3800992 条传播边，2856741 个唯一参与者，15789 个引爆点。路径预测遍历全量事件并对候选边做 reservoir sampling，采样 750000 条、候选边约 9665023 条，AUC 约 0.935；规模预测使用全量 4664 事件，RMSE 约 316.32。

每个输出目录都包含：

- `dashboard.html`：传播分析大屏；
- `event_report.md`：具体事件总结；
- `analysis_summary.json`：传播分析指标；
- `participants.csv`：参与者信息；
- `ignition_points.csv`：引爆点；
- `paths.json`：传播路径；
- `prediction_report.json`：路径和规模预测指标。


## 方法说明

### 传播分析指标

- 规模：节点数、边数、参与用户数；
- 结构：最大深度、最大宽度、平均分支数、叶子比例、最长路径；
- 时间：首发/末次传播时间、传播时长、分桶增长序列；
- 网络：入度/出度、PageRank、介数中心性。

### 引爆点检测

将事件按时间分桶，计算每个窗口新增节点数和 z-score。若窗口增量显著高于历史均值，则窗口内高出度、高 PageRank 或高后续级联贡献的节点会被标为引爆点。

### 传播路径预测

当前实现为可解释 baseline：

- 观察早期 `observation-ratio` 比例节点；
- 为已观察节点构造候选父节点；
- 用逻辑回归根据时间差、深度、出度、PageRank、用户历史活跃度等特征预测下一批边；
- 指标：AUC、Average Precision、Hits@K。

### 传播规模预测

当前实现为随机森林/梯度提升风格 baseline（若只安装 sklearn 则使用 RandomForestRegressor）：

- 用早期结构、时间增长与参与者特征预测最终节点数；
- 指标：MAE、RMSE、MAPE、R²。

## 后续可增强方向

- 使用 GNN/RvNN/TreeLSTM 替代 baseline；
- 加入文本语义、情绪、立场识别；
- 使用 Hawkes Process/DeepHawkes 进行时间强度建模；
- Web 可视化：传播树、地理热力、KOL 传播链路、关键节点回放。
