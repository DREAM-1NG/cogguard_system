"""Account detection snapshot helpers for the NLPCC graph-detector proxy."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.bot_detection import run_botrhg_detection
from app.core.account_profiler import build_account_profiles

__all__ = [
    "NLPCC_CODE_ROOT",
    "build_account_detection_detail",
    "build_nlpcc_method_card",
]

NLPCC_CODE_ROOT = Path(r"G:\Research\BotDetection\NLPCC\code")


def build_nlpcc_method_card() -> dict[str, Any]:
    """Return the stable method metadata exposed by the account detector."""

    return {
        "method": "NLPCC2026GraphDetector",
        "runtime_mode": "proxy",
        "source_code_root": str(NLPCC_CODE_ROOT),
        "graph_backbone": "rgcn",
        "text_encoder": "roberta-base",
        "routing_strategy": "weighted_reference_tail",
        "support_k": 8,
        "note": "The research code directory currently provides the contract shell only; the system uses a proxy runtime over the live social posts.",
    }


def build_account_detection_detail(
    posts: list[dict[str, Any]],
    account_id: str,
    *,
    routing_budget: float = 0.2,
    support_k: int = 8,
) -> dict[str, Any] | None:
    """Build the account-level detection snapshot for one account."""

    if not posts:
        return None

    detection = run_botrhg_detection(posts, routing_budget=routing_budget, support_k=support_k)
    account_rows = {str(row["account_id"]): row for row in detection.get("accounts", [])}
    account_row = account_rows.get(str(account_id))
    if account_row is None:
        return None

    profile_rows = build_account_profiles(posts)
    profile_map = {str(row["account_id"]): row for row in profile_rows}
    support_rows = []
    for support_row in account_row.get("support_evidence", []):
        support_account_id = str(support_row.get("account_id") or "")
        support_profile = profile_map.get(support_account_id, {})
        support_rows.append(
            {
                **support_row,
                "author_name": support_profile.get("author_name") or support_account_id,
                "post_count": support_profile.get("post_count", 0),
                "automation_score": support_profile.get("automation_score", 0),
                "user_url": support_profile.get("user_url", ""),
            }
        )

    similar_users = [
        {
            "account_id": row["account_id"],
            "author_name": row.get("author_name") or row["account_id"],
            "similarity": row.get("similarity", 0.0),
            "final_bot_probability": row.get("final_bot_probability", row.get("base_bot_probability", 0.0)),
            "final_prediction": row.get("final_prediction", row.get("base_prediction", "human")),
            "routed": bool(row.get("routed", False)),
            "post_count": row.get("post_count", 0),
            "user_url": row.get("user_url", ""),
        }
        for row in support_rows
    ]

    return {
        "method": detection.get("method", "BotRHG"),
        "method_card": {
            **detection.get("model_card", {}),
            **build_nlpcc_method_card(),
        },
        "account": account_row,
        "similar_users": similar_users,
        "support_evidence": support_rows,
        "summary": detection.get("summary", {}),
    }
