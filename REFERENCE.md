# KT2 / F-PROP 传播监控参考文献

> 更新时间：2026-06-28  
> 记录方式：本文记录 KT2 的参考文献、代码仓库、数据集和“文献如何迁移到系统设计”的关系。  
> 统一入口：KT2 当前需求、状态标签与验收标准以 `KT2_REQUIREMENTS.md` 为准；本文仅作为参考文献与研究路线清单，不作为完成状态源。

## 0. 文献迁移到统一 KT2 的方式

KT2 不是单一论文复现，也不是把多个模型机械拼接到产品里。它的统一定位是：面向社交媒体平台的信息扩散监控框架，将宏观规模预测、微观下一跳预测、已观测图上的协同角色解释与证据追溯放进同一套 `standard_cascades`、temporal edge stream、无泄漏 benchmark、dashboard 和 completion gate 中验证。

本轮统一框架进一步收敛为 **Macro/Micro 多尺度传播预测**，并明确采用一条统一方法论：以 MINDS 作为多尺度扩散 baseline 和跨级联表示基础，在此基础上吸收 FOREST 的 macro/micro 相互约束思想，再引入 CasFT 的连续化未来趋势建模。也就是说，MINDS 负责“跨事件共享传播状态从哪里来”，FOREST 负责“宏观规模和微观下一跳如何互相校正”，CasFT 负责“未来趋势如何从离散规模标签扩展为连续演化过程”。三者不是并列主模型，也不意味着 KT2 已复现三篇论文原架构。

| KT2 子模块 | 对应研究领域 | 核心任务定义 | 文献迁移方式 | 数据与评估迁移 |
|---|---|---|---|---|
| 规模预测 | Cascade popularity prediction / temporal cascade forecasting | 给定 `t_obs` 前社交媒体传播级联，预测未来窗口增长量、最终传播规模或未来流行度趋势 | 使用 CasFT 作为主复现候选；DeepHawkes、CasFlow、CasDO、ConCat、DeepCas、SEISMIC 作为统计/深度/连续时间 baseline | 使用 Twitter、Weibo、APS、FOREST Douban/Twitter、Twitter15/16；评估 MSLE、MAE、RMSE、MAPE、Direction Accuracy |
| 下一跳预测 | Dynamic graph learning / temporal link prediction / next activated user ranking | 给定观测前缀图和合法候选集，预测未来窗口内最可能被激活的用户或传播边 | 将级联转为 temporal edge stream；DyGFormer/DyGLib 为主候选，TGN 为 fallback；Topo-LSTM、FOREST、MINDS、DeepInf、TGAT、CAW 和本地 LR/Ranker 作对比 | 使用 FOREST、Twitter15/16、PHEME；评估 Candidate Recall、Hits@K、MAP@K、MRR、NDCG@K，并强制候选集无未来节点注入 |
| 多尺度协议 | Multi-scale information diffusion prediction | 在同一信息扩散任务下同时比较 macro 规模和 micro 下一用户/边预测 | FOREST/MINDS 提供开源多尺度 baseline；HyperIDP 作为时间超图多尺度建模论文参考和 protocol proxy 对照 | 只迁移任务分解、数据切分和共享表示思想；未复现原架构时不得写成完成 |
| 角色定位与证据追溯 | Observed-graph role explanation / source detection / provenance | 对 KT1 已判定协同用户，在已观测传播图中解释其起爆、桥接、放大、二级扩散或普通参与角色，并给出路径、帖子、时间和结构指标证据 | Freeman 介数中心性支撑桥接角色，rumor source detection 支撑源头追溯，online provenance 支撑证据链，Bi-GCN 支撑传播树上下行结构视角 | 使用 PHEME、Twitter15/16、KT1 协同输出；评估路径完整率、协同用户覆盖率、角色稳定性和人工抽查通过率 |

## 0.1 Macro/Micro 统一框架研究总结

| 框架问题 | FOREST 的贡献 | MINDS 的贡献 | CasFT 的贡献 | KT2 统一设计 |
|---|---|---|---|---|
| 如何表达传播状态 | 用 RNN 表示单条级联中的用户激活序列，并引入结构上下文 | 用 sequential hypergraph 表示多个级联之间随时间演化的全局扩散关系 | 用 neural ODE 从观测级联和增长率中提取连续动态线索 | 同时维护级联内状态、跨级联状态和未来趋势状态 |
| 如何连接 macro 与 micro | 用强化学习把宏观规模奖励反馈给微观下一用户预测 | 作为 baseline，用 sequential hypergraph / 共享表示组织跨级联 diffusion state，并用对抗学习与解耦约束降低任务特有特征混淆 | 主要强化 macro，生成未来 popularity trend 后用于最终规模预测 | `KT2SequenceJointModel` 以 MINDS-style `DynamicCasHGNN + RelationGNN + SharedLSTM` 为正式主干，micro 使用下一用户 autoregressive sampled softmax，macro 使用最终规模与 Euler latent trend decoder，FOREST 思想迁移为多步 rollout 期望增长对 macro trend 的软耦合；旧 `KT2JointModel` 的 candidate-level 原组件融合路径只保留为 ablation |
| 输出是什么 | 下一用户预测 + 规模奖励/多尺度评价 | Macro 规模预测 + Micro 扩散预测 | 未来趋势曲线 + 最终规模/流行度预测 | Macro 输出规模/趋势，Micro 输出 Top-K 用户/边，前端展示二者一致性 |
| 工程落地边界 | 经典 baseline，验证多尺度思想 | 强多尺度 baseline，验证跨级联共享表示 | Macro 主复现目标，当前 small-run | 当前已形成 KT2SequenceJointModel 正式序列联合模型 small-run；它迁移三者思想，但不宣称三者论文原架构已经融合复现 |

KT2 迁移原则是：先统一数据协议、任务定义、指标和展示，再实现可验证的本地联合训练链路。当前正式模型是 `KT2SequenceJointModel`：从 FOREST 级联构造多观测窗口序列样本，训练转移图邻居只来自训练级联，micro 标签是紧接观测前缀的下一用户，macro 标签是最终规模和未来累计趋势。模型主干用 `DynamicCasHGNN` 表示观测前缀阶段超边，用 `RelationGNN` 表示训练转移关系邻居，用 `SharedLSTM` 表示级联内时序状态；输出侧同时训练最终规模、Euler latent trend 和 next-user sampled softmax，并用 rollout 期望增长做 FOREST-style 软耦合。`KT2JointModel` 保留为 legacy candidate-level / 原组件融合消融路径；`KT2MacroMicroFramework` 仍是 benchmark 审计行。三者都不能写成 FOREST/MINDS/CasFT 原架构完整复现。

## 1. 前沿候选与多尺度参考

| 文献 | 论文链接 | 代码/资源 | 对 KT2 的价值 | 引用方式 |
|---|---|---|---|---|
| HyperIDP: Customizing Temporal Hypergraph Neural Networks for Multi-Scale Information Diffusion Prediction | https://aclanthology.org/2025.coling-main.64.pdf | 论文标注代码 URL: https://github.com/HowieHsu0126/HyperIDP；2026-06-26 本地记录为公开访问 404 | 同时覆盖宏观规模预测和微观下一用户预测，是 KT2 多尺度任务定义的重要参考 | 仅作为论文参考与 protocol proxy 对照，不能写成原架构复现 |
| MINDS: Enhancing Multi-Scale Diffusion Prediction via Sequential Hypergraphs and Adversarial Learning | https://ojs.aaai.org/index.php/AAAI/article/view/28701 | https://github.com/cspjiao/MINDS | 用顺序超图和对抗学习同时处理 macro/micro diffusion prediction，是开源统一 baseline | 作为可运行多尺度 baseline；不替代 CasFT/DyGLib 主线 |
| FOREST: Multi-scale Information Diffusion Prediction with Reinforced Recurrent Networks | https://www.ijcai.org/proceedings/2019/560 | https://github.com/yangchengbupt/FOREST | 经典多尺度扩散预测模型，将宏观规模 reward 通过 RRModel policy-gradient 反馈给微观 RNN 下一用户预测 | 作为经典多尺度 baseline 和 Douban/Twitter 数据适配来源；本地 adapter 已跑通 batch-limited / rollout-capped RL smoke，用于证明 macro/micro coupling 代码路径可执行，但不是 full-run 性能结论 |
| CasFT: Future Trend Modeling for Information Popularity Prediction with Dynamic Cues-Driven Diffusion Models | https://arxiv.org/abs/2409.16619 | https://github.com/UM-Data-Intelligence-Lab/CasFT | 用 neural ODE 提取动态线索，并用 diffusion model 生成未来流行度趋势，是规模预测主候选 | 当前只能写为 `frontier_reproduction_small_run`，后续需多数据多种子 full-run |
| DyGFormer / DyGLib: Towards Better Dynamic Graph Learning | https://papers.nips.cc/paper_files/paper/2023/hash/d611019afba70d547bd595e8a4158f55-Abstract-Conference.html | https://github.com/yule-BUAA/DyGLib | Transformer 动态图方法与统一动态图复现库，支撑下一跳候选边/用户排序 | 下一跳预测主候选；当前只完成 small-run，不是产品级最终模型 |

## 2. 规模预测：社交媒体级联时序预测

规模预测属于社交媒体平台上的时序级联预测问题。它不是普通单变量时间序列预测，而是利用早期传播子图、转发/回复时间戳、用户序列和内容上下文，预测未来传播规模或流行度趋势。

| 文献 | 论文链接 | 代码/数据 | 方法与功能 | 如何支撑 KT2 |
|---|---|---|---|---|
| Can Cascades be Predicted? | https://www.cs.cornell.edu/home/kleinber/www14-cascades.pdf | 无官方复现要求 | 经典早期观测窗口 cascade predictability 研究，强调早期结构和时间特征对最终传播规模的预测价值 | 支撑 KT2 “给定 `t_obs` 预测未来/最终规模”的任务定义 |
| SEISMIC | https://snap.stanford.edu/seismic/ | https://snap.stanford.edu/seismic/ | 基于自激点过程的 tweet popularity prediction 统计模型 | 作为统计模型 baseline 参考，帮助检查深度模型是否真正优于强统计基线 |
| DeepCas | https://arxiv.org/abs/1611.05373 | 可参考 https://github.com/ChenNed/Awesome-DL-Information-Cascades-Modeling | 使用随机游走采样级联图并学习深度级联表示 | 作为深度级联表示的早期 baseline 参考 |
| DeepHawkes | https://dl.acm.org/doi/10.1145/3132847.3132973 | https://github.com/CaoQi92/DeepHawkes | 将 Hawkes 过程强度机制与深度表示结合，兼顾预测和可解释传播强度 | 支撑中文微博规模预测对照和“传播强度/时间激发”解释 |
| CasFlow | https://ieeexplore.ieee.org/document/9519551 | https://github.com/Xovee/casflow | 建模级联结构与不确定性，关注跨平台 cascade prediction | 支撑跨平台泛化与不确定性 baseline |
| CasDO | https://github.com/CZ-TAO12/CasDO | https://github.com/CZ-TAO12/CasDO | 概率扩散与 neural ODE 路线，面向信息级联流行度预测 | 作为 CasFT 不可运行时的前沿 fallback / 对比模型 |
| ConCat | https://github.com/UM-Data-Intelligence-Lab/ConCat | https://github.com/UM-Data-Intelligence-Lab/ConCat | 连续时间级联动态建模，关注 observed cascade 到未来规模的连续演化 | 作为 CasFT 的连续时间 baseline 或 fallback |
| CasFT | https://arxiv.org/abs/2409.16619 | https://github.com/UM-Data-Intelligence-Lab/CasFT；Twitter/Weibo/APS | 用 neural ODE 学习观测期动态线索，再用 diffusion model 生成未来 popularity trend，并融合观测级联做最终预测 | KT2 规模预测主复现目标；需要从 small-run 扩展到多窗口、多数据、多随机种子 |

## 3. 下一跳预测：GNN / 动态图预测问题

下一跳预测可以落到动态图学习中的 temporal link prediction 或 next activated user ranking：传播图随时间新增用户和边，模型根据历史交互序列、候选集和观测前缀，预测未来窗口内最可能出现的传播边或被激活用户。因此它与 GNN for prediction 相关，但更准确地说是 continuous-time dynamic graph prediction，而不是静态 GNN 分类。

| 文献 | 论文链接 | 代码/资源 | 方法与功能 | 如何支撑 KT2 |
|---|---|---|---|---|
| Topo-LSTM | https://arxiv.org/abs/1711.10162 | https://github.com/vwz/topolstm | 面向 diffusion prediction 的拓扑感知 LSTM，预测下一批/下一节点扩散 | 作为信息扩散领域的经典微观预测 baseline |
| DeepInf | https://arxiv.org/abs/1807.05560 | 无稳定官方代码要求 | 用图神经网络建模社交影响预测，关注用户是否会被影响 | 支撑“候选用户激活概率排序”的任务视角 |
| TGAT | https://arxiv.org/abs/2002.07962 | https://github.com/StatsDLMathsRecomSys/Inductive-representation-learning-on-temporal-graphs | temporal graph attention，用时间编码和邻域聚合进行动态图表示学习 | 作为无未来泄漏 temporal link prediction 协议参考 |
| TGN | https://arxiv.org/abs/2006.10637 | https://github.com/twitter-research/tgn | 用 memory module 和 graph operator 表示连续时间动态图事件序列 | KT2 下一跳 fallback；当前已 small-run，需扩展事件级 Top-K 和多种子验证 |
| CAW | https://arxiv.org/abs/2101.05974 | https://github.com/snap-stanford/CAW | causal anonymous walks，用时间约束随机游走做归纳式 temporal network representation | 作为候选边预测中“不能偷看未来路径”的协议参考 |
| DyGFormer / DyGLib | https://papers.nips.cc/paper_files/paper/2023/hash/d611019afba70d547bd595e8a4158f55-Abstract-Conference.html | https://github.com/yule-BUAA/DyGLib | DyGFormer 使用邻居共现编码和 patching Transformer 学习长历史动态交互；DyGLib 提供统一训练和评估管线 | KT2 下一跳主复现目标；把传播级联转成 temporal edge stream 后用于候选用户/边排序 |

## 4. 角色定位与证据追溯：已观测图解释

角色定位不是下一跳预测，也不是未来路径生成。KT2 当前只对已观测传播图进行解释：在 KT1 已判定协同用户集合内，按结构位置和传播证据识别起爆/源头、桥接、放大、二级扩散和普通参与者，并追溯其路径、帖子、时间和上下文证据。

| 文献 / 资源 | 链接 | 方法与功能 | 如何支撑 KT2 |
|---|---|---|---|
| Freeman, A Set of Measures of Centrality Based on Betweenness | https://www.jstor.org/stable/3033543 | 提出以最短路径中介位置衡量节点控制通信流的介数中心性 | 支撑“桥接角色”的结构指标解释 |
| Finding Rumor Sources on Random Trees | https://doi.org/10.1287/opre.1110.0975 | 研究随机树上的谣言源头检测和源头估计理论 | 支撑“起爆/源头”角色和源头追溯任务背景 |
| Web-scale Provenance Reconstruction of Implicit Information Diffusion on Social Media | https://ruben.verborgh.org/publications/taxidou_dapd_2018/ | 面向社交媒体信息扩散的 provenance reconstruction，强调细粒度追溯、隐式影响和在线扩展 | 直接支撑 KT2 的证据链、关键路径、时间线回溯设计 |
| Bi-GCN: Rumor Detection on Social Media with Bi-Directional Graph Convolutional Networks | https://ojs.aaai.org/index.php/AAAI/article/view/5393 | 对传播树做 top-down 与 bottom-up 双向 GCN 建模，利用传播和扩散结构 | 支撑 KT2 在已观测传播图上同时看“源头到下游”和“下游回源”的结构解释 |

## 5. 数据集与验证资源

| 数据集 / 资源 | 链接 | 支撑模块 | 使用方式 |
|---|---|---|---|
| CasFT Twitter/Weibo/APS | https://github.com/UM-Data-Intelligence-Lab/CasFT | 规模预测 | 按 CasFT 官方格式放置数据，验证未来趋势生成与最终规模预测 |
| DeepHawkes Weibo | https://github.com/CaoQi92/DeepHawkes | 规模预测 | 中文微博规模预测 baseline 和 Hawkes 强度解释 |
| FOREST Douban/Twitter | https://github.com/yangchengbupt/FOREST | 多尺度、下一跳、规模预测 | 作为 KT2 small-run 和多尺度 baseline 数据源；当前本地 `G:\CISCN\dataset\forest-data` 支持 FOREST 原代码普通 RNN 与 RRModel policy-gradient smoke-run |
| Information Diffusion Datasets | https://github.com/fuxiaG/Information-Diffusion-Datasets | 多尺度/规模预测 | 汇总多个信息扩散任务数据，可用于补充 benchmark |
| Twitter15/16 | https://github.com/gszswork/Twitter15_16_dataset | 传播树、角色证据、下一跳 | 显式传播树结构，适合角色识别、源头追溯和未来边验证 |
| Rumor_RvNN | https://github.com/majingCUHK/Rumor_RvNN | Twitter15/16 补充来源 | 支撑 Twitter 谣言传播树数据解析 |
| PHEME veracity dataset | https://figshare.com/articles/dataset/PHEME_dataset_for_Rumour_Detection_and_Veracity_Classification/6392078 | 角色证据、时间线、谣言线程 | 用真实事件线程验证 observed-graph 证据追溯和时间线 |
| PHEME rumours/non-rumours classic | https://figshare.com/articles/dataset/PHEME_dataset_of_rumours_and_non-rumours/4010619 | 角色证据、谣言线程 | 作为 PHEME 经典 RNR 版本补充 |

## 6. 核心功能报告指标

| KT2 功能 | 主要参考方法 | 数据集支撑 | 报告指标 |
|---|---|---|---|
| 规模预测 | CasFT、SEISMIC、DeepCas、DeepHawkes、CasFlow、CasDO、ConCat、RF/Temporal baseline | 当前已用 FOREST Douban；后续扩展 CasFT Twitter/Weibo/APS、FOREST Twitter、DeepHawkes Weibo、Twitter15/16、Rumor_RvNN/Weibo | MSLE、MAE、RMSE、MAPE/sMAPE、Direction Accuracy、不同 `t_obs` 观测窗口表现；可补充 PCC、R2、预测区间覆盖率。每个结果必须同时记录数据版本、切分、随机种子、复现等级和命令/日志路径 |
| 下一跳预测 | DyGFormer/DyGLib、TGN、Topo-LSTM、DeepInf、TGAT、CAW、FOREST/MINDS、ProspectiveRanker/Heuristic baseline | 当前已用 FOREST Douban temporal edge stream；后续扩展 FOREST Twitter、Twitter15/16、Rumor_RvNN、PHEME | Candidate Recall、Hits@10/50/100、MAP@10/50/100、MRR、NDCG@10/50/100、平均候选集大小、候选来源、无泄漏审计；动态图上游训练可补充 AP/AUC，但 KT2 主比较以事件级 Top-K 排序指标为准 |
| 协同角色定位与证据追溯 | Freeman betweenness centrality、rumor source detection、online information diffusion provenance、Bi-GCN | 当前已用 KT1 本地样例与 PHEME 5 个真实时间线样例；后续扩展真实 KT1 跨事件输出、完整 PHEME、Twitter15/16、Rumor_RvNN/Weibo | coordination_user_coverage、path_complete_rate、role_stability、人工审核通过率、evidence_match、confidence_1to5；结构证据字段包括 out_degree_sum、betweenness_sum、pagerank_sum、post_count、first_seen、evidence_paths |

## 7. 当前引用口径

- 规模预测可以表述为“社交媒体信息级联的时序/流行度预测”，但需要强调它使用传播图结构、时间戳和级联上下文，不等同于普通时间序列预测。
- 下一跳预测可以表述为“动态图/GNN 预测问题”，更精确地说是 temporal link prediction 或 next activated user ranking；必须保留无未来泄漏候选集约束。
- 角色定位应表述为“已观测传播图上的解释与 provenance”，不是未来路径预测；当前实现是中心性与路径证据规则，不是监督学习角色分类。
- HyperIDP、MINDS、FOREST 作为多尺度任务定义和 baseline 支撑；CasFT 和 DyGFormer/DyGLib 分别是规模预测与下一跳预测的主要前沿复现候选；TGN 是下一跳 fallback；Freeman、source detection、provenance、Bi-GCN 是角色证据的理论和结构建模支撑。
- FOREST、MINDS、CasFT 迁移到 KT2 时分别对应 macro/micro 桥接、跨级联共享表示和 macro 未来趋势生成；MINDS 的 `Module.forward/RelationGNN` auxiliary、FOREST 的 RRModel policy-gradient adapter、CasFT 的 `CombinedSpatiotemporalModel5/NeuralPointProcess` TPP auxiliary 均已完成 KT2 joint small-run 接入；这些只能证明原始子路径可执行，`macro_micro_consistency` 只能写作协议层一致性审计指标，不能写作新模型性能或 full-run 完成证据。


