"""Review community-level evaluation gate.

This harness evaluates community-level runtime harmfulness aggregation against
fixed labelled samples. It also audits whether the optional graph export is
ready for downstream consumers. It does not train HGT, Graph Transformer,
Temporal Graph Network, or any other graph encoder.
"""

from __future__ import annotations

from typing import Any


DEFAULT_COMMUNITY_GATE_THRESHOLDS = {
    "collective_harm_accuracy": 0.7,
    "amplification_label_accuracy": 0.7,
    "harm_type_micro_f1": 0.5,
    "role_micro_f1": 0.5,
    "claim_coverage_rate": 0.7,
    "key_account_evidence_rate": 0.8,
}


def evaluate_community_gate(
    *,
    review_harmfulness: dict[str, Any] | None = None,
    communities: list[dict[str, Any]] | None = None,
    graph_export: dict[str, Any] | None = None,
    gold: dict[str, Any] | list[dict[str, Any]] | None = None,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Evaluate community-level Review outputs against fixed gold labels."""
    community_rows = communities
    if community_rows is None:
        community_rows = _as_list(_get(review_harmfulness, "community_level", "communities"))
    effective_graph_export = graph_export
    if effective_graph_export is None:
        maybe_graph_export = _get(review_harmfulness, "graph_export")
        effective_graph_export = maybe_graph_export if isinstance(maybe_graph_export, dict) else None

    community_index = {
        _text(community.get("community_id")): community
        for community in community_rows
        if _text(community.get("community_id"))
    }
    gold_rows = _normalize_gold(gold or {})
    thresholds = {**DEFAULT_COMMUNITY_GATE_THRESHOLDS, **(thresholds or {})}

    community_results = [
        _evaluate_single_community(row, community_index.get(row["community_id"]))
        for row in gold_rows
    ]
    failed_communities = [result for result in community_results if not result["passed"]]
    graph_audit = _audit_graph_export(effective_graph_export)
    metrics = _compute_metrics(community_results, graph_audit)
    threshold_status = _threshold_status(metrics, thresholds)
    review_queue = _build_community_gate_review_queue(failed_communities)

    return {
        "capability_boundary": {
            "status": "implemented_community_gate_evaluation_harness",
            "evaluation_harness_only": True,
            "trained_graph_model": False,
            "trained_hgt_or_tgn": False,
            "uses_gold_for_training": False,
            "live_llm_or_rag": False,
            "description": (
                "Evaluates existing Review community-level runtime aggregation on fixed labelled "
                "communities and optionally audits graph export consumer readiness. It does "
                "not train graph encoders or execute online Agent/RAG review."
            ),
        },
        "summary": {
            "gold_communities": len(gold_rows),
            "available_communities": len(community_index),
            "evaluated_communities": len(community_results),
            "passed_communities": sum(1 for result in community_results if result["passed"]),
            "failed_communities": len(failed_communities),
            "review_items": len(review_queue["review_items"]),
            "overall_pass": all(item["passed"] for item in threshold_status.values()) if threshold_status else False,
            "evaluated_from": "review_harmfulness.community_level.communities",
        },
        "thresholds": thresholds,
        "threshold_status": threshold_status,
        "metrics": metrics,
        "graph_audit": graph_audit,
        "community_results": community_results,
        "failed_communities": failed_communities,
        "review_queue": review_queue,
    }


def _evaluate_single_community(
    gold: dict[str, Any],
    community: dict[str, Any] | None,
) -> dict[str, Any]:
    predicted = _prediction_view(community)
    failure_reasons: list[str] = []

    if community is None:
        failure_reasons.append("missing_community_prediction")
    if gold.get("collective_harm") is not None and predicted["collective_harm"] != gold["collective_harm"]:
        failure_reasons.append("collective_harm_mismatch")
    if gold.get("amplification") is not None and predicted["amplification"] != gold["amplification"]:
        failure_reasons.append("amplification_label_mismatch")
    if gold.get("harm_types") is not None and not set(gold["harm_types"]).issubset(set(predicted["harm_types"])):
        failure_reasons.append("harm_type_mismatch")
    if gold.get("roles") is not None and not set(gold["roles"]).issubset(set(predicted["roles"])):
        failure_reasons.append("role_mismatch")
    if gold.get("claims") is not None and not set(gold["claims"]).issubset(set(predicted["claims"])):
        failure_reasons.append("claim_coverage_mismatch")
    if gold.get("key_accounts") is not None and not set(gold["key_accounts"]).issubset(
        set(predicted["key_accounts"])
    ):
        failure_reasons.append("key_account_mismatch")
    if gold.get("needs_claim_coverage", True) and not predicted["has_claim_coverage"]:
        failure_reasons.append("missing_claim_coverage")
    if gold.get("needs_key_account_evidence", True) and not predicted["has_key_account_evidence"]:
        failure_reasons.append("missing_key_account_evidence")
    if predicted["needs_review"] and not gold.get("allow_runtime_needs_review", False):
        failure_reasons.append("runtime_needs_review")

    return {
        "community_id": gold["community_id"],
        "passed": not failure_reasons,
        "failure_reasons": failure_reasons,
        "gold": gold,
        "predicted": predicted,
    }


def _prediction_view(community: dict[str, Any] | None) -> dict[str, Any]:
    if not community:
        return {
            "collective_harm": False,
            "amplification": False,
            "harm_types": [],
            "roles": [],
            "claims": [],
            "key_accounts": [],
            "has_claim_coverage": False,
            "has_key_account_evidence": False,
            "needs_review": True,
            "scores": {},
            "evidence": {},
        }

    risk_summary = community.get("risk_summary") or {}
    risk_flags = community.get("risk_flags") or {}
    harm_types = _nonzero_keys(risk_summary.get("dominant_harm_types"))
    roles = _nonzero_keys(community.get("subgroup_roles"))
    claims = [
        _text(claim.get("claim_id"))
        for claim in _as_list(community.get("claims_coverage"))
        if isinstance(claim, dict) and _text(claim.get("claim_id"))
    ]
    key_accounts = [
        _text(account.get("account_id"))
        for account in _as_list(community.get("key_accounts"))
        if isinstance(account, dict) and _text(account.get("account_id"))
    ]

    return {
        "collective_harm": bool(risk_flags.get("high_collective_harm")),
        "amplification": bool(risk_flags.get("coordinated_harm_amplification")),
        "harm_types": sorted(harm_types),
        "roles": sorted(roles),
        "claims": sorted(claims),
        "key_accounts": sorted(key_accounts),
        "has_claim_coverage": bool(claims),
        "has_key_account_evidence": bool(key_accounts),
        "needs_review": bool(risk_flags.get("needs_review")),
        "scores": {
            "harmful_ratio": _safe_float(risk_summary.get("harmful_ratio")),
            "harmful_posts": _safe_int(risk_summary.get("harmful_posts")),
            "harmful_accounts": _safe_int(risk_summary.get("harmful_accounts")),
            "amplification_score": _safe_float(risk_summary.get("amplification_score")),
        },
        "evidence": {
            "claims_coverage": _as_list(community.get("claims_coverage"))[:5],
            "key_accounts": _as_list(community.get("key_accounts"))[:5],
            "risk_flags": risk_flags,
        },
    }


def _compute_metrics(
    results: list[dict[str, Any]],
    graph_audit: dict[str, Any],
) -> dict[str, Any]:
    harm_precision, harm_recall, harm_f1 = _micro_prf(results, "harm_types")
    role_precision, role_recall, role_f1 = _micro_prf(results, "roles")

    metrics = {
        "collective_harm_accuracy": _accuracy(results, "collective_harm"),
        "amplification_label_accuracy": _accuracy(results, "amplification"),
        "harm_type_micro_precision": harm_precision,
        "harm_type_micro_recall": harm_recall,
        "harm_type_micro_f1": harm_f1,
        "role_micro_precision": role_precision,
        "role_micro_recall": role_recall,
        "role_micro_f1": role_f1,
        "claim_coverage_rate": _coverage_rate(results, "claims", "needs_claim_coverage", "has_claim_coverage"),
        "key_account_evidence_rate": _coverage_rate(
            results,
            "key_accounts",
            "needs_key_account_evidence",
            "has_key_account_evidence",
        ),
        "runtime_needs_review_rate": (
            round(sum(1 for result in results if result["predicted"]["needs_review"]) / len(results), 4)
            if results
            else 0.0
        ),
        "evaluated_communities": len(results),
    }
    if graph_audit["provided"]:
        metrics["graph_export_ready_rate"] = graph_audit["graph_export_ready_rate"]
    return metrics


def _accuracy(results: list[dict[str, Any]], key: str) -> float:
    denominator = sum(1 for result in results if result["gold"].get(key) is not None)
    if denominator == 0:
        return 0.0
    correct = sum(1 for result in results if result["gold"].get(key) == result["predicted"].get(key))
    return round(correct / denominator, 4)


def _micro_prf(results: list[dict[str, Any]], key: str) -> tuple[float, float, float]:
    tp = 0
    fp = 0
    fn = 0
    for result in results:
        gold_values = set(result["gold"].get(key) or [])
        predicted_values = set(result["predicted"].get(key) or [])
        tp += len(gold_values & predicted_values)
        fp += len(predicted_values - gold_values)
        fn += len(gold_values - predicted_values)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return round(precision, 4), round(recall, 4), round(f1, 4)


def _coverage_rate(
    results: list[dict[str, Any]],
    gold_key: str,
    required_key: str,
    predicted_presence_key: str,
) -> float:
    denominator = sum(
        1
        for result in results
        if result["gold"].get(required_key, True) or bool(result["gold"].get(gold_key))
    )
    if denominator == 0:
        return 0.0
    covered = 0
    for result in results:
        gold_values = set(result["gold"].get(gold_key) or [])
        predicted_values = set(result["predicted"].get(gold_key) or [])
        if gold_values:
            covered += int(gold_values.issubset(predicted_values))
        else:
            covered += int(bool(result["predicted"].get(predicted_presence_key)))
    return round(covered / denominator, 4)


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


def _audit_graph_export(graph_export: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(graph_export, dict):
        return {
            "provided": False,
            "graph_export_ready": False,
            "graph_export_ready_rate": 0.0,
            "trained_graph_model": False,
            "description": "No graph export artifact was provided to Community Gate.",
        }

    node_types = set(_as_list(_get(graph_export, "schema", "node_types")))
    edge_types = set(_as_list(_get(graph_export, "schema", "edge_types")))
    nodes = _as_list(graph_export.get("nodes"))
    edges = _as_list(graph_export.get("edges"))
    node_ids = {node.get("id") for node in nodes if isinstance(node, dict)}
    no_dangling_edges = all(
        isinstance(edge, dict) and edge.get("source") in node_ids and edge.get("target") in node_ids
        for edge in edges
    )
    trained_graph_model = bool(_get(graph_export, "capability_boundary", "trained_graph_model"))
    has_required_node_types = {"account", "post", "claim", "community", "target", "media"}.issubset(node_types)
    has_required_edge_types = {
        "authored",
        "member_of",
        "mentions_claim",
        "community_focuses_claim",
        "community_targets",
    }.issubset(edge_types)
    graph_native_ready = bool(_get(graph_export, "summary", "graph_native_ready"))
    count_matches = _safe_int(_get(graph_export, "summary", "node_count")) == len(nodes) and _safe_int(
        _get(graph_export, "summary", "edge_count")
    ) == len(edges)
    ready = (
        graph_native_ready
        and has_required_node_types
        and has_required_edge_types
        and no_dangling_edges
        and count_matches
        and not trained_graph_model
    )
    return {
        "provided": True,
        "graph_export_ready": ready,
        "graph_export_ready_rate": 1.0 if ready else 0.0,
        "graph_native_ready": graph_native_ready,
        "has_required_node_types": has_required_node_types,
        "has_required_edge_types": has_required_edge_types,
        "has_no_dangling_edges": no_dangling_edges,
        "count_matches_summary": count_matches,
        "trained_graph_model": trained_graph_model,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "description": (
            "Audits whether the exported heterogeneous graph is consumer-readable. "
            "A passing audit does not imply a trained graph model."
        ),
    }


def _build_community_gate_review_queue(failed_results: list[dict[str, Any]]) -> dict[str, Any]:
    review_items = []
    for result in failed_results:
        review_items.append(
            {
                "id": f"community_gate:{result['community_id']}",
                "type": "community_gate_failure_review",
                "priority": _review_priority(result),
                "execution_status": "planned_only",
                "requires_external_execution": True,
                "reason": "; ".join(result["failure_reasons"]),
                "agent_role": "CommunityJudge",
                "evidence": {
                    "community_id": result["community_id"],
                    "gold": result["gold"],
                    "predicted": result["predicted"],
                },
            }
        )

    agent_tasks = []
    if review_items:
        agent_tasks.append(
            {
                "agent": "CommunityJudge",
                "priority": "high" if any(item["priority"] == "high" for item in review_items) else "medium",
                "execution_status": "planned_only",
                "requires_external_execution": True,
                "objective": "Review Community Gate failures without training a graph encoder.",
                "inputs": [item["id"] for item in review_items],
                "output_contract": [
                    "collective_harm_review",
                    "amplification_review",
                    "role_decomposition_review",
                    "claim_and_key_account_evidence_refs",
                ],
            }
        )

    return {
        "capability_boundary": {
            "status": "implemented_community_gate_failure_review_queue",
            "evaluation_harness_only": True,
            "trained_graph_model": False,
            "live_llm_or_rag": False,
            "description": "Routes failed community-level evaluation samples to planned-only review tasks.",
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
    if gold.get("collective_harm") or gold.get("amplification") or gold.get("harm_types"):
        return "high"
    if result["predicted"].get("needs_review"):
        return "medium"
    return "low"


def _normalize_gold(raw_gold: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(raw_gold, dict):
        rows = [{**value, "community_id": key} for key, value in raw_gold.items() if isinstance(value, dict)]
    elif isinstance(raw_gold, list):
        rows = [row for row in raw_gold if isinstance(row, dict)]
    else:
        rows = []

    normalized = []
    for row in rows:
        community_id = _text(row.get("community_id"))
        if not community_id:
            continue
        normalized.append(
            {
                "community_id": community_id,
                "collective_harm": _optional_bool(row.get("collective_harm", row.get("harmful"))),
                "amplification": _optional_bool(row.get("amplification")),
                "harm_types": sorted(_as_list(row.get("harm_types"))),
                "roles": sorted(_as_list(row.get("roles"))),
                "claims": sorted(_as_list(row.get("claims"))),
                "key_accounts": sorted(_as_list(row.get("key_accounts"))),
                "needs_claim_coverage": bool(row.get("needs_claim_coverage", True)),
                "needs_key_account_evidence": bool(row.get("needs_key_account_evidence", True)),
                "allow_runtime_needs_review": bool(row.get("allow_runtime_needs_review", False)),
            }
        )
    return normalized


def _nonzero_keys(value: Any) -> list[str]:
    if isinstance(value, dict):
        return sorted(_text(key) for key, count in value.items() if _text(key) and _safe_float(count) > 0)
    return sorted(_as_list(value))


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
