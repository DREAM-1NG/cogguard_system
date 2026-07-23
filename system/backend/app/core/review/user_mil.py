"""Review user-level attention-MIL harmfulness scaffold.

This module treats an account as a bag of post instances. It follows the
attention-MIL problem shape from Ilse et al. (ICML 2018): infer a bag-level
label while preserving instance contributions. The current implementation is a
deterministic inference scaffold over Review post-level semantic outputs, not a
trained neural MIL model.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from math import exp
from typing import Any


USER_MIL_METHOD_TRACE = [
    {
        "paper": "Ilse et al., ICML 2018",
        "transfer": (
            "model an account as a bag of post instances and expose attention "
            "weights as instance-level contribution evidence"
        ),
    },
    {
        "paper": "Ribeiro et al., ICWSM 2018",
        "transfer": (
            "move from isolated content decisions to user-centric harmfulness "
            "characterization over account history"
        ),
    },
    {
        "paper": "Mishra et al., Findings EMNLP 2021",
        "transfer": (
            "preserve explainability and ethical boundaries when modeling users "
            "and online communities for abuse detection"
        ),
    },
    {
        "paper": "Ge et al., WWW 2021",
        "transfer": (
            "treat interaction/session context as part of abuse evidence rather "
            "than relying only on individual post labels"
        ),
    },
]

MAX_ACCOUNT_RESULTS = 50
MAX_ATTENTION_POSTS = 5


def score_user_mil(
    *,
    post_semantics: dict[str, Any] | None,
    account_profiles: list[dict[str, Any]] | None = None,
    coordination: dict[str, Any] | None = None,
    propagation: dict[str, Any] | None = None,
    existing_user_level: dict[str, Any] | None = None,
    event_id: str | None = None,
    platform: str | None = None,
    max_accounts: int = MAX_ACCOUNT_RESULTS,
    max_attention_posts: int = MAX_ATTENTION_POSTS,
) -> dict[str, Any]:
    """Score account bags with deterministic attention-MIL style aggregation."""
    post_semantics = post_semantics or {}
    account_profiles = account_profiles or []
    coordination = coordination or {}
    propagation = propagation or {}
    existing_user_level = existing_user_level or {}

    posts = _semantic_posts(post_semantics)
    grouped_posts: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for post in posts:
        account_id = _text(post.get("author_id"))
        if account_id:
            grouped_posts[account_id].append(post)

    profile_map = {
        _text(profile.get("account_id")): profile
        for profile in account_profiles
        if _text(profile.get("account_id"))
    }
    coordinated_accounts = _coordinated_accounts(coordination)
    propagation_roles = _propagation_roles(propagation)
    existing_accounts = {
        _text(account.get("account_id")): account
        for account in _as_list(existing_user_level.get("accounts"))
        if _text(account.get("account_id"))
    }

    for account_id in profile_map:
        grouped_posts.setdefault(account_id, [])
    for account_id in coordinated_accounts:
        grouped_posts.setdefault(account_id, [])
    for account_id in existing_accounts:
        grouped_posts.setdefault(account_id, [])

    account_results = [
        _score_account_bag(
            account_id=account_id,
            posts=account_posts,
            profile=profile_map.get(account_id, {}),
            coordinated=account_id in coordinated_accounts,
            roles=sorted(role for role, members in propagation_roles.items() if account_id in members),
            existing_account=existing_accounts.get(account_id, {}),
            max_attention_posts=max_attention_posts,
        )
        for account_id, account_posts in grouped_posts.items()
    ]
    account_results.sort(
        key=lambda item: (
            item["mil_harm_score"],
            item["bag_size"],
            item["context"]["coordinated"],
        ),
        reverse=True,
    )

    instances = sum(item["bag_size"] for item in account_results)
    harmful_accounts = sum(1 for item in account_results if item["label"] == "harmful")
    uncertain_accounts = sum(1 for item in account_results if item["label"] == "uncertain")

    return {
        "capability_boundary": {
            "status": "implemented_attention_mil_inference_scaffold",
            "trained_mil_model": False,
            "trained_user_encoder": False,
            "online_training": False,
            "uses_runtime_gold": False,
            "description": (
                "Accounts are represented as bags of Review post-level semantic "
                "instances and aggregated with deterministic attention-style "
                "weights. This is not a trained neural MIL or temporal model."
            ),
        },
        "method_trace": USER_MIL_METHOD_TRACE,
        "scope": {
            "event_id": event_id,
            "platform": platform,
        },
        "analysis_scope": {
            "bag_count": len(account_results),
            "instances_evaluated": instances,
            "semantic_posts_available": len(posts),
            "accounts_with_profiles": len(profile_map),
            "coordinated_accounts": len(coordinated_accounts),
        },
        "summary": {
            "account_bags": len(account_results),
            "instances_evaluated": instances,
            "harmful_accounts": harmful_accounts,
            "uncertain_accounts": uncertain_accounts,
            "avg_mil_harm_score": round(
                sum(item["mil_harm_score"] for item in account_results) / len(account_results),
                4,
            )
            if account_results
            else 0.0,
            "method": "attention_mil_over_post_semantic_instances",
        },
        "accounts": account_results[:max_accounts],
    }


def _score_account_bag(
    *,
    account_id: str,
    posts: list[dict[str, Any]],
    profile: dict[str, Any],
    coordinated: bool,
    roles: list[str],
    existing_account: dict[str, Any],
    max_attention_posts: int,
) -> dict[str, Any]:
    instance_rows = [_instance_view(post) for post in posts]
    attention_weights = _attention_weights(instance_rows)
    weighted_score = sum(row["instance_score"] * weight for row, weight in zip(instance_rows, attention_weights))
    noisy_or_score = 1.0
    for row in instance_rows:
        noisy_or_score *= 1.0 - min(0.95, row["instance_score"] * 0.82)
    noisy_or_score = 1.0 - noisy_or_score if instance_rows else 0.0

    existing_summary = existing_account.get("risk_summary") or {}
    persistence_score = _safe_float(existing_summary.get("persistence_score"))
    context_boost = 0.04 if coordinated and instance_rows else 0.0
    role_boost = 0.03 if roles and instance_rows else 0.0
    sample_penalty = 0.08 if len(instance_rows) == 1 else 0.0
    mil_score = max(
        0.0,
        min(
            1.0,
            0.62 * weighted_score
            + 0.25 * noisy_or_score
            + 0.13 * persistence_score
            + context_boost
            + role_boost
            - sample_penalty,
        ),
    )

    harm_types = Counter()
    stance_distribution = Counter()
    for row in instance_rows:
        harm_types.update(row["harm_types"])
        stance_distribution[row["stance_label"]] += 1

    ranked_instances = sorted(
        [
            {
                **row,
                "attention_weight": round(weight, 4),
            }
            for row, weight in zip(instance_rows, attention_weights)
        ],
        key=lambda item: (item["attention_weight"], item["instance_score"]),
        reverse=True,
    )
    attention_posts = [
        {
            "post_id": row["post_id"],
            "excerpt": row["excerpt"],
            "instance_score": row["instance_score"],
            "attention_weight": row["attention_weight"],
            "harm_label": row["harm_label"],
            "harm_types": row["harm_types"],
            "stance_label": row["stance_label"],
            "primary_claim": row["primary_claim"],
            "evidence_modalities": row["evidence_modalities"],
        }
        for row in ranked_instances[:max_attention_posts]
    ]

    label = _mil_label(mil_score, len(instance_rows))
    return {
        "account_id": account_id,
        "author_name": profile.get("author_name") or existing_account.get("author_name") or account_id,
        "bag_size": len(instance_rows),
        "mil_harm_score": round(mil_score, 4),
        "label": label,
        "confidence": round(_confidence(mil_score, len(instance_rows)), 4),
        "attention_method": "softmax_over_post_harm_multimodal_claim_scores",
        "attention_posts": attention_posts,
        "harm_type_distribution": dict(harm_types),
        "stance_distribution": dict(stance_distribution),
        "context": {
            "coordinated": coordinated,
            "propagation_roles": roles or ["participant"],
            "automation_score": round(_safe_float(profile.get("automation_score")), 4),
            "existing_persistence_score": round(persistence_score, 4),
        },
        "evidence": {
            "top_posts": attention_posts,
            "source": "post_semantics.aggregation_posts",
            "existing_user_aggregation": {
                "risk_flags": existing_account.get("risk_profile_flags") or {},
                "risk_summary": existing_summary,
            },
        },
    }


def _instance_view(post: dict[str, Any]) -> dict[str, Any]:
    harm = post.get("harmfulness") or {}
    stance = post.get("stance") or {}
    multimodal = post.get("multimodal_detection") or {}
    primary_claim = post.get("primary_claim") or {}
    harm_score = _safe_float(harm.get("score"))
    multimodal_score = _safe_float(multimodal.get("fused_harm_score"))
    stance_support = 0.05 if stance.get("label") == "support" and primary_claim else 0.0
    claim_grounding = 0.03 if primary_claim else -0.02
    uncertainty_penalty = 0.05 if harm.get("abstain") or stance.get("abstain") else 0.0
    instance_score = max(
        0.0,
        min(
            1.0,
            0.58 * harm_score
            + 0.27 * multimodal_score
            + stance_support
            + claim_grounding
            - uncertainty_penalty,
        ),
    )
    return {
        "post_id": post.get("post_id"),
        "excerpt": _text(post.get("excerpt"))[:240],
        "instance_score": round(instance_score, 4),
        "harm_label": _text(harm.get("label")) or "unknown",
        "harm_types": _as_list(harm.get("types")),
        "stance_label": _text(stance.get("label")) or "unknown",
        "primary_claim": primary_claim,
        "evidence_modalities": _as_list(multimodal.get("evidence_modalities")) or _as_list(post.get("modalities")),
    }


def _attention_weights(instances: list[dict[str, Any]]) -> list[float]:
    if not instances:
        return []
    logits = [3.2 * row["instance_score"] for row in instances]
    max_logit = max(logits)
    values = [exp(logit - max_logit) for logit in logits]
    total = sum(values) or 1.0
    return [value / total for value in values]


def _mil_label(score: float, bag_size: int) -> str:
    if bag_size == 0:
        return "insufficient_evidence"
    if score >= 0.58:
        return "harmful"
    if score >= 0.43:
        return "uncertain"
    return "non_harmful"


def _confidence(score: float, bag_size: int) -> float:
    if bag_size == 0:
        return 0.0
    boundary_distance = min(abs(score - 0.43), abs(score - 0.58))
    sample_factor = min(1.0, bag_size / 5)
    return max(0.25, min(0.92, 0.45 + 0.65 * boundary_distance + 0.18 * sample_factor))


def _semantic_posts(post_semantics: dict[str, Any]) -> list[dict[str, Any]]:
    posts = post_semantics.get("aggregation_posts")
    if isinstance(posts, list):
        return posts
    posts = post_semantics.get("posts")
    return posts if isinstance(posts, list) else []


def _coordinated_accounts(coordination: dict[str, Any]) -> set[str]:
    accounts: set[str] = set()
    for row in coordination.get("account_stats") or []:
        account_id = _text(row.get("account_id") or row.get("id"))
        if account_id:
            accounts.add(account_id)
    for node in (coordination.get("network") or {}).get("nodes") or []:
        account_id = _text(node.get("id") or node.get("account_id"))
        if account_id:
            accounts.add(account_id)
    return accounts


def _propagation_roles(propagation: dict[str, Any]) -> dict[str, set[str]]:
    roles = {"originator": set(), "bridge": set(), "amplifier": set()}
    key_roles = propagation.get("key_roles") or {}
    for role, source_key in (
        ("originator", "originators"),
        ("bridge", "bridges"),
        ("amplifier", "amplifiers"),
    ):
        for row in key_roles.get(source_key) or []:
            account_id = _text(row.get("account_id") or row.get("id"))
            if account_id:
                roles[role].add(account_id)
    return roles


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
