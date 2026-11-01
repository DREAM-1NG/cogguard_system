"""阶段检测器：战役生命周期建模与危险转换预测。

将协同操纵事件建模为 5 个阶段：
  seed → synchronize → breakout → saturation → regeneration

基于滑动窗口特征提取 + 规则分类 + logistic hazard 估计，
输出当前阶段、置信度、各转换风险和 breakout 预估时间。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

import yaml

from app.core.review.evidence_builder import EvidencePack, WindowFeatures, _burstiness

# 阶段常量
PHASES = ("seed", "synchronize", "breakout", "saturation", "regeneration")

# 加载配置
_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "risk_config.yaml"


def _load_phase_config() -> dict:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f).get("phase", {})
    return {}


@dataclass
class PhaseResult:
    """阶段检测结果。"""
    current_phase: str = "seed"
    phase_confidence: float = 0.5
    hazard_scores: dict[str, float] = field(default_factory=dict)
    time_to_breakout_estimate: float | None = None
    feature_history: list[WindowFeatures] = field(default_factory=list)
    window_count: int = 0


def _sigmoid(x: float) -> float:
    """数值稳定的 sigmoid 函数。"""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    ex = math.exp(x)
    return ex / (1.0 + ex)


def classify_phase(features: WindowFeatures, cfg: dict | None = None) -> tuple[str, float]:
    """根据窗口特征判定当前阶段。

    Returns
    -------
    (phase_name, confidence)
    """
    if cfg is None:
        cfg = _load_phase_config()

    cd = features.coordination_density
    burst = features.burstiness
    br = features.bridge_ratio
    spread = features.cross_cluster_spread
    ae_delta = features.automation_entropy_delta

    seed_cfg = cfg.get("seed", {})
    sync_cfg = cfg.get("synchronize", {})
    brk_cfg = cfg.get("breakout", {})
    sat_cfg = cfg.get("saturation", {})
    regen_cfg = cfg.get("regeneration", {})

    # 按优先级匹配（breakout > regeneration > saturation > synchronize > seed）
    if burst >= brk_cfg.get("burstiness_min", 2.0) and br >= brk_cfg.get("bridge_ratio_min", 0.1):
        confidence = min(0.5 + 0.25 * (burst / 3) + 0.25 * (br / 0.3), 0.99)
        return "breakout", confidence

    if ae_delta >= regen_cfg.get("automation_entropy_delta_min", 0.3):
        confidence = min(0.5 + 0.5 * (ae_delta / 1.0), 0.95)
        return "regeneration", confidence

    if burst < sat_cfg.get("burstiness_max", 1.5) and spread >= sat_cfg.get("cross_cluster_spread_min", 3):
        confidence = min(0.5 + 0.3 * (spread / 5), 0.95)
        return "saturation", confidence

    if cd >= sync_cfg.get("coordination_density_min", 0.05) and burst < sync_cfg.get("burstiness_max", 2.0):
        confidence = min(0.5 + 0.3 * (cd / 0.2) + 0.2 * (burst / 2), 0.95)
        return "synchronize", confidence

    if cd < seed_cfg.get("coordination_density_max", 0.05) and burst < seed_cfg.get("burstiness_max", 1.0):
        confidence = min(0.6 + 0.2 * (1 - cd / 0.05), 0.95)
        return "seed", confidence

    return "synchronize", 0.5


def estimate_hazard(features: WindowFeatures, cfg: dict | None = None) -> dict[str, float]:
    """估计各阶段转换的风险概率。

    使用 logistic 模型：P(transition) = sigmoid(w · features + b)
    """
    if cfg is None:
        cfg = _load_phase_config()

    hw = cfg.get("hazard_weights", {})
    w_burst = hw.get("burstiness", 1.2)
    w_bridge = hw.get("bridge_ratio", 2.0)
    w_auto = hw.get("high_automation_ratio", 1.5)
    w_coord = hw.get("coordination_density", 1.8)
    bias = hw.get("bias", -3.0)

    logit = (
        w_burst * features.burstiness
        + w_bridge * features.bridge_ratio
        + w_auto * features.high_automation_ratio
        + w_coord * features.coordination_density
        + bias
    )

    hazard_breakout = _sigmoid(logit)
    # 其他转换使用衰减版本
    hazard_saturation = _sigmoid(logit * 0.6)
    hazard_regeneration = _sigmoid(logit * 0.3)

    return {
        "breakout": round(hazard_breakout, 4),
        "saturation": round(hazard_saturation, 4),
        "regeneration": round(hazard_regeneration, 4),
    }


def detect_phase(evidence_pack: EvidencePack) -> PhaseResult:
    """执行阶段检测。

    Parameters
    ----------
    evidence_pack : EvidencePack
        由 evidence_builder.build_evidence_pack() 构建的证据包

    Returns
    -------
    PhaseResult
        包含当前阶段、置信度、转换风险和 breakout 预估时间
    """
    cfg = _load_phase_config()
    features = evidence_pack.features

    current_phase, confidence = classify_phase(features, cfg)
    hazard_scores = estimate_hazard(features, cfg)

    # 估计 breakout 时间（秒）：基于 hazard 概率的简单估计
    # 如果 hazard_breakout 高，预估时间短
    h_breakout = hazard_scores.get("breakout", 0)
    time_to_breakout = None
    if current_phase in ("seed", "synchronize") and h_breakout > 0.1:
        # 指数衰减模型：t = -ln(1-h) / lambda，简化为反比关系
        time_to_breakout = max(300, (1 - h_breakout) / max(h_breakout, 0.01) * 3600)

    return PhaseResult(
        current_phase=current_phase,
        phase_confidence=round(confidence, 4),
        hazard_scores=hazard_scores,
        time_to_breakout_estimate=round(time_to_breakout, 1) if time_to_breakout else None,
        feature_history=[features],
        window_count=1,
    )
