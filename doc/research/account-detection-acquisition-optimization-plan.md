# Account Detection Acquisition Optimization Plan

Updated: 2026-08-04

This plan upgrades the **Chinese Account Detection Active Learning Loop** from a deterministic acquisition baseline to a research-grade acquisition stack. The previous weighted selector has been removed from system code.

## Position

The deployed acquisition line is now strict:

- Cold start uses local Chinese masked-language-model ALPS embeddings and Core-set farthest-first selection.
- Warm start uses calibrated BotRHG probabilities and BADGE classifier-gradient embeddings.
- If the required local model path, calibration metadata, or BADGE vectors are missing, the system fails closed instead of producing a pseudo research batch.

The older weighted policies are not claimable acquisition methods and are no longer retained in the runtime selector. Baseline comparisons should be implemented in experiment scripts, not in the product acquisition path.

The research upgrade should be staged:

1. **Cold-Start Acquisition**: local Chinese MLM ALPS surprisal embeddings plus Core-set.
2. **Warm-Start Acquisition**: calibrated uncertainty plus BADGE gradient embeddings from the internal BotRHG classifier.
3. **Candidate Extensions**: committee disagreement, contrastive neighbor acquisition, energy OOD, and learned loss/meta acquisition.
4. **Activation Evidence**: equal-budget label-efficiency curves and leakage-safe evaluation.

## Literature-Grounded Upgrade Map

| Area | Primary references | What to implement | What it proves |
| --- | --- | --- | --- |
| Cold-start surprisal | ALPS, EMNLP 2020; Chinese RoBERTa/WWM | Use a local Chinese masked language model to compute account-level token surprisal. | The system can select informative examples before a reliable classifier exists. |
| Cold-start coverage | Core-set, ICLR 2018; Google k-center implementation | Run k-center greedy over Chinese RoBERTa/BotRHG embeddings. | The selected batch covers the account representation space instead of over-sampling one cluster. |
| Warm-start uncertainty | Lewis & Gale; Guo calibration; transformer AL studies | Use calibrated entropy/margin/least-confidence only after ECE gate passes. | Model uncertainty is a valid acquisition signal, not raw confidence theater. |
| Warm-start BADGE | BADGE, ICLR 2020; BADGE code | Extract gradient embeddings from the local account classifier and select diverse uncertain accounts. | Warm-start selection jointly captures uncertainty and diversity without manual weighted sums. |
| Disagreement | BatchBALD; Bayesian AL; ACTOR/ACAL for annotator-aware extensions | Compare Chinese RoBERTa, BotRHG, and optionally committee checkpoints; keep expensive BatchBALD as experiment candidate. | Disagreement adds value beyond single-model uncertainty only if equal-budget curves improve. |
| OOD | Hendrycks/Gimpel; Energy OOD; Ovadia shift | Compute energy or density OOD from logits/embeddings and cap its acquisition quota. | OOD supports safety review and drift discovery without overwhelming useful label acquisition. |
| Learned acquisition | Learning Loss; PLM AL; Practical Obstacles | Train a meta acquisition ranker only after multiple approved active rounds exist. | The system can learn which selected cases improve the next model, but only after enough round history exists. |
| Evaluation | Active Learning for BERT; Practical Obstacles; transferability/fragility studies | Compare random, uncertainty, core-set, ALPS, BADGE, current policy, and candidate extensions at equal budgets. | Any default switch is justified by label-efficiency, not by method novelty. |

## Implementation Roadmap

### Phase 1: Replace Non-Claimable Signals

- Add `system/research/social_bot_detection/acquisition/representations.py`.
- Export account embeddings, logits, calibrated probabilities, and optional gradients from the local Chinese RoBERTa/BotRHG model.
- Remove hashed text embedding from acquisition code and research reports.
- Add local Chinese MLM surprisal scoring for cold-start cases.

### Phase 2: Strong Baselines

- Add `acquisition/cold_start.py` with ALPS-style surprisal and k-center core-set.
- Add `acquisition/warm_start.py` with calibrated uncertainty and BADGE.
- Keep only strict system strategies: `cold_start_alps_core_set` and `warm_start_calibrated_uncertainty_badge`.
- Compare `random`, `uncertainty`, `core_set`, `alps_core_set`, and `badge` in offline experiment scripts.

### Phase 3: Candidate Extensions

- Add capped OOD acquisition using energy score or embedding density.
- Add ensemble disagreement only when at least two model families or checkpoints are available.
- Add contrastive neighbor acquisition with near-duplicate safeguards.
- Defer learned loss/meta acquisition until at least three approved active rounds exist.

### Phase 4: Claim Gates

- Every strategy must report label-efficiency curves under identical budgets.
- Required splits: frozen holdout, time-forward, platform-stratified, and community-disjoint.
- Required metrics: macro F1, AUPRC, ECE, false-positive burden, coverage, and abstain rate.
- A strategy can become default only if it beats random, uncertainty, and core-set baselines with confidence intervals.

## Current Code Impact

| Current module | Keep / change | Reason |
| --- | --- | --- |
| `social_bot_detection/active_learning.py` | Strict selector only | Runtime strategies are `cold_start_alps_core_set` and `warm_start_calibrated_uncertainty_badge`; no weighted selector remains. |
| `account_active_learning.py` | Strict adapter | It computes ALPS embeddings from `ACCOUNT_ACQUISITION_TEXT_MODEL_PATH` in cold start and passes calibrated BotRHG BADGE payloads in warm start. |
| `evaluate_active_round.py` | Extend | It already has holdout leakage and efficiency helpers; add full curve export. |
| `datasets.py` | Keep | `approved_account_corpus` is the correct training source for Chinese active rounds. |
| `account_model_governance_service.py` | Keep gates | Default acquisition changes still require persisted metrics and approval. |

## Claim Boundary

Claimable after Phase 2 plus experiments:

- "CogGuard implements a literature-grounded Chinese account active-learning loop with ALPS/core-set cold-start and BADGE warm-start candidates."
- "The acquisition method improves label efficiency over random/uncertainty/core-set on approved Chinese account labels" only if curves prove it.

Not claimable yet:

- "The current selector is a learned acquisition model."
- "OOD or disagreement always improves active learning."
- "Chinese social-media bot detection is solved across platforms."
- "The method is superior without frozen holdout and time-forward/community-disjoint reports."

## Local Preflight

Validated preflight artifact:

- `research-wiki/preflight_runs/20260804T152213Z-optimize-chinese-account-detection-active-learni/`
- Validation summary: `reference_count=17`, `verified_reference_count=17`, `omission_handling_count=3`.
