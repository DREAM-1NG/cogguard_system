"""风险研判业务逻辑服务。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import uuid4

from app.core.crawler.mock import MockCrawler
from app.core.risk import (
    analyze_harmful_batch,
    analyze_stance_batch,
    assess_risk_phase,
    build_evidence_pack,
    build_llm_bridge_result,
    build_risk_report,
    derive_stance_target,
    generate_countermeasures,
    map_to_disarm,
)
from app.core.risk.research.inference import (
    build_harmful_samples,
    build_stance_samples,
    harmful_model_available,
    predict_harmful_labels,
    predict_stance_labels,
    stance_model_available,
)
from app.db.mongodb import get_mongo_db


def _normalize_keyword(value: str | None) -> str:
    return (value or "").strip().lower()


def _normalize_hashtag(tag: Any) -> str:
    text = str(tag or "").strip().lower()
    if text.startswith("#") and text.endswith("#") and len(text) > 2:
        return text[1:-1]
    return text.strip("#")


def _match_keyword(post: dict, keyword: str | None) -> bool:
    lowered = _normalize_keyword(keyword)
    if not lowered:
        return True

    content = str(post.get("content", "")).lower()
    if lowered in content:
        return True

    hashtags = [_normalize_hashtag(tag) for tag in post.get("hashtags", []) or []]
    if any(lowered in tag for tag in hashtags):
        return True

    source_keyword = _normalize_keyword(post.get("source_keyword"))
    if source_keyword and lowered in source_keyword:
        return True

    raw_data = post.get("raw_data") or {}
    raw_source_keyword = _normalize_keyword(raw_data.get("source_keyword") if isinstance(raw_data, dict) else None)
    return bool(raw_source_keyword and lowered in raw_source_keyword)


async def _load_mock_posts(keyword: str | None, max_posts: int) -> list[dict]:
    crawler = MockCrawler()
    posts = await crawler.search(keywords=[keyword] if keyword else [], max_posts=max_posts)
    return [post.model_dump(mode="json") for post in posts]


async def _fetch_posts(platform: str | None, keyword: str | None, post_ids: list[str], max_posts: int) -> tuple[list[dict], str]:
    mongo_db = get_mongo_db()
    mongo_filter: dict = {}
    if platform:
        mongo_filter["platform"] = platform
    if post_ids:
        mongo_filter["post_id"] = {"$in": post_ids}

    cursor = mongo_db["raw_posts"].find(mongo_filter, {"_id": 0}).sort("timestamp", -1)
    posts = await cursor.to_list(length=max(max_posts * 3, 100))
    posts = [post for post in posts if _match_keyword(post, keyword)]

    if posts:
        return posts[:max_posts], "mongo"

    if platform == "mock_weibo" and not post_ids:
        fallback_posts = await _load_mock_posts(keyword, max_posts)
        return fallback_posts[:max_posts], "mock_fallback"

    return [], "empty"


def _inject_model_predictions(posts: list[dict], target: str) -> tuple[list[dict], list[dict]]:
    harmful_labels = predict_harmful_labels(build_harmful_samples(posts))
    stance_labels = predict_stance_labels(build_stance_samples(posts, target))

    harmful_results = []
    stance_results = []
    for post, harmful_label, stance_label in zip(posts, harmful_labels, stance_labels):
        content = str(post.get("content", ""))
        harmful_results.append({
            "post_id": str(post.get("post_id", "")),
            "author_id": str(post.get("author_id", "")),
            "content": content,
            "label": harmful_label,
            "score": 0.75 if harmful_label != "safe" else 0.35,
            "categories": [],
            "matched_terms": [],
            "reason": f"model_pred:{harmful_label}",
        })
        stance_results.append({
            "post_id": str(post.get("post_id", "")),
            "author_id": str(post.get("author_id", "")),
            "content": content,
            "target": target,
            "label": stance_label,
            "score": 0.75,
            "reason": f"model_pred:{stance_label}",
        })
    return harmful_results, stance_results


async def assess_risk(req) -> dict:
    posts, data_source = await _fetch_posts(req.platform, req.keyword, req.post_ids, req.max_posts)
    if not posts:
        return {"error": "没有可分析的数据，请先执行数据采集或调整筛选条件"}

    target = derive_stance_target(posts, req.stance_target, req.keyword)
    requested_mode = (getattr(req, "analysis_mode", "rule") or "rule").lower()
    use_model = requested_mode == "model" and harmful_model_available() and stance_model_available()
    harmful_results, stance_results = (
        _inject_model_predictions(posts, target)
        if use_model
        else (analyze_harmful_batch(posts), analyze_stance_batch(posts, target))
    )
    evidence_pack = build_evidence_pack(posts, harmful_results, stance_results, target)
    phase_result = assess_risk_phase(evidence_pack)
    disarm_result = map_to_disarm(evidence_pack, phase_result)
    recommendations = generate_countermeasures(evidence_pack, phase_result, disarm_result)
    llm_result = build_llm_bridge_result(
        target=target,
        phase_result=phase_result,
        disarm_result=disarm_result,
        evidence_pack=evidence_pack,
        recommendations=recommendations,
    )

    report = build_risk_report(
        report_id=str(uuid4()),
        platform=req.platform,
        keyword=req.keyword,
        target=target,
        evidence_pack=evidence_pack,
        phase_result=phase_result,
        disarm_result=disarm_result,
        recommendations=recommendations,
        llm_result=llm_result,
    )
    report["data_source"] = data_source
    report["analysis_mode"] = "model" if use_model else "rule"

    mongo_db = get_mongo_db()
    await mongo_db["risk_reports"].insert_one(deepcopy(report))
    return report


def _summarize_report(report: dict) -> dict:
    assessment = report.get("risk_assessment", {})
    return {
        "report_id": report.get("report_id", ""),
        "created_at": report.get("created_at", ""),
        "platform": report.get("platform", "all"),
        "target": report.get("target", ""),
        "status": report.get("status", "completed"),
        "executive_summary": report.get("executive_summary", ""),
        "risk_level": assessment.get("risk_level", "low"),
        "phase_label": assessment.get("phase_label", "播种期"),
        "data_source": report.get("data_source", "unknown"),
    }


async def list_reports(platform: str | None = None, limit: int = 20) -> list[dict]:
    mongo_db = get_mongo_db()
    mongo_filter: dict = {}
    if platform:
        mongo_filter["platform"] = platform
    cursor = mongo_db["risk_reports"].find(mongo_filter, {"_id": 0}).sort("created_at", -1).limit(limit)
    reports = await cursor.to_list(length=limit)
    return [_summarize_report(report) for report in reports]


async def get_report(report_id: str) -> dict | None:
    mongo_db = get_mongo_db()
    return await mongo_db["risk_reports"].find_one({"report_id": report_id}, {"_id": 0})
