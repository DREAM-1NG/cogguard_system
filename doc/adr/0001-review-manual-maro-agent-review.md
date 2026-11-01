# ADR 0001: Review uses analyst-triggered MARO-style LLM agent reviews

Date: 2026-06-30

## Status

Partially superseded by ADR 0007. The manual-trigger-only product rule is
superseded; the evidence and advisory constraints remain current.

## Context

Review already has deterministic post-level detectors, review queues, local review execution, and a legacy local multi-agent runtime. The project now needs a real multi-agent layer inspired by MARO, RAMA, MAD-Sherlock, and D2D, but the intended use is analyst support rather than benchmark fitting or automatic final classification.

Automatically running LLM agents inside `/risk/assess` would blur capability boundaries: the Agent layer could be mistaken for a trainable classifier, could add non-reproducible costs to every assessment, and could encourage optimizing LLM reports against dataset labels.

## Decision

Review LLM agents are analyst-triggered, not automatic. `/risk/assess` generates deterministic detector outputs, review queues, and suggested agents, but does not call LLM agents by default.

The manual review endpoint writes natural-language role-specific analysis reports into the persisted risk report JSON under `agent_reviews`. Agent report bodies are not structured classifier outputs. Each report keeps minimal audit metadata: `run_id`, `agent_name`, `model`, `input_refs`, `input_hash`, `status`, `created_at`, and `human_triggered_by`.

The first online Agent set is:

- `PostHarmAgent`
- `MultimodalConsistencyAgent`
- `ClaimEvidenceAgent`
- `PropagationTreeAgent`
- `QuestionReflectionAgent`
- `HarmfulnessJudgeAgent`
- `CountermeasureAgent`

`HarmfulnessJudgeAgent` provides an advisory judgment for human confirmation. `CountermeasureAgent` generates evidence-bound response plans and drafts, not auto-published content.

## Consequences

- Review Agent quality is evaluated by auditability, evidence use, uncertainty reporting, and human review usefulness, not by macro-F1 on PHEME/FakeSV/MultiOFF.
- Dataset metrics remain the responsibility of the underlying detectors and encoders.
- LLM provider failures are recorded as failed agent reviews; the system does not synthesize fake natural-language reports from local rules.
- The legacy deterministic multi-agent runtime remains available only through an explicit compatibility switch.

## Rejected Alternatives

- Automatic LLM Agent execution in `/risk/assess` | Rejected because it adds non-reproducible cost and conflicts with human-in-the-loop review.
- Agent reports as JSON classifier payloads | Rejected because MARO-style expert agents should provide natural-language analysis reports for analysts and Judge synthesis.
- Fitting Agent decisions to benchmark labels | Rejected because Review Agents are a review and explanation layer, not a trainable detector.

## Verification

Test with mock providers that manual review creates natural-language reports, records failures without synthetic fallback, and leaves `/risk/assess` deterministic by default.
