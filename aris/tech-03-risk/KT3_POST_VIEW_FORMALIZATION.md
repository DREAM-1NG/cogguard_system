# KT3 Post-Level Multi-View Harmfulness Formalization

## Target

本文档形式化 KT3 帖子级 harmfulness 研判任务：对一条 post 分别构造 `tweet / meme / img / video` 四类 Post View，由四个 View Detector 独立判定，再通过多数投票和加权融合得到帖子级最终结论。

目标不是把 OCR、ASR、URL、hashtag 拼成手工特征表，而是把单条 post 建模为一个多视角证据对象。每个视角都必须回答：该视角是否有可解码证据、该视角是否 harmful、属于哪类 harm、证据是什么、是否需要弃权。

## Canonical Decision Contract

KT3 帖子级研判的统一合同是：

`tweet / meme / img / video` 分别 detect，得到四个视角级判断；随后只使用 Effective View 做多数投票和融合，最终输出帖子是否 harmful。

更形式化地说，单条帖子表示为：

`p = (x_tweet, x_meme, x_img, x_video, c, m)`

其中 `c` 是 claim/evidence context，`m` 是平台、事件、语言、媒体可用性等元信息。四个视角检测器分别为：

| Detector | 输入视角 | 判断问题 | 必要边界 |
|---|---|---|---|
| `D_tweet` | `x_tweet` | 文本、hashtag、emoji 是否 harmful，并对 claim 持何种 stance | 可使用正文和可见文本上下文 |
| `D_meme` | `x_meme` | 图文组合是否构成 harmful meme | 必须有图文组合或可解码图像证据，不能只用 URL |
| `D_img` | `x_img` | 图片、OCR、caption、视觉区域是否携带 harmful evidence | 必须有 OCR、caption、alt、图像描述或视觉编码输出 |
| `D_video` | `x_video` | ASR、OCR、字幕、关键帧、视频描述是否携带 harmful evidence | 必须有 ASR/OCR/caption/keyframe/video encoder 输出 |

每个检测器输出：

`D_v(x_v, c) -> r_v = (available_v, abstain_v, y_v, s_v, q_v, H_v, E_v, reason_v)`

其中 `y_v in {harmful, non_harmful, uncertain}`，`s_v` 是视角 harmfulness score，`q_v` 是置信度，`H_v` 是 harm type，`E_v` 是可审计证据。

只有满足以下条件的视角才能进入帖子级决策：

`I_v = 1[available_v = true and abstain_v = false and y_v in {harmful, non_harmful}]`

多数投票：

`Vote_h = sum_v I_v * 1[y_v = harmful]`

`Vote_n = sum_v I_v * 1[y_v = non_harmful]`

`y_vote = harmful` if `Vote_h > N_eff / 2`

`y_vote = non_harmful` if `Vote_n > N_eff / 2`

`y_vote = uncertain` otherwise

加权融合：

`s_fuse = sum_v I_v * w_v * q_v * s_v / sum_v I_v * w_v * q_v`

`s_fuse >= tau_h` 判为 `harmful`，`s_fuse <= tau_n` 判为 `non_harmful`，中间区间判为 `uncertain`。

最终裁决：

| 条件 | 最终标签 | 策略 |
|---|---|---|
| `y_vote = y_fuse != uncertain` | `y_vote` | `majority_vote_confirmed_by_weighted_fusion` |
| `y_vote != uncertain` 且与 `y_fuse` 不一致或 `y_fuse=uncertain` | `y_vote` | `majority_vote` |
| `y_vote = uncertain` | `y_fuse` | `weighted_fusion_fallback` |

因此，URL-only 的图片或视频只能证明媒体存在，不能证明系统理解了媒体内容；对应 `meme / img / video` 视角必须 `abstain=true`，并被排除出多数投票、加权融合和 harm type 聚合。

## Status

COHERENT AFTER REFRAMING / EXTRA ASSUMPTION

当前代码已经实现四视角 runtime scaffold、弃权、 多数投票和加权 late fusion；但 `D_img / D_video` 尚未接入真实图像/视频编码器，四个 detector 也尚未训练。因此本文档把当前能力定位为“可审计的形式化接口和运行时闭环”，把后续目标定位为“可训练的多视角检测器与学习式融合”。

## Invariant Object

不变对象是单条帖子 `p` 的 harmfulness judgment：

`J(p) = (y_p, s_p, H_p, E_p, R_p)`

其中：

| Symbol | Meaning |
|---|---|
| `y_p` | 帖子级标签，取 `harmful / non_harmful / uncertain` |
| `s_p` | 帖子级 harmfulness score |
| `H_p` | harm type 集合或分布，例如 misinformation、hate/harassment、smear、mobilization、amplification |
| `E_p` | 支撑判断的跨视角证据 |
| `R_p` | review reasons，例如缺少可解码媒体、投票不确定、跨视角冲突 |

四个视角、claim reasoning、Agent 复核都只是估计 `J(p)` 的路径，不能替代这个不变对象。

## Assumptions

- 一条 post 最多被展开为四个 Post View：`tweet`、`meme`、`img`、`video`。
- `tweet` 视角使用正文、hashtag、emoji、可见文本上下文。
- `meme` 视角要求存在图文组合证据，即图片相关 OCR、caption、alt text、frame/context text 等可解码媒体证据；仅有图片 URL 不足以构成有效 meme 判断。
- `img` 视角要求存在图像可解码证据，例如 OCR、caption、alt text、图像描述或未来的视觉编码器输出；仅有图片 URL 不算可解码证据。
- `video` 视角要求存在视频可解码证据，例如 ASR、字幕、OCR、关键帧 caption、视频描述或未来的视频编码器输出；仅有 `.mp4` URL 不算可解码证据。
- 缺少可解码证据的视角必须 `abstain=true`，不能被当作 `non_harmful`。
- 多数投票和加权融合只允许 Effective View 参与，即 `available=true` 且 `abstain=false` 的视角。
- 当前 runtime scaffold 使用语义原型/词法回退估计 view score；后续训练版需要用公开数据集和项目 gold/control set 校准概率与阈值。

## Notation

单条帖子表示为：

`p = (x_tweet, x_meme, x_img, x_video, c, m)`

其中：

| Term | Meaning |
|---|---|
| `x_tweet` | 正文、hashtag、emoji、reply/repost 可见文本 |
| `x_meme` | 图文 meme 对象，包括图像、OCR、caption、图文关系 |
| `x_img` | 普通图像对象，包括 OCR、caption、alt text、视觉区域或图像编码 |
| `x_video` | 视频对象，包括关键帧、OCR、ASR、字幕、标题、视频描述 |
| `c` | claim candidates、retrieved evidence、fact-check context |
| `m` | 平台、事件、时间、语言、媒体可用性等元信息 |

视角集合为：

`V(p) = {tweet, meme, img, video}`

每个 detector 输出：

`D_v(x_v, c) -> r_v = (a_v, b_v, y_v, s_v, q_v, H_v, E_v, z_v)`

字段含义：

| Symbol | Field | Meaning |
|---|---|---|
| `a_v` | `available` | 视角是否存在可解码证据 |
| `b_v` | `abstain` | detector 是否弃权 |
| `y_v` | `label` | `harmful / non_harmful / uncertain` |
| `s_v` | `score` | 视角 harmfulness score |
| `q_v` | `confidence` | 视角判断置信度 |
| `H_v` | `harm_types` | 该视角支持的 harm type |
| `E_v` | `evidence` | 文本 span、OCR、ASR、caption、frame、region 或检索证据 |
| `z_v` | `reason` | `view_detected`、`view_unavailable`、`media_without_decodable_content` 等 |

Effective View 定义为：

`I_v = 1[a_v = 1 and b_v = 0 and y_v in {harmful, non_harmful}]`

`N_eff = sum_{v in V(p)} I_v`

## Derivation Strategy

推导采用“视角独立判定 -> 有效视角筛选 -> 多数投票 -> 加权融合 -> 最终裁决 -> 复核路由”的顺序。

这样设计有三个原因：

1. 可以防止缺失图像/视频证据被误当作 negative evidence。
2. 可以保留每个视角自己的证据链，便于用户级 MIL、社区级图模型和 Agent reviewer 继续消费。
3. 可以先实现可审计 scaffold，再平滑迁移到 CLIP/BLIP-2/video encoder/teacher-student 等可训练模型。

## Derivation Map

1. 每个 `D_v` 先判断 `a_v` 和 `b_v`，决定该视角能否进入帖子级融合。
2. 每个 Effective View 输出 `y_v, s_v, q_v, H_v, E_v`。
3. 多数投票只统计 Effective View 的离散标签。
4. 加权融合只统计 Effective View 的 score 和 confidence。
5. 最终裁决优先采用“多数投票与加权融合一致”的结果；若多数投票给出明确标签，则优先保留多数投票；否则回退到加权融合。
6. 若无 Effective View、投票平局、融合不确定或跨视角冲突，则进入 review queue / Agent reviewer。

## Main Derivation

### Step 1. View-Level Detection

对每个 `v in V(p)`：

`r_v = D_v(x_v, c)`

其中 `D_v` 的任务不是抽取特征，而是完成视角级研判：

| Detector | View | Question | Current Runtime Mapping |
|---|---|---|---|
| `D_tweet` | `tweet` | 正文、hashtag、emoji 是否 harmful，并对 claim 持何种 stance | `post_semantics.py::_infer_post_view_detection` 的 `tweet` view |
| `D_meme` | `meme` | 图文组合是否形成 offensive/hateful/misleading meme | `post_semantics.py::_infer_post_view_detection` 的 `meme` view |
| `D_img` | `img` | 图片/OCR/caption 是否携带 harmful evidence | `post_semantics.py::_infer_post_view_detection` 的 `img` view |
| `D_video` | `video` | ASR/OCR/keyframe/caption 是否携带 harmful evidence | `post_semantics.py::_infer_post_view_detection` 的 `video` view |

### Step 2. View Availability and Abstention

可用性规则是：

`a_tweet = 1` 当正文、hashtag 或 emoji 存在。

`a_meme = 1` 当图片相关 OCR、caption、alt text、图像描述或未来视觉编码输出存在。

`a_img = 1` 当图片 OCR、caption、alt text、图像描述或未来视觉编码输出存在。

`a_video = 1` 当 ASR、字幕、视频 OCR、关键帧 caption、视频描述或未来视频编码输出存在。

如果只有媒体 URL：

`a_meme = a_img = a_video = 0`

该视角输出：

`r_v = (available=false, abstain=true, label=uncertain, reason=media_without_decodable_content)`

### Step 3. Majority Vote

有效视角数量：

`N_eff = sum_v I_v`

harmful 票数：

`Vote_h = sum_v I_v * 1[y_v = harmful]`

non-harmful 票数：

`Vote_n = sum_v I_v * 1[y_v = non_harmful]`

多数投票规则：

`y_vote = harmful` if `Vote_h > N_eff / 2`

`y_vote = non_harmful` if `Vote_n > N_eff / 2`

`y_vote = uncertain` otherwise

当 `N_eff = 0` 时，`y_vote = uncertain`，并记录 `no_confident_view_votes`。

### Step 4. Weighted Late Fusion

每个有效视角的融合权重为：

`beta_v = w_v * q_v`

其中 `w_v` 是视角先验可靠性，`q_v` 是当前样本置信度。

帖子 harmfulness score：

`s_fuse = (sum_v I_v * beta_v * s_v) / (sum_v I_v * beta_v)`

当前 runtime 使用固定 `w_v`：

| View | Prior Weight |
|---|---:|
| `tweet` | 1.00 |
| `meme` | 1.15 |
| `img` | 0.90 |
| `video` | 1.10 |

融合标签：

`y_fuse = harmful` if `s_fuse >= tau_h`

`y_fuse = non_harmful` if `s_fuse <= tau_n`

`y_fuse = uncertain` otherwise

当前 runtime 阈值为 `tau_h=0.58`、`tau_n=0.48`。训练版需要在 validation split 上学习或校准 `w_v, tau_h, tau_n`。

### Step 5. Final Post-Level Decision

最终裁决函数：

`F(y_vote, y_fuse, s_fuse) -> J(p)`

规则如下：

| Condition | Final Label | Policy |
|---|---|---|
| `y_vote = y_fuse != uncertain` | `y_vote` | `majority_vote_confirmed_by_weighted_fusion` |
| `y_vote != uncertain` and `y_fuse` differs or uncertain | `y_vote` | `majority_vote` |
| `y_vote = uncertain` | `y_fuse` | `weighted_fusion_fallback` |

### Step 6. Harm Type Aggregation

harm type 也只能来自 Effective View：

`H_p = rank_by_sum_v I_v * beta_v * 1[h in H_v]`

如果最终标签是 `non_harmful`，则 `H_p = empty`。

### Step 7. Review Routing

以下情况必须进入复核队列：

| Trigger | Review Reason |
|---|---|
| 无有效视角 | `no_confident_view_votes` |
| 多数投票不确定 | `majority_vote_uncertain` |
| 加权融合不确定 | `weighted_fusion_uncertain` |
| meme/img/video 只有 URL 无可解码内容 | `media_without_decodable_content` |
| 有效视角标签冲突 | `cross_view_label_conflict` |
| 有效视角 score 分歧过大 | `cross_view_score_divergence` |

## Remarks and Interpretation

- 多数投票是最低可用、可审计的裁决规则，适合验收和故障定位。
- 加权融合用于处理视角可靠性差异，但当前权重是工程先验，不是训练所得。
- `meme` 不是第二个文本分类器；它必须依赖图文组合中的可解码媒体证据。
- `img/video` 不应该因为 URL 存在而参与融合；URL 只能说明媒体存在，不能说明系统理解了媒体内容。
- LLM/Multi-Agent 更适合作为 teacher、reviewer、rule optimizer、error analyst，而不是替代四个底层 detector 的在线分类器。

## Boundaries and Non-Claims

- 当前实现不是端到端多模态大模型。
- 当前实现没有训练好的图像编码器、视频编码器或 view detector。
- 当前实现没有把媒体 URL 当作图像/视频理解结果。
- 当前实现的 `score` 是 runtime scaffold 的语义相似度/词法回退估计，不是 calibrated probability。
- 当前多数投票和加权融合已经可运行，但完整 `MV-PostGuard` 仍需要在 HateXplain、Jigsaw、MultiOFF、Hateful Memes、MAMI、MMHS150K、PHEME、RumourEval、MOCHEG、FACTIFY3M、FakeSV 等数据上训练和校准。

## Open Risks

- `D_meme / D_img / D_video` 的真实能力取决于后续是否接入 CLIP/BLIP-2/keyframe/ASR/OCR/video encoder 与 aligned media 数据。
- claim-conditioned misinformation 需要 claim retrieval 和 evidence verification，否则只能得到弱化的 claim proxy。
- 多数投票在强相关视角之间可能高估共识，例如 tweet 正文和 OCR 文本重复；训练版需要加入 view dependency calibration。
- 低资源或跨语言场景需要单独校准阈值和置信度，否则 `uncertain` 与 `harmful` 的边界可能漂移。

## Code Alignment

当前代码映射：

| Formal Element | Code |
|---|---|
| `V(p)` | `POST_VIEW_ORDER = ("tweet", "meme", "img", "video")` |
| `D_v` | `POST_VIEW_DETECTORS` |
| view construction | `_post_view_payloads` |
| view detection | `_detect_single_post_view` |
| majority vote | `_majority_vote_post_views` |
| weighted fusion | `_weighted_fuse_post_views` |
| final decision | `_select_post_view_final_decision` |
| conflict routing | `_post_view_conflict` and `_post_view_review_reasons` |
| capability boundary | `_post_view_capability_boundary` |

测试映射：

| Boundary | Test |
|---|---|
| 四视角输出与 fusion policy | `TestPostSemantics.test_assess_post_semantics` |
| 缺少 video 视角时弃权 | `TestPostSemantics.test_post_view_detection_abstains_missing_video_view` |
| 图片 URL-only 不进入 meme/img 融合 | `TestPostSemantics.test_post_view_detection_excludes_image_url_without_decodable_content` |
| 视频 URL-only 不进入 video 融合 | `TestPostSemantics.test_post_view_detection_excludes_video_url_without_decodable_content` |
