# Propagation Analysis 完整技术方案：CascadeSwitch — 事件条件体制切换级联预测

> 状态更新（2026-08-15）：本文件保留 CascadeSwitch 的历史研究方案，不是当前系统的部署模型或正式实验记录。当前实现为 `system/research/propagation_analysis/` 中的 `PropagationSequenceJointModel`；最新 Macro/Micro 正式实验记录位于 `system/research/propagation_analysis/benchmark/formal_36x_fair_protocol_20260815.md`。

**定位**：领域时序预测研究（信息级联预测方向）
**关键技术**：LLM + 时序预测
**日期**：2026-04-28

---

## 1. 问题定义

**任务**：给定信息级联的早期观测窗口 [0, t_obs]，预测级联在 t_pred 时刻的最终规模（转发量）。

**核心瓶颈**：信息级联具有非平稳动态特性——受外生事件（KOL放大、官方回应、平台干预、叙事变异）驱动的体制转换（seeding → amplification → peak → decay）。纯统计时序模型（ARIMA/ETS）假设平稳性，在体制转换点失效；纯 LLM 数值预测不可靠（Tan et al., 2024）。

**研究假设**：将级联预测建模为体制切换问题，通过 LLM 提取外生事件后验驱动透明的体制转换，可在零训练条件下超越平稳基线。

## 2. 方法：CascadeSwitch

### 2.1 架构总览

```
观测级联 [0, t_obs]
  │
  ├──→ [时序特征提取] → volume, velocity, acceleration, burst_zscore
  │
  ├──→ [级联形态事件检测] → detected_events[] (无内容时从级联动态推断)
  │    或 [LLM 事件提取] → detected_events[] (有内容时通过 API 提取)
  │
  └──→ [体制切换预测器]
         Step 1: 事件评分向量 e ∈ R^6
         Step 2: 历史先验 b ∈ R^4
         Step 3: p(z) = softmax((W·e + b) / τ)    # 体制后验
         Step 4: ŷ(t) = Σ_z p(z) · f_z(t | history)  # 混合预测
         Step 5: σ²(t) = Σ_z p(z) · [f_z² + σ_z²] - ŷ²  # 不确定性
         → 输出: {predicted_size, direction, confidence_interval, regime_posterior, explanation}
```

### 2.2 核心机制：体制切换混合预测

**4 种传播体制及其参数化模型**（参数从观测窗口历史估计，无需训练）：

| 体制 | 模型 | 参数估计 | 直觉 |
|------|------|----------|------|
| Seeding | y(t+h) = v + β·h | β = 观测窗口平均速度 | 线性慢增长 |
| Amplification | y(t+h) = v·e^(r·h) | r = log(v_t/v_{t-3})/3 | 病毒式指数增长 |
| Peak | y(t+h) = K/(1+e^(-k(h-h₀))) | K=2v, k 从加速度估计 | 逻辑饱和 |
| Decay | y(t+h) = v·e^(-λ·h) | λ = -log(v_t/v_{t-3})/3 | 指数衰减 |

**体制后验计算**：

事件→体制评分矩阵 W ∈ R^(4×6)（手工设计，可解释）：

|  | kol_amp | official_resp | platform_int | narrative_mut | coord_burst | none |
|---|---|---|---|---|---|---|
| seeding | -1 | 0 | 0 | 0 | 0 | +2 |
| amplification | +2 | -1 | -1 | +1 | +2 | 0 |
| peak | +1 | +1 | 0 | 0 | +1 | 0 |
| decay | -1 | +2 | +2 | -1 | -1 | +1 |

```
p(z | events, history) = softmax((W · e + b) / τ)
```

其中 e 为事件置信度向量，b 为历史先验偏置（由速度/加速度/时间决定），τ=1.0。

**混合预测**：
```
ŷ(t+h) = Σ_z p(z) · f_z(t+h | history)
σ²(t+h) = Σ_z p(z) · (f_z(t+h)² + σ_z²) - ŷ(t+h)²
```

### 2.3 事件检测：两种模式

**模式 A：级联形态事件检测**（适用于公开数据集，无需内容）
- `coordinated_burst`：加速度 z-score > 2
- `kol_amplification`：单用户在 1 小时内贡献 > 10% 级联量
- `platform_intervention`：传播速率突然下降 > 50%
- `none`：无显著事件

**模式 B：LLM 事件提取**（适用于有内容的数据，如 CogGuard 系统）
- 通过 LLM API（Qwen/DeepSeek）从帖子内容中提取结构化事件
- 3 次调用多数投票，JSON schema 验证
- 降级机制：API 失败时回退到模式 A

### 2.4 贡献定位

- **主要贡献**：事件条件体制切换框架——将级联预测建模为体制切换问题，通过外生事件后验驱动透明的参数化预测，零训练、可解释
- **次要贡献**：级联形态事件检测——从级联动态中自动推断外生事件，使方法在无内容数据集上也可运行
- **非贡献**：不是新的 LLM 架构；不是新的时序模型；不是端到端训练方法

## 3. 实验设计

### 3.1 数据集

| 数据集 | 规模 | 平台 | 用途 | 是否需要额外标注 |
|--------|------|------|------|-----------------|
| Sina Weibo (DeepHawkes) | 119K 级联 | 微博 | 主实验 | 否（级联轨迹即标签） |
| CasFlow Weibo | ~120K 级联 | 微博 | 交叉验证 | 否 |
| CasFlow Twitter | ~30K 级联 | Twitter | 跨平台泛化 | 否 |
| CogGuard mock_weibo | 可控生成 | 模拟微博 | 系统集成验证 + LLM 事件提取验证 | 否 |

**任务设定**：观测窗口 t_obs ∈ {0.5h, 1h, 2h, 3h}，预测时间 t_pred ∈ {6h, 12h, 24h}。标准级联预测设定，与 DeepCas/CasFlow/CasCN 文献一致。

### 3.2 评估指标

| 指标 | 公式 | 用途 |
|------|------|------|
| MSLE | mean((log(ŷ+1) - log(y+1))²) | 级联预测标准指标（对数尺度，处理长尾） |
| MAPE | mean(\|ŷ-y\|/max(y,1)) | 相对误差 |
| Direction Accuracy | accuracy(sign(ŷ-v_obs), sign(y-v_obs)) | 方向预测准确率 |

### 3.3 基线对比

| 方法 | 类型 | 描述 |
|------|------|------|
| Naive | 统计 | 最近观测速率 × 剩余时间 |
| EWMA | 统计 | 指数加权移动平均外推 |
| Feature-Linear | 特征工程 | 手工级联特征 → 线性回归 |
| CascadeSwitch-uniform | 消融 | 均匀体制后验（无事件检测） |
| CascadeSwitch-shape | 完整 | 级联形态事件检测 + 体制切换 |

**文献基线**（引用已发表数值，不重新实现）：DeepCas, CasCN, CasFlow, VaCas, TempCas

### 3.4 实验矩阵

**实验 1：主结果**（Weibo DeepHawkes）
- 所有基线 × 所有观测窗口 × 所有预测时间
- 核心表格：MSLE 对比

**实验 2：消融——事件源**
- uniform（无事件）vs shape-only vs LLM（仅 CogGuard 数据）
- 证明事件检测的边际贡献

**实验 3：跨平台泛化**
- 在 CasFlow Twitter 上测试，不重新调参
- 证明方法的平台无关性

**实验 4：观测窗口敏感性**
- t_obs 从 0.5h 到 3h，观察性能变化曲线
- 分析体制切换在不同观测量下的稳定性

**实验 5：体制分析**
- 可视化不同级联的体制后验随时间变化
- 案例分析：体制切换点与实际传播动态的对应关系

## 4. 已实现代码

以下模块已实现并通过单元测试：

| 模块 | 路径 | 功能 |
|------|------|------|
| ts_features.py | app/core/propagation/ | 时序特征提取（小时聚合、速度、加速度、突发检测） |
| llm_context.py | app/core/propagation/ | LLM 事件提取（API 调用、JSON 验证、多数投票、mock 模式） |
| regime_model.py | app/core/propagation/ | 体制后验计算（W 矩阵、softmax）+ 4 种参数化预测 + 混合预测 |
| trend_predictor.py | app/core/propagation/ | 编排器：ts_features → events → regime → 输出 |
| propagation_legacy.py | app/core/ | 保留的源头追溯模块（580 行，MultiDiGraph + 证据链） |

**待实现**：
- `data/cascade_loader.py`：公开数据集加载器（DeepHawkes/CasFlow 格式解析）
- `eval/evaluate_cascade.py`：基准评估脚本
- `core/propagation/cascade_events.py`：级联形态事件检测（无内容模式）

## 5. 参考文献

### 核心方法论参考

[1] Gruver, J., Finzi, M., Qiu, S., & Wilson, A. G. (2023). Large Language Models Are Zero-Shot Time Series Forecasters. *NeurIPS 2023*.
https://arxiv.org/abs/2310.01728

[2] Jin, M., Wang, S., Ma, L., et al. (2024). Time-LLM: Time Series Forecasting by Reprogramming Large Language Models. *ICLR 2024*.
https://arxiv.org/abs/2310.01177

[3] Xue, H. & Salim, F. D. (2023). PromptCast: A New Prompt-based Learning Paradigm for Time Series Forecasting. *IEEE TKDE*.
https://arxiv.org/abs/2210.08964

[4] Tan, M. H., Merrill, M. A., Gupta, V., et al. (2024). Are Language Models Actually Useful for Time Series Forecasting? *NeurIPS 2024*.
https://arxiv.org/abs/2406.16964

[5] Rethinking the Role of Large Language Models in Time Series Forecasting. *arXiv 2026*.
https://arxiv.org/abs/2602.14744

### 信息级联预测

[6] Li, C., Ma, J., Guo, X., & Mei, Q. (2017). DeepCas: An End-to-end Predictor of Information Cascades. *WWW 2017*.
https://arxiv.org/abs/1611.05373

[7] Chen, X., Zhou, F., Zhang, K., et al. (2019). Information Diffusion Prediction via Recurrent Cascades Convolution. *ICDE 2019*.

[8] Yuan, C., Li, J., Zhou, W., et al. (2020). CasFlow: Exploring Hierarchical Structures and Propagation Uncertainty for Cascade Prediction. *IEEE TKDE*.
https://github.com/Xovee/casflow

[9] Cao, Q., Shen, H., Cen, K., Ouyang, W., & Cheng, X. (2017). DeepHawkes: Bridging the Gap between Prediction and Understanding of Information Cascades. *CIKM 2017*.
https://github.com/CaoQi92/DeepHawkes

[10] Autoregressive Cascade Predictor in Social Networks via Large Language Models. *arXiv 2025*.
https://arxiv.org/abs/2502.18040

[11] Modeling Trend Dynamics with Variational Neural ODEs for Information Popularity Prediction. *arXiv 2026*.
https://arxiv.org/abs/2603.09148

[12] Towards Realistic and Efficient Information Cascade Prediction (CasTemp). *arXiv 2025*.
https://arxiv.org/abs/2510.25348

### 立场检测与 LLM 增强

[13] LLM-Enhanced Multiple Instance Learning for Joint Rumor Detection and Stance Classification. *arXiv 2025*.
https://arxiv.org/abs/2502.08888

[14] Collaborative Stance Detection via Small and Large Language Models. *arXiv 2025*.
https://arxiv.org/abs/2502.19954

### 传播图分析

[15] Bian, T., Xiao, X., Xu, T., et al. (2020). Rumor Detection on Social Media with Bi-Directional Graph Convolutional Networks. *AAAI 2020*.

[16] Taxidou, I. & Fischer, P. M. (2018). Provenance for Online Information Diffusion. *Distributed and Parallel Databases*.

## 6. 数据集链接

| 数据集 | 链接 | 格式 |
|--------|------|------|
| Sina Weibo (DeepHawkes) | https://github.com/CaoQi92/DeepHawkes | mid \t uid \t timestamp \t retweet_path |
| CasFlow (Weibo/Twitter/APS) | https://github.com/Xovee/casflow | cascade graph + timestamps |
| FOREST (Twitter/Douban) | https://github.com/albertyang33/FOREST/tree/master/data | cascade sequences |
| Twitter15/16 | https://github.com/gszswork/Twitter15_16_dataset | propagation trees |
| 级联预测数据集汇总 | https://github.com/fuxiaG/Information-Diffusion-Datasets | 多数据集索引 |
| 级联预测方法汇总 | https://github.com/ChenNed/Awesome-DL-Information-Cascades-Modeling | 方法+数据集索引 |

## 7. 技术路线总结

```
Phase 1 (已完成): 文献调研 → 5 轨综述 → 方案收敛
Phase 2 (已完成): CascadeSwitch 核心代码实现 (ts_features, regime_model, llm_context, trend_predictor)
Phase 3 (待执行): 数据集加载器 + 级联形态事件检测 + 评估脚本
Phase 4 (待执行): 在 DeepHawkes Weibo 上跑基准实验
Phase 5 (待执行): 消融实验 + 跨平台泛化 + 体制分析可视化
Phase 6 (待执行): CogGuard 系统集成（LLM 事件提取模式）
```
