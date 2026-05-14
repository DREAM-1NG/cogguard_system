"""传播归因与趋势预测业务逻辑服务。"""

from __future__ import annotations

from app.core.propagation import build_propagation_graph
from app.core.propagation.trend_predictor import predict_trend
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

    # 获取评论数据用于显式边提取
    comments_cursor = mongo_db["raw_comments"].find(mongo_filter, {"_id": 0})
    comments = await comments_cursor.to_list(length=50000)

    return build_propagation_graph(posts, comments)


async def predict_propagation_trend(platform: str | None = None) -> dict:
    """预测传播趋势（CascadeSwitch）。"""
    mongo_db = get_mongo_db()

    mongo_filter: dict = {}
    if platform:
        mongo_filter["platform"] = platform

    cursor = mongo_db["raw_posts"].find(mongo_filter, {"_id": 0})
    posts = await cursor.to_list(length=10000)

    if not posts:
        return {"error": "没有可分析的数据，请先执行数据采集"}

    comments_cursor = mongo_db["raw_comments"].find(mongo_filter, {"_id": 0})
    comments = await comments_cursor.to_list(length=50000)

    return await predict_trend(posts, comments, mock_llm=True)
