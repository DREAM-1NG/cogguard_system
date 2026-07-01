# ADR 0002: KT3 MARO-style self-iteration uses auditable policy refinement

Date: 2026-07-01

## Status

Accepted

## Context

KT3 already supports analyst-triggered MARO-style natural-language Agent reviews. The remaining gap against MARO is self-iteration: rules, thresholds, review triggers, and Agent/Judge policies should not stay permanently hand-written.

The risk is that "self-iteration" can be misunderstood as online autonomous self-modification. For KT3, that is not acceptable: harmfulness characterization and countermeasure design remain human-in-the-loop, and detector outputs must remain unchanged by the Agent layer.

## Decision

KT3 implements self-iteration as validation-driven decision rule refinement:

```text
expert reports
-> human feedback / error memory
-> rule proposal
-> deterministic schema validation
-> validation evaluation
-> rule refinement loop
-> held-out audit
-> candidate policy
-> explicit human activation
-> Judge reads active policy as advisory provenance
```

The `DecisionRuleOptimizerAgent` capability is represented by rule proposal inputs in `refine_kt3_agent_policy_loop`. LLM-generated rules are proposals only. A deterministic evaluator validates schema, rejects unsafe fields, evaluates validation metrics, and reports held-out audit before a candidate policy can be activated.

## Consequences

- `/risk/assess` still does not call LLM Agents or self-modify policies.
- Candidate policies are stored in-process and marked `candidate_pending_human_approval`.
- `POST /api/v1/risk/kt3/policies/{policy_id}/activate` is required before a policy becomes active.
- `HarmfulnessJudgeAgent` receives active policy thresholds, accepted rule explanations, and provenance, but remains advisory.
- Human feedback is stored in `RiskAssessment.report_json.agent_feedback` for the first version.

## Research Alignment

- MARO: validation-driven automated decision rule optimization is implemented at the policy layer.
- RAMA: active retrieval adds claim-to-query, query refinement, source quality, and conflict re-query.
- MAD-Sherlock / D2D: optional full debate runs opening, rebuttal, free debate, closing, and judge synthesis on high-conflict cases.

## Rejected Alternatives

- Letting LLM directly write active policy | Rejected because it bypasses deterministic validation and human approval.
- Activating a refined policy automatically | Rejected because harmfulness decisions require human governance.
- Storing feedback in a new database table now | Rejected to avoid migration scope in the first implementation.
- Running full debate for every sample | Rejected because debate is expensive and should be reserved for high-conflict or low-confidence cases.

## Verification

Implemented tests cover policy refinement, invalid LLM rule rejection, feedback memory, explicit activation, Judge policy coupling, and optional full debate triggering.
