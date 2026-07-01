"""传播归因模块测试。

测试证据链提取、关键路径、显式/隐式边建模等新增功能，
同时回归验证原有 graph / key_roles / claims / timeline 字段。
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from app.core.propagation import build_propagation_graph


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

    def test_no_comments_graceful(self):
        """无评论时不崩溃，证据链仍可生成（仅隐式边）。"""
        result = build_propagation_graph(_make_posts())
        assert isinstance(result["evidence_chains"], list)

    def test_empty_comments(self):
        """显式传入空评论列表。"""
        result = build_propagation_graph(_make_posts(), comments=[])
        assert isinstance(result["evidence_chains"], list)


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
        """回复边方向：评论者 → 被回复者。"""
        result = build_propagation_graph(_make_posts(), _make_comments())
        explicit = [e for e in result["graph"]["edges"] if e["type"] == "explicit"]
        # c1: u2 回复 p1(u1) → u2→u1
        sources = {e["source"] for e in explicit}
        targets = {e["target"] for e in explicit}
        assert "u2" in sources  # Bob 回复了 Alice
        assert "u1" in targets


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
