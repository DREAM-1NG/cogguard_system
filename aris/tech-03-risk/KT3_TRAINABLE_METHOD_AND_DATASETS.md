# KT3 可训练方法推进与数据集缺口

## 1. 文档目标与能力边界

本文档回答一个具体问题：当前 KT3 已经具备帖子级多模态推理脚手架、用户级 Attention-MIL 风格聚合和本地多智能体复核运行时，下一步如何推进为可训练方法，以及需要哪些数据集支撑。

必须先固定边界：

- 当前 `post_semantics.py` 的 `multimodal_detection` 已融合 text、OCR、ASR、caption/media、emoji/hashtag，但不是已训练图像/视频多模态模型。
- 当前 `post_semantics.py` 已新增 `post_view_detection`，把帖子拆成 `tweet / meme / img / video` 四视图并执行 majority vote / weighted fusion；这是运行时 scaffold 与输出契约，不等于训练式 view detector 已完成。
- 当前已在 MultiOFF 上跑通 `text_only / image_only / late_fusion` ablation，其中 `image_only` 使用冻结 CLIP 图像 encoder，`late_fusion` 在 validation split 上调权；该结果只证明 MultiOFF 图文视图验证链路可执行，不代表跨 benchmark 全量验证。
- 当前 `kt3_user_mil.py` 已把账户建模为 post bag 并输出 `mil_harm_score` 和 `attention_posts`，但不是已训练神经 MIL、temporal Transformer 或 user encoder。
- 当前 `kt3_multi_agent.py` 已执行 Harm、Stance/Claim、Evidence、UserMIL、CommunityJudge、CounterNarrative 六个本地 agent，但默认不调用在线 LLM、外部搜索或向量库 RAG。
- 下一步训练目标不是把更多手工特征堆进规则，而是把现有接口升级为可学习的 `post encoder -> user MIL/temporal encoder -> community graph encoder`，并把 Agent/RAG 放在 teacher、reviewer、retriever、verifier 和 report orchestrator 位置。

推荐的数据目录策略是：公开大数据集和媒体文件不进入 Git 仓库，统一放在 `G:\CISCN\dataset\kt3_public\`；项目域 gold/control set 放在 `G:\CISCN\dataset\kt3_project_gold\`；仓库内只保存 manifest、schema、采样脚本和实验配置。

## 2. 总体训练闭环

KT3 的可训练闭环应分四层：

| 层级 | 当前实现 | 可训练目标 | 核心监督 | Agent/RAG 位置 |
|---|---|---|---|---|
| 帖子级 | late-fusion scaffold | 多模态、claim-conditioned、evidence-aware post model | harm label/type、target、stance、claim link、rationale/evidence、abstain | teacher 标注、证据检索、低置信复核 |
| 用户级 | deterministic Attention-MIL scaffold | trainable MIL / temporal user encoder | user harmful label、persistence、harm mixture、role、representative posts | 聚合解释复核、困难账户抽样 |
| 社区级 | graph export + community gate | HGT / Graph Transformer / TGN 社区 harmfulness model | community harm、amplification、subgroup role、target/claim concentration | 社区级 judge、subgraph explanation 审核 |
| 多智能体 | local deterministic agents | 可插拔 reviewer / retriever / verifier / rule optimizer | 复核结论、证据充分性、分歧、人工审核结果 | 不替代底层分类器，负责审计和闭环 |

训练闭环的关键不是一次性端到端训练所有层，而是先把数据契约、split、leakage policy、label policy 固定下来，再逐层训练和验收。推荐顺序是：

1. 建立 `kt3_train_dataset_manifest`，记录数据来源、版本、许可证、split、事件时间窗、媒体可用性、label policy、泄漏隔离策略。
2. 训练帖子级模型，先解决单条内容的 harm、stance、claim link 和 evidence 输出。
3. 冻结或半冻结帖子级 encoder，用它为用户级 MIL 提供 post embeddings 和 calibrated post predictions。
4. 在用户级上训练 bag-level harmfulness、persistence、harm-type mixture 和 representative evidence。
5. 用帖子和用户表示构建 account-post-claim-target-media-community 异构图，训练社区级 collective harm 模型。
6. 多智能体系统读取三层模型输出，负责 disagreement resolution、证据补全、低置信样本回流和反制叙事草案，不直接作为线上底层分类器。

## 3. 帖子级：从 scaffold 到可训练多模态模型

帖子级统一模型与全量验证的正式设计见 [KT3_POST_UNIFIED_MODEL_AND_VALIDATION.md](./KT3_POST_UNIFIED_MODEL_AND_VALIDATION.md)。本节保留训练路线总览，细化的 `MV-PostGuard` 四视图检测器、投票/融合公式、benchmark 验证矩阵和本地数据 readiness 以该专文为准。

当前最新可执行验证进展：`system/backend/scripts/run_kt3_multioff_multiview_ablation.py` 已在 MultiOFF official split 上完成 `D_tweet` text-only、`D_img` CLIP image-only、selective majority vote、validation-tuned late fusion 和 learned fusion 对照。结果保存在 `G:\CISCN\.tmp\kt3_post_multiview_ablation_full_registry\report.json`，MultiOFF 当前最优为 `learned_fusion`，Test Macro-F1 = 0.655878；其中 `late_fusion` Test Macro-F1 = 0.620743。该实验是可训练路线的第一步：冻结 CLIP 表示 + 轻量分类头 + validation-tuned/learned fusion。

进一步地，`system/backend/scripts/run_kt3_post_multiview_ablation.py` 已把本地可用数据统一到 full-registry suite：MultiOFF 跑 `text/image/majority_vote/late_fusion/learned_fusion`，PHEME 跑 `text_only / claim_context_only / claim_context_late_fusion`，FakeSV 跑 `text_only / video_feature_only / video_text_late_fusion`，HateXplain 和 mcfend 跑 text 或 claim-context baseline。结果保存在 `G:\CISCN\.tmp\kt3_post_multiview_ablation_full_registry\report.json`。该 suite 现在额外输出 `coverage_matrix`，用于区分“有指标”和“完成该数据集期望视图验证”；下一步才是 Hateful Memes/MAMI/MMHS150K/MOCHEG/FACTIFY3M 等跨 benchmark 扩展。

当前 suite 的可复现结果是：MultiOFF learned-fusion Test Macro-F1 = 0.655878；HateXplain text-only Test Macro-F1 = 0.766130；PHEME event-holdout text-only Test Macro-F1 = 0.591510，并新增 claim-context metadata view；mcfend claim-context-only Test Macro-F1 = 0.818745；FakeSV temporal split text-only metadata proxy Test Macro-F1 = 0.772814，C3D `video_feature_only` Test Macro-F1 = 0.604837，text + C3D `late_fusion` Test Macro-F1 = 0.783923。它证明统一 schema、split policy、训练/验证/测试报告、missing-view skipped policy、claim-context metadata baseline、预提取视频特征 baseline 和 view-coverage gate 已经跑通，但不证明 `MV-PostGuard` 的 raw-video encoder、ASR/OCR/audio/social context、external evidence/RAG view 或全 P0 benchmark 验证已完成。

### 3.1 任务定义

输入是一条帖子及其多模态上下文：

- 文本：正文、评论上下文、hashtags、emoji、提及对象。
- 图像：原图、OCR 文本、caption/alt text、视觉 embedding。
- 视频：关键帧、ASR、字幕、OCR、视频标题/封面/描述。
- Claim context：候选 claim、上游传播链路、同事件历史 claim、外部 fact-check evidence。

输出是联合结果：

- `harmfulness`: `harmful / non_harmful / uncertain`。
- `harm_type`: misinformation、hate/harassment、targeted smear、incitement/mobilization、manipulative amplification 等多标签。
- `target`: 被攻击群体、个人、组织、事件对象。
- `claim_link`: 当前帖子关联的 primary claim 或 `unlinked`。
- `stance`: support、deny、query、neutral、uncertain。
- `evidence`: 支撑判断的文本 span、OCR/ASR 片段、图像区域或检索证据。
- `abstain/calibration`: 低置信或证据不足时进入复核队列。

### 3.1.1 多视图帖子级 harmfulness 形式化

为了让帖子级研判可以被实现、训练和验收，KT3 将单条帖子 `p` 形式化为四类可选视图的集合：

`p = (x_tweet, x_meme, x_img, x_video, c, m)`

其中 `x_tweet` 表示文本/转评赞上下文/hashtags/emoji，`x_meme` 表示图文 meme 的联合对象，`x_img` 表示普通图像及其 OCR/caption/视觉区域，`x_video` 表示短视频及其关键帧/OCR/ASR/封面/标题/评论上下文，`c` 表示候选 claim/evidence context，`m` 表示元数据与事件上下文。并不是每条帖子都有四类视图，因此每个视图都有可用性标记 `a_v in {0,1}`。

对每个视图定义一个检测器：

| 检测器 | 输入 | 输出 | 典型方法 |
|---|---|---|---|
| `D_tweet` | `x_tweet, c` | `y_tweet, q_tweet, e_tweet` | 文本 encoder + claim-conditioned stance/harm head |
| `D_meme` | `x_meme, c` | `y_meme, q_meme, e_meme` | image-text encoder + OCR/caption/rationale |
| `D_img` | `x_img, c` | `y_img, q_img, e_img` | CLIP/ViT/BLIP-style visual-language encoder + OCR |
| `D_video` | `x_video, c` | `y_video, q_video, e_video` | keyframe + OCR + ASR + video/social context encoder |

其中 `y_v` 是该视图对 harmfulness 的判断，取值为 `harmful / non_harmful / uncertain`；`q_v` 是校准后的置信度或 harmful probability；`e_v` 是该视图给出的证据片段、区域、帧、OCR/ASR span 或检索证据。

最终帖子级判断由融合函数给出：

`Y_p = F({(a_v, y_v, q_v, e_v) | v in {tweet, meme, img, video}}, c, m)`

最低可用工程版可以采用多数投票，但必须先定义 Effective View：

- `I_v = 1[a_v = 1 and abstain_v = false and y_v in {harmful, non_harmful}]`。
- 只对 `I_v = 1` 的视图投票；缺少可解码媒体证据的视图必须 abstain，不能被当作 non-harmful。
- `harmful` 票数严格超过有效视图半数时输出 `harmful`。
- `non_harmful` 票数严格超过有效视图半数时输出 `non_harmful`。
- 票数相等、有效视图不足、最高置信度低于阈值、或视图间强冲突时输出 `uncertain` 并进入复核。

更推荐的训练式版本是加权投票或 late fusion：

`s_p = sum_v I_v * alpha_v * q_v * s_v / sum_v I_v * alpha_v * q_v`

其中 `alpha_v` 可以先由验证集上各视图可靠性设定，后续由 gating network 学习；`s_v` 是视图级 harmfulness score。最终可用 `s_p >= tau_h` 判为 harmful，`s_p <= tau_n` 判为 non-harmful，中间区间判为 uncertain。这样既保留了“tweet / meme / img / video 分别 detect 后融合”的可解释结构，也允许模型学习不同平台、不同事件、不同模态质量下的可靠性差异。

融合层必须输出审计字段：

- `view_results`: 每个检测器的 label、score、confidence、evidence、available flag。
- `fusion_policy`: majority vote、weighted vote、learned late fusion 或 human-review override。
- `conflict`: 是否存在文本否认但图像支持、ASR 与 caption 冲突、meme 语义反讽等跨视图冲突。
- `final_harmfulness`: 最终 harmful / non_harmful / uncertain。
- `review_reason`: 触发复核的原因，例如 low confidence、missing dominant modality、cross-view conflict、claim unlinked。

### 3.2 方法路线

帖子级推荐采用 teacher-student 训练，而不是在线每条帖子直接让 LLM 裁决。

Teacher 阶段：

- 用公开 gold 数据集校准标注规范，例如 HateXplain 的 label、target、rationale，RumourEval/PHEME 的 stance/thread，MOCHEG/FACTIFY3M 的 claim-evidence-explanation，Hateful Memes/FakeSV 的多模态样本。
- 用多模态 LLM 或强指令模型离线生成 `harm label + harm type + target + stance + rationale + uncertainty`，只作为弱标签或候选标签。
- 对高影响样本、低置信样本、跨模态冲突样本做人工审核，形成项目域 gold/control set。

Student 阶段：

- 文本编码器：中文/多语 RoBERTa、DeBERTa、XLM-R 或领域小模型，输出 post text embedding。
- 图像编码器：CLIP、ViT、BLIP-2 类视觉语言表示，结合 OCR 和 caption。
- 视频编码器：最低可用路线是关键帧 + OCR + ASR + title/description + comment context；后续再接 Video-LLaVA、InternVideo 或 VideoMAE 风格的视频表示。
- Claim-conditioned 模块：使用 bi-encoder 检索候选 claim，再用 cross-encoder / reranker 判断 claim link 和 stance。
- Evidence-aware 模块：对 text span、OCR/ASR span、image region、retrieved evidence 做 attention 或 cross-attention，用于解释和复核。

训练目标建议采用多任务联合：

| 目标 | 训练信号 | 损失或约束 |
|---|---|---|
| harmfulness | harmful/non-harmful/uncertain | cross entropy、focal loss、class-balanced loss |
| harm type | 多标签 harm 类型 | binary cross entropy |
| stance | support/deny/query/neutral/unlinked | cross entropy + claim-conditioned negatives |
| claim link | post-claim pair | contrastive loss / pairwise ranking loss |
| evidence/rationale | text span、OCR/ASR span、image evidence | token/region supervision、rationale alignment loss |
| distillation | teacher probability / rationale / explanation | KL divergence、temperature distillation |
| calibration | abstain、uncertain、human-review | ECE-aware calibration、selective classification objective |

评估不能只看 accuracy。帖子级最低指标应包括 macro-F1、harm-type micro/macro-F1、stance macro-F1、claim-link recall@k、evidence recall/nDCG、rationale plausibility/faithfulness、ECE calibration、abstain coverage-risk curve。

### 3.3 主要参考方法

- [HateXplain, AAAI 2021](https://ojs.aaai.org/index.php/AAAI/article/view/17745)：提供 hate/offensive/normal、target community 和 human rationales，适合支撑 harmfulness + target + rationale。
- [Hateful Memes, NeurIPS 2020](https://ai.meta.com/tools/hatefulmemes/)：强调图文联合语义，单模态模型容易失败，适合支撑多模态 harmfulness。
- [MultiOFF, TRAC 2020](https://aclanthology.org/2020.trac-1.6/) 与 [MAMI, SemEval 2022](https://aclanthology.org/2022.semeval-1.74/)：分别提供 offensive meme 与 misogyny subtype 任务，适合验证 meme/image/text 融合和 targeted harm subtype。
- [CLIP, ICML 2021](https://proceedings.mlr.press/v139/radford21a.html) 与 [BLIP-2, ICML 2023](https://proceedings.mlr.press/v202/li23q.html)：提供可迁移视觉语言 encoder / caption-rationale teacher 路线，适合从冻结 encoder + adapter 起步，避免在小数据上端到端训练过拟合。
- [MOCHEG, SIGIR 2023](https://dl.acm.org/doi/10.1145/3539618.3591879)：把 fact-checking 做成 claim truthfulness、文本/图像 evidence 和 explanation generation。
- [FACTIFY3M, EMNLP 2023](https://aclanthology.org/2023.emnlp-main.945/)：大规模多模态 fact verification，并引入 5W QA 解释。
- [FakeSV, AAAI 2023](https://ojs.aaai.org/index.php/AAAI/article/view/26689)：中文短视频 fake news，包含内容、评论和发布者画像，适合迁移到短视频帖子。
- [MuMiN](https://mumin-dataset.github.io/)：多语言、多模态、fact-checked misinformation heterogeneous graph，适合把帖子级输出接到用户级和社区级。
- [MARO, EMNLP 2025](https://aclanthology.org/2025.emnlp-main.291/)：把多专家 Agent、question-reflection 和自动决策规则优化用于跨域 misinformation detection。KT3 应迁移它的 reviewer/rule-optimizer 思路，但不应让 Agent 直接替代底层可训练 view detector。

### 3.4 文献启示下的实现闭环

这些高水平工作共同指向一个实现闭环：先训练可部署的 view detector，再让 Agent 做复核与规则优化，而不是把每条帖子直接交给 LLM zero-shot。

1. `D_tweet`：以 HateXplain/Jigsaw/PHEME/mcfend 为主训练文本 harmfulness、claim-conditioned stance 与 calibration；HateXplain 的 target/rationale 用于训练解释头，不能只保留二分类 label。
2. `D_meme / D_img`：以 MultiOFF/Hateful Memes/MAMI/MMHS150K 为主，采用 frozen CLIP/BLIP-2 表示 + 轻量分类头；每个实验必须报告 text-only、image-only、OCR-only 和 fusion ablation。
3. `D_video`：以 FakeSV 为主，先实现 keyframe/OCR/ASR/title/comment/publisher context 的多视图 temporal pooling；没有 ASR/OCR/caption 时必须 abstain，不能用视频 URL 或 tweet 文本冒充视频判断。
4. `Claim/Evidence`：以 RumourEval/PHEME/MOCHEG/FACTIFY3M/FEVER/HoVer/AVeriTeC 为主，训练 claim retrieval、stance/veracity 和 evidence selection；misinformation 型 harm 必须保留 claim link 与 evidence。
5. `Fusion/Gating`：先用 validation-tuned weighted late fusion，随后训练 gating network；训练目标包括 macro-F1、ECE、coverage-risk 和 cross-view conflict review rate。
6. `Agent Reviewer`：参考 MARO，把 Agent 放在 disagreement resolution、question generation、rule optimization、难例回流和 counter-narrative 草案，不作为底层分类器本身。

## 4. 用户级：从 deterministic MIL 到可训练 MIL/时序模型

### 4.1 任务定义

用户级输入不是账户 profile 表格，而是同一账户在事件窗口内的帖子 bag 或 sequence：

- `B_u = {p_1, p_2, ..., p_n}`，每个 `p_i` 包含帖子级 embedding、harm/stance/claim/evidence 输出和时间戳。
- 可选上下文包括账户在传播图中的角色、与其他账户的互动边、同 claim 下的行为轨迹和平台来源。

输出包括：

- `user_harmful`: 该账户是否持续参与 harmful 传播。
- `persistence`: accidental、episodic、persistent。
- `harm_type_mixture`: 账户层 harm 类型分布。
- `role`: originator、amplifier、harasser、mobilizer、bridge、participant 等。
- `representative_posts`: 对账户判断贡献最大的帖子证据。
- `uncertainty`: 样本太少、跨事件不稳定或证据冲突时进入复核。

### 4.2 方法路线

用户级训练建议从 Attention-MIL 起步，再扩展时序和图关系：

1. 用帖子级 student encoder 生成每条帖子表示 `z_i`。
2. 用 attention pooling 学习 `a_i = softmax(w^T tanh(Vz_i))`，得到账户表示 `z_u = sum_i a_i z_i`。
3. 用 bag-level label 训练账户 harmfulness，同时用 attention 权重解释关键帖子。
4. 对时序强的场景加入 temporal Transformer，把同一账户在事件窗口内的行为轨迹建模为序列。
5. 对互动强的场景加入 ego-graph 或 heterogeneous graph，把用户间 reply/repost/mention/co-share 关系作为上下文表示。

训练目标建议：

| 目标 | 监督来源 | 训练方式 |
|---|---|---|
| user harmfulness | 人工账户标签、平台处置标签、项目 gold | bag-level CE/BCE |
| persistence | 时间窗内重复 harmful 行为标签 | ordinal / multi-class loss |
| harm mixture | 账户帖子 harm type 聚合 gold | multi-label BCE |
| role | 传播图/人工角色标签 | multi-label BCE |
| representative evidence | 人工标注关键帖子或 teacher 证据 | attention alignment / ranking |
| cross-domain robustness | 不同事件/平台 split | domain adversarial 或 invariant risk 约束 |

这里的关键是：帖子数量、发帖频率、automation score、协同账户等信息可以作为上下文节点或 embedding，但不应成为主方法的手工阈值。主要判断应由 post representation、temporal aggregation 和 relation-aware aggregation 学到。

### 4.3 主要参考方法

- [Attention-based Deep MIL, ICML 2018](https://proceedings.mlr.press/v80/ilse18a.html)：把 bag-level label 学成可解释 attention aggregation，是用户级 post bag 的直接方法基础。
- [Characterizing and Detecting Hateful Users on Twitter, ICWSM 2018](https://ojs.aaai.org/index.php/ICWSM/article/view/15057)：将 hate speech 从单帖迁移到账户层，证明用户历史和网络结构对 hateful user 识别重要。
- [Modeling Users and Online Communities for Abuse Detection, Findings EMNLP 2021](https://aclanthology.org/2021.findings-emnlp.287/)：讨论用户/社区信息在 abuse detection 中的价值和伦理边界，适合指导 KT3 的能力边界。
- [You too Brutus, ACM HT 2021](https://dl.acm.org/doi/10.1145/3465336.3475106)：强调仅看文本会忽略用户社交连接，适合支撑用户级图关系建模。

## 5. 社区级：从图导出到可训练异构图模型

社区级不是成员 harmful score 的平均值，而是 collective harm 建模。推荐图结构为：

- 节点：account、post、claim、target、media、community、event。
- 边：account-authors-post、post-supports/denies-claim、post-mentions-target、post-uses-media、account-replies/reposts/mentions-account、account-co-shares-object、account-in-community。
- 节点表示：帖子级 encoder 输出、用户级 MIL 输出、claim/evidence embedding、media embedding。

可训练模型路线：

- HGT 或 Graph Transformer：处理多类型节点和边，学习 community representation。
- Temporal Graph Network：处理事件窗口内的动态 harm amplification。
- Graph contrastive learning：同一 campaign 或同一 claim 下的子图作为正样本，不同事件/control set 作为负样本。
- Subgraph explanation：输出关键账户、关键帖子、关键 claim 和关键 target，供 CommunityJudgeAgent 复核。

社区级输出包括 `collective_harm`、`harm_type_distribution`、`coordinated_amplification`、`subgroup_roles`、`target_concentration` 和 `evidence_subgraph`。评估指标包括 community macro-F1、role micro-F1、claim/target coverage、evidence subgraph precision、跨事件泛化和 control set false positive rate。

主要参考包括 [Heterogeneous Graph Transformer, WWW 2020](https://dl.acm.org/doi/10.1145/3366423.3380027)、[Graphormer, NeurIPS 2021](https://proceedings.neurips.cc/paper/2021/hash/f1c1592588411002af340cbaedd6fc33-Abstract.html)、[Temporal Graph Networks](https://arxiv.org/abs/2006.10637)、[Mannocci 等 coordinated online behavior survey](https://arxiv.org/abs/2304.09884)、[Labeled Datasets for Research on Information Operations, ICWSM 2025](https://ojs.aaai.org/index.php/ICWSM/article/view/35958) 和 [Coordinated Reply Attacks in Influence Operations, ICWSM 2025](https://ojs.aaai.org/index.php/ICWSM/article/view/35889)。

## 6. 多智能体：从本地运行时到训练闭环中的 reviewer/retriever

MARO 可以参考，但不能直接替代 KT3 的三层模型。原因是 MARO 解决的是跨域 misinformation detection 的多专家分析和决策规则优化，而 KT3 的任务是帖子、用户、社区三层 harmfulness characterization。

合理迁移方式是：

- Agent 做 teacher：离线生成弱标签、解释、低置信原因和可疑证据。
- Agent 做 reviewer：对 student 模型的高风险/低置信/跨模态冲突样本复核。
- Agent 做 retriever：检索 fact-check evidence、claim history、DISARM technique、相似历史事件。
- Agent 做 verifier：检查输出是否有证据、是否过度推断、是否需要人工审核。
- Agent 做 rule optimizer：参考 MARO，对复核规则和采样策略做跨事件验证，而不是写死手工规则。

训练中可以把多智能体输出作为 `weak label / rationale candidate / disagreement signal / review priority`，但不能把 agent verdict 无审核地当作 gold。上线时默认仍应走本地 deterministic fallback，并保留 provider audit、failure fallback、human review 和 no-auto-publish 的安全边界。

主要参考包括 [MARO, EMNLP 2025](https://aclanthology.org/2025.emnlp-main.291/)、[ReAct, ICLR 2023](https://openreview.net/forum?id=WE_vluYUL-X)、[RAG, NeurIPS 2020](https://arxiv.org/abs/2005.11401) 和多模态 fact-checking agent 工作。

## 7. 数据集支撑矩阵

表中链接优先使用官方论文页、数据主页、作者/组织 GitHub、Figshare、Zenodo、Kaggle 或竞赛主页。若没有确认的官方开源仓库，表中显式标注为“未确认官方仓库”，后续下载前必须再次检查 license、access policy 和可再分发限制。

当前机器可读权威入口是：

`G:\CISCN\CogGuard\system\backend\app\core\risk\config\kt3_post_benchmarks.json`

最新审计报告是：

`G:\CISCN\.tmp\kt3_post_dataset_audit_v2.json`

该 registry/audit 将 P0 benchmark 分成三类：`download_or_clone_public_dataset`、`accept_terms_then_download`、`request_dataset_access_then_download`。后续补数据时应优先更新 registry，再扩展 converter 和 suite，而不是在文档里手工维护散落链接。

| 数据集/资源 | 层级 | 论文/主页 | 数据/开源仓库入口 | 主要用途 | 本地状态 |
|---|---|---|---|---|---|
| HateXplain | 帖子级 | [AAAI 2021](https://ojs.aaai.org/index.php/AAAI/article/view/17745) | [official GitHub](https://github.com/hate-alert/HateXplain) | harm label、target、rationale supervision | 已有：`G:\CISCN\dataset\kt3_public\HateXplain`；已转换 20148 条；text-only Macro-F1 0.766130 |
| Jigsaw Toxicity | 帖子级 | [Kaggle challenge](https://www.kaggle.com/competitions/jigsaw-toxic-comment-classification-challenge) | [Kaggle data page](https://www.kaggle.com/competitions/jigsaw-toxic-comment-classification-challenge/data) | toxic/harmful 文本预训练和校准 | 缺少 |
| Hateful Memes | 帖子级 | [Meta data page](https://ai.meta.com/tools/hatefulmemes/) | [DrivenData challenge](https://www.drivendata.org/competitions/64/hateful-memes/page/205/)、[baseline GitHub](https://github.com/drivendataorg/hateful-memes/) | 图文联合 harmfulness | 缺少 |
| MMHS150K | 帖子级 | [WACV 2020 PDF](https://openaccess.thecvf.com/content_WACV_2020/papers/Gomez_Exploring_Hate_Speech_Detection_in_Multimodal_Publications_WACV_2020_paper.pdf) | [dataset/project page](https://gombru.github.io/2019/10/09/MMHS/)、[Kaggle mirror](https://www.kaggle.com/datasets/victorcallejasf/multimodal-hate-speech) | 社交图文 hate speech 扩展 | 缺少；原 registry GitHub 链接不可访问，本机无 Kaggle 凭据，需接受 Kaggle/Twitter media 条款后下载 |
| MAMI | 帖子级 | [SemEval 2022 paper](https://aclanthology.org/2022.semeval-1.74/) | [official GitHub](https://github.com/MIND-Lab/SemEval2022-Task-5-Multimedia-Automatic-Misogyny-Identification-MAMI-)、[CodaLab](https://competitions.codalab.org/competitions/34175) | 图文 misogyny / targeted harm | 缺少 |
| MultiOFF | 帖子级 | [TRAC 2020 paper](https://aclanthology.org/2020.trac-1.6/) | [registry 记录入口](../../system/backend/app/core/risk/config/kt3_post_benchmarks.json) | 图文 offensive/harmful 辅助训练 | 已有：`G:\CISCN\dataset\MultiOFF`，partial，3 条图片缺失 |
| RumourEval 2019 | 帖子级 | [SemEval 2019 paper](https://aclanthology.org/S19-2147/) | [CodaLab task data](https://competitions.codalab.org/competitions/19938)、[baseline GitHub](https://github.com/kochkinaelena/RumourEval2019) | claim-conditioned stance / veracity | present_unverified：baseline repo 已 clone 到 `G:\CISCN\dataset\kt3_public\RumourEval2019`，但 CodaLab 原始数据缺失 |
| PHEME | 帖子/用户/社区 | [Zubiaga dataset index](https://www.zubiaga.org/datasets/) | [Figshare veracity data](https://figshare.com/articles/dataset/PHEME_dataset_for_Rumour_Detection_and_Veracity_Classification/6392078)、[rumours/non-rumours data](https://figshare.com/articles/dataset/PHEME_dataset_of_rumours_and_non-rumours/4010619) | stance/thread、用户/社区弱监督 | 已有：`G:\CISCN\dataset\PHEME` |
| Twitter15/16 | 帖子/传播 | [Rumor RvNN GitHub/paper entry](https://github.com/majingCUHK/Rumor_RvNN) | [dataset mirror GitHub](https://github.com/gszswork/Twitter15_16_dataset) | rumor propagation、时间/社区结构 | 已有：`G:\CISCN\dataset\Twitter15_16_dataset` |
| FEVER | 帖子级 | [NAACL 2018 paper](https://aclanthology.org/N18-1074/) | [awslabs/fever](https://github.com/awslabs/fever)、[sheffieldnlp repo](https://github.com/sheffieldnlp/naacl2018-fever) | textual claim-evidence verification | 缺少 |
| HoVer | 帖子级 | [Findings EMNLP 2020 paper](https://aclanthology.org/2020.findings-emnlp.309/) | [homepage](https://hover-nlp.github.io/)、[GitHub](https://github.com/hover-nlp/hover) | multi-hop claim evidence | 缺少 |
| AVeriTeC | 帖子级 | [NeurIPS Datasets 2023](https://proceedings.neurips.cc/paper_files/paper/2023/hash/cd86a30526cd1aff61d6f89f107634e4-Abstract-Datasets_and_Benchmarks.html) | [FEVER dataset page](https://fever.ai/dataset/averitec.html)、[GitHub](https://github.com/MichSchli/AVeriTeC) | real-world claim verification with web evidence | 缺少 |
| MOCHEG | 帖子级 | [SIGIR 2023 paper](https://dl.acm.org/doi/10.1145/3539618.3591879) | [official GitHub](https://github.com/VT-NLP/Mocheg)、[MOCHEG v1 request form](https://docs.google.com/forms/d/e/1FAIpQLScAGehM6X9ARZWW3Fgt7fWMhc_Cec6iiAAN4Rn1BHAk6KOfbw/viewform?usp=sf_link) | 多模态 fact-checking、evidence、explanation | present_unverified：official implementation 已 clone 到 `G:\CISCN\dataset\kt3_public\Mocheg`，但 MOCHEG v1 数据缺失 |
| FACTIFY / FACTIFY3M | 帖子级 | [EMNLP 2023 paper](https://aclanthology.org/2023.emnlp-main.945/)、[arXiv](https://arxiv.org/abs/2306.05523) | [FACTIFY3M paper](https://aclanthology.org/2023.emnlp-main.945/)、[older Factify baseline repo](https://github.com/Shreyashm16/Factify) | 多模态 fact verification、5W QA explanation | 缺少；原 registry GitHub 不可访问，已 clone older Factify baseline 但不含数据文件 |
| FakeSV | 帖子/用户 | [AAAI 2023 paper](https://ojs.aaai.org/index.php/AAAI/article/view/26689) | [official GitHub](https://github.com/ICTMCG/FakeSV)、[HF features/checkpoints](https://huggingface.co/datasets/MischaQI/FakeSV) | 中文短视频 fake news、评论和发布者上下文 | ready for current video-feature baseline：公开 `data.json` 与 temporal split 已转换 5495 条；C3D zip 覆盖 train/validation/test，video_feature_only Macro-F1 0.604837，text+C3D late_fusion Macro-F1 0.783923；raw video、audio、ASR/OCR、评论/发布者上下文仍缺 |
| Fakeddit | 帖子级 | [LREC 2020 paper](https://aclanthology.org/2020.lrec-1.755/) | [official GitHub](https://github.com/entitize/Fakeddit)、[dataset website](https://fakeddit.netlify.app/) | 图文 misinformation 预训练 | present_unverified：downloader repo 已 clone 到 `G:\CISCN\dataset\kt3_public\Fakeddit`，但 v2.0 TSV 与 image data 需 Google Drive/CodaLab 下载 |
| MuMiN | 帖子/用户/社区 | [dataset website](https://mumin-dataset.github.io/)、[SIGIR 2022 paper](https://dl.acm.org/doi/10.1145/3477495.3531744) | [mumin-build](https://github.com/MuMiN-dataset/mumin-build)、[mumin-baseline](https://github.com/MuMiN-dataset/mumin-baseline)、[mumin-trawl](https://github.com/MuMiN-dataset/mumin-trawl) | 多语、多模态、fact-checked misinformation 异构图 | 缺少 |
| MCFEND | 帖子/用户 | [registry 记录入口](../../system/backend/app/core/risk/config/kt3_post_benchmarks.json) | [registry 记录入口](../../system/backend/app/core/risk/config/kt3_post_benchmarks.json) | 中文 fake news、多源 social context | 已有：`G:\CISCN\dataset\mcfend`；当前 post-case 只转换 text/claim，social_context 未纳入 |
| Hateful Users Twitter | 用户级 | [ICWSM 2018 paper](https://ojs.aaai.org/index.php/ICWSM/article/view/15057) | [author GitHub](https://github.com/manoelhortaribeiro/HatefulUsersTwitter) | user harmfulness、用户图建模 | 缺少完整可用 gold；仓库因平台政策仅部分共享 |
| 用户/社区 abuse 方法参考 | 用户/社区 | [Findings EMNLP 2021](https://aclanthology.org/2021.findings-emnlp.287/) | 方法论文，无单一数据仓库 | 用户/社区建模伦理与解释边界 | 作为方法参考 |
| IOHunter | 社区级 | [AAAI 2025 paper](https://dl.acm.org/doi/10.1609/aaai.v39i27.35046) | [official reproduction GitHub](https://github.com/mminici/InfoOpsGFM) | IO 图训练、跨行动泛化、control | 已有：`G:\CISCN\dataset\iohunter` |
| Labeled IO Datasets | 社区级 | [ICWSM 2025/arXiv](https://arxiv.org/html/2411.10609v1) | 论文入口；具体数据访问需按作者说明核验 | IO campaign/control set | 本地未见完整官方包 |
| Russian Troll Tweets | 社区级 | [FiveThirtyEight GitHub](https://github.com/fivethirtyeight/russian-troll-tweets) | [same GitHub data repo](https://github.com/fivethirtyeight/russian-troll-tweets) | IRA tweets、IO 行为弱监督、社区级案例 | 已有：`G:\CISCN\dataset\russian-troll-tweets` |
| Twitter/X Information Operations Archive | 社区级 | [X/Twitter disclosure blog](https://blog.x.com/en_us/topics/company/2021/disclosing-state-linked-information-operations-we-ve-removed) | [RAND archive entry](https://www.rand.org/research/projects/truth-decay/fighting-disinformation/search/items/information-operations-archive.html) | state-linked IO archive、campaign/control | 已有：`G:\CISCN\dataset\twitter_io` |
| CooRTweet demo data | 社区级 | [CCR 2025 paper](https://journal.computationalcommunication.org/article/view/5698) | [GitHub](https://github.com/nicolarighetti/CooRTweet)、[CRAN vignette](https://cran.r-project.org/web/packages/CooRTweet/vignettes/vignette.html) | 协同行为 smoke / method demo | 已有：`G:\CISCN\CogGuard\CooRTweet-master\data` |
| DISARM framework | Agent/RAG/知识库 | [DISARM Foundation](https://www.disarm.foundation/framework) | [DISARMframeworks GitHub](https://github.com/DISARMFoundation/DISARMframeworks/) | DISARM TTP 本体、反制叙事与路径解释 | 需作为 KB 拉取/版本化 |
| MITRE Technique Inference Engine | 方法迁移 | [MITRE CTID project](https://ctid.mitre.org/projects/technique-inference-engine/) | [GitHub](https://github.com/center-for-threat-informed-defense/technique-inference-engine) | “已观测 TTP 推断下一步 TTP”的路径预测范式 | 方法迁移参考 |
| MediaCrawler 数据 | 帖子/用户/项目域 | [project docs](https://nanmicoder.github.io/MediaCrawler/) | [GitHub](https://github.com/NanmiCoder/MediaCrawler) | 项目域适配、teacher 标注、人审 gold 构建 | 已有：`G:\CISCN\CogGuard\MediaCrawler-main\data` 与 `data_runs`，无 KT3 gold |
| KT3 project gold/control set | 三层 | 内部构建 | 建议落盘到 `G:\CISCN\dataset\kt3_project_gold\`，仓库只保存 manifest/schema | 正式验收和项目域训练 | 缺少 |

## 8. 本地已有数据能支撑什么

本地已有数据已经能支撑一部分帖子级 text harmfulness 与 text/claim misinformation baseline，但仍不足以训练完整 KT3 多模态 harmfulness。

可直接利用的部分：

- `G:\CISCN\dataset\PHEME`：可用于 claim/rumour thread、stance 和事件级传播结构实验，也可以为用户级 MIL 构造弱 bag，但不是 harmfulness gold。
- `G:\CISCN\dataset\kt3_public\HateXplain`：可用于 text harmfulness、target community 和 rationale supervision；当前已完成 text-only harmfulness 评测，尚未训练 target/rationale head。
- `G:\CISCN\dataset\Twitter15_16_dataset`：可用于谣言传播树和事件级时间泛化，不直接提供 hate/harassment/mobilization 等 harm 类型。
- `G:\CISCN\dataset\mcfend`：可作为中文 fake news/social context 数据源，但需要先确认字段、label policy、许可证和 split。
- `G:\CISCN\dataset\iohunter`、`G:\CISCN\dataset\twitter_io`、`G:\CISCN\dataset\russian-troll-tweets`：可支撑 IO/协同图和社区级弱监督，但不能替代帖子级 harmfulness 或用户级 harmful gold。
- `G:\CISCN\CogGuard\CooRTweet-master\data\*.rda`：适合协同行为检测/演示，不是 KT3 harmfulness 训练集。
- `G:\CISCN\CogGuard\MediaCrawler-main\data` 和 `data_runs`：适合做中文平台项目域样本池，可通过 teacher + 人审构建 KT3 gold/control set，但当前没有明确 harm/stance/user/community gold。

## 9. 本地缺少的数据

按优先级看，本地还缺少以下数据：

1. 帖子级 harmfulness gold：Jigsaw Toxicity、Hateful Memes、MMHS150K、MAMI；HateXplain 已有并已评测，MultiOFF 已有但有 3 条图片缺失。
2. 帖子级 claim-conditioned stance / verification gold：RumourEval 2019 原始 CodaLab 数据、FEVER、HoVer、AVeriTeC、MOCHEG v1 数据、FACTIFY/FACTIFY3M；其中 RumourEval/MOCHEG 的代码仓库已在本地，但不能替代原始 gold 数据。
3. 视频/短视频多模态 gold：FakeSV 当前已有公开 video id、keywords、label、split 和 C3D 预提取视频特征 baseline；仍缺 raw videos、评论/发布者上下文、VGG19/VGGish/audio、ASR/OCR/keyframe 等更完整视听与社交上下文。
4. 多模态异构图数据：MuMiN 或可替代的 fact-checked social graph。
5. 用户级 harmfulness gold：带账户标签、历史帖、网络关系和代表性证据的 hateful/abusive user 数据。
6. 项目域 KT3 gold/control set：从 MediaCrawler 和系统上游输出中抽样，人工标注帖子级、用户级、社区级三层标签。
7. 证据库与 RAG 索引：fact-check claim corpus、新闻证据、DISARM technique KB、历史事件案例库和向量索引。
8. 媒体二进制和对齐文件：真实图像、视频、关键帧、OCR、ASR、caption 与 post_id 的稳定映射。

因此，当前本地可以开始做 schema、采样、弱标注、HateXplain/PHEME/MCFEND/IOHunter 适配和 smoke training；但不能声称已经具备训练完整 KT3 帖子级多模态 harmfulness、用户级 MIL 或社区级 collective harm 模型所需的完整 gold 数据。

### 9.1 缺失数据下载入口

| 优先级 | 缺失资源 | 建议入口 | 备注 |
|---|---|---|---|
| P0 | HateXplain | [official GitHub](https://github.com/hate-alert/HateXplain)、[AAAI paper](https://ojs.aaai.org/index.php/AAAI/article/view/17745) | 已完成本地 clone/转换/评测；下一步训练 target/rationale head |
| P0 | Jigsaw Toxicity | [Kaggle competition](https://www.kaggle.com/competitions/jigsaw-toxic-comment-classification-challenge/data) | 需要 Kaggle token；用于文本 toxicity 预训练/校准 |
| P0 | Hateful Memes | [Meta page](https://ai.meta.com/tools/hatefulmemes/)、[DrivenData data page](https://www.drivendata.org/competitions/64/hateful-memes/page/205/) | 需要遵守 challenge/data access 条款 |
| P0 | MOCHEG | [GitHub](https://github.com/VT-NLP/Mocheg)、[request form](https://docs.google.com/forms/d/e/1FAIpQLScAGehM6X9ARZWW3Fgt7fWMhc_Cec6iiAAN4Rn1BHAk6KOfbw/viewform?usp=sf_link)、[SIGIR paper](https://dl.acm.org/doi/10.1145/3539618.3591879) | 已 clone implementation；还需通过表单获取 MOCHEG v1 数据 |
| P0 | FakeSV | [GitHub](https://github.com/ICTMCG/FakeSV)、[HF features/checkpoints](https://huggingface.co/datasets/MischaQI/FakeSV)、[AAAI paper](https://ojs.aaai.org/index.php/AAAI/article/view/26689) | 已完成公开 metadata/text proxy 与 C3D 预提取视频特征 baseline；下一步补 raw video、VGG19/VGGish/audio、ASR/OCR、评论和发布者上下文 |
| P1 | RumourEval 2019 | [Figshare](https://figshare.com/articles/dataset/RumourEval_2019_data/8845580)、[baseline GitHub](https://github.com/kochkinaelena/RumourEval2019) | 补齐 PHEME 之外的 stance/veracity benchmark |
| P1 | FEVER / HoVer / AVeriTeC | [FEVER GitHub](https://github.com/awslabs/fever)、[HoVer GitHub](https://github.com/hover-nlp/hover)、[AVeriTeC GitHub](https://github.com/MichSchli/AVeriTeC) | 构建 claim-evidence 检索和 verification 训练集 |
| P1 | FACTIFY3M | [EMNLP paper](https://aclanthology.org/2023.emnlp-main.945/)、[arXiv](https://arxiv.org/abs/2306.05523) | 原 registry GitHub 不可访问；需通过论文/作者或官方 release 获取数据，older Factify baseline repo 不含数据 |
| P1 | MuMiN | [website](https://mumin-dataset.github.io/)、[mumin-build](https://github.com/MuMiN-dataset/mumin-build) | post-user-community 异构图统一数据 |
| P1 | MMHS150K / MAMI / MultiOFF | [MMHS project](https://gombru.github.io/2019/10/09/MMHS/)、[MMHS Kaggle mirror](https://www.kaggle.com/datasets/victorcallejasf/multimodal-hate-speech)、[MAMI GitHub](https://github.com/MIND-Lab/SemEval2022-Task-5-Multimedia-Automatic-Misogyny-Identification-MAMI-)、[MultiOFF Zenodo](https://zenodo.org/records/3899868) | 扩展图文 hate/offensive/targeted harm；MMHS150K 需 Kaggle/Twitter media 条款 |
| P2 | Hateful Users Twitter | [paper](https://ojs.aaai.org/index.php/ICWSM/article/view/15057)、[GitHub](https://github.com/manoelhortaribeiro/HatefulUsersTwitter) | 平台政策导致原始推文可能需 rehydrate |
| P2 | DISARM KB | [DISARM Foundation](https://www.disarm.foundation/framework)、[GitHub](https://github.com/DISARMFoundation/DISARMframeworks/) | RAG/Agent 的 technique ontology，不是训练集 |
| P2 | KT3 project gold/control set | `G:\CISCN\dataset\kt3_project_gold\` | 从 MediaCrawler 和系统上游输出抽样，人审构建，必须冻结 split/leakage/label policy |

## 10. 推荐的最小可训练里程碑

第一阶段建议不要追求一次性全量训练，而是做一个最小可复现训练闭环：

| 里程碑 | 数据 | 产物 | 验收 |
|---|---|---|---|
| M1 文本帖子级 | HateXplain + PHEME + MCFEND | text/claim-conditioned post student | harm macro-F1、stance macro-F1、abstain calibration |
| M2 图文帖子级 | Hateful Memes + MOCHEG/FACTIFY + 项目 OCR 样本 | image/text/OCR multimodal student | multimodal AUROC、evidence recall、cross-modal conflict review |
| M3 短视频帖子级 | FakeSV + MediaCrawler 视频样本 | keyframe/OCR/ASR/video-context model | fake/harm F1、ASR/OCR ablation、中文域外泛化 |
| M4 用户级 MIL | PHEME/MCFEND/MediaCrawler post bags + 人审账户标签 | trainable Attention-MIL user model | user AUC/F1、representative post precision、time-split |
| M5 社区级图 | IOHunter/twitter_io/russian troll + 项目社区 gold | HGT/Graph Transformer community model | community F1、role F1、control false positive |
| M6 Agent/RAG 闭环 | 三层模型输出 + evidence KB + review logs | reviewer/retriever/verifier provider | 低置信样本召回、人工审核一致性、失败回退 |

M1 到 M3 解决帖子级语义底座，M4 才训练用户级 MIL，M5 再训练社区级图模型。这个顺序能避免用户级和社区级模型学习到帖子级规则噪声，也便于做 ablation。

## 11. 下一步工程任务

建议新增以下工程任务：

1. 新建 `G:\CISCN\dataset\kt3_public\` 和 `G:\CISCN\dataset\kt3_project_gold\`，只保存数据和 manifest，不写入 Git。
2. 在仓库新增 `scripts/kt3_data_audit.py`，扫描本地数据并生成 dataset manifest，不读取敏感 payload 到普通报告。
3. 在 `aris/tech-03-risk` 补 `KT3_DATASET_MANIFEST_SCHEMA.md`，固定字段：dataset_id、source、license、split、label_policy、modalities、leakage_policy、media_paths、checksum。
4. 从 MediaCrawler 样本构造第一版 `kt3_project_gold_v0`，至少包含 post_cases、user_gold、community_gold 和 control set。
5. 先训练 text-only post student，作为所有后续 MIL/graph 模型的冻结底座。
6. 再逐步接入 image/video encoder、用户级 MIL、社区级 HGT 和 Agent/RAG provider。

## 12. 结论

KT3 当前已经完成了三层 harmfulness characterization 的运行时契约，但还没有完成训练式模型。下一步最关键的不是继续加规则，而是补齐数据：公开 benchmark 用于方法对齐和可比性，项目域 gold/control set 用于真实验收，媒体二进制和证据库用于真正多模态和 RAG。只有当这些数据进入 manifest，并且 split、leakage policy、label policy 和 control set 冻结后，KT3 才能从当前 scaffold 稳定推进到可训练、可复现、可答辩的模型体系。
