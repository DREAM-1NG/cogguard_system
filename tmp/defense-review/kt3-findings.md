# KT3 报告研判模块 - 结题答辩 BRUTALLY HONEST 评审

只读分析，未修改任何源代码或 ARIS 文档。所有代码断言均给 file:line（相对仓库根 `g:/CISCN/cogguard_system/`）。区分【已落地代码】与【设计稿】。

---

## 一、代码状态（核实结果）

### 已落地（Layer 1，约 1340 行，全部 Apr-09 提交，真算法非占位）
| 文件 | 行数 | 内容核实 |
|------|------|---------|
| `new-system/backend/app/core/risk/phase_detector.py` | 169 | 真实现：5 状态生命周期 `PHASES`(line 22)、规则分类 `classify_phase`(line 54)、logistic hazard `estimate_hazard`(line 100, `P=sigmoid(w·features+b)` line 115-123)、breakout 时间估计 `detect_phase`(line 158-160) |
| `disarm_scorer.py` | 381 | 真实现：技术转换图 `TRANSITIONS`(line 48)、转换概率 `TRANSITION_PROBS`(line 62)、反制库 `COUNTERMEASURES`(line 84)、下一步预测 `predict_next_techniques`(line 373)、路径评分 depth/breadth/completeness `PathScore`(line 130) |
| `ds_fusion.py` | 234 | 真实现：Dempster 组合 `dempster_combine`(line 123)、冲突质量计算(line 130-141 含 risk∩safe=∅)、阶段调制 `apply_phase_adjustment`(line 104)、信念区间 `BeliefInterval`(line 29)、升级标记(line 213) |
| `evidence_builder.py` | 244 | 多源证据特征构建（协同/传播/账户） |
| `report_builder.py` | 278 | 模板化 JSON 报告组装 + 可解释风险因子 + 处置建议（纯规则，无 LLM） |

实际编排链：`services/risk_service.py:40-45` 直接顺序调用 `detect_phase → fuse_evidence → score_attack_path_full → build_report`。**这是函数调用流水线，不是 Agent 编排。**

### 未落地（Layer 2/3 全部 MISSING — 核实为零文件）
- `llm_bridge.py`（30 行，line 15-30）：三个函数 `generate_summary` / `explain_evidence` / `assess_complex_scenario` **全部 `return None` 占位，含 `# TODO: 接入 LLM API`**。
- `find` 搜索 `*agent* / *rag* / *retriev* / *stance* / *harmful* / *counter-narrative*`：**0 个文件**。
- `risk_service.py` grep `agent|rag|llm|stance|harmful|deepseek`：**0 匹配**。Agent 编排在已落地代码中完全不存在。
- DeepSeek 仅在 `config.py:82-83` 有 `LLM_API_BASE/LLM_MODEL` 配置常量，无任何调用代码。
- TASK_TRACKER WP-A1~A9（升级 llm_bridge、Harmful/Stance/Counter-narrative Agent、RAG 报告）**全部 `[ ]` 未勾选**。

**结论：真正的算法创新（Phase-Aware Hazard + DISARM 路径推理 + D-S 融合）已 100% 落地且能跑；学生新提的"三段 Agent+RAG"设计 0% 落地，纯设计稿。**

---

## 二、新三段设计精确描述（来自 EXPERIMENT_PLAN.md / TASK_TRACKER.md，2026-05-31）

针对导师批评"用 Agent 做报告研判创新性较弱"，学生把报告研判扩为三段：
- **(a) 基于 Agent 的证据编排**：把已有 phase_detector / ds_fusion / disarm_scorer 重新包装成 "Phase Agent / Evidence Agent / DISARM Agent"（EXPERIMENT_PLAN line 16-19）。注意：这是给已有函数贴 "Agent" 标签，算法本身不变。
- **(b) RAG 报告生成**：检索历史报告库 + DISARM 知识库 + 事件证据 → DeepSeek 生成结构化报告（line 21-23, 71-76）。
- **(c) Agent 解释/总结协同攻击**：新增 Harmful Content Agent（恶意言论）、Stance Detection Agent（立场）、Counter-narrative Agent（反制叙事），均为 DeepSeek zero/few-shot（line 25-28, 61-80）。

---

## 三、【裁决：是否解决导师批评】

> ## ❌ 没有解决，反而加重了。
>
> 导师的批评是"**用 Agent 做报告研判创新性较弱**"。学生的回应是"**加更多 Agent + 加 RAG**"。这是用被批评的同一种东西去回应批评——等于承认"研判=LLM 写报告"这个弱框架，然后再叠三个 LLM 包装层。**批评的根因是"创新落在 LLM 编排外壳上"，新设计把外壳做得更厚，根因更突出，不是更弱。**
>
> 更危险的是：新设计把项目真正的硬创新（已落地、能跑、CPU-only 的 Phase-Aware Hazard 预测 + DISARM 攻击路径预判 + D-S 冲突融合）降格为"被 Agent 调用的 tool"，叙事重心从"前瞻性检测算法"漂移到"DeepSeek 生成报告"。**这是把强牌打成弱牌。**

---

## 四、算法创新是否被保留？

**代码层面：保留且完好**。三大算法都在 Layer 1 真实落地（见第一节 file:line），新设计也声称把它们作为 "Agent tools" 复用（EXPERIMENT_PLAN line 36-45 的映射表），不会删除。

**叙事层面：被掩盖/替换**。问题不在代码丢失，而在定位漂移：
- METHOD_STANCE.md（早期，line 5）核心主张是"**阶段感知的风险预测与 DISARM 路径驱动的反制推理框架**"，明确"Prediction over Scoring / Anticipation over Detection"（line 144-149），并明确把"自动 DISARM 映射"列为 **Non-Contribution**（line 71-75）。
- EXPERIMENT_PLAN.md（新，line 7）核心价值主张改为"通过**多 Agent 协作**实现恶意内容检测、立场追踪…**报告输出**"。预测/反制从"主贡献"被稀释成众多 Agent 之一。

即：**硬创新没被删，但被通用 Agent+RAG 外壳盖住了，答辩时评委第一眼看到的是"又一个 LLM 多 Agent 报告系统"。**

---

## 五、离"弱"还是"可辩护"更近？

按任务定义的两个极：
- **弱**："用 Agent+RAG 生成报告" → 导师批评成立。
- **可辩护**："新颖前瞻性检测工具（阶段感知 hazard 预测 + DISARM 攻击路径预判 + 反制）由多 Agent 在虚假信息全生命周期上编排，证据链可审计"。

**当前新设计离"弱"明显更近**，理由：
1. 文档把 RAG 报告生成和三个 LLM Agent 与硬算法"优先级同等"（TASK_TRACKER line 39, EXPERIMENT_PLAN line 47），抹平了主/辅贡献层级。
2. 新增的三个 Agent（Harmful / Stance / Counter-narrative）全是 **DeepSeek zero/few-shot 调用**——这恰恰是"薄包装"的典型形态，无自有方法。
3. 0% 落地：答辩时若主打 Agent+RAG，等于主打一个还没写的、且学术上已被 2505.17511 / 2508.10143 / 2507.09174 占满的方向。

**但"可辩护"的硬件已经在手**（Layer 1 已落地），所以只需 reframing + 极少量补码即可翻盘。

---

## 六、精确重构 / Reframing 方案（让它可辩护）

**一句话定位（替换 EXPERIMENT_PLAN line 7）**：
> "KT3 是一个**阶段感知的前瞻性风险研判引擎**：用 Phase-Aware Hazard 预测战役下一阶段、用 DISARM 攻击路径图预判下一步技术并生成反制、用矛盾感知 D-S 融合输出可审计的信念区间；多 Agent 仅作为**编排与人机接口层**，把这些白盒结果串成可追溯的研判链，LLM 不参与裁决。"

**贡献层级（必须重新分层，对抗"优先级同等"）**：
- **主贡献（demo 主秀）**：Phase-Aware Hazard 预测 + DISARM 路径预判 + 反制（已落地，CPU-only，白盒可解释）。这是和所有 LLM 多 Agent 系统的差异化护城河。
- **次贡献**：矛盾感知 D-S 融合 + 升级标记（已落地）。
- **工程层（明确降级，不当创新卖）**：Agent 编排 + RAG 报告 + DeepSeek 解释。定位为"让白盒结论可读、可审计的呈现层"，**绝不作为创新点**。

**最小补码（让"Agent 编排"名副其实，而非贴标签）**：
1. `llm_bridge.py` 升级为真正调用 DeepSeek 的 `explain_evidence`，**输入限定为 Layer 1 已算出的结构化结果**（阶段/hazard/预测技术/反制/冲突），LLM 只做"把白盒 JSON 翻译成人话"，严禁让 LLM 改分或下结论。这样"可审计"成立。
2. 若时间紧，Stance/Harmful/Counter-narrative 三个 Agent **砍到只保留 Counter-narrative**，且让它消费 `disarm_result.predicted_next`（disarm_scorer.py:373）——把"预测的下一步技术"直接喂给反制叙事生成，形成"预判→反制"闭环。这是唯一能讲出差异化的 Agent，其余两个是红海，建议答辩时只字不提或列为 future work。
3. Demo 严格按 METHOD_STANCE line 135-141：**不展示风险分数仪表盘**，展示阶段时间线 + DISARM 攻击路径图（观测+预测+反制）+ 冲突标记。

核心动作：**把叙事从"我们做了个多 Agent+RAG 报告系统"改回"我们做了个能预判攻击下一步并给反制的白盒引擎，Agent 只是壳"。** 代码几乎不用动，动的是 PPT 和 ARIS 文档的定位句。

---

## 七、文献核实与"创新分界线"

四篇关键文献逐一核实（WebFetch arXiv 摘要页）：

| 文献 | 核实结果 | 真伪 |
|------|---------|------|
| **Multi-agent Systems for Misinformation Lifecycle: Detection, Correction And Source Identification**, Aditya Gautam, arXiv:2505.17511, 2025 | 真实。5 Agent（Indexer/Classifier/Extractor/Corrector/Verification）覆盖全生命周期 | ✅ 真，标题/年份与 TASK_TRACKER 一致 |
| **MCP-Orchestrated Multi-Agent System for Automated Disinformation Detection**, Avram/Groza/Lecu, arXiv:2508.10143, 2025 | 真实。MCP 编排 4 Agent，报 95.3% acc / F1 0.964 | ✅ 真（TASK_TRACKER 漏了 "Automated"，acc 数字对） |
| **RAMA: Retrieval-Augmented Multi-Agent Framework for Misinformation Detection in Multimodal Fact-Checking**, Shuo Yang 等, arXiv:2507.09174, 2025 | 真实。RAG+多 Agent 多模态事实核查 | ✅ 真（TASK_TRACKER 标题略简化，实体 RAMA 对） |
| **An Agentic Operationalization of DISARM for FIMI Investigation on Social Media**, Tseng/Toledano/De Clerck/Dukach/Tinn, arXiv:2601.15109, 2026-01-21（v3 2026-03） | 真实。Agent 化 DISARM 映射，案例发现 30+ 摩尔多瓦 2025 选举俄罗斯 bot | ✅ 真。**这是最危险的直接前作** |

（其余 2410.20140 多 Agent 辩论、2504.15548 LLM 语义增强有害内容检测，均经核实为真。）

**创新分界线（多 Agent 虚假信息系统 "有创新" vs "薄包装"）**：
> **薄包装** = 把现成 LLM 当各 Agent，靠 prompt 分工做 detection/分类/写报告，创新落在"编排拓扑/MCP/RAG 接法"上。2505.17511、2508.10143、2507.09174、2601.15109 已把这条线全占满，且都有数据集和指标。
>
> **有创新** = Agent 编排的是**别人没有的自有白盒方法**，且系统回答 SOTA 不回答的问题。分界三问：(1) 去掉 LLM 后还剩不剩独立可验证的方法？(2) 系统是否做了纯 detection/分类之外的事（预测/反制/不确定性量化）？(3) 结果可否脱离 LLM 黑盒被审计？

**学生方案落哪边**：
- 若主打 (b)RAG 报告 + (c) 三个 DeepSeek Agent → **落在薄包装侧**，且正面撞上 2601.15109（Agentic DISARM 已是公开前作，"DISARM Agent 化"不再新颖）。
- 若主打**已落地的 Phase-Aware Hazard 预测 + DISARM 路径预判 + 反制 + D-S 冲突融合** → **落在有创新侧**：三问全过——去掉 LLM 这些方法独立可验证（CPU-only 已跑）；做了预测+反制+信念区间（超出 detection）；白盒可审计。**关键差异化：2601.15109 只做 detection/mapping（"观测到什么"），KT3 做 anticipation+countermeasure（"下一步+怎么拦"），且不依赖 LLM。**

---

## 八、答辩攻击点 + 反驳

**攻击 1（导师原批评升级版）**："多 Agent + RAG 生成报告，2505.17511 / 2508.10143 / 2507.09174 早做了，你的 Agent 编排有何新意？"
- **反驳**："Agent 编排不是我们的创新点，是工程呈现层。创新在被编排的白盒方法：阶段感知 hazard 预测 + DISARM 攻击路径预判 + 反制推理。这些去掉 LLM 仍独立可验证（CPU-only 已落地约 1340 行）。SOTA 多 Agent 系统做的是 detection，我们做的是 anticipation + countermeasure。" 现场演示阶段时间线 + 攻击路径图。

**攻击 2（最致命）**："2601.15109 已经把 DISARM 做成 Agent 了，你这是重复工作。"
- **反驳**："2601.15109 是 flat tagging——把观测映射到 DISARM 标签，回答'观测到什么'。我们是 path reasoning——构建技术转换图（disarm_scorer.py:48 TRANSITIONS + line 62 转换概率），预测下一步技术（line 373）并据预测路径生成反制（COUNTERMEASURES line 84）。我们回答'下一步会发生什么 + 如何拦截'。而且我们 CPU-only、白盒可审计，不依赖 GPU/LLM 黑盒。" （见 METHOD_STANCE line 27-41 对比表。）

**攻击 3（落地性，最难防）**："你 PPT 讲的三个 Agent + RAG，代码在哪？"
- **诚实反驳**："Layer 1 检测研判算法已完整落地并通过 API 跑通（risk_service.py:40-45）。Agent 编排层与 RAG 是工程化呈现层，部分为 roadmap。我们的核心贡献是已验证的算法，不是未完成的 Agent。" **切忌把未写的 Agent+RAG 当成核心卖点——会被一句"代码呢"击穿。**

**攻击 4**："Phase 5 状态、DISARM 转换概率都是手工设的，凭什么可信？"
- **反驳**："这是 domain-informed operational prior，不是 descriptive taxonomy（METHOD_STANCE line 155-159）。验证关注预测有用性（breakout 前能否预警）而非分类完美性，可随实战数据迭代权重（hazard_weights 在 risk_config.yaml 可调）。"

**攻击 5**："D-S 融合是老方法。"
- **反驳**："D-S 是辅助贡献，新点在 phase-conditioned mass adjustment（ds_fusion.py:104）——置信度随战役阶段动态调制 + 冲突质量触发人工复核升级（line 213）。输出信念区间而非点估计，避免虚假确定性。"

---

## 附：一句话总结给学生
代码很好，叙事很糟。**别把已经跑通的硬创新藏到一个还没写、且学术上已是红海的"多 Agent+RAG 报告"壳子后面。** 把 PPT 主秀换成阶段预测 + 攻击路径预判 + 反制（这些已落地），Agent 只当壳和人机接口，答辩就从"弱"翻成"可辩护"。
