# KT3 帖子级统一检测模型与全量验证协议

## 1. 目标

本文档聚焦 KT3 帖子级 harmfulness detection。目标是基于高水平文献设计一个统一的帖子级检测模型，覆盖 `tweet / meme / img / video` 四类帖子视图，并定义可在公开数据集和项目数据集上执行的全量验证协议。

当前必须区分三种状态：

- `Current scaffold`：`post_semantics.py` 已经实现 text、OCR、ASR、caption/media、emoji/hashtag 的归一化 late fusion，但不是训练式多模态模型。
- `Trainable target`：本文定义的统一帖子级模型，是后续要训练和验证的目标架构。
- `Full validation`：只有当每个指定 benchmark 本地可用、split 固定、模型完成训练/评测并输出指标表时才算完成。当前本地数据尚不完整，因此全量验证尚未完成。

## 2. 文献证据与方法启发

帖子级 harmfulness 不是单一文本分类问题。相关领域的高水平工作给出四个共同结论：

| 方向 | 代表文献 | 对 KT3 的启发 |
|---|---|---|
| 图文 meme harmfulness | [Hateful Memes](https://ai.meta.com/tools/hatefulmemes/)、[MultiOFF, TRAC 2020](https://aclanthology.org/2020.trac-1.6/)、[MAMI, SemEval 2022](https://aclanthology.org/2022.semeval-1.74/) | meme 的 harmfulness 常来自图文组合、反讽和隐式语义，必须同时判断 text、image、OCR 和图文关系。 |
| 文本 harmfulness 与 rationale | [HateXplain, AAAI 2021](https://ojs.aaai.org/index.php/AAAI/article/view/17745)、[Jigsaw Toxicity](https://www.kaggle.com/competitions/jigsaw-toxic-comment-classification-challenge) | 输出不能只有 label，还应保留 target、rationale、uncertainty，便于后续用户级聚合和人工复核。 |
| Claim-conditioned misinformation/fact-checking | [MOCHEG, SIGIR 2023](https://github.com/VT-NLP/Mocheg)、[FACTIFY3M, EMNLP 2023](https://aclanthology.org/2023.emnlp-main.945/)、[MuMiN, SIGIR 2022](https://mumin-dataset.github.io/) | misinformation 型 harm 必须围绕 claim 和 evidence 判断，模型需要 claim retrieval、stance/veracity 和 evidence explanation。 |
| 短视频 fake/harmful news | [FakeSV, AAAI 2023](https://ojs.aaai.org/index.php/AAAI/article/view/26689) | video 不应直接假设端到端视频模型可用，最低路线是 keyframe + OCR + ASR + comment + publisher/social context。 |
| 通用视觉语言表示 | [CLIP, ICML 2021](https://proceedings.mlr.press/v139/radford21a.html)、[BLIP-2, ICML 2023](https://proceedings.mlr.press/v202/li23q.html) | 图像和 meme 视图可先用冻结视觉语言 encoder，再训练轻量适配头和融合层，降低数据与算力需求。 |

这些文献支撑 KT3 采用“多视图检测器 + 可解释融合”的模型，而不是把所有字段拼成一个手工特征表。

### 2.1 高水平文献到 KT3 方法模块的映射

| KT3 模块 | 主要参考 | 可迁移的方法思想 | 在 `MV-PostGuard` 中的落点 |
|---|---|---|---|
| `D_tweet` 文本 harmfulness | [HateXplain, AAAI 2021](https://ojs.aaai.org/index.php/AAAI/article/view/17745)、[Jigsaw Toxicity](https://www.kaggle.com/competitions/jigsaw-toxic-comment-classification-challenge) | label 不足以支撑可审计判断，应同时建模 target、rationale、bias/faithfulness 与 calibration | 文本视图输出 `label + harm_types + target/evidence/rationale + confidence`，为用户级 MIL 提供可聚合证据 |
| `D_meme / D_img` 图文 harmfulness | [Hateful Memes, NeurIPS 2020](https://proceedings.neurips.cc/paper/2020/hash/1b84c4cee2b8b3d823b30e2d604b1878-Abstract.html)、[MultiOFF, TRAC 2020](https://aclanthology.org/2020.trac-1.6/)、[MAMI, SemEval 2022](https://aclanthology.org/2022.semeval-1.74/) | 图文 harmfulness 往往来自跨模态组合，单独文本或单独图片会被 benign confounder、反讽和隐式目标误导 | 每个图文样本必须保留 `text-only / image-only / fusion` ablation，不能把 OCR 或 URL metadata 冒充视觉理解 |
| 视觉语言表示层 | [CLIP, ICML 2021](https://proceedings.mlr.press/v139/radford21a.html)、[BLIP-2, ICML 2023](https://proceedings.mlr.press/v202/li23q.html) | 先冻结强视觉语言 encoder，再训练轻量分类头/adapter/gating，可在数据有限时获得可迁移图像表示 | 当前 MultiOFF `image_only` 已采用 frozen CLIP；后续扩展 BLIP-2 caption/rationale teacher 与 learned fusion |
| claim-conditioned misinformation | [RumourEval 2019, SemEval](https://aclanthology.org/S19-2147/)、[MOCHEG, SIGIR 2023](https://github.com/VT-NLP/Mocheg)、[FACTIFY3M, EMNLP 2023](https://aclanthology.org/2023.emnlp-main.945/) | 谣言/事实核验必须先定位 claim，再判断 stance/veracity，并给出 retrieved evidence 与 explanation | `ClaimRetriever + ClaimReranker + EvidenceEncoder + StanceHead`，输出 `primary_claim / stance / evidence`，与 harmfulness 联合判断 |
| `D_video` 短视频视图 | [FakeSV, AAAI 2023](https://ojs.aaai.org/index.php/AAAI/article/view/26689) | 短视频不能只看标题或文本；最低路线是 keyframe/OCR/ASR/comment/publisher/social context 的多模态选择与融合 | 当前已接入 FakeSV 公开 metadata/text proxy，并新增 public C3D 预提取视频特征 baseline；仍不是 raw-video 端到端 encoder |
| Agent reviewer / decision optimizer | [MARO, EMNLP 2025](https://aclanthology.org/2025.emnlp-main.291/) | 多专家 Agent 可以做跨域分析、question-reflection 和 decision rule optimization，但不应替代底层可训练检测器 | KT3 Agent 层用于复核冲突、优化融合规则、回流难例和生成反制叙事；底层判断仍来自四视图检测器与校准融合 |

### 2.2 文献到方法论的进一步归纳

这些工作给 KT3 的统一方法论提供了四条约束，而不只是“参考数据集”：

1. Hateful Memes、MultiOFF、MAMI、MMHS150K 共同说明，图文 harmfulness 的难点来自跨模态组合、反讽和单模态 shortcut。因此 `D_meme / D_img` 必须报告 text-only、image-only、majority vote、weighted fusion、learned fusion 的 ablation，不能只给一个融合后分数。
2. HateXplain 说明文本 harmfulness 不能只做二分类，还要保留 target、rationale 和可审计证据。KT3 的 `D_tweet` 因此要输出 `harm_types / evidence / confidence`，供用户级 MIL 聚合。
3. MOCHEG 与 FACTIFY3M 说明 misinformation 型 harm 必须是 claim/evidence-conditioned：要有 claim retrieval、evidence selection、stance/veracity 和 explanation/5W QA，而不是把“像谣言的文本”直接判 harmful。
4. FakeSV 说明短视频检测不能用视频 URL 或标题冒充视频理解；最低可用路线应是 keyframe、OCR、ASR、comment、publisher/social context 的多视图融合。
5. MARO 说明 Multi-Agent 的强项在跨域分析、question-reflection 和 decision-rule optimization。KT3 应把 Agent 放在 reviewer/rule optimizer/teacher 位置，而不是让 Agent 取代底层四视图 detector。

## 3. 统一模型：MV-PostGuard

本文建议把 KT3 帖子级统一模型命名为 `MV-PostGuard`，即 Multi-View Post-level Guard。它由四类视图检测器、claim/evidence 条件模块和融合裁决层组成。

### 3.1 输入形式化

单条帖子 `p` 表示为：

`p = (x_tweet, x_meme, x_img, x_video, c, m)`

其中：

- `x_tweet`：正文、hashtags、emoji、reply/repost/comment text、用户可见文本上下文。
- `x_meme`：图文 meme 对象，包括图像、图中文字、caption 和 meme-level OCR。
- `x_img`：普通图片、OCR、caption/alt text、视觉区域。
- `x_video`：视频关键帧、封面、OCR、ASR、字幕、标题、评论摘要。
- `c`：claim candidates、retrieved evidence、fact-check context。
- `m`：平台、时间、事件、语言、数据集来源、媒体可用性等元信息。

不是每条帖子都包含所有视图，因此每个视图有可用性变量 `a_v in {0,1}`。

### 3.2 四类视图检测器

| 检测器 | 输入 | 编码器 | 输出 |
|---|---|---|---|
| `D_tweet` | `x_tweet, c` | text encoder + claim cross-encoder | `y_tweet, q_tweet, e_tweet, h_tweet, stance_tweet` |
| `D_meme` | `x_meme, c` | image-text encoder + OCR/rationale head | `y_meme, q_meme, e_meme, h_meme` |
| `D_img` | `x_img, c` | CLIP/BLIP-style image-text encoder + OCR head | `y_img, q_img, e_img, h_img` |
| `D_video` | `x_video, c` | keyframe encoder + OCR/ASR/text encoder + temporal pooling | `y_video, q_video, e_video, h_video` |

输出含义：

- `y_v`：视图级标签，取 `harmful / non_harmful / uncertain`。
- `q_v`：校准后的 harmful probability 或 confidence。
- `e_v`：视图级证据，例如文本 span、OCR/ASR 片段、图像区域、关键帧或检索证据。
- `h_v`：harm type 分布。
- `stance_v`：仅对 claim-conditioned 文本/视频/图文场景输出 stance。

### 3.3 Claim/Evidence 条件模块

对 misinformation/disinformation 型 harm，模型不能只判断内容是否“像谣言”，而应加入 claim-conditioned reasoning：

1. `ClaimRetriever` 从同事件 claim pool、fact-check corpus、历史帖子和外部证据库中取 top-k claim candidates。
2. `ClaimReranker` 对 `(post, claim)` 进行 cross-encoder scoring，得到 primary claim 或 `unlinked`。
3. `EvidenceEncoder` 编码 retrieved evidence、MOCHEG/FACTIFY 风格的 text/image evidence 和 5W QA。
4. `StanceHead` 输出 support、deny、query、neutral、uncertain。

这部分使 KT3 能覆盖两类 harm：一类是无需外部 claim 即可判断的 hate/harassment/offensive，另一类是必须依赖 claim/evidence 的 misinformation。

### 3.4 融合与多数投票

最低可用工程版采用多数投票，但投票对象必须先经过 Effective View 筛选。也就是说，只有 `available=true`、`abstain=false` 且输出了明确二分类标签的视图可以进入帖子级裁决；缺少可解码媒体内容的 `img / video / meme` 视图不能被当作 `non_harmful` 票。

`I_v = 1[a_v = 1 and abstain_v = false and y_v in {harmful, non_harmful}]`

`N_eff = sum_v I_v`

`V_h = sum_v I_v * 1[y_v = harmful]`

`V_n = sum_v I_v * 1[y_v = non_harmful]`

若 `V_h > N_eff / 2`，输出 `harmful`；若 `V_n > N_eff / 2`，输出 `non_harmful`；否则输出 `uncertain`。当 `N_eff = 0` 时，必须输出 `uncertain` 并进入复核。

训练式版本采用加权 late fusion，同样只融合 Effective View：

`s_p = sum_v I_v * alpha_v * q_v * s_v / sum_v I_v * alpha_v * q_v`

其中 `alpha_v` 可由验证集可靠性初始化，也可由 gating network 学习：

`alpha_v = G(z_v, modality_quality_v, dataset_id, language, claim_grounded)`

最终裁决：

- `s_p >= tau_h`：`harmful`
- `s_p <= tau_n`：`non_harmful`
- `tau_n < s_p < tau_h`：`uncertain`

如果存在跨视图冲突，例如文本否认 claim 但图像支持 claim、ASR 与 caption 相反、meme 反讽强烈，则即使 `s_p` 较高也应附加 `review_reason = cross_view_conflict`。

### 3.4.1 当前形式化：四视图 detect -> vote/fusion -> post judgment

根据最新 KT3 帖子级研判口径，单条 post 不再被视为一串拼接后的手工特征，而是被拆成四个可独立判定的 Post View：

`V(p) = {v_tweet, v_meme, v_img, v_video}`

每个视图由同构检测器执行：

`D_v(v, c) -> r_v = (a_v, y_v, s_v, q_v, h_v, e_v, abstain_v)`

字段含义如下：

| 字段 | 含义 | 当前能力边界 |
|---|---|---|
| `a_v` | 视图是否存在可解码证据 | 当前由正文、OCR、ASR、caption、media 类型判断；媒体 URL 本身不等于图像/视频已理解 |
| `y_v` | `harmful / non_harmful / uncertain` | 当前为语义原型 scaffold；目标是训练式 view detector |
| `s_v` | harmful score | 当前为 representation/lexical fallback score；目标是校准概率 |
| `q_v` | confidence | 当前由 harmful-vs-benign margin 估计；目标是 validation calibration |
| `h_v` | harm type distribution | 当前覆盖 misinformation、hate/harassment、smear、mobilization、amplification |
| `e_v` | view-level evidence | 当前返回文本 span、OCR/ASR/caption 摘要；目标扩展到图像区域、视频帧、检索证据 |
| `abstain_v` | 是否弃权 | 缺少可解码图像/视频内容时必须弃权，不能当作 non-harmful |

四个检测器的职责固定为：

| Detector | View | 需要回答的问题 | 当前代码映射 |
|---|---|---|---|
| `D_tweet` | tweet | 正文、hashtag、emoji、claim context 是否 harmful，以及对 claim 的 stance | `post_semantics.py::_infer_post_view_detection` 中 `tweet` |
| `D_meme` | meme | 图文组合是否形成 offensive/hateful/misleading meme | `post_semantics.py::_infer_post_view_detection` 中 `meme` |
| `D_img` | img | 图片/OCR/caption 是否携带 harmful 证据 | `post_semantics.py::_infer_post_view_detection` 中 `img` |
| `D_video` | video | keyframe/OCR/ASR/title/caption 是否携带 harmful 证据 | `post_semantics.py::_infer_post_view_detection` 中 `video` |

多数投票只统计 `available=true` 且 `abstain=false` 的视图。这里的 `available` 必须表示该视图存在可解码证据，而不是仅存在媒体 URL；例如只有 `.mp4` 链接但没有 ASR/OCR/caption 时，`D_video` 必须弃权，不能把 tweet 正文重复当作 video 证据：

`N_eff = sum_v 1[a_v = 1 and abstain_v = false]`

`Vote_h = sum_v 1[a_v = 1 and abstain_v = false and y_v = harmful]`

`Vote_n = sum_v 1[a_v = 1 and abstain_v = false and y_v = non_harmful]`

若 `Vote_h > N_eff / 2`，输出 `harmful`；若 `Vote_n > N_eff / 2`，输出 `non_harmful`；否则输出 `uncertain`。这条规则的核心不是追求最高性能，而是形成可解释、可审计的最低工程闭环。

加权融合用于处理视图可靠性差异，并同样只允许非弃权视图进入融合：

`s_post = sum_v 1[a_v = 1 and abstain_v = false] * w_v * q_v * s_v / sum_v 1[a_v = 1 and abstain_v = false] * w_v * q_v`

其中 `w_v` 是视图先验可靠性，`q_v` 是当前样本的 detector confidence。训练式目标中，`w_v` 和阈值应由 validation set 学习/校准；当前 runtime scaffold 采用固定先验权重，仅用于可解释推理和后续评测接口打通。

最终裁决优先级为：

1. 若 `majority_vote` 与 `weighted_fusion` 给出同一非 uncertain 标签，则采用 `majority_vote_confirmed_by_weighted_fusion`。
2. 若多数投票给出非 uncertain 标签但加权融合 uncertain，则采用 `majority_vote`，并保留复核理由。
3. 若多数投票 uncertain，则采用 `weighted_fusion_fallback`；若仍 uncertain，进入人工/Agent 复核队列。

当前代码已在 `system/backend/app/core/risk/post_semantics.py` 新增 `post_view_detection` 输出，结构包括：

- `view_results`: `tweet / meme / img / video` 四视图检测结果。
- `fusion.majority_vote`: 多数投票标签、投票计数、有效视图、弃权视图。
- `fusion.weighted_fusion`: 加权融合标签、harm score、贡献视图；贡献视图必须排除 `abstain=true` 的 `img/video`。
- `fusion_policy`: 最终采用的融合策略。
- `final_harmfulness`: 帖子级最终 `harmful / non_harmful / uncertain`。
- `conflict`: 跨视图 label conflict 或 score divergence。
- `review_reason`: 进入复核队列的原因，例如 view unavailable、media without decodable content、fusion uncertain。

需要特别强调：当前实现已经完成“四视图 detect + 多数投票/融合”的运行时 scaffold 和输出契约，但 `D_img / D_video` 尚未接入真正的图像编码器、视频编码器或训练好的多模态模型。因此它是可解释接口闭环，不是完整 `MV-PostGuard` 训练完成。当前 runtime 的严格边界是：`tweet` 可使用正文/hashtag/emoji；`meme` 可使用正文+OCR/caption；`img` 必须依赖 OCR/caption 等图像可解码文本；`video` 必须依赖 ASR/OCR/caption 等视频可解码文本。

### 3.5 输出契约

统一模型必须输出：

```json
{
  "final_harmfulness": "harmful | non_harmful | uncertain",
  "harm_score": 0.0,
  "harm_types": ["misinformation", "hate_or_harassment"],
  "primary_claim": {"claim_id": "...", "score": 0.0},
  "stance": {"label": "support | deny | query | neutral | uncertain | unlinked"},
  "view_results": {
    "tweet": {"available": true, "label": "harmful", "score": 0.0, "evidence": []},
    "meme": {"available": false, "label": "uncertain", "score": 0.0, "evidence": []},
    "img": {"available": true, "label": "non_harmful", "score": 0.0, "evidence": []},
    "video": {"available": false, "label": "uncertain", "score": 0.0, "evidence": []}
  },
  "fusion_policy": "majority_vote | weighted_vote | learned_late_fusion",
  "conflict": {"has_conflict": false, "type": null},
  "review_reason": []
}
```

## 4. 训练目标

训练采用多任务目标：

| 任务 | 标签 | 损失 |
|---|---|---|
| harmfulness | harmful / non-harmful / uncertain | class-balanced cross entropy / focal loss |
| harm type | misinformation、hate、offensive、harassment、incitement 等 | multi-label BCE |
| claim link | post-claim pair | contrastive loss / pairwise ranking |
| stance | support、deny、query、neutral、unlinked | cross entropy |
| evidence/rationale | span、OCR/ASR、region、frame、retrieved evidence | rationale alignment / retrieval loss |
| fusion reliability | view-level correctness、modality quality | gating calibration loss |
| abstention | uncertain、human-review cases | selective classification / coverage-risk loss |

关键训练原则：

- 先训练 `D_tweet` 和 `D_meme/D_img`，再训练 `D_video`，最后训练 fusion/gating。
- 能力不足或数据缺失的视图不能伪造 label，必须以 `available=false` 和 `uncertain` 进入融合。
- Teacher/LLM 标签只能作为弱监督，不可直接等同 gold。
- 所有指标必须按 dataset、harm type、modality availability 和 language 分组报告。

## 5. 全量验证数据集矩阵

| 数据集 | 视图 | 任务 | 指标 | 当前本地状态 |
|---|---|---|---|---|
| HateXplain | tweet/text | harmfulness、target、rationale | macro-F1、rationale F1、target F1 | ready：本地 `G:\CISCN\dataset\kt3_public\HateXplain`，已转换 20148 条 |
| Jigsaw Toxicity | tweet/text | toxicity | macro-F1、AUROC、ECE | 缺少 |
| MultiOFF | meme/img/text | offensive meme | macro-F1、image-missing rate、fusion ablation | partial：本地有 743 条 split 样本，缺 3 个图片引用 |
| Hateful Memes | meme/img/text | hateful meme | AUROC、accuracy、text/image/fusion ablation | 缺少 |
| MAMI | meme/img/text | misogyny + subtype | macro-F1、subtype F1 | 缺少 |
| MMHS150K | img/text | multimodal hate speech | macro-F1、AUROC | 缺少 |
| PHEME | tweet/thread | rumour/non-rumour、veracity | macro-F1、event split F1 | ready |
| RumourEval 2019 | tweet/thread | stance + veracity | stance macro-F1、veracity macro-F1 | present_unverified：baseline repo 已 clone，CodaLab 原始数据缺失 |
| MOCHEG | img/text/evidence | fact-checking + explanation | veracity F1、evidence recall、explanation metrics | present_unverified：official implementation 已 clone，MOCHEG v1 数据需 Google Form |
| FACTIFY3M | img/text/evidence | multimodal fact verification | F1、5W QA explanation | 缺少 |
| FakeSV | video/tweet/social | short-video fake news | F1、modality ablation | ready：公开 `data.json`、temporal split 与 C3D 预提取特征已可用；raw video、VGG19/VGGish/audio/评论/发布者上下文仍缺 |
| Fakeddit | img/text | multimodal fake news | accuracy、macro-F1 | present_unverified：downloader repo 已 clone，v2.0 TSV 与 image data 需 Google Drive/CodaLab |
| MuMiN | tweet/img/graph | misinformation tweet/claim | graph split F1、tweet classification | 缺少 |
| MCFEND | Chinese text/img/social | fake news | macro-F1、domain split F1 | ready |
| Twitter15/16 | tweet/thread | rumour event classification | macro-F1、event split F1 | ready |

## 6. 全量验证协议

全量验证必须按以下阶段执行：

1. `Dataset Readiness Audit`：检查数据是否存在、split 是否固定、label 字段是否可读、媒体是否能对齐。
2. `Schema Normalization`：将所有 benchmark 转成统一 `kt3_post_case` schema。
3. `Model Training`：按 text-only、image/text、video/social、claim/evidence 四组训练视图检测器。
4. `Fusion Training`：在 validation split 上学习或校准 `alpha_v` 和阈值 `tau_h / tau_n`。
5. `Full Evaluation`：在每个 benchmark 的 test split 上输出 per-dataset 指标。
6. `Ablation`：报告 `tweet-only`、`img-only`、`meme-only`、`video-only`、`majority_vote`、`weighted_vote`、`learned_fusion`。
7. `Error Analysis`：按 missing modality、cross-view conflict、claim unlinked、low confidence、language/domain 分组。

不能把单一 smoke test、单数据集结果或 runtime scaffold 输出写成“全量验证完成”。

## 7. 当前本地数据 readiness 审计

已新增机器可读 benchmark registry：

`G:\CISCN\CogGuard\system\backend\app\core\risk\config\kt3_post_benchmarks.json`

该 registry 记录每个 benchmark 的任务、视图、优先级、论文链接、数据链接、仓库链接、获取方式、是否需要媒体二进制和验证用途。审计脚本现在读取该 registry，因此“缺哪些数据、如何获取、是否需要申请”可以直接机器化输出。

只读审计命令：

```powershell
python G:\CISCN\CogGuard\system\backend\scripts\audit_kt3_post_datasets.py `
  --dataset-root G:\CISCN\dataset `
  --output G:\CISCN\.tmp\kt3_post_dataset_audit_v2.json
```

当前 registry-driven 审计结果：

| 状态 | 数据集 |
|---|---|
| ready | HateXplain、PHEME、Twitter15_16_dataset、mcfend |
| partial | MultiOFF |
| present_unverified | RumourEval 2019、MOCHEG、Fakeddit |
| missing | Jigsaw Toxicity、Hateful Memes、MMHS150K、MAMI、FACTIFY3M、MuMiN |

P0 缺口按获取动作划分：

| 获取动作 | P0 数据集 | 链接 |
|---|---|---|
| local conversion / validation | HateXplain | [HateXplain](https://github.com/hate-alert/HateXplain)，本地路径 `G:\CISCN\dataset\kt3_public\HateXplain` |
| local conversion / validation | FakeSV | [FakeSV](https://github.com/ICTMCG/FakeSV)，本地路径 `G:\CISCN\dataset\kt3_public\FakeSV`；公开部分已可做 video-id/keyword proxy，raw video/features 仍需协议或 HuggingFace 外部资源 |
| manual/contact required | FACTIFY3M | [FACTIFY3M paper](https://aclanthology.org/2023.emnlp-main.945/)；原 registry GitHub 不可访问，需通过论文/作者或官方 release 获取数据 |
| accept terms then download | Jigsaw Toxicity、MAMI、MMHS150K | [Jigsaw Toxicity](https://www.kaggle.com/competitions/jigsaw-toxic-comment-classification-challenge/data)、[MAMI / SemEval 2022 Task 5](https://competitions.codalab.org/competitions/34175)、[MMHS150K Kaggle mirror](https://www.kaggle.com/datasets/victorcallejasf/multimodal-hate-speech) |
| code cloned but data gated | RumourEval 2019、MOCHEG | [RumourEval baseline repo](https://github.com/kochkinaelena/RumourEval2019) 已 clone，但原始数据需 [CodaLab](https://competitions.codalab.org/competitions/19938)；[MOCHEG repo](https://github.com/VT-NLP/Mocheg) 已 clone，但 MOCHEG v1 数据需 [Google Form](https://docs.google.com/forms/d/e/1FAIpQLScAGehM6X9ARZWW3Fgt7fWMhc_Cec6iiAAN4Rn1BHAk6KOfbw/viewform?usp=sf_link) |
| request access then download | Hateful Memes | [Hateful Memes](https://ai.meta.com/tools/hatefulmemes/) |

`MultiOFF` 当前 partial 的原因是 split CSV 中有 3 条图片引用未在 `Labelled Images` 中找到，代表性缺失文件为 `80NRcEf.png`。这不阻止 text-only 或剔除缺失媒体后的实验，但不能称为完整图文全量验证。

审计报告位置：

`G:\CISCN\.tmp\kt3_post_dataset_audit_v2.json`

## 8. 下一步落地任务

### 8.1 已完成的数据标准化入口

已新增统一转换脚本：

```powershell
python G:\CISCN\CogGuard\system\backend\scripts\build_kt3_post_cases.py `
  --dataset-root G:\CISCN\dataset `
  --output-dir G:\CISCN\.tmp\kt3_post_cases_full
```

转换输出采用 `kt3-post-case-v1` JSONL schema，字段包括 `case_id / dataset / split / source_id / text / labels / views / claim_context / metadata`。该 schema 是后续训练和评测 `MV-PostGuard` 的统一输入，不代表模型已经训练。

当前已完成本地全量转换：

| 数据集 | 输出 | case 数 | 状态 | 说明 |
|---|---|---:|---|---|
| MultiOFF | `G:\CISCN\.tmp\kt3_post_cases_full\MultiOFF.jsonl` | 743 | partial | 740 条有图文视图，3 条缺图片引用 |
| HateXplain | `G:\CISCN\.tmp\kt3_post_cases_full\HateXplain.jsonl` | 20148 | converted | official train/val/test split，包含 text harm、target、rationale 监督；unassigned 样本不进入 suite 训练/测试 |
| PHEME | `G:\CISCN\.tmp\kt3_post_cases_full\PHEME.jsonl` | 6425 | converted | tweet 正文、rumour/veracity、claim category 已转入统一格式 |
| MCFEND | `G:\CISCN\.tmp\kt3_post_cases_full\mcfend.jsonl` | 23974 | converted | 中文 fake news title/content、label、claim context 已转入统一格式 |
| Twitter15/16 | `G:\CISCN\.tmp\kt3_post_cases_full\Twitter15_16_dataset.jsonl` | 2308 | partial | 本地副本缺 `source_tweets.txt`，只有 label/tree，不能直接用于文本模型训练 |

manifest 位置：

`G:\CISCN\.tmp\kt3_post_cases_full\manifest.json`

当前总计 `59093` 条统一 case，其中 `HateXplain`、`PHEME`、`MCFEND` 和 `FakeSV` 可直接用于 text/claim-conditioned 或 short-video metadata/text proxy 训练评测，`MultiOFF` 可用于 meme/img 训练但需处理 3 条缺失图片，`Twitter15/16` 只能作为传播结构或标签占位，不能作为内容检测训练数据。

### 8.2 已完成的 text-only baseline

已新增 text-only baseline 脚本：

```powershell
python G:\CISCN\CogGuard\system\backend\scripts\run_kt3_post_text_baseline.py `
  --case-dir G:\CISCN\.tmp\kt3_post_cases_full `
  --output-dir G:\CISCN\.tmp\kt3_post_text_baseline
```

该脚本使用 `TF-IDF(char n-gram) + Logistic Regression`，只读取 `kt3-post-case-v1.text` 和 `labels.harmfulness`，因此是 `tweet/text-only` 对照实验，不是完整的 `MV-PostGuard` 多视图模型。

当前本地 baseline 结果：

| 数据集 | split policy | train/test | Accuracy | Macro-F1 | 说明 |
|---|---|---:|---:|---:|---|
| MultiOFF | official train+validation -> test | 594 / 149 | 0.644295 | 0.619550 | 只用 meme OCR/text，不使用图片 encoder |
| PHEME | event holdout: sydneysiege + ottawashooting | 4314 / 2111 | 0.751303 | 0.591633 | harmful 类 F1 仅 0.336283，说明 text-only 事件泛化较弱 |
| MCFEND | stratified random 80/20 | 19179 / 4795 | 0.864442 | 0.820079 | 中文 fake news 文本基线较强，但仍未使用图像/社交上下文 |

报告位置：

`G:\CISCN\.tmp\kt3_post_text_baseline\report.json`

预测输出：

- `G:\CISCN\.tmp\kt3_post_text_baseline\MultiOFF_predictions.jsonl`
- `G:\CISCN\.tmp\kt3_post_text_baseline\PHEME_predictions.jsonl`
- `G:\CISCN\.tmp\kt3_post_text_baseline\mcfend_predictions.jsonl`

该结果证明统一 schema 上的训练/评测管线已经跑通，但不能被写成全量多模态验证。它的正确定位是 `D_tweet` 的 baseline，以及后续 `D_meme / D_img / D_video / claim-evidence` 模块的对照组。

### 8.3 已完成的 MultiOFF text/image/fusion ablation

已新增 MultiOFF 多视图 ablation 脚本：

```powershell
python G:\CISCN\CogGuard\system\backend\scripts\run_kt3_multioff_multiview_ablation.py `
  --case-dir G:\CISCN\.tmp\kt3_post_cases_full `
  --output-dir G:\CISCN\.tmp\kt3_multioff_multiview_ablation_hf_safe `
  --hf-endpoint https://huggingface.co
```

该脚本按照 MultiOFF 与 Hateful Memes 的图文 meme 检测范式，分别报告 `text_only`、`image_only` 与 `late_fusion`。其中 `image_only` 使用冻结 `openai/clip-vit-base-patch32` 图像 encoder + Logistic Regression；`late_fusion` 在 validation split 上网格搜索 text/image probability 权重，再在 test split 上评估。脚本显式禁止用浅层图片元数据替代图像 encoder：如果 CLIP 权重不可用，`image_only` 和 `late_fusion` 会被标记为 skipped。

当前可复现结果：

| 实验 | 训练/验证/测试 | Test Accuracy | Test Macro-F1 | 说明 |
|---|---:|---:|---:|---|
| `text_only` | 445 / 149 / 149 | 0.597315 | 0.573799 | 只用 meme OCR/text 作为 `D_tweet` 对照 |
| `image_only` | 443 / 148 / 148 | 0.621622 | 0.617147 | 使用冻结 CLIP 图像表示训练 `D_img` |
| `late_fusion` | validation 调权，test 评估 | 0.628378 | 0.620743 | 最优权重为 text 0.2 / image 0.8 |

报告位置：

`G:\CISCN\.tmp\kt3_multioff_multiview_ablation_hf_safe\report.json`

预测与缓存输出：

- `G:\CISCN\.tmp\kt3_multioff_multiview_ablation_hf_safe\text_only_predictions.jsonl`
- `G:\CISCN\.tmp\kt3_multioff_multiview_ablation_hf_safe\image_only_predictions.jsonl`
- `G:\CISCN\.tmp\kt3_multioff_multiview_ablation_hf_safe\late_fusion_predictions.jsonl`
- `G:\CISCN\.tmp\kt3_multioff_multiview_ablation_hf_safe\clip_image_embeddings_24a2abc8bb876cdc.npz`

方法依据：

- [MultiOFF, TRAC 2020](https://aclanthology.org/2020.trac-1.6/)：支撑 offensive meme 的 text/image/fusion 对照评测。
- [Hateful Memes Challenge, NeurIPS 2020](https://proceedings.neurips.cc/paper/2020/hash/1b84c4cee2b8b3d823b30e2d604b1878-Abstract.html)：支撑“不能只看单模态捷径，必须报告多模态融合”的评测原则。
- [MAMI, SemEval 2022 Task 5](https://aclanthology.org/2022.semeval-1.74/)：支撑图文 meme harmfulness/misogyny 任务的迁移方向。
- [CLIP, ICML 2021](https://proceedings.mlr.press/v139/radford21a.html)：支撑冻结 vision-language encoder 作为低数据条件下 `D_img` 初始化。

该结果是 KT3 帖子级验证的重要进展：第一次在本地公开图文 benchmark 上跑通了 `D_tweet / D_img / late_fusion` 的可复现对照。但它仍不是全量验证，因为只覆盖 MultiOFF、只覆盖 meme/img/text，不覆盖真实 video encoder、claim-conditioned evidence、Jigsaw/Hateful Memes/MAMI/MOCHEG 等 P0 数据集。

### 8.4 已完成的跨本地数据集 Post Multiview Suite

已新增跨数据集评测脚本：

```powershell
python G:\CISCN\CogGuard\system\backend\scripts\run_kt3_post_multiview_ablation.py `
  --datasets MultiOFF HateXplain PHEME mcfend FakeSV `
  --case-dir G:\CISCN\.tmp\kt3_post_cases_full `
  --output-dir G:\CISCN\.tmp\kt3_post_multiview_ablation_with_fakesv `
  --hf-endpoint https://huggingface.co
```

该脚本把本地可用的 `kt3-post-case-v1` 数据集放到同一 report 中评估，并对缺失视图显式 skipped。当前权威报告位置已经统一为：

`G:\CISCN\.tmp\kt3_post_multiview_ablation_full_registry\report.json`

当前结果：

| 数据集 | split policy | 可用视图 | 最优实验 | Test Accuracy | Test Macro-F1 | skipped 视图 |
|---|---|---|---|---:|---:|---|
| MultiOFF | official train/validation/test | text + image + fusion | `learned_fusion` | 0.662162 | 0.655878 | video |
| HateXplain | official train/val/test，unassigned ignored | text | `text_only` | 0.770270 | 0.766130 | image、fusion、video |
| PHEME | event holdout: sydneysiege + ottawashooting；train pool 15% 做 validation | text + claim-context metadata | `text_only` | 0.754145 | 0.591510 | image、video、external evidence retrieval |
| mcfend | stratified random 70/10/20 | text + claim-context metadata | `claim_context_only` | 0.863399 | 0.818745 | image、video、social context |
| FakeSV | official temporal time3 train/validation/test | keywords text + C3D pre-extracted video feature | `late_fusion` | 0.808333 | 0.783923 | raw video、audio、keyframe、ASR/OCR、comment/publisher social context |

报告中新增 `summary.coverage_matrix`，用于区分“有 test metric”和“完成该 benchmark 期望视图验证”。当前 view coverage 结果如下：

| 数据集 | full expected view coverage | 仍缺什么 |
|---|---:|---|
| MultiOFF | true | 无视图覆盖缺口；但数据审计仍是 partial，因为有少量图片引用缺失 |
| HateXplain | true | 无视图覆盖缺口；但 target/rationale head 仍未训练 |
| PHEME | true | claim view 已由 dataset annotation metadata baseline 验证；仍不是外部 RAG/evidence retrieval |
| mcfend | true | 无视图覆盖缺口；但当前只按 text/claim-context benchmark 验证，social context 尚未纳入 |
| FakeSV | true | 已完成 C3D 预提取视频特征 baseline；不是 raw-video 端到端 encoder |

预测输出：

- `G:\CISCN\.tmp\kt3_post_multiview_ablation_full_registry\MultiOFF\text_only_predictions.jsonl`
- `G:\CISCN\.tmp\kt3_post_multiview_ablation_full_registry\MultiOFF\image_only_predictions.jsonl`
- `G:\CISCN\.tmp\kt3_post_multiview_ablation_full_registry\MultiOFF\majority_vote_predictions.jsonl`
- `G:\CISCN\.tmp\kt3_post_multiview_ablation_full_registry\MultiOFF\late_fusion_predictions.jsonl`
- `G:\CISCN\.tmp\kt3_post_multiview_ablation_full_registry\MultiOFF\learned_fusion_predictions.jsonl`
- `G:\CISCN\.tmp\kt3_post_multiview_ablation_full_registry\HateXplain\text_only_predictions.jsonl`
- `G:\CISCN\.tmp\kt3_post_multiview_ablation_full_registry\PHEME\text_only_predictions.jsonl`
- `G:\CISCN\.tmp\kt3_post_multiview_ablation_full_registry\mcfend\text_only_predictions.jsonl`
- `G:\CISCN\.tmp\kt3_post_multiview_ablation_full_registry\FakeSV\text_only_predictions.jsonl`
- `G:\CISCN\.tmp\kt3_post_multiview_ablation_full_registry\FakeSV\video_feature_only_predictions.jsonl`
- `G:\CISCN\.tmp\kt3_post_multiview_ablation_full_registry\FakeSV\video_text_late_fusion_predictions.jsonl`

这一步把当前“本地可用数据”的验证统一到一个 suite 中，但仍需严格解释边界：

- `MultiOFF` 是当前唯一真正完成 `text/image/fusion` 的图文 benchmark。
- `HateXplain` 当前验证的是文本 harmfulness；target/rationale 已进入统一 schema，但尚未训练 rationale extraction 或 target classification head。
- `PHEME` 当前新增了 `claim_context_only` 与 `claim_context_late_fusion`，使用 PHEME annotation 中的 claim category 与 evidence link metadata；这让 claim view 覆盖通过，但仍不是外部 evidence retrieval 或 RAG。
- `mcfend` 官方方向是中文多源假新闻检测，但当前本地 `kt3-post-case` 只包含 `news.csv` 中的文本/claim 字段，没有从 `social_context.csv` 或潜在媒体源恢复图像/视频，因此当前只能算 text/claim-context baseline。
- `FakeSV` 当前已验证公开 `keywords` text view 与 C3D 预提取 video feature view。C3D 结果可作为 `D_video` 的预提取视频特征 baseline，但不是 raw video、audio、OCR、ASR、评论或发布者 social context 多模态模型。
- suite 的 skipped 不是失败，而是数据契约诚实暴露：缺少 aligned media、raw video 或 claim/evidence 数据时不能用 metadata 冒充 image/video/claim-evidence detection。

### 8.5 后续任务

1. 下载并校验剩余 P0 数据集：Jigsaw Toxicity、Hateful Memes、MOCHEG、MMHS150K、MAMI、FACTIFY3M、RumourEval 2019。
2. 为 MultiOFF 补齐缺失图片或在验证协议中固定 `media_missing_policy`。
3. 将 CLIP image-only 评估扩展到 Hateful Memes、MAMI、MMHS150K，并补充 BLIP-2/ViT 对照。
4. 接入 claim retrieval/evidence 模块，扩展到 MOCHEG/FACTIFY/RumourEval。
5. 修复/扩展 mcfend 转换器：读取 `social_context.csv`，恢复社交上下文与可能的多媒体 URL；若源数据没有媒体二进制，则只能把 mcfend 定位为 text/social fake-news 数据集。
6. 为 FakeSV 继续补 raw videos、VGG19/VGGish/audio、keyframe、OCR、ASR、评论和发布者上下文；当前 C3D 只完成预提取视频特征 baseline。
7. 在同一 report 中输出 `tweet-only / img-only / meme-only / video-only / majority_vote / weighted_vote / learned_fusion` ablation。

## 9. 当前结论

帖子级统一检测模型已经可以形式化为 `tweet / meme / img / video` 多视图检测器加可解释融合层。当前工程已经有运行时 scaffold、数据 readiness gate、统一 `kt3-post-case-v1` 转换、text-only baseline、MultiOFF 上的 `text_only / image_only / majority_vote / late_fusion / learned_fusion` 多视图 ablation，以及跨本地数据集 Post Multiview Suite。当前 full-registry suite 覆盖 15 个 registry benchmark，其中 5 个本地可评估：MultiOFF learned-fusion Test Macro-F1 = 0.655878，高于 text-only 的 0.573799；HateXplain text-only Macro-F1 = 0.766130；PHEME event-holdout text-only Macro-F1 = 0.591510，并新增 claim-context metadata view；mcfend claim-context-only Macro-F1 = 0.818745；FakeSV text-only metadata proxy Macro-F1 = 0.772814，C3D `video_feature_only` Macro-F1 = 0.604837，text + C3D `late_fusion` Macro-F1 = 0.783923。

但这仍不能声明已经完成数据集全量验证：strict full-validation gate 当前 `overall_pass=false`，P0 passed 为 FakeSV、HateXplain、PHEME、mcfend。MultiOFF 虽然 view coverage 通过，但 audit/conversion 仍是 partial；Hateful Memes、MAMI、MMHS150K、MOCHEG、FACTIFY3M、RumourEval 2019、Jigsaw 等 P0 数据仍未进入可评估状态。下一步应优先补齐 P0 数据集、claim/evidence 视图、raw-video/ASR/OCR/audio/social context 和跨 benchmark learned fusion。
