from __future__ import annotations

from app.core.propagation.types import PropagationFrame, SharedObjects


def build_claims(shared_objects: SharedObjects) -> list[dict]:
    claims = []
    for obj_id, shares in sorted(
        shared_objects.items(), key=lambda item: len(item[1]), reverse=True
    )[:20]:
        accounts = list({share["author_id"] for share in shares})
        claims.append(
            {
                "object_id": obj_id,
                "share_count": len(shares),
                "account_count": len(accounts),
                "first_share": str(shares[0]["ts"]) if shares else "",
            }
        )
    return claims


def build_timeline(df: PropagationFrame) -> list[dict]:
    timeline = []
    for _, row in df.head(100).iterrows():
        timeline.append(
            {
                "post_id": str(row.get("post_id", "")),
                "author_id": str(row.get("author_id", "")),
                "author_name": row.get("author_name", ""),
                "timestamp": str(row["ts"]),
                "content": str(row.get("content", ""))[:100],
            }
        )
    return timeline
