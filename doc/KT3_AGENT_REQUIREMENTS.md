# KT3 Agent Requirements: Research Mapping, Datasets, and Gap Analysis

## 1. Positioning

KT3 is positioned as a coordinated-community harmfulness characterization and response module. It receives posts, accounts, propagation evidence, and coordination evidence from upstream KT1/KT2 modules, then runs a closed loop:

```text
detect harmfulness -> map manipulation technique -> generate countermeasure -> report -> optimize
```

Multimodal fact-checking is one sub-agent in this loop. The full KT3 scope also includes hate/harm detection, stance/narrative analysis, community-level harmfulness judgment, DISARM mapping, countermeasure generation, report generation, and optimization.

Current implementation is a deterministic multi-agent baseline in `new-system/backend/app/core/risk/agents.py`. It provides stable input/output contracts and report fields, but most agents are still rule/template based and should not be described as fully reproducing the cited papers.

## 1.1 中文总结

KT3 的研究定位不是单独做“多模态事实核查”，而是面向协同群体分析中的 harmfulness characterization。按照 Mannocci et al. 2024 对协同行为分析的框架，上游模块先完成 Detect，输出协同账号、共享对象、传播链路和社区结构；KT3 接续完成 Characterize，重点回答这个协同群体是否有害、有害性体现在哪些内容和行为上、是否构成信息操纵技术、应该如何反制，以及如何把人工反馈用于下一轮优化。

当前系统已经实现了一个可运行的闭环骨架：

```text
帖子/账户/协同网络输入
-> Evidence Builder
-> FactCheck Agent + Hate/Harm Agent + Stance/Narrative Agent
-> Community Harm Judge
-> DISARM Mapping Agent
-> Countermeasure Agent
-> Report Agent
-> Optimization Agent trace
```

但当前实现仍是 deterministic baseline：事实核查主要基于内部帖子中的支持/反驳/求证线索，仇恨检测主要基于词典和规则，社区裁决是手工加权融合，反制叙事是安全模板，优化模块只记录 failure modes 与下一步动作，还没有真正执行 MARO 式自动规则搜索。

因此当前贡献应表述为：

```text
已完成 KT3 多智能体闭环系统骨架、统一接口、报告字段和可测试 baseline。
```

不应表述为：

```text
已完成 SOTA 多模态事实核查、仇恨检测、反制叙事生成或自动优化算法复现。
```

## 2. Agent Design Matrix

| Agent | Current implementation | Key references | Validation datasets | Current gap | Required improvement |
|---|---|---|---|---|---|
| Evidence Builder / Orchestrator | Builds `evidence_pack` from posts, coordination, propagation, and account profiles; orchestrates agent mode through `risk_service.assess_risk()` | Mannocci et al. 2024 coordinated behavior survey: https://arxiv.org/abs/2408.01257; CooRnet/CLSB: https://dl.acm.org/doi/10.1145/3400806.3400817; CooRTweet: https://github.com/nicolarighetti/CooRTweet | Local KT1/KT2 coordinated groups; CooRnet/CooRTweet-compatible sharing logs; PHEME rumor conversation data: https://figshare.com/articles/dataset/PHEME_dataset_for_Rumour_Detection_and_Veracity_Classification/6392078 | Orchestration is sequential and deterministic; no explicit task graph, retries, agent-level confidence calibration, or evidence provenance schema | Define `EvidencePack` schema; store agent traces; add source provenance for every evidence item; add asynchronous/parallel agent execution only after contracts stabilize |
| FactCheck Agent | Groups posts by URL/hashtag and uses internal support/refute/query cues to output `supported/refuted/conflicting/not_enough_evidence` | MOCHEG, SIGIR 2023: https://dl.acm.org/doi/10.1145/3539618.3591879 and dataset/code: https://github.com/VT-NLP/Mocheg; AVerTeC shared task: https://aclanthology.org/2024.fever-1.1/ and dataset: https://fever.ai/dataset/averitec.html; SAFE, NeurIPS 2024: https://arxiv.org/abs/2403.18802 and code/data: https://github.com/google-deepmind/long-form-factuality; NewsCLIPpings, EMNLP 2021: https://aclanthology.org/2021.emnlp-main.545/ and dataset: https://github.com/g-luo/news_clippings; FACTIFY: https://ceur-ws.org/Vol-3199/paper18.pdf and dataset: https://github.com/Shreyashm16/Factify | AVerTeC: https://github.com/MichSchli/AVeriTeC; MOCHEG: https://github.com/VT-NLP/Mocheg; NewsCLIPpings: https://huggingface.co/g-luo/news-clippings; FACTIFY: https://github.com/Shreyashm16/Factify | No Web/RAG retrieval; no image/video evidence; no entailment model; no AVerTeC-style evidence-quality score; no claim decomposition beyond simple question templates | Implement `claim extraction -> query generation -> retrieval -> evidence reranking -> NLI/verdict -> explanation`; use AVerTeC for text evidence QA, MOCHEG/FACTIFY/NewsCLIPpings for multimodal verification; evaluate verdict macro-F1, evidence recall, and evidence quality |
| Hate/Harm Agent | Extends harmful keyword baseline with target group, dehumanization, threat, category, and rationale fields | HateXplain, AAAI 2021: https://ojs.aaai.org/index.php/AAAI/article/view/17745 and dataset/code: https://github.com/hate-alert/HateXplain; HateCheck, ACL 2021: https://aclanthology.org/2021.acl-long.4/ and dataset: https://github.com/paul-rottger/hatecheck-data; Jigsaw Toxic Comment Classification: https://www.kaggle.com/c/jigsaw-toxic-comment-classification-challenge; Jigsaw Unintended Bias: https://www.kaggle.com/c/jigsaw-unintended-bias-in-toxicity-classification | HateXplain HF mirror: https://huggingface.co/datasets/Hate-speech-CNERG/hatexplain; HateCheck HF mirror: https://huggingface.co/datasets/Paul/hatecheck; Jigsaw Toxicity Kaggle: https://www.kaggle.com/c/jigsaw-toxic-comment-classification-challenge | Rule dictionary cannot handle implicit hate, sarcasm, reclaimed slurs, context, multilingual variants, or bias calibration | Train/evaluate target-aware classifier with `label + target_group + rationale`; use HateCheck for functional diagnostics; use Jigsaw for toxicity subtypes; add Chinese/local labeled data for domain transfer |
| Stance/Narrative Agent | Reuses rule-based stance detector and adds narrative actions: amplification, correction/query, sensational framing, attack framing | RumourEval 2019: https://aclanthology.org/S19-2147/ and data repo: https://github.com/kippfreud/RumourEval; PHEME: https://figshare.com/articles/dataset/PHEME_dataset_for_Rumour_Detection_and_Veracity_Classification/6392078; MDFEND, CIKM 2021: https://dl.acm.org/doi/10.1145/3459637.3482139 and Weibo21 code/data: https://github.com/kennqiang/MDFEND-Weibo21 | RumourEval 2019 HF mirror: https://huggingface.co/datasets/strombergnlp/rumoureval_2019; PHEME: https://figshare.com/articles/dataset/PHEME_dataset_for_Rumour_Detection_and_Veracity_Classification/6392078; Weibo21 split data: https://github.com/kennqiang/MDFEND-Weibo21 | No conversation-tree modeling; no temporal stance evolution; no claim-specific target encoding beyond text match | Replace rule detector with target-aware stance model; model support/deny/query/comment over conversation threads; add narrative role labels for amplification and correction |
| Community Harm Judge | Fuses post harmful ratio, hate ratio, fact conflict, coordination counts, propagation edges, automation score, and amplification ratio | Mannocci et al. 2024: https://arxiv.org/abs/2408.01257; MARO, EMNLP 2025: https://aclanthology.org/2025.emnlp-main.291/; TELLER, ACL Findings 2024: https://aclanthology.org/2024.findings-acl.919/ | Local annotated communities from KT1/KT2; CooRTweet-compatible coordinated-sharing networks; proxy datasets: PHEME and Weibo21 for rumor/misinformation groups | Weighted rule fusion is manually chosen; no calibrated uncertainty; no learned logic rules; no held-out community-level labels | Build a labeled community-level validation set; learn/calibrate fusion rules; use TELLER-style logic atoms for explainability; add MARO-style judge prompts once LLM mode is available |
| DISARM Mapping Agent | Maps harmfulness, coordination, fact conflict, and community harmfulness to simplified tactics/techniques | DISARM framework: https://github.com/DISARMFoundation/DISARMframeworks/; DISARM official framework page: https://www.disarm.foundation/framework; DISARM Navigator: https://disarmfoundation.github.io/disarm-navigator/ | DISARM master data in `DISARM_FRAMEWORKS_MASTER.xlsx`: https://github.com/DISARMFoundation/DISARMframeworks/; local analyst-labeled TTP mappings | Current mapping covers only a few simplified techniques; no full DISARM ontology, no STIX export, no multi-label TTP ranking | Import DISARM master data; create evidence-to-TTP mapping table; add multi-label ranking and confidence; support analyst correction and STIX-compatible export |
| Countermeasure Agent | Generates fact correction, counter-narrative, community handling, and optimization suggestions from fact/hate/community results | CONAN, ACL 2019: https://aclanthology.org/P19-1271/ and dataset: https://github.com/marcoguerini/CONAN; Generate-Prune-Select, ACL Findings 2021: https://github.com/WanzhengZhu/GPS; Fact-based counter-narrative generation: https://dspace.mit.edu/bitstream/handle/1721.1/162842/3696410.3714718.pdf | CONAN: https://github.com/marcoguerini/CONAN; Target-CONAN / multi-target variants should be added when available; local analyst-rated response set | Current output is template based; no retrieval-grounded response generation; no safety/helpfulness ranking; no target-specific cultural adaptation | Implement `generate -> safety filter -> evidence grounding -> ranking`; use CONAN for counter-narrative pairs; add human evaluation for helpfulness, non-escalation, and factual grounding |
| Report Agent | Produces structured JSON and compact Markdown report with fact-check, hate, community harmfulness, DISARM, countermeasures, evidence table, and optimization trace | MOCHEG explanation generation: https://dl.acm.org/doi/10.1145/3539618.3591879; AVerTeC evidence-quality evaluation: https://fever.ai/dataset/averitec.html; TELLER explainable logic atoms: https://aclanthology.org/2024.findings-acl.919/ | MOCHEG explanation data: https://github.com/VT-NLP/Mocheg; AVerTeC QA/evidence justifications: https://github.com/MichSchli/AVeriTeC; local analyst report rubrics | Markdown is basic; no PDF renderer; no report completeness scoring; no citation/provenance table beyond flattened evidence rows | Add report schema validation; add PDF/HTML export; include source provenance and confidence; evaluate report completeness and analyst acceptance |
| Optimization Agent | Records failure modes, metrics to track, and next actions for MARO-style optimization, but does not update rules yet | MARO, EMNLP 2025: https://aclanthology.org/2025.emnlp-main.291/; APO, EMNLP 2023: https://aclanthology.org/2023.emnlp-main.494/; DSPy: https://arxiv.org/abs/2310.03714 and framework: https://github.com/stanfordnlp/dspy; OPRO, ICLR 2024: https://openreview.net/forum?id=Bb4VGOWELI and code: https://github.com/google-deepmind/opro | MARO uses Weibo21 and AMTCele; Weibo21 link: https://github.com/kennqiang/MDFEND-Weibo21; for KT3 use local held-out analyst labels plus AVerTeC/HateXplain/RumourEval task splits | Trace only; no automatic rule/prompt search; no validation-task loop; no top-N rule voting; no human-feedback store | Add `feedback_cases` collection; run validation tasks per agent; implement MARO-style candidate decision-rule generation and selection; add top-N rule voting and rollback |

## 2.1 文献方法、当前方法与差距分析

### 2.1.1 Evidence Builder / Orchestrator

参考文献方法：

- Mannocci et al. 2024 将协同行为研究分为 Detect 与 Characterize 两阶段，并提出 authenticity、harmfulness、orchestration、time-variance 四个正交刻画维度。该综述对 KT3 的最大价值是任务边界定义：KT3 不再只判断单条内容，而是判断协同群体在 harmfulness 维度上的表现。
- CooRnet/CLSB 和 CooRTweet 代表一类基于协调共享行为的检测方法。它们通过账号在短时间窗口内共享同一 URL、hashtag 或对象来构建协同网络，输出账号节点、边权、共享对象和组件。
- Temporal Dynamics of Coordinated Online Behavior 类工作强调协同行为不是静态标签，而是随时间演化的过程，后续 KT3 应接入时间窗、阶段变化和持续性证据。

我们的方法：

- 当前 `Evidence Builder` 从帖子中构建内容分布、协同摘要、传播图和账户画像，形成 `evidence_pack`。
- `risk_service.assess_risk()` 是当前 orchestrator，在 `analysis_mode=agent` 下顺序调用各 agent。

差距：

- 当前 orchestrator 是顺序函数调用，不是显式 agent task graph。
- 证据来源和 provenance 还不完整，报告中的每个结论不能完全追溯到原始数据、agent、版本和规则。
- 没有对时序演化做多窗口建模，也没有 agent 重试、失败恢复或异步并行调度。

改进：

- 定义版本化 `EvidencePack`、`AgentOutput`、`EvidenceItem` schema。
- 引入 DAG 式编排，支持 agent 并行、依赖、超时、降级和 trace。
- 在证据表中保存 `source_type/source_id/agent/rule_version/confidence`。

### 2.1.2 FactCheck Agent

参考文献方法：

- FEVER 将事实核查定义为 claim verification：给定 claim，从 Wikipedia 检索证据句，判断 `SUPPORTED / REFUTED / NOT ENOUGH INFO`。
- AVerTeC 进一步强调真实场景中的 claim verification，需要问答式证据检索、证据质量评估和复杂 claim 分解。
- SAFE 面向长文本 factuality，把生成内容拆解为原子事实，再通过搜索增强方式逐条验证，适合迁移到 KT3 的 claim decomposition 与 evidence retrieval。
- MOCHEG 关注多模态事实核查，要求结合文本、图像和外部证据，并生成解释。
- NewsCLIPpings 关注 out-of-context image-text mismatch，适合检测图文错配型信息操纵。
- FACTIFY 也是多模态事实验证数据集，任务通常包含图文证据匹配、claim-image consistency 和真假判断。
- ProgramFC 将事实核查分解为可执行的程序化步骤，强调将复杂 claim 拆成子问题并逐步求证。

我们的方法：

- 当前 `FactCheck Agent` 将 URL/hashtag 作为 claim proxy，把同一共享对象下的帖子聚合起来。
- 使用内部帖子中的 `支持/属实/官方通报`、`假的/辟谣/不实`、`求证/有证据吗` 等线索生成 verdict。
- 输出 `supported/refuted/conflicting/not_enough_evidence`、question decomposition、evidence list 和 explanation。

差距：

- 没有外部 Web/RAG 检索。
- 没有 claim extraction 模型，URL/hashtag 只是 proxy。
- 没有图像/视频证据理解，无法覆盖 MOCHEG、NewsCLIPpings、FACTIFY 的多模态场景。
- 没有 NLI/entailment 判断，也没有 AVerTeC/FEVER 风格的 evidence recall 和 evidence quality 评估。

改进：

- 实现 `claim extraction -> question generation -> retrieval -> reranking -> NLI/verdict -> explanation`。
- 文本事实核查优先参考 FEVER、AVerTeC、SAFE、ProgramFC。
- 多模态事实核查优先参考 MOCHEG、NewsCLIPpings、FACTIFY、AVerImaTeC。
- 评估指标包括 verdict macro-F1、evidence recall、evidence precision、evidence quality 和 explanation faithfulness。

### 2.1.3 Hate/Harm Agent

参考文献方法：

- HateXplain 将仇恨检测设计为 `label + target group + rationales`，即不仅判断 hate/offensive/normal，还要求识别目标群体和解释性证据片段。
- HateCheck 提供功能测试集，覆盖去人化、威胁、侮辱、否定、引用、反仇恨等场景，适合发现模型是否只学关键词。
- Jigsaw Toxic Comment 和 Unintended Bias 数据集提供毒性、侮辱、威胁、身份攻击等大规模标注，可用于训练 toxicity baseline 和偏见诊断。
- ToxiGen 与 Measuring Hate Speech 等数据集补充隐式仇恨、群体指向、细粒度强度评分和 adversarial examples。

我们的方法：

- 当前 `Hate/Harm Agent` 在原 harmful keyword baseline 上增加 target group、dehumanization、threat、category 和 rationale。
- 输出每条帖子级别的 `safe/borderline/harmful`、类别、目标群体和解释词。

差距：

- 仍是词典规则，无法处理隐式仇恨、反讽、引用仇恨言论、反仇恨表达、上下文依赖和跨语言变体。
- rationale 只是命中词，不是模型学习出的解释片段。
- 目标群体类别非常粗糙，无法覆盖实际平台语境。

改进：

- 使用 HateXplain 训练或微调 target-aware hate classifier。
- 使用 HateCheck 做功能诊断，确保模型不是单纯关键词匹配。
- 使用 Jigsaw/ToxiGen/Measuring Hate Speech 扩展毒性、身份攻击和隐式仇恨覆盖。
- 补充中文/本地领域标注数据，用于跨语言迁移和平台语境适配。

### 2.1.4 Stance/Narrative Agent

参考文献方法：

- RumourEval 2019 将社交媒体谣言线程中的回复分类为 support、deny、query、comment，并做 veracity 判断。
- PHEME 提供谣言事件、线程结构、转发/回复上下文，适合研究 stance evolution 和 conversation-aware rumor verification。
- SemEval 2016 Task 6 针对推文立场检测，强调 stance 是相对于特定 target 的。
- COVIDLies 等数据集将 misinformation claim 与用户 stance 结合，适合从 claim-centric 角度建模支持、反驳和质疑。

我们的方法：

- 当前 `Stance/Narrative Agent` 复用规则版 stance detector，输出 support/deny/query/comment。
- 额外识别 amplification、correction_or_query、sensational_framing、attack_framing 等叙事动作。

差距：

- 没有利用 conversation tree。
- 没有建模 stance 随时间从支持到质疑、反驳、纠偏的演化。
- target encoding 仍然简单，无法处理隐含 target 或多 claim。

改进：

- 用 RumourEval/PHEME 训练 target-aware stance 模型。
- 增加 conversation graph 或 thread-aware 模型。
- 把 narrative action 作为辅助任务，与 stance 联合训练。

### 2.1.5 Community Harm Judge

参考文献方法：

- Mannocci et al. 2024 支撑社区级 characterization：harmfulness 应结合内容、行为、组织性和时间变化，而不是只看单条帖子。
- MARO 使用多维 agent 报告和 Judge Agent 做最终判断，并通过 Decision Rule Optimization 自动改进规则。
- TELLER 使用可解释逻辑单元支撑真假判断，强调 generalizable、explainable 和 controllable。

我们的方法：

- 当前 `Community Harm Judge` 融合帖子 harmful ratio、hate ratio、fact conflict、协同账号数、传播边数、自动化分数和 amplification ratio。
- 输出社区级 `level/score/verdict/confidence/harm_types`，并拆分 post/account/community 三层证据。

差距：

- 权重是手工设定，没有训练或校准。
- 缺少社区级人工标注集。
- 没有 MARO 的 Questioning Agent、自动规则优化和 top-N rule voting。
- 没有 TELLER 风格的逻辑规则学习或可控推理。

改进：

- 建立本地 analyst-labeled community dataset。
- 对融合规则做校准和消融实验。
- 引入 MARO 式 Judge prompt、Questioning Agent 和 rule optimization。
- 引入 TELLER 式逻辑原子表达，使每个社区判定可解释、可审计。

### 2.1.6 DISARM Mapping Agent

参考文献方法：

- DISARM/AMITT 将信息操纵行为组织为 tactics、techniques、countermeasures，是信息操纵防御领域的知识本体。
- DISARM Navigator 和 master framework data 支持技术检索、矩阵展示和知识库映射。

我们的方法：

- 当前 `DISARM Mapping Agent` 将 harmful_ratio、coordination、automation、fact conflict、community harmfulness 映射到少量简化技术，如 Coordinated Amplification、Misleading Claim Amplification、Abusive Messaging。

差距：

- 未导入完整 DISARM master data。
- 不是多标签 ranking，只是少量规则映射。
- 没有 STIX/TAXII 或标准化威胁情报导出。
- 没有 analyst feedback 修正 TTP 映射。

改进：

- 导入 DISARM Frameworks master spreadsheet。
- 建立 `evidence pattern -> candidate technique -> confidence -> analyst feedback` 流程。
- 输出多标签 TTP ranking，并保存版本化映射规则。

### 2.1.7 Countermeasure Agent

参考文献方法：

- CONAN 提供 hate speech 与 counter-narrative 对，强调反制叙事应非攻击性、去激化、针对仇恨话术。
- Generate-Prune-Select 将 counter-narrative 生成分为生成候选、过滤不安全/低质量候选、选择最佳候选。
- CounterGeDi 等可控生成方法通过控制属性减少有害输出，适合用于安全约束。
- Fact-based counter-narrative 研究强调反制叙事应结合事实证据，而不是只输出一般性劝说话术。

我们的方法：

- 当前 `Countermeasure Agent` 根据 fact risk、hate risk 和 community risk 生成事实纠偏、反制叙事、社区级处置和闭环优化建议。
- 反制叙事是模板化的，并显式包含安全约束：非攻击性、证据支撑、避免复述仇恨表达、避免扩大传播。

差距：

- 没有生成模型。
- 没有检索事实证据来支持反制内容。
- 没有 generate-prune-select，也没有 helpfulness/safety ranking。
- 没有人类评估闭环。

改进：

- 使用 CONAN 和多语言 counter-narrative 数据训练/评估。
- 实现 `generate -> safety filter -> evidence grounding -> rank -> human review`。
- 对反制结果评估 factual grounding、non-escalation、helpfulness 和 policy safety。

### 2.1.8 Report Agent

参考文献方法：

- MOCHEG 包含 explanation generation，强调事实核查结论应附带证据解释。
- AVerTeC 强调证据质量和可验证性，报告不应只有结论，还应展示证据链。
- TELLER 强调可解释逻辑单元，适合将复杂判断拆成可审计片段。

我们的方法：

- 当前 `Report Agent` 生成结构化 JSON 和 compact Markdown。
- 报告包含 fact_check_results、hate_results、community_harmfulness、DISARM、countermeasures、optimization_trace 和 evidence_table。

差距：

- Markdown 较基础。
- PDF renderer 只是占位。
- 没有引用格式、证据 provenance、报告完整性评分和人工审核意见。

改进：

- 定义 `KT3Report` schema 和 completeness checklist。
- 增加 HTML/PDF export。
- 每个结论关联 evidence item、agent、confidence、rule/model version。

### 2.1.9 Optimization Agent

参考文献方法：

- MARO 的 Decision Rule Optimization Agent 使用跨领域验证任务反馈，自动生成和筛选更泛化的 decision rule，推理时使用 top-N rules 多数投票。
- APO 使用自然语言梯度和 beam search 自动优化 prompt。
- DSPy 将 LM pipeline 声明为模块，通过编译器自动优化 prompts 或 few-shot examples。
- OPRO 将优化问题本身转化为 LLM prompt，让模型提出新候选解。
- TextGrad 用文本反馈模拟梯度，推动 prompt 或文本参数改进。

我们的方法：

- 当前 `Optimization Agent` 只记录 failure modes、metrics_to_track、feedback_sources 和 next_actions。
- 它能告诉系统“下一步应该优化什么”，但不会自动改规则、改 prompt 或回归验证。

差距：

- 没有 feedback_cases 数据库。
- 没有验证集回放。
- 没有候选规则生成、评估、选择、回滚。
- 没有 MARO top-N voting。

改进：

- 建立 `feedback_cases` 集合，保存人工复核、误判样本、处置结果。
- 为每个 agent 建立 validation task。
- 实现 MARO-style rule generation and selection。
- 后续用 DSPy/APO/OPRO/TextGrad 优化 prompts、few-shot examples 和 routing policy。

## 2.2 参考文献方法卡片

本节将核心参考文献拆成“方法卡片”，说明每篇文献具体解决什么问题、采用什么技术路线、是否有开源代码/数据，以及对 KT3 哪个 agent 有直接改进价值。

### 2.2.1 Evidence Builder / Orchestrator 相关文献

| 文献 | 链接 | 代码/数据 | 方法介绍 | 对 KT3 的迁移 |
|---|---|---|---|---|
| Mannocci et al. 2024, Detection and Characterization of Coordinated Online Behavior: A Survey | https://arxiv.org/abs/2408.01257 | 无官方代码，综述型文献 | 该综述将协同群体分析拆成 Detect 和 Characterize 两阶段。Detect 关注发现协同账号/群体，Characterize 进一步刻画 authenticity、harmfulness、orchestration、time-variance。它强调协同行为不能只看内容，也要看组织方式和时间变化。 | 用于定义 KT3 的任务边界：KT3 不负责发现协同群体，而是在 KT1/KT2 输出基础上补充 harmfulness characterization。当前 `Community Harm Judge` 的帖子级、账户级、社区级证据设计来源于这个框架。 |
| Coordinated Link Sharing Behavior and Problematic Information, ICWSM 2020 | https://dl.acm.org/doi/10.1145/3400806.3400817 | CooRnet/CooRTweet: https://github.com/nicolarighetti/CooRTweet | 通过“多个账号在短时间窗口内分享同一 URL/对象”构建 coordinated link sharing network。方法核心是共享对象、时间窗口和账号共现边权。 | 用于 KT1/KT2 的协同检测输出，也用于 KT3 的 `evidence_pack.coordination`。后续应将当前简化协同摘要替换为 CooRTweet 兼容字段。 |
| Temporal Dynamics of Coordinated Online Behavior, PNAS 2023 | https://www.pnas.org/doi/10.1073/pnas.2307038121 | 无统一公开代码 | 关注协同行为的时间演化，强调协调群体的出现、增强、迁移和衰退。相比静态网络，该方向更适合判断行动阶段和持续性。 | 用于改进 `phase_detector` 和 `Community Harm Judge`，加入多时间窗 harmfulness、coordination persistence 和 time-variance 指标。 |

### 2.2.2 FactCheck Agent 相关文献

| 文献 | 链接 | 代码/数据 | 方法介绍 | 对 KT3 的迁移 |
|---|---|---|---|---|
| FEVER, NAACL 2018 | https://aclanthology.org/N18-1074/ | Dataset: https://fever.ai/dataset/fever.html | FEVER 将事实核查定义为 claim verification：系统先从 Wikipedia 检索证据句，再判断 claim 是 `SUPPORTED`、`REFUTED` 还是 `NOT ENOUGH INFO`。它奠定了“claim -> evidence retrieval -> verdict”的标准范式。 | 用于替换当前 FactCheck Agent 的内部帖子线索规则。KT3 应先抽取 claim，再检索外部证据，最后用 NLI 或 LLM judge 输出 verdict。 |
| FEVEROUS | https://aclanthology.org/2021.fever-1.1/ | Dataset: https://fever.ai/dataset/feverous.html | FEVEROUS 扩展 FEVER，要求同时使用结构化表格和非结构化文本证据。它适合处理统计数据、公告表格、时间线等混合证据。 | KT3 后续事实核查可接入政府公告、平台公告、结构化知识表，对事实纠偏提供更可靠证据。 |
| HoVer, EMNLP 2020 | https://aclanthology.org/2020.findings-emnlp.309/ | Dataset/code: https://hover-nlp.github.io/ | HoVer 强调多跳事实验证，一个 claim 可能需要跨多个文档组合证据才能验证。 | 用于复杂谣言和跨事件 claim 的多跳检索，避免只用单条证据得出过强结论。 |
| SciFact, EMNLP 2020 | https://aclanthology.org/2020.emnlp-main.609/ | Code/data: https://github.com/allenai/scifact | SciFact 面向科学 claim verification，要求从论文摘要中找证据并判断支持/反驳。 | 若 KT3 面向公共卫生、科技、灾害等事件，可用 SciFact 思路处理科学证据和专家声明。 |
| AVerTeC, FEVER 2024 | https://aclanthology.org/2024.fever-1.1/ | Dataset/code: https://fever.ai/dataset/averitec.html and https://github.com/MichSchli/AVeriTeC | AVerTeC 更贴近真实事实核查流程：围绕 claim 生成问题，检索证据，回答问题，再根据证据质量和答案判断 claim。其评分要求 verdict 正确且证据召回达到阈值。 | KT3 FactCheck Agent 应采用 AVerTeC 风格的 question decomposition 和 evidence-quality evaluation，避免只输出真假标签。 |
| SAFE / Long-form Factuality, NeurIPS 2024 | https://arxiv.org/abs/2403.18802 | Code/data: https://github.com/google-deepmind/long-form-factuality | SAFE 将长文本拆成原子事实，并通过搜索增强的 LLM agent 判断每个事实是否被搜索结果支持。核心是 atomic fact decomposition、search query generation、evidence-based judgment。 | KT3 可将高传播帖子、话题摘要或反制报告拆成原子 claim，逐条做搜索增强核查。 |
| MOCHEG, SIGIR 2023 | https://dl.acm.org/doi/10.1145/3539618.3591879 | Code/data: https://github.com/VT-NLP/Mocheg | MOCHEG 是端到端多模态事实核查与解释生成数据集。任务要求结合文本 claim、图像和外部证据，输出 verdict 并生成解释。 | 用于 KT3 的多模态 FactCheck Agent：接入图片/视频时，应从图文一致性、视觉证据和文本证据共同生成判定。 |
| NewsCLIPpings, EMNLP 2021 | https://aclanthology.org/2021.emnlp-main.545/ | Code/data: https://github.com/g-luo/news_clippings | NewsCLIPpings 关注 out-of-context 图文错配：图片本身可能真实，但被错误搭配到另一个新闻文本中。 | 用于检测“旧图新用”“图文错配”“移花接木”型认知操纵。 |
| FACTIFY | https://ceur-ws.org/Vol-3199/paper18.pdf | Dataset/code: https://github.com/Shreyashm16/Factify | FACTIFY 关注多模态 fact verification，比较 claim、document text 和 image 的一致性。 | 可作为 KT3 多模态核查 baseline，用于评估 image-text consistency。 |
| ProgramFC, ACL 2023 | https://aclanthology.org/2023.acl-long.386/ | Code: https://github.com/teacherpeterpan/ProgramFC | ProgramFC 用 LLM 将复杂 claim 分解成可执行程序，每个子任务交给专门 handler，最后合成结论。它的优势是可解释、可调试、少样本。 | KT3 可用该思路把复杂舆情 claim 拆成时间、主体、地点、因果、数量等子问题，并记录每步证据。 |

### 2.2.3 Hate/Harm Agent 相关文献

| 文献 | 链接 | 代码/数据 | 方法介绍 | 对 KT3 的迁移 |
|---|---|---|---|---|
| HateXplain, AAAI 2021 | https://ojs.aaai.org/index.php/AAAI/article/view/17745 | Code/data: https://github.com/hate-alert/HateXplain; HF: https://huggingface.co/datasets/Hate-speech-CNERG/hatexplain | HateXplain 不只做 hate/offensive/normal 分类，还标注 target community 和 rationale token。方法强调可解释性、公平性和目标群体识别。 | KT3 Hate/Harm Agent 应输出 `label + target_group + rationale`，并把 rationale 放入 evidence_table，支撑报告可审计。 |
| HateCheck, ACL 2021 | https://aclanthology.org/2021.acl-long.4/ | Data: https://github.com/paul-rottger/hatecheck-data; experiments: https://github.com/paul-rottger/hatecheck-experiments | HateCheck 是功能测试集，包含 29 类 hate speech 功能，如去人化、威胁、侮辱、引用、否定、反仇恨。它用于诊断模型弱点，而不是训练大模型。 | KT3 应用 HateCheck 做回归测试，发现规则或模型是否误判引用、反驳、反仇恨表达。 |
| Jigsaw Toxic Comment | https://www.kaggle.com/c/jigsaw-toxic-comment-classification-challenge | Kaggle dataset | 大规模多标签 toxicity 数据，包含 toxic、severe toxic、obscene、threat、insult、identity hate 等标签。 | 用于训练基础 toxicity classifier，补充 threat、insult、identity attack 等标签。 |
| Jigsaw Unintended Bias | https://www.kaggle.com/c/jigsaw-unintended-bias-in-toxicity-classification | Kaggle dataset | 关注模型对身份词的 unintended bias，评估 identity mention 是否导致误报。 | 用于 KT3 偏见诊断，避免把正常提及群体身份误判为仇恨。 |
| ToxiGen, ACL 2022 | https://arxiv.org/abs/2203.09509 | Code/data: https://github.com/microsoft/TOXIGEN; HF: https://huggingface.co/datasets/toxigen/toxigen-data | ToxiGen 通过 adversarial classifier-in-the-loop 生成隐式 toxic/hate 样本，覆盖多个少数群体。 | 用于增强 KT3 对隐式仇恨和规避性表达的鲁棒性。 |
| Measuring Hate Speech | https://hatespeech.berkeley.edu/ | HF: https://huggingface.co/datasets/ucberkeley-dlab/measuring-hate-speech | 数据集使用多维问卷式标注衡量 hate intensity、target、annotator perspective，适合细粒度强度建模。 | 用于从二/三分类升级到连续 harmfulness intensity 和多维风险解释。 |
| OLID / OffensEval | https://sites.google.com/site/offensevalsharedtask/olid | Dataset page | OLID 将冒犯性语言分成 offensive、targeted offense 和 target type 等层次。 | 可用于区分一般攻击、定向骚扰和群体攻击，补充 KT3 harmful categories。 |
| HASOC | https://hasocfire.github.io/hasoc/ | Shared task datasets | HASOC 提供多语言 hate/offensive content identification benchmark。 | 用于跨语言和多平台有害内容检测扩展。 |

### 2.2.4 Stance/Narrative Agent 相关文献

| 文献 | 链接 | 代码/数据 | 方法介绍 | 对 KT3 的迁移 |
|---|---|---|---|---|
| RumourEval 2019 | https://aclanthology.org/S19-2147/ | Data repo: https://github.com/kippfreud/RumourEval; HF: https://huggingface.co/datasets/strombergnlp/rumoureval_2019 | RumourEval 将谣言线程回复分为 support、deny、query、comment，并做 veracity 预测。其核心是 thread-aware stance + rumor verification。 | KT3 应将帖子/评论围绕 claim 建成线程，分析支持、反驳、质疑、纠偏在社区中的比例。 |
| PHEME | https://figshare.com/articles/dataset/PHEME_dataset_for_Rumour_Detection_and_Veracity_Classification/6392078 | Dataset: same link | PHEME 提供多个突发事件的 rumor/non-rumor 线程、时间结构和 veracity 标签。 | 用于评估谣言传播过程中的 stance evolution 和阶段变化。 |
| SemEval 2016 Task 6 | https://alt.qcri.org/semeval2016/task6/ | Task data page | 经典 target-aware stance detection，判断文本对特定目标是 favor、against 还是 neither。 | KT3 应明确 stance target，不应只对文本做无目标情感分类。 |
| COVIDLies | https://github.com/ucinlp/covid19-data | Code/data: same link | 将 COVID misinformation claims 与社交媒体 stance 关联，适合 claim-centric misinformation stance detection。 | 用于迁移到公共事件中的 claim-level stance tracking。 |
| MDFEND / Weibo21, CIKM 2021 | https://dl.acm.org/doi/10.1145/3459637.3482139 | Code/data: https://github.com/kennqiang/MDFEND-Weibo21 | MDFEND 通过 domain gate 聚合多个专家表示，解决多领域 fake news detection 泛化问题。Weibo21 包含新闻内容、图片、评论和领域标签。 | 用于 KT3 跨事件/跨领域泛化，尤其是不同话题 harmfulness 分布不同的问题。 |
| UCD-RD, AAAI 2023 | https://ojs.aaai.org/index.php/AAAI/article/view/26584 | 需按论文说明获取 | 面向无监督跨领域谣言检测，通过对比学习和域不变表示降低领域偏移。 | 用于 KT3 在新话题无标注情况下的迁移。 |

### 2.2.5 Community Harm Judge / Multi-Agent Judge 相关文献

| 文献 | 链接 | 代码/数据 | 方法介绍 | 对 KT3 的迁移 |
|---|---|---|---|---|
| MARO, EMNLP 2025 | https://aclanthology.org/2025.emnlp-main.291/ | 未发现官方代码；arXiv: https://arxiv.org/abs/2503.23329 | MARO 包含两个模块：Multi-Dimensional Analysis 和 Decision Rule Optimization。前者用 Linguistic Agent、Comment Agent、Fact-Checking Agent Group 和 Questioning Agent 生成多维报告；后者用 Judge Agent 和优化器在跨领域验证任务上迭代改进 decision rules，推理时采用 top-N rules voting。 | KT3 已实现多 agent 分析和 Community Judge，但缺 Questioning Agent、自动 rule optimization 和 top-N voting。后续应按 MARO 增加反思补强和规则搜索闭环。 |
| DELL, ACL Findings 2024 | https://aclanthology.org/2024.findings-acl.155/ | Code: https://github.com/whr000001/DELL | DELL 使用 LLM 生成用户反应、解释 proxy tasks，并构建 LLM-based expert ensemble，最后融合专家预测和置信度。 | KT3 可用 DELL 思路为 FactCheck、Hate、Stance、Narrative 生成解释性 proxy reports，再由 Community Judge 融合。 |
| TELLER, ACL Findings 2024 | https://aclanthology.org/2024.findings-acl.919/ | Code: https://github.com/less-and-less-bugs/Trust_TELLER | TELLER 由 cognition system 和 decision system 构成。前者用人类专家逻辑谓词指导 LLM 生成 logic atoms，后者归纳可泛化逻辑规则做真假判断。 | KT3 可将 harmfulness 判定拆成 logic atoms，如 `contains_targeted_hate`、`has_fact_conflict`、`coordinated_amplification`，再做可解释社区裁决。 |
| MDFEND, CIKM 2021 | https://dl.acm.org/doi/10.1145/3459637.3482139 | Code/data: https://github.com/kennqiang/MDFEND-Weibo21 | MDFEND 使用 mixture-of-experts 和 domain gate，针对不同领域选择/加权专家。 | KT3 可将不同 agent 看作专家，将话题领域、平台、事件类型作为 gate 输入，学习 fusion 权重。 |

### 2.2.6 DISARM Mapping Agent 相关文献/资源

| 文献/资源 | 链接 | 代码/数据 | 方法介绍 | 对 KT3 的迁移 |
|---|---|---|---|---|
| DISARM Frameworks | https://github.com/DISARMFoundation/DISARMframeworks/ | Master data: repository spreadsheets | DISARM 将信息操纵活动组织为 tactics、techniques、tasks 和 countermeasures，类似信息操纵领域的 ATT&CK。 | KT3 应从简化规则映射升级为完整 DISARM ontology-backed mapping。 |
| DISARM Navigator | https://disarmfoundation.github.io/disarm-navigator/ | Tool page | 提供技术矩阵导航和可视化能力，便于分析师查看 tactic/technique。 | KT3 报告可增加 DISARM matrix view 或导出兼容格式。 |
| AMITT Framework | https://github.com/misinfosecproject/amitt_framework | Framework repo | AMITT 是早期 misinformation tactics/techniques 框架，描述影响行动生命周期。 | 可作为 DISARM 映射的补充知识源，尤其用于解释行动阶段。 |
| EU FIMI Reports | https://www.eeas.europa.eu/eeas/1st-eeas-report-foreign-information-manipulation-and-interference-threats_en | Public reports | 提供 FIMI 威胁报告、术语和操作案例，有助于把技术映射转化为威胁情报语言。 | KT3 报告中的 DISARM/FIMI 概念可参考其术语，提高报告规范性。 |

### 2.2.7 Countermeasure Agent 相关文献

| 文献 | 链接 | 代码/数据 | 方法介绍 | 对 KT3 的迁移 |
|---|---|---|---|---|
| CONAN, ACL 2019 | https://aclanthology.org/P19-1271/ | Dataset: https://github.com/marcoguerini/CONAN | CONAN 是多语言、专家构建的 hate speech/counter-narrative pair 数据集，反制话术由 NGO 操作者撰写，强调非攻击性和针对性回应。 | KT3 反制叙事应从模板升级为基于 CONAN 的 retrieval/fine-tuning，并保留安全约束。 |
| Generate-Prune-Select, ACL Findings 2021 | https://aclanthology.org/2021.findings-acl.12/ | Code: https://github.com/WanzhengZhu/GPS | 该方法将 counterspeech generation 分为生成多个候选、剪枝低质量或不安全候选、选择最佳候选。 | KT3 Countermeasure Agent 应采用 `generate -> safety prune -> evidence-grounded select`，而不是直接输出单条模板。 |
| Towards Knowledge-Grounded Counter Narrative Generation, ACL Findings 2021 | https://aclanthology.org/2021.findings-acl.79/ | 需按论文说明获取 | 将外部知识引入 counter-narrative generation，使反制内容更具体、更有事实支撑。 | KT3 应把 FactCheck Agent 检索到的证据传给 Countermeasure Agent，生成 fact-based counter-narrative。 |
| CounterGeDi, IJCAI 2022 | https://www.ijcai.org/proceedings/2022/0716.pdf | Code: https://github.com/hate-alert/CounterGEDI | 使用 GeDi 风格的可控生成，引导输出更礼貌、更去毒性、更有情绪适配的 counterspeech。 | KT3 可用该思路做反制叙事安全控制，防止反制文本本身带来攻击或升级冲突。 |
| Fact-based Counter Narrative Generation | https://dl.acm.org/doi/10.1145/3696410.3714718 | PDF: https://dspace.mit.edu/bitstream/handle/1721.1/162842/3696410.3714718.pdf | 通过相关背景知识和事实依据生成非攻击性的 counter narrative，提高 factual grounding。 | KT3 应把事实纠偏和反制叙事合并，确保每条反制建议能追溯到证据。 |

### 2.2.8 Report Agent 相关文献

| 文献 | 链接 | 代码/数据 | 方法介绍 | 对 KT3 的迁移 |
|---|---|---|---|---|
| MOCHEG explanation generation | https://dl.acm.org/doi/10.1145/3539618.3591879 | Code/data: https://github.com/VT-NLP/Mocheg | MOCHEG 不只输出 verdict，还生成 explanation，并评估解释是否覆盖关键证据。 | KT3 Report Agent 应为每个 major conclusion 生成 evidence-grounded explanation。 |
| AVerTeC evidence-quality evaluation | https://fever.ai/dataset/averitec.html | Code/data: https://github.com/MichSchli/AVeriTeC | AVerTeC 将 evidence correctness 纳入评分，要求证据召回达到阈值后 verdict 才算有效。 | KT3 报告应对事实核查结论显示 evidence quality，避免“无证据结论”。 |
| TELLER logic atoms | https://aclanthology.org/2024.findings-acl.919/ | Code: https://github.com/less-and-less-bugs/Trust_TELLER | 使用 human-readable logic atoms 和可泛化规则增强解释性。 | KT3 报告可将 Community Judge 的判定拆成 logic atoms，提高可读性和审计性。 |

### 2.2.9 Optimization Agent 相关文献

| 文献 | 链接 | 代码/数据 | 方法介绍 | 对 KT3 的迁移 |
|---|---|---|---|---|
| MARO Decision Rule Optimization | https://aclanthology.org/2025.emnlp-main.291/ | 未发现官方代码 | MARO 通过构造跨领域验证任务，让 Decision Rule Optimization Agent 生成候选规则，Judge 在验证任务上评估规则效果，最后选择 top-N rules，多数投票用于推理。 | KT3 应实现 `feedback_cases -> validation tasks -> candidate rules -> evaluation -> top-N voting -> rollback`。 |
| APO, EMNLP 2023 | https://aclanthology.org/2023.emnlp-main.494/ | Code often referenced via paper resources; implementation variants available in community repos | APO 使用自然语言“梯度”描述 prompt 错误方向，再通过 beam search 搜索更优 prompt。 | 可用于优化 FactCheck/Hate/Judge prompts，尤其是失败样本驱动的 prompt 改写。 |
| DSPy | https://arxiv.org/abs/2310.03714 | Framework: https://github.com/stanfordnlp/dspy | DSPy 将 LLM pipeline 声明为模块和 metric，再由 compiler 自动搜索 prompt 和 few-shot demonstrations。 | KT3 可把每个 agent 声明为 DSPy module，用 validation metrics 自动优化 few-shot 和 instruction。 |
| OPRO, ICLR 2024 | https://openreview.net/forum?id=Bb4VGOWELI | Code: https://github.com/google-deepmind/opro | OPRO 把优化问题描述给 LLM，让 LLM 根据历史候选和分数提出新候选。 | 可用于优化 Community Judge 规则权重描述或 countermeasure generation policy。 |
| TextGrad | https://github.com/zou-group/textgrad | Code: same link | TextGrad 将文本反馈当作梯度，驱动 prompt、reasoning path 或文本参数迭代改进。 | 可用于把人工审核意见转化为 agent prompt 或规则的改进信号。 |

## 3. Current Implementation Gap Summary

The current code is best described as a stable MVP and deterministic baseline:

- It already has end-to-end agent-mode API wiring through `analysis_mode=agent`.
- It already produces KT3 report fields: `fact_check_results`, `hate_results`, `narrative_results`, `community_harmfulness`, `disarm_assessment`, `countermeasures`, `optimization_trace`, `evidence_table`, and `agent_trace`.
- It does not yet implement Web retrieval, vector retrieval, multimodal image/video reasoning, trained hate speech models, conversation-tree stance modeling, learned community-level fusion, full DISARM ontology mapping, generated counter-narratives, or automatic prompt/rule optimization.

Therefore, in papers or project reports, current work should be claimed as:

```text
A deterministic multi-agent baseline and system scaffold for KT3 coordinated-community harmfulness characterization.
```

It should not yet be claimed as:

```text
A full reproduction of MARO, MOCHEG, AVerTeC, HateXplain, CONAN, or DISARM.
```

## 4. Improvement Roadmap

| Priority | Target | Main references | Deliverable |
|---|---|---|---|
| P0 | Build evaluation harness | HateXplain, HateCheck, RumourEval, AVerTeC | Offline scripts that load public datasets and compute task metrics for each agent |
| P0 | Define persistent schemas | Mannocci, MARO, TELLER | Versioned `EvidencePack`, `AgentOutput`, `KT3Report`, `FeedbackCase` schemas |
| P1 | Upgrade FactCheck Agent | AVerTeC, SAFE, MOCHEG, NewsCLIPpings, FACTIFY | RAG-based text evidence retrieval; multimodal entailment baseline; evidence-quality score |
| P1 | Upgrade Hate/Harm Agent | HateXplain, HateCheck, Jigsaw | Target-aware hate classifier with rationale and bias diagnostics |
| P1 | Upgrade Stance/Narrative Agent | RumourEval, PHEME | Conversation-aware stance and narrative role classifier |
| P1 | Upgrade Community Harm Judge | Mannocci, MARO, TELLER | Learned/calibrated fusion from post/account/community evidence |
| P2 | Upgrade DISARM Mapping | DISARM framework | Full ontology-backed TTP mapping with analyst feedback |
| P2 | Upgrade Countermeasure Agent | CONAN, GPS, fact-based counter-narrative generation | Retrieval-grounded response generation with safety/helpfulness ranking |
| P2 | Upgrade Optimization Agent | MARO, APO, DSPy, OPRO | Validation-loop-driven prompt/rule optimization and top-N voting |

## 5. Acceptance Criteria

Agent-mode implementation is considered research-ready only when the following are satisfied:

- FactCheck Agent reports verdict macro-F1 and evidence quality on AVerTeC or MOCHEG.
- Hate/Harm Agent reports macro-F1, target-group F1, and rationale quality on HateXplain, plus functional pass rates on HateCheck.
- Stance/Narrative Agent reports stance macro-F1 on RumourEval/PHEME.
- Community Harm Judge is evaluated on local analyst-labeled coordinated communities.
- Countermeasure Agent is evaluated with safety, helpfulness, factual grounding, and non-escalation criteria.
- Optimization Agent can replay a held-out validation set, propose rule/prompt candidates, select improved candidates, and record rollback metadata.
- Report Agent passes a completeness checklist and preserves evidence provenance for every major conclusion.

## 6. Expanded Reference Clusters

### 6.1 Coordinated Behavior and Community Characterization

| Reference | Method contribution | Link |
|---|---|---|
| Mannocci et al. 2024, Detection and Characterization of Coordinated Online Behavior: A Survey | Defines Detect -> Characterize and four characterization dimensions: authenticity, harmfulness, orchestration, time-variance | https://arxiv.org/abs/2408.01257 |
| Giglietto et al. 2020, Coordinated Link Sharing Behavior and Problematic Information | Detects coordination through near-synchronous sharing of the same links | https://dl.acm.org/doi/10.1145/3400806.3400817 |
| CooRnet / CooRTweet | Operational tool for coordinated sharing behavior and network construction | https://github.com/nicolarighetti/CooRTweet |
| Temporal Dynamics of Coordinated Online Behavior | Studies how coordination evolves over time rather than as a static label | https://www.pnas.org/doi/10.1073/pnas.2307038121 |

### 6.2 Text and Multimodal Fact-Checking

| Reference | Method contribution | Dataset/link |
|---|---|---|
| FEVER, NAACL 2018 | Claim verification with evidence retrieval and `SUPPORTED/REFUTED/NEI` labels | https://fever.ai/dataset/fever.html |
| FEVEROUS | Fact verification over structured tables and unstructured text | https://fever.ai/dataset/feverous.html |
| SciFact | Scientific claim verification with abstract-level evidence | https://github.com/allenai/scifact |
| LIAR | Short political statement fake news classification | https://www.cs.ucsb.edu/~william/data/liar_dataset.zip |
| MultiFC | Multi-domain fact-checking from many fact-checking sites | https://github.com/copenlu/multifc |
| HoVer | Multi-hop fact verification over multiple evidence documents | https://hover-nlp.github.io/ |
| AVerTeC | Real-world claim verification via question answering and evidence quality | https://fever.ai/dataset/averitec.html |
| SAFE | Long-form factuality via atomic fact decomposition and search-augmented verification | https://github.com/google-deepmind/long-form-factuality |
| MOCHEG | Multimodal claim verification with explanation generation | https://github.com/VT-NLP/Mocheg |
| NewsCLIPpings | Out-of-context image-text mismatch detection | https://github.com/g-luo/news_clippings |
| FACTIFY | Multimodal fact verification with image-text consistency | https://github.com/Shreyashm16/Factify |

### 6.3 Hate, Toxicity, and Harmful Language

| Reference | Method contribution | Dataset/link |
|---|---|---|
| HateXplain, AAAI 2021 | Explainable hate speech detection with label, target group, and rationales | https://github.com/hate-alert/HateXplain |
| HateCheck, ACL 2021 | Functional tests for hate speech systems | https://github.com/paul-rottger/hatecheck-data |
| Jigsaw Toxic Comment | Large-scale toxicity classification | https://www.kaggle.com/c/jigsaw-toxic-comment-classification-challenge |
| Jigsaw Unintended Bias | Toxicity with identity bias diagnostics | https://www.kaggle.com/c/jigsaw-unintended-bias-in-toxicity-classification |
| ToxiGen | Implicit hate and adversarial toxic generation dataset | https://github.com/microsoft/TOXIGEN |
| Measuring Hate Speech | Fine-grained hate intensity and target annotation | https://huggingface.co/datasets/ucberkeley-dlab/measuring-hate-speech |
| OLID | Offensive language identification | https://sites.google.com/site/offensevalsharedtask/olid |
| HASOC | Hate speech and offensive content identification | https://hasocfire.github.io/hasoc/ |

### 6.4 Stance, Rumor, and Narrative

| Reference | Method contribution | Dataset/link |
|---|---|---|
| RumourEval 2019 | Stance and veracity over rumor conversations | https://aclanthology.org/S19-2147/ |
| PHEME | Rumor and non-rumor event threads with veracity labels | https://figshare.com/articles/dataset/PHEME_dataset_for_Rumour_Detection_and_Veracity_Classification/6392078 |
| SemEval 2016 Task 6 | Target-aware stance detection in tweets | https://alt.qcri.org/semeval2016/task6/ |
| COVIDLies | Stance toward COVID misinformation claims | https://github.com/ucinlp/covid19-data |
| MDFEND / Weibo21 | Multi-domain fake news detection and domain generalization | https://github.com/kennqiang/MDFEND-Weibo21 |
| UCD-RD | Unsupervised cross-domain rumor detection | https://ojs.aaai.org/index.php/AAAI/article/view/26584 |

### 6.5 Multi-Agent and Explainable Misinformation Detection

| Reference | Method contribution | Link |
|---|---|---|
| MARO, EMNLP 2025 | Multi-dimensional agents, Questioning Agent, Judge Agent, rule optimization, top-N rule voting | https://aclanthology.org/2025.emnlp-main.291/ |
| DELL, ACL Findings 2024 | LLM experts for misinformation detection | https://aclanthology.org/2024.findings-acl.155/ |
| TELLER, ACL Findings 2024 | Trustworthy, explainable, generalizable, controllable fake news detection with logic atoms | https://aclanthology.org/2024.findings-acl.919/ |
| ProgramFC, EMNLP 2023 | Programmatic decomposition for fact-checking with LLMs | https://aclanthology.org/2023.emnlp-main.386/ |
| SelfCheckGPT | Black-box hallucination/factuality checking through consistency | https://aclanthology.org/2023.emnlp-main.557/ |

### 6.6 Counter-Narrative and Response Generation

| Reference | Method contribution | Dataset/link |
|---|---|---|
| CONAN, ACL 2019 | Counter-narratives against online hate speech | https://github.com/marcoguerini/CONAN |
| Generate-Prune-Select | Candidate generation, pruning, and selection for counter-narratives | https://github.com/WanzhengZhu/GPS |
| CounterGeDi | Controllable generation of counter-narratives | https://aclanthology.org/2021.acl-long.401/ |
| Fact-based counter-narrative generation | Grounds responses in factual evidence | https://dspace.mit.edu/bitstream/handle/1721.1/162842/3696410.3714718.pdf |

### 6.7 DISARM and FIMI Technique Mapping

| Reference | Method contribution | Link |
|---|---|---|
| DISARM Frameworks | Tactics, techniques, and countermeasures for information manipulation | https://github.com/DISARMFoundation/DISARMframeworks/ |
| DISARM Navigator | Interactive technique matrix and navigation | https://disarmfoundation.github.io/disarm-navigator/ |
| AMITT | Earlier adversarial misinformation and influence tactics framework | https://github.com/misinfosecproject/amitt_framework |
| EU FIMI work | Defines foreign information manipulation and interference reporting concepts | https://www.eeas.europa.eu/eeas/1st-eeas-report-foreign-information-manipulation-and-interference-threats_en |

### 6.8 Optimization and Closed-Loop Learning

| Reference | Method contribution | Link |
|---|---|---|
| MARO Decision Rule Optimization | Uses validation feedback to optimize decision rules and top-N voting | https://aclanthology.org/2025.emnlp-main.291/ |
| APO, EMNLP 2023 | Automatic prompt optimization with natural language gradients and beam search | https://aclanthology.org/2023.emnlp-main.494/ |
| DSPy | Compiles declarative LM pipelines into optimized prompts/demonstrations | https://github.com/stanfordnlp/dspy |
| OPRO, ICLR 2024 | Uses LLMs as optimizers to propose better candidate solutions | https://openreview.net/forum?id=Bb4VGOWELI |
| TextGrad | Uses textual feedback as gradients for optimization | https://github.com/zou-group/textgrad |
