"""传播归因业务逻辑服务。"""

from __future__ import annotations

from app.core.propagation import build_propagation_graph
from app.db.mongodb import get_mongo_db


async def analyze_propagation(platform: str | None = None) -> dict:
    """分析已采集数据的传播路径。"""
    mongo_db = get_mongo_db()

    mongo_filter: dict = {}
    if platform:
        mongo_filter["platform"] = platform

    cursor = mongo_db["raw_posts"].find(mongo_filter, {"_id": 0})
    posts = await cursor.to_list(length=10000)

    if not posts:
        return {"error": "没有可分析的数据，请先执行数据采集"}

    return build_propagation_graph(posts)
