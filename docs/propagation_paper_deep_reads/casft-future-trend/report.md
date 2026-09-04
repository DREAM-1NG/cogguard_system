# CasFT: Future Trend Modeling for Information Popularity Prediction with Dynamic Cues-Driven Diffusion：深度精读
> **作者**：Jing 等
> **会议/期刊与年份**：AAAI 2025
> **论文链接**：本地 PDF 为主；正式引用前请以项目文献索引中的官方链接为准
> **实际使用来源**：`H:\Zotero\attenger\Projects\CISCN\Propagation\Jing 等 - 2025 - CasFT future trend modeling for information popularity prediction with dynamic cues-driven diffusio.pdf`；本地 PDF 文本层、图表文本卡和正文引用
> **页码约定**：全文使用 1-based PDF 页码
> **论文类型**：方法/模型
> **学科 Lens**：computer-science-ai；动态图学习、信息扩散与可复现评测
> **读者画像**：cross-disciplinary；目标是 reproduce；深度为 deep；语言为 zh-CN
> **视觉能力模式**：text-only
> **解读置信度**：中；方法和结构化数值较可靠，像素级图表内容未核验

> **视觉能力说明**：本报告使用 text-only 工作流生成，未直接核验图像像素内容。图表解释仅依据标题、PDF 文本层、正文引用和结构化文本卡，因此不对坐标轴、颜色、曲线形状、面板布局、裁剪完整性或视觉显著性作未经支持的判断。
> **文本证据边界**：本轮为 text-only；视觉内容未直接核验。
## 1. 核心思想一句话总结（Elevator Pitch）
> CasFT 用 neural ODE 和 diffusion 生成未来流行度趋势，再预测最终规模。

## 2. 论文背景与动机（Background & Motivation）
### 2.1 具体问题
- PDF p.1-2 指出增长率在观测时间到预测时间之间显著波动，传统方法无法直接看到该阶段的真实变化。
- Figure 1（PDF p.1）图注定义了问题和观测/预测时间；正文进一步说明增长率积分得到增量。
- Figure 2（PDF p.4）与 PDF p.3 的正文共同支持三步流程：观测模式提取、未来趋势模拟、最终预测。
- PDF p.3-4 给出 neural ODE、ODE-GRU、diffusion 和融合预测模块；文本层能恢复关键变量与损失的功能关系。

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
> 旧方法依赖静态快照、有限候选或固定误差假设，在动态传播和分布漂移下容易失效；本文通过 图结构、时序事件和增长率进入动态编码器；ODE 连续推进增长率，diffusion 生成未来分段流行度序列，预测头融合观测与未来趋势。，使 解决只依据观测前缀回归最终规模、却忽略观测后到预测时段增长趋势和不确定性的问题。，但其证据范围仍由数据集、时间切分、候选生成和实现版本限定。

- **作者主张**：用连续动力学和生成式未来趋势模拟，改善信息级联 popularity prediction。
- **论文直接证据**：正文和对应 Figure/Table/Algorithm 的页码锚点见第 3、4 节。
- **本文推断**：迁移到 CogGuard 时，必须把论文任务定义和系统的真实事件任务分开，不能把 transductive 结果直接写成开放世界新用户预测。
- **外部背景**：动态图链路预测、信息级联预测和 conformal prediction 的指标并不天然等价，跨论文比较必须统一观察窗口、预测窗口和候选协议。

## 3. 核心方法/理论/研究设计详解（Core Method, Theory, or Study Design）
### 3.1 总体框架
`观测事件/时间边流 → 时间与结构编码 → 共享或任务特有表示 → 预测/校准输出 → 严格时间评估`

**数据流解释**：输入只能使用观测截止时间之前的事件、用户、边、时间戳和合法训练统计；中间模块负责保留时间顺序、局部结构和跨事件关系；输出根据论文类型对应最终规模、未来趋势、下一跳用户、链路分数、图表示或预测区间。

### 3.2 核心流程
1. **起点**：读取带时间戳的 cascade 或 temporal interaction stream。
2. **结构编码**：观测级联图、全局图结构表示、时间编码和级联事件序列共同形成动态状态。
3. **任务输出**：输出最终 popularity/规模；实验还比较不同 observation time、ODE solver、diffusion steps、hidden dimension 和 interval number。
4. **评估**：Table 2 使用 MSLE、MAPE；Table 3 做 CasFT 变体消融；Figure 3-5 和 Table 4 做超参数及 ODE solver 分析。

### 3.3 关键步骤、组件或概念
- 先用 GraphWave/NetSMF 等结构表示与时间编码构造观测表示，再由 ODE-GRU 建模增长率的连续演化；diffusion 模块以观测状态为条件，生成分段 future popularity sequence；最终将生成趋势与观测级联表示融合后回归 popularity。
- 训练同时优化最终规模预测损失和未来趋势生成的负对数似然。论文在 PDF p.5-6 给出 `L = L1 + λL2` 的功能定义；`L1` 约束最终预测，`L2` 约束生成趋势，`λ` 控制二者权衡。

### 3.4 关键形式化内容
由连续状态 `dh/dt = f_θ(h,t)` 得到从观测时间到预测时间的动态推进；增长率可通过积分形成增量。diffusion 逐步估计 `p_θ(Y_{k-1}|Y_k,c)`，生成条件未来序列；这些表达根据 PDF p.3-4 和式(24)-(25) 的可恢复文本整理，未补写不可恢复的排版细节。

### 3.5 核心创新
1. 问题层：把不可见的观测后趋势作为预测对象，而非只拟合最终规模。
2. 方法层：将 neural ODE 的连续动力学和 diffusion 的不确定性生成结合起来。
3. 实验层：按 observation time 和多个 solver/超参数设置报告结果，检验趋势生成模块。

## 4. 证据与结果分析（Evidence & Results）
### 4.1 研究设计与证据协议
- **研究问题/假设**：论文主要检验方法是否改善其定义的任务；不能把论文在封闭候选集上的结果直接外推成开放世界新用户发现。
- **数据与样本**：以论文明确列出的数据集、时间范围、节点/边定义和观察窗口为准；报告中的外部系统数据不能替代论文证据。
- **比较与评估**：优先记录论文原始指标、训练设置、负采样、时间切分、重复次数和消融；若原文未报告方差或置信区间，本文不补造。
- **不确定性**：区分作者主张、论文直接结果、本文推断和外部背景；所有核心数字都带 PDF 页码或图表锚点。

### 4.2 完整图表覆盖清单
| 编号 | PDF 页码 | 作用 | 是否关键 | 文本证据与限制 |
|---|---:|---|:---:|---|
| Figure 1 | PDF p.1 | 方法、理论或主结果 | 是 | A toy example of information popularity predic- tion problem (top) and the variations of average growth rates after observation time in Weibo and APS datasets, respec- tively (bottom), where t0 represents the observation time and tp represents the prediction time.；text-only，未直接核验图像像素。 |
| Figure 2 | PDF p.4 | 方法、理论或主结果 | 是 | An overview of our proposed model CasFT.；text-only，未直接核验图像像素。 |
| Table 1 | PDF p.5 | 方法、理论或主结果 | 是 | Statistics of the three datasets.；text-only，未直接核验图像像素。 |
| Table 2 | PDF p.6 | 方法、理论或主结果 | 是 | Performance comparison between baselines and CasFT on three datasets across different observation times measured by MSLE, MAPE (lower is better).；text-only，未直接核验图像像素。 |
| Table 3 | PDF p.6 | 方法、理论或主结果 | 是 | Performance comparison between CasFT and CasFT-variants on three datasets under two observation times measured by MSLE, MAPE (lower is better).；text-only，未直接核验图像像素。 |
| Figure 3 | PDF p.7 | 辅助背景、消融、复杂度或附录证据 | 否 | Impact of the diffusion steps.；text-only，未直接核验图像像素。 |
| Figure 4 | PDF p.7 | 辅助背景、消融、复杂度或附录证据 | 否 | Impact of the hidden dimension.；text-only，未直接核验图像像素。 |
| Figure 5 | PDF p.7 | 辅助背景、消融、复杂度或附录证据 | 否 | Impact of the interval number.；text-only，未直接核验图像像素。 |
| Table 4 | PDF p.7 | 方法、理论或主结果 | 是 | Impact of different types of ODE Solver on the per- formance of CasFT across the three datasets.；text-only，未直接核验图像像素。 |

### 4.3 关键证据与主要结果
- Table 1（PDF p.5）说明 Twitter、APS、Weibo 的数据统计；正文规定不同数据集的 observation/prediction time、70/15/15 切分和至少 10 个观测期参与者过滤。
- Table 2（PDF p.6）直接比较各 baseline 与 CasFT 的 MSLE、MAPE；文本卡可恢复 Twitter、APS、Weibo 多观察窗口的代表性数值，支持作者关于整体性能改善的主张。
- Table 3（PDF p.6）比较 CasFT 变体，直接用于判断 ODE 和 diffusion 的增益不能互相混同。
- Figure 3-5（PDF p.7）正文称 diffusion steps、hidden dimension 和 interval number 会影响最终预测；Table 4（PDF p.7）正文称 Euler 表现较弱且 dopri5 用于实验，但本轮不对曲线像素作观察。

### 4.4 逐图表解释
#### Figure 1（PDF p.1；关键）
- **原始标题**：A toy example of information popularity predic- tion problem (top) and the variations of average growth rates after observation time in Weibo and APS datasets, respec- tively (bottom), where t0 represents the observation time and tp represents the prediction time.
- **可恢复证据**：`assets/text/visuals/figure-1-p001.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 2（PDF p.4；关键）
- **原始标题**：An overview of our proposed model CasFT.
- **可恢复证据**：`assets/text/visuals/figure-2-p004.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 1（PDF p.5；关键）
- **原始标题**：Statistics of the three datasets.
- **可恢复证据**：`assets/text/visuals/table-1-p005.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 2（PDF p.6；关键）
- **原始标题**：Performance comparison between baselines and CasFT on three datasets across different observation times measured by MSLE, MAPE (lower is better).
- **可恢复证据**：`assets/text/visuals/table-2-p006.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 3（PDF p.6；关键）
- **原始标题**：Performance comparison between CasFT and CasFT-variants on three datasets under two observation times measured by MSLE, MAPE (lower is better).
- **可恢复证据**：`assets/text/visuals/table-3-p006.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 3（PDF p.7；非关键）
- **原始标题**：Impact of the diffusion steps.
- **可恢复证据**：`assets/text/visuals/figure-3-p007.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 4（PDF p.7；非关键）
- **原始标题**：Impact of the hidden dimension.
- **可恢复证据**：`assets/text/visuals/figure-4-p007.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 5（PDF p.7；非关键）
- **原始标题**：Impact of the interval number.
- **可恢复证据**：`assets/text/visuals/figure-5-p007.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 4（PDF p.7；关键）
- **原始标题**：Impact of different types of ODE Solver on the per- formance of CasFT across the three datasets.
- **可恢复证据**：`assets/text/visuals/table-4-p007.md`、图注和正文引用。
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
| C1: 传统 popularity prediction 忽略观测后到预测时刻之间的未来趋势。 | Figure 1, PDF p.1; PDF p.1-2 | 强支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C2: CasFT 使用 neural ODE 与 diffusion 生成未来趋势。 | Figure 2, PDF p.4; PDF p.3-4 | 强支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C3: CasFT 在论文数据协议下改善 MSLE/MAPE。 | Table 2, PDF p.6; Table 3, PDF p.6 | 强支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C4: ODE solver、diffusion steps、hidden dimension 和 interval number 会影响性能。 | Figure 3-5, PDF p.7; Table 4, PDF p.7 | 部分支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |

### 4.7 可靠性、复现性与争议点
- **最可靠结论**：方法定义、输入输出、算法步骤和正文明确报告的表格数值。
- **最弱结论**：仅由图注或 OCR 文本卡推断的像素级趋势，以及把作者称谓转写为普适 SOTA。
- **公平性风险**：数据版本、负采样、时间切分、候选集合、超参数和硬件差异都可能解释性能差异。
- **复现要求**：固定代码 revision、数据版本、随机种子、观察窗口、预测窗口、候选生成、失败日志和完整 JSON 输出。
- **实现核对**：对可运行模型，还要记录 patch/历史长度、邻居采样、负采样类型、显存峰值、单批推理时间和失败重试次数；这些工程量会影响系统是否适合在线事件监测。
- **最小复现实验**：先选一个数据集和一个严格时间切分，复现论文主指标；随后只改变一个组件或协议变量，并保持数据版本、候选集合、训练轮数和随机种子不变。若结果差异超过随机波动，再检查日志中的时间泄漏、样本重复、负采样和用户映射。

## 5. 论文的贡献与影响（Contribution & Impact）
### 5.1 主要贡献
1. 问题层：把不可见的观测后趋势作为预测对象，而非只拟合最终规模。
2. 方法层：将 neural ODE 的连续动力学和 diffusion 的不确定性生成结合起来。
3. 实验层：按 observation time 和多个 solver/超参数设置报告结果，检验趋势生成模块。

### 5.2 对 CogGuard 传播分析与预测的启发
- 传播分析侧应保留 provenance 证据、显式/重建/推断边区分、真实用户映射和可回溯详情；预测侧只读取观测前缀，不能复用未来真实节点。
- 下一跳输出需要明确是“已知用户再激活”还是“开放世界新用户激活”；候选覆盖不足时应 abstain，而不是输出匿名 bucket。
- 宏观趋势输出应同时返回观测规模、预测规模、趋势点、误差区间状态和校准状态；没有校准时不能把集中度分数称为置信度。
- 评测应统一使用时间切分、合法负采样、候选覆盖、Hits/MAP/MRR/NDCG、MSLE/MAE/RMSE/MAPE 以及失败原因。

### 5.3 值得探索的未来方向
1. **CogGuard 可迁移 ODE-style latent dynamics 作为趋势头，但应明确这不是 CasFT 原始 diffusion 复现。**
2. **趋势输出应有多个时间 checkpoint，并与 observed size、future cumulative growth 绑定；单个最终规模不足以支持监测界面。**
3. **若需要误差区间，应另外做 calibration，不能把 diffusion sample spread 或 entropy 直接叫置信度。**

## 6. 结论（Conclusion）
CasFT 是 CogGuard 宏观趋势预测的最直接前沿参考，但当前系统只适合声明“迁移连续趋势思想”；要称 CasFT 复现，必须实现原始 diffusion generator、数据协议和完整对比。

> **最终判断**：值得复现，优先用于 macro 趋势主线；原始训练成本和数据格式较重，建议先复现小规模、再决定是否接入在线系统。
>
> **复现清单**：固定论文版本和代码 revision；准备同版本数据；实现论文输入协议；复现主表和关键消融；记录 3 个以上随机种子、时间切分、候选生成、显存/运行时间和失败日志；最后再迁移到 CogGuard 真实事件。
