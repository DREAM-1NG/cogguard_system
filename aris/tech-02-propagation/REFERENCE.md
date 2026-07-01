# KT2 参考文献与数据集索引

**用途**：CascadeSwitch（事件条件体制切换级联预测）方案的完整文献与数据集库，供论文写作、方案精炼、实验设计、外部评审引用使用。
**最后更新**：2026-05-31
**关键技术**：LLM + 时序预测（信息级联预测方向）

---

## 目录

1. [理论基础（必引）](#1-理论基础必引)
2. [信息级联预测：经典与 SOTA](#2-信息级联预测经典与-sota)
3. [Hawkes 过程与事件驱动传播](#3-hawkes-过程与事件驱动传播)
4. [LLM 用于时间序列预测](#4-llm-用于时间序列预测)
5. [事件增强时序预测主线（KT2 核心血统）](#5-事件增强时序预测主线kt2-核心血统)
6. [LLM × 级联预测（同期对手）](#6-llm--级联预测同期对手)
7. [谣言与早期检测](#7-谣言与早期检测)
8. [立场检测](#8-立场检测)
9. [机器人与协同检测](#9-机器人与协同检测)
10. [事件抽取与 LLM 信息抽取](#10-事件抽取与-llm-信息抽取)
11. [传播图分析与可解释性](#11-传播图分析与可解释性)
12. [用户影响力建模（用户画像子功能）](#12-用户影响力建模用户画像子功能)
13. [危害性内容检测（危害性评估子功能）](#13-危害性内容检测危害性评估子功能)
14. [源头追溯与传播取证（源头追溯子功能）](#14-源头追溯与传播取证源头追溯子功能)
15. [影响力扩散与范围估计（范围估计子功能）](#15-影响力扩散与范围估计范围估计子功能)
16. [数据集汇总](#16-数据集汇总)
17. [产业参考](#17-产业参考)
18. [子功能-研究领域-文献映射总表](#18-子功能-研究领域-文献映射总表)
19. [文献-设计映射表](#19-文献-设计映射表)
20. [引用快速复制（BibTeX 占位）](#20-引用快速复制bibtex-占位)
21. [检索关键词与待补检索](#21-检索关键词与待补检索)
22. [文档维护](#22-文档维护)

---

## 1. 理论基础（必引）

> 这一节为 CascadeSwitch 的"体制切换 + 事件条件转移 + 4 阶段传播"提供经典锚点。**当前方案的最大薄弱点就在这里——必须补齐**。

### [F1] Hamilton (1989) — Markov 体制切换的奠基

- **标题**：A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle
- **作者**：James D. Hamilton
- **期刊**：*Econometrica*, 57(2), 357-384
- **年份**：1989
- **链接**：https://www.jstor.org/stable/1912559
- **对 KT2 的价值**：为"信号被多个不可观测体制（regime）混合生成"提供经典数学框架。CascadeSwitch 的 `p(z)` 后验是 Hamilton 框架的简化版（无马尔可夫转移、用 LLM 事件代替隐状态）。
- **引用方式**：作为 regime-switching 思想的**学界标准锚点**，回应"为什么用混合而不是单一模型"。

### [F2] Bass (1969) — 产品扩散的 S 形曲线

- **标题**：A New Product Growth Model for Consumer Durables
- **作者**：Frank M. Bass
- **期刊**：*Management Science*, 15(5), 215-227
- **年份**：1969
- **链接**：https://pubsonline.informs.org/doi/10.1287/mnsc.15.5.215
- **对 KT2 的价值**：Bass 模型把扩散分为 innovation（外生）+ imitation（内生）两过程，自然产生 S 形曲线，对应 CascadeSwitch 的 seeding/amplification/peak/decay 4 阶段。
- **引用方式**：回答"为什么是 4 个体制"——Bass 扩散曲线的导数过零点天然分出 4 段。

### [F3] Rogers (2003) — 创新扩散五阶段

- **标题**：Diffusion of Innovations (5th ed.)
- **作者**：Everett M. Rogers
- **出版**：Free Press / Simon & Schuster
- **年份**：2003（首版 1962）
- **链接**：https://www.simonandschuster.com/books/Diffusion-of-Innovations-5th-Edition/Everett-M-Rogers/9780743222099
- **对 KT2 的价值**：理论传播学经典，提供创新者→早期采用者→早期多数→晚期多数→落后者的五阶段分类，是 4 体制设定的社会学背景。
- **引用方式**：在 introduction 段落引用，建立"传播分阶段是公认事实"的语境。

### [F4] Bengio & Frasconi (1995) — 协变量条件 HMM

- **标题**：An Input-Output HMM Architecture
- **作者**：Yoshua Bengio, Paolo Frasconi
- **会议**：*NeurIPS 1994*（NIPS Proceedings 7）
- **年份**：1995
- **链接**：https://papers.nips.cc/paper/1994/hash/1adf8c44ad9b66dba8c7e94ba75aa75e-Abstract.html
- **对 KT2 的价值**：把 HMM 的隐状态转移概率改成依赖于输入协变量。CascadeSwitch 的 `p(z|events) = softmax(W·e + b)` 正是这种"协变量条件后验"的零训练版本。
- **引用方式**：回应"为什么 W 矩阵可以接受外部事件作为条件"。

### [F5] Jacobs et al. (1991) — 专家混合模型

- **标题**：Adaptive Mixtures of Local Experts
- **作者**：Robert A. Jacobs, Michael I. Jordan, Steven J. Nowlan, Geoffrey E. Hinton
- **期刊**：*Neural Computation*, 3(1), 79-87
- **年份**：1991
- **链接**：https://direct.mit.edu/neco/article/3/1/79/5560
- **对 KT2 的价值**：CascadeSwitch 的"4 个参数化模型按 p(z) 加权"是 mixture-of-experts 的经典形式，gating network 即为 W 矩阵 + softmax。
- **引用方式**：建立"加权混合"在机器学习中的合法性。

---

## 2. 信息级联预测：经典与 SOTA

### [C1] DeepHawkes (Cao et al., CIKM 2017) — 数据集 + Hawkes 神经网络

- **标题**：DeepHawkes: Bridging the Gap between Prediction and Understanding of Information Cascades
- **作者**：Qi Cao, Huawei Shen, Keting Cen, Wentao Ouyang, Xueqi Cheng
- **会议**：*CIKM 2017*
- **链接**：https://dl.acm.org/doi/10.1145/3132847.3132973
- **代码/数据**：https://github.com/CaoQi92/DeepHawkes
- **对 KT2 的价值**：①提供 119K Weibo cascade 主数据集；②把 Hawkes 自激发过程嵌入神经网络，提供"事件触发后续传播"的范式。
- **任务**：观测 t_obs 内级联，预测 t_pred 时刻规模。**直接对应 CascadeSwitch 任务设定**。

### [C2] DeepCas (Li et al., WWW 2017) — 端到端级联预测

- **标题**：DeepCas: An End-to-end Predictor of Information Cascades
- **作者**：Cheng Li, Jiaqi Ma, Xiaoxiao Guo, Qiaozhu Mei
- **会议**：*WWW 2017*
- **链接**：https://arxiv.org/abs/1611.05373
- **对 KT2 的价值**：级联规模预测的 baseline 标杆。任务设定（t_obs → t_pred）成为后续所有工作的事实标准。
- **作为 baseline**：MSLE 表里必出现的对照。

### [C3] CasCN (Chen et al., ICDE 2019) — 级联卷积

- **标题**：Information Diffusion Prediction via Recurrent Cascades Convolution
- **作者**：Xueqin Chen, Fan Zhou, Kunpeng Zhang, et al.
- **会议**：*ICDE 2019*
- **链接**：https://ieeexplore.ieee.org/document/8731519
- **对 KT2 的价值**：把 cascade 子图 + 时间序列联合编码，定义了 GCN+RNN 的 cascade 主流框架。
- **作为 baseline**：代码不易重复，**仅引用论文报告的 MSLE 数值**作为对比锚点。

### [C4] CasFlow (Yuan et al., TKDE 2020) — 层次结构 + 不确定性

- **标题**：CasFlow: Exploring Hierarchical Structures and Propagation Uncertainty for Cascade Prediction
- **作者**：Chengcheng Yuan, Jianyu Li, Wei Zhou, et al.
- **期刊**：*IEEE TKDE* 2020
- **链接**：https://ieeexplore.ieee.org/document/9314060
- **代码**：https://github.com/Xovee/casflow
- **对 KT2 的价值**：①提供 Weibo/Twitter/APS 三组级联数据；②首次显式建模传播不确定性，与 CascadeSwitch 的"混合方差 σ²"直接对接。
- **作为 baseline**：代码可运行，可在 Twitter 数据上做跨平台对比。

### [C5] VaCas (Cao et al., 2020) — 变分级联预测

- **标题**：Popularity Prediction on Social Platforms with Coupled Graph Neural Networks
- **作者**：Qi Cao, Huawei Shen, Jinhua Gao, et al.
- **会议**：*WSDM 2020*
- **链接**：https://dl.acm.org/doi/10.1145/3336191.3371841
- **对 KT2 的价值**：变分推断 + 图神经网络做 popularity prediction，为"不确定性建模"提供另一组 baseline 数。

### [C6] TempCas (Tang et al., AAAI 2021) — 时间感知级联

- **标题**：Fully Exploiting Cascade Graphs for Real-time Forwarding Prediction
- **会议**：*AAAI 2021*
- **链接**：https://ojs.aaai.org/index.php/AAAI/article/view/16104
- **对 KT2 的价值**：实时预测设定，与"早期预测"主题直接相关。

### [C7] CasTemp (arXiv 2025) — 高效现实级联预测

- **标题**：Towards Realistic and Efficient Information Cascade Prediction
- **链接**：https://arxiv.org/abs/2510.25348
- **对 KT2 的价值**：同期最新工作，强调"现实性"——告别合成轨迹假设，与 CascadeSwitch 的"零训练 + 真实级联"哲学一致。
- **引用方式**：作为同期对手方法对比。

### [C8] Variational Neural ODE (arXiv 2026) — 趋势动力学

- **标题**：Modeling Trend Dynamics with Variational Neural ODEs for Information Popularity Prediction
- **链接**：https://arxiv.org/abs/2603.09148
- **对 KT2 的价值**：用 Neural ODE 显式建模 popularity 演化的动力学，与 CascadeSwitch 的"参数化趋势模型"形成对比——他们用神经网络逼近 ODE，我们用经典 4 模型显式参数化。

### [C9] CasFT (arXiv 2024) — 动态线索驱动的扩散预测

- **标题**：Future Trend Modeling for Information Popularity Prediction with Dynamic Cues-Driven Diffusion Models
- **链接**：https://arxiv.org/html/2409.16619
- **数据集**：在 3 个真实世界数据集上验证
- **报告改进**：2.2%–19.3% over SOTA
- **对 KT2 的价值**：**直接对手 / 必比 baseline**——同样关注 popularity prediction 的"未来趋势建模"，且明确把"动态线索"（dynamic cues）作为驱动信号，与 CascadeSwitch 的"事件驱动体制切换"思想高度同型。
- **核心差异化论证**：
  - CasFT 是端到端训练的 diffusion model；CascadeSwitch 是零训练的体制切换混合
  - CasFT 的 dynamic cues 来自数据隐式学习；CascadeSwitch 的事件由 LLM 显式抽取，可解释
  - CasFT 在三数据集调优；CascadeSwitch 强调跨平台无重调
- **引用方式**：必引必比，作为 §5 事件增强 TSF 主线在级联预测领域的现成实例。

---

## 3. Hawkes 过程与事件驱动传播

### [H1] Rizoiu et al. (2017) — Hawkes Intensity Process (HIP)

- **标题**：Expecting to be HIP: Hawkes Intensity Processes for Social Media Popularity
- **作者**：Marian-Andrei Rizoiu, Lexing Xie, Scott Sanner, et al.
- **会议**：*WWW 2017*
- **链接**：https://arxiv.org/abs/1602.06033
- **对 KT2 的价值**：把外部驱动事件（如 Twitter promotion）作为 Hawkes 强度的外生项，**与 CascadeSwitch 的"事件→体制后验"思想最接近的传统模型**。
- **引用方式**：在 method 段落作为"事件驱动传播"思想的传统对照——他们用强度，我们用体制后验。

### [H2] SEISMIC (Zhao et al., KDD 2015) — 自激发 + 推文热度

- **标题**：SEISMIC: A Self-Exciting Point Process Model for Predicting Tweet Popularity
- **作者**：Qingyuan Zhao, Murat A. Erdogdu, Hera Y. He, Anand Rajaraman, Jure Leskovec
- **会议**：*KDD 2015*
- **链接**：https://dl.acm.org/doi/10.1145/2783258.2783401
- **对 KT2 的价值**：把推文热度建模为自激发过程，提供"早期观测→预测最终规模"的传统 baseline 之一。

### [H3] Tutorial on Hawkes Processes for Events in Social Media

- **作者**：Marian-Andrei Rizoiu, Young Lee, Swapnil Mishra, Lexing Xie
- **链接**：https://arxiv.org/abs/1708.06401
- **对 KT2 的价值**：综述性 tutorial，可在 introduction 段落引用建立 Hawkes 传统的语境。

---

## 4. LLM 用于时间序列预测

### [L1] LLMTime (Gruver et al., NeurIPS 2023) — LLM 零样本时序

- **标题**：Large Language Models Are Zero-Shot Time Series Forecasters
- **作者**：Nate Gruver, Marc Finzi, Shikai Qiu, Andrew Gordon Wilson
- **会议**：*NeurIPS 2023*
- **链接**：https://arxiv.org/abs/2310.07820
- **对 KT2 的价值**：早期 LLM 直接做数值时序预测的 positive evidence。
- **引用方式**：在 related work 中提及，但与 [L4] 形成对照。

### [L2] Time-LLM (Jin et al., ICLR 2024) — LLM 重编程

- **标题**：Time-LLM: Time Series Forecasting by Reprogramming Large Language Models
- **作者**：Ming Jin, Shiyu Wang, Lintao Ma, et al.
- **会议**：*ICLR 2024*
- **链接**：https://arxiv.org/abs/2310.01728
- **对 KT2 的价值**：把时序 patch 重编程到 LLM 的语言空间，是 LLM-TS 综合方案。
- **引用方式**：作为"LLM 直接做数值"派的代表，与我们"LLM 只做事件"形成对照。

### [L3] PromptCast (Xue & Salim, IEEE TKDE 2023)

- **标题**：PromptCast: A New Prompt-based Learning Paradigm for Time Series Forecasting
- **作者**：Hao Xue, Flora D. Salim
- **期刊**：*IEEE TKDE* 2023
- **链接**：https://arxiv.org/abs/2210.08964
- **对 KT2 的价值**：Prompt-based TS 预测代表作，证明 LLM 在某些 TS 任务有效。

### [L4] Tan et al. (NeurIPS 2024) — 反向论证

- **标题**：Are Language Models Actually Useful for Time Series Forecasting?
- **作者**：Mingtian Tan, Mike A. Merrill, Vinayak Gupta, Tim Althoff, Tom Hartvigsen
- **会议**：*NeurIPS 2024*
- **链接**：https://arxiv.org/abs/2406.16964
- **对 KT2 的价值**：**关键反向论证文献**——系统证明 LLM 在大多数 TS 任务上**不优于简单 baseline**。这正是 CascadeSwitch **不让 LLM 做数值预测**的设计依据。
- **引用方式**：在 motivation 段直接引用——"基于 [Tan et al. 2024] 的发现，我们将 LLM 限定为事件抽取器而非数值预测器"。

### [L5] Rethinking the Role of LLMs in TSF (arXiv 2026)

- **标题**：Rethinking the Role of Large Language Models in Time Series Forecasting
- **链接**：https://arxiv.org/abs/2602.14744
- **对 KT2 的价值**：进一步细化 LLM 在 TS 中的作用，提出"LLM 适合处理上下文/分布偏移而不适合数值"，与 CascadeSwitch 的 LLM-as-event-extractor 完美匹配。
- **引用方式**：直接论据——LLM 应做的是"上下文编码"。

### [L6] A Controlled Study of LLMs for TS Forecasting (arXiv 2025)

- **标题**：A Controlled Study of LLMs for Time Series Forecasting
- **链接**：https://arxiv.org/html/2504.08818
- **对 KT2 的价值**：**关键反向证据强化** —— 系统性 ablation 评估 LLM 是否真的帮助 TS forecasting，与 [L4] Tan et al. NeurIPS 2024 形成双重支撑。
- **引用方式**：在 motivation 段落与 [L4] 共同引用 —— "[L4][L6] 系列工作系统证明 LLM 在数值时序预测上**不优于**专门时序模型，因此 CascadeSwitch 把 LLM 限定为事件抽取器"。

### [L7] Foundation Models for Time Series 综述 (arXiv 2025)

- **标题**：Foundation Models for Time Series
- **链接**：https://arxiv.org/abs/2504.04011
- **对 KT2 的价值**：Transformer 时序基础模型综述，含 forecasting / anomaly / classification 多任务迁移视角。
- **引用方式**：在 related work 中作为 background，回应"为什么不直接用 TimesFM/Chronos zero-shot"——FM 需要海量预训练，CascadeSwitch 零训练即可运行。

### [L8] Empowering TS Analysis with Foundation Models (arXiv 2024)

- **标题**：Empowering Time Series Analysis with Foundation Models
- **链接**：https://arxiv.org/html/2405.02358v3
- **对 KT2 的价值**：FM 在时序的零样本/小样本/迁移能力综述。
- **引用方式**：作为 [L7] 的补充综述，提供 FM 迁移能力背景。

---

## 5. 事件增强时序预测主线（KT2 核心血统）

> **这一节是 KT2 方案的"血统索引"**——专门收录"用事件增强时序预测"这条主线上的关键工作。CascadeSwitch 不是开荒者，而是这条主线下的一个具体方法（事件抽取由 LLM 完成，预测由参数化体制切换完成）。本节文献用于：①证明路线合法性；②给出差异化论证；③精炼提案时作为对手参考。

### 5.1 主线定义

> **事件增强时序预测**（Event-enhanced / Event-driven Time Series Forecasting）：在数值时序之外，显式或隐式地引入"事件"维度（外生新闻、KOL 行为、平台干预、协同爆发、动态线索），让事件信号去调制或驱动数值预测。

这条主线在 2024-2025 年密集涌现，已成为 LLM-TS 与传统 TS 的主要交叉点之一。

### 5.2 主线代表文献（按相关度）

#### [E-T1] ⭐ Integrating Event Analysis in LLM-Based TSF with Reflection (arXiv 2024)

- **标题（v2）**：Integrating Event Analysis in LLM-Based Time Series Forecasting with Reflection
- **标题（v1）**：Iterative Event Reasoning in LLM-Based Time Series Forecasting
- **链接 v2**：https://arxiv.org/abs/2409.17515
- **链接 v1**：https://arxiv.org/html/2409.17515v1
- **核心机制**：LLM 反思机制把社会事件迭代式整合进时序预测，让事件文本与时序波动对齐
- **与 KT2 关系**：**几乎同型方法论** —— "LLM 做事件分析 + 数值模型做预测"是 CascadeSwitch 的核心思想被同期独立验证
- **关键差异化论证**：
  - E-T1 通过迭代 reflection 多次调用 LLM；CascadeSwitch 通过 W 矩阵一次性事件抽取后做 deterministic forecast，**计算成本更低**
  - E-T1 黑盒整合；CascadeSwitch 白盒 W 矩阵 + softmax，**可解释**
- **引用方式**：在 method 段落明确引用作为路线证据；在 related work 给出差异化对比

#### [E-T2] ⭐ Can LLMs Forecast Internet Traffic from Social Media? (arXiv 2025)

- **链接**：https://arxiv.org/html/2509.20123v1
- **核心**：原型系统从社交媒体讨论中预测互联网流量峰值，命中率 56-92% 的社会驱动尖峰
- **与 KT2 关系**：**直接将"社交事件 → 时序预测"这一迁移路线落地的实证案例**——证明 LLM 抽取的社交事件信号确实能驱动数值时序预测
- **引用方式**：作为"社交事件→时序预测"可行性的实证锚点，在 introduction 引用以建立路线合理性

#### [E-T3] Advancing Event Forecasting through Massive Training of LLMs (arXiv 2025)

- **链接**：https://arxiv.org/html/2507.19477v1
- **核心**：大规模 LLM 训练直接做事件结果预测（societal event forecasting）
- **与 KT2 关系**：**对手范式** —— 端到端 LLM 预测事件，与 CascadeSwitch 把 LLM 限定为事件抽取器形成尖锐对比
- **关键差异化论证**：
  - E-T3 需要海量 LLM 训练成本；CascadeSwitch 零训练
  - E-T3 黑盒输出事件预测；CascadeSwitch 在事件抽取与预测之间显式分离，可单独评估
- **引用方式**：作为"端到端 LLM 事件预测"派的代表对手，证明 CascadeSwitch 的零训练路线是更经济的选择

#### [E-T4] CasFT — Information Popularity with Dynamic Cues-Driven Diffusion (见 [C9])

- **位置**：本节交叉引用 §2 [C9]
- **角色**：事件增强主线在"信息级联预测"领域的现成实例

#### [E-T5] Future Trend Modeling 对手家族（CasFT, CasTemp, VarNeural ODE）

- **CasFT** [C9] — dynamic cues 驱动的扩散
- **CasTemp** [C7] — 现实+高效级联预测
- **VarNeural ODE** [C8] — 变分神经 ODE 趋势

这三篇构成了"信息级联预测领域内的事件增强变体"，CascadeSwitch 是其中**唯一零训练 + 白盒**的方法。

### 5.3 主线全景图

```
                      事件增强时序预测主线
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   通用 TS 增强         社交媒体场景          级联预测领域
        │                     │                     │
   [E-T1] Reflection     [E-T2] Internet Traffic   [E-T4] CasFT
   [L1]-[L8]              [E-T3] Massive Training  [C7] CasTemp
                                                   [C8] VarNeural ODE
                                                   [LC1] AutoCast
                                                          │
                                                  CascadeSwitch（KT2）
                                              零训练 + 白盒 + 跨平台
```

### 5.4 KT2 在主线中的精确定位

| 维度 | E-T1 Reflection | E-T3 Massive | CasFT [C9] | AutoCast [LC1] | **CascadeSwitch (KT2)** |
|------|-----------------|--------------|-----------|----------------|------------------------|
| 任务领域 | 通用 TS | 事件结果预测 | 级联预测 | 级联预测 | **级联预测** |
| LLM 角色 | 反思+整合 | 端到端预测器 | 不使用 | 端到端预测器 | **仅事件抽取器** |
| 训练需求 | 多次 LLM 调用 | 海量预训练 | 端到端训练 diffusion | LLM 微调 | **零训练** |
| 可解释性 | 中（reflection 文本） | 弱 | 弱 | 弱 | **强（W 矩阵 + 中文解释）** |
| 跨平台一致性 | N/A | N/A | 三数据集调优 | 平台特定 | **方法论无关** |
| 学界认可形态 | NeurIPS 系 | LLM 工作 | 同期 SOTA | LLM-cascade 早期 | 体制切换混合 |

### 5.5 论点合法性总结

> 在 [E-T1][E-T2][E-T3] 和 [C9][C7][C8][LC1] 共同奠定的主线下，**KT2 的 CascadeSwitch 不是孤立的方法，而是这条主线上一个明确占据"零训练 + 白盒 + 跨平台"角的具体实例**。reviewer 关于路线合法性的疑问可由本节文献组直接回应。

---

## 6. LLM × 级联预测（同期对手）

### [LC1] AutoCast LLM (arXiv 2025) — 自回归级联预测器

- **标题**：Autoregressive Cascade Predictor in Social Networks via Large Language Models
- **链接**：https://arxiv.org/abs/2502.18040
- **对 KT2 的价值**：**最直接的同期对手**——把 LLM 用作级联预测器。CascadeSwitch 的差异化论点：他们让 LLM 直接预测，我们让 LLM 只做事件分类，预测交给参数化模型。
- **引用方式**：必须比较，强调"训练成本"与"可解释性"差异。

### [LC2] LLM-MIL Joint Rumor & Stance (arXiv 2025)

- **标题**：LLM-Enhanced Multiple Instance Learning for Joint Rumor Detection and Stance Classification
- **链接**：https://arxiv.org/abs/2502.08888
- **对 KT2 的价值**：联合多任务范式，与 KT2 拟扩展的"传播预测 + 谣言 + 立场"三任务统一架构相关。

### [LC3] Collaborative Stance Detection (arXiv 2025)

- **标题**：Collaborative Stance Detection via Small and Large Language Models
- **链接**：https://arxiv.org/abs/2502.19954
- **对 KT2 的价值**：小模型 + 大模型协作做立场检测，符合 CascadeSwitch 的"轻量主干 + LLM 增强"哲学。

---

## 7. 谣言与早期检测

### [R1] Bi-GCN (Bian et al., AAAI 2020) — 双向图谣言检测

- **标题**：Rumor Detection on Social Media with Bi-Directional Graph Convolutional Networks
- **作者**：Tian Bian, Xi Xiao, Tingyang Xu, et al.
- **会议**：*AAAI 2020*
- **链接**：https://arxiv.org/abs/2001.06362
- **代码**：https://github.com/TianBian95/BiGCN
- **对 KT2 的价值**：propagation tree 上做谣言检测的代表作。如果 KT2 扩展到 rumor head，这是必比 baseline。

### [R2] EANN (Wang et al., KDD 2018) — 多模态谣言检测

- **标题**：EANN: Event Adversarial Neural Networks for Multi-Modal Fake News Detection
- **会议**：*KDD 2018*
- **链接**：https://dl.acm.org/doi/10.1145/3219819.3219903
- **对 KT2 的价值**：把"事件"作为 adversarial 信号去除事件偏置，提供"事件感知"的另一种思路。

### [R3] dEFEND (Shu et al., KDD 2019) — 可解释谣言检测

- **标题**：dEFEND: Explainable Fake News Detection
- **会议**：*KDD 2019*
- **链接**：https://dl.acm.org/doi/10.1145/3292500.3330935
- **对 KT2 的价值**：可解释假新闻检测的经典工作，对 CascadeSwitch 强调的"白盒 + 中文解释"提供对照。

### [R4] Ma et al. (ACL 2018) — RvNN 谣言检测 + 中文 Weibo Rumor 数据集

- **标题**：Rumor Detection on Twitter with Tree-structured Recursive Neural Networks
- **作者**：Jing Ma, Wei Gao, Kam-Fai Wong
- **会议**：*ACL 2018*
- **链接**：https://aclanthology.org/P18-1184/
- **代码**：https://github.com/majingCUHK/Rumor_RvNN
- **数据**：Weibo 谣言数据集（中文）
- **对 KT2 的价值**：①提供中文 Weibo Rumor 数据集；②树结构 RvNN 是 propagation tree 处理的另一基线。

### [R5] Early Rumor Detection (Liu et al., WWW 2024) — 早期检测专题

- **标题**：Early Rumor Detection: An Adversarial Multi-task Approach
- **会议**：*WWW 2024 / 同年代研究*
- **链接**：参考 https://arxiv.org/list/cs.SI/recent 中 early rumor detection 综述
- **对 KT2 的价值**：与"早期级联预测"主题方法论一致——观测窗口很短就要做判定，评估早 N 小时识别能力。

### [R6] Survey: Rumor Detection on Social Media

- **标题**：A Survey on Rumor Detection in Online Social Media
- **代表综述**：Zubiaga et al. (CSUR 2018) https://dl.acm.org/doi/10.1145/3161603
- **对 KT2 的价值**：背景综述，为新 reviewer 提供阅读入口。

---

## 8. 立场检测

### [S1] SemEval-2016 Task 6 (Mohammad et al., 2016)

- **标题**：SemEval-2016 Task 6: Detecting Stance in Tweets
- **链接**：https://aclanthology.org/S16-1003/
- **对 KT2 的价值**：英文立场检测的标准 benchmark + 数据集。WP4 stance_detector 必引必比。

### [S2] LLM-Stance Survey / 最新 LLM-Stance

- **标题代表**：A Survey of Stance Detection with Large Language Models
- **链接**：https://arxiv.org/abs/2403.05798（同类综述）
- **对 KT2 的价值**：综述 LLM 时代立场检测的方法演化。

### [S3] Collaborative Stance Detection (见 [LC3])

---

## 9. 机器人与协同检测

### [B1] BotDGT (Cui et al., 2024 系) — 动态图 Transformer

- **标题**：BotDGT: Dynamicity-aware Social Bot Detection with Dynamic Graph Transformers
- **链接**：相关工作可在 https://arxiv.org/list/cs.SI/recent 检索 "BotDGT"
- **对 KT2 的价值**：单账号 bot 检测的最新代表。如果 KT2 扩展到 bot 估计，作为差异化对手——他们做单账号，我们做群体级占比。

### [B2] TwiBot-22 (Feng et al., NeurIPS 2022) — Bot 检测大数据集

- **标题**：TwiBot-22: Towards Graph-Based Twitter Bot Detection
- **会议**：*NeurIPS 2022 D&B*
- **链接**：https://arxiv.org/abs/2206.04564
- **数据**：https://twibot22.github.io/
- **对 KT2 的价值**：bot 标签数据集，可用于群体级 bot 占比验证。

### [B3] MGTAB (Shi et al., 2023) — 多关系图 bot 数据集

- **标题**：MGTAB: A Multi-Relational Graph-Based Twitter Account Dataset for Stance Detection
- **链接**：https://arxiv.org/abs/2301.01123
- **对 KT2 的价值**：同时含 stance + bot 标签的数据集，**对 KT2 的多任务扩展极为合适**。

---

## 10. 事件抽取与 LLM 信息抽取

### [E1] LLM-as-Event-Extractor 综述（2024）

- **标题代表**：Large Language Models for Information Extraction: A Survey
- **链接**：https://arxiv.org/abs/2312.17617（IE 综述）
- **对 KT2 的价值**：为"LLM 做结构化事件抽取"提供方法论文献支撑。

### [E2] Schema-Guided Event Extraction with LLMs

- **链接代表**：https://arxiv.org/abs/2310.06162（GoLLIE）
- **对 KT2 的价值**：CascadeSwitch 的 LLM 事件抽取使用 JSON schema + 多次投票，对应 schema-guided extraction 的最佳实践。

---

## 11. 传播图分析与可解释性

### [G1] Provenance for Online Information Diffusion (Taxidou & Fischer, 2018)

- **期刊**：*Distributed and Parallel Databases*
- **链接**：https://link.springer.com/article/10.1007/s10619-016-7195-y
- **对 KT2 的价值**：信息传播 provenance 追溯，对应 propagation_legacy.py "源头追溯" 子功能。

### [G2] Cascading Behavior in Networks (Leskovec et al., KDD 2007)

- **标题**：Cost-effective Outbreak Detection in Networks
- **链接**：https://dl.acm.org/doi/10.1145/1281192.1281239
- **对 KT2 的价值**：网络爆发检测的经典工作，提供"关键节点提前识别"理论根据。

---

## 12. 用户影响力建模（用户画像子功能）

> 服务于"用户画像"子功能：识别 KOL、媒体、机器人协同集群在传播中扮演的角色与权重，为趋势预测提供 `kol_ratio` 等结构化特征，也为关键节点分析提供影响力排序。

### [U1] Cha et al. (ICWSM 2010) — 三种 Twitter 影响力度量

- **标题**：Measuring User Influence in Twitter: The Million Follower Fallacy
- **作者**：Meeyoung Cha, Hamed Haddadi, Fabricio Benevenuto, Krishna P. Gummadi
- **会议**：*ICWSM 2010*
- **链接**：https://ojs.aaai.org/index.php/ICWSM/article/view/14033
- **对 KT2 的价值**：经典论证粉丝数 ≠ 影响力，应同时使用 indegree / retweet / mention 三度量。**直接支撑"KOL 占比"特征不能仅用粉丝数判定**。
- **引用方式**：在用户画像章节引用，回应"为什么 kol_ratio 需要复合度量"。

### [U2] TwitterRank (Weng et al., WSDM 2010) — 主题敏感的影响力 PageRank

- **标题**：TwitterRank: Finding Topic-sensitive Influential Twitterers
- **作者**：Jianshu Weng, Ee-Peng Lim, Jing Jiang, Qi He
- **会议**：*WSDM 2010*
- **链接**：https://dl.acm.org/doi/10.1145/1718487.1718520
- **对 KT2 的价值**：把 PageRank 与话题分布耦合，给出主题敏感的影响力计算。CogGuard 在事件级监控时天然带话题约束，与 TwitterRank 的话题语境匹配。
- **引用方式**：用户画像段落 baseline。

### [U3] Bakshy et al. (WSDM 2011) — 影响力与级联规模的关系

- **标题**：Everyone's an Influencer: Quantifying Influence on Twitter
- **作者**：Eytan Bakshy, Jake M. Hofman, Winter A. Mason, Duncan J. Watts
- **会议**：*WSDM 2011*
- **链接**：https://dl.acm.org/doi/10.1145/1935826.1935845
- **对 KT2 的价值**：大规模实证证明个体过去的级联表现是预测未来影响力的最强单一信号。**为 CascadeSwitch 把"历史 KOL 行为"作为体制先验提供经验证据**。

### [U4] Anger & Kittl (2011) — Social Networking Potential

- **标题**：Measuring Influence on Twitter
- **会议**：*i-KNOW 2011*
- **链接**：https://dl.acm.org/doi/10.1145/2024288.2024326
- **对 KT2 的价值**：提出 SNP（Social Networking Potential）——用 retweet/mention 比例归一化，避免"僵尸粉"问题。可作为 bot_ratio 估计的辅助信号。

### [U5] PageRank (Brin & Page, 1998) — 网络中心性奠基

- **标题**：The Anatomy of a Large-Scale Hypertextual Web Search Engine
- **作者**：Sergey Brin, Lawrence Page
- **链接**：https://infolab.stanford.edu/~backrub/google.html
- **对 KT2 的价值**：网络中心性的奠基方法，propagation_legacy 中关键节点排序的理论基础。

### [U6] HITS (Kleinberg, JACM 1999) — Hub & Authority

- **标题**：Authoritative Sources in a Hyperlinked Environment
- **作者**：Jon M. Kleinberg
- **期刊**：*Journal of the ACM*, 46(5)
- **链接**：https://dl.acm.org/doi/10.1145/324133.324140
- **对 KT2 的价值**：把节点分为 hub（汇聚者）与 authority（权威），对应 KOL（authority）与放大器（hub）的分类。

### [U7] Pei et al. (Nature Communications 2014) — 找到真正的传播者

- **标题**：Searching for Superspreaders of Information in Real-world Social Media
- **链接**：https://www.nature.com/articles/srep05547
- **对 KT2 的价值**：实证发现网络位置 + k-shell 比粉丝数更能预测谁是真正的超级传播者。

### [U8] Survey on User Profiling in OSN

- **标题代表**：User Profiling: A Survey on Methods and Datasets in Online Social Networks
- **链接**：https://dl.acm.org/doi/10.1145/3580305 / https://arxiv.org/abs/2310.01049（同类综述）
- **对 KT2 的价值**：综述视角，建立用户画像与下游任务（影响力、立场、谣言）联动的语境。

---

## 13. 危害性内容检测（危害性评估子功能）

> 服务于"危害性评估"子功能：判断帖文是否构成仇恨言论、煽动、虚假信息、隐私泄露、网络暴力，输出危害等级（低/中/高/极高）与危害类型多标签。**目前 KT2 文献清单完全缺失这一块**，必须补齐。

### [D1] Davidson et al. (ICWSM 2017) — 仇恨言论 vs 攻击性语言

- **标题**：Automated Hate Speech Detection and the Problem of Offensive Language
- **作者**：Thomas Davidson, Dana Warmsley, Michael Macy, Ingmar Weber
- **会议**：*ICWSM 2017*
- **链接**：https://arxiv.org/abs/1703.04009
- **数据**：https://github.com/t-davidson/hate-speech-and-offensive-language
- **对 KT2 的价值**：危害性细粒度区分（hate speech vs offensive vs neither）的经典 baseline。提供 24K 推文数据集。

### [D2] HateXplain (Mathew et al., AAAI 2021) — 可解释仇恨检测

- **标题**：HateXplain: A Benchmark Dataset for Explainable Hate Speech Detection
- **作者**：Binny Mathew, Punyajoy Saha, Seid Muhie Yimam, et al.
- **会议**：*AAAI 2021*
- **链接**：https://arxiv.org/abs/2012.10289
- **数据**：https://github.com/hate-alert/HateXplain
- **对 KT2 的价值**：含 token 级 rationale 标注，与 CascadeSwitch 强调的"中文解释输出"思想一致。

### [D3] ToxiGen (Hartvigsen et al., ACL 2022) — 大规模隐性毒性

- **标题**：ToxiGen: A Large-Scale Machine-Generated Dataset for Adversarial and Implicit Hate Speech Detection
- **作者**：Thomas Hartvigsen, Saadia Gabriel, Hamid Palangi, et al.
- **会议**：*ACL 2022*
- **链接**：https://arxiv.org/abs/2203.09509
- **数据**：https://github.com/microsoft/TOXIGEN
- **对 KT2 的价值**：274K 隐性毒性数据，覆盖 13 个少数群体，**支撑 CogGuard 多群体危害评估场景**。

### [D4] OLID / OffensEval (Zampieri et al., NAACL 2019)

- **标题**：Predicting the Type and Target of Offensive Posts in Social Media
- **链接**：https://arxiv.org/abs/1902.09666
- **数据**：https://sites.google.com/site/offensevalsharedtask/
- **对 KT2 的价值**：分级分类（offensive 与否、targeted 与否、target 类型）的标准 benchmark。

### [D5] Llama Guard (Inan et al., 2023) — LLM 作为安全分类器

- **标题**：Llama Guard: LLM-based Input-Output Safeguard for Human-AI Conversations
- **作者**：Hakan Inan, Kartikeya Upasani, Jianfeng Chi, et al.
- **链接**：https://arxiv.org/abs/2312.06674
- **代码**：https://github.com/meta-llama/PurpleLlama
- **对 KT2 的价值**：把 LLM 用作多类别有害内容分类器，输出 schema 化结果，**直接对应 KT2 危害评估的"规则 + LLM 增强"路线**。

### [D6] Perspective API (Jigsaw, 持续更新) — 工业基线

- **官网**：https://perspectiveapi.com/
- **论文**：https://arxiv.org/abs/2007.05909（Lees et al. 2022 评估）
- **对 KT2 的价值**：Google Jigsaw 出品的工业级 toxicity 评分，作为危害评估的工业 baseline。

### [D7] COLD (Deng et al., EMNLP 2022) — 中文冒犯性数据集

- **标题**：COLD: A Benchmark for Chinese Offensive Language Detection
- **链接**：https://arxiv.org/abs/2201.06025
- **数据**：https://github.com/thu-coai/COLDataset
- **对 KT2 的价值**：**中文场景必备**——37K 中文标注，含 race/region/gender 子类。

### [D8] CDial-Bias (Zhou et al., 2022) — 中文对话偏见

- **标题**：Towards Identifying Social Bias in Dialog Systems: Framework, Dataset, and Benchmark
- **链接**：https://arxiv.org/abs/2202.08011
- **数据**：https://github.com/para-zhou/CDial-Bias
- **对 KT2 的价值**：补充中文社会偏见识别能力。

### [D9] MisinfoCorpus / FakeNewsNet (Shu et al., 2018) — 虚假信息

- **标题**：FakeNewsNet: A Data Repository with News Content, Social Context and Spatiotemporal Information for Studying Fake News
- **链接**：https://arxiv.org/abs/1809.01286
- **数据**：https://github.com/KaiDMML/FakeNewsNet
- **对 KT2 的价值**：把"虚假信息"作为危害类型之一，与 propagation 信息打通。

### [D10] Survey: Hate Speech Detection

- **标题代表**：A Survey on Automatic Detection of Hateful Comments
- **链接**：https://dl.acm.org/doi/10.1145/3232676 (Schmidt & Wiegand, 2017) / https://arxiv.org/abs/2308.03824 (LLM 时代综述)
- **对 KT2 的价值**：综述入口。

---

## 14. 源头追溯与传播取证（源头追溯子功能）

> 服务于"源头追溯"子功能：在已观测的传播图上反推谣言/虚假信息的可能起源节点，并构建从起源到关键放大节点的证据链。**propagation_legacy.py 已实现 MultiDiGraph + 证据链 + 关键路径，但缺文献支撑**。

### [O1] Shah & Zaman (IEEE TIT 2011) — Rumor Centrality

- **标题**：Rumors in a Network: Who's the Culprit?
- **作者**：Devavrat Shah, Tauhid Zaman
- **期刊**：*IEEE Transactions on Information Theory*
- **链接**：https://arxiv.org/abs/0909.4370
- **对 KT2 的价值**：**信息源识别（rumor source detection）领域的奠基工作**——证明在 SI 模型下最大似然源点等价于"rumor centrality"最大节点。**直接支撑 propagation_legacy 的源头追溯方法**。
- **引用方式**：源头追溯章节必引。

### [O2] NETSLEUTH (Prakash et al., ICDM 2012) — MDL 视角的源点检测

- **标题**：Spotting Culprits in Epidemics: How many and Which ones?
- **作者**：B. Aditya Prakash, Jilles Vreeken, Christos Faloutsos
- **会议**：*ICDM 2012*
- **链接**：https://faculty.cc.gatech.edu/~badityap/papers/netsleuth-icdm12.pdf
- **对 KT2 的价值**：用 Minimum Description Length 同时确定"源点数"与"源点位置"，比单源假设更现实。

### [O3] Pinto et al. (PRL 2012) — 有限观测者下的源点定位

- **标题**：Locating the Source of Diffusion in Large-Scale Networks
- **作者**：Pedro C. Pinto, Patrick Thiran, Martin Vetterli
- **期刊**：*Physical Review Letters*
- **链接**：https://arxiv.org/abs/1208.2534
- **对 KT2 的价值**：在仅观测部分节点的现实条件下做源点定位，**与 CogGuard 真实采集场景一致**（无法看到全网）。

### [O4] Jiang et al. (IEEE Comm. Surveys 2017) — 源点检测综述

- **标题**：Identifying Propagation Sources in Networks: State-of-the-Art and Comparative Studies
- **链接**：https://ieeexplore.ieee.org/document/7480789
- **对 KT2 的价值**：综述入口，覆盖 single source / multi source / partial observation 各场景。

### [O5] Provenance for Online Information Diffusion (Taxidou & Fischer, 2018)

- **期刊**：*Distributed and Parallel Databases*
- **链接**：https://link.springer.com/article/10.1007/s10619-016-7195-y
- **对 KT2 的价值**：信息传播 provenance 追溯框架，对应 propagation_legacy 的"证据链"建模思路。已在第 10 节 [G1] 引用，此处作为源头追溯的工程化实现参考。

### [O6] Antoniades & Dovrolis (ICWSM 2015) — 信息流取证

- **标题**：Co-evolutionary Dynamics in Social Networks: A Case Study of Twitter
- **链接**：https://arxiv.org/abs/1510.05902
- **对 KT2 的价值**：从信息流共演化视角追溯起源，提供与单源假设不同的视角。

### [O7] Truth Inference / Veracity Reasoning

- **标题代表**：Truth Discovery in Crowdsourced Data
- **链接**：综述见 https://dl.acm.org/doi/10.1145/2872427.2883022
- **对 KT2 的价值**：在源头追溯之后做"内容真实性推断"，与谣言检测形成互补。

### [O8] Cascading Behavior in Networks (Leskovec et al., KDD 2007)

- **标题**：Cost-effective Outbreak Detection in Networks
- **链接**：https://dl.acm.org/doi/10.1145/1281192.1281239
- **对 KT2 的价值**：网络爆发检测的经典工作，提供"关键节点提前识别"理论根据。已在第 10 节 [G2] 引用，此处作为源头追溯的关键节点排序理论基础。

---

## 15. 影响力扩散与范围估计（范围估计子功能）

> 服务于"范围估计"子功能：基于已观测级联估计真实扩散规模（含未观测部分），并预测剩余可触达上界。CascadeSwitch 的 `volume_forecast` 已经覆盖部分能力，但更精细的"已扩散用户数 / 真实触达上界"估计需要独立的扩散模型支撑。

### [I1] Kempe-Kleinberg-Tardos (KDD 2003) — 影响力最大化奠基

- **标题**：Maximizing the Spread of Influence through a Social Network
- **作者**：David Kempe, Jon Kleinberg, Éva Tardos
- **会议**：*KDD 2003*
- **链接**：https://www.cs.cornell.edu/home/kleinber/kdd03-inf.pdf
- **对 KT2 的价值**：**影响力扩散领域奠基论文**——形式化定义 IC（Independent Cascade）与 LT（Linear Threshold）模型。范围估计的所有后续工作都建立在这两个模型之上。

### [I2] Goldenberg et al. (Marketing Letters 2001) — Independent Cascade Model

- **标题**：Talk of the Network: A Complex Systems Look at the Underlying Process of Word-of-Mouth
- **链接**：https://link.springer.com/article/10.1023/A:1011122126881
- **对 KT2 的价值**：IC 模型的原始提出，从市场学角度解释"谁感染谁"的概率过程。

### [I3] Saito et al. (ICDM 2008) — 概率扩散模型参数学习

- **标题**：Prediction of Information Diffusion Probabilities for Independent Cascade Model
- **链接**：https://link.springer.com/chapter/10.1007/978-3-540-85567-5_9
- **对 KT2 的价值**：从历史观测估计 IC 模型边权（感染概率），**支撑 CogGuard 的"未观测部分扩散估计"**。

### [I4] Wang et al. (Nature Comm. 2013) — 估计推文真实曝光

- **标题**：Quantifying the Effect of Temporal Resolution on Time-varying Networks
- **链接**：https://www.nature.com/articles/srep03006
- **对 KT2 的价值**：时间分辨率对扩散估计的影响——支持小时聚合不丢失关键信号。

### [I5] Cheng et al. (WWW 2014) — 级联是否会变大？

- **标题**：Can Cascades be Predicted?
- **作者**：Justin Cheng, Lada Adamic, P. Alex Dow, Jon Kleinberg, Jure Leskovec
- **会议**：*WWW 2014*
- **链接**：https://arxiv.org/abs/1403.4608
- **对 KT2 的价值**：实证给出"早期信号 → 最终规模"可预测性的边界，**与 CascadeSwitch 早期预测设定直接相关**。

### [I6] Galuba et al. (WOSN 2010) — URL 扩散预测

- **标题**：Outtweeting the Twitterers — Predicting Information Cascades in Microblogs
- **链接**：https://www.usenix.org/conference/wosn-10/outtweeting-twitterers-predicting-information-cascades-microblogs
- **对 KT2 的价值**：早期 URL 扩散 baseline，提供轻量基线参考。

### [I7] Du et al. (NeurIPS 2013) — 连续时间影响力估计

- **标题**：Scalable Influence Estimation in Continuous-Time Diffusion Networks
- **链接**：https://papers.nips.cc/paper/2013/hash/5a4b25aaed25c2ee1b74de72dc03c14e-Abstract.html
- **对 KT2 的价值**：连续时间扩散网络下的可扩展影响力估计，比离散 IC/LT 更贴近真实推文流。

### [I8] Survey: Influence Maximization

- **标题代表**：A Survey on Influence Maximization in a Social Network
- **链接**：https://link.springer.com/article/10.1007/s10115-018-1254-2
- **对 KT2 的价值**：综述入口，列出 200+ 后续 IM 算法。

### [I9] CTIC / Topic-Aware Diffusion (Barbieri et al., ICDM 2012)

- **标题**：Topic-aware Social Influence Propagation Models
- **链接**：https://ieeexplore.ieee.org/document/6413740
- **对 KT2 的价值**：把话题语境引入扩散模型，与 CogGuard 事件级监控天然耦合。

---

## 16. 数据集汇总

### 16.1 主实验数据集（仅级联轨迹）

| 数据集 | 链接 | 规模 | 平台 | 任务支持 |
|--------|------|------|------|----------|
| **DeepHawkes Weibo** | https://github.com/CaoQi92/DeepHawkes | 119K cascade | Weibo | ts_features, regime 模式 A |
| **CasFlow Weibo** | https://github.com/Xovee/casflow | ~120K | Weibo | 全部模式 A |
| **CasFlow Twitter** | 同上 | ~30K | Twitter | 跨平台泛化 |
| **CasFlow APS** | 同上 | ~200K | APS 引文 | 引文级联（非社交） |
| **FOREST Twitter** | https://github.com/albertyang33/FOREST | - | Twitter | 级联序列 |
| **FOREST Douban** | 同上 | - | Douban | 中文社交 |

### 16.2 含文本 + 标签的数据集（支持模式 B + 谣言/立场扩展）

| 数据集 | 链接 | 含级联 | 含原文 | 含标签 | 用途 |
|--------|------|--------|--------|--------|------|
| **Weibo-COVID19** (Lu et al., WWW 2022) | https://github.com/RMSnow/WWW2022 | ✓ | ✓ | 谣言 | **唯一中文级联+原文+标签**——必下载 |
| **PHEME** | https://figshare.com/articles/PHEME_dataset_for_Rumour_Detection_and_Veracity_Classification/6392078 | ✓（树） | ✓ | 谣言+veracity | 英文版同等数据 |
| **Twitter15** | https://github.com/gszswork/Twitter15_16_dataset | ✓（树） | ✓ | 谣言 4 类 | 经典 baseline 数据 |
| **Twitter16** | 同上 | ✓ | ✓ | 谣言 4 类 | 经典 baseline 数据 |
| **Weibo Rumor (Ma et al., ACL 2018)** | https://github.com/majingCUHK/Rumor_RvNN | ✓ | ✓ | 谣言 2 类 | 中文经典 |
| **CHEF (Hu et al., ACL 2022)** | https://github.com/THU-BPM/CHEF | △ | ✓ | 中文事实核查 | 立场/谣言扩展用 |
| **Event-Centric Sentiment TS** (arXiv 2026) | https://arxiv.org/abs/2605.21198 | ✓（含交互结构） | ✓ | 情绪+事件 | **事件增强时序预测主线专用** —— KT2 跨领域验证候选 |

### 16.3 立场检测数据集（立场检测子功能）

| 数据集 | 链接 | 规模 | 标签 |
|--------|------|------|------|
| **SemEval-2016 Task 6** | http://alt.qcri.org/semeval2016/task6/ | ~4K | 5 主题 × {favor, against, none} |
| **C-Stance (Zhao et al., 2023)** | https://github.com/chuchun8/CStance | 中文立场 | 7 类 |
| **VAST** | https://github.com/emilyallaway/zero-shot-stance | 大规模零样本立场 | 自由话题 |

### 16.4 机器人检测数据集

| 数据集 | 链接 | 规模 | 标签 |
|--------|------|------|------|
| **TwiBot-22** | https://twibot22.github.io/ | 1M 账号 | bot/human |
| **TwiBot-20** | https://github.com/BunsenFeng/TwiBot-20 | 230K | bot/human |
| **MGTAB** | https://github.com/GraphDetec/MGTAB | 10K | stance + bot 联合 |
| **Cresci-2017** | https://botometer.osome.iu.edu/bot-repository/datasets.html | ~5K | bot 多类 |

### 16.5 危害性内容数据集（危害性评估子功能）

| 数据集 | 链接 | 规模 | 标签 | 语言 |
|--------|------|------|------|------|
| **HateXplain** | https://github.com/hate-alert/HateXplain | 20K | hate/offensive/normal + token rationale | 英文 |
| **Davidson 2017** | https://github.com/t-davidson/hate-speech-and-offensive-language | 24K | hate/offensive/neither | 英文 |
| **ToxiGen** | https://github.com/microsoft/TOXIGEN | 274K | 13 群体 × toxic/benign | 英文（机器生成） |
| **OLID / OffensEval** | https://sites.google.com/site/offensevalsharedtask/ | 14K | 三层（offensive/targeted/target type） | 英文 |
| **COLD** | https://github.com/thu-coai/COLDataset | 37K | offensive 二类 + 子类（race/region/gender） | **中文** |
| **CDial-Bias** | https://github.com/para-zhou/CDial-Bias | ~28K | 偏见/中性 | **中文** |
| **FakeNewsNet** | https://github.com/KaiDMML/FakeNewsNet | ~24K 新闻 | fake/real + 社交上下文 | 英文 |

### 16.6 用户影响力 / 社交角色数据集（用户画像子功能）

| 数据集 | 链接 | 规模 | 用途 |
|--------|------|------|------|
| **Higgs Twitter** | https://snap.stanford.edu/data/higgs-twitter.html | 456K 用户、~14M 边 | 真实 retweet/mention/reply/follow 网络 |
| **WeiboLeaks (历史)** | 论文引用为主 | - | KOL 行为研究历史数据 |
| **Twitter Influence Dataset** | https://snap.stanford.edu/data/index.html#sn | 多 | 网络中心性算法验证 |
| **Pushshift Reddit** | https://files.pushshift.io/reddit/ | 全 Reddit | 跨平台用户行为 |

### 16.7 源头追溯数据集（源头追溯子功能）

| 数据集 | 链接 | 规模 | 任务支持 |
|--------|------|------|----------|
| **PHEME** (重复出现) | 见 15.2 | 9 事件 × ~330 树 | rumor source + propagation tree |
| **CoAID** | https://github.com/cuilimeng/CoAID | 4K 健康谣言 | 谣言溯源 + propagation |
| **合成网络（IC/SI 模拟）** | NetworkX / SNAP 生成 | 任意 | source detection 算法验证标准做法 |
| **Twitter15/16** (重复出现) | 见 15.2 | ~1.5K 树 | 含 source 节点标注 |

### 16.8 影响力扩散数据集（范围估计子功能）

| 数据集 | 链接 | 规模 | 任务支持 |
|--------|------|------|----------|
| **HEP-PH / HEP-TH** (引文网络) | https://snap.stanford.edu/data/cit-HepPh.html | 34K 论文 | IC/LT 模型经典验证集 |
| **Memetracker** | https://snap.stanford.edu/data/memetracker9.html | 96M 引用 | meme 跨站点扩散 |
| **Sina Weibo Diffusion** | 文献中获取 | - | 真实扩散级联 |
| **Twitter Diffusion (Galuba 2010)** | https://www.usenix.org/conference/wosn-10 | URL 流 | URL 扩散预测 baseline |

### 16.9 索引与汇总仓库

| 资源 | 链接 |
|------|------|
| 信息扩散数据集汇总 | https://github.com/fuxiaG/Information-Diffusion-Datasets |
| 级联预测方法汇总 | https://github.com/ChenNed/Awesome-DL-Information-Cascades-Modeling |
| 谣言检测综述仓库 | https://github.com/SoftWiser-group/Awesome-Misinformation-Detection |
| Bot 检测综述仓库 | https://github.com/BunsenFeng/awesome-bot-detection |

---

## 17. 产业参考

### [P1] 知微传播分析 WeiboReach

- **官网**：http://www.weiboreach.com/
- **母公司**：知微数据 https://www.zhiweidata.com/
- **本地分析文档**：[ZHIWEI_PRODUCT_ANALYSIS.md](./ZHIWEI_PRODUCT_ANALYSIS.md)
- **对 KT2 的价值**：产业基准。功能可借鉴（传播力指数、阶段标注、关键节点），方法上差异化（事后 vs 前瞻、黑盒 vs 白盒、Weibo 专 vs 跨平台）。

### [P2] Crunchbase 知微数据

- **链接**：https://www.crunchbase.com/organization/weiboreach-com
- **用途**：公司基本信息、融资信息

---

## 18. 子功能-研究领域-文献映射总表

> 这张表是**传播监控功能板块**到**研究领域**到**关键文献**的总索引。每行对应一个子功能，每列给出主研究领域、二级研究领域、奠基/经典文献、SOTA 文献、CogGuard 实现路径。

### 17.1 一览表

| 子功能 | 主研究领域 | 二级研究领域 | 奠基文献 | SOTA / 主流 baseline | CogGuard 实现 | 是否关键技术二 |
|--------|----------|-------------|---------|---------------------|--------------|--------------|
| 趋势预测 | 信息级联预测 (Information Cascade Prediction) | LLM-TS、Hawkes、Regime Switching、**事件增强 TSF 主线** | [F1] Hamilton 1989, [F2] Bass 1969, [C1] DeepHawkes, [C2] DeepCas | [C4] CasFlow, [C7] CasTemp, [C8] VarNeural ODE, [C9] CasFT, [LC1] AutoCast LLM, [E-T1] Reflection 2024, [E-T2] Internet Traffic 2025, [E-T3] Massive Training 2025 | CascadeSwitch（ts_features + llm_context + regime_model + trend_predictor） | ✅ **核心** |
| 用户画像 | 用户影响力建模 (User Influence Modeling) | KOL 识别、网络中心性、社交角色发现 | [U5] PageRank, [U6] HITS, [U1] Cha ICWSM 2010 | [U2] TwitterRank, [U3] Bakshy WSDM 2011, [U7] Pei NatComm 2014 | 元数据聚合 + 标签匹配（与 KT1 协同信号融合） | ✗ 工程 |
| 立场检测 | Stance Detection | LLM 立场分类、跨语言立场、零样本立场 | [S1] SemEval-2016 | [LC3] Collaborative SLM-LLM, [LC2] LLM-MIL Joint, [S2] LLM-Stance Survey | LLM zero-shot 6 类分类（待实现 stance_detector.py） | △ 边缘 |
| 危害性评估 | Harmful Content Detection | Hate Speech、Toxicity、虚假信息 | [D1] Davidson 2017, [D4] OffensEval | [D2] HateXplain, [D3] ToxiGen, [D5] Llama Guard, [D7] COLD（中文） | 规则 + LLM 增强（待实现 harm_assessor.py） | ✗ 工程 |
| 源头追溯 | Rumor Source Detection | Network Provenance、Information Forensics | [O1] Shah & Zaman 2011, [G1] Taxidou 2018 | [O2] NETSLEUTH, [O3] Pinto PRL 2012, [O4] Jiang Survey 2017 | MultiDiGraph + 证据链（propagation_legacy.py 已实现） | ✗ 工程（旧方向遗留） |
| 范围估计 | Influence Diffusion | Influence Maximization、IC/LT 模型、连续时间扩散 | [I1] Kempe-Kleinberg-Tardos 2003, [I2] Goldenberg 2001 | [I3] Saito ICDM 2008, [I5] Cheng WWW 2014, [I7] Du NeurIPS 2013 | 节点计数 + 时间衰减 + CascadeSwitch volume_forecast | ✗ 工程 |

### 17.2 关键观察

**(1) 关键技术二的精确边界**

> 6 个子功能里，**只有"趋势预测"承载关键技术二的科学贡献**。其他 5 个子功能虽然各自有研究领域，但在 CogGuard 系统中以工程方式实现，不要求科学创新。

**(2) 文献覆盖度盘点**

| 子功能 | 文献覆盖 | 数据集覆盖 | 实现状态 |
|--------|---------|----------|---------|
| 趋势预测 | ✅ 完整（含奠基+SOTA+**事件增强 TSF 主线**+对手） | ⚠️ 仅模式 A 数据集，模式 B 待补 Weibo-COVID19 / Event-Centric Sentiment TS | ✅ WP1-3 完成 |
| 用户画像 | ✅ 本次补全 | ⚠️ 部分依赖 mediacrawler 真实数据 | △ 雏形 |
| 立场检测 | ✅ 完整 | ⚠️ 待补 SemEval / VAST / C-Stance | ❌ 未启动 |
| 危害性评估 | ✅ 本次补全（含 Llama Guard、COLD 等中文） | ✅ 本次补全（COLD/HateXplain/ToxiGen） | ❌ 未启动 |
| 源头追溯 | ✅ 本次补全（Shah & Zaman, NETSLEUTH） | ⚠️ 通常用合成网络验证 | ✅ propagation_legacy.py 已实现 |
| 范围估计 | ✅ 本次补全（Kempe et al.） | ⚠️ 用合成 IC/LT 网络验证 | △ 雏形 |

**(3) 与其他 KT 的协作关系**

| 子功能 | 上游依赖 | 下游消费者 |
|--------|---------|----------|
| 趋势预测 | KT1 协同检测信号（kol_ratio/coordinated_burst） | KT3 风险评估（消费 volume_forecast） |
| 用户画像 | KT1 协同集群 | 趋势预测（提供 KOL 占比） |
| 立场检测 | 内容采集 | KT3 风险评估（立场极化作为危害指标） |
| 危害性评估 | 立场检测（多极化 → 高危害先验） | KT3 风险评估（直接消费） |
| 源头追溯 | 趋势预测（确定监控对象） | 系统报告（提供"是谁先发的"证据） |
| 范围估计 | 趋势预测（共享 ts_features） | 系统报告（提供"已扩散到多少人"数字） |

### 17.3 论文/答辩材料的章节映射建议

**关键技术二章节**（论文核心）：
- 仅写 CascadeSwitch（趋势预测）
- 引用文献：F1-F5、C1-C8、H1-H3、L1-L5、LC1-LC3
- 不要把立场/危害/画像/源头追溯/范围估计写进关键技术章节

**系统设计文档**（功能完整性）：
- 6 子功能逐一描述
- 每个子功能引用对应的研究领域文献做"借鉴说明"，不做创新论证
- 把 KT2 标注在"趋势预测"那个子功能上

**评审材料**（问答准备）：
- 核心问题"关键技术二的创新点是什么"——只回答 CascadeSwitch
- 拓展问题"系统功能的依据是什么"——按本表给出文献引用清单

---

## 19. 文献-设计映射表

> 这张表用于回应 reviewer "为什么这样设计"——每个设计要素都对应至少一篇文献支撑。

| CascadeSwitch 设计要素 | 主要文献支撑 | 二级支撑 |
|----------------------|-------------|---------|
| **回归切换框架** | [F1] Hamilton 1989 | [F4] Bengio & Frasconi 1995 |
| **4 体制（seeding/amp/peak/decay）** | [F2] Bass 1969 | [F3] Rogers 2003 |
| **加权混合预测 ŷ = Σ p(z)·f_z** | [F5] Jacobs et al. 1991 | [F1] |
| **W 矩阵 + softmax 后验**（协变量条件转移） | [F4] Bengio & Frasconi 1995 | [F5] |
| **事件作为外生条件** | [H1] Rizoiu et al. HIP 2017 | [H2] SEISMIC |
| **事件增强 TSF 路线合法性** | [E-T1] Reflection 2024, [E-T2] Internet Traffic 2025 | [E-T3] Massive Training, [C9] CasFT |
| **LLM 不做数值，只做事件** | [L4] Tan et al. NeurIPS 2024, [L6] Controlled Study 2025 | [L5] Rethinking, [L7][L8] FM 综述 |
| **JSON schema 多投票事件抽取** | [E2] schema-guided IE | [E1] LLM-IE 综述 |
| **零训练 vs 端到端 baseline** | [LC1] AutoCast LLM 2025（对手） | [C7] CasTemp 2025, [C9] CasFT |
| **MSLE / direction accuracy 评估** | [C1] DeepHawkes | [C2] DeepCas |
| **跨平台泛化（Weibo→Twitter）** | [C4] CasFlow | [C7] CasTemp |
| **可解释 + 中文解释输出** | [R3] dEFEND（可解释先例） | [P1] 知微（产业可解释惯例） |
| **早期预测协议**（t_obs ∈ {0.5h, 1h, ...}） | [C1] DeepHawkes 设定 | [R5] Early Rumor Detection |
| **propagation_legacy 源头追溯** | [O1] Shah & Zaman 2011（Rumor Centrality） | [O2] NETSLEUTH, [G1] Taxidou 2018 |
| **范围估计** | [I1] Kempe-Kleinberg-Tardos 2003 | [I3] Saito ICDM 2008, [I5] Cheng WWW 2014 |
| **用户画像 KOL 度量** | [U1] Cha ICWSM 2010 | [U2] TwitterRank, [U3] Bakshy WSDM 2011 |
| **危害性评估（中文）** | [D7] COLD | [D5] Llama Guard, [D2] HateXplain |
| **bot 群体占比扩展** | [B2] TwiBot-22 | [B3] MGTAB |
| **立场扩展** | [S1] SemEval-2016 | [LC3] Collaborative Stance |
| **谣言扩展** | [R1] Bi-GCN AAAI 2020 | [R4] Ma et al. ACL 2018 |

---

## 20. 引用快速复制（BibTeX 占位）

```bibtex
@article{hamilton1989new,
  title={A new approach to the economic analysis of nonstationary time series and the business cycle},
  author={Hamilton, James D},
  journal={Econometrica},
  volume={57}, number={2}, pages={357--384}, year={1989}
}

@article{bass1969new,
  title={A new product growth model for consumer durables},
  author={Bass, Frank M},
  journal={Management Science},
  volume={15}, number={5}, pages={215--227}, year={1969}
}

@inproceedings{cao2017deephawkes,
  title={DeepHawkes: Bridging the Gap between Prediction and Understanding of Information Cascades},
  author={Cao, Qi and Shen, Huawei and Cen, Keting and Ouyang, Wentao and Cheng, Xueqi},
  booktitle={CIKM}, year={2017}
}

@inproceedings{li2017deepcas,
  title={DeepCas: An End-to-end Predictor of Information Cascades},
  author={Li, Cheng and Ma, Jiaqi and Guo, Xiaoxiao and Mei, Qiaozhu},
  booktitle={WWW}, year={2017}
}

@article{tan2024llmts,
  title={Are Language Models Actually Useful for Time Series Forecasting?},
  author={Tan, Mingtian and Merrill, Mike A and Gupta, Vinayak and Althoff, Tim and Hartvigsen, Tom},
  journal={NeurIPS}, year={2024}
}

@inproceedings{bian2020rumor,
  title={Rumor Detection on Social Media with Bi-Directional Graph Convolutional Networks},
  author={Bian, Tian and Xiao, Xi and Xu, Tingyang and Zhao, Peilin and Huang, Wenbing and Rong, Yu and Huang, Junzhou},
  booktitle={AAAI}, year={2020}
}

@inproceedings{rizoiu2017expecting,
  title={Expecting to be HIP: Hawkes Intensity Processes for Social Media Popularity},
  author={Rizoiu, Marian-Andrei and Xie, Lexing and Sanner, Scott and others},
  booktitle={WWW}, year={2017}
}

@inproceedings{feng2022twibot,
  title={TwiBot-22: Towards Graph-Based Twitter Bot Detection},
  author={Feng, Shangbin and others},
  booktitle={NeurIPS Datasets and Benchmarks}, year={2022}
}

@inproceedings{kempe2003maximizing,
  title={Maximizing the spread of influence through a social network},
  author={Kempe, David and Kleinberg, Jon and Tardos, {\'E}va},
  booktitle={KDD}, year={2003}
}

@article{shah2011rumors,
  title={Rumors in a network: Who's the culprit?},
  author={Shah, Devavrat and Zaman, Tauhid},
  journal={IEEE Transactions on Information Theory},
  volume={57}, number={8}, pages={5163--5181}, year={2011}
}

@inproceedings{cha2010measuring,
  title={Measuring user influence in Twitter: The million follower fallacy},
  author={Cha, Meeyoung and Haddadi, Hamed and Benevenuto, Fabricio and Gummadi, Krishna P},
  booktitle={ICWSM}, year={2010}
}

@inproceedings{weng2010twitterrank,
  title={TwitterRank: Finding topic-sensitive influential Twitterers},
  author={Weng, Jianshu and Lim, Ee-Peng and Jiang, Jing and He, Qi},
  booktitle={WSDM}, year={2010}
}

@inproceedings{davidson2017automated,
  title={Automated hate speech detection and the problem of offensive language},
  author={Davidson, Thomas and Warmsley, Dana and Macy, Michael and Weber, Ingmar},
  booktitle={ICWSM}, year={2017}
}

@inproceedings{mathew2021hatexplain,
  title={HateXplain: A benchmark dataset for explainable hate speech detection},
  author={Mathew, Binny and Saha, Punyajoy and Yimam, Seid Muhie and others},
  booktitle={AAAI}, year={2021}
}

@article{inan2023llamaguard,
  title={Llama Guard: LLM-based input-output safeguard for human-AI conversations},
  author={Inan, Hakan and Upasani, Kartikeya and Chi, Jianfeng and others},
  journal={arXiv preprint arXiv:2312.06674}, year={2023}
}

@inproceedings{deng2022cold,
  title={COLD: A benchmark for Chinese offensive language detection},
  author={Deng, Jiawen and Zhou, Jingyan and Sun, Hao and Mi, Fei and Huang, Minlie},
  booktitle={EMNLP}, year={2022}
}

@inproceedings{prakash2012spotting,
  title={Spotting culprits in epidemics: How many and which ones?},
  author={Prakash, B Aditya and Vreeken, Jilles and Faloutsos, Christos},
  booktitle={ICDM}, year={2012}
}

@article{pinto2012locating,
  title={Locating the source of diffusion in large-scale networks},
  author={Pinto, Pedro C and Thiran, Patrick and Vetterli, Martin},
  journal={Physical Review Letters}, volume={109}, number={6}, year={2012}
}

@inproceedings{cheng2014cascades,
  title={Can cascades be predicted?},
  author={Cheng, Justin and Adamic, Lada and Dow, P Alex and Kleinberg, Jon and Leskovec, Jure},
  booktitle={WWW}, year={2014}
}

@article{goldenberg2001talk,
  title={Talk of the network: A complex systems look at the underlying process of word-of-mouth},
  author={Goldenberg, Jacob and Libai, Barak and Muller, Eitan},
  journal={Marketing Letters}, volume={12}, number={3}, year={2001}
}

@article{kleinberg1999authoritative,
  title={Authoritative sources in a hyperlinked environment},
  author={Kleinberg, Jon M},
  journal={Journal of the ACM}, volume={46}, number={5}, year={1999}
}

@inproceedings{bakshy2011everyones,
  title={Everyone's an influencer: Quantifying influence on Twitter},
  author={Bakshy, Eytan and Hofman, Jake M and Mason, Winter A and Watts, Duncan J},
  booktitle={WSDM}, year={2011}
}

@inproceedings{leskovec2007cost,
  title={Cost-effective outbreak detection in networks},
  author={Leskovec, Jure and Krause, Andreas and Guestrin, Carlos and Faloutsos, Christos and VanBriesen, Jeanne and Glance, Natalie},
  booktitle={KDD}, year={2007}
}

@article{wang2024integrating,
  title={Integrating Event Analysis in LLM-Based Time Series Forecasting with Reflection},
  author={Wang, Authors of arXiv 2409.17515 and others},
  journal={arXiv preprint arXiv:2409.17515}, year={2024}
}

@article{zhang2024casft,
  title={Future Trend Modeling for Information Popularity Prediction with Dynamic Cues-Driven Diffusion Models},
  author={Authors of arXiv 2409.16619 and others},
  journal={arXiv preprint arXiv:2409.16619}, year={2024},
  note={CasFT}
}

@article{llm2025internet,
  title={Can LLMs Forecast Internet Traffic from Social Media?},
  author={Authors of arXiv 2509.20123 and others},
  journal={arXiv preprint arXiv:2509.20123}, year={2025}
}

@article{advancing2025event,
  title={Advancing Event Forecasting through Massive Training of Large Language Models},
  author={Authors of arXiv 2507.19477 and others},
  journal={arXiv preprint arXiv:2507.19477}, year={2025}
}

@article{controlled2025llmts,
  title={A Controlled Study of LLMs for Time Series Forecasting},
  author={Authors of arXiv 2504.08818 and others},
  journal={arXiv preprint arXiv:2504.08818}, year={2025}
}

@article{foundation2025ts,
  title={Foundation Models for Time Series},
  author={Authors of arXiv 2504.04011 and others},
  journal={arXiv preprint arXiv:2504.04011}, year={2025}
}

@article{empowering2024ts,
  title={Empowering Time Series Analysis with Foundation Models},
  author={Authors of arXiv 2405.02358 and others},
  journal={arXiv preprint arXiv:2405.02358}, year={2024}
}

@article{eventcentric2026,
  title={An Event-Centric Social Media Sentiment Time Series Benchmark with Interaction Structure},
  author={Authors of arXiv 2605.21198 and others},
  journal={arXiv preprint arXiv:2605.21198}, year={2026}
}
```

---

## 21. 检索关键词与待补检索

为后续 `research-lit` / WebSearch 节省时间，记录已知有效的检索关键词组合：

| 检索目标 | 推荐 query |
|---------|-----------|
| Cascade prediction SOTA 2025 | "information cascade prediction" 2025, "popularity prediction" social media |
| LLM × cascade 同期 | "large language model" cascade prediction |
| Regime-switching 时序 | "regime switching" "time series forecasting" |
| Hawkes × 社交 | Hawkes process social media popularity |
| 早期谣言检测 | "early rumor detection" / "early misinformation" |
| 中文级联 + 文本 | Weibo cascade text dataset rumor |
| 立场检测 LLM | LLM stance detection 2025 |
| Bot 群体级 | coordinated bot detection group level |
| 用户影响力 SOTA | user influence Twitter / Weibo measurement 2024 |
| 中文危害检测 | Chinese hate speech offensive detection 2025 |
| LLM 危害检测 | LLM safety classifier hate speech harmful 2024 |
| 谣言源头追溯 | rumor source detection / source localization social network |
| 信息传播取证 | information provenance Twitter Weibo |
| 影响力扩散估计 | influence estimation IC LT model continuous time |
| 范围估计早期信号 | "can cascades be predicted" early signal popularity |
| 事件增强 TSF 主线 | "event-driven" / "event-enhanced" time series forecasting |
| LLM-TS 反思整合 | LLM time series forecasting reflection event reasoning |
| 社交事件→流量预测 | LLM social media internet traffic event forecasting |
| 大规模事件预测 LLM | massive training LLM societal event forecasting |

**待补检索**（下一轮 research-lit 时填入）：

- [ ] WebSearch: "BotDGT" 精确论文与代码
- [ ] WebSearch: "DyCast" 大规模动态图级联
- [ ] WebSearch: "Hawkes-LLM" 联合工作
- [ ] WebFetch: Weibo-COVID19 数据集是否仍可下载
- [ ] WebFetch: 验证所有 arXiv 链接可达

---

## 22. 文档维护

- 新增文献时附"对 KT2 的价值"+"引用方式"两栏
- 引用过的文献在 `KT2_COMPLETE_PLAN.md` / 论文草稿中**用对应编号**（如 [F1], [C4]）以便交叉跟踪
- 数据集状态变化（下载、加载完成、出现损坏）请同步更新到 `TASK_TRACKER.md`
