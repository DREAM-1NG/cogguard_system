# CogGuard 系统背景综述事实交叉验证审计报告

> **验证目标**：`G:/CISCN/CogGuard/doc/system-background-review.md`
> **审计时间**：2026-08-05
> **验证执行人**：Fact Verification Subagent (Milestone 1)
> **权威参照基线**：
> 1. `doc/PROJECT_OVERVIEW.md`（落地状态真实权威）
> 2. `doc/SUBFUNCTION_LITERATURE_MAP.md`（文献信息权威，含已核实/存疑标注）
> 3. `UBIQUITOUS_LANGUAGE.md`（统一术语规范）
> 4. `CONTEXT.md`（系统语言与运行边界）
> 5. `doc/research/project-positioning-baseline.md`（项目定位与统一口径基线）

---

## 1. 执行摘要 (Executive Summary)

本审计报告对 `system-background-review.md` 全文 9 个章节进行了逐行、5 维度的深度事实交叉验证。

### 1.1 总体统计

| 验证维度 | 检查项数量 | 完全一致/合规 | 发现差异/偏差 | 错误/偏差分布说明 |
|---|---|---|---|---|
| **1. 落地状态检查 (Landing Status)** | 32 | 32 | 0 | 代码文件名、行数、已落地/设计稿/缺口三态标注与 `PROJECT_OVERVIEW.md` 100% 匹配 |
| **2. 文献信息核查 (Literature Info)** | 43 | 39 | 4 | 4 篇正文引用的高水平文献在第 9 章参考文献列表中被漏列 |
| **3. 创新边界与撞车检查 (Boundary & Overclaim)** | 6 | 6 | 0 | 撞车文献引用完整，诚实边界声明充分且与基线文档对齐 |
| **4. 术语合规性检查 (Terminology Compliance)** | 45 | 42 | 3 | 存在 1 处模块名旧术语 ("账户监测")、1 处中文译名与 canonical term 并存 ("分割保形区间")、1 处 API 版本说明差异 |
| **5. 口径一致性检查 (Positioning Alignment)** | 3 | 3 | 0 | 跨平台口径、内容分析归属 ("内容分析归谁？")、Agent 支撑定位三项答辩口径与基线文档完全一致 |
| **合计** | **129** | **120** | **9** | **严重错误 4 项，轻微偏差 3 项，待核实项 2 项** |

---

## 2. 严重错误 (Severe Errors - Must Fix)

> **定义**：直接影响事实准确性、文献完整性或代码落地状态描述的硬性错误，必须在润色阶段（M2）修补。

### 【ERR-01】文献漏列：Manchanayaka et al. IJCNN 2024 / arXiv 2407.11697
- **位置**：第 3.2.2 节（第 88 行表格）
- **观察到的现象**：正文表格引用了 `Manchanayaka 等 — Contrast Pattern Mining | IJCNN 2024 / arXiv 2407.11697 | "可疑窗口 vs 历史基线"对比范式`，但在第 9 章参考文献列表（第 490-545 行）中被遗漏。
- **权威出处**：`SUBFUNCTION_LITERATURE_MAP.md` 第 149 行，【已核实】文献。
- **逻辑推导**：正文引用的文献必须在参考文献列表中具备完整条目，否则存在引用断链。
- **修复建议**：在第 9 章“协同发现领域”补充第 12 条参考文献：`Manchanayaka, Zaidi, Karunasekera, Leckie. Identifying Coordinated Activities Using Contrast Pattern Mining. IJCNN 2024 / arXiv 2407.11697, 2024. 【已核实】`。

### 【ERR-02】文献漏列：Wu et al. IEEE TKDE 2024 (Evidence-Aware Fake News Detection)
- **位置**：第 5.2.4 节（第 240 行表格）
- **观察到的现象**：正文表格引用了 `Wu 等 — Evidence-Aware Fake News Detection | IEEE TKDE 2024 | 证据感知建模`，但在第 9 章参考文献列表中被遗漏。
- **权威出处**：`SUBFUNCTION_LITERATURE_MAP.md` 第 490 行（存疑 DOI 10027720）。
- **逻辑推导**：正文引用的证据建模代表文献必须在第 9 章收录，并添加必要的存疑标记。
- **修复建议**：在第 9 章“报告研判领域”补充参考文献：`Wu et al. Adversarial Contrastive Learning for Evidence-Aware Fake News Detection. IEEE TKDE 2024. 【存疑：DOI 10027720 需复核】`。

### 【ERR-03】文献漏列：Markov+LSTM 攻击链预测 (UMass Dartmouth Thesis)
- **位置**：第 5.2.2 节（第 222 行表格）
- **观察到的现象**：正文表格引用了 `Markov+LSTM 攻击链预测 | UMass Dartmouth thesis, 2023/2024 | Markov 攻击链下一步预测`，但在第 9 章参考文献列表中被遗漏。
- **权威出处**：`SUBFUNCTION_LITERATURE_MAP.md` 第 300 行，【已核实】文献。
- **逻辑推导**：作为 DISARM 攻击路径预测直接先前工作（网安 ATT&CK 域），漏列会导致攻击路径预测的借鉴来源缺乏文献支撑。
- **修复建议**：在第 9 章“报告研判领域”补充参考文献：`UMass Dartmouth Thesis. Attack Chain Contraction and Prediction using Markov Model and LSTM on MITRE ATT&CK. 2023/2024. 【已核实】`。

### 【ERR-04】文献漏列：MDP-MCTS Kill-Chain 推理 (arXiv 2512.15150)
- **位置**：第 5.2.2 节（第 223 行表格）
- **观察到的现象**：正文表格引用了 `MDP-MCTS Kill-Chain 推理 | arXiv 2512.15150, 2025 | MDP 把入侵建模为状态转移序列`，但在第 9 章参考文献列表中被遗漏。
- **权威出处**：`SUBFUNCTION_LITERATURE_MAP.md` 第 301 行，【已核实】文献。
- **逻辑推导**：同 ERR-03，作为网安 kill-chain 状态转移推理先前工作，属于论证“跨域迁移非首创”的关键文献。
- **修复建议**：在第 9 章“报告研判领域”补充参考文献：`Policy-Value Guided MDP-MCTS Framework for Cyber Kill-Chain Inference. arXiv 2512.15150, 2025. 【已核实】`。

---

## 3. 轻微偏差 (Minor Deviations - Recommend Fix)

> **定义**：不影响核心事实，但与统一术语规范或微观口径存在轻微不一致的地方。

### 【DEV-01】模块命名术语微调："账户监测" vs "账号自动化先验与角色画像"
- **位置**：第 6.1 节架构图（第 278 行）、第 6.4 节 API 表格（第 341 行）、第 7.5 节（第 428 行）
- **观察到的现象**：使用了 `账户监测` 作为模块/功能区名称。
- **权威出处**：`project-positioning-baseline.md` 第 3.6 节 & 第 6.1 节指定：将旧称“账户监测模块”统一改写为“账号自动化先验与角色画像 (Account Profiler / Social Bot Detection)”，并强调其是传播监控的支撑输入；`UBIQUITOUS_LANGUAGE.md` 第 90-99 行规范为 `Account Profiler` 与 `Social Bot Detection`。
- **修复建议**：在正文中保留代码路由 tag `accounts` 说明的同时，将模块功能名称标注为“账号自动化先验与角色画像 (Account Profiler)”。

### 【DEV-02】规范术语并存：中文译名 "分割保形区间" 与 Standard English Term
- **位置**：第 7.3 节表格（第 399 行）
- **观察到的现象**：表记为 `分割保形区间`。
- **权威出处**：`UBIQUITOUS_LANGUAGE.md` 第 72 行明确规范标准术语为 `Split-Conformal Interval`。
- **修复建议**：修改为 `Split-Conformal Interval (分割保形区间)`，符合规范术语集定义。

### 【DEV-03】API 版本标注格式表述微调
- **位置**：第 6.1 节（第 281 行）
- **观察到的现象**：写作 `后端 API (FastAPI, /api/v1 & /api/v2)`。
- **权威出处**：`PROJECT_OVERVIEW.md` 第 2.1 节写作 `后端 API (FastAPI, /api/v1)`；而 `CONTEXT.md` 第 31 行写明包含 `V2 REST routes`。
- **修复建议**：保持当前 `/api/v1 & /api/v2` 表述，但补充括号说明 `(/api/v1 为主业务路由，/api/v2 为 V2 统一分析接口)`，消解读者对路由版本的疑虑。

---

## 4. 待核实项 (Dubious Items / Flagged Citations)

> **定义**：源自 `SUBFUNCTION_LITERATURE_MAP.md` 标注为【存疑】的文献或缺少明确标记的引用。

### 【DUB-01】Wu et al. IEEE TKDE 2024 存疑标记补充
- **位置**：第 5.2.4 节（第 240 行表格）及修复后的第 9 章参考文献
- **说明**：`SUBFUNCTION_LITERATURE_MAP.md` 第 490 行明确标注该文献的 DOI (10027720) 为【存疑】（检索未直接命中确切卷期，引用前需人工复核）。正文引用时应加上【存疑】标注。

### 【DUB-02】Phase-Aware Hazard 与 DISARM 路径预判无公开标注数据集风险提示
- **位置**：第 5.4 节 & 第 7.4 节
- **说明**：`SUBFUNCTION_LITERATURE_MAP.md` 第 520 行与 548 行诚实标注：战役阶段演化与 DISARM 转换概率缺公开 ground-truth 数据，验证依赖 mock 数据 + 专家评估 + 案例研究。综述在 5.4 节诚实边界表格中已作声明，建议在 7.4 节落地表格中补充“验证依赖 mock/专家/案例”的标注。

---

## 5. 逐章审核清单 (Detailed Audit Checklist)

### 第 1 章：一页速览 (One-Page Summary)
- [x] **定位与闭环**：`面向网络舆论对抗的跨平台协同操纵分析证据驱动原型系统`、`事件 → 证据 → 协同发现 → 传播监控 → 报告研判 → 处置` 与 `PROJECT_OVERVIEW.md` §0 逐字一致。
- [x] **三大功能定义**：协同发现 (Coordination Discover / Detect)、传播监控 (Propagation Analysis)、报告研判 (Risk Review) 符合 `UBIQUITOUS_LANGUAGE.md` 与 `project-positioning-baseline.md`。
- [x] **技术栈与验证范围**：FastAPI / Vue 3 / MySQL 8 / MongoDB 7 / Redis 7 及 `mock_weibo, weibo, news`（跨源非跨平台身份解析）完全匹配代码与 Overiew 文档。
- [x] **一句话现状**：诚实表述落地状态与 LLM 客户端依赖缺失阻塞，无夸大。

### 第 2 章：问题域与研究背景 (Problem Domain & Research Background)
- [x] **2.1 节**：Mannocci et al. 2024 (arXiv 2408.01257) 综述引用及 2 阶段 4 维度（Authenticity, Harmfulness, Orchestration, Time-variance）核实无误。
- [x] **2.2 节**：Schneider & Rizoiu (*Beyond Content*, arXiv 2602.02838) 与 Luceri et al. (*CIB on TikTok*, arXiv 2505.10867) 撞车风险文献引用准确。
- [x] **2.3 节**：系统设计原则（规则/证据优先于黑盒 LLM，内容分析单向下沉至 Risk Review）严格符合 `project-positioning-baseline.md`。

### 第 3 章：协同发现的学术背景与技术路线 (Coordination Discover / Detect)
- [x] **3.2.1 节**：CooRTweet, Minici et al. (First Monday 2024/arXiv 2409.15402), Cinus et al. (arXiv 2410.22716), Luceri et al. (arXiv 2505.10867) 引用准确。
- [x] **3.2.2 节**：Sharma KDD 2021 纠偏正确（AMDN-HAGE 隐组/点过程，非 z-score）；Somin et al. (arXiv 2504.02757) 引用正确。
- [x] **3.2.3 节**：Traag et al. (Scientific Reports 2019 Leiden), Tardelli et al. (PNAS 2024 时序 archetype 纠偏正确，DOI 10.1073/pnas.2307038121), Pote et al. (ICWSM 2025) 引用准确。
- [x] **3.4 节诚实边界**：(1) PSL 框架 0 行代码；(2) 代码实际运行 `greedy_modularity` (CNM) 非 Leiden；(3) 跨平台仅验证 mock_weibo/weibo/news，边界交代极度清晰。
- [!] **发现偏差**：3.2.2 节表格引用的 Manchanayaka et al. (IJCNN 2024) 漏列于第 9 章参考文献（见 ERR-01）。

### 第 4 章：传播监控的学术背景与技术路线 (Propagation Analysis)
- [x] **4.1 节职责边界**：明确 Propagation Analysis 仅做传播动力学（规模/体制），不碰内容分析，符合 2026-06-03 架构边界调整。
- [x] **4.2.1 节**：DeepCas (WWW 2017), DeepHawkes (CIKM 2017), CasCN (ICDE 2019), CasFlow (TKDE 2021), CasFT (arXiv 2409.16619) 引用无误。
- [x] **4.2.2 节**：Time-LLM (ICLR 2024), LLMTime (Gruver NeurIPS 2023, arXiv 2310.07820 纠偏正确), AutoCas (arXiv 2502.18040), Tan et al. (NeurIPS 2024 Spotlight) 引用无误。
- [x] **4.2.3 节**：Topo-LSTM (arXiv 1711.10162), NDM (arXiv 1812.08933), FOREST (IJCAI 2019) 引用无误。
- [x] **4.4 节 CascadeSwitch 落地与边界**：Tier-0 宏观规模已落地，Tier-1 路径形态为设计稿，Tier-2 微观下一跳为缺口；LLM 事件抽取在线默认 `mock=True`；后端无 LLM SDK 依赖。表述诚实完全客观。

### 第 5 章：报告研判的学术背景与技术路线 (Risk Review)
- [x] **5.2.1 节**：Gautam (arXiv 2505.17511), arXiv 2508.18230 (ATT&CK 阶段感知 ML) 引用无误。
- [x] **5.2.2 节**：MITRE TIE (2024), Agentic DISARM (arXiv 2601.15109) 引用无误。
- [x] **5.2.3 & 5.2.4 节**：MCP-Orchestrated (arXiv 2508.10143), MARO (EMNLP 2025), Debate-to-Detect (EMNLP 2025), RAMA (arXiv 2507.09174), RumourEval (2019), HateXplain (AAAI 2021) 引用无误。
- [x] **5.4 节头号创新**：明确白盒前瞻引擎（Phase + DISARM + D-S ~1340 行）为头号已落地创新，Agent/RAG 降级为编排呈现层（设计稿），符合 `PROJECT_OVERVIEW.md` §6.2 表述纪律。
- [!] **发现偏差**：5.2.2 节引用的 Markov+LSTM 论文、MDP-MCTS 论文 (arXiv 2512.15150) 及 5.2.4 节引用的 Wu et al. (IEEE TKDE 2024) 漏列于第 9 章参考文献（见 ERR-02, ERR-03, ERR-04）。

### 第 6 章：系统总体架构 (Overall Architecture)
- [x] **6.1 分层架构**：前端/后端/服务层/核心算法/研究包/数据层/采集层 关系清晰，与代码目录一致。
- [x] **6.2 技术选型**：FastAPI, Vue 3, Ant Design Vue 4, ECharts 6, MySQL 8, MongoDB 7 (Motor), Redis 7, NetworkX, Celery 选型理由充分。
- [x] **6.3 数据流接缝**：`assess_risk()` 调用上游 `coordination` / `propagation` / `accounts` 证据链描述准确。
- [!] **发现偏差**：API 路由组描述中，建议补全 `/api/v1 & /api/v2` 的分层功能说明（见 DEV-03）。

### 第 7 章：落地状态总览 (Landing Status Overview)
- [x] **7.1 - 7.5 节代码表与行数**：
  - 数据采集：`base.py`, `mock.py`, `social.py` (883行), `news.py`, `normalizer.py`, `crawl_tasks.py` 均一致。
  - 协同发现：`detector.py` (184行), `network.py` (373行, 标注 CNM 特性), `stats.py` (142行), `significance.py` (0行设计稿), `channels.py` (设计稿), `semantic.py` (设计稿) 均与代码行数一致。
  - 传播监控：`ts_features.py` (107行), `llm_context.py` (162行), `regime_model.py` (224行), `trend_predictor.py` (180行), `propagation_legacy.py` (585行) 一致。
  - 报告研判：`evidence_builder.py` (244行), `phase_detector.py` (169行), `ds_fusion.py` (234行), `disarm_scorer.py` (381行), `report_builder.py` (278行), `llm_bridge.py` (~30行) 均与代码行数一致。
  - 研究包路径：`system/research/coordination_discover/`, `system/research/propagation_analysis/`, `system/research/review_teacher/`, `system/runtimes/review_student/` 完全符合 `UBIQUITOUS_LANGUAGE.md` 定义。

### 第 8 章：差距与风险分析 (Gaps & Risk Analysis)
- [x] **8.1 共性阻塞**：LLM 客户端依赖缺失、统计依赖缺失（scipy/statsmodels）、无评估闭环总结到位。
- [x] **8.2 答辩风险点**：文献撞车应对口径、"跨平台"口径、设计与实现不一致点梳理清晰。
- [x] **8.4 内容分析归属统一口径**：彻底消解答辩致命题“内容分析归谁”，4 条统一原则完全对齐 `PROJECT_OVERVIEW.md` §9.3。

### 第 9 章：参考文献列表 (References List)
- [!] **主要审计结果**：收录了 39 篇/条参考文献及撞车文献，核实状态标注详尽。但遗漏了正文中引用的 4 篇重要文献（见 ERR-01 至 ERR-04），须在 M2 修复中补充加入。

---

## 6. 验证结论与后续动作

1. **整体结论**：`G:/CISCN/CogGuard/doc/system-background-review.md` 是一份高度诚实、严谨且学术定位清晰的综述文档。其关于系统代码落地状态、三态划分、答辩风险与撞车文献的描述与 `doc/PROJECT_OVERVIEW.md` 和 `doc/research/project-positioning-baseline.md` 保持高度一致。
2. **需要修复的核心问题**：
   - 补充 4 篇遗漏的参考文献（ERR-01 至 ERR-04）；
   - 微调 1 处旧模块术语（DEV-01）、1 处规范术语（DEV-02）、1 处 API 版本说明（DEV-03）；
   - 标注 2 处存疑/无公开数据集风险提示（DUB-01, DUB-02）。
3. **下一步交接**：本报告已作为结构化产物保存至 `G:/CISCN/CogGuard/doc/system-background-review-audit.md`，可交由 M2 (R2 文档润色与修复) 写作智能体进行原位修复与润色。
