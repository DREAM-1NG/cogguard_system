"""DISARM 攻击路径评分器：将 MITRE ATT&CK 攻击图分析迁移到 DISARM。

基于 DISARM Red Framework 构建技术转换图，将上游证据映射到
观测技术，评分攻击路径深度/广度/完整度，预测下一步并推荐反制措施。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from app.core.review.ds_fusion import FusionResult
from app.core.review.evidence_builder import EvidencePack
from app.core.review.phase_detector import PhaseResult

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "risk_config.yaml"


def _load_disarm_config() -> dict:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f).get("disarm", {})
    return {}


# ---------------------------------------------------------------------------
# DISARM 技术知识库
# ---------------------------------------------------------------------------

TECHNIQUE_INFO: dict[str, dict] = {
    "T0097": {"tactic": "TA06", "name": "Create Fake Experts"},
    "T0098": {"tactic": "TA06", "name": "Establish Legitimacy"},
    "T0100": {"tactic": "TA07", "name": "Co-opt Trusted Sources"},
    "T0101": {"tactic": "TA08", "name": "Create Fake Social Media Accounts"},
    "T0102": {"tactic": "TA08", "name": "Develop Inauthentic Networks"},
    "T0103": {"tactic": "TA09", "name": "Post Content"},
    "T0104": {"tactic": "TA09", "name": "Social Media Sharing"},
    "T0105": {"tactic": "TA10", "name": "Coordinate Activity"},
    "T0106": {"tactic": "TA10", "name": "Amplify Existing Narrative"},
    "T0107": {"tactic": "TA10", "name": "Manipulate Platform Algorithms"},
    "T0049": {"tactic": "TA10", "name": "Flood Information Space"},
    "T0108": {"tactic": "TA11", "name": "Encourage Real-World Action"},
}

# 技术转换图：有向边表示可能的攻击路径推进
TRANSITIONS: dict[str, list[str]] = {
    "T0101": ["T0102", "T0103"],
    "T0102": ["T0105", "T0103"],
    "T0103": ["T0104", "T0106"],
    "T0104": ["T0105", "T0106"],
    "T0105": ["T0106", "T0049"],
    "T0106": ["T0049", "T0107"],
    "T0097": ["T0100", "T0103"],
    "T0100": ["T0103", "T0104"],
    "T0049": ["T0108"],
    "T0107": ["T0049"],
}

# 转换概率（领域知识）
TRANSITION_PROBS: dict[tuple[str, str], float] = {
    ("T0101", "T0102"): 0.8,
    ("T0101", "T0103"): 0.5,
    ("T0102", "T0105"): 0.7,
    ("T0102", "T0103"): 0.6,
    ("T0103", "T0104"): 0.7,
    ("T0103", "T0106"): 0.5,
    ("T0104", "T0105"): 0.6,
    ("T0104", "T0106"): 0.7,
    ("T0105", "T0106"): 0.9,
    ("T0105", "T0049"): 0.5,
    ("T0106", "T0049"): 0.7,
    ("T0106", "T0107"): 0.4,
    ("T0097", "T0100"): 0.6,
    ("T0097", "T0103"): 0.5,
    ("T0100", "T0103"): 0.7,
    ("T0100", "T0104"): 0.5,
    ("T0049", "T0108"): 0.4,
    ("T0107", "T0049"): 0.6,
}

# 反制措施知识库
COUNTERMEASURES: dict[str, dict] = {
    "T0101": {"action": "加强账户注册验证与异常检测", "priority": "medium"},
    "T0102": {"action": "监控异常网络结构形成", "priority": "medium"},
    "T0103": {"action": "内容审核与来源标注", "priority": "low"},
    "T0104": {"action": "限制可疑账户的分享频率", "priority": "medium"},
    "T0105": {"action": "监控协同账户集群活动", "priority": "high"},
    "T0106": {"action": "限制标记账户的放大能力", "priority": "high"},
    "T0107": {"action": "平台算法透明度审计", "priority": "medium"},
    "T0049": {"action": "部署信息洪水检测机制", "priority": "critical"},
    "T0108": {"action": "线下行动预警与快速响应", "priority": "critical"},
    "T0097": {"action": "专家身份核实机制", "priority": "medium"},
    "T0100": {"action": "可信来源保护与劫持检测", "priority": "high"},
}


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class ObservedTechnique:
    """观测到的 DISARM 技术。"""
    technique_id: str = ""
    tactic: str = ""
    name: str = ""
    belief: float = 0.0
    evidence: str = ""


@dataclass
class PredictedTechnique:
    """预测的下一步技术。"""
    technique_id: str = ""
    name: str = ""
    probability: float = 0.0


@dataclass
class Countermeasure:
    """反制建议。"""
    technique_id: str = ""
    action: str = ""
    priority: str = ""
    probability: float = 0.0


@dataclass
class PathScore:
    """攻击路径评分。"""
    depth: int = 0
    breadth: int = 0
    completeness: float = 0.0
    score: float = 0.0


@dataclass
class DisarmResult:
    """DISARM 分析结果。"""
    observed_techniques: list[ObservedTechnique] = field(default_factory=list)
    path_score: PathScore = field(default_factory=PathScore)
    predicted_next: list[PredictedTechnique] = field(default_factory=list)
    countermeasures: list[Countermeasure] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 证据→技术映射
# ---------------------------------------------------------------------------

def map_evidence_to_techniques(
    pack: EvidencePack,
    fusion: FusionResult,
    cfg: dict | None = None,
) -> list[ObservedTechnique]:
    """将上游证据映射到 DISARM 技术。"""
    if cfg is None:
        cfg = _load_disarm_config()
    thresholds = cfg.get("mapping_thresholds", {})
    observed: list[ObservedTechnique] = []

    # T0105: Coordinate Activity
    if pack.coordinated_accounts >= thresholds.get("coordinated_accounts_min", 5):
        info = TECHNIQUE_INFO["T0105"]
        observed.append(ObservedTechnique(
            technique_id="T0105", tactic=info["tactic"], name=info["name"],
            belief=fusion.manipulation.belief,
            evidence=f"{pack.coordinated_accounts} 个协同账户被检测到",
        ))

    # T0101: Create Fake Accounts
    if pack.features.high_automation_ratio >= thresholds.get("high_automation_ratio_min", 0.3):
        info = TECHNIQUE_INFO["T0101"]
        observed.append(ObservedTechnique(
            technique_id="T0101", tactic=info["tactic"], name=info["name"],
            belief=fusion.authenticity.belief,
            evidence=f"高自动化账户占比 {pack.features.high_automation_ratio:.0%}",
        ))

    # T0102: Develop Inauthentic Networks
    if pack.features.max_component_size >= thresholds.get("component_size_min", 10):
        info = TECHNIQUE_INFO["T0102"]
        observed.append(ObservedTechnique(
            technique_id="T0102", tactic=info["tactic"], name=info["name"],
            belief=fusion.manipulation.belief,
            evidence=f"最大协同组件包含 {pack.features.max_component_size} 个账户",
        ))

    # T0106: Amplify Existing Narrative
    if pack.features.burstiness >= thresholds.get("burstiness_min", 2.0):
        info = TECHNIQUE_INFO["T0106"]
        observed.append(ObservedTechnique(
            technique_id="T0106", tactic=info["tactic"], name=info["name"],
            belief=fusion.impact.belief,
            evidence=f"突发性指数 {pack.features.burstiness:.2f}",
        ))

    # T0104: Social Media Sharing
    if pack.features.bridge_ratio >= thresholds.get("bridge_ratio_min", 0.1):
        info = TECHNIQUE_INFO["T0104"]
        observed.append(ObservedTechnique(
            technique_id="T0104", tactic=info["tactic"], name=info["name"],
            belief=fusion.impact.belief,
            evidence=f"桥接节点占比 {pack.features.bridge_ratio:.0%}",
        ))

    # T0103: Post Content（基础行为，有传播活动即触发）
    if pack.claim_count > 0:
        info = TECHNIQUE_INFO["T0103"]
        observed.append(ObservedTechnique(
            technique_id="T0103", tactic=info["tactic"], name=info["name"],
            belief=max(fusion.manipulation.belief, 0.3),
            evidence=f"{pack.claim_count} 个共享对象被传播",
        ))

    return observed


# ---------------------------------------------------------------------------
# 路径评分
# ---------------------------------------------------------------------------

def _longest_chain(observed_ids: set[str], transitions: dict[str, list[str]]) -> int:
    """计算观测技术在转换图中的最长链长度（DFS）。"""
    memo: dict[str, int] = {}

    def dfs(node: str) -> int:
        if node in memo:
            return memo[node]
        best = 0
        for nxt in transitions.get(node, []):
            if nxt in observed_ids:
                best = max(best, 1 + dfs(nxt))
        memo[node] = best
        return best

    max_depth = 0
    for node in observed_ids:
        if node in transitions:
            max_depth = max(max_depth, 1 + dfs(node))
    return max(max_depth, 1) if observed_ids else 0


def _reachable_subgraph(observed_ids: set[str], transitions: dict[str, list[str]]) -> set[str]:
    """获取从观测节点可达的所有技术。"""
    reachable = set(observed_ids)
    queue = list(observed_ids)
    while queue:
        node = queue.pop(0)
        for nxt in transitions.get(node, []):
            if nxt not in reachable:
                reachable.add(nxt)
                queue.append(nxt)
    return reachable


def score_attack_path(
    observed: list[ObservedTechnique],
    cfg: dict | None = None,
) -> PathScore:
    """评分攻击路径。"""
    if cfg is None:
        cfg = _load_disarm_config()
    ps_cfg = cfg.get("path_scoring", {})

    if not observed:
        return PathScore()

    observed_ids = {t.technique_id for t in observed}
    depth = _longest_chain(observed_ids, TRANSITIONS)
    breadth = len({t.tactic for t in observed})
    reachable = _reachable_subgraph(observed_ids, TRANSITIONS)
    completeness = len(observed_ids) / max(len(reachable), 1)

    depth_norm = ps_cfg.get("depth_norm", 4)
    breadth_norm = ps_cfg.get("breadth_norm", 5)

    score = (
        ps_cfg.get("depth_weight", 0.4) * min(depth / depth_norm, 1.0)
        + ps_cfg.get("breadth_weight", 0.3) * min(breadth / breadth_norm, 1.0)
        + ps_cfg.get("completeness_weight", 0.3) * completeness
    ) * 100

    return PathScore(
        depth=depth,
        breadth=breadth,
        completeness=round(completeness, 4),
        score=round(score, 2),
    )


# ---------------------------------------------------------------------------
# 下一步预测
# ---------------------------------------------------------------------------

def predict_next_techniques(observed: list[ObservedTechnique]) -> list[PredictedTechnique]:
    """基于观测路径预测最可能的下一步技术。"""
    observed_ids = {t.technique_id for t in observed}
    candidates: dict[str, float] = {}

    for obs_id in observed_ids:
        for nxt in TRANSITIONS.get(obs_id, []):
            if nxt not in observed_ids:
                prob = TRANSITION_PROBS.get((obs_id, nxt), 0.5)
                candidates[nxt] = max(candidates.get(nxt, 0), prob)

    sorted_candidates = sorted(candidates.items(), key=lambda x: -x[1])[:3]
    return [
        PredictedTechnique(
            technique_id=tid,
            name=TECHNIQUE_INFO.get(tid, {}).get("name", "Unknown"),
            probability=round(prob, 4),
        )
        for tid, prob in sorted_candidates
    ]


# ---------------------------------------------------------------------------
# 反制建议
# ---------------------------------------------------------------------------

def recommend_countermeasures(
    predicted: list[PredictedTechnique],
    observed: list[ObservedTechnique],
) -> list[Countermeasure]:
    """基于预测和观测生成反制建议。"""
    recs: list[Countermeasure] = []

    # 优先为预测的下一步推荐反制
    for pred in predicted:
        if pred.technique_id in COUNTERMEASURES:
            cm = COUNTERMEASURES[pred.technique_id]
            recs.append(Countermeasure(
                technique_id=pred.technique_id,
                action=cm["action"],
                priority=cm["priority"],
                probability=pred.probability,
            ))

    # 补充当前观测到的高风险技术的反制
    for obs in observed:
        if obs.technique_id in COUNTERMEASURES and obs.belief > 0.6:
            cm = COUNTERMEASURES[obs.technique_id]
            if not any(r.technique_id == obs.technique_id for r in recs):
                recs.append(Countermeasure(
                    technique_id=obs.technique_id,
                    action=cm["action"],
                    priority=cm["priority"],
                    probability=obs.belief,
                ))

    # 按优先级排序
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    recs.sort(key=lambda r: (priority_order.get(r.priority, 9), -r.probability))
    return recs


# ---------------------------------------------------------------------------
# 主评分函数
# ---------------------------------------------------------------------------

def score_attack_path_full(
    evidence_pack: EvidencePack,
    phase_result: PhaseResult,
    fusion_result: FusionResult,
) -> DisarmResult:
    """执行完整 DISARM 攻击路径分析。"""
    cfg = _load_disarm_config()

    observed = map_evidence_to_techniques(evidence_pack, fusion_result, cfg)
    path = score_attack_path(observed, cfg)
    predicted = predict_next_techniques(observed)
    countermeasures = recommend_countermeasures(predicted, observed)

    return DisarmResult(
        observed_techniques=observed,
        path_score=path,
        predicted_next=predicted,
        countermeasures=countermeasures,
    )
