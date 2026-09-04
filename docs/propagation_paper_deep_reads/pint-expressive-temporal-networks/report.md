# Provably Expressive Temporal Graph Networks：深度精读
> **作者**：Souza 等
> **会议/期刊与年份**：2022
> **论文链接**：本地 PDF 为主；正式引用前请以项目文献索引中的官方链接为准
> **实际使用来源**：`H:\Zotero\attenger\Projects\CISCN\Propagation\Souza 等 - 2022 - Provably expressive temporal graph networks.pdf`；本地 PDF 文本层、图表文本卡和正文引用
> **页码约定**：全文使用 1-based PDF 页码
> **论文类型**：理论/方法
> **学科 Lens**：computer-science-ai；动态图学习、信息扩散与可复现评测
> **读者画像**：cross-disciplinary；目标是 reproduce；深度为 deep；语言为 zh-CN
> **视觉能力模式**：text-only
> **解读置信度**：中；方法和结构化数值较可靠，像素级图表内容未核验

> **视觉能力说明**：本报告使用 text-only 工作流生成，未直接核验图像像素内容。图表解释仅依据标题、PDF 文本层、正文引用和结构化文本卡，因此不对坐标轴、颜色、曲线形状、面板布局、裁剪完整性或视觉显著性作未经支持的判断。
> **文本证据边界**：本轮为 text-only；视觉内容未直接核验。
## 1. 核心思想一句话总结（Elevator Pitch）
> PINT 用相对位置和事件上下文增强 temporal GNN 表达性。

## 2. 论文背景与动机（Background & Motivation）
### 2.1 具体问题
- PDF p.1-4 以 temporal WL/表达性为主线，指出只做局部 message passing 可能无法区分时间图的直径、环和事件方向。
- Figure 2（PDF p.5）正文用于展示 TGNs 的限制；Figure 3（PDF p.6）给出 Proposition 7 的构造性反例。
- Figure 5（PDF p.7）和 Figure 6（PDF p.8）支持 PINT 的事件更新与区分能力说明。
- Propositions（PDF p.4-6）是理论主张的主要证据，Table 1/2（PDF p.9-10）是经验链路预测证据。

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
> 旧方法依赖静态快照、有限候选或固定误差假设，在动态传播和分布漂移下容易失效；本文通过 以节点 memory 和事件更新协议为基础，引入 positional features 与 pairwise interaction information，形成 PINT 更新和预测模块。，使 解决传统 message-passing temporal GNN 的表达性不足：不同的时间图可能被映射到相同表示。，但其证据范围仍由数据集、时间切分、候选生成和实现版本限定。

- **作者主张**：把 temporal graph 的可区分性与 temporal Weisfeiler-Lehman 类分析连接起来，并提出有理论保证的架构。
- **论文直接证据**：正文和对应 Figure/Table/Algorithm 的页码锚点见第 3、4 节。
- **本文推断**：迁移到 CogGuard 时，必须把论文任务定义和系统的真实事件任务分开，不能把 transductive 结果直接写成开放世界新用户预测。
- **外部背景**：动态图链路预测、信息级联预测和 conformal prediction 的指标并不天然等价，跨论文比较必须统一观察窗口、预测窗口和候选协议。

## 3. 核心方法/理论/研究设计详解（Core Method, Theory, or Study Design）
### 3.1 总体框架
`观测事件/时间边流 → 时间与结构编码 → 共享或任务特有表示 → 预测/校准输出 → 严格时间评估`

**数据流解释**：输入只能使用观测截止时间之前的事件、用户、边、时间戳和合法训练统计；中间模块负责保留时间顺序、局部结构和跨事件关系；输出根据论文类型对应最终规模、未来趋势、下一跳用户、链路分数、图表示或预测区间。

### 3.2 核心流程
1. **起点**：读取带时间戳的 cascade 或 temporal interaction stream。
2. **结构编码**：带时间的交互边、节点状态、相对位置/时间特征和事件顺序。
3. **任务输出**：主要输出未来链路预测 AP，并报告理论命题、运行时间和位置特征维度敏感性。
4. **评估**：Figure 2/3/6 说明表达性限制和反例；Figure 5 展示 PINT；Table 1/2 报告 AP；Figure 7/8 分析效率和位置维度。

### 3.3 关键步骤、组件或概念
- PINT 遵循 temporal message passing 协议：事件到来时更新相关节点 memory。与标准 TGN 不同，PINT 的更新显式使用相对位置/事件上下文，使消息不仅依赖节点状态，还依赖事件在时间图中的结构位置。得到的 node/edge embedding 用于未来链路预测。

### 3.4 关键形式化内容
论文通过 temporal WL 风格命题讨论模型能区分哪些时间图；经验任务可抽象为 `AP = Eval({score(u,v,t)}, E^+_test, E^-_test)`。理论保证说明表达能力边界，不能自动推出真实传播因果或更高业务准确率。

### 3.5 核心创新
1. 理论层：为 temporal GNN 的可表达性和失败案例提供可证明分析。
2. 架构层：用相对位置特征扩展 TGN 的事件消息。
3. 工程层：同时报告精度与预计算/运行时间，暴露理论增强的成本。

## 4. 证据与结果分析（Evidence & Results）
### 4.1 研究设计与证据协议
- **研究问题/假设**：论文主要检验方法是否改善其定义的任务；不能把论文在封闭候选集上的结果直接外推成开放世界新用户发现。
- **数据与样本**：以论文明确列出的数据集、时间范围、节点/边定义和观察窗口为准；报告中的外部系统数据不能替代论文证据。
- **比较与评估**：优先记录论文原始指标、训练设置、负采样、时间切分、重复次数和消融；若原文未报告方差或置信区间，本文不补造。
- **不确定性**：区分作者主张、论文直接结果、本文推断和外部背景；所有核心数字都带 PDF 页码或图表锚点。

### 4.2 完整图表覆盖清单
| 编号 | PDF 页码 | 作用 | 是否关键 | 文本证据与限制 |
|---|---:|---|:---:|---|
| Figure 1 | PDF p.2 | 辅助背景、消融、复杂度或附录证据 | 否 | Schematic diagram and summary of our contributions.；text-only，未直接核验图像像素。 |
| Figure 2 | PDF p.5 | 方法、理论或主结果 | 是 | Limitations of TGNs. [Left] Temporal graph with nodes u, v that TGN-Att/TGAT cannot distinguish. Colors are node features, edge features are identical, and t3 > t2 > t1. [Center] TCTs of u and v are non-isomorphic. However, the attention layers of TGAT/TGN-Att compute weighted averages over a same multiset of values, returning identical messages for u and v. [Right] MP-TGNs fail to distinguish the events (u, v, t3) and (v, z, t3) as TCTs of z and u are isomorphic. Meanwhile, CAW cannot separate (u, z, t3) and (u0, z, t3): the 3-depth TCTs of u and u0 are not isomorphic, but the temporal walks from u and u0 have length 1, keeping CAW from capturing structural differences.；text-only，未直接核验图像像素。 |
| Figure 3 | PDF p.6 | 方法、理论或主结果 | 是 | Examples of temporal graphs for which MP-TGNs cannot distinguish the diameter, girth, and number of cycles.；text-only，未直接核验图像像素。 |
| Figure 3 | PDF p.6 | 方法、理论或主结果 | 是 | provides a construction for Proposition 7. The temporal graphs G(t) and G0(t) differ in diameter (1 vs. 3), girth (3 vs. 6), and number of cycles (2 vs. 1). By inspecting the TCTs, one can observe that, for any node in G(t), there is a corresponding one in G0(t) whose TCTs are isomorphic, e.g., Tu1(t) ⇠= Tu0；text-only，未直接核验图像像素。 |
| Figure 5 | PDF p.7 | 方法、理论或主结果 | 是 | PINT. Following the MP-TGN protocol, PINT updates memory states as events unroll. Meanwhile, we use Eqs. (7-11) to update positional features. To extract the embedding for node v, we build its TCT, annotate nodes with memory + positional features, and run (injective) MP.；text-only，未直接核验图像像素。 |
| Figure 4 | PDF p.7 | 辅助背景、消融、复杂度或附录证据 | 否 | The effect of (u, v, t) on the monotone TCT of v. Also, note how the positional features of a node i, relative to v, can be incrementally updated.；text-only，未直接核验图像像素。 |
| Figure 6 | PDF p.8 | 辅助背景、消融、复杂度或附录证据 | 否 | PINT cannot distinguish the events (u, v, t3) and (v, z, t3).；text-only，未直接核验图像像素。 |
| Table 1 | PDF p.9 | 方法、理论或主结果 | 是 | Average Precision (AP) results for link prediction. We denote the best-performing model (highest mean AP) in blue. In 5 out of 6 datasets, PINT achieves the highest AP in the transductive setting. For the inductive case, PINT outperforms previous MP-TGNs and competes with CAW. We also evaluate PINT w/ and w/o relative positional features. Adopting positional features leads to signiﬁcant performance gains.；text-only，未直接核验图像像素。 |
| Figure 7 | PDF p.9 | 方法、理论或主结果 | 是 | Time comparison: PINT versus TGNs (in log- scale). The cost of pre-computing positional features is quickly diluted as the number of epochs increases.；text-only，未直接核验图像像素。 |
| Table 2 | PDF p.10 | 方法、理论或主结果 | 是 | Average precision results for TGN-Att + relative positional features.；text-only，未直接核验图像像素。 |
| Figure 8 | PDF p.10 | 方法、理论或主结果 | 是 | PINT: AP (mean and std) as a function of the dimensionality of the positional features.；text-only，未直接核验图像像素。 |

### 4.3 关键证据与主要结果
- Proposition 1/相关命题（PDF p.4-6）直接支撑 PINT 相对传统 temporal message passing 的表达性讨论。
- Table 1（PDF p.9）报告链路预测 AP，Table 2（PDF p.10）报告加入相对位置特征后的对比。
- Figure 7（PDF p.9）报告 PINT 与 TGNs 的时间比较，提示表达力增强伴随预计算成本。
- Figure 8（PDF p.10）研究位置特征维度对 AP 的影响；本轮只采用正文/图注可恢复关系。

### 4.4 逐图表解释
#### Figure 1（PDF p.2；非关键）
- **原始标题**：Schematic diagram and summary of our contributions.
- **可恢复证据**：`assets/text/visuals/figure-1-p002.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 2（PDF p.5；关键）
- **原始标题**：Limitations of TGNs. [Left] Temporal graph with nodes u, v that TGN-Att/TGAT cannot distinguish. Colors are node features, edge features are identical, and t3 > t2 > t1. [Center] TCTs of u and v are non-isomorphic. However, the attention layers of TGAT/TGN-Att compute weighted averages over a same multiset of values, returning identical messages for u and v. [Right] MP-TGNs fail to distinguish the events (u, v, t3) and (v, z, t3) as TCTs of z and u are isomorphic. Meanwhile, CAW cannot separate (u, z, t3) and (u0, z, t3): the 3-depth TCTs of u and u0 are not isomorphic, but the temporal walks from u and u0 have length 1, keeping CAW from capturing structural differences.
- **可恢复证据**：`assets/text/visuals/figure-2-p005.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 3（PDF p.6；关键）
- **原始标题**：Examples of temporal graphs for which MP-TGNs cannot distinguish the diameter, girth, and number of cycles.
- **可恢复证据**：`assets/text/visuals/figure-3-p006.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 3（PDF p.6；关键）
- **原始标题**：provides a construction for Proposition 7. The temporal graphs G(t) and G0(t) differ in diameter (1 vs. 3), girth (3 vs. 6), and number of cycles (2 vs. 1). By inspecting the TCTs, one can observe that, for any node in G(t), there is a corresponding one in G0(t) whose TCTs are isomorphic, e.g., Tu1(t) ⇠= Tu0
- **可恢复证据**：`assets/text/visuals/figure-3-p006.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 5（PDF p.7；关键）
- **原始标题**：PINT. Following the MP-TGN protocol, PINT updates memory states as events unroll. Meanwhile, we use Eqs. (7-11) to update positional features. To extract the embedding for node v, we build its TCT, annotate nodes with memory + positional features, and run (injective) MP.
- **可恢复证据**：`assets/text/visuals/figure-5-p007.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 4（PDF p.7；非关键）
- **原始标题**：The effect of (u, v, t) on the monotone TCT of v. Also, note how the positional features of a node i, relative to v, can be incrementally updated.
- **可恢复证据**：`assets/text/visuals/figure-4-p007.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 6（PDF p.8；非关键）
- **原始标题**：PINT cannot distinguish the events (u, v, t3) and (v, z, t3).
- **可恢复证据**：`assets/text/visuals/figure-6-p008.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 1（PDF p.9；关键）
- **原始标题**：Average Precision (AP) results for link prediction. We denote the best-performing model (highest mean AP) in blue. In 5 out of 6 datasets, PINT achieves the highest AP in the transductive setting. For the inductive case, PINT outperforms previous MP-TGNs and competes with CAW. We also evaluate PINT w/ and w/o relative positional features. Adopting positional features leads to signiﬁcant performance gains.
- **可恢复证据**：`assets/text/visuals/table-1-p009.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 7（PDF p.9；关键）
- **原始标题**：Time comparison: PINT versus TGNs (in log- scale). The cost of pre-computing positional features is quickly diluted as the number of epochs increases.
- **可恢复证据**：`assets/text/visuals/figure-7-p009.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 2（PDF p.10；关键）
- **原始标题**：Average precision results for TGN-Att + relative positional features.
- **可恢复证据**：`assets/text/visuals/table-2-p010.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 8（PDF p.10；关键）
- **原始标题**：PINT: AP (mean and std) as a function of the dimensionality of the positional features.
- **可恢复证据**：`assets/text/visuals/figure-8-p010.md`、图注和正文引用。
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
| C1: 传统 temporal message passing 存在可构造的表达性限制。 | Figure 2/3, PDF p.5-6; Propositions, PDF p.4-6 | 强支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C2: PINT 通过事件上下文/相对位置增强 temporal graph 表示。 | Figure 5/6, PDF p.7-8; PDF p.7-8 | 强支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C3: PINT 在链路预测上提供经验增益，但存在计算代价。 | Table 1/2, PDF p.9-10; Figure 7, PDF p.9 | 部分支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C4: PINT 已经解决 CogGuard 的传播因果溯源。 |  | 未支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |

### 4.7 可靠性、复现性与争议点
- **最可靠结论**：方法定义、输入输出、算法步骤和正文明确报告的表格数值。
- **最弱结论**：仅由图注或 OCR 文本卡推断的像素级趋势，以及把作者称谓转写为普适 SOTA。
- **公平性风险**：数据版本、负采样、时间切分、候选集合、超参数和硬件差异都可能解释性能差异。
- **复现要求**：固定代码 revision、数据版本、随机种子、观察窗口、预测窗口、候选生成、失败日志和完整 JSON 输出。
- **实现核对**：对可运行模型，还要记录 patch/历史长度、邻居采样、负采样类型、显存峰值、单批推理时间和失败重试次数；这些工程量会影响系统是否适合在线事件监测。
- **最小复现实验**：先选一个数据集和一个严格时间切分，复现论文主指标；随后只改变一个组件或协议变量，并保持数据版本、候选集合、训练轮数和随机种子不变。若结果差异超过随机波动，再检查日志中的时间泄漏、样本重复、负采样和用户映射。

## 5. 论文的贡献与影响（Contribution & Impact）
### 5.1 主要贡献
1. 理论层：为 temporal GNN 的可表达性和失败案例提供可证明分析。
2. 架构层：用相对位置特征扩展 TGN 的事件消息。
3. 工程层：同时报告精度与预计算/运行时间，暴露理论增强的成本。

### 5.2 对 CogGuard 传播分析与预测的启发
- 传播分析侧应保留 provenance 证据、显式/重建/推断边区分、真实用户映射和可回溯详情；预测侧只读取观测前缀，不能复用未来真实节点。
- 下一跳输出需要明确是“已知用户再激活”还是“开放世界新用户激活”；候选覆盖不足时应 abstain，而不是输出匿名 bucket。
- 宏观趋势输出应同时返回观测规模、预测规模、趋势点、误差区间状态和校准状态；没有校准时不能把集中度分数称为置信度。
- 评测应统一使用时间切分、合法负采样、候选覆盖、Hits/MAP/MRR/NDCG、MSLE/MAE/RMSE/MAPE 以及失败原因。

### 5.3 值得探索的未来方向
1. **用 PINT 检查 CogGuard 的传播边流是否包含足够的事件顺序和相对位置，避免仅用用户 ID embedding。**
2. **将表达性命题转化为诊断集：构造相同局部度但不同传播方向/时序的事件，测试下一跳是否可区分。**
3. **把计算成本纳入模型选择，避免在 8GB GPU 和在线响应约束下盲目增加位置维度。**

## 6. 结论（Conclusion）
PINT 适合作为 CogGuard 下一跳模型的理论增强参考，能解释为什么普通 TGN 可能混淆传播方向；但理论表达性不等于开放世界候选覆盖，也不替代数据协议。

> **最终判断**：值得做小规模理论/诊断复现，是否作为正式模型需由同协议 AP/MRR、归纳式候选覆盖和时延共同决定。
>
> **复现清单**：固定论文版本和代码 revision；准备同版本数据；实现论文输入协议；复现主表和关键消融；记录 3 个以上随机种子、时间切分、候选生成、显存/运行时间和失败日志；最后再迁移到 CogGuard 真实事件。
