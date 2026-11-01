# Temporal Graph Networks for Deep Learning on Dynamic Graphs：深度精读
> **作者**：Emanuele Rossi, Ben Chamberlain, Fabrizio Frasca, Davide Eynard, Federico Monti, Michael M. Bronstein
> **会议/期刊与年份**：ICML 2020
> **论文链接**：本地 PDF 为主；正式引用前请以项目文献索引中的官方链接为准
> **实际使用来源**：`H:\Zotero\attenger\Projects\CISCN\Propagation\Rossi 等 - 2020 - Temporal graph networks for deep learning on dynamic graphs.pdf`；本地 PDF 文本层、图表文本卡和正文引用
> **页码约定**：全文使用 1-based PDF 页码
> **论文类型**：方法/模型
> **学科 Lens**：computer-science-ai；动态图学习、信息扩散与可复现评测
> **读者画像**：cross-disciplinary；目标是 reproduce；深度为 deep；语言为 zh-CN
> **视觉能力模式**：text-only
> **解读置信度**：中；方法和结构化数值较可靠，像素级图表内容未核验

> **视觉能力说明**：本报告使用 text-only 工作流生成，未直接核验图像像素内容。图表解释仅依据标题、PDF 文本层、正文引用和结构化文本卡，因此不对坐标轴、颜色、曲线形状、面板布局、裁剪完整性或视觉显著性作未经支持的判断。
> **文本证据边界**：本轮为 text-only；视觉内容未直接核验。
## 1. 核心思想一句话总结（Elevator Pitch）
> TGN 用事件驱动的节点记忆、时间编码和邻居聚合，在连续时间动态图上进行链路预测和节点分类。

## 2. 论文背景与动机（Background & Motivation）
### 2.1 具体问题
- PDF p.1-2 将动态图表示为带时间戳的交互事件流，强调节点状态随事件持续更新。
- Figure 1（PDF p.3）标题明确展示一批时间戳交互的 TGN 计算过程；正文解释 memory、message 和 embedding 的关系。
- Figure 2（PDF p.5）与 PDF p.4-5 的文字支持 raw message store、memory updater、message aggregator 和 embedding module 的训练数据流。
- Figure 4（PDF p.14）和 Algorithm 1（PDF p.14）提供更接近实现的 TGN 图式与训练顺序。

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
> 旧方法依赖静态快照、有限候选或固定误差假设，在动态传播和分布漂移下容易失效；本文通过 每个交互事件产生 raw message；memory updater 更新源节点和目标节点记忆；embedding module 结合时间编码与采样邻居形成当前节点表示。，使 解决静态图或快照式 GNN 难以保留连续事件历史、时间间隔和节点状态的问题。，但其证据范围仍由数据集、时间切分、候选生成和实现版本限定。

- **作者主张**：以统一 memory/message/embedding 组件构造可扩展的连续时间动态图学习框架。
- **论文直接证据**：正文和对应 Figure/Table/Algorithm 的页码锚点见第 3、4 节。
- **本文推断**：迁移到 CogGuard 时，必须把论文任务定义和系统的真实事件任务分开，不能把 transductive 结果直接写成开放世界新用户预测。
- **外部背景**：动态图链路预测、信息级联预测和 conformal prediction 的指标并不天然等价，跨论文比较必须统一观察窗口、预测窗口和候选协议。

## 3. 核心方法/理论/研究设计详解（Core Method, Theory, or Study Design）
### 3.1 总体框架
`观测事件/时间边流 → 时间与结构编码 → 共享或任务特有表示 → 预测/校准输出 → 严格时间评估`

**数据流解释**：输入只能使用观测截止时间之前的事件、用户、边、时间戳和合法训练统计；中间模块负责保留时间顺序、局部结构和跨事件关系；输出根据论文类型对应最终规模、未来趋势、下一跳用户、链路分数、图表示或预测区间。

### 3.2 核心流程
1. **起点**：读取带时间戳的 cascade 或 temporal interaction stream。
2. **结构编码**：时间戳交互边、节点 memory、raw message、时间编码和时间邻居共同形成动态节点状态。
3. **任务输出**：在未来边预测中对候选边打分；在动态节点分类中对当前节点表示分类。
4. **评估**：Table 2 报告未来边 AP，Table 3 报告动态节点分类 ROC AUC；Figure 3 为消融；Algorithm 1 给出训练流程。

### 3.3 关键步骤、组件或概念
- TGN 将连续事件流按时间处理。对事件 e=(u,v,t)，先读取并按时间编码的历史 memory，构造 raw message；message aggregator 汇总同一时间窗口的消息；memory updater 更新节点状态。随后 embedding module 从当前 memory、时间差和采样邻居生成节点 embedding，用于未来边预测或节点分类。

### 3.4 关键形式化内容
节点 memory 可记作 `s_i(t) = Update(s_i(t^-), m_i(t))`；消息可记作 `m_i(t)=Message(s_i(t^-), s_j(t^-), φ(t-t_i), e_{ij})`；节点 embedding 由当前 memory 与时间邻居聚合得到。这里是按正文和 Algorithm 1 的操作语义重写，符号不替代论文原式。

### 3.5 核心创新
1. 架构层：提出可组合的 memory、message 和 embedding modules，而非固定一种 GNN。
2. 任务层：用同一连续时间表示支持未来边预测和动态节点分类。
3. 工程层：给出可实现的训练算法和邻居采样策略，适合构建动态图预测服务。

## 4. 证据与结果分析（Evidence & Results）
### 4.1 研究设计与证据协议
- **研究问题/假设**：论文主要检验方法是否改善其定义的任务；不能把论文在封闭候选集上的结果直接外推成开放世界新用户发现。
- **数据与样本**：以论文明确列出的数据集、时间范围、节点/边定义和观察窗口为准；报告中的外部系统数据不能替代论文证据。
- **比较与评估**：优先记录论文原始指标、训练设置、负采样、时间切分、重复次数和消融；若原文未报告方差或置信区间，本文不补造。
- **不确定性**：区分作者主张、论文直接结果、本文推断和外部背景；所有核心数字都带 PDF 页码或图表锚点。

### 4.2 完整图表覆盖清单
| 编号 | PDF 页码 | 作用 | 是否关键 | 文本证据与限制 |
|---|---:|---|:---:|---|
| Figure 1 | PDF p.3 | 方法、理论或主结果 | 是 | Computations performed by TGN on a batch of time-stamped interactions. Top: embeddings are produced by the embedding module using the temporal graph and the node’s memory (1). The embeddings are then used to predict the batch interactions and compute the loss (2, 3). Bottom: these same interactions are used to update the memory (4, 5, 6). This is a simpliﬁed ﬂow of operations which would prevent the training of all the modules in the bottom as they would not receiving a gradient. Section 3.2 explains how to change the ﬂow of operations to solve this problem and ﬁgure 2 shows the complete diagram.；text-only，未直接核验图像像素。 |
| Figure 2 | PDF p.5 | 方法、理论或主结果 | 是 | Flow of operations of TGN used to train the memory-related modules. Raw Message Store stores the necessary raw information to compute messages, i.e. the input to the message functions, which we call raw messages, for interactions which have been processed by the model in the past. This allows the model to delay the memory update brought by an interaction to later batches. At ﬁrst, the memory is updated using messages computed from raw messages stored in previous batches (1, 2, 3). The embeddings can then be computed using the just updated memory (grey link) (4). By doing this, the computation of the memory-related modules directly inﬂuences the loss (5, 6), and they receive a gradient. Finally, the raw messages for this batch interactions are stored in the raw message store (6) to be used in future batches.；text-only，未直接核验图像像素。 |
| Table 1 | PDF p.6 | 辅助背景、消融、复杂度或附录证据 | 否 | Previous models for deep learning on continuous-time dynamic graphs are speciﬁc case of our TGN framework. Shown are multiple variants of TGN used in our ablation studies. method (l,n) refers to graph convolution using l layers and n neighbors. †uses t-batches. ∗uses uniform sampling of neighbors, while the default is sampling the most recent neighbors. ‡message aggregation not explained in the paper. ∥uses a summary of the destination node neighborhood (obtained through graph attention) as additional input to the message function.；text-only，未直接核验图像像素。 |
| Table 2 | PDF p.7 | 方法、理论或主结果 | 是 | Average Precision (%) for future edge prediction task in transductive and inductive settings. First, Second, Third best performing method. ∗Static graph method. †Does not support inductive.；text-only，未直接核验图像像素。 |
| Table 3 | PDF p.7 | 方法、理论或主结果 | 是 | ROC AUC % for the dynamic node classiﬁcation. ∗Static graph method.；text-only，未直接核验图像像素。 |
| Table 2 | PDF p.7 | 方法、理论或主结果 | 是 | presents the results on future edge predic- tion. Our model clearly outperforms the baselines by a large margin in both transductive and induc- tive settings on all datasets. The gap is particularly large on the Twitter dataset, where we outperfom the second-best method (DyRep) by over 4% and 10% in the transductive and inductive case respec- tively. Table 3 shows the results on dynamic node classiﬁcation, where again our model obtains state- of-the-art results, with a large improvement over all other methods.；text-only，未直接核验图像像素。 |
| Figure 3 | PDF p.8 | 辅助背景、消融、复杂度或附录证据 | 否 | Ablation studies on the Wikipedia dataset for the transductive setting of the future edge prediction task. Means and standard deviations were computed over 10 runs.；text-only，未直接核验图像像素。 |
| Figure 4 | PDF p.14 | 方法、理论或主结果 | 是 | Schematic diagram of TGN. m_raw(t) is the raw message generated by event e(t), ˜t is the instant of time of the last event involving each node, and t−the one immediately preceding t.；text-only，未直接核验图像像素。 |
| Algorithm 1 | PDF p.14 | 方法、理论或主结果 | 是 | Training TGN；text-only，未直接核验图像像素。 |
| Table 4 | PDF p.15 | 辅助背景、消融、复杂度或附录证据 | 否 | Statistics of the datasets used in the experiments.；text-only，未直接核验图像像素。 |
| Table 5 | PDF p.16 | 辅助背景、消融、复杂度或附录证据 | 否 | Model Hyperparameters.；text-only，未直接核验图像像素。 |
| Figure 5 | PDF p.16 | 辅助背景、消融、复杂度或附录证据 | 否 | Comparison of two TGN-attn models using different neighbor sampling strategies (when sampling 10 neighbors). Sampling the most recent edges clearly outperforms uniform sampling. Means and standard deviations (visualized as ellipses) were computed over 10 runs.；text-only，未直接核验图像像素。 |

### 4.3 关键证据与主要结果
- Table 2（PDF p.7）报告 transductive 和 inductive future edge prediction 的 AP，直接支持 TGN 作为时间链路预测模型。
- Table 3（PDF p.7）报告动态节点分类 ROC AUC，说明同一记忆框架可用于非链路任务。
- Figure 3（PDF p.8）做 Wikipedia 消融；正文说明 memory、message、attention/neighbor sampling 等设计对性能有影响。
- Table 4、Table 5（PDF p.15-16）给出数据统计和超参数，是复现输入协议、数据规模和配置的关键证据。

### 4.4 逐图表解释
#### Figure 1（PDF p.3；关键）
- **原始标题**：Computations performed by TGN on a batch of time-stamped interactions. Top: embeddings are produced by the embedding module using the temporal graph and the node’s memory (1). The embeddings are then used to predict the batch interactions and compute the loss (2, 3). Bottom: these same interactions are used to update the memory (4, 5, 6). This is a simpliﬁed ﬂow of operations which would prevent the training of all the modules in the bottom as they would not receiving a gradient. Section 3.2 explains how to change the ﬂow of operations to solve this problem and ﬁgure 2 shows the complete diagram.
- **可恢复证据**：`assets/text/visuals/figure-1-p003.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 2（PDF p.5；关键）
- **原始标题**：Flow of operations of TGN used to train the memory-related modules. Raw Message Store stores the necessary raw information to compute messages, i.e. the input to the message functions, which we call raw messages, for interactions which have been processed by the model in the past. This allows the model to delay the memory update brought by an interaction to later batches. At ﬁrst, the memory is updated using messages computed from raw messages stored in previous batches (1, 2, 3). The embeddings can then be computed using the just updated memory (grey link) (4). By doing this, the computation of the memory-related modules directly inﬂuences the loss (5, 6), and they receive a gradient. Finally, the raw messages for this batch interactions are stored in the raw message store (6) to be used in future batches.
- **可恢复证据**：`assets/text/visuals/figure-2-p005.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 1（PDF p.6；非关键）
- **原始标题**：Previous models for deep learning on continuous-time dynamic graphs are speciﬁc case of our TGN framework. Shown are multiple variants of TGN used in our ablation studies. method (l,n) refers to graph convolution using l layers and n neighbors. †uses t-batches. ∗uses uniform sampling of neighbors, while the default is sampling the most recent neighbors. ‡message aggregation not explained in the paper. ∥uses a summary of the destination node neighborhood (obtained through graph attention) as additional input to the message function.
- **可恢复证据**：`assets/text/visuals/table-1-p006.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 2（PDF p.7；关键）
- **原始标题**：Average Precision (%) for future edge prediction task in transductive and inductive settings. First, Second, Third best performing method. ∗Static graph method. †Does not support inductive.
- **可恢复证据**：`assets/text/visuals/table-2-p007.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 3（PDF p.7；关键）
- **原始标题**：ROC AUC % for the dynamic node classiﬁcation. ∗Static graph method.
- **可恢复证据**：`assets/text/visuals/table-3-p007.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 2（PDF p.7；关键）
- **原始标题**：presents the results on future edge predic- tion. Our model clearly outperforms the baselines by a large margin in both transductive and induc- tive settings on all datasets. The gap is particularly large on the Twitter dataset, where we outperfom the second-best method (DyRep) by over 4% and 10% in the transductive and inductive case respec- tively. Table 3 shows the results on dynamic node classiﬁcation, where again our model obtains state- of-the-art results, with a large improvement over all other methods.
- **可恢复证据**：`assets/text/visuals/table-2-p007.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 3（PDF p.8；非关键）
- **原始标题**：Ablation studies on the Wikipedia dataset for the transductive setting of the future edge prediction task. Means and standard deviations were computed over 10 runs.
- **可恢复证据**：`assets/text/visuals/figure-3-p008.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 4（PDF p.14；关键）
- **原始标题**：Schematic diagram of TGN. m_raw(t) is the raw message generated by event e(t), ˜t is the instant of time of the last event involving each node, and t−the one immediately preceding t.
- **可恢复证据**：`assets/text/visuals/figure-4-p014.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Algorithm 1（PDF p.14；关键）
- **原始标题**：Training TGN
- **可恢复证据**：`assets/text/visuals/algorithm-1-p014.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 4（PDF p.15；非关键）
- **原始标题**：Statistics of the datasets used in the experiments.
- **可恢复证据**：`assets/text/visuals/table-4-p015.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 5（PDF p.16；非关键）
- **原始标题**：Model Hyperparameters.
- **可恢复证据**：`assets/text/visuals/table-5-p016.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 5（PDF p.16；非关键）
- **原始标题**：Comparison of two TGN-attn models using different neighbor sampling strategies (when sampling 10 neighbors). Sampling the most recent edges clearly outperforms uniform sampling. Means and standard deviations (visualized as ellipses) were computed over 10 runs.
- **可恢复证据**：`assets/text/visuals/figure-5-p016.md`、图注和正文引用。
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
| C1: TGN 用 memory/message/embedding 组件处理连续时间交互流。 | Figure 1, PDF p.3; Figure 2, PDF p.5; Algorithm 1, PDF p.14 | 强支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C2: TGN 支持未来边预测和动态节点分类。 | Table 2/3, PDF p.7 | 强支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C3: TGN 的效果依赖 memory、消息和邻居采样等组件。 | Figure 3, PDF p.8; PDF p.8 | 部分支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C4: TGN 可以直接解决 CogGuard 的开放世界下一跳预测。 |  | 未支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |

### 4.7 可靠性、复现性与争议点
- **最可靠结论**：方法定义、输入输出、算法步骤和正文明确报告的表格数值。
- **最弱结论**：仅由图注或 OCR 文本卡推断的像素级趋势，以及把作者称谓转写为普适 SOTA。
- **公平性风险**：数据版本、负采样、时间切分、候选集合、超参数和硬件差异都可能解释性能差异。
- **复现要求**：固定代码 revision、数据版本、随机种子、观察窗口、预测窗口、候选生成、失败日志和完整 JSON 输出。
- **实现核对**：对可运行模型，还要记录 patch/历史长度、邻居采样、负采样类型、显存峰值、单批推理时间和失败重试次数；这些工程量会影响系统是否适合在线事件监测。
- **最小复现实验**：先选一个数据集和一个严格时间切分，复现论文主指标；随后只改变一个组件或协议变量，并保持数据版本、候选集合、训练轮数和随机种子不变。若结果差异超过随机波动，再检查日志中的时间泄漏、样本重复、负采样和用户映射。

## 5. 论文的贡献与影响（Contribution & Impact）
### 5.1 主要贡献
1. 架构层：提出可组合的 memory、message 和 embedding modules，而非固定一种 GNN。
2. 任务层：用同一连续时间表示支持未来边预测和动态节点分类。
3. 工程层：给出可实现的训练算法和邻居采样策略，适合构建动态图预测服务。

### 5.2 对 CogGuard 传播分析与预测的启发
- 传播分析侧应保留 provenance 证据、显式/重建/推断边区分、真实用户映射和可回溯详情；预测侧只读取观测前缀，不能复用未来真实节点。
- 下一跳输出需要明确是“已知用户再激活”还是“开放世界新用户激活”；候选覆盖不足时应 abstain，而不是输出匿名 bucket。
- 宏观趋势输出应同时返回观测规模、预测规模、趋势点、误差区间状态和校准状态；没有校准时不能把集中度分数称为置信度。
- 评测应统一使用时间切分、合法负采样、候选覆盖、Hits/MAP/MRR/NDCG、MSLE/MAE/RMSE/MAPE 以及失败原因。

### 5.3 值得探索的未来方向
1. **将 cascade 转换为 `(parent, child, timestamp, edge_type)` 事件流，并明确 explicit/reconstructed/inferred 边的训练边界。**
2. **以观测截止时间前的 memory 初始化下一跳 micro head，候选集必须独立生成并审计。**
3. **结合自适应校准方法输出预测区间，但 TGN 本身只提供表示和打分，不提供概率校准。**

## 6. 结论（Conclusion）
TGN 是下一跳 temporal edge prediction 的可靠基础，但不是传播溯源模型，也不是开放世界新用户预测的充分条件；CogGuard 需要额外解决候选覆盖和真实身份映射。

> **最终判断**：值得复现，适合作为系统级 temporal graph runtime 或 DyGFormer 失败时的可解释 fallback；正式结论必须区分 transductive 和 inductive。
>
> **复现清单**：固定论文版本和代码 revision；准备同版本数据；实现论文输入协议；复现主表和关键消融；记录 3 个以上随机种子、时间切分、候选生成、显存/运行时间和失败日志；最后再迁移到 CogGuard 真实事件。
