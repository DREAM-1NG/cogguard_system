# KT1 协同检测模块 — 结题答辩评估报告

> 只读分析，未修改任何源代码或 ARIS 文档。
> 评估日期 2026-06-02。所有代码断言均给 `file:line` 证据，文献给 标题 + venue + 年份 + arXiv 号。
> 关键区分：**设计稿**（ARIS 文档里写了的方案）vs **已落地代码**（仓库里真实跑得起来的实现）。

---

## 1. 代码状态（设计稿 vs 落地）

### 1.1 真实落地的代码（已实现，可运行）

协同模块实际只有三个文件落地：

- `new-system/backend/app/core/coordination/detector.py` — `detect_groups()` / `flag_speed_share()`。这是 CooRTweet 的 Python 重写：同一 `object_id` 下、`time_window` 秒内的内容对配对，过滤自环与低参与账号。核心配对循环见 `detector.py:113-145`（`_calc_group_combinations`），时间窗判定 `detector.py:130` (`within = np.abs(time_deltas) <= time_window`)。**纯共享对象 + 时间窗，无显著性检验。**
- `new-system/backend/app/core/coordination/network.py` — `generate_coordinated_network()` 构建加权无向图 + 社区发现。边过滤仍是**百分位阈值**：`network.py:137-147` (`_apply_weight_threshold`，`threshold = np.percentile(positive, percentile*100)`)。这正是 FINAL_PROPOSAL 要替换掉的 "启发式阈值"。
- `new-system/backend/app/core/coordination/stats.py` — `account_stats()` / `group_stats()`。注意 `stats.py:15-30` (`_classify_object`) 已经把 object 分成 话题/图片/视频/链接/内容，但这只是**展示层分类**，不参与检测打分。

服务编排 `new-system/backend/app/services/coordination_service.py:467-507`：MongoDB → DataFrame → `detect_groups` → `generate_coordinated_network` → stats。共享对象抽取见 `coordination_service.py:151-159` (`_shared_objects`)：取 `hashtags + url + shared_urls + media_urls`，合成 `object_id`。**这就是"行为特征"的真实实现——URL/hashtag/媒体链接作为共享对象，不读内容。**

### 1.2 设计稿但**未落地**的代码（仅在 ARIS 文档里）

仓库中 **不存在** 以下文件（已用 `ls` 与全仓 `grep` 双重核实）：

- `significance.py` — 设计稿见 EXPERIMENT_PLAN.md:67-74（PairSurprisalLayer：对称超几何 + Cauchy combine + pair-level BH-FDR）。**未实现。**
- `semantic.py` — 设计稿见 EXPERIMENT_PLAN.md:75-84（SemanticPairAdapter：冻结句向量 + mutual-kNN + 经验零分布）。**未实现。**
- `channels.py` — systemDesign.md:553 提及 "significance.py + channels.py"。**未实现。**

证据：`new-system/backend/app/core/coordination/` 目录只有 `__init__.py / detector.py / network.py / stats.py`（`__init__.py:9-11` 只 import 这三个模块）。全仓 `grep "significance|SemanticPair|PairSurprisal|hypergeom|cauchy|enable_channels"` 在 `backend/app/` 下**零命中**。

### 1.3 结论（答辩定调）

> **PSL（对称超几何 + Cauchy + BH-FDR）、Semantic Adapter、多通道融合，目前 100% 是设计稿，0 行落地代码。** 真实可运行的协同检测 = CooRTweet 共享对象配对 + 百分位阈值 + 社区发现。答辩时必须区分"已实现的工程基线"与"提出的方法设计"，否则一旦评委追代码会暴露 gap。这是**最高优先级风险**。

---

## 2. 精确化的最新设计方向

把本轮导师讨论后的更新表述精确化为一句可写进论文的话：

> **KT1 的协同发现，只使用跨平台可复用的"行为型协同信号"（谁-和-谁、在多近的时间内、围绕同一个可被指纹化的对象，做了同一个动作），刻意排除任何"读内容"的信号（视频语义、字幕、文本立场、毒性、图文一致性）。内容理解一律下沉到 Characterization / KT3 下游，不回流为协同判定的依据。**

理由链（可辩护）：
1. 现有 CIB 检测文献的协同信号确实高度依赖**特定的共动作**（co-retweet / co-hashtag / co-URL / co-reply / time-burst）——见 Mannocci 综述与 Sharma 方法族。
2. 面向抖音等多媒体平台时，文献转向**内容型专用信号**（视频-语义 mismatch、转录文本相似），但 Luceri TikTok 2025 实证发现：**正是这些内容型/平台原生信号最不可迁移**（transcript 文本相似、Duet/Stitch 失效），而传统行为型协同指标"generalize well"。
3. 因此把创新押在"行为型信号的跨平台复用融合"上，比押在"内容型信号"上更稳健、更有迁移性。

---

## 3. 能跨平台泛化的"共同行为特征"清单（逐条、可实现）

按"是否依赖读内容"严格筛过，全部为**行为/结构信号**，可落到现有 `detect_groups` 配对框架或其 pair-adapter 接口：

| # | 行为特征 | 操作化定义（可实现） | 现状 |
|---|----------|----------------------|------|
| B1 | **时间同步 / 共现** | 同一 object 下两账号发布时间差 ≤ Δ（`detector.py:130` 已实现）；可扩展为多尺度窗口 burst | 已实现 |
| B2 | **共享 URL / 外链** | 规范化 URL（去 utm、解析跳转）→ `object_id`；`coordination_service.py:151-159` 已取 `url/shared_urls` | 已实现 |
| B3 | **共享 hashtag / 话题标签** | hashtag 文本作为 object_id（注意：用的是标签字符串本身，不是话题语义） | 已实现 |
| B4 | **共享媒体指纹** | 媒体按 **id / URL / 感知哈希（pHash, 视频关键帧哈希）** 抽象为 object_id，比较的是"是不是同一个媒体文件"而非"媒体讲了什么" | 部分（取 media_urls，未做指纹归一） |
| B5 | **共转发 / 共参与级联** | reply_to → 追溯 root_post_id → `cascade_{root}` 作为 object（EXPERIMENT_PLAN.md:86-90 设计，未落地） | 设计稿 |
| B6 | **账号行为节律** | 发文频率、间隔方差、作息熵、活跃-静默切换——RESEARCH_BRIEF.md:96 已列；属"账号级行为画像"，可作 Characterization 输入或弱协同先验 | 设计稿（account_profiler 基础） |
| B7 | **共参与序列 / hashtag 序列重叠** | 账号采用 hashtag 的**顺序序列**重叠（Luceri TikTok 2025 用到的可迁移信号之一） | 未提及，建议补 |
| B8 | **行为策略 / 动作序列同构** | 把账号活动建模为动作序列（发/转/评/赞的时序模式），比较策略相似度（Schneider 2026 "behavioral policies"，平台无关） | 未提及，前沿可选 |

> 注意 B3/B4 的边界细节：hashtag**字符串**和媒体**指纹**都是"对象标识符"，不是"对象内容"。"#台海" 作为字符串 token 参与配对是行为；分析"#台海"这个话题表达了什么立场是内容。这条要在论文里说死。

---

## 4. 行为特征 vs 内容检测 的边界线

**判据（一句话）**：信号是否需要"理解这条内容说了什么"。需要语义理解 = 内容检测（排除）；只需要"是不是同一个对象 / 同一个动作 / 同一个时刻" = 行为特征（允许）。

| 信号 | 归类 | 理由 |
|------|------|------|
| 两账号在 10s 内发同一 URL | 行为 | 只比对象标识符 + 时间戳 |
| 两账号共享同一媒体（按 id/pHash） | 行为 | 比的是"同一文件"，文件内容是黑盒 |
| 两账号用同一 hashtag 字符串 | 行为 | 比 token，不解释话题 |
| 共转发同一帖、共回复同一根 | 行为 | 比级联结构 |
| 账号发文节律/作息相似 | 行为（弱） | 比时序统计量，不读文 |
| 分析视频画面/字幕讲了什么 | **内容** | 需要视觉/语音/语义理解 |
| 视频-字幕 mismatch、图文不一致(OOC) | **内容** | 需要跨模态语义比对 |
| 文本立场 / 毒性 / 情感 | **内容** | 需要语义分类 |
| 文本相似度（句向量 cosine） | **灰区，见 §5** | 需要语义编码，但只用"相似不相似"做配对 |

边界的工程锚点：现在 `_shared_objects`（`coordination_service.py:151-159`）只吃 URL/hashtag/media_urls，**天然就在行为侧**，没有越界。stats 里的"视频/图片"分类（`stats.py:15-30`）只是展示标签，不进检测，也不越界。新方向其实是把**已经在做的事**理论化、并明令禁止把 semantic/视觉通道接进检测打分。

---

## 5. 与早期 PSL semantic channel（text2vec 文本相似度）的取舍

### 5.1 冲突点

PSL 设计稿明确包含 Semantic Pair Adapter：冻结句向量编码器（text2vec-base-chinese）→ cosine 相似 → kNN → 经验零分布 → `p_sem`，再和 object channel 一起 Cauchy 融合（FINAL_PROPOSAL.md:153-173, EXPERIMENT_PLAN.md:75-84）。**这一通道是"读文本语义"的——按 §4 判据落在内容侧。**

### 5.2 明确判断

> **语义相似度（句向量 cosine）算"内容检测"。新方向应将 semantic channel 移出 KT1 的协同发现（Detection）核心，降级为 Characterization 的可选证据通道，或彻底剔除。**

理由：
1. **判据上**：句向量编码必须"理解文本说了什么"才能给相似度，本质是内容理解，与"只比对象标识符"的行为信号性质不同。
2. **迁移性上**：文本语义相似高度依赖语言资源（中文 text2vec），跨平台/跨语言脆弱——正是 Luceri TikTok 2025 实证里"transcript 文本相似不可迁移"的同类信号。
3. **稳健性上**：生成式模型可廉价改写文本规避语义相似（Schneider 2026 直接点名 "generative models produce convincing text" 使内容方法 brittle）。把协同判定建立在可被 LLM 改写的信号上，对抗鲁棒性差。
4. **可辩护性上**：好处是论点更干净——"KT1 的协同信号一律不读内容"，一句话能站住；坏处是丢了一个召回来源。

### 5.3 折中建议（若评委质疑"丢召回"）

保留 **"模板化复用"** 这一**行为型**替代：检测**近乎逐字复制 / 同模板套壳**可以用**字符级/n-gram 指纹（MinHash, SimHash）**而非语义编码——这是"是不是同一段文字的复制"（对象指纹，行为侧），不是"这段文字什么意思"（语义，内容侧）。这样既抓到"复制粘贴水军"，又不破坏"不读内容"的论点。Luceri TikTok 2025 的 "repeated similar captions" 就属这类可迁移信号。

---

## 6. Detection / Characterization 分工是否干净

映射（基于 Mannocci et al. 2024 综述框架）：

- **Detection = f(U,H) 发现协同群体 → 行为同步信号（B1-B8）→ KT1 核心。**
- **Characterization = g(Y,H) 评估群体属性 → Authenticity/Harmfulness/Orchestration/Time-variance → 其中 Harmfulness（毒性/立场/虚假）属内容理解 → 下沉 Characterization 或 KT3。**

这个分工**基本干净**，且**与综述原文同构**——综述本身就把 detection 与 characterization 分成两个函数（RESEARCH_BRIEF.md:7-13 已引）。新方向相当于加了一条更强的约束："Detection 只用行为信号，所有内容理解推到 Characterization"。

**但有两个不干净的接缝，答辩要主动讲清**：

1. **Harmfulness 维度天然需要读内容**（综述定义 harmfulness 依赖 shared intent + actions + 内容，见 SURVEY_DIMENSIONS.md:20-26）。所以"内容检测全在 Characterization"是成立的，但反过来不能说"Characterization 不读内容"——它必须读。分工的干净之处在于**方向单一**：内容信号只从 Detection 流向 Characterization，绝不回流当协同判据。要把这条"单向阀"说清楚。

2. **Semantic channel 的归属**（§5）：原 PSL 把 semantic 放进 Detection 融合，违反了新分工。必须显式声明把它移到 Characterization 侧或剔除，否则分工自相矛盾。

> 一句话辩护：**"我们用行为同步发现'谁在协同'（Detection，平台无关、抗改写），用内容理解判断'协同得有多坏'（Characterization，下游、可换模型）。两者单向解耦：内容永不反向决定协同。"**

---

## 7. 文献定位（含引用 + 真伪核实）

### 7.1 LITERATURE_REFERENCES.md 关键条目核实结果

| 文档条目 | 核实结论 |
|----------|----------|
| **Mannocci et al. 2024 综述**（条目 #9） | **准确**。Detection and Characterization of Coordinated Online Behavior, arXiv:2408.01257 (2024-08)。作者 Mannocci, Mazza, Monreale, Tesconi, Cresci 正确。四维度 (authenticity/harmfulness/orchestration/time-variance) 与原文一致。可放心引用。 |
| **Tardelli et al. PNAS 2024**（条目 #3） | **标题/贡献错误**。文档写成 "Coordinated Inauthentic Behavior Detection on Social Media，跨平台协同检测"。**真实** = *Temporal dynamics of coordinated online behavior: Stability, archetypes, and influence*, PNAS 121(20):e2307038121, 2024，作者 Tardelli, Nizzoli, Tesconi, Conti, Nakov, Da San Martino, Cresci。这是**时序 archetype** 论文，**不是**跨平台检测论文（其单平台正是它自陈的 limitation）。EXPERIMENT_PLAN.md:311 把它当 "archetype 分类 baseline" 才是对的；LITERATURE_REFERENCES 条目 #3 的描述需修正。**答辩前必改，否则被问就穿帮。** |
| **Sharma et al. KDD 2021**（条目 #2） | **部分失实**。文档既称 "z-score 显著性"（条目 #2/#16 一致），又在 FINAL_PROPOSAL.md:231 写 "Sharma KDD 2021: GNN-based"——**自相矛盾**。真实最接近的是 AMDN-HAGE（*Identifying Coordinated Accounts on Social Media through Hidden Influence and Group Behaviours*, arXiv:2008.11308），用 Neural Temporal Point Process + GMM 的**生成式无监督**模型，**不是 z-score 也不是 GNN**。另有 Pacheco/Nwala 等 "Uncovering Coordinated Networks"（arXiv:2001.05658）用任意行为 trace 构图。引用前需核对到底指哪一篇并统一表述。 |
| **Cinus et al. WWW 2025**（条目 #4） | **venue/标题存疑**。文档写 "Graph Neural Networks for Coordinated Behavior Detection, WWW 2025, GNN 端到端"。搜索未找到该确切标题/venue。Cinus 团队真实近作是 *Exposing Cross-Platform Coordinated Inauthentic Activity in the Run-Up to the 2024 U.S. Election*（arXiv:2410.22716，作者 Cinus, Minici, Luceri, Ferrara），用**相似度网络**而非 "GNN 端到端"。**"Cinus WWW 2025 是 GNN" 这条很可能是虚构/张冠李戴，引用前必须核实，否则是答辩硬伤。** |
| Seckin et al. 2024 IO Datasets（条目 #12） | **准确**。arXiv:2411.10609，作者 Seckin, Pote, Nwala, Yin, Luceri, Flammini, Menczer。已被 AAAI ICWSM 2025 收录。可用作 ground-truth 数据源。 |
| Iannucci et al. 2025（条目 #10） | 标题/作者可信（Temporal Multiplex），arXiv 号 2512.19677 属未来日期格式，引用时标注 "preprint, 待核 arXiv 号"。 |
| ACCD（条目 #23, arXiv:2601.00400） | 真实存在（亦见 preprints.org/202601.0547），但 arXiv 号是 2026 年格式；作为 "Orchestration SOTA" 引用需谨慎标 preprint。 |

> **总体**：综述类（Mannocci）可信；但 Sharma / Tardelli / Cinus 三条核心对比基线均有标题/venue/方法错配，**这是最危险的答辩雷区**——评委查一篇就动摇整个文献基础。建议结题前对全表做一次逐条核实。

### 7.2 支持"内容型协同信号平台特定且脆弱"论点的论文

- **Luceri et al. 2025（最强支持 + 最接近的先前工作）** — *Coordinated Inauthentic Behavior on TikTok: Challenges and Opportunities for Detection in a Video-First Ecosystem*, arXiv:2505.10867 (2025-05, rev. 2025-10)。**实证**：在 793K 条 TikTok 大选视频上，"传统协同指标（同步发布、媒体复用、hashtag 序列重叠）generalize well 到 TikTok"，而**基于视频转录文本相似 和 Duet/Stitch 平台原生交互的信号失效**。这条直接坐实"内容型/平台原生信号脆弱、行为型信号可迁移"。**应作为 KT1 新方向的头号实证支撑。**
- **Schneider, Yuan, Rizoiu 2026** — *Beyond Content: Behavioral Policies Reveal Actors in Information Operations*, arXiv:2602.02838 (2026-02)。直接论点："这些（内容/网络）方法 increasingly brittle，因为生成式模型能产出以假乱真的文本、平台限制行为数据访问、行为者迁移平台"。提出 platform-agnostic 的行为策略表示（把用户活动建模为序列决策过程），活动型模型 macro-F1 94.9% > 文本嵌入 91.2%，且抗规避退化更平缓。**"内容脆弱 / 行为稳健"论点的最强理论+实验背书。**
- **Wohlert, Vega, Magnani, Segerberg 2025** — *Detecting Coordinated Behaviour on Video-First Platforms: The Challenge of Multimodality and Complex Similarity on TikTok*, arXiv:2506.05868 (2025-06)。**反向/张力证据**：主张视频平台**需要**专门的多模态内容相似度（视觉/音频/文本分层）。代表"该往内容多模态走"的对立阵营——答辩可能有评委站这边，需准备区分（见 §9）。

### 7.3 与新方向的张力 / 反方论文

- **Mannocci et al. 2026（Information Sciences）** — *Multimodal Coordinated Online Behavior: Trade-offs and Strategies*, arXiv:2507.12108 (2025-07, rev. 2026-02)。结论"multimodal 一致地提供更丰富的协同表示"。**注意细读**：这里的 "modality" 指**多种行为型交互**（co-retweet、co-hashtag 等），**不是**文本/图像/视频媒体内容。所以它其实**支持"多种行为信号融合"**（= 新方向的融合主张），而非"融合内容"。这条要正确引用，别被标题误导成反方。
- **Wohlert et al. 2025（上 §7.2）** 是真正的反方：明确主张内容多模态相似度是必要的。

### 7.4 最接近的先前工作（closest prior work）

1. **Luceri TikTok 2025（2505.10867）** — 几乎就是新方向的实证版："哪些信号跨平台可迁移"。**KT1 与它的差异**：它停在"发现某些信号能迁移"，未提供 **pair-level 统计显著性 / FDR 控制**，也未做成**可复用的融合框架**。
2. **Pacheco/Nwala "Uncovering Coordinated Networks"（2001.05658）** — "基于任意行为 trace 构建协同网络" 的通用框架，是"行为信号可任意替换"思想的源头。**差异**：无显著性检验、无跨平台复用的工程化。
3. **Schneider 2026（2602.02838）** — platform-agnostic 行为策略。**差异**：它走序列决策建模（重），KT1 走轻量统计配对 + 显著性，且面向**多平台共同信号的融合**而非单一策略表示。

---

## 8. 精确的创新空白（gap）

把上面三个 closest prior work 叠起来看，留给 KT1 的、别人没占的空地是：

> **"用一个平台无关的行为型协同信号集 + pair-level 统计显著性（对称超几何 + 依赖鲁棒的 Cauchy 融合 + BH-FDR）做成一个可跨平台复用、抗概念漂移的融合检测层，并明令把内容理解排除在协同判定之外、只下沉到下游表征。"**

拆解占位：
- Luceri 2025 证明"行为信号可迁移"但**无显著性/FDR、无融合框架化** → KT1 补"统计显著性 + 框架化"。
- PSL 原设计有"显著性 + 融合"但**含 semantic 内容通道、单平台** → 新方向补"剔内容 + 跨平台复用语义"。
- Schneider 2026 有 "platform-agnostic" 但**是单一重型策略表示、非多信号轻量融合** → KT1 补"多行为信号的轻量可解释融合 + 证据输出"。

**没有任何一篇同时具备：行为信号集 × pair-level FDR × 跨平台复用 × 内容单向解耦 × 证据可审计。这就是精确空白。**

> 诚实风险标注：这个空白**目前只在设计稿层面成立**（§1.3），代码未落地；且"跨平台复用"在仓库里只做到"跨源（微博+新闻）"，未做真正的多平台（抖音等）验证。答辩要把"创新主张"和"已验证范围"分开讲。

---

## 9. 创新一句话（answerable novelty statement）

> **"CogGuard KT1 提出一个平台无关的行为型协同发现层：只用'谁-何时-围绕同一个可指纹化对象-做同一动作'这类跨平台共有的行为痕迹作为协同信号，通过对称超几何检验 + 依赖鲁棒的 Cauchy 融合 + 配对级 BH-FDR，把多种行为信号融合成带形式化假阳性率保证、且每条边可审计证据的协同图；所有内容理解（语义、立场、毒性、多模态一致性）被刻意排除在协同判定之外、单向下沉到下游表征——因为内容型信号平台特定、且在生成式 AI 时代易被改写规避，而行为同步是跨平台、抗漂移、抗改写的稳健信号。"**

精简版（评委一句记得住）：

> **"别人靠'内容像不像'抓协同，我们靠'行为同不同步'——内容会被 AI 改写、换平台就失效，行为同步换平台照样成立。"**

---

## 10. 答辩最可能被攻击的 5 点 + 建议反驳

### 攻击 1（最致命）：方法没落地，PSL/语义/多通道全是 PPT
- **现状**：§1.3 — significance.py/semantic.py/channels.py 零代码，真实只有 CooRTweet 共享对象 + 百分位阈值。
- **反驳**：诚实分层。"已实现的是稳健工程基线（CooRTweet 重写 + 加权图 + 社区发现，跑得通、有前端、有 API）；PSL 是经 5 轮评审收敛的方法设计与实验计划。"**别声称 PSL 已跑出结果。** 若时间允许，结题前至少落地 `significance.py` 的对称超几何 + BH-FDR（不含语义通道，纯统计，3-4 天可做，FINAL_PROPOSAL.md:268-273 自评工作量），把"设计"变"已验证"，直接拆掉这颗雷。

### 攻击 2：文献错配（Tardelli/Sharma/Cinus 标题或方法写错）
- **现状**：§7.1 — Tardelli PNAS 实为 temporal archetype 非跨平台检测；Sharma 自相矛盾（z-score vs GNN）；Cinus "WWW 2025 GNN" 查无实据。
- **反驳**：结题前**逐条核实修正 LITERATURE_REFERENCES.md**（本报告已给正确标题/arXiv）。答辩时引用以核实过的为准：综述用 Mannocci 2408.01257，跨平台实证用 Luceri TikTok 2505.10867 + Cinus 2410.22716，行为稳健用 Schneider 2602.02838。**绝不在答辩现场报未核实的 venue。**

### 攻击 3：排除内容 = 自废武功，丢召回 / 丢"多模态"卖点
- **反驳**：(a) 召回——用**行为型替代**补回（媒体 pHash 指纹 B4、字符级模板指纹 §5.3、hashtag 序列 B7），不靠语义也能抓复制粘贴水军。(b) 多模态卖点——systemDesign.md:72-78, 95 已有明确收敛："多模态在**展示层/搜索层**承载，检测层单模态"。这是设计里写死的，不是临时找补。(c) Luceri 2025 实证：内容型信号本就最不可迁移，排除它反而提升跨平台稳健性。

### 攻击 4：抖音视频协同就是要看视频内容，你不看内容怎么抓？（Wohlert 2025 阵营）
- **反驳**：(a) 引 Luceri TikTok 2025 实证反制——TikTok 上**传统行为指标 generalize well**，失效的恰是转录文本相似与平台原生交互；同步发布/媒体复用/hashtag 序列照样抓得到协同。(b) "同一段视频被多账号复用"用**视频指纹/关键帧哈希**（行为侧 B4）即可，不需要理解视频讲什么。(c) 承认边界：若协同体现在"不同视频但同一叙事"，那属 Characterization 的内容层，本就不该 Detection 扛——这正是单向解耦的设计意图，不是缺陷。

### 攻击 5：超几何/Cauchy/BH 都是现成方法，创新在哪？
- **反驳**：FINAL_PROPOSAL.md:226-227 已自我设防——"不声称三个统计工具各自创新"。创新在**组合 + 场景化 + 架构**：pair-level 假设构造（对称 max(p_u,p_v) 校正双边活跃度）、依赖鲁棒的多行为通道融合（解决综述 Challenge #3 异质性）、配对级形式化 FDR（替代百分位阈值抑制热门话题误报）、即插即用层 + 跨平台行为信号复用。把它定位成"**面向跨平台行为协同的可审计显著性融合层**"，而非"发明新统计量"。

### 攻击 6（附加）：跨平台只验了"跨源(微博+新闻)"，敢叫跨平台?
- **现状**：systemDesign.md:96, 103 自陈 M2 错位——只做"跨源证据"非"跨平台身份解析"，且短期仅 mock_weibo/weibo/news。
- **反驳**：措辞校准——对外说"**平台无关的行为信号设计 + 跨源验证**"，把"多平台泛化"作为**信号设计层面的可迁移性论证（引 Luceri 2025）**，而非声称已在抖音跑通。non-goal 已在 systemDesign.md:51 显式列出，主动讲比被问出来好。

---

## 附：核实过的可引用文献清单（结题用）

- Mannocci, Mazza, Monreale, Tesconi, Cresci. *Detection and Characterization of Coordinated Online Behavior: A Survey*. arXiv:2408.01257, 2024.
- Tardelli, Nizzoli, Tesconi, Conti, Nakov, Da San Martino, Cresci. *Temporal dynamics of coordinated online behavior: Stability, archetypes, and influence*. PNAS 121(20):e2307038121, 2024.
- Luceri, Salkar, Balasubramanian, Pinto, Sun, Ferrara. *Coordinated Inauthentic Behavior on TikTok: Challenges and Opportunities for Detection in a Video-First Ecosystem*. arXiv:2505.10867, 2025.
- Schneider, Yuan, Rizoiu. *Beyond Content: Behavioral Policies Reveal Actors in Information Operations*. arXiv:2602.02838, 2026.
- Wohlert, Vega, Magnani, Segerberg. *Detecting Coordinated Behaviour on Video-First Platforms: The Challenge of Multimodality and Complex Similarity on TikTok*. arXiv:2506.05868, 2025.
- Mannocci, Cresci, Magnani, Monreale, Tesconi. *Multimodal Coordinated Online Behavior: Trade-offs and Strategies*. Information Sciences (postprint), arXiv:2507.12108, 2025/2026.
- Cinus, Minici, Luceri, Ferrara. *Exposing Cross-Platform Coordinated Inauthentic Activity in the Run-Up to the 2024 U.S. Election*. arXiv:2410.22716, 2024.
- (AMDN-HAGE) *Identifying Coordinated Accounts on Social Media through Hidden Influence and Group Behaviours*. arXiv:2008.11308, 2020/2021.
- Pacheco et al. *Uncovering Coordinated Networks on Social Media*. arXiv:2001.05658, 2020.
- Seckin, Pote, Nwala, Yin, Luceri, Flammini, Menczer. *Labeled Datasets for Research on Information Operations*. arXiv:2411.10609, 2024 (ICWSM 2025).
- Liu & Xie. *Cauchy Combination Test*. JASA, 2020.（PSL 核心统计工具，未核实页码）


