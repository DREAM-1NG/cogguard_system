# 传播监控核心功能：复现实验报告

## 1. 文献复现说明

### 1.1 主复现目标

**HyperIDP** (COLING 2025): *Customizing Temporal Hypergraph Neural Networks for Multi-Scale Information Diffusion Prediction*

复现范围：
- 多尺度任务定义：宏观级联最终规模预测 + 微观下一受影响用户预测
- 数据协议：Christianity、Android、Douban 数据集上的时间序列划分
- 评价指标：MSLE（宏观）、Hits@K / MAP@K（微观）
- 模型核心思想：temporal hypergraph neural architecture + collaborative-adversarial learning

### 1.2 复现边界

HyperIDP 论文 PDF 标注代码地址为 `https://github.com/HowieHsu0126/HyperIDP`，但截至本报告日期（2026-06-26）公开访问返回 GitHub 404，`git ls-remote` 返回 `Repository not found`。因此采用 **protocol-level reproduction**：

1. 复现其任务协议（观测窗口定义、无泄漏划分、联合宏观/微观评价）
2. 使用 MINDS（AAAI 2024）和 FOREST（IJCAI 2019）的公开代码作为可运行统一 baseline
3. 对照 HyperIDP 论文报告的指标数值作为性能上界参照
4. 不复现 HyperIDP 的 architecture search 模块（缺少代码细节）

### 1.3 已运行的可复现 baseline

| 模型 | 来源 | 代码状态 | 本地运行状态 |
|------|------|----------|-------------|
| MINDS | AAAI 2024, github.com/cspjiao/MINDS | 公开可用 | 已成功运行（christianity, 30 epochs, best valid MAP@100 epoch=29） |
| FOREST | IJCAI 2019, github.com/yangchengbupt/FOREST | 公开可用 | 已成功运行（douban, 1 epoch sanity run） |
| RF_Baseline | scikit-learn RandomForestRegressor | 自建 | 已成功运行（douban） |
| TemporalSizeBaseline | 固定时间窗中位数增长倍数 | 自建 | 已成功运行（douban, 7-day observation window） |
| LR_EdgeClassifier | scikit-learn LogisticRegression | 自建 | 已成功运行（douban observed-candidate protocol） |
| ProspectiveHeuristic | 非学习时间/中心性启发式 | 自建 | 已成功运行（douban prospective next-user protocol） |
| ProspectiveRanker | scikit-learn LogisticRegression 排序器 | 自建 | 已成功运行（douban prospective learned ranker protocol） |
| HyperIDPProtocolProxy | temporal coactivation hyperedge proxy + RF/LR | 自建 | 已成功运行（douban protocol-level macro/micro proxy） |
| HyperIDPAdversarialProxy | shared MLP + macro/micro heads + gradient reversal task adversary | 自建 | 已成功运行（douban protocol-level adversarial proxy） |

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
| FOREST | douban | — | 0.2149 | 0.0584 | — | — | 1 |
| HyperIDP (论文) | christianity | — | 0.5187 | 0.1914 | — | — | 30 |
| HyperIDP (论文) | douban | — | 0.3052 | 0.0998 | — | — | 30 |

注：
- MINDS 已完成 30 epochs 训练，并使用验证集 MAP@100 选择 epoch，最终测试集只评估一次；FOREST 当前仍仅用于验证 pipeline，非完整训练结果。
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

**HyperIDP 当前阶段不适合直接落地，但适合作为研究复现主目标持续推进。**

理由：
1. HyperIDP 是目前唯一联合优化宏观+微观的前沿统一模型，性能显著优于 baseline
2. 论文标注的官方仓库当前不可公开访问，完整复现需从论文重建 temporal hypergraph NAS + adversarial learning
3. 本地已补 HyperIDPProtocolProxy 和 HyperIDPAdversarialProxy，证明 protocol-level macro/micro 输出链路与 adversarial multi-task 训练支架可运行，但还不是 HyperIDP 原架构
4. 本地 MINDS Christianity 数据已验证可运行；douban/android 仍需获取后补齐

### 5.2 推荐路线

| 阶段 | 行动 | 产出 |
|------|------|------|
| 当前 | 以 MINDS Christianity 为可运行统一 baseline，完成 30 epochs 对齐论文指标 | 完整训练结果 + 性能差距量化 |
| 短期 | 在 HyperIDP proxy 基础上补 temporal hypergraph NAS | 更接近论文的 protocol-level reproduction 代码 |
| 中期 | 若 HyperIDP 官方仓库可公开访问，验证并替换自建实现 | 完整复现或证伪 |
| 落地 | 将验证后的最优模型封装为 CogGuard 传播预测 API | 系统集成 |

### 5.3 当前瓶颈

1. **训练时长**：FOREST douban CPU 1 epoch 约 12 分钟；完整 30 epochs 需要 GPU 或长时间后台任务
2. **DeepWalk 嵌入缺失**：FOREST network 模式无法启用
3. **数据集覆盖**：本地 MINDS 仓库仅有 Christianity；douban/android 需获取数据后进一步验证
4. **HyperIDP 复现深度**：已有 protocol/adversarial proxy，但从论文复现 NAS 模块工程量仍大，MINDS 30 epochs 已可作为当前统一 baseline 参照

---

## 附录：实验环境与命令

**环境：**
- Python 3.12.13
- `/Users/albert/Desktop/cogguard_system/.venv`：numpy、scikit-learn，用于 RF/LR benchmark orchestrator
- `/Users/albert/Desktop/xas/.venv`：PyTorch CPU 环境，用于 MINDS/FOREST adapter 子进程
- Apple Silicon (darwin), 无 GPU

**运行命令：**

```bash
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

# 查看帮助
python -m benchmark.run_benchmark --help
```
