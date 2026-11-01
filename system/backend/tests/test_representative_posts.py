from __future__ import annotations

from app.core.review.representative_posts import select_representative_posts


def _posts() -> list[dict[str, object]]:
    return [
        {
            "post_id": "weibo-leading",
            "platform": "weibo",
            "content": "Weibo post",
            "reposts": 200,
            "likes": 20,
            "comments": 10,
            "label": "harmful",
            "model_score": 0.99,
        },
        {
            "post_id": "douyin-leading",
            "platform": "douyin",
            "content": "Douyin post",
            "reposts": 10,
            "likes": 500,
            "comments": 100,
            "label": "non_harmful",
            "model_score": 0.01,
        },
        {
            "post_id": "xhs-leading",
            "platform": "xhs",
            "content": "XHS post",
            "reposts": 1,
            "likes": 2,
            "comments": 900,
            "label": "harmful",
            "model_score": 0.75,
        },
    ]


def test_representative_selection_preserves_cross_platform_engagement_leaders():
    selected, manifest = select_representative_posts(_posts(), limit=3)

    assert {row["post_id"] for row in selected} == {
        "weibo-leading",
        "douyin-leading",
        "xhs-leading",
    }
    assert manifest["source"] == "engagement_representative"
    assert manifest["selection_criteria"] == ["reposts", "likes", "comments"]
    assert all("label" not in item and "model_score" not in item for item in manifest["items"])


def test_explicit_post_selection_takes_precedence_and_remains_auditable():
    selected, manifest = select_representative_posts(
        _posts(),
        selected_post_ids=["post:xhs-leading", "post:missing", "post:weibo-leading"],
        limit=2,
    )

    assert [row["post_id"] for row in selected] == ["xhs-leading", "weibo-leading"]
    assert manifest["source"] == "analyst_selected"
    assert [item["post_id"] for item in manifest["items"]] == ["xhs-leading", "weibo-leading"]
