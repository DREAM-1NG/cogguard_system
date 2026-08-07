"""Review 模块单元测试。

测试核心模块：evidence_builder, phase_detector, ds_fusion, disarm_scorer, report_builder。
不依赖数据库，使用 mock 数据。
"""

import math
import asyncio
import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from app.core.review.evidence_builder import (
    EvidencePack,
    WindowFeatures,
    build_evidence_pack,
    _gini,
    _shannon_entropy,
    _burstiness,
)
from app.core.review.gate_suite import evaluate_gate_suite
from app.core.review.gate_suite import evaluate_gate_suite_from_dataset
from app.core.review.gate_dataset import get_gate_dataset_contract_spec
from app.core.review.gate_dataset import build_gate_dataset_manifest
from app.core.review.gate_dataset import gate_dataset_contract_view
from app.core.review.gate_dataset import normalize_gate_dataset
from app.core.review.gate_dataset import validate_gate_dataset_contract
from app.core.review.graph_exporter import export_review_heterogeneous_graph
from app.core.review.graph_exporter import read_review_graph_artifact
from app.core.review.graph_exporter import write_review_graph_artifact
from app.core.review.agent_review import run_manual_agent_review
from app.core.review.agent_review import OpenAICompatibleAgentProvider
from app.core.review.agent_review import OpenAICompatibleConfig
from app.core.review.governance_reference import build_governance_reference_context
from app.core.review.governance_reference import load_governance_reference_library
from app.core.review.agent_policy import optimize_agent_policy
from app.core.review.agent_policy import refine_agent_policy_loop
from app.core.review.agent_policy import summarize_feedback_memory
from app.core.review.multi_agent import execute_multi_agent_review
from app.core.review.post_gate import evaluate_post_gate
from app.core.review.community_gate import evaluate_community_gate
from app.core.review.review_executor import execute_review_queue
from app.core.review.review_queue import build_review_queue
from app.core.review.user_gate import evaluate_user_gate
from app.core.review.user_mil import score_user_mil
from app.core.review.layered_harmfulness import assess_layered_harmfulness
from app.core.review.phase_detector import (
    PhaseResult,
    classify_phase,
    estimate_hazard,
    detect_phase,
)
from app.core.review.ds_fusion import (
    FusionResult,
    dempster_combine,
    mass_to_belief_interval,
    coordination_mass,
    propagation_mass,
    account_mass,
    fuse_evidence,
)
from app.core.review.disarm_scorer import (
    map_evidence_to_techniques,
    score_attack_path,
    predict_next_techniques,
    recommend_countermeasures,
    score_attack_path_full,
)
from app.core.review.post_semantics import (
    assess_post_semantics,
    build_claim_candidates,
    normalize_multimodal_post,
)
from app.core.review.report_builder import build_report
from app.api.v1 import risk as risk_api
from app.services import risk_service

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"


def _load_script_module(script_name: str):
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(script_name, SCRIPT_DIR / f"{script_name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# ===================================================================
# Fixtures: mock upstream data
# ===================================================================

def _mock_coord_data(coordinated_accounts=15, coordinated_edges=20):
    graph_edges = [
        {
            "source": "u0",
            "target": "u1",
            "weight": 3,
            "avg_time_delta": 10,
            "edge_symmetry_score": 0.7,
            "relation": "url_share",
            "object_id": "https://cdn.example.com/image1.jpg",
            "object_instances": [
                {"relation": "url_share", "object_id": "https://cdn.example.com/image1.jpg"},
                {"relation": "mention_target", "object_id": "target:health_agency"},
            ],
        }
    ] + [
        {"source": "u0", "target": f"u{i}", "weight": 3,
         "avg_time_delta": 10, "edge_symmetry_score": 0.7}
        for i in range(2, min(coordinated_accounts, 10))
    ]
    return {
        "network": {
            "nodes": [{"id": f"u{i}"} for i in range(coordinated_accounts)],
            "edges": graph_edges,
            "node_count": coordinated_accounts,
            "edge_count": coordinated_edges,
            "component_count": 2,
            "components": [
                {"size": 10, "accounts": [f"u{i}" for i in range(10)]},
                {"size": 5, "accounts": [f"u{i}" for i in range(10, 15)]},
            ],
        },
        "account_stats": [
            {"account_id": f"u{i}", "degree": 3, "avg_weight": 2.5,
             "coordinated_shares_count": 5}
            for i in range(coordinated_accounts)
        ],
        "summary": {
            "total_pairs": 30,
            "coordinated_accounts": coordinated_accounts,
            "coordinated_edges": coordinated_edges,
        },
    }


def _mock_prop_data():
    return {
        "graph": {
            "nodes": [{"id": f"u{i}"} for i in range(20)],
            "edges": [{"source": "u0", "target": "u1", "weight": 2}],
            "node_count": 20,
            "edge_count": 15,
        },
        "key_roles": {
            "originators": [
                {"account_id": "u0", "out_degree": 10},
                {"account_id": "u1", "out_degree": 5},
            ],
            "bridges": [
                {"account_id": "u2", "betweenness": 0.6},
                {"account_id": "u3", "betweenness": 0.4},
                {"account_id": "u4", "betweenness": 0.3},
            ],
            "amplifiers": [
                {"account_id": "u5", "in_degree": 8},
            ],
        },
        "claims": [
            {"object_id": "url1", "share_count": 50, "account_count": 15,
             "first_share": "2026-04-09T10:00:00"},
            {"object_id": "url2", "share_count": 20, "account_count": 8,
             "first_share": "2026-04-09T10:05:00"},
        ],
        "timeline": [
            {"post_id": f"p{i}", "author_id": f"u{i % 20}",
             "timestamp": f"2026-04-09T10:{i:02d}:00", "content": f"test {i}"}
            for i in range(30)
        ],
    }


def _mock_acct_data():
    return [
        {"account_id": f"u{i}", "automation_score": 70 + i, "regularity": 0.8,
         "active_hours": 3, "min_interval_seconds": 15}
        for i in range(8)
    ] + [
        {"account_id": f"u{i}", "automation_score": 20 + i, "regularity": 0.3,
         "active_hours": 12, "min_interval_seconds": 300}
        for i in range(8, 20)
    ]


def _mock_posts_for_semantics():
    return [
        {
            "post_id": "p1",
            "author_id": "u1",
            "author_name": "alice",
            "platform": "mock_weibo",
            "event_id": "test_event",
            "content": "大家快转这个 url1，真相终于曝光了 😂",
            "hashtags": ["#曝光"],
            "media_urls": ["https://cdn.example.com/image1.jpg"],
            "raw_data": {
                "ocr_text": "url1 真相曝光",
                "caption": "截图显示相关说法正在扩散",
            },
        },
        {
            "post_id": "p2",
            "author_id": "u2",
            "author_name": "bob",
            "platform": "mock_weibo",
            "event_id": "test_event",
            "content": "这个 url1 的说法不对，我查了原文，属于误传。",
            "hashtags": ["#辟谣"],
            "media_urls": [],
            "raw_data": {
                "asr_text": "这个链接内容被断章取义",
            },
        },
    ]


# ===================================================================
# Test: evidence_builder
# ===================================================================

class TestEvidenceBuilder:
    def test_gini_uniform(self):
        assert _gini([1, 1, 1, 1]) == 0.0

    def test_gini_concentrated(self):
        g = _gini([0, 0, 0, 100])
        assert g > 0.5

    def test_shannon_entropy_uniform(self):
        e = _shannon_entropy([10, 20, 30, 40, 50])
        assert e > 0

    def test_shannon_entropy_constant(self):
        assert _shannon_entropy([5, 5, 5, 5]) == 0.0

    def test_burstiness_regular(self):
        from datetime import datetime, timedelta
        ts = [datetime(2026, 1, 1) + timedelta(minutes=i * 10) for i in range(10)]
        b = _burstiness(ts)
        assert b < 0.1  # very regular

    def test_build_evidence_pack(self):
        pack = build_evidence_pack(_mock_coord_data(), _mock_prop_data(), _mock_acct_data())
        assert isinstance(pack, EvidencePack)
        assert pack.coordinated_accounts == 15
        assert pack.features.coordination_density > 0
        assert pack.features.bridge_ratio > 0
        assert pack.features.high_automation_ratio > 0
        assert pack.features.automation_entropy >= 0
        assert pack.claim_count == 2

    def test_build_evidence_pack_empty(self):
        pack = build_evidence_pack({}, {}, [])
        assert pack.coordinated_accounts == 0
        assert pack.features.coordination_density == 0.0


# ===================================================================
# Test: phase_detector
# ===================================================================

class TestPhaseDetector:
    def test_classify_seed(self):
        f = WindowFeatures(coordination_density=0.01, burstiness=0.5)
        phase, conf = classify_phase(f)
        assert phase == "seed"
        assert conf > 0.5

    def test_classify_synchronize(self):
        f = WindowFeatures(coordination_density=0.1, burstiness=1.5)
        phase, _ = classify_phase(f)
        assert phase == "synchronize"

    def test_classify_breakout(self):
        f = WindowFeatures(burstiness=3.0, bridge_ratio=0.2)
        phase, _ = classify_phase(f)
        assert phase == "breakout"

    def test_classify_saturation(self):
        f = WindowFeatures(burstiness=1.0, cross_cluster_spread=5)
        phase, _ = classify_phase(f)
        assert phase == "saturation"

    def test_classify_regeneration(self):
        f = WindowFeatures(automation_entropy_delta=0.5)
        phase, _ = classify_phase(f)
        assert phase == "regeneration"

    def test_estimate_hazard(self):
        f = WindowFeatures(burstiness=2.5, bridge_ratio=0.15,
                           high_automation_ratio=0.4, coordination_density=0.2)
        hazard = estimate_hazard(f)
        assert "breakout" in hazard
        assert 0 <= hazard["breakout"] <= 1

    def test_detect_phase_integration(self):
        pack = build_evidence_pack(_mock_coord_data(), _mock_prop_data(), _mock_acct_data())
        result = detect_phase(pack)
        assert isinstance(result, PhaseResult)
        assert result.current_phase in ("seed", "synchronize", "breakout", "saturation", "regeneration")
        assert result.window_count == 1


# ===================================================================
# Test: ds_fusion
# ===================================================================

class TestDSFusion:
    def test_dempster_combine_no_conflict(self):
        m1 = {"risk": 0.6, "safe": 0.1, "uncertain": 0.3}
        m2 = {"risk": 0.5, "safe": 0.2, "uncertain": 0.3}
        combined, conflict = dempster_combine(m1, m2)
        assert conflict < 0.5
        assert abs(sum(combined.values()) - 1.0) < 0.01

    def test_dempster_combine_high_conflict(self):
        m1 = {"risk": 0.9, "safe": 0.05, "uncertain": 0.05}
        m2 = {"risk": 0.05, "safe": 0.9, "uncertain": 0.05}
        combined, conflict = dempster_combine(m1, m2)
        assert conflict > 0.5

    def test_mass_to_belief_interval(self):
        mass = {"risk": 0.6, "safe": 0.1, "uncertain": 0.3}
        bi = mass_to_belief_interval(mass)
        assert bi.belief == 0.6
        assert bi.plausibility == 0.9
        assert bi.belief <= bi.plausibility

    def test_fuse_evidence_integration(self):
        pack = build_evidence_pack(_mock_coord_data(), _mock_prop_data(), _mock_acct_data())
        phase = detect_phase(pack)
        result = fuse_evidence(pack, phase)
        assert isinstance(result, FusionResult)
        assert 0 <= result.manipulation.belief <= result.manipulation.plausibility <= 1
        assert 0 <= result.conflict_mass <= 1


# ===================================================================
# Test: disarm_scorer
# ===================================================================

class TestDisarmScorer:
    def _get_fusion_result(self):
        from app.core.review.ds_fusion import BeliefInterval
        return FusionResult(
            manipulation=BeliefInterval(belief=0.7, plausibility=0.9),
            authenticity=BeliefInterval(belief=0.6, plausibility=0.8),
            impact=BeliefInterval(belief=0.5, plausibility=0.7),
        )

    def test_map_evidence_to_techniques(self):
        pack = build_evidence_pack(_mock_coord_data(), _mock_prop_data(), _mock_acct_data())
        fusion = self._get_fusion_result()
        observed = map_evidence_to_techniques(pack, fusion)
        assert len(observed) > 0
        assert any(t.technique_id == "T0105" for t in observed)

    def test_score_attack_path(self):
        pack = build_evidence_pack(_mock_coord_data(), _mock_prop_data(), _mock_acct_data())
        fusion = self._get_fusion_result()
        observed = map_evidence_to_techniques(pack, fusion)
        path = score_attack_path(observed)
        assert path.depth >= 1
        assert path.breadth >= 1
        assert 0 <= path.score <= 100

    def test_predict_next(self):
        pack = build_evidence_pack(_mock_coord_data(), _mock_prop_data(), _mock_acct_data())
        fusion = self._get_fusion_result()
        observed = map_evidence_to_techniques(pack, fusion)
        predicted = predict_next_techniques(observed)
        assert isinstance(predicted, list)
        for p in predicted:
            assert 0 <= p.probability <= 1

    def test_countermeasures(self):
        pack = build_evidence_pack(_mock_coord_data(), _mock_prop_data(), _mock_acct_data())
        fusion = self._get_fusion_result()
        observed = map_evidence_to_techniques(pack, fusion)
        predicted = predict_next_techniques(observed)
        cms = recommend_countermeasures(predicted, observed)
        assert isinstance(cms, list)

    def test_full_pipeline(self):
        pack = build_evidence_pack(_mock_coord_data(), _mock_prop_data(), _mock_acct_data())
        phase = detect_phase(pack)
        fusion = fuse_evidence(pack, phase)
        result = score_attack_path_full(pack, phase, fusion)
        assert len(result.observed_techniques) > 0
        assert result.path_score.score >= 0


# ===================================================================
# Test: report_builder
# ===================================================================

class TestReportBuilder:
    def test_build_report(self):
        pack = build_evidence_pack(_mock_coord_data(), _mock_prop_data(), _mock_acct_data())
        phase = detect_phase(pack)
        fusion = fuse_evidence(pack, phase)
        disarm = score_attack_path_full(pack, phase, fusion)
        post_semantics = assess_post_semantics(
            _mock_posts_for_semantics(),
            _mock_prop_data(),
            prefer_embeddings=False,
        )
        review_harmfulness = assess_layered_harmfulness(
            post_semantics=post_semantics,
            account_profiles=_mock_acct_data(),
            coordination=_mock_coord_data(),
            propagation=_mock_prop_data(),
            event_id="test_event",
            platform="mock_weibo",
        )

        report = build_report(
            event_id="test_event",
            platform="mock_weibo",
            evidence_pack=pack,
            phase_result=phase,
            fusion_result=fusion,
            disarm_result=disarm,
            post_semantics=post_semantics,
            review_harmfulness=review_harmfulness,
        )

        # 验证报告结构
        assert "report_id" in report
        assert report["event_id"] == "test_event"
        assert report["platform"] == "mock_weibo"

        # 验证阶段
        assert report["phase"]["current_phase"] in ("seed", "synchronize", "breakout", "saturation", "regeneration")

        # 验证评分
        scores = report["scores"]
        assert 0 <= scores["overall_risk_score"] <= 100
        assert scores["risk_level"] in ("low", "medium", "high", "critical")
        assert scores["manipulation"]["belief"] <= scores["manipulation"]["plausibility"]

        # 验证融合
        assert 0 <= report["fusion"]["conflict_mass"] <= 1

        # 验证 DISARM
        da = report["disarm_analysis"]
        assert len(da["observed_techniques"]) > 0
        assert da["attack_path"]["depth"] >= 1

        # 验证风险因子
        assert "manipulation_factors" in report["risk_factors"]

        # 验证建议
        assert isinstance(report["recommendations"], list)
        assert report["post_semantics"]["summary"]["available_claims"] >= 1
        assert report["review_harmfulness"]["user_level"]["summary"]["account_count"] >= 1
        assert report["review_harmfulness"]["community_level"]["summary"]["community_count"] >= 1
        assert report["review_harmfulness"]["global_summary"]["review_harm_risk_level"] in {
            "low",
            "medium",
            "high",
        }


class TestPostSemantics:
    def test_normalize_multimodal_post(self):
        normalized = normalize_multimodal_post(_mock_posts_for_semantics()[0])
        assert normalized.text
        assert "ocr" in normalized.modalities
        assert "media" in normalized.modalities
        assert normalized.semantic_text

    def test_build_claim_candidates(self):
        claims = build_claim_candidates(_mock_prop_data())
        assert len(claims) == 2
        assert claims[0].claim_id in {"url1", "url2"}
        assert claims[0].claim_text

    def test_assess_post_semantics(self):
        result = assess_post_semantics(
            _mock_posts_for_semantics(),
            _mock_prop_data(),
            prefer_embeddings=False,
        )
        assert result["analysis_scope"]["normalized_posts"] == 2
        assert result["summary"]["linked_posts"] >= 1
        assert len(result["posts"]) >= 1
        assert len(result["aggregation_posts"]) == 2

        first_post = result["posts"][0]
        assert "harmfulness" in first_post
        assert "stance" in first_post
        assert "modalities" in first_post
        assert "multimodal_detection" in first_post
        assert first_post["multimodal_detection"]["fusion_method"] == "modality-aware-late-fusion"
        assert first_post["multimodal_detection"]["capability_boundary"]["trained_multimodal_model"] is False
        assert first_post["multimodal_detection"]["capability_boundary"]["true_image_encoder"] is False
        assert set(first_post["multimodal_detection"]["evidence_modalities"]) & {
            "text",
            "ocr",
            "asr",
            "caption_media",
        }

        view_detection = first_post["post_view_detection"]
        assert view_detection["schema_version"] == "review-post-view-detection-v1"
        assert set(view_detection["view_results"]) == {"tweet", "meme", "img", "video"}
        assert view_detection["fusion"]["majority_vote"]["label"] in {
            "harmful",
            "non_harmful",
            "uncertain",
        }
        assert view_detection["fusion"]["weighted_fusion"]["label"] in {
            "harmful",
            "non_harmful",
            "uncertain",
        }
        assert view_detection["fusion_policy"] in {
            "majority_vote_confirmed_by_weighted_fusion",
            "majority_vote",
            "weighted_fusion_fallback",
        }
        assert view_detection["capability_boundary"]["majority_vote"] is True
        assert view_detection["capability_boundary"]["trained_view_detectors"] is False

    def test_post_view_detection_majority_and_fusion_use_effective_views(self):
        result = assess_post_semantics(
            _mock_posts_for_semantics(),
            _mock_prop_data(),
            prefer_embeddings=False,
        )

        view_detection = result["aggregation_posts"][0]["post_view_detection"]
        view_results = view_detection["view_results"]
        eligible = {
            name: view
            for name, view in view_results.items()
            if view["available"] and not view["abstain"] and view["label"] in {"harmful", "non_harmful"}
        }
        abstained = {
            name
            for name, view in view_results.items()
            if not view["available"] or view["abstain"]
        }

        majority_vote = view_detection["fusion"]["majority_vote"]
        harmful_votes = sum(1 for view in eligible.values() if view["label"] == "harmful")
        non_harmful_votes = sum(1 for view in eligible.values() if view["label"] == "non_harmful")
        if not eligible:
            expected_majority_label = "uncertain"
        elif harmful_votes > len(eligible) / 2:
            expected_majority_label = "harmful"
        elif non_harmful_votes > len(eligible) / 2:
            expected_majority_label = "non_harmful"
        else:
            expected_majority_label = "uncertain"

        assert set(majority_vote["eligible_views"]) == set(eligible)
        assert set(majority_vote["abstained_views"]) == abstained
        assert majority_vote["vote_counts"].get("harmful", 0) == harmful_votes
        assert majority_vote["vote_counts"].get("non_harmful", 0) == non_harmful_votes
        assert majority_vote["label"] == expected_majority_label

        weighted_fusion = view_detection["fusion"]["weighted_fusion"]
        weighted_contributors = {
            item["view"]
            for item in weighted_fusion["contributors"]
        }
        expected_contributors = {
            name
            for name, view in eligible.items()
            if float(view.get("confidence") or 0.0) > 0.0
        }
        assert weighted_contributors == expected_contributors
        assert weighted_contributors.isdisjoint(abstained)

        if majority_vote["label"] == weighted_fusion["label"] and majority_vote["label"] != "uncertain":
            expected_final = majority_vote["label"]
            expected_policy = "majority_vote_confirmed_by_weighted_fusion"
        elif majority_vote["label"] != "uncertain":
            expected_final = majority_vote["label"]
            expected_policy = "majority_vote"
        else:
            expected_final = weighted_fusion["label"]
            expected_policy = "weighted_fusion_fallback"

        assert view_detection["final_harmfulness"] == expected_final
        assert view_detection["fusion_policy"] == expected_policy

    def test_post_view_detection_abstains_missing_video_view(self):
        result = assess_post_semantics(
            [_mock_posts_for_semantics()[0]],
            _mock_prop_data(),
            prefer_embeddings=False,
        )

        view_detection = result["aggregation_posts"][0]["post_view_detection"]
        assert view_detection["view_results"]["tweet"]["available"] is True
        assert view_detection["view_results"]["meme"]["available"] is True
        assert view_detection["view_results"]["video"]["available"] is False
        assert "video" in view_detection["fusion"]["majority_vote"]["abstained_views"]
        assert any(reason.startswith("view_unavailable") for reason in view_detection["review_reason"])

    def test_post_view_detection_excludes_image_url_without_decodable_content(self):
        post = {
            "post_id": "p_image_url_only",
            "author_id": "u_image",
            "author_name": "image_only",
            "platform": "mock_weibo",
            "event_id": "test_event",
            "content": "大家快转这个 url1，真相终于曝光了",
            "hashtags": ["#曝光"],
            "media_urls": ["https://cdn.example.com/image.jpg"],
            "raw_data": {},
        }

        result = assess_post_semantics([post], _mock_prop_data(), prefer_embeddings=False)

        view_detection = result["aggregation_posts"][0]["post_view_detection"]
        meme_view = view_detection["view_results"]["meme"]
        img_view = view_detection["view_results"]["img"]
        weighted_contributors = view_detection["fusion"]["weighted_fusion"]["contributors"]
        assert meme_view["available"] is False
        assert meme_view["abstain"] is True
        assert meme_view["reason"] == "media_without_decodable_content"
        assert img_view["available"] is False
        assert img_view["abstain"] is True
        assert img_view["reason"] == "media_without_decodable_content"
        assert {"meme", "img"}.issubset(set(view_detection["fusion"]["majority_vote"]["abstained_views"]))
        assert all(item["view"] not in {"meme", "img"} for item in weighted_contributors)

    def test_post_view_detection_excludes_video_url_without_decodable_content(self):
        post = {
            "post_id": "p_video_url_only",
            "author_id": "u_video",
            "author_name": "video_only",
            "platform": "mock_weibo",
            "event_id": "test_event",
            "content": "大家快转这个 url1，真相终于曝光了",
            "hashtags": ["#曝光"],
            "media_urls": ["https://cdn.example.com/clip.mp4"],
            "raw_data": {},
        }

        result = assess_post_semantics([post], _mock_prop_data(), prefer_embeddings=False)

        view_detection = result["aggregation_posts"][0]["post_view_detection"]
        video_view = view_detection["view_results"]["video"]
        weighted_contributors = view_detection["fusion"]["weighted_fusion"]["contributors"]
        assert video_view["available"] is False
        assert video_view["abstain"] is True
        assert video_view["reason"] == "media_without_decodable_content"
        assert "video" in view_detection["fusion"]["majority_vote"]["abstained_views"]
        assert all(item["view"] != "video" for item in weighted_contributors)


class TestReviewPostValidationScripts:
    def test_multiview_suite_reports_expected_view_coverage(self):
        suite = _load_script_module("run_review_post_multiview_ablation")
        multioff_report = {
            "dataset": "MultiOFF",
            "experiments": {
                "text_only": {"status": "evaluated"},
                "image_only": {"status": "evaluated"},
                "majority_vote": {"status": "evaluated"},
                "late_fusion": {"status": "evaluated"},
                "learned_fusion": {"status": "evaluated"},
            },
        }
        pheme_report = {
            "dataset": "PHEME",
            "experiments": {
                "text_only": {"status": "evaluated"},
                "claim_context_only": {"status": "evaluated"},
                "claim_context_late_fusion": {"status": "evaluated"},
            },
        }
        fakesv_report = {
            "dataset": "FakeSV",
            "experiments": {
                "text_only": {"status": "evaluated"},
                "image_only": {"status": "skipped"},
                "video_feature_only": {"status": "skipped"},
                "majority_vote": {"status": "skipped"},
                "late_fusion": {"status": "skipped"},
                "learned_fusion": {"status": "skipped"},
            },
        }
        fakesv_video_report = {
            "dataset": "FakeSV",
            "experiments": {
                "text_only": {"status": "evaluated"},
                "video_feature_only": {"status": "evaluated"},
                "video_text_late_fusion": {"status": "evaluated"},
                "majority_vote": {"status": "evaluated"},
                "late_fusion": {"status": "evaluated"},
            },
        }

        multioff_coverage = suite.build_validation_coverage("MultiOFF", multioff_report)
        pheme_coverage = suite.build_validation_coverage("PHEME", pheme_report)
        fakesv_coverage = suite.build_validation_coverage("FakeSV", fakesv_report)
        fakesv_video_coverage = suite.build_validation_coverage("FakeSV", fakesv_video_report)

        assert multioff_coverage["full_expected_view_coverage"] is True
        assert multioff_coverage["majority_vote_evaluated"] is True
        assert multioff_coverage["weighted_fusion_evaluated"] is True
        assert pheme_coverage["claim_evidence_view_evaluated"] is True
        assert pheme_coverage["claim_view_evaluated"] is True
        assert pheme_coverage["evidence_view_required"] is False
        assert pheme_coverage["claim_context_metadata_baseline"] is True
        assert pheme_coverage["full_expected_view_coverage"] is True
        mocheg_coverage = suite.build_validation_coverage("MOCHEG", pheme_report)
        assert mocheg_coverage["claim_view_evaluated"] is True
        assert mocheg_coverage["evidence_view_required"] is True
        assert mocheg_coverage["full_expected_view_coverage"] is False
        assert "evidence_view_not_evaluated" in mocheg_coverage["missing_requirements"]
        assert fakesv_coverage["video_view_required"] is True
        assert fakesv_coverage["video_metadata_proxy_only"] is True
        assert fakesv_coverage["full_expected_view_coverage"] is False
        assert "true_video_view_not_evaluated" in fakesv_coverage["missing_requirements"]
        assert fakesv_video_coverage["true_video_view_evaluated"] is True
        assert fakesv_video_coverage["video_metadata_proxy_only"] is False
        assert fakesv_video_coverage["preextracted_video_feature_baseline"] is True
        assert fakesv_video_coverage["full_expected_view_coverage"] is True

    def test_claim_context_text_uses_claim_and_evidence_metadata(self):
        suite = _load_script_module("run_review_post_multiview_ablation")
        case = {
            "claim_context": {
                "claim_text": "A claim about an event",
                "evidence_text": "Short evidence summary",
                "evidence_links": [
                    {
                        "link": "https://example.org/story",
                        "mediatype": "news-media",
                        "position": "for",
                    }
                ],
            }
        }

        text = suite.claim_context_text(case)

        assert "A claim about an event" in text
        assert "Short evidence summary" in text
        assert "news-media" in text
        assert "example.org" in text

    def test_full_validation_gate_requires_expected_view_coverage(self):
        gate = _load_script_module("summarize_review_full_validation")
        ready_row = {
            "audit_status": "ready",
            "conversion_status": "converted",
            "case_count": 10,
            "suite_status": "evaluated",
            "best_test_macro_f1": {"experiment": "text_only", "macro_f1": 0.8},
            "validation_coverage": {
                "full_expected_view_coverage": True,
                "missing_requirements": [],
            },
        }
        text_only_multimodal_row = {
            **ready_row,
            "validation_coverage": {
                "full_expected_view_coverage": False,
                "missing_requirements": ["image_or_meme_view_not_evaluated"],
            },
        }

        assert gate.dataset_passes(ready_row) is True
        assert gate.dataset_passes(text_only_multimodal_row) is False
        blocker = gate.dataset_blocker({"dataset": "Hateful Memes", **text_only_multimodal_row})
        assert "image_or_meme_view_not_evaluated" in blocker["reasons"]


class TestReviewPostGate:
    def test_evaluate_post_gate_reports_metrics_and_boundaries(self):
        cases = [
            {
                "case_id": "post_gate_fixture",
                "posts": _mock_posts_for_semantics(),
                "propagation": _mock_prop_data(),
                "gold": {
                    "p1": {
                        "claim_id": "url1",
                        "stance": "support",
                        "harm_label": "harmful",
                        "harm_types": ["misinformation", "manipulative_amplification"],
                        "must_have_modalities": ["text", "ocr", "media"],
                    },
                    "p2": {
                        "claim_id": "url1",
                        "stance": "deny",
                        "harm_label": "non_harmful",
                        "harm_types": [],
                        "must_have_modalities": ["text", "asr"],
                    },
                },
            }
        ]

        report = evaluate_post_gate(cases, prefer_embeddings=False)

        assert report["capability_boundary"]["status"] == "implemented_post_gate_evaluation_harness"
        assert report["capability_boundary"]["evaluation_harness_only"] is True
        assert report["capability_boundary"]["trained_model"] is False
        assert report["capability_boundary"]["uses_gold_for_training"] is False
        assert report["capability_boundary"]["live_llm_or_rag"] is False
        assert report["summary"]["evaluated_posts"] == 2
        assert report["summary"]["evaluated_from"] == "aggregation_posts"
        assert report["semantic_scopes"][0]["aggregation_posts"] == 2
        assert report["semantic_scopes"][0]["representative_posts"] == 2
        assert set(report["metrics"]).issuperset(
            {
                "claim_link_accuracy",
                "stance_accuracy",
                "harm_label_accuracy",
                "harm_type_micro_precision",
                "harm_type_micro_recall",
                "harm_type_micro_f1",
                "evidence_presence_rate",
                "abstain_rate",
            }
        )
        assert report["metrics"]["claim_link_accuracy"] == 1.0
        assert report["metrics"]["evidence_presence_rate"] == 1.0
        assert report["metrics"]["abstain_rate"] == 1.0
        assert report["metrics"]["stance_accuracy"] == 0.0
        assert report["metrics"]["harm_label_accuracy"] == 0.5
        assert report["threshold_status"]["stance_accuracy"]["passed"] is False
        assert len(report["case_results"][0]["post_results"]) == 2

    def test_evaluate_post_gate_routes_failures_to_planned_review_queue(self):
        cases = [
            {
                "case_id": "post_gate_failures",
                "posts": _mock_posts_for_semantics(),
                "propagation": _mock_prop_data(),
                "gold": {
                    "p1": {
                        "claim_id": "url1",
                        "stance": "support",
                        "harm_label": "harmful",
                        "harm_types": ["misinformation"],
                    },
                    "p2": {
                        "claim_id": "url1",
                        "stance": "deny",
                        "harm_label": "non_harmful",
                        "harm_types": [],
                    },
                },
            }
        ]

        report = evaluate_post_gate(cases, prefer_embeddings=False)
        queue = report["review_queue"]

        assert report["summary"]["failed_posts"] >= 1
        assert queue["capability_boundary"]["status"] == "implemented_post_gate_failure_review_queue"
        assert queue["capability_boundary"]["evaluation_harness_only"] is True
        assert queue["capability_boundary"]["live_llm_or_rag"] is False
        assert queue["summary"]["review_items"] == report["summary"]["failed_posts"]
        assert queue["summary"]["agent_tasks"] == 1
        assert all(item["type"] == "post_gate_failure_review" for item in queue["review_items"])
        assert all(item["execution_status"] == "planned_only" for item in queue["review_items"])
        assert all(item["requires_external_execution"] is True for item in queue["review_items"])
        assert any(item["priority"] == "high" for item in queue["review_items"])
        assert all(task["execution_status"] == "planned_only" for task in queue["agent_tasks"])
        assert all("gold" in item["evidence"] and "predicted" in item["evidence"] for item in queue["review_items"])
        assert any(
            "stance_mismatch" in item["reason"] or "harm_label_mismatch" in item["reason"]
            for item in queue["review_items"]
        )


def _mock_user_gate_accounts():
    return [
        {
            "account_id": "u_harmful",
            "author_name": "harmful_user",
            "risk_summary": {
                "input_posts": 4,
                "linked_posts": 4,
                "harmful_posts": 3,
                "harmful_ratio": 0.75,
                "avg_harm_score": 0.72,
                "persistence_score": 0.78,
                "trajectory": "stable",
                "harm_types": {"misinformation": 3},
            },
            "role_profile": {
                "propagation_roles": ["amplifier"],
                "harmful_roles": ["amplifier", "attention_shaper"],
            },
            "risk_profile_flags": {
                "high_harmful": True,
                "needs_review": False,
            },
            "representative_posts": [
                {
                    "post_id": "hp1",
                    "excerpt": "harmful evidence",
                    "harm_label": "harmful",
                    "harm_score": 0.8,
                }
            ],
            "top_claims": [{"claim_id": "url1", "linked_posts": 4, "harmful_posts": 3}],
        },
        {
            "account_id": "u_uncertain",
            "author_name": "uncertain_user",
            "risk_summary": {
                "input_posts": 1,
                "linked_posts": 1,
                "harmful_posts": 0,
                "harmful_ratio": 0.0,
                "avg_harm_score": 0.0,
                "persistence_score": 0.2,
                "trajectory": "insufficient_temporal_evidence",
                "harm_types": {},
            },
            "role_profile": {
                "propagation_roles": ["participant"],
                "harmful_roles": ["participant"],
            },
            "risk_profile_flags": {
                "high_harmful": False,
                "needs_review": True,
            },
            "representative_posts": [],
            "top_claims": [],
        },
    ]


class TestReviewUserGate:
    def test_evaluate_user_gate_reports_metrics_and_boundaries(self):
        gold = {
            "u_harmful": {
                "harmful": True,
                "persistence_label": "high",
                "trajectory": "stable",
                "roles": ["amplifier", "attention_shaper"],
            },
            "u_uncertain": {
                "harmful": False,
                "persistence_label": "low",
                "trajectory": "insufficient_temporal_evidence",
                "roles": ["participant"],
                "needs_representative_evidence": False,
            },
        }

        report = evaluate_user_gate(accounts=_mock_user_gate_accounts(), gold=gold)

        assert report["capability_boundary"]["status"] == "implemented_user_gate_evaluation_harness"
        assert report["capability_boundary"]["evaluation_harness_only"] is True
        assert report["capability_boundary"]["trained_user_encoder"] is False
        assert report["capability_boundary"]["trained_mil_or_temporal_model"] is False
        assert report["capability_boundary"]["uses_gold_for_training"] is False
        assert report["capability_boundary"]["live_llm_or_rag"] is False
        assert report["summary"]["evaluated_from"] == "review_harmfulness.user_level.accounts"
        assert report["summary"]["evaluated_accounts"] == 2
        assert report["metrics"]["harmful_flag_accuracy"] == 1.0
        assert report["metrics"]["persistence_label_accuracy"] == 1.0
        assert report["metrics"]["trajectory_accuracy"] == 1.0
        assert report["metrics"]["role_micro_f1"] == 1.0
        assert report["metrics"]["representative_evidence_rate"] == 1.0
        assert report["metrics"]["runtime_needs_review_rate"] == 0.5
        assert report["threshold_status"]["role_micro_f1"]["passed"] is True

    def test_evaluate_user_gate_routes_failures_to_planned_review_queue(self):
        gold = {
            "u_harmful": {
                "harmful": True,
                "persistence_label": "high",
                "trajectory": "stable",
                "roles": ["amplifier", "attention_shaper"],
            },
            "u_uncertain": {
                "harmful": True,
                "persistence_label": "medium",
                "trajectory": "escalating",
                "roles": ["mobilizer"],
            },
        }

        report = evaluate_user_gate(accounts=_mock_user_gate_accounts(), gold=gold)
        queue = report["review_queue"]

        assert report["summary"]["failed_accounts"] == 1
        assert report["threshold_status"]["harmful_flag_accuracy"]["passed"] is False
        assert queue["capability_boundary"]["status"] == "implemented_user_gate_failure_review_queue"
        assert queue["capability_boundary"]["evaluation_harness_only"] is True
        assert queue["capability_boundary"]["live_llm_or_rag"] is False
        assert queue["summary"]["review_items"] == 1
        assert queue["summary"]["agent_tasks"] == 1
        item = queue["review_items"][0]
        assert item["type"] == "user_gate_failure_review"
        assert item["execution_status"] == "planned_only"
        assert item["requires_external_execution"] is True
        assert item["priority"] == "high"
        assert "harmful_flag_mismatch" in item["reason"]
        assert "role_mismatch" in item["reason"]
        assert "gold" in item["evidence"] and "predicted" in item["evidence"]
        assert queue["agent_tasks"][0]["execution_status"] == "planned_only"


def _mock_community_gate_communities():
    return [
        {
            "community_id": "c_harmful",
            "member_count": 6,
            "coord_edge_count": 8,
            "coord_density": 0.42,
            "risk_summary": {
                "semantic_posts": 8,
                "harmful_posts": 5,
                "harmful_ratio": 0.625,
                "harmful_accounts": 3,
                "dominant_harm_types": {
                    "misinformation": 4,
                    "manipulative_amplification": 3,
                },
                "stance_distribution": {"support": 5, "deny": 1},
                "amplification_score": 0.71,
            },
            "subgroup_roles": {
                "amplifier": 2,
                "attention_shaper": 2,
                "originator": 1,
            },
            "claims_coverage": [
                {
                    "claim_id": "url1",
                    "claim_text": "misleading claim",
                    "linked_posts": 6,
                    "harmful_posts": 5,
                    "linked_accounts": 3,
                }
            ],
            "key_accounts": [
                {
                    "account_id": "u_harmful",
                    "author_name": "harmful_user",
                    "harmful_posts": 3,
                    "roles": ["amplifier", "attention_shaper"],
                }
            ],
            "risk_flags": {
                "high_collective_harm": True,
                "coordinated_harm_amplification": True,
                "needs_review": False,
            },
        },
        {
            "community_id": "c_benign",
            "member_count": 3,
            "coord_edge_count": 1,
            "coord_density": 0.05,
            "risk_summary": {
                "semantic_posts": 3,
                "harmful_posts": 0,
                "harmful_ratio": 0.0,
                "harmful_accounts": 0,
                "dominant_harm_types": {},
                "stance_distribution": {"deny": 2, "neutral": 1},
                "amplification_score": 0.12,
            },
            "subgroup_roles": {"participant": 3},
            "claims_coverage": [],
            "key_accounts": [],
            "risk_flags": {
                "high_collective_harm": False,
                "coordinated_harm_amplification": False,
                "needs_review": False,
            },
        },
    ]


def _mock_community_gate_graph_export():
    return {
        "capability_boundary": {
            "status": "implemented_graph_export_schema",
            "trained_graph_model": False,
        },
        "schema": {
            "node_types": ["account", "post", "claim", "community", "target", "media"],
            "edge_types": [
                "authored",
                "mentions_claim",
                "member_of",
                "community_focuses_claim",
                "community_targets",
            ],
        },
        "summary": {
            "node_count": 6,
            "edge_count": 5,
            "graph_native_ready": True,
        },
        "nodes": [
            {"id": "community:c_harmful", "type": "community", "attrs": {}},
            {"id": "account:u_harmful", "type": "account", "attrs": {}},
            {"id": "post:p1", "type": "post", "attrs": {}},
            {"id": "claim:url1", "type": "claim", "attrs": {}},
            {"id": "target:health_agency", "type": "target", "attrs": {}},
            {"id": "media:https%3A%2F%2Fcdn.example.com%2Fimage1.jpg", "type": "media", "attrs": {}},
        ],
        "edges": [
            {
                "id": "member_of:account:u_harmful->community:c_harmful",
                "source": "account:u_harmful",
                "target": "community:c_harmful",
                "type": "member_of",
                "attrs": {},
            },
            {
                "id": "authored:account:u_harmful->post:p1",
                "source": "account:u_harmful",
                "target": "post:p1",
                "type": "authored",
                "attrs": {},
            },
            {
                "id": "mentions_claim:post:p1->claim:url1",
                "source": "post:p1",
                "target": "claim:url1",
                "type": "mentions_claim",
                "attrs": {},
            },
            {
                "id": "community_focuses_claim:community:c_harmful->claim:url1",
                "source": "community:c_harmful",
                "target": "claim:url1",
                "type": "community_focuses_claim",
                "attrs": {},
            },
            {
                "id": "community_targets:community:c_harmful->target:health_agency",
                "source": "community:c_harmful",
                "target": "target:health_agency",
                "type": "community_targets",
                "attrs": {},
            },
        ],
    }


class TestReviewCommunityGate:
    def test_evaluate_community_gate_reports_metrics_boundaries_and_graph_audit(self):
        gold = {
            "c_harmful": {
                "collective_harm": True,
                "amplification": True,
                "harm_types": ["misinformation", "manipulative_amplification"],
                "roles": ["amplifier", "attention_shaper", "originator"],
                "claims": ["url1"],
                "key_accounts": ["u_harmful"],
            },
            "c_benign": {
                "collective_harm": False,
                "amplification": False,
                "harm_types": [],
                "roles": ["participant"],
                "needs_claim_coverage": False,
                "needs_key_account_evidence": False,
            },
        }

        report = evaluate_community_gate(
            communities=_mock_community_gate_communities(),
            graph_export=_mock_community_gate_graph_export(),
            gold=gold,
        )

        assert report["capability_boundary"]["status"] == "implemented_community_gate_evaluation_harness"
        assert report["capability_boundary"]["evaluation_harness_only"] is True
        assert report["capability_boundary"]["trained_graph_model"] is False
        assert report["capability_boundary"]["trained_hgt_or_tgn"] is False
        assert report["capability_boundary"]["uses_gold_for_training"] is False
        assert report["capability_boundary"]["live_llm_or_rag"] is False
        assert report["summary"]["evaluated_from"] == "review_harmfulness.community_level.communities"
        assert report["summary"]["evaluated_communities"] == 2
        assert report["metrics"]["collective_harm_accuracy"] == 1.0
        assert report["metrics"]["amplification_label_accuracy"] == 1.0
        assert report["metrics"]["harm_type_micro_f1"] == 1.0
        assert report["metrics"]["role_micro_f1"] == 1.0
        assert report["metrics"]["claim_coverage_rate"] == 1.0
        assert report["metrics"]["key_account_evidence_rate"] == 1.0
        assert report["metrics"]["graph_export_ready_rate"] == 1.0
        assert report["graph_audit"]["graph_export_ready"] is True
        assert report["graph_audit"]["trained_graph_model"] is False
        assert report["threshold_status"]["role_micro_f1"]["passed"] is True

    def test_evaluate_community_gate_routes_failures_to_planned_review_queue(self):
        gold = {
            "c_harmful": {
                "collective_harm": True,
                "amplification": True,
                "harm_types": ["misinformation", "manipulative_amplification"],
                "roles": ["amplifier", "attention_shaper"],
                "claims": ["url1"],
                "key_accounts": ["u_harmful"],
            },
            "c_benign": {
                "collective_harm": True,
                "amplification": True,
                "harm_types": ["incitement_mobilization"],
                "roles": ["mobilizer"],
                "claims": ["url2"],
                "key_accounts": ["u_missing"],
            },
        }

        report = evaluate_community_gate(
            communities=_mock_community_gate_communities(),
            gold=gold,
        )
        queue = report["review_queue"]

        assert report["summary"]["failed_communities"] == 1
        assert report["threshold_status"]["collective_harm_accuracy"]["passed"] is False
        assert queue["capability_boundary"]["status"] == "implemented_community_gate_failure_review_queue"
        assert queue["capability_boundary"]["evaluation_harness_only"] is True
        assert queue["capability_boundary"]["trained_graph_model"] is False
        assert queue["capability_boundary"]["live_llm_or_rag"] is False
        assert queue["summary"]["review_items"] == 1
        assert queue["summary"]["agent_tasks"] == 1
        item = queue["review_items"][0]
        assert item["type"] == "community_gate_failure_review"
        assert item["agent_role"] == "CommunityJudge"
        assert item["execution_status"] == "planned_only"
        assert item["requires_external_execution"] is True
        assert item["priority"] == "high"
        assert "collective_harm_mismatch" in item["reason"]
        assert "harm_type_mismatch" in item["reason"]
        assert "role_mismatch" in item["reason"]
        assert "gold" in item["evidence"] and "predicted" in item["evidence"]
        assert queue["agent_tasks"][0]["agent"] == "CommunityJudge"
        assert queue["agent_tasks"][0]["execution_status"] == "planned_only"


class TestReviewGateSuite:
    def test_evaluate_gate_suite_composes_layered_gates(self):
        post_cases = [
            {
                "case_id": "suite_post_gate",
                "posts": _mock_posts_for_semantics(),
                "propagation": _mock_prop_data(),
                "gold": {
                    "p1": {
                        "claim_id": "url1",
                        "stance": "support",
                        "harm_label": "harmful",
                        "harm_types": ["misinformation", "manipulative_amplification"],
                        "must_have_modalities": ["text", "ocr", "media"],
                    },
                    "p2": {
                        "claim_id": "url1",
                        "stance": "deny",
                        "harm_label": "non_harmful",
                        "harm_types": [],
                        "must_have_modalities": ["text", "asr"],
                    },
                },
            }
        ]
        review_harmfulness = {
            "user_level": {"accounts": _mock_user_gate_accounts()},
            "community_level": {"communities": _mock_community_gate_communities()},
        }
        user_gold = {
            "u_harmful": {
                "harmful": True,
                "persistence_label": "high",
                "trajectory": "stable",
                "roles": ["amplifier", "attention_shaper"],
            },
            "u_uncertain": {
                "harmful": False,
                "persistence_label": "low",
                "trajectory": "insufficient_temporal_evidence",
                "roles": ["participant"],
                "needs_representative_evidence": False,
            },
        }
        community_gold = {
            "c_harmful": {
                "collective_harm": True,
                "amplification": True,
                "harm_types": ["misinformation", "manipulative_amplification"],
                "roles": ["amplifier", "attention_shaper", "originator"],
                "claims": ["url1"],
                "key_accounts": ["u_harmful"],
            },
            "c_benign": {
                "collective_harm": False,
                "amplification": False,
                "harm_types": [],
                "roles": ["participant"],
                "needs_claim_coverage": False,
                "needs_key_account_evidence": False,
            },
        }

        report = evaluate_gate_suite(
            post_cases=post_cases,
            review_harmfulness=review_harmfulness,
            user_gold=user_gold,
            community_gold=community_gold,
            graph_export=_mock_community_gate_graph_export(),
            prefer_embeddings=False,
        )

        assert report["capability_boundary"]["status"] == "implemented_review_layered_gate_suite"
        assert report["capability_boundary"]["evaluation_harness_only"] is True
        assert report["capability_boundary"]["trained_post_model"] is False
        assert report["capability_boundary"]["trained_user_encoder"] is False
        assert report["capability_boundary"]["trained_graph_model"] is False
        assert report["capability_boundary"]["uses_gold_for_training"] is False
        assert report["capability_boundary"]["live_llm_or_rag"] is False
        assert report["summary"]["executed_gates"] == 3
        assert report["summary"]["skipped_gates"] == 0
        assert set(report["summary"]["gate_names"]) == {"community_gate", "post_gate", "user_gate"}
        assert set(report["gates"]) == {"community_gate", "post_gate", "user_gate"}
        assert report["summary"]["gate_status"]["post_gate"]["failed_items"] >= 1
        assert "stance_accuracy" in report["summary"]["gate_status"]["post_gate"]["failed_thresholds"]
        assert report["summary"]["gate_status"]["user_gate"]["overall_pass"] is True
        assert report["summary"]["gate_status"]["community_gate"]["overall_pass"] is True
        assert report["summary"]["review_items"] >= report["summary"]["failed_items"]

    def test_evaluate_gate_suite_accepts_dataset_contract(self):
        dataset = {
            "metadata": {
                "dataset_id": "review-fixed-smoke",
                "version": "v1",
                "source": "unit_fixture",
                "label_policy": "fixed labels are used only for offline evaluation",
                "control_set_notes": "contains one post case and account/community controls",
            },
            "prefer_embeddings": False,
            "post_cases": [
                {
                    "case_id": "suite_dataset_post_gate",
                    "posts": _mock_posts_for_semantics(),
                    "propagation": _mock_prop_data(),
                    "gold": {
                        "p1": {
                            "claim_id": "url1",
                            "stance": "support",
                            "harm_label": "harmful",
                            "harm_types": ["misinformation", "manipulative_amplification"],
                            "must_have_modalities": ["text", "ocr", "media"],
                        },
                        "p2": {
                            "claim_id": "url1",
                            "stance": "deny",
                            "harm_label": "non_harmful",
                            "harm_types": [],
                            "must_have_modalities": ["text", "asr"],
                        },
                    },
                }
            ],
            "user_gold": {
                "u_harmful": {
                    "harmful": True,
                    "persistence_label": "high",
                    "trajectory": "stable",
                    "roles": ["amplifier", "attention_shaper"],
                },
                "u_uncertain": {
                    "harmful": False,
                    "persistence_label": "low",
                    "trajectory": "insufficient_temporal_evidence",
                    "roles": ["participant"],
                    "needs_representative_evidence": False,
                },
            },
            "community_gold": {
                "c_harmful": {
                    "collective_harm": True,
                    "amplification": True,
                    "harm_types": ["misinformation", "manipulative_amplification"],
                    "roles": ["amplifier", "attention_shaper", "originator"],
                    "claims": ["url1"],
                    "key_accounts": ["u_harmful"],
                },
                "c_benign": {
                    "collective_harm": False,
                    "amplification": False,
                    "harm_types": [],
                    "roles": ["participant"],
                    "needs_claim_coverage": False,
                    "needs_key_account_evidence": False,
                },
            },
            "thresholds": {
                "post": {
                    "stance_accuracy": 0.0,
                    "harm_type_micro_f1": 0.0,
                }
            },
        }
        review_harmfulness = {
            "user_level": {"accounts": _mock_user_gate_accounts()},
            "community_level": {"communities": _mock_community_gate_communities()},
        }

        report = evaluate_gate_suite_from_dataset(
            dataset=dataset,
            review_harmfulness=review_harmfulness,
            graph_export=_mock_community_gate_graph_export(),
        )

        assert report["dataset_contract"]["provided"] is True
        assert report["dataset_contract"]["metadata"]["dataset_id"] == "review-fixed-smoke"
        assert report["dataset_contract"]["validation"]["valid"] is True
        assert report["dataset_contract"]["counts"] == {
            "post_cases": 1,
            "user_gold": 2,
            "community_gold": 2,
        }
        assert report["dataset_contract"]["manifest"]["contains_gold_payload"] is False
        assert report["dataset_contract"]["manifest"]["counts"] == report["dataset_contract"]["counts"]
        assert len(report["dataset_contract"]["manifest"]["dataset_fingerprint"]) == 64
        assert report["summary"]["executed_gates"] == 3
        assert report["summary"]["skipped_gates"] == 0
        assert report["capability_boundary"]["evaluation_harness_only"] is True
        assert report["capability_boundary"]["uses_gold_for_training"] is False
        assert report["gates"]["post_gate"]["thresholds"]["stance_accuracy"] == 0.0
        assert report["gates"]["post_gate"]["thresholds"]["harm_type_micro_f1"] == 0.0

    def test_evaluate_gate_suite_marks_missing_gold_as_skipped(self):
        report = evaluate_gate_suite(
            review_harmfulness={
                "user_level": {"accounts": _mock_user_gate_accounts()},
                "community_level": {"communities": _mock_community_gate_communities()},
            }
        )

        assert report["capability_boundary"]["evaluation_harness_only"] is True
        assert report["summary"]["executed_gates"] == 0
        assert report["summary"]["skipped_gates"] == 3
        assert report["summary"]["overall_pass"] is False
        assert report["dataset_contract"]["provided"] is False
        assert set(report["skipped_gates"]) == {"community_gate", "post_gate", "user_gate"}
        assert report["skipped_gates"]["post_gate"]["reason"] == "missing_post_cases"
        assert report["skipped_gates"]["user_gate"]["reason"] == "missing_user_gold"
        assert report["skipped_gates"]["community_gate"]["reason"] == "missing_community_gold"


class TestReviewGateDataset:
    def test_gate_dataset_contract_spec_is_machine_readable(self):
        contract = get_gate_dataset_contract_spec()

        assert contract["contract_version"] == "review-gate-dataset-v1"
        assert contract["artifact_type"] == "gate_dataset_contract"
        assert contract["entrypoints"]["evaluate"] == "POST /api/v1/risk/review/gate-suite"
        assert contract["usage_policy"]["uses_gold_for_training"] is False
        assert contract["usage_policy"]["runtime_gold_generation"] is False
        assert contract["usage_policy"]["default_persistence"] is False
        assert contract["leakage_policy"]["no_runtime_derived_gold"] is True
        assert contract["leakage_policy"]["control_set_required_for_formal_acceptance"] is True
        assert contract["manifest_policy"]["contains_gold_payload"] is False
        assert contract["manifest_policy"]["fingerprint_algorithm"] == "sha256-canonical-json"
        assert contract["readiness_policy"]["formal_acceptance_metadata_fields"] == [
            "control_set_notes",
            "split",
            "leakage_policy",
            "threshold_policy",
        ]
        assert contract["readiness_policy"]["required_gate_layers"] == [
            "post_gate",
            "user_gate",
            "community_gate",
        ]
        assert "readiness_missing_split" in contract["validation_warning_codes"]
        assert "readiness_missing_full_layer_coverage" in contract["validation_warning_codes"]
        assert set(contract["required_metadata_fields"]) == {
            "dataset_id",
            "version",
            "source",
            "label_policy",
            "control_set_notes",
        }
        assert set(contract["layer_contracts"]) == {"community_gate", "post_gate", "user_gate"}
        assert "claim_link_accuracy" in contract["layer_contracts"]["post_gate"]["metrics"]
        assert "role_micro_f1" in contract["layer_contracts"]["user_gate"]["default_thresholds"]
        assert "claim_coverage_rate" in contract["layer_contracts"]["community_gate"]["metrics"]
        assert contract["example_skeleton"]["contract_version"] == "review-gate-dataset-v1"

    def test_normalize_gate_dataset_reports_contract_and_counts(self):
        normalized = normalize_gate_dataset(
            {
                "metadata": {
                    "dataset_id": "dataset-contract-smoke",
                    "version": "v1",
                    "source": "unit_fixture",
                    "label_policy": "expert labels only",
                    "control_set_notes": "same-topic same-window controls",
                },
                "post_cases": [{"case_id": "c1", "posts": [], "gold": {}}],
                "user_gold": [{"account_id": "u1", "harmful": False}],
                "community_gold": {"community_1": {"collective_harm": False}},
                "thresholds": {
                    "post": {"stance_accuracy": "0.7"},
                    "user": {"role_micro_f1": 0.5},
                    "community": {"claim_coverage_rate": 1},
                },
                "prefer_embeddings": False,
            }
        )
        view = gate_dataset_contract_view(normalized)

        assert normalized["provided"] is True
        assert normalized["validation"]["valid"] is True
        assert "post_cases_0_missing_gold" in normalized["validation"]["warnings"]
        assert "readiness_missing_split" in normalized["validation"]["warnings"]
        assert "readiness_missing_leakage_policy" in normalized["validation"]["warnings"]
        assert "readiness_missing_threshold_policy" in normalized["validation"]["warnings"]
        assert "readiness_contract_warnings_present" in normalized["validation"]["warnings"]
        assert normalized["validation"]["layer_coverage"] == {
            "post_gate": True,
            "user_gate": True,
            "community_gate": True,
        }
        readiness = normalized["evaluation_readiness"]
        assert readiness["formal_acceptance_ready"] is False
        assert readiness["has_required_metadata"] is True
        assert readiness["has_control_notes"] is True
        assert readiness["has_split"] is False
        assert readiness["has_leakage_policy"] is False
        assert readiness["has_threshold_policy"] is False
        assert readiness["has_full_layer_coverage"] is True
        assert normalized["thresholds"]["post"]["stance_accuracy"] == 0.7
        assert view["metadata"]["dataset_id"] == "dataset-contract-smoke"
        assert view["evaluation_readiness"]["formal_acceptance_ready"] is False
        assert view["counts"] == {
            "post_cases": 1,
            "user_gold": 1,
            "community_gold": 1,
        }
        assert view["threshold_layers"] == ["community", "post", "user"]
        assert view["usage_policy"]["uses_gold_for_training"] is False
        assert view["leakage_policy"]["no_runtime_derived_gold"] is True

    def test_normalize_gate_dataset_warns_without_inventing_gold(self):
        normalized = normalize_gate_dataset(
            {
                "metadata": "bad metadata",
                "post_cases": "not a list",
                "user_gold": "not gold",
                "community_gold": [{"community_id": "c1"}, "bad item"],
                "thresholds": {
                    "post": {"stance_accuracy": "bad"},
                    "user": "bad threshold layer",
                },
                "prefer_embeddings": "yes",
            }
        )
        view = gate_dataset_contract_view(normalized)

        assert normalized["provided"] is True
        assert normalized["post_cases"] is None
        assert normalized["user_gold"] is None
        assert normalized["community_gold"] == [{"community_id": "c1"}]
        assert normalized["prefer_embeddings"] is None
        assert normalized["validation"]["valid"] is True
        assert normalized["validation"]["layer_coverage"] == {
            "post_gate": False,
            "user_gate": False,
            "community_gate": True,
        }
        original_warnings = {
            "metadata_ignored_non_object",
            "metadata_missing_dataset_id",
            "metadata_missing_version",
            "metadata_missing_source",
            "metadata_missing_label_policy",
            "metadata_missing_control_set_notes",
            "post_cases_ignored_non_list",
            "user_gold_ignored_invalid_type",
            "community_gold_dropped_non_object_items",
            "thresholds_post_stance_accuracy_ignored_non_numeric",
            "thresholds_user_ignored_non_object",
            "prefer_embeddings_ignored_non_bool",
        }
        assert original_warnings.issubset(set(normalized["validation"]["warnings"]))
        assert set(normalized["evaluation_readiness"]["readiness_warnings"]) == {
            "readiness_contract_warnings_present",
            "readiness_missing_control_set_notes",
            "readiness_missing_full_layer_coverage",
            "readiness_missing_leakage_policy",
            "readiness_missing_required_metadata",
            "readiness_missing_split",
            "readiness_missing_threshold_policy",
        }
        assert normalized["evaluation_readiness"]["formal_acceptance_ready"] is False
        assert view["metadata"]["dataset_id"] == "unspecified"
        assert view["counts"] == {
            "post_cases": 0,
            "user_gold": 0,
            "community_gold": 1,
        }

    def test_validate_gate_dataset_contract_reports_missing_metadata_and_layer_coverage(self):
        validation = validate_gate_dataset_contract(
            {
                "metadata": {
                    "dataset_id": "contract-validation-smoke",
                    "version": "v1",
                },
                "post_cases": [
                    {
                        "case_id": "case_without_gold",
                        "posts": [],
                    }
                ],
                "user_gold": [{"account_id": "u1", "harmful": False}],
                "community_gold": {},
                "thresholds": {"post": {"stance_accuracy": 0.5}},
            }
        )

        assert validation["contract_version"] == "review-gate-dataset-v1"
        assert validation["valid"] is False
        assert validation["layer_coverage"] == {
            "post_gate": True,
            "user_gate": True,
            "community_gate": False,
        }
        assert validation["counts"] == {
            "post_cases": 1,
            "user_gold": 1,
            "community_gold": 0,
        }
        assert validation["threshold_layers"] == ["post"]
        assert set(validation["missing_metadata_fields"]) == {
            "source",
            "label_policy",
            "control_set_notes",
        }
        assert "post_cases_0_missing_gold" in validation["warnings"]
        assert validation["formal_acceptance_ready"] is False
        assert validation["evaluation_readiness"]["has_required_metadata"] is False
        assert validation["evaluation_readiness"]["missing_layers"] == ["community_gate"]
        assert set(validation["readiness_warnings"]) >= {
            "readiness_missing_required_metadata",
            "readiness_missing_control_set_notes",
            "readiness_missing_full_layer_coverage",
            "readiness_missing_leakage_policy",
            "readiness_missing_split",
            "readiness_missing_threshold_policy",
        }
        assert validation["usage_policy"]["runtime_gold_generation"] is False
        assert validation["leakage_policy"]["no_training_or_calibration_from_gate_gold"] is True
        assert validation["manifest"]["contains_gold_payload"] is False
        assert validation["manifest"]["counts"] == validation["counts"]
        assert len(validation["manifest"]["dataset_fingerprint"]) == 64

    def test_validate_gate_dataset_contract_reports_formal_acceptance_readiness(self):
        validation = validate_gate_dataset_contract(
            {
                "metadata": {
                    "dataset_id": "formal-acceptance-smoke",
                    "version": "v1",
                    "source": "expert_labelled_project_sample",
                    "label_policy": "independent labels only; no runtime-derived gold",
                    "control_set_notes": "same-topic same-window benign controls included",
                    "split": "eval",
                    "leakage_policy": "gold labels prepared outside current runtime report path",
                    "threshold_policy": "thresholds frozen before gate execution",
                },
                "post_cases": [
                    {
                        "case_id": "post_ready_case",
                        "posts": [{"post_id": "p1", "content": "sample"}],
                        "gold": {
                            "p1": {
                                "claim_id": "c1",
                                "stance": "support",
                                "harm_label": "harmful",
                                "harm_types": ["misinformation"],
                            }
                        },
                    }
                ],
                "user_gold": {"u1": {"harmful": True, "roles": ["amplifier"]}},
                "community_gold": {"c1": {"collective_harm": True, "harm_types": ["misinformation"]}},
                "thresholds": {
                    "post": {"stance_accuracy": 0.7},
                    "user": {"role_micro_f1": 0.5},
                    "community": {"claim_coverage_rate": 0.7},
                },
                "prefer_embeddings": False,
            }
        )

        readiness = validation["evaluation_readiness"]
        assert validation["valid"] is True
        assert validation["formal_acceptance_ready"] is True
        assert validation["readiness_warnings"] == []
        assert readiness["has_required_metadata"] is True
        assert readiness["has_control_notes"] is True
        assert readiness["has_split"] is True
        assert readiness["has_leakage_policy"] is True
        assert readiness["has_threshold_policy"] is True
        assert readiness["has_full_layer_coverage"] is True
        assert readiness["missing_layers"] == []
        assert validation["manifest"]["formal_acceptance_ready"] is True
        assert validation["manifest"]["evaluation_readiness"]["formal_acceptance_ready"] is True

    def test_gate_dataset_manifest_is_stable_and_gold_safe(self):
        dataset = {
            "metadata": {
                "dataset_id": "manifest-smoke",
                "version": "v1",
                "source": "unit_fixture",
                "label_policy": "expert labels only",
                "control_set_notes": "same-topic controls",
            },
            "post_cases": [
                {
                    "case_id": "post_manifest_case",
                    "posts": [{"post_id": "p1", "content": "sample"}],
                    "gold": {
                        "p1": {
                            "claim_id": "c1",
                            "stance": "support",
                            "harm_label": "harmful",
                            "harm_types": ["misinformation"],
                        }
                    },
                }
            ],
            "user_gold": {"u1": {"harmful": True, "roles": ["amplifier"]}},
            "community_gold": {"c1": {"collective_harm": True, "harm_types": ["misinformation"]}},
            "thresholds": {"post": {"stance_accuracy": 0.7}},
            "prefer_embeddings": False,
        }
        normalized = normalize_gate_dataset(dataset)
        manifest = build_gate_dataset_manifest(normalized)
        repeated = build_gate_dataset_manifest(normalized)
        modified = normalize_gate_dataset(
            {
                **dataset,
                "user_gold": {"u1": {"harmful": False, "roles": ["participant"]}},
            }
        )
        modified_manifest = build_gate_dataset_manifest(modified)

        assert manifest == repeated
        assert manifest["artifact_type"] == "gate_dataset_manifest"
        assert manifest["contains_gold_payload"] is False
        assert manifest["counts"] == {
            "post_cases": 1,
            "user_gold": 1,
            "community_gold": 1,
        }
        assert manifest["layer_coverage"] == {
            "post_gate": True,
            "user_gate": True,
            "community_gate": True,
        }
        assert len(manifest["dataset_fingerprint"]) == 64
        assert len(manifest["layer_fingerprints"]["user_gate"]) == 64
        assert manifest["dataset_fingerprint"] != modified_manifest["dataset_fingerprint"]
        assert manifest["layer_fingerprints"]["user_gate"] != modified_manifest["layer_fingerprints"]["user_gate"]
        assert "post_cases" not in manifest
        assert "user_gold" not in manifest
        assert "community_gold" not in manifest


class TestLayeredHarmfulness:
    def test_assess_layered_harmfulness(self):
        post_semantics = assess_post_semantics(
            _mock_posts_for_semantics(),
            _mock_prop_data(),
            prefer_embeddings=False,
        )
        result = assess_layered_harmfulness(
            post_semantics=post_semantics,
            account_profiles=_mock_acct_data(),
            coordination=_mock_coord_data(),
            propagation=_mock_prop_data(),
            event_id="test_event",
            platform="mock_weibo",
        )

        assert result["capability_boundary"]["user_level"] == "implemented_runtime_aggregation"
        assert result["post_level"]["analysis_scope"]["normalized_posts"] == 2
        assert result["user_level"]["summary"]["account_count"] >= 2
        assert result["community_level"]["summary"]["community_count"] >= 1
        assert result["audit"]["semantic_posts_used"] == 2


class TestReviewUserMIL:
    def test_score_user_mil_reports_attention_bags_and_boundaries(self):
        post_semantics = assess_post_semantics(
            _mock_posts_for_semantics(),
            _mock_prop_data(),
            prefer_embeddings=False,
        )
        layered = assess_layered_harmfulness(
            post_semantics=post_semantics,
            account_profiles=_mock_acct_data(),
            coordination=_mock_coord_data(),
            propagation=_mock_prop_data(),
            event_id="test_event",
            platform="mock_weibo",
        )

        mil = score_user_mil(
            post_semantics=post_semantics,
            account_profiles=_mock_acct_data(),
            coordination=_mock_coord_data(),
            propagation=_mock_prop_data(),
            existing_user_level=layered["user_level"],
            event_id="test_event",
            platform="mock_weibo",
        )

        assert mil["capability_boundary"]["status"] == "implemented_attention_mil_inference_scaffold"
        assert mil["capability_boundary"]["trained_mil_model"] is False
        assert mil["capability_boundary"]["trained_user_encoder"] is False
        assert mil["analysis_scope"]["bag_count"] >= 2
        assert mil["analysis_scope"]["instances_evaluated"] == 2
        assert mil["summary"]["method"] == "attention_mil_over_post_semantic_instances"
        assert len(mil["method_trace"]) >= 3
        account_with_posts = next(account for account in mil["accounts"] if account["bag_size"] > 0)
        assert "mil_harm_score" in account_with_posts
        assert account_with_posts["attention_method"] == "softmax_over_post_harm_multimodal_claim_scores"
        assert account_with_posts["attention_posts"]
        assert account_with_posts["attention_posts"][0]["evidence_modalities"]


class TestReviewQueue:
    def test_build_review_queue(self):
        post_semantics = assess_post_semantics(
            _mock_posts_for_semantics(),
            _mock_prop_data(),
            prefer_embeddings=False,
        )
        layered = assess_layered_harmfulness(
            post_semantics=post_semantics,
            account_profiles=_mock_acct_data(),
            coordination=_mock_coord_data(),
            propagation=_mock_prop_data(),
            event_id="test_event",
            platform="mock_weibo",
        )

        queue = build_review_queue(
            post_semantics=post_semantics,
            review_harmfulness=layered,
        )

        assert queue["capability_boundary"]["status"] == "implemented_review_queue_scaffold"
        assert queue["capability_boundary"]["live_llm_or_rag"] is False
        assert queue["summary"]["agent_tasks"] >= 1
        assert isinstance(queue["review_items"], list)
        assert isinstance(queue["retrieval_tasks"], list)
        assert isinstance(queue["counter_narrative_inputs"], list)
        assert any(item["type"] == "post_semantic_review" for item in queue["review_items"])
        assert any(item["type"] == "account_harm_review" for item in queue["review_items"])
        assert any(item["type"] == "community_harm_review" for item in queue["review_items"])
        assert any(task["purpose"] in {"claim_linking_and_context", "external_verification_or_context"} for task in queue["retrieval_tasks"])
        assert all(item["execution_status"] == "planned_only" for item in queue["review_items"])
        assert all(task["requires_external_execution"] is True for task in queue["agent_tasks"])


class TestReviewExecution:
    def test_execute_review_queue_locally(self):
        post_semantics = assess_post_semantics(
            _mock_posts_for_semantics(),
            _mock_prop_data(),
            prefer_embeddings=False,
        )
        layered = assess_layered_harmfulness(
            post_semantics=post_semantics,
            account_profiles=_mock_acct_data(),
            coordination=_mock_coord_data(),
            propagation=_mock_prop_data(),
            event_id="test_event",
            platform="mock_weibo",
        )
        queue = build_review_queue(
            post_semantics=post_semantics,
            review_harmfulness=layered,
        )

        execution = execute_review_queue(
            post_semantics=post_semantics,
            review_harmfulness=layered,
            review_queue=queue,
        )

        assert execution["capability_boundary"]["status"] == "implemented_local_deterministic_review_executor"
        assert execution["capability_boundary"]["live_llm_or_external_rag"] is False
        assert execution["capability_boundary"]["pluggable_retriever"] is False
        assert execution["capability_boundary"]["pluggable_review_provider"] is False
        assert execution["summary"]["review_items_executed"] == len(queue["review_items"])
        assert execution["summary"]["retrieval_tasks_executed"] == len(queue["retrieval_tasks"])
        assert execution["summary"]["agent_tasks_executed"] == len(queue["agent_tasks"])
        assert execution["summary"]["corpus_documents"] >= 1
        assert execution["summary"]["provider_results_used"] == 0
        assert execution["summary"]["provider_failures"] == 0
        assert execution["provider_audit"]["live_external_call"] is False
        assert all(result["execution_mode"] == "local_lexical_retrieval" for result in execution["retrieval_results"])
        assert all(result["execution_status"] == "executed_local" for result in execution["review_results"])
        assert all(result["execution_mode"].startswith("deterministic") for result in execution["review_results"])

        second_execution = execute_review_queue(
            post_semantics=post_semantics,
            review_harmfulness=layered,
            review_queue=queue,
        )
        assert execution["retrieval_results"] == second_execution["retrieval_results"]
        assert execution["review_results"] == second_execution["review_results"]
        assert execution["agent_results"] == second_execution["agent_results"]
        assert execution["counter_narrative_drafts"] == second_execution["counter_narrative_drafts"]

    def test_execute_review_queue_accepts_offline_mock_providers(self):
        post_semantics = assess_post_semantics(
            _mock_posts_for_semantics(),
            _mock_prop_data(),
            prefer_embeddings=False,
        )
        layered = assess_layered_harmfulness(
            post_semantics=post_semantics,
            account_profiles=_mock_acct_data(),
            coordination=_mock_coord_data(),
            propagation=_mock_prop_data(),
            event_id="test_event",
            platform="mock_weibo",
        )
        queue = build_review_queue(
            post_semantics=post_semantics,
            review_harmfulness=layered,
        )
        retriever_calls = []
        review_calls = []

        def mock_retriever(*, task, corpus, local_result, max_evidence):
            retriever_calls.append(task["id"])
            return {
                **local_result,
                "execution_status": "executed_provider",
                "execution_mode": "mock_offline_retriever",
                "evidence_found": 1,
                "top_evidence": [
                    {
                        "doc_id": "mock:evidence",
                        "doc_type": "mock",
                        "score": 0.91,
                        "excerpt": "offline mock evidence",
                        "payload_ref": {"doc_id": "mock:evidence"},
                    }
                ],
                "external_retrieval_required": False,
            }

        def mock_review_provider(*, item, local_result, retrieval_evidence):
            review_calls.append(item["id"])
            return {
                **local_result,
                "execution_status": "executed_provider",
                "execution_mode": "mock_offline_review_provider",
                "local_outcome": "mock_provider_reviewed",
                "local_confidence": 0.88,
                "external_review_required": False,
                "review_notes": ["offline mock provider result"],
            }

        execution = execute_review_queue(
            post_semantics=post_semantics,
            review_harmfulness=layered,
            review_queue=queue,
            evidence_retriever=mock_retriever,
            review_provider=mock_review_provider,
        )

        assert execution["capability_boundary"]["status"] == "implemented_pluggable_local_review_executor"
        assert execution["capability_boundary"]["pluggable_retriever"] is True
        assert execution["capability_boundary"]["pluggable_review_provider"] is True
        assert execution["capability_boundary"]["live_llm_or_external_rag"] is False
        assert execution["summary"]["provider_failures"] == 0
        assert execution["summary"]["provider_results_used"] == len(queue["retrieval_tasks"]) + len(queue["review_items"])
        assert len(retriever_calls) == len(queue["retrieval_tasks"])
        assert len(review_calls) == len(queue["review_items"])
        assert all(result["execution_mode"] == "mock_offline_retriever" for result in execution["retrieval_results"])
        assert all(result["provider_status"] == "provider_result_used" for result in execution["retrieval_results"])
        assert all(result["execution_mode"] == "mock_offline_review_provider" for result in execution["review_results"])
        assert all(result["local_outcome"] == "mock_provider_reviewed" for result in execution["review_results"])

    def test_execute_review_queue_falls_back_when_provider_fails(self):
        post_semantics = assess_post_semantics(
            _mock_posts_for_semantics(),
            _mock_prop_data(),
            prefer_embeddings=False,
        )
        layered = assess_layered_harmfulness(
            post_semantics=post_semantics,
            account_profiles=_mock_acct_data(),
            coordination=_mock_coord_data(),
            propagation=_mock_prop_data(),
            event_id="test_event",
            platform="mock_weibo",
        )
        queue = build_review_queue(
            post_semantics=post_semantics,
            review_harmfulness=layered,
        )

        def failing_retriever(**_kwargs):
            raise RuntimeError("retriever unavailable")

        def failing_review_provider(**_kwargs):
            raise RuntimeError("review provider unavailable")

        execution = execute_review_queue(
            post_semantics=post_semantics,
            review_harmfulness=layered,
            review_queue=queue,
            evidence_retriever=failing_retriever,
            review_provider=failing_review_provider,
        )

        assert execution["capability_boundary"]["status"] == "implemented_pluggable_local_review_executor"
        assert execution["capability_boundary"]["provider_failure_policy"] == "fallback_to_local_result"
        assert execution["capability_boundary"]["live_llm_or_external_rag"] is False
        assert execution["summary"]["review_items_executed"] == len(queue["review_items"])
        assert execution["summary"]["retrieval_tasks_executed"] == len(queue["retrieval_tasks"])
        assert execution["summary"]["provider_results_used"] == 0
        assert execution["summary"]["provider_failures"] == len(queue["retrieval_tasks"]) + len(queue["review_items"])
        assert len(execution["provider_audit"]["failures"]) == execution["summary"]["provider_failures"]
        assert all(result["provider_status"] == "fallback_after_provider_error" for result in execution["retrieval_results"])
        assert all(result["provider_status"] == "fallback_after_provider_error" for result in execution["review_results"])
        assert all(result["execution_mode"] == "local_lexical_retrieval" for result in execution["retrieval_results"])
        assert all(result["execution_mode"].startswith("deterministic") for result in execution["review_results"])


class TestReviewMultiAgentRuntime:
    def test_execute_multi_agent_review_runs_distinct_local_agents(self):
        post_semantics = assess_post_semantics(
            _mock_posts_for_semantics(),
            _mock_prop_data(),
            prefer_embeddings=False,
        )
        layered = assess_layered_harmfulness(
            post_semantics=post_semantics,
            account_profiles=_mock_acct_data(),
            coordination=_mock_coord_data(),
            propagation=_mock_prop_data(),
            event_id="test_event",
            platform="mock_weibo",
        )
        user_mil = score_user_mil(
            post_semantics=post_semantics,
            account_profiles=_mock_acct_data(),
            coordination=_mock_coord_data(),
            propagation=_mock_prop_data(),
            existing_user_level=layered["user_level"],
            event_id="test_event",
            platform="mock_weibo",
        )
        graph = export_review_heterogeneous_graph(
            post_semantics=post_semantics,
            review_harmfulness=layered,
            coordination=_mock_coord_data(),
            propagation=_mock_prop_data(),
        )
        queue = build_review_queue(
            post_semantics=post_semantics,
            review_harmfulness=layered,
        )
        review_execution = execute_review_queue(
            post_semantics=post_semantics,
            review_harmfulness=layered,
            review_queue=queue,
        )

        multi_agent = execute_multi_agent_review(
            post_semantics=post_semantics,
            review_harmfulness=layered,
            user_mil=user_mil,
            graph_export=graph,
            review_execution=review_execution,
        )

        assert multi_agent["capability_boundary"]["status"] == "implemented_local_multi_agent_runtime"
        assert multi_agent["capability_boundary"]["multi_agent_runtime"] is True
        assert multi_agent["capability_boundary"]["live_llm_or_external_rag"] is False
        assert multi_agent["summary"]["agents_executed"] == 6
        assert multi_agent["blackboard"]["post_count"] == 2
        assert {result["agent"] for result in multi_agent["agent_results"]} == {
            "HarmReviewAgent",
            "StanceClaimAgent",
            "EvidenceRetrievalAgent",
            "UserMILAgent",
            "CommunityJudgeAgent",
            "CounterNarrativeAgent",
        }
        assert all(result["execution_status"] == "executed_local_agent" for result in multi_agent["agent_results"])
        assert multi_agent["final_decision"]["decision"] in {
            "high_priority_harmfulness_review",
            "targeted_followup_required",
            "monitor",
        }
        assert multi_agent["final_decision"]["publish_counter_narrative_without_human_approval"] is False

    def test_execute_multi_agent_review_accepts_offline_provider(self):
        post_semantics = assess_post_semantics(
            _mock_posts_for_semantics(),
            _mock_prop_data(),
            prefer_embeddings=False,
        )
        layered = assess_layered_harmfulness(
            post_semantics=post_semantics,
            account_profiles=_mock_acct_data(),
            coordination=_mock_coord_data(),
            propagation=_mock_prop_data(),
            event_id="test_event",
            platform="mock_weibo",
        )
        calls = []

        def mock_agent_provider(*, agent_name, blackboard, local_result):
            calls.append(agent_name)
            if agent_name == "EvidenceRetrievalAgent":
                return {
                    **local_result,
                    "execution_status": "executed_provider_agent",
                    "execution_mode": "mock_offline_agent_provider",
                    "decision": "mock_provider_evidence_checked",
                    "live_external_call": False,
                }
            return None

        multi_agent = execute_multi_agent_review(
            post_semantics=post_semantics,
            review_harmfulness=layered,
            user_mil={},
            graph_export={},
            review_execution={},
            agent_provider=mock_agent_provider,
        )

        assert len(calls) == 6
        assert multi_agent["summary"]["provider_results_used"] == 1
        assert multi_agent["capability_boundary"]["pluggable_agent_provider"] is True
        assert multi_agent["capability_boundary"]["live_llm_or_external_rag"] is False
        evidence_agent = next(
            result for result in multi_agent["agent_results"] if result["agent"] == "EvidenceRetrievalAgent"
        )
        assert evidence_agent["provider_status"] == "provider_result_used"
        assert evidence_agent["decision"] == "mock_provider_evidence_checked"


class TestReviewManualAgentReview:
    def _report(self):
        post_semantics = assess_post_semantics(
            _mock_posts_for_semantics(),
            _mock_prop_data(),
            prefer_embeddings=False,
        )
        layered = assess_layered_harmfulness(
            post_semantics=post_semantics,
            account_profiles=_mock_acct_data(),
            coordination=_mock_coord_data(),
            propagation=_mock_prop_data(),
            event_id="test_event",
            platform="mock_weibo",
        )
        review_queue = build_review_queue(post_semantics=post_semantics, review_harmfulness=layered)
        layered["review_queue"] = review_queue
        return {
            "report_id": "manual-agent-report",
            "event_id": "test_event",
            "platform": "mock_weibo",
            "scores": {"risk_level": "high"},
            "post_semantics": post_semantics,
            "review_harmfulness": layered,
            "disarm_analysis": {"countermeasures": [{"action": "fact-check"}]},
        }

    def test_governance_reference_loader_matches_platform_refs(self):
        library = load_governance_reference_library()
        assert library["schema_version"] == "review-governance-reference-library-v1"
        ref_ids = {item["ref_id"] for item in library["platform_references"]}
        assert "meta-community-standards" in ref_ids
        assert "weibo-community-convention" in ref_ids
        assert "douyin-trust-center" in ref_ids

        context = {
            "selected_posts": [
                {
                    "post_id": "p1",
                    "text": "该帖子疑似传播谣言并存在图文不一致。",
                    "stance": {"label": "query", "claim_id": "c1"},
                    "post_view_detection": {"conflict": {"score": 0.8}},
                }
            ],
            "media_inputs": [{"media_type": "image", "uri": "G:/media/a.jpg"}],
            "propagation_context": {"claim_rank": [{"claim_id": "c1"}]},
        }
        reference = build_governance_reference_context(context)
        categories = {item["category_id"] for item in reference["matched_categories"]}
        assert "misinformation" in categories
        assert reference["platform_reference_refs"]
        assert reference["usage_boundary"]["does_not_override_detector_outputs"] is True

    def test_manual_agent_review_writes_natural_language_reports(self):
        calls = []

        async def mock_provider(*, agent_name, system_prompt, user_prompt, input_bundle, model):
            calls.append((agent_name, system_prompt, user_prompt, input_bundle, model))
            return f"{agent_name} report"

        result = asyncio.run(
            run_manual_agent_review(
                report=self._report(),
                agent_names=[
                    "PostHarmAgent",
                    "MultimodalConsistencyAgent",
                    "ClaimEvidenceAgent",
                    "PropagationTreeAgent",
                    "QuestionReflectionAgent",
                    "HarmfulnessJudgeAgent",
                    "CountermeasureAgent",
                ],
                selected_post_ids=["p1"],
                selected_tree_ids=["tree-1"],
                human_triggered_by=42,
                provider=mock_provider,
                model="mock-model",
            )
        )

        assert result["schema_version"] == "review-manual-agent-review-v1"
        assert result["audit"]["capability_boundary"]["manual_human_triggered"] is True
        assert result["audit"]["capability_boundary"]["fits_benchmark_labels"] is False
        assert result["audit"]["effective_runtime_mode"] == "complex"
        execution_plan = result["audit"]["execution_plan"]
        expected_expert_count = len(execution_plan["expert_agents"])
        expected_reflection_count = min(expected_expert_count, 2)
        assert result["summary"]["completed"] == expected_expert_count + expected_reflection_count + 3
        assert result["summary"]["failed"] == 0
        assert result["summary"]["reflection_response_reports"] == expected_reflection_count
        assert len(calls) == result["summary"]["completed"]
        assert calls[0][0] == "PostHarmAgent"
        assert calls[-1][0] == "CountermeasureAgent"
        assert result["input_bundle"]["input_refs"]["post_ids"] == ["p1"]
        assert result["input_bundle"]["governance_reference"]["platform_reference_refs"]
        roles = [item.get("report_role") for item in result["agent_reports"]]
        reflection_reports = [item for item in result["agent_reports"] if item.get("report_role") == "reflection_response"]
        assert roles.count("expert_initial") == expected_expert_count
        assert "reflection" in roles
        assert "judge_final" in roles
        assert "countermeasure_final" in roles
        assert len(reflection_reports) == expected_reflection_count
        for report in result["agent_reports"]:
            assert report["status"] == "completed"
            assert report["analysis_report"]["format"] == "natural_language_or_semi_structured_report"
            assert report["analysis_report"]["capability_boundary"]["not_json_classifier"] is True
            assert report["report_text"]
            assert "not_a_classifier_output" in report["safety_flags"]
            assert report["system_audit_sidecar"]["not_agent_primary_output"] is True
            assert report["structured_sidecar"]["schema_version"] == "review-agent-sidecar-v1"
            assert report["structured_sidecar"]["platform_reference_refs"]

        judge_report = next(item for item in result["agent_reports"] if item.get("report_role") == "judge_final")
        governance_report = judge_report["structured_sidecar"]["governance_report"]
        assert governance_report["governance_report_text"]
        assert governance_report["platform_reference_refs"]
        assert governance_report["recommended_action"] in {
            "补证",
            "人审",
            "限流",
            "标注",
            "辟谣推荐",
            "删除建议",
            "账号处置建议",
            "反制叙事草案",
            "不处置",
        }

    def test_manual_agent_review_adds_active_retrieval_and_light_debate_sidecar(self):
        calls = []

        async def mock_provider(*, agent_name, system_prompt, user_prompt, input_bundle, model):
            calls.append((agent_name, input_bundle))
            return f"{agent_name} report"

        async def mock_retriever(*, query, context, top_k):
            return [
                {
                    "url": "https://example.com/evidence",
                    "title": "External evidence",
                    "snippet": f"retrieved for {query[:20]}",
                    "score": 0.8,
                }
            ][:top_k]

        result = asyncio.run(
            run_manual_agent_review(
                report=self._report(),
                agent_names=["ClaimEvidenceAgent", "MultimodalConsistencyAgent", "HarmfulnessJudgeAgent"],
                selected_post_ids=["p1"],
                selected_tree_ids=["tree-1"],
                human_triggered_by=42,
                provider=mock_provider,
                model="mock-model",
                enable_active_retrieval=True,
                enable_light_debate=True,
                active_retriever=mock_retriever,
                external_retrieval_enabled=True,
            )
        )

        assert result["summary"]["completed"] == 7
        assert result["summary"]["reflection_response_reports"] == 2
        assert result["summary"]["active_retrieval_used"] is True
        assert result["summary"]["light_debate_triggered"] is True
        assert result["active_retrieval"]["audit"]["external_provider_configured"] is True
        assert result["active_retrieval"]["capability_boundary"]["external_retrieval_default_enabled"] is True
        assert result["active_retrieval"]["external_results"]
        for report in result["agent_reports"]:
            sidecar = report["structured_sidecar"]
            assert sidecar["active_retrieval_used"] is True
            assert sidecar["retrieval_queries"]
            assert sidecar["source_quality"]["external_evidence"] >= 1
        multimodal_report = next(item for item in result["agent_reports"] if item["agent_name"] == "MultimodalConsistencyAgent")
        assert multimodal_report["structured_sidecar"]["light_debate_used"] is True

    def test_manual_agent_review_records_failure_without_synthetic_report(self):
        result = asyncio.run(
            run_manual_agent_review(
                report=self._report(),
                agent_names=["PostHarmAgent"],
                selected_post_ids=["p1"],
                human_triggered_by=42,
                provider=None,
                model="mock-model",
                runtime_mode="simple",
            )
        )

        assert result["summary"]["completed"] == 0
        assert result["summary"]["failed"] == 2
        assert result["audit"]["effective_runtime_mode"] == "simple"
        assert {item["agent_name"] for item in result["agent_reports"]} == {"PostHarmAgent", "HarmfulnessJudgeAgent"}
        for report in result["agent_reports"]:
            assert report["status"] == "failed"
            assert report["report_text"] is None
            assert report["structured_sidecar"]["schema_version"] == "review-agent-sidecar-v1"
            assert "no_synthetic_fallback" in report["safety_flags"]

    def test_manual_agent_review_requires_vision_for_multimodal_agent(self):
        calls = []

        async def mock_provider(*, agent_name, system_prompt, user_prompt, input_bundle, model):
            calls.append(agent_name)
            return "should not be called"

        result = asyncio.run(
            run_manual_agent_review(
                report=self._report(),
                agent_names=["MultimodalConsistencyAgent"],
                selected_post_ids=["p1"],
                human_triggered_by=42,
                provider=mock_provider,
                model="mock-model",
                include_media_base64=False,
                require_vision=True,
                runtime_mode="simple",
            )
        )

        assert "MultimodalConsistencyAgent" not in calls
        assert calls == ["HarmfulnessJudgeAgent"]
        assert result["summary"]["completed"] == 1
        assert result["summary"]["failed"] == 1
        failed_report = next(item for item in result["agent_reports"] if item["status"] == "failed")
        assert failed_report["agent_name"] == "MultimodalConsistencyAgent"
        assert failed_report["vision_required"] is True
        assert failed_report["vision_input_status"]["has_vision_input"] is False
        assert "missing_vision_input" in failed_report["safety_flags"]
        assert failed_report["report_text"] is None

    def test_openai_provider_uses_responses_api_with_image_input(self, tmp_path, monkeypatch):
        image_path = tmp_path / "frame.png"
        image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        captured = {}

        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"output_text": "Responses API natural-language report"}

        class FakeAsyncClient:
            def __init__(self, timeout):
                captured["timeout"] = timeout

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url, headers, json):
                captured["url"] = url
                captured["headers"] = headers
                captured["payload"] = json
                return FakeResponse()

        # The OpenAI-compatible provider (and its httpx import) lives in
        # ``agent_provider``; ``agent_review`` only re-exports it.
        monkeypatch.setattr("app.core.review.agent_provider.httpx.AsyncClient", FakeAsyncClient)
        provider = OpenAICompatibleAgentProvider(
            OpenAICompatibleConfig(
                api_key="sk-test-secret",
                base_url="https://example.test/v1",
                model="gpt-vision-test",
                wire_api="responses",
            )
        )
        result = asyncio.run(
            provider(
                agent_name="MultimodalConsistencyAgent",
                system_prompt="system",
                user_prompt="user",
                input_bundle={
                    "media_inputs": [
                        {"media_type": "image", "data_url": "data:image/png;base64,AAAA"}
                    ]
                },
                model="",
            )
        )

        assert result == "Responses API natural-language report"
        assert captured["url"] == "https://example.test/v1/responses"
        assert captured["headers"]["Authorization"] == "Bearer sk-test-secret"
        assert captured["payload"]["instructions"] == "system"
        assert captured["payload"]["input"][0]["content"][0] == {"type": "input_text", "text": "user"}
        assert captured["payload"]["input"][0]["content"][1]["type"] == "input_image"
        assert captured["payload"]["input"][0]["content"][1]["image_url"].startswith("data:image/png")

    def test_import_cc_switch_llm_config_redacts_key_and_writes_env(self, tmp_path, capsys, monkeypatch):
        script = _load_script_module("import_cc_switch_llm_config")
        db_path = tmp_path / "cc-switch.db"
        env_path = tmp_path / ".env"
        secret = "sk-test-very-secret-key"
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                """
                create table providers (
                    id text,
                    app_type text,
                    name text,
                    settings_config text,
                    is_current integer
                )
                """
            )
            conn.execute(
                "insert into providers values (?, ?, ?, ?, ?)",
                (
                    "provider-1",
                    "codex",
                    "Current Codex",
                    json.dumps(
                        {
                            "auth": {"OPENAI_API_KEY": secret},
                            "config": (
                                'model_provider = "custom"\n'
                                'model = "gpt-vision-test"\n'
                                '[model_providers.custom]\n'
                                'wire_api = "responses"\n'
                                'base_url = "https://example.test/v1"\n'
                            ),
                        }
                    ),
                    1,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        monkeypatch.setattr(
            sys,
            "argv",
            [
                "import_cc_switch_llm_config.py",
                "--db",
                str(db_path),
                "--env",
                str(env_path),
            ],
        )
        exit_code = script.main()
        assert exit_code == 0
        output = capsys.readouterr().out
        assert secret not in output
        env_text = env_path.read_text(encoding="utf-8")
        assert "LLM_API_KEY=sk-test-very-secret-key" in env_text
        assert "LLM_API_BASE=https://example.test/v1" in env_text
        assert "LLM_MODEL=gpt-vision-test" in env_text
        assert "LLM_API_WIRE=responses" in env_text
        assert "LLM_REQUIRE_VISION=true" in env_text

    def test_service_appends_manual_agent_review_to_persisted_report(self):
        report = self._report()

        class FakeResult:
            def __init__(self, row):
                self.row = row

            def scalar_one_or_none(self):
                return self.row

        class FakeSession:
            def __init__(self, row):
                self.row = row
                self.flushed = False

            async def execute(self, _stmt):
                return FakeResult(self.row)

            async def flush(self):
                self.flushed = True

        row = type("RiskRow", (), {"report_json": json.dumps(report, ensure_ascii=False)})()
        db = FakeSession(row)

        async def mock_provider(*, agent_name, system_prompt, user_prompt, input_bundle, model):
            assert agent_name in {"PostHarmAgent", "HarmfulnessJudgeAgent"}
            assert input_bundle["input_refs"]["case_id"] == "case-1"
            return f"{agent_name} 自然语言报告：仅供人工复核。"

        result = asyncio.run(
            risk_service.run_agent_review(
                report_id="manual-agent-report",
                case_id="case-1",
                agent_names=["PostHarmAgent"],
                selected_post_ids=["p1"],
                selected_tree_ids=["tree-1"],
                runtime_mode="simple",
                user_id=42,
                db=db,
                provider=mock_provider,
            )
        )

        persisted = json.loads(row.report_json)
        assert db.flushed is True
        assert result["summary"]["completed"] == 2
        assert persisted["agent_reviews"][0]["report_format"] == "maro_style_natural_language_analysis_report"
        assert persisted["agent_reviews"][0]["analysis_report"]["capability_boundary"]["primary_agent_output"] is True
        assert persisted["agent_reviews"][0]["structured_sidecar"]["active_retrieval_used"] is False
        assert persisted["agent_reviews"][0]["human_triggered_by"] == "42"
        assert persisted["agent_review_runs"][0]["case_id"] == "case-1"
        assert persisted["agent_review_runs"][0]["effective_runtime_mode"] == "simple"
        assert persisted["agent_review_runs"][0]["input_refs"]["post_ids"] == ["p1"]
        assert persisted["review_harmfulness"]["agent_review_suggestions"]["manual_trigger_required"] is True

    def test_optimize_agent_policy_uses_validation_and_reports_held_out(self):
        manifest = {
            "dataset_id": "mock-review-policy",
            "source": "unit-test",
            "splits": {
                "validation": [
                    {"case_id": "v1", "gold_label": "harmful", "harm_score": 0.82, "review_reason": ["conflict"]},
                    {"case_id": "v2", "gold_label": "non_harmful", "harm_score": 0.22},
                    {"case_id": "v3", "gold_label": "harmful", "harm_score": 0.64},
                ],
                "held_out": [
                    {"case_id": "h1", "gold_label": "harmful", "harm_score": 0.74},
                    {"case_id": "h2", "gold_label": "non_harmful", "harm_score": 0.18},
                ],
            },
        }

        result = optimize_agent_policy(manifest)

        assert result["schema_version"] == "review-agent-policy-v1"
        assert result["policy_id"].startswith("review-policy-")
        assert result["optimization"]["validation_cases"] == 3
        assert result["optimization"]["held_out_cases"] == 2
        assert result["optimization"]["held_out_metrics"] is not None
        assert result["capability_boundary"]["does_not_modify_detector_outputs"] is True

    def test_refine_policy_loop_uses_feedback_and_rejects_invalid_llm_rules(self):
        manifest = {
            "dataset_id": "mock-review-refine",
            "source": "unit-test",
            "baseline_policy": {
                "review_threshold": 0.6,
                "abstain_threshold": 0.3,
                "retrieval_threshold": 0.7,
                "countermeasure_threshold": 0.9,
            },
            "splits": {
                "validation": [
                    {"case_id": "v1", "gold_label": "harmful", "harm_score": 0.56},
                    {"case_id": "v2", "gold_label": "harmful", "harm_score": 0.58},
                    {"case_id": "v3", "gold_label": "non_harmful", "harm_score": 0.22},
                ],
                "held_out": [
                    {"case_id": "h1", "gold_label": "harmful", "harm_score": 0.57},
                    {"case_id": "h2", "gold_label": "non_harmful", "harm_score": 0.25},
                ],
            },
        }
        feedback = [
            {
                "review_id": "review-1",
                "corrected_label": "harmful",
                "error_types": ["false_negative"],
                "evidence_refs": [{"doc_id": "post:p1"}],
            }
        ]

        def mock_rule_generator(**_kwargs):
            return {
                "candidate_rules": [
                    {
                        "rule_id": "bad-field",
                        "description": "invalid direct detector mutation",
                        "policy_patch": {"mutate_detector_output": True},
                    },
                    {
                        "rule_id": "lower-review",
                        "source": "human_feedback",
                        "description": "catch validation false negatives",
                        "policy_patch": {"review_threshold": 0.54, "retrieval_threshold": 0.62},
                    },
                    {
                        "rule_id": "platform-template",
                        "source": "platform_template",
                        "description": "require public platform reference in governance reports",
                        "policy_patch": {
                            "trigger_conditions": {"retrieval_on_claim_uncertainty": True},
                            "report_template_constraints": {
                                "require_platform_reference": True,
                                "require_human_confirmation_items": True,
                                "countermeasure_internal_only": True,
                            },
                        },
                    },
                ]
            }

        result = refine_agent_policy_loop(
            manifest,
            feedback_memory=feedback,
            max_iterations=2,
            enable_llm_rule_generator=True,
            rule_generator=mock_rule_generator,
        )

        assert result["schema_version"] == "review-agent-policy-refinement-v1"
        assert result["policy_id"].startswith("review-refined-policy-")
        assert result["error_memory_summary"]["feedback_count"] == 1
        assert result["error_memory_summary"]["error_type_counts"]["false_negative"] == 1
        assert result["held_out_audit"] is not None
        assert result["activation_status"] == "candidate_pending_human_approval"
        assert result["capability_boundary"]["human_approval_required_for_activation"] is True
        assert any(rule["status"] == "rejected_schema" for rule in result["candidate_rules"])
        assert any(rule.get("rule_id") == "lower-review" for rule in result["candidate_rules"])
        platform_rule = next(rule for rule in result["candidate_rules"] if rule.get("rule_id") == "platform-template")
        assert platform_rule["source"] == "platform_template"
        assert platform_rule["status"] in {"evaluated", "accepted_for_round"}
        assert result["policy"]["report_template_constraints"]["require_platform_reference"] is True
        assert result["policy"]["trigger_conditions"]["retrieval_on_claim_uncertainty"] is True
        assert result["validation_metrics_by_round"][0]["stage"] == "baseline"
        assert result["refinement_trace"]

    def test_refine_policy_loop_requires_real_llm_generator_when_enabled(self):
        manifest = {
            "dataset_id": "mock-review-refine",
            "splits": {
                "validation": [{"case_id": "v1", "gold_label": "harmful", "harm_score": 0.6}],
                "held_out": [{"case_id": "h1", "gold_label": "harmful", "harm_score": 0.6}],
            },
        }
        with pytest.raises(ValueError):
            refine_agent_policy_loop(
                manifest,
                enable_llm_rule_generator=True,
                rule_generator=None,
            )

    def test_feedback_summary_counts_error_memory(self):
        summary = summarize_feedback_memory(
            [
                {
                    "review_id": "r1",
                    "corrected_label": "harmful",
                    "error_types": ["false_negative", "claim_unlinked"],
                    "evidence_refs": [{"doc_id": "e1"}, {"doc_id": "e2"}],
                },
                {
                    "run_id": "run-2",
                    "corrected_harmfulness": "non_harmful",
                    "error_types": ["false_positive"],
                },
            ]
        )

        assert summary["feedback_count"] == 2
        assert summary["linked_review_count"] == 2
        assert summary["evidence_ref_count"] == 2
        assert summary["corrected_label_counts"]["harmful"] == 1
        assert summary["error_type_counts"]["false_negative"] == 1

    def test_manual_agent_review_injects_active_policy_into_judge_context_and_sidecar(self):
        captured = {}
        policy = {
            "policy_id": "review-refined-policy-test",
            "activation_status": "active_human_approved",
            "policy": {
                "review_threshold": 0.54,
                "abstain_threshold": 0.34,
                "retrieval_threshold": 0.6,
                "countermeasure_threshold": 0.7,
            },
            "candidate_rules": [
                {
                    "rule_id": "lower-review",
                    "round": 1,
                    "source": "DecisionRuleOptimizerAgent",
                    "description": "Lower review threshold after false negatives.",
                    "status": "accepted_for_round",
                }
            ],
        }

        async def mock_provider(*, agent_name, system_prompt, user_prompt, input_bundle, model):
            captured[agent_name] = {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "input_bundle": input_bundle,
            }
            return f"{agent_name} policy-aware report"

        result = asyncio.run(
            run_manual_agent_review(
                report=self._report(),
                agent_names=["HarmfulnessJudgeAgent"],
                selected_post_ids=["p1"],
                human_triggered_by=42,
                provider=mock_provider,
                model="mock-model",
                policy=policy,
            )
        )

        judge_report = next(item for item in result["agent_reports"] if item.get("report_role") == "judge_final")
        prompt_payload = json.loads(captured["HarmfulnessJudgeAgent"]["user_prompt"])
        assert prompt_payload["policy_guidance"]["active_policy_present"] is True
        assert prompt_payload["policy_guidance"]["policy_id"] == "review-refined-policy-test"
        assert prompt_payload["policy_guidance"]["accepted_rule_refs"][0]["rule_id"] == "lower-review"
        assert "active_policy" in captured["HarmfulnessJudgeAgent"]["input_bundle"]
        assert judge_report["structured_sidecar"]["active_policy_id"] == "review-refined-policy-test"
        assert judge_report["structured_sidecar"]["policy_rule_refs"][0]["rule_id"] == "lower-review"

    def test_manual_agent_review_runs_single_pass_judge_and_post_judge_countermeasure_by_default(self):
        async def mock_provider(*, agent_name, system_prompt, user_prompt, input_bundle, model):
            return f"{agent_name} output"

        result = asyncio.run(
            run_manual_agent_review(
                report=self._report(),
                agent_names=["HarmfulnessJudgeAgent", "CountermeasureAgent"],
                selected_post_ids=["p1"],
                human_triggered_by=42,
                provider=mock_provider,
                model="mock-model",
            )
        )
        roles = [item.get("report_role") for item in result["agent_reports"]]
        assert "judge_final" in roles
        assert "countermeasure_final" in roles
        assert "judge_draft" not in roles
        assert "countermeasure_draft" not in roles

    def test_manual_agent_review_enable_deep_judge_self_refines_judge_only(self):
        async def mock_provider(*, agent_name, system_prompt, user_prompt, input_bundle, model):
            return f"{agent_name} output"

        result = asyncio.run(
            run_manual_agent_review(
                report=self._report(),
                agent_names=["HarmfulnessJudgeAgent", "CountermeasureAgent"],
                selected_post_ids=["p1"],
                human_triggered_by=42,
                provider=mock_provider,
                model="mock-model",
                enable_deep_judge=True,
            )
        )
        roles = [item.get("report_role") for item in result["agent_reports"]]
        assert "judge_draft" in roles
        assert "judge_critique" in roles
        assert "judge_final" in roles
        assert "countermeasure_final" in roles
        assert "countermeasure_draft" not in roles
        assert "countermeasure_critique" not in roles

    def test_full_debate_triggers_for_high_conflict_and_low_conflict_stays_off(self):
        async def mock_provider(*, agent_name, system_prompt, user_prompt, input_bundle, model):
            return f"{agent_name} debate/report text"

        high_conflict = asyncio.run(
            run_manual_agent_review(
                report=self._report(),
                agent_names=["MultimodalConsistencyAgent", "HarmfulnessJudgeAgent"],
                selected_post_ids=["p1"],
                human_triggered_by=42,
                provider=mock_provider,
                model="mock-model",
                enable_full_debate=True,
                debate_max_rounds=2,
            )
        )

        assert high_conflict["summary"]["full_debate_triggered"] is True
        assert high_conflict["full_debate"]["schema_version"] == "review-full-debate-v1"
        stages = [turn["stage"] for turn in high_conflict["full_debate"]["turns"]]
        assert stages[:2] == ["opening", "rebuttal"]
        assert "judge_synthesis" in stages
        assert high_conflict["agent_reports"][0]["structured_sidecar"]["debate_mode"] == "full_debate"

        low_report = self._report()
        for post in low_report["post_semantics"]["posts"]:
            post["post_view_detection"] = {
                "conflict": {},
                "review_reason": [],
            }
            post["stance"] = {"label": "support", "abstain": False}

        low_conflict = asyncio.run(
            run_manual_agent_review(
                report=low_report,
                agent_names=["MultimodalConsistencyAgent", "HarmfulnessJudgeAgent"],
                selected_post_ids=["p1"],
                human_triggered_by=42,
                provider=mock_provider,
                model="mock-model",
                enable_full_debate=True,
            )
        )

        assert low_conflict["summary"]["full_debate_triggered"] is False
        assert low_conflict["full_debate"] is None
        assert low_conflict["agent_reports"][0]["structured_sidecar"]["debate_mode"] == "light_debate"

    def test_manual_agent_review_simple_mode_skips_complex_enhancements(self):
        async def mock_provider(*, agent_name, system_prompt, user_prompt, input_bundle, model):
            return f"{agent_name} output"

        result = asyncio.run(
            run_manual_agent_review(
                report=self._report(),
                agent_names=["PostHarmAgent", "ClaimEvidenceAgent"],
                selected_post_ids=["p1"],
                human_triggered_by=42,
                provider=mock_provider,
                model="mock-model",
                runtime_mode="simple",
            )
        )

        assert result["audit"]["effective_runtime_mode"] == "simple"
        assert result["summary"]["active_retrieval_used"] is False
        assert result["summary"]["light_debate_triggered"] is False
        assert result["summary"]["full_debate_triggered"] is False
        assert result["summary"]["reflection_response_reports"] == 0
        assert {item["agent_name"] for item in result["agent_reports"]} == {
            "PostHarmAgent",
            "ClaimEvidenceAgent",
            "HarmfulnessJudgeAgent",
        }
        assert all(item["report_role"] != "reflection" for item in result["agent_reports"])
        assert all(item["agent_name"] != "CountermeasureAgent" for item in result["agent_reports"])

    def test_manual_agent_review_upgrades_simple_request_when_complex_features_are_enabled(self):
        async def mock_provider(*, agent_name, system_prompt, user_prompt, input_bundle, model):
            return f"{agent_name} output"

        result = asyncio.run(
            run_manual_agent_review(
                report=self._report(),
                agent_names=["PostHarmAgent"],
                selected_post_ids=["p1"],
                human_triggered_by=42,
                provider=mock_provider,
                model="mock-model",
                runtime_mode="simple",
                enable_active_retrieval=True,
            )
        )

        assert result["audit"]["recommended_runtime_mode"] == "complex"
        assert result["audit"]["effective_runtime_mode"] == "complex"
        assert result["audit"]["runtime_upgraded_by_requested_features"] is True
        assert "enabled_active_retrieval" in result["audit"]["runtime_reasons"]

    def test_service_feedback_refine_and_activate_policy(self):
        report = self._report()

        class FakeResult:
            def __init__(self, row):
                self.row = row

            def scalar_one_or_none(self):
                return self.row

        class FakeSession:
            def __init__(self, row):
                self.row = row
                self.flushed = False

            async def execute(self, _stmt):
                return FakeResult(self.row)

            async def flush(self):
                self.flushed = True

        row = type("RiskRow", (), {"report_json": json.dumps(report, ensure_ascii=False)})()
        db = FakeSession(row)

        feedback_result = asyncio.run(
            risk_service.record_review_agent_feedback(
                report_id="manual-agent-report",
                feedback={
                    "review_id": "review-1",
                    "case_id": "p1",
                    "corrected_harmfulness": "harmful",
                    "error_types": ["false_negative"],
                    "notes": "missed implicit harm",
                    "evidence_refs": [{"doc_id": "post:p1"}],
                    "reviewer_confidence": 0.9,
                },
                user_id=42,
                db=db,
            )
        )

        assert db.flushed is True
        assert feedback_result["summary"]["feedback_count"] == 1
        persisted = json.loads(row.report_json)
        assert persisted["agent_feedback"][0]["corrected_label"] == "harmful"

        manifest = {
            "dataset_id": "service-refine",
            "baseline_policy": {"review_threshold": 0.6, "abstain_threshold": 0.3},
            "splits": {
                "validation": [
                    {"case_id": "v1", "gold_label": "harmful", "harm_score": 0.56},
                    {"case_id": "v2", "gold_label": "non_harmful", "harm_score": 0.2},
                ],
                "held_out": [{"case_id": "h1", "gold_label": "harmful", "harm_score": 0.58}],
            },
        }
        refined = asyncio.run(
            risk_service.refine_review_policy(
                dataset_manifest=manifest,
                feedback_report_ids=["manual-agent-report"],
                max_iterations=1,
                db=db,
            )
        )

        assert refined["error_memory_summary"]["feedback_count"] == 1
        assert refined["activation_status"] == "candidate_pending_human_approval"
        activated = risk_service.activate_review_policy(refined["policy_id"], user_id=42)
        assert activated["activation_status"] == "active_human_approved"
        assert risk_service.get_review_policy(refined["policy_id"])["activation_status"] == "active_human_approved"


class TestReviewGraphExport:
    def test_export_review_heterogeneous_graph(self, tmp_path):
        post_semantics = assess_post_semantics(
            _mock_posts_for_semantics(),
            _mock_prop_data(),
            prefer_embeddings=False,
        )
        layered = assess_layered_harmfulness(
            post_semantics=post_semantics,
            account_profiles=_mock_acct_data(),
            coordination=_mock_coord_data(),
            propagation=_mock_prop_data(),
            event_id="test_event",
            platform="mock_weibo",
        )

        graph = export_review_heterogeneous_graph(
            post_semantics=post_semantics,
            review_harmfulness=layered,
            coordination=_mock_coord_data(),
            propagation=_mock_prop_data(),
        )

        assert graph["capability_boundary"]["status"] == "implemented_graph_export_schema"
        assert graph["capability_boundary"]["trained_graph_model"] is False
        assert graph["summary"]["graph_native_ready"] is True
        assert graph["summary"]["node_types"]["account"] >= 2
        assert graph["summary"]["node_types"]["post"] == 2
        assert graph["summary"]["node_types"]["claim"] >= 1
        assert graph["summary"]["node_types"]["community"] >= 1
        assert graph["summary"]["node_types"]["media"] >= 1
        assert graph["summary"]["node_types"]["target"] >= 1
        assert graph["summary"]["edge_types"]["authored"] >= 2
        assert graph["summary"]["edge_types"]["member_of"] >= 2
        assert graph["summary"]["edge_types"]["post_uses_media"] >= 1
        assert graph["summary"]["edge_types"]["account_shares_object"] >= 1
        assert graph["summary"]["edge_types"]["account_targets"] >= 1
        assert graph["summary"]["edge_types"]["community_targets"] >= 1
        assert graph["summary"]["edge_types"]["co_shares_object"] >= 1
        assert graph["summary"]["dropped_dangling_edges"] >= 0
        assert {"account", "post", "claim", "community", "target", "media"}.issubset(
            set(graph["schema"]["node_types"])
        )
        assert "mentions_claim" in graph["schema"]["edge_types"]
        assert "co_shares_object" in graph["schema"]["edge_types"]
        node_ids = {node["id"] for node in graph["nodes"]}
        assert all(edge["source"] in node_ids and edge["target"] in node_ids for edge in graph["edges"])
        assert any(
            edge["type"] == "co_shares_object"
            and edge["attrs"].get("relation") == "url_share"
            and edge["attrs"].get("object_id") == "https://cdn.example.com/image1.jpg"
            for edge in graph["edges"]
        )
        manifest = write_review_graph_artifact(graph, tmp_path / "review-graph.json")
        assert manifest["artifact_exported"] is True
        assert manifest["consumer_readable"] is True
        assert manifest["export_verified"] is True
        assert manifest["trained_graph_model"] is False
        assert manifest["node_count"] == graph["summary"]["node_count"]
        assert manifest["edge_count"] == graph["summary"]["edge_count"]

        artifact = read_review_graph_artifact(manifest["artifact_path"])
        assert artifact["schema_version"] == manifest["schema_version"]
        assert artifact["capability_boundary"]["trained_graph_model"] is False
        assert artifact["graph"]["summary"] == graph["summary"]

    def test_read_review_graph_artifact_rejects_invalid_consumer_contract(self, tmp_path):
        invalid_artifact = tmp_path / "invalid-review-graph.json"
        invalid_artifact.write_text(
            """
            {
              "schema_version": "review-graph-export-v1",
              "artifact_type": "review_heterogeneous_graph",
              "graph": {
                "schema": {"node_types": ["account"], "edge_types": ["dangling"]},
                "summary": {"node_count": 1, "edge_count": 1},
                "nodes": [{"id": "account:u1", "type": "account", "attrs": {}}],
                "edges": [{"id": "dangling:1", "source": "account:u1", "target": "account:missing", "type": "dangling", "attrs": {}}]
              }
            }
            """,
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match="dangling edge"):
            read_review_graph_artifact(invalid_artifact)


class TestRiskServiceReviewIntegration:
    def test_assess_risk_includes_review_harmfulness(self, monkeypatch):
        async def mock_coordination_detection(**_kwargs):
            return _mock_coord_data()

        async def mock_propagation(**_kwargs):
            return _mock_prop_data()

        async def mock_account_profiles(**_kwargs):
            return _mock_acct_data()

        async def mock_load_posts(**_kwargs):
            return _mock_posts_for_semantics()

        monkeypatch.setattr(
            risk_service.coordination_service,
            "run_coordination_detection",
            mock_coordination_detection,
        )
        monkeypatch.setattr(
            risk_service.propagation_service,
            "analyze_propagation",
            mock_propagation,
        )
        monkeypatch.setattr(
            risk_service.account_service,
            "get_account_profiles",
            mock_account_profiles,
        )
        monkeypatch.setattr(risk_service, "_load_posts_for_semantics", mock_load_posts)

        report = asyncio.run(
            risk_service.assess_risk(
                platform="mock_weibo",
                event_id="test_event",
                db=None,
            )
        )

        assert report["event_id"] == "test_event"
        assert report["post_semantics"]["analysis_scope"]["normalized_posts"] == 2
        assert report["review_harmfulness"]["post_level"]["analysis_scope"]["normalized_posts"] == 2
        assert report["review_harmfulness"]["user_level"]["summary"]["account_count"] >= 2
        assert report["review_harmfulness"]["user_mil"]["capability_boundary"]["trained_mil_model"] is False
        assert report["review_harmfulness"]["user_mil"]["analysis_scope"]["instances_evaluated"] == 2
        assert report["review_harmfulness"]["community_level"]["summary"]["community_count"] >= 1
        assert report["review_harmfulness"]["review_queue"]["capability_boundary"]["live_llm_or_rag"] is False
        assert report["review_harmfulness"]["review_queue"]["summary"]["agent_tasks"] >= 1
        assert report["review_harmfulness"]["review_execution"]["capability_boundary"]["live_llm_or_external_rag"] is False
        assert report["review_harmfulness"]["review_execution"]["summary"]["review_items_executed"] >= 1
        suggestions = report["review_harmfulness"]["agent_review_suggestions"]
        assert suggestions["manual_trigger_required"] is True
        assert suggestions["capability_boundary"]["llm_called"] is False
        assert suggestions["suggested_agents"]
        assert report["review_harmfulness"]["multi_agent_review"]["capability_boundary"]["status"] == "disabled_by_default"
        assert report["review_harmfulness"]["multi_agent_review"]["summary"]["agents_executed"] == 0
        assert report["review_harmfulness"]["multi_agent_review"]["agent_results"] == []
        assert report["review_harmfulness"]["graph_export"]["capability_boundary"]["trained_graph_model"] is False
        assert report["review_harmfulness"]["graph_export"]["summary"]["node_types"]["post"] == 2
        assert report["review_harmfulness"]["gate_suite"]["capability_boundary"]["evaluation_harness_only"] is True
        assert report["review_harmfulness"]["gate_suite"]["capability_boundary"]["trained_post_model"] is False
        assert report["review_harmfulness"]["gate_suite"]["capability_boundary"]["trained_user_encoder"] is False
        assert report["review_harmfulness"]["gate_suite"]["capability_boundary"]["trained_graph_model"] is False
        assert report["review_harmfulness"]["gate_suite"]["summary"]["executed_gates"] == 0
        assert report["review_harmfulness"]["gate_suite"]["summary"]["skipped_gates"] == 3
        assert set(report["review_harmfulness"]["gate_suite"]["skipped_gates"]) == {
            "community_gate",
            "post_gate",
            "user_gate",
        }

    def test_assess_risk_executes_gate_suite_when_gold_dataset_provided(self, monkeypatch):
        async def mock_coordination_detection(**_kwargs):
            return _mock_coord_data()

        async def mock_propagation(**_kwargs):
            return _mock_prop_data()

        async def mock_account_profiles(**_kwargs):
            return _mock_acct_data()

        async def mock_load_posts(**_kwargs):
            return _mock_posts_for_semantics()

        monkeypatch.setattr(
            risk_service.coordination_service,
            "run_coordination_detection",
            mock_coordination_detection,
        )
        monkeypatch.setattr(
            risk_service.propagation_service,
            "analyze_propagation",
            mock_propagation,
        )
        monkeypatch.setattr(
            risk_service.account_service,
            "get_account_profiles",
            mock_account_profiles,
        )
        monkeypatch.setattr(risk_service, "_load_posts_for_semantics", mock_load_posts)

        gate_dataset = {
            "metadata": {
                "dataset_id": "service-review-smoke",
                "version": "v1",
                "source": "risk_service_fixture",
                "label_policy": "matches current deterministic scaffold outputs",
                "control_set_notes": "exercises all three gates without claiming model readiness",
            },
            "prefer_embeddings": False,
            "post_cases": [
                {
                    "case_id": "service_post_gate",
                    "posts": _mock_posts_for_semantics(),
                    "propagation": _mock_prop_data(),
                    "gold": {
                        "p1": {
                            "claim_id": "url1",
                            "stance": "uncertain",
                            "harm_label": "non_harmful",
                            "harm_types": [],
                            "must_have_modalities": ["text", "ocr", "media"],
                        },
                        "p2": {
                            "claim_id": "url1",
                            "stance": "uncertain",
                            "harm_label": "non_harmful",
                            "harm_types": [],
                            "must_have_modalities": ["text", "asr"],
                        },
                    },
                }
            ],
            "user_gold": {
                "u1": {
                    "harmful": False,
                    "persistence_label": "low",
                    "trajectory": "insufficient_temporal_evidence",
                    "roles": ["originator"],
                },
                "u2": {
                    "harmful": False,
                    "persistence_label": "low",
                    "trajectory": "insufficient_temporal_evidence",
                    "roles": ["bridge_relay"],
                },
            },
            "community_gold": {
                "component_0": {
                    "collective_harm": False,
                    "amplification": False,
                    "harm_types": [],
                    "roles": ["amplifier", "bridge_relay", "originator", "participant"],
                    "claims": ["url1"],
                    "key_accounts": ["u1"],
                    "allow_runtime_needs_review": True,
                }
            },
            "thresholds": {
                "post": {
                    "claim_link_accuracy": 1.0,
                    "stance_accuracy": 1.0,
                    "harm_label_accuracy": 1.0,
                    "harm_type_micro_f1": 0.0,
                    "evidence_presence_rate": 1.0,
                },
                "user": {
                    "harmful_flag_accuracy": 1.0,
                    "persistence_label_accuracy": 1.0,
                    "trajectory_accuracy": 1.0,
                    "role_micro_f1": 1.0,
                    "representative_evidence_rate": 1.0,
                },
                "community": {
                    "collective_harm_accuracy": 1.0,
                    "amplification_label_accuracy": 1.0,
                    "harm_type_micro_f1": 0.0,
                    "role_micro_f1": 1.0,
                    "claim_coverage_rate": 1.0,
                    "key_account_evidence_rate": 1.0,
                },
            },
        }

        report = asyncio.run(
            risk_service.assess_risk(
                platform="mock_weibo",
                event_id="test_event",
                db=None,
                gate_dataset=gate_dataset,
            )
        )

        suite = report["review_harmfulness"]["gate_suite"]
        assert suite["dataset_contract"]["provided"] is True
        assert suite["dataset_contract"]["metadata"]["dataset_id"] == "service-review-smoke"
        assert suite["dataset_contract"]["counts"] == {
            "post_cases": 1,
            "user_gold": 2,
            "community_gold": 1,
        }
        assert suite["summary"]["executed_gates"] == 3
        assert suite["summary"]["skipped_gates"] == 0
        assert suite["capability_boundary"]["evaluation_harness_only"] is True
        assert suite["capability_boundary"]["trained_post_model"] is False
        assert suite["capability_boundary"]["trained_user_encoder"] is False
        assert suite["capability_boundary"]["trained_graph_model"] is False
        assert suite["gates"]["post_gate"]["summary"]["evaluated_posts"] == 2
        assert suite["gates"]["post_gate"]["summary"]["review_items"] == 2
        assert suite["gates"]["user_gate"]["summary"]["evaluated_accounts"] == 2
        assert suite["gates"]["community_gate"]["summary"]["evaluated_communities"] == 1


class TestRiskAPIReviewIntegration:
    def test_gate_dataset_contract_api_returns_machine_readable_spec(self):
        response = asyncio.run(
            risk_api.get_gate_dataset_contract(
                _current_user=type("User", (), {"id": 42})(),
            )
        )

        contract = response["data"]
        assert response["code"] == 0
        assert contract["contract_version"] == "review-gate-dataset-v1"
        assert contract["usage_policy"]["uses_gold_for_training"] is False
        assert contract["usage_policy"]["runtime_gold_generation"] is False
        assert contract["usage_policy"]["default_persistence"] is False
        assert contract["leakage_policy"]["no_runtime_derived_gold"] is True
        assert "metadata" in contract["top_level_fields"]
        assert set(contract["layer_contracts"]) == {"community_gate", "post_gate", "user_gate"}

    def test_gate_dataset_validate_api_does_not_run_risk_or_persist(self):
        response = asyncio.run(
            risk_api.validate_gate_dataset(
                request=risk_api.ReviewGateDatasetValidationRequest(
                    gate_dataset={
                        "metadata": {
                            "dataset_id": "api-contract-validation",
                            "version": "v1",
                            "source": "api_fixture",
                            "label_policy": "offline labels only",
                            "control_set_notes": "same-window controls",
                        },
                        "post_cases": [],
                        "user_gold": {"u1": {"harmful": False}},
                    }
                ),
                _current_user=type("User", (), {"id": 42})(),
            )
        )

        data = response["data"]
        assert response["code"] == 0
        assert data["contract_version"] == "review-gate-dataset-v1"
        assert data["valid"] is True
        assert data["layer_coverage"] == {
            "post_gate": False,
            "user_gate": True,
            "community_gate": False,
        }
        assert data["counts"] == {
            "post_cases": 0,
            "user_gold": 1,
            "community_gold": 0,
        }
        assert data["manifest"]["contains_gold_payload"] is False
        assert data["manifest"]["counts"] == data["counts"]
        assert len(data["manifest"]["dataset_fingerprint"]) == 64
        assert data["usage_policy"]["uses_gold_for_training"] is False
        assert data["usage_policy"]["default_persistence"] is False

    def test_assess_risk_api_returns_review_harmfulness(self):
        calls = {}
        expected_report = {
            "report_id": "r1",
            "event_id": "event-api",
            "platform": "mock_weibo",
            "post_semantics": {"analysis_scope": {"normalized_posts": 2}},
            "review_harmfulness": {
                "post_level": {"analysis_scope": {"normalized_posts": 2}},
                "user_level": {"summary": {"account_count": 2}},
                "community_level": {"summary": {"community_count": 1}},
                "global_summary": {"review_harm_risk_level": "medium"},
                "review_queue": {
                    "summary": {"review_items": 1, "agent_tasks": 1},
                    "capability_boundary": {"live_llm_or_rag": False},
                },
                "review_execution": {
                    "summary": {"review_items_executed": 1},
                    "capability_boundary": {"live_llm_or_external_rag": False},
                },
                "graph_export": {
                    "summary": {"node_count": 4, "edge_count": 3},
                    "capability_boundary": {"trained_graph_model": False},
                },
                "gate_suite": {
                    "summary": {"executed_gates": 0, "skipped_gates": 3},
                    "capability_boundary": {"evaluation_harness_only": True},
                    "skipped_gates": {
                        "post_gate": {"reason": "missing_post_cases"},
                        "user_gate": {"reason": "missing_user_gold"},
                        "community_gate": {"reason": "missing_community_gold"},
                    },
                },
            },
        }

        class FakeService:
            async def legacy_assess_risk(self, **kwargs):
                calls.update(kwargs)
                return expected_report

        response = asyncio.run(
            risk_api.assess_risk(
                platform="mock_weibo",
                event_id="event-api",
                time_window=120,
                min_participation=3,
                edge_weight=0.7,
                current_user=type("User", (), {"id": 42})(),
                service=FakeService(),
            )
        )

        assert response["code"] == 0
        assert response["data"]["review_harmfulness"]["global_summary"]["review_harm_risk_level"] == "medium"
        assert response["data"]["review_harmfulness"]["review_queue"]["summary"]["review_items"] == 1
        assert response["data"]["review_harmfulness"]["review_execution"]["summary"]["review_items_executed"] == 1
        assert response["data"]["review_harmfulness"]["graph_export"]["summary"]["node_count"] == 4
        assert response["data"]["review_harmfulness"]["gate_suite"]["summary"]["skipped_gates"] == 3
        assert response["data"]["review_harmfulness"]["gate_suite"]["capability_boundary"]["evaluation_harness_only"] is True
        assert calls["platform"] == "mock_weibo"
        assert calls["event_id"] == "event-api"
        assert set(calls) == {"platform", "event_id"}

    def test_run_agent_review_api_maps_to_case_review_request(self):
        calls = {}
        committed = {"value": False}

        class FakeDB:
            async def commit(self):
                committed["value"] = True

        class FakeService:
            db = FakeDB()

            async def legacy_request_review(self, **kwargs):
                calls.update(kwargs)
                return {"case_id": "case-r1", "action_required": "review_available"}

        response = asyncio.run(
            risk_api.run_agent_review(
                request=risk_api.ReviewAgentReviewRunRequest(
                    report_id="r1",
                    selected_post_ids=["p1"],
                    selected_tree_ids=["tree-1"],
                    agent_names=["PostHarmAgent"],
                    enable_active_retrieval=True,
                    enable_light_debate=True,
                    policy_id="review-policy-test",
                    retrieval_top_k=5,
                ),
                current_user=type("User", (), {"id": 42})(),
                service=FakeService(),
            )
        )

        assert response["code"] == 0
        assert response["data"] == {"case_id": "case-r1", "action_required": "review_available"}
        assert calls["report_id"] == "r1"
        assert calls["evidence_refs"] == ["p1", "tree-1"]
        assert calls["actor"].id == 42
        assert committed["value"] is True

    def test_review_policy_optimize_and_get_api(self, monkeypatch):
        stored = {
            "policy_id": "review-policy-api",
            "policy": {"review_threshold": 0.52},
            "optimization": {"validation_cases": 1},
        }
        calls = {}

        def mock_optimize(dataset_manifest):
            calls["dataset_manifest"] = dataset_manifest
            return stored

        def mock_get(policy_id):
            calls["policy_id"] = policy_id
            return stored

        monkeypatch.setattr(risk_api.risk_service, "optimize_review_policy", mock_optimize)
        monkeypatch.setattr(risk_api.risk_service, "get_review_policy", mock_get)

        response = asyncio.run(
            risk_api.optimize_review_policy(
                request=risk_api.ReviewPolicyOptimizeRequest(
                    dataset_manifest={"splits": {"validation": [{"case_id": "v1"}]}}
                ),
                _current_user=type("User", (), {"id": 42})(),
            )
        )
        detail = asyncio.run(
            risk_api.get_review_policy(
                policy_id="review-policy-api",
                _current_user=type("User", (), {"id": 42})(),
            )
        )

        assert response["code"] == 0
        assert response["data"]["policy_id"] == "review-policy-api"
        assert detail["data"]["optimization"]["validation_cases"] == 1
        assert calls["dataset_manifest"]["splits"]["validation"][0]["case_id"] == "v1"
        assert calls["policy_id"] == "review-policy-api"

    def test_assess_gate_suite_api_accepts_dataset_body_without_persistence(self):
        calls = {}
        gate_dataset = {
            "metadata": {
                "dataset_id": "api-gate-suite-smoke",
                "version": "v1",
                "source": "api_fixture",
                "label_policy": "offline evaluation only",
                "control_set_notes": "body contract smoke test",
            },
            "post_cases": [],
            "user_gold": {"u1": {"harmful": False}},
            "community_gold": {},
        }
        expected_report = {
            "report_id": "r-gate",
            "event_id": "event-api",
            "platform": "mock_weibo",
            "assessed_at": "2026-06-28T00:00:00+00:00",
            "scores": {"risk_level": "medium"},
            "post_semantics": {"analysis_scope": {"normalized_posts": 2}},
            "review_harmfulness": {
                "global_summary": {"review_harm_risk_level": "medium"},
                "gate_suite": {
                    "dataset_contract": {
                        "provided": True,
                        "metadata": {"dataset_id": "api-gate-suite-smoke"},
                        "counts": {"post_cases": 0, "user_gold": 1, "community_gold": 0},
                        "manifest": {
                            "contains_gold_payload": False,
                            "dataset_fingerprint": "a" * 64,
                            "counts": {"post_cases": 0, "user_gold": 1, "community_gold": 0},
                        },
                    },
                    "summary": {"executed_gates": 1, "skipped_gates": 2},
                    "capability_boundary": {
                        "evaluation_harness_only": True,
                        "uses_gold_for_training": False,
                        "live_llm_or_rag": False,
                    },
                },
            },
        }

        class FakeService:
            async def legacy_assess_risk(self, **kwargs):
                calls.update(kwargs)
                return expected_report

        response = asyncio.run(
            risk_api.assess_gate_suite(
                request=risk_api.ReviewGateSuiteRequest(
                    platform="mock_weibo",
                    event_id="event-api",
                    time_window=120,
                    min_participation=3,
                    edge_weight=0.7,
                    gate_dataset=gate_dataset,
                ),
                current_user=type("User", (), {"id": 42})(),
                service=FakeService(),
            )
        )

        assert response["code"] == 0
        assert response["data"]["report_context"]["event_id"] == "event-api"
        assert response["data"]["report_context"]["risk_level"] == "medium"
        assert response["data"]["persistence"]["persisted"] is False
        assert response["data"]["gate_suite"]["dataset_contract"]["provided"] is True
        assert response["data"]["gate_suite"]["dataset_contract"]["metadata"]["dataset_id"] == "api-gate-suite-smoke"
        assert response["data"]["gate_suite"]["summary"]["executed_gates"] == 1
        assert response["data"]["review_harmfulness"]["gate_suite"] == response["data"]["gate_suite"]
        assert calls["platform"] == "mock_weibo"
        assert calls["event_id"] == "event-api"
        assert set(calls) == {"platform", "event_id"}
