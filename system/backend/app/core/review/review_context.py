"""Role-scoped Review input bundles.

The Teacher prompt and provider payload must expose only the evidence relevant
to the current Agent role. This module deliberately contains projection logic,
not retrieval or judgement logic.
"""

from __future__ import annotations

from typing import Any


ROLE_KEYS = {
    "PostHarmAgent": {
        "post_fields": (
            "post_id",
            "content",
            "text",
            "excerpt",
            "language",
            "lang",
            "hashtags",
            "harmfulness",
            "post_view_detection",
            "target_groups",
        ),
        "context_fields": ("schema_version", "input_refs", "review_task", "capability_boundary"),
    },
    "ClaimEvidenceAgent": {
        "post_fields": (
            "post_id",
            "content",
            "text",
            "excerpt",
            "language",
            "lang",
            "hashtags",
            "claims",
            "primary_claim",
            "claim_context",
            "stance",
        ),
        "context_fields": (
            "schema_version",
            "input_refs",
            "review_task",
            "review_queue",
            "active_retrieval",
            "evidence_bundle",
        ),
    },
    "PropagationTreeAgent": {
        "post_fields": ("post_id", "content", "text", "excerpt", "created_at", "author_id"),
        "context_fields": ("schema_version", "input_refs", "review_task", "propagation_context"),
    },
    "MultimodalConsistencyAgent": {
        "post_fields": (
            "post_id",
            "content",
            "text",
            "excerpt",
            "post_view_detection",
            "evidence",
            "media_urls",
        ),
        "context_fields": ("schema_version", "input_refs", "review_task", "media_inputs", "capability_boundary"),
    },
}


def scope_agent_context(agent_name: str, context: dict[str, Any]) -> dict[str, Any]:
    """Return the minimum typed context appropriate for one Agent role."""

    role = str(agent_name or "").split(":", 1)[0]
    if role in ROLE_KEYS:
        spec = ROLE_KEYS[role]
        scoped = {
            key: context.get(key)
            for key in spec["context_fields"]
            if key in context
        }
        scoped["selected_posts"] = [
            _project_post(post, spec["post_fields"])
            for post in _as_dicts(context.get("selected_posts"))
        ]
        return scoped

    if role in {"QuestionReflectionAgent", "HarmfulnessJudgeAgent", "CountermeasureAgent"}:
        scoped = {
            key: context.get(key)
            for key in (
                "schema_version",
                "input_refs",
                "review_task",
                "review_queue",
                "active_retrieval",
                "evidence_bundle",
                "policy_bundles",
                "rationale_capsules",
                "policy_decision_frame",
            )
            if key in context
        }
        scoped["selected_posts"] = [
            _project_post(post, ("post_id", "content", "text", "excerpt", "language", "lang"))
            for post in _as_dicts(context.get("selected_posts"))
        ]
        return scoped

    # Keep legacy debate/provider roles compatible, while still copying the
    # mapping so a provider cannot mutate the canonical context in-place.
    return dict(context)


def _project_post(post: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    return {field: post[field] for field in fields if field in post}


def _as_dicts(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return [item for item in values if isinstance(item, dict)]


__all__ = ["ROLE_KEYS", "scope_agent_context"]
