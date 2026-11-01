import json
from pathlib import Path

from scripts.import_mediacrawler_data_runs import (
    build_latest_trump_visit_sources,
    dedupe_rows_by_id,
    normalize_platform_files,
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
