# 传播监控核心功能研究与开发请求

> 适用范围：Propagation Analysis / F-PROP 传播监控模块  
> 目标读者：负责下一轮传播监控代码开发、实验验证和文档同步的组员  
> 当前阶段：前沿研究对齐、代表性方法复现、公开数据集验证  
> 文档目的：将传播监控任务先定位为研究复现与实证验证问题，用研究问题、数据集、评价协议和文献簇约束开发方向，而不是替实现者规定具体模型、字段或代码结构。

---

## 1. 总体定位

传播监控模块当前围绕三个问题展开：

1. **事件规模预测**：在早期观测窗口内，根据传播历史预测后续传播规模及走势。
2. **传播预测（下一节点 / 下一跳）**：在传播尚未结束时，预测下一批可能被激活的用户或传播边。
3. **协同用户角色判定与证据追溯**：对已经确定为协同的用户，在已观测传播图上判定其传播角色，并回溯支撑证据链。

三者的学术性质不同：

| 子问题 | 学术任务 | 时间属性 | 当前状态 | 目标定位 |
|---|---|---|---|---|
| 事件规模预测 | Macroscopic cascade / popularity prediction | 预测未来规模 | 部分落地：已有随机森林离线 baseline | Propagation Analysis 核心研究功能，应对齐事件驱动、非平稳传播预测 |
| 下一节点 / 下一跳预测 | Microscopic diffusion prediction / temporal link prediction | 预测未来参与者或边 | 未完成产品级功能：已有离线候选边分类 baseline | 功能创新扩展，应建立无未来泄漏的前瞻预测协议 |
| 协同用户角色判定与证据追溯 | Propagation role identification / provenance on observed cascades | 解释已发生传播 | 已落地：传播图中心性角色 + 证据链回溯 | 工程支撑功能，应固化并与协同检测结果联动 |

本轮后续开发不应再把“已有 baseline 指标”直接表述为“核心功能已完成”。代码开发应首先修正任务定义与评价协议，再选择具体实现方案。

当前阶段的首要目标不是立即做系统页面功能扩展，而是围绕三项核心功能完成研究对齐闭环：

1. 明确规模预测、角色定位、下一跳预测三项主功能的任务边界。
2. 选择可支撑三项主功能的代表性方法或方法组合。
3. 在可获得的传播数据集上验证其性能和适配性。
4. 将实验结果与当前 `cogguard_dev` baseline 对比，明确哪些能力进入工程落地，哪些保留为研究探索。

---

## 2. 现有实现与目标差距

### 2.1 事件规模预测

现有实现：

- `subsystems/cogguard_dev` 中已有离线规模预测 baseline。
- 方法是基于早期观测子图的结构和时间特征训练 `RandomForestRegressor`，预测最终节点数。
- 验证主要报告 `MAE / RMSE / MAPE / R2`，可作为传统监督学习 baseline。

主要差距：

- 该实现回答的是“早期结构特征能否回归最终规模”，但没有体现主设计文档中的 **CascadeSwitch / 事件条件体制切换** 思路。
- 当前方法缺少对传播非平稳性的显式建模，也没有区分 `seeding / amplification / peak / decay` 等传播阶段。
- LLM 或事件抽取尚未作为外生上下文进入预测过程。
- 评价协议尚未充分对齐级联预测文献常用设定，例如不同 `t_obs`、不同 `t_pred`、MSLE、direction accuracy、跨平台泛化和消融实验。

目标问题：

> 给定一个信息级联在早期观测窗口 `[0, t_obs]` 内的传播历史、传播结构、时间动态和可选事件上下文，估计其在未来 `t_pred` 或最终时刻的规模分布，并解释当前预测主要受哪些传播动态或外生事件驱动。

开发约束：

- 不预设唯一模型；组员可以在 CascadeSwitch、HyperIDP、MINDS、FOREST、CasFT、ConCat、CasDO 等路线中选择或组合，但必须解释其如何服务规模预测。
- LLM、事件抽取、图模型、点过程、Transformer、传统回归都可以作为实现选择；文档只约束任务定义、评估协议和 baseline 对照。
- 必须保留与简单统计、特征回归和当前随机森林 baseline 的对比，避免把复杂模型收益写成默认事实。

### 2.2 下一节点 / 下一跳预测

现有实现：

- `subsystems/cogguard_dev` 中已有路径预测实验。
- 方法是：给定未来 child 和候选 parent，用 `LogisticRegression` 判断候选 parent-child 是否为真实边。
- 输出主要是全局 `AUC / Average Precision`。

主要差距：

- 这更接近离线边分类评估，不等价于线上“下一节点 / 下一跳传播预测”。
- 当前样本构造使用 future child，并在候选集中补入真实 parent，因此不满足严格前瞻预测协议。
- 现有报告没有区分候选集生成质量和候选排序质量。
- 现有功能没有事件级 Top-K 预测对象，因此不能直接被传播监控页面或报告研判消费。

目标问题：

> 给定截止到 `t_obs` 的已观测传播图、节点激活序列和候选用户集合，在不使用未来真实传播节点的条件下，预测未来时间窗 `Δt` 内最可能被激活的用户或最可能出现的传播边。

开发约束：

- 下一节点预测必须是 prospective prediction，不能使用未来节点构造输入。
- 评价必须至少区分两层：候选集合是否覆盖真实未来节点，以及模型能否把真实节点排到前列。
- 组员可以选择逻辑回归、学习排序、图神经网络、时间图模型或点过程模型，但必须证明实验协议不存在未来泄漏。

### 2.3 协同用户角色判定与证据追溯

现有实现：

- 已在 `propagation_legacy.py::build_propagation_graph` 及相关内部流程中落地。
- 图结构使用 NetworkX `MultiDiGraph`。
- `_identify_key_roles` 已通过出入度和介数中心性识别起爆、桥接、扩散等角色。
- `_extract_evidence_chains` / `_extract_key_paths_for_claim` 已能在已观测传播图上回溯证据链和关键路径。

主要差距：

- 当前实现是合理的工程启发式，但尚未在文档中被定义为一个独立的 provenance / role identification 子任务。
- 角色判定当前偏中心性规则，缺少与协同用户集合的显式联动说明。
- 证据链回溯容易被误写成“路径预测”，需要严格区分：它解释已经发生的传播，不预测未来路径。

目标问题：

> 给定已经判定为协同的用户集合及其参与的传播图，在已观测传播事实内识别这些用户的扩散角色，并构造从源头、关键中继到支撑帖的可审计证据链。

开发约束：

- 该功能应作为已落地能力固化，不应与未来下一跳预测混用术语。
- 下一轮开发重点不是重新发明角色识别模型，而是让协同检测结果能够过滤、解释和组织已有传播图证据。
- 若后续增强模型，也应保持可解释性和证据可追溯优先。

---

## 3. 学术任务定义与评价协议

### 3.1 事件规模预测

形式化定义：

给定传播事件 `c` 的部分观测 `O_c(t_obs)`，其中包含截止 `t_obs` 的传播节点、边、时间戳、内容上下文和外部协同信号，学习或构造函数：

```text
F_size: O_c(t_obs) -> P(Y_c(t_pred) | O_c(t_obs))
```

其中 `Y_c(t_pred)` 表示未来时刻或最终时刻的传播规模。若模型只输出点估计，也必须在实验中说明其不确定性处理方式或局限。

推荐评价维度：

| 维度 | 推荐指标 | 用途 |
|---|---|---|
| 规模误差 | MSLE、MAE、RMSE、MAPE | 衡量预测规模与真实规模差距 |
| 趋势方向 | Direction Accuracy、Macro-F1 | 判断预测是否能识别上升、平稳、下降 |
| 早期性 | 不同 `t_obs` 下的性能曲线 | 验证早期预警价值 |
| 不确定性 | 区间覆盖率、校准误差 | 验证置信度是否可信 |
| 泛化性 | 跨数据集 / 跨平台测试 | 验证方法是否依赖单一平台特征 |

最低对比要求：

- 当前 `RandomForestRegressor` baseline。
- 至少一个简单时间外推 baseline，如 naive / moving average / EWMA。
- 至少一个公开文献基线或可比文献结果，如 DeepCas、DeepHawkes、CasFlow、CasCN、TempCas。

### 3.2 下一节点 / 下一跳预测

形式化定义：

给定传播事件在 `t_obs` 前的观测图 `G_c(t_obs)`、已激活节点集合 `V_obs` 和一个不含未来泄漏的候选集合 `U_c(t_obs)`，学习排序函数：

```text
F_next: (G_c(t_obs), V_obs, U_c(t_obs)) -> ranked(U_c)
```

目标是在未来时间窗 `(t_obs, t_obs + Δt]` 内，将真实被激活用户或真实出现的传播边排在候选列表前部。

推荐评价维度：

| 维度 | 推荐指标 | 用途 |
|---|---|---|
| 候选集质量 | Candidate Recall@K / Candidate Coverage | 判断真实未来节点是否进入候选集合 |
| 排序质量 | Hits@K、Recall@K、MRR、MAP、NDCG@K | 判断真实未来节点是否被排到前列 |
| 边预测质量 | AUC、Average Precision | 用于候选边分类，不可单独代表产品能力 |
| 时间预测 | Time MAE / Time RMSE | 若同时预测激活时间，衡量时间误差 |

最低对比要求：

- 当前 `LogisticRegression` 候选边分类 baseline，但必须标注为 offline edge classifier。
- 至少一个基于时间或中心性的非学习 baseline。
- 至少一个微观扩散或时间图方向的强基线，如 Topo-LSTM、FOREST、DeepInf、TGAT、TGN、CAW。

### 3.3 协同用户角色判定与证据追溯

形式化定义：

给定传播图 `G_c`、协同用户集合 `S_coord` 和已识别 claim 集合 `Q_c`，构造解释函数：

```text
F_role: (G_c, S_coord) -> role labels with graph evidence
F_prov: (G_c, Q_c) -> provenance paths and supporting posts
```

该任务不预测未来，而是为已发生传播提供可审计解释。

推荐评价维度：

| 维度 | 推荐检查方式 | 用途 |
|---|---|---|
| 角色稳定性 | 不同事件、不同子图采样下角色是否稳定 | 防止中心性结果对噪声过敏 |
| 证据完整性 | 是否能从 claim 回溯到源头、中继和支撑帖 | 验证报告可用性 |
| 协同联动 | 是否能按协同组过滤角色和路径 | 验证与 Coordination Discover 的闭环 |
| 可解释性 | 每个角色是否有图结构依据 | 避免黑盒标签 |

最低对比要求：

- 与简单中心性基线对齐，如 degree、betweenness、PageRank。
- 与 source detection / provenance 文献中的问题定义保持一致。
- 明确说明该任务不是 next-hop prediction。

---

## 4. 数据集支持

| 数据集 | 适用任务 | 说明 |
|---|---|---|
| DeepHawkes Sina Weibo | 规模预测 | 级联规模预测经典数据来源，适合对齐 DeepHawkes / DeepCas 任务设定 |
| CasFlow Weibo / Twitter / APS | 规模预测、跨平台泛化 | 适合检验结构、不确定性和跨平台泛化 |
| Twitter15 / Twitter16 | 下一跳、传播树、证据追溯 | 显式传播树结构，适合下一节点、关键路径和源头回溯 |
| PHEME | 下一跳、证据追溯、谣言线程分析 | 包含 source tweet 与 reactions，适合 claim 线程和证据链分析 |
| FOREST Twitter / Douban | 微观 + 宏观扩散预测 | IJCAI 2019 FOREST 使用的多尺度扩散预测资源，适合下一节点和规模联合分析 |
| Weibo Rumor / Ma-Weibo | 中文系统验证 | 适合中文传播监控展示；若父节点缺失，需说明 fallback 对路径任务的限制 |
| CogGuard mock_weibo | 工程回归 | 仅用于接口、页面和回归测试，不作为学术主结果 |

数据集使用原则：

- 规模预测至少使用一个微博类数据集和一个非微博 / 跨平台数据集。
- 下一节点预测必须使用能可靠恢复传播树或传播边的数据集。
- 证据追溯可以使用树结构数据集验证路径完整性，但不能据此声称完成未来路径预测。

---

## 5. 高水平文献簇与方法参考池

### 5.1 方法选择原则

本轮不再设置“唯一主复现模型”，也不把某篇论文绑定为最终系统方案。传播监控模块的主功能收敛为 **规模预测 + 角色定位 + 下一跳预测**，方法选择应服务这三项能力，而不是反过来让功能被某个模型锁死。

方法审查准则按优先级排列如下：

1. 是否能支撑三项主功能中的至少一项，并清楚说明覆盖的是宏观规模、角色定位还是微观下一跳。
2. 是否有公开论文、代码、数据集或足够清晰的复现实验协议。
3. 是否能在不引入未来泄漏的前提下与当前 `RandomForestRegressor`、`LogisticRegression` 和图中心性 baseline 对比。
4. 是否留有工程落地弹性，例如可先做可解释启发式、再替换成图模型或时序模型。
5. 是否能为功能创新提供空间，例如多尺度联合建模、协同用户条件化预测、证据链可解释输出等。

### 5.2 统一多尺度扩散预测候选

| 论文 | 作者 | venue + 年份 | 论文链接 | 代码链接 | 数据集支持 | 审查定位 |
|---|---|---|---|---|---|---|
| `HyperIDP: Customizing Temporal Hypergraph Neural Networks for Multi-Scale Information Diffusion Prediction` | Haowei Xu, Chao Gao, Xianghua Li, Zhen Wang | COLING 2025 | https://aclanthology.org/2025.coling-main.64.pdf | 未核实到可访问官方仓库 | Christianity、Android、Douban | 多尺度前沿参照，可启发规模预测与下一跳联合建模 |
| `Enhancing Multi-Scale Diffusion Prediction via Sequential Hypergraphs and Adversarial Learning (MINDS)` | Pengfei Jiao, Hongqian Chen, Qing Bao, Wang Zhang, Huaming Wu | AAAI 2024 | https://ojs.aaai.org/index.php/AAAI/article/view/28701 | https://github.com/cspjiao/MINDS | Christianity、Android、Douban、Memetracker | 开源多尺度候选，可作为复现起点或强 baseline |
| `Multi-scale Information Diffusion Prediction with Reinforced Recurrent Networks (FOREST)` | Cheng Yang, Jian Tang, Maosong Sun, Ganqu Cui, Zhiyuan Liu | IJCAI 2019 | https://www.ijcai.org/proceedings/2019/0560.pdf | https://github.com/yangchengbupt/FOREST | Twitter、Douban、Memetracker | 经典开源多尺度 baseline |
| `MSR: A Multifaceted Self-Retrieval Framework for Microscopic Cascade Prediction` | Dongsheng Hong, Chao Chen, Xujia Li, Shuhui Wang, Wen Lin, Xiangwen Liao | AAAI 2025 | https://ojs.aaai.org/index.php/AAAI/article/view/33282 | 未找到官方仓库 | Twitter、Memetracker、Douban | 微观下一节点候选方法 |

### 5.3 规模预测 baselines：Information Cascade / Popularity Prediction

| 论文 | 作者 | venue + 年份 | 论文链接 | 代码链接 | 数据集支持 | baseline 价值 |
|---|---|---|---|---|---|---|
| `Can Cascades be Predicted?` | Justin Cheng, Lada A. Adamic, P. Alex Dow, Jon Kleinberg, Jure Leskovec | WWW 2014 | https://www.cs.cornell.edu/home/kleinber/www14-cascades.pdf | 未找到 | Facebook photo reshare cascades | 早期可预测性与观测窗口经典定义 |
| `SEISMIC: A Self-Exciting Point Process Model for Predicting Tweet Popularity` | Qingyuan Zhao, Murat A. Erdogdu, Hera Y. He, Anand Rajaraman, Jure Leskovec | KDD 2015 | https://snap.stanford.edu/seismic/ | https://snap.stanford.edu/seismic/ | Twitter | 自激点过程强统计 baseline |
| `DeepCas: an End-to-end Predictor of Information Cascades` | Cheng Li, Jiaqi Ma, Xiaoxiao Guo, Qiaozhu Mei | WWW 2017 | https://arxiv.org/abs/1611.05373 | https://github.com/chengli-um/DeepCas | 常用 Weibo / APS 复现设定 | 深度级联图表示经典 baseline |
| `DeepHawkes: Bridging the Gap between Prediction and Understanding of Information Cascades` | Qi Cao, Huawei Shen, Keting Cen, Wentao Ouyang, Xueqi Cheng | CIKM 2017 | https://dl.acm.org/doi/10.1145/3132847.3132973 | https://github.com/CaoQi92/DeepHawkes | Sina Weibo、citation cascades | Hawkes 机制与深度表示结合 |
| `Variational Information Diffusion for Probabilistic Cascades Prediction (VaCas)` | Fan Zhou, Xovee Xu, Kunpeng Zhang, Goce Trajcevski, Ting Zhong | INFOCOM 2020 | https://www.xoveexu.com/file/paper/20-07-INFOCOM-VaCas.pdf | 未找到 | Weibo、APS | 概率级联预测与不确定性参照 |
| `CasFlow: Exploring Hierarchical Structures and Propagation Uncertainty for Cascade Prediction` | Xovee Xu, Fan Zhou, Kunpeng Zhang, Siyuan Liu, Goce Trajcevski | TKDE 2021 | https://doi.org/10.1109/TKDE.2021.3126475 | https://github.com/Xovee/casflow | Twitter、Weibo、APS | 分层结构与传播不确定性强 baseline |
| `Anytime Information Cascade Popularity Prediction via Self-Exciting Processes (CASPER)` | Xi Zhang, Akshay Aravamudan, Georgios C. Anagnostopoulos | ICML 2022 | https://proceedings.mlr.press/v162/zhang22a.html | https://github.com/xizhang-cc/casper | synthetic + real cascades | anytime popularity prediction baseline |
| `Continuous-Time Graph Learning for Cascade Popularity Prediction (CTCP)` | Xiaodong Lu, Shuo Ji, Le Yu, Leilei Sun, Bowen Du, Tongyu Zhu | IJCAI 2023 | https://www.ijcai.org/proceedings/2023/247 | https://github.com/lxd99/CTCP | Twitter、Weibo、APS | 连续时间图学习强 baseline |
| `Information Cascade Popularity Prediction via Probabilistic Diffusion (CasDO)` | Zhangtao Cheng, Fan Zhou, Xovee Xu, Kunpeng Zhang, Goce Trajcevski, Ting Zhong, Philip S. Yu | TKDE 2024 | https://www.computer.org/csdl/journal/tk/2024/12/10684548/20mFznkhw1G | https://github.com/CZ-TAO12/CasDO | Twitter、Weibo、APS | 概率扩散与 neural ODE 前沿 baseline |
| `On Your Mark, Get Set, Predict! Modeling Continuous-Time Dynamics of Cascades for Information Popularity Prediction (ConCat)` | Xin Jing, Yichen Jing, Yuhuan Lu, Bangchao Deng, Sikun Yang, Dingqi Yang | TKDE 2025 | https://arxiv.org/abs/2409.16623 | https://github.com/UM-Data-Intelligence-Lab/ConCat | Twitter、Weibo、APS | 连续时间动态规模预测 baseline |
| `CasFT: Future Trend Modeling for Information Popularity Prediction with Dynamic Cues-Driven Diffusion Models` | Xin Jing, Yichen Jing, Yuhuan Lu, Bangchao Deng, Xueqin Chen, Dingqi Yang | AAAI 2025 | https://arxiv.org/abs/2409.16619 | https://github.com/UM-Data-Intelligence-Lab/CasFT | Twitter、Weibo、APS | 动态线索驱动趋势建模 baseline |
| `AutoCas: Autoregressive Cascade Predictor in Social Networks via Large Language Models` | Yuhao Zheng, Chenghua Gong, Rui Sun, Juyuan Zhang, Liming Pan, Linyuan Lv | arXiv 2025 | https://arxiv.org/abs/2502.18040 | https://anonymous.4open.science/r/AutoCas-85C6 | Weibo、Twitter、APS | LLM-enhanced cascade prediction baseline |
| `Beyond Leakage and Complexity: Towards Realistic and Efficient Information Cascade Prediction (CasTemp)` | Jie Peng, Rui Wang, Qiang Wang, Zhewei Wei, Bin Tong, Guan Wang | arXiv 2025 | https://arxiv.org/abs/2510.25348 | 未找到 | Twitter、Weibo、APS、Taoke | 无泄漏协议与轻量化现实设定参照 |

### 5.4 下一节点 / 下一跳 baselines：Microscopic Diffusion and Temporal Graph Prediction

| 论文 | 作者 | venue + 年份 | 论文链接 | 代码链接 | 数据集支持 | baseline 价值 |
|---|---|---|---|---|---|---|
| `NetInf` | Manuel Gomez-Rodriguez, Jure Leskovec, Andreas Krause | KDD 2010 | https://dl.acm.org/doi/10.1145/1835804.1835933 | 未找到官方仓库 | cascade diffusion networks | 传播网络推断经典定义 |
| `NetRate` | Manuel Gomez-Rodriguez, David Balduzzi, Bernhard Schölkopf | ICML 2011 | https://icml.cc/2011/papers/561_icmlpaper.pdf | 未找到官方仓库 | continuous-time cascades | 连续时间传播速率推断 |
| `Topological Recurrent Neural Network for Diffusion Prediction (Topo-LSTM)` | Jia Wang 等 | ICDM 2017 | https://arxiv.org/abs/1711.10162 | https://github.com/vwz/topolstm | diffusion cascades | 下一节点预测经典 baseline |
| `Social Influence Prediction with Deep Learning (DeepInf)` | Jiezhong Qiu 等 | KDD 2018 | https://arxiv.org/abs/1807.05560 | 未找到官方仓库 | OAG、Twitter、Weibo、Digg | GNN 社会影响预测 baseline |
| `Inductive Representation Learning on Temporal Graphs (TGAT)` | Da Xu 等 | ICLR 2020 | https://arxiv.org/abs/2002.07962 | https://github.com/StatsDLMathsRecomSys/Inductive-representation-learning-on-temporal-graphs | temporal graph benchmarks | temporal link prediction 强 baseline |
| `Temporal Graph Networks for Deep Learning on Dynamic Graphs (TGN)` | Emanuele Rossi 等 | arXiv 2020 | https://arxiv.org/abs/2006.10637 | https://github.com/twitter-research/tgn | temporal event graphs | memory-based temporal graph baseline |
| `Inductive Representation Learning in Temporal Networks via Causal Anonymous Walks (CAW)` | Yanbang Wang 等 | ICLR 2021 | https://arxiv.org/abs/2101.05974 | https://github.com/snap-stanford/CAW | temporal networks | 无未来泄漏归纳 temporal link baseline |
| `Towards Better Dynamic Graph Learning: New Architecture and Unified Library (DyGFormer / DyGLib)` | Le Yu 等 | NeurIPS 2023 | https://arxiv.org/abs/2303.13047 | https://github.com/yule-BUAA/DyGLib | 14 dynamic graph datasets | 统一复现库与强动态图 baseline |
| `Do We Really Need Complicated Model Architectures For Temporal Networks? (GraphMixer)` | Weilin Cong 等 | ICLR 2023 | https://arxiv.org/abs/2302.11636 | https://github.com/CongWeilin/GraphMixer | temporal link benchmarks | 轻量 temporal link baseline |
| `Time-aware Graph Structure Learning via Sequence Prediction on Temporal Graphs (TGSL)` | Haozhen Zhang 等 | CIKM 2023 | https://arxiv.org/abs/2306.07699 | https://github.com/ViktorAxelsen/TGSL | temporal link benchmarks | 候选边生成与结构增强 baseline |
| `Efficient Neural Common Neighbor for Temporal Graph Link Prediction (TNCN)` | Xiaohui Zhang 等 | arXiv 2024 | https://arxiv.org/abs/2406.07926 | https://github.com/GraphPKU/TNCN | TGB large-scale datasets | 高效 temporal link 前沿 baseline |
| `Future Link Prediction Without Memory or Aggregation (CRAFT)` | Lu Yi 等 | arXiv 2025 | https://arxiv.org/abs/2505.19408 | 未找到官方仓库 | TGB、TGB-Seq 等 | future link prediction 前沿参照 |
| `Taming Heterogeneity in Temporal Interactions for Temporal Graph Link Prediction (TAMI)` | Zhongyi Yu 等 | NeurIPS 2025 | https://arxiv.org/abs/2510.23577 | https://github.com/Alleinx/TAMI_temporal_graph | 经典 temporal graph + TGB datasets | temporal heterogeneity 前沿 baseline |
| `Improving Information Diffusion Prediction by Tackling Noise and Sparsity Challenges (DDiff)` | Songbo Yang | arXiv 2024，已撤回 | https://arxiv.org/abs/2410.18492 | 未找到官方仓库 | 未稳定核实 | 不作为复现目标，仅作为风险提示 |

### 5.5 角色判定与证据追溯：Role Identification and Provenance

| 论文 / 资源 | 作者 | venue + 年份 | 论文链接 | 代码链接 | 与本项目关系 |
|---|---|---|---|---|---|
| `Finding Rumor Sources on Random Trees` | Devavrat Shah, Tauhid Zaman | Operations Research 2011 | https://doi.org/10.1287/opre.1110.0975 | 未找到官方仓库 | 源头追溯理论基础 |
| `Provenance for Online Information Diffusion` | Io Taxidou, Peter M. Fischer 等 | Distributed and Parallel Databases 2018 | https://link.springer.com/article/10.1007/s10619-017-7205-1 | 未找到官方仓库 | 在线信息扩散 provenance 直接参照 |
| `Rumor Detection on Social Media with Bi-Directional Graph Convolutional Networks (Bi-GCN)` | Tian Bian 等 | AAAI 2020 | https://arxiv.org/abs/2001.06362 | https://github.com/TianBian95/BiGCN | 传播图双向结构建模参照 |
| `PHEME dataset for Rumour Detection and Veracity Classification` | Arkaitz Zubiaga 等 | dataset | https://figshare.com/articles/dataset/PHEME_dataset_for_Rumour_Detection_and_Veracity_Classification/6392078 | 数据集链接同左 | 证据链、线程结构和已观测图分析数据 |

---

## 6. 当前阶段开发请求：复现与数据集验证

### 6.1 开发者需要先完成的判断

下一轮开发不从“补字段”或“前端展示”开始，而从三项主功能的最小闭环开始：

1. **规模预测**：当前数据能否支持早期观测窗口到未来规模的预测，选用随机森林、CascadeSwitch、多尺度图模型或其它方法时分别需要哪些输入。
2. **角色定位**：协同用户集合如何进入传播图解释流程，起爆、桥接、扩散、放大等角色如何给出可追溯证据。
3. **下一跳预测**：候选用户或候选边如何在 `t_obs` 时刻生成，如何避免使用 future child、真实 parent 等未来信息。
4. **辅助能力**：立场、危害、情感、影响力指数、前端可视化等只作为辅助增强，不作为主功能完成的前置条件。

### 6.2 复现实验最低交付物

| 交付物 | 要求 |
|---|---|
| 文献复现说明 | 说明选用哪些文献或方法支撑规模预测、角色定位、下一跳预测；可以复现单一模型，也可以组合多个方法，但需解释取舍 |
| 数据集适配报告 | 说明所用数据集的事件数、节点数、边数、时间戳可用性、父子边可用性、文本可用性 |
| 无泄漏划分协议 | 规模预测和下一跳预测都必须说明训练 / 验证 / 测试是否存在时间泄漏 |
| baseline 对比表 | 至少包含当前 `RandomForestRegressor`、`LogisticRegression`、中心性角色识别 baseline；可按任务加入 MINDS、FOREST、Topo-LSTM、TGN、CasFlow 等对照 |
| 结论判断 | 明确该方法是否适合进入 CogGuard 系统落地，若不适合，要说明瓶颈 |

### 6.3 代码开发应满足的最低学术约束

| 子功能 | 最低约束 |
|---|---|
| 规模预测 | 有明确早期观测窗口；能报告规模误差和趋势方向；可选择是否建模不确定性，但需说明局限 |
| 角色定位 | 能按协同用户集合过滤传播图；每个角色标签有图结构或行为证据；允许从启发式规则逐步演进到学习模型 |
| 下一节点预测 | 候选集无未来泄漏；同时报告候选覆盖和排序质量；至少提供一个简单 baseline 和一个文献强 baseline 或协议参照 |

### 6.4 本阶段暂不要求的内容

- 暂不要求前端页面展示最前沿模型结果。
- 暂不要求把复现模型立即改造成统一 API。
- 暂不要求完整复现所有论文。
- 暂不要求确定最终系统落地模型；本阶段只确定三项主功能的任务边界和最小验证闭环。

本阶段真正需要的是：用可运行实验判断哪些前沿研究路线适合我们的数据、任务和系统边界。

### 6.5 不建议在本轮文档中预设的内容

- 不预设最终模型必须是 HyperIDP、CascadeSwitch、MINDS 或任何单一算法。
- 不在本文档中规定具体 API 字段名。
- 不在本文档中规定文件如何拆分。
- 不把工程上暂时可显示的指标当成学术任务完成证明。

组员在下一轮代码开发中可以自由决定实现方式，但需要在 PR 或提交说明中解释：所选方法如何对应前沿文献、如何完成数据集验证、如何满足本文档的问题定义和评价协议。

---

## 7. 与现有文档的同步要求

后续修改代码时，需要同步更新：

- `FEATURE_STATUS_MATRIX.md`：只记录真实落地状态，不把 baseline 写成主功能完成。
- `PROPAGATION_ANALYSIS_COMPLETE_PLAN.md`：如继续保留 CascadeSwitch，应标注为规模预测候选方案之一，而不是整个传播监控模块的唯一技术路线。
- `REFERENCE.md`：新增文献时补充“对 Propagation Analysis 的价值”和“引用方式”。
- 前端传播监控页：不要展示未完成的下一节点预测为已完成功能；已落地的角色判定和证据回溯可以展示，但需标注为已观测图分析。

---

## 8. 快速参考链接

- `HyperIDP` paper https://aclanthology.org/2025.coling-main.64.pdf
- `MINDS` paper https://ojs.aaai.org/index.php/AAAI/article/view/28701
- `MINDS` code https://github.com/cspjiao/MINDS
- `FOREST` paper https://www.ijcai.org/proceedings/2019/0560.pdf
- `FOREST` code https://github.com/yangchengbupt/FOREST
- `Can Cascades Be Predicted?` https://www.cs.cornell.edu/home/kleinber/www14-cascades.pdf
- `SEISMIC` https://snap.stanford.edu/seismic/
- `DeepCas` paper https://arxiv.org/abs/1611.05373
- `DeepCas` code https://github.com/chengli-um/DeepCas
- `DeepHawkes` code https://github.com/CaoQi92/DeepHawkes
- `CasFlow` code https://github.com/Xovee/casflow
- `CasDO` code https://github.com/CZ-TAO12/CasDO
- `ConCat` code https://github.com/UM-Data-Intelligence-Lab/ConCat
- `CasFT` code https://github.com/UM-Data-Intelligence-Lab/CasFT
- `AutoCas` anonymous code https://anonymous.4open.science/r/AutoCas-85C6
- `CasTemp` paper https://arxiv.org/abs/2510.25348
- `Topo-LSTM` code https://github.com/vwz/topolstm
- `TGAT` code https://github.com/StatsDLMathsRecomSys/Inductive-representation-learning-on-temporal-graphs
- `TGN` code https://github.com/twitter-research/tgn
- `CAW` code https://github.com/snap-stanford/CAW
- `DyGFormer / DyGLib` code https://github.com/yule-BUAA/DyGLib
- `TGSL` code https://github.com/ViktorAxelsen/TGSL
- `TNCN` code https://github.com/GraphPKU/TNCN
- `TAMI` code https://github.com/Alleinx/TAMI_temporal_graph
- `Bi-GCN` code https://github.com/TianBian95/BiGCN
- `PHEME` dataset https://figshare.com/articles/dataset/PHEME_dataset_for_Rumour_Detection_and_Veracity_Classification/6392078
- `Twitter15/16` dataset https://github.com/gszswork/Twitter15_16_dataset
