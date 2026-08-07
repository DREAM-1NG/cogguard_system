from __future__ import annotations

import pytest

from app.services.account_corpus_service import build_corpus_documents


def test_build_corpus_documents_combines_posts_and_comments() -> None:
    documents = build_corpus_documents(
        [
            {
                "post_id": "p-1",
                "author_id": "u-1",
                "platform": "weibo",
                "event_id": "event-1",
                "content": "这是 一条中文帖子",
                "timestamp": "2026-05-11T01:00:00+08:00",
            }
        ],
        [
            {
                "comment_id": "c-1",
                "user_id": "u-2",
                "platform": "weibo",
                "event_id": "event-1",
                "content": "这是一条中文评论",
                "timestamp": "2026-05-11T01:01:00+08:00",
            }
        ],
        event_id="event-1",
        platform="weibo",
    )

    assert [document.source_kind for document in documents] == ["post", "comment"]
    assert {document.account_id for document in documents} == {"u-1", "u-2"}
    assert all(document.text_fingerprint for document in documents)


def test_build_corpus_documents_deduplicates_normalized_text_across_sources() -> None:
    documents = build_corpus_documents(
        [
            {
                "post_id": "p-1",
                "platform": "weibo",
                "event_id": "event-1",
                "content": "重复的\n中文内容",
            }
        ],
        [
            {
                "comment_id": "c-1",
                "platform": "weibo",
                "event_id": "event-1",
                "content": "重复的  中文内容",
            }
        ],
    )

    assert len(documents) == 1
    assert documents[0].text == "重复的 中文内容"


def test_build_corpus_documents_excludes_non_chinese_and_out_of_scope_rows() -> None:
    documents = build_corpus_documents(
        [
            {"post_id": "english", "platform": "weibo", "event_id": "event-1", "content": "english only"},
            {"post_id": "other", "platform": "xhs", "event_id": "event-1", "content": "其他平台中文"},
            {"post_id": "selected", "platform": "weibo", "event_id": "event-1", "content": "保留中文"},
        ],
        event_id="event-1",
        platform="weibo",
    )

    assert [document.source_id for document in documents] == ["selected"]


@pytest.mark.parametrize("require_chinese", [False])
def test_build_corpus_documents_can_include_mixed_language_audit_fixture(require_chinese: bool) -> None:
    documents = build_corpus_documents(
        [{"post_id": "p-1", "platform": "weibo", "content": "English fixture"}],
        require_chinese=require_chinese,
    )

    assert len(documents) == 1
