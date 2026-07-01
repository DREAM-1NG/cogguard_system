# CogGuard 子功能 → 高水平文献 → 数据集 精确映射

> 版本：2026-06-03 ｜ 配套：`doc/PROJECT_OVERVIEW.md`
> 用途：为三大模块的**每个子功能**提供可验证的文献原文链接与数据集链接，供论文写作、答辩问辩、实验选型使用。
> 链接标注：**【已核实】**= WebSearch/WebFetch 确认存在且定位准确；**【存疑】**= 未逐字命中或 ID 可能错配，引用前须人工复核。**所有链接不编造**，存疑项一律标注。

## 如何使用本表

- 每个子功能标注了**落地状态**（已落地 / 设计稿 / 缺口），不要把设计稿或缺口当成已实现去汇报。
- 文献分两类：**方法基准**（本子功能对标/借鉴的高水平工作）与**撞车风险**（已做了相似事情、答辩须主动区分的工作）。
- 数据集按"是否适合该子功能"匹配，部分子功能（尤其 KT3 的阶段预测、DISARM 路径）**缺公开标注数据**，已诚实标明验证只能靠 mock + 案例 + 专家。

## ⚠️ 关键错引纠正（核实后，结题前务必改正）

| 原文档引用（错误） | 核实后真实情况 | 出处 |
|---|---|---|
| Sharma KDD 2021「z-score 显著性」 | 真实方法是 **AMDN-HAGE（神经时序点过程 + 高斯混合隐组模型）**，非 z-score；标题《Identifying Coordinated Accounts...Hidden Influence and Group Behaviours》 | KT1 |
| Tardelli「PNAS 2024 跨平台协同检测」DOI 2313891121 | 实为 **时序 archetype 论文**《Temporal dynamics of coordinated online behavior》，DOI **10.1073/pnas.2307038121**，应归到 Time-variance 维度 | KT1 |
| Cinus「WWW 2025 GNN 端到端协同检测」 | **查无实据**，建议剔除「GNN 端到端」表述，改引 similarity-network 工作 arXiv 2410.22716 / 2409.15402 | KT1 |
| Gruver「LLMs Are Zero-Shot TS Forecasters」arXiv 2310.01728 | 实为 **2310.07820**；2310.01728 是 Time-LLM | KT2 |
| TempCas（列为级联预测基线） | 无可靠出处，**已剔除**以免编造 | KT2 |
| network.py 社区发现「Leiden」 | 代码实为 **greedy_modularity（CNM）**，设计与实现不一致 | KT1 |

## 全局存疑清单（引用前复核）

- KT1：Cinus WWW2025 DOI 3696410.3714818、RGT AAAI article/20314 页号、Post-hoc Influence ACM DOI 3700644、Cresci-2017 直链、AAAI2024 toxicity-KG 页号
- KT2：VaCas(INFOCOM2020) 独立 DOI、Bi-GCN arXiv 2001.06362、Taxidou provenance DOI、PHEME 原始 figshare、（2026 年 arXiv ID 未核未采用）
- KT3：TKDE2024 evidence-aware DOI 10027720、IPM2025 单篇 DOI、SIGIR2023 ACM 路径、arXiv 2410.20140 与 2503.23329 编号、PHEME/SemEval-2016/HateXplain 镜像链接

---

# 第一部分 · KT1 协同发现


> 生成日期：2026-06-03
> 范围：KT1 跨平台协同发现，最新方向「只用共同行为特征做复用融合检测，内容检测不作协同信号」。
> 框架：Mannocci et al. 2024 综述（arXiv 2408.01257）的 **Detection + Characterization 两阶段**，
> Characterization 四维度（authenticity / harmfulness / orchestration / time-variance）已 WebFetch 核实原文确为此四维。
> 链接标注：【已核实】= WebSearch/WebFetch 确认存在并定位准确；【存疑】= 搜不到或与原文不符，须人工复核。

---

## 重要错引纠正（核实结论，先行汇总）

| 原文档引用（错误） | 核实后的真实情况 | 处理建议 |
|---|---|---|
| Sharma et al. KDD 2021「z-score 显著性 / 三通道 z-score」 | 真实标题 **"Identifying Coordinated Accounts on Social Media through Hidden Influence and Group Behaviours"**（Sharma, Zhang, Ferrara, Liu, KDD 2021）。核心方法是 **AMDN-HAGE（神经时序点过程 + 高斯混合隐组模型）**，**不是 z-score**。文档把方法内核写成 z-score 属错误。 | 保留为 baseline，但纠正方法描述为「隐组/点过程生成模型」 |
| Tardelli et al. "PNAS 2024 跨平台协同检测 + 传播互动边"（DOI 2313891121） | 真实是 **"Temporal dynamics of coordinated online behavior: Stability, archetypes, and influence"**（Tardelli, Nizzoli, Tesconi, Conti, Nakov, Da San Martino, Cresci），**PNAS 121(20) 2024，DOI 10.1073/pnas.2307038121**，arXiv 2301.06774。是 **时序 archetype/稳定性** 论文，**非跨平台检测**。文档 DOI 与定位均错。 | 重新归位到 **子功能 8 Time-variance**，DOI 改为 2307038121 |
| Cinus et al. "WWW 2025 GNN 端到端协同检测"（DOI 10.1145/3696410.3714818） | **查无实据**。Cinus 的真实代表作是 **similarity-network**（非端到端 GNN）的跨平台 CIB 检测：Minici/Luceri/Cinus/Ferrara《Uncovering...2024 US Election》(arXiv 2409.15402) 与《Exposing Cross-Platform...》(arXiv 2410.22716)。WWW 2025 GNN 端到端版本未能在检索中证实。 | **剔除「GNN 端到端」表述**；DOI 3696410.3714818 标【存疑】须人工复核是否真为该论文 |
| Alizadeh et al. Science Advances 2020「内容特征」 | 标题/venue 大体可信（内容特征 CIB），但在「内容不作协同信号」的新方向下，本文仅作历史对照，不进核心通道。 | 降级为背景，标注与新方向的张力 |

---

## 落地状态总览（对照代码）

| 代码文件 | 状态 | 覆盖子功能 |
|---|---|---|
| `detector.py`（184 行，已落地） | 已落地 | 1 时间共现、2 共享对象配对、5 部分（配对表→图前置） |
| `network.py`（373 行，已落地） | 已落地 | 5 网络构建 + 社区发现（用 greedy_modularity，**非 Leiden**）、7 orchestration 的桥/核心节点雏形 |
| `stats.py`（142 行，已落地） | 已落地 | 5 account/group 统计、对象类型分类（话题/链接/图片/视频） |
| `significance.py` | **设计稿（未落地）** | 4 显著性筛查 PSL（对称超几何 + Cauchy + BH-FDR） |
| `channels.py` | **设计稿（未落地）** | 2 共享对象通道、3 cascade 通道（roadmap defer） |
| `semantic.py` | **设计稿（未落地）** | 内容语义通道（新方向下作为可选信号，非协同主信号） |
| 无对应文件 | **缺口** | 6 Authenticity（`account_profiler.py` 仅浅层）、8 Time-variance、9 Harmfulness（归 KT3） |

> 注：`network.py` 当前用 networkx `greedy_modularity_communities`（CNM 贪心模块度），与设计文档宣称的 **Leiden** 不一致 —— 这是「设计 vs 实现」的一处裂缝，子功能 5 下标注。

---

# Detection 阶段

## 子功能 1 — 时间同步 / 共现检测（time burst / co-occurrence）

**落地状态：已落地**（`detector.py::detect_groups`，按 `time_window` 秒内同 `object_id` 配对；`flag_speed_share` 做更窄窗口打标）。

### 高水平文献

| 标题 | 作者 | venue+年份 | CCF/级别 | 链接 | 与该子功能的关系 |
|---|---|---|---|---|---|
| Detection and Characterization of Coordinated Online Behavior: A Survey | Mannocci, Mazza, Monreale, Tesconi, Cresci | arXiv 2408.01257, 2024 | 非CCF（综述）| https://arxiv.org/abs/2408.01257 【已核实】 | 框架来源；将「时间同步」列为 detection 的核心行为信号之一 |
| Echoes of the hidden: Uncovering coordination beyond network structure | Somin, Cohen, Kepner, Pentland | arXiv 2504.02757, 2025 | 非CCF | https://arxiv.org/abs/2504.02757 【已核实】 | 证明「共享突发(bursty)活动」可在链接稀疏时识别协同 —— time-burst 的直接理论支撑 |
| Coordinated Inauthentic Behavior and Information Spreading on Twitter | Nizzoli/Cresci 团队 | arXiv 2503.15720 | 非CCF | https://arxiv.org/abs/2503.15720 【已核实】 | 同步性定义「unexpected/suspicious similarity」，含时间维度 |
| Identifying Coordinated Accounts ... Hidden Influence and Group Behaviours | Sharma, Zhang, Ferrara, Liu | **KDD 2021** | **CCF-A** | https://arxiv.org/abs/2008.11308 【已核实】 | 时序点过程建模账号活动同步性（注：非 z-score，已纠正） |

### 数据集

| 数据集 | 链接 | 规模 | 为何适合该子功能 |
|---|---|---|---|
| CooRTweet / coordination-network-toolkit | https://github.com/QUT-Digital-Observatory/coordination-network-toolkit 【已核实】 | 工具+示例数据（默认 60s 窗口，支持 co-post/co-tweet）| 直接提供 co-occurrence 时间窗实现与示例，作 detector.py 对照基准 |
| Seckin IO Labeled Datasets | https://arxiv.org/abs/2411.10609 【已核实】（论文页无直链，数据需正文/联系作者）| 26 campaign，303k 账号，13M+ 帖（含同时段有机对照）| 有 ground-truth 协同 vs 有机，可校验「同时段突发」是否真协同 |

---

## 子功能 2 — 共享对象通道（co-URL / co-hashtag / 共媒体指纹 id）

**落地状态：已落地（基础）+ 设计稿（扩展）**。`detector.py` 已按 `object_id` 配对；`stats.py::_classify_object` 已分类话题/链接/图片/视频。`channels.py::extract_object_channel` 为设计稿（未落地）。

### 高水平文献

| 标题 | 作者 | venue+年份 | CCF/级别 | 链接 | 与该子功能的关系 |
|---|---|---|---|---|---|
| Uncovering Coordinated Cross-Platform Information Operations (2024 US Election) | Minici, Luceri, Cinus, Ferrara | First Monday 29(11) 2024 / arXiv 2409.15402 | 非CCF（社区高影响）| https://arxiv.org/abs/2409.15402 【已核实】 | 核心信号即 **link-sharing（co-URL）** 相似网络，跨 X/YouTube/Web |
| Exposing Cross-Platform Coordinated Inauthentic Activity (Run-Up 2024 US Election) | Cinus, Minici, Luceri, Ferrara | arXiv 2410.22716, 2024 | 非CCF | https://arxiv.org/abs/2410.22716 【已核实】 | similarity network（含 co-link）跨 X/Facebook/Telegram；新方向「共同行为特征复用融合」的范本 |
| CIB on TikTok: Challenges and Opportunities for Detection in a Video-First Ecosystem | Luceri 等 | arXiv 2505.10867, 2025 | 非CCF | https://arxiv.org/abs/2505.10867 【已核实】 | co-caption / **multimedia content reuse（共媒体指纹）** / co-hashtag 的最新定义 |

### 数据集

| 数据集 | 链接 | 规模 | 为何适合该子功能 |
|---|---|---|---|
| Seckin IO Labeled Datasets | https://arxiv.org/abs/2411.10609 【已核实】 | 26 campaign / 13M 帖 | 含 URL/hashtag 重用的标注 campaign，适合 co-URL/co-hashtag 验证 |
| CooRTweet toolkit（co-link/co-tweet 网络类型）| https://github.com/QUT-Digital-Observatory/coordination-network-toolkit 【已核实】 | 工具+示例 | 内置 co-link 网络构建，直接对照共享对象通道 |
| IRA russian-troll-tweets | https://github.com/fivethirtyeight/russian-troll-tweets 【已核实】 | ~300 万条 troll 推文 | 含大量重复 URL/hashtag 推送，co-object 信号强 |

---

## 子功能 3 — 共转发 / 回复级联通道（co-retweet / reply cascade）

**落地状态：roadmap defer（未落地）**。设计文档 §6.4 将 Cascade Channel（reply chain → root_post_id）列为 P2，不进 MVP。

### 高水平文献

| 标题 | 作者 | venue+年份 | CCF/级别 | 链接 | 与该子功能的关系 |
|---|---|---|---|---|---|
| Coordinated Reply Attacks in Influence Operations: Characterization and Detection | Pote, Elmas, Flammini, Menczer | **ICWSM 2025** | **CCF-B** | https://ojs.aaai.org/index.php/ICWSM/article/view/35889 【已核实】 | 专门刻画 **reply 级联** 协同攻击的检测（原文档 "Evidence-Based" 标题有误，已纠正为本文） |
| Uncovering Coordinated Cross-Platform IO (2024 US Election) | Minici, Luceri, Cinus, Ferrara | First Monday 2024 / arXiv 2409.15402 | 非CCF | https://arxiv.org/abs/2409.15402 【已核实】 | 含 co-retweet / 转发放大网络分析 |
| CooRTweet toolkit（co-retweet / co-reply 网络类型）| QUT Digital Observatory | 开源工具 2024 | 非CCF（工具）| https://github.com/QUT-Digital-Observatory/coordination-network-toolkit 【已核实】 | 直接支持 co-retweet / co-reply 网络类型，是该通道的参考实现 |

### 数据集

| 数据集 | 链接 | 规模 | 为何适合该子功能 |
|---|---|---|---|
| IRA russian-troll-tweets | https://github.com/fivethirtyeight/russian-troll-tweets 【已核实】 | ~300 万条 | 含 retweet/reply 链，经典协同级联案例 |
| Seckin IO Labeled Datasets | https://arxiv.org/abs/2411.10609 【已核实】 | 26 campaign | 多 campaign 含 reply/retweet 网络结构标注 |

---

## 子功能 4 — 显著性筛查 PSL（对称超几何 + Cauchy combination + pair-level BH-FDR）

**落地状态：设计稿（未落地）**。`significance.py` 设计接口 `symmetric_pair_pvalue` / `cauchy_combine` / `bh_fdr`（systemDesign §6.6），代码尚未实现。目标：抑制热门话题自然共振误报。

### 高水平文献

| 标题 | 作者 | venue+年份 | CCF/级别 | 链接 | 与该子功能的关系 |
|---|---|---|---|---|---|
| Cauchy Combination Test: A Powerful Test With Analytic p-Value Calculation Under Arbitrary Dependency Structures | Liu & Xie | **JASA 2020** | 非CCF（统计顶刊）| https://www.tandfonline.com/doi/full/10.1080/01621459.2018.1554485 【已核实】 | PSL 的多通道 p 值融合核心工具（任意依赖下有效）|
| Controlling the False Discovery Rate (BH procedure) | Benjamini & Hochberg | JRSS-B 1995 | 非CCF（统计经典）| https://www.jstor.org/stable/2346101 【已核实】 | pair-level FDR 校准的理论依据 |
| Identifying Coordinated Accounts ... Hidden Influence and Group Behaviours | Sharma, Zhang, Ferrara, Liu | **KDD 2021** | **CCF-A** | https://arxiv.org/abs/2008.11308 【已核实】 | 直接对比 baseline（PSL 用对称超几何 + Cauchy 替代其隐组生成模型的显著性判定）|
| Echoes of the hidden: Uncovering coordination beyond network structure | Somin, Cohen, Kepner, Pentland | arXiv 2504.02757, 2025 | 非CCF | https://arxiv.org/abs/2504.02757 【已核实】 | 论证「观察 vs 期望」突发显著性优于纯结构法，支撑 PSL 的统计意义 |
| Identifying Coordinated Activities Using Contrast Pattern Mining | Manchanayaka, Zaidi, Karunasekera, Leckie | IJCNN 2024 / arXiv 2407.11697 | CCF-C（降级标注）| https://arxiv.org/abs/2407.11697 【已核实】 | 「可疑窗口 vs 历史基线」对比范式，与 PSL「观察 vs 期望」同源（pattern level）|

### 数据集

| 数据集 | 链接 | 规模 | 为何适合该子功能 |
|---|---|---|---|
| Seckin IO Labeled Datasets | https://arxiv.org/abs/2411.10609 【已核实】 | 26 campaign，303k 账号，13M 帖（**含 13M 同话题同时段有机对照**）| **最适合 FDR 校准**：有 ground-truth 协同 + 大规模有机对照，可直接量化误报率 |
| CooRTweet toolkit 示例数据 | https://github.com/QUT-Digital-Observatory/coordination-network-toolkit 【已核实】 | 工具+示例 | 提供 baseline 阈值法，作 PSL 显著性提升的对照 |

---

## 子功能 5 — 协同网络构建 + 社区发现（加权图 + Leiden/modularity）

**落地状态：已落地（实现与设计有偏差）**。`network.py::generate_coordinated_network` 构建加权无向图 + 阈值分位裁剪 + 子图提取；社区发现用 **networkx `greedy_modularity_communities`（CNM 贪心模块度）**。
> ⚠ 设计 vs 实现裂缝：设计文档与汇报口径常称 **Leiden**，但代码实际是 greedy modularity。汇报需如实说明，或补一个 Leiden 实现（python-louvain/leidenalg）。

### 高水平文献

| 标题 | 作者 | venue+年份 | CCF/级别 | 链接 | 与该子功能的关系 |
|---|---|---|---|---|---|
| From Louvain to Leiden: guaranteeing well-connected communities | Traag, Waltman, van Eck | **Scientific Reports 2019** | 非CCF（Nature 子刊）| https://www.nature.com/articles/s41598-019-41695-z （arXiv https://arxiv.org/abs/1810.08473）【已核实】 | Leiden 算法原始出处；社区发现升级目标 |
| Exposing Cross-Platform Coordinated Inauthentic Activity | Cinus, Minici, Luceri, Ferrara | arXiv 2410.22716, 2024 | 非CCF | https://arxiv.org/abs/2410.22716 【已核实】 | similarity network → 社区/簇提取的跨平台范本 |
| Uncovering Coordinated Cross-Platform IO (2024 US Election) | Minici, Luceri, Cinus, Ferrara | First Monday 2024 / arXiv 2409.15402 | 非CCF | https://arxiv.org/abs/2409.15402 【已核实】 | 协同网络构建 + 网络属性识别核心账号 |
| Detection and Characterization of Coordinated Online Behavior: A Survey | Mannocci 等 | arXiv 2408.01257, 2024 | 非CCF（综述）| https://arxiv.org/abs/2408.01257 【已核实】 | 综述「网络构建 + 社区发现」为 detection 主流 pipeline |

### 数据集

| 数据集 | 链接 | 规模 | 为何适合该子功能 |
|---|---|---|---|
| IRA russian-troll-tweets | https://github.com/fivethirtyeight/russian-troll-tweets 【已核实】 | ~300 万条 | 已知协同社区结构，适合社区发现验证 |
| Seckin IO Labeled Datasets | https://arxiv.org/abs/2411.10609 【已核实】 | 26 campaign | 多 campaign 提供多个明确社区边界 |
| TwiBot-22 | https://github.com/LuoUndergradXJTU/TwiBot-22 【已核实】（Google Drive 申请制，需机构邮箱）| 1M 用户，含关系图 | 大规模图，可测社区发现可扩展性 |

---

# Characterization 阶段（四维表征）

> 四维度来源已 WebFetch 核实：Mannocci survey (arXiv 2408.01257) 原文明确「four defining dimensions: authenticity, harmfulness, orchestration, and time-variance」。

## 子功能 6 — Authenticity（账号自动化 / bot 程度）

**落地状态：缺口**（`account_profiler.py` 仅浅层自动化评分；CogGuard §1.5 已声明退出 bot 叙事，本维度仅作辅助标注）。

### 高水平文献

| 标题 | 作者 | venue+年份 | CCF/级别 | 链接 | 与该子功能的关系 |
|---|---|---|---|---|---|
| TwiBot-22: Towards Graph-Based Twitter Bot Detection | Feng, Tan, Wan 等 | **NeurIPS 2022 Datasets & Benchmarks** | CCF-A（主会，D&B track）| https://github.com/LuoUndergradXJTU/TwiBot-22 【已核实】 | Authenticity 维度的标准评估基准 + 35 baseline |
| Heterogeneity-Aware Twitter Bot Detection with Relational Graph Transformers (RGT) | Feng 等 | **AAAI 2022** | **CCF-A** | https://ojs.aaai.org/index.php/AAAI/article/view/20314 【存疑：编号需复核】 | 异构关系图 bot 判别（CogGuard non-goal 参考）|
| Dissecting a Social Bot Powered by Generative AI | — | Social Network Analysis and Mining (Springer) 2025 | 非CCF（SCI）| https://link.springer.com/article/10.1007/s13278-025-01410-5 【存疑】 | LLM-bot 时代传统特征失效，需行为模式 → 支撑「不靠内容/靠行为」新方向 |

### 数据集

| 数据集 | 链接 | 规模 | 为何适合该子功能 |
|---|---|---|---|
| TwiBot-22 | https://github.com/LuoUndergradXJTU/TwiBot-22 【已核实】（申请制）| 1M 用户，10M+ 推文 | 最大规模 bot 标注基准，Authenticity 评估首选 |
| Cresci-2017 | https://botometer.osome.iu.edu/bot-repository/datasets.html 【已核实页面存在，但未列出 Cresci-2017 直链；学术申请制】 | ~37k 账号 | 经典 bot 数据，含多种协同自动化模式，适合消融 |

---

## 子功能 7 — Orchestration（组织化程度：中心化 / 去中心化 / 涌现）

**落地状态：缺口（雏形）**。`network.py` 已产出 `bridge_score` / `core_nodes` / `cross_cluster_weight` 等结构指标，可作为 orchestration 的代理特征，但未形成中心化/去中心化分级。

### 高水平文献

| 标题 | 作者 | venue+年份 | CCF/级别 | 链接 | 与该子功能的关系 |
|---|---|---|---|---|---|
| Detection and Characterization of Coordinated Online Behavior: A Survey | Mannocci 等 | arXiv 2408.01257, 2024 | 非CCF（综述）| https://arxiv.org/abs/2408.01257 【已核实】 | 定义 orchestration 三档：centralized / distributed / non-orchestrated |
| Uncovering Coordinated Cross-Platform IO (2024 US Election) | Minici, Luceri, Cinus, Ferrara | First Monday 2024 / arXiv 2409.15402 | 非CCF | https://arxiv.org/abs/2409.15402 【已核实】 | 用网络属性识别 orchestration 的指挥/枢纽结构 |
| Post-hoc Evaluation of Nodes Influence in Information Cascades: Coordinated Accounts | — | arXiv 2401.01684, 2024（DOI 10.1145/3700644）| 非CCF（ACM 期刊）| https://arxiv.org/abs/2401.01684 【已核实 arXiv；ACM DOI 存疑需复核】 | 组织度 ≠ 影响力，需分开评估 |

### 数据集

| 数据集 | 链接 | 规模 | 为何适合该子功能 |
|---|---|---|---|
| IRA russian-troll-tweets | https://github.com/fivethirtyeight/russian-troll-tweets 【已核实】 | ~300 万条 | 国家级 centralized orchestration 的典型样本 |
| GameStop / WallStreetBets（WSBCausality 复现数据）| https://github.com/RiegelGestr/WSBCausality 【已核实】 | Reddit WSB 集体行动数据 | **emergent/去中心化涌现** 协同的对照样本（非国家组织）|
| Seckin IO Labeled Datasets | https://arxiv.org/abs/2411.10609 【已核实】 | 26 campaign（多国家/平台）| 跨多 orchestration 类型，适合分级标注 |

---
## 子功能 8 — Time-variance（时序模式 archetype：stable / bursty / adaptive / dormant）

**落地状态：缺口**。`detector.py::flag_speed_share` 有多窗口打标雏形，但无 archetype 分类。

### 高水平文献

| 标题 | 作者 | venue+年份 | CCF/级别 | 链接 | 与该子功能的关系 |
|---|---|---|---|---|---|
| **Temporal dynamics of coordinated online behavior: Stability, archetypes, and influence** | Tardelli, Nizzoli, Tesconi, Conti, Nakov, Da San Martino, Cresci | **PNAS 121(20) 2024** | 非CCF（综合顶刊）| https://www.pnas.org/doi/10.1073/pnas.2307038121 （arXiv 2301.06774）【已核实】 | **本维度核心文献**（原文档误标「跨平台检测」，实为时序 archetype/稳定性，已归位并修正 DOI）|
| Echoes of the hidden: Uncovering coordination beyond network structure | Somin, Cohen, Kepner, Pentland | arXiv 2504.02757, 2025 | 非CCF | https://arxiv.org/abs/2504.02757 【已核实】 | bursty 活动模式作为时序 archetype 的判别信号 |
| Insights into Using Temporal Coordinated Behaviour ... Influence | — | **Findings of EMNLP 2025** | CCF-B（Findings）| https://aclanthology.org/2025.findings-emnlp.1325/ 【条目已核实；建议用 aclanthology 链接】 | 时序协同模式与影响力关联 |

### 数据集

| 数据集 | 链接 | 规模 | 为何适合该子功能 |
|---|---|---|---|
| Seckin IO Labeled Datasets | https://arxiv.org/abs/2411.10609 【已核实】 | 26 campaign（多时段）| 多 campaign 横跨不同时间窗，适合提取 stable/bursty/dormant archetype |
| IRA russian-troll-tweets | https://github.com/fivethirtyeight/russian-troll-tweets 【已核实】 | ~300 万条（含时间戳）| 长周期数据，适合 time-variance 建模 |

---

## 子功能 9 — Harmfulness（内容毒性）— **归属 KT3，此处仅标注**

**落地状态：归属 KT3（不在 KT1 实现）**。按闭环分工，内容毒性/危害性评估归 KT3 多 Agent 编排；KT1 仅传递协同群组与证据边。此处给代表文献以备汇报衔接。

### 高水平文献（代表，仅作衔接）

| 标题 | 作者 | venue+年份 | CCF/级别 | 链接 | 与该子功能的关系 |
|---|---|---|---|---|---|
| The Influence of Coordinated Behavior on Toxicity | Mannocci, Cresci 等 | arXiv 2310.01283, 2023 | 非CCF | https://arxiv.org/abs/2310.01283 【已核实】 | 直接连接 Detection（协同）与 Harmfulness（毒性）的因果链，是 KT1→KT3 衔接论据 |
| Supporting Online Toxicity Detection with Knowledge Graphs | — | AAAI 2024 | CCF-A | https://aaai.org/papers/ 【存疑：具体页号未核实】 | KT3 毒性评估方法参考（隐式毒性）|

### 数据集

| 数据集 | 链接 | 规模 | 为何适合该子功能 |
|---|---|---|---|
| （归 KT3）| — | — | KT1 不直接用毒性数据集；由 KT3 选型 |

---

## 附：链接核实状态清单

**【已核实】可直接使用：**
- arXiv 2408.01257（Mannocci survey，四维度原文确认）
- arXiv 2301.06774 / PNAS 10.1073/pnas.2307038121（Tardelli temporal archetype，7 位作者已核实）
- arXiv 2410.22716、2409.15402（Cinus/Minici 跨平台 CIB，similarity network）
- arXiv 2505.10867（Luceri TikTok CIB）
- arXiv 2411.10609（Seckin IO datasets，26 campaign/303k 账号/13M 帖已核实）
- arXiv 2008.11308（Sharma KDD 2021，方法 AMDN-HAGE 非 z-score，已纠正）
- arXiv 2504.02757（Somin bursty coordination）
- arXiv 2310.01283（toxicity-coordination）
- ICWSM 2025 view/35889（Pote reply attacks）
- github.com/LuoUndergradXJTU/TwiBot-22（申请制）
- github.com/QUT-Digital-Observatory/coordination-network-toolkit
- github.com/fivethirtyeight/russian-troll-tweets（IRA）
- github.com/RiegelGestr/WSBCausality（GameStop/WSB）
- Leiden: nature s41598-019-41695-z / arXiv 1810.08473

**【存疑】须人工复核：**
- ⚠ **Cinus WWW 2025 GNN 端到端**（DOI 10.1145/3696410.3714818）：检索无法证实「GNN 端到端协同检测」论文存在；ACM 页 403 无法打开。**建议剔除该表述**，改引 arXiv 2410.22716 / 2409.15402。
- ⚠ RGT AAAI 2022 article/20314：页号未二次核实
- ⚠ Post-hoc Influence ACM DOI 10.1145/3700644（arXiv 2401.01684 本体已核实）
- ⚠ Cresci-2017 直链：botometer 页存在但未列该数据集直链（学术申请制）
- ⚠ AAAI 2024 toxicity-KG 页号、Springer GenAI-bot 链接

**【已纠正错引】：** Sharma 方法（z-score → AMDN-HAGE）、Tardelli 定位（跨平台检测 → 时序 archetype，DOI 修正）、Cinus（剔除 GNN 端到端表述）、network.py 社区发现（文档称 Leiden → 代码实为 greedy modularity）。

---

# 第二部分 · KT2 传播监控


> 生成日期：2026-06-03
> 范围：KT2 = 传播监控；关键技术 "LLM + 时序预测"；核心方案 **CascadeSwitch**（事件条件体制切换级联规模预测）；功能形态借鉴知微(Zhiwei)。
> 链接标注：**【已核实】** = 本轮 WebSearch 实际命中标题/venue/作者一致；**【存疑】** = 文档给出但本轮未逐字命中或 ID 可能错配。
> 代码落地状态依据 `new-system/backend/app/core/propagation/` 与 `propagation_legacy.py` 实读。

## 落地状态总览

| 子功能 | 代码文件 | 状态 |
|---|---|---|
| 1. 时序特征工程 | `propagation/ts_features.py` | 已落地 |
| 2. LLM 事件抽取 | `propagation/llm_context.py` | 已落地（在线默认 `mock=True`/无 API_KEY 走中性结果，真实 API 通路已写未接） |
| 3. 体制切换级联规模预测 CascadeSwitch | `propagation/regime_model.py` + `trend_predictor.py` | 已落地（4 体制 + softmax 后验混合，零训练） |
| 4. 传播子图 + 关键角色识别 | `propagation_legacy.py` | 已落地（起爆/桥接/扩散 + 源头追溯） |
| 5. 证据链 + 关键路径回溯 | `propagation_legacy.py` | 已落地（**已观测图回溯，非预测**） |
| 6. 传播路径预测（next-node/未来路径结构） | — | **缺口（无设计无代码）**，须与子功能 5 的"路径回溯"严格区分 |

---

## 子功能 1：时序特征工程（volume / velocity / acceleration / burst_zscore）

落地状态：**已落地**（`ts_features.py::extract_ts_features`，小时聚合 → 速度/加速度/突发 z-score）。

高水平文献表：

| 标题 | 作者 | venue+年份 | 链接 | 与该子功能关系 |
|---|---|---|---|---|
| Are Language Models Actually Useful for Time Series Forecasting? | Tan, Merrill, Gupta, Althoff, Hartvigsen | NeurIPS 2024 (Spotlight) | https://arxiv.org/abs/2406.16964 【已核实】 | 论证纯 LLM 数值预测不可靠 → 为"轻量时序特征 + 体制模型"而非端到端 LLM 预测提供动机 |
| DeepHawkes: Bridging the Gap between Prediction and Understanding of Information Cascades | Cao, Shen, Cen, Ouyang, Cheng | CIKM 2017 | https://dl.acm.org/doi/10.1145/3132847.3132973 【已核实】 | 级联早期时序/转发轨迹特征的经典刻画，本模块按小时聚合的特征工程对标其观测窗设定 |

数据集表：

| 数据集 | 链接 | 规模/格式 | 为何适合 |
|---|---|---|---|
| Sina Weibo (DeepHawkes) | https://github.com/CaoQi92/DeepHawkes 【已核实】 | ~119K 级联；`mid\tuid\ttimestamp\tretweet_path` | 含逐条转发时间戳，可直接按小时聚合出 volume/velocity/acceleration |
| CasFlow (Weibo/Twitter/APS) | https://github.com/Xovee/casflow 【已核实】 | ~12 万级联 + 时间戳 | 多平台时间戳轨迹，验证时序特征跨平台稳定性 |

---

## 子功能 2：LLM 事件抽取（6 类外生事件 + 多数投票）

落地状态：**已落地但默认 mock**。`llm_context.py::extract_events` 支持 OpenAI 兼容 API（默认 `api.deepseek.com/v1`）+ 3 次多数投票 + JSON 校验；但 `mock=True` 或缺 `LLM_API_KEY` 时返回中性结果，在线真实 API **尚未接入**。6 类事件：kol_amplification / official_response / platform_intervention / narrative_mutation / coordinated_burst / none。

高水平文献表：

| 标题 | 作者 | venue+年份 | 链接 | 与该子功能关系 |
|---|---|---|---|---|
| Time-LLM: Time Series Forecasting by Reprogramming Large Language Models | Jin, Wang, Ma, et al. | ICLR 2024 | https://arxiv.org/abs/2310.01728 【已核实】 | LLM 作为时序"上下文/语义编码器"的范式来源，对应本模块以 LLM 提取外生事件供时序模型条件化 |
| Large Language Models Are Zero-Shot Time Series Forecasters (LLMTime) | Gruver, Finzi, Qiu, Wilson | NeurIPS 2023 | https://arxiv.org/abs/2310.07820 【已核实，注：文档[1]误标 2310.01728，正确 ID 为 2310.07820】 | LLM 零样本处理序列/数值的能力边界，支撑"LLM 仅做事件抽取、不做数值外推"的分工 |
| Autoregressive Cascade Predictor in Social Networks via LLMs (AutoCas) | Zheng, Gong, Sun, Zhang, Pan, Lyu | arXiv 2025 | https://arxiv.org/abs/2502.18040 【已核实】 | LLM 直接驱动级联预测的最新代表，作为"LLM 介入级联"路线的高水平对照 |

数据集表：

| 数据集 | 链接 | 规模/格式 | 为何适合 |
|---|---|---|---|
| CogGuard mock_weibo（本系统内生成） | 系统内合成，无外链 | 可控生成、含帖子正文 | 仅有内容文本时才能验证 LLM 事件抽取（模式 B）；公开级联数据集多无正文 |

> 诚实说明：本子功能在线默认走 mock，真实 LLM 事件抽取仅在 CogGuard 自有含正文数据上演示过通路，**未在公开数据集上做过事件抽取实验**（公开级联数据通常脱敏无正文）。

---

## 子功能 3：体制切换级联规模预测 CascadeSwitch

落地状态：**已落地**（`regime_model.py` 4 体制参数化模型 + W 矩阵 + softmax 后验；`trend_predictor.py` 编排）。4 体制：seeding(线性) / amplification(指数) / peak(logistic) / decay(指数衰减)；后验 `p(z)=softmax((W·e+b)/τ)`，混合预测 `ŷ=Σ p(z)·f_z`，零训练、可解释。

高水平文献表：

| 标题 | 作者 | venue+年份 | 链接 | 与该子功能关系 |
|---|---|---|---|---|
| DeepCas: An End-to-end Predictor of Information Cascades | Li, Ma, Guo, Mei | WWW 2017 | https://arxiv.org/abs/1611.05373 【已核实】 | 级联规模预测任务的奠基工作，定义观测窗→最终规模设定，本方案的标准任务对标 |
| DeepHawkes | Cao, Shen, Cen, Ouyang, Cheng | CIKM 2017 | https://dl.acm.org/doi/10.1145/3132847.3132973 【已核实】 | Hawkes 自激点过程 + 深度学习；本方案"参数化体制 + 后验混合"是其可解释零训练替代 |
| Information Diffusion Prediction via Recurrent Cascades Convolution (CasCN) | Chen, Zhou, Zhang, et al. | ICDE 2019 | https://ieeexplore.ieee.org/document/8731564 ；代码 https://github.com/ChenNed/CasCN 【已核实】 | 主流深度基线之一，文献数值对照 |
| CasFlow: Exploring Hierarchical Structures and Propagation Uncertainty for Cascade Prediction | Xu, Zhou, Xu, Zhang, et al. | IEEE TKDE 2021 | https://ieeexplore.ieee.org/document/9611000/ ；代码 https://github.com/Xovee/casflow 【已核实】 | 显式建模传播不确定性；本方案以混合方差 σ² 输出置信区间，正面对照其不确定性建模 |
| VaCas (Variational Information Diffusion for Probabilistic Cascade Prediction) | Xu et al. | INFOCOM 2020 | https://www.xoveexu.com/pub 【存疑：作者主页确认存在，未单独核到 DOI/arXiv 独立页】 | 概率化级联预测基线，文档列为"引用数值不重跑"基线 |
| CasFT: Future Trend Modeling for Information Popularity Prediction with Dynamic Cues-Driven Diffusion Models | (见 arXiv) | arXiv 2024 | https://arxiv.org/abs/2409.16619 【已核实】 | 用 neural ODE 抽取动态线索引导未来增量生成；与本方案"事件线索驱动体制"思路同源的最新工作 |
| Are LLMs Actually Useful for Time Series Forecasting? | Tan et al. | NeurIPS 2024 | https://arxiv.org/abs/2406.16964 【已核实】 | 为"不用 LLM 做数值外推、改用透明体制模型"的核心设计决策提供文献支撑 |

> 文档第 5 节列出的 TempCas 未单独核实到权威出处，本表暂不列入以免编造；CasTemp(arXiv 2510.25348)为搜索中出现的相邻新作，非文档原引用，仅备注。

数据集表：

| 数据集 | 链接 | 规模/格式 | 为何适合 |
|---|---|---|---|
| Sina Weibo (DeepHawkes) | https://github.com/CaoQi92/DeepHawkes 【已核实】 | ~119K 级联 | 规模预测主实验，转发轨迹即标签，无需额外标注 |
| CasFlow (Weibo/Twitter/APS) | https://github.com/Xovee/casflow 【已核实】 | Weibo~12万 / Twitter~3万 / APS | 交叉验证 + 跨平台泛化（Twitter 不重调参） |
| 级联数据集汇总 (A Survey of Datasets for Information Diffusion Tasks) | https://github.com/fuxiaG/Information-Diffusion-Datasets 【已核实，配套论文 arXiv 2407.05161】 | 多数据集索引 | 选型与属性对照（用户/内容六维属性） |
| 级联建模方法+数据汇总 | https://github.com/ChenNed/Awesome-DL-Information-Cascades-Modeling 【已核实】 | 方法+数据索引 | 基线与数据集快速定位 |

---

## 子功能 4：传播子图 + 关键角色识别（起爆 / 桥接 / 扩散，源头追溯）

落地状态：**已落地**（`propagation_legacy.py::build_propagation_graph` → `_identify_key_roles`：起爆=出度高入度低、桥接=介数中心性、扩散=入度最高；NetworkX MultiDiGraph）。

高水平文献表：

| 标题 | 作者 | venue+年份 | 链接 | 与该子功能关系 |
|---|---|---|---|---|
| Rumor Detection on Social Media with Bi-Directional Graph Convolutional Networks (Bi-GCN) | Bian, Xiao, Xu, et al. | AAAI 2020 | https://arxiv.org/abs/2001.06362 【存疑：文档列 AAAI 2020，本轮未单独核 arXiv 页，标题/venue 业界通行】 | 传播图双向结构建模的代表，支撑"在传播图上做角色/结构分析"的方法论 |
| FOREST: Multi-scale Information Diffusion Prediction with Reinforced Recurrent Networks | Yang, Tang, et al. | IJCAI 2019 | https://www.ijcai.org/Proceedings/2019/560 ；代码 https://github.com/albertyang33/FOREST 【已核实】 | 微观+宏观传播结构联合建模，为关键角色/传播结构分析提供数据与方法参照 |

数据集表：

| 数据集 | 链接 | 规模/格式 | 为何适合 |
|---|---|---|---|
| FOREST (Twitter/Douban) | https://github.com/albertyang33/FOREST 【已核实，IJCAI 2019 源码库】 | 级联序列（含用户级转发关系） | 含转发参与者序列，可重建传播子图、识别起爆/桥接/扩散角色 |
| Twitter15/16（传播树） | https://github.com/gszswork/Twitter15_16_dataset 【已核实，含 `tree/` 子目录每源推文一棵树】 | 传播树结构 + source tweet | 显式树结构，便于角色识别与源头追溯验证 |

---

## 子功能 5：证据链 + 关键路径回溯

落地状态：**已落地**（`propagation_legacy.py::_extract_evidence_chains` / `_extract_key_paths_for_claim`）。
**关键区分：这是对"已观测、已构建好的传播图"做溯源回溯（claim→源头→关键路径→支撑帖），不是对未来路径的预测。** 与子功能 8 严格区分。

高水平文献表：

| 标题 | 作者 | venue+年份 | 链接 | 与该子功能关系 |
|---|---|---|---|---|
| Provenance for Online Information Diffusion | Taxidou, Fischer, et al. | Distributed and Parallel Databases, 2018 | https://link.springer.com/article/10.1007/s10619-017-7205-1 【存疑：期刊与作者通行，本轮未单独核到该 DOI 页】 | 信息扩散溯源(provenance)的直接对标，支撑"证据链/源头追溯"为已观测图上的溯源任务 |
| Rumor Detection on Social Media with Bi-GCN | Bian et al. | AAAI 2020 | https://arxiv.org/abs/2001.06362 【存疑】 | 传播路径作为可解释证据的方法论参照 |

数据集表：

| 数据集 | 链接 | 规模/格式 | 为何适合 |
|---|---|---|---|
| Twitter15/16（传播树） | https://github.com/gszswork/Twitter15_16_dataset 【已核实】 | 每源推文一棵传播树 | 树结构提供天然的"源头→路径→叶节点"，适合证据链/关键路径回溯验证 |
| FOREST | https://github.com/albertyang33/FOREST 【已核实】 | 含转发参与序列 | 可回溯转发链路与关键节点 |

---

## 子功能 6：传播路径预测（next-node / 未来路径结构预测）—— 缺口

落地状态：**缺口（无设计、无代码）**。
**严格区分**：本系统已有的是子功能 5 的"已观测图路径**回溯**（溯源）"，**不是**对未来谁会转发、传播树如何生长的**预测**。当前 CascadeSwitch 只预测**规模(标量)**，不预测**路径结构**。本子功能在 CogGuard 中**完全没有对应实现**，汇报时不可与"路径回溯"混淆。

该方向代表文献（"若要做需要什么"，非本项目成果）：

| 标题 | 作者 | venue+年份 | 链接 | 与该方向关系 |
|---|---|---|---|---|
| Topological Recurrent Neural Network for Diffusion Prediction (Topo-LSTM) | Wang, Shen, Cheng, et al. | arXiv 2017 | https://arxiv.org/abs/1711.10162 【已核实】 | 微观下一跳预测：估计"下一个被激活节点"的概率，正是 next-node 路径预测 |
| Neural Diffusion Model for Microscopic Cascade Prediction (NDM) | Yang, Tang, et al. | arXiv 2018 | https://arxiv.org/abs/1812.08933 【已核实】 | 用户级"谁感染谁"的微观级联预测，预测传播路径结构 |
| DeepDiffuse: Predicting the 'Who' and 'When' in Cascades | Islam, et al. | IEEE ICDM 2018 | https://sanghani.cs.vt.edu/research/publications/2018/deepdiffuse-predicting-the-who-and-when-in-cascades.html 【已核实】 | 同时预测下一个参与者(who)与时间(when)，路径预测经典 |
| FOREST | Yang et al. | IJCAI 2019 | https://www.ijcai.org/Proceedings/2019/560 【已核实】 | 微观路径 + 宏观规模联合，路径预测代表 |

若要做需要的数据：

| 数据集 | 链接 | 规模/格式 | 为何适合 |
|---|---|---|---|
| Twitter15/16（传播树） | https://github.com/gszswork/Twitter15_16_dataset 【已核实】 | 每源推文完整传播树结构 | 路径预测需"谁转发谁"的边级真值；树结构提供监督信号 |
| FOREST (Twitter/Douban) | https://github.com/albertyang33/FOREST 【已核实】 | 含用户级转发序列 | 微观下一跳预测的标准实验数据 |

> 诚实结论：CogGuard 当前**无传播路径预测实现，也无设计文档**。若纳入需新增微观扩散模型（Topo-LSTM/NDM 类）+ 边级真值数据(Twitter15/16/FOREST)，与现有"规模预测(CascadeSwitch)"和"路径回溯(propagation_legacy)"均为不同任务。答辩时应主动声明为未覆盖方向，避免被质疑"路径回溯冒充路径预测"。

---

## 存疑链接清单（需进一步核实，勿在答辩中当作已坐实）

1. **VaCas (INFOCOM 2020)** — 作者主页 https://www.xoveexu.com/pub 确认论文存在，但未核到独立 DOI/arXiv 页。
2. **Bi-GCN (AAAI 2020) arXiv 2001.06362** — 标题/venue 业界通行，本轮未逐字命中 arXiv 页，使用前复核。
3. **Provenance for Online Information Diffusion (Taxidou & Fischer)** — 期刊 Distributed and Parallel Databases 通行，DOI 1007/s10619-017-7205-1 未本轮核到，使用前复核。
4. **PHEME 原始库链接** — 本表给出 PhemePlus 扩展库（含原引用）；原始 PHEME 数据集通常在 figshare，引用时建议补原始 figshare DOI。
5. **TempCas** — 文档第5节列为基线但无可靠出处，本表已剔除以免编造。

## 文档与实读的关键纠偏

- 文档[1]把 Gruver "LLMs Are Zero-Shot TS Forecasters" 标为 arXiv 2310.01728，**实为 2310.07820**；2310.01728 是 Time-LLM。本表已分列纠正。
- 文档[5][11] 等 2026 年 arXiv ID（2602.14744 / 2603.09148）未核实，本表未采用，避免幻觉。
- 子功能 2 在线默认 `mock`，真实 LLM 事件抽取未在公开数据上跑过 —— 这是实现 vs 设计的真实差距。

---

# 第三部分 · KT3 报告研判


> 仓库根：`g:/CISCN/cogguard_system/`；核心代码：`new-system/backend/app/core/risk/`
> 链接标注：【已核实】= 已通过 WebSearch/官方页核实可访问；【存疑】= 未能直接核实或需进一步确认。
> 总叙事：KT3 从 detection 升级到 anticipation + countermeasure。头号创新是已落地的白盒前瞻引擎（Phase-Aware Hazard + DISARM 攻击路径预判 + D-S 融合）；多 Agent + RAG 是编排/呈现层（设计稿）。

---

## 子功能 1：多源证据构建 + 统一证据包

**落地状态：已落地**（`evidence_builder.py`，`build_evidence_pack()`；从 coordination/propagation/accounts 三上游提取窗口特征：协同密度、边对称性、桥接比、突发性 CV、自动化熵、Gini 集中度等）

### 高水平文献

| 标题 | 作者 | venue+年份 | 链接 | 与该子功能关系 |
|------|------|-----------|------|--------------|
| Adversarial Contrastive Learning for Evidence-Aware Fake News Detection | Wu et al. | IEEE TKDE 2024 | https://ieeexplore.ieee.org/document/10027720 【存疑】(检索未直接命中确切卷期，需复核 DOI) | 证据感知建模的学术基础：把上游异质证据结构化为统一表示 |
| Labeled Datasets for Research on Information Operations | Seckin et al. | arXiv 2411.10609, 2024 | https://arxiv.org/abs/2411.10609 【已核实】 | 提供"叙事+网络交互+参与策略"多源标注，对应证据包多维特征构成 |
| Exposing Cross-Platform Coordinated Inauthentic Activity (2024 US Election) | Various | arXiv 2410.22716, 2025 (WWW) | https://arxiv.org/html/2410.22716v3 【已核实】 | 跨平台协同特征工程的近作，支撑证据包中协同/桥接/跨集群特征定义 |

### 数据集

| 数据集/资源 | 链接 | 用途 | 为何适合 |
|------------|------|------|---------|
| IO Labeled Datasets (Seckin 2024) | https://arxiv.org/abs/2411.10609 【已核实】 | 真实协同账户多维特征验证证据包字段 | 含多国 IO 战役标注，可映射到协同/传播/账户三源 |
| 项目自有上游输出（coordination/propagation/accounts 服务） | 本仓库 `new-system/backend` | 证据包的实际输入 | 字段一一对应，已落地集成 |

> 说明：证据构建本身是常见工程，非主创新；价值在于为下游 phase-conditioned 融合提供统一接口。

---

## 子功能 2：Phase-Aware Hazard（5 状态战役生命周期 + logistic hazard）

**落地状态：已落地**（`phase_detector.py`：`classify_phase()` 按优先级规则判定 seed→synchronize→breakout→saturation→regeneration；`estimate_hazard()` 用 logistic `sigmoid(w·features+b)` 估各转换风险；`time_to_breakout_estimate` 指数衰减估计）

### 高水平文献

| 标题 | 作者 | venue+年份 | 链接 | 与该子功能关系 |
|------|------|-----------|------|--------------|
| Multi-agent Systems for the Misinformation Lifecycle | A. Gautam | arXiv 2505.17511, 2025 (ICWSM) | https://arxiv.org/html/2505.17511v1 【已核实】 | "全生命周期"对标：KT3 把生命周期具体化为 5 状态 + hazard 预测，非分类→纠正→溯源 |
| ML Framework for Predicting and Mapping ATT&CK Techniques (phase-aware, Cyber Kill Chain 7 阶段) | — | arXiv 2508.18230, 2025 | https://arxiv.org/html/2508.18230v1 【已核实】 | **方法论原语来源**：phase-aware 多模型 + 阶段间有向图，KT3 是把"阶段感知预测"范式迁移到信息操纵域 |
| A Unified Framework for Multi-Modal Rumor Detection with Evolving Stances | — | IPM 2025 | https://www.sciencedirect.com/journal/information-processing-and-management 【存疑】(期刊主页可达，单篇 DOI 需复核) | 动态演化 + 立场随时间变化，支撑"阶段时序建模"叙事 |

> 创新声明（诚实）：5 状态生命周期是 **operational model 非 descriptive taxonomy**；logistic hazard 是标准生存/危险率思路。新颖处在于把"战役阶段演化 + breakout 预警"组合用于信息操纵风险预判，时序预测范式与网络安全 kill-chain 阶段预测（2508.18230）同源。

### 数据集

| 数据集/资源 | 链接 | 用途 | 为何适合 |
|------------|------|------|---------|
| **无公开"战役阶段标注"演化数据** | — | — | seed/synchronize/breakout/... 阶段缺公开 ground-truth |
| IO Labeled Datasets (Seckin) 作时序代理 | https://arxiv.org/abs/2411.10609 【已核实】 | 用真实 IO 时间线近似演化轨迹 | 含时间戳与活动量，可做阶段切分的弱监督代理 |

> 诚实说明（重点）：Phase-Aware Hazard 这种"战役阶段演化"**缺公开标注数据**，验证依赖 mock 数据 + 专家评估 + 案例研究（与 METHOD_STANCE.md 风险缓解一致），定位为 proof-of-concept。

---

## 子功能 3：DISARM Attack-Path（技术转换图 + 路径评分 + 下一步预测 + 反制）

**落地状态：已落地**（`disarm_scorer.py`：`TECHNIQUE_INFO`/`TRANSITIONS`/`TRANSITION_PROBS` 手工领域图；`map_evidence_to_techniques()` 证据→DISARM 技术；`score_attack_path()` 用最长链 depth × tactic breadth × completeness 评分；`predict_next_techniques()` 取转换概率 top-3；`recommend_countermeasures()` 按 priority 排序）

> ⚠️ **诚实标注（核心风险点）**：路径预测范式 **源自网络安全 ATT&CK 域**，本项目是 **跨域迁移到 DISARM + 阶段条件化**，并非首创"攻击路径预测"。下表前 4 行是子功能 4 的真正先前工作。

### 高水平文献

| 标题 | 作者 | venue+年份 | 链接 | 与该子功能关系 |
|------|------|-----------|------|--------------|
| Technique Inference Engine (TIE) — "Know Your Adversary's Next Move" | MITRE CTID | CTID 2024 | https://ctid.mitre.org/projects/technique-inference-engine/ 【已核实】(代码: https://github.com/center-for-threat-informed-defense/technique-inference-engine 【已核实】) | **直接先前工作**：从已观测 TTP 推荐下一步 TTP。KT3 的 predict_next 是同一范式在 DISARM 域的规则版重做 |
| ML Framework for Predicting and Mapping ATT&CK Techniques (有向图建模阶段间依赖) | — | arXiv 2508.18230, 2025 | https://arxiv.org/html/2508.18230v1 【已核实】 | **直接先前工作**：用有向图捕捉 recon→objectives 的攻击者移动，与 KT3 的 TRANSITIONS 转换图同构 |
| Attack Chain Contraction and Prediction using Markov Model and LSTM on MITRE ATT&CK | UMass Dartmouth thesis | 2023/2024 | https://repository.lib.umassd.edu/esploro/outputs/graduate/Attack-chain-contraction-and-prediction-using/9914504161701301 【已核实】 | **直接先前工作**：Markov 攻击链下一步预测，对应 KT3 的 TRANSITION_PROBS 概率转移 |
| Policy–Value Guided MDP–MCTS Framework for Cyber Kill-Chain Inference | — | arXiv 2512.15150, 2025 | https://arxiv.org/html/2512.15150 【已核实】 | 补充先前工作：MDP 把入侵建模为状态转移序列，印证"攻击链预测"是成熟网安范式 |
| An Agentic Operationalization of DISARM for FIMI Investigation | — | arXiv 2601.15109, 2026 | https://arxiv.org/html/2601.15109v3 【已核实】 | **域内对标**：已有 DISARM Agent 化先例，但其为 flat tagging；KT3 差异=路径推理+预测+反制（见 METHOD_STANCE 对比表） |
| DISARM Red Framework (TTP 本体) | DISARM Foundation | 持续维护 | https://www.disarm.foundation/framework 【已核实】 | 提供 KT3 技术/战术 ID（T01xx/TA0x）的官方定义来源 |

> 创新声明（诚实，必读）：
> - **路径预测/下一步推断范式** = 网络安全 ATT&CK 域成熟方法（TIE 2024、2508.18230、Markov+LSTM thesis、MDP-MCTS 2512.15150）。
> - **KT3 的贡献是跨域迁移**：把上述范式搬到 DISARM 信息操纵 TTP，并加 **阶段条件化**（path 推理与 phase_detector 联动）+ **白盒可审计**（手工转换图 vs 黑盒 ML）+ **CPU-only 规则版**。
> - 不可声称"首创攻击路径预测"；应表述为"首次将网络安全攻击路径推理迁移到信息操纵 DISARM 域"。

### 数据集

| 数据集/资源 | 链接 | 用途 | 为何适合 |
|------------|------|------|---------|
| DISARM Frameworks (本体+TTP) | https://github.com/DISARMFoundation/DISARMframeworks/ 【已核实】 | 技术/战术 ID、转换图节点来源 | 官方 master 框架，KT3 的 TECHNIQUE_INFO 直接对齐 |
| DISARM 技术索引 | https://github.com/DISARMFoundation/DISARMframeworks/blob/main/generated_pages/techniques_index.md 【已核实】 | 校验技术 ID 命名 | 与代码中 T0097–T0108、T0049 一致 |
| MITRE ATT&CK Enterprise (TIE/2508.18230 训练源) | https://attack.mitre.org/ 【已核实】 | 跨域迁移的"源域"参照 | 证明转换图/路径预测方法在源域已验证 |
| IO 案例（Seckin / Twitter IRA archive） | https://arxiv.org/abs/2411.10609 【已核实】 | 用真实 IO 序列验证路径合理性 | 提供真实 TTP 序列做案例研究 |

> 诚实说明：DISARM 转换图与转换概率是**手工 domain-informed prior**，无公开"DISARM 技术序列"标注数据；验证靠案例研究 + 专家判断。

---

## 子功能 4：结构化报告生成

**落地状态：模板版已落地 / RAG 增强版设计稿**
（已落地：`report_builder.py`，`build_report()` 组装 phase/scores/fusion/evidence/disarm/risk_factors/recommendations 为 JSON。RAG 增强版 = EXPERIMENT_PLAN.md 中 WP-A4，检索历史报告库+DISARM 知识库+证据库 → DeepSeek 生成，**尚未落地**）

### 高水平文献

| 标题 | 作者 | venue+年份 | 链接 | 与该子功能关系 |
|------|------|-----------|------|--------------|
| Retrieval-Augmented Multi-Agent Framework for Misinformation Detection in Multimodal Fact-Checking | — | arXiv 2507.09174, 2025 | https://arxiv.org/html/2507.09174 【已核实】 | 直接支撑 RAG+Agent 报告生成（检索→生成）架构 |
| End-to-End Multimodal Fact-Checking and Explanation Generation | — | SIGIR 2023 | https://dl.acm.org/doi/10.1145/3539618.3591879 【存疑】(ACM DL 路径需复核 DOI) | 支撑报告的解释性生成（explanation generation） |
| Multi-Agent Retrieval-Augmented Framework for Evidence-Based Counterspeech | — | arXiv 2507.07307, 2025 | https://arxiv.org/html/2507.07307v2 【已核实】 | RAG 多 Agent 生成结构化输出的近作参照 |

### 数据集

| 数据集/资源 | 链接 | 用途 | 为何适合 |
|------------|------|------|---------|
| 项目自有历史报告库（MySQL） | 本仓库 `new-system/backend` | RAG 检索源 | 报告模板与字段已定义，可作检索语料 |
| DISARM 知识库（本地 YAML / 官方框架） | https://github.com/DISARMFoundation/DISARMframeworks/ 【已核实】 | RAG 检索知识源 | TTP 描述可注入生成提示 |

> 诚实说明：模板报告已落地且可运行；RAG 增强为设计稿，无专属公开数据集，检索语料为项目自建。

---

## 子功能 5：基于 Agent 的证据编排

**落地状态：设计稿**（WP-A1/WP-A6：升级 `llm_bridge.py` 为 DeepSeek Agent 编排器；现有 phase/evidence/disarm 模块作为 Agent 的 tool 被调用。当前代码仅为模块化函数，编排外壳未落地）

### 高水平文献

| 标题 | 作者 | venue+年份 | 链接 | 与该子功能关系 |
|------|------|-----------|------|--------------|
| MCP-Orchestrated Multi-Agent System for Automated Disinformation Detection | — | arXiv 2508.10143, 2025 | https://arxiv.org/html/2508.10143v1 【已核实】 | 直接对标：Agent 编排集成检测（95.3% acc），KT3 编排层需差异化（白盒 tool） |
| Multi-agent Systems for the Misinformation Lifecycle | A. Gautam | arXiv 2505.17511, 2025 | https://arxiv.org/html/2505.17511v1 【已核实】 | 多 Agent 全流程编排的最直接对标 |
| Multi-Agent Debate for Visual Misinformation Detection | — | arXiv 2410.20140, 2024 | https://arxiv.org/abs/2410.20140 【存疑】(编号未直接命中，需复核) | 支撑 Agent 间辩论/交叉验证编排机制 |
| A Multi-Agent Framework with Automated Decision Rule Optimization (cross-domain) | — | arXiv 2503.23329, 2025 | https://arxiv.org/abs/2503.23329 【存疑】(编号未直接核实) | 支撑 Agent 自适应规则方向 |

### 数据集

| 数据集/资源 | 链接 | 用途 | 为何适合 |
|------------|------|------|---------|
| 无专属数据集（编排层） | — | — | 编排本身复用子功能 1-5 的证据，无独立数据需求 |

> 诚实说明：编排是设计稿；已有 MCP 编排先例（2508.10143），KT3 差异点在"白盒规则 tool + 不做最终裁决"，需在汇报中明确避免被指"Agent 外壳被覆盖"。

---

## 子功能 6：恶意言论/有害内容检测 Agent

**落地状态：设计稿**（WP-A2：DeepSeek zero/few-shot 分类 + 语义增强，输出 harmful/safe/borderline）

### 高水平文献

| 标题 | 作者 | venue+年份 | 链接 | 与该子功能关系 |
|------|------|-----------|------|--------------|
| LLM-based Semantic Augmentation for Harmful Content Detection | — | arXiv 2504.15548, 2025 | https://arxiv.org/html/2504.15548v1 【已核实】 | 直接支撑：LLM 语义增强 > zero-shot，方法论与该 Agent 一致 |
| HateXplain: A Benchmark Dataset for Explainable Hate Speech Detection | Mathew et al. | AAAI 2021 | https://ar5iv.labs.arxiv.org/html/2012.10289 【已核实】 | 可解释有害内容检测的基准方法 |

### 数据集

| 数据集/资源 | 链接 | 用途 | 为何适合 |
|------------|------|------|---------|
| Jigsaw Toxic Comment Classification | https://huggingface.co/datasets/google/jigsaw_toxicity_pred 【已核实】 | 训练/评估有害内容分类 | ~160k Wikipedia 评论多标签毒性标注，业界标准 |
| HateXplain | https://huggingface.co/datasets/hatexplain 【存疑】(论文确认存在: https://ar5iv.labs.arxiv.org/html/2012.10289 【已核实】) | 仇恨言论 + 理由标注 | 提供 rationale，支撑可解释输出 |
| Perspective API | https://perspectiveapi.com/ 【已核实】 | 毒性打分基线/弱标签 | Jigsaw 官方毒性评分服务，可作对比基线 |

> 诚实说明：方法成熟（毒性检测是红海），创新点弱；定位为"反馈/扩展检测"辅助功能，非主创新。

---

## 子功能 7：立场检测 Agent

**落地状态：设计稿**（WP-A3：DeepSeek 判断 support/deny/neutral/query，claim-post 对）

### 高水平文献

| 标题 | 作者 | venue+年份 | 链接 | 与该子功能关系 |
|------|------|-----------|------|--------------|
| SemEval-2019 Task 7: RumourEval, Determining Rumour Veracity and Support | Gorrell et al. | SemEval 2019 | https://aclanthology.org/S19-2147/ 【已核实】 | 直接对标：support/deny/query/comment 四类立场，与该 Agent 标签一致 |
| Determining the Rumour Stance with Pre-Trained Deep Bidirectional Transformers (BUT-FIT) | — | SemEval 2019 | https://arxiv.org/abs/1902.10126 【已核实】 | 立场分类 SOTA 方法参照 |
| A Unified Framework for Multi-Modal Rumor Detection with Evolving Stances | — | IPM 2025 | https://www.sciencedirect.com/journal/information-processing-and-management 【存疑】(单篇 DOI 需复核) | 支撑"立场演化追踪"叙事 |

### 数据集

| 数据集/资源 | 链接 | 用途 | 为何适合 |
|------------|------|------|---------|
| RumourEval 2019 | https://huggingface.co/datasets/strombergnlp/rumoureval_2019 【已核实】 | 立场分类训练/评估 | Twitter+Reddit，support/deny/query/comment 标注，与设计标签对齐 |
| PHEME | https://figshare.com/articles/dataset/PHEME_dataset_for_Rumour_Detection_and_Veracity_Classification/6392078 【存疑】(figshare 镜像常见，需复核确切条目) | 谣言线程立场/真实性 | 谣言传播线程标注，支撑演化追踪 |
| SemEval-2016 Task 6 Stance | https://www.saifmohammad.com/WebPages/StanceDataset.htm 【存疑】(作者页常见，需复核) | 目标-立场对分类 | 经典 stance 基准，favor/against/none |

> 诚实说明：立场检测有成熟基准（RumourEval/PHEME），方法非新；价值在与上游事件联动做"立场演化追踪"。

---

## 子功能 8：反制叙事 Agent（Counter-narrative）

**落地状态：设计稿**（WP-A5：基于 DISARM 路径分析，DeepSeek 生成 counter_strategy/target_audience/priority）

### 高水平文献

| 标题 | 作者 | venue+年份 | 链接 | 与该子功能关系 |
|------|------|-----------|------|--------------|
| Generating Counter Narratives against Online Hate Speech (Multi-Target CONAN) | Fanton et al. / Chung et al. | ACL 2021 (arXiv 2107.08720) | https://ar5iv.labs.arxiv.org/html/2107.08720 【已核实】 | 直接对标：counter-narrative 自动生成方法与数据 |
| Multi-Agent Retrieval-Augmented Framework for Evidence-Based Counterspeech Against Health Misinformation | — | arXiv 2507.07307, 2025 | https://arxiv.org/html/2507.07307v2 【已核实】 | 直接支撑：多 Agent + RAG 生成反制叙事 |
| CONAN: Multilingual Dataset of Responses to Fight Online Hate Speech | Chung et al. | ACL 2019 | https://aclanthology.org/P19-1271/ 【已核实】 | counter-narrative 任务奠基数据 |

### 数据集

| 数据集/资源 | 链接 | 用途 | 为何适合 |
|------------|------|------|---------|
| Multi-Target CONAN | https://github.com/marcoguerini/CONAN 【已核实】 | counter-narrative 生成训练/评估 | 多目标专家撰写反制叙事对，直接可用 |
| DIALOCONAN | https://arxiv.org/abs/2211.03433 【已核实】 | 多轮反制对话 | 3000+ hater-NGO 对话，支撑对话式反制 |
| DISARM 反制库（COUNTERMEASURES 代码内） | https://github.com/DISARMFoundation/DISARMframeworks/ 【已核实】 | 反制策略与 TTP 对齐 | KT3 的反制建议从 DISARM 路径自然推出 |

> 诚实说明：反制叙事生成有 CONAN 系列成熟数据，但 KT3 差异点是"反制由 DISARM 预测路径驱动"（path→countermeasure），这是与通用 hate-speech counter-narrative 的真正区别，需在汇报中突出。

---

## 汇总状态表

| # | 子功能 | 落地状态 | 是否缺公开数据集 |
|---|--------|---------|----------------|
| 1 | 多源证据构建 | 已落地 | 部分（靠 IO 标注代理 + 自有上游） |
| 2 | Phase-Aware Hazard | 已落地 | **是（重点：缺战役阶段标注）** |
| 3 | DISARM Attack-Path | 已落地 | 是（手工 prior + 案例研究） |
| 4 | 结构化报告（模板/RAG） | 模板已落地 / RAG 设计稿 | RAG 用自建语料 |
| 5 | Agent 证据编排 | 设计稿 | 无独立需求 |
| 6 | 有害内容 Agent | 设计稿 | 否（Jigsaw/HateXplain） |
| 7 | 立场检测 Agent | 设计稿 | 否（RumourEval/PHEME） |
| 8 | 反制叙事 Agent | 设计稿 | 否（CONAN 系列） |

