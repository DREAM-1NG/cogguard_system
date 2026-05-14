"""风险研判模块单元测试。

测试核心模块：evidence_builder, phase_detector, ds_fusion, disarm_scorer, report_builder。
不依赖数据库，使用 mock 数据。
"""

import math

import pytest

from app.core.risk.evidence_builder import (
    EvidencePack,
    WindowFeatures,
    build_evidence_pack,
    _gini,
    _shannon_entropy,
    _burstiness,
)
from app.core.risk.phase_detector import (
    PhaseResult,
    classify_phase,
    estimate_hazard,
    detect_phase,
)
from app.core.risk.ds_fusion import (
    FusionResult,
    dempster_combine,
    mass_to_belief_interval,
    coordination_mass,
    propagation_mass,
    account_mass,
    fuse_evidence,
)
from app.core.risk.disarm_scorer import (
    map_evidence_to_techniques,
    score_attack_path,
    predict_next_techniques,
    recommend_countermeasures,
    score_attack_path_full,
)
from app.core.risk.report_builder import build_report


# ===================================================================
# Fixtures: mock upstream data
# ===================================================================

def _mock_coord_data(coordinated_accounts=15, coordinated_edges=20):
    return {
        "network": {
            "nodes": [{"id": f"u{i}"} for i in range(coordinated_accounts)],
            "edges": [
                {"source": "u0", "target": f"u{i}", "weight": 3,
                 "avg_time_delta": 10, "edge_symmetry_score": 0.7}
                for i in range(1, min(coordinated_accounts, 10))
            ],
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
        from app.core.risk.ds_fusion import BeliefInterval
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

        report = build_report(
            event_id="test_event",
            platform="mock_weibo",
            evidence_pack=pack,
            phase_result=phase,
            fusion_result=fusion,
            disarm_result=disarm,
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
