---
status: accepted
date: 2026-08-04
---

# ADR 0010: Review Teacher-Student Delivery Lines

## Context

Risk Review needs to cover social-media governance cases with two conflicting
requirements:

- complex and high-impact cases need evidence-rich, auditable multi-agent
  analysis;
- routine online screening needs low latency, stable cost, and reproducible
  model behavior.

The current codebase already has a MARO-style Review Agent runtime,
`review-teacher-silver-v1` export, and a `2+1` ReviewStudent training path.
Keeping these as one undifferentiated "agent model" would make the system slow,
hard to evaluate, and unclear about which component is responsible for
classification, escalation, reporting, and future optimization.

## Decision

Risk Review adopts two explicit delivery lines.

### MultiAgents

`MultiAgents` is the complex/hard-case teacher and reviewer line. It is used
for analyst-triggered or automatically escalated hard cases, including low
confidence, cross-view conflict, claim-linked uncertainty, evidence gaps, and
high-impact governance samples.

Its responsibilities are:

- generate expert analysis reports for content harm, claim/evidence,
  multimodal consistency, propagation context, and countermeasure planning;
- run MARO-style question reflection before final advisory judgment when the
  case is complex;
- produce auditable natural-language review reports and structured sidecars;
- export `review-teacher-silver-v1` rows for offline training;
- collect error memory and candidate rule hints for offline policy refinement.

It does not replace the deployable classifier, does not auto-publish
countermeasures, and does not directly optimize benchmark labels during normal
review runs.

### ReviewStudent

`ReviewStudent` is the deployable online triage line. The target method uses
dataset-supervised fine-tuning plus distillation from valid MultiAgents teacher
predictions. The first stage remains an encoder-based `2+1` task:

- `attack_hate_offense`;
- `misinfo_claim_risk`;
- claim-linked `stance` as an auxiliary head.

Selective routing is a separate `defer/review_required` head. It decides when a
sample should escalate to MultiAgents or human review, rather than mixing
uncertainty into the two semantic risk axes.

The default research backbone is `XLM-R-base`; the Chinese deployment branch is
`hfl/chinese-roberta-wwm-ext`. `XLM-T` remains a later social-media-domain
comparison candidate.

## Consequences

Positive:

- The system can claim both a high-quality review capability and a deployable
  low-latency moderation classifier without confusing their evidence standards.
- MultiAgents can stay expensive because it only runs on hard cases and teacher
  sampling batches.
- ReviewStudent and MultiAgents can be compared on the same structured Judge
  labels with standard classification and calibration metrics. MultiAgents is
  additionally evaluated for evidence use, auditability, review usefulness,
  latency, and cost.
- Teacher outputs become structured supervision and audit traces, not
  unbounded text that the student must imitate.

Negative:

- The project now has two evaluation loops: one for agent review quality and one
  for student model performance.
- Distillation claims require enough teacher-silver coverage; a small smoke set
  proves integration only, not distillation benefit.
- Deployment must maintain a routing boundary so Student outputs never become
  canonical decisions without the configured review and approval path.

## Implementation Notes

- MultiAgents teacher experiments write `agent_predictions.jsonl`,
  `teacher_silver.jsonl`, and suite-level `report.json`.
- Event Review Case asynchronous Teacher jobs use the same MARO runtime when an
  active provider is available. The deterministic Teacher DAG is a continuity
  fallback only and is marked non-claimable.
- The current baseline freezes XLM-R, extracts CLS features, and trains only the
  selective multi-task head. It is not end-to-end XLM-R SFT.
- ReviewStudent may consume only `review-teacher-silver-v1` rows with
  `distillation_eligible=true`; dataset gold is isolated from the Agent prompt
  and from the teacher prediction fields.
- The target end-to-end training reports `Macro-F1`, `PR-AUC`, `ECE`,
  `coverage-risk`, `high-risk recall`, and defer quality.
- MultiAgents and ReviewStudent share one MARO-style `2+1` benchmark protocol:
  HateXplain/MultiOFF map to `attack_hate_offense`, PHEME/mcfend/FakeSV map to
  `misinfo_claim_risk`, and claim-linked stance remains auxiliary. Horizontal
  results require the identical `case_id + dataset + split` population.
- Comparison gold is read only from source cases. MultiAgent predictions enter
  the primary table only when the current structured Judge footer is valid and
  `teacher_silver.distillation_eligible=true`; legacy smoke rows remain runtime
  evidence. MultiAgent `review_required` and Student `defer/abstain` are routing
  coverage metrics and are reported separately from raw classification.
- `build_review_maro_case_manifest.py` creates a deterministic, stratified,
  gold-free population manifest. `compare_review_maro_systems.py` writes
  per-axis, per-dataset, and strictly paired comparison results.
- The fixed first formal protocol uses three mutually exclusive populations:
  `500` balanced test cases (`100` per dataset) for paired MultiAgent/Student
  comparison, `1,000` train cases (`200` per dataset) for Teacher Silver, and
  `1,000` validation tasks (`500` per semantic axis) for rule refinement.
  `build_review_maro_experiment_protocol.py` derives all three with the same
  dataset split policy as the Student runner, exports no gold, and fails on
  population overlap or shortfall.
- The next meaningful teacher-silver pilot should sample hard cases by dataset,
  risk axis, language, modality availability, claim linkage, and current
  Student uncertainty/error type.
- Teacher Silver pilots should be staged: `15` total cases remain interface
  smoke only, approximately `50` per dataset is a schema/coverage pilot, and a
  distillation-effect claim requires a balanced learning curve with at least
  hundreds of valid hard cases and an untouched target-domain test set.
- Full natural-language rationales and countermeasure drafts remain teacher-side
  artifacts. The student may consume evidence spans and confidence/defer signals
  but does not learn report generation in the first stage.

## Rejected

- Run MultiAgents for every online sample | Rejected because cost and latency
  are not compatible with social-media screening.
- Distill full free-form multi-agent reports into the encoder | Rejected because
  an encoder student should learn structured classification and routing signals,
  not become a weak report generator.
- Treat a 15-case teacher smoke set as sufficient distillation data | Rejected
  because it validates integration only; real distillation requires hundreds to
  thousands of balanced hard cases.
- Merge `defer` into the harmfulness labels | Rejected because escalation is a
  routing decision with its own risk-coverage objective.

## Verification

- Current hard-case teacher smoke completed 15/15 cases across HateXplain,
  MultiOFF, PHEME, mcfend, and FakeSV, proving runtime integration only. Those
  historical rows predate the structured Judge footer and are not valid
  distillation supervision.
- The current code supports a five-dataset frozen-XLM-R feature evaluation with
  reloadable selective-head checkpoints and encoder provenance. End-to-end SFT,
  response/logit distillation, and RL are not yet claimed complete.
- Teacher confidence can now supervise a probability target mixed with dataset
  labels by `distillation_alpha`. Because the encoder remains frozen, this is
  confidence-weighted soft-target distillation into the multi-task head, not
  end-to-end XLM-R distillation.
- The strict v3 baseline at
  `G:\CISCN\.tmp\review_student_xlmr_full_v3_20260805` passed artifact checks
  for all five datasets and emitted `9,699` test predictions. It is blocked from
  deployment because three datasets abstain on every test case and high-risk
  recall is zero on four datasets.
- Teacher silver now requires a validated structured Judge prediction and
  explicitly blocks rows that lack one; targeted Review regression tests pass.
