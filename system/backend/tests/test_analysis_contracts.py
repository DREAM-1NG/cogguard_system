from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.core.analysis import (
    AnalysisRunStatus,
    InvalidRunTransition,
    TimeWindow,
    build_event_snapshot,
    transition_run_status,
)


def _dt(day: int, hour: int = 0) -> datetime:
    return datetime(2026, 5, day, hour, tzinfo=timezone.utc)


def _snapshot(posts: list[dict], comments: list[dict]):
    return build_event_snapshot(
        event_id="trump_visit_2026_05_21",
        posts=posts,
        comments=comments,
        core_window=TimeWindow(start=_dt(11), end=_dt(22)),
        context_window=TimeWindow(start=_dt(1), end=_dt(31)),
    )


def test_snapshot_fingerprint_is_stable_across_input_order_and_duplicates():
    posts = [
        {
            "platform": "weibo",
            "post_id": "p1",
            "author_id": "u1",
            "content": "event claim",
            "timestamp": _dt(12),
            "crawl_job_id": 7,
            "source_keyword": "特朗普访华",
        },
        {
            "platform": "xhs",
            "post_id": "p2",
            "author_id": "u2",
            "content": "context post",
            "timestamp": _dt(10),
            "crawl_job_id": 8,
            "source_keyword": "特朗普访华",
        },
    ]
    comments = [
        {
            "platform": "weibo",
            "comment_id": "c1",
            "post_id": "p1",
            "author_id": "u3",
            "content": "reply",
            "timestamp": _dt(12, 1),
            "reply_to": "p1",
        }
    ]

    first = _snapshot(posts + [dict(posts[0])], comments)
    second = _snapshot(list(reversed(posts)), list(reversed(comments)))

    assert first.data_fingerprint == second.data_fingerprint
    assert first.snapshot_id == second.snapshot_id
    assert len(first.posts) == 2
    assert first.quality_report.duplicate_posts == 1
    assert first.platforms == ["weibo", "xhs"]


def test_snapshot_filters_context_window_and_reports_core_coverage():
    posts = [
        {"platform": "weibo", "post_id": "core", "author_id": "u1", "content": "a", "timestamp": _dt(12)},
        {"platform": "douyin", "post_id": "context", "author_id": "u2", "content": "b", "timestamp": _dt(5)},
        {"platform": "xhs", "post_id": "outside", "author_id": "u3", "content": "c", "timestamp": _dt(31)},
    ]

    snapshot = _snapshot(posts, [])

    assert [post["post_id"] for post in snapshot.posts] == ["context", "core"]
    assert snapshot.quality_report.core_posts == 1
    assert snapshot.quality_report.context_posts == 2
    assert snapshot.quality_report.excluded_posts == 1
    assert snapshot.quality_report.status == "pass"


def test_snapshot_relationships_only_capture_observed_parent_references():
    posts = [
        {
            "platform": "weibo",
            "post_id": "p1",
            "author_id": "u1",
            "content": "source",
            "timestamp": _dt(12),
        },
        {
            "platform": "weibo",
            "post_id": "p2",
            "author_id": "u2",
            "content": "repost",
            "timestamp": _dt(13),
            "repost_id": "p1",
        },
    ]
    comments = [
        {
            "platform": "weibo",
            "comment_id": "c1",
            "post_id": "p2",
            "author_id": "u3",
            "content": "reply",
            "timestamp": _dt(13, 1),
            "reply_to": "p2",
        }
    ]

    snapshot = _snapshot(posts, comments)

    assert {(edge.relation_type, edge.source_id, edge.target_id) for edge in snapshot.relationships} == {
        ("repost", "weibo:post:p1", "weibo:post:p2"),
        ("reply", "weibo:post:p2", "weibo:comment:c1"),
    }


def test_snapshot_links_comment_post_id_when_no_comment_parent_is_available():
    snapshot = _snapshot(
        [
            {
                "platform": "douyin",
                "post_id": "p1",
                "author_id": "u1",
                "content": "source post",
                "timestamp": _dt(12),
            }
        ],
        [
            {
                "platform": "douyin",
                "comment_id": "c1",
                "post_id": "p1",
                "author_id": "u2",
                "content": "top-level comment",
                "timestamp": _dt(12, 1),
            }
        ],
    )

    assert {(edge.relation_type, edge.source_id, edge.target_id) for edge in snapshot.relationships} == {
        ("parent", "douyin:post:p1", "douyin:comment:c1"),
    }


def test_analysis_run_state_machine_rejects_terminal_reversal():
    assert transition_run_status(AnalysisRunStatus.QUEUED, AnalysisRunStatus.RUNNING) == AnalysisRunStatus.RUNNING
    assert transition_run_status(AnalysisRunStatus.RUNNING, AnalysisRunStatus.AWAITING_REVIEW) == AnalysisRunStatus.AWAITING_REVIEW
    assert transition_run_status(AnalysisRunStatus.AWAITING_REVIEW, AnalysisRunStatus.COMPLETED) == AnalysisRunStatus.COMPLETED
    assert transition_run_status(AnalysisRunStatus.COMPLETED, AnalysisRunStatus.COMPLETED) == AnalysisRunStatus.COMPLETED

    with pytest.raises(InvalidRunTransition):
        transition_run_status(AnalysisRunStatus.COMPLETED, AnalysisRunStatus.RUNNING)


def test_snapshot_rejects_missing_core_evidence_without_fabricating_content():
    snapshot = _snapshot(
        [{"platform": "weibo", "post_id": "context", "timestamp": _dt(5), "content": "context only"}],
        [],
    )

    assert snapshot.quality_report.status == "reject"
    assert "no_core_posts" in snapshot.quality_report.issues
    assert snapshot.posts[0]["post_id"] == "context"
