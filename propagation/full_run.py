from __future__ import annotations

import csv
import heapq
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, mean_absolute_error, mean_squared_error, r2_score, roc_auc_score
from sklearn.model_selection import train_test_split

from .analysis import (
    _clean_text,
    _depths,
    _influence_scores,
    build_narrative,
    ignition_points,
    key_paths,
    participant_table,
    summarize_event,
    write_event_report,
)
from .loaders import build_weibo_rumor_event, iter_weibo_rumor_rows
from .models import PropagationEvent, sorted_nodes_by_time
from .prediction import _cascade_features, _edge_features
from .visualization import build_dashboard_from_artifacts


def run_weibo_rumor_full(
    data_dir: str,
    output_dir: str,
    observation_ratio: float = 0.3,
    path_sample_limit: int = 750_000,
    path_future_per_event: int = 200,
    progress_every: int = 100,
    max_events: Optional[int] = None,
) -> Dict:
    """Run a full Weibo Rumor analysis without materializing all events at once."""

    root = Path(data_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    participants_path = out / "participants.csv"
    ignitions_path = out / "ignition_points.csv"
    paths_path = out / "paths.json"

    summaries: List[Dict] = []
    paths: Dict[str, List[Dict]] = {}
    role_counts: Counter = Counter()
    unique_users = set()
    total_ignitions = 0
    top_participants: List[Tuple[float, int, Dict]] = []
    top_ignitions: List[Tuple[float, int, Dict]] = []
    heap_seq = 0
    largest_event: Optional[PropagationEvent] = None
    largest_participants = pd.DataFrame()
    largest_ignitions = pd.DataFrame()
    largest_paths: List[Dict] = []
    size_X: List[List[float]] = []
    size_y: List[int] = []
    path_X: List[List[float]] = []
    path_y: List[int] = []
    sampled_path_candidates = 0
    processed_events = 0
    processed_nodes = 0

    write_participant_header = True
    write_ignition_header = True
    rng = random.Random(42)

    rows = list(iter_weibo_rumor_rows(data_dir, max_events=max_events))
    total_events = len(rows)
    total_referenced_posts = sum(len(row[2]) for row in rows)

    for idx, row in enumerate(rows, 1):
        event = build_weibo_rumor_event(root, row)
        if not event.nodes:
            continue
        processed_events += 1
        processed_nodes += len(event.nodes)

        summary = summarize_event(event)
        summaries.append(summary)
        participants = participant_table(event)
        ignitions = ignition_points(event)
        event_paths = key_paths(event)
        paths[event.event_id] = event_paths

        if not participants.empty:
            participants.to_csv(participants_path, index=False, mode="w" if write_participant_header else "a", header=write_participant_header)
            write_participant_header = False
            role_counts.update(participants["role"].value_counts().to_dict())
            unique_users.update(participants["user_id"].astype(str).tolist())
            for _, item in participants.iterrows():
                heap_seq += 1
                row_dict = _jsonable_row(item.to_dict())
                score = float(row_dict.get("out_degree_sum") or 0) + float(row_dict.get("pagerank_sum") or 0)
                _heap_push(top_participants, (score, heap_seq, row_dict), 50)

        if not ignitions.empty:
            ignitions.to_csv(ignitions_path, index=False, mode="w" if write_ignition_header else "a", header=write_ignition_header)
            write_ignition_header = False
            total_ignitions += len(ignitions)
            for _, item in ignitions.iterrows():
                heap_seq += 1
                row_dict = _jsonable_row(item.to_dict())
                score = float(row_dict.get("score") or 0)
                _heap_push(top_ignitions, (score, heap_seq, row_dict), 50)

        sampled_path_candidates = _append_prediction_samples(
            event=event,
            observation_ratio=observation_ratio,
            size_X=size_X,
            size_y=size_y,
            path_X=path_X,
            path_y=path_y,
            path_sample_limit=path_sample_limit,
            path_future_per_event=path_future_per_event,
            rng=rng,
            sampled_seen=sampled_path_candidates,
        )

        if largest_event is None or len(event.nodes) > len(largest_event.nodes):
            largest_event = event
            largest_participants = participants.copy()
            largest_ignitions = ignitions.copy()
            largest_paths = event_paths

        if progress_every and idx % progress_every == 0:
            print(
                f"[weibo-full] {idx}/{total_events} events, {processed_nodes} nodes processed",
                file=sys.stderr,
                flush=True,
            )

    if write_participant_header:
        _write_empty_csv(participants_path, ["event_id", "user_id", "post_count", "out_degree_sum", "pagerank_sum", "role"])
    if write_ignition_header:
        _write_empty_csv(ignitions_path, ["event_id", "node_id", "user_id", "timestamp", "reason", "score"])

    prediction_report = {
        "observation_ratio": observation_ratio,
        "path_prediction": _fit_path_prediction(path_X, path_y, sampled_path_candidates, path_sample_limit, processed_events),
        "size_prediction": _fit_size_prediction(size_X, size_y),
    }
    (out / "prediction_report.json").write_text(json.dumps(prediction_report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    summary = {
        "dataset": "weibo_rumor",
        "mode": "full-streaming",
        "dataset_events": processed_events,
        "event_index_rows": total_events,
        "referenced_post_ids": total_referenced_posts,
        "focus_event_id": largest_event.event_id if largest_event else None,
        "totals": {
            "nodes": int(sum(item["node_count"] for item in summaries)),
            "edges": int(sum(item["edge_count"] for item in summaries)),
            "participants": len(unique_users),
            "ignition_points": total_ignitions,
        },
        "event_summaries": summaries,
        "narrative": build_narrative(summaries, _top_dataframe(top_ignitions)),
    }
    (out / "analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    paths_path.write_text(json.dumps(paths, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    top_participants_df = _top_dataframe(top_participants)
    top_ignitions_df = _top_dataframe(top_ignitions)
    if largest_event:
        write_event_report(
            out / "event_report.md",
            largest_event,
            summaries,
            largest_participants,
            largest_ignitions,
            {largest_event.event_id: largest_paths},
        )
    build_dashboard_from_artifacts(
        output_dir,
        summaries,
        largest_event,
        top_participants_df,
        top_ignitions_df,
        dict(role_counts),
        len(unique_users),
        total_ignitions,
        prediction_report,
    )
    return summary


def _append_prediction_samples(
    event: PropagationEvent,
    observation_ratio: float,
    size_X: List[List[float]],
    size_y: List[int],
    path_X: List[List[float]],
    path_y: List[int],
    path_sample_limit: int,
    path_future_per_event: int,
    rng: random.Random,
    sampled_seen: int,
) -> int:
    graph = event.to_graph()
    ordered = [node.node_id for node in sorted_nodes_by_time(event)]
    if len(ordered) < 2:
        return sampled_seen

    cut = max(1, int(len(ordered) * observation_ratio))
    observed_ordered = ordered[:cut]
    observed = set(observed_ordered)
    size_X.append(_cascade_features(graph, observed))
    size_y.append(len(ordered))

    if len(ordered) < 4:
        return sampled_seen
    future = ordered[cut : min(len(ordered), cut + max(5, len(ordered) // 3))]
    future = future[:path_future_per_event]
    observed_graph = graph.subgraph(observed).copy()
    depths = _depths(observed_graph)
    pagerank = _influence_scores(observed_graph) if observed else {}
    base_candidates = observed_ordered[:20]

    for child in future:
        true_parent = event.nodes[child].parent_id
        candidates = list(base_candidates)
        if true_parent and true_parent not in candidates and true_parent in graph.nodes:
            candidates.append(true_parent)
        for parent in candidates:
            if parent == child:
                continue
            sample = _edge_features(event, graph, parent, child, depths, pagerank)
            label = 1 if parent == true_parent else 0
            sampled_seen += 1
            if len(path_y) < path_sample_limit:
                path_X.append(sample)
                path_y.append(label)
            else:
                replace_at = rng.randrange(sampled_seen)
                if replace_at < path_sample_limit:
                    path_X[replace_at] = sample
                    path_y[replace_at] = label
    return sampled_seen


def _fit_path_prediction(path_X: List[List[float]], path_y: List[int], candidates_seen: int, sample_limit: int, events: int) -> Dict:
    if len(set(path_y)) < 2 or len(path_y) < 20:
        return {"status": "skipped", "reason": "not enough positive/negative candidate edges", "sampled_candidates": len(path_y)}
    X = np.asarray(path_X, dtype=float)
    y = np.asarray(path_y, dtype=int)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)
    clf = LogisticRegression(max_iter=1000, class_weight="balanced")
    clf.fit(X_train, y_train)
    prob = clf.predict_proba(X_test)[:, 1]
    return {
        "status": "ok",
        "events_considered": events,
        "candidate_edges_seen_estimate": int(candidates_seen),
        "sample_limit": int(sample_limit),
        "samples": int(len(y)),
        "positive_rate": float(y.mean()),
        "auc": _safe_auc(y_test, prob),
        "average_precision": float(average_precision_score(y_test, prob)),
        "note": "Full event set traversed; candidate edges were reservoir-sampled for bounded memory.",
    }


def _fit_size_prediction(size_X: List[List[float]], size_y: List[int]) -> Dict:
    if len(size_y) < 4:
        return {"status": "skipped", "reason": "need at least 4 events for train/test size prediction"}
    X = np.asarray(size_X, dtype=float)
    y = np.asarray(size_y, dtype=float)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=max(0.25, 1 / len(size_y)), random_state=42)
    model = RandomForestRegressor(n_estimators=200, random_state=42, min_samples_leaf=1)
    model.fit(X_train, y_train)
    pred = model.predict(X_test)
    return {
        "status": "ok",
        "train_events": int(len(y_train)),
        "test_events": int(len(y_test)),
        "mae": float(mean_absolute_error(y_test, pred)),
        "rmse": float(mean_squared_error(y_test, pred) ** 0.5),
        "mape_percent": float(np.mean(np.abs((y_test - pred) / np.maximum(y_test, 1))) * 100),
        "r2": float(r2_score(y_test, pred)) if len(y_test) > 1 else None,
        "examples": [{"true_size": float(t), "predicted_size": float(p)} for t, p in zip(y_test[:10], pred[:10])],
    }


def _heap_push(heap: List[Tuple[float, int, Dict]], item: Tuple[float, int, Dict], limit: int) -> None:
    heapq.heappush(heap, item)
    if len(heap) > limit:
        heapq.heappop(heap)


def _top_dataframe(heap: List[Tuple[float, int, Dict]]) -> pd.DataFrame:
    rows = [row for _, _, row in sorted(heap, key=lambda item: item[0], reverse=True)]
    return pd.DataFrame(rows)


def _jsonable_row(row: Dict) -> Dict:
    clean = {}
    for key, value in row.items():
        if pd.isna(value):
            clean[key] = None
        elif hasattr(value, "isoformat"):
            clean[key] = value.isoformat()
        elif isinstance(value, np.generic):
            clean[key] = value.item()
        else:
            clean[key] = value
    return clean


def _write_empty_csv(path: Path, columns: List[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)


def _safe_auc(y_true, prob):
    try:
        return float(roc_auc_score(y_true, prob))
    except Exception:
        return None
