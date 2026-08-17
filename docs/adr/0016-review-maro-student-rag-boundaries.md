# ADR 0016: Review Teacher, Text Student, And RAG Boundaries

- Status: Accepted for the current coding stage
- Date: 2026-08-15
- Scope: Review Teacher, Review Student, evidence retrieval, rationale supervision

## Context

CogGuard previously exposed several overlapping ideas under a broad multi-agent
review surface: harmfulness, claim verification, policy matching, rationale
distillation, and optional countermeasure generation. A single flat risk label
would hide the different observation units and would make a MARO result look
like a general content-moderation proof. Teacher confidence and free-form Agent
traces are also not stable Student supervision contracts.

## Decision

1. Keep two delivery lines. Review Student is a low-cost synchronous text model
   for independent task axes. Review Teacher is an analyst-triggered,
   asynchronous MARO-compatible advisory chain.
2. Use typed bundles instead of shared unbounded context:
   `EvidenceBundle` for claim evidence, `PolicyBundle` for active policy
   clauses, and `RationaleCapsule` for quality-gated auxiliary supervision.
3. Keep the Teacher chain task-scoped. Simple cases run necessary experts and one
   Judge. Complex cases add QuestionReflection and no more than two targeted
   responses before a task-specific Judge.
4. Separate `EvidenceRAG`, `PolicyRAG`, and `ReasonBank`. Policy text cannot
   establish factual support, and retrieval similarity cannot establish truth.
   `claim_assessment`, `retrieval_status`, and `evidence_relation` are separate
   typed states: `insufficient` is legal only after a checkable claim, completed
   retrieval, traceable sources, and quoted spans.
5. Do not use Teacher probabilities or confidence as Student targets. Allow
   fixed gold labels, quality-gated hard/structured labels, verified input spans,
   and rationale capsule embeddings as explicitly typed supervision only.
6. Countermeasure is a post-Judge, explicit-only internal advisory. It must
   preserve evidence and policy references, require human approval, and never
   auto-publish.
7. Multimodal consistency, raw image/video fusion, OCR/ASR/caption fusion,
   continuous pretraining, and live provider integration are later tracks. The
   current implementation does not claim those capabilities.
8. Student hard-case mining is an offline candidate-manifest operation, not a
   learned defer head and not an automatic production Teacher trigger.

## Consequences

- Review task labels remain orthogonal; there is no unified cognitive-risk
  target or product-level PASS/REVIEW/REJECT mapping in this boundary.
- Teacher reports remain useful for analyst audit while Student training uses
  only observable, quality-gated targets.
- RAG quality can be evaluated by retrieval, provenance, citation, relation,
  and policy-clause metrics independently of final classification.
- Missing input, provider failure, and zero relevant retrieval hits are exposed
  as audit states. They cannot become a factual-risk prediction or Student
  claim-deception supervision.
- Existing Coordination and Propagation modules remain separate and are not
  modified by this ADR.
- The current coding stage is not an experiment result and must not be used to
  claim model accuracy, generalization, or Teacher cost reduction.

## Verification

- Contract tests cover serialization and task-specific rationale gating.
- Runtime tests cover task normalization, capability filtering, explicit-only
  Countermeasure, and the two-response cap.
- Static checks must pass without dataset training, external LLM calls, or
  DeepSeek/API credentials.
