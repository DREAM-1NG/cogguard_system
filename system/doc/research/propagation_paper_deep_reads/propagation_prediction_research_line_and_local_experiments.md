# 传播预测研究线补充与本地实验对比

> 更新日期：2026-08-10  
> 系统功能名：传播监测 / 传播预测  
> 系统方法名：`PropagationAnalysisSequenceJointModel`  
> 研发侧旧命名：`KT2SequenceJointModel`，仅用于解释历史实验文件名，不用于前端文案。

## 1. 任务边界

传播预测不是观测传播分析的一部分。观测传播分析只解释已经采集到的事实，传播预测只在给定 `observed_until` 或 `observation_ratio` 的前缀上预测未来趋势和下一跳研判。

当前传播预测分为两个任务：

| 层级 | 任务定义 | 当前系统输出 | 当前边界 |
|---|---|---|---|
| Macro | 给定观测截止前的级联前缀，预测最终规模和未来累计趋势 | `observed_size`、`predicted_size`、`trend_points`、`direction`、`calibration_status` | 趋势曲线已可输出，但区间尚未校准，不能称为置信区间 |
| Micro | 给定观测前缀和合法候选用户，预测下一跳用户排序 | `top_users`、`candidate_count`、`coverage`、`reactivation_count` | 当前主要是已知用户再激活研判，不是可靠的开放世界新用户激活预测 |

严格时间约束为：

```text
event rows
  -> filter rows by observed_until
  -> build observed prefix
  -> generate legal candidates without future tail
  -> run model inference
  -> output trend curve and top users
```

不能从 `observed_until` 之后的真实节点构造候选集，也不能在模型不可用时用速度、加速度或活动度排序伪装成模型预测。

## 2. 研究线补充

### 2.1 Multi-scale macro / micro diffusion prediction

这一线回答：规模预测和下一用户预测是否应被统一建模。

| 论文 |  venue | 方法要点 | 对系统的迁移 |
|---|---|---|---|
| [FOREST / reinforced recurrent diffusion prediction](https://www.ijcai.org/proceedings/2019/560), IJCAI 2019 / TNNLS extension | CCF-A / CCF-B | 用 RNN 建模微观传播序列，用强化学习把不可微的宏观规模信号反馈到微观预测 | 支撑 macro/micro 软耦合思想，但当前系统没有复现其 RL 训练 |
| [MS-HGAT](https://ojs.aaai.org/index.php/AAAI/article/view/20334), AAAI 2022 | CCF-A | 用 memory-enhanced sequential hypergraph 捕捉用户和级联的动态依赖 | 支撑把级联阶段组织为动态超图，而不是只做单级联序列 |
| [MINDS](https://ojs.aaai.org/index.php/AAAI/article/view/28701), AAAI 2024 | CCF-A | 用 sequential hypergraph、social homophily、shared/private 表示、adversarial learning 和 orthogonality 同时优化 macro 与 micro | 当前系统方法的主干直接对齐这一线，是正式 baseline 对比对象 |
| [Ghidorah / test-time training for robust multi-scale diffusion](https://ojs.aaai.org/index.php/AAAI/article/view/33470), AAAI 2025 | CCF-A | 面向分布漂移，在测试时用自监督辅助任务做实例级适配 | 支撑下一阶段解决跨平台、跨事件泛化问题 |
| [HyperIDP](https://aclanthology.org/2025.coling-main.64/), COLING 2025 | NLP 顶会 | 用 temporal hypergraph 做多尺度预测，并强调任务间互补表示 | 可作为后续 temporal hypergraph backbone 的细化参考 |

系统方法的当前形式：

```text
user_sequence, timestamps
  -> user embedding
  -> RelationGNN
  -> DynamicCasHGNN
  -> SharedLSTM
  -> shared state z_shared
  -> macro private state z_macro
  -> micro private state z_micro
  -> final-size head + trend decoder
  -> next-user decoder
```

训练目标应保持为多任务软耦合，而不是把 micro 候选概率和 macro 最终规模硬等同：

```math
L = L_{final} + \lambda_t L_{trend} + \lambda_u L_{next}
    + \lambda_c L_{soft}
    + \lambda_a L_{adv}
    + \lambda_o L_{orth}
```

其中 `L_soft` 只约束短期 rollout 增长方向或局部增长量，不应使用：

```math
\sum_{u \in U_{candidate}} \sigma(s_u) = y_{final} - y_{obs}
```

原因是候选集不完整，且已知用户再激活不等价于新增传播规模。

### 2.2 Future trend and continuous-time cascade modeling

这一线回答：规模预测是否应该只输出一个数，还是输出未来趋势曲线。

| 论文 | venue | 方法要点 | 对系统的迁移 |
|---|---|---|---|
| [CasFT](https://arxiv.org/abs/2409.16619), AAAI 2025 | CCF-A | 用 Neural ODE 提取观测动态线索，再用 diffusion model 生成 future popularity trend，并融合趋势表示预测最终规模 | 当前系统只迁移连续趋势思想，没有复现 diffusion generator |
| [GODEN](https://dl.acm.org/doi/10.1145/3664647.3681363), ACM MM 2024 | CCF-A | 用 Graph Neural ODE 建模连续时间扩散过程 | 支撑把当前 Euler-style trend decoder 升级为显式连续时间动态图模型 |
| [CasFlow](https://doi.org/10.1109/TKDE.2021.3126475), TKDE 2021 | CCF-B | 建模层次结构和传播不确定性，用于 cascade popularity prediction | 可作为 macro 规模预测和不确定性建模 baseline |

当前系统 Macro 头可以写成：

```math
z = f_{\theta}(C_{\le t_{obs}}, G_{rel}, H_{cas})
```

```math
\hat y_{final} = y_{obs} + \operatorname{softplus}(g_{\theta}(z_{macro}))
```

趋势解码采用单调累计形式：

```math
h_{k+1} = h_k + \Delta t \cdot F_{\theta}(h_k, k/H, r_{obs})
```

```math
\hat y_{k+1} = \hat y_k + \operatorname{softplus}(q_{\theta}(h_{k+1})) \Delta t
```

这保证 `trend_points` 不小于观测规模，但还不能表达 CasFT diffusion generator 的多样未来趋势分布。

### 2.3 Temporal graph and inductive next-hop prediction

这一线回答：下一跳预测如何从“已知用户再激活”走向“开放世界新用户激活”。

| 论文 / 框架 | venue | 方法要点 | 对系统的迁移 |
|---|---|---|---|
| [TGN](https://arxiv.org/abs/2006.10637), 2020 | 动态图基础方法 | 用 memory、message、aggregator、updater 处理 timed event stream | 可把帖子、评论、转发、回复统一成连续时间事件流 |
| [CAW](https://openreview.net/forum?id=KYPz4YsCPj), ICLR 2022 | CCF-A | 用 causal anonymous walks 做归纳式 temporal link prediction，不依赖固定节点身份 | 是补齐未参与事件新用户候选的重要方向 |
| [DyGFormer / DyGLib](https://proceedings.neurips.cc/paper_files/paper/2023/hash/d611019afba70d547bd595e8a4158f55-Abstract-Conference.html), NeurIPS 2023 | CCF-A | 使用历史一跳交互、邻居共现编码和 patching Transformer，并提供统一评测库 | 支撑 micro head 替换和严格动态负采样实验 |
| [TGB](https://arxiv.org/abs/2307.01026), NeurIPS 2023 Datasets and Benchmarks | CCF-A | 提供 temporal graph benchmark、loader、evaluator、leaderboard，强调 realistic negatives | 支撑 random、historical、inductive negatives 的下一跳评测协议 |
| [RotDiff](https://dl.acm.org/doi/10.1145/3583780.3615041), CIKM 2023 | CCF-B | 用双曲空间和旋转表示建模扩散路径中的层级和非对称关系 | 可用于传播路径层级强、树状结构明显的数据集 |
| [H-Diffu](https://dl.acm.org/doi/10.1109/TKDE.2022.3209067), TKDE 2022 | CCF-B | 用双曲表示联合社会图和传播图，预测潜在被影响用户 | 可作为 micro 下一用户预测的几何表示 baseline |

当前系统 micro 输出更准确地定义为：

```math
\Pr(u_{next}=u \mid C_{\le t_{obs}}, u \in U_{mapped})
```

它不是完整开放世界任务：

```math
\Pr(u_{new} \in U_{future} \setminus U_{\le t_{obs}} \mid C_{\le t_{obs}}, G_{history})
```

要补齐开放世界能力，需要：

| 能力 | 必要实现 |
|---|---|
| 历史候选池 | 建立跨事件历史互动图、训练用户目录和平台身份映射表 |
| 归纳式表示 | 引入 CAW 或 DyGFormer/TGN 风格 temporal graph encoder |
| 候选审计 | 报告 `candidate_count`、`candidate_recall`、`mapped_bucket_coverage`、`unmapped_bucket_count` |
| 无泄漏评测 | random negatives、historical negatives、inductive negatives 分开报告 |
| 前端语义 | 在未完成身份映射前，继续声明为已知用户再激活研判 |

### 2.4 Uncertainty and calibration

这一线回答：趋势区间能否被称为置信区间。

| 论文 | venue | 方法要点 | 对系统的迁移 |
|---|---|---|---|
| [Adaptive Conformal Inference](https://arxiv.org/abs/2106.00170), NeurIPS 2021 | CCF-A | 在线调整 conformal 参数，在分布变化下维持长期覆盖率 | 用于把当前 `intervals=None` 升级为有验证覆盖率的趋势区间 |
| [TGB](https://tgb.complexdatalab.com/) | benchmark | 强调可复现 temporal split 和标准 evaluator | 用于保证区间和下一跳指标不是由简单负样本或泄漏造成 |

当前系统不能展示“置信区间”，只能展示：

```text
calibration_status = unavailable
intervals = null
score = model score or score concentration
```

下一阶段需要用验证集残差构造 conformal interval：

```math
I_t(x) = [\hat y_t(x) - q_{1-\alpha}, \hat y_t(x) + q_{1-\alpha}]
```

并在 rolling backtest 中报告覆盖率：

```math
coverage = \frac{1}{N}\sum_i 1[y_i \in I_i]
```

## 3. 本地实验数据集

本地实验使用 FOREST 格式数据：

| 数据集 | 本地路径 | 文件 | 用途 |
|---|---|---|---|
| Douban | `G:\CISCN\dataset\forest-data\douban` | `cascade.txt`、`cascadevalid.txt`、`cascadetest.txt`、`edges.txt` | 社交扩散主实验 |
| Twitter | `G:\CISCN\dataset\forest-data\twitter` | `cascade.txt`、`cascadevalid.txt`、`cascadetest.txt`、`edges.txt` | 社交扩散主实验，也是系统默认 checkpoint 训练来源 |
| Memetracker | `G:\CISCN\dataset\forest-data\memetracker` | `cascade.txt`、`cascadevalid.txt`、`cascadetest.txt` | 辅助泛化数据集，本地 staged social edges 为 0，不适合作为社交图强结论 |

可用外部实现：

| 方法 | 本地路径 |
|---|---|
| MINDS | `G:\CISCN\dataset\MINDS` |
| FOREST | `G:\CISCN\CogGuard\subsystems\kt2_repos\FOREST` |
| CasFT | `G:\CISCN\CogGuard\subsystems\kt2_repos\CasFT` |
| DyGLib | `G:\CISCN\CogGuard\subsystems\kt2_repos\DyGLib` |
| TGN | `G:\CISCN\CogGuard\subsystems\kt2_repos\tgn` |

系统侧 checkpoint：

```text
G:\CISCN\CogGuard\.worktrees\refactor-system\system\research\propagation_analysis\benchmark\checkpoints\propagation_analysis_sequence_twitter_system.pt
```

## 4. 对比对象与口径

正式比较只使用可训练模型：

| 角色 | 名称 | 说明 |
|---|---|---|
| Baseline | `MINDS` | 官方公开代码适配，作为多尺度 diffusion prediction baseline |
| System | `PropagationAnalysisSequenceJointModel` | 系统侧命名，研发侧同源为 `KT2SequenceJointModel` |

不进入正式 improvement verdict 的对象：

```text
RF_Baseline
TemporalSizeBaseline
LR_EdgeClassifier
ProspectiveHeuristic
ProspectiveRanker
HyperIDPProtocolProxy
velocity / acceleration / activity fallback
```

原因是这些方法不是同等级的可训练 macro/micro 联合模型。

## 5. 已有 3 seed 采样实验结果

结果文件：

```text
G:\CISCN\CogGuard\.worktrees\refactor-system\system\research\propagation_analysis\benchmark\sequence_vs_minds_sample_300c_5ep_3seed.json
```

实验配置：

| 项 | 值 |
|---|---|
| datasets | `douban,twitter,memetracker` |
| seeds | `42,43,44` |
| epochs | `5` |
| MINDS cascade cap | `300` |
| system train/eval cap | train `300`, eval `100` |
| evidence_level | `preflight` |
| full_validation_passed | `false` |
| overall_verdict | `does_not_support_propagation_analysis_improvement` |

未通过 full validation 的原因：

| 检查项 | 结果 |
|---|---|
| dataset_count_at_least_3 | pass |
| seed_count_at_least_3 | pass |
| minds_epochs_at_least_5 | pass |
| propagation_analysis_epochs_at_least_5 | pass |
| minds_uses_all_available_cascades | fail |
| propagation_analysis_uses_all_train_and_test_cascades | fail |
| no_missing_model_pairs | pass |

### 5.1 公共指标均值

公共指标只包含两边都能直接比较的指标。

| dataset | method | MSLE lower better | Hits@10 higher better | Hits@50 higher better | Hits@100 higher better | MAP@10 higher better | MAP@50 higher better | MAP@100 higher better |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| douban | MINDS | 0.0632 | 0.1535 | 0.2140 | 0.2723 | 0.0802 | 0.0827 | 0.0836 |
| douban | PropagationAnalysisSequenceJointModel | 0.1063 | 0.0089 | 0.0256 | 0.0522 | 0.0035 | 0.0041 | 0.0044 |
| twitter | MINDS | 0.2733 | 0.0569 | 0.1047 | 0.1414 | 0.0482 | 0.0501 | 0.0506 |
| twitter | PropagationAnalysisSequenceJointModel | 0.1288 | 0.0044 | 0.0111 | 0.0278 | 0.0008 | 0.0011 | 0.0013 |
| memetracker | MINDS | 0.0668 | 0.1357 | 0.2566 | 0.3319 | 0.0863 | 0.0918 | 0.0928 |
| memetracker | PropagationAnalysisSequenceJointModel | 0.1271 | 0.0289 | 0.0489 | 0.1056 | 0.0088 | 0.0096 | 0.0103 |

### 5.2 Better-direction delta

`MSLE` 越低越好，因此 delta = `MINDS - system`。Hits/MAP 越高越好，因此 delta = `system - MINDS`。

| dataset | metric | MINDS | system | better-direction delta | winner |
|---|---|---:|---:|---:|---|
| douban | msle | 0.0632 | 0.1063 | -0.0431 | MINDS |
| douban | hits@10 | 0.1535 | 0.0089 | -0.1446 | MINDS |
| douban | hits@50 | 0.2140 | 0.0256 | -0.1885 | MINDS |
| douban | hits@100 | 0.2723 | 0.0522 | -0.2200 | MINDS |
| douban | map@10 | 0.0802 | 0.0035 | -0.0767 | MINDS |
| douban | map@50 | 0.0827 | 0.0041 | -0.0787 | MINDS |
| douban | map@100 | 0.0836 | 0.0044 | -0.0792 | MINDS |
| twitter | msle | 0.2733 | 0.1288 | 0.1445 | system |
| twitter | hits@10 | 0.0569 | 0.0044 | -0.0524 | MINDS |
| twitter | hits@50 | 0.1047 | 0.0111 | -0.0936 | MINDS |
| twitter | hits@100 | 0.1414 | 0.0278 | -0.1136 | MINDS |
| twitter | map@10 | 0.0482 | 0.0008 | -0.0473 | MINDS |
| twitter | map@50 | 0.0501 | 0.0011 | -0.0490 | MINDS |
| twitter | map@100 | 0.0506 | 0.0013 | -0.0493 | MINDS |
| memetracker | msle | 0.0668 | 0.1271 | -0.0604 | MINDS |
| memetracker | hits@10 | 0.1357 | 0.0289 | -0.1068 | MINDS |
| memetracker | hits@50 | 0.2566 | 0.0489 | -0.2077 | MINDS |
| memetracker | hits@100 | 0.3319 | 0.1056 | -0.2263 | MINDS |
| memetracker | map@10 | 0.0863 | 0.0088 | -0.0775 | MINDS |
| memetracker | map@50 | 0.0918 | 0.0096 | -0.0822 | MINDS |
| memetracker | map@100 | 0.0928 | 0.0103 | -0.0825 | MINDS |

结论：系统方法只在 Twitter 的 macro MSLE 上优于 MINDS，其余公共 micro ranking 指标均落后。该结果不支持声明系统方法整体优于 MINDS。

### 5.3 系统方法自身补充指标

这些指标是系统模型额外输出，不与 MINDS 直接比较。

| dataset | MSLE lower better | MAE lower better | RMSE lower better | MAPE% lower better | sMAPE% lower better | Direction Acc higher better | Trend MAE lower better | Trend RMSE lower better | MRR higher better | NDCG@10 higher better | Candidate Recall higher better | Soft Consistency higher better |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| douban | 0.1063 | 5.8337 | 16.4371 | 16.3991 | 16.7374 | 1.0000 | 217.3037 | 282.0211 | 0.0055 | 0.0048 | 0.9233 | 0.0026 |
| twitter | 0.1288 | 6.0093 | 14.8247 | 17.9156 | 18.5984 | 1.0000 | 174.1331 | 204.7176 | 0.0021 | 0.0017 | 0.9233 | 0.0022 |
| memetracker | 0.1271 | 2.4195 | 4.6033 | 19.1682 | 18.3816 | 1.0000 | 51.8403 | 52.7581 | 0.0123 | 0.0135 | 0.8367 | 0.0073 |

解释：

| 现象 | 判断 |
|---|---|
| Direction Acc 全为 1.0 | 说明这些采样级联中增长方向容易判定，不能单独证明规模预测强 |
| Trend MAE/RMSE 偏大 | 说明连续趋势头可运行，但趋势点误差仍大 |
| Candidate Recall 高但 Hits/MAP 低 | 候选覆盖不是主要瓶颈，排序能力和候选语义仍弱 |
| Twitter macro MSLE 优于 MINDS | 可能与 Twitter checkpoint/训练分布更接近有关，但 micro 指标仍落后，不能证明整体更好 |

## 6. 2026-08-10 新增 smoke 实验

本轮只用于验证当前本机代码、CUDA、数据和 MINDS adapter 可以跑通，不作为正式模型结论。

运行命令：

```powershell
cd G:\CISCN\CogGuard\subsystems\cogguard_dev
python -u -m benchmark.kt2_minds_comparison `
  --datasets douban,twitter,memetracker `
  --seeds 42 `
  --forest_data_root G:\CISCN\dataset\forest-data `
  --minds_repo G:\CISCN\dataset\MINDS `
  --max_minds_cascades 50 `
  --minds_epochs 1 `
  --minds_batch_size 8 `
  --minds_emb_dim 32 `
  --minds_max_seq_length 100 `
  --minds_reproduction_level public_code_adapter `
  --kt2_epochs 1 `
  --kt2_batch_size 16 `
  --kt2_hidden_dim 32 `
  --kt2_max_train_cascades 50 `
  --kt2_max_test_cascades 30 `
  --kt2_max_sequence_len 32 `
  --kt2_obs_ratios 0.3 `
  --kt2_trend_steps 4 `
  --kt2_negative_samples 16 `
  --kt2_rollout_steps 3 `
  --kt2_max_eval_cascades 30 `
  --out benchmark\propagation_prediction_research_line_smoke_20260810_valid.json `
  --config_id propagation-prediction-research-line-smoke-20260810-valid `
  --device cuda `
  --timeout 900
```

输出文件：

```text
G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\propagation_prediction_research_line_smoke_20260810_valid.json
G:\CISCN\CogGuard\subsystems\cogguard_dev\benchmark\propagation_prediction_research_line_smoke_20260810_valid.md
```

运行结果：

| 项 | 值 |
|---|---|
| status | `ok` |
| evidence_level | `preflight` |
| full_validation_passed | `false` |
| overall_verdict | `does_not_support_kt2_improvement` |
| elapsed_s | `49.7` |

Smoke 公共指标：

| dataset | MINDS MSLE lower better | system MSLE lower better | MINDS Hits@50 higher better | system Hits@50 higher better | MINDS MAP@50 higher better | system MAP@50 higher better | verdict |
|---|---:|---:|---:|---:|---:|---:|---|
| douban | 18.4414 | 0.2192 | 0.0467 | 0.0333 | 0.0018 | 0.0008 | does_not_support_kt2_improvement |
| twitter | 7.3997 | 0.2252 | 0.0000 | 0.0333 | 0.0000 | 0.0014 | supports_kt2_improvement |
| memetracker | 11.6400 | 0.1345 | 0.1224 | 0.0667 | 0.0046 | 0.0026 | does_not_support_kt2_improvement |

Smoke 结论：当前流水线可以执行，系统方法和 MINDS adapter 都可跑通。但由于只有 1 seed、1 epoch、小样本上限，不能替代 3 seed sample，更不能替代 full validation。

## 7. 综合判断

当前系统传播预测已经实现：

| 能力 | 是否实现 | 证据 |
|---|---|---|
| 当前事件前缀适配 | 已实现 | `event_adapter.py` 构造 observed prefix 和候选映射 |
| Twitter checkpoint 加载 | 已实现 | system README 记录 checkpoint、SHA-256 和 runtime |
| Macro 最终规模预测 | 已实现 | 5 epoch sample 中输出 MSLE/MAE/RMSE |
| Macro 趋势曲线 | 已实现 | 输出 `trend_points`，并有 `trend_mae/trend_rmse` |
| Micro 下一跳排序 | 已实现 | 输出 Hits/MAP/MRR/NDCG 和 Top-K 用户 |
| 无启发式 fallback 的公开路径 | 已收口 | checkpoint 或数据不可用时返回 unavailable/abstain |
| 与 MINDS 可训练 baseline 对比 | 已有 preflight 证据 | 3 数据集、3 seed、5 epoch，但 cascade 采样，非 full validation |
| 开放世界新用户激活 | 未完成 | 当前主要是已知用户再激活研判 |
| 区间校准 | 未完成 | `calibration_status=unavailable` |
| TGB-style 负采样 | 未完成 | 尚未分 random/historical/inductive negatives |

结论必须谨慎表述为：

```text
系统已具备传播趋势预测和下一跳研判的可运行模型链路。
在本地 FOREST Douban/Twitter/Memetracker 采样实验中，系统方法不支持整体优于 MINDS。
当前最稳定的正向证据是 Twitter 上的 macro MSLE 改善。
当前最大短板是 micro 下一跳排序显著弱于 MINDS，并且开放世界新用户预测和区间校准尚未完成。
```

## 8. 后续方法论优化计划

### 8.1 短期：补齐严格评测

| 工作 | 做法 | 支撑 |
|---|---|---|
| rolling backtest | 对每条级联按 `obs_ratio=0.1/0.3/0.5` 构造时间回放，不读取未来尾部 | TGB / DyGLib |
| 负采样分层 | 分别报告 random、historical、inductive negatives | TGB |
| 候选覆盖仪表 | 报告 mapped users、unmapped buckets、candidate recall、future injection audit | TGB / CAW |
| 多 seed full validation | 取消 cascade cap，至少 3 datasets、3 seeds、5 epochs | 当前 comparison script 的 full-run gate |

### 8.2 中期：强化 micro head

| 工作 | 做法 | 支撑 |
|---|---|---|
| DyGFormer micro head | 用历史一跳交互、邻居共现编码和 Transformer patching 替换简单 decoder | DyGFormer / DyGLib |
| TGN event stream | 把帖子、评论、回复、共享对象互动建成 timed events，用 memory 更新节点状态 | TGN |
| CAW inductive candidate | 对未参与当前事件但在历史图中可达的用户构造匿名 walk 表示 | CAW |
| identity registry | 建立 `bucket -> user_id` 稳定注册表，报告冲突和无法映射用户 | 系统工程要求 |

### 8.3 中期：强化 macro trend

| 工作 | 做法 | 支撑 |
|---|---|---|
| Neural ODE trend head | 把 Euler-style decoder 升级为可学习连续时间动力系统 | CasFT / GODEN |
| diffusion trend generator | 对未来增长轨迹做多样性生成，而不是单条 deterministic curve | CasFT |
| hierarchy-aware cascade encoder | 对树状级联引入双曲或层次结构表示 | H-Diffu / RotDiff |

### 8.4 长期：校准和部署稳定性

| 工作 | 做法 | 支撑 |
|---|---|---|
| adaptive conformal interval | 在验证集和在线回放中用残差校准趋势区间 | ACI |
| test-time adaptation | 对跨事件、跨平台漂移做实例级自监督适配 | Ghidorah / T3MAL |
| method card | 前端/接口展示 checkpoint、训练数据、候选协议、校准状态、适用边界 | TGB-style benchmark governance |

## 9. 当前不应做出的结论

以下说法目前不严谨：

```text
系统方法已经超过 MINDS。
系统已经复现 CasFT。
系统已经具备开放世界下一跳新用户预测。
趋势区间已经是置信区间。
Memetracker 结果可以证明社交图传播预测能力。
```

可以做出的结论是：

```text
系统方法已经把 MINDS 式多尺度主干、FOREST 式软耦合思想和 CasFT 式连续趋势输出组织成可训练、可部署的传播预测链路。
它已经能在本地 Douban/Twitter/Memetracker 上运行，并可与 MINDS 做同源采样对比。
当前实验显示其 macro 在 Twitter 上有优势，但 micro 排序整体落后，需要优先进行动态图 micro head、归纳式候选和严格负采样协议优化。
```
