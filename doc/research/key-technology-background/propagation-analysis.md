# 传播分析与传播预测研究定位

> 本文定义传播模块的当前研究边界。观测传播分析是系统事实分析能力；传播预测是在严格时间协议下运行的模型能力。二者共享事件范围和实体标识，但不得混合证据语义。

## 1. 功能边界

### 1.1 观测传播分析

输入是 MongoDB 中当前 `event_id/platform` 的 `raw_posts/raw_comments` 快照。系统输出：

- 用户传播投影、分层簇状摘要和关键传播路径；
- URL、标签等共享对象及关联帖子；
- 起爆、扩散等角色和结构指标；
- 用户、帖子、评论、共享对象、事件组成的 provenance 图；
- 时间线、证据引用和删边、删节点、时间前缀稳定性。

关系必须区分：

| 类型 | 含义 | 可作何种结论 |
| --- | --- | --- |
| `explicit` | 平台数据明确给出 `reply_to` 等关系 | 可称平台观测关系 |
| `reconstructed` | 根据父帖子/父评论 ID 重建，但缺少同等强度平台确认字段 | 可称可追溯重建关系 |
| `inferred` | 同一 URL/标签的时间邻近发布者 | 仅可称潜在传播联系 |

布局关系只决定图形位置，不是传播事实。视觉源头是当前证据图中的解释性根节点，不应写成经过因果验证的真实首发源。

当前实现：

- `system/backend/app/services/propagation_observation_service.py`
- `system/backend/app/core/propagation_legacy.py`
- `system/backend/app/core/propagation/roles.py`
- `GET /api/v1/propagation/analyze`

Bi-GCN（AAAI 2020）和 FANG（CIKM 2020）支持传播结构与异构社会上下文建模；PGExplainer（NeurIPS 2020）和 SubgraphX（NeurIPS 2021）支持子图级解释思想；CARE-GNN（CIKM 2020）支持对可疑关系噪声保持谨慎；RumorLens（TVCG 2021）可作为交互与视觉分析参照。这些文献不证明当前规则已复现其模型。

## 2. 传播预测

### 2.1 任务定义

给定带时区的观测截止时间 `t_obs` 与预测范围 `horizon`：

- Macro：预测最终传播规模与未来累计规模趋势；
- Micro：在合法候选集中排序未来可能再激活的真实用户。

所有帖子、评论、候选生成和证据引用必须满足时间不晚于 `t_obs`。非法或无时区截止时间必须拒绝，不能退化为读取完整事件。

### 2.2 当前模型数据流

1. 按 `event_id/platform` 读取事件数据。
2. 在模型调用前按 `observed_until` 截断。
3. 将截止快照转换为用户序列、相对时间、关系邻居和阶段超边。
4. `RelationGNN` 学习训练级联中的用户转移上下文。
5. `DynamicCasHGNN` 聚合传播阶段超边。
6. `SharedLSTM` 编码激活顺序和相对时间。
7. Macro 私有分支预测非负最终增长，并通过 Euler-style latent dynamics 产生单调趋势点。
8. Micro 私有分支对合法 bucket 打分；仅映射为当前事件真实身份的用户进入 Top-K。

系统 checkpoint 位于 `system/research/propagation_analysis/benchmark/checkpoints/propagation_analysis_sequence_twitter_system.pt`，运行时名为 `PropagationSequenceJointModel`。公开接口为 `POST /api/v1/propagation/model-event-predict`。

### 2.3 方法来源与迁移边界

| 研究 | 对当前方法的支撑 | 未复现内容 |
| --- | --- | --- |
| [MINDS, AAAI 2024](https://ojs.aaai.org/index.php/AAAI/article/view/28701) | sequential hypergraph、共享/任务特有表示、多尺度 Macro/Micro 联合建模 | 当前不是官方代码逐层复现，也未完成论文级完整数据协议对齐 |
| [FOREST, IJCAI 2019](https://www.ijcai.org/proceedings/2019/0560.pdf) | 用 Micro 行为约束 Macro 结果的联合优化思想 | 未复现其强化学习训练目标 |
| [CasFT, AAAI 2025](https://doi.org/10.1609/aaai.v39i11.33296) | 连续未来趋势与非静态规模预测思想 | 未复现 diffusion generator 和原始 neural ODE 流程 |
| [TGN, ICML 2020](https://proceedings.mlr.press/v119/rossi20a.html) | temporal edge stream 与时间动态图比较基线 | 当前主干不是 TGN |
| [DyGFormer, NeurIPS 2023](https://proceedings.neurips.cc/paper_files/paper/2023/hash/d611019afba70d547bd595e8a4158f55-Abstract-Conference.html) | 强时序图下一边/节点排名基线 | 当前主干不是动态图 Transformer |
| [TGB, NeurIPS 2023](https://proceedings.neurips.cc/paper_files/paper/2023/hash/c53d4ed65c3fd8a01a2e96b08a30f0e5-Abstract-Datasets_and_Benchmarks.html) | 时间切分、负采样与动态图评估协议 | 尚未完成完整 TGB 风格验证 |

## 3. 输出与学术口径

系统当前输出：

- `macro.observed_size/predicted_size/trend_points/direction`；
- `micro.top_users/candidate_count/candidate_bucket_count/coverage`；
- `data_scope.observed_until/prediction_horizon_hours/excluded_after_cutoff`；
- 模型状态、checkpoint、方法元数据。

当前不能宣称：

- `intervals` 是校准置信区间；系统没有部署独立校准残差；
- score concentration 是预测置信度；它只是分数集中程度；
- Top-K 覆盖可识别新用户；当前真实身份输出主要是已观测用户再激活；
- 系统推理跑通等于模型性能优于 MINDS、FOREST、TGN 或 DyGFormer；
- 已完整复现 CasFT 的 diffusion/Neural ODE。

## 4. 验证要求

| 任务 | 必报指标 |
| --- | --- |
| 规模与趋势 | MSLE、MAE、RMSE、MAPE/sMAPE、Direction Accuracy、Trend MAE/RMSE |
| 下一跳 | Candidate Recall、Hits@K、MAP@K、MRR、NDCG@K、实名映射覆盖率 |
| 观测证据 | 端点完整率、路径完整率、协调用户覆盖率、稳定性、人工抽查通过率 |
| 协议审计 | 数据版本、时间切分、随机种子、候选来源、未来泄漏检查、checkpoint 哈希 |

正式研究结论要求严格时间切分、至少三个随机种子、同协议可训练 baseline、均值与标准差，以及独立校准验证。当前 Twitter checkpoint 已完成系统 CPU 推理接入，但现有样本实验仍标记 `full_validation_passed=false`，只能证明训练与部署流水线可运行。

## 5. 后续优化

1. 将 `propagation_legacy.py` 拆为 provenance、projection、path、role、stability 和 layout 模块。
2. 为大事件提供 provenance 分页/按 ID 查询，避免完整实体图与全量传播投影同时进入一个响应。
3. 接入 Coordination Discover 群组文件，角色主榜只展示协同用户，普通用户保留为路径上下文。
4. 用人工核验边或平台原生转发关系学习推断边可信度，并报告结构扰动鲁棒性。
5. 建立独立时间验证与校准集，补规模区间和下一跳概率校准。
6. 将已知用户再激活和未知新用户激活拆成两个任务；后者需要可解析身份的候选来源或单独的开放世界目标。
7. 在同一数据和候选协议下比较 MINDS、FOREST、TGN、DyGFormer，并报告候选覆盖，而不是只比较排序指标。
