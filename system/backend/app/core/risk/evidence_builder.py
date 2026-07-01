"""证据构建器：从上游服务提取特征，构建统一证据包。

从 coordination、propagation、accounts 三个上游模块的输出中
提取结构化特征，供阶段检测、D-S 融合和 DISARM 评分使用。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class WindowFeatures:
    """单个滑动窗口内的特征向量。"""
    window_start: datetime | None = None
    window_end: datetime | None = None

    # 协同特征
    coordination_density: float = 0.0
    edge_symmetry_mean: float = 0.0
    max_component_size: int = 0
    component_count: int = 0
    coordinated_account_ratio: float = 0.0

    # 传播特征
    bridge_ratio: float = 0.0
    originator_concentration: float = 0.0
    burstiness: float = 0.0
    cross_cluster_spread: int = 0

    # 账户特征
    automation_entropy: float = 0.0
    high_automation_ratio: float = 0.0
    regularity_mean: float = 0.0

    # 阶段变化量（与前一窗口比较）
    automation_entropy_delta: float = 0.0


@dataclass
class EvidencePack:
    """统一证据包，汇聚所有上游特征。"""
    # 原始上游数据引用
    coord_data: dict = field(default_factory=dict)
    prop_data: dict = field(default_factory=dict)
    acct_data: list = field(default_factory=list)

    # 聚合特征
    features: WindowFeatures = field(default_factory=WindowFeatures)

    # 协同摘要
    coordinated_accounts: int = 0
    coordinated_pairs: int = 0
    coordinated_edges: int = 0

    # 传播摘要
    total_accounts: int = 0
    bridge_count: int = 0
    originator_count: int = 0
    amplifier_count: int = 0
    claim_count: int = 0
    top_claim_share_count: int = 0

    # 账户摘要
    high_automation_count: int = 0
    avg_automation_score: float = 0.0

    # 时间线
    timeline: list = field(default_factory=list)
    claims: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _gini(values: list[float]) -> float:
    """计算 Gini 系数（衡量分布集中度）。"""
    if not values or len(values) < 2:
        return 0.0
    sorted_v = sorted(values)
    n = len(sorted_v)
    total = sum(sorted_v)
    if total == 0:
        return 0.0
    cumsum = 0.0
    gini_sum = 0.0
    for i, v in enumerate(sorted_v):
        cumsum += v
        gini_sum += (2 * (i + 1) - n - 1) * v
    return gini_sum / (n * total)


def _shannon_entropy(values: list[float], n_bins: int = 5) -> float:
    """计算 Shannon 熵（将连续值分桶后计算）。"""
    if not values:
        return 0.0
    min_v, max_v = min(values), max(values)
    if max_v == min_v:
        return 0.0
    bin_width = (max_v - min_v) / n_bins
    bins = [0] * n_bins
    for v in values:
        idx = min(int((v - min_v) / bin_width), n_bins - 1)
        bins[idx] += 1
    total = len(values)
    entropy = 0.0
    for count in bins:
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    return entropy


def _burstiness(timestamps: list[datetime]) -> float:
    """计算突发性（事件间隔的变异系数 CV = std/mean）。"""
    if len(timestamps) < 3:
        return 0.0
    sorted_ts = sorted(timestamps)
    intervals = [
        (sorted_ts[i + 1] - sorted_ts[i]).total_seconds()
        for i in range(len(sorted_ts) - 1)
    ]
    if not intervals:
        return 0.0
    mean_interval = sum(intervals) / len(intervals)
    if mean_interval == 0:
        return 0.0
    variance = sum((x - mean_interval) ** 2 for x in intervals) / len(intervals)
    std = math.sqrt(variance)
    return std / mean_interval


# ---------------------------------------------------------------------------
# 主构建函数
# ---------------------------------------------------------------------------

def build_evidence_pack(
    coord_data: dict,
    prop_data: dict,
    acct_data: list[dict],
) -> EvidencePack:
    """从上游服务输出构建统一证据包。

    Parameters
    ----------
    coord_data : dict
        coordination_service.run_coordination_detection() 的返回值
    prop_data : dict
        propagation_service.analyze_propagation() 的返回值
    acct_data : list[dict]
        account_service.get_account_profiles() 的返回值
    """
    pack = EvidencePack(coord_data=coord_data, prop_data=prop_data, acct_data=acct_data)

    # ---- 协同特征 ----
    summary = coord_data.get("summary", {})
    network = coord_data.get("network", {})
    account_stats = coord_data.get("account_stats", [])

    pack.coordinated_accounts = summary.get("coordinated_accounts", 0)
    pack.coordinated_pairs = summary.get("total_pairs", 0)
    pack.coordinated_edges = summary.get("coordinated_edges", 0)

    n = pack.coordinated_accounts
    max_edges = n * (n - 1) / 2 if n > 1 else 1
    pack.features.coordination_density = pack.coordinated_edges / max_edges

    edges = network.get("edges", [])
    if edges:
        symmetry_scores = [e.get("edge_symmetry_score", 0) for e in edges]
        pack.features.edge_symmetry_mean = sum(symmetry_scores) / len(symmetry_scores)

    components = network.get("components", [])
    pack.features.component_count = len(components)
    if components:
        pack.features.max_component_size = max(c.get("size", 0) for c in components)

    total_accounts = len(acct_data) if acct_data else 1
    pack.features.coordinated_account_ratio = n / max(total_accounts, 1)

    # ---- 传播特征 ----
    graph = prop_data.get("graph", {})
    key_roles = prop_data.get("key_roles", {})
    claims = prop_data.get("claims", [])
    timeline = prop_data.get("timeline", [])

    node_count = graph.get("node_count", 0)
    bridges = key_roles.get("bridges", [])
    originators = key_roles.get("originators", [])
    amplifiers = key_roles.get("amplifiers", [])

    pack.bridge_count = len(bridges)
    pack.originator_count = len(originators)
    pack.amplifier_count = len(amplifiers)
    pack.total_accounts = node_count
    pack.claim_count = len(claims)
    pack.claims = claims
    pack.timeline = timeline

    if claims:
        pack.top_claim_share_count = max(c.get("share_count", 0) for c in claims)

    pack.features.bridge_ratio = len(bridges) / max(node_count, 1)

    out_degrees = [o.get("out_degree", 0) for o in originators]
    pack.features.originator_concentration = _gini(out_degrees)

    # 突发性：从时间线提取时间戳
    timestamps = []
    for item in timeline:
        ts = item.get("timestamp")
        if isinstance(ts, str):
            try:
                timestamps.append(datetime.fromisoformat(ts))
            except (ValueError, TypeError):
                pass
        elif isinstance(ts, datetime):
            timestamps.append(ts)
    pack.features.burstiness = _burstiness(timestamps)

    # 跨集群传播：协同组件中有传播活动的数量
    prop_node_ids = {n_item.get("id") for n_item in graph.get("nodes", [])}
    spread = 0
    for comp in components:
        comp_accounts = set(comp.get("accounts", []))
        if comp_accounts & prop_node_ids:
            spread += 1
    pack.features.cross_cluster_spread = spread

    # ---- 账户特征 ----
    if acct_data:
        auto_scores = [a.get("automation_score", 0) for a in acct_data]
        pack.avg_automation_score = sum(auto_scores) / len(auto_scores)
        pack.high_automation_count = sum(1 for s in auto_scores if s >= 60)
        pack.features.high_automation_ratio = pack.high_automation_count / len(acct_data)
        pack.features.automation_entropy = _shannon_entropy(auto_scores, n_bins=5)

        regularities = [a.get("regularity", 0) for a in acct_data]
        pack.features.regularity_mean = sum(regularities) / len(regularities)

    return pack
