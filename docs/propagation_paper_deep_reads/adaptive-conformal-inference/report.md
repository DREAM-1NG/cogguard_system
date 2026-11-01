# Adaptive Conformal Inference Under Distribution Shift：深度精读
> **作者**：Gibbs, Candès
> **会议/期刊与年份**：NeurIPS 2021
> **论文链接**：本地 PDF 为主；正式引用前请以项目文献索引中的官方链接为准
> **实际使用来源**：`H:\Zotero\attenger\Projects\CISCN\Propagation\Gibbs和Candès - 2021 - Adaptive conformal inference under distribution shift.pdf`；本地 PDF 文本层、图表文本卡和正文引用
> **页码约定**：全文使用 1-based PDF 页码
> **论文类型**：理论/不确定性校准
> **学科 Lens**：computer-science-ai；动态图学习、信息扩散与可复现评测
> **读者画像**：cross-disciplinary；目标是 reproduce；深度为 deep；语言为 zh-CN
> **视觉能力模式**：text-only
> **解读置信度**：中；方法和结构化数值较可靠，像素级图表内容未核验

> **视觉能力说明**：本报告使用 text-only 工作流生成，未直接核验图像像素内容。图表解释仅依据标题、PDF 文本层、正文引用和结构化文本卡，因此不对坐标轴、颜色、曲线形状、面板布局、裁剪完整性或视觉显著性作未经支持的判断。
> **文本证据边界**：本轮为 text-only；视觉内容未直接核验。
## 1. 核心思想一句话总结（Elevator Pitch）
> 自适应共形校准在线更新阈值，以维持漂移分布下的局部覆盖。

## 2. 论文背景与动机（Background & Motivation）
### 2.1 具体问题
- PDF p.1-4 将问题定义为分布随时间变化时，固定 conformal 阈值无法保证局部覆盖。
- Figure 1（PDF p.5）图注和正文比较 adaptive、fixed 和 Bernoulli coverage；正文称自适应方法在挑选的股票案例中表现更稳定。
- Figure 2（PDF p.9）是未归一化 conformity score 的失败/偏离案例，正文明确指出归一化重要。
- Theorem 4.1/4.2 与 Algorithm 1（PDF p.18-19）构成理论和实现的核心证据。

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
> 旧方法依赖静态快照、有限候选或固定误差假设，在动态传播和分布漂移下容易失效；本文通过 根据上一时刻是否覆盖更新阈值参数，再用归一化 conformity score 构造预测区间；CQR 扩展到分位数回归和选举预测。，使 固定阈值 conformal 在非平稳序列和结构突变期间覆盖率会偏离目标，系统需要可在线适应的区间。，但其证据范围仍由数据集、时间切分、候选生成和实现版本限定。

- **作者主张**：建立分布漂移下的局部覆盖保证，并用股票波动和选举预测验证自适应更新。
- **论文直接证据**：正文和对应 Figure/Table/Algorithm 的页码锚点见第 3、4 节。
- **本文推断**：迁移到 CogGuard 时，必须把论文任务定义和系统的真实事件任务分开，不能把 transductive 结果直接写成开放世界新用户预测。
- **外部背景**：动态图链路预测、信息级联预测和 conformal prediction 的指标并不天然等价，跨论文比较必须统一观察窗口、预测窗口和候选协议。

## 3. 核心方法/理论/研究设计详解（Core Method, Theory, or Study Design）
### 3.1 总体框架
`观测事件/时间边流 → 时间与结构编码 → 共享或任务特有表示 → 预测/校准输出 → 严格时间评估`

**数据流解释**：输入只能使用观测截止时间之前的事件、用户、边、时间戳和合法训练统计；中间模块负责保留时间顺序、局部结构和跨事件关系；输出根据论文类型对应最终规模、未来趋势、下一跳用户、链路分数、图表示或预测区间。

### 3.2 核心流程
1. **起点**：读取带时间戳的 cascade 或 temporal interaction stream。
2. **结构编码**：时间序列观测、点预测/分位数预测、过去残差 conformity score 和在线阈值。
3. **任务输出**：输出预测区间并评价平均覆盖、局部覆盖轨迹和区间稳定性。
4. **评估**：Algorithm 1（PDF p.18-19）给出核心更新；Theorem 4.1/4.2 提供理论；Figure 1-3/9 报告覆盖行为。

### 3.3 关键步骤、组件或概念
- 在每个时刻 t，模型先产生预测区间，再根据真实值是否落入区间更新阈值。更新步长/遗忘机制控制对新分布的适应速度；归一化 score 使不同时间的误差尺度更可比。CQR 情况下先得到上下分位数，再用 conformal 修正。

### 3.4 关键形式化内容
若 `I_t` 表示是否覆盖，阈值可按覆盖误差递推：`α_{t+1}=α_t+γ(1-α_target-I_t)`；区间形如 `[q_lo(x_t)-q_t, q_hi(x_t)+q_t]`。这里是按论文 Algorithm 1 和更新式的功能语义重写，实际符号和索引以 PDF p.4、18-19 为准。

### 3.5 核心创新
1. 理论层：把分布漂移下的局部覆盖作为在线预测区间目标。
2. 算法层：用递推阈值和归一化 conformity score 适应非平稳误差。
3. 应用层：将同一校准思想用于金融波动和实时选举预测。

## 4. 证据与结果分析（Evidence & Results）
### 4.1 研究设计与证据协议
- **研究问题/假设**：论文主要检验方法是否改善其定义的任务；不能把论文在封闭候选集上的结果直接外推成开放世界新用户发现。
- **数据与样本**：以论文明确列出的数据集、时间范围、节点/边定义和观察窗口为准；报告中的外部系统数据不能替代论文证据。
- **比较与评估**：优先记录论文原始指标、训练设置、负采样、时间切分、重复次数和消融；若原文未报告方差或置信区间，本文不补造。
- **不确定性**：区分作者主张、论文直接结果、本文推断和外部背景；所有核心数字都带 PDF 页码或图表锚点。

### 4.2 完整图表覆盖清单
| 编号 | PDF 页码 | 作用 | 是否关键 | 文本证据与限制 |
|---|---:|---|:---:|---|
| Figure 1 | PDF p.5 | 方法、理论或主结果 | 是 | Local coverage frequencies for adaptive conformal (blue), a non-adaptive method that holds αt = α ﬁxed (red), and an i.i.d. Bernoulli(0.1) sequence (grey) for the prediction of stock market volatility. The coloured dotted lines mark the average coverage obtained across all time points, while the black line indicates the target level of 1 −α = 0.9.；text-only，未直接核验图像像素。 |
| Figure 2 | PDF p.9 | 方法、理论或主结果 | 是 | Local coverage frequencies for adaptive conformal (blue), a non-adaptive method that holds αt = α ﬁxed (red), and an i.i.d. Bernoulli(0.1) sequence (grey) for the prediction of stock market volatility with conformity score ˜St. The coloured dotted lines mark the average coverage obtained across all time points, while the black line indicates the target level of 1 −α = 0.9.；text-only，未直接核验图像像素。 |
| Figure 3 | PDF p.10 | 方法、理论或主结果 | 是 | Local coverage frequencies of adaptive conformal (blue), a non-adaptive method that holds αt = α ﬁxed (red), and an i.i.d. Bernoulli(0.1) sequence (grey) for county-level election predictions. Coloured dotted lines show the average coverage across all time points, while the black line indicates the target coverage level of 1 −α = 0.9.；text-only，未直接核验图像像素。 |
| Figure 4 | PDF p.14 | 辅助背景、消融、复杂度或附录证据 | 否 | shows daily open prices for the four stocks considered in Section 2.2.；text-only，未直接核验图像像素。 |
| Figure 4 | PDF p.14 | 辅助背景、消融、复杂度或附录证据 | 否 | Daily open prices for the four stocks considered in Section 2.2.；text-only，未直接核验图像像素。 |
| Figure 5 | PDF p.15 | 辅助背景、消融、复杂度或附录证据 | 否 | Realized trajectories of αt for predicting stock market volatility as outlined in Section 2.2 using update (2).；text-only，未直接核验图像像素。 |
| Figure 6 | PDF p.15 | 辅助背景、消融、复杂度或附录证据 | 否 | Realized trajectories of αt for predicting stock market volatility as outlined in Section 2.2 using update (3) with ws ∝0.95t−s.；text-only，未直接核验图像像素。 |
| Figure 7 | PDF p.16 | 辅助背景、消融、复杂度或附录证据 | 否 | Realized trajectory of αt for election night forecasting as outlined in Section 6 using update (2).；text-only，未直接核验图像像素。 |
| Figure 8 | PDF p.16 | 辅助背景、消融、复杂度或附录证据 | 否 | Realized trajectory of αt for election night forecasting as outlined in Section 6 using update (3) with ws ∝0.95t−s.；text-only，未直接核验图像像素。 |
| Figure 9 | PDF p.16 | 辅助背景、消融、复杂度或附录证据 | 否 | shows the local coverage level of adaptive and non-adaptive conformal inference for the prediction of market volatility (see Section 2.2) for 8 additional stocks/indices.；text-only，未直接核验图像像素。 |
| Figure 9 | PDF p.17 | 方法、理论或主结果 | 是 | Local coverage frequencies for adaptive conformal (blue), a non-adaptive method that holds αt = α ﬁxed (red), and an i.i.d. Bernoulli(0.1) sequence (grey) for the prediction of market volatility. The coloured dotted lines mark the average coverage obtained across all time points, while the black line indicates the target level of 1 −α = 0.9.；text-only，未直接核验图像像素。 |
| Algorithm 1 | PDF p.18 | 方法、理论或主结果 | 是 | below outlines the core conformal inference method used to predict election results. An R implementation of this algorithm as well as the core method outlined in Section 2.2 can be found at https://github.com/isgibbs/AdaptiveConformal.；text-only，未直接核验图像像素。 |
| Algorithm 1 | PDF p.19 | 方法、理论或主结果 | 是 | CQR method for election night prediction Data: Observed sequence of county-level votes counts and covariates {(Xt, Yt)}1≤t≤T and vote counts for the democratic candidate in the previous election {Y prev t }1≤t≤T . for t = 1, 2, . . . , T do；text-only，未直接核验图像像素。 |

### 4.3 关键证据与主要结果
- Theorem 4.1/4.2（PDF p.4 附近）给出自适应覆盖相关理论保证，支持方法不是经验性滑动窗口。
- Figure 1（PDF p.5）正文称固定方法在部分股票上失效，而 adaptive 方法保持更接近目标的局部覆盖。
- Figure 3（PDF p.10）正文称非自适应方法在选举时区切换期间出现大幅覆盖偏离，自适应方法维持近似 90% 覆盖。
- Algorithm 1（PDF p.18-19）给出选举预测的 CQR 实现流程；Figure 9（PDF p.16-17）提供额外股票/指数的附录证据。

### 4.4 逐图表解释
#### Figure 1（PDF p.5；关键）
- **原始标题**：Local coverage frequencies for adaptive conformal (blue), a non-adaptive method that holds αt = α ﬁxed (red), and an i.i.d. Bernoulli(0.1) sequence (grey) for the prediction of stock market volatility. The coloured dotted lines mark the average coverage obtained across all time points, while the black line indicates the target level of 1 −α = 0.9.
- **可恢复证据**：`assets/text/visuals/figure-1-p005.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 2（PDF p.9；关键）
- **原始标题**：Local coverage frequencies for adaptive conformal (blue), a non-adaptive method that holds αt = α ﬁxed (red), and an i.i.d. Bernoulli(0.1) sequence (grey) for the prediction of stock market volatility with conformity score ˜St. The coloured dotted lines mark the average coverage obtained across all time points, while the black line indicates the target level of 1 −α = 0.9.
- **可恢复证据**：`assets/text/visuals/figure-2-p009.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 3（PDF p.10；关键）
- **原始标题**：Local coverage frequencies of adaptive conformal (blue), a non-adaptive method that holds αt = α ﬁxed (red), and an i.i.d. Bernoulli(0.1) sequence (grey) for county-level election predictions. Coloured dotted lines show the average coverage across all time points, while the black line indicates the target coverage level of 1 −α = 0.9.
- **可恢复证据**：`assets/text/visuals/figure-3-p010.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 4（PDF p.14；非关键）
- **原始标题**：shows daily open prices for the four stocks considered in Section 2.2.
- **可恢复证据**：`assets/text/visuals/figure-4-p014.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 4（PDF p.14；非关键）
- **原始标题**：Daily open prices for the four stocks considered in Section 2.2.
- **可恢复证据**：`assets/text/visuals/figure-4-p014.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 5（PDF p.15；非关键）
- **原始标题**：Realized trajectories of αt for predicting stock market volatility as outlined in Section 2.2 using update (2).
- **可恢复证据**：`assets/text/visuals/figure-5-p015.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 6（PDF p.15；非关键）
- **原始标题**：Realized trajectories of αt for predicting stock market volatility as outlined in Section 2.2 using update (3) with ws ∝0.95t−s.
- **可恢复证据**：`assets/text/visuals/figure-6-p015.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 7（PDF p.16；非关键）
- **原始标题**：Realized trajectory of αt for election night forecasting as outlined in Section 6 using update (2).
- **可恢复证据**：`assets/text/visuals/figure-7-p016.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 8（PDF p.16；非关键）
- **原始标题**：Realized trajectory of αt for election night forecasting as outlined in Section 6 using update (3) with ws ∝0.95t−s.
- **可恢复证据**：`assets/text/visuals/figure-8-p016.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 9（PDF p.16；非关键）
- **原始标题**：shows the local coverage level of adaptive and non-adaptive conformal inference for the prediction of market volatility (see Section 2.2) for 8 additional stocks/indices.
- **可恢复证据**：`assets/text/visuals/figure-9-p016.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 9（PDF p.17；关键）
- **原始标题**：Local coverage frequencies for adaptive conformal (blue), a non-adaptive method that holds αt = α ﬁxed (red), and an i.i.d. Bernoulli(0.1) sequence (grey) for the prediction of market volatility. The coloured dotted lines mark the average coverage obtained across all time points, while the black line indicates the target level of 1 −α = 0.9.
- **可恢复证据**：`assets/text/visuals/figure-9-p017.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Algorithm 1（PDF p.18；关键）
- **原始标题**：below outlines the core conformal inference method used to predict election results. An R implementation of this algorithm as well as the core method outlined in Section 2.2 can be found at https://github.com/isgibbs/AdaptiveConformal.
- **可恢复证据**：`assets/text/visuals/algorithm-1-p018.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Algorithm 1（PDF p.19；关键）
- **原始标题**：CQR method for election night prediction Data: Observed sequence of county-level votes counts and covariates {(Xt, Yt)}1≤t≤T and vote counts for the democratic candidate in the previous election {Y prev t }1≤t≤T . for t = 1, 2, . . . , T do
- **可恢复证据**：`assets/text/visuals/algorithm-1-p019.md`、图注和正文引用。
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
| C1: 固定 conformal 方法在分布漂移下可能失去局部覆盖。 | PDF p.1-4; Figure 1/3, PDF p.5/10 | 强支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C2: 自适应阈值更新改善局部覆盖稳定性。 | Theorem 4.1/4.2, PDF p.4; Algorithm 1, PDF p.18-19; Figure 1/3, PDF p.5/10 | 强支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C3: 归一化 conformity score 对覆盖质量重要。 | Figure 2, PDF p.9; PDF p.9 | 强支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C4: Adaptive conformal 可直接保证 CogGuard 传播预测区间在任意事件上有效。 |  | 未支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |

### 4.7 可靠性、复现性与争议点
- **最可靠结论**：方法定义、输入输出、算法步骤和正文明确报告的表格数值。
- **最弱结论**：仅由图注或 OCR 文本卡推断的像素级趋势，以及把作者称谓转写为普适 SOTA。
- **公平性风险**：数据版本、负采样、时间切分、候选集合、超参数和硬件差异都可能解释性能差异。
- **复现要求**：固定代码 revision、数据版本、随机种子、观察窗口、预测窗口、候选生成、失败日志和完整 JSON 输出。
- **实现核对**：对可运行模型，还要记录 patch/历史长度、邻居采样、负采样类型、显存峰值、单批推理时间和失败重试次数；这些工程量会影响系统是否适合在线事件监测。
- **最小复现实验**：先选一个数据集和一个严格时间切分，复现论文主指标；随后只改变一个组件或协议变量，并保持数据版本、候选集合、训练轮数和随机种子不变。若结果差异超过随机波动，再检查日志中的时间泄漏、样本重复、负采样和用户映射。

## 5. 论文的贡献与影响（Contribution & Impact）
### 5.1 主要贡献
1. 理论层：把分布漂移下的局部覆盖作为在线预测区间目标。
2. 算法层：用递推阈值和归一化 conformity score 适应非平稳误差。
3. 应用层：将同一校准思想用于金融波动和实时选举预测。

### 5.2 对 CogGuard 传播分析与预测的启发
- 传播分析侧应保留 provenance 证据、显式/重建/推断边区分、真实用户映射和可回溯详情；预测侧只读取观测前缀，不能复用未来真实节点。
- 下一跳输出需要明确是“已知用户再激活”还是“开放世界新用户激活”；候选覆盖不足时应 abstain，而不是输出匿名 bucket。
- 宏观趋势输出应同时返回观测规模、预测规模、趋势点、误差区间状态和校准状态；没有校准时不能把集中度分数称为置信度。
- 评测应统一使用时间切分、合法负采样、候选覆盖、Hits/MAP/MRR/NDCG、MSLE/MAE/RMSE/MAPE 以及失败原因。

### 5.3 值得探索的未来方向
1. **为 CogGuard 的规模趋势输出增加独立 calibration split，报告 empirical coverage、平均区间宽度和局部覆盖轨迹。**
2. **按事件时间顺序更新阈值，不能使用预测窗口之后的信息校准当前输出。**
3. **将 `confidence_like_score` 改名为分数集中度；只有通过覆盖率验证后才显示 prediction interval。**

## 6. 结论（Conclusion）
该论文不改进动态图表示或下一跳排序，却直接解决 CogGuard 当前“区间/概率尚未校准”的系统风险；它应作为预测服务的校准层，而不是模型 backbone。

> **最终判断**：值得复现其更新和 CQR 机制，尤其适合在线趋势预测；但覆盖保证依赖时间顺序、score 设计和更新参数，不能直接照搬股票/选举的经验数值。
>
> **复现清单**：固定论文版本和代码 revision；准备同版本数据；实现论文输入协议；复现主表和关键消融；记录 3 个以上随机种子、时间切分、候选生成、显存/运行时间和失败日志；最后再迁移到 CogGuard 真实事件。
