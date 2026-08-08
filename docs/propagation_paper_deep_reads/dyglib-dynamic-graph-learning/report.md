# Towards Better Dynamic Graph Learning: New Architecture and Unified Library：深度精读
> **作者**：Yu 等
> **会议/期刊与年份**：2023
> **论文链接**：本地 PDF 为主；正式引用前请以项目文献索引中的官方链接为准
> **实际使用来源**：`H:\Zotero\attenger\Projects\CISCN\Propagation\Yu 等 - 2023 - Towards better dynamic graph learning new architecture and unified library.pdf`；本地 PDF 文本层、图表文本卡和正文引用
> **页码约定**：全文使用 1-based PDF 页码
> **论文类型**：方法/基准与代码库
> **学科 Lens**：computer-science-ai；动态图学习、信息扩散与可复现评测
> **读者画像**：cross-disciplinary；目标是 reproduce；深度为 deep；语言为 zh-CN
> **视觉能力模式**：text-only
> **解读置信度**：中；方法和结构化数值较可靠，像素级图表内容未核验

> **视觉能力说明**：本报告使用 text-only 工作流生成，未直接核验图像像素内容。图表解释仅依据标题、PDF 文本层、正文引用和结构化文本卡，因此不对坐标轴、颜色、曲线形状、面板布局、裁剪完整性或视觉显著性作未经支持的判断。
> **文本证据边界**：本轮为 text-only；视觉内容未直接核验。
## 1. 核心思想一句话总结（Elevator Pitch）
> DyGLib 用 DyGFormer、patching 和严格负采样规范动态图链路预测。

## 2. 论文背景与动机（Background & Motivation）
### 2.1 具体问题
- PDF p.1-3 指出动态图库实现多、命名和协议不统一，导致模型比较与复现困难。
- Figure 1（PDF p.4）正文用于说明统一框架和 DyGFormer 的结构关系。
- Table 1（PDF p.7）和 Table 2（PDF p.8）分别支持动态链路预测与 NCoE 组件结果。
- Figure 2、Table 3-5（PDF p.8-9）把历史长度、变化率、正负样本和负采样的影响显式化。

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
> 旧方法依赖静态快照、有限候选或固定误差假设，在动态传播和分布漂移下容易失效；本文通过 将连续交互序列切成时间 patch，分别编码节点历史、时间间隔和交互特征，再通过 Transformer 聚合形成候选边表示。，使 解决动态图方法实现分散、数据协议不一致、输入历史长度和负采样差异导致难以公平比较的问题。，但其证据范围仍由数据集、时间切分、候选生成和实现版本限定。

- **作者主张**：同时贡献 DyGFormer 模型、NCoE 组件和统一代码库/评测协议。
- **论文直接证据**：正文和对应 Figure/Table/Algorithm 的页码锚点见第 3、4 节。
- **本文推断**：迁移到 CogGuard 时，必须把论文任务定义和系统的真实事件任务分开，不能把 transductive 结果直接写成开放世界新用户预测。
- **外部背景**：动态图链路预测、信息级联预测和 conformal prediction 的指标并不天然等价，跨论文比较必须统一观察窗口、预测窗口和候选协议。

## 3. 核心方法/理论/研究设计详解（Core Method, Theory, or Study Design）
### 3.1 总体框架
`观测事件/时间边流 → 时间与结构编码 → 共享或任务特有表示 → 预测/校准输出 → 严格时间评估`

**数据流解释**：输入只能使用观测截止时间之前的事件、用户、边、时间戳和合法训练统计；中间模块负责保留时间顺序、局部结构和跨事件关系；输出根据论文类型对应最终规模、未来趋势、下一跳用户、链路分数、图表示或预测区间。

### 3.2 核心流程
1. **起点**：读取带时间戳的 cascade 或 temporal interaction stream。
2. **结构编码**：时间戳边流、节点历史交互、时间 patch、时间编码和候选负样本。
3. **任务输出**：输出动态链路预测/AP 等结果，并分析不同历史长度、变化检测和负采样策略。
4. **评估**：Table 1/2 报告 AP；Figure 2 比较输入长度；Table 3-5 分析变化率、正负样本和负采样。

### 3.3 关键步骤、组件或概念
- DyGFormer 先按时间对节点历史交互进行 patching，以降低长历史序列的计算压力；每个 patch 由时间编码、交互特征和邻居历史编码组成。Transformer 对 patch 序列建模，再将源节点、目标节点及时间上下文融合为候选边分数。NCoE 用于识别交互变化或增强动态图表征。
- 复现核对应把 DyGFormer 的历史 patch 与 CogGuard 的传播窗口一一对应：先按 observed_until 截断，再从训练历史生成 random、historical 和 inductive 三类负样本，最后在同一候选集上计算 AP、MRR、Hits@K 和候选召回。系统接入时还要记录每个 patch 的事件数、邻居采样上限、训练/验证/测试事件数量、峰值显存、单事件推理时延和失败原因。如果未来真实用户被提前加入候选集，结果只能标记为 transductive proxy，不能写成归纳式新用户预测。另外，DyGLib 的链路标签表示“未来是否发生交互”，而 CogGuard 的传播标签还必须保留父用户、帖子、时间戳、边类型和证据引用。因此模型分数只能作为下一跳研判排序，不能单独生成已确认的传播路径；路径事实仍由观测分析模块提供。

### 3.4 关键形式化内容
动态图链路预测可抽象为 `s(u,v,t)=f_θ(P_u^{<t},P_v^{<t},φ(t))`，其中 `P_u^{<t}` 是 t 前的 patch 化历史。训练用正边和固定协议生成的随机、历史或归纳负边；评估 AP/链路排序，不能把未来真实节点混入候选。

### 3.5 核心创新
1. 协议层：将动态图任务、负采样和历史窗口统一到公开库中。
2. 模型层：用 patching 处理长交互历史，降低 Transformer 的时间和显存成本。
3. 工程层：把模型、数据和评估脚本组织为可复现库，适合作为系统 micro runtime 的基线。

## 4. 证据与结果分析（Evidence & Results）
### 4.1 研究设计与证据协议
- **研究问题/假设**：论文主要检验方法是否改善其定义的任务；不能把论文在封闭候选集上的结果直接外推成开放世界新用户发现。
- **数据与样本**：以论文明确列出的数据集、时间范围、节点/边定义和观察窗口为准；报告中的外部系统数据不能替代论文证据。
- **比较与评估**：优先记录论文原始指标、训练设置、负采样、时间切分、重复次数和消融；若原文未报告方差或置信区间，本文不补造。
- **不确定性**：区分作者主张、论文直接结果、本文推断和外部背景；所有核心数字都带 PDF 页码或图表锚点。

### 4.2 完整图表覆盖清单
| 编号 | PDF 页码 | 作用 | 是否关键 | 文本证据与限制 |
|---|---:|---|:---:|---|
| Figure 1 | PDF p.4 | 方法、理论或主结果 | 是 | Framework of the proposed model.；text-only，未直接核验图像像素。 |
| Table 1 | PDF p.7 | 方法、理论或主结果 | 是 | AP for transductive dynamic link prediction with random, historical, and inductive negative sampling strategies. NSS is the abbreviation of Negative Sampling Strategies.；text-only，未直接核验图像像素。 |
| Table 2 | PDF p.8 | 方法、理论或主结果 | 是 | AP for TCL with NCoE.；text-only，未直接核验图像像素。 |
| Figure 2 | PDF p.8 | 方法、理论或主结果 | 是 | Performance of different methods on LastFM and Can. Parl. with varying input lengths.；text-only，未直接核验图像像素。 |
| Table 3 | PDF p.9 | 方法、理论或主结果 | 是 | CLR and CNR of changes made by DyGFormer.；text-only，未直接核验图像像素。 |
| Table 4 | PDF p.9 | 方法、理论或主结果 | 是 | LR and CNR of TP and TN with random negative sampling strategy.；text-only，未直接核验图像像素。 |
| Table 5 | PDF p.9 | 方法、理论或主结果 | 是 | LR and CNR of FP under random, historical, and inductive negative sampling strategy.；text-only，未直接核验图像像素。 |

### 4.3 关键证据与主要结果
- Table 1（PDF p.7）报告 transductive dynamic link prediction 的 AP，并区分 random、historical、inductive negatives。
- Table 2（PDF p.8）报告 NCoE 下的 AP，支撑新增组件的任务价值。
- Figure 2（PDF p.8）显示输入长度变化会改变方法表现；正文支持历史窗口是重要实验变量。
- Table 3-5（PDF p.9）提供变化率、正负样本和负采样分析，提醒复现时不能只抄模型结构。

### 4.4 逐图表解释
#### Figure 1（PDF p.4；关键）
- **原始标题**：Framework of the proposed model.
- **可恢复证据**：`assets/text/visuals/figure-1-p004.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 1（PDF p.7；关键）
- **原始标题**：AP for transductive dynamic link prediction with random, historical, and inductive negative sampling strategies. NSS is the abbreviation of Negative Sampling Strategies.
- **可恢复证据**：`assets/text/visuals/table-1-p007.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 2（PDF p.8；关键）
- **原始标题**：AP for TCL with NCoE.
- **可恢复证据**：`assets/text/visuals/table-2-p008.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Figure 2（PDF p.8；关键）
- **原始标题**：Performance of different methods on LastFM and Can. Parl. with varying input lengths.
- **可恢复证据**：`assets/text/visuals/figure-2-p008.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 3（PDF p.9；关键）
- **原始标题**：CLR and CNR of changes made by DyGFormer.
- **可恢复证据**：`assets/text/visuals/table-3-p009.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 4（PDF p.9；关键）
- **原始标题**：LR and CNR of TP and TN with random negative sampling strategy.
- **可恢复证据**：`assets/text/visuals/table-4-p009.md`、图注和正文引用。
- **逐图表解释**：本报告只解释标题、正文明确描述和文本层可恢复的数字或关系；不解释未被文字证据支持的坐标轴、颜色、曲线形状、布局或视觉显著性。
- **审查状态**：text-only，未直接核验图像像素；因此不能把自动裁剪图当作已完成的视觉复核。

#### Table 5（PDF p.9；关键）
- **原始标题**：LR and CNR of FP under random, historical, and inductive negative sampling strategy.
- **可恢复证据**：`assets/text/visuals/table-5-p009.md`、图注和正文引用。
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
| C1: DyGLib 提供统一动态图学习实现和评测协议。 | Figure 1, PDF p.4; PDF p.1-3 | 强支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C2: DyGFormer 使用 patching 和 Transformer 处理长历史。 | Figure 1, PDF p.4; Figure 2, PDF p.8 | 强支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C3: 负采样协议会显著影响动态图链路预测结果。 | Table 1, PDF p.7; Table 4/5, PDF p.9 | 强支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |
| C4: DyGFormer 直接解决传播分析与开放世界新用户识别。 |  | 未支持 | 数据、时间切分、候选协议或实现差异 | 固定时间切分、3 个随机种子、泄漏审计和失败日志 |

### 4.7 可靠性、复现性与争议点
- **最可靠结论**：方法定义、输入输出、算法步骤和正文明确报告的表格数值。
- **最弱结论**：仅由图注或 OCR 文本卡推断的像素级趋势，以及把作者称谓转写为普适 SOTA。
- **公平性风险**：数据版本、负采样、时间切分、候选集合、超参数和硬件差异都可能解释性能差异。
- **复现要求**：固定代码 revision、数据版本、随机种子、观察窗口、预测窗口、候选生成、失败日志和完整 JSON 输出。
- **实现核对**：对可运行模型，还要记录 patch/历史长度、邻居采样、负采样类型、显存峰值、单批推理时间和失败重试次数；这些工程量会影响系统是否适合在线事件监测。
- **最小复现实验**：先选一个数据集和一个严格时间切分，复现论文主指标；随后只改变一个组件或协议变量，并保持数据版本、候选集合、训练轮数和随机种子不变。若结果差异超过随机波动，再检查日志中的时间泄漏、样本重复、负采样和用户映射。

## 5. 论文的贡献与影响（Contribution & Impact）
### 5.1 主要贡献
1. 协议层：将动态图任务、负采样和历史窗口统一到公开库中。
2. 模型层：用 patching 处理长交互历史，降低 Transformer 的时间和显存成本。
3. 工程层：把模型、数据和评估脚本组织为可复现库，适合作为系统 micro runtime 的基线。

### 5.2 对 CogGuard 传播分析与预测的启发
- 传播分析侧应保留 provenance 证据、显式/重建/推断边区分、真实用户映射和可回溯详情；预测侧只读取观测前缀，不能复用未来真实节点。
- 下一跳输出需要明确是“已知用户再激活”还是“开放世界新用户激活”；候选覆盖不足时应 abstain，而不是输出匿名 bucket。
- 宏观趋势输出应同时返回观测规模、预测规模、趋势点、误差区间状态和校准状态；没有校准时不能把集中度分数称为置信度。
- 评测应统一使用时间切分、合法负采样、候选覆盖、Hits/MAP/MRR/NDCG、MSLE/MAE/RMSE/MAPE 以及失败原因。

### 5.3 值得探索的未来方向
1. **把 cascade edge stream 适配为 DyGFormer 输入，区分确认传播边与推断边。**
2. **对下一跳候选同时报告 transductive 已知用户和 inductive 新用户设置，避免一句“下一跳预测”掩盖任务差异。**
3. **采用 TGB 风格固定负采样、时间切分和 AP/MRR/Hits@K 协议，并记录 patch 长度与推理成本。**

## 6. 结论（Conclusion）
DyGLib/DyGFormer 是 CogGuard 下一跳预测最适合的工程化参考之一；它提供协议和实现，但需要系统自行定义传播事件语义、真实身份映射和开放世界候选集。

> **最终判断**：值得复现，优先作为 micro 预测工程基座；它比单纯启发式排序更接近可训练动态图模型，但不能替代传播分析中的 provenance 图。
>
> **复现清单**：固定论文版本和代码 revision；准备同版本数据；实现论文输入协议；复现主表和关键消融；记录 3 个以上随机种子、时间切分、候选生成、显存/运行时间和失败日志；最后再迁移到 CogGuard 真实事件。
