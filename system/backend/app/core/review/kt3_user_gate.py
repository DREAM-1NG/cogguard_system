"""KT3 user-level evaluation gate.

This harness evaluates runtime account-level harmfulness aggregation against a
fixed labelled sample set. It does not train MIL, temporal Transformer, graph
models, or user encoders; gold labels are used only for metrics and review
routing.
"""

from __future__ import annotations

from typing import Any


DEFAULT_USER_GATE_THRESHOLDS = {
    "harmful_flag_accuracy": 0.7,
    "persistence_label_accuracy": 0.7,
    "trajectory_accuracy": 0.6,
    "role_micro_f1": 0.5,
    "representative_evidence_rate": 0.8,
}


def evaluate_kt3_user_gate(
    *,
    kt3_harmfulness: dict[str, Any] | None = None,
    accounts: list[dict[str, Any]] | None = None,
    gold: dict[str, Any] | list[dict[str, Any]] | None = None,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Evaluate account-level KT3 outputs against fixed gold labels."""
    account_rows = accounts if accounts is not None else _as_list(_get(kt3_harmfulness, "user_level", "accounts"))
    account_index = {
        _text(account.get("account_id")): account
        for account in account_rows
        if _text(account.get("account_id"))
    }
    gold_rows = _normalize_gold(gold or {})
    thresholds = {**DEFAULT_USER_GATE_THRESHOLDS, **(thresholds or {})}

    account_results = [
        _evaluate_single_account(row, account_index.get(row["account_id"]))
        for row in gold_rows
    ]
    failed_accounts = [result for result in account_results if not result["passed"]]
    metrics = _compute_metrics(account_results)
    threshold_status = _threshold_status(metrics, thresholds)
    review_queue = _build_user_gate_review_queue(failed_accounts)

    return {
        "capability_boundary": {
            "status": "implemented_user_gate_evaluation_harness",
            "evaluation_harness_only": True,
            "trained_user_encoder": False,
            "trained_mil_or_temporal_model": False,
            "uses_gold_for_training": False,
            "live_llm_or_rag": False,
            "description": (
                "Evaluates existing KT3 user-level runtime aggregation on fixed labelled accounts. "
                "It does not train account encoders or execute online Agent/RAG review."
            ),
        },
        "summary": {
            "gold_accounts": len(gold_rows),
            "available_accounts": len(account_index),
            "evaluated_accounts": len(account_results),
            "passed_accounts": sum(1 for result in account_results if result["passed"]),
            "failed_accounts": len(failed_accounts),
            "review_items": len(review_queue["review_items"]),
            "overall_pass": all(item["passed"] for item in threshold_status.values()) if threshold_status else False,
            "evaluated_from": "kt3_harmfulness.user_level.accounts",
        },
        "thresholds": thresholds,
        "threshold_status": threshold_status,
        "metrics": metrics,
        "account_results": account_results,
        "failed_accounts": failed_accounts,
        "review_queue": review_queue,
    }


def _evaluate_single_account(gold: dict[str, Any], account: dict[str, Any] | None) -> dict[str, Any]:
    predicted = _prediction_view(account)
    failure_reasons: list[str] = []

    if account is None:
        failure_reasons.append("missing_account_prediction")
    if gold.get("harmful") is not None and predicted["harmful"] != gold["harmful"]:
        failure_reasons.append("harmful_flag_mismatch")
    if gold.get("persistence_label") is not None and predicted["persistence_label"] != gold["persistence_label"]:
        failure_reasons.append("persistence_label_mismatch")
    if gold.get("trajectory") is not None and predicted["trajectory"] != gold["trajectory"]:
        failure_reasons.append("trajectory_mismatch")
    if gold.get("roles") is not None and not set(gold["roles"]).issubset(set(predicted["roles"])):
        failure_reasons.append("role_mismatch")
    if gold.get("needs_representative_evidence", True) and not predicted["has_representative_evidence"]:
        failure_reasons.append("missing_representative_evidence")
    if predicted["needs_review"]:
        failure_reasons.append("runtime_needs_review")

    return {
        "account_id": gold["account_id"],
        "passed": not failure_reasons,
        "failure_reasons": failure_reasons,
        "gold": gold,
        "predicted": predicted,
    }


def _prediction_view(account: dict[str, Any] | None) -> dict[str, Any]:
    if not account:
        return {
            "harmful": False,
            "persistence_label": "missing",
            "trajectory": "missing",
            "roles": [],
            "has_representative_evidence": False,
            "needs_review": True,
            "scores": {},
        }

    summary = account.get("risk_summary") or {}
    flags = account.get("risk_profile_flags") or {}
    role_profile = account.get("role_profile") or {}
    representative_posts = _as_list(account.get("representative_posts"))
    persistence_score = _safe_float(summary.get("persistence_score"))
    return {
        "harmful": bool(flags.get("high_harmful")),
        "persistence_label": _persistence_label(persistence_score),
        "trajectory": _text(summary.get("trajectory")) or "unknown",
        "roles": _as_list(role_profile.get("harmful_roles")),
        "has_representative_evidence": any(_text(post.get("post_id")) for post in representative_posts if isinstance(post, dict)),
        "needs_review": bool(flags.get("needs_review")),
        "scores": {
            "harmful_ratio": _safe_float(summary.get("harmful_ratio")),
            "avg_harm_score": _safe_float(summary.get("avg_harm_score")),
            "persistence_score": persistence_score,
        },
        "evidence": {
            "representative_posts": representative_posts[:3],
            "top_claims": _as_list(account.get("top_claims"))[:3],
            "risk_profile_flags": flags,
        },
    }


def _compute_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    role_tp = 0
    role_fp = 0
    role_fn = 0
    for result in results:
        gold_roles = set(result["gold"].get("roles") or [])
        predicted_roles = set(result["predicted"].get("roles") or [])
        role_tp += len(gold_roles & predicted_roles)
        role_fp += len(predicted_roles - gold_roles)
        role_fn += len(gold_roles - predicted_roles)

    role_precision = role_tp / (role_tp + role_fp) if (role_tp + role_fp) else 0.0
    role_recall = role_tp / (role_tp + role_fn) if (role_tp + role_fn) else 0.0
    role_f1 = (
        2 * role_precision * role_recall / (role_precision + role_recall)
        if (role_precision + role_recall)
        else 0.0
    )
    evidence_total = sum(1 for result in results if result["gold"].get("needs_representative_evidence", True))
    return {
        "harmful_flag_accuracy": _accuracy(results, "harmful"),
        "persistence_label_accuracy": _accuracy(results, "persistence_label"),
        "trajectory_accuracy": _accuracy(results, "trajectory"),
        "role_micro_precision": round(role_precision, 4),
        "role_micro_recall": round(role_recall, 4),
        "role_micro_f1": round(role_f1, 4),
        "representative_evidence_rate": (
            round(
                sum(
                    1
                    for result in results
                    if result["gold"].get("needs_representative_evidence", True)
                    and result["predicted"]["has_representative_evidence"]
                )
                / evidence_total,
                4,
            )
            if evidence_total
            else 0.0
        ),
        "runtime_needs_review_rate": (
            round(sum(1 for result in results if result["predicted"]["needs_review"]) / len(results), 4)
            if results
            else 0.0
        ),
        "evaluated_accounts": len(results),
    }


def _accuracy(results: list[dict[str, Any]], key: str) -> float:
    denominator = sum(1 for result in results if result["gold"].get(key) is not None)
    if denominator == 0:
        return 0.0
    correct = sum(1 for result in results if result["gold"].get(key) == result["predicted"].get(key))
    return round(correct / denominator, 4)


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


def _build_user_gate_review_queue(failed_results: list[dict[str, Any]]) -> dict[str, Any]:
    review_items = []
    for result in failed_results:
        review_items.append(
            {
                "id": f"user_gate:{result['account_id']}",
                "type": "user_gate_failure_review",
                "priority": _review_priority(result),
                "execution_status": "planned_only",
                "requires_external_execution": True,
                "reason": "; ".join(result["failure_reasons"]),
                "agent_role": "AccountBehaviorReviewer",
                "evidence": {
                    "account_id": result["account_id"],
                    "gold": result["gold"],
                    "predicted": result["predicted"],
                },
            }
        )

    agent_tasks = []
    if review_items:
        agent_tasks.append(
            {
                "agent": "AccountBehaviorReviewer",
                "priority": "high" if any(item["priority"] == "high" for item in review_items) else "medium",
                "execution_status": "planned_only",
                "requires_external_execution": True,
                "objective": "Review KT3 User Gate failures without training a user encoder.",
                "inputs": [item["id"] for item in review_items],
                "output_contract": ["persistence_review", "role_review", "trajectory_review", "evidence_refs"],
            }
        )

    return {
        "capability_boundary": {
            "status": "implemented_user_gate_failure_review_queue",
            "evaluation_harness_only": True,
            "live_llm_or_rag": False,
            "description": "Routes failed user-level evaluation samples to planned-only review tasks.",
        },
        "summary": {
            "review_items": len(review_items),
            "agent_tasks": len(agent_tasks),
        },
        "review_items": review_items,
        "agent_tasks": agent_tasks,
    }


def _review_priority(result: dict[str, Any]) -> str:
    gold = result.get("gold") or {}
    if gold.get("harmful") or gold.get("roles"):
        return "high"
    if result["predicted"].get("needs_review"):
        return "medium"
    return "low"


def _normalize_gold(raw_gold: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(raw_gold, dict):
        rows = [{**value, "account_id": key} for key, value in raw_gold.items() if isinstance(value, dict)]
    elif isinstance(raw_gold, list):
        rows = [row for row in raw_gold if isinstance(row, dict)]
    else:
        rows = []

    normalized = []
    for row in rows:
        account_id = _text(row.get("account_id"))
        if not account_id:
            continue
        normalized.append(
            {
                "account_id": account_id,
                "harmful": _optional_bool(row.get("harmful")),
                "persistence_label": _optional_text(row.get("persistence_label")),
                "trajectory": _optional_text(row.get("trajectory")),
                "roles": sorted(_as_list(row.get("roles"))),
                "needs_representative_evidence": bool(row.get("needs_representative_evidence", True)),
            }
        )
    return normalized


def _persistence_label(score: float) -> str:
    if score >= 0.66:
        return "high"
    if score >= 0.33:
        return "medium"
    return "low"


def _get(value: dict[str, Any] | None, *path: str) -> Any:
    current: Any = value or {}
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


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
