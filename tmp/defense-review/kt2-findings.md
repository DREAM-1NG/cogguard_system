# KT2 传播监控模块 结题答辩评审findings

> 只读分析产物，生成于 2026-06-02。所有代码断言均给 file:line（仓库根 g:/CISCN/cogguard_system/）。
> 区分约定：【已落地】= 代码可读可运行；【设计稿】= 仅 ARIS 文档定义，代码未实现；【缺口】= 文档与代码均无。

---

## 0. 一句话结论（先看这个）

- **事件规模预测 = CascadeSwitch 的级联规模（cascade size）预测**，这是真东西，代码已落地（trend_predictor + regime_model + ts_features），但当前线上 `predict` 走 `mock_llm=True`，LLM 分支未真正接通。
- **传播路径预测（预测下一跳/未来路径结构）当前没有任何设计也没有任何代码**。文档里出现的"传播路径"全部是"已观测转发链的可视化 / 关键路径回溯（取证）"，属于 micro-level **重建**而非 **预测**。这是最大的事实风险点：如果对外宣称"传播路径预测"作为关键技术，会被评委直接证伪。

---

## 1. 代码状态（file:line 实证）

### 1.1 CascadeSwitch 核心（已落地，规模预测）

| 模块 | 文件:行 | 状态 | 证据 |
|---|---|---|---|
| 时序特征 | `new-system/backend/app/core/propagation/ts_features.py:15-94` | 已落地 | `extract_ts_features` 输出 volumes/velocity/acceleration/burst_zscore/trend_direction |
| 体制后验+参数化预测 | `core/propagation/regime_model.py:28-33`(W矩阵)、`:43-82`(softmax后验)、`:105-156`(4体制f_z)、`:159-224`(mixture_forecast) | 已落地 | 与 KT2_COMPLETE_PLAN.md:51-69 的 W/softmax/mixture 公式一致 |
| LLM 事件提取 | `core/propagation/llm_context.py:55-119` | 已落地但默认旁路 | `extract_events` 有真实 httpx 调用(`:122-140`)+3次多数投票(`:96-119`)+mock 分支(`:73-74`) |
| 编排器 | `core/propagation/trend_predictor.py:15-91` | 已落地 | predict_trend 串 ts→events→posterior→mixture→explanation |
| 子包导出 | `core/propagation/__init__.py:4-6` | 已落地 | 仅 re-export `build_propagation_graph`（旧模块） |

**预测输出形态**（`trend_predictor.py:77-91` + `regime_model.py:216-224`）：
`volume_forecast{1h/6h/24h}` + `confidence_interval` + `direction(rising/stable/declining)` + `regime_posterior` + `detected_events` + `explanation`。
→ 输出的是**未来时刻的传播量级（标量序列）**，即 cascade size，**没有任何节点级/边级的未来结构输出**。

### 1.2 服务层与 API

| 项 | 文件:行 | 状态 | 关键事实 |
|---|---|---|---|
| 预测服务 | `services/propagation_service.py:64-81` | 已落地 | `predict_propagation_trend` 第 73 行硬编码 `await predict_trend(posts, comments, mock_llm=True)` —— **LLM 分支线上被强制旁路** |
| 分析服务 | `services/propagation_service.py:44-61` | 已落地 | `analyze_propagation` 调旧模块 `build_propagation_graph` |
| API 路由 | `api/v1/propagation.py:13-31` | 已落地 | 仅 `/analyze`(GET) 与 `/predict-trend`(POST)。**无** `predict`/`stance`/`harm` 正式契约接口 |

**核实结论（针对线索）**：`mock_llm=True` 确为当前线上行为，证据 `propagation_service.py:73`。意味着演示时 `detected_events` 恒为空、`llm_available=False`，体制后验完全由 `_compute_history_prior`（`regime_model.py:85-102`，纯速度/加速度规则）驱动 —— **LLM 在闭环里目前不产生实际作用**。

### 1.3 旧模块（源头追溯 / 关键路径，已落地，但是"重建"不是"预测"）

`core/propagation_legacy.py`（~585 行）：
- `build_propagation_graph()` `:23` → 输出 graph/key_roles/claims/timeline/evidence_chains。
- `_extract_key_paths_for_claim()` `:388-504`：核心是 `nx.shortest_simple_paths(simple_G, originator_id, amp_id)`（`:424-427`），**在已观测图上搜索 originator→amplifier 的路径**，做证据链取证。
- **这是 micro-level 的"路径重建/归因"**，输入是完整历史图，输出是历史路径的 Top-K 排序，**与"预测未来下一跳"无关**。把它当"传播路径预测"对外宣传会被证伪。

### 1.4 未落地（设计稿 / 缺口）

- 立场检测 `stance_detector.py`：【设计稿】仅 EXPERIMENT_PLAN.md:31、FEATURE_STATUS_MATRIX.md:28 定义，无代码（Glob 确认 propagation/ 下无此文件）。
- 危害评估 `harm_assessor.py`：【设计稿】同上（FEATURE_STATUS_MATRIX.md:29）。
- 级联形态事件检测 `cascade_events.py`（无内容模式）：【缺口】KT2_COMPLETE_PLAN.md:161 列为"待实现"，代码不存在。
- 数据集加载器 `cascade_loader.py` / 评估脚本 `evaluate_cascade.py`：【缺口】KT2_COMPLETE_PLAN.md:159-161 待实现，**意味着文档承诺的 DeepHawkes/CasFlow 基准实验目前一行评估代码都没有**。
- 知微借鉴扩展字段（influence_score / peak_eta_hours / stage_transition_eta / risk_level）：【设计稿】REQUIREMENTS.md:247-254、ZHIWEI_PRODUCT_ANALYSIS.md:382-389 定义，trend_predictor 输出里**尚未出现**。

---

## 2. 知微（Zhiwei / WeiboReach）借鉴边界

### 2.1 知微到底提供什么（基于 ZHIWEI_PRODUCT_ANALYSIS.md）

知微数据（2012 成立，A 轮 1300 万，11-50 人，ZHIWEI:14-22）旗下 WeiboReach 的核心能力（ZHIWEI:55-137）：
- 模块 A 单条微博传播分析：转发/评论/点赞分钟级时序曲线、**传播路径图（谁转发谁）**、转发层级分布、关键节点（ZHIWEI:57-72）。
- 模块 B 传播路径与关键节点：基于微博原生 repost 关系的**树状传播链**，PageRank/Betweenness 类算法，d3.js 力导向布局（ZHIWEI:75-89）。
- 模块 C 用户画像（KOL/水军/地域/认证，ZHIWEI:93-107）。
- 模块 D 文本分析（情感/词云/立场，ZHIWEI:109-121）。
- 模块 E 传播力指数 0-100（广度/深度/速度/持续性，ZHIWEI:123-137）。
- 知微事见：事件影响力指数、事件演化追踪（5 阶段经验划分，ZHIWEI:140-176）。

**关键事实**：知微的"传播路径"= 事后展示已发生的转发链，**它本身也不做路径预测**，甚至文档明确指出知微"缺乏预测能力，以事后分析、影响力排名为主"（ZHIWEI:325）。文档作者亦声明因网络限制未能访问官网，部分功能为**推测**（ZHIWEI:51、478-503，标注"推测"）。

### 2.2 哪些应"借鉴"（功能/UX 层），哪些是原创（方法层）

| 维度 | 借鉴知微（功能/UX） | 本项目原创（方法/贡献） |
|---|---|---|
| 阶段划分 | 5 阶段经验命名验证了"分阶段"有产业必要性（ZHIWEI:167-176） | 4 体制 **可计算后验** p(z)=softmax(W·e+b)，白盒可验证（regime_model.py:43-82） |
| 输出形态 | 传播力指数仪表盘、阶段时间轴、风险分级 UX（ZHIWEI:354-410） | 事件条件体制切换的**前瞻预测**+置信区间+中文解释 |
| 特征集 | max_chain_depth/unique_reposter/kol_ratio 等指标命名（ZHIWEI:295-302） | 用 LLM 抽取的外生事件作为体制驱动信号（llm_context.py） |
| 可视化 | 路径图/堆叠图/热力图（ZHIWEI:403-410） | —（纯展示层，非贡献） |

### 2.3 如何不被评委说成"只是抄产品"

- **划清"产品形态借鉴"与"方法贡献"**：借鉴的是 UX 与指标命名（任何舆情产品都有），贡献是知微**没有的**——零训练、可解释的 regime-switching 预测方法（ZHIWEI:319-339、REQUIREMENTS.md:44-46）。
- **知微无公开方法、算法黑盒、不可发表、绑定微博**；本项目跨平台（DeepHawkes Weibo + CasFlow Twitter）、白盒、可发表（ZHIWEI:321-339）。
- **一句话防御**："我们没有复刻知微的任何算法（它不公开），我们借鉴的是工业界验证过的'分阶段+传播力'产品形态，把它升级为有数学后验、可跨平台泛化、可在公开基准上量化评估的预测方法。"

---

## 3. 事件规模预测 = CascadeSwitch 级联规模预测？（确认并衔接）

**确认：是同一件事。**
- KT2_COMPLETE_PLAN.md:11 任务定义：给定早期观测窗口 [0,t_obs]，预测 t_pred 时刻**最终规模（转发量）**。这就是文献里的 cascade/popularity size prediction（macro-level）。
- 代码侧 `mixture_forecast`（regime_model.py:159-224）输出 `volume_forecast{1h/6h/24h}` 标量，即"事件规模/级联规模"的未来量级。
- "事件规模预测"是面向答辩/产品的中文叫法，"级联规模预测（cascade size prediction）"是其学术对应。两者**指同一任务、同一份代码**，衔接无缝。可在答辩中明确："事件规模预测在学术上即 information cascade size / popularity prediction，我们的 CascadeSwitch 属此任务的零训练可解释解法。"

---

## 4. 传播路径预测（有无设计？可行性？缺口？）

### 4.1 当前到底有没有（核实结论）

**没有。** 三处证据：
1. ARIS 全目录 grep `路径预测/path prediction/next-node/next-hop/下一跳/structure prediction` —— **0 命中**。
2. ZHIWEI 全文"传播路径"仅指路径图可视化（ZHIWEI:64、262、406）与对标表里的"传播路径可视化"（ZHIWEI:512）。
3. 代码侧唯一与"路径"相关的是 `propagation_legacy.py:388-504` 的 `_extract_key_paths_for_claim`，用 `nx.shortest_simple_paths` 在**已观测图**上回溯，是取证/重建，非预测。

→ **"传播路径预测"在本项目当前既无设计稿也无代码，是一个纯缺口。** 若汇报材料里出现该词作为"已有关键技术"，属过度宣称，必须改口径。

### 4.2 它与规模预测是不同任务

| | 事件规模预测（macro） | 传播路径预测（micro） |
|---|---|---|
| 预测对象 | 未来总量级（标量） | 下一个被感染节点 / 未来路径结构（节点序列/子图） |
| 文献类别 | popularity/size prediction（DeepCas/CasFlow…） | diffusion/next-infected-user prediction（见 §6） |
| 本项目现状 | 已落地（CascadeSwitch） | 缺口 |
| 难度 | 中（已用参数化模型解） | 高（需节点级表示/图序列建模，与"零训练"哲学冲突） |

### 4.3 可行性与建议口径

- **可行性中等偏低**：micro-level 路径预测（如 §6 的 Ricci-curvature、multi-scale attention 方法）通常需要训练图序列模型，与 CascadeSwitch"零训练、可解释"主张相悖；硬上会破坏方法一致性，且 CogGuard 真实采集是**部分观测**（看不到全网转发关系），下一跳预测数据条件不足。
- **建议**：答辩中**不要把"路径预测"立为已实现关键技术**。两条稳妥路线：
  (a) 诚实定位为"未来工作 / 路线图"，承认是缺口；
  (b) 若必须有"路径"叙事，立为 **"传播路径回溯/取证"（已落地，propagation_legacy）+ "规模与体制前瞻预测"（已落地，CascadeSwitch）** 的组合，明确"回溯是事后、预测是事前"，**不混用"路径预测"这个词**。

---

## 5. 如何把两个预测立为"关键技术"而非"功能堆叠"

- **统一在一个问题框架下**：信息级联的非平稳动态（体制转换）是共同根因（KT2_COMPLETE_PLAN.md:13）。规模预测是"主任务"，体制后验是"机制"，事件抽取（LLM）是"驱动信号"——三者是**一条方法链**而非并列功能。
- **关键技术 = "LLM 事件条件 + 体制切换混合预测"**（KT2_COMPLETE_PLAN.md:86-89 的主/次贡献定位）：主贡献是事件条件 regime-switching 框架，次贡献是级联形态事件检测，明确"非贡献"是不发明新 LLM/新时序架构——这种自我克制反而增强可信度。
- **避免堆叠的判据**：每个输出（volume/direction/regime_posterior/explanation）都从**同一后验 p(z)** 派生（regime_model.py:188-214），不是各跑各的模型。这是"一个方法多个视图"，可据此反驳"功能拼盘"质疑。
- **风险**：当前 LLM 旁路（mock_llm=True）使"LLM 事件条件"这一卖点在演示中不生效；评估脚本未落地使"超越基线"无数据支撑。立"关键技术"前需补这两块，否则关键技术=纸面。

---

## 6. 文献定位（2024-2026，含核实）

### 6.1 规模预测 baseline 真实性核实（文档已列 DeepCas/CasFlow/CasCN/VaCas/TempCas）

均为**真实存在**的已发表工作，REFERENCE.md 与外部检索一致：
- DeepCas — *DeepCas: An End-to-end Predictor of Information Cascades*, WWW 2017, arXiv:1611.05373（REFERENCE.md:104-111）。
- DeepHawkes — *DeepHawkes: Bridging the Gap between Prediction and Understanding of Information Cascades*, CIKM 2017（REFERENCE.md:94-102；任务设定 t_obs→t_pred 的事实标准）。
- CasCN — *Information Diffusion Prediction via Recurrent Cascades Convolution*, ICDE 2019（REFERENCE.md:113-120）。
- CasFlow — *CasFlow: Exploring Hierarchical Structures and Propagation Uncertainty for Cascade Prediction*, IEEE TKDE 2020/2021（REFERENCE.md:122-130；github kpzhang/casflow 与 Xovee/casflow 均可查）。
- VaCas — 变分级联预测, 2020（REFERENCE.md:132-138）。
- TempCas — *AAAI 2021* 时间感知级联（REFERENCE.md:140-147）。
- 综述背书：*A Survey of Information Cascade Analysis: Models, Predictions, and Recent Advances*, ACM CSUR, arXiv:2005.11041（macro/micro 任务分类的权威出处）。

→ **baseline 列表可信**。唯一隐患：本项目**尚无评估代码**复现/引用这些 MSLE 数值（§1.4），"对比 SOTA"目前是承诺非事实。

### 6.2 与 CascadeSwitch 直接同型/对手工作（2024-2026）

- **CasFT** — *Future Trend Modeling for Information Popularity Prediction with Dynamic Cues-Driven Diffusion Models*, arXiv:2409.16619（REFERENCE.md:160-170 标为"直接对手/必比 baseline"）。同样用"动态线索驱动未来趋势"，但端到端训练、线索隐式学习；CascadeSwitch 零训练、事件由 LLM 显式抽取可解释。**这是答辩最可能被点名的对照，务必能讲清差异。**
- **Autoregressive Cascade Predictor via LLMs** — arXiv:2502.18040（REFERENCE.md:195）。直接用 LLM 做级联时序自回归预测——与本项目"**不让 LLM 做数值预测、只做事件抽取**"形成对立设计，可作为差异化论据（呼应 Tan et al. NeurIPS 2024, arXiv:2406.16964 的反向论证，REFERENCE.md:230-236）。
- **CasTemp** — *Towards Realistic and Efficient Information Cascade Prediction*, arXiv:2510.25348。强调 leak-free 评估与"现实性"，与零训练哲学一致；可引为同期 SOTA。
- **Variational Neural ODE** — arXiv:2603.09148（REFERENCE.md:154-158），用 NN 逼近 ODE，与本项目"显式 4 参数化模型"对比。

### 6.3 传播路径预测（micro-level）相关工作 —— 证明这是独立研究方向（本项目缺口对应的文献）

- **Ricci Curvature Tells When You Will be Informed**, arXiv:2405.17282（2024）— 明确"现有扩散预测模型主要预测 **next informed user**"，是 next-node 预测的代表。
- **Make Information Diffusion Explainable: LLM-based Causal Framework for Diffusion Prediction**（OpenReview ZdQhQOXVku）— 预测"未来被感染用户"，且用 LLM——与本项目最接近的"路径/微观预测+LLM"工作，可作为**若要补路径预测的方法蓝本**。
- **Multi-scale Context-enhanced Dynamic Attention Network for Diffusion Prediction**, arXiv:2308.04266 — "预测传播路径上的 target users"，典型 micro-level 路径预测。

→ 文献明确区分 **macro（size，本项目已做）** vs **micro（next-user/path，本项目缺口）**。这佐证 §4：路径预测是另一条技术线，不能用现有 CascadeSwitch 代码冒充。

### 6.4 CascadeSwitch 命名核实

外部检索 `"CascadeSwitch"` 无任何同名级联预测论文（命中均为 LLM routing / 能源 regime-switching 等无关工作）。→ **CascadeSwitch 是本项目自造方法名**，非借用已发表方法，原创性命名成立（但也意味着尚无外部引用背书，全靠自证）。

---

## 7. 可辩护的创新一句话

> "CogGuard KT2 的关键技术 CascadeSwitch，把信息级联规模预测重构为**事件条件下的体制切换问题**：用 LLM 把帖子内容显式抽取为外生事件（KOL放大/官方回应/平台干预等），经一个可解释的 W 矩阵 softmax 后验在 seeding/amplification/peak/decay 四体制间动态加权，做**零训练、可跨平台、带置信区间且自带中文解释**的前瞻预测——这正是知微等商业产品所缺、纯统计模型在体制转换点失效、纯 LLM 数值预测不可靠之处的交集。"

（备用短版：用 LLM 做"事件抽取器"而非"数值预测器"，以零训练可解释的体制切换实现级联规模前瞻预测。）

---

## 8. 答辩攻击点 + 反驳

| # | 评委可能的攻击 | 反驳 / 应对 |
|---|---|---|
| A1 | "你们的传播路径预测在哪？" | **坦白这是路线图/未来工作**，当前已落地的是"路径回溯取证（事后）+规模与体制前瞻预测（事前）"。切勿硬称已实现路径预测——会被 §4 证伪。 |
| A2 | "这不就是抄知微吗？" | 知微算法黑盒/不可发表/无预测能力（ZHIWEI:321-339）；我们借鉴产品形态，贡献是知微没有的零训练可解释 regime-switching 预测方法，且跨平台、可在公开基准评估。 |
| A3 | "LLM 到底起了什么作用？演示里好像没调用。" | **最尖锐、最真实**：当前 `propagation_service.py:73` 硬编码 mock_llm=True，线上 LLM 旁路。须在答辩前接通真实 API（llm_context 已具备调用能力），否则只能解释为"LLM 模式已实现，演示环境为控成本/稳定性走 mock，可现场切换"。 |
| A4 | "超越 DeepCas/CasFlow 的数据呢？" | 评估脚本未落地（KT2_COMPLETE_PLAN.md:159-161）。当前只能展示方法与定性案例；定量对比需补 evaluate_cascade.py + 跑 DeepHawkes。**这是结题硬伤，建议优先补。** |
| A5 | "和 CasFT(2409.16619)/LLM-autoregressive(2502.18040) 比有何不同？" | CasFT 端到端训练+隐式线索；2502.18040 让 LLM 直接做数值预测。我们零训练+LLM 仅做可解释事件抽取（Tan et al. 2406.16964 证明 LLM 不擅数值预测）。 |
| A6 | "4 体制的 W 矩阵是手工拍的，凭什么对？" | 承认手工设计（regime_model.py:28-33），但有理论锚点（Hamilton 1989 regime-switching、Bengio&Frasconi 协变量条件 HMM、Jacobs mixture-of-experts，REFERENCE.md:40-87），且零训练即可解释；可做 W 敏感性消融作为后续验证。 |
| A7 | "立场检测、危害评估说有，代码呢？" | 明确为设计稿（FEATURE_STATUS_MATRIX.md:28-29），不要宣称已实现。 |

### 最大风险点（排序）
1. **传播路径预测无设计无代码**——若材料已写"路径预测"必须立刻改口径（缺口/未来工作）。
2. **LLM 线上旁路（mock_llm=True, propagation_service.py:73）**——关键技术卖点演示中不生效。
3. **无评估代码/无基准数值**——"超越 baseline"无实证支撑。


