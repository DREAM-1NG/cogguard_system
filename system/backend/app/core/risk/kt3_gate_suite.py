"""KT3 layered gate suite.

This module composes the post, user, and community evaluation gates into one
auditable report. It remains an offline evaluation harness: gold labels are used
only to compute metrics and route failures, never to train or calibrate models.
"""

from __future__ import annotations

from typing import Any

from app.core.risk.kt3_community_gate import evaluate_kt3_community_gate
from app.core.risk.kt3_gate_dataset import gate_dataset_contract_view
from app.core.risk.kt3_gate_dataset import normalize_kt3_gate_dataset
from app.core.risk.kt3_post_gate import evaluate_kt3_post_gate
from app.core.risk.kt3_user_gate import evaluate_kt3_user_gate


def evaluate_kt3_gate_suite(
    *,
    gate_dataset: dict[str, Any] | None = None,
    post_cases: list[dict[str, Any]] | None = None,
    kt3_harmfulness: dict[str, Any] | None = None,
    user_gold: dict[str, Any] | list[dict[str, Any]] | None = None,
    community_gold: dict[str, Any] | list[dict[str, Any]] | None = None,
    graph_export: dict[str, Any] | None = None,
    prefer_embeddings: bool | None = None,
    thresholds: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    """Run the available KT3 layer gates and return one summary report."""
    normalized_dataset = normalize_kt3_gate_dataset(gate_dataset)
    post_cases = post_cases if post_cases is not None else normalized_dataset.get("post_cases")
    user_gold = user_gold if user_gold is not None else normalized_dataset.get("user_gold")
    community_gold = (
        community_gold if community_gold is not None else normalized_dataset.get("community_gold")
    )
    thresholds = _merge_thresholds(normalized_dataset.get("thresholds"), thresholds)
    effective_prefer_embeddings = _effective_prefer_embeddings(prefer_embeddings, normalized_dataset)
    gates: dict[str, dict[str, Any]] = {}
    skipped: dict[str, dict[str, str]] = {}

    if post_cases:
        gates["post_gate"] = evaluate_kt3_post_gate(
            post_cases,
            prefer_embeddings=effective_prefer_embeddings,
            thresholds=thresholds.get("post"),
        )
    else:
        skipped["post_gate"] = {
            "reason": "missing_post_cases",
            "description": "Post Gate requires fixed labelled post cases.",
        }

    if user_gold:
        gates["user_gate"] = evaluate_kt3_user_gate(
            kt3_harmfulness=kt3_harmfulness,
            gold=user_gold,
            thresholds=thresholds.get("user"),
        )
    else:
        skipped["user_gate"] = {
            "reason": "missing_user_gold",
            "description": "User Gate requires fixed account-level gold labels.",
        }

    if community_gold:
        gates["community_gate"] = evaluate_kt3_community_gate(
            kt3_harmfulness=kt3_harmfulness,
            graph_export=graph_export,
            gold=community_gold,
            thresholds=thresholds.get("community"),
        )
    else:
        skipped["community_gate"] = {
            "reason": "missing_community_gold",
            "description": "Community Gate requires fixed community-level gold labels.",
        }

    return {
        "capability_boundary": {
            "status": "implemented_kt3_layered_gate_suite",
            "evaluation_harness_only": True,
            "trained_post_model": False,
            "trained_user_encoder": False,
            "trained_graph_model": False,
            "uses_gold_for_training": False,
            "live_llm_or_rag": False,
            "description": (
                "Composes KT3 Post/User/Community Gates into one offline evaluation "
                "report. It only executes layers with explicit labelled inputs and "
                "does not run training, online LLM/RAG, or graph model inference."
            ),
        },
        "dataset_contract": gate_dataset_contract_view(normalized_dataset),
        "summary": _suite_summary(gates, skipped),
        "gates": gates,
        "skipped_gates": skipped,
    }


def evaluate_kt3_gate_suite_from_dataset(
    *,
    dataset: dict[str, Any],
    kt3_harmfulness: dict[str, Any] | None = None,
    graph_export: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate KT3 gates from one explicit labelled dataset contract."""
    return evaluate_kt3_gate_suite(
        gate_dataset=dataset,
        kt3_harmfulness=kt3_harmfulness,
        graph_export=graph_export,
    )


def _merge_thresholds(
    dataset_thresholds: Any,
    explicit_thresholds: dict[str, dict[str, float]] | None,
) -> dict[str, dict[str, float]]:
    merged: dict[str, dict[str, float]] = {}
    if isinstance(dataset_thresholds, dict):
        for layer, values in dataset_thresholds.items():
            if isinstance(values, dict):
                merged[str(layer)] = dict(values)
    for layer, values in (explicit_thresholds or {}).items():
        if isinstance(values, dict):
            merged.setdefault(str(layer), {}).update(values)
    return merged


def _effective_prefer_embeddings(
    prefer_embeddings: bool | None,
    normalized_dataset: dict[str, Any],
) -> bool:
    if prefer_embeddings is not None:
        return bool(prefer_embeddings)
    dataset_preference = normalized_dataset.get("prefer_embeddings")
    if isinstance(dataset_preference, bool):
        return dataset_preference
    return False


def _suite_summary(
    gates: dict[str, dict[str, Any]],
    skipped: dict[str, dict[str, str]],
) -> dict[str, Any]:
    gate_status = {}
    review_items = 0
    failed_items = 0

    for name, report in gates.items():
        summary = report.get("summary") or {}
        threshold_status = report.get("threshold_status") or {}
        review_queue = report.get("review_queue") or {}
        gate_status[name] = {
            "overall_pass": bool(summary.get("overall_pass")),
            "metrics": sorted((report.get("metrics") or {}).keys()),
            "review_items": _safe_int(_get(review_queue, "summary", "review_items")),
            "failed_items": _failed_items(summary),
        }
        review_items += gate_status[name]["review_items"]
        failed_items += gate_status[name]["failed_items"]
        if threshold_status:
            gate_status[name]["failed_thresholds"] = sorted(
                key for key, value in threshold_status.items() if not bool(value.get("passed"))
            )

    return {
        "executed_gates": len(gates),
        "skipped_gates": len(skipped),
        "gate_names": sorted(gates),
        "skipped_gate_names": sorted(skipped),
        "review_items": review_items,
        "failed_items": failed_items,
        "overall_pass": bool(gates) and all(status["overall_pass"] for status in gate_status.values()),
        "gate_status": gate_status,
    }


def _failed_items(summary: dict[str, Any]) -> int:
    for key in ("failed_posts", "failed_accounts", "failed_communities"):
        if key in summary:
            return _safe_int(summary.get(key))
    return 0


def _get(value: dict[str, Any] | None, *path: str) -> Any:
    current: Any = value or {}
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
