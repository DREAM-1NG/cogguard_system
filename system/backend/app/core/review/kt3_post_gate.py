"""KT3 post-level evaluation gate.

This module evaluates the existing post semantic scaffold against a fixed
labelled sample set. It is intentionally a thin harness: gold labels are used
only for metrics and review routing, never for fitting thresholds, prototypes,
or model weights.
"""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

from app.core.review.post_semantics import assess_post_semantics


PostSemanticScorer = Callable[..., dict[str, Any]]


DEFAULT_POST_GATE_THRESHOLDS = {
    "claim_link_accuracy": 0.7,
    "stance_accuracy": 0.7,
    "harm_label_accuracy": 0.7,
    "harm_type_micro_f1": 0.5,
    "evidence_presence_rate": 0.9,
}


def evaluate_kt3_post_gate(
    cases: list[dict[str, Any]],
    *,
    scorer: PostSemanticScorer = assess_post_semantics,
    prefer_embeddings: bool = False,
    max_output_posts: int = 20,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Evaluate post-level KT3 outputs against fixed gold cases.

    The returned review queue is a planned-only evaluation artifact. It does not
    execute LLM, web, vector-database, or multi-agent review.
    """
    frozen_cases = deepcopy(cases)
    thresholds = {**DEFAULT_POST_GATE_THRESHOLDS, **(thresholds or {})}

    case_reports: list[dict[str, Any]] = []
    post_results: list[dict[str, Any]] = []
    failed_results: list[dict[str, Any]] = []
    semantic_scopes: list[dict[str, Any]] = []

    for case in frozen_cases:
        case_id = _text(case.get("case_id")) or f"case_{len(case_reports) + 1}"
        post_semantics = scorer(
            case.get("posts") or [],
            case.get("propagation") or case.get("prop_data") or {},
            prefer_embeddings=prefer_embeddings,
            max_output_posts=max_output_posts,
        )
        aggregation_posts = _as_list(post_semantics.get("aggregation_posts"))
        predictions = {
            _text(post.get("post_id")): post
            for post in aggregation_posts
            if _text(post.get("post_id"))
        }
        gold_rows = _normalize_gold(case.get("gold") or case.get("labels") or {})
        case_post_results = [
            _evaluate_single_post(case_id, gold, predictions.get(gold["post_id"]))
            for gold in gold_rows
        ]
        failures = [result for result in case_post_results if not result["passed"]]

        semantic_scopes.append(
            {
                "case_id": case_id,
                "input_posts": _safe_int(_get(post_semantics, "analysis_scope", "input_posts")),
                "aggregation_posts": len(aggregation_posts),
                "representative_posts": len(_as_list(post_semantics.get("posts"))),
                "claim_candidates": _safe_int(_get(post_semantics, "analysis_scope", "claim_candidates")),
                "encoder_backend": _get(post_semantics, "modeling", "encoder_backend"),
            }
        )
        case_reports.append(
            {
                "case_id": case_id,
                "gold_posts": len(gold_rows),
                "aggregation_posts_evaluated": len(aggregation_posts),
                "representative_posts": len(_as_list(post_semantics.get("posts"))),
                "failed_posts": len(failures),
                "post_results": case_post_results,
            }
        )
        post_results.extend(case_post_results)
        failed_results.extend(failures)

    metrics = _compute_metrics(post_results)
    threshold_status = _threshold_status(metrics, thresholds)
    review_queue = _build_post_gate_review_queue(failed_results)

    return {
        "capability_boundary": {
            "status": "implemented_post_gate_evaluation_harness",
            "evaluation_harness_only": True,
            "trained_model": False,
            "uses_gold_for_training": False,
            "mutates_inputs": False,
            "live_llm_or_rag": False,
            "description": (
                "Evaluates existing KT3 post semantic outputs on fixed labelled cases. "
                "It does not train a post classifier or execute online Agent/RAG review."
            ),
        },
        "summary": {
            "cases": len(frozen_cases),
            "evaluated_posts": len(post_results),
            "passed_posts": sum(1 for result in post_results if result["passed"]),
            "failed_posts": len(failed_results),
            "review_items": len(review_queue["review_items"]),
            "overall_pass": all(item["passed"] for item in threshold_status.values()) if threshold_status else False,
            "evaluated_from": "aggregation_posts",
        },
        "thresholds": thresholds,
        "threshold_status": threshold_status,
        "metrics": metrics,
        "semantic_scopes": semantic_scopes,
        "case_results": case_reports,
        "failed_posts": failed_results,
        "review_queue": review_queue,
    }


def _evaluate_single_post(
    case_id: str,
    gold: dict[str, Any],
    prediction: dict[str, Any] | None,
) -> dict[str, Any]:
    predicted = _prediction_view(prediction)
    failure_reasons: list[str] = []

    if prediction is None:
        failure_reasons.append("missing_prediction")
    if gold.get("claim_id") is not None and predicted["claim_id"] != gold["claim_id"]:
        failure_reasons.append("claim_link_mismatch")
    if gold.get("stance") is not None and predicted["stance"] != gold["stance"]:
        failure_reasons.append("stance_mismatch")
    if gold.get("harm_label") is not None and predicted["harm_label"] != gold["harm_label"]:
        failure_reasons.append("harm_label_mismatch")
    if gold.get("harm_types") is not None and not set(gold["harm_types"]).issubset(set(predicted["harm_types"])):
        failure_reasons.append("harm_type_mismatch")
    if gold.get("must_have_modalities"):
        missing = sorted(set(gold["must_have_modalities"]) - set(predicted["modalities"]))
        if missing:
            failure_reasons.append("missing_modalities:" + ",".join(missing))
    if gold.get("evidence_required", True) and not predicted["has_evidence"]:
        failure_reasons.append("missing_evidence")
    if predicted["abstained"]:
        failure_reasons.append("model_abstained")

    return {
        "case_id": case_id,
        "post_id": gold["post_id"],
        "passed": not failure_reasons,
        "failure_reasons": failure_reasons,
        "gold": gold,
        "predicted": predicted,
    }


def _prediction_view(prediction: dict[str, Any] | None) -> dict[str, Any]:
    if not prediction:
        return {
            "claim_id": "NIL",
            "stance": "missing",
            "harm_label": "missing",
            "harm_types": [],
            "modalities": [],
            "evidence": {},
            "has_evidence": False,
            "abstained": True,
        }

    primary_claim = prediction.get("primary_claim") or {}
    stance = prediction.get("stance") or {}
    harmfulness = prediction.get("harmfulness") or {}
    evidence = prediction.get("evidence") or {}
    return {
        "claim_id": _text(primary_claim.get("claim_id")) or "NIL",
        "stance": _text(stance.get("label")) or "missing",
        "harm_label": _text(harmfulness.get("label")) or "missing",
        "harm_types": _as_list(harmfulness.get("types")),
        "modalities": _as_list(prediction.get("modalities")),
        "evidence": evidence,
        "has_evidence": any(_text(value) for value in evidence.values()),
        "abstained": bool(stance.get("abstain")) or bool(harmfulness.get("abstain")),
        "scores": {
            "claim": _safe_float(primary_claim.get("score")),
            "stance": _safe_float(stance.get("confidence")),
            "harm": _safe_float(harmfulness.get("score")),
        },
    }


def _compute_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    claim_total = _metric_denominator(results, "claim_id")
    stance_total = _metric_denominator(results, "stance")
    harm_label_total = _metric_denominator(results, "harm_label")
    evidence_total = sum(1 for result in results if result["gold"].get("evidence_required", True))

    type_tp = 0
    type_fp = 0
    type_fn = 0
    for result in results:
        gold_types = set(result["gold"].get("harm_types") or [])
        predicted_types = set(result["predicted"].get("harm_types") or [])
        type_tp += len(gold_types & predicted_types)
        type_fp += len(predicted_types - gold_types)
        type_fn += len(gold_types - predicted_types)

    precision = type_tp / (type_tp + type_fp) if (type_tp + type_fp) else 0.0
    recall = type_tp / (type_tp + type_fn) if (type_tp + type_fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    return {
        "claim_link_accuracy": _accuracy(results, "claim_id", claim_total),
        "stance_accuracy": _accuracy(results, "stance", stance_total),
        "harm_label_accuracy": _accuracy(results, "harm_label", harm_label_total),
        "harm_type_micro_precision": round(precision, 4),
        "harm_type_micro_recall": round(recall, 4),
        "harm_type_micro_f1": round(f1, 4),
        "evidence_presence_rate": (
            round(
                sum(
                    1
                    for result in results
                    if result["gold"].get("evidence_required", True) and result["predicted"]["has_evidence"]
                )
                / evidence_total,
                4,
            )
            if evidence_total
            else 0.0
        ),
        "abstain_rate": (
            round(sum(1 for result in results if result["predicted"]["abstained"]) / len(results), 4)
            if results
            else 0.0
        ),
        "evaluated_posts": len(results),
    }


def _accuracy(results: list[dict[str, Any]], key: str, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    correct = 0
    for result in results:
        expected = result["gold"].get(key)
        if expected is None:
            continue
        if result["predicted"].get(_prediction_key(key)) == expected:
            correct += 1
    return round(correct / denominator, 4)


def _prediction_key(gold_key: str) -> str:
    return {"claim_id": "claim_id", "stance": "stance", "harm_label": "harm_label"}[gold_key]


def _metric_denominator(results: list[dict[str, Any]], key: str) -> int:
    return sum(1 for result in results if result["gold"].get(key) is not None)


def _threshold_status(metrics: dict[str, Any], thresholds: dict[str, float]) -> dict[str, dict[str, Any]]:
    status = {}
    for name, threshold in thresholds.items():
        value = _safe_float(metrics.get(name))
        status[name] = {
            "value": value,
            "threshold": threshold,
            "passed": value >= threshold,
        }
    return status


def _build_post_gate_review_queue(failed_results: list[dict[str, Any]]) -> dict[str, Any]:
    review_items = []
    retrieval_tasks = []
    for result in failed_results:
        item_id = f"post_gate:{result['case_id']}:{result['post_id']}"
        review_items.append(
            {
                "id": item_id,
                "type": "post_gate_failure_review",
                "priority": _review_priority(result),
                "execution_status": "planned_only",
                "requires_external_execution": True,
                "reason": "; ".join(result["failure_reasons"]),
                "agent_role": "HarmReviewer",
                "evidence": {
                    "case_id": result["case_id"],
                    "post_id": result["post_id"],
                    "gold": result["gold"],
                    "predicted": result["predicted"],
                },
            }
        )
        if any(reason in result["failure_reasons"] for reason in {"claim_link_mismatch", "missing_prediction"}):
            retrieval_tasks.append(
                {
                    "id": f"retrieve:{item_id}",
                    "source_type": "post",
                    "source_id": result["post_id"],
                    "priority": _review_priority(result),
                    "execution_status": "planned_only",
                    "requires_external_execution": True,
                    "purpose": "post_gate_claim_or_context_review",
                    "query": _review_query(result),
                    "expected_evidence": ["canonical claim", "stance context", "harmfulness evidence"],
                }
            )

    agent_tasks = []
    if review_items:
        agent_tasks.append(
            {
                "agent": "HarmReviewer",
                "priority": "high" if any(item["priority"] == "high" for item in review_items) else "medium",
                "execution_status": "planned_only",
                "requires_external_execution": True,
                "objective": "Review KT3 Post Gate failures without changing the underlying scorer.",
                "inputs": [item["id"] for item in review_items],
                "output_contract": ["corrected_label", "claim_grounding", "stance_review", "evidence_refs"],
            }
        )

    return {
        "capability_boundary": {
            "status": "implemented_post_gate_failure_review_queue",
            "evaluation_harness_only": True,
            "live_llm_or_rag": False,
            "description": "Routes failed or abstained Post Gate samples to planned-only review tasks.",
        },
        "summary": {
            "review_items": len(review_items),
            "retrieval_tasks": len(retrieval_tasks),
            "agent_tasks": len(agent_tasks),
        },
        "review_items": review_items,
        "retrieval_tasks": retrieval_tasks,
        "agent_tasks": agent_tasks,
    }


def _review_priority(result: dict[str, Any]) -> str:
    gold = result.get("gold") or {}
    if gold.get("harm_label") == "harmful" or gold.get("harm_types"):
        return "high"
    if result["predicted"].get("abstained"):
        return "medium"
    return "low"


def _review_query(result: dict[str, Any]) -> str:
    gold = result.get("gold") or {}
    predicted = result.get("predicted") or {}
    evidence = predicted.get("evidence") or {}
    return _text(
        " ".join(
            [
                _text(gold.get("claim_id")),
                _text(evidence.get("text")),
                _text(evidence.get("ocr_text")),
                _text(evidence.get("asr_text")),
                _text(evidence.get("media_text")),
            ]
        )
    )[:220]


def _normalize_gold(raw_gold: Any) -> list[dict[str, Any]]:
    if isinstance(raw_gold, dict):
        rows = [{**value, "post_id": key} for key, value in raw_gold.items() if isinstance(value, dict)]
    elif isinstance(raw_gold, list):
        rows = [row for row in raw_gold if isinstance(row, dict)]
    else:
        rows = []

    normalized = []
    for row in rows:
        post_id = _text(row.get("post_id"))
        if not post_id:
            continue
        claim_id = _text(row.get("claim_id"))
        normalized.append(
            {
                "post_id": post_id,
                "claim_id": claim_id if claim_id else "NIL",
                "stance": _optional_text(row.get("stance")),
                "harm_label": _optional_text(row.get("harm_label")),
                "harm_types": sorted(_as_list(row.get("harm_types"))),
                "must_have_modalities": sorted(_as_list(row.get("must_have_modalities"))),
                "evidence_required": bool(row.get("evidence_required", True)),
            }
        )
    return normalized


def _get(value: dict[str, Any] | None, *path: str) -> Any:
    current: Any = value or {}
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _optional_text(value: Any) -> str | None:
    text = _text(value)
    return text if text else None


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
