# Account Detection Acquisition Optimization Plan

Updated: 2026-08-04

This plan upgrades the current **Chinese Account Detection Active Learning Loop** from a deterministic acquisition baseline to a research-grade acquisition stack. The current weighted selector stays as a safe fallback and comparison baseline.

## Position

The current `cold_start_surprisal_diversity` and `uncertainty_disagreement_diversity` policies are not a learned acquisition method. They are auditable baseline policies that prevent unsafe behavior: no pseudo-labels, no uncalibrated uncertainty, and a fixed random audit slice.

The research upgrade should be staged:

1. **Cold-Start Acquisition**: local Chinese MLM surprisal plus embedding core-set.
2. **Warm-Start Acquisition**: calibrated uncertainty plus BADGE gradient embeddings.
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
- Remove hashed text embedding from research reports; keep it only as a runtime fallback marked `non_claimable`.
- Add local Chinese MLM surprisal scoring for cold-start cases.

### Phase 2: Strong Baselines

- Add `acquisition/cold_start.py` with ALPS-style surprisal and k-center core-set.
- Add `acquisition/warm_start.py` with calibrated uncertainty and BADGE.
- Keep current weighted selector as `heuristic_baseline`.
- Add budgeted strategies: `random`, `uncertainty`, `core_set`, `alps_core_set`, `badge`, `heuristic_baseline`.

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
| `social_bot_detection/active_learning.py` | Keep as baseline/fallback | It is auditable and safe, but not research-grade acquisition. |
| `account_active_learning.py` | Extend | It should pass embeddings/logits/gradients from active model artifacts. |
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
