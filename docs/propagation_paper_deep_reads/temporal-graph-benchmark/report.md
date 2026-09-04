# Temporal Graph Benchmark for Machine Learning on Temporal Graphs：深度精读
> **作者**：Huang 等
> **会议/期刊与年份**：2023
> **论文链接**：本地 PDF 为主；正式引用前请以项目文献索引中的官方链接为准
> **实际使用来源**：`H:\Zotero\attenger\Projects\CISCN\Propagation\Huang 等 - 2023 - Temporal graph benchmark for machine learning on temporal graphs.pdf`；本地 PDF 文本层、图表文本卡和正文引用
> **页码约定**：全文使用 1-based PDF 页码
> **论文类型**：基准/数据集/评测协议
> **学科 Lens**：computer-science-ai；动态图学习、信息扩散与可复现评测
> **读者画像**：cross-disciplinary；目标是 reproduce；深度为 deep；语言为 zh-CN
> **视觉能力模式**：text-only
> **解读置信度**：中；方法和结构化数值较可靠，像素级图表内容未核验

> **视觉能力说明**：本报告使用 text-only 工作流生成，未直接核验图像像素内容。图表解释仅依据标题、PDF 文本层、正文引用和结构化文本卡，因此不对坐标轴、颜色、曲线形状、面板布局、裁剪完整性或视觉显著性作未经支持的判断。
> **文本证据边界**：本轮为 text-only；视觉内容未直接核验。
## 1. 核心思想一句话总结（Elevator Pitch）
> TGB 用大规模时间图数据、统一任务、负采样、时间切分和效率指标，让动态图模型能够公平复现和比较。

## 2. 论文背景与动机（Background & Motivation）
### 2.1 具体问题
- PDF p.1-2 认为动态图库和评测标准不足是模型进展受限的重要原因。
- Figure 2（PDF p.3）正文定义 TGB 从数据、任务、负采样到评估的完整 pipeline。
- Figure 3（PDF p.5）定义 node affinity prediction，与一般 link prediction 任务区分。
- Table 1（PDF p.6）给出数据集规模和属性；Table 2/3（PDF p.8-9）给出小、中、大数据集动态链路结果。

### 2.2 为什么重要
- **现实价值**：传播系统需要在严格观测截止时间下判断规模、趋势、下一跳或预测区间，错误的候选集和时间泄漏会直接造成过高估计。
- **学术价值**：论文分别处理多尺度扩散、连续时间图表示、归纳式节点泛化、基准协议和在线不确定性校准；这些问题共同决定系统预测是否可信。
- **CogGuard 场景**：观测分析和预测模型必须分离；预测只能读取 `observed_until` 之前的数据，并把候选覆盖、模型状态和证据引用返回给前端。

### 2.3 论文之前的研究版本
| 路线 | 代表方法 | 有效之处 | 关键局限 | 本文回应 |
|---|---|---|---|---|
| 宏观扩散预测 | 特征回归、RNN、点过程 | 能预测最终规模或增长 | 忽略连续演化和不确定性 | 引入动态图、趋势生成或多任务约束 |
| 微观下一跳/链路预测 | GNN、TGN、Transformer | 能编码时间关系 | 依赖候选协议，可能是传递式而非归纳式 | 明确负采样、时间切分和新节点设置 |
| 可信预测 | 固定分位数或固定阈值 | 实现简单 | 分布漂移下局部覆盖不稳定 | 在线自适应更新或校准区间 |

### 2.4 从痛点到研究问题
> 旧方法依赖静态快照、有限候选或固定误差假设，在动态传播和分布漂移下容易失效；本文通过 数据集按 temporal link property prediction 与 node affinity prediction 组织，pipeline 固定训练/验证/测试、负采样、评估和效率统计。，使 解决动态图研究中数据规模小、任务定义不一致、负样本协议不透明和只报告准确率不报告成本的问题。，但其证据范围仍由数据集、时间切分、候选生成和实现版本限定。

- **作者主张**：提供多尺度 temporal graph 数据集、基准任务和可复用评测管线。
- **论文直接证据**：正文和对应 Figure/Table/Algorithm 的页码锚点见第 3、4 节。
- **本文推断**：迁移到 CogGuard 时，必须把论文任务定义和系统的真实事件任务分开，不能把 transductive 结果直接写成开放世界新用户预测。
- **外部背景**：动态图链路预测、信息级联预测和 conformal prediction 的指标并不天然等价，跨论文比较必须统一观察窗口、预测窗口和候选协议。

## 3. 核心方法/理论/研究设计详解（Core Method, Theory, or Study Design）
### 3.1 总体框架
`观测事件/时间边流 → 时间与结构编码 → 共享或任务特有表示 → 预测/校准输出 → 严格时间评估`

**数据流解释**：输入只能使用观测截止时间之前的事件、用户、边、时间戳和合法训练统计；中间模块负责保留时间顺序、局部结构和跨事件关系；输出根据论文类型对应最终规模、未来趋势、下一跳用户、链路分数、图表示或预测区间。

### 3.2 核心流程
1. **起点**：读取带时间戳的 cascade 或 temporal interaction stream。
2. **结构编码**：带时间戳的边、节点属性、动态链路、节点偏好/亲和关系及时间切分。
3. **任务输出**：输出动态链路预测 MRR/AP 等指标、node affinity prediction 指标、推理时间、训练时间和显存。
4. **评估**：Figure 2 展示 TGB pipeline；Table 1/2/3/4/6/7 报告数据与结果；Figure 4-7 报告推理/训练时间、显存和额外属性。

### 3.3 关键步骤、组件或概念
- TGB 将每个时间边预测任务拆成时间顺序的数据流、固定的正边和负边、模型推理以及统一指标。动态链路任务在时刻 t 预测未来交互；node affinity 任务预测用户对节点/项目的偏好。数据管线还显式记录 transductive/inductive、历史负采样、推理时间、训练时间和 GPU 内存。

### 3.4 关键形式化内容
排名指标可写为 `MRR = (1/N) Σ_i 1/r_i`，其中 `r_i` 是真实未来边在候选列表中的名次。AP/MRR 只有在候选集和负采样协议固定时才可比较；node affinity 是另一种任务，不能与下一跳用户预测混为一谈。

### 3.5 核心创新
1. 数据层：提供跨规模、跨关系类型的 temporal graph 数据集。
2. 协议层：统一时间切分、负采样、指标和任务定义。
3. 工程层：把训练/推理时间与 GPU 内存纳入复现报告。

## 4. 证据与结果分析（Evidence & Results）
### 4.1 研究设计与证据协议
- **研究问题/假设**：论文主要检验方法是否改善其定义的任务；不能把论文在封闭候选集上的结果直接外推成开放世界新用户发现。
- **数据与样本**：以论文明确列出的数据集、时间范围、节点/边定义和观察窗口为准；报告中的外部系统数据不能替代论文证据。
- **比较与评估**：优先记录论文原始指标、训练设置、负采样、时间切分、重复次数和消融；若原文未报告方差或置信区间，本文不补造。
- **不确定性**：区分作者主张、论文直接结果、本文推断和外部背景；所有核心数字都带 PDF 页码或图表锚点。

### 4.2 完整图表覆盖清单
| 编号 | PDF 页码 | 作用 | 是否关键 | 文本证据与限制 |
|---|---:|---|:---:|---|
| Figure 1 | PDF p.2 | 辅助背景、消融、复杂度或附录证据 | 否 | TGB consists of a diverse set of datasets that are one order of magnitude larger than existing datasets in terms of number of nodes, edges, and timestamps.；text-only，未直接核验图像像素。 |
| Figure 2 | PDF p.3 | 方法、理论或主结果 | 是 | Overview of the Temporal Graph Benchmark (TGB) pipeline: (a) TGB includes large-scale and realistic datasets from five different domains with both dynamic link prediction and node property prediction tasks. (b) TGB automatically downloads datasets and processes them into numpy, PyTorch and PyG compatible TemporalData formats. (c) Novel TG models can be easily evaluated on TGB datasets via reproducible and realistic evaluation protocols. (d) TGB provides public and online leaderboards to track recent developments in temporal graph learning domain. The code is publicly available as a Python library.；text-only，未直接核验图像像素。 |
| Figure 3 | PDF p.5 | 方法、理论或主结果 | 是 | The node affinity prediction task aims to predict how the preference of a user towards items changes over time. In the tgbn-genre example, the task is to predict the frequency at which the user would listen to each genre over the next week given their listening history until today.；text-only，未直接核验图像像素。 |
| Table 1 | PDF p.6 | 方法、理论或主结果 | 是 | Dataset Statistics. Dataset names are colored based on their scale as small, medium, and large. ¶: Edges can be Weighted, Directed, or Attributed.；text-only，未直接核验图像像素。 |
| Table 1 | PDF p.6 | 方法、理论或主结果 | 是 | shows the statistics and properties of the temporal graph datasets provided by TGB. Datasets such as tgbl-flight, tgbl-comment, tgbl-coin, and tgbn-reddit are orders of magnitude larger than existing TG benchmark datasets [35, 33, 24], while their number of nodes and edges span a wide spectrum, ranging from thousands to millions. In addition, TGB dataset domains are highly diverse, coming from five distinct domains including social networks, interaction networks, rating networks, traffic networks, and trade networks. Moreover, the duration of the datasets varies from months to years, and the number of timestamps in TGB datasets ranges from 32 to more than 30 million with diverse ranges of time granularity from UNIX timestamps to annually. The datasets can be weighted, directed, or have edge attributes. We also report the surprise index (i.e., /Etest\Etrain/；text-only，未直接核验图像像素。 |
| Table 2 | PDF p.8 | 方法、理论或主结果 | 是 | Results for dynamic link property prediction on small datasets.；text-only，未直接核验图像像素。 |
| Figure 4 | PDF p.8 | 辅助背景、消融、复杂度或附录证据 | 否 | Test set inference time of TG methods can have up to two orders of magnitude difference.；text-only，未直接核验图像像素。 |
| Table 2a | PDF p.8 | 辅助背景、消融、复杂度或附录证据 | 否 | shows the performance of TG methods for dynamic link property prediction on the tgbl-wiki dataset. tgbl-wiki is an existing dataset where many methods achieve over-optimistic performance in the literature [35, 46, 9]. With TGB’s evaluation protocol, there is now a clear distinction in model performance and NAT achieves the best result on this dataset. As tgbl-wiki is the smallest dataset in this task, it is computationally feasible to sample all possible destinations of a given source node. Thus, we compare the true destination with all possible negative destinations in this dataset. In Table 2b, we report the results on tgbl-review where we sample 100 negative edges per positive edge. Here, we observe that many of the best performing methods on tgbl-wiki has a significant drop in performance including NAT, CAWN and Edgebank. More notably, the method rankings also changed significantly with GraphMixer and TGAT being the top two methods. This observation emphasizes the importance of dataset diversity when benchmarking TG methods. In Appendix H, we conduct an ablation study on the effect of number of negative samples on the performance of dynamic link property prediction.；text-only，未直接核验图像像素。 |
| Figure 5 | PDF p.9 | 辅助背景、消融、复杂度或附录证据 | 否 | Total train and validation time of TG methods can have two orders of magnitude difference.；text-only，未直接核验图像像素。 |
| Table 3 | PDF p.9 | 方法、理论或主结果 | 是 | Results for dynamic link property prediction task on medium and large datasets.；text-only，未直接核验图像像素。 |
| Figure 4a | PDF p.9 | 辅助背景、消融、复杂度或附录证据 | 否 | and 4b show the inference time of different methods for the test set of tgbl-wiki and tgbl-review, respectively. Similarly, Figure 5a and 5b show the total training and validation time of TG methods for tgbl-wiki and tgbl-review. Notice that as a heuristic baseline, EdgeBank inference, train, or validation time is generally at least one order of magnitude lower than neural network based methods. We also observe an order of difference in inference time within TG methods. We believe one important future direction is to improve the computational time of these models to be closer to baselines such as EdgeBank, which can better scale to large real-world temporal graphs.；text-only，未直接核验图像像素。 |
| Table 3 | PDF p.9 | 方法、理论或主结果 | 是 | shows the performance of TG methods on medium and large TGB datasets. Note that some methods, including CAWN, TCL, and GraphMixer, ran out of memory on GPU for these datasets, thus their performance is not reported. Overall, TGN has the best performance on all of these three datasets. Surprisingly, the EdgeBank heuristic is highly competitive on the tgbl-coin dataset where it even significantly outperforms DyRep. Therefore, it is important to include EdgeBank as a baseline for all datasets. Another observation is that for medium and large TGB datasets, there can be a significant performance change for a single model between the validation and test set. This is because TGB datasets span over a long time (such as tgbl-comment, lasting 5 years) and one can expect that models need to deal with potential distribution shifts between the validation set and the test set. Figure 6a, 6b and 6c reports the test time for TG methods on tgbl-coin, tgbl-flight and tgbl-comment, respectively. On both tgbl-coin and tgbl-comment, Edgebank is at least one order of magnitude faster than TGN and DyRep while on the tgbl-flight, due to the large number of temporal edges, DyRep is the fastest method.；text-only，未直接核验图像像素。 |
| Table 4 | PDF p.9 | 方法、理论或主结果 | 是 | shows the performance of various methods on the node affinity prediction task in the dynamic node property prediction category. As node-level tasks have received less attention compared to edge-level tasks in the literature, adopting methods that are specially designed for link prediction to this task is non-trivial. As a result, these methods are omitted in this section. Considering Table 4, the key observation is that simple heuristics like persistence forecast and moving average are strong contenders to TG methods such as DyRep and TGN. Notably, persistence forecast is SOTA on tgbn-trade while moving average is the best performing on other datasets. TGN is second place on tgbn-genre dataset. Different from link prediction where the existence of a link is casted as binary classification, the node affinity prediction task compares the likelihood or weight that the model assigns to different target nodes (mostly positive links). These results highlight the need for the future development of TG methods that can acquire flexible node representations capable of learning how user preferences evolve over time.；text-only，未直接核验图像像素。 |
| Figure 6 | PDF p.10 | 辅助背景、消融、复杂度或附录证据 | 否 | Inference time comparison of TG methods.；text-only，未直接核验图像像素。 |
| Table 4 | PDF p.10 | 辅助背景、消融、复杂度或附录证据 | 否 | Node affinity prediction results.；text-only，未直接核验图像像素。 |
| Figure 7 | PDF p.17 | 辅助背景、消融、复杂度或附录证据 | 否 | GPU Memory Usage for tgbl-wiki dataset.；text-only，未直接核验图像像素。 |
| Table 5 | PDF p.17 | 辅助背景、消融、复杂度或附录证据 | 否 | Additional dataset properties. Dataset names are colored based on their scale as small, medium, and large. ⋆: denotes the average number of edges per timestamp.；text-only，未直接核验图像像素。 |
| Table 6 | PDF p.18 | 方法、理论或主结果 | 是 | Results for dynamic link property prediction on small datasets with 20 negative samples.；text-only，未直接核验图像像素。 |
| Table 7 | PDF p.18 | 方法、理论或主结果 | 是 | Transductive vs. Inductive Setting on tgbl-wiki Dataset.；text-only，未直接核验图像像素。 |

### 4.3 关键证据与主要结果
- Table 2（PDF p.8）报告小数据集动态链路预测结果；Table 3（PDF p.9）报告中、大数据集结果，体现规模对方法和成本的影响。
- Figure 4/4a/5/6（PDF p.8-10）正文将推理时间、训练时间和效率作为基准的一部分，而不是附属信息。
- Table 4（PDF p.9-10）报告 node affinity prediction，说明动态图任务不只是一种链路预测。
- Table 6/7（PDF p.18）提供更多负样本和 transductive/inductive 对比，直接支撑 CogGuard 必须显式声明候选协议。

### 4.4 逐图表解释
#### Figure 1（PDF p.2；非关键）
- **原始标题**：TGB consists of a diverse set of datasets that are one order of magnitude larger than existing datasets in terms of number of nodes, edges, and timestamps.
- **可恢复证据**：`assets/text/visuals/figure-1-p002.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 2（PDF p.3；关键）
- **原始标题**：Overview of the Temporal Graph Benchmark (TGB) pipeline: (a) TGB includes large-scale and realistic datasets from five different domains with both dynamic link prediction and node property prediction tasks. (b) TGB automatically downloads datasets and processes them into numpy, PyTorch and PyG compatible TemporalData formats. (c) Novel TG models can be easily evaluated on TGB datasets via reproducible and realistic evaluation protocols. (d) TGB provides public and online leaderboards to track recent developments in temporal graph learning domain. The code is publicly available as a Python library.
- **可恢复证据**：`assets/text/visuals/figure-2-p003.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 3（PDF p.5；关键）
- **原始标题**：The node affinity prediction task aims to predict how the preference of a user towards items changes over time. In the tgbn-genre example, the task is to predict the frequency at which the user would listen to each genre over the next week given their listening history until today.
- **可恢复证据**：`assets/text/visuals/figure-3-p005.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 1（PDF p.6；关键）
- **原始标题**：Dataset Statistics. Dataset names are colored based on their scale as small, medium, and large. ¶: Edges can be Weighted, Directed, or Attributed.
- **可恢复证据**：`assets/text/visuals/table-1-p006.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 1（PDF p.6；关键）
- **原始标题**：shows the statistics and properties of the temporal graph datasets provided by TGB. Datasets such as tgbl-flight, tgbl-comment, tgbl-coin, and tgbn-reddit are orders of magnitude larger than existing TG benchmark datasets [35, 33, 24], while their number of nodes and edges span a wide spectrum, ranging from thousands to millions. In addition, TGB dataset domains are highly diverse, coming from five distinct domains including social networks, interaction networks, rating networks, traffic networks, and trade networks. Moreover, the duration of the datasets varies from months to years, and the number of timestamps in TGB datasets ranges from 32 to more than 30 million with diverse ranges of time granularity from UNIX timestamps to annually. The datasets can be weighted, directed, or have edge attributes. We also report the surprise index (i.e., |Etest\Etrain|
- **可恢复证据**：`assets/text/visuals/table-1-p006.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 2（PDF p.8；关键）
- **原始标题**：Results for dynamic link property prediction on small datasets.
- **可恢复证据**：`assets/text/visuals/table-2-p008.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 4（PDF p.8；非关键）
- **原始标题**：Test set inference time of TG methods can have up to two orders of magnitude difference.
- **可恢复证据**：`assets/text/visuals/figure-4-p008.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 2a（PDF p.8；非关键）
- **原始标题**：shows the performance of TG methods for dynamic link property prediction on the tgbl-wiki dataset. tgbl-wiki is an existing dataset where many methods achieve over-optimistic performance in the literature [35, 46, 9]. With TGB’s evaluation protocol, there is now a clear distinction in model performance and NAT achieves the best result on this dataset. As tgbl-wiki is the smallest dataset in this task, it is computationally feasible to sample all possible destinations of a given source node. Thus, we compare the true destination with all possible negative destinations in this dataset. In Table 2b, we report the results on tgbl-review where we sample 100 negative edges per positive edge. Here, we observe that many of the best performing methods on tgbl-wiki has a significant drop in performance including NAT, CAWN and Edgebank. More notably, the method rankings also changed significantly with GraphMixer and TGAT being the top two methods. This observation emphasizes the importance of dataset diversity when benchmarking TG methods. In Appendix H, we conduct an ablation study on the effect of number of negative samples on the performance of dynamic link property prediction.
- **可恢复证据**：`assets/text/visuals/table-2a-p008.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 5（PDF p.9；非关键）
- **原始标题**：Total train and validation time of TG methods can have two orders of magnitude difference.
- **可恢复证据**：`assets/text/visuals/figure-5-p009.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 3（PDF p.9；关键）
- **原始标题**：Results for dynamic link property prediction task on medium and large datasets.
- **可恢复证据**：`assets/text/visuals/table-3-p009.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 4a（PDF p.9；非关键）
- **原始标题**：and 4b show the inference time of different methods for the test set of tgbl-wiki and tgbl-review, respectively. Similarly, Figure 5a and 5b show the total training and validation time of TG methods for tgbl-wiki and tgbl-review. Notice that as a heuristic baseline, EdgeBank inference, train, or validation time is generally at least one order of magnitude lower than neural network based methods. We also observe an order of difference in inference time within TG methods. We believe one important future direction is to improve the computational time of these models to be closer to baselines such as EdgeBank, which can better scale to large real-world temporal graphs.
- **可恢复证据**：`assets/text/visuals/figure-4a-p009.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 3（PDF p.9；关键）
- **原始标题**：shows the performance of TG methods on medium and large TGB datasets. Note that some methods, including CAWN, TCL, and GraphMixer, ran out of memory on GPU for these datasets, thus their performance is not reported. Overall, TGN has the best performance on all of these three datasets. Surprisingly, the EdgeBank heuristic is highly competitive on the tgbl-coin dataset where it even significantly outperforms DyRep. Therefore, it is important to include EdgeBank as a baseline for all datasets. Another observation is that for medium and large TGB datasets, there can be a significant performance change for a single model between the validation and test set. This is because TGB datasets span over a long time (such as tgbl-comment, lasting 5 years) and one can expect that models need to deal with potential distribution shifts between the validation set and the test set. Figure 6a, 6b and 6c reports the test time for TG methods on tgbl-coin, tgbl-flight and tgbl-comment, respectively. On both tgbl-coin and tgbl-comment, Edgebank is at least one order of magnitude faster than TGN and DyRep while on the tgbl-flight, due to the large number of temporal edges, DyRep is the fastest method.
- **可恢复证据**：`assets/text/visuals/table-3-p009.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 4（PDF p.9；关键）
- **原始标题**：shows the performance of various methods on the node affinity prediction task in the dynamic node property prediction category. As node-level tasks have received less attention compared to edge-level tasks in the literature, adopting methods that are specially designed for link prediction to this task is non-trivial. As a result, these methods are omitted in this section. Considering Table 4, the key observation is that simple heuristics like persistence forecast and moving average are strong contenders to TG methods such as DyRep and TGN. Notably, persistence forecast is SOTA on tgbn-trade while moving average is the best performing on other datasets. TGN is second place on tgbn-genre dataset. Different from link prediction where the existence of a link is casted as binary classification, the node affinity prediction task compares the likelihood or weight that the model assigns to different target nodes (mostly positive links). These results highlight the need for the future development of TG methods that can acquire flexible node representations capable of learning how user preferences evolve over time.
- **可恢复证据**：`assets/text/visuals/table-4-p009.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 6（PDF p.10；非关键）
- **原始标题**：Inference time comparison of TG methods.
- **可恢复证据**：`assets/text/visuals/figure-6-p010.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 4（PDF p.10；非关键）
- **原始标题**：Node affinity prediction results.
- **可恢复证据**：`assets/text/visuals/table-4-p010.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 7（PDF p.17；非关键）
- **原始标题**：GPU Memory Usage for tgbl-wiki dataset.
- **可恢复证据**：`assets/text/visuals/figure-7-p017.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 5（PDF p.17；非关键）
- **原始标题**：Additional dataset properties. Dataset names are colored based on their scale as small, medium, and large. ⋆: denotes the average number of edges per timestamp.
- **可恢复证据**：`assets/text/visuals/table-5-p017.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 6（PDF p.18；关键）
- **原始标题**：Results for dynamic link property prediction on small datasets with 20 negative samples.
- **可恢复证据**：`assets/text/visuals/table-6-p018.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 7（PDF p.18；关键）
- **原始标题**：Transductive vs. Inductive Setting on tgbl-wiki Dataset.
- **可恢复证据**：`assets/text/visuals/table-7-p018.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

### 4.5 定性证据、失败案例与边界
- 本轮未进行像素级视觉核验，因此不对图中的颜色、坐标、曲线相交、布局密度或视觉异常作额外结论。
- 论文数字只支持其定义的任务、数据集、时间窗口和候选协议；不能直接外推到 CogGuard 的真实采集事件。
- 对动态图预测，必须特别检查 transductive 与 inductive 设置、未来节点是否进入候选集、负采样是否读取测试期统计以及是否存在重复事件。
- 对趋势预测，必须区分点预测与区间预测；未校准区间不能称为置信区间。

### 4.6 主张—证据审计
| 核心主张 | 最强证据 | 支持等级 | 最大替代解释 | 最小补强实验 |
|---|---|---|---|---|
| C1: TGB 统一时间图任务、数据和评测 pipeline。 | Figure 2, PDF p.3; PDF p.1-3 | 强支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C2: TGB 明确区分动态链路预测和 node affinity prediction。 | Figure 3, PDF p.5; Table 4, PDF p.9-10 | 强支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C3: 动态图模型比较必须报告负采样、时间切分和效率。 | Table 6/7, PDF p.18; Figure 4/5/6, PDF p.8-10 | 强支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C4: TGB 的 MRR/AP 可直接作为 CogGuard 下一跳全部场景的唯一指标。 | PDF p.5; Table 2/3, PDF p.8-9 | 部分支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |

### 4.7 可靠性、复现性与争议点
- **最可靠结论**：方法定义、输入输出、算法步骤和正文明确报告的表格数值。
- **最弱结论**：仅由图注或 OCR 文本卡推断的像素级趋势，以及把作者称谓转写为普适 SOTA。
- **公平性风险**：数据版本、负采样、时间切分、候选集合、超参数和硬件差异都可能解释性能差异。
- **复现要求**：固定代码 revision、数据版本、随机种子、观察窗口、预测窗口、候选生成、失败日志和完整 JSON 输出。
- **实现核对**：对可运行模型，还要记录 patch/历史长度、邻居采样、负采样类型、显存峰值、单批推理时间和失败重试次数；这些工程量会影响系统是否适合在线事件监测。
- **最小复现实验**：先选一个数据集和一个严格时间切分，复现论文主指标；随后只改变一个组件或协议变量，并保持数据版本、候选集合、训练轮数和随机种子不变。若结果差异超过随机波动，再检查日志中的时间泄漏、样本重复、负采样和用户映射。

## 5. 论文的贡献与影响（Contribution & Impact）
### 5.1 主要贡献
1. 数据层：提供跨规模、跨关系类型的 temporal graph 数据集。
2. 协议层：统一时间切分、负采样、指标和任务定义。
3. 工程层：把训练/推理时间与 GPU 内存纳入复现报告。

### 5.2 对 CogGuard 传播分析与预测的启发
- 传播分析侧应保留 provenance 证据、显式/重建/推断边区分、真实用户映射和可回溯详情；预测侧只读取观测前缀，不能复用未来真实节点。
- 下一跳输出需要明确是“已知用户再激活”还是“开放世界新用户激活”；候选覆盖不足时应 abstain，而不是输出匿名 bucket。
- 宏观趋势输出应同时返回观测规模、预测规模、趋势点、误差区间状态和校准状态；没有校准时不能把集中度分数称为置信度。
- 评测应统一使用时间切分、合法负采样、候选覆盖、Hits/MAP/MRR/NDCG、MSLE/MAE/RMSE/MAPE 以及失败原因。

### 5.3 值得探索的未来方向
1. **为 CogGuard 建立 propagation prediction benchmark schema，至少记录 observed_until、horizon、candidate source 和 edge provenance。**
2. **将 micro 输出拆成已知用户再激活、候选邻居激活和新用户归纳式激活三种设置。**
3. **在前端展示候选覆盖、MRR/Hits/MAP、推理时延和模型 abstain 原因，而不是只显示一个分数。**

## 6. 结论（Conclusion）
TGB 不是单一预测模型，而是 CogGuard 预测模块最重要的评测协议参考；它能显著降低系统中“模型跑通但比较不公平”的风险。

> **最终判断**：非常值得复现其协议和记录格式；不必把 TGB 所有数据集都接入系统，但应采用其时间切分、负采样、指标和效率报告思想。
>
> **复现清单**：固定论文版本和代码 revision；准备同版本数据；实现论文输入协议；复现主表和关键消融；记录 3 个以上随机种子、时间切分、候选生成、显存/运行时间和失败日志；最后再迁移到 CogGuard 真实事件。
