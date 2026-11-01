# 传播监控核心功能：复现实验报告

> 统一入口：KT2 当前需求、状态标签与验收标准以 `../KT2_REQUIREMENTS.md` 为准；本文仅记录复现实验、数据协议、指标和命令证据。
> 状态快照：当前 CasFT、DyGFormer/DyGLib 与 TGN 均只能声明为 `frontier_reproduction_small_run`；`benchmark/KT2_COMPLETION_GATE.md` 仍为 `incomplete`，唯一 critical 开放项是 `role_evidence/manual_review_records`。

## 1. 文献复现说明

### 1.1 当前复现定位

本报告记录当前可运行 baseline、公开代码 adapter、protocol proxy 和前沿仓库数据适配入口。它不表示 KT2 前沿复现已经完成，也不设置唯一主复现模型。HyperIDP 作为多尺度参考，CasFT、DyGFormer/DyGLib 与 TGN 作为下一阶段前沿复现目标。

当前新增的前沿复现准备状态是：外部仓库已统一 clone 到 `G:\CISCN\CogGuard\subsystems\kt2_repos`，benchmark 已能导出 CasFT `dataset.txt` 与 DyGLib/TGN temporal edge stream；CasFT、DyGFormer/DyGLib 与 TGN 均已完成上游 small-run，并记录为 `frontier_reproduction_small_run`。CasFT 当前是 500 cascades / 1 epoch / seed=0 / CPU Windows shim；DyGFormer/DyGLib 与 TGN 当前是 20 cascades / 1 epoch / seed=0 / num_runs=3 的重复 small-run。这里的 small-run 都不是多数据多随机种子 full-run，也不能写成产品级最终模型。

当前覆盖范围：
- 多尺度任务定义：宏观级联最终规模预测 + 微观下一受影响用户预测。
- 数据协议：Christianity、Android、Douban 数据集上的时间序列划分。
- 评价指标：MSLE（宏观）、Hits@K / MAP@K（微观）。
- HyperIDP proxy 覆盖：temporal hypergraph neural architecture + collaborative-adversarial learning 的协议级近似，不是原论文架构复现。
- 全量实验验证审计：`python -m benchmark.experiment_audit` 生成 `benchmark/KT2_EXPERIMENT_AUDIT.json/.md`，当前总状态为 `incomplete`。

### 1.2 复现边界

HyperIDP 论文 PDF 标注代码地址为 `https://github.com/HowieHsu0126/HyperIDP`，但截至本报告日期（2026-06-26）公开访问返回 GitHub 404，`git ls-remote` 返回 `Repository not found`。GitHub 可访问性可能随时间变化；若后续重新评估 HyperIDP，应先复验该仓库状态并更新时间戳。因此当前仅采用 **protocol-level proxy**：

1. 复现其任务协议（观测窗口定义、无泄漏划分、联合宏观/微观评价）
2. 使用 MINDS（AAAI 2024）和 FOREST（IJCAI 2019）的公开代码作为可运行统一 baseline
3. 对照 HyperIDP 论文报告的指标数值作为参考，不声明复现完成
4. 不复现 HyperIDP 的 architecture search 模块（缺少代码细节）

### 1.3 已运行的可复现 baseline

| 模型 | 来源 | 代码状态 | 本地运行状态 |
|------|------|----------|-------------|
| MINDS | AAAI 2024, github.com/cspjiao/MINDS | 公开可用 | 已成功运行（christianity, 30 epochs, best valid MAP@100 epoch=29） |
| FOREST | IJCAI 2019, github.com/yangchengbupt/FOREST | 公开可用 | 已成功运行（douban, 30 epochs, best valid MAP@100 epoch=10, sequence-only） |
| RF_Baseline | scikit-learn RandomForestRegressor | 自建 | 已成功运行（douban） |
| TemporalSizeBaseline | 固定时间窗中位数增长倍数 | 自建 | 已成功运行（douban, 7-day observation window） |
| LR_EdgeClassifier | scikit-learn LogisticRegression | 自建 | 已成功运行（douban observed-candidate protocol） |
| ProspectiveHeuristic | 非学习时间/中心性启发式 | 自建 | 已成功运行（douban prospective next-user protocol） |
| ProspectiveRanker | scikit-learn LogisticRegression 排序器 | 自建 | 已成功运行（douban prospective learned ranker protocol） |
| HyperIDPProtocolProxy | temporal coactivation hyperedge proxy + RF/LR | 自建 | 已成功运行（douban protocol-level macro/micro proxy） |
| HyperIDPAdversarialProxy | shared MLP + macro/micro heads + gradient reversal task adversary | 自建 | 已成功运行（douban protocol-level adversarial proxy） |
| CasFT | AAAI 2025, github.com/UM-Data-Intelligence-Lab/CasFT | 公开可用，本地 HEAD `ebb7e8e` | 已完成 500 cascades / 1 epoch / seed=0 / CPU Windows shim small-run；结果见 `benchmark/casft_external_attempt.json`，但不是多随机种子 full-run |
| KT2JointModel 原组件融合 small matrix | MINDS + FOREST + CasFT 子路径 | 自建联合模型 + 公开仓库子组件 | 已接入 MINDS `DynamicCasHGNN/Fusion/SharedLSTM` 与 `Module.forward`、FOREST `RNNModel/RRModel` CE/RL auxiliary、CasFT `GaussianDiffusion_ST/ST_Diffusion` 与 `CombinedSpatiotemporalModel5/NeuralPointProcess`；并将 MINDS macro 输出、FOREST RRModel sampled EOS size、CasFT spatiotemporal size 输出作为 teacher signal 对齐 KT2 macro head。当前 `benchmark/kt2_original_fusion_experiment_small_matrix.json` 覆盖 Douban/Twitter/Memetracker × seeds 42/43/44 共 9 行，`matrix_coverage.coverage_ratio=1.0`、`original_subpath_audit.all_original_subpaths_passed=true`、`all_alignment_losses_recorded=true`；仍不是三篇论文原数据协议、完整训练脚本和多种子 full-run reproduction |
| KT2JointModel 观测窗口 sweep smoke | MINDS + FOREST + CasFT 子路径 | 自建联合模型 + 公开仓库子组件 | `benchmark/kt2_original_fusion_experiment_obs_sweep_smoke.json` 已验证 `--obs_ratios 0.3,0.5`、`--config_id obs-sweep-smoke` 与 `--resume` 可共同工作；当前覆盖 Douban / seed 42 / 2 个观测窗口，`matrix_coverage.coverage_ratio=1.0`。这只证明多观测窗口复现实验基础设施可运行，不是论文 full-run |
| DyGFormer/DyGLib | NeurIPS 2023, github.com/yule-BUAA/DyGLib | 公开可用，本地 HEAD `3aacc36` | 已完成 20 cascades / 1 epoch / 3 次重复 small-run；结果见 `benchmark/dyglib_external_attempt.json`，但不是多随机种子 full-run |
| TGN | twitter-research/tgn | 公开可用，本地 HEAD `d55bbe6` | 已完成 20 cascades / 1 epoch / 3 次重复 small-run；结果见 `benchmark/tgn_external_attempt.json`，但不是多随机种子 full-run |

---

## 2. 数据集适配报告

### 2.1 FOREST 数据集

| 数据集 | 训练级联数 | 验证级联数 | 测试级联数 | 平均长度 | 社交边数 | DeepWalk嵌入 |
|--------|-----------|-----------|-----------|---------|---------|-------------|
| twitter | 2768 | 347 | 346 | 39.38 | 619,262 | MISSING |
| douban | 8529 | 1067 | 1066 | 32.03 | 758,310 | MISSING |
| memetracker | 10131 | 1266 | 1266 | 16.10 | MISSING | MISSING |

说明：
- DeepWalk 嵌入缺失：FOREST 的 network 模式不可用，仅能以序列模式运行
- 文本可用性：无文本内容

### 2.2 MINDS 数据集

| 数据集 | 总级联数 | 社交边数 | 划分方式 |
|--------|---------|---------|---------|
| christianity | 589 | 35,624 | 80%/10%/10% (train/valid/test) |
| douban | — | — | 待验证 |
| android | — | — | 待验证 |

### 2.3 数据集与任务覆盖

| 数据集 | 宏观规模预测 | 微观下一用户预测 | 适用框架 |
|--------|-------------|----------------|---------|
| christianity | ✓ (MSLE) | ✓ (Hits@K, MAP@K) | MINDS |
| douban | ✓ (MSLE via RF/Temporal) | ✓ (Hits@K, MAP@K) | FOREST, RF/Temporal/LR/Prospective；MINDS 数据待获取 |
| twitter | — | ✓ (Hits@K, MAP@K) | FOREST |

---

## 3. 无泄漏划分协议

### 3.1 规模预测（宏观）

| 项目 | 协议 | 泄漏风险评估 |
|------|------|-------------|
| 观测窗口 | 级联前 10% 的传播序列作为输入特征 | 无泄漏：仅使用早期观测 |
| 标签定义 | 级联最终参与人数 | 无泄漏：标签为未来完整传播规模 |
| 划分方式（RF） | FOREST 原始 cascade.txt / cascadetest.txt 划分 | 低风险：原始划分已分离；但按最终长度比例取观测窗会弱化真实早期预测含义 |
| 划分方式（TemporalSizeBaseline） | FOREST 原始 train/test，固定 7 天时间窗，仅用训练集估计中位数增长倍数 | 无测试未来输入；作为 naive/moving-average 类时间外推 baseline |
| 划分方式（MINDS） | 80%/10%/10% 随机划分 | 中等风险：随机划分可能存在同期级联间渗透 |

### 3.2 下一用户预测（微观）

| 项目 | 协议 | 泄漏风险评估 |
|------|------|-------------|
| 输入 | 级联中已观测的用户序列前缀 | 无泄漏：teacher forcing 只使用已知前缀 |
| 标签 | 序列中的下一个用户 | 无泄漏：逐步预测下一位 |
| 候选集 | 全体用户空间 + previous user mask | 无泄漏：mask 不引入未来信息 |
| 划分方式 | 独立的训练/验证/测试级联文件 | 无泄漏：测试级联不参与训练 |
| LR 候选集 | 默认仅使用观测窗内已激活用户作为候选 | 候选集无未来节点注入；额外报告 Candidate Recall |
| LR 旧口径 | 可选 `--lr_inject_true_parent` 复刻旧离线设置 | 高泄漏风险：会把真实 parent 注入候选集，仅可作为反例或历史对照 |
| ProspectiveHeuristic 候选集 | 训练集全局热度用户 + 观测前缀社交邻居 + 训练集转移统计 | 无未来节点注入；先报告 full candidate recall，再报告 Top-K 排序质量 |
| ProspectiveRanker 候选集 | 与 ProspectiveHeuristic 同源候选，训练时只对候选打未来窗口标签 | 测试无未来节点注入；验证可学习排序是否优于非学习启发式 |

### 3.3 已知泄漏风险点

1. **MINDS 随机划分**：未严格按时间排序，同一时间段的级联可能分布在训练集和测试集中
2. **FOREST network 模式缺失**：DeepWalk 基于全图生成，若包含测试级联边则存在泄漏。当前该模式已禁用
3. **全局社交图**：MINDS/FOREST 均使用静态全图作为先验知识，与原论文一致

---

## 4. Baseline 对比表

### 4.1 微观下一用户预测

| 模型 | 数据集 | Candidate Recall | Hits@100 | MAP@100 | MRR | NDCG@100 | Epochs |
|------|--------|------------------|----------|---------|-----|----------|--------|
| LR_EdgeClassifier | douban | 0.0884 | 0.0884 | 0.0884 | 0.0884 | 0.0884 | n/a |
| ProspectiveHeuristic | douban | 0.8773 | 0.3080 | 0.0831 | 0.3201 | 0.2101 | n/a |
| ProspectiveRanker | douban | 0.8111 | 0.3083 | 0.0838 | 0.3225 | 0.2109 | n/a |
| HyperIDPProtocolProxy | douban | 0.8131 | 0.3088 | 0.0836 | 0.3221 | 0.2109 | n/a |
| HyperIDPAdversarialProxy | douban | 0.8131 | 0.3075 | 0.0826 | 0.3158 | 0.2094 | 5 |
| MINDS | christianity | — | 0.5848 | 0.1895 | — | — | 30 |
| FOREST | douban | — | 0.3289 | 0.0868 | — | — | 30 |
| HyperIDP (论文) | christianity | — | 0.5187 | 0.1914 | — | — | 30 |
| HyperIDP (论文) | douban | — | 0.3052 | 0.0998 | — | — | 30 |

注：
- MINDS 与 FOREST 均已完成 30 epochs 训练，并使用验证集 MAP@100 选择 epoch，最终测试集只评估一次。
- FOREST douban 30 epochs 最佳验证点为 epoch 10，测试 Hits@100=0.3289、MAP@100=0.0868；由于 DeepWalk 嵌入缺失，network 模式关闭，仅代表 sequence-only 复现结果。训练日志全程打印 `loss: nan`，但 validation/test Hits/MAP 正常产出，因此该结果可作为运行记录，不能视为与原论文完全同配置。
- LR_EdgeClassifier 默认不注入未来真实 parent，`candidate_recall_observed=0.0884`，因此 Hits/MAP 同时反映候选覆盖瓶颈；其 AUC=0.9911、AP=0.4043 仍属于离线候选边分类指标，不能单独代表线上下一节点预测能力。
- ProspectiveHeuristic 是严格前瞻候选协议：不使用未来真实节点，候选池覆盖 0.8773，Top-100 Hits 为 0.3080、MRR 为 0.3201、NDCG@100 为 0.2101。
- ProspectiveRanker 在较小候选池设置下覆盖 0.8111，Top-100 Hits 为 0.3083、MRR 为 0.3225、NDCG@100 为 0.2109，排序略优于启发式但提升有限，说明下一步应增强特征或换用 GNN/temporal graph 模型。
- HyperIDPProtocolProxy 不是 HyperIDP 原论文架构，只用训练集时间共激活构造 hyperedge proxy，在同一候选协议下验证 macro/micro 统一输出链路可运行。
- HyperIDPAdversarialProxy 在同一特征和候选协议上增加 shared encoder、macro/micro heads 和 gradient-reversal task adversary；它验证 collaborative-adversarial 训练支架可运行，但仍不是论文 NAS 架构。

### 4.2 宏观级联规模预测

| 模型 | 数据集 | MSLE | MAE | Direction Acc. | 说明 |
|------|--------|------|-----|----------------|------|
| TemporalSizeBaseline | douban | 1.8181 | 25.6510 | 0.9972 | 固定 7 天观测窗 + 训练集中位数增长倍数 |
| RF_Baseline | douban | 0.4961 | 5.2125 | — | 观测窗口为级联前 10% 序列，作为强传统监督 baseline |
| HyperIDPProtocolProxy | douban | 0.0228 | 2.0966 | — | 观测窗口为级联前 30% 序列；用于 protocol-level proxy，不可与固定时间窗 baseline 直接等价比较 |
| HyperIDPAdversarialProxy | douban | 0.0293 | 4.3287 | 1.0000 | 观测窗口为级联前 30% 序列；5 epochs adversarial proxy |
| CasFT | douban | 10.9604 | 2.7008 | — | 500 cascades / 1 epoch / seed=0 / CPU Windows shim small-run；另有 `smape=0.5824`、`pcc=-0.4065`、`r2=-0.6614` |
| MINDS | christianity | 0.0807 | — | — | 30 epochs，best valid MAP@100 epoch=29，test-only final evaluation |
| HyperIDP (论文) | christianity | 0.2836 | — | — | 论文报告值 |
| HyperIDP (论文) | douban | 0.3218 | — | — | 论文报告值 |

### 4.3 观测窗口敏感性

| 模型 | 数据集 | 观测比例 | MSLE | MAE | Candidate Recall | Hits@100 | MAP@100 | MRR |
|------|--------|----------|------|-----|------------------|----------|---------|-----|
| HyperIDPProtocolProxy | douban | 0.1 | 0.3509 | 4.9259 | 0.8038 | 0.3085 | 0.0872 | 0.3344 |
| HyperIDPProtocolProxy | douban | 0.3 | 0.0228 | 2.0966 | 0.8131 | 0.3088 | 0.0836 | 0.3221 |
| HyperIDPProtocolProxy | douban | 0.5 | 0.0057 | 1.9467 | 0.8237 | 0.3078 | 0.0768 | 0.2672 |

注：
- 该曲线记录在 `benchmark/observation_sensitivity.json`。
- 随观测比例提高，宏观规模误差显著下降；微观 Top-100 Hits 基本稳定，MAP/MRR 在更晚观测下反而略降，说明当前候选排序对“剩余未来用户”的排名仍需更强 temporal graph/NAS 模型增强。

### 4.4 模型能力矩阵

| 模型 | 微观预测 | 宏观预测 | 统一模型 | 代码可用 | 运行验证 |
|------|---------|---------|---------|---------|---------|
| HyperIDP | ✓ | ✓ | ✓ | ✗ | ✗ (protocol-level) |
| HyperIDPProtocolProxy | ✓ | ✓ | ✓ (proxy) | ✓ | ✓ |
| HyperIDPAdversarialProxy | ✓ | ✓ | ✓ (proxy) | ✓ | ✓ |
| MINDS | ✓ | ✓ | ✓ | ✓ | ✓ |
| FOREST | ✓ | ✗ | ✗ | ✓ | ✓ |
| RF_Baseline | ✗ | ✓ | ✗ | ✓ | ✓ |
| TemporalSizeBaseline | ✗ | ✓ | ✗ | ✓ | ✓ |
| LR_EdgeClassifier | ✓ (offline edge ranking) | ✗ | ✗ | ✓ | ✓ |
| ProspectiveHeuristic | ✓ (prospective non-learning baseline) | ✗ | ✗ | ✓ | ✓ |
| ProspectiveRanker | ✓ (prospective learned ranker) | ✗ | ✗ | ✓ | ✓ |

---

## 5. 结论与推荐路线

### 5.1 判断

**HyperIDP 当前阶段不适合直接落地，也不再作为唯一主复现目标；它只作为多尺度论文参考与 proxy baseline。**

理由：
1. HyperIDP 可作为 macro/micro 多尺度协议参考，但不能锁定 KT2 功能路线。
2. 规模预测前沿复现优先接入 CasFT；下一跳预测前沿复现优先接入 DyGFormer/DyGLib 或 TGN。
3. 本地已补 HyperIDPProtocolProxy 和 HyperIDPAdversarialProxy，证明 protocol-level macro/micro 输出链路与 adversarial multi-task 训练支架可运行，但还不是 HyperIDP 原架构。
4. 本地 MINDS Christianity 数据已验证可运行；douban/android 仍需获取后补齐。

### 5.2 推荐路线

| 阶段 | 行动 | 产出 |
|------|------|------|
| 当前 | 以 MINDS Christianity 与 FOREST douban 为可运行统一 baseline，完成 30 epochs 对齐论文指标 | 完整训练结果 + 性能差距量化 |
| 短期 | 扩展已跑通的 CasFT、DyGFormer/DyGLib 与 TGN small-run 至多种子/多数据集；保留 HyperIDP proxy 作为参考 | 产出上游训练日志、随机种子、指标 JSON，并将对应状态从 small-run 升级为可比较的 full-run 候选证据 |
| 中期 | 若 HyperIDP 官方仓库可公开访问，验证并作为候选 baseline 接入 | 完整复现或证伪 |
| 落地 | 将验证后的最优模型封装为 CogGuard 传播预测 API | 系统集成 |

### 5.3 当前瓶颈

1. **训练成本与环境**：FOREST douban CPU 30 epochs 已完成一次，耗时约 2.5 小时；CasFT 已完成 500 cascades / 1 epoch / seed=0 / CPU Windows shim small-run；KT2JointModel 已完成真实 CasFT `CombinedSpatiotemporalModel5/NeuralPointProcess` auxiliary smoke、FOREST `RRModel` rollout smoke，以及 Douban/Twitter/Memetracker × seeds 42/43/44 的 original-subpath fusion small matrix。该矩阵已支持 `--resume`、`--max_runs`、`--obs_ratios` 与 `--config_id`，并报告 `matrix_coverage`、original subpath audit 和 teacher alignment audit；下一步瓶颈是按原论文数据协议、更多 epoch/观测窗口和官方 baseline 指标扩展，而不是 small-run 可运行性
2. **DeepWalk 嵌入缺失**：FOREST network 模式无法启用，当前结果为 sequence-only
3. **数据集覆盖**：本地 MINDS 仓库仅有 Christianity；douban/android 需获取数据后进一步验证
4. **HyperIDP 复现深度**：已有 protocol/adversarial proxy，但从论文复现 NAS 模块工程量仍大，MINDS/FOREST 30 epochs 已可作为当前统一 baseline 参照
5. **全量验证审计**：`KT2_EXPERIMENT_AUDIT` 当前标记规模预测 `passed`、下一跳预测 `passed`、角色证据 `partial`、前端协议 `passed`；因此不得声明 KT2 全量实验验证完成，除非人工抽查记录补齐并通过

---

## 附录：实验环境与命令

**当前本机环境：**
- Windows / PowerShell，Python 来自 `D:\Anaconda\python.exe`
- GPU：RTX 4060 Laptop 8GB，可承诺 small-run，不承诺完整长训
- 外部仓库目录：`G:\CISCN\CogGuard\subsystems\kt2_repos`
- 数据目录：`G:\CISCN\dataset`

**运行命令：**

```bash
# 前沿仓库 export-only 状态检查（不会声明上游模型已复现）
python -m benchmark.run_benchmark \
  --models casft dyglib tgn \
  --datasets douban \
  --forest_dir G:\CISCN\CogGuard\subsystems\kt2_repos\FOREST \
  --casft_dir G:\CISCN\CogGuard\subsystems\kt2_repos\CasFT \
  --dyglib_dir G:\CISCN\CogGuard\subsystems\kt2_repos\DyGLib \
  --tgn_dir G:\CISCN\CogGuard\subsystems\kt2_repos\tgn \
  --frontier_max_cascades 100 \
  --frontier_timeout 120 \
  --output benchmark\frontier_status.json

# DyGFormer/DyGLib 上游 small-run（已完成一次）
python -m benchmark.run_benchmark \
  --models dyglib \
  --datasets douban \
  --forest_dir G:\CISCN\CogGuard\subsystems\kt2_repos\FOREST \
  --dyglib_dir G:\CISCN\CogGuard\subsystems\kt2_repos\DyGLib \
  --frontier_max_cascades 20 \
  --frontier_epochs 1 \
  --frontier_batch_size 16 \
  --frontier_gpu -1 \
  --frontier_timeout 120 \
  --run_external_frontier \
  --output benchmark\dyglib_external_attempt.json

# TGN 上游 small-run（已完成一次）
python -m benchmark.run_benchmark \
  --models tgn \
  --datasets douban \
  --forest_dir G:\CISCN\CogGuard\subsystems\kt2_repos\FOREST \
  --tgn_dir G:\CISCN\CogGuard\subsystems\kt2_repos\tgn \
  --frontier_max_cascades 20 \
  --frontier_epochs 1 \
  --frontier_batch_size 16 \
  --frontier_gpu -1 \
  --frontier_timeout 120 \
  --run_external_frontier \
  --output benchmark\tgn_external_attempt.json

# 完整 benchmark suite（需指定外部模型仓库路径）
python -m benchmark.run_benchmark \
  --models minds forest rf temporal lr heuristic ranker hyperidp_proxy hyperidp_adv_proxy \
  --datasets douban \
  --forest_dir /path/to/FOREST \
  --minds_dir /path/to/MINDS \
  --python /path/to/torch/python \
  --epochs 30

# 快速 sanity run（不重复 FOREST 长任务）
python -m benchmark.run_benchmark \
  --models temporal heuristic ranker lr rf hyperidp_proxy hyperidp_adv_proxy \
  --datasets douban \
  --forest_dir /path/to/FOREST \
  --python /path/to/torch/python \
  --heuristic_max_future_per_cascade 20 \
  --lr_max_future_per_cascade 20

python -m benchmark.run_benchmark \
  --models minds \
  --datasets christianity \
  --minds_dir /path/to/MINDS \
  --python /path/to/torch/python \
  --epochs 30

python -m benchmark.run_benchmark \
  --models forest \
  --datasets douban \
  --forest_dir /path/to/FOREST \
  --python /path/to/torch/python \
  --epochs 30

# 查看帮助
python -m benchmark.run_benchmark --help

# 全量实验验证审计（不运行长训练，只汇总当前证据和缺口）
python -m benchmark.experiment_audit
```

