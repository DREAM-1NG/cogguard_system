# Risk Review MARO-style Self-Iteration Implementation Note

Date: 2026-07-01

## Position

Risk Review self-iteration is implemented as a governed policy-refinement loop, not as online autonomous self-modification. The Agent layer remains analyst-triggered. `/risk/assess` still produces detector outputs, review queues, and suggested Agents without calling LLMs.

The engineering target is:

```text
expert Agent reports
-> QuestionReflection / human feedback
-> feedback and error memory
-> DecisionRuleOptimizerAgent-style rule candidates
-> deterministic schema validation
-> validation split evaluation
-> multi-round rule refinement
-> held-out audit
-> candidate policy
-> explicit human activation
-> HarmfulnessJudgeAgent advisory report under active policy
```

## Research Alignment

| Research cluster | Core idea | Risk Review implementation | Boundary |
|---|---|---|---|
| MARO, EMNLP 2025 | Multi-dimensional experts, question-reflection, automated decision rule optimization | `refine_review_agent_policy_loop` runs error analysis, rule proposal, deterministic evaluation, policy revision, and held-out audit | Not a full reproduction; rule generator is pluggable and guarded |
| RAMA, 2025 | Retrieval-augmented multi-agent verification | `retrieve_active_evidence` performs claim-to-query, query refinement, local-first evidence aggregation, source quality, and conflict re-query | External retrieval is optional and off by default |
| MAD-Sherlock | Multimodal debate and out-of-context reasoning | `enable_full_debate` supports high-conflict multimodal debate transcripts | No visual OOC web search by default |
| D2D, EMNLP 2025 | Multi-stage debate/debunking with judge synthesis | Full debate stages include opening, rebuttal, free debate, closing, and judge synthesis | No auto-publication of debunking or counter-narrative |

## Code Mapping

| Functionality | Code |
|---|---|
| Feedback memory summary | `system/backend/app/core/risk/review_agent_policy.py::summarize_feedback_memory` |
| Policy error analysis | `system/backend/app/core/risk/review_agent_policy.py::analyze_policy_errors` |
| MARO-style refinement loop | `system/backend/app/core/risk/review_agent_policy.py::refine_review_agent_policy_loop` |
| Human feedback API | `POST /api/v1/risk/review/agent-feedback/record` |
| Policy refinement API | `POST /api/v1/risk/review/policies/refine` |
| Policy activation API | `POST /api/v1/risk/review/policies/{policy_id}/activate` |
| Judge policy coupling | `system/backend/app/core/risk/review_agent_review.py::_policy_guidance_for_prompt` |
| RAMA-style active retrieval | `system/backend/app/core/risk/review_active_retrieval.py::retrieve_active_evidence` |
| Full debate | `system/backend/app/core/risk/review_active_retrieval.py::build_full_debate_trace` |

## Input and Output

Policy refinement input:

```json
{
  "dataset_manifest": {
    "dataset_id": "review-validation",
    "splits": {
      "validation": [{"case_id": "v1", "gold_label": "harmful", "harm_score": 0.72}],
      "held_out": [{"case_id": "h1", "gold_label": "non_harmful", "harm_score": 0.21}]
    }
  },
  "feedback_report_ids": ["report-id"],
  "baseline_policy_id": "optional-policy-id",
  "max_iterations": 3,
  "enable_llm_rule_generator": false,
  "held_out_required": true
}
```

Policy refinement output includes:

- `candidate_rules`
- `refinement_trace`
- `error_memory_summary`
- `validation_metrics_by_round`
- `held_out_audit`
- `activation_status`
- `can_activate`
- `non_activatable_reasons`

Agent review input adds:

- `enable_full_debate`
- `debate_max_rounds`
- `active_policy_id`

Agent review sidecar adds:

- `active_policy_id`
- `policy_rule_refs`
- `debate_mode`
- `full_debate_trace_refs`
- `retrieval_refinement_trace`

## MARO Output Alignment

MARO's expert Agents primarily produce natural-language or semi-structured
analysis reports. Risk Review follows that boundary after the 2026-07-01 alignment:

```text
Agent primary output = analysis_report.text
System metadata = system_audit_sidecar
Backward-compatible alias = structured_sidecar
```

`system_audit_sidecar` is not treated as the Agent's judgement. It is generated
by the Risk Review service for reproducibility, UI display, retrieval provenance,
policy linkage, and failure auditing. The sidecar explicitly records:

```json
{
  "sidecar_role": "system_audit_not_agent_primary_output",
  "not_agent_primary_output": true,
  "primary_agent_output_ref": "analysis_report.text"
}
```

The Agent execution order is also closer to MARO:

```text
expert Agents produce initial analysis reports
-> QuestionReflectionAgent reads expert reports and asks/refines questions
-> expert Agents produce reflection-response reports
-> HarmfulnessJudgeAgent reads original reports, reflection responses, active policy, retrieval, and debate traces
-> CountermeasureAgent produces evidence-bound response advice
```

## Capability Claims

Supported:

- Validation-driven policy refinement.
- Human feedback/error memory entering the next refinement loop.
- Rejection of unsafe or invalid LLM-proposed policy fields.
- Held-out audit separation.
- Human-approved activation before active use.
- Judge report using active policy as advisory provenance.
- Optional high-conflict full debate transcript.
- Local-first active retrieval with query refinement and source-quality summary.

Not supported yet:

- Online autonomous policy activation.
- Training or fine-tuning the underlying post, video, or propagation-tree detector.
- Persistent feedback database and long-term active learning.
- Default external Web/RAG retrieval.
- Full visual out-of-context search or image provenance retrieval.
- Full MARO reproduction with cross-domain task generation.
