# Risk Review Full Validation Data Acquisition and Readiness

## Purpose

本文档记录 Risk Review 帖子级统一检测模型 `MV-PostGuard` 进行全量验证所需的数据、论文、开源仓库、当前本地状态和下一步动作。它的作用是防止把“论文/代码仓库已找到”误写成“数据集已可全量验证”。

当前权威机器可读入口：

- Registry: `G:\CISCN\CogGuard\system\backend\app\core\risk\config\review_post_benchmarks.json`
- Audit script: `G:\CISCN\CogGuard\system\backend\scripts\audit_review_post_datasets.py`
- Latest audit report: `G:\CISCN\.tmp\review_post_dataset_audit_v2.json`
- Full-validation gate script: `G:\CISCN\CogGuard\system\backend\scripts\summarize_review_full_validation.py`
- Latest full-validation gate report: `G:\CISCN\.tmp\review_full_validation_gate_report.json`

重跑审计：

```powershell
cd G:\CISCN\CogGuard\system\backend
python scripts\audit_review_post_datasets.py `
  --dataset-root G:\CISCN\dataset `
  --output G:\CISCN\.tmp\review_post_dataset_audit_v2.json
```

判定是否可以声称 full validation 完成：

```powershell
cd G:\CISCN\CogGuard\system\backend
python scripts\summarize_review_full_validation.py `
  --audit G:\CISCN\.tmp\review_post_dataset_audit_v2.json `
  --manifest G:\CISCN\.tmp\review_post_cases_full\manifest.json `
  --suite G:\CISCN\.tmp\review_post_multiview_ablation_full_registry\report.json `
  --output G:\CISCN\.tmp\review_full_validation_gate_report.json
```

## Current Readiness Summary

截至本次审计，15 个 benchmark 的状态为：

| Status | Datasets | Meaning |
|---|---|---|
| `ready` | FakeSV, HateXplain, PHEME, Twitter15_16_dataset, mcfend | 本地结构可读，可进入 converter 或已能作为当前 suite 的输入；FakeSV 的 ready 来自 C3D 预提取视频特征覆盖 temporal split，仍不代表 raw-video 模型完成 |
| `partial` | MultiOFF | 可做局部验证，但 aligned image 或少量文件仍不完整 |
| `present_unverified` | Fakeddit, MAMI, MOCHEG, RumourEval 2019 | 本地有代码仓库、baseline 或部分文件，但缺正式数据包/必要 split/gold 文件 |
| `missing` | FACTIFY3M, Hateful Memes, Jigsaw Toxicity, MMHS150K, MuMiN | 本地未发现可用数据目录或 required files |

P0 数据集中，真正 `ready` 的只有：

- FakeSV
- HateXplain
- PHEME
- mcfend

当前 full-validation gate 的结论是 `overall_pass=false`，`claim=full_validation_not_complete`。Gate 要求每个 P0 数据集同时满足 audit ready、conversion converted、suite evaluated 且有 test metric；任何 `partial`、`present_unverified`、`missing`、`skipped` 或 metadata-proxy-only 状态都不能支撑 full validation claim。

P0 但尚未满足 full validation 的数据集是：

- FACTIFY3M
- Hateful Memes
- Jigsaw Toxicity
- MAMI
- MMHS150K
- MOCHEG
- MultiOFF
- RumourEval 2019

其中 MultiOFF 仍不能称为完整 benchmark，因为有少量图片引用缺失。FakeSV 已通过 C3D 预提取视频特征 baseline 支撑当前 `D_video` 视图覆盖，但仍不能称为 raw-video 完整 benchmark，因为尚未接入 raw video、keyframe、OCR、ASR、audio、评论或发布者 social-context 多模态特征。

## P0 Dataset Matrix

| Dataset | Role in MV-PostGuard | Paper / Method Link | Data / Repo Link | Local Status | Required Action |
|---|---|---|---|---|---|
| MultiOFF | `D_meme / D_img` 图文 harmfulness；text/image/fusion ablation | [MultiOFF, TRAC 2020](https://aclanthology.org/2020.trac-1.6/) | [GitHub](https://github.com/FirojAlam/multioff) | `partial` | 补齐缺失图片或在协议中固定 `media_missing_policy`; 当前可跑 text/image/weighted fusion/learned fusion |
| HateXplain | `D_tweet` 文本 harmfulness、target、rationale | [HateXplain, AAAI 2021](https://ojs.aaai.org/index.php/AAAI/article/view/17745) | [GitHub](https://github.com/hate-alert/HateXplain) | `ready` | 下一步训练 target/rationale head，而不只做 text label |
| Jigsaw Toxicity | `D_tweet` toxicity calibration baseline | [Kaggle Challenge](https://www.kaggle.com/competitions/jigsaw-toxic-comment-classification-challenge) | [Data](https://www.kaggle.com/competitions/jigsaw-toxic-comment-classification-challenge/data) | `missing` | 需要 Kaggle account/token 并接受数据条款后下载 |
| Hateful Memes | hard negative 图文 meme benchmark | [NeurIPS 2020](https://proceedings.neurips.cc/paper/2020/hash/1b84c4cee2b8b3d823b30e2d604b1878-Abstract.html) | [Meta AI dataset page](https://ai.meta.com/tools/hatefulmemes/), [MMF project](https://github.com/facebookresearch/mmf/tree/main/projects/hateful_memes) | `missing` | 需要申请/接受 Meta 数据条款后下载图片与 labels |
| MAMI | `D_meme / D_img` misogyny + subtype benchmark | [SemEval 2022 Task 5](https://aclanthology.org/2022.semeval-1.74/) | [Official GitHub](https://github.com/MIND-Lab/MAMI), [Data request form](https://forms.gle/AGWMiGicBHiQx4q98) | `present_unverified` | 本地已 clone baseline/evaluation，但缺 `TRAINING`, `train.csv`, `test.csv`, `ref`; 需填表获取数据包 |
| MMHS150K | tweet-image hate speech benchmark | [ICWSM 2019](https://ojs.aaai.org/index.php/ICWSM/article/view/3252) | [Author page](https://gombru.github.io/2019/10/09/MMHS/), [Kaggle mirror](https://www.kaggle.com/datasets/victorcallejasf/multimodal-hate-speech) | `missing` | 需要 Kaggle token/terms 或作者页面说明的数据获取方式 |
| PHEME | claim-conditioned text rumour / veracity | [Figshare dataset](https://figshare.com/articles/dataset/PHEME_dataset_for_Rumour_Detection_and_Veracity_Classification/6392078) | [Figshare](https://figshare.com/articles/dataset/PHEME_dataset_for_Rumour_Detection_and_Veracity_Classification/6392078) | `ready` | 当前可跑 event-holdout text/claim proxy；后续补更严格 veracity/stance head |
| RumourEval 2019 | stance + veracity benchmark | [SemEval 2019 Task 7](https://aclanthology.org/S19-2147/) | [CodaLab](https://competitions.codalab.org/competitions/19938), [Baseline GitHub](https://github.com/kochkinaelena/RumourEval2019) | `present_unverified` | 本地只有 baseline/results 仓库；需从 CodaLab 下载 original train/test data |
| MOCHEG | multimodal claim verification + evidence/explanation | [SIGIR 2023 DOI](https://dl.acm.org/doi/10.1145/3539618.3591879) | [GitHub](https://github.com/VT-NLP/Mocheg), [Data request form](https://docs.google.com/forms/d/e/1FAIpQLScAGehM6X9ARZWW3Fgt7fWMhc_Cec6iiAAN4Rn1BHAk6KOfbw/viewform?usp=sf_link) | `present_unverified` | 本地有 implementation，但缺 `Corpus2.csv`, `train`, `dev`, `test`; 需填表获取数据 |
| FACTIFY3M | large-scale multimodal fact verification + 5W QA explanation | [EMNLP 2023](https://aclanthology.org/2023.emnlp-main.945/) | Paper/author channel; prior GitHub unavailable | `missing` | 需要联系作者或等待官方 release；older Factify baseline 不含 FACTIFY3M 数据 |
| FakeSV | `D_video` short-video misinformation benchmark | [AAAI 2023](https://ojs.aaai.org/index.php/AAAI/article/view/26689) | [GitHub](https://github.com/ICTMCG/FakeSV), [HF features](https://huggingface.co/datasets/MischaQI/FakeSV) | `ready` | 当前 C3D zip 覆盖 temporal split，可跑 video_feature baseline；仍需 raw video、VGG19/VGGish/audio、keyframe、ASR/OCR、评论和发布者上下文 |
| mcfend | Chinese fake news / text-social benchmark | [GitHub](https://github.com/ICTMCG/MCFEND) | [GitHub](https://github.com/ICTMCG/MCFEND) | `ready` | 当前 conversion 主要 text-only；后续补 social_context/user context 与中文 domain split |

## P1 / Optional Datasets

| Dataset | Role | Link | Local Status | Required Action |
|---|---|---|---|---|
| Fakeddit | optional image-text fake news benchmark | [Paper](https://aclanthology.org/2020.lrec-1.755/), [Project](https://fakeddit.netlify.app/), [GitHub](https://github.com/entitize/Fakeddit) | `present_unverified` | 本地只有 downloader repo；需要 Google Drive/CodaLab v2.0 TSV 与 image files |
| MuMiN | optional multimodal misinformation graph benchmark | [SIGIR 2022 DOI](https://dl.acm.org/doi/10.1145/3477495.3531744), [Dataset site](https://mumin-dataset.github.io/), [GitHub](https://github.com/MuMiN-dataset/mumin) | `missing` | 需按官网下载/构建；注意 Twitter/platform redistribution terms |
| Twitter15/16 | optional rumour propagation/text benchmark | [ACL 2018](https://aclanthology.org/P18-1184/), [Dataset repo](https://github.com/gszswork/Twitter15_16_dataset), [RvNN repo](https://github.com/majingCUHK/Rumor_RvNN) | `ready` in audit, but local conversion notes text limitations | 需要核实 source tweet text 是否完整；否则只适合作为 propagation/tree auxiliary data |

## Current Validation Evidence

当前已跑通的本地 full-registry suite：

```powershell
cd G:\CISCN\CogGuard\system\backend
python scripts\run_review_post_multiview_ablation.py `
  --case-dir G:\CISCN\.tmp\review_post_cases_full `
  --output-dir G:\CISCN\.tmp\review_post_multiview_ablation_full_registry `
  --hf-endpoint https://huggingface.co
```

现有可复现结果：

| Dataset | Current Best Experiment | Test Macro-F1 | Boundary |
|---|---|---:|---|
| MultiOFF | `learned_fusion` | 0.655878 | validation-calibrated Logistic Regression fusion over text/image probabilities；但少量图片引用缺失，且不是端到端多模态 Transformer |
| HateXplain | `text_only` | 0.766130 | 只验证 text harmfulness；target/rationale head 尚未训练 |
| PHEME | `text_only` | 0.591510 | event-holdout text baseline；已新增 claim-context metadata baseline，但非外部 evidence retrieval/RAG |
| mcfend | `claim_context_only` | 0.818745 | 中文 claim-context/text baseline；social/user context 尚未纳入 |
| FakeSV | `late_fusion` text + C3D video feature | 0.783923 | C3D 是预提取视频特征 baseline，不是 raw-video / keyframe / ASR / OCR / audio / social-context 完整模型 |

因此当前状态是“full validation runner 雏形已跑通”，不是“全量验证完成”。

当前 full-registry runner 覆盖 15 个 benchmark。`G:\CISCN\.tmp\review_post_multiview_ablation_full_registry\report.json` 中 evaluated datasets 为 MultiOFF、HateXplain、PHEME、FakeSV、mcfend；Jigsaw Toxicity、Hateful Memes、MAMI、MMHS150K、RumourEval 2019、MOCHEG、FACTIFY3M、Fakeddit、MuMiN 因缺少 `review-post-case-v1` JSONL 被显式 skipped；Twitter15/16 因本地缺 source tweet text，只有 label/tree，无法作为内容检测训练/测试数据。

MultiOFF 现在同时报告四个视角/融合对照：`text_only` Macro-F1 = 0.573799，`image_only` Macro-F1 = 0.617147，validation-grid `late_fusion` Macro-F1 = 0.620743，validation-calibrated `learned_fusion` Macro-F1 = 0.655878。`learned_fusion` 是一个轻量 Logistic Regression fusion head，输入为 text/image harmful probabilities、均值、差值和乘积，用 validation split 校准并在 test split 评估；它代表向可训练融合层迈进，但仍不是完整端到端 `MV-PostGuard`。

最新 suite 已新增 `summary.coverage_matrix`。该矩阵不只问“有没有 macro-F1”，还问“该数据集期望验证的视图是否真的被验证”。当前 full expected view coverage 为 true 的数据集是 FakeSV、MultiOFF、HateXplain、PHEME、mcfend；其中 MultiOFF 仍因审计/转换状态为 `partial` 无法通过 full-validation gate。PHEME 的 claim view 由 dataset annotation 中的 claim category 与 evidence link metadata baseline 支撑，仍不是外部 evidence retrieval/RAG。FakeSV 的 video view 由 public C3D 预提取特征 baseline 支撑，仍不是 raw-video 端到端模型。因此当前 strict gate 的 P0 passed 为 FakeSV、HateXplain、PHEME、mcfend，`overall_pass=false`。

统一转换入口已扩展到完整 registry：

```powershell
cd G:\CISCN\CogGuard\system\backend
python scripts\build_review_post_cases.py `
  --dataset-root G:\CISCN\dataset `
  --output-dir G:\CISCN\.tmp\review_post_cases_full
```

当前 manifest 覆盖 15 个 benchmark、59093 条 case：FakeSV、HateXplain、PHEME、mcfend 已 converted；MultiOFF、Twitter15/16 为 partial；其余 gated/missing 数据集不会生成伪样本，而是在 manifest 中保留 missing 状态与 required files。

## Acquisition Checklist

### Must Do Before Claiming Full Validation

1. 下载或申请 P0 gated datasets：Jigsaw、Hateful Memes、MAMI、MMHS150K、MOCHEG、RumourEval 2019、FACTIFY3M。
2. 对每个新数据集新增 converter，把样本转为 `review-post-case-v1`。
3. 对每个数据集固定 split policy，并在 manifest 中记录 official/random/event/temporal split。
4. 对有媒体的数据集确认 aligned local image/video files 存在，禁止 URL-only 冒充媒体理解。
5. 扩展 suite，使每个 dataset 至少报告可用的 `tweet-only / img-only / meme-only / video-only / majority_vote / weighted_fusion / learned_fusion`，并在 `coverage_matrix` 中显式标注未验证的期望视图。
6. 对 claim-conditioned datasets 增加 claim retrieval、stance/veracity、evidence recall 和 explanation 指标。
7. 对所有结果输出 dataset-level、view-level、harm-type-level、missing-modality-level error analysis。

### Local Paths To Use

所有数据和临时结果必须放在 `G:\CISCN` 下：

| Purpose | Path |
|---|---|
| Public/gated dataset repos | `G:\CISCN\dataset\review_public\<DatasetName>` |
| Downloaded benchmark files | `G:\CISCN\dataset\<DatasetName>` or `G:\CISCN\dataset\review_public\<DatasetName>` |
| Unified cases | `G:\CISCN\.tmp\review_post_cases_full` |
| Audit reports | `G:\CISCN\.tmp\review_post_dataset_audit_v2.json` |
| Suite reports | `G:\CISCN\.tmp\review_post_multiview_ablation_*` |

Do not create Risk Review temporary dataset folders under `C:\`.

## Non-Claims

- A cloned repository is not a ready dataset unless required train/dev/test labels and media files are present.
- A benchmark appearing in `present_unverified` is not eligible for full validation claims.
- `partial` supports scoped local experiments only; it does not satisfy full validation.
- Current FakeSV now includes a C3D pre-extracted video-feature baseline, but it is not raw-video/keyframe/ASR/OCR/audio/social-context validation.
- Current MultiOFF numbers are useful image-text validation evidence, but do not cover all meme/image benchmarks.
