---
status: accepted
date: 2026-09-02
supersedes: ADR-0004
---

# ADR 0010: Student Review Runtime And Distillation

## Context

The implemented Student line uses an XLM-R encoder, multi-head classification, latent rationale alignment, and uncertainty-based hardcase mining. ADR 0004 instead required a dedicated `defer` head and rejected rationale distillation, so it no longer describes the selected implementation.

## Decision

Student Review uses one checkpoint-gated XLM-R runtime with `attack_hate_offense`, `misinfo_claim_risk`, and `stance` prediction heads plus a configurable `rationale_proj` used only during distillation. `ReviewStudentInput` serializes post text, claim context, and available Decodable Evidence text through one shared training and inference contract.

Hardcase routing is outside the model. It combines classification uncertainty with governance signals and may request Teacher Review; there is no dedicated `defer` head. Teacher rationale embeddings and soft labels are offline training targets, not generated product text.

An approved compatible checkpoint is required for product inference. Missing, unapproved, or incompatible checkpoints produce `shadow_untrained` and `abstain`; the runtime must not return a product judgment from randomly initialized weights.

## Consequences

- Model definition and inference live in `system/runtimes/review_student`.
- Losses, datasets, hardcase mining, and staged training live in `system/research/review_student`.
- Student Review remains preliminary; only analyst confirmation creates a canonical decision.
- `Selective Student` is a deprecated alias and must not name the canonical implementation.
