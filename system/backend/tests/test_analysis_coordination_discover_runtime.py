from __future__ import annotations

from datetime import datetime, timezone

from app.core.analysis import TimeWindow, build_event_snapshot
from app.core.analysis.coordination_discover import analyze_coordination_discover_snapshot, build_coordination_discover_evidence_edges


def _dt(day: int, hour: int = 0, minute: int = 0) -> datetime:
    return datetime(2026, 5, day, hour, minute, tzinfo=timezone.utc)


def _snapshot():
    return build_event_snapshot(
        event_id="trump_visit",
        posts=[
            {
                "event_id": "trump_visit",
                "platform": "weibo",
                "post_id": "p1",
                "author_id": "u1",
                "author_name": "Alice",
                "timestamp": _dt(11, 1, 0),
                "content": "Trump visit coordination rumor update from field notes",
                "url": "https://example.com/story",
                "media_urls": ["https://cdn.example.com/clip.mp4"],
                "hashtags": ["#TrumpVisit", "#SharedNarrative"],
                "entities": ["White House"],
                "target": "Trump",
            },
            {
                "event_id": "trump_visit",
                "platform": "douyin",
                "post_id": "p2",
                "author_id": "u2",
                "author_name": "Bob",
                "timestamp": _dt(11, 1, 20),
                "content": "Trump visit coordination rumor update from field notes again",
                "url": "https://example.com/story",
                "media_urls": ["https://cdn.example.com/clip.mp4"],
                "hashtags": ["#TrumpVisit", "#SharedNarrative"],
                "entities": ["White House"],
                "target": "Trump",
                "repost_id": "p1",
            },
            {
                "event_id": "trump_visit",
                "platform": "xhs",
                "post_id": "p3",
                "author_id": "u3",
                "author_name": "Carol",
                "timestamp": _dt(11, 6, 40),
                "content": "Trump visit coordination rumor update from field notes again today",
                "url": "https://example.com/story",
                "media_urls": ["https://cdn.example.com/clip.mp4"],
                "hashtags": ["#TrumpVisit"],
                "entities": ["White House"],
                "target": "Trump",
                "quote_post_id": "p2",
            },
        ],
        comments=[
            {
                "comment_id": "c1",
                "post_id": "p1",
                "author_id": "u4",
                "author_name": "Dan",
                "timestamp": _dt(11, 1, 5),
                "reply_to": "p1",
                "content": "reply to first",
                "entities": ["White House"],
            },
            {
                "comment_id": "c2",
                "post_id": "p1",
                "author_id": "u5",
                "author_name": "Eve",
                "timestamp": _dt(11, 1, 12),
                "reply_to": "c1",
                "content": "reply to reply",
                "entities": ["White House"],
            },
        ],
        core_window=TimeWindow(start=_dt(11, 1, 0), end=_dt(11, 7, 0)),
        context_window=TimeWindow(start=_dt(11, 0, 0), end=_dt(11, 23, 59)),
    )


def test_coordination_discover_evidence_builder_covers_multiple_object_types():
    snapshot = _snapshot()

    result = build_coordination_discover_evidence_edges(snapshot, {"min_participation": 1})
    kinds = {edge["evidence_kind"] for edge in result["evidence_edges"]}

    assert result["summary"]["evidence_edge_count"] > 0
    assert {"url", "media", "hashtag", "entity", "target", "native_relation", "near_duplicate"}.issubset(kinds)
    assert result["coverage"]["kind_counts"]["url"] >= 1
    assert result["coverage"]["kind_counts"]["near_duplicate"] >= 1


def test_coordination_discover_analysis_uses_overlapping_windows_and_reports_lineage_significance():
    snapshot = _snapshot()

    result = analyze_coordination_discover_snapshot(
        snapshot,
        {
            "time_window": 3600,
            "min_participation": 1,
            "edge_weight": 0.4,
            "window_hours": [1, 6, 24],
            "overlap_ratio": 0.5,
            "null_model_samples": 8,
            "perturbation_samples": 5,
        },
    )

    assert result["status"] == "ok"
    assert result["technology"] == "coordination_discover"
    assert result["summary"]["coordinated_edges"] >= 1
    assert [window["window_hours"] for window in result["windows"]] == [1, 6, 24]
    assert all(window["slice_count"] > 0 for window in result["windows"])
    assert result["community_lineage"]
    assert any(item["support_count"] >= 2 and item["stability_score"] >= 0.5 for item in result["community_lineage"])
    assert 0.0 <= result["null_model"]["p_value"] <= 1.0
    assert result["null_model"]["observed_edges"] >= 1
    assert 0.0 <= result["perturbation_robustness"]["median_retained_ratio"] <= 1.0
    assert "kind_counts" in result["evidence_coverage"]
    assert result["domain_shift"]["status"] in {"measured", "not_evaluated"}
