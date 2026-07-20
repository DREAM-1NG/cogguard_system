"""Dempster-Shafer 证据融合：矛盾感知的多源证据组合。

将协同、传播、账户三个上游模块的证据转换为信念质量函数，
通过 Dempster 组合规则融合，输出信念区间和冲突检测结果。

关键创新：阶段感知质量调整（phase-conditioned mass adjustment）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.core.review.evidence_builder import EvidencePack
from app.core.review.phase_detector import PhaseResult

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "risk_config.yaml"


def _load_fusion_config() -> dict:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f).get("fusion", {})
    return {}


@dataclass
class BeliefInterval:
    """信念区间：[belief, plausibility]。"""
    belief: float = 0.0
    plausibility: float = 0.0


@dataclass
class FusionResult:
    """D-S 融合结果。"""
    manipulation: BeliefInterval = field(default_factory=BeliefInterval)
    authenticity: BeliefInterval = field(default_factory=BeliefInterval)
    impact: BeliefInterval = field(default_factory=BeliefInterval)
    overall: BeliefInterval = field(default_factory=BeliefInterval)
    conflict_mass: float = 0.0
    escalation_required: bool = False
    per_source_masses: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# 质量分配函数
# ---------------------------------------------------------------------------

def _build_mass(strength: float, risk_scale: float, safe_scale: float, cap: float = 0.95) -> dict[str, float]:
    """从强度值构建三元质量函数 {risk, safe, uncertain}。"""
    strength = min(max(strength, 0.0), cap)
    m_risk = strength * risk_scale
    m_safe = (1 - strength) * safe_scale
    m_uncertain = max(1.0 - m_risk - m_safe, 0.0)
    return {"risk": m_risk, "safe": m_safe, "uncertain": m_uncertain}


def coordination_mass(pack: EvidencePack, cfg: dict) -> dict[str, float]:
    """协同模块 → 操纵性质量函数。"""
    c = cfg.get("coordination", {})
    f = pack.features
    strength = (
        c.get("density_weight", 0.4) * min(f.coordination_density, 1.0)
        + c.get("symmetry_weight", 0.3) * f.edge_symmetry_mean
        + c.get("ratio_weight", 0.3) * f.coordinated_account_ratio
    )
    return _build_mass(strength, c.get("risk_scale", 0.9), c.get("safe_scale", 0.5), cfg.get("mass_cap", 0.95))


def propagation_mass(pack: EvidencePack, cfg: dict) -> dict[str, float]:
    """传播模块 → 影响力质量函数。"""
    c = cfg.get("propagation", {})
    f = pack.features
    burst_norm = c.get("burstiness_norm", 5.0)
    spread_norm = c.get("spread_norm", 10.0)
    strength = (
        c.get("bridge_weight", 0.35) * min(f.bridge_ratio, 1.0)
        + c.get("burstiness_weight", 0.35) * min(f.burstiness / burst_norm, 1.0)
        + c.get("spread_weight", 0.3) * min(f.cross_cluster_spread / spread_norm, 1.0)
    )
    return _build_mass(strength, c.get("risk_scale", 0.85), c.get("safe_scale", 0.4), cfg.get("mass_cap", 0.95))


def account_mass(pack: EvidencePack, cfg: dict) -> dict[str, float]:
    """账户模块 → 行为真实性质量函数。"""
    c = cfg.get("accounts", {})
    f = pack.features
    entropy_max = c.get("entropy_max", 2.3)
    strength = (
        c.get("automation_weight", 0.5) * f.high_automation_ratio
        + c.get("entropy_weight", 0.3) * (1 - min(f.automation_entropy / entropy_max, 1.0))
        + c.get("regularity_weight", 0.2) * f.regularity_mean
    )
    return _build_mass(strength, c.get("risk_scale", 0.85), c.get("safe_scale", 0.5), cfg.get("mass_cap", 0.95))


# ---------------------------------------------------------------------------
# 阶段调制
# ---------------------------------------------------------------------------

def apply_phase_adjustment(mass: dict[str, float], phase: str, cfg: dict) -> dict[str, float]:
    """根据战役阶段调整质量分配。"""
    multipliers = cfg.get("phase_multipliers", {})
    mult = multipliers.get(phase, 0.8)

    adjusted_risk = mass["risk"] * mult
    adjusted_safe = mass["safe"] * mult
    adjusted_uncertain = 1.0 - adjusted_risk - adjusted_safe
    return {
        "risk": adjusted_risk,
        "safe": adjusted_safe,
        "uncertain": max(adjusted_uncertain, 0.0),
    }


# ---------------------------------------------------------------------------
# Dempster 组合规则
# ---------------------------------------------------------------------------

def dempster_combine(m1: dict[str, float], m2: dict[str, float]) -> tuple[dict[str, float], float]:
    """Dempster 组合规则：合并两个质量函数。

    Returns
    -------
    (combined_mass, conflict_mass)
    """
    # 定义焦元交集规则：risk∩risk=risk, safe∩safe=safe, uncertain∩X=X, risk∩safe=∅
    intersection_map = {
        ("risk", "risk"): "risk",
        ("safe", "safe"): "safe",
        ("uncertain", "risk"): "risk",
        ("risk", "uncertain"): "risk",
        ("uncertain", "safe"): "safe",
        ("safe", "uncertain"): "safe",
        ("uncertain", "uncertain"): "uncertain",
        ("risk", "safe"): None,   # 冲突
        ("safe", "risk"): None,   # 冲突
    }

    combined: dict[str, float] = {}
    conflict = 0.0

    for h1, v1 in m1.items():
        for h2, v2 in m2.items():
            product = v1 * v2
            intersection = intersection_map.get((h1, h2))
            if intersection is None:
                conflict += product
            else:
                combined[intersection] = combined.get(intersection, 0.0) + product

    # 归一化
    norm = 1.0 - conflict
    if norm > 0:
        combined = {k: v / norm for k, v in combined.items()}
    else:
        # 完全冲突：退化为均匀分布
        combined = {"risk": 0.33, "safe": 0.33, "uncertain": 0.34}
        conflict = 1.0

    return combined, conflict


def mass_to_belief_interval(mass: dict[str, float]) -> BeliefInterval:
    """从质量函数计算信念区间。"""
    belief = mass.get("risk", 0.0)
    plausibility = belief + mass.get("uncertain", 0.0)
    return BeliefInterval(
        belief=round(min(belief, 1.0), 4),
        plausibility=round(min(plausibility, 1.0), 4),
    )


# ---------------------------------------------------------------------------
# 主融合函数
# ---------------------------------------------------------------------------

def fuse_evidence(evidence_pack: EvidencePack, phase_result: PhaseResult) -> FusionResult:
    """执行 D-S 证据融合。

    Parameters
    ----------
    evidence_pack : EvidencePack
        统一证据包
    phase_result : PhaseResult
        阶段检测结果（用于阶段调制）
    """
    cfg = _load_fusion_config()
    phase = phase_result.current_phase

    # 1. 计算各源质量函数
    m_coord = coordination_mass(evidence_pack, cfg)
    m_prop = propagation_mass(evidence_pack, cfg)
    m_acct = account_mass(evidence_pack, cfg)

    # 2. 阶段调制
    m_coord = apply_phase_adjustment(m_coord, phase, cfg)
    m_prop = apply_phase_adjustment(m_prop, phase, cfg)
    m_acct = apply_phase_adjustment(m_acct, phase, cfg)

    # 3. 逐步组合（coord + prop → combined → + acct）
    combined_12, conflict_12 = dempster_combine(m_coord, m_prop)
    combined_all, conflict_all = dempster_combine(combined_12, m_acct)

    # 总冲突 = 1 - (1-k12)(1-k_all)
    total_conflict = 1 - (1 - conflict_12) * (1 - conflict_all)

    # 4. 冲突检测
    threshold = cfg.get("conflict_escalation_threshold", 0.3)
    escalation = total_conflict > threshold

    # 5. 各维度信念区间
    manipulation_bi = mass_to_belief_interval(m_coord)
    impact_bi = mass_to_belief_interval(m_prop)
    authenticity_bi = mass_to_belief_interval(m_acct)
    overall_bi = mass_to_belief_interval(combined_all)

    return FusionResult(
        manipulation=manipulation_bi,
        authenticity=authenticity_bi,
        impact=impact_bi,
        overall=overall_bi,
        conflict_mass=round(total_conflict, 4),
        escalation_required=escalation,
        per_source_masses={
            "coordination": {k: round(v, 4) for k, v in m_coord.items()},
            "propagation": {k: round(v, 4) for k, v in m_prop.items()},
            "accounts": {k: round(v, 4) for k, v in m_acct.items()},
            "combined": {k: round(v, 4) for k, v in combined_all.items()},
        },
    )
