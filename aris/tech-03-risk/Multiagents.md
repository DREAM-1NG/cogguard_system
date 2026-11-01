# Risk Review 多智能体文献总表：Multiagents

更新时间：2026-07-03

## 1. 文档定位

本文档用于统一管理 Risk Review 在“帖子/传播树/证据/反制”方向上最关键的多智能体与自优化文献。整理原则不是堆论文名，而是回答四个问题：

- 这篇论文为什么要提出这个系统。
- 它到底如何组织 Agent、检索、辩论、优化或自改进。
- 它在实验上证明了什么。
- 这些机制对 Risk Review 哪一层最有迁移价值，哪些地方不能直接照搬。

因此，本文全部按 `Motivation - Method - Result - 对 Risk Review 的启示` 组织，不复述论文摘要原句。

## 2. 总览表

| 论文 | 方向 | 论文链接 | 开源仓库 | 对 Risk Review 的直接价值 |
|---|---|---|---|---|
| MARO, EMNLP 2025 | 多专家分析 + 规则自优化 | https://aclanthology.org/2025.emnlp-main.291/ | https://github.com/Brtulien/MARO | 是 Risk Review 人工复核层、规则优化层的主参考 |
| D2D, EMNLP 2025 | 多阶段辩论检测 | https://aclanthology.org/2025.emnlp-main.764/ | https://github.com/hanshenmesen/Debate-to-Detect | 是 Risk Review 高冲突样本 full debate 的主参考 |
| ED2D, AAAI 2026 | 证据驱动辩论 + 反制说服 | https://ojs.aaai.org/index.php/AAAI/article/view/41196 | 未确认开源仓库 | 是 Risk Review 反制安全闸和解释风险控制的重要参考 |
| RAMA, 2025 | 多模态 RAG + 多 Agent 验证 | https://arxiv.org/abs/2507.09174 | https://github.com/kalendsyang/RAMA | 是 Risk Review 主张证据检索和多模态验证的主参考 |
| Self-RAG, ICLR 2024 | 自反思检索增强生成 | https://openreview.net/forum?id=hSyW5go0v8 | https://github.com/AkariAsai/self-rag | 支持 Risk Review 从固定 top-k 检索升级到“是否检索/是否再检索”的模型化决策 |
| ARES, NAACL 2024 | RAG 自动评估 + LM judges | https://aclanthology.org/2024.naacl-long.20/ | https://github.com/stanford-futuredata/ARES | 支持 Risk Review 训练或调用证据相关性、回答忠实度、回答相关性评估器 |
| RAGAS, EACL 2024 | RAG 评估指标框架 | https://aclanthology.org/2024.eacl-demo.16/ | https://github.com/explodinggradients/ragas | 可作为 Risk Review 证据研判与治理报告 factuality/faithfulness 自动评估基线 |
| FActScore, EMNLP 2023 | 原子事实级事实性评估 | https://aclanthology.org/2023.emnlp-main.741/ | https://github.com/shmsw25/factscore | 支持 Risk Review 把治理报告和反制草案拆成 atomic facts 再核验证据支撑 |
| RAFTS, ACL 2024 | 检索增强 + 支持/反驳对比论证 | https://aclanthology.org/2024.acl-long.556/ | 未确认开源仓库 | 支持 Risk Review ClaimEvidenceAgent 生成 support/refute 双链路，而不是单向证据摘要 |
| MAD-Sherlock, 2024/2025 | 图文语境错配 + 外部检索 | https://arxiv.org/abs/2410.20140 | 未确认开源仓库 | 是 Risk Review 图文错配和 OOC 检测的主参考 |
| MOCHEG, SIGIR 2023 | 多模态 claim-evidence graph | https://dl.acm.org/doi/10.1145/3539618.3591879 | 未确认开源仓库 | 支持 Risk Review 把证据列表升级为多模态证据图 |
| FACTIFY3M, EMNLP 2023 | 大规模多模态事实验证 + 5W 解释 | https://aclanthology.org/2023.emnlp-main.945/ | 未确认开源仓库 | 支持 Risk Review 用 Who/What/When/Where/Why 组织证据研判报告 |
| VLM 基座簇：BLIP-2 / InstructBLIP / LLaVA / Qwen2.5-VL / InternVL2.5 | 视觉语言预训练与视觉指令调优 | https://arxiv.org/abs/2301.12597 / https://arxiv.org/abs/2305.06500 / https://papers.nips.cc/paper_files/paper/2023/hash/6dcf277ea32ce3288914faf369fe6de0-Abstract-Conference.html / https://arxiv.org/abs/2502.13923 / https://arxiv.org/abs/2412.05271 | 多数有官方或主仓库，部署时按模型逐项确认 | 是 Risk Review 多 VLM ensemble、视觉描述、OCR/版式理解和视频关键帧研判的基础 |
| T2Agent, AAAI 2026 | 工具增强 + MCTS 搜索式验证 | https://ojs.aaai.org/index.php/AAAI/article/view/36977 | 未确认开源仓库 | 是 Risk Review 从固定链路升级到动态验证规划的重要参考 |
| Agentic DISARM, 2026 | DISARM Agent 化落地 | https://arxiv.org/abs/2601.15109 | 未确认开源仓库 | 是 Risk Review DISARM 映射层的直接对标 |
| Reflexion, NeurIPS 2023 | 失败反思记忆 | https://papers.nips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html | https://github.com/noahshinn/reflexion | 是 Risk Review error memory / feedback memory 的主参考 |
| Self-Refine, 2023 | 输出自反馈迭代 | https://arxiv.org/abs/2303.17651 | https://github.com/madaan/self-refine | 是 Risk Review 报告初稿 -> critique -> revised report 的主参考 |
| ProTeGi, EMNLP 2023 | 文本梯度 prompt 优化 | https://aclanthology.org/2023.emnlp-main.494/ | https://github.com/pree-dew/protegi | 可用于优化 Judge / 检索 / 反制 prompt，仓库为社区实现 |
| OPRO, 2023 | LLM 作为优化器 | https://arxiv.org/abs/2309.03409 | https://github.com/google-deepmind/opro | 可用于生成规则候选与阈值候选 |
| MIPRO / DSPy, EMNLP 2024 | 多阶段 LM program 优化 | https://aclanthology.org/2024.emnlp-main.525/ | https://github.com/stanfordnlp/dspy | 可把 Risk Review Agent 链看成可编译的 LM program |
| TextGrad, 2024 | 文本反向传播式优化 | https://arxiv.org/abs/2406.07496 | https://github.com/zou-group/textgrad | 可优化 Judge rubric、检索模板、反制草案模板 |
| RARG, NAACL 2024 | 证据驱动反制文本生成 | https://aclanthology.org/2024.naacl-long.313/ | 未确认开源仓库 | 支持 Risk Review CountermeasureAgent 从“自由草案”升级为“证据约束反制建议” |
| Counter Narrative Multi-Aspect Eval, NAACL 2024 | LLM-as-Judge 多维反制文本评估 | https://aclanthology.org/2024.naacl-short.14/ | https://github.com/OSU-NLP-Group/LLM-CN-Eval | 支持 Risk Review 评估反制草案的反驳性、信息量、适当性、流畅度与去激化 |
| LLM-based CN Ranking, EMNLP Findings 2024 | 成对比较/锦标赛式反制文本排序 | https://aclanthology.org/2024.findings-emnlp.559/ | https://github.com/hitz-zentroa/cn-eval | 支持 Risk Review 用 pairwise ranking 替代 BLEU/ROUGE 式表层评估 |
| CONAN / MultiTarget-CONAN | 专家反叙事与人机协同数据构建 | https://www.semanticscholar.org/paper/CONAN-COunter-NArratives-through-Nichesourcing%3A-a-Chung-Kuzmenko/1dae97251a05320f5749355baa50387607318832 / https://aclanthology.org/2021.acl-long.250/ | https://github.com/marcoguerini/CONAN | 支持 Risk Review 反制建议参考专家语料和 human-in-the-loop 审核，而不是直接外发 |
| ADAS, ICLR 2025 | 自动设计 Agent 系统 | https://arxiv.org/abs/2408.08435 | https://github.com/ShengranHu/ADAS | 是 Risk Review 长期工作流自动发现的参考，而不是当前优先实现 |
| AFlow, ICLR 2025 | MCTS 工作流搜索 | https://arxiv.org/abs/2410.10762 | https://github.com/FoundationAgents/AFlow | 是 Risk Review 未来从“调权重”升级到“搜工作流”的重要参考 |

## 3. 核心论文闭环

### 3.1 MARO: A Multi-Agent Framework with Automated Decision Rule Optimization for Cross-Domain Misinformation Detection

- Motivation
  - 这篇工作针对的是跨域 misinformation detection。作者认为，单一 LLM 直接判别目标域新闻有两个根本问题：一是分析维度过于单薄，只盯文本表面；二是最终判别依赖人工写死的 decision rule，因此一旦换领域就会失灵。
- Method
  - MARO 把系统拆成两个模块。第一个是 `Multi-Dimensional Analysis Module`，不是让一个 Agent 直接给真假，而是让多个专家 Agent 先分别从语言风格、评论反应、外部事实三个角度生成分析报告。
  - 其中语言 Agent 负责识别夸张语气、叙事方式和语言异常；评论 Agent 负责汇总评论区立场、情绪和带证据的评论；事实核查组先让 `Fact-Questioning Agent` 从新闻中抽 claim 并生成 yes/no 问题，再用 Google/Wikipedia 找证据，由 `Fact-Checking Agent` 判断 claim 与证据的一致性。
  - 在专家 Agent 首轮输出之后，MARO 不立即做裁决，而是引入 `Questioning Agent` 做 question-reflection。它读取已有分析报告，专门找“哪里分析还不够”“哪里证据没覆盖”“哪里论据过于表面”，再把追问回灌给语言、评论、事实核查三个专家，让它们做第二轮更深的分析。
  - 第二个模块是 `Decision Rule Optimization Module`。这里的关键不是 prompt 微调，而是规则优化。作者构造 cross-domain validation tasks：从源域中取 query news，再配上其他域的 demonstration news 和多维分析报告，让 Judge Agent 在“有示例、有分析报告、有规则”的条件下做判断。
  - 规则优化流程从一个人工规则 `r0` 出发，记录 `<rule, accuracy>` 轨迹，然后让 `Decision Rule Optimization Agent` 基于已有轨迹提出新规则。每一轮都要在 validation task set 上做确定性评估，只有分数更高的规则才会进入保留集合，再把 top-k 规则反馈进下一轮优化 prompt。它本质上是一个“LLM 生成候选规则 + 外部验证器打分 + 迭代修订”的闭环。
- Result
  - 在 Weibo21 上，MARO 相对第二名 RAEmo 平均准确率提升 5.98，平均 F1 提升 6.85。
  - 在 AMTCele 上，MARO 相对第二名 DELL 平均准确率提升 3.14，平均 F1 提升 3.55。
  - 消融显示，去掉 `Decision Rule Optimization Agent`、去掉 cross-domain validation task、去掉 Questioning Agent 都会明显降分，说明 MARO 的核心价值不是“多 Agent”四个字，而是“专家分析 -> 反思追问 -> 验证集规则优化”这个闭环。
- 开源仓库
  - 论文：https://aclanthology.org/2025.emnlp-main.291/
  - 官方实现：https://github.com/Brtulien/MARO
- 对 Risk Review 的启示
  - Risk Review 最该继承的不是字段化输出，而是 `专家自然语言分析报告 -> reflection -> rule refinement loop`。
  - Risk Review 的 `HarmfulnessJudgeAgent` 不应只读固定阈值，而应显式读取 active policy、规则解释、过往失败类型。
  - Risk Review 当前已做出的“人工触发 Agent、人工激活 policy、deterministic evaluator 验证候选规则”的方向和 MARO 是同向的，但还没有完全到 MARO 的迭代深度。

### 3.2 D2D: Debate-to-Detect

- Motivation
  - D2D 认为传统 misinformation detection 把复杂核查过程压缩成一个静态分类动作，这会丢掉现实世界 fact-checking 中最重要的过程信息：对立论证、证据反驳、裁判标准和阶段化推理。
- Method
  - D2D 将检测任务重新表述成一次“现实世界式辩论”。其结构分成 `Agent Layer` 和 `Orchestrator Layer`。
  - `Agent Layer` 中，正反双方各自配置多名辩手，且每一方有固定立场，用来强制生成彼此冲突的论证路径，避免单模型一开始就顺着某个方向走到底。系统还会先做 topical domain inference，再根据领域动态生成 agent profile，使每个辩手说话时带有领域角色。
  - 裁决部分不是单一 judge，而是多 judge 并行，从五个维度分别评分：`Factuality`、`Source Reliability`、`Reasoning Quality`、`Clarity`、`Ethics`。这一步很重要，因为它把“正确与否”和“论证质量”“来源可信度”“表达伦理性”拆开了。
  - `Orchestrator Layer` 明确规定五个辩论阶段：`Opening Statement`、`Rebuttal`、`Free Debate`、`Closing Statement`、`Judgment`。不同阶段承担不同功能，不是简单多轮聊天。Opening 负责提出主论点，Rebuttal 负责对打，Free Debate 允许生成新的攻击/防守路径，Closing 负责整合，最后由 Judge panel 裁决。
  - D2D 还维护 shared memory。每轮轮到某个 Agent 发言之前，它不会读取全部历史原文，而是读取压缩后的争点与证据摘要，借此压制冗余、减少上下文漂移，并保持跨阶段一致性。
- Result
  - 在 Weibo21 和 FakeNewsDataset 上，D2D 在 accuracy / precision / recall / F1 上都达到最高，F1 分别为 81.97 和 81.94。
  - 去掉 domain profile、去掉 stage design、去掉 multi-dimensional judgment 都会明显下降，说明 D2D 的增益不是单纯来自“更多轮数”，而是来自角色、阶段和多维裁决三者共同作用。
  - 对 2025 年新新闻的附加测试中，D2D 的 F1 为 79.83，明显高于 SMAD 的 73.92，说明它不只是记忆旧新闻。
- 开源仓库
  - 论文：https://aclanthology.org/2025.emnlp-main.764/
  - 官方实现：https://github.com/hanshenmesen/Debate-to-Detect
- 对 Risk Review 的启示
  - Risk Review 不需要把所有样本都送去 full debate，但在“跨模态冲突、证据矛盾、Judge 低置信”的样本上，D2D 是非常合适的协议参考。
  - 对 Risk Review 来说，最可迁移的是 `stage-aware debate protocol + shared memory + multi-dimensional judges`，而不是简单把几个 Agent 并排调用。

### 3.3 ED2D: Beyond Detection

- Motivation
  - ED2D 进一步提出，仅仅提高 detection accuracy 还不够，因为真实治理场景不仅要给出真假结论，还要影响用户认知和传播行为。也就是说，检测系统会开始承担“解释”和“劝阻分享”的干预责任。
- Method
  - ED2D 在 D2D 式多 Agent debate 的基础上加入 factual evidence retrieval，让辩论过程必须引用检索到的证据，而不是只靠模型自身常识。
  - 它把 debate transcript 当作可用的干预材料，而不是仅作为中间推理痕迹。系统不仅预测真假，还生成 debunking transcript，目标是说服用户修正认识、减少再次传播。
  - 论文的关键贡献不在于再多一个 Agent，而在于同时评价两个目标：`detection quality` 和 `intervention quality`。这让系统进入了治理场景而非纯分类场景。
- Result
  - 论文报告 ED2D 在三个 misinformation detection benchmark 上优于已有基线。
  - 更关键的是，作者发现：当 ED2D 预测正确时，它生成的 debunking transcript 在说服效果上可接近人工专家；但当 ED2D 预测错误时，它的解释反而可能强化用户误解，即使旁边同时展示了正确的人类解释。
- 开源仓库
  - 论文：https://ojs.aaai.org/index.php/AAAI/article/view/41196
  - 开源仓库：未确认
- 对 Risk Review 的启示
  - 这是 Risk Review `CountermeasureAgent` 最必须吸收的一篇论文。
  - 它说明反制不是“检测正确就自动生成一段话”这么简单。只有当证据充分、Judge 置信足够、争议点收敛时，系统才应给出反制草案；否则应该只建议人工复核，而不要输出看似完整但事实基础不足的反制解释。

### 3.4 RAMA: Retrieval-Augmented Multi-Agent Framework for Misinformation Detection in Multimodal Fact-Checking

- Motivation
  - RAMA 关注的是多模态 claim 的核查难题。很多图文或视频 misinformation 的问题不在“图像里看到了什么”，而在“这段模态组合到底指向什么主张、缺了什么上下文、该去哪里找证据”。
- Method
  - RAMA 的第一步不是直接判断真假，而是 `strategic query formulation`：把多模态输入中的主张、事件、实体、时空线索整理成可执行的 web query。这一点对 Risk Review 很关键，因为 claim-to-query 往往比最终分类更决定上限。
  - 第二步是 `cross-verification evidence aggregation`。系统不会用单一来源，而是尝试从多个权威来源收证，然后做交叉验证，以避免某一来源本身失真。
  - 第三步是 `multi-agent ensemble`。根据论文和官方仓库，RAMA 并不是单一 VLM 推全流程，而是把 Web retrieval、多个多模态模型和不同 prompt 变体组合起来，最后再聚合结果。官方实现里使用了 DeepResearcher 负责检索，Qwen2.5-VL 与 InternVL3 负责多模态判别，再用 voting 做整合。
- Result
  - 论文报告 RAMA 在多模态 fact-checking benchmark 上优于现有方法，尤其对“模糊 claim”“看起来不太可能但真实”的样本更有效。
  - 官方仓库进一步公开了 ACMMM25 Grand Challenge 成绩：Public Test F1 为 91.00，Hidden Test F1 为 76.61。
- 开源仓库
  - 论文：https://arxiv.org/abs/2507.09174
  - 官方实现：https://github.com/kalendsyang/RAMA
- 对 Risk Review 的启示
  - Risk Review 的 `ClaimEvidenceAgent` 和 `ActiveEvidenceRetriever` 应优先对齐 RAMA，而不是停留在“claim 字符串回填 + 本地 RAG 占位”。
  - 其中最值得迁移的不是挑战赛里的具体大模型组合，而是 `claim-to-query -> 多源证据聚合 -> 多模型交叉核查 -> 再融合` 这一机制。

### 3.5 MAD-Sherlock

- Motivation
  - MAD-Sherlock 针对的是最容易误导公众、也最难靠文本模型解决的一类样本：真实图片搭配误导性文字，即 out-of-context misinformation。这里的问题不是图像是否伪造，而是图文组合是否在制造错误语境。
- Method
  - 它把任务定义成 `visual misinformation detection through multi-agent debate`。多模态 Agent 之间不是各做各的分类，而是围绕“图像与文本的上下文是否一致”开展协作和争辩。
  - 一个关键点是引入外部信息请求与 cross-context reasoning。系统不满足于看当前帖子的图文，而是主动寻找与图像相关的历史语境、原始出处、时间地点和新闻背景，判断这张图是不是被“旧图新用”或“跨事件挪用”。
  - 由于目标是 time-agnostic 和 domain-agnostic，它不依赖专门为某个数据集训练的 finetuned detector，而更接近“检索增强的多 Agent 推理器”。
- Result
  - 在 NewsCLIPpings、VERITE、MMFakeBench 上，MAD-Sherlock 分别比已有方法高 2%、3%、5%。
  - 论文还做了 ablation 和 user study，结果显示 debate 本身和最终解释质量不仅影响检测性能，也影响用户信任。
- 开源仓库
  - 论文：https://arxiv.org/abs/2410.20140
  - 开源仓库：未确认
- 对 Risk Review 的启示
  - 这篇论文直接支持 Risk Review 的 `MultimodalConsistencyAgent`。
  - 对于 MultiOFF、mcfend 这类图文样本，Risk Review 不应只做 text score 和 image score 的后融合，而应显式建模“图像在什么原语境中成立、在当前文本语境中是否被误用”。

### 3.6 T2Agent

- Motivation
  - T2Agent 针对的是 mixed-source multimodal misinformation。作者认为，现实中的伪造来源很多样，有的是文本-图像矛盾，有的是外部事实冲突，有的是图像真实性有疑点。固定链路和固定工具集通常无法兼顾所有情况。
- Method
  - T2Agent 构建了一个可扩展 toolkit，其中包含 web search、forgery detection、consistency analysis 等工具，并且每个工具都用标准化模板描述，便于继续扩展。
  - 为了避免每个样本都把所有工具跑一遍，系统先用 Bayesian optimization 风格的 selector 选出更可能有用的工具子集，再把这个子集作为 MCTS 的动作空间。
  - 随后，系统把验证过程当作一条搜索路径，使用 Monte Carlo Tree Search 在“不同工具调用顺序、不同证据采集路径”之间探索。它不是简单地枚举工具，而是边评估边扩展验证轨迹。
  - 论文还把传统 MCTS 改造成 multi-source verification 版本：将整体任务分解成面向不同 forgery source 的子任务，同时设计 dual reward，分别奖励推理轨迹质量和证据置信度，从而平衡 exploration 和 exploitation。
- Result
  - 论文报告 T2Agent 在 challenging mixed-source multimodal misinformation benchmarks 上持续优于现有基线，并证明搜索机制与工具集都带来独立增益。
  - 其价值不只在准确率，还在于说明“多工具验证路径”本身应该被优化，而不是预先写死。
- 开源仓库
  - 论文：https://ojs.aaai.org/index.php/AAAI/article/view/36977
  - 开源仓库：未确认，论文当前口径为 code will be released
- 对 Risk Review 的启示
  - 如果 Risk Review 下一步要从“固定 Agent 顺序 + 固定 policy”升级到“搜索式验证”，T2Agent 是最直接的方法参考。
  - 但这属于第二阶段工作。当前 Risk Review 更适合先补齐 MARO 式规则自优化，再考虑 T2Agent 式 verification path search。

### 3.7 Agentic DISARM

- Motivation
  - DISARM 提供了信息操纵 TTP 的统一语言，但人工把海量社交媒体内容映射到 DISARM taxonomy 成本很高，也难以规模化。
- Method
  - 这篇工作提出 framework-agnostic 的 multi-agent pipeline，先检测 candidate manipulative behaviors，再把这些行为透明地映射到 DISARM TTP。
  - 它的重点不是做 end-to-end 分类，而是把“检测”和“taxonomy mapping”分成两个阶段，并且让不同 Agent 对应不同子任务，从而保持映射过程可解释。
  - 与 Risk Review 不同的是，它更接近 flat tagging，即把观察到的行为标注成 DISARM 技术，而不是做路径预测、阶段推演和反制规划。
- Result
  - 作者在两套由领域实践者标注的真实数据上评估，结论是这种 agent-based operationalization 能显著扩展原本高度依赖人工、且解释负担很重的 FIMI 分析工作。
- 开源仓库
  - 论文：https://arxiv.org/abs/2601.15109
  - DISARM 本体资源：https://github.com/DISARMFoundation/DISARMframeworks
  - Agent 化实现：未确认开源仓库
- 对 Risk Review 的启示
  - Risk Review 在 DISARM 层不应只说“参考 DISARM”，而应明确回答：我们做的是 `DISARM path reasoning + next-step prediction + countermeasure planning`，而不是单纯 flat mapping。

### 3.8 Reflexion

- Motivation
  - Reflexion 解决的是 Agent 如何在不做参数更新的条件下从失败中快速改进。对于需要多次尝试的任务，单次规划很容易重复犯同一类错误。
- Method
  - 它把反馈写成自然语言 reflection，而不是数值梯度。Agent 在一次尝试后读取外部反馈或内部模拟反馈，生成反思文本，再把这段反思写入 episodic memory。
  - 下一轮再做任务时，Agent 不是从零开始，而是条件化在这个 memory 上。因此“学习”发生在测试时和语言空间，而不是在权重更新里。
  - 这种方法兼容标量反馈和自由文本反馈，也兼容外部环境回报或自我评价。
- Result
  - 在 HumanEval 上，Reflexion 的 pass@1 达到 91%，明显高于文中对比的 GPT-4 80%。
  - 论文还在序列决策、代码、语言推理等多个任务上证明 verbal reinforcement 的广泛有效性。
- 开源仓库
  - 论文：https://papers.nips.cc/paper_files/paper/2023/hash/1b44b878bb782e6954cd888628510e90-Abstract-Conference.html
  - 官方实现：https://github.com/noahshinn/reflexion
- 对 Risk Review 的启示
  - Risk Review 的 `feedback memory / error memory` 最值得直接借鉴 Reflexion。
  - 人工纠错、误判类型、证据缺失原因不应只存在表里，而应在下一轮 policy refinement 和 report generation 中真正参与推理。

### 3.9 Self-Refine

- Motivation
  - Self-Refine 回答的是另一个问题：即使没有环境交互，仅靠模型自身，也常常可以把“第一版不够好”的输出通过反馈循环变得更好。
- Method
  - 它使用同一个 LLM 扮演生成器、反馈者和修订者三个角色。流程是 `initial output -> feedback -> refined output -> feedback -> refined output`。
  - 关键不在于多角色，而在于 feedback 必须明确指出问题和修订方向，因此 refinement 不是重写，而是带着 critique 迭代。
  - 它不需要监督训练或 RL，因此非常适合作为 inference-time 提升模块。
- Result
  - 论文在 7 类任务上验证，平均绝对性能提升约 20%，且人类偏好和自动指标都优于同模型的一次性生成。
- 开源仓库
  - 论文：https://arxiv.org/abs/2303.17651
  - 官方实现：https://github.com/madaan/self-refine
- 对 Risk Review 的启示
  - Risk Review 当前的 `QuestionReflectionAgent` 更像“一次追问”。如果要进一步对齐高水平工作，应该支持 `报告初稿 -> critique -> revised report` 的真实修订链。

### 3.10 ProTeGi

- Motivation
  - ProTeGi 面向 prompt engineering 的一个核心痛点：手工改 prompt 成本高，而且改动方向经常是凭感觉。
- Method
  - 它把小批量样本上的失败案例转化为自然语言“梯度”，也就是一段针对当前 prompt 的批评文本，指出 prompt 哪里模糊、哪里约束不够、哪里容易误导。
  - 然后系统沿着“反方向”去编辑 prompt，用 beam search 保留多条候选演化路径，再用 bandit 机制优先评估更有前景的候选，从而提高搜索效率。
  - 这里的核心思想不是文字版梯度这个比喻本身，而是把 prompt 优化变成 `critic -> rewrite -> select -> evaluate` 的外部闭环。
- Result
  - 论文报告在三类 NLP 任务和 jailbreak detection 上，相比已有 prompt editing 方法更优，并且相对初始 prompt 最多提升 31%。
- 开源仓库
  - 论文：https://aclanthology.org/2023.emnlp-main.494/
  - 社区实现：https://github.com/pree-dew/protegi
- 对 Risk Review 的启示
  - ProTeGi 非常适合优化 `Judge prompt`、`ClaimEvidenceAgent prompt`、`Countermeasure safety prompt`。
  - 但它优化的是 prompt，而不是 governance rule 本身，所以它应该服务于 Risk Review 的报告质量提升，而不是取代 MARO 式 rule refinement。

### 3.11 OPRO

- Motivation
  - OPRO 处理的是黑盒优化问题：目标函数可评估，但没有梯度，且候选空间是语言或离散结构。
- Method
  - 它把 LLM 当作 optimizer，而不是 executor。每次优化时，把历史候选解及其得分一起塞进 prompt，要求 LLM 生成新候选。
  - 新候选再被外部 evaluator 打分，得分高的候选继续进入下一轮上下文。这样就形成 `history of solutions + scores -> propose new solutions -> external evaluation -> append history` 的循环。
  - 从方法论上看，它是一种基于语言历史轨迹的 black-box search。
- Result
  - 在 prompt optimization 上，OPRO 报告 GSM8K 相对人工 prompt 最高提升 8%，在 Big-Bench Hard 上最高可提升 50%。
- 开源仓库
  - 论文：https://arxiv.org/abs/2309.03409
  - 官方实现：https://github.com/google-deepmind/opro
- 对 Risk Review 的启示
  - Risk Review 的 `DecisionRuleOptimizerAgent` 可以借鉴 OPRO 的候选生成方式：把过往 `<rule, score>`、失败类型、held-out 表现摘要送入优化器，生成新规则候选。
  - 但 Risk Review 必须保留 deterministic evaluator 和 human activation，不能让 LLM 直接生效规则。

### 3.12 MIPRO / DSPy

- Motivation
  - MIPRO 关注的不是单个 prompt，而是 multi-stage LM program。作者指出，复杂 LM pipeline 中的问题通常不是某一处 prompt 坏，而是多个模块的 instructions 和 few-shot examples 联合作用不佳。
- Method
  - MIPRO 先把整个程序分解为多个模块，然后分别优化每个模块的自由文本 instruction 和 demonstrations。
  - 为了处理没有 module-level labels、也没有梯度的情况，它使用三类机制：
  - 第一，program-aware 和 data-aware proposal，为不同模块提出与任务结构匹配的 instruction 候选。
  - 第二，使用 stochastic mini-batch evaluation 来学习目标函数的 surrogate，避免每次都全量评估。
  - 第三，做 meta-optimization，不只是调候选 prompt 本身，也不断改进 proposal 的生成方式。
  - 在 DSPy 的 `MIPROv2` 实现中，优化 instruction 和 few-shot examples 的联合搜索进一步通过 Bayesian Optimization 来完成。
- Result
  - 论文报告在 7 个多阶段 LM program 中，有 5 个任务超过已有优化器，最高准确率提升达 13%。
- 开源仓库
  - 论文：https://aclanthology.org/2024.emnlp-main.525/
  - 官方实现：https://github.com/stanfordnlp/dspy
  - MIPROv2 文档：https://dspy.ai/api/optimizers/MIPROv2/
- 对 Risk Review 的启示
  - 如果把 Risk Review 看成 `Retriever -> Expert Agents -> Judge -> Countermeasure` 的 LM program，那么 MIPRO 比单纯的 prompt hack 更适合做系统级优化。
  - 但 Risk Review 当前阶段仍应限制优化对象，优先优化 `Judge`、`retrieval query template`、`reflection template`，不要一开始就放开全链路联合搜索。

### 3.13 TextGrad

- Motivation
  - TextGrad 出发点是：复杂 AI 系统需要一种像自动求导那样通用的优化机制，但现实系统中的很多变量是文本、代码、规则，不可微。
- Method
  - 它把系统写成 computation graph，把文本提示、代码片段、候选结构都看成变量，再让 LLM 生成针对这些变量的 textual feedback，作为“文本梯度”。
  - 这些 textual gradients 会沿图结构回传到上游变量，驱动 prompt、代码或其他组件的更新。
  - 它的优势不在于数学上真的可微，而在于提供了一个统一抽象，让多组件系统都可以纳入同一种优化接口。
- Result
  - 论文报告 Google-Proof QA 中 GPT-4o 零样本准确率从 51% 提升到 55%，LeetCode-Hard 优化上得到约 20% 相对提升，并在 prompt、分子设计、放疗方案等任务上通用有效。
- 开源仓库
  - 论文：https://arxiv.org/abs/2406.07496
  - 官方实现：https://github.com/zou-group/textgrad
- 对 Risk Review 的启示
  - TextGrad 很适合用来优化 Risk Review 中“文本性强、又有清晰目标函数”的组件，比如 Judge rubric、反制模板、安全提示词、检索 query 模板。
  - 但它不直接等价于 MARO 的规则优化，因为 MARO 的对象是决策规则和验证闭环，TextGrad 的对象更偏语言组件。

### 3.14 ADAS

- Motivation
  - ADAS 提出的观点更激进：既然 CoT、Self-Reflection、Toolformer 等 agentic pattern 都是人工设计的，那么长远来看，Agent 系统结构本身也应该自动学习，而不是永远依赖人工拼装。
- Method
  - 作者把这类问题定义为 `Automated Design of Agentic Systems`，目标是自动发明新的 agent building blocks，或以新的方式组合它们。
  - 具体算法 `Meta Agent Search` 让一个 meta agent 在代码空间中持续编写新的 Agent 设计。它会基于既有发现维护 archive，再从 archive 出发生成新设计、评估新设计、保留更优设计。
  - 因为设计对象是代码级 agent，而不是单条 prompt，这种方法理论上能联合搜索 prompts、tools、workflow 和它们的组合方式。
- Result
  - 论文报告在 coding、science、math 多个领域上，Meta Agent Search 可以持续发明新的 agent 设计，且这些设计显著超过手工设计的强基线，并在跨域和跨模型迁移中保持优势。
- 开源仓库
  - 论文：https://arxiv.org/abs/2408.08435
  - 官方实现：https://github.com/ShengranHu/ADAS
- 对 Risk Review 的启示
  - ADAS 代表 Risk Review 的长期方向：未来可以自动搜索 `Agent 划分方式`、`角色配置`、`工作流结构`。
  - 但它不应成为当前阶段的第一优先级，因为 Risk Review 目前连人工定义的治理闭环都还在完善，过早做工作流自动发现容易把系统推向不可控。

### 3.15 AFlow

- Motivation
  - AFlow 关注的是另一个比“调 prompt”更高层的问题：工作流本身如何自动生成和优化。作者认为，现有 agentic workflow 大多仍靠人工写结构，缺少真正自动的 workflow search。
- Method
  - AFlow 把 workflow 写成代码表示的图，图中节点是 LLM invocation，边是执行依赖。
  - 它在这个工作流空间上运行 MCTS，不断执行 `select -> expand -> evaluate -> update`。不同于只改提示词，AFlow 可以修改节点、操作符和连接方式。
  - 系统中还有 `Operator` 抽象，把常见操作如 Generate、Review、Revise、Ensemble、Test 封装起来，以缩小搜索空间并提高搜索效率。
  - 评估器为每个候选 workflow 提供反馈，再把反馈回灌给优化器，形成工作流级别的搜索闭环。
- Result
  - 论文在 6 个 benchmark 上平均超过 SOTA 基线 5.7%，并展示了小模型在特定任务上以 4.55% 的推理成本超过 GPT-4o。
- 开源仓库
  - 论文：https://arxiv.org/abs/2410.10762
  - 官方实现：https://github.com/FoundationAgents/AFlow
- 对 Risk Review 的启示
  - AFlow 非常适合作为 Risk Review 的第三阶段参考：当我们已经有稳定的 expert agents、judge、retrieval、policy optimizer 以后，再搜索“谁先谁后”“哪些样本触发 debate”“哪些样本跳过某些 Agent”。
  - 在当前阶段，AFlow 应作为方法论储备，而不是马上并入主链路。

### 3.16 Self-RAG / ARES / RAGAS / FActScore / RAFTS：从手工来源打分升级到模型化证据验证

- Motivation
  - 这些工作共同解决的问题是：RAG 系统不能只“检索到一些文本再生成答案”。在事实核查和治理研判场景中，更关键的是模型是否知道何时检索、检索证据是否相关、生成结论是否忠实于证据、以及结论中的每个事实断言是否被外部证据支持。
  - 这直接回应 Risk Review 的一个风险：如果把多源 Web/RAG 做成手工来源分数、固定 top-k、固定权重融合，本质上仍然是特征工程，不能支撑高水平治理研判。
- Method
  - Self-RAG 把“是否检索、是否使用证据、是否需要反思”变成模型内部的可学习/可生成控制流程，而不是固定规则。它让模型在生成过程中自我判断检索需求和证据使用质量。
  - ARES 使用自动生成的训练数据和轻量 LM judges 来评估 `context relevance`、`answer faithfulness`、`answer relevance`。它的关键思想是把 RAG 质量评估变成可训练的判别任务，而不是人工写来源权重。
  - RAGAS 提供 reference-free RAG 评估维度，包括 faithfulness、context precision、answer relevance 等，可用于没有人工参考答案时的持续质量评估。
  - FActScore 将长文本拆成 atomic facts，再逐条检索外部来源判断是否支持。它非常适合治理报告和反制草案，因为报告中的一个错误事实足以破坏整体可信度。
  - RAFTS 则强调 retrieval 后不只生成单向解释，而是生成 support/refute contrastive arguments，再做事实核查。这比“找三条证据摘要”更接近真实研判。
- Result
  - Self-RAG 在需要知识密集型回答的任务中显示出更强的事实性和检索控制能力。
  - ARES 证明 LM judge 可以在有限人工标注下评估 RAG 组件质量。
  - FActScore 在长文本事实性评估中推动了“原子事实支持率”这一思路，避免整体印象式打分。
- 开源仓库
  - Self-RAG：https://openreview.net/forum?id=hSyW5go0v8 ，https://github.com/AkariAsai/self-rag
  - ARES：https://aclanthology.org/2024.naacl-long.20/ ，https://github.com/stanford-futuredata/ARES
  - RAGAS：https://aclanthology.org/2024.eacl-demo.16/ ，https://github.com/explodinggradients/ragas
  - FActScore：https://aclanthology.org/2023.emnlp-main.741/ ，https://github.com/shmsw25/factscore
  - RAFTS：https://aclanthology.org/2024.acl-long.556/
- 对 Risk Review 的启示
  - Risk Review 的 `ActiveEvidenceRetriever` 不应继续停留在固定 top-k 和来源字段拼接，而应升级为 `Adaptive Retrieval -> Evidence Judge -> Atomic Fact Verification -> Contrastive Argument -> Judge Synthesis`。
  - 证据可信度不要写成 `Authority + Relevance + Recency` 这种手工公式，而应通过 LM/NLI/VLM judge 学习或判别 evidence relevance、faithfulness、support/refute/insufficient。
  - `HarmfulnessJudgeAgent` 和 `CountermeasureAgent` 输出报告后，应经过 atomic fact checking；未被证据支持的事实断言必须降级为“待核验”，不能进入确定性处置建议。

### 3.17 MOCHEG / FACTIFY3M / VLM 基座簇：多模态事实图与多视觉模型协同

- Motivation
  - 多模态 misinformation 的难点不是“文本模型 + 图片模型各自打分再平均”，而是 claim、图像、OCR、ASR、视频关键帧、外部证据之间存在复杂关系。高水平研究越来越强调 evidence graph、5W explanation、VLM-based verification 和 out-of-context reasoning。
- Method
  - MOCHEG 将多模态事实核查表示为 claim-evidence graph，把 claim、文本证据、图像证据和解释联系起来。这比扁平证据列表更适合支撑可审计报告。
  - FACTIFY3M 构造大规模多模态事实验证任务，并使用 5W QA 组织解释，使系统不仅判断真假，还说明谁、何时、何地、发生了什么、为什么证据相关。
  - BLIP-2、InstructBLIP、LLaVA、Qwen2.5-VL、InternVL2.5 等 VLM 基座提供视觉描述、文档/OCR理解、定位、图文推理和视频关键帧理解能力。它们适合作为不同视觉专家，而不是单独替代整个判别系统。
- Result
  - MOCHEG 和 FACTIFY3M 表明，多模态事实核查的可解释性需要显式证据结构。
  - LLaVA、BLIP-2、Qwen2.5-VL、InternVL2.5 等模型证明视觉指令调优和视觉语言预训练可以显著提升开放场景视觉理解能力。
- 开源仓库
  - MOCHEG：https://dl.acm.org/doi/10.1145/3539618.3591879
  - FACTIFY3M：https://aclanthology.org/2023.emnlp-main.945/
  - BLIP-2：https://arxiv.org/abs/2301.12597
  - InstructBLIP：https://arxiv.org/abs/2305.06500
  - LLaVA：https://papers.nips.cc/paper_files/paper/2023/hash/6dcf277ea32ce3288914faf369fe6de0-Abstract-Conference.html
  - Qwen2.5-VL：https://arxiv.org/abs/2502.13923
  - InternVL2.5：https://arxiv.org/abs/2412.05271
- 对 Risk Review 的启示
  - Risk Review 的多 VLM ensemble 不应做多数投票。更合理的是拆成视觉描述、OCR/版式理解、语境一致性、图像证据检索、最终裁决多个角色，每个角色输出自然语言证据和不确定性。
  - 对 MultiOFF、mcfend、FakeSV 这类样本，Risk Review 应将媒体内容构造成 evidence graph，并让 Judge 读取图文/音视关系，而不是只看 late fusion score。
  - 多模型协同的关键是 disagreement handling：当 Qwen2.5-VL、InternVL、LLaVA 或其他视觉模型输出冲突时，应触发 MAD-Sherlock/D2D 式辩论和外部证据请求，而不是强行平均。

### 3.18 RARG / Counter-Narrative Evaluation / CONAN：反制文本质量自动评估

- Motivation
  - 反制叙事不是“检测为 harmful 后生成一段友善回应”。在治理场景中，反制文本如果事实不准、语气激化、目标对象错误或越权处置，可能比不生成更危险。因此前沿工作更关注 evidence-grounded generation、专家语料、LLM-as-Judge 和成对比较评估。
- Method
  - CONAN 和 MultiTarget-CONAN 提供专家反叙事和人机协同构建数据，强调反制文本应来自专家知识和审核循环。
  - RARG 将检索增强引入 counter-narrative generation，使生成内容绑定外部事实背景，而不是凭模型常识自由发挥。
  - NAACL 2024 的 multi-aspect counter-narrative evaluation 使用 LLM-as-Judge 依据 NGO guidelines 评价反制文本的多个维度。
  - EMNLP Findings 2024 的 LLM-based ranking 使用 pairwise/tournament ranking 评估反制文本，比 BLEU/ROUGE 更接近人工偏好。
- Result
  - 这些研究共同表明，反制文本质量不能用表层相似度衡量，而应评价事实支撑、针对性、去激化、适当性和说服力。
  - 成对比较和多维 LLM judge 往往比单一打分更稳定，也更适合没有唯一标准答案的反制任务。
- 开源仓库
  - RARG：https://aclanthology.org/2024.naacl-long.313/
  - Multi-aspect evaluation：https://aclanthology.org/2024.naacl-short.14/ ，https://github.com/OSU-NLP-Group/LLM-CN-Eval
  - LLM-based ranking：https://aclanthology.org/2024.findings-emnlp.559/ ，https://github.com/hitz-zentroa/cn-eval
  - CONAN：https://www.semanticscholar.org/paper/CONAN-COunter-NArratives-through-Nichesourcing%3A-a-Chung-Kuzmenko/1dae97251a05320f5749355baa50387607318832 ，https://github.com/marcoguerini/CONAN
  - MultiTarget-CONAN：https://aclanthology.org/2021.acl-long.250/
- 对 Risk Review 的启示
  - Risk Review 应新增 `CountermeasureEvaluatorAgent`，让反制草案经过 evidence-grounded critique、multi-aspect judge、pairwise ranking 或 tournament ranking 后再展示。
  - 评估对象不是“文本好不好听”，而是是否证据支撑、是否去激化、是否避免扩大传播、是否符合平台公开治理口径、是否明确为内部建议草案。
  - 这一路线可以避免手工列一堆安全关键词，也避免 BLEU/ROUGE 这类不适合治理场景的表层指标。

### 3.19 前沿方法的共同结论：不要把模型能力退化成手工特征工程

- 真实多源 Web/RAG 可信度验证应参考 Self-RAG、ARES、RAGAS、FActScore、RAFTS：让模型学习或判别检索需求、证据相关性、忠实度、原子事实支撑和支持/反驳链路。
- 多 VLM ensemble 应参考 RAMA、MAD-Sherlock、MOCHEG、FACTIFY3M 和 VLM 基座：把多个 VLM 组织成角色化证据生成和争议解决系统，而不是简单投票。
- 反制文本质量自动评估应参考 RARG、CONAN、MultiTarget-CONAN 和 LLM-as-Judge counter-narrative evaluation：做 evidence-grounded critique 和 pairwise ranking，而不是关键词过滤或 BLEU/ROUGE。
- 长期自优化应参考 Reflexion、Self-Refine、ProTeGi、OPRO、MIPRO、TextGrad、MARO：把失败案例和人工反馈转成 prompt/rule/workflow 候选，再用 validation 评估和人工激活闭环控制风险。

## 4. 对 Risk Review 的统一实现结论

结合上述文献，Risk Review 的多智能体主线应该分成三层推进，而不是一口气追求“全自动自进化”。

### 4.1 当前应优先对齐

- `MARO`
  - 对齐专家报告、question-reflection、validation-driven rule refinement、人工激活策略。
- `RAMA`
  - 对齐 claim-to-query、多源证据聚合、多模型交叉核查。
- `Self-RAG / ARES / RAGAS / FActScore / RAFTS`
  - 对齐自适应检索、证据相关性评估、忠实度评估、原子事实核验和支持/反驳对比论证，避免手工来源打分。
- `MAD-Sherlock`
  - 对齐图文语境错配和 OOC 检索，而不是停留在图文 late fusion。
- `MOCHEG / FACTIFY3M / VLM 基座簇`
  - 对齐多模态证据图、5W 解释、多 VLM 角色化协同和冲突触发辩论，避免 VLM 多数投票。
- `D2D`
  - 对齐高冲突样本上的 full debate protocol，而不是全量样本全开辩论。
- `ED2D`
  - 对齐反制安全闸，严格区分“可解释”与“可干预”。
- `RARG / Counter-Narrative Evaluation / CONAN`
  - 对齐证据约束反制草案、LLM-as-Judge 多维评估和 pairwise ranking，避免关键词式安全过滤。

### 4.2 第二阶段应补齐

- `Reflexion`
  - 把人工反馈、失败案例、误判类型转成真实 error memory。
- `Self-Refine`
  - 让分析报告和反制草案支持 critique 后重写。
- `FActScore / RAGAS / ARES`
  - 让治理报告和反制草案支持自动 factuality、faithfulness 和 evidence support 检查。
- `OPRO`
  - 让规则候选生成从固定邻域搜索升级为 LLM 生成候选。
- `MIPRO / TextGrad / ProTeGi`
  - 系统化优化 Judge、retriever、reflection、countermeasure 的文本组件。

### 4.3 长期方向

- `T2Agent`
  - 从固定 Agent 顺序升级到 search-based verification path。
- `ADAS / AFlow`
  - 从“调权重与 prompt”升级到“自动发现 Agent 工作流”。

## 5. 管理约定

- Risk Review 多智能体相关新增论文，优先补充到本文档，再在 `REVIEW_AGENTIC_MARO_REFERENCE.md` 和 `doc/research/literature-references.md` 中做摘要式映射。
- 若论文无官方开源仓库，统一写为“未确认开源仓库”，不要臆造 GitHub 链接。
- 若存在社区实现而非官方实现，必须明确标注“社区实现”。
