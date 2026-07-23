# CogGuard 创新性独立核验报告（adversarial novelty check）

> 独立核验者视角，2026-06-02。不盲信 coordination_discover/propagation_analysis/risk-review-findings 里的文献结论，全部用 WebSearch/WebFetch 重新抓 arXiv 摘要核对。
> 标注约定：【真实】= arXiv 页面已确认存在且摘要核对过；【无法独立证实】= 搜不到或仅二手提及。
> 裁决三档：**可辩护/可发表** | **增量(incremental)** | **被覆盖(已有工作做了同一件事)**。

---

## 一、findings 里点名文献的真伪核验（先排雷）

| 文献 | arXiv | 核验结果 | 摘要要点 |
|---|---|---|---|
| Luceri et al. *CIB on TikTok* | 2505.10867 | 【真实】2025-05，v2 2025-10 | 793K TikTok 2024 大选视频。**原文明确**："traditional coordination indicators generalize well to TikTok"，而 transcript 文本相似 + Duet/Stitch 失效。即"行为型协同信号可迁移、内容型不可迁移"是该文**已发表的实证结论**，不是 Coordination Discover 首创。 |
| Schneider, Yuan, Rizoiu *Beyond Content* | 2602.02838 | 【真实】2026-02-02，arXiv preprint，未过审 | "platform-agnostic framework that identifies malicious actors from their behavioral policies"，把用户活动建成序列决策过程。policy 分类器 macro-F1 94.9% vs 文本 91.2%，且"degrade more gracefully under evasion"。**这正是 Coordination Discover 想讲的 behavior-over-content + platform-agnostic + 抗规避，已被人系统化做出并量化。** |
| AutoCas (LLM 自回归 cascade) | 2502.18040 | 【真实】2025-02-25 | 把级联扩散重构成自回归任务，LLM 作 backbone 做 popularity 预测（不是自由文本数值预测，是 tokenize cascade）。 |
| CasFT | 2409.16619 | 【真实】2024-09-25 | neural-ODE 动态线索 + diffusion model 生成 future trend，深度学习、端到端，cascade popularity 预测，提升 2.2–19.3%。 |
| Agentic DISARM (FIMI) | 2601.15109 | 【真实】2026-01-21，ICMCIS 2026 (Bath, 5月) | 多 agent 把观测**映射**到 DISARM 类目，transparent/auditable reasoning，摩尔多瓦大选发现 30+ 俄机器人。**摘要无"预测下一步技术/攻击路径预判"——确属 flat tagging。** |
| Gautam *Multi-agent Misinformation Lifecycle* | 2505.17511 | 【真实】2025-05-23，单作者，preprint | 5 agent（Indexer/Classifier/Extractor/Corrector/Verification）覆盖 检测-纠正-溯源全生命周期。**"misinformation lifecycle + 多 agent + 可解释 + 证据/溯源"已被这篇占位。** |
| Avram et al. *MCP-Orchestrated Multi-Agent Disinfo* | 2508.10143 | 【真实】2025-08-13，SYNASC 2025 | MCP 编排 4 agent 做新闻标题虚假信息检测，95.3% acc。仅 1 个 agent 用 LLM，偏关系抽取，非全生命周期。 |

findings 里点名的 6 篇核心撞车论文**全部为真**，arXiv 号无伪造。年份偏新的 2602.02838 / 2601.15109 也都能在 arXiv 抓到摘要，已确认。

---

## 二、Coordination Discover 协同检测 — 裁决：**增量偏被覆盖（最危险）**

### 最接近的先前工作（双料撞车）
1. **Schneider, Yuan, Rizoiu. *Beyond Content: Behavioral Policies Reveal Actors in Information Operations*. arXiv:2602.02838, 2026.** — 直接撞 Coordination Discover 的核心 thesis。
2. **Luceri et al. *Coordinated Inauthentic Behavior on TikTok*. arXiv:2505.10867, 2025.** — 直接撞 Coordination Discover 的"行为型信号比内容型更可迁移"论证。
3. 旁证：Cinus/Minici/Luceri/Ferrara *Exposing Cross-Platform Coordinated Inauthentic Activity*. arXiv:2410.22716, 2024（跨平台、link-sharing 行为相似）；新出 ACCD *Adaptive Causal Coordination Detection*. arXiv:2601.00400, 2026（因果 CCM + 半监督，跨 Twitter-IRA/Reddit 多数据集）。

### 精确 delta
- Coordination Discover 的两条主张本身——"behavior-over-content"与"platform-agnostic 行为信号更可迁移/抗规避"——**已被 2602.02838 与 2505.10867 分别明确做出并量化**。Coordination Discover 不是首次提出这个命题，最多是**复述既有结论**。
- Coordination Discover 真实落地代码只是 CooRTweet 共享对象配对 + 百分位阈值 + 社区发现（findings 已证 `detector.py` / `network.py`）；声称的 PSL（对称超几何 + Cauchy + pair-level BH-FDR）+ Semantic Adapter + 多通道融合**0 行落地**。
- 唯一可能的真 delta = **PSL 这一套 pair-level 显著性 + FDR 的统计严谨化检测管线**（若真做出来）。这点在 2602.02838（policy 序列分类）和 2505.10867（network pruning）里**没有**对应物——它们不是 pair-level surprisal/FDR 框架。

### 裁决
- "behavior-over-content / platform-agnostic"作为**主创新主张 = 被覆盖**，绝不能作为 Coordination Discover 的卖点首发权来讲，2602.02838 会被评委一句话击穿。
- 若把卖点收窄到"**pair-level 超几何显著性 + Cauchy combine + BH-FDR 的可校准协同配对统计框架（跨平台共享对象通用）**"，且补出落地代码与零分布校准实验，**可降为可辩护的增量方法贡献**。当前因 PSL 未落地，实事求是只能讲工程基线。
- **被夸大的主张**：把"行为优先/平台无关"当成本项目原创洞见。这是 2026 年的既有共识，不是 CogGuard 的发现。

---

## 三、Propagation Analysis 传播监控 — 裁决：规模预测部分**可辩护（窄）**；传播路径预测**不成立（无设计无代码）**

### 最接近的先前工作
- **AutoCas. arXiv:2502.18040, 2025**（LLM 自回归 cascade popularity 预测）。
- **CasFT. arXiv:2409.16619, 2024**（neural-ODE + diffusion future-trend）。
- 经典基线：DeepCas/DeepHawkes/CasFlow（findings 已列），以及 LSTM 级联预测 arXiv:2004.12373。

### 精确 delta
- Propagation Analysis 的 CascadeSwitch = **零训练 + 4 体制 regime-switching（Hamilton-style）+ softmax 后验 + mixture forecast + LLM 仅做可解释事件抽取**（findings: `regime_model.py`/`trend_predictor.py` 已落地）。
- 相对 CasFT/AutoCas 的真 delta 清晰且成立：二者均**重训练深度模型/把 LLM 当数值预测 backbone**；CascadeSwitch **不训练、白盒可解释、LLM 不碰数值**（只抽事件做体制条件先验）。这是一个**架构取向上的真区别**，不是被覆盖。
- 但有两处致命落地缺口（findings 已证，独立核验认同其逻辑）：
  - **`mock_llm=True` 线上硬旁路（`propagation_service.py:73`）→ LLM 在闭环里目前不起作用**，"借鉴知微 + LLM 可解释"的卖点演示时不生效。
  - **无 evaluate_cascade.py / 无 DeepHawkes-CasFlow 基准数值**→"超越 baseline"零实证。

### "传播路径预测"专项裁决
- 独立核验同意 findings：文档里所有"传播路径"都是 `nx.shortest_simple_paths` 在**已观测图**上的关键路径回溯/取证（`propagation_legacy.py`），属 micro-level **重建**，**不是预测未来下一跳/未来结构**。
- 我额外检索了"路径预测"方向（next-hop / 级联结构预测在文献中是独立成熟子领域），CogGuard **既无设计也无代码**对接。
- **被夸大的主张**：若对外材料写"传播路径预测"作为关键技术，**直接证伪**，必须立即改口径为"传播路径重建/关键路径取证"或列入未来工作。这是 Propagation Analysis 最危险的表述风险。

### 裁决
- 规模预测（CascadeSwitch）：**窄可辩护**——零训练可解释 regime-switching 是真 delta，但必须 (a) 接通真实 LLM，(b) 补基准数值，否则降为"方法设计 + 定性案例"。
- 路径预测：**不成立**，按事实改口径。
- 知微借鉴：findings 立场正确——借的是产品形态，知微无公开可发表的预测方法，不构成学术撞车，但也不能反过来当学术创新。

---

## 四、Risk Review 报告研判 — 裁决：硬算法核**可辩护（窄白盒贡献）**；多 Agent+RAG 外壳**被覆盖**

### 最接近的先前工作
- **Tseng et al. *An Agentic Operationalization of DISARM for FIMI*. arXiv:2601.15109, 2026 (ICMCIS).** — 撞 Risk Review 的"agent + DISARM + 可审计推理"外壳。
- **Gautam. *Multi-agent Systems for Misinformation Lifecycle*. arXiv:2505.17511, 2025.** — 撞 Risk Review 的"多 agent + 全生命周期 + 证据/溯源 + 可解释"。
- **Avram et al. arXiv:2508.10143, 2025**（MCP 多 agent 虚假信息检测）。
- 关键独立发现（findings 未点的更危险撞车，在**算法核**层面）：
  - **MITRE TIE (Technique Inference Engine), CTID 2024** + **Markov-chain attack-chain prediction thesis (UMassD)** + **arXiv:2508.18230 (2025, directed-graph inter-phase ATT&CK technique prediction)** — 这些已在 **ATT&CK 域**实现了"**技术转换概率图 → 预测下一步技术 → 多步路径生成**"，正是 Risk Review `disarm_scorer.py`（TRANSITIONS + TRANSITION_PROBS + predict_next_techniques）的算法原语。

### 精确 delta
- Risk Review 真落地的硬核（findings 已证 `phase_detector.py` / `disarm_scorer.py` / `ds_fusion.py` 约 1340 行，CPU 白盒）：**5 阶段生命周期 + logistic hazard breakout 预测 + DISARM 转换图预测下一技术 + 阶段调制 D-S 融合**。
- 相对 2601.15109 的 delta **成立且重要**：2601.15109 是 flat tagging（观测→DISARM 标签），**摘要确无 next-technique/path 预测**；Risk Review 做转换图 + 下一步预测 + 据预测生成反制。这是真区别。
- **但**："技术转换概率图 + 预测下一步技术 + 多步路径评分"这一算法范式在 **ATT&CK/CTI 域已是成熟做法**（MITRE TIE / Markov attack-chain / 2508.18230）。Risk Review 的真 delta 因此**收窄为"把该范式迁移到 DISARM 影响行动域 + 叠加 phase-conditioned hazard + D-S 冲突融合"**，而非"白盒路径预测"本身的原创。
- Phase-Aware Hazard：rumor/cascade 的多阶段 + 早期预警/breakout 预测在文献中已有（多 stage SIR、early-warning signals arXiv:2505.24795，早期扩散信号 UChicago）。Risk Review 的 hazard 是 domain-informed 手工权重 logistic，**delta 在工程可审计性而非建模新颖性**。

### 裁决
- 多 Agent + RAG 报告外壳：**被覆盖**（2505.17511 + 2601.15109 + 2508.10143 三篇已分别占位"多 agent / 生命周期 / DISARM agent / RAG 证据"）。findings 的判断正确：把硬创新藏到这个红海外壳后是把强牌打成弱牌。
- 硬算法核（phase hazard + DISARM 路径预判 + 阶段调制 D-S）：**窄可辩护**——前提是 (a) 主秀讲这三个**已落地、CPU、白盒**的算法，(b) 诚实承认转换图/下一步预测的范式源自 ATT&CK 域、本贡献是 DISARM 迁移 + 阶段条件化，(c) Agent/RAG 仅作呈现壳（且大部分未落地，不能当卖点）。
- **被夸大的主张**：(1) 把"多 Agent+RAG 做报告研判"当创新 = 被覆盖；(2) 暗示"DISARM 路径预测/下一步技术预测"是原创算法 = 范式已存在于 ATT&CK 域，需明确 framing 为跨域迁移而非首创。

---

## 五、总裁决表

| 模块 | 主张 | 裁决 | 最危险撞车 |
|---|---|---|---|
| Coordination Discover | behavior-over-content / platform-agnostic 协同 | **被覆盖** | Schneider/Rizoiu 2602.02838 |
| Coordination Discover | PSL pair-level 显著性框架（若落地） | 增量→可辩护 | 无直接撞车（但 0 行代码） |
| Propagation Analysis | CascadeSwitch 零训练 regime-switching 规模预测 | **窄可辩护** | CasFT 2409.16619 / AutoCas 2502.18040 |
| Propagation Analysis | 传播路径预测 | **不成立（无设计无代码）** | 概念上被任意 next-hop 预测工作压制 |
| Risk Review | 多 Agent+RAG 报告研判 | **被覆盖** | Gautam 2505.17511 / 2601.15109 |
| Risk Review | Phase-Aware Hazard + DISARM 路径预判（白盒 CPU） | **窄可辩护** | MITRE TIE / Markov attack-chain / 2508.18230（算法原语已存在于 ATT&CK 域） |

---

## Sources
- Schneider, Yuan, Rizoiu, *Beyond Content* — https://arxiv.org/abs/2602.02838
- Luceri et al., *CIB on TikTok* — https://arxiv.org/abs/2505.10867
- AutoCas — https://arxiv.org/abs/2502.18040
- CasFT — https://arxiv.org/abs/2409.16619
- Agentic DISARM (FIMI) — https://arxiv.org/abs/2601.15109
- Gautam, *Multi-agent Misinformation Lifecycle* — https://arxiv.org/abs/2505.17511
- Avram et al., *MCP-Orchestrated Multi-Agent Disinfo* — https://arxiv.org/abs/2508.10143
- Cinus/Minici/Luceri/Ferrara, *Exposing Cross-Platform CIB* — https://arxiv.org/abs/2410.22716
- ACCD *Adaptive Causal Coordination Detection* — https://arxiv.org/abs/2601.00400
- LSTM cascade prediction — https://arxiv.org/abs/2004.12373
- MITRE TIE (Technique Inference Engine) — https://ctid.mitre.org/blog/2024/09/09/know-your-adversarys-next-move-with-tie/
- Markov + LSTM attack-chain prediction (UMassD thesis) — https://repository.lib.umassd.edu/esploro/outputs/graduate/Attack-chain-contraction-and-prediction-using/9914504161701301
- ML framework predicting ATT&CK techniques (directed graph) — https://arxiv.org/html/2508.18230v1
- Control/virality early-warning in rumor models — https://arxiv.org/html/2505.24795v2
- Early diffusion signals (UChicago) — https://knowledge.uchicago.edu/records/1kcnx-1bz42
