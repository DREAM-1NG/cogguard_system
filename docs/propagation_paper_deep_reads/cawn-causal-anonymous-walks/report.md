# Inductive Representation Learning in Temporal Networks via Causal Anonymous Walks：深度精读
> **作者**：Wang 等
> **会议/期刊与年份**：2022
> **论文链接**：本地 PDF 为主；正式引用前请以项目文献索引中的官方链接为准
> **实际使用来源**：`H:\Zotero\attenger\Projects\CISCN\Propagation\Wang 等 - 2022 - Inductive representation learning in temporal networks via causal anonymous walks.pdf`；本地 PDF 文本层、图表文本卡和正文引用
> **页码约定**：全文使用 1-based PDF 页码
> **论文类型**：方法/模型
> **学科 Lens**：computer-science-ai；动态图学习、信息扩散与可复现评测
> **读者画像**：cross-disciplinary；目标是 reproduce；深度为 deep；语言为 zh-CN
> **视觉能力模式**：text-only
> **解读置信度**：中；方法和结构化数值较可靠，像素级图表内容未核验

> **视觉能力说明**：本报告使用 text-only 工作流生成，未直接核验图像像素内容。图表解释仅依据标题、PDF 文本层、正文引用和结构化文本卡，因此不对坐标轴、颜色、曲线形状、面板布局、裁剪完整性或视觉显著性作未经支持的判断。
> **文本证据边界**：本轮为 text-only；视觉内容未直接核验。
## 1. 核心思想一句话总结（Elevator Pitch）
> CAW 用保留因果顺序的匿名时间游走表示局部动态图模式，在不依赖节点身份的情况下支持归纳式链路预测。

## 2. 论文背景与动机（Background & Motivation）
### 2.1 具体问题
- PDF p.1-3 说明动态图的高阶结构和因果顺序对归纳式表示学习重要，而静态或身份依赖表示难以迁移到新节点。
- Figure 1、Figure 2（PDF p.2）通过 triadic closure、feed-forward loops 和 CAW 定义说明，游走保留时间因果关系并去除具体节点身份。
- Figure 3（PDF p.3）正文用于说明 TGAT 在去除节点身份后可能出现结构歧义。
- Theorem/Proposition 与 Algorithm 1（PDF p.4）共同给出 CAW 的提取逻辑和表达性主张。

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
> 旧方法依赖静态快照、有限候选或固定误差假设，在动态传播和分布漂移下容易失效；本文通过 从目标时间前的时间边流提取 causal anonymous walks，对多个游走进行集合化编码，再与端点特征结合进行链路分类。，使 解决 TGAT 等方法在归纳设置下丢失高阶因果结构、或因匿名化过度而混淆不同动态图模式的问题。，但其证据范围仍由数据集、时间切分、候选生成和实现版本限定。

- **作者主张**：通过时间约束、匿名化和游走集合保留可迁移的结构模式，并给出表达性与复杂度分析。
- **论文直接证据**：正文和对应 Figure/Table/Algorithm 的页码锚点见第 3、4 节。
- **本文推断**：迁移到 CogGuard 时，必须把论文任务定义和系统的真实事件任务分开，不能把 transductive 结果直接写成开放世界新用户预测。
- **外部背景**：动态图链路预测、信息级联预测和 conformal prediction 的指标并不天然等价，跨论文比较必须统一观察窗口、预测窗口和候选协议。

## 3. 核心方法/理论/研究设计详解（Core Method, Theory, or Study Design）
### 3.1 总体框架
`观测事件/时间边流 → 时间与结构编码 → 共享或任务特有表示 → 预测/校准输出 → 严格时间评估`

**数据流解释**：输入只能使用观测截止时间之前的事件、用户、边、时间戳和合法训练统计；中间模块负责保留时间顺序、局部结构和跨事件关系；输出根据论文类型对应最终规模、未来趋势、下一跳用户、链路分数、图表示或预测区间。

### 3.2 核心流程
1. **起点**：读取带时间戳的 cascade 或 temporal interaction stream。
2. **结构编码**：时间边流、因果游走、匿名节点序列、端点特征和历史窗口共同构成输入。
3. **任务输出**：输出候选边的正/负分类分数，主要评价 AUC 和 AP；不是直接的传播规模预测。
4. **评估**：Table 2、Table 6-8 报告 AUC/AP；Algorithm 1-3 说明游走提取、在线概率计算和迭代采样；Figure 5-7 分析采样和复杂度。

### 3.3 关键步骤、组件或概念
- 给定查询边 (u,v,t)，只从 t 之前的历史边中提取满足时间因果约束的游走；将节点身份替换为首次出现顺序等匿名编码，形成 CAW。对多个 CAW 做集合聚合，再结合端点的时间特征和可用属性，输入 MLP/序列编码器得到候选边分数。
- Algorithm 1 负责从历史时间边流抽取游走；Algorithm 2 计算在线采样概率；Algorithm 3 迭代采样。关键约束是游走中事件时间单调不减且不读取查询时刻之后的边。匿名化降低对节点 ID 的依赖，但也要求训练/测试特征协议一致。

### 3.4 关键形式化内容
对查询边的预测可抽象为 `score(u,v,t)=f_θ(CAW(u,v,t), x_u, x_v, Δt)`；CAW 是以历史边流为条件的匿名游走集合。论文还给出 temporal WL/表达性相关理论；本报告只保留可从正文恢复的功能关系，不重写无法可靠恢复的完整定理。

### 3.5 核心创新
1. 表示层：将因果时间结构编码为匿名游走集合，增强对未见节点/结构的归纳能力。
2. 理论层：把可表达性和具体采样算法联系起来，避免只给经验性 GNN 结构。
3. 工程层：Algorithm 1-3 给出可落地的在线采样和复杂度控制路径。

## 4. 证据与结果分析（Evidence & Results）
### 4.1 研究设计与证据协议
- **研究问题/假设**：论文主要检验方法是否改善其定义的任务；不能把论文在封闭候选集上的结果直接外推成开放世界新用户发现。
- **数据与样本**：以论文明确列出的数据集、时间范围、节点/边定义和观察窗口为准；报告中的外部系统数据不能替代论文证据。
- **比较与评估**：优先记录论文原始指标、训练设置、负采样、时间切分、重复次数和消融；若原文未报告方差或置信区间，本文不补造。
- **不确定性**：区分作者主张、论文直接结果、本文推断和外部背景；所有核心数字都带 PDF 页码或图表锚点。

### 4.2 完整图表覆盖清单
| 编号 | PDF 页码 | 作用 | 是否关键 | 文本证据与限制 |
|---|---:|---|:---:|---|
| Figure 1 | PDF p.2 | 方法、理论或主结果 | 是 | Triadic closure and feed-forward loops: Causal anonymous walks (CAW) capture the laws.；text-only，未直接核验图像像素。 |
| Figure 2 | PDF p.2 | 方法、理论或主结果 | 是 | Causal anonymous walks (CAW): causality extraction and set-based anonymization.；text-only，未直接核验图像像素。 |
| Figure 3 | PDF p.3 | 方法、理论或主结果 | 是 | Ambiguity due to removing node identi- ties in TGAT (Xu et al., 2020) (t1 < t2 < t3).；text-only，未直接核验图像像素。 |
| Algorithm 1 | PDF p.4 | 方法、理论或主结果 | 是 | Temporal Walk Extraction (E, α, M, m, w0, t0)；text-only，未直接核验图像像素。 |
| Figure 4 | PDF p.4 | 辅助背景、消融、复杂度或附录证据 | 否 | The correlation be- tween walks needs to be captured to learn this law.；text-only，未直接核验图像像素。 |
| Table 1 | PDF p.6 | 辅助背景、消融、复杂度或附录证据 | 否 | Summary of dataset statistics. Average link stream intensity is calculated by 2/E//(/V /T), where T is the total time range of all edges in unit of seconds, /V / and /E/ are number of nodes and temporal links.；text-only，未直接核验图像像素。 |
| Table 2 | PDF p.8 | 方法、理论或主结果 | 是 | Performance in AUC (mean in percentage ± 95% conﬁdence level.) † highlights the best baselines. ∗, bold font, bold font∗respectively highlights the case where our models’ performance exceeds the best baseline on average, by 70% conﬁdence, by 95% conﬁdence.；text-only，未直接核验图像像素。 |
| Figure 5 | PDF p.9 | 辅助背景、消融、复杂度或附录证据 | 否 | Hyperparameter sensitivity in CAW sampling. AUC on all inductive test links are reported.；text-only，未直接核验图像像素。 |
| Figure 6 | PDF p.9 | 辅助背景、消融、复杂度或附录证据 | 否 | Complexity evaluation: The accumulated runtime of (a) temporal random walk extraction (Alg.1) and (b) the entire CAW-N training, timed over one epoch on Wikipedia (using different /E/ for training).；text-only，未直接核验图像像素。 |
| Algorithm 2 | PDF p.14 | 方法、理论或主结果 | 是 | Online probability computation (G, α)；text-only，未直接核验图像像素。 |
| Algorithm 3 | PDF p.14 | 方法、理论或主结果 | 是 | Iterative Sampling (E, α, wp, tp)；text-only，未直接核验图像像素。 |
| Figure 7 | PDF p.16 | 辅助背景、消融、复杂度或附录证据 | 否 | Effect of sampling of different tree structures on inductive performance. We conduct more experiment to investigate this topic with Wikipedia and UCI datasets. The setup is as follows: ﬁrst, we ﬁx CAW sampling number M = 64 = 26 and length m = 2, so that we always have k1k2 = M = 26; next, we assign different values to k1, so that the shape of the tree changes accordingly; controlling other hyperparameters to be the optimal combination found by grid search, we plot the corresponding inductive AUC scores of CAW-N-mean on all testing edges in Fig. 7. It is observed that while tree-structured sampling may affect the performance to some extent, its negative impact is less prominent when the ﬁrst-step sampling number k1 is relatively large, and our model still achieves state-of-the-art performance compared to our baselines. That makes the tree-structured sampling a reasonable strategy that can further reduce time complexity.；text-only，未直接核验图像像素。 |
| Table 4 | PDF p.17 | 辅助背景、消融、复杂度或附录证据 | 否 | Hyperparameter search range of CAW sampling.；text-only，未直接核验图像像素。 |
| Table 5 | PDF p.18 | 辅助背景、消融、复杂度或附录证据 | 否 | Snapshot split for evaluating snapshot-based baselines.；text-only，未直接核验图像像素。 |
| Table 6 | PDF p.19 | 辅助背景、消融、复杂度或附录证据 | 否 | Performance in Average Precision (AP) (mean in percentage ± 95% conﬁdence level.) † highlights the best baselines. ∗, bold font, bold font∗respectively highlights the case where our models’ performance exceeds the best baseline on average, by 70% conﬁdence, by 95% conﬁdence.；text-only，未直接核验图像像素。 |
| Figure 8 | PDF p.20 | 辅助背景、消融、复杂度或附录证据 | 否 | Visualizing most discriminatory CAWs, and their occurrence ratios with positive / negative samples.；text-only，未直接核验图像像素。 |
| Figure 8 | PDF p.20 | 辅助背景、消融、复杂度或附录证据 | 否 | lists the 3 highest-scored and the 3 lowest-scored shapes of CAW, which are extracted from the Wikipedia dataset with M = 32 and m = 3. A law of general motif closure can be observed from the highest-scored CAWs: two nodes that commonly appear in some types of motif are more inclined to have a link in between. For example, the highest-scored shape of CAW, (0, ∞) →(1, 2) →(2, 3) →(1, 2), implies that the nodes except the ﬁrst in this CAW appear in the sampled common 3-hop neighborhood around the two nodes between which the link is to be；text-only，未直接核验图像像素。 |
| Figure 9 | PDF p.21 | 辅助背景、消融、复杂度或附录证据 | 否 | Visualizing all AWs, and their occurrence ratios with positive / negative samples.；text-only，未直接核验图像像素。 |
| Table 7 | PDF p.21 | 方法、理论或主结果 | 是 | TGN performance in AUC (mean in percentage ± 95% conﬁdence level). Bond font highlights the case when TGN out performs CAW-N. TGN generally outperforms other baselines.；text-only，未直接核验图像像素。 |
| Table 8 | PDF p.22 | 方法、理论或主结果 | 是 | TGN performance in AP (mean in percentage ± 95% conﬁdence level). Bond font highlights the case when TGN out performs CAW-N. TGN generally outperforms other baselines.；text-only，未直接核验图像像素。 |

### 4.3 关键证据与主要结果
- Table 1（PDF p.6）报告数据集统计，决定游走采样和归纳式拆分的规模边界。
- Table 2（PDF p.8）报告 inductive link prediction 的 AUC；正文称 CAW 在多个数据集上与基线比较。
- Figure 5、Figure 6（PDF p.9）分别讨论超参数敏感性和复杂度；正文明确将采样数量与运行成本联系起来。
- Table 6（PDF p.19）以及 Table 7/8（PDF p.21-22）报告 AP/AUC 与 TGN 对比；它们支持 CAW 的链路预测价值，但不支持宏观规模预测结论。

### 4.4 逐图表解释
#### Figure 1（PDF p.2；关键）
- **原始标题**：Triadic closure and feed-forward loops: Causal anonymous walks (CAW) capture the laws.
- **可恢复证据**：`assets/text/visuals/figure-1-p002.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 2（PDF p.2；关键）
- **原始标题**：Causal anonymous walks (CAW): causality extraction and set-based anonymization.
- **可恢复证据**：`assets/text/visuals/figure-2-p002.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 3（PDF p.3；关键）
- **原始标题**：Ambiguity due to removing node identi- ties in TGAT (Xu et al., 2020) (t1 < t2 < t3).
- **可恢复证据**：`assets/text/visuals/figure-3-p003.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Algorithm 1（PDF p.4；关键）
- **原始标题**：Temporal Walk Extraction (E, α, M, m, w0, t0)
- **可恢复证据**：`assets/text/visuals/algorithm-1-p004.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 4（PDF p.4；非关键）
- **原始标题**：The correlation be- tween walks needs to be captured to learn this law.
- **可恢复证据**：`assets/text/visuals/figure-4-p004.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 1（PDF p.6；非关键）
- **原始标题**：Summary of dataset statistics. Average link stream intensity is calculated by 2|E|/(|V |T), where T is the total time range of all edges in unit of seconds, |V | and |E| are number of nodes and temporal links.
- **可恢复证据**：`assets/text/visuals/table-1-p006.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 2（PDF p.8；关键）
- **原始标题**：Performance in AUC (mean in percentage ± 95% conﬁdence level.) † highlights the best baselines. ∗, bold font, bold font∗respectively highlights the case where our models’ performance exceeds the best baseline on average, by 70% conﬁdence, by 95% conﬁdence.
- **可恢复证据**：`assets/text/visuals/table-2-p008.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 5（PDF p.9；非关键）
- **原始标题**：Hyperparameter sensitivity in CAW sampling. AUC on all inductive test links are reported.
- **可恢复证据**：`assets/text/visuals/figure-5-p009.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 6（PDF p.9；非关键）
- **原始标题**：Complexity evaluation: The accumulated runtime of (a) temporal random walk extraction (Alg.1) and (b) the entire CAW-N training, timed over one epoch on Wikipedia (using different |E| for training).
- **可恢复证据**：`assets/text/visuals/figure-6-p009.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Algorithm 2（PDF p.14；关键）
- **原始标题**：Online probability computation (G, α)
- **可恢复证据**：`assets/text/visuals/algorithm-2-p014.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Algorithm 3（PDF p.14；关键）
- **原始标题**：Iterative Sampling (E, α, wp, tp)
- **可恢复证据**：`assets/text/visuals/algorithm-3-p014.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 7（PDF p.16；非关键）
- **原始标题**：Effect of sampling of different tree structures on inductive performance. We conduct more experiment to investigate this topic with Wikipedia and UCI datasets. The setup is as follows: ﬁrst, we ﬁx CAW sampling number M = 64 = 26 and length m = 2, so that we always have k1k2 = M = 26; next, we assign different values to k1, so that the shape of the tree changes accordingly; controlling other hyperparameters to be the optimal combination found by grid search, we plot the corresponding inductive AUC scores of CAW-N-mean on all testing edges in Fig. 7. It is observed that while tree-structured sampling may affect the performance to some extent, its negative impact is less prominent when the ﬁrst-step sampling number k1 is relatively large, and our model still achieves state-of-the-art performance compared to our baselines. That makes the tree-structured sampling a reasonable strategy that can further reduce time complexity.
- **可恢复证据**：`assets/text/visuals/figure-7-p016.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 4（PDF p.17；非关键）
- **原始标题**：Hyperparameter search range of CAW sampling.
- **可恢复证据**：`assets/text/visuals/table-4-p017.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 5（PDF p.18；非关键）
- **原始标题**：Snapshot split for evaluating snapshot-based baselines.
- **可恢复证据**：`assets/text/visuals/table-5-p018.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 6（PDF p.19；非关键）
- **原始标题**：Performance in Average Precision (AP) (mean in percentage ± 95% conﬁdence level.) † highlights the best baselines. ∗, bold font, bold font∗respectively highlights the case where our models’ performance exceeds the best baseline on average, by 70% conﬁdence, by 95% conﬁdence.
- **可恢复证据**：`assets/text/visuals/table-6-p019.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 8（PDF p.20；非关键）
- **原始标题**：Visualizing most discriminatory CAWs, and their occurrence ratios with positive / negative samples.
- **可恢复证据**：`assets/text/visuals/figure-8-p020.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 8（PDF p.20；非关键）
- **原始标题**：lists the 3 highest-scored and the 3 lowest-scored shapes of CAW, which are extracted from the Wikipedia dataset with M = 32 and m = 3. A law of general motif closure can be observed from the highest-scored CAWs: two nodes that commonly appear in some types of motif are more inclined to have a link in between. For example, the highest-scored shape of CAW, (0, ∞) →(1, 2) →(2, 3) →(1, 2), implies that the nodes except the ﬁrst in this CAW appear in the sampled common 3-hop neighborhood around the two nodes between which the link is to be
- **可恢复证据**：`assets/text/visuals/figure-8-p020.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 9（PDF p.21；非关键）
- **原始标题**：Visualizing all AWs, and their occurrence ratios with positive / negative samples.
- **可恢复证据**：`assets/text/visuals/figure-9-p021.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 7（PDF p.21；关键）
- **原始标题**：TGN performance in AUC (mean in percentage ± 95% conﬁdence level). Bond font highlights the case when TGN out performs CAW-N. TGN generally outperforms other baselines.
- **可恢复证据**：`assets/text/visuals/table-7-p021.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 8（PDF p.22；关键）
- **原始标题**：TGN performance in AP (mean in percentage ± 95% conﬁdence level). Bond font highlights the case when TGN out performs CAW-N. TGN generally outperforms other baselines.
- **可恢复证据**：`assets/text/visuals/table-8-p022.md`、图注和正文引用。
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
| C1: CAW 保留时间因果顺序并以匿名化方式表示动态图局部模式。 | Figure 1/2, PDF p.2; Algorithm 1, PDF p.4 | 强支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C2: CAW 支持归纳式 temporal link prediction。 | Table 2, PDF p.8; Table 6-8, PDF p.19-22 | 强支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C3: CAW 的采样数量和树结构会影响性能与运行成本。 | Figure 5-7, PDF p.9/16; Algorithm 2/3, PDF p.14 | 部分支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C4: CAW 直接提供传播路径因果证明。 |  | 未支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |

### 4.7 可靠性、复现性与争议点
- **最可靠结论**：方法定义、输入输出、算法步骤和正文明确报告的表格数值。
- **最弱结论**：仅由图注或 OCR 文本卡推断的像素级趋势，以及把作者称谓转写为普适 SOTA。
- **公平性风险**：数据版本、负采样、时间切分、候选集合、超参数和硬件差异都可能解释性能差异。
- **复现要求**：固定代码 revision、数据版本、随机种子、观察窗口、预测窗口、候选生成、失败日志和完整 JSON 输出。
- **实现核对**：对可运行模型，还要记录 patch/历史长度、邻居采样、负采样类型、显存峰值、单批推理时间和失败重试次数；这些工程量会影响系统是否适合在线事件监测。
- **最小复现实验**：先选一个数据集和一个严格时间切分，复现论文主指标；随后只改变一个组件或协议变量，并保持数据版本、候选集合、训练轮数和随机种子不变。若结果差异超过随机波动，再检查日志中的时间泄漏、样本重复、负采样和用户映射。

## 5. 论文的贡献与影响（Contribution & Impact）
### 5.1 主要贡献
1. 表示层：将因果时间结构编码为匿名游走集合，增强对未见节点/结构的归纳能力。
2. 理论层：把可表达性和具体采样算法联系起来，避免只给经验性 GNN 结构。
3. 工程层：Algorithm 1-3 给出可落地的在线采样和复杂度控制路径。

### 5.2 对 CogGuard 传播分析与预测的启发
- 传播分析侧应保留 provenance 证据、显式/重建/推断边区分、真实用户映射和可回溯详情；预测侧只读取观测前缀，不能复用未来真实节点。
- 下一跳输出需要明确是“已知用户再激活”还是“开放世界新用户激活”；候选覆盖不足时应 abstain，而不是输出匿名 bucket。
- 宏观趋势输出应同时返回观测规模、预测规模、趋势点、误差区间状态和校准状态；没有校准时不能把集中度分数称为置信度。
- 评测应统一使用时间切分、合法负采样、候选覆盖、Hits/MAP/MRR/NDCG、MSLE/MAE/RMSE/MAPE 以及失败原因。

### 5.3 值得探索的未来方向
1. **将 CAW 作为下一跳候选边的结构编码器，尤其适合新用户或新边的归纳式场景。**
2. **把 `observed_until` 作为硬边界，候选边只由训练历史、观测用户、合法社交邻居产生。**
3. **报告 CAW 采样覆盖率、候选召回和运行成本，不能仅报告 AUC。**

## 6. 结论（Conclusion）
CAW 是 CogGuard 开放世界下一跳预测的重要方法参考，尤其补足“未参与事件的新用户”归纳能力；但论文是链路预测，不等于传播因果证据追溯。

> **最终判断**：值得复现，优先用于开放世界 micro 预测研究；需要先把 cascade 关系映射为可靠时间边流，并单独验证匿名化对真实用户映射的影响。
>
> **复现清单**：固定论文版本和代码 revision；准备同版本数据；实现论文输入协议；复现主表和关键消融；记录 3 个以上随机种子、时间切分、候选生成、显存/运行时间和失败日志；最后再迁移到 CogGuard 真实事件。
