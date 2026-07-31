---
status: accepted
date: 2026-07-20
---

# Review First-Stage Student Boundary

## Context

Risk Review now has two execution layers:

- Offline teacher: an analyst-triggered, MARO-style multi-agent reviewer. It is expensive and should run on hard cases only.
- Online student: a low-latency encoder classifier for deployment and large-batch screening.

The previous student boundary was too broad because it suggested learning rationale summaries and fine-grained governance labels directly. For an encoder student such as `XLM-R-base` or `hfl/chinese-roberta-wwm-ext`, that target is not the right first-stage deployment shape.

## Decision

The first-stage student uses a shared `2+1` semantic triage protocol:

- `attack_hate_offense`: attack, hate, harassment, or offensive language risk.
- `misinfo_claim_risk`: misinformation, claim, rumor, or veracity risk.
- `stance`: claim-linked auxiliary head only; samples without claim context are masked out.

Selective routing is a separate `defer` head. It learns whether a case should be escalated to the teacher/human review path, instead of mixing uncertainty into the two semantic risk heads.

The student input is `post_text + claim_context`. The main multilingual research line is `XLM-R-base`; the Chinese deployment branch is `hfl/chinese-roberta-wwm-ext`. Both branches use the same labels, metrics, and output schema.

## Teacher Silver

The offline teacher exports `review-teacher-silver-v1` as structured JSON:

- `case_id`
- `main_axes`
- `stance`
- `fine_labels`
- `confidence`
- `review_reason`
- `evidence_spans`
- `trace_refs`
- `sample_mode`

Full multi-agent traces are retained only for `sample_mode=hard_case`. Ordinary samples keep structured summaries only. The student consumes this structured signal as auxiliary supervision and audit context, not as natural-language report text.

## Consequences

- `rationale summary` is not a first-stage student target.
- `harm_types`, target groups, amplification patterns, and countermeasure advice remain teacher-side sidecar/audit fields for now.
- Gold labels remain the primary target; teacher silver provides confidence, defer supervision, and hard-case routing cues.
- Online review APIs remain unchanged. The teacher remains analyst-triggered; the student remains an offline training artifact and future deployment classifier.

## Rejected

- Distilling full natural-language multi-agent reports into the encoder student: rejected because it would turn an encoder classifier into a weak report generator target and would be hard to evaluate.
- Training all fine-grained governance labels in phase one: rejected because local labels are uneven across datasets and would make the first-stage student over-claim coverage.
- Using `XLM-T` as the first backbone: deferred because it is not present in the local cache and is not required to establish the first reproducible student line.
