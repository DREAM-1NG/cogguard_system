"""MARO-style decision rule optimization for KT3 agent review.

This module optimizes the review/Judge policy only. It does not mutate detector
outputs and must be run on explicit validation splits, with held-out/gate data
kept for reporting.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from itertools import product
from typing import Any, Callable
import json


DEFAULT_POLICY = {
    "review_threshold": 0.52,
    "abstain_threshold": 0.45,
    "retrieval_threshold": 0.58,
    "countermeasure_threshold": 0.72,
    "trigger_conditions": {
        "retrieval_on_claim_uncertainty": True,
        "review_on_cross_view_conflict": True,
        "countermeasure_requires_human_review": True,
    },
    "report_template_constraints": {
        "require_platform_reference": True,
        "require_evidence_sufficiency": True,
        "require_human_confirmation_items": True,
        "countermeasure_internal_only": True,
    },
    "agent_weights": {
        "PostHarmAgent": 0.22,
        "MultimodalConsistencyAgent": 0.16,
        "ClaimEvidenceAgent": 0.20,
        "PropagationTreeAgent": 0.14,
        "QuestionReflectionAgent": 0.10,
        "HarmfulnessJudgeAgent": 0.12,
        "CountermeasureAgent": 0.06,
    },
}


def optimize_kt3_agent_policy(dataset_manifest: dict[str, Any]) -> dict[str, Any]:
    """Optimize a review policy from explicit validation cases."""
    splits = dataset_manifest.get("splits") or {}
    validation_cases = _as_list(splits.get("validation"))
    held_out_cases = _as_list(splits.get("held_out") or splits.get("gate") or splits.get("test"))
    baseline_policy = _normalize_policy(dataset_manifest.get("baseline_policy") or DEFAULT_POLICY)
    if not validation_cases:
        raise ValueError("KT3 policy optimization requires splits.validation cases")

    candidates = _candidate_policies(baseline_policy)
    scored = [_score_policy(policy, validation_cases) for policy in candidates]
    best = max(scored, key=lambda item: item["objective_score"])
    held_out = _score_policy(best["policy"], held_out_cases) if held_out_cases else None
    baseline = _score_policy(baseline_policy, validation_cases)
    policy_id = _policy_id(dataset_manifest, best["policy"])
    return {
        "schema_version": "kt3-agent-policy-v1",
        "policy_id": policy_id,
        "created_at": _utc_now(),
        "policy": best["policy"],
        "optimization": {
            "method": "validation_grid_search_review_policy",
            "objective": "macro_f1_minus_abstain_penalty_plus_review_precision",
            "validation_cases": len(validation_cases),
            "held_out_cases": len(held_out_cases),
            "validation_metrics": best["metrics"],
            "baseline_metrics": baseline["metrics"],
            "held_out_metrics": held_out["metrics"] if held_out else None,
            "candidate_count": len(candidates),
        },
        "capability_boundary": {
            "optimizes_review_policy_only": True,
            "does_not_modify_detector_outputs": True,
            "validation_split_required": True,
            "held_out_not_used_for_optimization": True,
            "human_feedback_reserved_for_active_learning": True,
        },
        "dataset_manifest_summary": {
            "dataset_id": dataset_manifest.get("dataset_id") or dataset_manifest.get("name"),
            "split_names": sorted(splits.keys()),
            "source": dataset_manifest.get("source"),
        },
        "activation_status": "candidate_pending_human_approval",
        "activated_by": None,
        "activated_at": None,
    }


def refine_kt3_agent_policy_loop(
    dataset_manifest: dict[str, Any],
    *,
    feedback_memory: list[dict[str, Any]] | None = None,
    baseline_policy: dict[str, Any] | None = None,
    max_iterations: int = 3,
    enable_llm_rule_generator: bool = False,
    rule_generator: Callable[..., Any] | None = None,
    held_out_required: bool = True,
) -> dict[str, Any]:
    """Run a MARO-style decision rule refinement loop.

    LLM-generated rules are treated as proposals only. Every candidate must
    pass schema validation and deterministic validation/held-out evaluation
    before it can be stored as an activation candidate.
    """
    splits = dataset_manifest.get("splits") or {}
    validation_cases = _as_list(splits.get("validation"))
    held_out_cases = _as_list(splits.get("held_out") or splits.get("gate") or splits.get("test"))
    if not validation_cases:
        raise ValueError("KT3 policy refinement requires splits.validation cases")
    if held_out_required and not held_out_cases:
        raise ValueError("KT3 policy refinement requires a held-out/gate split when held_out_required=true")

    current_policy = _normalize_policy(
        baseline_policy
        or dataset_manifest.get("baseline_policy")
        or DEFAULT_POLICY
    )
    max_iterations = max(1, min(int(max_iterations or 1), 8))
    feedback_summary = summarize_feedback_memory(feedback_memory or [])
    candidate_rules: list[dict[str, Any]] = []
    refinement_trace: list[dict[str, Any]] = []
    metrics_by_round: list[dict[str, Any]] = []

    baseline_score = _score_policy(current_policy, validation_cases)
    metrics_by_round.append(
        {
            "round": 0,
            "stage": "baseline",
            "policy": current_policy,
            "metrics": baseline_score["metrics"],
            "objective_score": baseline_score["objective_score"],
        }
    )

    for iteration in range(1, max_iterations + 1):
        round_errors = analyze_policy_errors(current_policy, validation_cases)
        round_start = _score_policy(current_policy, validation_cases)
        proposals: list[dict[str, Any]] = []
        proposal_failures: list[dict[str, Any]] = []

        if enable_llm_rule_generator:
            try:
                if rule_generator is None:
                    raise ValueError("DecisionRuleOptimizerAgent requires an active text_llm provider")
                else:
                    proposals.extend(
                        _normalize_rule_generator_output(
                            rule_generator(
                                iteration=iteration,
                                current_policy=current_policy,
                                error_summary=round_errors,
                                feedback_summary=feedback_summary,
                                validation_metrics=round_start["metrics"],
                                held_out_audit=_score_policy(current_policy, held_out_cases)["metrics"] if held_out_cases else None,
                                historical_rules=[
                                    {
                                        "rule_id": item.get("rule_id"),
                                        "source": item.get("source"),
                                        "description": item.get("description"),
                                        "status": item.get("status"),
                                        "objective_score": item.get("objective_score"),
                                    }
                                    for item in candidate_rules[-12:]
                                    if isinstance(item, dict)
                                ],
                            )
                        )
                    )
            except Exception as exc:
                if not proposals:
                    raise
                proposal_failures.append(
                    {
                        "source": "DecisionRuleOptimizerAgent",
                        "status": "failed",
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )

        proposals.extend(_deterministic_rule_candidates(current_policy, round_errors, feedback_summary, iteration))
        evaluated_rules = []
        best_round_score = round_start
        best_round_rule_id = None
        best_round_policy = current_policy

        for index, raw_rule in enumerate(proposals):
            rule_record = _prepare_rule_record(raw_rule, iteration=iteration, index=index)
            validation = _validate_rule_candidate(rule_record, current_policy)
            if not validation["valid"]:
                rule_record.update(
                    {
                        "status": "rejected_schema",
                        "rejection_reasons": validation["errors"],
                    }
                )
                candidate_rules.append(rule_record)
                evaluated_rules.append(rule_record)
                continue

            candidate_policy = validation["policy"]
            scored = _score_policy(candidate_policy, validation_cases)
            rule_record.update(
                {
                    "status": "evaluated",
                    "candidate_policy": candidate_policy,
                    "validation_metrics": scored["metrics"],
                    "objective_score": scored["objective_score"],
                    "objective_delta": round(scored["objective_score"] - round_start["objective_score"], 6),
                }
            )
            if scored["objective_score"] > best_round_score["objective_score"]:
                best_round_score = scored
                best_round_rule_id = rule_record["rule_id"]
                best_round_policy = candidate_policy
            candidate_rules.append(rule_record)
            evaluated_rules.append(rule_record)

        accepted = best_round_rule_id is not None
        if accepted:
            current_policy = best_round_policy
            for rule in evaluated_rules:
                if rule.get("rule_id") == best_round_rule_id:
                    rule["status"] = "accepted_for_round"
                    break
        round_after = _score_policy(current_policy, validation_cases)
        metrics_by_round.append(
            {
                "round": iteration,
                "stage": "refinement",
                "policy": current_policy,
                "metrics": round_after["metrics"],
                "objective_score": round_after["objective_score"],
                "accepted_rule_id": best_round_rule_id,
            }
        )
        refinement_trace.append(
            {
                "round": iteration,
                "error_analysis": round_errors,
                "proposal_failures": proposal_failures,
                "rules_considered": [rule.get("rule_id") for rule in evaluated_rules],
                "accepted_rule_id": best_round_rule_id,
                "policy_changed": accepted,
                "validation_before": round_start["metrics"],
                "validation_after": round_after["metrics"],
            }
        )
        if not accepted:
            break

    held_out_audit = _score_policy(current_policy, held_out_cases) if held_out_cases else None
    final_validation = _score_policy(current_policy, validation_cases)
    non_activatable_reasons = []
    if held_out_required and held_out_audit is None:
        non_activatable_reasons.append("missing_held_out_audit")
    if final_validation["metrics"]["coverage_risk"]["coverage"] <= 0:
        non_activatable_reasons.append("zero_validation_coverage")
    policy_id = _refined_policy_id(dataset_manifest, current_policy, refinement_trace, feedback_summary)
    return {
        "schema_version": "kt3-agent-policy-refinement-v1",
        "policy_id": policy_id,
        "created_at": _utc_now(),
        "policy": current_policy,
        "candidate_rules": candidate_rules,
        "refinement_trace": refinement_trace,
        "error_memory_summary": feedback_summary,
        "validation_metrics_by_round": metrics_by_round,
        "held_out_audit": held_out_audit["metrics"] if held_out_audit else None,
        "optimization": {
            "method": "maro_style_decision_rule_optimizer_agent_loop",
            "objective": "macro_f1_minus_abstain_penalty_plus_review_precision",
            "validation_cases": len(validation_cases),
            "held_out_cases": len(held_out_cases),
            "max_iterations": max_iterations,
            "iterations_executed": len(refinement_trace),
            "llm_rule_generator_enabled": bool(enable_llm_rule_generator),
            "deterministic_evaluator": True,
            "baseline_metrics": baseline_score["metrics"],
            "final_validation_metrics": final_validation["metrics"],
        },
        "activation_status": "candidate_pending_human_approval",
        "activated_by": None,
        "activated_at": None,
        "can_activate": not non_activatable_reasons,
        "non_activatable_reasons": non_activatable_reasons,
        "capability_boundary": {
            "decision_rule_optimizer_agent": True,
            "agent_proposes_rules_only": True,
            "deterministic_schema_validation_required": True,
            "does_not_modify_detector_outputs": True,
            "held_out_not_used_for_optimization": True,
            "human_approval_required_for_activation": True,
            "online_auto_rewrite_disabled": True,
        },
        "dataset_manifest_summary": {
            "dataset_id": dataset_manifest.get("dataset_id") or dataset_manifest.get("name"),
            "split_names": sorted(splits.keys()),
            "source": dataset_manifest.get("source"),
        },
    }


def summarize_feedback_memory(feedback_memory: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize human audit feedback for the next refinement loop."""
    error_type_counts: dict[str, int] = {}
    corrected_label_counts: dict[str, int] = {}
    linked_reviews = set()
    evidence_refs = 0
    valid_feedback = 0
    for item in feedback_memory:
        if not isinstance(item, dict):
            continue
        valid_feedback += 1
        for error_type in _as_list(item.get("error_types")):
            key = str(error_type)
            error_type_counts[key] = error_type_counts.get(key, 0) + 1
        corrected = item.get("corrected_label") or item.get("corrected_harmfulness")
        if corrected:
            key = str(corrected)
            corrected_label_counts[key] = corrected_label_counts.get(key, 0) + 1
        review_ref = item.get("review_id") or item.get("run_id")
        if review_ref:
            linked_reviews.add(str(review_ref))
        evidence_refs += len(_as_list(item.get("evidence_refs")))
    return {
        "feedback_count": valid_feedback,
        "error_type_counts": error_type_counts,
        "corrected_label_counts": corrected_label_counts,
        "linked_review_count": len(linked_reviews),
        "evidence_ref_count": evidence_refs,
        "top_error_types": [
            {"error_type": key, "count": value}
            for key, value in sorted(error_type_counts.items(), key=lambda row: row[1], reverse=True)[:8]
        ],
    }


def analyze_policy_errors(policy: dict[str, Any], cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Return deterministic error analysis used by rule refinement."""
    predictions = [_predict_case(policy, case) for case in cases]
    rows = []
    counts = {
        "false_positive": 0,
        "false_negative": 0,
        "uncertain_when_labelled": 0,
        "low_confidence_correct": 0,
        "retrieval_needed_on_error": 0,
        "countermeasure_missed": 0,
    }
    for case, prediction in zip(cases, predictions):
        gold = _gold_label(case)
        pred = prediction["label"]
        if gold == pred:
            if prediction["confidence"] < 0.35:
                counts["low_confidence_correct"] += 1
            continue
        error_types = []
        if pred == "harmful" and gold == "non_harmful":
            counts["false_positive"] += 1
            error_types.append("false_positive")
        if pred == "non_harmful" and gold == "harmful":
            counts["false_negative"] += 1
            error_types.append("false_negative")
        if pred == "uncertain" and gold in {"harmful", "non_harmful"}:
            counts["uncertain_when_labelled"] += 1
            error_types.append("uncertain_when_labelled")
        if prediction["retrieval_required"]:
            counts["retrieval_needed_on_error"] += 1
            error_types.append("retrieval_needed_on_error")
        if gold == "harmful" and not prediction["countermeasure_recommended"] and _case_score(policy, case) >= 0.65:
            counts["countermeasure_missed"] += 1
            error_types.append("countermeasure_missed")
        rows.append(
            {
                "case_id": case.get("case_id") or case.get("id"),
                "gold_label": gold,
                "predicted_label": pred,
                "score": prediction["score"],
                "confidence": prediction["confidence"],
                "error_types": error_types,
            }
        )
    total_errors = len(rows)
    return {
        "case_count": len(cases),
        "error_count": total_errors,
        "error_rate": round(total_errors / len(cases), 6) if cases else 0.0,
        "counts": counts,
        "representative_errors": rows[:12],
    }


def apply_policy_to_agent_suggestions(
    suggestions: dict[str, Any],
    policy: dict[str, Any] | None,
) -> dict[str, Any]:
    """Attach policy metadata to manual suggestions without running agents."""
    if not policy:
        return suggestions
    active_policy = policy.get("policy") if "policy" in policy else policy
    weighted_agents = _normalize_policy(active_policy)["agent_weights"]
    ranked = sorted(weighted_agents.items(), key=lambda item: item[1], reverse=True)
    enriched = dict(suggestions)
    enriched["policy_recommendation"] = {
        "policy_id": policy.get("policy_id") if isinstance(policy, dict) else None,
        "activation_status": policy.get("activation_status") if isinstance(policy, dict) else None,
        "recommended_agents": [name for name, _weight in ranked[:4]],
        "agent_weights": weighted_agents,
        "review_threshold": active_policy.get("review_threshold"),
        "abstain_threshold": active_policy.get("abstain_threshold"),
        "retrieval_threshold": active_policy.get("retrieval_threshold"),
        "countermeasure_threshold": active_policy.get("countermeasure_threshold"),
        "does_not_execute_llm": True,
    }
    return enriched


def _deterministic_rule_candidates(
    current_policy: dict[str, Any],
    error_summary: dict[str, Any],
    feedback_summary: dict[str, Any],
    iteration: int,
) -> list[dict[str, Any]]:
    counts = error_summary.get("counts") or {}
    feedback_counts = feedback_summary.get("error_type_counts") or {}
    proposals: list[dict[str, Any]] = []
    if counts.get("false_negative", 0) + feedback_counts.get("false_negative", 0) > 0:
        proposals.append(
            {
                "source": "deterministic_error_analysis",
                "description": "Lower review threshold to catch missed harmful cases.",
                "policy_patch": {
                    "review_threshold": current_policy["review_threshold"] - 0.04,
                    "retrieval_threshold": current_policy["retrieval_threshold"] - 0.03,
                },
            }
        )
    if counts.get("false_positive", 0) + feedback_counts.get("false_positive", 0) > 0:
        proposals.append(
            {
                "source": "deterministic_error_analysis",
                "description": "Raise review threshold to reduce harmful over-calling.",
                "policy_patch": {
                    "review_threshold": current_policy["review_threshold"] + 0.04,
                    "abstain_threshold": current_policy["abstain_threshold"] + 0.02,
                },
            }
        )
    if counts.get("uncertain_when_labelled", 0) + feedback_counts.get("over_abstain", 0) > 0:
        proposals.append(
            {
                "source": "deterministic_error_analysis",
                "description": "Lower abstain threshold when too many labelled cases are unresolved.",
                "policy_patch": {
                    "abstain_threshold": current_policy["abstain_threshold"] - 0.04,
                },
            }
        )
    if counts.get("retrieval_needed_on_error", 0) > 0:
        proposals.append(
            {
                "source": "data_error",
                "description": "Trigger retrieval earlier for cases that failed under uncertainty.",
                "policy_patch": {
                    "retrieval_threshold": current_policy["retrieval_threshold"] - 0.04,
                    "trigger_conditions": {
                        "retrieval_on_claim_uncertainty": True,
                    },
                },
            }
        )
    if counts.get("countermeasure_missed", 0) + feedback_counts.get("countermeasure_missed", 0) > 0:
        proposals.append(
            {
                "source": "deterministic_error_analysis",
                "description": "Lower countermeasure trigger for high-score harmful cases.",
                "policy_patch": {
                    "countermeasure_threshold": current_policy["countermeasure_threshold"] - 0.04,
                },
            }
        )
    proposals.append(
        {
            "source": "validation_metric",
            "description": f"Round {iteration} conservative neighbor around current policy.",
            "policy_patch": {
                "review_threshold": current_policy["review_threshold"] + (0.02 if iteration % 2 == 0 else -0.02),
                "abstain_threshold": current_policy["abstain_threshold"],
                "retrieval_threshold": current_policy["retrieval_threshold"],
                "countermeasure_threshold": current_policy["countermeasure_threshold"],
            },
        }
    )
    proposals.append(
        {
            "source": "platform_template",
            "description": "Require governance reports to cite public platform reference basis and human confirmation items.",
            "policy_patch": {
                "report_template_constraints": {
                    "require_platform_reference": True,
                    "require_evidence_sufficiency": True,
                    "require_human_confirmation_items": True,
                    "countermeasure_internal_only": True,
                }
            },
        }
    )
    return proposals


def _normalize_rule_generator_output(raw: Any) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, str):
        parsed = json.loads(raw)
        return _normalize_rule_generator_output(parsed)
    if isinstance(raw, dict):
        if isinstance(raw.get("candidate_rules"), list):
            return [item for item in raw["candidate_rules"] if isinstance(item, dict)]
        return [raw]
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def _prepare_rule_record(raw_rule: dict[str, Any], *, iteration: int, index: int) -> dict[str, Any]:
    rule_id = str(raw_rule.get("rule_id") or f"rule-r{iteration}-{index}")
    source = _normalize_rule_source(raw_rule.get("source"))
    return {
        "rule_id": rule_id,
        "round": iteration,
        "source": source,
        "source_detail": str(raw_rule.get("source_detail") or raw_rule.get("source") or source),
        "description": str(raw_rule.get("description") or raw_rule.get("rationale") or ""),
        "policy_patch": raw_rule.get("policy_patch") or raw_rule.get("patch") or {},
        "raw_rule": raw_rule,
    }


def _validate_rule_candidate(rule: dict[str, Any], current_policy: dict[str, Any]) -> dict[str, Any]:
    patch = rule.get("policy_patch")
    if not isinstance(patch, dict):
        return {"valid": False, "errors": ["policy_patch_must_be_object"]}
    errors = []
    allowed = {
        "review_threshold",
        "abstain_threshold",
        "retrieval_threshold",
        "countermeasure_threshold",
        "agent_weights",
        "trigger_conditions",
        "report_template_constraints",
    }
    unknown = sorted(set(patch) - allowed)
    if unknown:
        errors.append(f"unknown_policy_fields:{','.join(unknown)}")
    candidate = {**current_policy}
    for key in ("review_threshold", "abstain_threshold", "retrieval_threshold", "countermeasure_threshold"):
        if key not in patch:
            continue
        value = _safe_float(patch.get(key), None)
        if value is None or not 0.0 < value < 1.0:
            errors.append(f"{key}_must_be_between_0_and_1")
        else:
            candidate[key] = value
    if "agent_weights" in patch:
        weights = patch.get("agent_weights")
        if not isinstance(weights, dict):
            errors.append("agent_weights_must_be_object")
        else:
            known_agents = set(DEFAULT_POLICY["agent_weights"])
            unknown_agents = sorted(set(weights) - known_agents)
            if unknown_agents:
                errors.append(f"unknown_agent_weights:{','.join(unknown_agents)}")
            candidate["agent_weights"] = {**candidate.get("agent_weights", {}), **weights}
    if "trigger_conditions" in patch:
        trigger_conditions = patch.get("trigger_conditions")
        if not isinstance(trigger_conditions, dict):
            errors.append("trigger_conditions_must_be_object")
        else:
            candidate["trigger_conditions"] = {
                **(candidate.get("trigger_conditions") or {}),
                **{
                    str(key): bool(value)
                    for key, value in trigger_conditions.items()
                    if isinstance(key, str)
                },
            }
    if "report_template_constraints" in patch:
        constraints = patch.get("report_template_constraints")
        if not isinstance(constraints, dict):
            errors.append("report_template_constraints_must_be_object")
        else:
            candidate["report_template_constraints"] = {
                **(candidate.get("report_template_constraints") or {}),
                **{
                    str(key): bool(value)
                    for key, value in constraints.items()
                    if isinstance(key, str)
                },
            }
    if errors:
        return {"valid": False, "errors": errors}
    return {"valid": True, "errors": [], "policy": _normalize_policy(candidate)}


def _normalize_rule_source(value: Any) -> str:
    text = str(value or "").strip()
    allowed_sources = {
        "data_error",
        "human_feedback",
        "platform_template",
        "validation_metric",
        "DecisionRuleOptimizerAgent",
        "deterministic_error_analysis",
        "deterministic_neighbor_search",
    }
    if text in allowed_sources:
        return text
    lowered = text.lower()
    if "feedback" in lowered or "human" in lowered:
        return "human_feedback"
    if "platform" in lowered or "template" in lowered or "governance" in lowered:
        return "platform_template"
    if "metric" in lowered or "validation" in lowered:
        return "validation_metric"
    if "error" in lowered or "false_" in lowered:
        return "data_error"
    return "DecisionRuleOptimizerAgent"


def _candidate_policies(baseline: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    review_values = _nearby(baseline["review_threshold"], [0.46, 0.52, 0.58, 0.64])
    abstain_values = _nearby(baseline["abstain_threshold"], [0.38, 0.45, 0.52])
    retrieval_values = _nearby(baseline["retrieval_threshold"], [0.50, 0.58, 0.66])
    counter_values = _nearby(baseline["countermeasure_threshold"], [0.66, 0.72, 0.80])
    for review, abstain, retrieval, counter in product(
        review_values,
        abstain_values,
        retrieval_values,
        counter_values,
    ):
        policy = _normalize_policy(
            {
                **baseline,
                "review_threshold": review,
                "abstain_threshold": abstain,
                "retrieval_threshold": retrieval,
                "countermeasure_threshold": counter,
            }
        )
        candidates.append(policy)
    return candidates


def _score_policy(policy: dict[str, Any], cases: list[dict[str, Any]]) -> dict[str, Any]:
    if not cases:
        return {
            "policy": policy,
            "objective_score": 0.0,
            "metrics": _empty_metrics(),
        }
    predictions = [_predict_case(policy, case) for case in cases]
    labels = [_gold_label(case) for case in cases]
    macro_f1 = _macro_f1(labels, [row["label"] for row in predictions])
    accuracy = sum(1 for gold, pred in zip(labels, predictions) if gold == pred["label"]) / len(labels)
    abstain_rate = sum(1 for row in predictions if row["abstain"]) / len(predictions)
    review_required = [row for row in predictions if row["review_required"]]
    review_precision = (
        sum(1 for row in review_required if row["label"] != _gold_label(row["case"])) / len(review_required)
        if review_required
        else 0.0
    )
    retrieval_rate = sum(1 for row in predictions if row["retrieval_required"]) / len(predictions)
    counter_rate = sum(1 for row in predictions if row["countermeasure_recommended"]) / len(predictions)
    ece = _ece(labels, predictions)
    coverage_risk = _coverage_risk(labels, predictions)
    objective = macro_f1 - 0.12 * abstain_rate + 0.08 * review_precision - 0.05 * ece
    return {
        "policy": policy,
        "objective_score": round(objective, 6),
        "metrics": {
            "macro_f1": round(macro_f1, 6),
            "accuracy": round(accuracy, 6),
            "ece": round(ece, 6),
            "abstain_rate": round(abstain_rate, 6),
            "review_precision": round(review_precision, 6),
            "retrieval_trigger_rate": round(retrieval_rate, 6),
            "countermeasure_trigger_rate": round(counter_rate, 6),
            "coverage_risk": coverage_risk,
        },
    }


def _predict_case(policy: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    score = _case_score(policy, case)
    uncertainty = _case_uncertainty(case)
    abstain = score < policy["abstain_threshold"] or uncertainty >= 0.55
    if abstain:
        label = "uncertain"
    elif score >= policy["review_threshold"]:
        label = "harmful"
    else:
        label = "non_harmful"
    return {
        "case": case,
        "score": score,
        "confidence": round(max(0.0, min(1.0, abs(score - 0.5) * 2)), 6),
        "label": label,
        "abstain": abstain,
        "review_required": abstain or score >= policy["review_threshold"] or uncertainty >= 0.35,
        "retrieval_required": score >= policy["retrieval_threshold"] or uncertainty >= 0.4,
        "countermeasure_recommended": score >= policy["countermeasure_threshold"] and not abstain,
    }


def _case_score(policy: dict[str, Any], case: dict[str, Any]) -> float:
    scores = case.get("scores") or {}
    views = case.get("view_scores") or {}
    sidecar = case.get("structured_sidecar") or {}
    values = [
        _safe_float(scores.get("harm_score")),
        _safe_float(scores.get("final_score")),
        _safe_float(case.get("harm_score")),
        _safe_float(sidecar.get("confidence")),
    ]
    for value in views.values() if isinstance(views, dict) else []:
        values.append(_safe_float(value))
    weights = policy["agent_weights"]
    agent_scores = case.get("agent_scores") or {}
    weighted_agent = 0.0
    total_weight = 0.0
    if isinstance(agent_scores, dict):
        for agent, value in agent_scores.items():
            weight = _safe_float(weights.get(agent), 0.0)
            if weight <= 0:
                continue
            weighted_agent += weight * _safe_float(value, 0.5)
            total_weight += weight
    base_values = [value for value in values if value > 0]
    base = sum(base_values) / len(base_values) if base_values else 0.5
    if total_weight > 0:
        base = 0.65 * base + 0.35 * (weighted_agent / total_weight)
    return round(max(0.0, min(1.0, base)), 6)


def _case_uncertainty(case: dict[str, Any]) -> float:
    if case.get("abstain"):
        return 0.65
    reasons = case.get("review_reason") or case.get("uncertainties") or []
    if isinstance(reasons, str):
        reasons = [reasons]
    conflict = _safe_float(case.get("conflict_score"))
    return max(min(1.0, 0.1 * len(reasons)), min(conflict, 1.0))


def _gold_label(case: dict[str, Any]) -> str:
    label = (
        case.get("gold_label")
        or case.get("label")
        or case.get("harmfulness_label")
        or case.get("final_harmfulness")
        or "non_harmful"
    )
    label = str(label)
    if label in {"harmful", "non_harmful", "uncertain"}:
        return label
    if label in {"1", "true", "True", "harm"}:
        return "harmful"
    return "non_harmful"


def _macro_f1(labels: list[str], predictions: list[str]) -> float:
    classes = sorted(set(labels) | set(predictions) | {"harmful", "non_harmful"})
    scores = []
    for cls in classes:
        tp = sum(1 for gold, pred in zip(labels, predictions) if gold == cls and pred == cls)
        fp = sum(1 for gold, pred in zip(labels, predictions) if gold != cls and pred == cls)
        fn = sum(1 for gold, pred in zip(labels, predictions) if gold == cls and pred != cls)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        scores.append(2 * precision * recall / (precision + recall) if precision + recall else 0.0)
    return sum(scores) / len(scores) if scores else 0.0


def _ece(labels: list[str], predictions: list[dict[str, Any]], bins: int = 5) -> float:
    total = len(predictions)
    if total == 0:
        return 0.0
    ece = 0.0
    for index in range(bins):
        low = index / bins
        high = (index + 1) / bins
        bucket = [
            (gold, pred)
            for gold, pred in zip(labels, predictions)
            if low <= pred["confidence"] < high or (index == bins - 1 and pred["confidence"] == 1.0)
        ]
        if not bucket:
            continue
        acc = sum(1 for gold, pred in bucket if gold == pred["label"]) / len(bucket)
        conf = sum(pred["confidence"] for _gold, pred in bucket) / len(bucket)
        ece += len(bucket) / total * abs(acc - conf)
    return ece


def _coverage_risk(labels: list[str], predictions: list[dict[str, Any]]) -> dict[str, float]:
    covered = [(gold, pred) for gold, pred in zip(labels, predictions) if not pred["abstain"]]
    coverage = len(covered) / len(predictions) if predictions else 0.0
    errors = sum(1 for gold, pred in covered if gold != pred["label"])
    risk = errors / len(covered) if covered else 0.0
    return {"coverage": round(coverage, 6), "risk": round(risk, 6)}


def _normalize_policy(policy: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "review_threshold": _clamp(_safe_float(policy.get("review_threshold"), 0.52)),
        "abstain_threshold": _clamp(_safe_float(policy.get("abstain_threshold"), 0.45)),
        "retrieval_threshold": _clamp(_safe_float(policy.get("retrieval_threshold"), 0.58)),
        "countermeasure_threshold": _clamp(_safe_float(policy.get("countermeasure_threshold"), 0.72)),
        "trigger_conditions": {
            **DEFAULT_POLICY["trigger_conditions"],
            **(policy.get("trigger_conditions") or {}),
        },
        "report_template_constraints": {
            **DEFAULT_POLICY["report_template_constraints"],
            **(policy.get("report_template_constraints") or {}),
        },
        "agent_weights": {**DEFAULT_POLICY["agent_weights"], **(policy.get("agent_weights") or {})},
    }
    weight_sum = sum(max(0.0, _safe_float(value)) for value in normalized["agent_weights"].values()) or 1.0
    normalized["agent_weights"] = {
        agent: round(max(0.0, _safe_float(weight)) / weight_sum, 6)
        for agent, weight in normalized["agent_weights"].items()
    }
    return normalized


def _nearby(current: float, values: list[float]) -> list[float]:
    rows = sorted(set([round(current, 2), *values]))
    return [value for value in rows if 0.0 < value < 1.0]


def _empty_metrics() -> dict[str, Any]:
    return {
        "macro_f1": 0.0,
        "accuracy": 0.0,
        "ece": 0.0,
        "abstain_rate": 0.0,
        "review_precision": 0.0,
        "retrieval_trigger_rate": 0.0,
        "countermeasure_trigger_rate": 0.0,
        "coverage_risk": {"coverage": 0.0, "risk": 0.0},
    }


def _policy_id(manifest: dict[str, Any], policy: dict[str, Any]) -> str:
    payload = {
        "dataset_id": manifest.get("dataset_id") or manifest.get("name"),
        "policy": policy,
        "validation_count": len(_as_list((manifest.get("splits") or {}).get("validation"))),
    }
    digest = sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return f"kt3-policy-{digest[:12]}"


def _refined_policy_id(
    manifest: dict[str, Any],
    policy: dict[str, Any],
    refinement_trace: list[dict[str, Any]],
    feedback_summary: dict[str, Any],
) -> str:
    payload = {
        "dataset_id": manifest.get("dataset_id") or manifest.get("name"),
        "policy": policy,
        "trace": [
            {
                "round": item.get("round"),
                "accepted_rule_id": item.get("accepted_rule_id"),
                "policy_changed": item.get("policy_changed"),
            }
            for item in refinement_trace
        ],
        "feedback_summary": feedback_summary,
    }
    digest = sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    return f"kt3-refined-policy-{digest[:12]}"


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 6)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
