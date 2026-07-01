"""Layered KT3 harmfulness aggregation.

The post-level module judges individual items. This module lifts those
judgements to account and community views so the final risk report exposes the
three KT3 layers described in the requirements document.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from typing import Any


def assess_layered_harmfulness(
    *,
    post_semantics: dict[str, Any] | None,
    account_profiles: list[dict[str, Any]] | None,
    coordination: dict[str, Any] | None,
    propagation: dict[str, Any] | None,
    event_id: str | None = None,
    platform: str | None = None,
) -> dict[str, Any]:
    """Aggregate KT3 post-level semantics into user and community layers."""
    post_semantics = post_semantics or {}
    account_profiles = account_profiles or []
    coordination = coordination or {}
    propagation = propagation or {}

    posts = _semantic_posts(post_semantics)
    account_profile_map = {
        str(profile.get("account_id") or ""): profile
        for profile in account_profiles
        if str(profile.get("account_id") or "").strip()
    }
    coordinated_accounts = _coordinated_accounts(coordination)
    propagation_roles = _propagation_roles(propagation)
    post_timestamps = _post_timestamps(propagation)
    community_map = _community_membership(coordination, propagation, posts)

    account_level = _build_account_level(
        posts=posts,
        account_profiles=account_profile_map,
        coordinated_accounts=coordinated_accounts,
        propagation_roles=propagation_roles,
        post_timestamps=post_timestamps,
        community_map=community_map,
    )
    community_level = _build_community_level(
        account_level=account_level["accounts"],
        coordination=coordination,
    )
    global_summary = _build_global_summary(posts, account_level, community_level)

    return {
        "scope": {
            "event_id": event_id,
            "platform": platform,
        },
        "capability_boundary": {
            "post_level": "runtime_semantic_scaffold",
            "user_level": "implemented_runtime_aggregation",
            "community_level": "implemented_runtime_aggregation",
            "modeling_note": (
                "This release aggregates post-level semantic judgements into account "
                "and community views. It is not yet a trained heterogeneous graph model."
            ),
        },
        "post_level": {
            "summary": post_semantics.get("summary", {}),
            "analysis_scope": post_semantics.get("analysis_scope", {}),
        },
        "user_level": account_level,
        "community_level": community_level,
        "global_summary": global_summary,
        "audit": _build_audit(posts, account_profile_map),
    }


def _semantic_posts(post_semantics: dict[str, Any]) -> list[dict[str, Any]]:
    posts = post_semantics.get("aggregation_posts")
    if isinstance(posts, list):
        return posts
    posts = post_semantics.get("posts")
    return posts if isinstance(posts, list) else []


def _coordinated_accounts(coordination: dict[str, Any]) -> set[str]:
    accounts: set[str] = set()
    for row in coordination.get("account_stats") or []:
        account_id = str(row.get("account_id") or row.get("id") or "").strip()
        if account_id:
            accounts.add(account_id)
    for node in (coordination.get("network") or {}).get("nodes") or []:
        account_id = str(node.get("id") or node.get("account_id") or "").strip()
        if account_id:
            accounts.add(account_id)
    return accounts


def _propagation_roles(propagation: dict[str, Any]) -> dict[str, set[str]]:
    roles = {
        "originator": set(),
        "bridge": set(),
        "amplifier": set(),
    }
    key_roles = propagation.get("key_roles") or {}
    role_sources = {
        "originator": key_roles.get("originators") or [],
        "bridge": key_roles.get("bridges") or [],
        "amplifier": key_roles.get("amplifiers") or [],
    }
    for role, rows in role_sources.items():
        for row in rows:
            account_id = str(row.get("account_id") or row.get("id") or "").strip()
            if account_id:
                roles[role].add(account_id)
    return roles


def _post_timestamps(propagation: dict[str, Any]) -> dict[str, datetime]:
    timestamps: dict[str, datetime] = {}
    for row in propagation.get("timeline") or []:
        post_id = str(row.get("post_id") or "").strip()
        timestamp = _parse_datetime(row.get("timestamp"))
        if post_id and timestamp is not None:
            timestamps[post_id] = timestamp
    for chain in propagation.get("evidence_chains") or []:
        for post in chain.get("supporting_posts") or []:
            post_id = str(post.get("post_id") or "").strip()
            timestamp = _parse_datetime(post.get("timestamp"))
            if post_id and timestamp is not None:
                timestamps.setdefault(post_id, timestamp)
    return timestamps


def _community_membership(
    coordination: dict[str, Any],
    propagation: dict[str, Any],
    posts: list[dict[str, Any]],
) -> dict[str, str]:
    membership: dict[str, str] = {}
    network = coordination.get("network") or {}

    for prefix, rows in (
        ("component", network.get("components") or []),
        ("cluster", network.get("clusters") or coordination.get("cluster_stats") or []),
        ("group", coordination.get("group_stats") or []),
    ):
        for index, row in enumerate(rows):
            community_id = str(row.get("id") or row.get("cluster_id") or row.get("component_id") or f"{prefix}_{index}")
            for account_id in _extract_member_ids(row):
                membership.setdefault(account_id, community_id)

    if not membership:
        for node in network.get("nodes") or []:
            account_id = str(node.get("id") or node.get("account_id") or "").strip()
            if account_id:
                membership[account_id] = "community_all"

    if not membership:
        for node in (propagation.get("graph") or {}).get("nodes") or []:
            account_id = str(node.get("id") or node.get("account_id") or "").strip()
            if account_id:
                membership[account_id] = "community_all"

    if not membership:
        for post in posts:
            account_id = str(post.get("author_id") or "").strip()
            if account_id:
                membership[account_id] = "community_all"
    return membership


def _extract_member_ids(row: dict[str, Any]) -> set[str]:
    members: set[str] = set()
    for key in ("accounts", "members", "nodes", "account_ids", "member_ids"):
        value = row.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    account_id = str(item.get("id") or item.get("account_id") or "").strip()
                else:
                    account_id = str(item or "").strip()
                if account_id:
                    members.add(account_id)
    return members


def _build_account_level(
    *,
    posts: list[dict[str, Any]],
    account_profiles: dict[str, dict[str, Any]],
    coordinated_accounts: set[str],
    propagation_roles: dict[str, set[str]],
    post_timestamps: dict[str, datetime],
    community_map: dict[str, str],
) -> dict[str, Any]:
    grouped_posts: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for post in posts:
        account_id = str(post.get("author_id") or "").strip()
        if account_id:
            grouped_posts[account_id].append(post)

    for account_id in account_profiles:
        grouped_posts.setdefault(account_id, [])
    for account_id in coordinated_accounts:
        grouped_posts.setdefault(account_id, [])

    accounts = [
        _build_account_summary(
            account_id=account_id,
            posts=account_posts,
            profile=account_profiles.get(account_id, {}),
            coordinated=account_id in coordinated_accounts,
            roles=_roles_for_account(account_id, propagation_roles),
            timestamps=post_timestamps,
            community_id=community_map.get(account_id),
        )
        for account_id, account_posts in grouped_posts.items()
    ]
    accounts.sort(
        key=lambda item: (
            item["risk_summary"]["harmful_posts"],
            item["risk_summary"]["avg_harm_score"],
            item["profile_signals"]["automation_score"],
        ),
        reverse=True,
    )

    harmful_accounts = sum(1 for item in accounts if item["risk_profile_flags"]["high_harmful"])
    return {
        "summary": {
            "account_count": len(accounts),
            "accounts_with_semantic_posts": sum(1 for item in accounts if item["risk_summary"]["input_posts"] > 0),
            "harmful_accounts": harmful_accounts,
            "coordinated_accounts": sum(1 for item in accounts if item["risk_profile_flags"]["coordinated"]),
        },
        "accounts": accounts[:50],
    }


def _build_account_summary(
    *,
    account_id: str,
    posts: list[dict[str, Any]],
    profile: dict[str, Any],
    coordinated: bool,
    roles: list[str],
    timestamps: dict[str, datetime],
    community_id: str | None,
) -> dict[str, Any]:
    harm_scores = [_harm_score(post) for post in posts]
    harmful_posts = [post for post in posts if _harm_label(post) == "harmful"]
    linked_posts = [post for post in posts if post.get("primary_claim")]
    harm_types = Counter()
    stance_distribution = Counter()
    claim_counter: dict[str, dict[str, Any]] = {}

    for post in posts:
        harm_types.update(_harm_types(post))
        stance_label = str((post.get("stance") or {}).get("label") or "unknown")
        stance_distribution[stance_label] += 1
        claim = post.get("primary_claim") or {}
        claim_id = str(claim.get("claim_id") or "").strip()
        if claim_id:
            entry = claim_counter.setdefault(
                claim_id,
                {
                    "claim_id": claim_id,
                    "claim_text": str(claim.get("claim_text") or "")[:240],
                    "linked_posts": 0,
                    "harmful_posts": 0,
                    "support": 0,
                    "deny": 0,
                    "query": 0,
                    "neutral": 0,
                },
            )
            entry["linked_posts"] += 1
            if _harm_label(post) == "harmful":
                entry["harmful_posts"] += 1
            if stance_label in {"support", "deny", "query", "neutral"}:
                entry[stance_label] += 1

    input_posts = len(posts)
    harmful_ratio = len(harmful_posts) / input_posts if input_posts else 0.0
    avg_harm_score = sum(harm_scores) / len(harm_scores) if harm_scores else 0.0
    persistence_score = _persistence_score(
        harmful_ratio=harmful_ratio,
        linked_claim_count=len(claim_counter),
        input_posts=input_posts,
    )
    role_mix = _harmful_roles(roles, harm_types)
    trajectory = _trajectory(posts, timestamps)
    automation_score = float(profile.get("automation_score") or 0)

    return {
        "account_id": account_id,
        "author_name": profile.get("author_name") or _first_author_name(posts) or account_id,
        "community_id": community_id,
        "risk_summary": {
            "input_posts": input_posts,
            "linked_posts": len(linked_posts),
            "harmful_posts": len(harmful_posts),
            "harmful_ratio": round(harmful_ratio, 4),
            "avg_harm_score": round(avg_harm_score, 4),
            "persistence_score": round(persistence_score, 4),
            "stance_distribution": dict(stance_distribution),
            "harm_types": dict(harm_types),
            "trajectory": trajectory,
        },
        "top_claims": sorted(
            claim_counter.values(),
            key=lambda item: (item["harmful_posts"], item["linked_posts"]),
            reverse=True,
        )[:5],
        "role_profile": {
            "propagation_roles": roles or ["participant"],
            "harmful_roles": role_mix,
        },
        "profile_signals": {
            "automation_score": round(automation_score, 2),
            "regularity": round(float(profile.get("regularity") or 0), 4),
            "post_count": int(profile.get("post_count") or input_posts),
        },
        "risk_profile_flags": {
            "high_harmful": harmful_ratio >= 0.5 or len(harmful_posts) >= 3,
            "high_automation": automation_score >= 60,
            "coordinated": coordinated,
            "needs_review": any(_post_needs_review(post) for post in posts),
        },
        "representative_posts": _representative_posts(posts),
    }


def _roles_for_account(account_id: str, propagation_roles: dict[str, set[str]]) -> list[str]:
    roles = [role for role, members in propagation_roles.items() if account_id in members]
    return sorted(roles)


def _harmful_roles(roles: list[str], harm_types: Counter[str]) -> list[str]:
    harmful_roles: set[str] = set()
    if "originator" in roles:
        harmful_roles.add("originator")
    if "bridge" in roles:
        harmful_roles.add("bridge_relay")
    if "amplifier" in roles:
        harmful_roles.add("amplifier")
    if harm_types.get("hate_harassment", 0):
        harmful_roles.add("harasser")
    if harm_types.get("targeted_smear", 0):
        harmful_roles.add("smear_account")
    if harm_types.get("incitement_mobilization", 0):
        harmful_roles.add("mobilizer")
    if harm_types.get("manipulative_amplification", 0):
        harmful_roles.add("attention_shaper")
    return sorted(harmful_roles) or ["participant"]


def _persistence_score(
    *,
    harmful_ratio: float,
    linked_claim_count: int,
    input_posts: int,
) -> float:
    claim_span = min(1.0, linked_claim_count / 3) if linked_claim_count else 0.0
    sample_support = min(1.0, input_posts / 5) if input_posts else 0.0
    return min(1.0, 0.55 * harmful_ratio + 0.25 * claim_span + 0.20 * sample_support)


def _trajectory(posts: list[dict[str, Any]], timestamps: dict[str, datetime]) -> str:
    timed_posts = [
        (timestamps.get(str(post.get("post_id") or "")), post)
        for post in posts
    ]
    timed_posts = [(ts, post) for ts, post in timed_posts if ts is not None]
    if len(timed_posts) < 4:
        return "insufficient_temporal_evidence"
    timed_posts.sort(key=lambda item: item[0])
    midpoint = len(timed_posts) // 2
    early = timed_posts[:midpoint]
    late = timed_posts[midpoint:]
    early_avg = sum(_harm_score(post) for _ts, post in early) / len(early)
    late_avg = sum(_harm_score(post) for _ts, post in late) / len(late)
    if late_avg - early_avg >= 0.12:
        return "escalating"
    if early_avg - late_avg >= 0.12:
        return "decaying"
    return "stable"


def _representative_posts(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(posts, key=_harm_score, reverse=True)
    return [
        {
            "post_id": post.get("post_id"),
            "excerpt": post.get("excerpt", ""),
            "harm_label": _harm_label(post),
            "harm_score": round(_harm_score(post), 4),
            "primary_type": (post.get("harmfulness") or {}).get("primary_type"),
            "primary_claim": post.get("primary_claim"),
        }
        for post in ranked[:3]
    ]


def _build_community_level(
    *,
    account_level: list[dict[str, Any]],
    coordination: dict[str, Any],
) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for account in account_level:
        community_id = account.get("community_id") or "community_all"
        grouped[str(community_id)].append(account)

    community_metrics = _coordination_community_metrics(coordination)
    communities = [
        _build_community_summary(
            community_id=community_id,
            accounts=accounts,
            metrics=community_metrics.get(community_id, {}),
        )
        for community_id, accounts in grouped.items()
    ]
    communities.sort(
        key=lambda item: (
            item["risk_summary"]["harmful_posts"],
            item["risk_summary"]["harmful_accounts"],
            item["member_count"],
        ),
        reverse=True,
    )

    return {
        "summary": {
            "community_count": len(communities),
            "harmful_communities": sum(1 for item in communities if item["risk_flags"]["high_collective_harm"]),
        },
        "communities": communities[:20],
    }


def _coordination_community_metrics(coordination: dict[str, Any]) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    network = coordination.get("network") or {}
    for prefix, rows in (
        ("component", network.get("components") or []),
        ("cluster", network.get("clusters") or coordination.get("cluster_stats") or []),
    ):
        for index, row in enumerate(rows):
            community_id = str(row.get("id") or row.get("cluster_id") or row.get("component_id") or f"{prefix}_{index}")
            metrics[community_id] = {
                "member_count": int(row.get("size") or row.get("member_count") or len(_extract_member_ids(row))),
                "edge_count": _safe_count(row.get("edge_count") or row.get("edges") or 0),
                "density": round(float(row.get("density") or 0), 4),
            }
    if not metrics and network.get("node_count"):
        metrics["community_all"] = {
            "member_count": int(network.get("node_count") or 0),
            "edge_count": int(network.get("edge_count") or 0),
            "density": 0.0,
        }
    return metrics


def _build_community_summary(
    *,
    community_id: str,
    accounts: list[dict[str, Any]],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    harm_types = Counter()
    stance_distribution = Counter()
    claim_counter: dict[str, dict[str, Any]] = {}
    subgroup_roles = Counter()
    harmful_posts = 0
    semantic_posts = 0
    harmful_accounts = 0

    for account in accounts:
        summary = account["risk_summary"]
        semantic_posts += int(summary["input_posts"])
        harmful_posts += int(summary["harmful_posts"])
        if account["risk_profile_flags"]["high_harmful"]:
            harmful_accounts += 1
        harm_types.update(summary.get("harm_types") or {})
        stance_distribution.update(summary.get("stance_distribution") or {})
        subgroup_roles.update(account.get("role_profile", {}).get("harmful_roles") or [])
        for claim in account.get("top_claims") or []:
            claim_id = claim["claim_id"]
            entry = claim_counter.setdefault(
                claim_id,
                {
                    "claim_id": claim_id,
                    "claim_text": claim.get("claim_text", ""),
                    "linked_posts": 0,
                    "harmful_posts": 0,
                    "linked_accounts": 0,
                },
            )
            entry["linked_posts"] += int(claim.get("linked_posts") or 0)
            entry["harmful_posts"] += int(claim.get("harmful_posts") or 0)
            entry["linked_accounts"] += 1

    harmful_ratio = harmful_posts / semantic_posts if semantic_posts else 0.0
    coordinated_member_count = sum(1 for item in accounts if item["risk_profile_flags"]["coordinated"])
    amplification_score = min(
        1.0,
        0.45 * harmful_ratio
        + 0.35 * (coordinated_member_count / max(len(accounts), 1))
        + 0.20 * min(1.0, len(claim_counter) / 5),
    )

    return {
        "community_id": community_id,
        "member_count": int(metrics.get("member_count") or len(accounts)),
        "coord_edge_count": int(metrics.get("edge_count") or 0),
        "coord_density": round(float(metrics.get("density") or 0), 4),
        "risk_summary": {
            "semantic_posts": semantic_posts,
            "harmful_posts": harmful_posts,
            "harmful_ratio": round(harmful_ratio, 4),
            "harmful_accounts": harmful_accounts,
            "dominant_harm_types": dict(harm_types.most_common(5)),
            "stance_distribution": dict(stance_distribution),
            "amplification_score": round(amplification_score, 4),
        },
        "subgroup_roles": dict(subgroup_roles),
        "claims_coverage": sorted(
            claim_counter.values(),
            key=lambda item: (item["harmful_posts"], item["linked_posts"], item["linked_accounts"]),
            reverse=True,
        )[:10],
        "key_accounts": [
            {
                "account_id": account["account_id"],
                "author_name": account["author_name"],
                "harmful_posts": account["risk_summary"]["harmful_posts"],
                "roles": account["role_profile"]["harmful_roles"],
            }
            for account in accounts[:10]
        ],
        "risk_flags": {
            "high_collective_harm": harmful_ratio >= 0.35 or harmful_posts >= 5,
            "coordinated_harm_amplification": amplification_score >= 0.45 and coordinated_member_count > 0,
            "needs_review": any(account["risk_profile_flags"]["needs_review"] for account in accounts),
        },
    }


def _build_global_summary(
    posts: list[dict[str, Any]],
    account_level: dict[str, Any],
    community_level: dict[str, Any],
) -> dict[str, Any]:
    harm_types = Counter()
    stance_distribution = Counter()
    claim_counter: dict[str, dict[str, Any]] = {}

    for post in posts:
        harm_types.update(_harm_types(post))
        stance_distribution[str((post.get("stance") or {}).get("label") or "unknown")] += 1
        claim = post.get("primary_claim") or {}
        claim_id = str(claim.get("claim_id") or "").strip()
        if claim_id:
            entry = claim_counter.setdefault(
                claim_id,
                {
                    "claim_id": claim_id,
                    "claim_text": str(claim.get("claim_text") or "")[:240],
                    "linked_posts": 0,
                    "harmful_posts": 0,
                },
            )
            entry["linked_posts"] += 1
            if _harm_label(post) == "harmful":
                entry["harmful_posts"] += 1

    harmful_ratio = (
        sum(1 for post in posts if _harm_label(post) == "harmful") / len(posts)
        if posts
        else 0.0
    )
    harmful_accounts = account_level["summary"]["harmful_accounts"]
    harmful_communities = community_level["summary"]["harmful_communities"]
    if harmful_ratio >= 0.45 or harmful_communities >= 2:
        risk_level = "high"
    elif harmful_ratio >= 0.2 or harmful_accounts >= 2 or harmful_communities >= 1:
        risk_level = "medium"
    else:
        risk_level = "low"

    return {
        "harm_types": dict(harm_types),
        "stance_distribution": dict(stance_distribution),
        "claim_rank": sorted(
            claim_counter.values(),
            key=lambda item: (item["harmful_posts"], item["linked_posts"]),
            reverse=True,
        )[:10],
        "kt3_harm_risk_level": risk_level,
    }


def _build_audit(
    posts: list[dict[str, Any]],
    account_profiles: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    post_account_ids = {str(post.get("author_id") or "").strip() for post in posts if post.get("author_id")}
    missing_profiles = post_account_ids - set(account_profiles)
    unlinked_posts = sum(1 for post in posts if not post.get("primary_claim"))
    return {
        "semantic_posts_used": len(posts),
        "missing_account_profiles": len(missing_profiles),
        "missing_claim_match_ratio": round(unlinked_posts / len(posts), 4) if posts else 0.0,
        "aggregation_source": "post_semantics.aggregation_posts" if posts else "none",
    }


def _harm_label(post: dict[str, Any]) -> str:
    return str((post.get("harmfulness") or {}).get("label") or "unknown")


def _harm_score(post: dict[str, Any]) -> float:
    try:
        return float((post.get("harmfulness") or {}).get("score") or 0)
    except (TypeError, ValueError):
        return 0.0


def _harm_types(post: dict[str, Any]) -> list[str]:
    harm = post.get("harmfulness") or {}
    values = harm.get("types") or []
    return [str(value) for value in values if value]


def _post_needs_review(post: dict[str, Any]) -> bool:
    harm = post.get("harmfulness") or {}
    stance = post.get("stance") or {}
    harm_label = str(harm.get("label") or "")
    stance_label = str(stance.get("label") or "")
    has_claim = bool(post.get("primary_claim"))
    harm_score = _harm_score(post)
    stance_confidence = _safe_float(stance.get("confidence"))
    return (
        bool(harm.get("abstain"))
        or bool(stance.get("abstain"))
        or harm_label == "uncertain"
        or stance_label in {"uncertain", "unlinked"}
        or (harm_label == "harmful" and not has_claim)
        or (harm_label in {"harmful", "uncertain"} and harm_score < 0.6)
        or (has_claim and stance_confidence < 0.45)
    )


def _first_author_name(posts: list[dict[str, Any]]) -> str:
    for post in posts:
        author_name = str(post.get("author_name") or "").strip()
        if author_name:
            return author_name
    return ""


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(normalized)
        except ValueError:
            return None
    return None


def _safe_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
