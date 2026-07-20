"""传播归因模块测试。

测试证据链提取、关键路径、显式/隐式边建模等新增功能，
同时回归验证原有 graph / key_roles / claims / timeline 字段。
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from app.core.propagation import build_propagation_graph
from app.services.kt2_prediction_service import build_event_inference_bundle, predict_event_with_checkpoint


# ---------------------------------------------------------------------------
# Fixtures: 构造测试数据
# ---------------------------------------------------------------------------

def _ts(minutes: int) -> str:
    """生成 UTC 时间戳字符串，偏移 minutes 分钟。"""
    base = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
    return (base + timedelta(minutes=minutes)).isoformat()


def _make_posts() -> list[dict]:
    """构造一组含协同传播模式的帖子。

    传播链：
      u1 --[url_A]--> u2 --[url_A]--> u3
      u1 --[#tag1]--> u4
      u2 --[#tag1]--> u4  (u4 同时被 u1 和 u2 影响)
    """
    return [
        {"post_id": "p1", "author_id": "u1", "author_name": "Alice",
         "timestamp": _ts(0), "url": "https://example.com/a", "hashtags": ["#tag1"], "content": "原始帖子"},
        {"post_id": "p2", "author_id": "u2", "author_name": "Bob",
         "timestamp": _ts(5), "url": "https://example.com/a", "hashtags": [], "content": "转发帖子"},
        {"post_id": "p3", "author_id": "u3", "author_name": "Carol",
         "timestamp": _ts(10), "url": "https://example.com/a", "hashtags": [], "content": "再次转发"},
        {"post_id": "p4", "author_id": "u4", "author_name": "Dave",
         "timestamp": _ts(15), "url": "", "hashtags": ["#tag1"], "content": "标签跟随"},
        {"post_id": "p5", "author_id": "u5", "author_name": "Eve",
         "timestamp": _ts(20), "url": "https://example.com/b", "hashtags": [], "content": "独立帖子"},
    ]


def _make_comments() -> list[dict]:
    """构造评论数据，含 reply_to 字段。"""
    return [
        {"comment_id": "c1", "post_id": "p1", "author_id": "u2", "author_name": "Bob",
         "timestamp": _ts(3), "reply_to": "p1", "content": "回复原帖"},
        {"comment_id": "c2", "post_id": "p2", "author_id": "u3", "author_name": "Carol",
         "timestamp": _ts(8), "reply_to": "p2", "content": "回复转发"},
        {"comment_id": "c3", "post_id": "p1", "author_id": "u4", "author_name": "Dave",
         "timestamp": _ts(12), "reply_to": "c1", "content": "回复评论"},
    ]


# ---------------------------------------------------------------------------
# 回归测试：原有字段不变
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:
    """确保新增功能不破坏原有返回结构。"""

    def test_top_level_keys(self):
        result = build_propagation_graph(_make_posts())
        assert "graph" in result
        assert "key_roles" in result
        assert "claims" in result
        assert "timeline" in result
        assert "evidence_chains" in result  # 新增字段
        assert "path_analysis" in result
        assert "diffusion_summary" in result
        assert "user_quality" in result

    def test_graph_structure(self):
        result = build_propagation_graph(_make_posts())
        g = result["graph"]
        assert "nodes" in g and "edges" in g
        assert "node_count" in g and "edge_count" in g
        assert g["node_count"] > 0
        assert g["edge_count"] > 0

    def test_key_roles_structure(self):
        result = build_propagation_graph(_make_posts())
        kr = result["key_roles"]
        assert "originators" in kr
        assert "bridges" in kr
        assert "amplifiers" in kr

    def test_bridge_roles_fallback_to_relay_structure_when_betweenness_is_sparse(self):
        posts = [
            {"post_id": "p1", "author_id": "source", "author_name": "Source",
             "timestamp": _ts(0), "url": "https://example.com/a", "hashtags": [], "content": "root"},
            {"post_id": "p2", "author_id": "relay", "author_name": "Relay",
             "timestamp": _ts(1), "url": "https://example.com/a", "hashtags": [], "content": "relay-in"},
            {"post_id": "p3", "author_id": "leaf", "author_name": "Leaf",
             "timestamp": _ts(2), "url": "https://example.com/a", "hashtags": [], "content": "leaf"},
        ]

        result = build_propagation_graph(posts)
        bridges = result["key_roles"]["bridges"]

        assert bridges
        assert bridges[0]["account_id"] == "relay"
        assert bridges[0]["in_degree"] > 0
        assert bridges[0]["out_degree"] > 0

    def test_claims_structure(self):
        result = build_propagation_graph(_make_posts())
        assert len(result["claims"]) > 0
        c = result["claims"][0]
        assert "object_id" in c
        assert "share_count" in c
        assert "account_count" in c
        assert "first_share" in c

    def test_timeline_structure(self):
        result = build_propagation_graph(_make_posts())
        assert len(result["timeline"]) > 0
        t = result["timeline"][0]
        assert "post_id" in t
        assert "author_id" in t
        assert "timestamp" in t

    def test_empty_posts(self):
        result = build_propagation_graph([])
        assert result["graph"]["node_count"] == 0
        assert result["evidence_chains"] == []
        assert result["diffusion_summary"]["visible_nodes"] == []

    def test_no_comments_graceful(self):
        """无评论时不崩溃，证据链仍可生成（仅隐式边）。"""
        result = build_propagation_graph(_make_posts())
        assert isinstance(result["evidence_chains"], list)


class TestUserQualityParsing:
    def test_parses_chinese_follower_units_and_verified_values(self):
        posts = [
            {
                "post_id": "p1",
                "author_id": "u1",
                "author_name": "High Reach",
                "timestamp": _ts(0),
                "url": "https://example.com/a",
                "hashtags": [],
                "content": "source",
                "author_profile": {"followers_count": "1.2万", "verified": "认证"},
            },
            {
                "post_id": "p2",
                "author_id": "u2",
                "author_name": "Mass Reach",
                "timestamp": _ts(1),
                "url": "https://example.com/a",
                "hashtags": [],
                "content": "follow",
                "author_profile": {"followers_count": "2亿", "verified": "未认证"},
            },
        ]

        result = build_propagation_graph(posts)
        accounts = {row["account_id"]: row for row in result["user_quality"]["top_accounts"]}

        assert accounts["u1"]["followers"] == 12000
        assert accounts["u1"]["verified"] is True
        assert accounts["u2"]["followers"] == 200000000
        assert accounts["u2"]["verified"] is False
        assert result["user_quality"]["verified_count"] == 1


class TestKT2EventInferenceAdapter:
    def test_event_bundle_maps_real_user_candidates(self):
        bundle = build_event_inference_bundle(
            _make_posts(),
            _make_comments(),
            max_sequence_len=16,
            user_hash_buckets=128,
            relation_neighbor_count=4,
            hyperedge_count=4,
            relation_neighbors={},
        )

        assert bundle["status"] == "ok"
        assert bundle["candidate_meta"]["u1"]["author_name"] == "Alice"
        assert bundle["candidate_meta"]["u2"]["author_name"] == "Bob"
        assert bundle["candidate_buckets"]

    def test_event_bundle_accepts_collected_field_aliases(self):
        bundle = build_event_inference_bundle(
            [
                {"post_id": "p1", "user_id": "u1", "screen_name": "Alice Screen", "created_at": _ts(0)},
                {"post_id": "p2", "uid": "u2", "username": "Bob User", "publish_time": _ts(1)},
                {"post_id": "p3", "account_id": "u3", "account_label": "Carol Account", "published_at": _ts(2)},
            ],
            [],
            max_sequence_len=16,
            user_hash_buckets=128,
            relation_neighbor_count=4,
            hyperedge_count=4,
            relation_neighbors={},
        )

        assert bundle["status"] == "ok"
        assert bundle["candidate_meta"]["u1"]["author_name"] == "Alice Screen"
        assert bundle["candidate_meta"]["u2"]["author_name"] == "Bob User"
        assert bundle["candidate_meta"]["u3"]["author_name"] == "Carol Account"

    def test_missing_checkpoint_returns_unavailable_status(self, tmp_path):
        result = predict_event_with_checkpoint(
            tmp_path / "missing-twitter-checkpoint.pt",
            _make_posts(),
            _make_comments(),
        )

        assert result["status"] == "missing_checkpoint"

    def test_empty_comments(self):
        """显式传入空评论列表。"""
        result = build_propagation_graph(_make_posts(), comments=[])
        assert isinstance(result["evidence_chains"], list)

    def test_zhiview_style_summaries_from_observed_metadata(self):
        posts = [
            {
                "post_id": "p1",
                "author_id": "u1",
                "author_name": "Alice",
                "timestamp": _ts(0),
                "url": "https://example.com/a",
                "hashtags": [],
                "content": "源头",
                "source": "微博 weibo.com",
                "author_profile": {"ip_location": "北京", "followers_count": 20000, "verified": True},
            },
            {
                "post_id": "p2",
                "author_id": "u2",
                "author_name": "Bob",
                "timestamp": _ts(5),
                "url": "https://example.com/a",
                "hashtags": [],
                "content": "转发",
                "source": "小米手机",
                "author_profile": {"ip_location": "广东", "followers_count": 800, "verified": False},
            },
            {
                "post_id": "p3",
                "author_id": "u3",
                "author_name": "Carol",
                "timestamp": _ts(10),
                "url": "https://example.com/a",
                "hashtags": [],
                "content": "继续转发",
                "source": "小米手机",
                "author_profile": {"ip_location": "广东", "followers_count": 50},
            },
        ]

        result = build_propagation_graph(posts)

        assert result["path_analysis"]["edge_count"] > 0
        assert result["path_analysis"]["layer_distribution"]
        assert result["user_quality"]["total_users"] == 3
        assert result["user_quality"]["verified_count"] == 1
        assert any(row["quality"] == "高" and row["count"] == 1 for row in result["user_quality"]["buckets"])

    def test_diffusion_summary_uses_observed_root_and_readable_backbone(self):
        posts = [
            {"post_id": "p0", "author_id": "root", "author_name": "Root", "timestamp": _ts(0),
             "url": "https://example.com/main", "hashtags": [], "content": "root"},
            {"post_id": "p1", "author_id": "a", "author_name": "A", "timestamp": _ts(1),
             "url": "https://example.com/main", "hashtags": [], "content": "a"},
            {"post_id": "p2", "author_id": "b", "author_name": "B", "timestamp": _ts(2),
             "url": "https://example.com/main", "hashtags": [], "content": "b"},
            {"post_id": "p3", "author_id": "c", "author_name": "C", "timestamp": _ts(3),
             "url": "https://example.com/main", "hashtags": [], "content": "c"},
            {"post_id": "p4", "author_id": "parallel", "author_name": "Parallel", "timestamp": _ts(4),
             "url": "https://example.com/side", "hashtags": [], "content": "parallel"},
            {"post_id": "p5", "author_id": "side", "author_name": "Side", "timestamp": _ts(5),
             "url": "https://example.com/side", "hashtags": [], "content": "side"},
        ]

        result = build_propagation_graph(posts)
        summary = result["diffusion_summary"]

        assert summary["root_node"]["id"] == "root"
        assert len(summary["visible_nodes"]) <= 300
        assert summary["tree_edges"]
        assert summary["layers"][0]["level"] == 0
        visible_ids = {node["id"] for node in summary["visible_nodes"]}
        assert {"root", "a", "b", "c"}.issubset(visible_ids)
        assert "root" in summary["detail_index"]["nodes"]
        assert "https://example.com/main" in summary["detail_index"]["objects"]

    def test_diffusion_summary_aligns_root_with_key_path_origin(self):
        posts = [
            {"post_id": "p0", "author_id": "global", "author_name": "Global", "timestamp": _ts(0),
             "url": "https://example.com/noise-a", "hashtags": [], "content": "global"},
            {"post_id": "p1", "author_id": "noise1", "author_name": "Noise1", "timestamp": _ts(1),
             "url": "https://example.com/noise-a", "hashtags": [], "content": "noise"},
            {"post_id": "p2", "author_id": "noise2", "author_name": "Noise2", "timestamp": _ts(2),
             "url": "https://example.com/noise-a", "hashtags": [], "content": "noise"},
            {"post_id": "p3", "author_id": "origin", "author_name": "Origin", "timestamp": _ts(3),
             "url": "https://example.com/key", "hashtags": [], "content": "origin"},
            {"post_id": "p4", "author_id": "hop1", "author_name": "Hop1", "timestamp": _ts(4),
             "url": "https://example.com/key", "hashtags": [], "content": "hop1"},
            {"post_id": "p5", "author_id": "hop2", "author_name": "Hop2", "timestamp": _ts(5),
             "url": "https://example.com/key", "hashtags": [], "content": "hop2"},
        ]

        result = build_propagation_graph(posts)
        summary = result["diffusion_summary"]
        top_path = result["path_analysis"]["key_paths"][0]["nodes"]
        edge_keys = {(edge["source"], edge["target"]) for edge in summary["tree_edges"]}

        assert summary["root_node"]["id"] == top_path[0]
        assert (top_path[0], top_path[1]) in edge_keys
        assert (top_path[1], top_path[2]) in edge_keys

    def test_diffusion_summary_contains_clustered_similarity_layout(self):
        posts = [
            {"post_id": "p0", "author_id": "root", "author_name": "Root", "timestamp": _ts(0),
             "url": "https://example.com/main", "hashtags": ["#main"], "content": "root"},
            {"post_id": "p1", "author_id": "near", "author_name": "Near", "timestamp": _ts(1),
             "url": "https://example.com/main", "hashtags": ["#main"], "content": "near"},
            {"post_id": "p2", "author_id": "mid", "author_name": "Mid", "timestamp": _ts(2),
             "url": "https://example.com/main", "hashtags": [], "content": "mid"},
            {"post_id": "p3", "author_id": "far", "author_name": "Far", "timestamp": _ts(3),
             "url": "https://example.com/other", "hashtags": [], "content": "far"},
            {"post_id": "p4", "author_id": "far2", "author_name": "Far2", "timestamp": _ts(4),
             "url": "https://example.com/other", "hashtags": [], "content": "far2"},
        ]

        result = build_propagation_graph(posts)
        summary = result["diffusion_summary"]
        nodes = {node["id"]: node for node in summary["visible_nodes"]}

        assert summary["meta"]["layout"] == "clustered_similarity"
        assert nodes["root"]["layout_x"] == 0
        assert nodes["root"]["layout_y"] == 0
        assert nodes["near"]["shared_object_ids"]
        assert nodes["near"]["similarity_to_root"] > nodes["far"]["similarity_to_root"]
        assert nodes["near"]["layout_radius"] <= nodes["mid"]["layout_radius"]
        assert all("layout_cluster" in node for node in nodes.values())

        graph_edge_keys = {(edge["source"], edge["target"]) for edge in result["graph"]["edges"]}
        for edge in summary["tree_edges"]:
            assert edge["type"] != "similarity"
            if not edge.get("is_parallel_root"):
                assert (edge["source"], edge["target"]) in graph_edge_keys

    def test_diffusion_summary_respects_dynamic_node_limit_and_full_view(self):
        posts = [
            {"post_id": f"p{i}", "author_id": f"u{i}", "author_name": f"User{i}",
             "timestamp": _ts(i), "url": "https://example.com/dynamic-limit",
             "hashtags": [], "content": f"post {i}"}
            for i in range(12)
        ]

        limited = build_propagation_graph(posts, diffusion_node_limit=5)["diffusion_summary"]
        full = build_propagation_graph(posts, diffusion_node_limit=0)["diffusion_summary"]

        assert limited["meta"]["visible_node_limit"] == 5
        assert limited["meta"]["visible_node_count"] <= 5
        assert limited["meta"]["is_full_view"] is False
        assert full["meta"]["visible_node_limit"] == 12
        assert full["meta"]["visible_node_count"] == 12
        assert full["meta"]["is_full_view"] is True

    def test_diffusion_summary_edges_do_not_connect_same_layer_nodes(self):
        result = build_propagation_graph(_make_posts(), _make_comments(), diffusion_node_limit=0)
        summary = result["diffusion_summary"]
        layer_by_node = {node["id"]: node["layer"] for node in summary["visible_nodes"]}

        for edge in summary["tree_edges"] + summary["highlight_edges"]:
            assert layer_by_node[edge["source"]] != layer_by_node[edge["target"]]


# ---------------------------------------------------------------------------
# 边类型测试
# ---------------------------------------------------------------------------

class TestEdgeTypes:
    """验证 MultiDiGraph 中显式边和隐式边的正确性。"""

    def test_implicit_edges_have_type(self):
        result = build_propagation_graph(_make_posts())
        implicit = [e for e in result["graph"]["edges"] if e["type"] == "implicit"]
        assert len(implicit) > 0

    def test_explicit_edges_added(self):
        result = build_propagation_graph(_make_posts(), _make_comments())
        explicit = [e for e in result["graph"]["edges"] if e["type"] == "explicit"]
        assert len(explicit) > 0

    def test_both_edge_types_coexist(self):
        result = build_propagation_graph(_make_posts(), _make_comments())
        types = {e["type"] for e in result["graph"]["edges"]}
        assert "implicit" in types
        assert "explicit" in types

    def test_explicit_edge_direction(self):
        """回复边方向：被回复内容作者 → 评论者。"""
        result = build_propagation_graph(_make_posts(), _make_comments())
        explicit = [e for e in result["graph"]["edges"] if e["type"] == "explicit"]
        # c1: u2 回复 p1(u1)，传播方向应为 u1→u2。
        assert any(e["source"] == "u1" and e["target"] == "u2" for e in explicit)

    def test_diffusion_root_requires_observed_post_evidence(self):
        posts = [
            {"post_id": "p1", "author_id": "poster", "author_name": "Poster",
             "timestamp": _ts(0), "url": "https://example.com/root", "hashtags": [], "content": "source"},
            {"post_id": "p2", "author_id": "follower", "author_name": "Follower",
             "timestamp": _ts(5), "url": "https://example.com/root", "hashtags": [], "content": "follow"},
        ]
        comments = [
            {"comment_id": "c1", "post_id": "p1", "author_id": "comment_only", "author_name": "CommentOnly",
             "timestamp": _ts(1), "reply_to": "p1", "content": "reply"},
            {"comment_id": "c2", "post_id": "p1", "author_id": "second_commenter", "author_name": "SecondCommenter",
             "timestamp": _ts(2), "reply_to": "c1", "content": "reply to comment"},
        ]

        result = build_propagation_graph(posts, comments)
        summary = result["diffusion_summary"]
        root_detail = summary["detail_index"]["nodes"][summary["root_node"]["id"]]

        assert summary["root_node"]["id"] == "poster"
        assert root_detail["post_count"] > 0
        assert root_detail["posts"]


# ---------------------------------------------------------------------------
# 证据链测试
# ---------------------------------------------------------------------------

class TestEvidenceChains:
    """验证证据链结构和内容。"""

    def test_chains_generated(self):
        result = build_propagation_graph(_make_posts(), _make_comments())
        chains = result["evidence_chains"]
        assert len(chains) > 0

    def test_chain_structure(self):
        result = build_propagation_graph(_make_posts(), _make_comments())
        chain = result["evidence_chains"][0]
        assert "claim_id" in chain
        assert "share_count" in chain
        assert "originator" in chain
        assert "key_paths" in chain
        assert "supporting_posts" in chain

    def test_originator_is_earliest(self):
        result = build_propagation_graph(_make_posts(), _make_comments())
        # url_A 的 originator 应该是 u1 (Alice, 最早发布)
        url_chain = None
        for c in result["evidence_chains"]:
            if "example.com/a" in c["claim_id"]:
                url_chain = c
                break
        if url_chain:
            assert url_chain["originator"]["account_id"] == "u1"

    def test_supporting_posts_present(self):
        result = build_propagation_graph(_make_posts(), _make_comments())
        chain = result["evidence_chains"][0]
        assert len(chain["supporting_posts"]) > 0
        sp = chain["supporting_posts"][0]
        assert "post_id" in sp
        assert "author_id" in sp
        assert "timestamp" in sp

    def test_top_10_limit(self):
        """即使有超过 10 个 claim，证据链最多 10 条。"""
        posts = []
        for i in range(25):
            for j in range(3):
                posts.append({
                    "post_id": f"p_{i}_{j}",
                    "author_id": f"u_{j}",
                    "author_name": f"User{j}",
                    "timestamp": _ts(i * 10 + j),
                    "url": f"https://example.com/{i}",
                    "hashtags": [],
                    "content": f"Post {i}-{j}",
                })
        result = build_propagation_graph(posts)
        assert len(result["evidence_chains"]) <= 10


# ---------------------------------------------------------------------------
# 关键路径测试
# ---------------------------------------------------------------------------

class TestKeyPaths:
    """验证关键路径提取和评分。"""

    def test_paths_exist_for_multi_share_claim(self):
        result = build_propagation_graph(_make_posts(), _make_comments())
        for chain in result["evidence_chains"]:
            if chain["share_count"] >= 3:
                assert len(chain["key_paths"]) > 0, \
                    f"claim {chain['claim_id']} has {chain['share_count']} shares but no paths"

    def test_path_structure(self):
        result = build_propagation_graph(_make_posts(), _make_comments())
        for chain in result["evidence_chains"]:
            for path in chain["key_paths"]:
                assert "path_id" in path
                assert "nodes" in path
                assert "edges" in path
                assert "score" in path
                assert "explanation" in path
                assert len(path["nodes"]) >= 2

    def test_path_edges_match_nodes(self):
        result = build_propagation_graph(_make_posts(), _make_comments())
        for chain in result["evidence_chains"]:
            for path in chain["key_paths"]:
                assert len(path["edges"]) == len(path["nodes"]) - 1
                for i, edge in enumerate(path["edges"]):
                    assert edge["source"] == path["nodes"][i]
                    assert edge["target"] == path["nodes"][i + 1]

    def test_path_score_positive(self):
        result = build_propagation_graph(_make_posts(), _make_comments())
        for chain in result["evidence_chains"]:
            for path in chain["key_paths"]:
                assert path["score"] > 0

    def test_paths_sorted_by_score(self):
        result = build_propagation_graph(_make_posts(), _make_comments())
        for chain in result["evidence_chains"]:
            scores = [p["score"] for p in chain["key_paths"]]
            assert scores == sorted(scores, reverse=True)

    def test_max_5_paths_per_claim(self):
        result = build_propagation_graph(_make_posts(), _make_comments())
        for chain in result["evidence_chains"]:
            assert len(chain["key_paths"]) <= 5


# ---------------------------------------------------------------------------
# 路径解释测试
# ---------------------------------------------------------------------------

class TestPathExplanation:
    """验证路径解释是中文且包含关键信息。"""

    def test_explanation_is_chinese(self):
        result = build_propagation_graph(_make_posts(), _make_comments())
        for chain in result["evidence_chains"]:
            for path in chain["key_paths"]:
                exp = path["explanation"]
                assert "发起传播" in exp or "桥接扩散" in exp or "放大传播" in exp or "中继传播" in exp or "接收传播" in exp

    def test_explanation_contains_arrow(self):
        result = build_propagation_graph(_make_posts(), _make_comments())
        for chain in result["evidence_chains"]:
            for path in chain["key_paths"]:
                if len(path["nodes"]) >= 2:
                    assert "→" in path["explanation"]
