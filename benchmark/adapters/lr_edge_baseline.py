#!/usr/bin/env python3
"""
LogisticRegression baseline for offline candidate-edge classification.

This adapter reads FOREST-format cascades. For each cascade it observes an
early prefix, then scores candidate parent -> future-child pairs. The true
parent is approximated as the immediately previous activated user in the
sequence, which makes this an offline edge-classifier baseline rather than a
strict prospective next-node predictor.
"""
import argparse
import json
import math
import os
from collections import Counter, defaultdict
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


K_LIST = (10, 50, 100)


def parse_cascade(line: str) -> List[Tuple[int, int]]:
    pairs: List[Tuple[int, int]] = []
    for raw in line.strip().split():
        parts = raw.split(",")
        if len(parts) != 2:
            continue
        try:
            pairs.append((int(parts[0]), int(parts[1])))
        except ValueError:
            continue
    return pairs


def load_cascades(path: str) -> List[List[Tuple[int, int]]]:
    cascades: List[List[Tuple[int, int]]] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            cascade = parse_cascade(line)
            if len(cascade) >= 4:
                cascades.append(cascade)
    return cascades


def load_social_graph(path: str) -> Tuple[set, Dict[int, int], Dict[int, int]]:
    edges = set()
    out_degree: Dict[int, int] = defaultdict(int)
    in_degree: Dict[int, int] = defaultdict(int)
    if not os.path.exists(path):
        return edges, out_degree, in_degree

    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            parts = line.strip().replace(",", " ").split()
            if len(parts) < 2:
                continue
            try:
                src, dst = int(parts[0]), int(parts[1])
            except ValueError:
                continue
            edges.add((src, dst))
            out_degree[src] += 1
            in_degree[dst] += 1
    return edges, out_degree, in_degree


def build_samples(
    cascades: Sequence[List[Tuple[int, int]]],
    social_edges: set,
    out_degree: Dict[int, int],
    in_degree: Dict[int, int],
    obs_ratio: float,
    max_future_per_cascade: int,
    max_candidates: int,
    inject_true_parent: bool,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict[str, float]]:
    X: List[List[float]] = []
    y: List[int] = []
    groups: List[int] = []
    group_id = 0
    total_queries = 0
    covered_by_observed = 0
    injected_true_parent = 0

    for cascade in cascades:
        users = [user for user, _ in cascade]
        times = [ts for _, ts in cascade]
        cut = max(2, int(len(cascade) * obs_ratio))
        if cut >= len(cascade):
            continue

        observed_users = unique_preserving_order(users[:cut])
        observed_counts = Counter(users[:cut])
        first_seen = {}
        last_seen = {}
        last_seen_time = {}
        for idx, user in enumerate(users[:cut]):
            first_seen.setdefault(user, idx)
            last_seen[user] = idx
            last_seen_time[user] = times[idx]

        end = min(len(cascade), cut + max_future_per_cascade)
        for idx in range(cut, end):
            child = users[idx]
            child_time = times[idx]
            true_parent = users[idx - 1]
            total_queries += 1

            candidates = list(observed_users)
            if true_parent in candidates:
                covered_by_observed += 1
            elif inject_true_parent:
                candidates.append(true_parent)
                injected_true_parent += 1
            candidates = limit_candidates(candidates, true_parent, max_candidates)

            for parent in candidates:
                if parent == child:
                    continue
                X.append(
                    edge_features(
                        parent,
                        child,
                        child_time,
                        first_seen,
                        last_seen,
                        last_seen_time,
                        observed_counts,
                        social_edges,
                        out_degree,
                        in_degree,
                        cut,
                    )
                )
                y.append(1 if parent == true_parent else 0)
                groups.append(group_id)
            group_id += 1

    meta = {
        "queries": float(total_queries),
        "candidate_recall_observed": covered_by_observed / max(total_queries, 1),
        "offline_true_parent_injected": float(injected_true_parent),
    }
    return np.asarray(X, dtype=float), np.asarray(y, dtype=int), np.asarray(groups, dtype=int), meta


def unique_preserving_order(values: Iterable[int]) -> List[int]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def limit_candidates(candidates: List[int], true_parent: int, limit: int) -> List[int]:
    if len(candidates) <= limit:
        return candidates
    limited = candidates[-limit:]
    if true_parent in candidates and true_parent not in limited:
        limited[-1] = true_parent
    return limited


def edge_features(
    parent: int,
    child: int,
    child_time: int,
    first_seen: Dict[int, int],
    last_seen: Dict[int, int],
    last_seen_time: Dict[int, int],
    observed_counts: Counter,
    social_edges: set,
    out_degree: Dict[int, int],
    in_degree: Dict[int, int],
    cut: int,
) -> List[float]:
    parent_last_idx = last_seen.get(parent)
    parent_first_idx = first_seen.get(parent)
    parent_observed = parent_last_idx is not None
    if parent_observed:
        # Parent timestamps after the observation window are intentionally not used.
        parent_time = last_seen_time.get(parent, child_time)
        lag = max(child_time - parent_time, 0)
        recency = max(cut - parent_last_idx, 0)
        first_seen_rank = (parent_first_idx or 0) / max(cut, 1)
    else:
        lag = 0
        recency = cut + 1
        first_seen_rank = 1.0

    return [
        1.0 if parent_observed else 0.0,
        1.0 if (parent, child) in social_edges else 0.0,
        math.log1p(out_degree.get(parent, 0)),
        math.log1p(in_degree.get(parent, 0)),
        math.log1p(out_degree.get(child, 0)),
        math.log1p(in_degree.get(child, 0)),
        math.log1p(observed_counts.get(parent, 0)),
        math.log1p(lag),
        math.log1p(recency),
        first_seen_rank,
    ]


def grouped_hits_map(
    y_true: np.ndarray,
    prob: np.ndarray,
    groups: np.ndarray,
    total_queries: int,
) -> Dict[str, Optional[float]]:
    metrics: Dict[str, Optional[float]] = {}
    unique_groups = np.unique(groups)
    valid = max(total_queries, len(unique_groups))
    hit_counts = {k: 0 for k in K_LIST}
    ap_sums = {k: 0.0 for k in K_LIST}
    ndcg_sums = {k: 0.0 for k in K_LIST}
    reciprocal_rank_sum = 0.0

    for group in unique_groups:
        mask = groups == group
        labels = y_true[mask]
        scores = prob[mask]
        ranked = labels[np.argsort(-scores)]
        relevant_positions = np.flatnonzero(ranked == 1)
        if len(relevant_positions):
            reciprocal_rank_sum += 1.0 / float(relevant_positions[0] + 1)
        for k in K_LIST:
            top_k = ranked[:k]
            if top_k.sum() > 0:
                hit_counts[k] += 1
            relevant_seen = 0
            precision_sum = 0.0
            for idx, label in enumerate(top_k, start=1):
                if label == 1:
                    relevant_seen += 1
                    precision_sum += relevant_seen / idx
            ap_sums[k] += precision_sum / max(labels.sum(), 1)
            ndcg_sums[k] += ndcg_at_k(top_k, int(labels.sum()))

    metrics["mrr"] = reciprocal_rank_sum / valid if valid else None
    for k in K_LIST:
        metrics[f"hits@{k}"] = hit_counts[k] / valid if valid else None
        metrics[f"map@{k}"] = ap_sums[k] / valid if valid else None
        metrics[f"ndcg@{k}"] = ndcg_sums[k] / valid if valid else None
    return metrics


def ndcg_at_k(labels: np.ndarray, relevant_count: int) -> float:
    if relevant_count <= 0:
        return 0.0
    dcg = 0.0
    for idx, label in enumerate(labels, start=1):
        if label == 1:
            dcg += 1.0 / np.log2(idx + 1)
    ideal_hits = min(relevant_count, len(labels))
    idcg = sum(1.0 / np.log2(idx + 1) for idx in range(1, ideal_hits + 1))
    return float(dcg / idcg) if idcg else 0.0


def safe_auc(y_true: np.ndarray, prob: np.ndarray) -> Optional[float]:
    try:
        return float(roc_auc_score(y_true, prob))
    except ValueError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", required=True)
    parser.add_argument("--obs_ratio", type=float, default=0.3)
    parser.add_argument("--max_future_per_cascade", type=int, default=50)
    parser.add_argument("--max_candidates", type=int, default=100)
    parser.add_argument("--inject_true_parent", action="store_true")
    args = parser.parse_args()

    train_path = os.path.join(args.data_dir, "cascade.txt")
    test_path = os.path.join(args.data_dir, "cascadetest.txt")
    edge_path = os.path.join(args.data_dir, "edges.txt")
    train_cascades = load_cascades(train_path)
    test_cascades = load_cascades(test_path)
    social_edges, out_degree, in_degree = load_social_graph(edge_path)

    X_train, y_train, _, train_meta = build_samples(
        train_cascades,
        social_edges,
        out_degree,
        in_degree,
        args.obs_ratio,
        args.max_future_per_cascade,
        args.max_candidates,
        args.inject_true_parent,
    )
    X_test, y_test, groups_test, test_meta = build_samples(
        test_cascades,
        social_edges,
        out_degree,
        in_degree,
        args.obs_ratio,
        args.max_future_per_cascade,
        args.max_candidates,
        args.inject_true_parent,
    )

    if len(set(y_train.tolist())) < 2 or len(set(y_test.tolist())) < 2:
        print("[LR] ERROR: not enough positive/negative samples")
        return

    clf = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000, class_weight="balanced"),
    )
    clf.fit(X_train, y_train)
    prob = clf.predict_proba(X_test)[:, 1]
    ranking_metrics = grouped_hits_map(y_test, prob, groups_test, int(test_meta["queries"]))

    result = {
        "model": "LR_EdgeClassifier",
        "dataset": os.path.basename(args.data_dir),
        "mode": "offline_edge_classifier_injected" if args.inject_true_parent else "observed_candidate_edge_classifier",
        "obs_ratio": args.obs_ratio,
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "queries_train": int(train_meta["queries"]),
        "queries_test": int(test_meta["queries"]),
        "candidate_recall_observed": float(test_meta["candidate_recall_observed"]),
        "offline_true_parent_injected": int(test_meta["offline_true_parent_injected"]),
        "auc": safe_auc(y_test, prob),
        "average_precision": float(average_precision_score(y_test, prob)),
        "msle": None,
        "mae": None,
        "note": (
            "Uses future child for offline edge classification; true parent injection is disabled by default. "
            "Candidate recall reports how often the proxy true parent is present in observed candidates."
        ),
    }
    result.update(ranking_metrics)
    print(
        "[LR] "
        f"AUC={result['auc']:.4f} AP={result['average_precision']:.4f} "
        f"Hits@100={result['hits@100']:.4f}"
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
