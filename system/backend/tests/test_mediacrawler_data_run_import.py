import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.import_mediacrawler_data_runs import (
    PlatformImportResult,
    build_legacy_weibo_reconciliation_filters,
    build_latest_trump_visit_sources,
    dedupe_rows_by_id,
    normalize_platform_files,
    reconcile_legacy_weibo_manifest,
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_dedupe_rows_by_id_keeps_latest_last_modify_ts():
    rows = [
        {"note_id": "p1", "content": "old", "last_modify_ts": 1},
        {"note_id": "p1", "content": "new", "last_modify_ts": 9},
        {"note_id": "p2", "content": "only", "last_modify_ts": 3},
    ]

    deduped = dedupe_rows_by_id(rows, "note_id")

    assert [row["content"] for row in deduped] == ["new", "only"]


def test_normalize_platform_files_adds_event_metadata_and_reports_missing_refs(tmp_path):
    posts_path = tmp_path / "xhs" / "search_contents_2026-05-21.jsonl"
    comments_path = tmp_path / "xhs" / "search_comments_2026-05-21.jsonl"
    _write_jsonl(
        posts_path,
        [
            {
                "note_id": "xhs-1",
                "title": "标题",
                "desc": "正文",
                "time": 1779201805000,
                "liked_count": "4.3万",
                "comment_count": "1,318",
                "source_keyword": "特朗普访华",
            },
            {
                "note_id": "xhs-1",
                "title": "标题更新",
                "desc": "正文更新",
                "time": 1779201805000,
                "last_modify_ts": 99,
                "source_keyword": "特朗普访华",
            },
        ],
    )
    _write_jsonl(
        comments_path,
        [
            {
                "comment_id": "c1",
                "note_id": "xhs-1",
                "content": "一级评论",
                "parent_comment_id": 0,
                "create_time": 1779326166000,
            },
            {
                "comment_id": "c2",
                "note_id": "missing-post",
                "content": "孤儿评论",
                "parent_comment_id": 0,
                "create_time": 1779326166000,
            },
        ],
    )

    result = normalize_platform_files(
        platform="xhs",
        posts_path=posts_path,
        comments_path=comments_path,
        event_id="trump_visit_2026_05_21",
        keyword="特朗普访华",
    )

    assert result.stats["raw_posts"] == 2
    assert result.stats["unique_posts"] == 1
    assert result.stats["raw_comments"] == 2
    assert result.stats["unique_comments"] == 2
    assert result.missing_comment_post_refs == ["missing-post"]
    assert result.posts[0]["content"] == "标题更新\n正文更新"
    assert result.posts[0]["event_id"] == "trump_visit_2026_05_21"
    assert result.posts[0]["dedupe_key"] == "trump_visit_2026_05_21:xhs:post:xhs-1"
    assert result.comments[0]["dedupe_key"] == "trump_visit_2026_05_21:xhs:comment:c1"


def test_latest_trump_visit_preset_resolves_only_latest_effective_directories(tmp_path):
    root = tmp_path / "data_runs"

    expected = {
        "weibo": root / "weibo_trump_visit_2026-05-21" / "search_more" / "weibo" / "jsonl",
        "xhs": root / "xhs_trump_visit_2026-05-21" / "search_full2" / "xhs" / "jsonl",
        "douyin": root / "douyin_trump_visit_2026-05-21" / "search_full6" / "douyin" / "jsonl",
    }
    for platform, directory in expected.items():
        _write_jsonl(directory / "search_contents_2026-05-21.jsonl", [])
        _write_jsonl(directory / "search_comments_2026-05-21.jsonl", [])

    sources = build_latest_trump_visit_sources(root)

    assert set(sources) == {"weibo", "xhs", "douyin"}
    assert sources["weibo"].posts_path == expected["weibo"] / "search_contents_2026-05-21.jsonl"
    assert sources["xhs"].comments_path == expected["xhs"] / "search_comments_2026-05-21.jsonl"


def test_legacy_weibo_reconciliation_filters_use_only_the_current_manifest_and_audited_signature():
    filters = build_legacy_weibo_reconciliation_filters(
        [
            PlatformImportResult(
                platform="weibo",
                posts=[{"post_id": "current-weibo-post"}],
                comments=[{"comment_id": "current-weibo-comment"}],
                stats={},
            ),
            PlatformImportResult(
                platform="xhs",
                posts=[{"post_id": "xhs-post"}],
                comments=[{"comment_id": "xhs-comment"}],
                stats={},
            ),
            PlatformImportResult(
                platform="douyin",
                posts=[{"post_id": "douyin-post"}],
                comments=[{"comment_id": "douyin-comment"}],
                stats={},
            ),
        ],
        event_id="trump_visit_2026_05_21",
    )

    legacy_signature = {
        "event_id": "trump_visit_2026_05_21",
        "platform": "weibo",
        "crawl_job_id": 0,
        "crawl_metadata.ingestion_mode": "historical_jsonl_sync",
        "crawl_metadata.jsonl_date": "2026-05-20",
    }
    assert filters["posts"] == {
        **legacy_signature,
        "post_id": {"$nin": ["current-weibo-post"]},
    }
    assert filters["comments"] == {
        **legacy_signature,
        "comment_id": {"$nin": ["current-weibo-comment"]},
    }


def test_legacy_weibo_reconciliation_preview_reports_counts_without_deleting(monkeypatch):
    class Collection:
        def __init__(self, count):
            self.count = count
            self.count_queries = []
            self.delete_queries = []

        async def count_documents(self, query):
            self.count_queries.append(query)
            return self.count

        async def delete_many(self, query):
            self.delete_queries.append(query)
            return SimpleNamespace(deleted_count=self.count)

    posts = Collection(58)
    comments = Collection(4068)
    monkeypatch.setattr(
        "scripts.import_mediacrawler_data_runs.get_mongo_db",
        lambda: {"raw_posts": posts, "raw_comments": comments},
    )

    counts = asyncio.run(
        reconcile_legacy_weibo_manifest(
            [
                PlatformImportResult(
                    platform="weibo",
                    posts=[{"post_id": "current-weibo-post"}],
                    comments=[{"comment_id": "current-weibo-comment"}],
                    stats={},
                )
            ],
            event_id="trump_visit_2026_05_21",
            execute=False,
        )
    )

    assert counts == {
        "post_preview": 58,
        "post_deleted": 0,
        "comment_preview": 4068,
        "comment_deleted": 0,
    }
    assert posts.delete_queries == []
    assert comments.delete_queries == []
    assert posts.count_queries[0]["post_id"] == {"$nin": ["current-weibo-post"]}
    assert comments.count_queries[0]["comment_id"] == {"$nin": ["current-weibo-comment"]}


def test_legacy_weibo_reconciliation_deletes_only_the_previewed_signature(monkeypatch):
    class Collection:
        def __init__(self, count):
            self.count = count
            self.queries = []

        async def count_documents(self, query):
            self.queries.append(("preview", query))
            return self.count

        async def delete_many(self, query):
            self.queries.append(("delete", query))
            return SimpleNamespace(deleted_count=self.count)

    posts = Collection(58)
    comments = Collection(4068)
    monkeypatch.setattr(
        "scripts.import_mediacrawler_data_runs.get_mongo_db",
        lambda: {"raw_posts": posts, "raw_comments": comments},
    )

    counts = asyncio.run(
        reconcile_legacy_weibo_manifest(
            [
                PlatformImportResult(
                    platform="weibo",
                    posts=[{"post_id": "current-weibo-post"}],
                    comments=[{"comment_id": "current-weibo-comment"}],
                    stats={},
                )
            ],
            event_id="trump_visit_2026_05_21",
            execute=True,
        )
    )

    assert counts == {
        "post_preview": 58,
        "post_deleted": 58,
        "comment_preview": 4068,
        "comment_deleted": 4068,
    }
    assert posts.queries == [("preview", posts.queries[0][1]), ("delete", posts.queries[0][1])]
    assert comments.queries == [("preview", comments.queries[0][1]), ("delete", comments.queries[0][1])]


def test_legacy_weibo_reconciliation_rejects_other_events_without_querying(monkeypatch):
    class Collection:
        async def count_documents(self, _query):
            raise AssertionError("other events must not be queried for legacy cleanup")

    monkeypatch.setattr(
        "scripts.import_mediacrawler_data_runs.get_mongo_db",
        lambda: {"raw_posts": Collection(), "raw_comments": Collection()},
    )

    with pytest.raises(ValueError, match="limited to event trump_visit_2026_05_21"):
        asyncio.run(
            reconcile_legacy_weibo_manifest(
                [
                    PlatformImportResult(
                        platform="weibo",
                        posts=[{"post_id": "current-weibo-post"}],
                        comments=[{"comment_id": "current-weibo-comment"}],
                        stats={},
                    )
                ],
                event_id="other-event",
                execute=True,
            )
        )
