from datetime import datetime, timezone
from pathlib import Path

from app.core.coordination.io_reproduction import make_sample_events
from app.models.coordination_registry import CoordinationDataset
from app.core.coordination.io_reproduction import normalize_event_table
from app.services.coordination_model_service import (
    _build_coordination_community_payload,
    _build_coordination_graph_payload,
    _build_result_snapshot,
    _build_account_profile_url,
    _enrich_top_object_item,
    _format_top_object_item,
    _summarize_event_table,
)


def test_summarize_event_table_detects_labeled_dataset():
    events = make_sample_events()
    summary = _summarize_event_table(events)

    assert summary["has_labels"] is True
    assert summary["event_rows"] == len(events)
    assert summary["account_nodes"] >= 1
    assert "url_share" in summary["available_relations"]


def test_build_result_snapshot_marks_unlabeled_pretrained_mode():
    dataset = CoordinationDataset(
        id=7,
        slug="uploaded-demo",
        display_name="Uploaded Demo",
        source_type="uploaded",
        source_format="csv",
        source_path="G:/tmp/source.csv",
        metadata_json="{}",
        has_labels=False,
        event_rows=12,
        account_nodes=4,
        object_ids=5,
        user_user_edges=3,
        available_relations='["url_share","retweet_target"]',
        latest_run_id=None,
        created_by=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    discovery = {
        "metrics": {"modularity": 0.8, "cluster_count": 2, "mean_object_concentration": 0.6},
        "nodes": [
            {"account_id": "u1", "node_score": 0.9, "cluster_id": 0, "directed_out_weight": 2.0, "directed_in_weight": 1.0},
            {"account_id": "u2", "node_score": 0.7, "cluster_id": 0, "directed_out_weight": 1.0, "directed_in_weight": 1.0},
            {"account_id": "u3", "node_score": 0.6, "cluster_id": 1, "directed_out_weight": 1.0, "directed_in_weight": 0.0},
        ],
        "edges": [
            {"source": "u1", "target": "u2", "weight": 2.0, "edge_score": 0.8},
            {"source": "u2", "target": "u3", "weight": 1.2, "edge_score": 0.5},
        ],
        "communities": [
            {"cluster_id": 0, "size": 2, "community_score": 0.8, "density": 1.0, "object_concentration": 0.9, "relation_breakdown": {"url_share": 3}, "top_nodes": ["u1", "u2"], "top_objects": [{"object_id": "url:a", "count": 2}]},
            {"cluster_id": 1, "size": 1, "community_score": 0.6, "density": 0.0, "object_concentration": 0.8, "relation_breakdown": {"retweet_target": 1}, "top_nodes": ["u3"], "top_objects": [{"object_id": "rt:b", "count": 1}]},
        ],
        "evidence_summary": {"top_objects": [{"object_id": "url:a", "count": 2}, {"object_id": "rt:b", "count": 1}]},
    }
    detect = {
        "detect_model": {
            "lm_feature_source": "sbert:sentence-transformers/all-MiniLM-L6-v2",
            "pretrained_metadata": {"checkpoint_path": "G:/tmp/china.pt"},
        },
        "predictions": [
            {"account_id": "u1", "node_score": 0.93, "predicted_label": 1, "cluster_id": 0},
            {"account_id": "u2", "node_score": 0.61, "predicted_label": 1, "cluster_id": 0},
            {"account_id": "u3", "node_score": 0.44, "predicted_label": 0, "cluster_id": 1},
        ],
        "metrics": {},
        "unlabeled_inference_summary": {"score_mean": 0.66, "positive_at_0_5": 2},
    }

    snapshot = _build_result_snapshot(dataset, discovery, detect, result_source="rerun")

    assert snapshot["label_status"]["uses_pretrained_detect"] is True
    assert snapshot["label_status"]["shows_supervised_metrics"] is False
    assert snapshot["metrics"]["detect"] == {}
    assert snapshot["metrics"]["detect_inference"]["positive_at_0_5"] == 2
    assert snapshot["global_key_nodes"][0]["account_id"] == "u1"


def _make_graph_fixture(tmp_path: Path):
    source_path = tmp_path / "events.csv"
    source_path.write_text(
        "\n".join(
            [
                "account_id,relation,object_id,timestamp,content_id,content,label",
                "u1,url_share,url:a,1,c1,alpha beta beta,1",
                "u2,url_share,url:a,2,c2,alpha gamma,1",
                "u3,url_share,url:b,3,c3,gamma delta,0",
                "u1,profile,profile:u1,4,c4,profile should_ignore,1",
            ]
        ),
        encoding="utf-8",
    )
    dataset = CoordinationDataset(
        id=9,
        slug="graph-demo",
        display_name="Graph Demo",
        source_type="uploaded",
        source_format="csv",
        source_path=str(source_path),
        metadata_json="{}",
        has_labels=True,
        event_rows=4,
        account_nodes=3,
        object_ids=3,
        user_user_edges=2,
        available_relations='["url_share"]',
        latest_run_id=None,
        created_by=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    discovery = {
        "nodes": [
            {"account_id": "u1", "node_score": 0.7, "cluster_id": 0, "directed_out_weight": 2.0, "directed_in_weight": 1.0},
            {"account_id": "u2", "node_score": 0.6, "cluster_id": 0, "directed_out_weight": 1.0, "directed_in_weight": 2.0},
            {"account_id": "u3", "node_score": 0.4, "cluster_id": 1, "directed_out_weight": 1.0, "directed_in_weight": 0.0},
        ],
        "edges": [
            {"source": "u1", "target": "u2", "weight": 2.0, "edge_score": 0.9, "relations": {"url_share": 2}},
            {"source": "u2", "target": "u3", "weight": 1.0, "edge_score": 0.3, "relations": {"url_share": 1}},
        ],
        "communities": [
            {"cluster_id": 0, "size": 2, "community_score": 0.82, "density": 1.0, "top_objects": [{"object_id": "url:a", "count": 2}]},
            {"cluster_id": 1, "size": 1, "community_score": 0.32, "density": 0.0, "top_objects": [{"object_id": "url:b", "count": 1}]},
        ],
    }
    detect = {
        "predictions": [
            {"account_id": "u1", "node_score": 0.95, "predicted_label": 1, "cluster_id": 0},
            {"account_id": "u2", "node_score": 0.88, "predicted_label": 1, "cluster_id": 0},
            {"account_id": "u3", "node_score": 0.2, "predicted_label": 0, "cluster_id": 1},
        ]
    }
    return dataset, discovery, detect


def test_build_coordination_graph_payload_filters_nodes_and_edges(tmp_path):
    dataset, discovery, detect = _make_graph_fixture(tmp_path)

    payload = _build_coordination_graph_payload(
        dataset,
        discovery,
        detect,
        node_limit=2,
        min_node_score=0.5,
    )

    assert [node["id"] for node in payload["nodes"]] == ["u1", "u2"]
    assert payload["summary"]["total_nodes"] == 3
    assert payload["summary"]["rendered_node_count"] == 2
    assert payload["summary"]["rendered_edge_count"] == 1
    assert payload["links"][0]["source"] == "u1"
    assert payload["links"][0]["target"] == "u2"
    assert all(link["source"] in {"u1", "u2"} and link["target"] in {"u1", "u2"} for link in payload["links"])


def test_build_coordination_community_payload_returns_members_and_topwords(tmp_path):
    dataset, discovery, detect = _make_graph_fixture(tmp_path)

    payload = _build_coordination_community_payload(
        dataset,
        discovery,
        detect,
        cluster_id="0",
    )

    assert payload["cluster_id"] == 0
    assert [member["id"] for member in payload["members"]] == ["u1", "u2"]
    assert payload["members"][0]["node_score"] == 0.95
    assert payload["topwords"][0] == {"term": "alpha", "account_count": 2, "frequency": 2}
    assert all(item["term"] != "should_ignore" for item in payload["topwords"])
    assert payload["top_objects"][0]["object_id"] == "url:a"


def test_format_top_object_item_preserves_raw_url_display_value():
    item = _format_top_object_item({"object_id": "https://a.example/path?q=1", "count": 2})

    assert item["relation"] == "url_share"
    assert item["display_value"] == "https://a.example/path?q=1"


def test_format_top_object_item_keeps_processed_structured_identifier_visible():
    item = _format_top_object_item({"object_id": "china:coRT:edge:389:331", "count": 2})

    assert item["relation"] == "retweet_target"
    assert item["display_value"] == "china:coRT:edge:389:331"


def test_enrich_top_object_item_adds_weibo_object_url_and_examples(tmp_path):
    source_path = tmp_path / "events.csv"
    source_path.write_text(
        "\n".join(
            [
                "account_id,relation,object_id,timestamp,content_id,content,nickname,post_url",
                "u1,reply_target,tweet:5300274638881704,2026-05-21T10:00:00+00:00,c1,这是第一条评论,甲,https://m.weibo.cn/detail/5300274638881704",
                "u2,reply_target,tweet:5300274638881704,2026-05-21T10:01:00+00:00,c2,这是第二条评论,乙,https://m.weibo.cn/detail/5300274638881704",
            ]
        ),
        encoding="utf-8",
    )
    dataset = CoordinationDataset(
        id=10,
        slug="weibo-demo",
        display_name="Weibo Demo",
        source_type="uploaded",
        source_format="csv",
        source_path=str(source_path),
        metadata_json="{}",
        has_labels=False,
        event_rows=2,
        account_nodes=2,
        object_ids=1,
        user_user_edges=1,
        available_relations='["reply_target"]',
        latest_run_id=None,
        created_by=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    payload = _build_coordination_community_payload(
        dataset,
        {
            "nodes": [{"account_id": "u1", "cluster_id": 0}, {"account_id": "u2", "cluster_id": 0}],
            "communities": [
                {
                    "cluster_id": 0,
                    "size": 2,
                    "community_score": 0.8,
                    "density": 1.0,
                    "object_concentration": 1.0,
                    "relation_breakdown": {"reply_target": 2},
                    "top_objects": [{"relation": "reply_target", "object_id": "tweet:5300274638881704", "count": 2, "share": 1.0}],
                }
            ],
        },
        {"predictions": [{"account_id": "u1", "node_score": 0.8}, {"account_id": "u2", "node_score": 0.7}]},
        cluster_id="0",
    )

    top_object = payload["top_objects"][0]
    assert top_object["object_url"] == "https://m.weibo.cn/detail/5300274638881704"
    assert top_object["display_value"] == "这是第一条评论"
    assert top_object["evidence_examples"]
    assert top_object["evidence_examples"][0]["post_url"] == "https://m.weibo.cn/detail/5300274638881704"


def test_object_evidence_examples_keep_enough_rows_for_account_level_filtering(tmp_path):
    source_path = tmp_path / "events_many.csv"
    source_path.write_text(
        "\n".join(
            [
                "account_id,relation,object_id,timestamp,content_id,content,nickname,post_url",
                "u1,reply_target,tweet:1,2026-05-21T10:00:00+00:00,c1,目标账号帖子,甲,https://m.weibo.cn/detail/1",
                "u2,reply_target,tweet:1,2026-05-21T10:01:00+00:00,c2,样例2,乙,https://m.weibo.cn/detail/1",
                "u3,reply_target,tweet:1,2026-05-21T10:02:00+00:00,c3,样例3,丙,https://m.weibo.cn/detail/1",
                "u4,reply_target,tweet:1,2026-05-21T10:03:00+00:00,c4,样例4,丁,https://m.weibo.cn/detail/1",
                "u5,reply_target,tweet:1,2026-05-21T10:04:00+00:00,c5,样例5,戊,https://m.weibo.cn/detail/1",
            ]
        ),
        encoding="utf-8",
    )
    dataset = CoordinationDataset(
        id=14,
        slug="weibo-many-demo",
        display_name="Weibo Many Demo",
        source_type="uploaded",
        source_format="csv",
        source_path=str(source_path),
        metadata_json="{}",
        has_labels=False,
        event_rows=5,
        account_nodes=5,
        object_ids=1,
        user_user_edges=1,
        available_relations='["reply_target"]',
        latest_run_id=None,
        created_by=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    payload = _build_coordination_community_payload(
        dataset,
        {
            "nodes": [
                {"account_id": "u1", "cluster_id": 0},
                {"account_id": "u2", "cluster_id": 0},
                {"account_id": "u3", "cluster_id": 0},
                {"account_id": "u4", "cluster_id": 0},
                {"account_id": "u5", "cluster_id": 0},
            ],
            "communities": [
                {
                    "cluster_id": 0,
                    "size": 5,
                    "community_score": 0.8,
                    "density": 1.0,
                    "object_concentration": 1.0,
                    "relation_breakdown": {"reply_target": 5},
                    "top_objects": [{"relation": "reply_target", "object_id": "tweet:1", "count": 5, "share": 1.0}],
                }
            ],
        },
        {"predictions": [{"account_id": f"u{i}", "node_score": 0.9 - i * 0.1} for i in range(1, 6)]},
        cluster_id="0",
    )

    examples = payload["top_objects"][0]["evidence_examples"]
    assert len(examples) >= 5
    assert any(example["account_id"] == "u1" for example in examples)


def test_build_coordination_graph_payload_returns_empty_when_result_is_missing(tmp_path):
    dataset = CoordinationDataset(
        id=11,
        slug="uploaded-empty",
        display_name="Uploaded Empty",
        source_type="uploaded",
        source_format="csv",
        source_path=str(tmp_path / "source.csv"),
        metadata_json="{}",
        has_labels=False,
        event_rows=0,
        account_nodes=0,
        object_ids=0,
        user_user_edges=0,
        available_relations="[]",
        latest_run_id=None,
        created_by=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    payload = _build_coordination_graph_payload(
        dataset,
        {},
        {},
        node_limit=200,
        min_node_score=0.0,
    )

    assert payload["dataset_summary"]["display_name"] == "Uploaded Empty"
    assert payload["nodes"] == []
    assert payload["links"] == []
    assert payload["summary"]["total_nodes"] == 0
    assert payload["summary"]["rendered_node_count"] == 0
    assert payload["summary"]["rendered_edge_count"] == 0


def test_normalize_event_table_accepts_real_platform_alias_columns():
    import pandas as pd

    frame = pd.DataFrame(
        [
            {
                "uid": "123",
                "event_type": "url_share",
                "object": "https://example.com/a",
                "created_at": "2026-07-03T10:00:00+00:00",
                "note_id": "n1",
                "desc": "小红书正文",
                "author_name": "测试用户",
                "platform_name": "xiaohongshu",
                "note_url": "https://www.xiaohongshu.com/explore/abc123",
                "user_url": "https://www.xiaohongshu.com/user/profile/5f123",
            }
        ]
    )

    normalized = normalize_event_table(frame)

    assert normalized.loc[0, "account_id"] == "123"
    assert normalized.loc[0, "relation"] == "url_share"
    assert normalized.loc[0, "object_id"] == "https://example.com/a"
    assert normalized.loc[0, "content_id"] == "n1"
    assert normalized.loc[0, "content"] == "小红书正文"
    assert normalized.loc[0, "nickname"] == "测试用户"
    assert normalized.loc[0, "platform"] == "xiaohongshu"
    assert normalized.loc[0, "post_url"] == "https://www.xiaohongshu.com/explore/abc123"
    assert normalized.loc[0, "profile_url"] == "https://www.xiaohongshu.com/user/profile/5f123"


def test_build_account_profile_url_supports_real_platforms():
    assert _build_account_profile_url(platform="weibo", account_id="123", screen_name="") == "https://m.weibo.cn/u/123"
    assert _build_account_profile_url(platform="xiaohongshu", account_id="abc123", screen_name="") == "https://www.xiaohongshu.com/user/profile/abc123"
    assert _build_account_profile_url(platform="douyin", account_id="9988", screen_name="") == "https://www.douyin.com/user/9988"


def test_build_coordination_community_payload_resolves_xhs_and_douyin_objects(tmp_path):
    xhs_source = tmp_path / "xhs.csv"
    xhs_source.write_text(
        "\n".join(
            [
                "account_id,relation,object_id,timestamp,content_id,content,nickname,platform,post_url",
                "u1,reply_target,note:abc123,2026-07-03T10:00:00+00:00,n1,这是小红书笔记内容,甲,xiaohongshu,https://www.xiaohongshu.com/explore/abc123",
                "u2,reply_target,note:abc123,2026-07-03T10:01:00+00:00,n2,这是第二条小红书内容,乙,xiaohongshu,https://www.xiaohongshu.com/explore/abc123",
            ]
        ),
        encoding="utf-8",
    )
    xhs_dataset = CoordinationDataset(
        id=12,
        slug="xhs-demo",
        display_name="XHS Demo",
        source_type="uploaded",
        source_format="csv",
        source_path=str(xhs_source),
        metadata_json="{}",
        has_labels=False,
        event_rows=2,
        account_nodes=2,
        object_ids=1,
        user_user_edges=1,
        available_relations='["reply_target"]',
        latest_run_id=None,
        created_by=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    xhs_payload = _build_coordination_community_payload(
        xhs_dataset,
        {
            "nodes": [{"account_id": "u1", "cluster_id": 0}, {"account_id": "u2", "cluster_id": 0}],
            "communities": [
                {
                    "cluster_id": 0,
                    "size": 2,
                    "community_score": 0.8,
                    "density": 1.0,
                    "object_concentration": 1.0,
                    "relation_breakdown": {"reply_target": 2},
                    "top_objects": [{"relation": "reply_target", "object_id": "note:abc123", "count": 2, "share": 1.0}],
                }
            ],
        },
        {"predictions": [{"account_id": "u1", "node_score": 0.8}, {"account_id": "u2", "node_score": 0.7}]},
        cluster_id="0",
    )
    assert xhs_payload["top_objects"][0]["object_url"] == "https://www.xiaohongshu.com/explore/abc123"
    assert "小红书" in xhs_payload["top_objects"][0]["display_value"]

    douyin_source = tmp_path / "douyin.csv"
    douyin_source.write_text(
        "\n".join(
            [
                "account_id,relation,object_id,timestamp,content_id,content,nickname,platform,post_url",
                "u1,reply_target,video:729001,2026-07-03T10:00:00+00:00,v1,这是抖音视频文案,甲,douyin,https://www.douyin.com/video/729001",
                "u2,reply_target,video:729001,2026-07-03T10:01:00+00:00,v2,这是第二条抖音文案,乙,douyin,https://www.douyin.com/video/729001",
            ]
        ),
        encoding="utf-8",
    )
    douyin_dataset = CoordinationDataset(
        id=13,
        slug="douyin-demo",
        display_name="Douyin Demo",
        source_type="uploaded",
        source_format="csv",
        source_path=str(douyin_source),
        metadata_json="{}",
        has_labels=False,
        event_rows=2,
        account_nodes=2,
        object_ids=1,
        user_user_edges=1,
        available_relations='["reply_target"]',
        latest_run_id=None,
        created_by=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    douyin_payload = _build_coordination_community_payload(
        douyin_dataset,
        {
            "nodes": [{"account_id": "u1", "cluster_id": 0}, {"account_id": "u2", "cluster_id": 0}],
            "communities": [
                {
                    "cluster_id": 0,
                    "size": 2,
                    "community_score": 0.8,
                    "density": 1.0,
                    "object_concentration": 1.0,
                    "relation_breakdown": {"reply_target": 2},
                    "top_objects": [{"relation": "reply_target", "object_id": "video:729001", "count": 2, "share": 1.0}],
                }
            ],
        },
        {"predictions": [{"account_id": "u1", "node_score": 0.8}, {"account_id": "u2", "node_score": 0.7}]},
        cluster_id="0",
    )
    assert douyin_payload["top_objects"][0]["object_url"] == "https://www.douyin.com/video/729001"
    assert "抖音" in douyin_payload["top_objects"][0]["display_value"]
