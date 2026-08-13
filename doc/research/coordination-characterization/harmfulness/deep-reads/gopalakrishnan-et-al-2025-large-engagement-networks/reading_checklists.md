# 严格精读四张清单

## 一句话链条

旧的 coordinated campaign 研究缺少 topic 级可靠 ground truth → ephemeral astroturfing 提供可检测的 fake-trend 锚点 → 作者把 campaign 与人工筛选 organic trends 转成用户 engagement networks → 用图分类模型测试 campaign-vs-non-campaign 与 campaign type 分类 → 证据支持 LEN 是大图分类基准，但边界是土耳其 Twitter 2023、非 harmful intent gold、非协调发现算法。

## 章节清单

| 章节 | 解决的问题 | 关键锚点 |
|---|---|---|
| Abstract/Introduction | 定义任务、数据集、公开资源与贡献；说明 campaign-vs-organic 而不是 harmfulness detection。 | PDF p.1 |
| Related Work | 定位图分类方法、图分类数据集、trend manipulation 与 coordination/campaign detection。 | PDF p.2-4 |
| Campaigns Collection Methodology | 用 ephemeral astroturfing 检测得到 campaign topic 标签，说明时间、地区、过滤与人工 type 标注。 | PDF p.4-5 |
| Non-Campaigns Collection Methodology | 用外部事件/体育/节日/内部讨论等启发式人工标注 organic/non-campaign trends。 | PDF p.5 |
| Building Networks | 定义图构造、节点、边、节点/边属性、LaBSE 文本编码、LEN/LEN-small 规模。 | PDF p.5 |
| Graph Classification on Engagement Networks | 说明 75/25 stratified random split、指标、硬件、baseline、GNN/VNGE/LSD、三项任务。 | PDF p.5-7 |
| Results | 报告 binary、campaign type、news-based 子集、运行时、混淆矩阵。 | Table 4-6, Figure 2-3, PDF p.6-9 |
| Limitations | API 不可复现、latest engagement 保留 74% edges、非 campaign 样本偏向热门事件、ephemeral astroturfing 假设。 | PDF p.9 |
| Ethics Checklist/Statement | 公共用户、哈希标识符、CC-BY、不可把 campaign 当 fully inauthentic。 | PDF p.11-12 |
| Appendix | 连通分量统计与 ROC 曲线。 | Table 7, Figure 4-5, PDF p.13-15 |

## 视觉清单

| 编号 | 页码 | 标题/作用 | 关键？ | 处理 |
|---|---:|---|:---:|---|
| Table 1 | p.2 | 图分类数据集规模比较，强调 LEN 图更大。 | 否 | 已视觉核验，背景比较。 |
| Figure 1 | p.3 | ephemeral astroturfing 推文与趋势例子。 | 否 | 已视觉核验，示例非结果证据。 |
| Table 2 | p.4 | LEN 314 图的子类型、节点/边统计和说明。 | 是 | 已视觉核验，支撑数据集与标签审计。 |
| Table 3 | p.5 | LEN-small 100 图统计。 | 是 | 已视觉核验，支撑小数据集设置。 |
| Table 4 | p.6 | Campaign vs. non-campaign 主结果。 | 是 | 已视觉核验，嵌入报告。 |
| Figure 2 | p.6 | 训练运行时随边数变化。 | 是 | 已视觉核验，支撑计算成本。 |
| Table 5 | p.7 | 7 类 campaign type 分类主结果。 | 是 | 已视觉核验，嵌入报告。 |
| Table 6 | p.8 | news-based campaign vs. non-campaign 子集结果。 | 是 | 已视觉核验，嵌入报告。 |
| Figure 3 | p.8 | campaign type 混淆矩阵。 | 是 | 已视觉核验，嵌入报告。 |
| Figure 4 | p.13 | LEN-small ROC/AUROC。 | 是 | 已视觉核验，附录证据。 |
| Figure 5 | p.14 | LEN ROC/AUROC。 | 是 | 已视觉核验，附录证据。 |
| Table 7 | p.15 | 连通分量与 fLCC。 | 是 | 已视觉核验，支撑图结构边界。 |

## 形式化清单

| 对象 | 定义/协议 | 位置 | 是否展开 |
|---|---|---|---|
| Campaign label | fake trend topic 经 ephemeral astroturfing 检测、过滤、人工 type 标注后作为 campaign。 | PDF p.4-5 | 是 |
| Non-campaign label | 由外部事件、体育、节日、内部讨论等启发式人工筛选的 trends。 | PDF p.5 | 是 |
| Engagement network | 节点为 Twitter users；有向边 A→B 表示 A retweet/reply/quote B；重复 pair 只保留 latest engagement，保留约 74% edges。 | PDF p.5 | 是 |
| Node attributes | bio 的 LaBSE embedding + follower/following/tweet count + verified status。 | PDF p.5 | 是 |
| Edge attributes | engagement type、tweet text 的 LaBSE embedding、impression/engagement/likes/timestamp/sensitive。 | PDF p.5 | 是 |
| Split protocol | stratified random sampling 75% train / 25% test；代码中无 validation 使用。 | PDF p.5-6; code train_twitter_MPNN.py lines 182, 347 | 是 |
| GNN architecture | 2-layer GNN + global mean pooling + 2-layer MLP；GINE 使用 edge_attr。 | PDF p.6-7; code lines 431-451 | 是 |
| Metrics | Binary: accuracy/precision/recall/F1；multi-class: accuracy/weighted precision/recall/micro-F1/macro-F1。 | PDF p.6 | 是 |
| Baselines | Text + MLP、GCN/GAT/GIN/GraphSAGE/GINE、VNGE、LSD。 | PDF p.6-7 | 是 |
| 不适用项 | 无理论定理或数学证明；伦理清单也说明无理论结果。 | PDF p.11-12 | 略过，说明原因 |

## 主张-证据清单

| ID | 主张 | 最强证据 | 支持等级 | 主要 caveat |
|---|---|---|---|---|
| C1 | LEN 是大规模 Twitter engagement graph 分类基准。 | Table 1-3, PDF p.1, p.5 | 强支持 | 数据页与 PDF 对 campaign 数有冲突。 |
| C2 | campaign ground truth 来自 ephemeral astroturfing，而不是 harmful intent。 | 方法正文 PDF p.4-5; Ethics PDF p.12 | 部分支持 | 依赖 Elmas 2021/2023 检测假设；非 campaign 不是无协调证明。 |
| C3 | 二分类可区分 campaign/non-campaign，但结果中等且大图更难。 | Table 4, Figure 4-5 | 强支持 | random split 可能同时间/同事件相关泄漏；无跨 campaign/time/platform test。 |
| C4 | campaign type 分类弱于 binary，类别不平衡明显。 | Table 5, Figure 3, PDF p.8 | 强支持 | campaign type 与 harmfulness/intent 不等价。 |
| C5 | 图构造和模型有复现风险。 | Building Networks, Limitations, code snapshot | 强支持 | latest edge、LaBSE preprocessing、requirements 与数据版本未完全锁定。 |
| C6 | 不应把 LEN 称为 Harmfulness SOTA。 | Ethics statement, task定义, Table 5/6 | 强支持 | 论文只讨论可能负面社会影响的类型例子，不提供 harmful gold。 |
