"""账户监测业务逻辑服务。"""

from __future__ import annotations

from app.core.account_profiler import build_account_profiles
from app.db.mongodb import get_mongo_db


async def get_account_profiles(platform: str | None = None) -> list[dict]:
    """获取所有账户的行为画像。"""
    mongo_db = get_mongo_db()

    mongo_filter: dict = {}
    if platform:
        mongo_filter["platform"] = platform

    cursor = mongo_db["raw_posts"].find(mongo_filter, {"_id": 0})
    posts = await cursor.to_list(length=10000)

    return build_account_profiles(posts)


async def get_account_detail(account_id: str) -> dict | None:
    """获取单个账户的详细画像及其帖子列表。"""
    mongo_db = get_mongo_db()
    cursor = mongo_db["raw_posts"].find({"author_id": account_id}, {"_id": 0})
    posts = await cursor.to_list(length=1000)

    if not posts:
        return None

    profiles = build_account_profiles(posts)
    profile = profiles[0] if profiles else {}

    recent_posts = sorted(posts, key=lambda p: p.get("timestamp", ""), reverse=True)[:20]
    for p in recent_posts:
        if "raw_data" in p:
            del p["raw_data"]
        for k, v in p.items():
            if hasattr(v, "isoformat"):
                p[k] = v.isoformat()

    return {**profile, "recent_posts": recent_posts}
