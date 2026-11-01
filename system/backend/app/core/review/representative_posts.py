"""Select a bounded, auditable review sample from an event snapshot.

The selector is deliberately outside the risk judgement.  It only makes the
analyst's requested engagement-based sample reproducible, and it never reads
labels, model scores, or the post text when assigning priority.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from typing import Any


DEFAULT_REPRESENTATIVE_POST_LIMIT = 6

__all__ = [
    "DEFAULT_REPRESENTATIVE_POST_LIMIT",
    "select_representative_posts",
]


def select_representative_posts(
    posts: Iterable[Mapping[str, Any]],
    *,
    selected_post_ids: Iterable[str] | None = None,
    limit: int = DEFAULT_REPRESENTATIVE_POST_LIMIT,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return selected rows and a product-safe selection audit record.

    Explicit analyst selections win.  Otherwise, rank only measured repost,
    like, and comment counts, while retaining one leading post per platform
    when the event spans several platforms.
    """

    rows = [_normalized_row(row) for row in posts if _post_id(row)]
    maximum = max(1, min(int(limit or DEFAULT_REPRESENTATIVE_POST_LIMIT), 20))
    requested = _requested_ids(selected_post_ids)
    by_id = {row["post_id"]: row for row in rows}
    if requested:
        selected = [by_id[post_id] for post_id in requested if post_id in by_id][:maximum]
        return selected, _manifest(selected, source="analyst_selected", limit=maximum)

    if not rows:
        return [], _manifest([], source="engagement_representative", limit=maximum)

    scored = _rank_rows(rows)
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    for platform in _platform_order(scored):
        row = next((item for item in scored if item["platform"] == platform), None)
        if row is not None:
            _append_unique(selected, selected_ids, row, maximum)
    for metric in ("reposts", "likes", "comments"):
        row = max(scored, key=lambda item: (item["engagement"][metric], item["post_id"]))
        _append_unique(selected, selected_ids, row, maximum)
    for row in scored:
        _append_unique(selected, selected_ids, row, maximum)
    return selected, _manifest(selected, source="engagement_representative", limit=maximum)


def _normalized_row(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "post_id": _post_id(row),
        "platform": str(row.get("platform") or "").strip(),
        "author_name": str(row.get("author_name") or row.get("author_id") or "").strip(),
        "excerpt": _excerpt(row),
        "engagement": {
            "reposts": _metric(row, "reposts", "repost_count", "share_count", "retweet_count"),
            "likes": _metric(row, "likes", "like_count", "favorite_count"),
            "comments": _metric(row, "comments_count", "comment_count", "comments"),
        },
        "row": dict(row),
    }


def _rank_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    maxima = {
        metric: max((row["engagement"][metric] for row in rows), default=0)
        for metric in ("reposts", "likes", "comments")
    }
    for row in rows:
        engagement = row["engagement"]
        row["selection_score"] = sum(
            math.log1p(engagement[metric]) / math.log1p(maximum)
            for metric, maximum in maxima.items()
            if maximum > 0
        )
    return sorted(rows, key=lambda row: (-row["selection_score"], row["post_id"]))


def _platform_order(rows: list[dict[str, Any]]) -> list[str]:
    platforms: list[str] = []
    for row in rows:
        platform = row["platform"]
        if platform and platform not in platforms:
            platforms.append(platform)
    return platforms


def _append_unique(
    selected: list[dict[str, Any]], selected_ids: set[str], row: dict[str, Any], limit: int
) -> None:
    if len(selected) >= limit or row["post_id"] in selected_ids:
        return
    selected.append(row)
    selected_ids.add(row["post_id"])


def _manifest(selected: list[dict[str, Any]], *, source: str, limit: int) -> dict[str, Any]:
    return {
        "schema": "cogguard.review.representative_post_selection.v1",
        "source": source,
        "limit": limit,
        "selection_criteria": ["reposts", "likes", "comments"],
        "items": [
            {
                "post_id": row["post_id"],
                "platform": row["platform"],
                "author_name": row["author_name"],
                "excerpt": row["excerpt"],
                "engagement": dict(row["engagement"]),
            }
            for row in selected
        ],
    }


def _requested_ids(values: Iterable[str] | None) -> list[str]:
    result: list[str] = []
    for value in values or []:
        text = str(value or "").strip()
        if text.startswith("post:"):
            text = text.split(":", 1)[1].strip()
        elif ":post:" in text:
            text = text.rsplit(":post:", 1)[1].strip()
        if text and text not in result:
            result.append(text)
    return result


def _post_id(row: Mapping[str, Any]) -> str:
    return str(row.get("post_id") or row.get("id") or "").strip()


def _metric(row: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        try:
            return max(0, int(float(row.get(key) or 0)))
        except (TypeError, ValueError):
            continue
    return 0


def _excerpt(row: Mapping[str, Any]) -> str:
    for key in ("content", "text", "title"):
        value = str(row.get(key) or "").strip()
        if value:
            return value[:360]
    return ""
