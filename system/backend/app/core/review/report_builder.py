"""报告构建器：组装所有分析结果为最终 JSON 报告。"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from app.core.review.disarm_scorer import DisarmResult
from app.core.review.ds_fusion import FusionResult
from app.core.review.evidence_builder import EvidencePack
from app.core.review.phase_detector import PhaseResult

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "risk_config.yaml"


def _load_scoring_config() -> dict:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f).get("scoring", {})
    return {}


def _risk_level(score: float, cfg: dict) -> str:
    levels = cfg.get("levels", {})
    if score <= levels.get("low_max", 25):
        return "low"
    if score <= levels.get("medium_max", 50):
        return "medium"
    if score <= levels.get("high_max", 75):
        return "high"
    return "critical"


def _dimension_score(belief: float, plausibility: float) -> float:
    """从信念区间计算 0-100 分数。"""
    return round((belief * 0.7 + plausibility * 0.3) * 100, 2)


def _build_risk_factors(
    pack: EvidencePack,
    phase: PhaseResult,
    fusion: FusionResult,
) -> dict[str, list[str]]:
    """生成可解释的风险因子列表。"""
    factors: dict[str, list[str]] = {
        "manipulation_factors": [],
        "authenticity_factors": [],
        "impact_factors": [],
    }
    f = pack.features

    # 操纵性因子
    if pack.coordinated_accounts > 5:
        factors["manipulation_factors"].append(
            f"检测到 {pack.coordinated_accounts} 个协同账户"
        )
    if f.edge_symmetry_mean > 0.5:
        factors["manipulation_factors"].append(
            f"边对称性均值 {f.edge_symmetry_mean:.2f}（高度双向协同）"
        )
    if f.coordination_density > 0.1:
        factors["manipulation_factors"].append(
            f"协同密度 {f.coordination_density:.3f}"
        )

    # 行为真实性因子
    if f.high_automation_ratio > 0.3:
        factors["authenticity_factors"].append(
            f"高自动化账户占比 {f.high_automation_ratio:.0%}"
        )
    if f.regularity_mean > 0.7:
        factors["authenticity_factors"].append(
            f"平均规律性 {f.regularity_mean:.2f}（疑似机器行为）"
        )

    # 影响力因子
    if f.burstiness > 2.0:
        factors["impact_factors"].append(
            f"突发性指数 {f.burstiness:.2f}（快速扩散）"
        )
    if f.bridge_ratio > 0.1:
        factors["impact_factors"].append(
            f"桥接节点占比 {f.bridge_ratio:.0%}（跨群传播）"
        )
    if f.cross_cluster_spread > 3:
        factors["impact_factors"].append(
            f"跨集群传播范围 {f.cross_cluster_spread} 个组件"
        )

    # 阶段相关因子
    if phase.current_phase == "breakout":
        factors["impact_factors"].append("当前处于 breakout 阶段（快速扩散期）")
    h_breakout = phase.hazard_scores.get("breakout", 0)
    if h_breakout > 0.5:
        factors["impact_factors"].append(
            f"breakout 转换风险 {h_breakout:.0%}"
        )

    # 冲突因子
    if fusion.escalation_required:
        factors["manipulation_factors"].append(
            f"证据冲突质量 {fusion.conflict_mass:.2f}（需人工复核）"
        )

    return factors


def _build_recommendations(
    phase: PhaseResult,
    fusion: FusionResult,
    disarm: DisarmResult,
    risk_level: str,
) -> list[dict]:
    """生成处置建议。"""
    recs: list[dict] = []

    if fusion.escalation_required:
        recs.append({
            "priority": "high",
            "action": "人工复核",
            "reason": f"证据冲突质量 {fusion.conflict_mass:.2f} 超过阈值，需分析师介入",
        })

    if risk_level == "critical":
        recs.append({
            "priority": "critical",
            "action": "立即启动应急响应",
            "reason": "综合风险评分达到 critical 级别",
        })

    if phase.current_phase in ("synchronize",) and phase.hazard_scores.get("breakout", 0) > 0.5:
        recs.append({
            "priority": "high",
            "action": "预防性干预",
            "reason": f"当前处于同步阶段，breakout 风险 {phase.hazard_scores['breakout']:.0%}",
        })

    # 添加 DISARM 反制建议
    for cm in disarm.countermeasures[:3]:
        recs.append({
            "priority": cm.priority,
            "action": cm.action,
            "reason": f"针对预测技术 {cm.technique_id}（概率 {cm.probability:.0%}）",
        })

    return recs


def build_report(
    event_id: str,
    platform: str,
    evidence_pack: EvidencePack,
    phase_result: PhaseResult,
    fusion_result: FusionResult,
    disarm_result: DisarmResult,
    post_semantics: dict | None = None,
    review_harmfulness: dict | None = None,
) -> dict:
    """组装完整风险评估报告。"""
    cfg = _load_scoring_config()

    # 维度分数
    manip_score = _dimension_score(fusion_result.manipulation.belief, fusion_result.manipulation.plausibility)
    auth_score = _dimension_score(fusion_result.authenticity.belief, fusion_result.authenticity.plausibility)
    impact_score = _dimension_score(fusion_result.impact.belief, fusion_result.impact.plausibility)

    # 综合分数
    overall = (
        manip_score * cfg.get("manipulation_weight", 0.40)
        + auth_score * cfg.get("authenticity_weight", 0.35)
        + impact_score * cfg.get("impact_weight", 0.25)
    )
    overall = round(overall, 2)
    level = _risk_level(overall, cfg)

    risk_factors = _build_risk_factors(evidence_pack, phase_result, fusion_result)
    recommendations = _build_recommendations(phase_result, fusion_result, disarm_result, level)

    return {
        "report_id": str(uuid.uuid4()),
        "event_id": event_id,
        "platform": platform,
        "assessed_at": datetime.now(timezone.utc).isoformat(),
        "phase": {
            "current_phase": phase_result.current_phase,
            "phase_confidence": phase_result.phase_confidence,
            "hazard_scores": phase_result.hazard_scores,
            "time_to_breakout_estimate": phase_result.time_to_breakout_estimate,
            "window_count": phase_result.window_count,
        },
        "scores": {
            "overall_risk_score": overall,
            "risk_level": level,
            "manipulation": {
                "score": manip_score,
                "belief": fusion_result.manipulation.belief,
                "plausibility": fusion_result.manipulation.plausibility,
            },
            "authenticity": {
                "score": auth_score,
                "belief": fusion_result.authenticity.belief,
                "plausibility": fusion_result.authenticity.plausibility,
            },
            "impact": {
                "score": impact_score,
                "belief": fusion_result.impact.belief,
                "plausibility": fusion_result.impact.plausibility,
            },
        },
        "fusion": {
            "conflict_mass": fusion_result.conflict_mass,
            "escalation_required": fusion_result.escalation_required,
            "per_source_masses": fusion_result.per_source_masses,
        },
        "evidence": {
            "coordination": {
                "coordinated_accounts": evidence_pack.coordinated_accounts,
                "coordinated_pairs": evidence_pack.coordinated_pairs,
                "coordination_density": round(evidence_pack.features.coordination_density, 4),
                "edge_symmetry_mean": round(evidence_pack.features.edge_symmetry_mean, 4),
                "component_count": evidence_pack.features.component_count,
                "max_component_size": evidence_pack.features.max_component_size,
            },
            "propagation": {
                "total_accounts": evidence_pack.total_accounts,
                "bridge_ratio": round(evidence_pack.features.bridge_ratio, 4),
                "burstiness": round(evidence_pack.features.burstiness, 4),
                "cross_cluster_spread": evidence_pack.features.cross_cluster_spread,
                "originator_count": evidence_pack.originator_count,
                "amplifier_count": evidence_pack.amplifier_count,
            },
            "accounts": {
                "high_automation_ratio": round(evidence_pack.features.high_automation_ratio, 4),
                "automation_entropy": round(evidence_pack.features.automation_entropy, 4),
                "regularity_mean": round(evidence_pack.features.regularity_mean, 4),
                "avg_automation_score": round(evidence_pack.avg_automation_score, 2),
            },
        },
        "claims": evidence_pack.claims[:20],
        "post_semantics": post_semantics,
        "review_harmfulness": review_harmfulness,
        "disarm_analysis": {
            "observed_techniques": [
                {
                    "technique_id": t.technique_id,
                    "tactic": t.tactic,
                    "name": t.name,
                    "belief": t.belief,
                    "evidence": t.evidence,
                }
                for t in disarm_result.observed_techniques
            ],
            "attack_path": {
                "depth": disarm_result.path_score.depth,
                "breadth": disarm_result.path_score.breadth,
                "completeness": disarm_result.path_score.completeness,
                "score": disarm_result.path_score.score,
            },
            "predicted_next": [
                {
                    "technique_id": p.technique_id,
                    "name": p.name,
                    "probability": p.probability,
                }
                for p in disarm_result.predicted_next
            ],
            "countermeasures": [
                {
                    "technique_id": c.technique_id,
                    "action": c.action,
                    "priority": c.priority,
                    "probability": c.probability,
                }
                for c in disarm_result.countermeasures
            ],
        },
        "risk_factors": risk_factors,
        "recommendations": recommendations,
    }
