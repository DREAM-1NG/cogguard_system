"""Regression coverage for historical social JSONL ingestion."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from app.models.post import StandardComment, StandardPost
from scripts import import_mediacrawler_jsonl as importer


def test_build_document_keeps_assigned_and_source_event_ids() -> None:
    document = importer.build_document(
        {"platform": "weibo"},
        item_type="post",
        item_id="post-1",
        event_id="trump_visit_2026_05_21",
        source_event_id="特朗普访华_2026_05_20",
        source_keyword="特朗普访华",
        job_id=0,
        crawl_metadata={},
    )

    assert document["event_id"] == "trump_visit_2026_05_21"
    assert document["source_event_id"] == "特朗普访华_2026_05_20"
    assert document["dedupe_key"] == "trump_visit_2026_05_21:weibo:post:post-1"


def test_dry_run_assigns_event_override_without_mongo(tmp_path: Path, monkeypatch) -> None:
    content_path = tmp_path / "search_contents_2026-05-20.jsonl"
    content_path.write_text(json.dumps({"post_id": "post-1", "source_keyword": "热点事件"}) + "\n", encoding="utf-8")
    comment_path = tmp_path / "search_comments_2026-05-20.jsonl"
    comment_path.write_text(json.dumps({"comment_id": "comment-1", "post_id": "post-1"}) + "\n", encoding="utf-8")

    monkeypatch.setitem(
        importer.PLATFORM_CONFIG,
        "weibo",
        importer.PlatformImportConfig(
            post_loader=lambda _raw, platform: StandardPost(
                post_id="post-1",
                platform=platform,
                content="fixture post",
                author_id="author-1",
                author_name="Fixture Author",
                timestamp=datetime(2026, 5, 20, tzinfo=timezone.utc),
            ),
            comment_loader=lambda _raw, platform: StandardComment(
                comment_id="comment-1",
                post_id="post-1",
                platform=platform,
                content="fixture comment",
                author_id="author-2",
                author_name="Fixture Commenter",
                timestamp=datetime(2026, 5, 20, tzinfo=timezone.utc),
            ),
        ),
    )

    summary = asyncio.run(
        importer.import_pair(
            None,
            platform="weibo",
            content_path=content_path,
            comment_path=comment_path,
            job_id=0,
            event_id_override="trump_visit_2026_05_21",
            dry_run=True,
        )
    )

    assert summary["event_ids"] == ["trump_visit_2026_05_21"]
    assert summary["source_event_ids"] == ["热点事件_2026_05_20"]
