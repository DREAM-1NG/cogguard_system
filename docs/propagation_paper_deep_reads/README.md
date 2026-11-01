# CogGuard 传播分析与传播预测论文精读索引

> 本目录记录 8 篇与传播分析、宏观级联预测、下一跳动态图预测、评测协议和不确定性校准相关论文的 text-only 深度精读。

## 阅读范围

- 读者画像：computer-science-ai、跨学科读者、目标为 reproduce、深度 deep、语言 zh-CN。
- 每篇报告都逐项覆盖本地抽取清单中的 Figure/Table/Algorithm。
- 本轮没有直接做像素级视觉核验；报告只使用 PDF 文本层、图注、正文引用和结构化文本卡。
- 因此所有视觉清单保留 `visual_verification=not-performed`，不能把报告中的图表解释当作视觉审稿结论。

## 论文分组与 CogGuard 对齐

| 主题 | 论文 | 对 CogGuard 的主要作用 | 复现判断 |
|---|---|---|---|
| 多尺度传播预测 | MINDS | 统一 macro/micro backbone、顺序超图、共享/私有表示和消融协议 | 值得优先复现 |
| 宏观未来趋势 | CasFT | neural ODE + diffusion future trend，支撑趋势曲线而非单点规模 | 值得小规模复现 |
| 连续时间 micro | TGN、DyGLib/DyGFormer | memory、patching、时间边流和可扩展下一跳排序 | 值得复现并做严格候选审计 |
| 归纳式新用户 | CAW | 匿名因果游走和未见节点泛化 | 值得做开放世界补强 |
| 表达性理论 | PINT | 解释 temporal GNN 能否区分传播方向和高阶时序结构 | 值得做诊断复现 |
| 评测协议 | TGB | 时间切分、负采样、MRR/AP、效率和显存统一记录 | 必须借鉴 |
| 区间校准 | Adaptive conformal inference | 分布漂移下的在线 coverage 和 CQR 校准 | 值得接入校准层 |

## 当前系统方法论结论

传播分析是观测功能：从 MongoDB 原始帖子/评论构造 provenance 图，区分显式、重建和推断关系，输出路径、层级、角色、共享对象和证据链。传播预测是独立模型功能：只读取 `observed_until` 前缀，宏观输出规模/趋势，微观输出合法候选用户或边的排序；候选覆盖不足时必须 abstain。

当前真正需要收口的不是再增加一个分类头，而是统一任务协议：事件级宏观标签、用户/边级微观标签、严格时间切分、归纳式候选集、真实用户映射、模型校准和前端可追溯证据。系统公开链路必须只展示当前事件 `observed_until` 前缀上的模型推理；速度、加速度、活动度排序和缓存 benchmark 结果只能作为研究或消融证据，不能作为传播监测页的预测输出。论文结果可以作为方法依据，但不能代替 CogGuard 真实事件上的无泄漏验证。

## 复现总清单

1. 固定每篇论文 PDF、代码 revision、依赖和数据版本。
2. 按原论文的 observation/prediction horizon 构造数据，并记录 transductive/inductive 设置。
3. 先复现主表，再复现关键消融、历史长度、负采样、solver 或采样数量敏感性。
4. 对 CogGuard 单独报告候选覆盖、真实用户映射率、推理时延、显存、失败原因和 abstain 比例。
5. 趋势区间接入独立 calibration split；没有 coverage 证据时不要把集中度分数称为置信度。

## 文件

- [minds-multiscale-diffusion/report.md](minds-multiscale-diffusion/report.md)：Enhancing Multi-Scale Diffusion Prediction via Sequential Hypergraphs and Adversarial Learning
- [casft-future-trend/report.md](casft-future-trend/report.md)：CasFT: Future Trend Modeling for Information Popularity Prediction with Dynamic Cues-Driven Diffusion
- [tgn-temporal-graph-networks/report.md](tgn-temporal-graph-networks/report.md)：Temporal Graph Networks for Deep Learning on Dynamic Graphs
- [cawn-causal-anonymous-walks/report.md](cawn-causal-anonymous-walks/report.md)：Inductive Representation Learning in Temporal Networks via Causal Anonymous Walks
- [dyglib-dynamic-graph-learning/report.md](dyglib-dynamic-graph-learning/report.md)：Towards Better Dynamic Graph Learning: New Architecture and Unified Library
- [temporal-graph-benchmark/report.md](temporal-graph-benchmark/report.md)：Temporal Graph Benchmark for Machine Learning on Temporal Graphs
- [pint-expressive-temporal-networks/report.md](pint-expressive-temporal-networks/report.md)：Provably Expressive Temporal Graph Networks
- [adaptive-conformal-inference/report.md](adaptive-conformal-inference/report.md)：Adaptive Conformal Inference Under Distribution Shift
