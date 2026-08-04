# Chinese Account Detection Active Learning Loop

Updated: 2026-08-04

## Positioning

CogGuard's Chinese account detection is an analyst-in-the-loop active-learning system for collected Chinese social-media accounts. The model ranks account cases for review; analysts provide observable behavior labels; only approved or adjudicated labels enter a versioned corpus; candidate models activate only after leakage-safe evaluation and governance approval.

The official method name is **Chinese Account Detection Active Learning Loop**. Do not describe it as an automatic bot label generator, a pseudo-label pipeline, or a universal Chinese social bot detector.

## Why The Label Set Is Small

The supervised target is account-level social-bot detection with abstention:

- `human` maps to training target `non_bot`.
- `bot` maps to training target `bot`.
- `insufficient_evidence` maps to training target `abstain`.

The `human`/`bot` boundary follows the account-level bot detection framing in Ferrara et al. 2016, Varol et al. 2017, Cresci et al. 2017, DABot 2021, and TwiBot benchmark practice. The `insufficient_evidence` option is grounded in selective classification and abstention literature, not in DABot or TwiBot. Coordination, spam behavior, repeated templates, institution/media context, temporal bursts, OOD, and disagreement are evidence or acquisition signals. They are not supervised labels unless a separate annotation guide, agreement study, and dataset support that new task.

The system explicitly rejects identity, nationality, ideology, intent, and attribution labels.

## Closed Loop

1. **Account Detection Case** builds one platform-scoped case from collected posts, evidence ids, provenance, and a stable fingerprint.
2. **Account Label Batch** selects unlabeled cases with a fixed annotation budget and a random audit slice.
3. **Account Detection Label** records analyst-provided `human`, `bot`, or `insufficient_evidence` plus evidence post ids, reason tags, confidence, and case fingerprint.
4. **Approved Account Corpus** exports only approved or adjudicated labels into JSONL with a manifest, data fingerprint, and dataset card.
5. **Shadow Account Model** trains from a versioned approved corpus through `approved_account_corpus` and never from model predictions.
6. **Model Activation** requires persisted metrics, a registered dataset fingerprint, verified checkpoint bytes, frozen holdout, time-forward evaluation, platform stratification, community-disjoint checks, calibration, false-positive burden review, shadow run, and active administrator approval.

## Cold Start And Warm Start

**Cold start** means no reliable calibrated Chinese account ranker exists. The selector must not use classifier uncertainty because there is no trustworthy posterior. If language-model surprisal is available, the selector uses surprisal plus diversity. If not, it records a coverage/diversity/random-audit fallback. This is the ALPS-style initialization regime.

**Warm start** means a versioned and calibrated account model exists. Only then may the selector use uncertainty, model disagreement, OOD score, graph representativeness, and representation diversity. These scores rank human review priority only; they never create labels.

Every batch manifest records `model_state`, `ranker_status`, `surprisal_source`, `diversity_source`, and `acquisition_policy` so experiments can separate cold-start and warm-start regimes.

## Literature-Supported Decisions

| Decision | Primary support | Implementation consequence |
| --- | --- | --- |
| Use bot/human with abstention, not invented behavior classes. | Ferrara et al. 2016; Varol et al. 2017; Cresci et al. 2017; Geifman and El-Yaniv 2017. | `AccountBehaviorLabel` allows only `human`, `bot`, `insufficient_evidence`; reason tags carry richer evidence. |
| Keep Weibo active learning but avoid DABot-style hand-feature claims as the main model claim. | Wu et al. 2021 DABot. | The system transfers the human-labeling loop and governance, not a large manual feature stack as a novelty claim. |
| Use surprisal/diversity before model uncertainty is calibrated. | Yuan et al. 2020 ALPS; Sener and Savarese 2018. | `cold_start_surprisal_diversity` or `cold_start_coverage_diversity` is selected when no calibrated ranker exists. |
| Compare warm-start acquisition to simple baselines before adding expensive methods. | Ein-Dor et al. 2020; BADGE 2020; BatchBALD 2019; Contrastive Active Learning 2021; Schroeder et al. 2022; active-learning transferability and fragility studies. | Warm-start consumes calibrated uncertainty plus optional disagreement/OOD/representativeness/embedding signals; gradient and committee acquisition remain future extensions. |
| Keep active-learning deployment claims conservative. | Lowell et al. 2019 Practical Obstacles; active-learning transferability and fragility studies. | Equal-budget efficiency reports against random and simple baselines are required before claiming acquisition superiority. |
| Treat analyst labels as review records, not automatic truth. | Artstein and Poesio 2008; Passonneau and Carpenter 2014; ACTOR 2023; ACAL 2024. | Labels store analyst id, confidence, evidence ids, adjudicator id, and status. |
| Require calibration, abstention, and OOD boundaries before activation. | Guo et al. 2017; Hendrycks and Gimpel 2017; Ovadia et al. 2019; selective classification. | Uncalibrated probabilities cannot trigger warm-start uncertainty; candidate models need ECE and deployment gates. |
| Avoid graph and temporal leakage in account-level evaluation. | OGB; TGB; Pitfalls of GNN Evaluation; link-prediction leakage studies. | Frozen holdout and active-pool leakage manifests are required; community-disjoint checks remain an activation gate. |
| Maintain dataset/model documentation. | Datasheets for Datasets; Data Statements for NLP; Model Cards; Human-in-the-loop ML survey; Croissant metadata as a future target. | Approved corpus export writes JSONL, manifest, dataset card, fingerprint, and registered dataset version. |

## Implemented Seams

- `system/research/social_bot_detection/active_learning.py` implements deterministic account acquisition with cold-start and warm-start manifests.
- `system/research/social_bot_detection/chinese_corpus.py` exports approved labels as reproducible JSONL and a manifest.
- `system/research/social_bot_detection/datasets.py` loads `approved_account_corpus` exports for local BotRHG training and excludes `abstain` rows from binary supervised training.
- `system/research/social_bot_detection/cli.py` accepts `--dataset-name approved_account_corpus` so approved Chinese labels can feed the existing local RoBERTa/BotRHG training path.
- `system/research/social_bot_detection/evaluate_active_round.py` evaluates frozen holdout, time-forward, platform, community-disjoint, calibration, false-positive burden gates, holdout leakage manifests, and equal-budget active-learning efficiency rows.
- `system/backend/app/core/account_labeling.py` defines canonical labels and case fingerprints.
- `system/backend/app/core/account_active_learning.py` adapts backend cases into research acquisition candidates, safely parses calibrated model signals, and ignores malformed probability/embedding payloads.
- `system/backend/app/services/account_active_learning_service.py` persists label batches from Mongo posts and model outputs.
- `system/backend/app/services/account_label_service.py` stores submitted, approved, rejected, and adjudicated labels only after validating case existence, queued batch membership when supplied, case fingerprint, and evidence post ids.
- `system/backend/app/services/account_dataset_service.py` exports approved corpora and registers dataset versions only when label and current case fingerprints still match.
- `system/backend/app/services/account_model_governance_service.py` registers shadow candidates only when the dataset exists, labels are present, checkpoint bytes match the supplied SHA-256, records immutable active-administrator approval rows, and activates only from persisted metrics plus recorded approvals.
- `system/backend/alembic/versions/b6c2e9d4a731_add_account_detection_active_learning_tables.py` adds the account detection governance tables.
- `doc/research/account-detection-acquisition-optimization-plan.md` records the literature-grounded upgrade path from heuristic baseline to ALPS/core-set cold-start and BADGE warm-start acquisition.

## Current Limits

- The current active-learning selector is a deterministic baseline/fallback. It can consume learned embeddings, but the deterministic hashed text fallback and weighted score are not research claims.
- The account-model governance path now has immutable per-administrator approval rows; it still should be unified with the shared analysis governance service to avoid long-term duplicate governance surfaces.
- Chinese RoBERTa/BotRHG training can now consume approved corpus exports, but a full active-round retraining run on accumulated Chinese labels is not yet completed in this pass.
- Frozen holdout leakage checks and active-learning efficiency report utilities exist, but real time-forward/platform/community-disjoint reports and signed experiment artifacts are still required before publication claims.
- SelectiveNet-style learned rejection, energy-based OOD, BADGE gradient acquisition, Croissant metadata, and automatic card generation are documented future upgrade paths, not current implemented capabilities.

## Verification

```powershell
$env:PYTHONPATH='G:\CISCN\CogGuard\.worktrees\refactor-system\system;G:\CISCN\CogGuard\.worktrees\refactor-system\system\backend'
.\system\backend\.venv\Scripts\python.exe -m pytest system\backend\tests\test_account_active_learning.py system\research\social_bot_detection\tests\test_active_learning.py -q
```

Latest targeted result: `20 passed, 6 skipped, 2 warnings`.
