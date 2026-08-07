"""Shared MongoDB readers for event-scoped analysis services."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

POST_ANALYSIS_LIMIT = 10_000
COMMENT_ANALYSIS_LIMIT = 50_000
ACCOUNT_DISPLAY_NAME_LIMIT = 100


async def _event_collection_signature(
    collection: Any,
    mongo_filter: dict[str, Any],
) -> dict[str, Any] | None:
    """Read a cheap ingestion-generation marker without loading source rows."""

    count_documents = getattr(collection, "count_documents", None)
    find_one = getattr(collection, "find_one", None)
    if not callable(count_documents) or not callable(find_one):
        return None

    try:
        count = int(await count_documents(mongo_filter))
        if count == 0:
            return {"count": 0, "marker": None}
        projection = {
            "_id": 1,
            "crawl_job_id": 1,
            "crawl_metadata.source_id": 1,
            "timestamp": 1,
            "created_at": 1,
        }
        try:
            latest = await find_one(
                mongo_filter,
                projection,
                sort=[("crawl_job_id", -1), ("_id", -1)],
            )
        except TypeError:
            # Small fake collections used by unit tests do not accept Motor's
            # optional sort argument; production Motor does.
            latest = await find_one(mongo_filter, projection)
        if not isinstance(latest, dict):
            return None
        marker = {
            "id": str(latest.get("_id") or ""),
            "crawl_job_id": str(latest.get("crawl_job_id") or ""),
            "source_id": str(
                (latest.get("crawl_metadata") or {}).get("source_id")
                if isinstance(latest.get("crawl_metadata"), dict)
                else ""
            ),
            "timestamp": str(latest.get("timestamp") or latest.get("created_at") or ""),
        }
        if not any(marker.values()):
            return None
        return {"count": count, "marker": marker}
    except Exception:
        return None


async def event_data_fingerprint(
    mongo_db: Any,
    *,
    event_id: str | None = None,
    platform: str | None = None,
) -> str | None:
    """Return an ingestion-aware version for an event/platform scope.

    Crawl writes attach a monotonically increasing ``crawl_job_id`` to every
    row. The marker plus collection cardinality makes cache invalidation cheap
    while keeping the complete content fingerprint in the immutable snapshot
    path used by research runs. If a collection cannot provide the marker, the
    caller should bypass the query cache rather than risk stale data.
    """

    mongo_filter = build_event_filter(event_id, platform)
    signatures: dict[str, Any] = {}
    for collection_name in ("raw_posts", "raw_comments"):
        collection = _get_collection(mongo_db, collection_name)
        if collection is None:
            return None
        signature = await _event_collection_signature(collection, mongo_filter)
        if signature is None:
            return None
        signatures[collection_name] = signature
    payload = {
        "event_id": event_id or "*",
        "platform": platform or "*",
        "collections": signatures,
        "schema": 1,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def build_event_filter(event_id: str | None = None, platform: str | None = None) -> dict[str, Any]:
    mongo_filter: dict[str, Any] = {}
    if event_id:
        mongo_filter["event_id"] = event_id
    if platform:
        mongo_filter["platform"] = platform
    return mongo_filter


def _get_collection(mongo_db: Any, collection_name: str) -> Any | None:
    if isinstance(mongo_db, dict):
        collection = mongo_db.get(collection_name)
        if collection is not None:
            return collection
    try:
        return mongo_db[collection_name]
    except (KeyError, TypeError):
        return None


async def load_event_posts(
    mongo_db: Any,
    *,
    event_id: str | None = None,
    platform: str | None = None,
    limit: int = POST_ANALYSIS_LIMIT,
) -> list[dict[str, Any]]:
    collection = _get_collection(mongo_db, "raw_posts")
    if collection is None:
        return []
    cursor = collection.find(build_event_filter(event_id, platform), {"_id": 0})
    return await cursor.to_list(length=limit)


async def load_event_comments(
    mongo_db: Any,
    *,
    event_id: str | None = None,
    platform: str | None = None,
    limit: int = COMMENT_ANALYSIS_LIMIT,
) -> list[dict[str, Any]]:
    collection = _get_collection(mongo_db, "raw_comments")
    if collection is None:
        return []
    cursor = collection.find(build_event_filter(event_id, platform), {"_id": 0})
    return await cursor.to_list(length=limit)


async def load_event_account_names(
    mongo_db: Any,
    *,
    event_id: str,
    account_ids: Iterable[str],
) -> dict[str, str]:
    """Resolve display names for the small set of accounts shown in a case."""

    requested_ids = list(
        dict.fromkeys(
            account_id
            for value in account_ids
            if (account_id := str(value or "").strip())
        )
    )[:ACCOUNT_DISPLAY_NAME_LIMIT]
    if not event_id or not requested_ids:
        return {}

    collection = _get_collection(mongo_db, "raw_posts")
    if collection is None:
        return {}
    cursor = collection.find(
        {"event_id": event_id, "author_id": {"$in": requested_ids}},
        {"_id": 0, "author_id": 1, "author_name": 1},
    )
    rows = await cursor.to_list(length=ACCOUNT_DISPLAY_NAME_LIMIT)
    requested = set(requested_ids)
    names: dict[str, str] = {}
    for row in rows:
        account_id = str(row.get("author_id") or "").strip()
        display_name = str(row.get("author_name") or "").strip()
        if (
            account_id in requested
            and display_name
            and display_name != account_id
            and not display_name.isdigit()
        ):
            names.setdefault(account_id, display_name)
    return names


def analysis_scope_metadata(
    *,
    event_id: str | None = None,
    platform: str | None = None,
    posts_count: int = 0,
    comments_count: int | None = None,
) -> dict[str, Any]:
    scope = {"posts": posts_count}
    if comments_count is not None:
        scope["comments"] = comments_count
    return scope


__all__ = [
    "ACCOUNT_DISPLAY_NAME_LIMIT",
    "COMMENT_ANALYSIS_LIMIT",
    "POST_ANALYSIS_LIMIT",
    "analysis_scope_metadata",
    "build_event_filter",
    "event_data_fingerprint",
    "load_event_account_names",
    "load_event_comments",
    "load_event_posts",
]
