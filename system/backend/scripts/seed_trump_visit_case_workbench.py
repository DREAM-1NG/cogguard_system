"""Seed the real Trump-visit case governance anchors for the demo event."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.db.mongodb import close_mongo, get_mongo_db
from app.db.mysql import async_session_factory, close_mysql
from app.models.analysis import AnalysisRun
from app.models.case_workbench import (
    AuthoritySource,
    AuthoritySourceAccount,
    CaseAnalysisLink,
    CaseClaim,
    CaseRecord,
)


EVENT_ID = "trump_visit_2026_05_21"
CASE_ID = "case_trump_visit_2026_05_21"
PRIMARY_SOURCE_ID = "authority_cctv_news"
SUPPORTING_SOURCE_ID = "authority_xinhua_news"
CHINA_NEWS_SOURCE_ID = "authority_china_news_service"
PRIMARY_CLAIM_ID = "claim_trump_visit_cctv_primary"
SUPPORTING_CLAIM_ID = "claim_trump_visit_xinhua_supporting"
CHINA_NEWS_CLAIM_ID = "claim_trump_visit_china_news_supporting"
CASE_RUN_LINK_ID = "case_link_trump_visit_latest_semantic"

AUTHORITY_POSTS = {
    PRIMARY_SOURCE_ID: {
        "name": "央视新闻",
        "url": "https://news.cctv.com/",
        "tier": "central_mainstream_media",
        "platform": "douyin",
        "author_id": "66598046050",
        "post_id": "7639757357911756083",
        "claim_id": PRIMARY_CLAIM_ID,
        "role": "primary",
    },
    SUPPORTING_SOURCE_ID: {
        "name": "新华社",
        "url": "https://www.news.cn/",
        "tier": "central_mainstream_media",
        "platform": "douyin",
        "author_id": "93288642596",
        "post_id": "7639577678311443775",
        "claim_id": SUPPORTING_CLAIM_ID,
        "role": "supporting",
    },
    CHINA_NEWS_SOURCE_ID: {
        "name": "中国新闻社",
        "url": "https://www.chinanews.com.cn/",
        "tier": "central_mainstream_media",
        "platform": "xhs",
        "author_id": "61d65bc0000000001000c773",
        "post_id": "6a058d370000000035031ba0",
        "claim_id": CHINA_NEWS_CLAIM_ID,
        "role": "supporting",
    },
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    return None


async def _load_authority_post(mongo_db: Any, spec: dict[str, str]) -> dict[str, Any]:
    post = await mongo_db.raw_posts.find_one(
        {
            "event_id": EVENT_ID,
            "platform": spec["platform"],
            "author_id": spec["author_id"],
            "post_id": spec["post_id"],
        },
        {"_id": 0},
    )
    if not isinstance(post, dict):
        raise RuntimeError(
            "authority post not found: "
            f"{spec['platform']} author={spec['author_id']} post={spec['post_id']}"
        )
    content = str(post.get("content") or "").strip()
    if not content:
        raise RuntimeError(f"authority post content is empty: {spec['post_id']}")
    source_url = str(post.get("url") or "").strip()
    if not source_url:
        raise RuntimeError(f"authority post URL is empty: {spec['post_id']}")
    return post


async def _latest_completed_run() -> AnalysisRun | None:
    async with async_session_factory() as db:
        result = await db.execute(
            select(AnalysisRun)
            .where(AnalysisRun.event_id == EVENT_ID, AnalysisRun.status == "completed")
            .order_by(AnalysisRun.created_at.desc(), AnalysisRun.id.desc())
            .limit(1)
        )
        return result.scalars().first()


async def seed_case_workbench() -> dict[str, Any]:
    mongo_db = get_mongo_db()
    posts = {
        source_id: await _load_authority_post(mongo_db, spec)
        for source_id, spec in AUTHORITY_POSTS.items()
    }
    latest_run = await _latest_completed_run()

    async with async_session_factory() as db:
        case = (
            await db.execute(select(CaseRecord).where(CaseRecord.case_id == CASE_ID))
        ).scalar_one_or_none()
        if case is None:
            case = CaseRecord(
                case_id=CASE_ID,
                event_id=EVENT_ID,
                title="特朗普访华三平台舆论传播案例",
                lifecycle="evidence_ready",
                canonical_verdict_json="{}",
                canonical_approved=False,
                closure_note="",
                created_by=0,
            )
            db.add(case)
        else:
            case.event_id = EVENT_ID
            case.title = "特朗普访华三平台舆论传播案例"
            if case.lifecycle == "draft":
                case.lifecycle = "evidence_ready"

        seeded_sources: list[str] = []
        seeded_bindings: list[str] = []
        seeded_claims: list[str] = []
        for source_id, spec in AUTHORITY_POSTS.items():
            post = posts[source_id]
            source = (
                await db.execute(select(AuthoritySource).where(AuthoritySource.source_id == source_id))
            ).scalar_one_or_none()
            if source is None:
                source = AuthoritySource(source_id=source_id, name=spec["name"], url=spec["url"])
                db.add(source)
            source.name = spec["name"]
            source.url = spec["url"]
            source.review_status = "allowlisted"
            source.tier = spec["tier"]
            source.reviewed_by = 0
            seeded_sources.append(source_id)

            binding = (
                await db.execute(
                    select(AuthoritySourceAccount).where(
                        AuthoritySourceAccount.source_id == source_id,
                        AuthoritySourceAccount.platform == spec["platform"],
                        AuthoritySourceAccount.author_id == spec["author_id"],
                    )
                )
            ).scalar_one_or_none()
            verification_snapshot = {
                "seeded_from": "raw_posts",
                "event_id": EVENT_ID,
                "post_id": spec["post_id"],
                "display_name": post.get("author_name") or spec["name"],
            }
            if binding is None:
                binding = AuthoritySourceAccount(
                    source_id=source_id,
                    platform=spec["platform"],
                    author_id=spec["author_id"],
                    display_name_snapshot=str(post.get("author_name") or spec["name"]),
                    verification_snapshot=_json(verification_snapshot),
                    reviewed_by=0,
                )
                db.add(binding)
            else:
                binding.display_name_snapshot = str(post.get("author_name") or spec["name"])
                binding.verification_snapshot = _json(verification_snapshot)
                binding.reviewed_by = 0
            seeded_bindings.append(f"{spec['platform']}:{spec['author_id']}")

            exact_quote = str(post.get("content") or "").strip()
            claim = (
                await db.execute(select(CaseClaim).where(CaseClaim.claim_id == spec["claim_id"]))
            ).scalar_one_or_none()
            if claim is None:
                claim = CaseClaim(claim_id=spec["claim_id"], case_id=CASE_ID)
                db.add(claim)
            claim.authority_source_id = source_id
            claim.exact_quote = exact_quote
            claim.quote_start = 0
            claim.quote_end = len(exact_quote)
            claim.source_url = str(post.get("url") or "")
            claim.account = str(post.get("author_name") or spec["name"])
            claim.published_at = _parse_datetime(post.get("timestamp"))
            claim.role = spec["role"]
            claim.source_tier_snapshot = spec["tier"]
            claim.source_review_snapshot = "allowlisted"
            claim.content_sha256 = hashlib.sha256(exact_quote.encode("utf-8")).hexdigest()
            seeded_claims.append(spec["claim_id"])

        linked_run_id = None
        if latest_run is not None:
            linked_run_id = latest_run.run_id
            link = (
                await db.execute(select(CaseAnalysisLink).where(CaseAnalysisLink.link_id == CASE_RUN_LINK_ID))
            ).scalar_one_or_none()
            stages = ["coordination_discover", "propagation_analysis", "semantic_enrichment", "student"]
            if link is None:
                link = CaseAnalysisLink(
                    link_id=CASE_RUN_LINK_ID,
                    case_id=CASE_ID,
                    snapshot_or_run_id=latest_run.run_id,
                    stages_json=_json(stages),
                    blockers_json="[]",
                )
                db.add(link)
            else:
                link.case_id = CASE_ID
                link.snapshot_or_run_id = latest_run.run_id
                link.stages_json = _json(stages)
                link.blockers_json = "[]"

        await db.commit()

    return {
        "event_id": EVENT_ID,
        "case_id": CASE_ID,
        "authority_sources": seeded_sources,
        "authority_source_accounts": seeded_bindings,
        "claims": seeded_claims,
        "linked_run_id": linked_run_id,
    }


async def main_async(_args: argparse.Namespace) -> int:
    try:
        result = await seed_case_workbench()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        return 0
    finally:
        await close_mongo()
        await close_mysql()


def main() -> int:
    parser = argparse.ArgumentParser()
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
