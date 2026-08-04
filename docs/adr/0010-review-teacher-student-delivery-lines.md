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

`ReviewStudent` is the deployable online triage line. It uses SFT plus
distillation from dataset gold labels and MultiAgents teacher silver. The first
stage remains an encoder-based `2+1` task:

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
- ReviewStudent can be evaluated with standard classification and calibration
  metrics, while MultiAgents is evaluated by evidence use, auditability, and
  review usefulness.
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
- ReviewStudent training consumes `review-teacher-silver-v1` plus original
  dataset labels and reports `Macro-F1`, `PR-AUC`, `ECE`, `coverage-risk`,
  `high-risk recall`, and defer quality.
- The next meaningful teacher-silver pilot should sample hard cases by dataset,
  risk axis, language, modality availability, claim linkage, and current
  Student uncertainty/error type.
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
  MultiOFF, PHEME, mcfend, and FakeSV.
- Current ReviewStudent full run consumed teacher silver across all five
  datasets and produced full evaluation reports for XLM-R and hash fallback.
- Targeted regression tests passed for ReviewStudent local snapshot resolution
  and Review Agent runtime behavior.
