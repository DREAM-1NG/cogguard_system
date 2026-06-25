from __future__ import annotations

import json
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Tuple

import networkx as nx
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    mean_absolute_error,
    mean_squared_error,
    mean_squared_log_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

from .analysis import _depths, _influence_scores
from .models import PropagationEvent, sorted_nodes_by_time


def run_prediction(events: List[PropagationEvent], output_dir: str, observation_ratio: float = 0.3) -> Dict:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path_report = path_prediction(events, observation_ratio)
    size_report = size_prediction(events, observation_ratio)
    report = {"observation_ratio": observation_ratio, "path_prediction": path_report, "size_prediction": size_report}
    (out / "prediction_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return report


def path_prediction(events: List[PropagationEvent], observation_ratio: float) -> Dict:
    X, y, groups = [], [], []
    group_id = 0
    total_queries = 0
    covered_by_observed = 0
    injected_true_parent = 0
    for event in events:
        graph = event.to_graph()
        ordered = [n.node_id for n in sorted_nodes_by_time(event)]
        if len(ordered) < 4:
            continue
        cut = max(2, int(len(ordered) * observation_ratio))
        observed = set(ordered[:cut])
        future = ordered[cut : min(len(ordered), cut + max(5, len(ordered) // 3))]
        future = future[:1000]
        depths = _depths(graph.subgraph(observed).copy())
        observed_graph = graph.subgraph(observed).copy()
        pagerank = _influence_scores(observed_graph) if observed else {}
        for child in future:
            true_parent = event.nodes[child].parent_id
            candidates = list(observed)
            total_queries += 1
            if true_parent and true_parent in candidates:
                covered_by_observed += 1
            if true_parent and true_parent not in candidates and true_parent in graph.nodes:
                candidates.append(true_parent)
                injected_true_parent += 1
            limited_candidates = _limit_candidates(candidates, true_parent, 20)
            for parent in limited_candidates:
                if parent == child:
                    continue
                X.append(_edge_features(event, graph, parent, child, depths, pagerank))
                y.append(1 if parent == true_parent else 0)
                groups.append(group_id)
            group_id += 1
    if len(set(y)) < 2 or len(y) < 20:
        return {"status": "skipped", "reason": "not enough positive/negative candidate edges"}
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=int)
    groups = np.asarray(groups, dtype=int)
    train_mask, test_mask = _group_train_test_mask(groups, test_size=0.3, random_state=42)
    X_train, X_test = X[train_mask], X[test_mask]
    y_train, y_test = y[train_mask], y[test_mask]
    g_test = groups[test_mask]
    if len(set(y_train.tolist())) < 2 or len(set(y_test.tolist())) < 2:
        return {"status": "skipped", "reason": "group split lacks positive/negative candidate edges"}
    clf = LogisticRegression(max_iter=1000, class_weight="balanced")
    clf.fit(X_train, y_train)
    prob = clf.predict_proba(X_test)[:, 1]
    hits_k, map_k = _hits_and_map_at_k(y_test, prob, g_test)
    return {
        "status": "ok",
        "samples": int(len(y)),
        "positive_rate": float(y.mean()),
        "candidate_recall_observed": float(covered_by_observed / max(total_queries, 1)),
        "offline_true_parent_injected": int(injected_true_parent),
        "note": "Offline edge-classification baseline: future child is known and true parent may be injected into candidates.",
        "auc": _safe_auc(y_test, prob),
        "average_precision": float(average_precision_score(y_test, prob)),
        **hits_k,
        **map_k,
    }


def size_prediction(events: List[PropagationEvent], observation_ratio: float) -> Dict:
    if len(events) < 4:
        return {"status": "skipped", "reason": "need at least 4 events for train/test size prediction"}
    X, y = [], []
    for event in events:
        graph = event.to_graph()
        ordered = [n.node_id for n in sorted_nodes_by_time(event)]
        cut = max(1, int(len(ordered) * observation_ratio))
        observed = set(ordered[:cut])
        X.append(_cascade_features(graph, observed))
        y.append(len(ordered))
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=max(0.25, 1 / len(events)), random_state=42)
    model = RandomForestRegressor(n_estimators=200, random_state=42, min_samples_leaf=1)
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    rmse = float(mean_squared_error(y_test, pred) ** 0.5)
    mape = float(np.mean(np.abs((y_test - pred) / np.maximum(y_test, 1))) * 100)
    pred_clipped = np.maximum(pred, 0)
    msle = float(mean_squared_log_error(y_test, pred_clipped))
    return {
        "status": "ok",
        "train_events": int(len(y_train)),
        "test_events": int(len(y_test)),
        "mae": float(mean_absolute_error(y_test, pred)),
        "rmse": rmse,
        "msle": msle,
        "mape_percent": mape,
        "r2": float(r2_score(y_test, pred)) if len(y_test) > 1 else None,
        "examples": [
            {"true_size": float(t), "predicted_size": float(p)} for t, p in zip(y_test[:10], pred[:10])
        ],
    }


def _edge_features(event: PropagationEvent, graph: nx.DiGraph, parent: str, child: str, depths: Dict[str, int], pagerank: Dict[str, float]) -> List[float]:
    p = event.nodes.get(parent)
    c = event.nodes.get(child)
    dt = 0.0
    if p and c and p.timestamp and c.timestamp:
        dt = max((c.timestamp - p.timestamp).total_seconds() / 60.0, 0.0)
    return [
        float(graph.out_degree(parent) if parent in graph else 0),
        float(graph.in_degree(parent) if parent in graph else 0),
        float(depths.get(parent, 0)),
        float(pagerank.get(parent, 0.0)),
        float(np.log1p(dt)),
        1.0 if p and c and p.user_id == c.user_id else 0.0,
    ]


def _cascade_features(graph: nx.DiGraph, observed: set) -> List[float]:
    sub = graph.subgraph(observed).copy()
    depths = _depths(sub)
    out_degrees = [d for _, d in sub.out_degree()]
    timestamps = [data.get("timestamp") for _, data in sub.nodes(data=True) if data.get("timestamp")]
    duration = 0.0
    if timestamps:
        duration = max((max(timestamps) - min(timestamps)).total_seconds() / 60.0, 0.0)
    return [
        float(sub.number_of_nodes()),
        float(sub.number_of_edges()),
        float(max(depths.values(), default=0)),
        float(max(out_degrees, default=0)),
        float(np.mean(out_degrees) if out_degrees else 0.0),
        float(sum(1 for d in out_degrees if d == 0) / max(len(out_degrees), 1)),
        float(duration),
        float(sub.number_of_nodes() / max(duration, 1.0)),
    ]


def _limit_candidates(candidates: List[str], true_parent: str | None, limit: int) -> List[str]:
    if len(candidates) <= limit:
        return candidates
    limited = candidates[:limit]
    if true_parent and true_parent in candidates and true_parent not in limited:
        limited[-1] = true_parent
    return limited


def _group_train_test_mask(groups: np.ndarray, test_size: float, random_state: int) -> Tuple[np.ndarray, np.ndarray]:
    unique_groups = np.unique(groups)
    train_groups, test_groups = train_test_split(unique_groups, test_size=test_size, random_state=random_state)
    train_set = set(train_groups.tolist())
    test_set = set(test_groups.tolist())
    return np.isin(groups, list(train_set)), np.isin(groups, list(test_set))


def _hits_and_map_at_k(y_true: np.ndarray, prob: np.ndarray, groups: np.ndarray, ks: Tuple[int, ...] = (10, 50, 100)) -> Tuple[Dict, Dict]:
    """Compute Hits@K and MAP@K grouped by query (child node)."""
    unique_groups = np.unique(groups)
    hits = {k: 0 for k in ks}
    ap_sums = {k: 0.0 for k in ks}
    valid_queries = 0

    for g in unique_groups:
        mask = groups == g
        g_y = y_true[mask]
        g_prob = prob[mask]
        if g_y.sum() == 0:
            continue
        valid_queries += 1
        ranked_idx = np.argsort(-g_prob)
        ranked_labels = g_y[ranked_idx]
        for k in ks:
            top_k = ranked_labels[:k]
            if top_k.sum() > 0:
                hits[k] += 1
            relevant_seen = 0
            precision_sum = 0.0
            for i, label in enumerate(top_k):
                if label == 1:
                    relevant_seen += 1
                    precision_sum += relevant_seen / (i + 1)
            ap_sums[k] += precision_sum / max(g_y.sum(), 1)

    if valid_queries == 0:
        return (
            {f"hits@{k}": None for k in ks},
            {f"map@{k}": None for k in ks},
        )
    return (
        {f"hits@{k}": float(hits[k] / valid_queries) for k in ks},
        {f"map@{k}": float(ap_sums[k] / valid_queries) for k in ks},
    )


def _safe_auc(y_true, prob):
    try:
        return float(roc_auc_score(y_true, prob))
    except Exception:
        return None
