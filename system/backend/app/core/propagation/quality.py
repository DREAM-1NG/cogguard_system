from __future__ import annotations

from collections import Counter
import re
from typing import Any

import pandas as pd


def build_user_quality_portrait(posts: list[dict], comments: list[dict]) -> dict:
    users: dict[str, dict] = {}
    for record in list(posts) + list(comments):
        user_id = str(record.get("author_id") or record.get("user_id") or "")
        if not user_id:
            continue
        profile = users.setdefault(
            user_id,
            {
                "account_id": user_id,
                "author_name": record.get("author_name") or record.get("nickname") or user_id,
                "post_count": 0,
                "followers": None,
                "following": None,
                "statuses": None,
                "verified": None,
            },
        )
        profile["post_count"] += 1
        for target, keys in {
            "followers": ("followers_count", "followers", "fans_count", "fan_count"),
            "following": ("friends_count", "following_count", "follow_count"),
            "statuses": ("statuses_count", "post_count", "tweet_count", "weibo_count"),
        }.items():
            value = _to_number(_profile_value(record, *keys))
            if value is not None:
                profile[target] = max(profile[target] or 0, value)
        verified = _to_bool(_profile_value(record, "verified", "is_verified", "verified_type"))
        if verified is not None:
            profile["verified"] = bool(profile["verified"] or verified)

    bucket_counts: Counter[str] = Counter()
    verified_count = 0
    followers_values: list[int] = []
    metrics_available = 0
    top_accounts: list[dict] = []

    for profile in users.values():
        bucket = _quality_bucket(profile)
        bucket_counts[bucket] += 1
        if profile.get("verified"):
            verified_count += 1
        if profile.get("followers") is not None:
            followers_values.append(int(profile["followers"]))
        if any(profile.get(key) is not None for key in ("followers", "following", "statuses", "verified")):
            metrics_available += 1
        top_accounts.append(
            {
                "account_id": profile["account_id"],
                "author_name": profile["author_name"],
                "quality": bucket,
                "followers": profile.get("followers"),
                "verified": bool(profile.get("verified")),
                "post_count": profile.get("post_count", 0),
            }
        )

    total = max(len(users), 1)
    top_accounts.sort(
        key=lambda item: (
            item["quality"] == "高",
            item["quality"] == "中",
            item.get("followers") or 0,
            item.get("post_count") or 0,
        ),
        reverse=True,
    )

    return {
        "total_users": len(users),
        "metrics_available": metrics_available,
        "verified_count": verified_count,
        "verified_rate": round(verified_count / total, 4) if users else 0,
        "avg_followers": round(sum(followers_values) / len(followers_values), 2) if followers_values else None,
        "buckets": [
            {
                "quality": label,
                "count": bucket_counts.get(label, 0),
                "ratio": round(bucket_counts.get(label, 0) / total, 4),
            }
            for label in ("高", "中", "低", "未知")
        ],
        "top_accounts": top_accounts[:10],
    }


def _profile_value(record: dict, *keys: str) -> Any:
    for key in keys:
        for path in _field_paths(key):
            value = _nested_get(record, path)
            if value not in (None, ""):
                return value
    return None


def _field_paths(key: str) -> list[tuple[str, ...]]:
    return [
        (key,),
        ("author_profile", key),
        ("user", key),
        ("raw_data", key),
        ("raw_data", "user", key),
        ("raw_data", "mblog", key),
        ("raw_data", "mblog", "user", key),
        ("raw_data", "post_details_raw", key),
        ("raw_data", "post_details_raw", "mblog", key),
        ("raw_data", "post_details_raw", "mblog", "user", key),
        ("post_details_raw", key),
        ("post_details_raw", "mblog", key),
        ("post_details_raw", "mblog", "user", key),
    ]


def _nested_get(data: dict, path: tuple[str, ...]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _to_number(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)) and not pd.isna(value):
        return int(value)
    text = str(value).replace(",", "").strip()
    if not text:
        return None
    multiplier = 1
    if text.endswith("万"):
        multiplier = 10000
        text = text[:-1]
    elif text.endswith("亿"):
        multiplier = 100000000
        text = text[:-1]
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return int(float(match.group(0)) * multiplier)


def _to_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not pd.isna(value):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "yes", "y", "1", "认证", "已认证"}:
        return True
    if text in {"false", "no", "n", "0", "未认证", "未验证"}:
        return False
    return None


def _quality_bucket(profile: dict) -> str:
    has_signal = any(profile.get(key) is not None for key in ("followers", "following", "statuses", "verified"))
    if not has_signal:
        return "未知"

    followers = profile.get("followers") or 0
    following = profile.get("following") or 0
    statuses = profile.get("statuses") or 0
    score = 0
    if followers >= 10000:
        score += 3
    elif followers >= 1000:
        score += 2
    elif followers >= 100:
        score += 1
    if profile.get("verified"):
        score += 2
    if statuses >= 1000:
        score += 1
    if following and followers / max(following, 1) >= 2:
        score += 1

    if score >= 4:
        return "高"
    if score >= 2:
        return "中"
    return "低"
